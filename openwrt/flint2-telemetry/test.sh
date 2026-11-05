#!/bin/sh
set -eu
/usr/sbin/flint2-agent --version
/usr/sbin/flint2-agent --help
lua -e 'require("flint2.core"); require("flint2.metrics"); require("flint2.sources"); require("flint2.platform").reset_sigterm()'
