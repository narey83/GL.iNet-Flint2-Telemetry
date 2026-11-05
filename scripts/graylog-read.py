#!/usr/bin/env python3
"""Read Graylog JSON using GRAYLOG_URL/GRAYLOG_CA_FILE; API token on stdin."""
import importlib.util
import json
from pathlib import Path
import sys

spec=importlib.util.spec_from_file_location("provision",Path(__file__).with_name("provision-graylog.py"))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if len(sys.argv)!=2:
    raise SystemExit("Usage: graylog-read.py /api-relative-path < token-file")
api=module.Graylog(sys.stdin.read().strip())
print(json.dumps(api.request("GET",sys.argv[1]),indent=2))
