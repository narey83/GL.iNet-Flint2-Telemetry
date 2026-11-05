-- Compose an atomic nft JSON transaction. All new terminal actions are logs;
-- existing fw4 matches/verdicts remain owned and evaluated by fw4.
local M = {}
local owned = {forward="flint2_evt_fwd", drop_from_wan="flint2_evt_drop",
    reject_from_wan="flint2_evt_reject"}

-- Re-evaluating random generators, maps with side effects or time-dependent
-- expressions could log a denial that the original rule does not then match.
-- Admit only the read-only expression forms needed by fw4 zone rules.
local packet_meta = {nfproto=true, l4proto=true, iifname=true, oifname=true,
    iif=true, oif=true, ibrname=true, obrname=true, pkttype=true, protocol=true,
    length=true, mark=true, skuid=true, skgid=true}
local payload_keys = {protocol=true, field=true, base=true, offset=true, len=true}
local containers = {set=true, range=true, concat=true,
    ["&"]=true, ["|"]=true, ["^"]=true, ["<<"]=true, [">>"]=true}
local function pure(value)
    if type(value)=="string" or type(value)=="number" or type(value)=="boolean" then return true end
    if type(value)~="table" then return false end
    if value.meta then return packet_meta[value.meta.key] == true end
    if value.payload then
        for key, item in pairs(value.payload) do
            if not payload_keys[key] or
                (type(item)~="string" and type(item)~="number") then return false end
        end
        return true
    end
    if value.ct then return value.ct.key=="state" or value.ct.key=="status" end
    if value.prefix then return type(value.prefix.addr)=="string" and type(value.prefix.len)=="number" end
    for key, item in pairs(value) do
        if type(key)~="number" and not containers[key] then return false end
        if not pure(item) then return false end
    end
    return true
end

function M.build(snapshot, active, wan, vpn)
    local chains, rules, commands = {}, {}, {}
    for _, entry in ipairs(assert(snapshot.nftables, "Missing nftables state")) do
        local item = entry.chain or entry.rule
        if item and item.family == "inet" and item.table == "fw4" then
            if entry.chain then chains[item.name] = true
            else rules[item.chain] = rules[item.chain] or {}; table.insert(rules[item.chain], item) end
        end
    end
    local function object(chain) return {family="inet", table="fw4", name=chain} end
    local function command(action, kind, item) commands[#commands+1] = {[action]={[kind]=item}} end
    local function own_jump(rule, target)
        return rule.comment == "!flint2" and #rule.expr == 1 and
            rule.expr[1].jump and rule.expr[1].jump.target == target
    end
    for _, parent in ipairs({"forward", "drop_from_wan", "reject_from_wan"}) do
        local target = owned[parent]
        for _, rule in ipairs(rules[parent] or {}) do
            if own_jump(rule, target) then
                command("delete", "rule", {family="inet", table="fw4", chain=parent, handle=rule.handle})
            end
        end
    end
    for _, parent in ipairs({"forward", "drop_from_wan", "reject_from_wan"}) do
        local target = owned[parent]
        if chains[target] then
            command("flush", "chain", object(target)); command("delete", "chain", object(target))
        end
    end
    if not active then return commands end
    assert(chains.forward, "Missing fw4 forward chain")
    local function interface_match(name)
        assert(type(name)=="string" and #name>0 and #name<=15 and name:match("^[%w_.:-]+$"), "Invalid device")
        return {match={op="==", left={meta={key="iifname"}}, right=name}}
    end
    local ipv4 = {match={op="==", left={meta={key="nfproto"}}, right="ipv4"}}
    local function rule(chain, expressions)
        command("add", "rule", {family="inet", table="fw4", chain=chain, expr=expressions})
    end
    local function connect(parent, target)
        command("insert", "rule", {family="inet", table="fw4", chain=parent,
            comment="!flint2", expr={{jump={target=target}}}})
    end
    local function ct(key, value) return {match={op="in", left={ct={key=key}}, right=value}} end
    command("add", "chain", object(owned.forward))
    rule(owned.forward, {ipv4, interface_match(wan), ct("state", "new"), ct("status", "dnat"),
        {limit={rate=50, burst=250, per="second"}}, {log={prefix="FLINT2 FORWARD wan in: "}}})
    for _, device in ipairs(vpn) do
        rule(owned.forward, {ipv4, interface_match(device), ct("state", "new"),
            {limit={rate=30, burst=5, per="minute"}}, {log={prefix="FLINT2 FORWARD vpn in: "}}})
    end
    connect("forward", owned.forward)
    for _, verdict in ipairs({"drop", "reject"}) do
        local parent = verdict .. "_from_wan"
        local target, observations = owned[parent], {}
        for _, original in ipairs(rules[parent] or {}) do
            if not own_jump(original, target) then
                local expressions, terminal = {ipv4, interface_match(wan)}, false
                for index, expression in ipairs(original.expr) do
                    if expression.match then
                        assert(not terminal, "Match follows fw4 verdict")
                        assert(pure(expression.match.left) and pure(expression.match.right),
                            "Unsupported stateful fw4 match")
                        expressions[#expressions+1] = expression
                    elseif expression.counter or expression.log then
                        -- Observation-only state is never copied or reset.
                    elseif expression[verdict] ~= nil or (verdict == "reject" and
                        expression.jump and expression.jump.target == "handle_reject") then
                        assert(index == #original.expr, "Non-terminal fw4 verdict")
                        terminal = true
                    else error("Unsupported expression in fw4 " .. parent) end
                end
                assert(terminal, "Missing terminal verdict in fw4 " .. parent)
                expressions[#expressions+1] = {limit={rate=1, burst=5, per="second"}}
                expressions[#expressions+1] = {log={prefix="FLINT2 " .. verdict:upper() .. " wan in: "}}
                observations[#observations+1] = expressions
            end
        end
        -- Empty/inactive zone chains produce no denial observations.
        if #observations > 0 then
            if verdict == "reject" then
                assert(#(rules.handle_reject or {}) > 0, "Missing fw4 reject handler")
                for _, handler in ipairs(rules.handle_reject) do
                    local rejected = false
                    for index, expression in ipairs(handler.expr) do
                        if expression.reject ~= nil then
                            assert(index == #handler.expr, "Non-terminal fw4 rejection")
                            rejected = true
                        else
                            assert(expression.match or expression.counter or expression.log,
                                "Unsupported fw4 reject handler")
                            if expression.match then
                                assert(pure(expression.match.left) and pure(expression.match.right),
                                    "Unsupported fw4 reject match")
                            end
                        end
                    end
                    assert(rejected, "Non-rejecting fw4 handler rule")
                end
            end
            command("add", "chain", object(target))
            for _, expressions in ipairs(observations) do rule(target, expressions) end
            connect(parent, target)
        end
    end
    return commands
end
return M
