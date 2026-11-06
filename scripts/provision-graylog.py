"""Create/update only the dedicated Flint2 input, stream, search and dashboard.

API token is read from stdin, never stored. Run with --apply to write to Graylog.
"""
try:
    from graylog_fields import migrate
except ModuleNotFoundError:
    from scripts.graylog_fields import migrate
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.parse
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TITLE = "Flint2 Telemetry"
MBPS_RULE_TITLE = "Flint2 interface Mbps display"
MBPS_PIPELINE_TITLE = "Flint2 dashboard units"
MBPS_RULE_SOURCE = '''rule "Flint2 interface Mbps display"
when
    has_field("flint2_rx_bits_per_second") && has_field("flint2_tx_bits_per_second")
then
    set_field("flint2_dashboard_rx_mbps", to_double($message.flint2_rx_bits_per_second) / 1000000.0);
    set_field("flint2_dashboard_tx_mbps", to_double($message.flint2_tx_bits_per_second) / 1000000.0);
end'''


class Graylog:
    def __init__(self, token, base_url=None, ca_file=None):
        self.auth = base64.b64encode((token + ":token").encode()).decode()
        profile=Path(os.environ.get("FLINT2_SITE_CONFIG",ROOT/"local/site.json"))
        settings=json.loads(profile.read_text()) if profile.exists() else {}
        self.base_url=(base_url or os.environ.get("GRAYLOG_URL") or settings.get("graylog_url","")).rstrip("/")
        parsed=urllib.parse.urlsplit(self.base_url)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Configure an HTTPS GRAYLOG_URL or local/site.json")
        self.ca_file=Path(ca_file or os.environ.get("GRAYLOG_CA_FILE") or settings.get("graylog_ca_file","/etc/ssl/certs/ca-certificates.crt"))
        if not self.ca_file.is_absolute():self.ca_file=ROOT/self.ca_file

    def request(self, method, path, body=None):
        if not path.startswith("/") or any(c in path for c in '\n\r"'):
            raise ValueError("Invalid Graylog API path")
        config = ('url = '+json.dumps(self.base_url+'/api'+path)+'\n'
                  f'header = "Authorization: Basic {self.auth}"\n'
                  'header = "X-Requested-By: flint2-provisioner"\n'
                  'header = "Content-Type: application/json"\n'
                  'header = "Accept: application/json"\n'
                  'cacert = '+json.dumps(str(self.ca_file))+'\n')
        command = ["curl", "--silent", "--show-error", "--fail-with-body", "--max-time", "30",
                   "--request", method, "--config", "-"]
        if body is not None:
            # curl config accepts JSON-escaped strings, keeping the token off argv.
            config += "data = " + json.dumps(json.dumps(body)) + "\n"
        result = subprocess.run(command, check=False, input=config, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"{method} {path}: {result.stderr} {result.stdout[:1500]}")
        return json.loads(result.stdout) if result.stdout.strip() else {}


def dashboard(stream_id):
    query_id = str(uuid.uuid4())
    widgets, search_types, titles, mapping, positions = [], [], {}, {}, {}

    def widget(title, query, series, position, kind="numeric", group=None, window=300,
               fixed_interval=None):
        widget_id, search_id = str(uuid.uuid4()), str(uuid.uuid4())
        pivots, row_groups = [], []
        if group == "timestamp":
            widget_interval = ({"type": "timeunit", "value": fixed_interval, "unit": "minutes"}
                               if fixed_interval else {"type": "auto", "scaling": 1.0})
            search_interval = ({"type": "timeunit", "timeunit": f"{fixed_interval}m"}
                               if fixed_interval else {"type": "auto", "scaling": 1.0})
            pivots = [{"field": "timestamp", "type": "time", "config": {"interval": widget_interval}}]
            row_groups = [{"type": "time", "field": "timestamp", "interval": search_interval}]
        elif group:
            pivots = [{"field": group, "type": "values", "config": {"limit": 256}}]
            row_groups = [{"type": "values", "field": group, "limit": 256}]
        expression = {"type": "elasticsearch", "query_string": query}
        timerange = {"type": "relative", "from": window}
        widget_series, search_series = [], []
        for function, field, label in series:
            expression_text = f"{function}({field or ''})"
            widget_series.append({"config": {"name": label}, "function": expression_text})
            search_series.append({"type": function, "id": label, "field": field})
        widgets.append({"id": widget_id, "type": "aggregation", "filter": None,
                        "timerange": timerange, "query": expression, "streams": [stream_id],
                        "config": {"row_pivots": pivots, "column_pivots": [], "series": widget_series,
                                   "sort": [], "visualization": kind, "visualization_config":
                                   {"interpolation": "linear"} if kind == "line" else None,
                                   "formatting_settings": None, "rollup": True, "event_annotation": False}})
        search_types.append({"id": search_id, "type": "pivot", "name": "chart", "timerange": timerange,
                             "query": expression, "streams": [stream_id], "series": search_series,
                             "row_groups": row_groups, "column_groups": [], "sort": [], "rollup": True,
                             "filter": None})
        titles[widget_id], mapping[widget_id], positions[widget_id] = title, [search_id], position

    def pos(col, row, width=3, height=2):
        return {"col": col, "row": row, "width": width, "height": height}

    for i, (title, field) in enumerate([
        ("CPU average · 5 min (%)", "cpu_used_percent"),
        ("Memory average · 5 min (%)", "memory_used_percent"),
        ("Temperature average · 5 min (°C)", "temperature_celsius"),
        ("Connections average · 5 min", "conntrack_count")
    ]):
        widget(title, "event_kind:system", [("avg", field, title)], pos(1 + i * 3, 1))
    widget("CPU & memory · 24 hours (%)", "event_kind:system",
           [("avg", "cpu_used_percent", "CPU %"), ("avg", "memory_used_percent", "Memory %")],
           pos(1, 3, 6, 3), "line", "timestamp", 86400)
    widget("WAN traffic · 24 hours (Mbps)", "event_kind:interface AND interface:pppoe-wan",
           [("avg", "flint2_dashboard_rx_mbps", "Download Mbps"), ("avg", "flint2_dashboard_tx_mbps", "Upload Mbps")],
           pos(7, 3, 6, 3), "line", "timestamp", 86400, fixed_interval=5)
    widget("Temperature · 24 hours (°C)", "event_kind:system",
           [("avg", "temperature_celsius", "°C")], pos(1, 6, 6, 3), "line", "timestamp", 86400)
    widget("Connection table · 24 hours", "event_kind:system",
           [("avg", "conntrack_count", "Connections"), ("max", "conntrack_max", "Capacity")],
           pos(7, 6, 6, 3), "line", "timestamp", 86400)
    widget("WAN availability · 24 hours (1 = up)", "event_kind:wan", [("min", "wan_up", "WAN up")],
           pos(1, 9, 6, 3), "line", "timestamp", 86400)
    widget("Agent delivery · 24 hours", "event_kind:system",
           [("max", "queue_depth", "Queued records"), ("max", "queue_dropped_total", "Dropped since agent start")],
           pos(7, 9, 6, 3), "line", "timestamp", 86400)
    widget("Interfaces · average rates, last 5 min", "event_kind:interface",
           [("avg", "flint2_dashboard_rx_mbps", "RX Mbps"), ("avg", "flint2_dashboard_tx_mbps", "TX Mbps"),
            ("max", "rx_errors", "RX errors since interface creation"), ("max", "tx_errors", "TX errors since interface creation")],
           pos(1, 12, 12, 3), "table", "interface")
    widget("DHCP inventory · names seen in last 10 min", "event_kind:device",
           [("card", "device_ip", "Distinct IPs"), ("card", "device_mac", "Distinct MACs")],
           pos(1, 15, 6, 4), "table", "device_name", 600)
    widget("DHCP records by network · last 10 min", "event_kind:device",
           [("card", "device_mac", "Distinct MAC addresses")], pos(7, 15, 6, 4), "table", "device_network", 600)
    # Dedicated message widget for changes; keep standard searchable structured fields.
    wid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    expr, timerange = {"type": "elasticsearch", "query_string": "event_kind:event"}, {"type": "relative", "from": 86400}
    fields = ["timestamp", "event_type", "message", "interface", "wan_ipv4", "wan_up"]
    widgets.append({"id": wid, "type": "messages", "filter": None, "timerange": timerange,
                    "query": expr, "streams": [stream_id], "config": {"fields": fields,
                    "show_message_row": True, "show_summary": False, "decorators": [],
                    "sort": [{"type": "pivot", "field": "timestamp", "direction": "Descending"}]}})
    search_types.append({"id": sid, "type": "messages", "name": "messages", "timerange": timerange,
                         "query": expr, "streams": [stream_id], "limit": 100, "offset": 0,
                         "sort": [{"field": "timestamp", "order": "DESC"}], "fields": fields, "decorators": [], "filter": None})
    titles[wid], mapping[wid], positions[wid] = "WAN, interface and agent events · 24 hours", [sid], pos(1, 19, 12, 4)
    search = {"queries": [{"id": query_id, "timerange": {"type": "relative", "from": 86400},
                            "filter": None, "query": {"type": "elasticsearch", "query_string": "flint2:telemetry"},
                            "search_types": search_types}], "parameters": []}
    view = {"type": "DASHBOARD", "title": TITLE, "summary": "Flint2 router health, network rates, WAN events and DHCP inventory",
            "description": "30-second snapshots; 5-minute averages in summary tiles; charts cover 24 hours. "
            "DHCP records are inventory, not proof of online status. Interface totals overlap; do not sum bridges and physical ports. "
            "Counter resets omit the first rate sample. Delivery uses a bounded RAM queue; gaps are possible during reboot or extended outages.",
            "properties": [], "requires": {}, "state": {query_id: {"selected_fields": None,
            "static_message_list_id": None, "titles": {"widget": titles}, "widgets": widgets,
            "widget_mapping": mapping, "positions": positions, "formatting": {"highlighting": []},
            "display_mode_settings": {"positions": {}}}}}
    return migrate(search), migrate(view)


def ensure_mbps_pipeline(api, stream_id):
    rules = api.request("GET", "/system/pipelines/rule")
    rule = {"title": MBPS_RULE_TITLE,
            "description": "Decimal megabits per second for dashboard widgets; canonical bits/sec fields remain intact",
            "source": MBPS_RULE_SOURCE}
    existing = next((item for item in rules if item["title"] == MBPS_RULE_TITLE), None)
    if existing:
        api.request("PUT", "/system/pipelines/rule/" + existing["id"], {**rule, "id": existing["id"]})
    else:
        api.request("POST", "/system/pipelines/rule", rule)
    pipelines = api.request("GET", "/system/pipelines/pipeline")
    connections = api.request("GET", "/system/pipelines/connections")
    connected = next((item for item in connections if item["stream_id"] == stream_id), None)
    pipeline_ids = set(connected["pipeline_ids"] if connected else [])
    # Existing installations may already run this rule in their routing pipeline.
    if any(item["id"] in pipeline_ids and f'rule "{MBPS_RULE_TITLE}"' in item.get("source", "")
           for item in pipelines):
        return
    source = f'pipeline "{MBPS_PIPELINE_TITLE}"\nstage 0 match either\nrule "{MBPS_RULE_TITLE}"\nend'
    pipeline = {"title": MBPS_PIPELINE_TITLE, "description": "Dashboard-only rate units", "source": source}
    existing = next((item for item in pipelines if item["title"] == MBPS_PIPELINE_TITLE), None)
    if existing:
        saved = api.request("PUT", "/system/pipelines/pipeline/" + existing["id"],
                            {**pipeline, "id": existing["id"]})
    else:
        saved = api.request("POST", "/system/pipelines/pipeline", pipeline)
    pipeline_ids.add(saved["id"])
    api.request("POST", "/system/pipelines/connections/to_stream",
                {"stream_id": stream_id, "pipeline_ids": sorted(pipeline_ids)})


def provision(api):
    (ROOT / "dist").mkdir(parents=True, exist_ok=True)
    inputs = api.request("GET", "/system/inputs")["inputs"]
    matching = [item for item in inputs if item["title"] == TITLE]
    if matching:
        item = matching[0]
        if item["type"] != "org.graylog2.inputs.gelf.http.GELFHttpInput" or item["attributes"]["port"] != 12201:
            raise ValueError("Existing Flint2 input has an unexpected type or port")
        input_id = item["id"]
    else:
        input_id = api.request("POST", "/system/inputs", {"title": TITLE,
            "type": "org.graylog2.inputs.gelf.http.GELFHttpInput", "global": True,
            "configuration": {"bind_address": os.environ.get("GRAYLOG_INPUT_BIND_ADDRESS", "127.0.0.1"),
                "port": 12201, "recv_buffer_size": 1048576,
                "number_worker_threads": 2, "tls_enable": False, "enable_bulk_receiving": True,
                "enable_cors": False, "max_chunk_size": 262144, "idle_writer_timeout": 60}})["id"]
    streams = api.request("GET", "/streams")["streams"]
    stream = next((s for s in streams if s["title"] == TITLE), None)
    if stream:
        stream_id = stream["id"]
    else:
        index_id = os.environ.get("GRAYLOG_INDEX_SET_ID") or next(
            (s["index_set_id"] for s in streams if s["title"] == "Syslog"), None)
        if index_id is None:
            index_sets = api.request("GET", "/system/indices/index_sets")["index_sets"]
            index_id = next(s["id"] for s in index_sets if s.get("default"))
        stream_id = api.request("POST", "/streams", {"title": TITLE, "description": "Structured Flint2 router telemetry",
            "index_set_id": index_id, "matching_type": "AND", "remove_matches_from_default_stream": True})["stream_id"]
        api.request("POST", f"/streams/{stream_id}/rules", {"field": "gl2_source_input", "type": 1,
                    "value": input_id, "inverted": False, "description": "Dedicated Flint2 GELF input"})
    api.request("POST", f"/streams/{stream_id}/resume")
    ensure_mbps_pipeline(api, stream_id)
    search, view = dashboard(stream_id)
    views = api.request("GET", "/views")["views"]
    existing = next((v for v in views if v["title"] == TITLE and v["type"] == "DASHBOARD"), None)
    if existing:
        saved_search = api.request("POST", '/views/search', {**search, "id": existing["search_id"]})
        view["search_id"] = saved_search["id"]
        saved = api.request("PUT", f'/views/{existing["id"]}', {**view, "id": existing["id"]})
    else:
        saved_search = api.request("POST", "/views/search", search)
        view["search_id"] = saved_search["id"]
        saved = api.request("POST", "/views", view)
    result = {"input_id": input_id, "stream_id": stream_id, "dashboard_id": saved["id"],
              "search_id": view["search_id"], "url": api.base_url+"/dashboards/" + saved["id"]}
    (ROOT / "dist/graylog-resources.json").write_text(json.dumps(result, indent=2) + "\n")
    (ROOT / "dist/graylog-dashboard.json").write_text(json.dumps(view, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        provision(Graylog(sys.stdin.read().strip()))
    else:
        search, view = dashboard("STREAM_ID")
        print(json.dumps({"search": search, "view": view}, indent=2))
