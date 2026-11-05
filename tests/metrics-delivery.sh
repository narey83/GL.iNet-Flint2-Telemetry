#!/bin/sh
# Isolated router integration test; all HTTP calls use a fake curl.
set -eu
test_dir=/tmp/flint2-metrics-test
mkdir -p "$test_dir/bin" "$test_dir/config" "$test_dir/runtime"
cp /tmp/flint2-test/config/flint2 "$test_dir/config/flint2"
uci -c "$test_dir/config" set flint2.main.interval=10
uci -c "$test_dir/config" set flint2.main.format=gelf
uci -c "$test_dir/config" set flint2.main.metrics_enabled=1
uci -c "$test_dir/config" set flint2.main.metric_events_enabled=1
uci -c "$test_dir/config" set flint2.main.flow_capture=0
uci -c "$test_dir/config" set flint2.main.router_logs=0
uci -c "$test_dir/config" set flint2.main.metrics_endpoint=https://collector.test/v1/metrics
uci -c "$test_dir/config" commit flint2
echo 0 > "$test_dir/attempt"
echo 0 > "$test_dir/log-attempt"
cat > "$test_dir/bin/curl" <<'CURL'
#!/bin/sh
case "$*" in
    *collector.test*)
        n=$(cat /tmp/flint2-metrics-test/attempt)
        n=$((n + 1))
        echo "$n" > /tmp/flint2-metrics-test/attempt
        cp /tmp/flint2-metrics-test/runtime/payload.ndjson "/tmp/flint2-metrics-test/metrics-$n.json"
        case "$n" in
            1) printf 503 ;;
            2) echo '{"partialSuccess":{"rejectedDataPoints":"3"}}' > /tmp/flint2-metrics-test/runtime/response.json; printf 200 ;;
            3) printf 400 ;;
            *) echo '{}' > /tmp/flint2-metrics-test/runtime/response.json; printf 200 ;;
        esac ;;
    *)
        n=$(cat /tmp/flint2-metrics-test/log-attempt)
        n=$((n + 1))
        echo "$n" > /tmp/flint2-metrics-test/log-attempt
        cat /tmp/flint2-metrics-test/runtime/payload.ndjson >> /tmp/flint2-metrics-test/logs.ndjson
        printf 202 ;;
esac
CURL
chmod 755 "$test_dir/bin/curl"
: > "$test_dir/logs.ndjson"
set +e
PATH="$test_dir/bin:$PATH" FLINT2_CONFIG_DIR="$test_dir/config" FLINT2_RUNTIME_DIR="$test_dir/runtime" \
LUA_PATH="/tmp/flint2-test/package/files/usr/lib/lua/?.lua;;" \
timeout --kill-after=2 25 lua /tmp/flint2-test/package/files/usr/sbin/flint2-agent > "$test_dir/output.log" 2>&1
result=$?
set -e
[ "$result" = 124 ] || { cat "$test_dir/output.log"; exit 1; }
lua - <<'LUA'
local json = require("cjson")
local function read(path) local f=assert(io.open(path));local s=f:read("*a");f:close();return s end
local base="/tmp/flint2-metrics-test/"
assert(read(base.."metrics-1.json")==read(base.."metrics-2.json"), "retried batch must be byte identical")
assert(read(base.."metrics-2.json")~=read(base.."metrics-3.json"), "partial success must not replay accepted points")
assert(read(base.."metrics-4.json"), "permanent rejection must not block later metrics")
local samples, events = {}, 0
for line in io.lines(base.."logs.ndjson") do
    local r=json.decode(line)
    if r._flint2_event_kind=="system" then samples[#samples+1]=r end
    if r._flint2_event_kind=="metric" then events=events+1 end
end
assert(#samples>=3 and events>0, "Graylog continues receiving system and metric events during metrics failure")
assert(samples[3]._flint2_metrics_dropped_total==1 and samples[3]._flint2_metrics_rejected_total>3, "metrics loss is observable")
assert(samples[3]._flint2_delivery_failed==0, "metrics failures do not set log delivery failure")
print("PASS: native retry, partial success, permanent rejection, independent delivery and Graylog metric events")
LUA
