"""
Tests for  POST /api/chat-with-thread
======================================
Requires emails to already be logged (run test_log_email first, or
the pipeline will find no emails and likely return an empty answer).

Run:
    python tests/test_chat_with_thread.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.helpers import (
    header, info, dim, Results, request, make_messages, new_client
)

USER_ID   = "testuser@example.com"
THREAD_ID = "chat_test_thread"
ROUTE_LOG  = "/api/log-email"
ROUTE_CHAT = "/api/chat-with-thread"

results = Results("POST /api/chat-with-thread")


# ─── seed helper ──────────────────────────────

async def seed_thread(client, thread_id: str, messages):
    """Pre-load emails so the chat pipeline has data to work with."""
    await client.post(ROUTE_LOG, json={
        "user_id": USER_ID,
        "thread_id": thread_id,
        "messages": messages,
    })


# ─── test cases ───────────────────────────────

async def test_basic_question(client):
    """Ask a simple question about a seeded thread."""
    tid = f"{THREAD_ID}_basic"
    await seed_thread(client, tid, [
        {
            "message_id": "chat_b1",
            "from_address": "alice@example.com",
            "to": [USER_ID],
            "subject": "Project Phoenix – kickoff",
            "timestamp": "2026-02-10T09:00:00Z",
            "body": "Hi team, the Project Phoenix kickoff is scheduled for March 3rd at 2pm EST.",
        }
    ])
    await request(
        client, "POST", ROUTE_CHAT,
        "basic question about email",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "question": "When is the Project Phoenix kickoff?",
        },
    )


async def test_summary_question(client):
    """Ask for a thread summary."""
    tid = f"{THREAD_ID}_summary"
    await seed_thread(client, tid, make_messages(USER_ID, n=3))
    await request(
        client, "POST", ROUTE_CHAT,
        "ask for thread summary",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "question": "Summarize this email thread in 2 sentences.",
        },
    )


async def test_who_sent_question(client):
    """Ask who sent the email."""
    tid = f"{THREAD_ID}_who"
    await seed_thread(client, tid, [
        {
            "message_id": "who_1",
            "from_address": "ceo@bigcorp.com",
            "to": [USER_ID],
            "subject": "Quarterly results",
            "timestamp": "2026-02-12T08:00:00Z",
            "body": "Dear team, Q4 results exceeded expectations by 15%.",
        }
    ])
    await request(
        client, "POST", ROUTE_CHAT,
        "ask who sent the email",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "question": "Who sent the quarterly results email?",
        },
    )


async def test_action_items_question(client):
    """Ask the pipeline to extract action items."""
    tid = f"{THREAD_ID}_actions"
    await seed_thread(client, tid, [
        {
            "message_id": "act_1",
            "from_address": "manager@example.com",
            "to": [USER_ID],
            "subject": "Sprint review follow-up",
            "timestamp": "2026-02-15T14:00:00Z",
            "body": (
                "Hi,\n\nFollow-up from today's sprint review:\n"
                "1. Alice to fix login bug by Friday\n"
                "2. Bob to update the API docs by next Monday\n"
                "3. Charlie to demo the new dashboard at next sprint\n\n"
                "Thanks!"
            ),
        }
    ])
    await request(
        client, "POST", ROUTE_CHAT,
        "extract action items",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "question": "What are the action items from this thread?",
        },
    )


async def test_empty_question_string(client):
    """Empty question string – server should still respond (not crash)."""
    tid = f"{THREAD_ID}_empty_q"
    await seed_thread(client, tid, make_messages(USER_ID, n=1))
    await request(
        client, "POST", ROUTE_CHAT,
        "empty question string (no crash)",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "question": "",
        },
    )


async def test_long_question(client):
    """Very long question (300 chars)."""
    tid = f"{THREAD_ID}_longq"
    await seed_thread(client, tid, make_messages(USER_ID, n=2))
    long_q = "What is the main topic discussed " * 9  # ~300 chars
    await request(
        client, "POST", ROUTE_CHAT,
        "long question (300 chars)",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "question": long_q,
        },
    )


async def test_parallel_chat_requests(client):
    """
    Ask 4 different questions against the same thread simultaneously.
    Tests that the pipeline handles concurrent reads correctly.
    """
    tid = f"{THREAD_ID}_parallel"
    await seed_thread(client, tid, [
        {
            "message_id": "par_1",
            "from_address": "boss@example.com",
            "to": [USER_ID],
            "subject": "Year-end review",
            "timestamp": "2026-02-18T10:00:00Z",
            "body": (
                "Hi,\n\nYear-end review is on December 15th at 3pm. "
                "Please prepare a self-assessment. Budget for bonuses is $50k. "
                "HR will send the forms by Dec 1st."
            ),
        }
    ])

    questions = [
        "When is the year-end review?",
        "What should I prepare?",
        "What is the bonus budget?",
        "Who will send the forms?",
    ]
    tasks = [
        request(
            client, "POST", ROUTE_CHAT,
            f"parallel chat Q#{i+1}",
            results,
            json_body={
                "user_id": USER_ID,
                "thread_id": tid,
                "question": q,
            },
        )
        for i, q in enumerate(questions)
    ]
    await asyncio.gather(*tasks)


# ─── runner ───────────────────────────────────

async def main():
    header("POST /api/chat-with-thread  –  Test Suite")
    async with new_client() as client:
        await test_basic_question(client)
        await test_summary_question(client)
        await test_who_sent_question(client)
        await test_action_items_question(client)
        await test_empty_question_string(client)
        await test_long_question(client)
        await test_parallel_chat_requests(client)

    passed = results.print_summary()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
