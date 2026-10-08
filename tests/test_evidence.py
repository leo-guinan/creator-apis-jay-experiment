import unittest
import json
import tempfile
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from creator_apis.api import ReportingAPI, create_handler
from creator_apis.evidence import EvidenceLedger
from creator_apis.reporting import LedgerReport
from creator_apis.store import LedgerStore
from creator_apis.sqlite_store import SQLiteLedgerStore


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = EvidenceLedger(
            fixture_status="synthetic",
            campaign_id="campaign:jay-14day-001",
            experiment_id="experiment:ai-roi-am",
        )
        self.ledger.add_contributor("contributor:jay", "Jay")
        self.ledger.add_source("source:jay-interview", "contributor:jay")
        self.ledger.add_content_block("block:work-not-done", "source:jay-interview")
        self.ledger.add_artifact("artifact:jay-clip-v1", ["block:work-not-done"])
        self.ledger.add_placement(
            "placement:youtube-jay-clip-v1", "artifact:jay-clip-v1", "youtube"
        )
        self.ledger.add_route(
            "route:jay-youtube-001",
            "placement:youtube-jay-clip-v1",
            "https://example.test/calibration",
        )
        self.ledger.add_placement(
            "placement:x-jay-clip-v1", "artifact:jay-clip-v1", "x"
        )
        self.ledger.add_route(
            "route:jay-x-001",
            "placement:x-jay-clip-v1",
            "https://example.test/calibration",
        )

    def test_direct_purchase_traces_to_contributor_and_accrues_synthetic_royalty(self):
        self.ledger.record_event(
            "event:click-1",
            "route_click",
            session_id="session:1",
            route_id="route:jay-youtube-001",
        )
        self.ledger.record_conversion(
            "conversion:1",
            session_id="session:1",
            amount_cents=100_000,
            purchase_event_id="event:purchase-1",
        )

        result = self.ledger.direct_attribution("conversion:1")
        accrual = self.ledger.accrue_royalty("conversion:1", rate=0.10)

        self.assertEqual(result.classification, "direct")
        self.assertEqual(result.contributor_id, "contributor:jay")
        self.assertEqual(
            result.trace,
            [
                "route:jay-youtube-001",
                "placement:youtube-jay-clip-v1",
                "artifact:jay-clip-v1",
                "block:work-not-done",
                "source:jay-interview",
                "contributor:jay",
            ],
        )
        self.assertEqual(accrual.amount_cents, 10_000)
        self.assertEqual(accrual.fixture_status, "synthetic")

    def test_second_placement_has_same_experiment_and_traces_independently(self):
        self.ledger.record_event(
            "event:x-click-1",
            "route_click",
            session_id="session:x-1",
            route_id="route:jay-x-001",
        )
        self.ledger.record_conversion(
            "conversion:x-1",
            session_id="session:x-1",
            amount_cents=100_000,
            purchase_event_id="event:x-purchase-1",
        )

        result = self.ledger.direct_attribution("conversion:x-1")
        exported = self.ledger.export()

        self.assertEqual(result.classification, "direct")
        self.assertEqual(result.trace[0], "route:jay-x-001")
        self.assertEqual(result.experiment_id, "experiment:ai-roi-am")
        self.assertEqual(
            exported["records"]["placement:x-jay-clip-v1"]["channel"], "x"
        )

    def test_multiple_route_clicks_in_one_session_are_ambiguous(self):
        self.ledger.record_event(
            "event:ambiguous-youtube-click",
            "route_click",
            session_id="session:ambiguous",
            route_id="route:jay-youtube-001",
        )
        self.ledger.record_event(
            "event:ambiguous-x-click",
            "route_click",
            session_id="session:ambiguous",
            route_id="route:jay-x-001",
        )
        self.ledger.record_conversion(
            "conversion:ambiguous",
            session_id="session:ambiguous",
            amount_cents=100_000,
            purchase_event_id="event:ambiguous-purchase",
        )

        result = self.ledger.direct_attribution("conversion:ambiguous")

        self.assertEqual(result.classification, "unknown")
        self.assertEqual(result.reason, "ambiguous_route_clicks")
        self.assertEqual(result.evidence_event_ids, [
            "event:ambiguous-youtube-click",
            "event:ambiguous-x-click",
        ])

    def test_session_mismatch_stays_unknown_and_has_no_royalty(self):
        self.ledger.record_event(
            "event:click-2",
            "route_click",
            session_id="session:click",
            route_id="route:jay-youtube-001",
        )
        self.ledger.record_conversion(
            "conversion:2",
            session_id="session:other",
            amount_cents=100_000,
            purchase_event_id="event:purchase-2",
        )

        result = self.ledger.direct_attribution("conversion:2")

        self.assertEqual(result.classification, "unknown")
        self.assertIsNone(result.contributor_id)
        with self.assertRaises(ValueError):
            self.ledger.accrue_royalty("conversion:2", rate=0.10)

    def test_events_are_append_only_and_exports_are_marked_synthetic(self):
        self.ledger.record_event(
            "event:view-1", "landing_page_view", session_id="session:1"
        )
        self.ledger.record_event(
            "event:view-2", "landing_page_view", session_id="session:1"
        )

        exported = self.ledger.export()

        self.assertEqual([event["event_id"] for event in exported["events"]], [
            "event:view-1",
            "event:view-2",
        ])
        self.assertEqual(exported["fixture_status"], "synthetic")
        self.assertEqual(exported["records"]["contributor:jay"]["fixture_status"], "synthetic")
        self.assertEqual(exported["campaign_id"], "campaign:jay-14day-001")
        self.assertEqual(exported["experiment_id"], "experiment:ai-roi-am")
        self.assertEqual(exported["events"][0]["experiment_id"], "experiment:ai-roi-am")

    def test_report_summarizes_channels_events_and_direct_royalty(self):
        self.ledger.record_event(
            "event:report-click",
            "route_click",
            session_id="session:report",
            route_id="route:jay-youtube-001",
        )
        self.ledger.record_conversion(
            "conversion:report",
            session_id="session:report",
            amount_cents=100_000,
            purchase_event_id="event:report-purchase",
        )

        summary = LedgerReport(self.ledger).summary(royalty_rate=0.10)

        self.assertEqual(summary["scope"]["campaign_id"], "campaign:jay-14day-001")
        self.assertEqual(summary["counts"]["placements"], 2)
        self.assertEqual(summary["counts"]["routes"], 2)
        self.assertEqual(summary["placements_by_channel"], {"youtube": 1, "x": 1})
        self.assertEqual(summary["events_by_type"]["route_click"], 1)
        self.assertEqual(summary["attributions"][0]["classification"], "direct")
        self.assertEqual(summary["royalty"]["accrued_amount_cents"], 10_000)

    def test_report_does_not_count_out_of_scope_records(self):
        self.ledger.add_placement(
            "placement:other", "artifact:jay-clip-v1", "linkedin",
            campaign_id="campaign:other", experiment_id="experiment:other",
        )

        summary = LedgerReport(self.ledger).summary(
            campaign_id="campaign:jay-14day-001",
            experiment_id="experiment:ai-roi-am",
        )

        self.assertEqual(summary["counts"]["placements"], 2)
        self.assertNotIn("linkedin", summary["placements_by_channel"])

    def test_json_store_round_trip_preserves_report(self):
        self.ledger.record_event(
            "event:stored-click",
            "route_click",
            session_id="session:stored",
            route_id="route:jay-youtube-001",
        )
        self.ledger.record_conversion(
            "conversion:stored",
            session_id="session:stored",
            amount_cents=100_000,
            purchase_event_id="event:stored-purchase",
        )
        expected = LedgerReport(self.ledger).summary(royalty_rate=0.10)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            LedgerStore.save(self.ledger, path)
            restored = LedgerStore.load(path)

        self.assertEqual(LedgerReport(restored).summary(royalty_rate=0.10), expected)

    def test_versioned_http_report_endpoint_returns_json(self):
        self.ledger.record_event(
            "event:http-click",
            "route_click",
            session_id="session:http",
            route_id="route:jay-youtube-001",
        )
        self.ledger.record_conversion(
            "conversion:http",
            session_id="session:http",
            amount_cents=100_000,
            purchase_event_id="event:http-purchase",
        )
        server = __import__("http.server").server.HTTPServer(
            ("127.0.0.1", 0), create_handler(ReportingAPI(self.ledger))
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(
                f"http://127.0.0.1:{server.server_port}/v1/reports?royalty_rate=0.1"
            ) as response:
                payload = json.load(response)
            self.assertEqual(payload["api_version"], "v1")
            self.assertEqual(payload["report"]["counts"]["conversions"], 1)
            self.assertEqual(payload["report"]["royalty"]["accrued_amount_cents"], 10_000)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_reporting_api_rejects_unknown_query_parameters(self):
        with self.assertRaises(ValueError):
            ReportingAPI(self.ledger).get_report({"unexpected": "value"})

    def test_sqlite_event_survives_store_reload_and_changes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            store.append_event({
                "event_id": "event:durable-click",
                "event_type": "route_click",
                "session_id": "session:durable",
                "route_id": "route:jay-youtube-001",
            })

            reloaded = SQLiteLedgerStore(path)
            report = LedgerReport(reloaded.load()).summary()

        self.assertEqual(report["counts"]["events"], 1)
        self.assertEqual(report["events_by_type"]["route_click"], 1)

    def test_post_event_is_idempotent_and_report_reads_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(ReportingAPI(store=store))
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            body = json.dumps({
                "event_id": "event:http-durable-click",
                "event_type": "route_click",
                "session_id": "session:http-durable",
                "route_id": "route:jay-x-001",
            }).encode()
            request = Request(
                f"http://127.0.0.1:{server.server_port}/v1/events",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urlopen(request) as response:
                    first = json.load(response)
                with urlopen(request) as response:
                    second = json.load(response)
                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/v1/reports"
                ) as response:
                    report = json.load(response)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(first["created"], True)
        self.assertEqual(second["created"], False)
        self.assertEqual(report["report"]["counts"]["events"], 1)

    def test_post_event_rejects_unknown_route(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(ReportingAPI(store=store))
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            request = Request(
                f"http://127.0.0.1:{server.server_port}/v1/events",
                data=json.dumps({
                    "event_id": "event:bad-route",
                    "event_type": "route_click",
                    "session_id": "session:bad",
                    "route_id": "route:missing",
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
