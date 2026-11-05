import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("metric_dashboard", ROOT / "scripts/update-metrics-dashboard.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MetricsDashboardTests(unittest.TestCase):
    def test_preserves_existing_pages_and_user_changes(self):
        view = {"state": {"original": {"widgets": [{"id": "user-widget"}], "titles": {"tab": {"title": "My overview"}}}},
                "description": "User description"}
        search = {"queries": [{"id": "original", "search_types": [{"id": "user-search"}]}]}
        before_view, before_search = copy.deepcopy(view), copy.deepcopy(search)
        changed_view, changed_search, ids = module.update(view, search, "stream")
        self.assertEqual(view, before_view)
        self.assertEqual(search, before_search)
        self.assertEqual(changed_view["state"]["original"], view["state"]["original"])
        self.assertEqual(changed_search["queries"][0], search["queries"][0])
        rerun_view, rerun_search, new_ids = module.update(changed_view, changed_search, "stream", ids)
        self.assertEqual(len(rerun_view["state"]), 4)
        self.assertEqual(len(rerun_search["queries"]), 4)
        self.assertFalse(set(ids) & set(new_ids))
        self.assertEqual(rerun_view["description"], changed_view["description"])

    def test_all_metric_families_and_valid_widget_mapping(self):
        pages = module.pages("stream")
        queries = []
        for page in pages:
            self.assertIn(page.state["titles"]["tab"]["title"],
                          {"System metrics", "Network metrics", "Delivery & catalogue"})
            by_id = {s["id"]: s for s in page.query["search_types"]}
            occupied = set()
            for widget in page.state["widgets"]:
                wid = widget["id"]
                mapped = by_id[page.state["widget_mapping"][wid][0]]
                self.assertEqual(widget["query"], mapped["query"])
                queries.append(mapped["query"]["query_string"])
                if widget["type"] == "aggregation":
                    self.assertEqual(widget["config"]["series"][0]["config"]["name"], mapped["series"][0]["id"])
                    self.assertNotEqual(mapped["series"][0]["type"], "sum", "Do not sum repeated cumulative totals")
                    if mapped["column_groups"]:
                        self.assertFalse(mapped["rollup"], "Do not average unrelated dimension series into a total")
                p = page.state["positions"][wid]
                for x in range(p["col"], p["col"] + p["width"]):
                    self.assertLessEqual(x, 12)
                    for y in range(p["row"], p["row"] + p["height"]):
                        self.assertNotIn((x, y), occupied, "Widget layout overlaps")
                        occupied.add((x, y))
        for metric in ["system.uptime", "system.cpu.utilization", "system.memory.limit", "system.memory.usage",
                       "system.memory.utilization", "system.network.io", "system.network.errors",
                       "system.network.packet.dropped", "flint2.system.load_average", "flint2.temperature",
                       "flint2.conntrack.count", "flint2.conntrack.limit", "flint2.logs.queue.depth",
                       "flint2.logs.delivery.failed", "flint2.logs.dropped", "flint2.metrics.queue.depth",
                       "flint2.metrics.delivery.failed", "flint2.metrics.dropped", "flint2.metrics.rejected",
                       "flint2.wan.up", "flint2.wan.uptime", "flint2.dhcp.lease_records"]:
            self.assertTrue(any(metric in query for query in queries), metric)


if __name__ == "__main__":
    unittest.main()
