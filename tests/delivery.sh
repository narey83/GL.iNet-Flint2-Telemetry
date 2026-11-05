#!/bin/sh
# Router integration test. Uses isolated UCI files and a fake curl, never sends data.
set -eu
test_dir=/tmp/flint2-test
mkdir -p "$test_dir/bin" "$test_dir/delivery-config" "$test_dir/runtime"
cp "$test_dir/config/flint2" "$test_dir/delivery-config/flint2"
uci -c "$test_dir/delivery-config" set flint2.main.interval=10
uci -c "$test_dir/delivery-config" set flint2.main.format=gelf
uci -c "$test_dir/delivery-config" set flint2.main.metric_events_enabled=0
uci -c "$test_dir/delivery-config" set flint2.main.metrics_enabled=0
uci -c "$test_dir/delivery-config" set flint2.main.flow_capture=0
uci -c "$test_dir/delivery-config" set flint2.main.router_logs=0
uci -c "$test_dir/delivery-config" commit flint2
echo 0 > "$test_dir/attempt"
cat > "$test_dir/bin/curl" <<'CURL'
#!/bin/sh
n=$(cat /tmp/flint2-test/attempt)
n=$((n + 1))
echo "$n" > /tmp/flint2-test/attempt
cp /tmp/flint2-test/runtime/payload.ndjson "/tmp/flint2-test/attempt-$n.ndjson"
case "$n" in
    1) exit 22 ;;
    2) printf 302 ;;
    *) printf 202 ;;
esac
CURL
chmod 755 "$test_dir/bin/curl"
set +e
PATH="$test_dir/bin:$PATH" FLINT2_CONFIG_DIR="$test_dir/delivery-config" \
FLINT2_RUNTIME_DIR="$test_dir/runtime" \
LUA_PATH="$test_dir/package/files/usr/lib/lua/?.lua;;" \
timeout --kill-after=2 25 lua "$test_dir/package/files/usr/sbin/flint2-agent" > "$test_dir/delivery.log" 2>&1
result=$?
set -e
[ "$result" = 124 ] || { cat "$test_dir/delivery.log"; exit 1; }
lua - <<'LUA'
local json = require("cjson")
local sizes = {}
for n = 1, 3 do
    local count = 0
    for line in io.lines("/tmp/flint2-test/attempt-" .. n .. ".ndjson") do
        assert(json.decode(line)._flint2_component == "telemetry")
        count = count + 1
    end
    sizes[n] = count
end
assert(sizes[2] > sizes[1], "failed transport must retain queued data")
assert(sizes[3] > sizes[2], "HTTP redirect must retain queued data")
local f = assert(io.open("/tmp/flint2-test/delivery.log"))
local log = f:read("*a"); f:close()
assert(log:find("delivery failed", 1, true), "failure transition logged")
assert(log:find("delivery recovered", 1, true), "recovery transition logged")
print("PASS: delivery retries, HTTP redirect rejection, queue retention and recovery")
LUA
