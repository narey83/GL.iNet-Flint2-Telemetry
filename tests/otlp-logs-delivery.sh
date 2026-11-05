#!/bin/sh
# OpenWrt integration: permanent OTLP log rejection cannot poison the queue.
set -eu
test_dir=/tmp/flint2-otlp-logs-test
mkdir -p "$test_dir/bin" "$test_dir/config" "$test_dir/runtime"
cp /tmp/flint2-test/config/flint2 "$test_dir/config/flint2"
for setting in interval=10 metrics_enabled=0 metric_events_enabled=0 flow_capture=0 router_logs=0 format=otlp_http_json; do
    uci -c "$test_dir/config" set "flint2.main.$setting"
done
uci -c "$test_dir/config" commit flint2
echo 0 > "$test_dir/attempt"
cat > "$test_dir/bin/curl" <<'CURL'
#!/bin/sh
base=/tmp/flint2-otlp-logs-test
n=$(cat "$base/attempt")
n=$((n+1))
echo "$n" > "$base/attempt"
cp "$base/runtime/payload.ndjson" "$base/attempt-$n.json"
case "$n" in
    1) printf 400 ;;
    2) printf 503 ;;
    *) echo '{"partialSuccess":{"rejectedLogRecords":"1"}}' > "$base/runtime/response.json"; printf 200 ;;
esac
CURL
chmod 755 "$test_dir/bin/curl"
set +e
PATH="$test_dir/bin:$PATH" FLINT2_CONFIG_DIR="$test_dir/config" FLINT2_RUNTIME_DIR="$test_dir/runtime" \
LUA_PATH='/tmp/flint2-test/package/files/usr/lib/lua/?.lua;;' \
timeout --kill-after=2 25 lua /tmp/flint2-test/package/files/usr/sbin/flint2-agent > "$test_dir/output.log" 2>&1
result=$?
set -e
[ "$result" = 124 ] || { cat "$test_dir/output.log"; exit 1; }
lua - <<'LUA'
local json=require('cjson')
local function records(n)
    local f=assert(io.open('/tmp/flint2-otlp-logs-test/attempt-'..n..'.json'))
    local data=json.decode(f:read('*a'));f:close()
    return data.resourceLogs[1].scopeLogs[1].logRecords
end
local function ids(records)
    local result={}
    for _,r in ipairs(records) do for _,a in ipairs(r.attributes) do
        if a.key=='event.id' then result[a.value.stringValue]=true end
    end end
    return result
end
local first,second,third=ids(records(1)),ids(records(2)),ids(records(3))
for id in pairs(first) do assert(not second[id], 'permanently rejected records were replayed') end
for id in pairs(second) do assert(third[id], 'transient failure lost queued records') end
print('PASS: OTLP logs discard permanent rejection and retain records after 503')
LUA
