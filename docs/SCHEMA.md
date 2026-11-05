# Event and metric contract

Schema baseline: [ECS 8.17](https://www.elastic.co/guide/en/ecs/8.17/index.html).
Envelope: [OTLP/HTTP JSON](https://opentelemetry.io/docs/specs/otlp/).
Native metrics: [OTel system conventions 1.45.0](https://opentelemetry.io/docs/specs/semconv/system/system-metrics/)
(currently Development stability). Pin changes to these baselines intentionally.

## Event envelope

Every event has `@timestamp` (UTC ISO 8601), `message`, `ecs.version`, `observer.name`,
`observer.type=router`, `agent.version`, `agent.ephemeral_id`, `event.id`, `event.kind`,
`event.dataset`, `event.module=flint2` and `flint2.component=telemetry`.
`flint2.schema_version=2` versions Flint2 extensions; it is not the ECS version.
`flint2.event_kind` identifies the collector record type. `flint2.boot_id` identifies
the router boot and `flint2.sequence` counts records in the current agent run.
New optional fields are additive. Removing fields, changing types/units or changing
meaning requires a documented schema change and adapter migration.

| Dataset | Contents |
| --- | --- |
| `flint2.network_flow` | ECS source/destination IP, address, TCP/UDP ports, source bytes/packets, event start/end/duration, network transport/iana_number/type/direction |
| `flint2.router_log` | event.original, process.name/pid, log.level, log.syslog facility/severity; parsed network/firewall fields when available |
| `flint2.system` | `flint2.*` health snapshots; native metrics are the preferred metric representation |
| `flint2.interface` | `flint2.interface`, cumulative RX/TX counters and measured bit rates |
| `flint2.wan` / `flint2.event` | WAN state snapshots and agent/interface/WAN change events |
| `flint2.device` / `flint2.inventory` | lease/device inventory and inventory counts |
| `flint2.metric` | optional structured copies of native metric points |

`event.category` and `event.type` are arrays. `event.duration` is nanoseconds;
`source.bytes` is bytes from the source, and `source.packets` is its packet count.
These flows are unidirectional; **network.bytes is deliberately absent**, because
ECS defines it as both directions combined. Ports are present only for TCP/UDP.
`network.direction` uses the perimeter values inbound/outbound/internal/unknown.
Raw observations do not establish application identity or connection success.

## Flint2 extensions

- `flint2.capture.*`: engine, engine_id, scope (wan/lan), unidirectional boolean,
  export_time (Unix seconds), and local exporter sequence. This is capture provenance,
  not an interoperable flow ID. It can wrap after exporter restart.
- `flint2.local_device.*`: ip, name, mac, network; best-effort observed device labels.
  `flint2.peer.*`: local peer ip/name when known. No claim of presence or ownership.
- `flint2.packet.*` and `flint2.tcp.*`: parsed lengths, TTL, IP ID, TCP window,
  bit flags or firewall flag text. These are extensions rather than invented ECS fields.
- `flint2.metric_*`: name, unit, description, numeric value, type, temporality,
  monotonic flag and timestamp strings. Attributes use `flint2.metric_attribute_*`.
  These log copies are distinct from the native OTLP metric output.
- Other health/inventory fields remain under `flint2.*`, including their unit suffixes.
  Unsupported or unavailable measurements are omitted rather than filled with zero.

## Wire adapters

ECS NDJSON uses one nested document per line, numbers/booleans unchanged.
OTLP logs carry the nested ECS document in a structured `AnyValue` body, plus
canonical dotted attributes with typed values. int64 values/timestamps use decimal
strings in Protobuf JSON; fractional numbers use doubleValue. Resources describe
the agent service and router host; scope is `flint2.agent`.

GELF projects dotted attribute names to underscores (`source.bytes` → `source_bytes`,
`flint2.capture.scope` → `flint2_capture_scope`). GELF does not preserve structured
arrays/objects in indexed fields: single values become scalars, multiple values
become JSON strings and booleans become 0/1. `ecs_document` holds the full nested
JSON document so arrays and boolean types can be recovered. Backend-specific
projections and lookup results are adapter fields, never part of the agent contract.

## Native metrics

System CPU/memory/network names, attributes, types and units follow the pinned OTel
conventions where available. CPU utilization is a 0–1 fraction per logical core/mode;
memory usage/limit are non-monotonic cumulative sums in bytes. Network byte/error/drop
sums are monotonic cumulative per interface/direction. Router load, temperature,
conntrack, WAN state, inventory and delivery health use `flint2.*` metric names.
Counters retain a start across samples and reset it when the counter decreases,
interface identity changes, the clock rolls back or the process restarts. First
observations have unknown starts (`startTimeUnixNano == timeUnixNano`). Unsafe
integers above Lua's exact integer range are omitted. Native metric attributes
exclude device IP/MAC/name labels to control cardinality.
