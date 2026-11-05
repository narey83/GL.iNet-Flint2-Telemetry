#!/usr/bin/env python3
"""Add native metric pages without replacing existing dashboard pages.

Token is read from stdin. Only pages recorded as managed by this script are
replaced on subsequent runs. --apply performs the reviewed API changes.
"""
try:
    from graylog_fields import migrate
except ModuleNotFoundError:
    from scripts.graylog_fields import migrate
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("provision", ROOT / "scripts/provision-graylog.py")
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)
MANAGED = ROOT / "dist/graylog-metric-pages.json"


class Page:
    def __init__(self, title, stream):
        self.id = str(uuid.uuid4())
        self.stream = stream
        self.query = {"id": self.id, "timerange": {"type": "relative", "from": 3600},
                      "filter": {"type": "stream", "id": stream},
                      "query": {"type": "elasticsearch", "query_string": "flint2:telemetry AND event_kind:metric"},
                      "search_types": []}
        self.state = {"selected_fields": None, "static_message_list_id": None,
                      "titles": {"tab": {"title": title}, "widget": {}}, "widgets": [],
                      "widget_mapping": {}, "positions": {}, "formatting": {"highlighting": []},
                      "display_mode_settings": {"positions": {}}}

    def add(self, title, metric, col, row, width=6, height=3, kind="line", rows=("timestamp",),
            columns=(), operation="avg", window=3600, extra="", fields=None):
        wid, sid = str(uuid.uuid4()), str(uuid.uuid4())
        query = "event_kind:metric"
        if metric:
            query += " AND metric_name:" + (metric if isinstance(metric, str) else "(" + " OR ".join(metric) + ")")
        if extra:
            query += " AND " + extra
        expr = {"type": "elasticsearch", "query_string": query}
        timerange = {"type": "relative", "from": window}
        common = {"timerange": timerange, "query": expr, "streams": [self.stream], "filter": None}

        def groups(names):
            frontend, backend = [], []
            for name in names:
                if name == "timestamp":
                    frontend.append({"field": name, "type": "time", "config": {"interval": {"type": "auto", "scaling": 1.0}}})
                    backend.append({"field": name, "type": "time", "interval": {"type": "auto", "scaling": 1.0}})
                else:
                    frontend.append({"field": name, "type": "values", "config": {"limit": 64}})
                    backend.append({"field": name, "type": "values", "limit": 64})
            return frontend, backend

        if kind == "messages":
            fields = fields or ["timestamp", "metric_name", "metric_value", "metric_unit", "metric_type"]
            widget = {**common, "id": wid, "type": "messages", "config": {"fields": fields,
                      "show_message_row": True, "show_summary": False, "decorators": [],
                      "sort": [{"type": "pivot", "field": "timestamp", "direction": "Descending"}]}}
            search_type = {**common, "id": sid, "type": "messages", "name": "messages", "fields": fields,
                           "limit": 100, "offset": 0, "sort": [{"field": "timestamp", "order": "DESC"}], "decorators": []}
        else:
            front_rows, back_rows = groups(rows)
            front_cols, back_cols = groups(columns)
            function = f"{operation}(metric_value)"
            widget = {**common, "id": wid, "type": "aggregation", "config": {
                "row_pivots": front_rows, "column_pivots": front_cols,
                "series": [{"config": {"name": "Value"}, "function": function}], "sort": [],
                "visualization": kind, "visualization_config": {"interpolation": "linear"} if kind == "line" else None,
                "formatting_settings": None, "rollup": not columns, "event_annotation": False}}
            search_type = {**common, "id": sid, "type": "pivot", "name": "chart",
                           "series": [{"type": operation, "id": "Value", "field": "metric_value"}],
                           "row_groups": back_rows, "column_groups": back_cols, "sort": [], "rollup": not columns}
        self.state["widgets"].append(widget)
        self.state["titles"]["widget"][wid] = title
        self.state["widget_mapping"][wid] = [sid]
        self.state["positions"][wid] = {"col": col, "row": row, "width": width, "height": height}
        self.query["search_types"].append(search_type)


def pages(stream):
    system = Page("System metrics", stream)
    for i, (title, metric, operation) in enumerate([
        ("Host uptime · max 5 min (seconds)", "system.uptime", "max"),
        ("Temperature · average 5 min (°C)", "flint2.temperature", "avg"),
        ("Memory capacity · max 5 min (bytes)", "system.memory.limit", "max"),
        ("Connections · average 5 min", "flint2.conntrack.count", "avg")
    ]):
        system.add(title, metric, 1 + i * 3, 1, 3, 2, "numeric", rows=(), operation=operation, window=300)
    system.add("CPU mode fractions by logical core · 5 min (0–1)", "system.cpu.utilization", 1, 3, 12, 3,
               "table", rows=("metric_attribute_cpu_logical_number",), columns=("metric_attribute_cpu_mode",), window=300)
    system.add("CPU user time fraction by core · 1 hour", "system.cpu.utilization", 1, 6,
               columns=("metric_attribute_cpu_logical_number",), extra="metric_attribute_cpu_mode:user")
    system.add("CPU modes · average across cores (0–1)", "system.cpu.utilization", 7, 6,
               columns=("metric_attribute_cpu_mode",))
    system.add("Memory used and available · bytes", "system.memory.usage", 1, 9,
               columns=("metric_attribute_system_memory_state",))
    system.add("Memory used and available · fraction (0–1)", "system.memory.utilization", 7, 9,
               columns=("metric_attribute_system_memory_state",))
    system.add("Load average · 1, 5 and 15 minute windows", "flint2.system.load_average", 1, 12,
               columns=("metric_attribute_flint2_window_minutes",))
    system.add("SoC temperature · °C", "flint2.temperature", 7, 12)
    system.add("Connection table count and capacity", ("flint2.conntrack.count", "flint2.conntrack.limit"),
               1, 15, 12, columns=("metric_name",))

    network = Page("Network metrics", stream)
    for i, (title, metric, window, operation) in enumerate([
        ("WAN up · min 5 min (1 = up)", "flint2.wan.up", 300, "min"),
        ("WAN session uptime · max 5 min (seconds)", "flint2.wan.uptime", 300, "max"),
        ("DHCP lease records · max 10 min (not online devices)", "flint2.dhcp.lease_records", 600, "max")
    ]):
        network.add(title, metric, 1 + i * 4, 1, 4, 2, "numeric", rows=(), window=window, operation=operation)
    network.add("Received bytes · cumulative totals by interface", "system.network.io", 1, 3,
                columns=("metric_attribute_network_interface_name",), extra="metric_attribute_network_io_direction:receive", operation="max")
    network.add("Transmitted bytes · cumulative totals by interface", "system.network.io", 7, 3,
                columns=("metric_attribute_network_interface_name",), extra="metric_attribute_network_io_direction:transmit", operation="max")
    network.add("Highest byte counter observed · 5 min (not interval traffic)", "system.network.io", 1, 6, 12, 3,
                "table", rows=("metric_attribute_network_interface_name",), columns=("metric_attribute_network_io_direction",), operation="max", window=300)
    network.add("Highest error counters observed · 5 min", "system.network.errors", 1, 9, 6, 3,
                "table", rows=("metric_attribute_network_interface_name",), columns=("metric_attribute_network_io_direction",), operation="max", window=300)
    network.add("Highest dropped-packet counters observed · 5 min", "system.network.packet.dropped", 7, 9, 6, 3,
                "table", rows=("metric_attribute_network_interface_name",), columns=("metric_attribute_network_io_direction",), operation="max", window=300)
    network.add("WAN availability · 1 = up, 0 = down", "flint2.wan.up", 1, 12, operation="min")
    network.add("WAN session uptime · seconds (drops on reconnect)", "flint2.wan.uptime", 7, 12, operation="max")
    network.add("DHCP inventory size · lease records", "flint2.dhcp.lease_records", 1, 15, 12, operation="max")

    delivery = Page("Delivery & catalogue", stream)
    delivery.add("Graylog queue depth · records", "flint2.logs.queue.depth", 1, 1, operation="max")
    delivery.add("Graylog delivery failure · 1 = failed, 0 = healthy", "flint2.logs.delivery.failed", 7, 1, operation="max")
    delivery.add("Discarded log records · total since agent start", "flint2.logs.dropped", 1, 4, operation="max")
    delivery.add("Optional OTLP exporter health · empty while disabled", (
        "flint2.metrics.queue.depth", "flint2.metrics.delivery.failed", "flint2.metrics.dropped", "flint2.metrics.rejected"),
        7, 4, 6, 3, "table", rows=("metric_name",), operation="max", window=300)
    delivery.add("All metric families · highest sample value, last 10 min (across series)", None,
                 1, 7, 12, 5, "table", rows=("metric_name",), operation="max", window=600)
    delivery.add("All native metric samples · expand a row for attributes and counter starts", None,
                 1, 12, 12, 6, "messages", window=600,
                 fields=["timestamp", "metric_name", "metric_value", "metric_unit", "metric_type",
                         "metric_temporality", "metric_start_time_unix_nano"])
    for page in (system, network, delivery):
        page.query = migrate(page.query)
        page.state = migrate(page.state)
    return [system, network, delivery]


def update(view, search, stream, managed_ids=()):
    view, search = copy.deepcopy(view), copy.deepcopy(search)
    managed_ids = set(managed_ids)
    search["queries"] = [q for q in search["queries"] if q["id"] not in managed_ids]
    view["state"] = {key: state for key, state in view["state"].items() if key not in managed_ids}
    new_pages = pages(stream)
    for page in new_pages:
        search["queries"].append(page.query)
        view["state"][page.id] = page.state
    note = " Native metric pages show per-core CPU, memory states, load windows, cumulative interface counters and delivery health. Counters are not interval traffic; interface totals overlap. Optional OTLP health is empty while disabled."
    if note.strip() not in view.get("description", ""):
        view["description"] = view.get("description", "") + note
    return view, search, [p.id for p in new_pages]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    resource_ids = json.loads((ROOT / "dist/graylog-resources.json").read_text())
    api = provision.Graylog(sys.stdin.read().strip())
    view = api.request("GET", "/views/" + resource_ids["dashboard_id"])
    search = api.request("GET", "/views/search/" + view["search_id"])
    managed_ids = json.loads(MANAGED.read_text())["query_ids"] if MANAGED.exists() else []
    new_view, new_search, ids = update(view, search, resource_ids["stream_id"], managed_ids)
    if not args.apply:
        print(json.dumps({"view": new_view, "search": new_search}, indent=2))
        return
    # Save a local before-image of the exact owning resources for recovery.
    (ROOT / "dist/graylog-before-native-metrics.json").write_text(json.dumps({"view": view, "search": search}, indent=2) + "\n")
    # Validate every generated search before mutating the stored dashboard.
    result = api.request("POST", "/views/search/sync", new_search)
    for query in result.get("results", {}).values():
        if query.get("errors"):
            raise RuntimeError(query["errors"])
        for search_type in query.get("search_types", {}).values():
            if search_type.get("errors"):
                raise RuntimeError(search_type["errors"])
    saved_search = api.request("POST", "/views/search", new_search)
    assert saved_search["id"] == view["search_id"], "Search ID changed unexpectedly"
    api.request("PUT", "/views/" + view["id"], new_view)
    MANAGED.write_text(json.dumps({"dashboard_id": view["id"], "query_ids": ids}, indent=2) + "\n")
    (ROOT / "dist/graylog-dashboard.json").write_text(json.dumps(new_view, indent=2) + "\n")
    print(json.dumps({"dashboard": resource_ids["url"], "added_pages": len(ids),
                      "new_widgets": sum(len(new_view["state"][i]["widgets"]) for i in ids)}, indent=2))


if __name__ == "__main__":
    main()
