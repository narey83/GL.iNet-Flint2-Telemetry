#!/bin/sh
# Only run in a disposable OpenWrt test machine/container. Uses its default UCI
# firewall and reloads it; never run this script on an operational router.
set -eu
base=${FLINT2_TEST_ROOT:-/tmp/flint2-test}
helper="$base/package/files/usr/libexec/flint2/firewall-events"
mkdir -p /usr/libexec/flint2
cp "$base/package/files/usr/libexec/flint2/firewall-nft.lua" /usr/libexec/flint2/
uci -q delete firewall.flint2_events || true
uci commit firewall
cp "$base/package/files/etc/config/flint2" /etc/config/flint2
uci set flint2.main.enabled=1
uci set flint2.main.wan_interface=eth0
uci set flint2.main.vpn_interface=wgtest
uci commit flint2
fw4 reload
# An inactive WAN has an empty reject chain. Add a constrained denial rule in
# this disposable fixture; the observer must retain its source-prefix match.
nft add rule inet fw4 reject_from_wan ip saddr 198.51.100.0/24 iifname eth0 counter jump handle_reject
nft -s list table inet fw4 > "$base/fw4-before"
# Observe the real helper's snapshot redirection, then delegate to real nft.
# A private parent prevents another local user from replacing a derived path
# with a symlink between mktemp and the snapshot write.
probe=$(mktemp -d "$base/nft-probe.XXXXXX")
real_nft=$(command -v nft)
cat > "$probe/nft" <<'NFT'
#!/bin/sh
set -eu
if [ "$*" = '-j list table inet fw4' ]; then
    destination=$(readlink "/proc/$$/fd/1")
    FLINT2_NFT_PARENT="${destination%/*}" lua -e '
    local stat=require("posix.sys.stat")
    local info=assert(stat.lstat(os.getenv("FLINT2_NFT_PARENT")))
    assert(stat.S_ISDIR(info.st_mode)~=0 and info.st_uid==0 and info.st_mode%512==448,
        "Firewall snapshot parent must be root-owned and mode 0700")'
    : > "$FLINT2_NFT_PROBED"
    if [ -n "${FLINT2_NFT_GATE:-}" ]; then
        "$FLINT2_REAL_NFT" "$@"
        : > "$FLINT2_NFT_GATE/$$"
        attempt=0
        while [ "$attempt" -lt 100 ]; do
            set -- "$FLINT2_NFT_GATE"/*
            [ "$#" -lt 2 ] || exit 0
            sleep 0.05
            attempt=$((attempt+1))
        done
        echo 'Concurrent snapshot barrier timed out' >&2
        exit 1
    fi
fi
exec "$FLINT2_REAL_NFT" "$@"
NFT
chmod 755 "$probe/nft"
PATH="$probe:$PATH" FLINT2_REAL_NFT="$real_nft" FLINT2_NFT_PROBED="$probe/probed" sh "$helper" start
[ -f "$probe/probed" ]
nft -s list table inet fw4 > "$base/fw4-first"
sh "$helper" start
nft -s list table inet fw4 > "$base/fw4-second"
cmp "$base/fw4-first" "$base/fw4-second"
[ "$(nft list chain inet fw4 forward | grep -c 'comment "!flint2"')" = 1 ]
nft list chain inet fw4 flint2_evt_fwd | grep -q 'ct status dnat'
nft list chain inet fw4 flint2_evt_fwd | grep -q 'iifname "wgtest"'
nft list chain inet fw4 flint2_evt_reject | grep -q 'ip saddr 198.51.100.0/24'
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
# Force two helpers to read the same empty ownership state. Exactly one create
# transaction must win; the other must fail atomically instead of adding jumps.
mkdir "$probe/gate"
PATH="$probe:$PATH" FLINT2_REAL_NFT="$real_nft" FLINT2_NFT_PROBED="$probe/probed" \
    FLINT2_NFT_GATE="$probe/gate" sh "$helper" start > "$probe/first.log" 2>&1 & first_pid=$!
PATH="$probe:$PATH" FLINT2_REAL_NFT="$real_nft" FLINT2_NFT_PROBED="$probe/probed" \
    FLINT2_NFT_GATE="$probe/gate" sh "$helper" start > "$probe/second.log" 2>&1 & second_pid=$!
if wait "$first_pid"; then first=0; else first=$?; fi
if wait "$second_pid"; then second=0; else second=$?; fi
if ! { [ "$first" = 0 ] && [ "$second" != 0 ]; } &&
    ! { [ "$second" = 0 ] && [ "$first" != 0 ]; }; then
    cat "$probe/first.log" "$probe/second.log"; exit 1
fi
[ "$(nft list chain inet fw4 forward | grep -c 'comment "!flint2"')" = 1 ]
sh "$helper" stop
rm "$probe/nft" "$probe/probed" "$probe/first.log" "$probe/second.log" "$probe/gate/"*
rmdir "$probe/gate" "$probe"
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
echo 'PASS: real fw4 rules, private snapshots, concurrent start, atomic failure, reload and policy-preserving cleanup'
