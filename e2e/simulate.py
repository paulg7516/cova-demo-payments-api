"""End-to-end test rig for Cova: real traffic numbers in Datadog, real
deploys on GitHub, and a stand-in deploy pipeline.

Every 10 seconds it:
  1. asks GitHub which commit is live (the newest "production" deployment),
     just like a CD pipeline would;
  2. runs that version of the service: real requests through this app, with
     errors injected when the live commit's message contains "[e2e-bad]"
     (the bad deploy) or while a blip is running (--blip);
  3. sends the request and error counts to Datadog as e2e.requests and
     e2e.errors, tagged service:cova-demo-payments-api.

When Cova rolls back, it creates a new GitHub deployment of the previous
commit; the next loop sees that and the errors stop, exactly as a real
pipeline redeploying the old build would.

    export DD_API_KEY=...            # Datadog API key (Organization Settings -> API Keys)
    export DD_SITE=datadoghq.com     # or datadoghq.eu, us5.datadoghq.com, ...
    python e2e/simulate.py           # Ctrl+C to stop

    python e2e/simulate.py --dry-run --bad    # no Datadog/GitHub: just show the loop
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

REPO = os.environ.get("GITHUB_REPO", "paulg7516/cova-demo-payments-api")
SERVICE = "cova-demo-payments-api"
TICK = 10
REQUESTS_PER_TICK = 120
BAD_ERROR_RATE = 0.12   # 12% 5xx on the bad deploy (threshold is 1%)
BASE_ERROR_RATE = 0.002  # healthy background noise

_fault = {"rate": BASE_ERROR_RATE}


@app.middleware("http")
async def _inject_faults(request: Request, call_next):
    if random.random() < _fault["rate"]:
        return JSONResponse({"detail": "upstream timeout (injected by e2e)"}, status_code=503)
    return await call_next(request)


def gh_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or ""
    if tok:
        return tok
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        sys.exit("Set GITHUB_TOKEN or sign in with `gh auth login`.")


_msgs: dict[str, str] = {}


def live_commit(client: httpx.Client) -> tuple[str, str]:
    """(sha, message) of the newest production deployment."""
    r = client.get(f"https://api.github.com/repos/{REPO}/deployments", params={"environment": "production", "per_page": 1})
    r.raise_for_status()
    deps = r.json()
    if not deps:
        return "", ""
    sha = deps[0]["sha"]
    if sha not in _msgs:
        c = client.get(f"https://api.github.com/repos/{REPO}/commits/{sha}")
        c.raise_for_status()
        _msgs[sha] = c.json()["commit"]["message"].splitlines()[0]
    return sha, _msgs[sha]


def send_to_datadog(requests_n: int, errors_n: int) -> None:
    site = os.environ.get("DD_SITE", "datadoghq.com")
    now = int(time.time())
    tags = [f"service:{SERVICE}", "env:prod", "source:cova-e2e"]
    body = {"series": [
        {"metric": "e2e.requests", "type": 1, "interval": TICK, "points": [{"timestamp": now, "value": requests_n}], "tags": tags},
        {"metric": "e2e.errors", "type": 1, "interval": TICK, "points": [{"timestamp": now, "value": errors_n}], "tags": tags},
    ]}
    r = httpx.post(f"https://api.{site}/api/v2/series", json=body, timeout=10,
                   headers={"DD-API-KEY": os.environ["DD_API_KEY"], "Content-Type": "application/json"})
    if r.status_code >= 300:
        print(f"  ! Datadog said {r.status_code}: {r.text[:200]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no Datadog or GitHub calls")
    ap.add_argument("--bad", action="store_true", help="dry run only: pretend the bad deploy is live")
    ap.add_argument("--blip", type=int, default=0, help="inject errors for this many seconds from the start, then stop")
    ap.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run until Ctrl+C)")
    a = ap.parse_args()
    if not a.dry_run and not os.environ.get("DD_API_KEY"):
        sys.exit("Set DD_API_KEY (Datadog -> Organization Settings -> API Keys).")

    gh = None if a.dry_run else httpx.Client(timeout=10, headers={
        "Authorization": f"Bearer {gh_token()}", "Accept": "application/vnd.github+json"})
    app_client = TestClient(app)
    paths = ["/health", "/version"] + [r.path for r in app.routes if getattr(r, "methods", None) and "GET" in r.methods
                                       and "{" not in r.path and r.path not in ("/health", "/version", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect")]
    started, n = time.time(), 0
    print(f"Simulating {SERVICE}: {REQUESTS_PER_TICK} requests every {TICK}s. Ctrl+C to stop.")
    while True:
        n += 1
        if a.dry_run:
            sha, msg = ("bad1234", "Retry Stripe calls [e2e-bad]") if a.bad else ("good123", "Baseline")
        else:
            sha, msg = live_commit(gh)
        bad = "[e2e-bad]" in msg
        blip = a.blip and time.time() - started < a.blip
        _fault["rate"] = BAD_ERROR_RATE if (bad or blip) else BASE_ERROR_RATE
        errors = sum(1 for _ in range(REQUESTS_PER_TICK) if app_client.get(random.choice(paths)).status_code >= 500)
        if not a.dry_run:
            send_to_datadog(REQUESTS_PER_TICK, errors)
        why = "bad deploy" if bad else "blip" if blip else "healthy"
        print(f"{time.strftime('%H:%M:%S')}  live {sha[:7] or '(no deploys)'}  {why:10}  "
              f"{errors}/{REQUESTS_PER_TICK} errors = {100 * errors / REQUESTS_PER_TICK:.1f}%"
              f"{'' if a.dry_run else '  -> Datadog'}", flush=True)
        if a.ticks and n >= a.ticks:
            return
        time.sleep(TICK)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
