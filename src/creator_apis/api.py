import json
from http.server import BaseHTTPRequestHandler
from typing import Mapping
from urllib.parse import parse_qs, urlsplit

from .reporting import LedgerReport


class ReportingAPI:
    """Versioned, read-only application boundary for ledger reports."""

    def __init__(self, ledger):
        self.ledger = ledger

    def get_report(self, params: Mapping[str, str] | None = None) -> dict:
        params = dict(params or {})
        allowed = {"campaign_id", "experiment_id", "royalty_rate"}
        unknown = set(params) - allowed
        if unknown:
            raise ValueError(f"unknown query parameter: {sorted(unknown)[0]}")
        rate_text = params.get("royalty_rate")
        rate = 0.10 if rate_text in (None, "") else float(rate_text)
        if not 0 <= rate <= 1:
            raise ValueError("royalty_rate must be between 0 and 1")
        report = LedgerReport(self.ledger).summary(
            campaign_id=params.get("campaign_id"),
            experiment_id=params.get("experiment_id"),
            royalty_rate=rate,
        )
        return {"api_version": "v1", "report": report}


def create_handler(api: ReportingAPI):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler contract
            parsed = urlsplit(self.path)
            if parsed.path != "/v1/reports":
                self._send_json(404, {"error": "not_found"})
                return
            try:
                query = {
                    key: values[-1]
                    for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
                }
                payload = api.get_report(query)
            except (TypeError, ValueError) as exc:
                self._send_json(400, {"error": "invalid_request", "message": str(exc)})
                return
            self._send_json(200, payload)

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return Handler
