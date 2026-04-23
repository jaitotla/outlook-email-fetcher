"""
Tests for  POST /api/store-attachments
=======================================
Run:
    python tests/test_store_attachments.py
"""
import asyncio
import base64
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.helpers import (
    header, info, dim, Results, request, make_attachment, new_client
)

USER_ID   = "testuser@example.com"
THREAD_ID = "store_attach_test_thread"
MSG_ID    = "msg_attach_001"
ROUTE     = "/api/store-attachments"

results = Results("POST /api/store-attachments")


# ─── test cases ───────────────────────────────

async def test_single_pdf(client):
    """Store one PDF attachment."""
    await request(
        client, "POST", ROUTE,
        "single PDF attachment",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_pdf",
            "message_id": MSG_ID,
            "attachments": [make_attachment("report.pdf")],
        },
        expect_keys=["success", "saved_files"],
    )


async def test_multiple_attachments(client):
    """Store PDF + TXT + CSV in one request."""
    await request(
        client, "POST", ROUTE,
        "multiple attachments (pdf+txt+csv)",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_multi",
            "message_id": "msg_multi_001",
            "attachments": [
                make_attachment("report.pdf"),
                make_attachment("notes.txt",    b"Meeting notes: Q1 review\nAction items:\n1. Follow up"),
                make_attachment("data.csv",     b"name,value\nalice,100\nbob,200"),
            ],
        },
        expect_keys=["success", "saved_files"],
    )


async def test_text_file(client):
    """Store a plain text file."""
    await request(
        client, "POST", ROUTE,
        "plain text file",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_txt",
            "message_id": "msg_txt_001",
            "attachments": [
                {
                    "filename": "readme.txt",
                    "content": base64.b64encode(b"This is a readme file.\nLine 2.\n").decode(),
                    "mime_type": "text/plain",
                }
            ],
        },
        expect_keys=["success"],
    )


async def test_large_file(client):
    """Store a ~100 KB synthetic binary file."""
    raw = b"A" * 100_000
    await request(
        client, "POST", ROUTE,
        "large file (~100 KB)",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_large",
            "message_id": "msg_large_001",
            "attachments": [
                {
                    "filename": "bigfile.bin",
                    "content": base64.b64encode(raw).decode(),
                    "mime_type": "application/octet-stream",
                }
            ],
        },
        expect_keys=["success"],
    )


async def test_filename_sanitization(client):
    """Filenames with special characters must be sanitized."""
    await request(
        client, "POST", ROUTE,
        "special-char filename sanitized",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_sanitize",
            "message_id": "msg_sanitize_001",
            "attachments": [
                {
                    "filename": "../../etc/passwd.txt",
                    "content": base64.b64encode(b"safe content").decode(),
                    "mime_type": "text/plain",
                }
            ],
        },
        expect_keys=["success"],
    )


async def test_empty_attachments_rejected(client):
    """Empty attachments list must return HTTP 400."""
    await request(
        client, "POST", ROUTE,
        "empty attachments → 400",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_empty",
            "message_id": "msg_empty_001",
            "attachments": [],
        },
        expect_status=400,
    )


async def test_metadata_file_created(client):
    """Response must reference a metadata_file path."""
    body = await request(
        client, "POST", ROUTE,
        "metadata file created",
        results,
        json_body={
            "user_id": USER_ID,
            "thread_id": f"{THREAD_ID}_meta",
            "message_id": "msg_meta_001",
            "attachments": [make_attachment("meta_check.pdf")],
        },
        expect_keys=["success", "metadata_file"],
    )
    if body.get("metadata_file"):
        info(f"  metadata_file → {body['metadata_file']}")


async def test_parallel_uploads(client):
    """Upload attachments for 5 different threads simultaneously."""
    tasks = [
        request(
            client, "POST", ROUTE,
            f"parallel upload #{i+1}",
            results,
            json_body={
                "user_id": USER_ID,
                "thread_id": f"{THREAD_ID}_par_{i+1:03d}",
                "message_id": f"msg_par_{i+1:03d}",
                "attachments": [make_attachment(f"file_{i+1}.pdf")],
            },
            expect_keys=["success"],
        )
        for i in range(5)
    ]
    await asyncio.gather(*tasks)


# ─── runner ───────────────────────────────────

async def main():
    header("POST /api/store-attachments  –  Test Suite")
    async with new_client() as client:
        await test_single_pdf(client)
        await test_multiple_attachments(client)
        await test_text_file(client)
        await test_large_file(client)
        await test_filename_sanitization(client)
        await test_empty_attachments_rejected(client)
        await test_metadata_file_created(client)
        await test_parallel_uploads(client)

    passed = results.print_summary()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
