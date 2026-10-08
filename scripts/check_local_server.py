import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen


def check_server(base_url: str, *, expect_scenarios: bool = False) -> dict:
    parsed = urlsplit(base_url)
    errors: list[str] = []
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        errors.append("base URL is not localhost")
    try:
        with urlopen(f"{base_url.rstrip('/')}/healthz", timeout=5) as response:
            health = json.load(response)
        if health.get("status") != "ok":
            errors.append("health status is not ok")
        if health.get("api_version") != "v1":
            errors.append("health api version mismatch")
        if health.get("fixture_status") != "synthetic":
            errors.append("health fixture is not synthetic")
        if health.get("read_only") is not True:
            errors.append("health does not declare read_only")
        if expect_scenarios and health.get("scenarios") != ["ambiguous", "direct", "no-click"]:
            errors.append("expected fixed scenario set is not available")
    except Exception as exc:  # noqa: BLE001 - CLI converts reachability failures to a receipt
        health = None
        errors.append(f"health readback error: {exc}")
    try:
        with urlopen(f"{base_url.rstrip('/')}/v1/reports", timeout=5) as response:
            report = json.load(response)
        if report.get("api_version") != "v1" or report.get("report", {}).get("fixture_status") != "synthetic":
            errors.append("report is not a synthetic v1 report")
    except Exception as exc:  # noqa: BLE001
        report = None
        errors.append(f"report readback error: {exc}")
    try:
        with urlopen(f"{base_url.rstrip('/')}/", timeout=5) as response:
            dashboard = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type")
        if content_type != "text/html; charset=utf-8":
            errors.append("dashboard content type mismatch")
        for marker in ("Creator APIs report", "/v1/reports", "fixture_status"):
            if marker not in dashboard:
                errors.append(f"dashboard missing marker: {marker}")
    except Exception as exc:  # noqa: BLE001
        content_type = None
        errors.append(f"dashboard readback error: {exc}")
    result = {
        "verification_version": "v1",
        "status": "verified" if not errors else "failed",
        "base_url": base_url,
        "health": health,
        "report": report,
        "dashboard_content_type": content_type,
        "errors": errors,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a local Creator APIs server readiness contract.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expect-scenarios", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check_server(args.base_url, expect_scenarios=args.expect_scenarios)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"status={result['status']}")
    if result["errors"]:
        for error in result["errors"]:
            print(f"error={error}")
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
