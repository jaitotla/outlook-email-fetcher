"""
OpenMailBot IMAP Monitor
========================
Multi-user IMAP email monitoring bot that:
  1. Monitors Gmail inboxes for new emails via IMAP
  2. Fetches email data in the format required for the label pipeline
  3. Calls /api/label-email-async endpoint with OAuth token
  4. Uses ThreadPoolExecutor for concurrent processing (up to 100 users)
  5. Runs continuously every minute

USAGE:
  1. Configure users in USERS list or load from database/CSV
  2. Set AGENT_URL to your OpenMailBot agent endpoint
  3. Run: python app.py

REQUIREMENTS:
  - User must have Gmail OAuth token (from Apps Script: ScriptApp.getOAuthToken())
  - IMAP must be enabled in Gmail settings
  - App-specific password or OAuth2 for IMAP authentication
"""

import imaplib
import email
import time
import json
import logging
import base64
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from email.header import decode_header
from email.utils import parsedate_to_datetime

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Agent endpoint (label pipeline)
AGENT_URL = "http://localhost:5051"  # Change to your agent URL (e.g., https://your-agent.com)

# User configuration
# NOTE: In production, load this from database, CSV, or environment variables
USERS = [
    {
        "email": "user1@gmail.com",
        "imap_password": "app_password_1",  # Gmail app-specific password
        "access_token": "ya29.xxx",  # OAuth token from ScriptApp.getOAuthToken()
    },
    {
        "email": "user2@gmail.com",
        "imap_password": "app_password_2",
        "access_token": "ya29.yyy",
    },
    # Add up to 100 users...
]

# Processing configuration
MAX_WORKERS = 10  # Process 10 users concurrently (adjust based on server capacity)
CHECK_INTERVAL_SECONDS = 60  # Check every 1 minute
NEW_EMAIL_WINDOW_MINUTES = 2  # Only process emails from last 2 minutes
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("imap_monitor")

# ═══════════════════════════════════════════════════════════════════
# EMAIL PROCESSING
# ═══════════════════════════════════════════════════════════════════

def decode_email_header(header: str) -> str:
    """Decode email header (handles MIME encoding)"""
    if not header:
        return ""
    
    decoded_parts = []
    for part, encoding in decode_header(header):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
        else:
            decoded_parts.append(str(part))
    return ' '.join(decoded_parts)


def extract_email_body(msg: email.message.Message) -> str:
    """Extract plain text body from email message"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
            
            # Get plain text
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                        break
                except Exception as e:
                    logger.warning(f"Failed to decode text/plain part: {e}")
            
            # Fallback to HTML
            elif content_type == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                except Exception as e:
                    logger.warning(f"Failed to decode text/html part: {e}")
    else:
        # Not multipart
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"Failed to decode single-part message: {e}")
    
    return body.strip()


def format_email_for_pipeline(msg: email.message.Message, msg_id: str) -> Dict[str, Any]:
    """
    Format email message for the label pipeline.
    
    Returns dict matching EmailMessage schema:
    {
        "message_id": str,
        "from_address": str,
        "to": List[str],
        "subject": str,
        "timestamp": str (ISO 8601),
        "body": str
    }
    """
    # Extract headers
    from_address = decode_email_header(msg.get("From", ""))
    to_addresses = decode_email_header(msg.get("To", ""))
    subject = decode_email_header(msg.get("Subject", ""))
    
    # Parse date
    date_header = msg.get("Date")
    try:
        dt = parsedate_to_datetime(date_header) if date_header else datetime.utcnow()
        timestamp = dt.isoformat()
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_header}': {e}")
        timestamp = datetime.utcnow().isoformat()
    
    # Extract body
    body = extract_email_body(msg)
    
    # Parse TO addresses (can be comma-separated)
    to_list = [addr.strip() for addr in to_addresses.split(",") if addr.strip()]
    
    return {
        "message_id": msg_id,
        "from_address": from_address,
        "to": to_list,
        "subject": subject,
        "timestamp": timestamp,
        "body": body
    }


def fetch_thread_messages(mail: imaplib.IMAP4_SSL, thread_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all messages in a Gmail thread.
    
    NOTE: Gmail IMAP doesn't natively support thread grouping like Gmail API.
    This is a simplified version that treats each message as its own thread.
    For true thread support, you'd need to use Gmail REST API.
    """
    # For IMAP, we'll just return the single message
    # In production, you could implement thread reconstruction using References/In-Reply-To headers
    return []


def call_label_pipeline(
    user_email: str,
    thread_id: str,
    gmail_thread_id: str,
    messages: List[Dict[str, Any]],
    access_token: str
) -> Optional[Dict[str, Any]]:
    """
    Call the /api/label-email-async endpoint.
    
    Expected payload:
    {
        "user_id": "user@example.com",
        "thread_id": "canonical_message_id",
        "gmail_thread_id": "gmail_hex_thread_id",
        "messages": [EmailMessage, ...],
        "access_token": "ya29.xxx"
    }
    
    Returns:
    {
        "job_id": "uuid",
        "status": "pending",
        "message": "Processing in background..."
    }
    """
    endpoint = f"{AGENT_URL}/api/label-email-async"
    
    payload = {
        "user_id": user_email,
        "thread_id": thread_id,
        "gmail_thread_id": gmail_thread_id,
        "messages": messages,
        "access_token": access_token
    }
    
    try:
        logger.info(f"📤 Calling label pipeline for {user_email} | Thread: {gmail_thread_id[:16]}...")
        
        response = requests.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 202:
            result = response.json()
            logger.info(f"✅ Job queued: {result.get('job_id')} | User: {user_email}")
            return result
        else:
            logger.error(f"❌ Label pipeline failed [{response.status_code}]: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"⏱️  Timeout calling label pipeline for {user_email}")
        return None
    except Exception as e:
        logger.error(f"❌ Error calling label pipeline for {user_email}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# IMAP MONITORING
# ═══════════════════════════════════════════════════════════════════

def process_single_user(user: Dict[str, str]) -> Dict[str, Any]:
    """
    Process new emails for a single user.
    
    Returns:
    {
        "user": "user@example.com",
        "emails_processed": 5,
        "jobs_queued": 5,
        "errors": []
    }
    """
    email_addr = user['email']
    imap_password = user['imap_password']
    access_token = user.get('access_token', '')
    
    result = {
        "user": email_addr,
        "emails_processed": 0,
        "jobs_queued": 0,
        "errors": []
    }
    
    try:
        # ── Connect to Gmail IMAP ──────────────────────────────────────
        logger.debug(f"🔌 Connecting to IMAP for {email_addr}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_addr, imap_password)
        mail.select("INBOX")
        
        # ── Search for UNSEEN emails from recent window ────────────────
        # Gmail IMAP search: UNSEEN = unread emails
        # SINCE = emails since a specific date
        cutoff_time = datetime.now() - timedelta(minutes=NEW_EMAIL_WINDOW_MINUTES)
        search_date = cutoff_time.strftime("%d-%b-%Y")  # Format: "04-May-2026"
        
        logger.debug(f"🔍 Searching UNSEEN emails since {search_date} for {email_addr}")
        _, message_ids = mail.search(None, f'(UNSEEN SINCE {search_date})')
        
        msg_id_list = message_ids[0].split()
        
        if not msg_id_list:
            logger.debug(f"📭 No new emails for {email_addr}")
            mail.logout()
            return result
        
        logger.info(f"📬 Found {len(msg_id_list)} new email(s) for {email_addr}")
        
        # ── Process each message ───────────────────────────────────────
        for msg_num in msg_id_list:
            try:
                # Fetch the email
                _, msg_data = mail.fetch(msg_num, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Get Message-ID and Gmail Thread ID
                message_id = msg.get("Message-ID", "").strip().strip("<>")
                
                # For Gmail IMAP, we need to use X-GM-THRID for true thread ID
                # But it's not always available, so we'll use the message ID as fallback
                _, thrid_data = mail.fetch(msg_num, "(X-GM-THRID)")
                gmail_thread_id = None
                
                # Parse X-GM-THRID from response
                if thrid_data and thrid_data[0]:
                    thrid_str = thrid_data[0].decode() if isinstance(thrid_data[0], bytes) else str(thrid_data[0])
                    # Response format: "123 (X-GM-THRID 1234567890)"
                    if "X-GM-THRID" in thrid_str:
                        gmail_thread_id = thrid_str.split("X-GM-THRID")[1].strip().rstrip(")")
                
                # Fallback: use message ID if no thread ID available
                if not gmail_thread_id:
                    gmail_thread_id = message_id
                
                # Check if email is recent enough (within NEW_EMAIL_WINDOW_MINUTES)
                date_header = msg.get("Date")
                try:
                    msg_time = parsedate_to_datetime(date_header) if date_header else datetime.utcnow()
                    time_diff = datetime.now(msg_time.tzinfo) - msg_time
                    
                    if time_diff.total_seconds() > (NEW_EMAIL_WINDOW_MINUTES * 60):
                        logger.debug(f"⏭️  Skipping old email: {message_id[:30]}... ({time_diff.total_seconds():.0f}s old)")
                        continue
                except Exception as e:
                    logger.warning(f"⚠️  Failed to parse date for {message_id}: {e}")
                    # Process anyway if date parsing fails
                
                # Format email for pipeline
                formatted_msg = format_email_for_pipeline(msg, message_id)
                
                logger.debug(f"📧 Processing: {formatted_msg['subject'][:50]}... | From: {formatted_msg['from_address'][:30]}")
                
                # Call label pipeline
                pipeline_result = call_label_pipeline(
                    user_email=email_addr,
                    thread_id=message_id,  # Canonical Message-ID
                    gmail_thread_id=gmail_thread_id,  # Gmail's thread ID
                    messages=[formatted_msg],  # Single message (IMAP doesn't group threads)
                    access_token=access_token
                )
                
                result["emails_processed"] += 1
                
                if pipeline_result:
                    result["jobs_queued"] += 1
                else:
                    result["errors"].append(f"Failed to queue job for message {message_id[:30]}...")
                    
            except Exception as msg_err:
                error_msg = f"Error processing message {msg_num}: {str(msg_err)[:100]}"
                logger.error(f"❌ {error_msg}")
                result["errors"].append(error_msg)
        
        # ── Cleanup ────────────────────────────────────────────────────
        mail.logout()
        logger.info(f"✅ Completed {email_addr}: {result['jobs_queued']}/{result['emails_processed']} jobs queued")
        
    except imaplib.IMAP4.error as imap_err:
        error_msg = f"IMAP error for {email_addr}: {str(imap_err)[:100]}"
        logger.error(f"❌ {error_msg}")
        result["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Connection failed for {email_addr}: {str(e)[:100]}"
        logger.error(f"❌ {error_msg}")
        result["errors"].append(error_msg)
    
    return result


def run_monitoring_cycle():
    """
    Run one monitoring cycle for all users using ThreadPoolExecutor.
    Processes up to MAX_WORKERS users concurrently.
    """
    logger.info("")
    logger.info("╔════════════════════════════════════════════════════════════════╗")
    logger.info("║         IMAP MONITORING CYCLE START                            ║")
    logger.info("╚════════════════════════════════════════════════════════════════╝")
    logger.info(f"Users: {len(USERS)} | Max Workers: {MAX_WORKERS}")
    logger.info(f"Window: {NEW_EMAIL_WINDOW_MINUTES} min | Agent: {AGENT_URL}")
    logger.info("")
    
    cycle_start = time.time()
    total_processed = 0
    total_queued = 0
    total_errors = 0
    
    # Process users in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all user tasks
        future_to_user = {
            executor.submit(process_single_user, user): user
            for user in USERS
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_user):
            user = future_to_user[future]
            try:
                result = future.result()
                total_processed += result["emails_processed"]
                total_queued += result["jobs_queued"]
                total_errors += len(result["errors"])
                
                if result["errors"]:
                    for error in result["errors"]:
                        logger.warning(f"⚠️  {error}")
                        
            except Exception as exc:
                logger.error(f"❌ User {user['email']} generated exception: {exc}")
                total_errors += 1
    
    # ── Cycle Summary ──────────────────────────────────────────────────
    cycle_duration = time.time() - cycle_start
    
    logger.info("")
    logger.info("╔════════════════════════════════════════════════════════════════╗")
    logger.info("║         IMAP MONITORING CYCLE COMPLETE                         ║")
    logger.info("╚════════════════════════════════════════════════════════════════╝")
    logger.info(f"Duration:         {cycle_duration:.2f}s")
    logger.info(f"Emails Processed: {total_processed}")
    logger.info(f"Jobs Queued:      {total_queued}")
    logger.info(f"Errors:           {total_errors}")
    logger.info("")
    
    return cycle_duration


# ═══════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════

def main():
    """
    Main monitoring loop.
    Runs continuously, checking for new emails every CHECK_INTERVAL_SECONDS.
    """
    logger.info("🚀 OpenMailBot IMAP Monitor Starting...")
    logger.info(f"📊 Configuration:")
    logger.info(f"   Users:          {len(USERS)}")
    logger.info(f"   Max Workers:    {MAX_WORKERS}")
    logger.info(f"   Check Interval: {CHECK_INTERVAL_SECONDS}s")
    logger.info(f"   Email Window:   {NEW_EMAIL_WINDOW_MINUTES} min")
    logger.info(f"   Agent URL:      {AGENT_URL}")
    logger.info("")
    
    # Validate configuration
    if not USERS:
        logger.error("❌ No users configured! Update USERS list in app.py")
        return
    
    if not AGENT_URL:
        logger.error("❌ AGENT_URL not set! Update AGENT_URL in app.py")
        return
    
    # Check agent connectivity
    try:
        logger.info("🔍 Testing agent connectivity...")
        response = requests.get(f"{AGENT_URL}/health", timeout=10)
        if response.status_code == 200:
            logger.info("✅ Agent is reachable")
        else:
            logger.warning(f"⚠️  Agent returned HTTP {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️  Cannot reach agent: {e}")
        logger.warning("   Continuing anyway (agent may come online later)")
    
    logger.info("")
    logger.info("🔄 Starting monitoring loop...")
    logger.info("")
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        
        try:
            # Run one monitoring cycle
            cycle_duration = run_monitoring_cycle()
            
            # Calculate sleep time (ensure we check every CHECK_INTERVAL_SECONDS)
            sleep_time = max(0, CHECK_INTERVAL_SECONDS - cycle_duration)
            
            if sleep_time > 0:
                logger.info(f"😴 Sleeping for {sleep_time:.2f}s until next cycle...")
                logger.info(f"   Next cycle: #{cycle_count + 1} at {(datetime.now() + timedelta(seconds=sleep_time)).strftime('%H:%M:%S')}")
                logger.info("")
                time.sleep(sleep_time)
            else:
                logger.warning(f"⚠️  Cycle took longer than interval ({cycle_duration:.2f}s > {CHECK_INTERVAL_SECONDS}s)")
                logger.warning("   Starting next cycle immediately...")
                logger.info("")
                
        except KeyboardInterrupt:
            logger.info("")
            logger.info("🛑 Shutting down gracefully...")
            logger.info("👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error in main loop: {e}")
            logger.error("   Continuing in 10 seconds...")
            time.sleep(10)


if __name__ == "__main__":
    main()
