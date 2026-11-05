local core = require("flint2.core")
local count = 0
local function check(condition, message)
    count = count + 1
    assert(condition, message)
end
local function near(a, b) return math.abs(a - b) < 0.000001 end
local before = core.cpu("cpu  10 0 20 70 0 0 0 0 10 0\ncpu0 1 2 3 4")
local after = core.cpu("cpu  20 0 40 140 0 0 0 0 20 0")
check(before.total == 100, "guest CPU time must not be counted twice")
check(near(core.cpu_percent(before, after), 30), "CPU delta")
check(core.cpu_percent(after, before) == nil, "CPU reset")
check(core.cpu_percent(before, before) == nil, "zero CPU elapsed")
check(core.cpu("broken") == nil, "missing CPU stats")
local mem = core.memory("MemTotal: 1000 kB\nMemAvailable: 400 kB\n")
check(mem.memory_total_bytes == 1024000, "memory units")
check(near(mem.memory_used_percent, 60), "memory available")
check(next(core.memory("MemTotal: 0 kB")) == nil, "invalid memory stats")
check(core.rate(100, 200, 2) == 400, "bit rate")
check(core.rate(200, 100, 2) == nil, "counter reset")
check(core.rate(100, 200, 0) == nil, "zero elapsed")
check(core.rate(nil, 200, 2) == nil, "first rate sample")
local devices = core.lease_records("43200 aa:bb:cc:dd:ee:ff 192.168.0.2 phone *\n0 11:22:33:44:55:66 192.168.0.3 * *\nbad line\n")
check(#devices == 2, "lease parser tolerates malformed lines")
check(devices[2].device_name == "192.168.0.3", "unnamed device")
check(devices[1].lease_expiry_raw == 43200, "lease expiry retained without assuming online status")
local q = {}
check(core.enqueue(q, "a", 2) == 0, "initial enqueue")
core.enqueue(q, "b", 2)
check(core.enqueue(q, "c", 2) == 1 and #q == 2 and q[1] == "b", "bounded queue discards oldest")
check(core.valid_interface("pppoe-wan"), "PPPoE interface")
check(not core.valid_interface("../../etc/passwd"), "reject path traversal")
check(not core.valid_interface("eth0\ninjected"), "reject config injection")
local function config()
    return {endpoint = "https://collector.example.invalid/gelf",
        ca_file = "/etc/flint2/collector.crt", interval = "30", inventory_interval = "300",
        max_queue = "512", interface = {"br-lan"}}
end
check(core.validate(config()).interval == 30, "UCI numeric conversion")
for key, value in pairs({endpoint = "http://example.com/gelf", ca_file = "/etc/cert\ninjected",
    interval = "0", inventory_interval = "1", max_queue = "100000"}) do
    local c = config(); c[key] = value
    check(not pcall(core.validate, c), "reject invalid " .. key)
end
local c = config(); c.interface = {"br-lan; reboot"}
check(not pcall(core.validate, c), "reject interface command injection")
local otlp = core.otlp({{timestamp = 1793907000.25, host = "router", short_message = "Test",
    _agent_version = "0.1.0", _event_kind = "system", _temperature_celsius = 46.5}})
local resource = otlp.resourceLogs[1]
check(resource.resource.attributes[1].value.stringValue == "flint2-telemetry", "OTLP service resource")
local log = resource.scopeLogs[1].logRecords[1]
check(log.timeUnixNano == "1793907000250000128" or log.timeUnixNano == "1793907000249999872" or
    log.timeUnixNano == "1793907000250000000", "OTLP timestamp encoded as decimal string")
local message
for _, value in ipairs(log.body.kvlistValue.values) do
    if value.key=="message" then message=value.value.stringValue end
end
check(log.severityNumber == 9 and message == "Test", "OTLP structured ECS log body")
local numeric = false
for _, attribute in ipairs(log.attributes) do
    if attribute.key == "flint2.temperature_celsius" then numeric = attribute.value.doubleValue == 46.5 end
end
check(numeric, "OTLP preserves numeric attribute types")
for _, key in ipairs({"interface", "flow_lan_interface", "vpn_interface"}) do
    local c = config(); c[key] = nil
    check(#core.validate(c)[key] == 0, "empty " .. key .. " must remain empty")
    c = config(); c[key] = {"eth0", "eth0"}
    check(not pcall(core.validate, c), "reject duplicate " .. key)
    c = config(); c[key] = {"eth0; reboot"}
    check(not pcall(core.validate, c), "reject invalid " .. key)
    c = config(); c[key] = {}
    for i = 1, (key == "interface" and 33 or 9) do c[key][i] = "eth" .. i end
    check(not pcall(core.validate, c), "enforce " .. key .. " size limit")
end
print("PASS: " .. count .. " core checks")
