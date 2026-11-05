local metrics = require("flint2.metrics")
local core = require("flint2.core")
local count = 0
local function check(condition, why) count = count + 1; assert(condition, why) end
local function sample(time, rx, tx, index)
    return {{timestamp = time, host = "router", _boot_id = "boot", _agent_start_id = "agent", _agent_version = "0.2.0",
        _event_kind = "system", _uptime_seconds = 100, _memory_total_bytes = 1000, _memory_available_bytes = 400,
        _temperature_celsius = 46.5, _conntrack_count = 30, _conntrack_max = 100, _queue_dropped_total = 0},
        {_event_kind = "interface", _interface = "wan", _interface_index = index or 1,
            _rx_bytes = rx, _tx_bytes = tx, _rx_errors = 0, _tx_errors = 0, _rx_dropped = 0, _tx_dropped = 0},
        {_event_kind = "device", _device_ip = "192.168.0.2", _device_mac = "aa:bb:cc:dd:ee:ff"}}
end
local function lookup(payload, name)
    for _, metric in ipairs(payload.resourceMetrics[1].scopeMetrics[1].metrics) do
        if metric.name == name then return metric end
    end
end
local exporter = metrics.new()
local p, size = exporter:build(sample(1000.25, 100, 200), "cpu0 10 0 20 70 0 0 0 0 10 0")
check(size > 0, "native points generated")
local net = lookup(p, "system.network.io")
check(net.unit == "By" and net.sum.aggregationTemporality == 2 and net.sum.isMonotonic, "cumulative monotonic network bytes")
check(net.sum.dataPoints[1].asInt == "100", "int64 serialized as string")
check(net.sum.dataPoints[1].startTimeUnixNano == "1000250000000", "unknown start equals first sample")
check(net.sum.dataPoints[1].timeUnixNano == "1000250000000", "exact timestamp construction")
check(lookup(p, "system.cpu.utilization") == nil, "first CPU sample has no invented utilization")
local memory = lookup(p, "system.memory.usage")
check(not memory.sum.isMonotonic and memory.unit == "By", "memory uses non-monotonic cumulative sum")
local values = {}
for _, point in ipairs(memory.sum.dataPoints) do values[point.attributes[1].value.stringValue] = tonumber(point.asInt) end
check(values.used == 600 and values.available == 400, "memory states sum to limit")
local native_events = metrics.events(p)
check(#native_events == size, "every native point has a Graylog metric event")
local rx_event
for _, event in ipairs(native_events) do
    if event.metric_name == "system.network.io" and event.metric_attribute_network_io_direction == "receive" then rx_event = event end
    check(event.device_ip == nil and event.device_mac == nil, "inventory identifiers excluded from metric dimensions")
end
check(rx_event.metric_value == 100 and rx_event.metric_unit == "By", "Graylog preserves value and units")
check(rx_event.metric_start_time_unix_nano == "1000250000000" and rx_event.metric_monotonic == 1,
    "Graylog preserves counter semantics")
check(core.gelf_encode({_metric_value=21}):find('21.0',1,true) ~= nil, "whole metric values force a floating-point index type")
check(core.gelf_encode({_metric_value=0.25}):find('0.25',1,true) ~= nil, "fractional metric values retained")
check(core.gelf_encode({_metric_value=-2}):find('-2.0',1,true) ~= nil, "negative whole metrics remain floating point")
p = exporter:build(sample(1010.25, 120, 250), "cpu0 20 0 40 140 0 0 0 0 20 0")
net = lookup(p, "system.network.io")
check(net.sum.dataPoints[1].startTimeUnixNano == "1000250000000", "start retained across increases")
local cpu = lookup(p, "system.cpu.utilization")
check(cpu.unit == "1" and #cpu.gauge.dataPoints == 7, "per-CPU, per-mode utilization gauge")
local total, user = 0
for _, point in ipairs(cpu.gauge.dataPoints) do
    total = total + point.asDouble
    for _, attr in ipairs(point.attributes) do
        if attr.key == "cpu.mode" and attr.value.stringValue == "user" then user = point.asDouble end
    end
end
check(math.abs(total - 1) < 0.000001 and user == 0.1, "CPU normalization excludes duplicate guest time")
p = exporter:build(sample(1020.25, 5, 280), "cpu0 1 0 2 7 0 0 0 0")
net = lookup(p, "system.network.io")
check(net.sum.dataPoints[1].startTimeUnixNano == "1020250000000", "decreased counter starts new cumulative sequence")
check(net.sum.dataPoints[2].startTimeUnixNano == "1000250000000", "independent transmit sequence preserved")
check(lookup(p, "system.cpu.utilization") == nil, "CPU reset skips invalid deltas")
p = exporter:build(sample(1030.25, 500, 600, 2))
check(lookup(p, "system.network.io").sum.dataPoints[1].startTimeUnixNano == "1030250000000", "ifindex change detects recreated interface")
exporter:build({sample(1040.25, 0, 0)[1]})
p = exporter:build(sample(1050.25, 700, 800, 2))
check(lookup(p, "system.network.io").sum.dataPoints[1].startTimeUnixNano == "1050250000000", "reappearing interface starts a fresh sequence")
p = exporter:build(sample(1000, 800, 900, 2))
check(lookup(p, "system.network.io").sum.dataPoints[1].startTimeUnixNano == "1000000000000", "clock rollback resets cumulative start")
p = metrics.new():build(sample(1100, 800, 900))
check(lookup(p, "system.network.io").sum.dataPoints[1].startTimeUnixNano == "1100000000000", "agent restart does not reuse an old start time")
p = exporter:build(sample(1200, -1, 9007199254740992))
check(lookup(p, "system.network.io") == nil, "negative and unsafe int64 counters omitted")
local disposition, rejected = core.otlp_result("200", '{"partialSuccess":{"rejectedDataPoints":"3"}}', "rejectedDataPoints")
check(disposition == "accepted" and rejected == 3, "OTLP partial success counts rejected points without replay")
check(core.otlp_result("200", '{}', "rejectedDataPoints") == "accepted", "empty OTLP success object")
check(core.otlp_result("503", '', "rejectedDataPoints") == "retry", "retry transient failures")
check(core.otlp_result("429", '', "rejectedDataPoints") == "retry", "retry throttling")
check(core.otlp_result("400", '', "rejectedDataPoints") == "drop", "discard permanently rejected batch")
check(core.otlp_result("302", '', "rejectedDataPoints") == "retry", "redirect is not success")
check(core.otlp_result("200", 'bad json', "rejectedDataPoints") == "retry", "invalid acknowledgement retained")
check(core.otlp_result("200", '{"partialSuccess":{"rejectedDataPoints":-1}}', "rejectedDataPoints") == "retry", "invalid rejection count")
check(core.otlp_result("200", '{"partialSuccess":{"rejectedDataPoints":"1e999"}}', "rejectedDataPoints") == "retry", "infinite rejection count")
local c = {endpoint="https://graylog.test/gelf", ca_file="/etc/cert", interval=30, inventory_interval=300,
    max_queue=512, interface={"wan"}, metrics_enabled="1", metrics_endpoint="http://unsafe.test/v1/metrics"}
check(not pcall(core.validate,c), "native exporter requires TLS")
c.metrics_endpoint = "https://collector.test/v1/metrics"
check(core.validate(c).metrics_max_queue == 8, "independent bounded metrics queue defaults")
c.metrics_max_queue = 33
check(not pcall(core.validate,c), "native queue is bounded")
print("PASS: " .. count .. " native metrics checks")
