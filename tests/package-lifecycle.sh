#!/bin/sh
# Destructive qualification on a disposable current OpenWrt system only.
# Run install, reboot the test system, then run remove with the same artifacts.
set -eu
[ "${FLINT2_DISPOSABLE_TEST:-0}" = 1 ] || { echo 'Requires an explicitly disposable test system' >&2; exit 1; }
unset LUA_PATH LUA_CPATH FLINT2_CONFIG_DIR FLINT2_RUNTIME_DIR
directory=$1
mode=${2:-install}
state=/root/flint2-package-qualification
mkdir -p "$state"
service_pid() {
    ubus call service list '{"name":"flint2"}' | lua -e '
    local data=require("cjson").decode(io.read("*a"))
    local service=data.flint2 or {}; local count,pid=0,nil
    for _,instance in pairs(service.instances or {}) do
        if instance.running then
            count=count+1
            if instance.command[1]=="/usr/bin/lua" then pid=instance.pid end
        end
    end
    assert(count==2 and pid,"Expected one agent and one capture instance")
    print(pid)'
}
case "$mode" in
install)
    if apk info --exists flint2-telemetry; then echo 'Backend already installed' >&2; exit 1; fi
    (cd "$directory" && sha256sum -c SHA256SUMS)
    cp "$directory/public-key.pem" /etc/apk/keys/flint2-current-test.pem
    set -- "$directory"/flint2-capture-*.apk
    [ "$#" = 1 ] && [ -f "$1" ]; capture=$1
    set -- "$directory"/flint2-telemetry-*.apk
    [ "$#" = 1 ] && [ -f "$1" ]; backend=$1
    set -- "$directory"/luci-app-flint2-telemetry-*.apk
    [ "$#" = 1 ] && [ -f "$1" ]; ui=$1
    nft -s list table inet fw4 > "$state/firewall-before"
    apk add "$capture" "$backend"
    [ "$(uci get flint2.main.enabled)" = 0 ]
    if /etc/init.d/flint2 running; then echo 'Public install started collection' >&2; exit 1; fi
    [ ! -f /www/luci-static/resources/view/flint2/interfaces.js ]
    lua -e 'assert(not pcall(require,"nixio"),"Backend pulled in nixio/LuCI"); require("flint2.platform").reset_sigterm()'
    flint2-agent --version
    flint2-agent --help
    uci set flint2.main.enabled=1
    uci set flint2.main.interval=10
    uci set flint2.main.router_logs=0
    uci set flint2.main.wan_interface=br-lan
    uci set flint2.main.endpoint=https://127.0.0.1:9/v1/logs
    uci set flint2.main.metrics_endpoint=https://127.0.0.1:9/v1/metrics
    uci commit flint2
    flint2-agent --check-config
    /etc/init.d/flint2 start
    sleep 2
    service_pid
    grep -q "^plugin_buffer_size: $(flint2-capture --flint2-buffer-size)$" /var/run/flint2/capture-1.conf
    /etc/init.d/flint2 reload
    sleep 2
    service_pid
    fw4 reload
    [ "$(nft list chain inet fw4 forward | grep -c 'comment "!flint2"')" = 1 ]
    before=$(service_pid)
    cp /etc/config/flint2 "$state/config-before-upgrade"
    set -- "$directory"/qualification-only/flint2-telemetry-*.apk
    [ "$#" = 1 ] && [ -f "$1" ]
    apk add "$1"
    sleep 2
    after=$(service_pid)
    [ "$before" != "$after" ]
    cmp "$state/config-before-upgrade" /etc/config/flint2
    /etc/init.d/flint2 enabled
    apk add "$ui"
    apk info --who-owns /www/luci-static/resources/view/flint2/interfaces.js | grep -q luci-app-flint2-telemetry
    apk info --who-owns /usr/sbin/flint2-agent | grep -q flint2-telemetry
    cmp /usr/share/licenses/flint2-telemetry/LICENSE /usr/share/licenses/luci-app-flint2-telemetry/LICENSE
    echo 'PASS: signed clean install, disabled defaults, headless backend, service/reload, upgrade and config preservation'
    echo 'Reboot this disposable test system, then run this script with remove.'
    ;;
remove)
    service_pid
    cmp "$state/config-before-upgrade" /etc/config/flint2
    [ "$(nft list chain inet fw4 forward | grep -c 'comment "!flint2"')" = 1 ]
    apk del luci-app-flint2-telemetry flint2-telemetry flint2-capture
    [ ! -e /usr/sbin/flint2-agent ] && [ ! -e /usr/sbin/flint2-capture ]
    [ ! -e /www/luci-static/resources/view/flint2/interfaces.js ]
    if uci -q get firewall.flint2_events; then echo 'Orphan firewall include' >&2; exit 1; fi
    nft -s list table inet fw4 > "$state/firewall-after"
    cmp "$state/firewall-before" "$state/firewall-after"
    ubus call service list '{"name":"flint2"}' | lua -e '
    local value=require("cjson").decode(io.read("*a")); for _,s in pairs(value) do
        for _,i in pairs(s.instances or {}) do assert(not i.running,"Orphan service") end
    end'
    rm -f /etc/apk/keys/flint2-current-test.pem
    echo 'PASS: reboot persistence, package removal and exact firewall policy restoration'
    ;;
*) exit 2 ;;
esac
