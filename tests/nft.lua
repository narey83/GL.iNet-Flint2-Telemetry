local nft = require("flint2.nft")
local json = require("cjson")
local snapshot = {nftables={}}
local function chain(name)
    snapshot.nftables[#snapshot.nftables+1] = {chain={family="inet", table="fw4", name=name}}
end
local function rule(name, expressions, comment, handle)
    local value = {family="inet", table="fw4", chain=name, expr=expressions, comment=comment, handle=handle}
    snapshot.nftables[#snapshot.nftables+1] = {rule=value}
    return value
end
chain("forward"); chain("drop_from_wan"); chain("reject_from_wan"); chain("handle_reject")
rule("handle_reject", {{reject=json.null}})
local filter = {match={op="==", left={payload={protocol="ip", field="saddr"}},
    right={prefix={addr="198.51.100.0", len=24}}}}
local denial = rule("drop_from_wan", {filter, {counter={packets=5, bytes=500}}, {drop=json.null}})
local rejecting = rule("reject_from_wan", {filter, {jump={target="handle_reject"}}})
local commands = nft.build(snapshot, true, "eth0", {"wgtest"})
local seen = {drop=false, reject=false}
for _, command in ipairs(commands) do
    local value = command.add and command.add.rule
    if value and (value.chain=="flint2_evt_drop" or value.chain=="flint2_evt_reject") then
        assert(value.expr[3] == filter, "deny condition was not preserved")
        for _, expression in ipairs(value.expr) do
            assert(not expression.drop and not expression.reject and not expression.accept and
                not expression.counter and not expression.jump, "copied a verdict or state")
        end
        seen[value.chain:match("flint2_evt_(.+)")] = true
    end
end
assert(seen.drop and seen.reject, "missing deny observations")
assert(denial.expr[2].counter.packets==5, "changed an existing counter")
assert(not pcall(nft.build, snapshot, true, 'bad"device', {}), "unsafe interface accepted")
rejecting.expr={{accept=json.null}}
assert(not pcall(nft.build, snapshot, true, "eth0", {}), "unsupported verdict accepted")
rejecting.expr={filter, {jump={target="handle_reject"}}}
denial.expr={filter, {limit={rate=1, per="second"}}, {drop=json.null}}
assert(not pcall(nft.build, snapshot, true, "eth0", {}), "stateful deny match copied")
denial.expr={filter, {drop=json.null}}
chain("flint2_evt_fwd")
rule("forward", {{jump={target="flint2_evt_fwd"}}}, "!flint2", 123)
rule("forward", {{jump={target="unrelated"}}}, "!flint2", 456)
commands = nft.build(snapshot, false, "auto", {})
assert(#commands==3 and commands[1].delete.rule.handle==123, "cleanup touched an unrelated rule")
snapshot={nftables={{chain={family="inet", table="fw4", name="forward"}},
    {chain={family="inet", table="fw4", name="reject_from_wan"}}}}
commands=nft.build(snapshot, true, "eth0", {})
for _, command in ipairs(commands) do
    assert(not (command.insert and command.insert.rule.chain=="reject_from_wan"),
        "empty chain created denial observations")
end
print("PASS: nft match preservation, safe cleanup, unsupported policies and empty WAN chains")
