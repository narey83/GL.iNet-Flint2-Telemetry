# Configuration

Use **LuCI → Services → Flint2 Telemetry** for ordinary export and interface setup.
The same settings are stored in `/etc/config/flint2`; headless installations can
configure them with UCI. See [Graylog setup](integrations/GRAYLOG.md) for a complete
receiver-to-dashboard walkthrough.

## Choose your outputs

| Setup | Log export format | Send metrics as log events | Export native OpenTelemetry metrics |
| --- | --- | --- | --- |
| Log receiver only | Receiver-supported GELF, ECS NDJSON or OTLP logs | Off unless you want metric charts in log search | Off |
| Log receiver with metric charts | Receiver-supported GELF, ECS NDJSON or OTLP logs | On | Off |
| OTLP logs and native metrics | OpenTelemetry logs | Optional | On; configure a separate metrics endpoint |
| Logs plus an independent metrics backend | Receiver-supported log format | Optional | On; configure the metrics-capable receiver |

For Graylog-only dashboards, select **GELF over HTTPS**, turn **Send metrics as log
events** on and turn **Export native OpenTelemetry metrics** off. A direct TLS-enabled
GELF HTTP input can use `https://graylog.example.net:12201/gelf`; a reverse proxy is
optional. The Graylog web/API URL is not automatically the GELF ingestion URL.

Native metrics and metric log copies are independent. Enabling one does not enable
the other. CPU/rates need two samples; flow expiry can take roughly a minute plus
delivery/indexing time. Enable telemetry after the receiver and trust are configured.

## UCI options and public defaults

The table describes a fresh generic IPK. Existing site settings are preserved on
upgrade; GUI fallback values do not replace options already stored in UCI.

`/etc/config/flint2`, section `config agent 'main'`:

| Option | Default | Meaning |
| --- | --- | --- |
| enabled | 0 | Explicit opt-in to collection/delivery |
| format | otlp_http_json | otlp_http_json, ecs_ndjson, gelf |
| endpoint | https://collector.example.invalid/v1/logs | Full HTTPS logs/ingestion URL |
| ca_file | system CA bundle | File containing trusted public CA certificates |
| headers_file | unset | Owner-only HTTP header file |
| interval | 30 | Sample/retry interval, 10–3600 seconds |
| inventory_interval | 300 | Inventory refresh, 60–86400 seconds |
| max_queue | 2048 | RAM log queue, 32–2048 records |
| metrics_enabled | 1 | Independent native OTLP metrics output |
| metrics_endpoint | https://collector.example.invalid/v1/metrics | Full native OTLP HTTPS receiver URL |
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

## Authentication and certificate trust

All outputs require HTTPS and server certificate verification. Direct TLS inputs
work without a reverse proxy. The certificate must cover the hostname/IP used in
the endpoint. Use the system CA bundle or install your private CA’s public
certificate and select its absolute path. The GUI selects an existing file; it does
not upload certificates or manage server private keys. A blank metrics CA override
inherits the log CA. TLS client-certificate authentication is not implemented.

Endpoint URLs accept a hostname or IPv4 address, optional port and input path.
Paths use letters, digits, underscores, hyphens and slashes. Credentials, query
strings, fragments and IPv6-literal URLs are not supported.
Supply authentication through an owner-only header file, not URL parameters.

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
permissions; symlinks are rejected. Curl reads them by filename so header values do not appear in process
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

## GUI controls and Save & Apply

With LuCI installed, use Services → Flint2 Telemetry. The interface selectors accept
existing devices and valid custom names (maximum 15 characters). Statistics lists
allow up to 32 devices; local capture and VPN lists allow eight each. Duplicate
entries are rejected. Capture/firewall switches retain their selections while off.
The page also controls telemetry enablement, log export format/HTTPS endpoint,
CA certificate path, metric event copies and native OTLP metrics. Native metrics
have their own HTTPS endpoint and optional CA override (empty inherits the log CA).
Disabling native metrics retains their configured destination. HTTPS inputs can
be reached directly; no reverse proxy or Caddy dependency is required. Advanced
authentication header paths and queue settings remain in UCI. Save & Apply commits
the validated form and reloads the service, which checks its configuration before
starting. Empty selections are respected, and choosing a missing VPN name does
not enable or start the VPN. WireGuard connection/handshake logging is not yet part
of this agent; forwarded traffic observations are separate from tunnel establishment.


| GUI control | UCI option |
| --- | --- |
| Enable telemetry | `enabled` |
| Log export format | `format` |
| Log HTTPS endpoint | `endpoint` |
| Log CA certificate file | `ca_file` |
| Send metrics as log events | `metric_events_enabled` |
| Export native OpenTelemetry metrics | `metrics_enabled` |
| Metrics HTTPS endpoint | `metrics_endpoint` |
| Metrics CA certificate file | `metrics_ca_file` |

The metrics endpoint/CA controls appear when native metrics are enabled. Save &
Apply commits settings and reloads telemetry, so queued in-memory data can be lost.
Turning capture or firewall observations off retains the associated interface lists;
clearing a visible list explicitly removes its selections. The page does not check
that a receiver is reachable or install a CA file. If the service fails to start,
check the installed certificate/header paths and router system log; on a headless
system, run `lua /usr/sbin/flint2-agent --check-config` for its configuration error.
