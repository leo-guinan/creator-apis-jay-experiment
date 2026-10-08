import json
import uuid
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, unquote, urlsplit

from .reporting import LedgerReport


class ReportingAPI:
    """Versioned reporting and bounded event-ingestion boundary."""

    def __init__(self, ledger=None, *, store=None):
        if ledger is None and store is None:
            raise ValueError("ledger or store is required")
        self.ledger = ledger
        self.store = store

    def _current_ledger(self):
        return self.store.load() if self.store is not None else self.ledger

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
        report = LedgerReport(self._current_ledger()).summary(
            campaign_id=params.get("campaign_id"),
            experiment_id=params.get("experiment_id"),
            royalty_rate=rate,
        )
        return {"api_version": "v1", "report": report}

    def append_event(self, event: dict) -> tuple[dict, bool]:
        if self.store is None:
            raise ValueError("event ingestion requires a durable store")
        return self.store.append_event(event)

    def route_destination(self, route_id: str) -> str:
        route = self._current_ledger().records.get(route_id)
        if route is None or route.get("record_type") != "route":
            raise ValueError(f"unknown route id: {route_id}")
        return route["destination"]


def create_handler(api: ReportingAPI, *, dashboard_path: str | Path | None = None):
    dashboard_file: Path | None = Path(dashboard_path) if dashboard_path is not None else None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler contract
            parsed = urlsplit(self.path)
            if parsed.path.startswith("/r/"):
                self._redirect_route(unquote(parsed.path[3:]))
                return
            if parsed.path == "/" and dashboard_file is not None:
                try:
                    body = dashboard_file.read_bytes()
                except OSError:
                    self._send_json(404, {"error": "dashboard_not_found"})
                    return
                self._send_bytes(200, body, "text/html; charset=utf-8")
                return
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

        def _redirect_route(self, route_id: str) -> None:
            if not route_id:
                self._send_json(400, {"error": "invalid_route"})
                return
            try:
                destination = api.route_destination(route_id)
                cookie = SimpleCookie()
                cookie.load(self.headers.get("Cookie", ""))
                session = cookie.get("capi_session")
                is_new_session = session is None or not session.value
                session_id = session.value if not is_new_session else f"session:{uuid.uuid4().hex}"
                api.append_event(
                    {
                        "event_id": f"event:route-click-{uuid.uuid4().hex}",
                        "event_type": "route_click",
                        "session_id": session_id,
                        "route_id": route_id,
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            except ValueError as exc:
                status = 404 if str(exc).startswith("unknown route id") else 400
                self._send_json(status, {"error": "invalid_route", "message": str(exc)})
                return
            self.send_response(302)
            self.send_header("Location", destination)
            self.send_header("Cache-Control", "no-store")
            if is_new_session:
                self.send_header(
                    "Set-Cookie",
                    f"capi_session={session_id}; Path=/; HttpOnly; SameSite=Lax",
                )
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):  # noqa: N802 - stdlib handler contract
            parsed = urlsplit(self.path)
            if parsed.path != "/v1/events":
                self._send_json(404, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 64 * 1024:
                    raise ValueError("request body must be between 1 and 65536 bytes")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("event body must be a JSON object")
                event, created = api.append_event(payload)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                self._send_json(400, {"error": "invalid_request", "message": str(exc)})
                return
            self._send_json(
                201 if created else 200,
                {"api_version": "v1", "created": created, "event": event},
            )

        def _send_json(self, status: int, payload: dict) -> None:
            self._send_bytes(
                status,
                json.dumps(payload, sort_keys=True).encode("utf-8"),
                "application/json",
            )

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return Handler
