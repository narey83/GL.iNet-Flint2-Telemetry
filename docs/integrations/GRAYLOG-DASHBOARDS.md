# Graylog dashboard imports

The [native content pack](../../integrations/graylog/flint2-dashboards.json) preserves
10 dashboard layouts from an existing Flint2 installation. Follow the
[setup and import guide](GRAYLOG.md) first. The downloadable file contains no search
results, host addresses, service lookup contents, credentials or original server IDs.

| Imported dashboard | Widgets | What it covers |
| --- | ---: | --- |
| Flint2 · Telemetry | 43 across four pages | Router health, interfaces, inventory, metric copies and delivery health |
| Flint2 · Bandwidth & Traffic Spikes | 18 | Observed bytes/packets, directions, remote IPs, service-port estimates |
| Flint2 · Inbound Access | 18 | Forwarded attempts, destinations, ports and optional enrichment |
| Flint2 · LAN Devices | 18 | Local device labels, addresses, directions, guest/IoT observations |
| Flint2 · Network Flow Threat Signals | 21 | TCP flag aggregates, large flows and optional intelligence matches |
| Flint2 · Perimeter Drop Map | 17 | Drop observations, port groups and optional GeoIP/ASN maps |
| Flint2 · Router Vitals | 15 | System/interface samples and selected router logs |
| Flint2 · Sources | 3 | Router source names and record counts |
| Flint2 · Threat Intel | 17 | Optional source/peer intelligence flags with related events |
| Flint2 · VPN Access | 13 | Forwarded VPN attempts, source addresses, destinations and ports |

The pack adds one input-scoped stream, 16 pipeline rules and one connected pipeline.
It creates no input, lookup table, external output, alert or scheduled notification.
All dashboard queries remain scoped to this stream. Original streams are not removed
or replaced. Old index history is not copied or retroactively enriched.

## Generalizations from the original setup

- Fresh content-pack IDs replace original server IDs. Input selection is an install
  parameter. No collector hostname, private CA, WAN address or user identity is stored.
  Address-specific highlighting is removed.
- Queries and aggregations use canonical GELF-projected ECS fields such as
  `source_bytes`, `source_ip`, `destination_port`, `network_direction` and
  `event_action`. WAN/LAN clauses use `flint2_capture_scope`; both observation points
  can describe the same traffic, so do not add their totals together.
- Fixed `pppoe-wan` rate filters become monitored-interface averages. Choose a
  specific interface in a copied widget/query if you want a WAN-only rate. Bridge
  and physical-port measurements can overlap.
- Private service names, device aliases and Transmission-specific port overrides
  are not distributed. Example P2P port groups use common port numbers and can be
  edited; they do not identify an application or prove backscatter.
- Service labels are numeric port estimates. For flows, the smaller of the source
  and destination ports is used; for firewall observations, the destination port is
  used. This heuristic can be wrong and is not application identification.
- VPN source addresses replace private peer-name lookups. VPN widgets describe
  forwarded attempts, not successful connections or WireGuard handshakes. The
  internal-destination views count RFC1918 IPv4 destinations; other local ranges
  need an adapted classification rule.
- Port/scanner/volume titles avoid claiming malicious intent or benign status from
  a port or ASN match. Intelligence fields remain optional provider assessments.

## Backend-only computed fields

The connected pipeline writes only `flint2_dashboard_*` fields. Canonical ECS and
agent fields remain intact; the router does not depend on this pipeline.

| Field | Meaning |
| --- | --- |
| `flint2_dashboard_megabytes` | Observed `source_bytes / 1000000`, decimal MB |
| `flint2_dashboard_rx_mbps` / `_tx_mbps` | Interface receive/transmit bits per second divided by 1000000; decimal Mbps for rate widgets |
| `flint2_dashboard_peer_ip` | Source for inbound flows; destination for outbound/internal flows |
| `flint2_dashboard_wan_ip` | Opposite endpoint for direction-classified flows; interpret only with WAN scope |
| `flint2_dashboard_service_port` / `flint2_dashboard_service` | Estimated port and its numeric string label |
| `flint2_dashboard_tcp_flags` | Exact aggregate masks 2=SYN, 18=SYN-ACK, 16=ACK, 4=RST, 1=FIN; other masks remain unlabelled |
| `flint2_dashboard_tcp_syn_only` | TCP flow whose aggregate flags equal 2; not proof of an unanswered packet or an attack |
| `flint2_dashboard_high_byte_flow` | At least 10000000 observed bytes in a flow record |
| `flint2_dashboard_high_packet_flow` | At least 1000 observed packets in a flow record |
| `flint2_dashboard_flow_indicator` / `_type` | SYN-only aggregate (`TCP_SYN`) or UDP record with at least 60000 packets (`UDP_VOLUME`); heuristic, not a confirmed threat |
| `flint2_dashboard_destination_class` | `private_ipv4` for router-log destinations in 10/8, 172.16/12 or 192.168/16 |

Thresholds apply to individual unidirectional records. They are not validated
attack detectors or packet-rate measurements. Capture/acceleration loss, flow
expiry, queue loss and repeated observations affect counts. Use the original
`event_start`, `event_end`, source counters and capture scope when interpreting them.

The telemetry rate chart and interface table show Mbps. Flow dashboards still
show transferred volume in MB per stated interval; a flow record's bytes are
not a continuous link-speed measurement. On Graylog 4.3, newly imported Mbps
widgets populate from records processed after the enrichment rule is installed.

## Optional enrichment fields

These fields are **not** fabricated by the content pack. Without an external
provider, their panels legitimately remain empty. Configure enrichers in your own
backend, observe database/provider licensing and update requirements, and use the
pipeline simulator before processing real traffic.

| Capability | Fields expected by these dashboards | Requirements |
| --- | --- | --- |
| Source GeoIP | `source_geo_country_name`, `source_geo_city_name`, `source_geo_location` | Your own GeoIP database/provider; the map expects a coordinate value Graylog's map visualization accepts, commonly `latitude,longitude` |
| Source ASN organization | `source_as_organization_name` | Your own ASN database/provider; no customer ASN allowlist is bundled |
| Source intelligence | `flint2_dashboard_src_threat_indicated`, `_spamhaus`, `_tor` | Boolean assessments from your selected providers; suffixes are full fields such as `flint2_dashboard_src_threat_indicated_tor` |
| Flow-peer intelligence | `flint2_dashboard_peer_threat_indicated` | Boolean assessment of `flint2_dashboard_peer_ip`; run after that field is computed |

GeoIP/ASN field names correspond to the underscore projection of ECS source geo/AS
fields. Your enricher must map its response to these names; installing a generic
GeoIP database alone does not guarantee that mapping. Set the map's coordinate
format/index mapping appropriately for your Graylog version. Do not substitute a
country centroid or label a private IP as a public GeoIP match.

For a trusted service-name lookup, you can add a later stage that resolves
`flint2_dashboard_service_port` or the firewall `destination_port` and writes
`flint2_dashboard_service`. Keep a numeric fallback. Peer/source threat enrichment
and service labels should run in a later stage than the shipped computation so
same-stage rule order cannot overwrite results. The pack deliberately ships no
private CSV paths, VPN names, lookup API keys or intelligence feed URLs.

## Validate, customize and remove

The native pack was installed on Graylog 4.3.15 using a temporary pack ID and
placeholder input ID, then explicitly paused for testing. All 10 dashboards,
13 pages and 183 widgets imported. Their searches executed against a short window
of existing telemetry with zero query/search-type errors. Ten pipeline simulator
cases checked masks, thresholds, service-port direction, private/public VPN
traffic and module/dataset guards. Simulator messages were not submitted to an
input or indexed. Missing optional enrichment is not a claim of populated panels.
Temporary entities and uploaded test definitions were removed after validation.

Duplicate a dashboard before customizing it. Keep your copies and rule changes
outside a managed pack if you want them to survive a future reinstall. Test new
pack revisions on a separate stream first. The initial upload does not overwrite
similarly titled existing dashboards, but installation and uninstallation can reuse
or remove entities according to Graylog's ownership tracking.

To remove the import, use **System → Content Packs → this pack → its installation →
Uninstall**. Review the entity list, especially if entities were reused by another
installation. Remove the uploaded definition afterward if no longer needed. This
does not uninstall the router agent or delete already indexed log data.

For maintainers: update only definitions, retain input parameterization and fresh
IDs, and run `python3 -m unittest discover -s tests -p 'test_*.py'`. The artifact tests
check widget/search consistency, all stream references, data privacy and the rule
write namespace. A changed native pack also needs an actual install/uninstall and
pipeline simulation on each claimed Graylog version. Keep private raw exports and
query results out of Git. Recompute the accompanying SHA-256 after any JSON change.
