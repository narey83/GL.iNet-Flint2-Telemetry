# Graylog setup

Send Flint2 telemetry directly to a dedicated GELF HTTP input with TLS enabled,
or use an optional HTTPS reverse proxy. **Caddy is not required.** Then import the
[dashboard content pack](../../integrations/graylog/flint2-dashboards.json).
The pack adapts the layouts of a working installation: **10 dashboards, 13 pages
and 183 widgets**. It contains definitions, not captured events or site lookup data.

The native content pack and pipeline simulations were tested on **Graylog 4.3.15**.
That records compatibility with the existing installation, not a recommendation to
install an old server version. Other Graylog releases need their own import check;
menu labels and input options can differ. No commercial dashboard plugin is required
by the pack. Optional intelligence enrichment can have separate prerequisites.

## 1. Create the input

In **System → Inputs**, choose **GELF HTTP**, launch an input and name it
`Flint2 Telemetry`. Use a free TCP port, for example `12201`.

- Enable **bulk receiving**: the agent sends newline-separated GELF messages.
- Allow messages/requests of at least **262144 bytes (256 KiB)**. The agent limits
  each log request to 240 KiB. On 4.3, check the input's **max chunk size** option.
- Disable CORS unless another application needs it.
- If TLS terminates at a reverse proxy, keep the plain HTTP input private to that
  proxy. Its ingestion path is `/gelf`.

Copy this input's ID from its details/link. You will supply it when installing the
content pack; the ID belongs to your server and is not included in the download.

## 2. Choose direct TLS or an optional reverse proxy

### Direct Graylog HTTPS input — no proxy required

On the **GELF HTTP input**, enable TLS and supply the certificate chain and private
key paths readable by the Graylog process. Use a certificate valid for the hostname
(or IP SAN) the router will connect to. Some versions require a PKCS#8 PEM private
key; follow the input's TLS requirements. Keep the private key on the Graylog server.
The input's HTTPS address is separate from the Graylog web/API HTTPS configuration.

For example, with TLS on input port 12201, use:

```text
https://graylog.example.net:12201/gelf
```

For Docker, mount your certificate directory read-only and use the paths **inside
that container** in the input settings. Publish the TLS port on the appropriate
server/LAN address, for example:

```yaml
# Add to your existing Graylog service, preserving its other settings.
volumes:
  - ./graylog-input-tls:/etc/graylog/input-tls:ro
ports:
  - "12201:12201/tcp"
```

The input can bind to `0.0.0.0` inside the container. Restrict access to trusted
senders using the host/network firewall; the Docker example publishes on all host
addresses, so narrow that binding when appropriate. GELF inputs do not automatically
validate Graylog API tokens. This agent supports server-authenticated TLS; input
configurations requiring TLS client certificates are not supported by its current
exporter.

Use a publicly trusted certificate or install your private CA's **public certificate**
on the router and select its path in the telemetry GUI. Never copy the server's
private key to the router or disable certificate verification.

Graylog documents [GELF input options](https://go2docs.graylog.org/current/getting_in_log_data/gelf.html)
and [securing inputs with TLS](https://go2docs.graylog.org/current/getting_in_log_data/secure_inputs_with_tls.htm).
Those guides describe current releases; use the options available in your installed version.

### Optional reverse proxy

A reverse proxy can provide certificate management, access restrictions or header
authentication. Any compatible HTTPS proxy can be used. If TLS terminates there,
keep the plain GELF HTTP input private to it and forward to `/gelf`.

For host-based Caddy, an example is:

```caddyfile
telemetry.example.net {
    handle /flint2-telemetry {
        @not_router not remote_ip {$FLINT2_ROUTER_IP}
        respond @not_router 403
        @not_post not method POST
        respond @not_post 405
        request_body {
            max_size 256KB
        }
        rewrite * /gelf
        reverse_proxy 127.0.0.1:12201
    }
}
```

Set `FLINT2_ROUTER_IP` to the address the proxy actually sees. For a host proxy and
containerized Graylog, publish its plain input on host loopback only, such as
`127.0.0.1:12201:12201/tcp`. If both services are containers, use a private shared
network and proxy to `graylog:12201`; `127.0.0.1` does not reach another container.
Use your own hostname and path. Do not expose a plain GELF HTTP listener directly
to the Internet.

For proxy header authentication, configure the owner-only header file described in
[configuration](../CONFIGURATION.md). An API token for Graylog administration is
not automatically an ingestion credential.

## 3. Configure the router

Install a compatible IPK using the [main installation guide](../../README.md#install-and-configure).
In **LuCI → Services → Flint2 Telemetry**, choose:

| GUI control | Graylog-only setting |
| --- | --- |
| Enable telemetry | On |
| Log export format | GELF over HTTPS |
| Log HTTPS endpoint | Your direct input URL, for example `https://graylog.example.net:12201/gelf`, or your optional proxy URL |
| Log CA certificate file | System CA bundle or your installed public CA certificate |
| Send metrics as log events | On |
| Export native OpenTelemetry metrics | Off, unless you have a separate metrics-capable receiver |

Click **Save & Apply**. The form validates its values, commits UCI changes and
reloads telemetry; the service checks its configuration before starting. There is
no need to run the commands below for ordinary GUI configuration.

For headless systems, the equivalent UCI configuration is:

```sh
uci set flint2.main.format='gelf'
uci set flint2.main.endpoint='https://graylog.example.net:12201/gelf'
uci set flint2.main.metrics_enabled='0'
uci set flint2.main.metric_events_enabled='1'
uci set flint2.main.enabled='1'
uci commit flint2
lua /usr/sbin/flint2-agent --check-config
/etc/init.d/flint2 restart
```

Replace the endpoint before running these commands. With a private CA, also set
`flint2.main.ca_file` to the installed certificate path before enabling telemetry.
Choose existing statistics, flow and VPN devices in **LuCI → Services → Flint2
Telemetry**. Selecting a VPN device does not start a VPN server.

`metrics_enabled=0` disables the separate native OTLP metrics exporter. Keeping
`metric_events_enabled=1` sends metric point copies through the log output, which
these dashboards can search. Graylog remains a log backend. To also export native
metrics, configure a separate metrics-capable OTLP destination and enable that
exporter; see [destinations](../BACKENDS.md).

Search the input for `event_module:flint2`. System records normally arrive within
30 seconds; flow expiry can take roughly a minute plus delivery/indexing time.
Check `event_dataset`, `flint2_event_kind`, `source_ip` and `source_bytes`.
GELF projects canonical ECS dots to underscores; `ecs_document` retains the nested
original document. No old NetFlow/syslog exporter is needed.

## 4. Import the dashboards

1. Download [flint2-dashboards.json](https://raw.githubusercontent.com/narey83/GL.iNet-Flint2-Telemetry/main/integrations/graylog/flint2-dashboards.json).
   Save the raw JSON, not the surrounding GitHub HTML page. An optional
   [SHA-256 file](../../integrations/graylog/flint2-dashboards.json.sha256) accompanies it.
2. Open **System → Content Packs → Upload**, select the JSON and upload it.
3. Select **GL.iNet Flint2 Telemetry dashboards**, revision 1, and **Install**.
   Set `FLINT2_INPUT_ID` to the ID of the GELF HTTP input created in step 1.
4. Review **Streams → Flint2 portable dashboards**. Both rules must match:
   `event_module` equals `flint2`, and `gl2_source_input` equals your input ID.
   Choose an appropriate index set/retention policy. Graylog 4.3 imports streams
   into its default index set and can start them even when an exported disabled
   flag is set. **Do not rely on that flag as a pause control.**
5. Review **System → Configurations → Message Processors**. Stream matching must
   occur before the connected pipeline runs; on 4.3 this normally means **Message
   Filter Chain before Pipeline Processor**. Consider your other pipelines before
   changing the global order.
6. Open **Dashboards** and select the new `Flint2 · …` dashboards. Wait for fresh
   records: installing a pipeline does not enrich older indexed messages.

To review the import before accepting traffic, leave `FLINT2_INPUT_ID` at
`SET_YOUR_GELF_INPUT_ID`. That placeholder matches no normal input. Then explicitly
pause the new stream, replace its input-ID rule, review its index set and pipeline
connection, and start it when ready. The pack does not remove matches from the
existing/default streams and does not create an input or modify your old dashboards.

For a new setup, this pack is the dashboard installation path. The older
`provision-graylog.py` and `update-metrics-dashboard.py` scripts are an alternative
managed-dashboard workflow; do not run them expecting to update these imported
copies. `connect-existing-dashboards.py` is only for a pre-existing legacy site,
not a clean-install prerequisite.

## 5. Verify and troubleshoot

In the new stream, search these examples:

```text
event_dataset:flint2.system
event_dataset:flint2.network_flow AND flint2_capture_scope:wan
event_dataset:flint2.network_flow AND flint2_capture_scope:lan
event_dataset:flint2.router_log
flint2_event_kind:metric
_exists_:flint2_dashboard_megabytes
```

Check the latest system record's `flint2_source_invalid_datagrams`,
`flint2_queue_dropped_total` and `flint2_delivery_failed`. These are cumulative
within a process run; a restart resets them. Zero delivery errors do not prove
capture is lossless.

| Symptom | Check |
| --- | --- |
| No records at the input | Input running, DNS, router clock, TLS trust, published port/firewall rules, POST path and any optional proxy restrictions |
| Input gets records but stream is empty | Input-ID rule, `event_module:flint2`, and stream running state |
| Core records exist but derived fields do not | Pipeline connected to the new stream, message processor order, and fresh records after import |
| Metric charts are empty | `metric_events_enabled=1`; allow two samples for CPU/rates |
| Maps/ASN/threat panels are empty | Configure the [optional enrichments](GRAYLOG-DASHBOARDS.md#optional-enrichment-fields); these fields are not produced by the router |
| LAN panels are empty | Selected capture bridge, device labels and `flint2_capture_scope:lan` |
| VPN panels are empty | Actual forwarded traffic, a running tunnel and selected VPN event device; handshakes alone do not create these events |
| Guest/IoT panels are empty | Their filters use network labels `guest`/`iot`; adapt them to your configured logical network names |
| UI error after import on another version | Check compatibility and server logs before changing the original dashboards; test imports are qualified only on 4.3.15 |

See the [dashboard catalogue and field contract](GRAYLOG-DASHBOARDS.md) for what
was preserved, what was generalized and how to remove the import.

Graylog documents upload/install workflows in its official
[Content Packs guide](https://go2docs.graylog.org/current/what_more_can_graylog_do_for_me/content_packs.html).
That page describes a newer release; the live import checks above were on 4.3.15.
