# Optional Graylog integration

For Graylog, choose `format=gelf`, disable native metrics until a metrics destination
exists and enable `metric_events_enabled=1` to search point copies as log events.
GELF HTTPS must reach a GELF HTTP input through a TLS terminator, with bulk receiving
enabled and a request allowance of at least 256 KiB. Restrict or authenticate access.
Graylog stores point copies as logs; it does not become an OTLP metrics backend.

The Python adapter scripts read their API token from stdin. Set `GRAYLOG_URL` and
`GRAYLOG_CA_FILE`, or put them in ignored `local/site.json`. They never put the token
in the package. `provision-graylog.py --apply` provisions the dedicated input/stream
and a base dashboard. It replaces that dashboard definition: export any custom
edits before rerunning. `update-metrics-dashboard.py --apply` adds/replaces only its
managed metric tabs. IDs and before-images are saved under ignored `dist/`.

`connect-existing-dashboards.py` is an **optional legacy-site migration adapter**.
It projects canonical fields into the old site's NetFlow/syslog enrichment fields
and routes them to those streams. Those fields are backend conveniences, not the
agent's public schema. The script requires the expected existing pipelines/streams;
it is not a prerequisite for a clean install. Standard ECS names remain available
through GELF's underscore projection and the full `ecs_document` JSON.

The optional legacy adapter supplies port-name labels for VPN forwarding to Internet
destinations. Those labels identify the customary port usage, not an observed
application. The existing site's LAN service mappings remain local backend rules.
