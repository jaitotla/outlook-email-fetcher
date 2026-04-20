"""
Run all test suites in sequence, then print a combined report.
=================================================================
Usage:
    python tests/run_all.py
    python tests/run_all.py --workers 10 --ramp
    python tests/run_all.py --skip concurrency
    python tests/run_all.py --only log-email,label-email
"""
import argparse
import asyncio
import importlib
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.helpers import header, ok, fail, info, warn, RESET, GREEN, RED, BOLD, CYAN, DIM

SUITES = [
    ("log-email",        "tests.test_log_email",          "main"),
    ("label-email",      "tests.test_label_email",        "main"),
    ("store-attachments","tests.test_store_attachments",  "main"),
    ("chat",             "tests.test_chat_with_thread",   "main"),
    ("draft",            "tests.test_draft_with_attachments", "main"),
    ("concurrency",      "tests.test_concurrency",        None),   # uses its own CLI
]


async def run_suite(name: str, module_path: str, fn_name: str | None,
                    workers: int, ramp: bool) -> bool:
    header(f"Suite: {name}")
    t0 = time.perf_counter()
    try:
        mod = importlib.import_module(module_path)

        if fn_name:
            result = await getattr(mod, fn_name)()
        else:
            # concurrency suite – call main directly
            result = await mod.main(workers, ramp)

        elapsed = time.perf_counter() - t0
        status  = result if isinstance(result, bool) else (result == 0 if isinstance(result, int) else True)
        label   = f"{name:<25} {elapsed:.2f}s"
        if status:
            ok(label)
        else:
            fail(label)
        return status
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        fail(f"{name:<25} EXCEPTION: {exc}")
        import traceback; traceback.print_exc()
        return False


async def main(skip: list, only: list, workers: int, ramp: bool):
    header("OpenMailBot Agent – Full Test Runner")
    info(f"Suites available : {', '.join(s[0] for s in SUITES)}")
    if only:
        info(f"Running only     : {', '.join(only)}")
    if skip:
        info(f"Skipping         : {', '.join(skip)}")

    suite_results = []
    t_start = time.perf_counter()

    for name, module_path, fn_name in SUITES:
        if only and name not in only:
            print(f"{DIM}  ⊘  {name:<25} skipped (not in --only){RESET}")
            continue
        if name in skip:
            warn(f"  ⊘  {name:<25} skipped (--skip)")
            continue

        passed = await run_suite(name, module_path, fn_name, workers, ramp)
        suite_results.append((name, passed))

    wall = time.perf_counter() - t_start

    # ── combined report ───────────────────────
    bar = "═" * 58
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}  Combined Report{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}")
    for name, passed in suite_results:
        sym = f"{GREEN}✔{RESET}" if passed else f"{RED}✘{RESET}"
        print(f"  {sym}  {name}")

    total   = len(suite_results)
    n_pass  = sum(1 for _, p in suite_results if p)
    n_fail  = total - n_pass
    verdict = f"{GREEN}ALL PASSED{RESET}" if n_fail == 0 else f"{RED}{n_fail} SUITE(S) FAILED{RESET}"
    print(f"\n  {n_pass}/{total} suites passed  |  wall time: {wall:.1f}s")
    print(f"  {verdict}\n")
    return n_fail == 0


def cli():
    p = argparse.ArgumentParser(description="Run all OpenMailBot agent test suites")
    p.add_argument("--skip",    default="",
                   help="Comma-separated suite names to skip (e.g. concurrency,draft)")
    p.add_argument("--only",    default="",
                   help="Comma-separated suite names to run exclusively")
    p.add_argument("--workers", type=int, default=10,
                   help="Concurrent workers for the concurrency suite (default: 10)")
    p.add_argument("--ramp",    action="store_true",
                   help="Enable ramp-up test in the concurrency suite")
    args = p.parse_args()

    skip = [s.strip() for s in args.skip.split(",") if s.strip()]
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    passed = asyncio.run(main(skip, only, args.workers, args.ramp))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    cli()
