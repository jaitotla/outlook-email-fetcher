"""
AUTOMATED EMAIL LABELING MONITOR
Runs every 1 minute to fetch, label, and organize Gmail emails automatically.

This script:
1. Runs continuously with 1-minute intervals
2. Tracks last run timestamp (persisted to file)
3. Fetches new emails since last run
4. Sends emails to label endpoint (main.py) for AI classification
5. Applies returned labels via IMAP

Gmail Label Colors (created via Code.gs on add-on installation):
- Response: backgroundColor="#4a86e8", textColor="#ffffff" (blue)
- Fyi: backgroundColor="#16a766", textColor="#ffffff" (green)
- Notification: backgroundColor="#e7e7e7", textColor="#000000" (light gray)
- Meeting: backgroundColor="#653e9b", textColor="#ffffff" (purple)
- Awaiting Reply: backgroundColor="#fad165", textColor="#000000" (yellow)
- Escalation: backgroundColor="#cc3a21", textColor="#ffffff" (red)
- Hotels: backgroundColor="#ffad47", textColor="#000000" (orange)
- Airline/Airlines: backgroundColor="#7a4706", textColor="#ffffff" (brown)
- Travel: backgroundColor="#149e60", textColor="#ffffff" (green)
- Restaurant: backgroundColor="#ffbc6b", textColor="#000000" (light orange)
- Booking: backgroundColor="#4a86e8", textColor="#ffffff" (blue)
- Bank: backgroundColor="#2da2bb", textColor="#ffffff" (teal)
- Recruitment: backgroundColor="#8e63ce", textColor="#ffffff" (purple)
"""
import imaplib
import email
import re
import requests
import time
import json
import os
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

# --- USER CONFIG ---
USER_ID = 'patilswapnil1606@gmail.com'  # <-- Your Gmail address
APP_PASSWORD = 'vcjx frxi nwqr kwvu'  # <-- Your Gmail app password (16 chars)
AGENT_URL = 'http://localhost:5051'  # <-- Your agent server URL

# IMAP settings
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# Monitoring settings
CHECK_INTERVAL_SECONDS = 60  # Run every 1 minute
TIMESTAMP_FILE = "last_run_timestamp.txt"  # File to persist last run time

# Gmail label color codes (for reference)
GMAIL_COLORS = {
    "Response": {"backgroundColor": "#4a86e8", "textColor": "#ffffff"},
    "Fyi": {"backgroundColor": "#16a766", "textColor": "#ffffff"},
    "Notification": {"backgroundColor": "#e7e7e7", "textColor": "#000000"},
    "Meeting": {"backgroundColor": "#653e9b", "textColor": "#ffffff"},
    "Awaiting Reply": {"backgroundColor": "#fad165", "textColor": "#000000"},
    "Escalation": {"backgroundColor": "#cc3a21", "textColor": "#ffffff"},
    "Hotels": {"backgroundColor": "#ffad47", "textColor": "#000000"},
    "Airline": {"backgroundColor": "#7a4706", "textColor": "#ffffff"},
    "Airlines": {"backgroundColor": "#7a4706", "textColor": "#ffffff"},
    "Travel": {"backgroundColor": "#149e60", "textColor": "#ffffff"},
    "Restaurant": {"backgroundColor": "#ffbc6b", "textColor": "#000000"},
    "Booking": {"backgroundColor": "#4a86e8", "textColor": "#ffffff"},
    "Bank": {"backgroundColor": "#2da2bb", "textColor": "#ffffff"},
    "Recruitment": {"backgroundColor": "#8e63ce", "textColor": "#ffffff"},
}

# ============================================================================
# TIMESTAMP TRACKING
# ============================================================================

def get_last_run_timestamp() -> datetime:
    """
    Load the last run timestamp from file.
    Returns 1 minute ago if file doesn't exist (first run).
    """
    timestamp_path = Path(__file__).parent / TIMESTAMP_FILE
    
    if timestamp_path.exists():
        try:
            with open(timestamp_path, 'r') as f:
                timestamp_str = f.read().strip()
                # Parse ISO format: 2026-05-04T12:34:56+00:00
                last_run = datetime.fromisoformat(timestamp_str)
                # Ensure UTC
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                else:
                    last_run = last_run.astimezone(timezone.utc)
                print(f"📅 Last run: {last_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                return last_run
        except Exception as e:
            print(f"⚠️  Failed to read timestamp file: {e}")
    
    # First run: start from 1 minute ago
    first_run = datetime.now(timezone.utc) - timedelta(minutes=1)
    print(f"🆕 First run detected, starting from 1 minute ago: {first_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    return first_run


def save_last_run_timestamp(timestamp: datetime) -> None:
    """Save the last run timestamp to file (ISO format with timezone)."""
    timestamp_path = Path(__file__).parent / TIMESTAMP_FILE
    
    try:
        # Ensure timestamp is timezone-aware (UTC)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        
        # Save as ISO format with timezone
        with open(timestamp_path, 'w') as f:
            f.write(timestamp.isoformat())
        print(f"💾 Saved timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    except Exception as e:
        print(f"❌ Failed to save timestamp: {e}")


# ============================================================================
# EMAIL FETCHING (IMAP)
# ============================================================================

def _decode_header_value(header_value: str) -> str:
    """Fully decode a potentially RFC-2047-encoded header string."""
    if not header_value:
        return ""
    parts = decode_header(header_value)
    decoded_parts = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def _extract_email_address(from_field: str) -> str:
    """Pull the bare address out of 'Display Name <addr@host>'."""
    match = re.search(r"<(.+?)>", from_field)
    return match.group(1).strip() if match else from_field.strip()


def _get_plain_body(msg) -> str:
    """Extract the plain-text body from an email.Message object."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if (
                part.get_content_type() == "text/plain"
                and part.get("Content-Disposition") != "attachment"
            ):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body


def _parse_timestamp(msg) -> datetime:
    """Return a datetime object from the email Date header (UTC)."""
    date_str = msg.get("Date", "")
    try:
        dt = parsedate_to_datetime(date_str)
        # Normalize to UTC
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def get_emails(
    user_id: str,
    app_password: str,
    last_check: Optional[datetime] = None,
    imap_host: str = IMAP_HOST,
    imap_port: int = IMAP_PORT
) -> List[Dict[str, Any]]:
    """
    Fetch emails from IMAP server.
    
    Parameters
    ----------
    user_id : str
        Email address for IMAP login
    app_password : str
        IMAP app password (Gmail: 16-character app password)
    last_check : Optional[datetime]
        Fetch only emails received after this datetime (UTC).
        If None, fetches emails from the last day.
    imap_host : str
        IMAP server hostname (default: "imap.gmail.com")
    imap_port : int
        IMAP SSL port (default: 993)
    
    Returns
    -------
    List[Dict[str, Any]]
        List of email dictionaries with keys: message_id, from_address,
        subject, timestamp, body, uid (IMAP UID for labeling)
    """
    # If no last_check provided, fetch emails from the last day
    if last_check is None:
        last_check = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    elif last_check.tzinfo is None:
        # Ensure last_check is timezone-aware (UTC)
        last_check = last_check.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if in different timezone
        last_check = last_check.astimezone(timezone.utc)
    
    print(f"Fetching emails since: {last_check.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    # IMAP SINCE criterion needs "DD-Mon-YYYY" format
    since_str = last_check.strftime("%d-%b-%Y")
    
    # Connect to IMAP server
    imap = imaplib.IMAP4_SSL(imap_host, imap_port)
    try:
        imap.login(user_id.strip(), app_password.strip())
        imap.select("INBOX", readonly=True)
        
        # Search for emails since the specified date
        status, data = imap.search(None, f"SINCE {since_str}")
        if status != "OK" or not data[0]:
            print("No messages found!")
            return []
        
        mail_ids = data[0].split()
        emails = []
        
        for num in mail_ids:
            # Fetch both RFC822 and UID for labeling later
            status, msg_data = imap.fetch(num, "(RFC822 UID)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            
            # Extract UID and message from response
            # msg_data structure: [(b'1 (UID 12345 RFC822 {size}', b'message...'), b')']
            uid = None
            msg = None
            
            for item in msg_data:
                if isinstance(item, tuple):
                    # First element of tuple contains UID info
                    if isinstance(item[0], bytes):
                        uid_match = re.search(rb'UID (\d+)', item[0])
                        if uid_match:
                            uid = uid_match.group(1).decode()
                    # Second element contains the message
                    if len(item) > 1 and isinstance(item[1], bytes):
                        msg = email.message_from_bytes(item[1])
                elif isinstance(item, bytes) and not msg:
                    # Fallback: sometimes the message is directly in bytes
                    try:
                        msg = email.message_from_bytes(item)
                    except:
                        pass
            
            if msg is None:
                continue
            
            # Parse timestamp
            msg_dt = _parse_timestamp(msg)
            
            # Post-filter: skip messages older than last_check
            # (IMAP SINCE has day-level granularity only)
            if msg_dt < last_check:
                continue
            
            # Extract headers
            subject = _decode_header_value(msg.get("Subject", "(no subject)"))
            from_raw = _decode_header_value(msg.get("From", ""))
            from_address = _extract_email_address(from_raw)
            
            # Extract message ID
            message_id = (msg.get("Message-ID") or "").strip().strip("<>")
            
            # Extract body
            body = _get_plain_body(msg)
            
            # Format timestamp as string
            timestamp_str = msg_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            emails.append({
                "message_id": message_id,
                "from_address": from_address,
                "subject": subject,
                "timestamp": timestamp_str,
                "body": body,
                "uid": uid,
                "imap_id": num.decode() if isinstance(num, bytes) else num,
            })
        
        print(f"\nFound {len(emails)} email(s)\n")
        return emails
        
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass


def apply_label_to_emails(
    user_id: str,
    app_password: str,
    email_uids: List[str],
    label_name: str,
    imap_host: str = IMAP_HOST,
    imap_port: int = IMAP_PORT
) -> bool:
    """
    Apply a Gmail label to specific emails using IMAP.
    
    Note: IMAP can apply labels, but cannot set label colors.
    To create colored labels, use the Gmail API.
    
    Parameters
    ----------
    user_id : str
        Email address for IMAP login
    app_password : str
        IMAP app password
    email_uids : List[str]
        List of IMAP UIDs to label (from get_emails results)
    label_name : str
        Label name to apply (will be created if it doesn't exist)
    imap_host : str
        IMAP server hostname
    imap_port : int
        IMAP SSL port
    
    Returns
    -------
    bool
        True if successful, False otherwise
    """
    if not email_uids:
        print("No emails to label!")
        return False
    
    imap = imaplib.IMAP4_SSL(imap_host, imap_port)
    try:
        imap.login(user_id.strip(), app_password.strip())
        imap.select("INBOX", readonly=False)  # Need write access
        
        # Gmail IMAP uses X-GM-LABELS for label support
        # Apply label to each email
        for uid in email_uids:
            try:
                # Store the label using Gmail's X-GM-LABELS extension
                status, data = imap.uid('STORE', uid, '+X-GM-LABELS', f'"{label_name}"')
                if status == "OK":
                    print(f"✓ Applied label '{label_name}' to email UID {uid}")
                else:
                    print(f"✗ Failed to apply label to UID {uid}: {data}")
            except Exception as e:
                print(f"✗ Error labeling UID {uid}: {e}")
        
        print(f"\nSuccessfully applied '{label_name}' label to {len(email_uids)} email(s)")
        print(f"\nNote: Label color must be set via Gmail API.")
        print(f"For red color, use: backgroundColor='#fb4c2f', textColor='#ffffff'")
        return True
        
    except Exception as e:
        print(f"Error applying labels: {e}")
        return False
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass


# ============================================================================
# LABEL API INTEGRATION
# ============================================================================

def get_label_from_api(emails: List[Dict[str, Any]]) -> Optional[str]:
    """
    Send emails to label endpoint and get classification.
    
    Parameters
    ----------
    emails : List[Dict[str, Any]]
        List of email dictionaries from get_emails()
    
    Returns
    -------
    Optional[str]
        Label name if successful, None if API call fails
    """
    if not emails:
        return None
    
    # Use first email for thread identification
    first_email = emails[0]
    thread_id = first_email.get('message_id', 'unknown_thread')
    
    # Format payload for /api/label-email endpoint
    # Expected format based on LogEmailRequest in main.py:
    # {
    #     "user_id": "user@example.com",
    #     "thread_id": "thread_xxx",
    #     "messages": [
    #         {
    #             "message_id": "msg_xxx",
    #             "from_address": "sender@example.com",
    #             "to": ["recipient@example.com"],
    #             "subject": "Meeting tomorrow",
    #             "timestamp": "2026-02-06T10:00:00Z",
    #             "body": "<html>...</html>"
    #         }
    #     ]
    # }
    
    # Transform emails to match expected format
    messages = []
    for em in emails:
        # Convert timestamp to ISO format with timezone
        try:
            # Parse the timestamp string back to datetime
            dt = datetime.strptime(em['timestamp'], "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
            iso_timestamp = dt.isoformat()
        except Exception:
            iso_timestamp = em['timestamp']
        
        messages.append({
            "message_id": em['message_id'],
            "from_address": em['from_address'],
            "to": [USER_ID],  # Assume email was sent to user
            "subject": em['subject'],
            "timestamp": iso_timestamp,
            "body": em['body']
        })
    
    payload = {
        "user_id": USER_ID,
        "thread_id": thread_id,
        "messages": messages
    }
    
    # Call label endpoint
    endpoint = f"{AGENT_URL}/api/label-email"
    
    try:
        print(f"🔍 Sending {len(messages)} email(s) to label API...")
        print(f"   Thread ID: {thread_id}")
        print(f"   Endpoint: {endpoint}")
        
        response = requests.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            label = data.get('label')
            classification_method = data.get('classification_method', 'unknown')
            print(f"✅ Label received: {label} (method: {classification_method})")
            return label
        else:
            print(f"❌ Label API error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Label API request failed: {e}")
        return None


# ============================================================================
# MAIN MONITORING LOOP
# ============================================================================

def monitor_emails_continuously():
    """
    Main monitoring loop - runs every 1 minute continuously.
    
    Process:
    1. Load last run timestamp (or -1 minute for first run)
    2. Fetch new emails since last run
    3. Group emails by thread (for multi-message threads)
    4. Send to label API for classification
    5. Apply returned labels via IMAP
    6. Save current timestamp
    7. Wait 1 minute and repeat
    """
    print("=" * 80)
    print("📧 AUTOMATED EMAIL LABELING MONITOR")
    print("=" * 80)
    print(f"User: {USER_ID}")
    print(f"Agent URL: {AGENT_URL}")
    print(f"Check Interval: {CHECK_INTERVAL_SECONDS} seconds (1 minute)")
    print(f"Timestamp File: {TIMESTAMP_FILE}")
    print("=" * 80)
    print("\n🚀 Starting monitoring loop... (Press Ctrl+C to stop)\n")
    
    try:
        while True:
            cycle_start = datetime.now(timezone.utc)
            print(f"\n{'=' * 80}")
            print(f"🔄 Monitor Cycle Started: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"{'=' * 80}\n")
            
            # Step 1: Get last run timestamp
            last_run = get_last_run_timestamp()
            
            # Step 2: Fetch new emails
            try:
                emails = get_emails(
                    user_id=USER_ID,
                    app_password=APP_PASSWORD,
                    last_check=last_run,
                    imap_host=IMAP_HOST,
                    imap_port=IMAP_PORT
                )
            except Exception as e:
                print(f"❌ Error fetching emails: {e}")
                emails = []
            
            # Step 3: Process emails if found
            if emails:
                print(f"\n📬 Processing {len(emails)} new email(s)...")
                
                # Group emails by thread (for now, process individually)
                # In a real implementation, you'd group by In-Reply-To header
                for idx, em in enumerate(emails, 1):
                    print(f"\n--- Email {idx}/{len(emails)} ---")
                    print(f"From: {em['from_address']}")
                    print(f"Subject: {em['subject'][:60]}...")
                    print(f"Date: {em['timestamp']}")
                    
                    # Get label from API
                    label = get_label_from_api([em])
                    
                    if label:
                        # Apply label via IMAP
                        uid = em.get('uid')
                        if uid:
                            try:
                                print(f"🏷️  Applying label '{label}' to email UID {uid}...")
                                success = apply_label_to_emails(
                                    user_id=USER_ID,
                                    app_password=APP_PASSWORD,
                                    email_uids=[uid],
                                    label_name=label,
                                    imap_host=IMAP_HOST,
                                    imap_port=IMAP_PORT
                                )
                                if success:
                                    print(f"✅ Label applied successfully!")
                                else:
                                    print(f"⚠️  Label application failed")
                            except Exception as e:
                                print(f"❌ Error applying label: {e}")
                        else:
                            print(f"⚠️  No UID available for labeling")
                    else:
                        print(f"⚠️  No label returned from API")
                
                print(f"\n✅ Processed {len(emails)} email(s)")
            else:
                print("ℹ️  No new emails found")
            
            # Step 4: Save current timestamp
            save_last_run_timestamp(cycle_start)
            
            # Step 5: Calculate wait time
            cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            wait_time = max(0, CHECK_INTERVAL_SECONDS - cycle_duration)
            
            print(f"\n{'=' * 80}")
            print(f"✅ Cycle Complete")
            print(f"   Duration: {cycle_duration:.1f}s")
            print(f"   Next run in: {wait_time:.0f}s")
            print(f"{'=' * 80}")
            
            # Wait for next cycle
            if wait_time > 0:
                print(f"\n💤 Sleeping for {wait_time:.0f} seconds...\n")
                time.sleep(wait_time)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped by user (Ctrl+C)")
        print("=" * 80)
        print("Thank you for using OpenMailBot!")
        print("=" * 80)


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Check if user wants to run in continuous monitoring mode
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        # Run continuous monitoring
        monitor_emails_continuously()
    else:
        # Legacy mode: single run for testing
        from datetime import timedelta
        
        print("=" * 80)
        print("Gmail Email Fetcher & Labeler (Single Run Mode)")
        print("=" * 80)
        print("TIP: Run with 'python get_emails.py monitor' for continuous monitoring")
        print("=" * 80)
        
        # Fetch emails from the last 1 minute
        last_check = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        # Step 1: Fetch emails
        emails = get_emails(USER_ID, APP_PASSWORD, last_check=last_check)
        
        # Print results
        for em in emails:
            print("-" * 80)
            print(f"From: {em['from_address']}")
            print(f"Subject: {em['subject']}")
            print(f"Date: {em['timestamp']}")
            print(f"Message ID: {em['message_id']}")
            print(f"UID: {em.get('uid', 'N/A')}")
            print(f"Body:\n{em['body'][:500]}")
            print()
        
        # Step 2: Get label from API and apply
        if emails:
            print("\n" + "=" * 80)
            print("Getting label from API...")
            print("=" * 80)
            
            label = get_label_from_api(emails)
            
            if label:
                print(f"\n📌 Label received: {label}")
                
                # Extract UIDs from fetched emails
                uids = [em['uid'] for em in emails if em.get('uid')]
                
                if uids:
                    # Apply the label
                    success = apply_label_to_emails(
                        USER_ID, 
                        APP_PASSWORD, 
                        uids, 
                        label
                    )
                    
                    if success:
                        print("\n" + "=" * 80)
                        print("✅ LABELING COMPLETE")
                        print("=" * 80)
                        print(f"Applied label '{label}' to {len(uids)} email(s)")
                        print("\nNote: Label colors are set via Code.gs on add-on installation")
                        print(f"Color for '{label}': {GMAIL_COLORS.get(label, 'not defined')}")
                        print("=" * 80)
                else:
                    print("No UIDs available for labeling.")
            else:
                print("\n⚠️  No label received from API")
        else:
            print("\nNo emails found to label.")
