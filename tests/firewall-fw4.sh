#!/bin/sh
# Only run in a disposable OpenWrt test machine/container. Uses its default UCI
# firewall and reloads it; never run this script on an operational router.
set -eu
base=${FLINT2_TEST_ROOT:-/tmp/flint2-test}
helper="$base/package/files/usr/libexec/flint2/firewall-events"
cp "$base/package/files/etc/config/flint2" /etc/config/flint2
uci set flint2.main.enabled=1
uci set flint2.main.wan_interface=eth0
uci set flint2.main.vpn_interface=wgtest
uci commit flint2
fw4 reload
nft -s list table inet fw4 > "$base/fw4-before"
sh "$helper" start
nft -s list table inet fw4 > "$base/fw4-first"
sh "$helper" start
nft -s list table inet fw4 > "$base/fw4-second"
cmp "$base/fw4-first" "$base/fw4-second"
[ "$(nft list chain inet fw4 forward | grep -c 'comment "!flint2"')" = 1 ]
nft list chain inet fw4 flint2_evt_fwd | grep -q 'ct status dnat'
nft list chain inet fw4 flint2_evt_fwd | grep -q 'iifname "wgtest"'
if nft list chain inet fw4 flint2_evt_fwd | grep -Eq '(accept|reject|drop|queue)'; then
    echo 'FAIL: observation chain contains a verdict' >&2; exit 1
fi
# An invalid later interface must not partly apply a replacement ruleset.
uci set 'flint2.main.vpn_interface=wgtest invalid;interface'
if sh "$helper" start; then echo 'FAIL: invalid interface accepted' >&2; exit 1; fi
nft -s list table inet fw4 > "$base/fw4-failed"
cmp "$base/fw4-first" "$base/fw4-failed"
uci set flint2.main.vpn_interface=wgtest
# Cleanup must work after WAN discovery stops working.
uci set flint2.main.wan_interface=auto
sh "$helper" stop
nft -s list table inet fw4 > "$base/fw4-after"
cmp "$base/fw4-before" "$base/fw4-after"
sh "$helper" stop
uci set flint2.main.wan_interface=eth0
uci set firewall.flint2_events=include
uci set firewall.flint2_events.path="$helper"
uci set firewall.flint2_events.type=script
uci set firewall.flint2_events.fw4_compatible=1
uci commit firewall
uci commit flint2
fw4 reload
[ "$(nft list chain inet fw4 forward | grep -c 'comment "!flint2"')" = 1 ]
fw4 reload
[ "$(nft list chain inet fw4 forward | grep -c 'comment "!flint2"')" = 1 ]
uci set flint2.main.enabled=0
uci commit flint2
fw4 reload
if nft list chain inet fw4 flint2_evt_fwd >/dev/null 2>&1; then
    echo 'FAIL: disabled agent kept its hooks' >&2; exit 1
fi
uci delete firewall.flint2_events
uci commit firewall
echo 'PASS: real fw4 rules, atomic failure, reload, idempotency and policy-preserving cleanup'
