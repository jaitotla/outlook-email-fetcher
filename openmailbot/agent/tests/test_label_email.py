"""
Tests for  POST /api/label-email
=================================
Run:
    python tests/test_label_email.py
"""
import asyncio
import sys
import os
import time
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.helpers import (
    header, info, dim, Results, request, make_messages, new_client
)

# ─── LOGGING SETUP ───────────────────────────────
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%H:%M:%S.%f'[:-3]
)
logger = logging.getLogger("API_TEST")

USER_ID   = "testuser@example.com"
THREAD_ID = "label_email_test_thread"
ROUTE     = "/api/label-email"

results = Results("POST /api/label-email")


# ─── comprehensive logging helper ───────────────────────────────

async def detailed_logged_request(client, method, route, test_name, payload, results):
    """
    Execute request with COMPREHENSIVE logging at every step.
    Shows:
    - Input data structure
    - Request timing
    - Response data
    - Processing flow
    - Async operations
    """
    
    header(f"\n🔍 DETAILED REQUEST LOG: {test_name}")
    
    # STEP 1: Log incoming payload
    logger.info("=" * 80)
    logger.info("STEP 1: INCOMING REQUEST PAYLOAD")
    logger.info("=" * 80)
    logger.info(f"Route: {method} {route}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"Payload Size: {len(json.dumps(payload))} bytes")
    logger.info(f"Payload Structure:")
    logger.info(f"  - user_id: {payload.get('user_id')}")
    logger.info(f"  - thread_id: {payload.get('thread_id')}")
    logger.info(f"  - num_messages: {len(payload.get('messages', []))}")
    
    # STEP 2: Log message details
    logger.info("=" * 80)
    logger.info("STEP 2: MESSAGE DETAILS (INPUT DATA)")
    logger.info("=" * 80)
    for idx, msg in enumerate(payload.get('messages', []), 1):
        logger.info(f"Message #{idx}:")
        logger.info(f"  - ID: {msg.get('message_id')}")
        logger.info(f"  - From: {msg.get('from_address')}")
        logger.info(f"  - To: {msg.get('to')}")
        logger.info(f"  - Subject: {msg.get('subject')}")
        logger.info(f"  - Body Length: {len(msg.get('body', ''))} chars")
        logger.info(f"  - Timestamp: {msg.get('timestamp')}")
    
    # STEP 3: Start request (async point)
    logger.info("=" * 80)
    logger.info("STEP 3: SENDING REQUEST (ASYNC OPERATION)")
    logger.info("=" * 80)
    req_start = time.time()
    req_start_dt = datetime.now()
    logger.info(f"Request START time: {req_start_dt.strftime('%H:%M:%S.%f')[:-3]}")
    logger.info(f"🚀 Awaiting request...")
    
    try:
        # ASYNC: Wait for response
        response = await request(
            client, method, route, test_name, results,
            json_body=payload,
            expect_keys=["success", "label", "category", "topic", "subtopic"],
        )
        
        req_end = time.time()
        req_end_dt = datetime.now()
        req_elapsed = req_end - req_start
        
        logger.info(f"✅ Response received at: {req_end_dt.strftime('%H:%M:%S.%f')[:-3]}")
        logger.info(f"⏱️  Total request time: {req_elapsed:.3f}s")
        
        # STEP 4: Log response structure
        logger.info("=" * 80)
        logger.info("STEP 4: RESPONSE STRUCTURE (DATA OUT)")
        logger.info("=" * 80)
        logger.info(f"Response Type: {type(response)}")
        logger.info(f"Response Size: {len(json.dumps(response)) if response else 0} bytes")
        logger.info(f"Success: {response.get('success', 'N/A')}")
        logger.info(f"HTTP Status: OK (200)")
        
        # STEP 5: Log response fields
        logger.info("=" * 80)
        logger.info("STEP 5: CLASSIFICATION RESULTS (FINAL OUTPUT)")
        logger.info("=" * 80)
        logger.info(f"Label: {response.get('label', 'N/A')}")
        logger.info(f"Category: {response.get('category', 'N/A')}")
        logger.info(f"Topic: {response.get('topic', 'N/A')}")
        logger.info(f"Subtopic: {response.get('subtopic', 'N/A')}")
        logger.info(f"Messages Processed: {response.get('messages_processed', 'N/A')}")
        logger.info(f"Graph Store Status: {response.get('graph_store_status', 'N/A')}")
        
        # STEP 6: Log processing chain
        if response.get('processing_chain'):
            logger.info("=" * 80)
            logger.info("STEP 6: PROCESSING CHAIN (INTERNAL FLOW)")
            logger.info("=" * 80)
            for step_name, step_result in response.get('processing_chain', {}).items():
                logger.info(f"  → {step_name}: {step_result}")
        
        # STEP 7: Summary
        logger.info("=" * 80)
        logger.info("STEP 7: REQUEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Test: {test_name}")
        logger.info(f"✅ Status: SUCCESS")
        logger.info(f"✅ Total Time: {req_elapsed:.3f}s")
        logger.info(f"✅ Messages In: {len(payload.get('messages', []))}")
        logger.info(f"✅ Classification Out: {response.get('label')}")
        logger.info("=" * 80)
        
        return response
        
    except Exception as e:
        req_end = time.time()
        req_elapsed = req_end - req_start
        logger.error("=" * 80)
        logger.error("❌ REQUEST FAILED")
        logger.error("=" * 80)
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {str(e)}")
        logger.error(f"Time Elapsed Before Error: {req_elapsed:.3f}s")
        logger.error("=" * 80)
        raise


async def timed_parallel(test_name, tasks, results):
    """Execute parallel tasks and track total time."""
    start_time = datetime.now()
    start_timestamp = time.time()
    
    await asyncio.gather(*tasks)
    
    end_time = datetime.now()
    end_timestamp = time.time()
    elapsed = end_timestamp - start_timestamp
    
    info(f"  📊 PARALLEL [{test_name}] "
         f"START: {start_time.strftime('%H:%M:%S.%f')[:-3]} | "
         f"END: {end_time.strftime('%H:%M:%S.%f')[:-3]} | "
         f"TOTAL: {elapsed:.3f}s")


# ─── helpers to build thematic messages ───────

# ─── test cases ───────────────────────────────

async def test_comprehensive_logging_demo(client):
    """
    COMPREHENSIVE DEMO - Single request with ALL logging.
    Shows entire data flow from input → processing → output.
    """
    payload = {
        "user_id": USER_ID,
        "thread_id": f"{THREAD_ID}_comprehensive",
        "messages": [
            {
                "message_id": "demo_msg_1",
                "from_address": "project-manager@company.com",
                "to": [USER_ID],
                "subject": "Team Standup - Tomorrow @ 9 AM",
                "timestamp": "2026-02-23T14:30:00Z",
                "body": """Hi team,

Let's have our daily standup tomorrow at 9 AM in Conference Room B.

Agenda:
1. Sprint progress review
2. Blockers and risks
3. Code review status

Please come prepared with updates.

Thanks,
Project Manager""",
            },
            {
                "message_id": "demo_msg_2",
                "from_address": "qa-lead@company.com",
                "to": [USER_ID],
                "subject": "Re: Team Standup - Tomorrow @ 9 AM",
                "timestamp": "2026-02-23T15:00:00Z",
                "body": """Thanks for organizing!

I'll have the test results ready for discussion.
Can we also cover the performance regression issue we found?

See you tomorrow!
QA Lead""",
            },
        ],
    }
    
    await detailed_logged_request(
        client, "POST", ROUTE,
        "DEMO: Complete Email Thread Labeling",
        payload,
        results,
    )


async def test_quick_single_message(client):
    """Quick test: Single simple message"""
    payload = {
        "user_id": USER_ID,
        "thread_id": f"{THREAD_ID}_quick",
        "messages": [
            {
                "message_id": "quick_1",
                "from_address": "invoice@vendor.com",
                "to": [USER_ID],
                "subject": "Invoice #12345 - Payment Due",
                "timestamp": "2026-02-23T10:00:00Z",
                "body": "Please find attached invoice #12345 for $2,500. Due by March 10th.",
            },
        ],
    }
    
    await detailed_logged_request(
        client, "POST", ROUTE,
        "QUICK TEST: Single Invoice Message",
        payload,
        results,
    )


# ─── runner ───────────────────────────────────

async def main():
    header("POST /api/label-email  –  COMPREHENSIVE LOGGING DEMO")
    header("This test shows EVERY detail: input data, processing flow, async points, and output")
    
    async with new_client() as client:
        # Single comprehensive test with detailed logging at every step
        await test_comprehensive_logging_demo(client)
        
        header("\n\n" + "="*80)
        header("Additional Quick Test (for comparison)")
        header("="*80)
        await test_quick_single_message(client)

    passed = results.print_summary()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
