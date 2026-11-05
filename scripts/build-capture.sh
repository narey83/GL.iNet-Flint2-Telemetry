#!/bin/sh
# Linux x86_64 host only. Downloads are checksum verified before extraction.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cache=${FLINT2_BUILD_CACHE:-"$root/vendor/.cache"}
work="$cache/work"
[ "$(uname -sm)" = 'Linux x86_64' ] || { echo 'Requires a Linux x86_64 build host' >&2; exit 1; }
mkdir -p "$cache"
fetch() {
    name=$1 digest=$2 url=$3
    if [ ! -f "$cache/$name" ]; then curl --fail --location --proto '=https' --tlsv1.2 "$url" -o "$cache/$name"; fi
    printf '%s  %s\n' "$digest" "$cache/$name" | sha256sum --check --status
}
sdk_name=openwrt-sdk-21.02.7-mediatek-mt7622_gcc-8.4.0_musl.Linux-x86_64
fetch sdk.tar.xz 723b08a90778779cbc20da03a36fa0e213b22dd63ce601803f0eae44f303681d "https://downloads.openwrt.org/releases/21.02.7/targets/mediatek/mt7622/$sdk_name.tar.xz"
fetch pmacct-1.7.9.tar.gz 94185c33d659772035c63be0a82601bb9eb064fb4be1d68ba279b47204b2750a https://github.com/pmacct/pmacct/releases/download/v1.7.9/pmacct-1.7.9.tar.gz
fetch libpcap-1.11.0.tar.gz 596389bc8560ea027dff9db8aaf6c173d992366d9aef4baf5d7c6d180b4d49ad https://www.tcpdump.org/release/libpcap-1.11.0.tar.gz
# Refuse reuse of partially configured source trees.
[ ! -e "$work" ] || { echo "Remove the previous build directory before rebuilding: $work" >&2; exit 1; }
mkdir "$work"
# Upstream's tarball make rules probe git and otherwise discover our enclosing
# checkout, incorrectly trying to initialize a submodule in the Flint2 repository.
# Keep discovery inside the extracted build tree; use the bundled libcdada sources.
export GIT_CEILING_DIRECTORIES="$work"
tar -xJf "$cache/sdk.tar.xz" -C "$work"
tar -xzf "$cache/pmacct-1.7.9.tar.gz" -C "$work"
tar -xzf "$cache/libpcap-1.11.0.tar.gz" -C "$work"
sdk="$work/$sdk_name"
export STAGING_DIR="$sdk/staging_dir/target-aarch64_cortex-a53_musl"
export PATH="$sdk/staging_dir/toolchain-aarch64_cortex-a53_gcc-8.4.0_musl/bin:$sdk/staging_dir/host/bin:$PATH"
export M4="$sdk/staging_dir/host/bin/m4"
export BISON_PKGDATADIR="$sdk/staging_dir/host/share/bison"
export CC=aarch64-openwrt-linux-musl-gcc
export CFLAGS='-Os -fPIC -fstack-protector-strong -D_FORTIFY_SOURCE=2'
export LDFLAGS='-Wl,-z,relro,-z,now'
# The upstream SDK has non-relocatable libtool metadata.
python3 - "$sdk/staging_dir" <<'PY'
from pathlib import Path
import sys
staging = Path(sys.argv[1])
for path in staging.rglob('*.la'):
    text = path.read_text()
    path.write_text(text.replace('/builder/shared-workdir/build/staging_dir/', str(staging) + '/'))
PY
cd "$work/libpcap-1.11.0"
./configure --host=aarch64-openwrt-linux-musl --disable-shared --disable-dbus --without-libnl
make -j "${FLINT2_BUILD_JOBS:-2}"
cd "$work/pmacct-1.7.9"
for source_patch in "$root"/vendor/patches/*.patch; do
    patch -p1 -F0 -N -i "$source_patch"
done
PKG_CONFIG=/bin/false ./configure --host=aarch64-openwrt-linux-musl \
    --with-pcap-includes="$work/libpcap-1.11.0" --with-pcap-libs="$work/libpcap-1.11.0" \
    --disable-bgp-bins --disable-bmp-bins --disable-st-bins
make -j "${FLINT2_BUILD_JOBS:-2}"
mkdir -p "$root/package/files/usr/sbin"
aarch64-openwrt-linux-musl-strip -o "$root/package/files/usr/sbin/flint2-capture" src/pmacctd
printf 'Built %s\n' "$root/package/files/usr/sbin/flint2-capture"
