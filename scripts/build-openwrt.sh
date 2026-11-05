#!/bin/sh
# Build the standalone source packages in a fresh, verified current OpenWrt SDK.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
target=${1:-x86/64}
case "$target" in x86/64|mediatek/filogic) ;; *) echo 'Unsupported qualification target' >&2; exit 2 ;; esac
[ "$(uname -sm)" = 'Linux x86_64' ] || { echo 'Requires Linux x86_64' >&2; exit 1; }
work=${FLINT2_OPENWRT_WORK:-"$root/vendor/.cache/current-$(echo "$target" | tr / -)"}
[ ! -e "$work" ] || { echo "Use a fresh work directory: $work" >&2; exit 1; }
mkdir -p "$work"
cd "$work"
base="https://downloads.openwrt.org/snapshots/targets/$target"
curl --fail --location --proto '=https' --tlsv1.2 "$base/sha256sums" -o sha256sums
name=$(awk '/ \*openwrt-sdk-.*\.tar.zst$/ {sub(/^\*/, "", $2); print $2; exit}' sha256sums)
case "$name" in ''|*[!a-zA-Z0-9._-]*) echo 'Invalid SDK filename' >&2; exit 1 ;; esac
curl --fail --location --proto '=https' --tlsv1.2 "$base/$name" -o "$name"
awk -v name="$name" '$2=="*"name {print $1 "  " name}' sha256sums > sdk.sha256
[ -s sdk.sha256 ] || exit 1
sha256sum --check sdk.sha256
curl --fail --location --proto '=https' --tlsv1.2 "$base/feeds.buildinfo" -o feeds.buildinfo
tar --zstd -xf "$name"
sdk="$work/${name%.tar.zst}"
cd "$sdk"
# Use the feed revisions shipped with this snapshot rather than moving heads.
sed -n '/^src-git --root=package base /p' feeds.conf.default > feeds.conf
cat "$work/feeds.buildinfo" >> feeds.conf
python3 "$root/scripts/prepare-openwrt-sdk.py" "$sdk"
./scripts/feeds update -a
# Install this dependency closure, rather than every unrelated application in
# all feeds (which can introduce their own mutually exclusive Kconfig options).
./scripts/feeds install libpcap lua lua-cjson luasocket luaposix libuci-lua ubus \
    curl ca-bundle jsonfilter coreutils-timeout firewall4 luci-base
for package in flint2-capture flint2-telemetry luci-app-flint2-telemetry; do
    [ ! -e "package/$package" ] || { echo "Package already exists: $package" >&2; exit 1; }
    cp -R "$root/openwrt/$package" "package/$package"
    printf '\nCONFIG_PACKAGE_%s=m\n' "$package" >> .config
done
make defconfig > "$work/defconfig.log" 2>&1
cat "$work/defconfig.log"
if grep -Eq 'error:|recursive dependency detected' "$work/defconfig.log"; then exit 1; fi
for package in flint2-capture flint2-telemetry luci-app-flint2-telemetry; do
    make "package/$package/compile" V=s -j "${FLINT2_BUILD_JOBS:-2}"
done
mkdir "$work/artifacts"
find bin -type f \( -name 'flint2-*.apk' -o -name 'luci-app-flint2-telemetry-*.apk' \) \
    -exec cp '{}' "$work/artifacts/" \;
cp "$work/sdk.sha256" "$work/feeds.buildinfo" "$work/defconfig.log" "$work/artifacts/"
cp feeds.conf "$work/artifacts/"
cp public-key.pem "$work/artifacts/"
cp -R "$root/openwrt" "$work/artifacts/recipes"
git -C "$root" rev-parse HEAD > "$work/artifacts/project-commit.txt"
if [ "${FLINT2_TEST_UPGRADE:-0}" = 1 ]; then
    # A packaging-only revision of the same backend tests conffile and service
    # migration. Keep it outside the installable candidate set and feed assets.
    mkdir "$work/artifacts/qualification-only"
    sed -i 's/^PKG_RELEASE:=1$/PKG_RELEASE:=2/' package/flint2-telemetry/Makefile
    make package/flint2-telemetry/compile V=s -j "${FLINT2_BUILD_JOBS:-2}"
    find bin -type f -name 'flint2-telemetry-0.4.0-r2.apk' \
        -exec cp '{}' "$work/artifacts/qualification-only/" \;
    cp package/flint2-telemetry/Makefile "$work/artifacts/qualification-only/"
    sed -i 's/^PKG_RELEASE:=2$/PKG_RELEASE:=1/' package/flint2-telemetry/Makefile
fi
cd "$work/artifacts"
if [ -d qualification-only ]; then
    sha256sum ./*.apk qualification-only/*.apk public-key.pem > SHA256SUMS
else
    sha256sum ./*.apk public-key.pem > SHA256SUMS
fi
printf 'Packages and build evidence: %s/artifacts\n' "$work"
