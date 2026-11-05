# Configuration

`/etc/config/flint2`, section `config agent 'main'`:

| Option | Default | Meaning |
| --- | --- | --- |
| enabled | 0 | Explicit opt-in to collection/delivery |
| format | otlp_http_json | otlp_http_json, ecs_ndjson, gelf |
| endpoint | example.invalid | Full HTTPS logs/ingestion URL |
| ca_file | system CA bundle | File containing trusted public CA certificates |
| headers_file | unset | Owner-only HTTP header file |
| interval | 30 | Sample/retry interval, 10–3600 seconds |
| inventory_interval | 300 | Inventory refresh, 60–86400 seconds |
| max_queue | 2048 | RAM log queue, 32–2048 records |
| metrics_enabled | 1 | Independent native OTLP metrics output |
| metrics_endpoint | example.invalid | Full HTTPS /v1/metrics URL |
| metrics_ca_file | ca_file | Metrics trust file |
| metrics_headers_file | unset | Metrics-specific HTTP header file |
| metrics_max_queue | 8 | RAM queue, 1–32 batches |
| metric_events_enabled | 0 | Copy native metrics into log output |
| router_logs / flow_capture / firewall_events | 1 | Optional source switches |
| wan_interface | auto | WAN l3 device from ubus, or explicit interface |
| interface (list) | br-lan | Interfaces for counters; WAN is added automatically |
| flow_lan_interface (list) | br-lan, br-guest, br-iot | Initial profile lists these bridges; clear the list for WAN-only capture |
| vpn_interface (list) | empty | Interfaces for forwarded-attempt firewall observations |
| capture_filter | auto | BPF; auto excludes HTTPS logs destination to reduce feedback |

List values use UCI `list`. Replace bridge names to suit the router. Missing
interfaces are skipped. Custom BPF must fit a single line. Auto exclusion resolves
the destination at service start; reload after DNS/address changes. Disable optional
metrics if no native metrics destination is configured. Each exporter uses its own
header file; it does not silently reuse the other output's credentials.

```sh
umask 077
# Create the file securely with your editor; no token is bundled in the package.
vi /etc/flint2/log-headers
# File contents, with your real secret substituted:
# Authorization: Bearer YOUR_TOKEN
chmod 600 /etc/flint2/log-headers
uci set flint2.main.headers_file='/etc/flint2/log-headers'
uci commit flint2
```

Header files must be regular files owned by the agent user with no group/other
permissions. Curl reads them by filename so header values do not appear in process
arguments. Trust certificates contain no private key. Never set an endpoint URL
containing a token or user credentials.

Optional device aliases:

```uci
config device_alias
    option mac '02:00:00:00:00:01'
    option name 'Example device'
```

For a local installation, `scripts/build-ipk.py --site-config local/flint2.config
--ca-file local/collector.crt --output-directory local/dist` explicitly bundles the
site UCI profile and a **public certificate**. Keep these files private/ignored.
The generic build never scans `local/` for site settings.

## LuCI interface page

With LuCI installed, use Services → Flint2 Telemetry. The interface selectors accept
existing devices and valid custom names (maximum 15 characters). Statistics lists
allow up to 32 devices; local capture and VPN lists allow eight each. Duplicate
entries are rejected. Capture/firewall switches retain their selections while off.
The page displays its capabilities and the current log destination. Export settings
remain in UCI. Empty selections are respected, and choosing a missing VPN name does
not enable or start the VPN. WireGuard connection/handshake logging is not yet part
of this agent; forwarded traffic observations are separate from tunnel establishment.
