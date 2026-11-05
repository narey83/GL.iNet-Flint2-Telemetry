#!/bin/sh
# Run after copying package/ and tests/ under /tmp/flint2-test on an OpenWrt test router.
# No live configuration, services, firewall rules or real HTTP endpoints are changed.
set -eu
base=/tmp/flint2-test
mkdir -p "$base/config"
cp "$base/package/files/etc/config/flint2" "$base/config/flint2"
uci -c "$base/config" set flint2.main.enabled=1
uci -c "$base/config" commit flint2
for test in delivery metrics-delivery otlp-logs-delivery; do sh "$base/tests/$test.sh"; done
# The fake HTTP tests above use no authentication. Check credential-file validation separately.
printf 'Authorization: Bearer test-only\n' > "$base/header-test"
uci -c "$base/config" set flint2.main.headers_file="$base/header-test"
uci -c "$base/config" commit flint2
chmod 644 "$base/header-test"
export FLINT2_CONFIG_DIR="$base/config"
export LUA_PATH="$base/package/files/usr/lib/lua/?.lua;;"
if lua "$base/package/files/usr/sbin/flint2-agent" --check-config >/dev/null 2>&1; then
    echo 'FAIL: exporter accepted a world-readable secret file' >&2; exit 1
fi
chmod 600 "$base/header-test"
lua "$base/package/files/usr/sbin/flint2-agent" --check-config
rm "$base/header-test"
uci -c "$base/config" delete flint2.main.headers_file
uci -c "$base/config" commit flint2
echo 'PASS: secret file permission validation'
