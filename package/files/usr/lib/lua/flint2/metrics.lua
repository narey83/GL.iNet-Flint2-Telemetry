-- OTLP/HTTP JSON metrics. Collection state advances independently of delivery.
local M = {}
local MAX_INTEGER = 9007199254740991

local function nanos(seconds)
    local whole = math.floor(seconds)
    local fraction = math.floor((seconds - whole) * 1000000000)
    return string.format("%.0f%09d", whole, fraction)
end
M.nanos = nanos

-- Graylog stores each native point as a searchable event; OTLP stays available
-- as the independent, standards-based wire format for metrics backends.
function M.events(payload)
    local events = {}
    for _, resource in ipairs(payload.resourceMetrics) do
        for _, scope in ipairs(resource.scopeMetrics) do
            for _, metric in ipairs(scope.metrics) do
                local data = metric.sum or metric.gauge
                for _, point in ipairs(data.dataPoints) do
                    local event = {metric_name = metric.name, metric_unit = metric.unit,
                        metric_description = metric.description, metric_value = point.asDouble or tonumber(point.asInt),
                        metric_time_unix_nano = point.timeUnixNano,
                        metric_start_time_unix_nano = point.startTimeUnixNano,
                        metric_type = metric.sum and "sum" or "gauge"}
                    if metric.sum then
                        event.metric_temporality = "cumulative"
                        event.metric_monotonic = data.isMonotonic and 1 or 0
                    end
                    for _, attr in ipairs(point.attributes or {}) do
                        event["metric_attribute_" .. attr.key:gsub("%.", "_")] =
                            attr.value.stringValue or tonumber(attr.value.intValue)
                    end
                    events[#events + 1] = event
                end
            end
        end
    end
    return events
end

local function finite(value)
    return type(value) == "number" and value == value and value > -math.huge and value < math.huge
end

local function attributes(values)
    local keys, result = {}, {}
    for key in pairs(values or {}) do keys[#keys + 1] = key end
    table.sort(keys)
    for _, key in ipairs(keys) do
        local value = values[key]
        result[#result + 1] = {key = key, value = type(value) == "number" and
            {intValue = string.format("%.0f", value)} or {stringValue = value}}
    end
    return #result > 0 and result or nil
end

local function cpu_samples(text)
    local result = {}
    for line in (text or ""):gmatch("[^\n]+") do
        local id, rest = line:match("^cpu(%d+)%s+(.+)")
        if id then
            local raw = {}
            for value in rest:gmatch("%d+") do raw[#raw + 1] = tonumber(value) end
            if #raw >= 4 then
                result[id] = {user = raw[1], nice = raw[2], system = raw[3], idle = raw[4],
                    iowait = raw[5] or 0, interrupt = (raw[6] or 0) + (raw[7] or 0), steal = raw[8] or 0}
            end
        end
    end
    return result
end

function M.new()
    local counters, previous_cpus = {}, {}
    local exporter = {}

    function exporter:build(records, cpu_text)
        assert(#records > 0, "metrics need a sample")
        local first = records[1]
        local now = nanos(first.timestamp)
        local metrics, by_name, seen = {}, {}, {}
        local point_count = 0

        local function add(name, unit, description, value, attrs, instrument, monotonic, identity)
            if not finite(value) then return end
            if instrument == "sum" and (math.abs(value) > MAX_INTEGER or value ~= math.floor(value)) then return end
            local point = {timeUnixNano = now, attributes = attributes(attrs)}
            if instrument == "sum" then point.asInt = string.format("%.0f", value)
            else point.asDouble = value end
            if instrument == "sum" then
                if monotonic and value < 0 then return end
                local key = name
                for _, attr in ipairs(point.attributes or {}) do
                    key = key .. "\0" .. attr.key .. "=" .. (attr.value.stringValue or attr.value.intValue)
                end
                local previous = counters[key]
                -- The first observation has an unknown start: start == sample time.
                -- A decrease, recreated interface or clock rollback begins a new sequence.
                local reset = not previous or previous.identity ~= identity or
                    first.timestamp <= previous.time or (monotonic and value < previous.value)
                point.startTimeUnixNano = reset and now or previous.start
                counters[key] = {value = value, time = first.timestamp, start = point.startTimeUnixNano, identity = identity}
                seen[key] = true
            end
            local metric = by_name[name]
            if not metric then
                metric = {name = name, unit = unit, description = description}
                metric[instrument or "gauge"] = {dataPoints = {}}
                if instrument == "sum" then
                    metric.sum.aggregationTemporality = 2 -- CUMULATIVE
                    metric.sum.isMonotonic = monotonic
                end
                by_name[name], metrics[#metrics + 1] = metric, metric
            end
            local points = metric[instrument or "gauge"].dataPoints
            points[#points + 1] = point
            point_count = point_count + 1
        end

        for _, record in ipairs(records) do
            local kind = record._event_kind
            if kind == "system" then
                add("system.uptime", "s", "Time since host boot", record._uptime_seconds)
                local total, available = record._memory_total_bytes, record._memory_available_bytes
                if finite(total) and finite(available) and total > 0 and available >= 0 and available <= total then
                    add("system.memory.limit", "By", "Total physical memory", total, nil, "sum", false)
                    for state, value in pairs({used = total - available, available = available}) do
                        local attrs = {["system.memory.state"] = state}
                        add("system.memory.usage", "By", "Memory by state", value, attrs, "sum", false)
                        add("system.memory.utilization", "1", "Fraction of memory by state", value / total, attrs)
                    end
                end
                for _, window in ipairs({1, 5, 15}) do
                    add("flint2.system.load_average", "{task}", "Linux runnable and uninterruptible task load average",
                        record["_load_" .. window], {["flint2.window.minutes"] = window})
                end
                for _, entry in ipairs({
                    {"flint2.temperature", "Cel", "SoC thermal zone temperature", "_temperature_celsius"},
                    {"flint2.conntrack.count", "{connection}", "Connection tracking entries", "_conntrack_count"},
                    {"flint2.conntrack.limit", "{connection}", "Connection tracking capacity", "_conntrack_max"},
                    {"flint2.logs.queue.depth", "{record}", "Queued Graylog or OTLP log records", "_queue_depth"},
                    {"flint2.logs.delivery.failed", "1", "Last log delivery failed (1) or succeeded (0)", "_delivery_failed"},
                    {"flint2.metrics.queue.depth", "{batch}", "Queued native metric snapshots", "_metrics_queue_depth"},
                    {"flint2.metrics.delivery.failed", "1", "Last metrics delivery failed (1) or succeeded (0)", "_metrics_delivery_failed"}
                }) do add(entry[1], entry[2], entry[3], record[entry[4]]) end
                for _, entry in ipairs({
                    {"flint2.logs.dropped", "{record}", "Log records discarded since agent start", "_queue_dropped_total"},
                    {"flint2.metrics.dropped", "{batch}", "Metric batches discarded since agent start", "_metrics_dropped_total"},
                    {"flint2.metrics.rejected", "{point}", "Metric points rejected by the receiver since agent start", "_metrics_rejected_total"}
                }) do add(entry[1], entry[2], entry[3], record[entry[4]], nil, "sum", true, first._agent_start_id) end
            elseif kind == "interface" then
                for _, direction in ipairs({{"rx", "receive"}, {"tx", "transmit"}}) do
                    local prefix = "_" .. direction[1]
                    local attrs = {["network.interface.name"] = record._interface, ["network.io.direction"] = direction[2]}
                    add("system.network.io", "By", "Network bytes transferred", record[prefix .. "_bytes"], attrs, "sum", true, record._interface_index)
                    add("system.network.errors", "{error}", "Network errors", record[prefix .. "_errors"], attrs, "sum", true, record._interface_index)
                    add("system.network.packet.dropped", "{packet}", "Network packets dropped", record[prefix .. "_dropped"], attrs, "sum", true, record._interface_index)
                end
            elseif kind == "wan" then
                add("flint2.wan.up", "1", "WAN up (1) or down (0)", record._wan_up)
                add("flint2.wan.uptime", "s", "Current WAN session uptime", record._wan_uptime_seconds)
            elseif kind == "inventory" then
                add("flint2.dhcp.lease_records", "{record}", "DHCP inventory records, not online device count", record._dhcp_lease_records)
            end
        end
        local cpus = cpu_samples(cpu_text)
        local cpu_ids = {}
        for id in pairs(cpus) do cpu_ids[#cpu_ids + 1] = id end
        table.sort(cpu_ids, function(a, b) return tonumber(a) < tonumber(b) end)
        for _, id in ipairs(cpu_ids) do
            local states, before = cpus[id], previous_cpus[id]
            if before then
                local total, valid = 0, true
                for state, value in pairs(states) do
                    local delta = value - before[state]
                    if delta < 0 then valid = false end
                    total = total + delta
                end
                if valid and total > 0 then
                    for _, state in ipairs({"user", "nice", "system", "idle", "iowait", "interrupt", "steal"}) do
                        add("system.cpu.utilization", "1", "Per logical CPU time fraction over the sample interval",
                            (states[state] - before[state]) / total, {["cpu.logical_number"] = tonumber(id), ["cpu.mode"] = state})
                    end
                end
            end
        end
        previous_cpus = cpus
        for key in pairs(counters) do if not seen[key] then counters[key] = nil end end
        local resource = {attributes = attributes({["service.name"] = "flint2-telemetry",
            ["service.version"] = first._agent_version, ["host.name"] = first.host,
            ["os.type"] = "linux", ["flint2.boot.id"] = first._boot_id})}
        return {resourceMetrics = {{resource = resource, scopeMetrics = {{
            scope = {name = "flint2.agent", version = first._agent_version}, metrics = metrics}}}}}, point_count
    end
    return exporter
end

return M
