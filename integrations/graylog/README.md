# Graylog import

[Download the native content pack](https://raw.githubusercontent.com/narey83/GL.iNet-Flint2-Telemetry/main/integrations/graylog/flint2-dashboards.json)
for **10 dashboards and 183 widgets** adapted from a working Flint2 installation.

1. Follow the [Graylog input/HTTPS/router setup guide](../../docs/integrations/GRAYLOG.md).
2. Upload `flint2-dashboards.json` under **System → Content Packs** and install it.
3. Supply your own GELF input ID, review the stream/index set and processor order,
   and wait for fresh telemetry.

Tested with Graylog 4.3.15. Maps, ASN and intelligence panels need your own enrichment;
see the [dashboard catalogue](../../docs/integrations/GRAYLOG-DASHBOARDS.md).
No event data, credentials, private device names or source-site IDs are included.

Verify the download using `sha256sum -c flint2-dashboards.json.sha256` from this
directory (or `shasum -a 256 flint2-dashboards.json` on macOS).
