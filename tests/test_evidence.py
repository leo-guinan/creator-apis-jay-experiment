import unittest

from creator_apis.evidence import EvidenceLedger


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


if __name__ == "__main__":
    unittest.main()
