"""
Shared helpers, fixtures, and pretty-printing utilities
used by every individual test script.
"""
import asyncio
import base64
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

# ──────────────────────────────────────────────
#  Target server
# ──────────────────────────────────────────────
BASE_URL = "http://localhost:5050"
TIMEOUT  = httpx.Timeout(120.0, connect=10.0)

# ──────────────────────────────────────────────
#  ANSI colours
# ──────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg):     print(f"{GREEN}  ✔  {msg}{RESET}")
def fail(msg):   print(f"{RED}  ✘  {msg}{RESET}")
def info(msg):   print(f"{CYAN}  ℹ  {msg}{RESET}")
def warn(msg):   print(f"{YELLOW}  ⚠  {msg}{RESET}")
def dim(msg):    print(f"{DIM}     {msg}{RESET}")

def header(title: str) -> None:
    bar = "═" * 58
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}")

# ──────────────────────────────────────────────
#  Result tracker
# ──────────────────────────────────────────────
class Results:
    def __init__(self, suite_name: str):
        self.suite = suite_name
        self.passed: List[str] = []
        self.failed: List[Dict] = []
        self.timings: Dict[str, float] = {}

    def record(self, name: str, passed: bool, elapsed: float, detail: str = ""):
        self.timings[name] = round(elapsed, 3)
        if passed:
            self.passed.append(name)
        else:
            self.failed.append({"name": name, "detail": detail})

    def print_summary(self) -> bool:
        total = len(self.passed) + len(self.failed)
        header(f"Summary – {self.suite}")
        print(f"  Total   : {total}")
        print(f"  {GREEN}Passed{RESET}  : {len(self.passed)}")
        print(f"  {RED}Failed{RESET}  : {len(self.failed)}")
        if self.failed:
            print(f"\n{RED}  Failures:{RESET}")
            for f in self.failed:
                print(f"    • {f['name']}: {f['detail']}")
        if self.timings:
            slowest = sorted(self.timings.items(), key=lambda x: -x[1])[:3]
            print(f"\n{DIM}  Slowest:{RESET}")
            for n, t in slowest:
                print(f"    {n:<50} {t}s")
        verdict = f"{GREEN}ALL PASSED{RESET}" if not self.failed else f"{RED}SOME FAILED{RESET}"
        print(f"\n  Verdict : {verdict}\n")
        return not self.failed


# ──────────────────────────────────────────────
#  Core request helper
# ──────────────────────────────────────────────
async def request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    name: str,
    results: Results,
    *,
    json_body: Any = None,
    params: Dict = None,
    expect_status: int = 200,
    expect_keys: List[str] = None,
) -> Dict:
    t0 = time.perf_counter()
    try:
        if method == "GET":
            resp = await client.get(path, params=params)
        else:
            resp = await client.post(path, json=json_body)
        elapsed = time.perf_counter() - t0

        try:
            body = resp.json()
        except Exception:
            body = {}

        missing_keys = [k for k in (expect_keys or []) if k not in body]
        status_ok    = resp.status_code == expect_status
        passed       = status_ok and not missing_keys

        label = f"{name:<52} HTTP {resp.status_code}  {elapsed:.3f}s"
        if passed:
            ok(label)
        else:
            reasons = []
            if not status_ok:
                reasons.append(f"expected HTTP {expect_status}, got {resp.status_code}")
            if missing_keys:
                reasons.append(f"missing keys: {missing_keys}")
            fail(label)
            dim(f"reason : {'; '.join(reasons)}")
            dim(f"body   : {str(body)[:200]}")
            results.record(name, False, elapsed, "; ".join(reasons))
            return body

        results.record(name, True, elapsed)
        return body

    except httpx.ConnectError:
        elapsed = time.perf_counter() - t0
        fail(f"{name:<52} CONNECTION REFUSED")
        results.record(name, False, elapsed, "connection refused – is the server running?")
        return {}
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        fail(f"{name:<52} EXCEPTION: {exc}")
        results.record(name, False, elapsed, str(exc))
        return {}


# ──────────────────────────────────────────────
#  Sample data factories
# ──────────────────────────────────────────────
def make_messages(user_id: str = "testuser@example.com", n: int = 2) -> List[Dict]:
    return [
        {
            "message_id": f"msg_{i+1:03d}",
            "from_address": f"sender{i+1}@example.com",
            "to": [user_id],
            "subject": f"Test subject #{i+1}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "body": (
                f"Hello,\n\nThis is test message #{i+1}.\n"
                "Please review the attached documents.\n\n"
                "Let's schedule a meeting to discuss this.\n\n"
                "Best regards,\nSender"
            ),
        }
        for i in range(n)
    ]


def make_attachment(filename: str = "report.pdf", content: bytes = None) -> Dict:
    raw = content or b"%PDF-1.4 fake pdf content for testing purposes"
    return {
        "filename": filename,
        "content": base64.b64encode(raw).decode(),
        "mime_type": "application/pdf" if filename.endswith(".pdf") else "text/plain",
    }


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
