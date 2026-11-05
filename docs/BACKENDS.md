# Logging and monitoring destinations

Choose destinations by their supported ingestion format. Each installation supplies
its own HTTPS endpoint and CA trust through LuCI or UCI. Authentication header
files are an advanced UCI setting.
The agent has no required logging vendor or central cloud service.

| Output | Compatible destination | Signals |
| --- | --- | --- |
| OTLP/HTTP JSON | OTLP HTTP receiver or OpenTelemetry Collector | Logs and native metrics at separate endpoints |
| ECS NDJSON over HTTPS | HTTP receiver accepting newline-delimited ECS JSON | Logs, flow observations and optional metric event copies |
| GELF over HTTPS | GELF HTTP input with native TLS or an HTTPS proxy, with bulk receiving enabled | Logs, flow observations and optional metric event copies |

All outputs support direct HTTPS receivers; **Caddy and reverse proxies are
optional**. For example, a TLS-enabled GELF HTTP input can receive at
`https://graylog.example.net:12201/gelf`. Configure TLS on that ingestion input;
HTTPS on a product's web interface alone does not secure a separate input port.
The current exporter verifies server certificates and does not supply TLS client
certificates. See [trust and authentication](CONFIGURATION.md#authentication-and-certificate-trust).

OTLP is the default. A compatible OpenTelemetry Collector can route signals using
its supported destination exporters. A platform accepting JSON in general may
require a different envelope, authentication method or acknowledgement: confirm
compatibility before enabling export. Direct vendor-specific ingestion protocols
need a supported adapter; direct Splunk HEC is not implemented.

Native metrics are a separate signal. Optional metric event copies let log search
systems store measurements as events; they do not provide a native metrics backend.
`deploy/otel/` contains an optional metrics-to-Prometheus example. Historical
storage, dashboards and alerting belong to the chosen backend.

Backend-specific projections and dashboards remain optional integrations, outside
the agent's ECS/OTLP contract. See the [optional Graylog integration](integrations/GRAYLOG.md)
for the HTTPS/input setup guide and downloadable native dashboard content pack.
