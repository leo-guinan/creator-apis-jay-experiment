import json
import uuid
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, unquote, urlsplit

from .reporting import LedgerReport
from .audit import audit_local_state


class ReportingAPI:
    """Versioned reporting and bounded event-ingestion boundary."""

    def __init__(self, ledger=None, *, store=None, scenario_stores=None, audit_paths=None):
        if ledger is None and store is None and not scenario_stores:
            raise ValueError("ledger, store, or scenario_stores is required")
        self.ledger = ledger
        self.store = store
        self.scenario_stores = dict(scenario_stores or {})
        self.audit_paths = dict(audit_paths or {})

    def _current_ledger(self, scenario: str | None = None):
        if scenario is not None:
            if scenario not in self.scenario_stores:
                raise ValueError(f"unknown scenario: {scenario}")
            return self.scenario_stores[scenario].load()
        if self.store is not None:
            return self.store.load()
        if self.ledger is not None:
            return self.ledger
        if self.scenario_stores:
            return self.scenario_stores[sorted(self.scenario_stores)[0]].load()
        raise ValueError("default ledger is not configured")

    def available_scenarios(self) -> list[str]:
        return sorted(self.scenario_stores)

    def health(self) -> dict:
        ledger = self._current_ledger()
        return {
            "status": "ok",
            "api_version": "v1",
            "fixture_status": ledger.fixture_status,
            "storage": "sqlite" if self.store is not None or self.scenario_stores else "json",
            "scenarios": self.available_scenarios(),
            "read_only": True,
        }

    def integrity(self) -> dict:
        if self.store is None:
            return {"status": "unavailable", "errors": ["integrity requires a SQLite store"]}
        return self.store.verify_integrity()

    def imports(self) -> dict:
        if self.store is None:
            return {"api_version": "v1", "imports": []}
        return {"api_version": "v1", "imports": self.store.list_import_batches()}

    def audit(self) -> dict:
        if self.store is None:
            return {"audit_version": "v1", "status": "blocked", "errors": ["audit requires a SQLite store"], "warnings": []}
        return audit_local_state(self.store, **self.audit_paths)

    def get_report(self, params: Mapping[str, str] | None = None) -> dict:
        params = dict(params or {})
        allowed = {"campaign_id", "experiment_id", "royalty_rate", "scenario"}
        unknown = set(params) - allowed
        if unknown:
            raise ValueError(f"unknown query parameter: {sorted(unknown)[0]}")
        rate_text = params.get("royalty_rate")
        rate = 0.10 if rate_text in (None, "") else float(rate_text)
        if not 0 <= rate <= 1:
            raise ValueError("royalty_rate must be between 0 and 1")
        report = LedgerReport(self._current_ledger(params.get("scenario"))).summary(
            campaign_id=params.get("campaign_id"),
            experiment_id=params.get("experiment_id"),
            royalty_rate=rate,
        )
        return {"api_version": "v1", "report": report}

    def append_event(self, event: dict) -> tuple[dict, bool]:
        if self.store is None:
            raise ValueError("event ingestion requires a durable store")
        return self.store.append_event(event)

    def append_conversion(self, conversion: dict) -> tuple[dict, bool]:
        if self.store is None:
            raise ValueError("conversion ingestion requires a durable store")
        return self.store.append_conversion(conversion)

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
            if parsed.path == "/healthz":
                self._send_json(200, api.health())
                return
            if parsed.path == "/v1/integrity":
                payload = api.integrity()
                self._send_json(200 if payload["status"] == "verified" else 503, {"api_version": "v1", **payload})
                return
            if parsed.path == "/v1/imports":
                self._send_json(200, api.imports())
                return
            if parsed.path == "/v1/audit":
                payload = api.audit()
                self._send_json(200 if payload["status"] != "blocked" else 503, {"api_version": "v1", **payload})
                return
            if parsed.path == "/v1/scenarios":
                self._send_json(200, {"api_version": "v1", "scenarios": api.available_scenarios()})
                return
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
            if parsed.path == "/v1/conversions":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 64 * 1024:
                        raise ValueError("request body must be between 1 and 65536 bytes")
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError("conversion body must be a JSON object")
                    if not payload.get("session_id"):
                        cookie = SimpleCookie()
                        cookie.load(self.headers.get("Cookie", ""))
                        session = cookie.get("capi_session")
                        if session is None or not session.value:
                            raise ValueError("session_id or capi_session cookie is required")
                        payload["session_id"] = session.value
                    conversion, created = api.append_conversion(payload)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    self._send_json(400, {"error": "invalid_request", "message": str(exc)})
                    return
                self._send_json(
                    201 if created else 200,
                    {"api_version": "v1", "created": created, "conversion": conversion},
                )
                return
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
