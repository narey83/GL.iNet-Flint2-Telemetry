local M = {}

function M.read(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local value = f:read("*a")
    f:close()
    return value
end

function M.number(path)
    return tonumber(M.read(path))
end

function M.cpu(text)
    local values, total = {}, 0
    local line = (text or ""):match("^cpu%s+([^\n]+)")
    if not line then return nil end
    for value in line:gmatch("%d+") do
        values[#values + 1] = tonumber(value)
    end
    -- guest/guest_nice are already included in user/nice.
    for i = 1, math.min(8, #values) do total = total + values[i] end
    if #values < 4 then return nil end
    return {total = total, idle = values[4] + (values[5] or 0)}
end

function M.cpu_percent(previous, current)
    if not previous or not current then return nil end
    local elapsed = current.total - previous.total
    local idle = current.idle - previous.idle
    if elapsed <= 0 or idle < 0 or idle > elapsed then return nil end
    return 100 * (elapsed - idle) / elapsed
end

function M.memory(text)
    local values = {}
    for key, value in (text or ""):gmatch("([%w_]+):%s+(%d+)") do
        values[key] = tonumber(value) * 1024
    end
    local total, available = values.MemTotal, values.MemAvailable
    if not total or total == 0 or not available then return {} end
    return {memory_total_bytes = total, memory_available_bytes = available,
        memory_used_percent = 100 * (total - available) / total}
end

function M.rate(previous, current, elapsed)
    if not previous or not current or elapsed <= 0 or current < previous then return nil end
    return (current - previous) * 8 / elapsed
end

function M.valid_interface(value)
    return type(value) == "string" and #value > 0 and #value <= 15 and
        value:match("^[%w_.:-]+$") ~= nil
end

function M.quote(value)
    return "'" .. value:gsub("'", "'\\''") .. "'"
end

function M.validate(config)
    config.format = config.format or "gelf"
    assert(config.format == "gelf" or config.format == "otlp_http_json" or config.format=="ecs_ndjson", "invalid export format")
    assert(type(config.endpoint) == "string" and
        config.endpoint:match("^https://[%w.-]+[:%d]*/[%w/_-]+$"), "endpoint must be an HTTPS URL")
    assert(type(config.ca_file) == "string" and config.ca_file:match("^/[%w/_.-]+$"), "invalid CA path")
    for key, range in pairs({interval = {10, 3600}, inventory_interval = {60, 86400}, max_queue = {32, 2048}}) do
        local n = tonumber(config[key])
        assert(n and n == math.floor(n) and n >= range[1] and n <= range[2], "invalid " .. key)
        config[key] = n
    end
    local function interfaces(key, maximum)
        config[key] = config[key] or {}
        assert(type(config[key]) == "table" and #config[key] <= maximum, "invalid " .. key .. " list")
        local seen = {}
        for _, name in ipairs(config[key]) do
            assert(M.valid_interface(name) and not seen[name], "invalid or duplicate " .. key .. " interface")
            seen[name] = true
        end
    end
    interfaces("interface", 32)
    for _, option in ipairs({"router_logs", "flow_capture", "firewall_events"}) do
        config[option] = config[option] or "1"
        assert(config[option] == "0" or config[option] == "1", "invalid " .. option)
    end
    config.wan_interface = config.wan_interface or "auto"
    assert(M.valid_interface(config.wan_interface), "invalid WAN interface")
    interfaces("flow_lan_interface", 8)
    interfaces("vpn_interface", 8)
    config.capture_filter=config.capture_filter or "auto"
    assert(not config.capture_filter:find("[\r\n]"),"invalid capture filter")
    for _, key in ipairs({"headers_file","metrics_headers_file"}) do
        if config[key] then assert(config[key]:match("^/[%w/_.-]+$"),"invalid header file path") end
    end
    config.metrics_enabled = config.metrics_enabled or "0"
    assert(config.metrics_enabled == "0" or config.metrics_enabled == "1", "invalid metrics_enabled")
    config.metric_events_enabled = config.metric_events_enabled or "1"
    assert(config.metric_events_enabled == "0" or config.metric_events_enabled == "1", "invalid metric_events_enabled")
    config.metrics_max_queue = tonumber(config.metrics_max_queue or "8")
    assert(config.metrics_max_queue and config.metrics_max_queue == math.floor(config.metrics_max_queue) and
        config.metrics_max_queue >= 1 and config.metrics_max_queue <= 32, "invalid metrics_max_queue")
    config.metrics_ca_file = config.metrics_ca_file or config.ca_file
    if config.metrics_enabled == "1" then
        assert(type(config.metrics_endpoint) == "string" and
            config.metrics_endpoint:match("^https://[%w.-]+[:%d]*/[%w/_-]+$"), "metrics_endpoint must be an HTTPS URL")
        assert(config.metrics_ca_file:match("^/[%w/_.-]+$"), "invalid metrics CA path")
    end
    return config
end

function M.otlp_result(status, text, rejected_field)
    local json = require("cjson")
    local code = tonumber(status) or 0
    if code ~= 200 then
        if code >= 400 and code < 600 and code ~= 429 and code ~= 502 and code ~= 503 and code ~= 504 then
            return "drop", 0
        end
        return "retry", 0
    end
    local ok, result = pcall(json.decode, text or "")
    if not ok or type(result) ~= "table" then return "retry", 0 end
    local partial = result.partialSuccess
    if partial == nil then return "accepted", 0 end
    if type(partial) ~= "table" then return "retry", 0 end
    local rejected = tonumber(partial[rejected_field] or 0)
    if not rejected or rejected ~= rejected or rejected < 0 or rejected > 9007199254740991 or
        rejected ~= math.floor(rejected) then return "retry", 0 end
    return "accepted", rejected
end

function M.canonical_name(name)
    if name:find(".",1,true) then return name end
    local names={flint2="flint2.component",agent_version="agent.version",agent_start_id="agent.ephemeral_id"}
    return names[name] or "flint2."..name
end

function M.gelf_encode(record)
    local json=require("cjson")
    local projection={}
    for key,value in pairs(record) do
        local name=key:sub(1,1)=="_" and ("_"..M.canonical_name(key:sub(2)):gsub("%.","_")) or key
        if type(value)=="table" then value=#value==1 and value[1] or json.encode(value) end
        if type(value)=="boolean" then value=value and 1 or 0 end
        projection[name]=value
    end
    projection._ecs_document=json.encode(M.ecs_document(record))
    local encoded = json.encode(projection)
    -- Force metric_value to a JSON floating-point token even for whole numbers,
    -- so a new Graylog index never infers a long and truncates later fractions.
    return (encoded:gsub('("_flint2_metric_value":)(%-?%d+)([,}])', '%1%2.0%3', 1))
end

function M.ecs_document(record)
    local timestamp=record.timestamp or 0
    local whole=math.floor(timestamp)
    local document={['@timestamp']=os.date("!%Y-%m-%dT%H:%M:%S",whole)..
        string.format(".%03dZ",math.floor((timestamp-whole)*1000)),message=record.short_message or "Flint2 telemetry",
        ecs={version="8.17.0"},observer={name=record.host,type="router"}}
    local function put(name,value)
        local node=document
        local parts={}
        for part in name:gmatch("[^.]+") do parts[#parts+1]=part end
        for i=1,#parts-1 do node[parts[i]]=node[parts[i]] or {};node=node[parts[i]] end
        node[parts[#parts]]=value
    end
    for key,value in pairs(record) do
        if key:sub(1,1)=="_" then
            put(M.canonical_name(key:sub(2)),value)
        end
    end
    return document
end

function M.any_value(value)
    local kind=type(value)
    if kind=="string" then return {stringValue=value} end
    if kind=="number" then
        assert(value==value and math.abs(value)<math.huge,"Non-finite OTLP value")
        if value==math.floor(value) and math.abs(value)<=9007199254740991 then
            return {intValue=string.format("%.0f",value)}
        end
        return {doubleValue=value}
    end
    if kind=="boolean" then return {boolValue=value} end
    assert(kind=="table","Unsupported OTLP attribute type")
    local values={}
    if #value>0 then
        for _, item in ipairs(value) do values[#values+1]=M.any_value(item) end
        return {arrayValue={values=values}}
    end
    for key,item in pairs(value) do values[#values+1]={key=key,value=M.any_value(item)} end
    return {kvlistValue={values=values}}
end

function M.otlp(records)
    local first = records[1]
    local logs = {}
    for _, record in ipairs(records) do
        local attributes = {}
        for key, value in pairs(record) do
            if key:sub(1, 1) == "_" then
                local name=M.canonical_name(key:sub(2))
                attributes[#attributes+1]={key=name,value=M.any_value(value)}
            end
        end
        logs[#logs + 1] = {timeUnixNano = string.format("%.0f", record.timestamp * 1000000000),
            observedTimeUnixNano = string.format("%.0f", record.timestamp * 1000000000),
            severityNumber = ({[0]=21,[1]=21,[2]=21,[3]=17,[4]=13,[5]=9,[6]=9,[7]=5})[record.level or 6],
            severityText = ({[0]="FATAL",[1]="FATAL",[2]="FATAL",[3]="ERROR",[4]="WARN",[5]="INFO",[6]="INFO",[7]="DEBUG"})[record.level or 6],
            body = M.any_value(M.ecs_document(record)),
            attributes = attributes}
    end
    return {resourceLogs = {{resource = {attributes = {
        {key = "service.name", value = {stringValue = "flint2-telemetry"}},
        {key = "service.version", value = {stringValue = first._agent_version}},
        {key = "host.name", value = {stringValue = first.host}},
        {key = "os.type", value = {stringValue = "linux"}}
    }}, scopeLogs = {{scope = {name = "flint2.agent", version = first._agent_version}, logRecords = logs}}}}}
end

function M.lease_records(text)
    local records = {}
    for line in (text or ""):gmatch("[^\n]+") do
        local expiry, mac, ip, name = line:match("^(%d+)%s+(%S+)%s+(%S+)%s+(%S+)")
        if expiry and #mac == 17 and mac:match("^[%x:]+$") and ip:match("^[%d.]+$") then
            records[#records + 1] = {device_mac = mac:lower(), device_ip = ip,
                device_name = name ~= "*" and name:sub(1, 128) or ip,
                inventory_source = "dhcp", lease_expiry_raw = tonumber(expiry)}
            if #records == 256 then break end
        end
    end
    return records
end

function M.enqueue(queue, event, maximum)
    local dropped = 0
    if #queue >= maximum then table.remove(queue, 1); dropped = 1 end
    queue[#queue + 1] = event
    return dropped
end

return M
