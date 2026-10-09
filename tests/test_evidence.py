import unittest
import json
import http.client
import os
import sqlite3
import subprocess
import sys
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

    def test_health_endpoint_reports_local_read_only_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteLedgerStore.create(Path(directory) / "direct.sqlite", self.ledger)
            api = ReportingAPI(store=store, scenario_stores={"direct": store})
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(api, dashboard_path=Path(__file__).parents[1] / "app" / "index.html")
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/healthz") as response:
                    health = json.load(response)
                checker = Path(__file__).parents[1] / "scripts" / "check_local_server.py"
                environment = dict(os.environ)
                environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
                check = subprocess.run(
                    [sys.executable, str(checker), "--base-url", f"http://127.0.0.1:{server.server_port}",
                     "--output", str(Path(directory) / "health-check.json")],
                    check=True, capture_output=True, text=True, env=environment,
                )
                health_check = json.loads((Path(directory) / "health-check.json").read_text(encoding="utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["api_version"], "v1")
        self.assertEqual(health["fixture_status"], "synthetic")
        self.assertEqual(health["storage"], "sqlite")
        self.assertEqual(health["scenarios"], ["direct"])
        self.assertTrue(health["read_only"])
        self.assertIn("status=verified", check.stdout)
        self.assertEqual(health_check["status"], "verified")

    def test_local_audit_reports_degraded_without_backup_and_serves_read_only_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteLedgerStore.create(Path(directory) / "audit.sqlite", self.ledger)
            api = ReportingAPI(store=store)
            server = __import__("http.server").server.HTTPServer(("127.0.0.1", 0), create_handler(api))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/audit") as response:
                    audit = json.load(response)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()
        self.assertEqual(audit["api_version"], "v1")
        self.assertEqual(audit["status"], "degraded")
        self.assertEqual(audit["integrity"]["status"], "verified")
        self.assertIn("no verified backup receipt configured", audit["warnings"])

    def test_audit_state_matrix_and_http_statuses(self):
        root = Path(__file__).parents[1]
        checker = root / "scripts" / "check_audit_states.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit-states.json"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            result = subprocess.run([sys.executable, str(checker), "--output", str(output)], check=True, capture_output=True, text=True, env=environment)
            receipt = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("verified", result.stdout)
        self.assertEqual(receipt["status"], "verified")
        self.assertEqual(receipt["states"]["ready"]["audit"]["status"], "ready")
        self.assertEqual(receipt["states"]["degraded"]["audit"]["status"], "degraded")
        self.assertEqual(receipt["states"]["blocked"]["audit"]["status"], "blocked")
        self.assertEqual(receipt["states"]["ready"]["http_status"], 200)
        self.assertEqual(receipt["states"]["degraded"]["http_status"], 200)
        self.assertEqual(receipt["states"]["blocked"]["http_status"], 503)

    def test_scenario_report_selection_is_fixed_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "direct.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            api = ReportingAPI(scenario_stores={"direct": store})
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(api)
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/scenarios") as response:
                    scenarios = json.load(response)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/reports?scenario=direct") as response:
                    report = json.load(response)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(scenarios["scenarios"], ["direct"])
        self.assertEqual(report["report"]["fixture_status"], "synthetic")
        with self.assertRaises(ValueError):
            api.get_report({"scenario": "../outside"})

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

    def test_dashboard_asset_declares_read_only_report_contract(self):
        dashboard = Path(__file__).parents[1] / "app" / "index.html"
        source = dashboard.read_text(encoding="utf-8")

        self.assertIn("Creator APIs report", source)
        self.assertIn("/v1/reports", source)
        self.assertIn("fixture_status", source)
        self.assertIn("placements_by_channel", source)
        self.assertIn("/v1/scenarios", source)
        self.assertIn("activeScenario", source)
        self.assertIn("response.status === 404", source)

    def test_http_root_serves_dashboard_asset(self):
        dashboard = Path(__file__).parents[1] / "app" / "index.html"
        server = __import__("http.server").server.HTTPServer(
            ("127.0.0.1", 0),
            create_handler(ReportingAPI(self.ledger), dashboard_path=dashboard),
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
                body = response.read().decode()
                content_type = response.headers["Content-Type"]
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertIn("Creator APIs report", body)
        self.assertEqual(content_type, "text/html; charset=utf-8")

    def test_route_redirect_records_durable_click_and_reuses_session_cookie(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(ReportingAPI(store=store))
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "/r/route:jay-youtube-001")
                first = connection.getresponse()
                cookie = first.getheader("Set-Cookie")
                first_location = first.getheader("Location")
                first.read()
                connection.close()

                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request(
                    "GET",
                    "/r/route:jay-youtube-001",
                    headers={"Cookie": cookie.split(";", 1)[0]},
                )
                second = connection.getresponse()
                second.read()
                connection.close()
                durable = SQLiteLedgerStore(path).load()
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        clicks = [event for event in durable.events if event["event_type"] == "route_click"]
        self.assertEqual(first.status, 302)
        self.assertEqual(second.status, 302)
        self.assertEqual(first_location, "https://example.test/calibration")
        self.assertIsNotNone(cookie)
        self.assertEqual(len(clicks), 2)
        self.assertEqual(clicks[0]["session_id"], clicks[1]["session_id"])
        self.assertIn("observed_at", clicks[0])

    def test_route_redirect_rejects_unknown_route(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(ReportingAPI(store=store))
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "/r/route:missing")
                response = connection.getresponse()
                response.read()
                connection.close()
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(response.status, 404)

    def test_local_conversion_endpoint_uses_route_cookie_and_updates_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(ReportingAPI(store=store))
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "/r/route:jay-youtube-001")
                click_response = connection.getresponse()
                cookie = click_response.getheader("Set-Cookie").split(";", 1)[0]
                click_response.read()

                body = json.dumps({"conversion_id": "conversion:http-local", "amount_cents": 100_000})
                connection.request(
                    "POST", "/v1/conversions", body=body,
                    headers={"Content-Type": "application/json", "Content-Length": str(len(body)), "Cookie": cookie},
                )
                conversion_response = connection.getresponse()
                conversion_payload = json.loads(conversion_response.read())
                connection.request(
                    "POST", "/v1/conversions", body=body,
                    headers={"Content-Type": "application/json", "Content-Length": str(len(body)), "Cookie": cookie},
                )
                replay_response = connection.getresponse()
                replay_payload = json.loads(replay_response.read())
                report = ReportingAPI(store=store).get_report()["report"]
                connection.close()
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(conversion_response.status, 201)
        self.assertEqual(replay_response.status, 200)
        self.assertTrue(conversion_payload["created"])
        self.assertFalse(replay_payload["created"])
        self.assertEqual(conversion_payload["conversion"]["session_id"], cookie.split("=", 1)[1])
        self.assertEqual(report["counts"]["conversions"], 1)
        self.assertEqual(report["attributions"][0]["classification"], "direct")
        self.assertEqual(report["royalty"]["accrued_amount_cents"], 10_000)

    def test_http_verifier_matches_report_and_dashboard_readback(self):
        root = Path(__file__).parents[1]
        runner = root / "scripts" / "run_synthetic_scenarios.py"
        verifier = root / "scripts" / "verify_local_http.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            subprocess.run(
                [sys.executable, str(runner), "--output-dir", directory],
                check=True, capture_output=True, text=True, env=environment,
            )
            store = SQLiteLedgerStore(Path(directory) / "direct.sqlite")
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0),
                create_handler(
                    ReportingAPI(store=store),
                    dashboard_path=root / "app" / "index.html",
                ),
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [sys.executable, str(verifier), "--base-url", f"http://127.0.0.1:{server.server_port}",
                     "--sqlite", str(Path(directory) / "direct.sqlite"), "--output", str(Path(directory) / "http-verification.json")],
                    check=True, capture_output=True, text=True, env=environment,
                )
                verification = json.loads((Path(directory) / "http-verification.json").read_text(encoding="utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertIn("verified", result.stdout)
        self.assertEqual(verification["status"], "verified")
        self.assertEqual(verification["report_status"], "verified")
        self.assertEqual(verification["dashboard_status"], "verified")
        self.assertEqual(verification["report"]["royalty"]["accrued_amount_cents"], 10_000)

    def test_event_batch_import_and_independent_verification(self):
        root = Path(__file__).parents[1]
        importer = root / "scripts" / "import_event_batch.py"
        verifier = root / "scripts" / "verify_event_batch.py"
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            database = directory / "ledger.sqlite"
            SQLiteLedgerStore.create(database, self.ledger)
            input_path = directory / "events.jsonl"
            input_path.write_text(json.dumps({
                "source_name": "unit-export",
                "source_event_id": "evt-001",
                "event_type": "route_click",
                "route_id": "route:jay-youtube-001",
                "session_id": "session:batch-001",
                "observed_at": "2026-10-08T00:00:00Z",
            }) + "\n", encoding="utf-8")
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            apply_receipt = directory / "apply.json"
            subprocess.run([sys.executable, str(importer), "--database", str(database), "--input", str(input_path), "--receipt", str(apply_receipt), "--apply"], check=True, capture_output=True, text=True, env=environment)
            verification = subprocess.run([sys.executable, str(verifier), "--receipt", str(apply_receipt)], check=True, capture_output=True, text=True, env=environment)
            replay_receipt = directory / "replay.json"
            subprocess.run([sys.executable, str(importer), "--database", str(database), "--input", str(input_path), "--receipt", str(replay_receipt), "--apply"], check=True, capture_output=True, text=True, env=environment)
            replay_verification = subprocess.run([sys.executable, str(verifier), "--receipt", str(replay_receipt)], check=True, capture_output=True, text=True, env=environment)
            apply = json.loads(apply_receipt.read_text(encoding="utf-8"))
            replay = json.loads(replay_receipt.read_text(encoding="utf-8"))
            manifests = SQLiteLedgerStore(database).list_import_batches()
        self.assertIn("verified", verification.stdout)
        self.assertIn("verified", replay_verification.stdout)
        self.assertEqual(apply["counts"]["applied"], 1)
        self.assertEqual(replay["counts"]["duplicate"], 1)
        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0]["batch_id"], apply["batch_id"])

    def test_event_batch_import_rejects_mixed_batch_atomically(self):
        root = Path(__file__).parents[1]
        importer = root / "scripts" / "import_event_batch.py"
        verifier = root / "scripts" / "verify_event_batch.py"
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            database = directory / "ledger.sqlite"
            SQLiteLedgerStore.create(database, self.ledger)
            before = len(SQLiteLedgerStore(database).load().events)
            input_path = directory / "events.jsonl"
            input_path.write_text(json.dumps({"source_name": "unit-export", "source_event_id": "evt-002", "event_type": "route_click", "route_id": "route:jay-youtube-001"}) + "\n{malformed}\n", encoding="utf-8")
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            receipt = directory / "rejected.json"
            subprocess.run([sys.executable, str(importer), "--database", str(database), "--input", str(input_path), "--receipt", str(receipt), "--apply"], check=True, capture_output=True, text=True, env=environment)
            verification = subprocess.run([sys.executable, str(verifier), "--receipt", str(receipt)], check=True, capture_output=True, text=True, env=environment)
            result = json.loads(receipt.read_text(encoding="utf-8"))
            after = len(SQLiteLedgerStore(database).load().events)
        self.assertIn("verified", verification.stdout)
        self.assertEqual(result["status"], "rejected_atomic")
        self.assertEqual(before, after)

    def test_event_batch_receipt_tampering_is_rejected(self):
        root = Path(__file__).parents[1]
        importer = root / "scripts" / "import_event_batch.py"
        verifier = root / "scripts" / "verify_event_batch.py"
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            database = directory / "ledger.sqlite"
            SQLiteLedgerStore.create(database, self.ledger)
            input_path = directory / "events.jsonl"
            input_path.write_text(json.dumps({"source_name": "unit-export", "source_event_id": "evt-003", "event_type": "route_click", "route_id": "route:jay-youtube-001"}) + "\n", encoding="utf-8")
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            receipt = directory / "receipt.json"
            subprocess.run([sys.executable, str(importer), "--database", str(database), "--input", str(input_path), "--receipt", str(receipt), "--apply"], check=True, capture_output=True, text=True, env=environment)
            tampered = json.loads(receipt.read_text(encoding="utf-8"))
            tampered["counts"]["applied"] = 99
            receipt.write_text(json.dumps(tampered), encoding="utf-8")
            result = subprocess.run([sys.executable, str(verifier), "--receipt", str(receipt)], capture_output=True, text=True, env=environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed", result.stdout)

        root = Path(__file__).parents[1]
        runner = root / "scripts" / "run_synthetic_scenarios.py"
        verifier = root / "scripts" / "verify_synthetic_scenarios.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            subprocess.run(
                [sys.executable, str(runner), "--output-dir", directory],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            result = subprocess.run(
                [sys.executable, str(verifier), "--receipt-dir", directory],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            verification = json.loads((Path(directory) / "verification.json").read_text(encoding="utf-8"))

        self.assertIn("verified=3", result.stdout)
        self.assertEqual(verification["status"], "verified")
        self.assertEqual(verification["scenarios_verified"], 3)
        self.assertEqual(set(verification["scenarios"]), {"direct", "ambiguous", "no-click"})
        for scenario in verification["scenarios"].values():
            self.assertEqual(scenario["status"], "verified")
            self.assertTrue(scenario["database_sha256"])
            self.assertTrue(scenario["receipt_sha256"])

    def test_scenario_runner_preserves_direct_ambiguous_and_no_click_receipts(self):
        script = Path(__file__).parents[1] / "scripts" / "run_synthetic_scenarios.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(script.parents[1] / "src") + ":" + str(script.parent)
            result = subprocess.run(
                [sys.executable, str(script), "--output-dir", directory],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            receipts = {
                path.stem: json.loads(path.read_text(encoding="utf-8"))
                for path in Path(directory).glob("*.json")
            }

        self.assertIn("direct", result.stdout)
        self.assertEqual(set(receipts), {"direct", "ambiguous", "no-click"})
        self.assertEqual(receipts["direct"]["report"]["attributions"][0]["classification"], "direct")
        self.assertEqual(receipts["direct"]["report"]["royalty"]["accrued_amount_cents"], 10_000)
        self.assertEqual(receipts["ambiguous"]["report"]["attributions"][0]["classification"], "unknown")
        self.assertEqual(receipts["ambiguous"]["report"]["attributions"][0]["reason"], "ambiguous_route_clicks")
        self.assertEqual(receipts["no-click"]["report"]["attributions"][0]["reason"], "no_valid_route_click")
        self.assertEqual(receipts["no-click"]["report"]["royalty"]["accrued_amount_cents"], 0)
        for receipt in receipts.values():
            self.assertEqual(receipt["fixture_status"], "synthetic")
            self.assertEqual(receipt["report"]["fixture_status"], "synthetic")

    def test_local_conversion_endpoint_rejects_missing_session(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteLedgerStore.create(Path(directory) / "ledger.sqlite", self.ledger)
            server = __import__("http.server").server.HTTPServer(
                ("127.0.0.1", 0), create_handler(ReportingAPI(store=store))
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({"conversion_id": "conversion:no-session", "amount_cents": 100})
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request(
                    "POST", "/v1/conversions", body=body,
                    headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                )
                response = connection.getresponse()
                response_payload = json.loads(response.read())
                remaining_conversions = len(store.load().conversions)
                connection.close()
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

        self.assertEqual(response.status, 400)
        self.assertEqual(response_payload["error"], "invalid_request")
        self.assertEqual(remaining_conversions, 0)

    def test_http_scenario_replay_exercises_end_to_end_user_path(self):
        root = Path(__file__).parents[1]
        script = root / "scripts" / "replay_http_scenarios.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            result = subprocess.run(
                [sys.executable, str(script), "--output-dir", directory],
                check=True, capture_output=True, text=True, env=environment,
            )
            receipts = {
                path.stem: json.loads(path.read_text(encoding="utf-8"))
                for path in Path(directory).glob("*.json")
            }

        self.assertIn("direct", result.stdout)
        self.assertEqual(set(receipts), {"direct", "ambiguous", "no-click"})
        self.assertEqual(receipts["direct"]["status"], "verified")
        self.assertEqual(receipts["direct"]["steps"][0]["status"], 302)
        self.assertTrue(receipts["direct"]["steps"][0]["set_cookie"])
        self.assertEqual(receipts["direct"]["report"]["attributions"][0]["classification"], "direct")
        self.assertEqual(receipts["ambiguous"]["report"]["attributions"][0]["reason"], "ambiguous_route_clicks")
        self.assertEqual(receipts["no-click"]["report"]["attributions"][0]["reason"], "no_valid_route_click")
        for receipt in receipts.values():
            self.assertEqual(receipt["report_status"], "verified")
            self.assertEqual(receipt["database_unchanged"], True)


    def test_restart_recovery_preserves_http_observations_and_report(self):
        root = Path(__file__).parents[1]
        script = root / "scripts" / "check_restart_recovery.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            result = subprocess.run(
                [sys.executable, str(script), "--output-dir", directory],
                check=True, capture_output=True, text=True, env=environment,
            )
            receipt = json.loads((Path(directory) / "restart-recovery.json").read_text(encoding="utf-8"))

        self.assertIn("verified", result.stdout)
        self.assertEqual(receipt["status"], "verified")
        self.assertEqual(receipt["before_restart"]["report"]["counts"]["conversions"], 1)
        self.assertEqual(receipt["after_restart"]["report"]["counts"]["conversions"], 1)
        self.assertEqual(receipt["after_restart"]["report"]["attributions"][0]["classification"], "direct")
        self.assertTrue(receipt["report_unchanged"])
        self.assertTrue(receipt["database_unchanged_after_restart"])


    def test_negative_path_matrix_preserves_ledger_state(self):
        root = Path(__file__).parents[1]
        script = root / "scripts" / "check_negative_paths.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            result = subprocess.run(
                [sys.executable, str(script), "--output-dir", directory],
                check=True, capture_output=True, text=True, env=environment,
            )
            receipt = json.loads((Path(directory) / "negative-paths.json").read_text(encoding="utf-8"))

        self.assertIn("verified", result.stdout)
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["database_unchanged"])
        self.assertGreaterEqual(len(receipt["checks"]), 6)
        for check in receipt["checks"]:
            self.assertEqual(check["status"], "verified")
            self.assertEqual(check["actual"], check["expected"])


    def test_backup_restore_preserves_report_and_logical_state(self):
        root = Path(__file__).parents[1]
        script = root / "scripts" / "check_backup_restore.py"
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src") + ":" + str(root / "scripts")
            result = subprocess.run(
                [sys.executable, str(script), "--output-dir", directory],
                check=True, capture_output=True, text=True, env=environment,
            )
            receipt = json.loads((Path(directory) / "backup-restore.json").read_text(encoding="utf-8"))

        self.assertIn("verified", result.stdout)
        self.assertEqual(receipt["status"], "verified")
        self.assertTrue(receipt["report_unchanged"])
        self.assertTrue(receipt["logical_state_unchanged"])
        self.assertEqual(receipt["restored_report"]["royalty"]["accrued_amount_cents"], 10_000)


    def test_event_integrity_chain_detects_payload_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            store = SQLiteLedgerStore.create(path, self.ledger)
            store.append_event({"event_id": "event:integrity-1", "event_type": "route_click", "session_id": "session:integrity", "route_id": "route:jay-youtube-001"})
            store.append_event({"event_id": "event:integrity-2", "event_type": "landing_page_view", "session_id": "session:integrity"})
            verified = store.verify_integrity()
            with sqlite3.connect(path) as connection:
                payload = json.loads(connection.execute("SELECT payload FROM events WHERE event_id = ?", ("event:integrity-1",)).fetchone()[0])
                payload["session_id"] = "session:tampered"
                connection.execute("UPDATE events SET payload = ? WHERE event_id = ?", (json.dumps(payload, sort_keys=True), "event:integrity-1"))
            tampered = SQLiteLedgerStore(path).verify_integrity()

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["event_count"], 2)
        self.assertEqual(tampered["status"], "failed")
        self.assertTrue(tampered["errors"])


if __name__ == "__main__":
    unittest.main()
