# Documentation

Flint2 Telemetry collects OpenWrt router observations and exports them through
standard log/metrics formats. Current package: **0.3.1-6**. See
[GitHub Releases](https://github.com/narey83/GL.iNet-Flint2-Telemetry/releases/latest)
for the generic IPK, matching sources, checksums and optional Graylog imports.

| Start here | What it covers |
| --- | --- |
| [Signed feed and LuCI updates](FEED.md) | One-time feed registration, public-key identity, compatible firmware and package updates |
| [Official repository preparation](OPENWRT-SUBMISSION.md) | Maintainer, proposed package split, upstream requirements and outstanding compatibility tests |
| [Current OpenWrt development builds](OPENWRT-CURRENT.md) | Separate source packages, fw4 behavior, APK artifacts and isolated qualification |
| [Install and configure](../README.md#install-and-configure) | Firmware compatibility, IPK installation and GUI-first setup |
| [Configuration](CONFIGURATION.md) | GUI controls, output combinations, UCI defaults, CA trust and authentication |
| [Destinations](BACKENDS.md) | OTLP logs/metrics, ECS NDJSON and GELF; direct HTTPS or an optional proxy |
| [Graylog setup](integrations/GRAYLOG.md) | Native TLS input without Caddy, Docker options, GUI settings and content-pack installation |
| [Graylog dashboard catalogue](integrations/GRAYLOG-DASHBOARDS.md) | Ten dashboards, 183 widgets, computed fields and optional enrichment |
| [Dashboard downloads](../integrations/graylog/README.md) | Native content pack and SHA-256 verification |
| [Event/metrics schema](SCHEMA.md) | ECS field contract, typed OTLP representation and transport projections |
| [Builds and releases](RELEASES.md) | Run GitHub builds, download artifacts and qualify draft releases |
| [Validation evidence](../VALIDATION.md) | Checks actually performed and their limits |
| [Roadmap](../ROADMAP.md) | Delivered features and planned work |

For a logging backend alone, disable native metrics export. Enable metric log
copies if you want measurements in log dashboards. Native OpenTelemetry metrics
need a metrics-capable destination of their own. Caddy is not required for either
signal when its receiver provides HTTPS directly.
