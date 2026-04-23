"""
Tests for  POST /api/draft-with-attachments
============================================
Seeds emails + attachments first, then calls the draft pipeline.

Run:
    python tests/test_draft_with_attachments.py
"""
import asyncio
import base64
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.helpers import (
    header, info, dim, Results, request,
    make_messages, make_attachment, new_client
)

USER_ID   = "testuser@example.com"
THREAD_ID = "draft_test_thread"
ROUTE_LOG  = "/api/log-email"
ROUTE_ATT  = "/api/store-attachments"
ROUTE_DRAFT = "/api/draft-with-attachments"

results = Results("POST /api/draft-with-attachments")


# ─── seed helpers ─────────────────────────────

async def seed_email(client, thread_id: str):
    await client.post(ROUTE_LOG, json={
        "user_id": USER_ID,
        "thread_id": thread_id,
        "messages": make_messages(USER_ID, n=2),
    })


async def seed_attachment(client, thread_id: str, filename="doc.pdf"):
    await client.post(ROUTE_ATT, json={
        "user_id": USER_ID,
        "thread_id": thread_id,
        "message_id": "seed_msg_001",
        "attachments": [make_attachment(filename)],
    })


# ─── test cases ───────────────────────────────

async def test_basic_draft(client):
    """Generate a draft with default preferences."""
    tid = f"{THREAD_ID}_basic"
    await seed_email(client, tid)
    await seed_attachment(client, tid, "proposal.pdf")
    await request(
        client, "POST", ROUTE_DRAFT,
        "basic draft generation",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "user_preferences": None,
        },
    )


async def test_professional_tone(client):
    """Generate a professional-tone draft."""
    tid = f"{THREAD_ID}_professional"
    await seed_email(client, tid)
    await seed_attachment(client, tid, "contract.pdf")
    await request(
        client, "POST", ROUTE_DRAFT,
        "professional tone draft",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "user_preferences": {
                "name": "Jane Smith",
                "position": "Senior Manager",
                "tone": "professional",
                "custom_instructions": "Be concise and use bullet points.",
            },
        },
    )


async def test_casual_tone(client):
    """Generate a casual-tone draft."""
    tid = f"{THREAD_ID}_casual"
    await seed_email(client, tid)
    await request(
        client, "POST", ROUTE_DRAFT,
        "casual tone draft",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "user_preferences": {
                "name": "Tom",
                "position": "Developer",
                "tone": "casual",
            },
        },
    )


async def test_formal_with_name(client):
    """Formal draft signed with user name and position."""
    tid = f"{THREAD_ID}_formal"
    await seed_email(client, tid)
    await seed_attachment(client, tid, "annual_report.pdf")
    await request(
        client, "POST", ROUTE_DRAFT,
        "formal draft with name",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "user_preferences": {
                "name": "Dr. Emily Chen",
                "position": "Chief Executive Officer",
                "tone": "formal",
                "custom_instructions": "Include a thank-you opening paragraph.",
            },
        },
    )


async def test_no_attachments(client):
    """Draft for a thread that has no attachments – should still work."""
    tid = f"{THREAD_ID}_noattach"
    await seed_email(client, tid)
    # No attachment seeding
    await request(
        client, "POST", ROUTE_DRAFT,
        "draft with no attachments",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "user_preferences": {"tone": "professional"},
        },
    )


async def test_multiple_attachments(client):
    """Draft for thread with multiple attachment types."""
    tid = f"{THREAD_ID}_multiatt"
    await seed_email(client, tid)
    # Seed 3 attachments
    for fname in ["report.pdf", "spreadsheet.csv", "notes.txt"]:
        await seed_attachment(client, tid, fname)
    await request(
        client, "POST", ROUTE_DRAFT,
        "draft with multiple attachments",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": tid,
            "user_preferences": {
                "name": "Bob",
                "tone": "professional",
            },
        },
    )


async def test_parallel_drafts(client):
    """
    Generate drafts for 3 different threads simultaneously.
    """
    tids = [f"{THREAD_ID}_par_{i}" for i in range(3)]
    # Seed all threads first
    for tid in tids:
        await seed_email(client, tid)

    tasks = [
        request(
            client, "POST", ROUTE_DRAFT,
            f"parallel draft #{i+1}",
            results,
            json_body={
                "user_id": USER_ID,
                "thread_id": tid,
                "user_preferences": {"tone": "professional", "name": f"User {i+1}"},
            },
        )
        for i, tid in enumerate(tids)
    ]
    await asyncio.gather(*tasks)


# ─── runner ───────────────────────────────────

async def main():
    header("POST /api/draft-with-attachments  –  Test Suite")
    async with new_client() as client:
        await test_basic_draft(client)
        await test_professional_tone(client)
        await test_casual_tone(client)
        await test_formal_with_name(client)
        await test_no_attachments(client)
        await test_multiple_attachments(client)
        await test_parallel_drafts(client)

    passed = results.print_summary()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
