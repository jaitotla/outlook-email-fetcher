"""
Concurrency stress test – fires many requests simultaneously
=============================================================
Sends large batches of concurrent requests to every route and
measures throughput, latency, and error rate.

Run:
    python tests/test_concurrency.py
    python tests/test_concurrency.py --workers 20
    python tests/test_concurrency.py --workers 10 --ramp
"""
import argparse
import asyncio
import base64
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.helpers import (
    header, info, warn, ok, fail, dim, Results,
    make_messages, make_attachment, new_client, BASE_URL,
    TIMEOUT
)
import httpx
from datetime import datetime, timezone

# ─── default workers ──────────────────────────
DEFAULT_WORKERS = 10

results = Results("Concurrency Stress Test")


# ─── fire-and-record helper ───────────────────

async def fire(client, method, path, name, json_body=None, params=None,
               expect_status=200):
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r = await client.get(path, params=params)
        else:
            r = await client.post(path, json=json_body)
        elapsed = time.perf_counter() - t0
        passed = (r.status_code == expect_status)
        results.record(name, passed, elapsed,
                       "" if passed else f"HTTP {r.status_code}")
        return passed, elapsed, r.status_code
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        results.record(name, False, elapsed, str(exc))
        return False, elapsed, 0


# ─── batch helpers ────────────────────────────

def batch_log_email(n: int):
    """Return n coroutine factories for /api/log-email"""
    async def _task(client, i):
        return await fire(
            client, "POST", "/api/log-email",
            f"log-email  #{i+1:03d}",
            json_body={
                "user_id": "stress@example.com",
                "thread_id": f"stress_log_{i+1:04d}",
                "messages": make_messages("stress@example.com", n=2),
            },
        )
    return [_task for _ in range(n)]


def batch_label_email(n: int):
    async def _task(client, i):
        return await fire(
            client, "POST", "/api/label-email",
            f"label-email #{i+1:03d}",
            json_body={
                "user_id": "stress@example.com",
                "thread_id": f"stress_label_{i+1:04d}",
                "messages": make_messages("stress@example.com", n=1),
            },
        )
    return [_task for _ in range(n)]


def batch_store_attachments(n: int):
    async def _task(client, i):
        return await fire(
            client, "POST", "/api/store-attachments",
            f"store-attachments #{i+1:03d}",
            json_body={
                "user_id": "stress@example.com",
                "thread_id": f"stress_att_{i+1:04d}",
                "message_id": f"stress_msg_{i+1:04d}",
                "attachments": [make_attachment(f"stress_{i+1}.pdf")],
            },
        )
    return [_task for _ in range(n)]


def batch_health(n: int):
    async def _task(client, i):
        return await fire(
            client, "GET", "/health",
            f"health       #{i+1:03d}",
        )
    return [_task for _ in range(n)]


def batch_metrics(n: int):
    async def _task(client, i):
        return await fire(
            client, "GET", "/api/label-email/metrics",
            f"metrics      #{i+1:03d}",
            params={"user_id": "stress@example.com"},
        )
    return [_task for _ in range(n)]


async def run_batch(client, factories, label: str):
    """Run all factories concurrently and print a summary line."""
    header(f"{label}  ({len(factories)} simultaneous requests)")
    t0 = time.perf_counter()
    outcomes = await asyncio.gather(*[f(client, i) for i, f in enumerate(factories)])
    total_elapsed = time.perf_counter() - t0

    n_ok  = sum(1 for passed, _, _ in outcomes if passed)
    n_err = len(outcomes) - n_ok
    avg   = sum(e for _, e, _ in outcomes) / len(outcomes)
    mx    = max(e for _, e, _ in outcomes)
    tp    = len(outcomes) / total_elapsed

    ok(f"  {n_ok}/{len(outcomes)} succeeded")
    if n_err:
        fail(f"  {n_err} failed")
    dim(f"  wall time={total_elapsed:.2f}s  avg={avg:.3f}s  max={mx:.3f}s  "
        f"throughput≈{tp:.1f} req/s")


# ─── ramp test ────────────────────────────────

async def ramp_test(client, route: str, label: str, make_body_fn, levels=(1, 5, 10, 20, 30)):
    """
    Gradually increase concurrency and record throughput at each level.
    Useful for finding the saturation point.
    """
    header(f"Ramp test – {label}")
    print(f"  {'Workers':<10} {'OK/N':<10} {'Wall(s)':<10} {'Avg(s)':<10} {'TP(req/s)':<12}")
    print(f"  {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*12}")

    for w in levels:
        tasks = []
        for i in range(w):
            body = make_body_fn(i, w)
            tasks.append(
                fire(client, "POST", route, f"ramp_{w}_{i}", json_body=body)
            )
        t0 = time.perf_counter()
        outcomes = await asyncio.gather(*tasks)
        wall = time.perf_counter() - t0
        n_ok = sum(1 for ok_, _, _ in outcomes if ok_)
        avg  = sum(e for _, e, _ in outcomes) / len(outcomes)
        tp   = w / wall
        color = "\033[92m" if n_ok == w else "\033[91m"
        reset = "\033[0m"
        print(f"  {w:<10} {color}{n_ok}/{w}{reset:<16} {wall:<10.2f} {avg:<10.3f} {tp:<12.1f}")


# ─── mixed concurrent batch ───────────────────

async def mixed_burst(client, n: int):
    """
    Fire a mix of ALL 5 routes at the same time.
    Each route gets n/5 workers (rounded).
    """
    per_route = max(1, n // 5)
    header(f"Mixed burst – all routes  ({per_route} workers each = {per_route*5} total)")

    all_tasks = (
        batch_log_email(per_route)
        + batch_label_email(per_route)
        + batch_store_attachments(per_route)
        + batch_health(per_route)
        + batch_metrics(per_route)
    )

    t0 = time.perf_counter()
    outcomes = await asyncio.gather(*[f(client, i) for i, f in enumerate(all_tasks)])
    wall = time.perf_counter() - t0

    n_ok  = sum(1 for p, _, _ in outcomes if p)
    n_err = len(outcomes) - n_ok
    avg   = sum(e for _, e, _ in outcomes) / len(outcomes)
    mx    = max(e for _, e, _ in outcomes)

    ok(f"  {n_ok}/{len(outcomes)} succeeded")
    if n_err:
        fail(f"  {n_err} failed")
    dim(f"  wall={wall:.2f}s  avg={avg:.3f}s  max={mx:.3f}s")


# ─── runner ───────────────────────────────────

async def main(workers: int, ramp: bool):
    header(f"Concurrency Stress Test  –  workers={workers}")
    info(f"Target : {BASE_URL}")
    info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    async with new_client() as client:

        # ── per-route batches ──────────────────
        await run_batch(client, batch_health(workers),            "GET  /health")
        await run_batch(client, batch_log_email(workers),         "POST /api/log-email")
        await run_batch(client, batch_store_attachments(workers), "POST /api/store-attachments")
        await run_batch(client, batch_label_email(workers),       "POST /api/label-email")
        await run_batch(client, batch_metrics(workers),           "GET  /api/label-email/metrics")

        # ── mixed burst ───────────────────────
        await mixed_burst(client, workers)

        # ── ramp test (optional) ──────────────
        if ramp:
            levels = (1, 5, 10, 20, 30)

            await ramp_test(
                client, "/api/log-email", "/api/log-email",
                lambda i, w: {
                    "user_id": "ramp@example.com",
                    "thread_id": f"ramp_{w}_{i}",
                    "messages": make_messages("ramp@example.com", n=1),
                },
                levels=levels,
            )
            await ramp_test(
                client, "/api/store-attachments", "/api/store-attachments",
                lambda i, w: {
                    "user_id": "ramp@example.com",
                    "thread_id": f"ramp_att_{w}_{i}",
                    "message_id": f"ramp_msg_{w}_{i}",
                    "attachments": [make_attachment(f"ramp_{i}.pdf")],
                },
                levels=levels,
            )

    results.print_summary()


def cli():
    p = argparse.ArgumentParser(description="Concurrency stress test for OpenMailBot agent")
    p.add_argument("--workers",  type=int, default=DEFAULT_WORKERS,
                   help=f"Number of simultaneous requests per route (default: {DEFAULT_WORKERS})")
    p.add_argument("--ramp", action="store_true",
                   help="Also run graduated ramp-up test on key routes")
    p.add_argument("--url", default=None,
                   help="Override base URL (default: http://localhost:5050)")
    args = p.parse_args()

    if args.url:
        import tests.helpers as _h
        _h.BASE_URL = args.url

    asyncio.run(main(args.workers, args.ramp))


if __name__ == "__main__":
    cli()
