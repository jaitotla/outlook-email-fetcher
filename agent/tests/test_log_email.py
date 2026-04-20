"""
Tests for  POST /api/log-email
==============================
Run:
    python tests/test_log_email.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.helpers import (
    header, info, dim, Results, request, make_messages, new_client
)

# ─── constants ────────────────────────────────
USER_ID   = "testuser@example.com"
THREAD_ID = "log_email_test_thread"
ROUTE     = "/api/log-email"

results = Results("POST /api/log-email")


# ─── test cases ───────────────────────────────

async def test_basic_log(client):
    """Happy path: log 2 messages for a thread."""
    await request(
        client, "POST", ROUTE,
        "basic log (2 messages)",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": THREAD_ID,
            "messages": make_messages(USER_ID, n=2),
        },
        expect_keys=["success", "thread_id", "clean_count"],
    )


async def test_single_message(client):
    """Single message thread."""
    await request(
        client, "POST", ROUTE,
        "single message thread",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_single",
            "messages": make_messages(USER_ID, n=1),
        },
        expect_keys=["success"],
    )


async def test_html_body(client):
    """HTML email body should be cleaned by the pipeline."""
    await request(
        client, "POST", ROUTE,
        "HTML body stripped",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_html",
            "messages": [
                {
                    "message_id": "html_msg_001",
                    "from_address": "html@example.com",
                    "to": [USER_ID],
                    "subject": "HTML email",
                    "timestamp": "2026-02-20T10:00:00Z",
                    "body": (
                        "<html><body><p>Hello <b>World</b></p>"
                        "<a href='https://example.com'>click here</a>"
                        "<script>alert('xss')</script></body></html>"
                    ),
                }
            ],
        },
        expect_keys=["success"],
    )


async def test_quoted_reply(client):
    """Quoted content should be stripped; only new text kept."""
    await request(
        client, "POST", ROUTE,
        "quoted reply deduplicated",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_quoted",
            "messages": [
                {
                    "message_id": "quoted_msg_001",
                    "from_address": "bob@example.com",
                    "to": [USER_ID],
                    "subject": "Re: Meeting",
                    "timestamp": "2026-02-20T11:00:00Z",
                    "body": (
                        "Sure, Thursday works!\n\n"
                        "On Wed, Feb 19 Alice <alice@example.com> wrote:\n"
                        "> Can we meet Thursday?\n"
                        "> Let me know your availability.\n"
                    ),
                }
            ],
        },
        expect_keys=["success"],
    )


async def test_missing_messages_rejected(client):
    """Empty messages list must return HTTP 400."""
    await request(
        client, "POST", ROUTE,
        "empty messages → 400",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_empty",
            "messages": [],
        },
        expect_status=400,
    )


async def test_large_thread(client):
    """Log a thread with 10 messages."""
    await request(
        client, "POST", ROUTE,
        "large thread (10 messages)",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_large",
            "messages": make_messages(USER_ID, n=10),
        },
        expect_keys=["success", "clean_count"],
    )


async def test_very_large_thread(client):
    """Log a thread with 20 messages."""
    await request(
        client, "POST", ROUTE,
        "very large thread (20 messages)",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_very_large",
            "messages": make_messages(USER_ID, n=20),
        },
        expect_keys=["success", "clean_count"],
    )


async def test_different_users_isolated(client):
    """Same thread_id for two different users should not collide."""
    shared_thread = "shared_thread_isolation"
    tasks = [
        request(
            client, "POST", ROUTE,
            f"isolation user{i+1}",
            results,
            json_body={
                "user_id": f"user{i+1}@example.com",
                "thread_id": shared_thread,
                "messages": make_messages(f"user{i+1}@example.com", n=1),
            },
            expect_keys=["success"],
        )
        for i in range(3)
    ]
    await asyncio.gather(*tasks)


async def test_parallel_batch_5_requests(client):
    """Submit 5 requests in parallel to test concurrent handling."""
    tasks = [
        request(
            client, "POST", ROUTE,
            f"parallel batch request {i+1}/5",
            results,
            json_body={
                "user_id": f"batch_user_{i+1}@example.com",
                "thread_id": f"batch_thread_{i+1}",
                "messages": make_messages(f"batch_user_{i+1}@example.com", n=2),
            },
            expect_keys=["success"],
        )
        for i in range(5)
    ]
    await asyncio.gather(*tasks)


async def test_parallel_batch_10_requests(client):
    """Submit 10 requests in 2 batches of 5 to stress test."""
    # First batch of 5
    tasks_batch1 = [
        request(
            client, "POST", ROUTE,
            f"stress batch-1 request {i+1}/5",
            results,
            json_body={
                "user_id": f"stress_batch1_user_{i+1}@example.com",
                "thread_id": f"stress_batch1_thread_{i+1}",
                "messages": make_messages(f"stress_batch1_user_{i+1}@example.com", n=3),
            },
            expect_keys=["success"],
        )
        for i in range(5)
    ]
    
    # Second batch of 5
    tasks_batch2 = [
        request(
            client, "POST", ROUTE,
            f"stress batch-2 request {i+1}/5",
            results,
            json_body={
                "user_id": f"stress_batch2_user_{i+1}@example.com",
                "thread_id": f"stress_batch2_thread_{i+1}",
                "messages": make_messages(f"stress_batch2_user_{i+1}@example.com", n=3),
            },
            expect_keys=["success"],
        )
        for i in range(5)
    ]
    
    await asyncio.gather(*tasks_batch1)
    await asyncio.gather(*tasks_batch2)


# ─── runner ───────────────────────────────────

async def main():
    header("POST /api/log-email  –  Test Suite")
    async with new_client() as client:
        await test_basic_log(client)
        await test_single_message(client)
        await test_html_body(client)
        await test_quoted_reply(client)
        await test_missing_messages_rejected(client)
        await test_large_thread(client)
        await test_very_large_thread(client)
        await test_different_users_isolated(client)
        
        # New: Parallel batch tests
        await test_parallel_batch_5_requests(client)
        await test_parallel_batch_10_requests(client)

    passed = results.print_summary()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
