#!/bin/sh
set -eu
case "$PKG_NAME" in
    flint2-telemetry) /usr/sbin/flint2-agent --version | grep -F "$PKG_VERSION" ;;
    *) exit 1 ;;
esac
