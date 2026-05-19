"""
IMAP Email Fetcher Service
Fetches emails from IMAP servers for multiple users and sends them to the agent for processing
"""
import imaplib
import email
import re
import requests
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import threading
import logging

from .imap_database import IMAPDatabaseManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("imap_fetcher")


class IMAPFetcherService:
    """
    Service for fetching emails from IMAP servers for multiple users.
    Integrates with agent endpoint for email processing.
    """
    
    def __init__(
        self, 
        db_manager: Optional[IMAPDatabaseManager] = None,
        agent_url: str = "http://localhost:5051",
        enable_label_classification: bool = True
    ):
        """
        Initialize IMAP fetcher service.
        
        Parameters
        ----------
        db_manager : Optional[IMAPDatabaseManager]
            Database manager for user credentials. If None, creates default.
        agent_url : str
            Agent server URL for processing emails
        enable_label_classification : bool
            Enable external label API calls. Set to False to skip classification when agent is unavailable.
        """
        self.db = db_manager or IMAPDatabaseManager()
        self.agent_url = agent_url
        self.enable_label_classification = enable_label_classification
        self._running = False
        self._thread = None
    
    @staticmethod
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
    
    @staticmethod
    def _extract_email_address(from_field: str) -> str:
        """Pull the bare address out of 'Display Name <addr@host>'."""
        match = re.search(r"<(.+?)>", from_field)
        return match.group(1).strip() if match else from_field.strip()
    
    @staticmethod
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
    
    @staticmethod
    def _parse_timestamp(msg) -> datetime:
        """Return a datetime object from the email Date header (UTC)."""
        date_str = msg.get("Date", "")
        try:
            dt = parsedate_to_datetime(date_str)
            # Normalize to UTC
            return dt.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
    
    def fetch_emails_for_user(
        self,
        user_id: str,
        email_address: str,
        app_password: str,
        last_check: Optional[datetime] = None,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from IMAP server for a single user.
        
        Parameters
        ----------
        user_id : str
            User identifier
        email_address : str
            Email address for IMAP login
        app_password : str
            IMAP app password
        last_check : Optional[datetime]
            Fetch only emails received after this datetime (UTC).
            If None, fetches emails from the last day.
        imap_host : str
            IMAP server hostname
        imap_port : int
            IMAP SSL port
        
        Returns
        -------
        List[Dict[str, Any]]
            List of email dictionaries
        """
        # If no last_check provided, fetch emails from the last day
        if last_check is None:
            last_check = datetime.now(timezone.utc) - timedelta(days=1)
        elif last_check.tzinfo is None:
            # Ensure last_check is timezone-aware (UTC)
            last_check = last_check.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC if in different timezone
            last_check = last_check.astimezone(timezone.utc)
        
        logger.info(f"📧 Fetching emails for {user_id} since {last_check.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # IMAP SINCE criterion needs "DD-Mon-YYYY" format
        since_str = last_check.strftime("%d-%b-%Y")
        
        # Connect to IMAP server
        try:
            imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        except Exception as e:
            logger.error(f"❌ Failed to connect to IMAP server {imap_host}:{imap_port} for {user_id}: {e}")
            return []
        
        try:
            imap.login(email_address.strip(), app_password.strip())
            imap.select("INBOX", readonly=True)
            
            # Search for emails since the specified date
            status, data = imap.search(None, f"SINCE {since_str}")
            if status != "OK" or not data[0]:
                logger.info(f"📭 No new messages found for {user_id}")
                return []
            
            mail_ids = data[0].split()
            emails = []
            
            for num in mail_ids:
                # Fetch both RFC822 and UID for labeling later
                status, msg_data = imap.fetch(num, "(RFC822 UID)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                
                # Extract UID and message from response
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
                msg_dt = self._parse_timestamp(msg)
                
                # Post-filter: skip messages older than last_check
                # (IMAP SINCE has day-level granularity only)
                if msg_dt < last_check:
                    continue
                
                # Extract headers
                subject = self._decode_header_value(msg.get("Subject", "(no subject)"))
                from_raw = self._decode_header_value(msg.get("From", ""))
                from_address = self._extract_email_address(from_raw)
                
                # Extract message ID
                message_id = (msg.get("Message-ID") or "").strip().strip("<>")
                
                # Extract body
                body = self._get_plain_body(msg)
                
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
            
            logger.info(f"✅ Found {len(emails)} new email(s) for {user_id}")
            return emails
            
        except Exception as e:
            logger.error(f"❌ Error fetching emails for {user_id}: {e}")
            return []
        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass
    
    def get_label_from_api(
        self,
        user_id: str,
        emails: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Send emails to label endpoint for AI classification.
        
        Parameters
        ----------
        user_id : str
            User identifier
        emails : List[Dict[str, Any]]
            List of email dictionaries
        
        Returns
        -------
        Optional[str]
            Label name if successful, None otherwise
        """
        if not emails:
            return None
        
        # Skip if label classification is disabled
        if not self.enable_label_classification:
            logger.debug(f"ℹ️  Label classification disabled for user {user_id}")
            return None
        
        # Use first email for thread identification
        first_email = emails[0]
        thread_id = first_email.get('message_id', 'unknown_thread')
        
        # Convert timestamps to ISO format
        messages = []
        for em in emails:
            try:
                dt = datetime.strptime(em['timestamp'], "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
                iso_timestamp = dt.isoformat()
            except Exception:
                iso_timestamp = em['timestamp']
            
            messages.append({
                "message_id": em['message_id'],
                "from_address": em['from_address'],
                "to": [user_id],
                "subject": em['subject'],
                "timestamp": iso_timestamp,
                "body": em['body']
            })
        
        payload = {
            "user_id": user_id,
            "thread_id": thread_id,
            "messages": messages
        }
        
        # Call label endpoint
        endpoint = f"{self.agent_url}/api/label-email"
        
        try:
            logger.info(f"🔍 Classifying {len(messages)} email(s)...")
            response = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                label = data.get('label')
                method = data.get('classification_method', 'unknown')
                logger.info(f"✅ Label: {label} (method: {method})")
                return label
            else:
                logger.warning(f"⚠️  Label API error: HTTP {response.status_code}")
                return None
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️  Label API request failed: {e}")
            return None
    
    def apply_label_via_imap(
        self,
        user_id: str,
        email_address: str,
        app_password: str,
        email_uids: List[str],
        label_name: str,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993
    ) -> bool:
        """
        Apply a Gmail label to specific emails using IMAP X-GM-LABELS.
        
        Parameters
        ----------
        user_id : str
            User identifier (for logging)
        email_address : str
            Email address for IMAP login
        app_password : str
            IMAP app password
        email_uids : List[str]
            List of IMAP UIDs to label
        label_name : str
            Label name to apply
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
            return False
        
        imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        try:
            imap.login(email_address.strip(), app_password.strip())
            imap.select("INBOX", readonly=False)
            
            # Apply label using Gmail's X-GM-LABELS extension
            for uid in email_uids:
                try:
                    status, data = imap.uid('STORE', uid, '+X-GM-LABELS', f'"{label_name}"')
                    if status == "OK":
                        logger.debug(f"✓ Applied label '{label_name}' to UID {uid}")
                    else:
                        logger.warning(f"✗ Failed to apply label to UID {uid}")
                except Exception as e:
                    logger.warning(f"✗ Error labeling UID {uid}: {e}")
            
            logger.info(f"🏷️  Applied label '{label_name}' to {len(email_uids)} email(s)")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error applying labels: {e}")
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
    
    def send_emails_to_agent(
        self,
        user_id: str,
        emails: List[Dict[str, Any]],
        endpoint: str = "/api/log-email"
    ) -> Tuple[bool, Optional[str]]:
        """
        Send fetched emails to agent for storage and processing.
        
        Parameters
        ----------
        user_id : str
            User identifier
        emails : List[Dict[str, Any]]
            List of email dictionaries from fetch_emails_for_user()
        endpoint : str
            Agent endpoint to send emails to (default: /api/log-email)
        
        Returns
        -------
        Tuple[bool, Optional[str]]
            (success, error_message)
        """
        if not emails:
            return True, None
        
        url = f"{self.agent_url}{endpoint}"
        
        # Group emails by thread (first email's message_id)
        # For simplicity, send each email as a separate thread
        for email_data in emails:
            try:
                # Convert timestamp to ISO format with timezone
                dt = datetime.strptime(email_data['timestamp'], "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
                iso_timestamp = dt.isoformat()
            except Exception:
                iso_timestamp = email_data['timestamp']
            
            payload = {
                "user_id": user_id,
                "thread_id": email_data['message_id'],
                "messages": [{
                    "message_id": email_data['message_id'],
                    "from_address": email_data['from_address'],
                    "to": [user_id],  # Assume email was sent to user
                    "subject": email_data['subject'],
                    "timestamp": iso_timestamp,
                    "body": email_data['body']
                }]
            }
            
            try:
                logger.debug(f"📤 Sending email {email_data['message_id']} to agent...")
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.debug(f"✅ Email {email_data['message_id']} sent to agent successfully")
                else:
                    logger.warning(f"⚠️  Agent returned HTTP {response.status_code} for {email_data['message_id']}")
            
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Failed to send email {email_data['message_id']} to agent: {e}")
                return False, str(e)
        
        logger.info(f"✅ Sent {len(emails)} email(s) to agent for {user_id}")
        return True, None
    
    def fetch_and_process_for_user(self, user_id: str) -> Tuple[int, Optional[str]]:
        """
        Fetch and process emails for a single user with full labeling workflow:
        1. Fetch new emails from IMAP
        2. Classify each email using /api/label-email
        3. Apply returned label via IMAP
        4. Store email data via /api/log-email
        
        Parameters
        ----------
        user_id : str
            User identifier
        
        Returns
        -------
        Tuple[int, Optional[str]]
            (number_of_emails_processed, error_message)
        """
        # Get user from database
        user = self.db.get_user(user_id)
        if not user:
            return 0, f"User {user_id} not found in database"
        
        if not user['enabled']:
            return 0, f"IMAP disabled for user {user_id}"
        
        # Determine last check time
        last_check = None
        if user['last_check']:
            try:
                last_check = datetime.fromisoformat(user['last_check'])
            except:
                pass
        
        # Step 1: Fetch emails
        emails = self.fetch_emails_for_user(
            user_id=user_id,
            email_address=user['email'],
            app_password=user['app_password'],
            last_check=last_check,
            imap_host=user['imap_host'],
            imap_port=user['imap_port']
        )
        
        if not emails:
            # Update last check time even if no emails found
            self.db.update_last_check(user_id, datetime.now(timezone.utc))
            logger.info(f"📭 No new emails for {user_id}")
            return 0, None
        
        logger.info(f"📬 Processing {len(emails)} email(s) for {user_id}...")
        
        processed_count = 0
        labeled_count = 0
        stored_count = 0
        
        # Step 2-4: For each email, classify and apply label
        for email_data in emails:
            try:
                logger.info(f"📧 Processing: {email_data['subject'][:50]}")
                
                # Step 2: Get label from AI classification
                label = self.get_label_from_api(user_id, [email_data])
                
                if label:
                    # Step 3: Apply label via IMAP
                    uid = email_data.get('uid')
                    if uid:
                        success = self.apply_label_via_imap(
                            user_id=user_id,
                            email_address=user['email'],
                            app_password=user['app_password'],
                            email_uids=[uid],
                            label_name=label,
                            imap_host=user['imap_host'],
                            imap_port=user['imap_port']
                        )
                        if success:
                            labeled_count += 1
                    else:
                        logger.warning(f"⚠️  No UID available for labeling")
                else:
                    logger.warning(f"⚠️  No label returned from API")
                
                # Step 4: Store email data via /api/log-email
                try:
                    log_success, _ = self.send_emails_to_agent(
                        user_id, 
                        [email_data], 
                        endpoint="/api/log-email"
                    )
                    if log_success:
                        stored_count += 1
                except Exception as e:
                    logger.warning(f"⚠️  Failed to store email: {e}")
                
                processed_count += 1
            
            except Exception as e:
                logger.error(f"❌ Error processing email: {e}")
        
        # Update last check time
        self.db.update_last_check(user_id, datetime.now(timezone.utc))
        
        logger.info(f"✅ Completed: {processed_count} processed, {labeled_count} labeled, {stored_count} stored")
        
        return processed_count, None
    
    def fetch_and_process_all_users(self) -> Dict[str, Any]:
        """
        Fetch and process emails for all enabled users.
        
        Returns
        -------
        Dict[str, Any]
            Summary of processing results
        """
        users = self.db.get_all_enabled_users()
        
        if not users:
            logger.info("📭 No enabled users found in IMAP database")
            return {"total_users": 0, "results": []}
        
        logger.info(f"📧 Starting IMAP fetch for {len(users)} user(s)...")
        
        results = []
        total_emails = 0
        
        for user in users:
            user_id = user['user_id']
            logger.info(f"🔄 Processing user: {user_id}")
            
            count, error = self.fetch_and_process_for_user(user_id)
            
            results.append({
                "user_id": user_id,
                "emails_fetched": count,
                "success": error is None,
                "error": error
            })
            
            total_emails += count
        
        logger.info(f"✅ IMAP fetch completed: {total_emails} total email(s) from {len(users)} user(s)")
        
        return {
            "total_users": len(users),
            "total_emails": total_emails,
            "results": results
        }
    
    def start_background_monitoring(self, interval_seconds: int = 60):
        """
        Start background monitoring thread that fetches emails periodically.
        
        Parameters
        ----------
        interval_seconds : int
            Interval between fetch runs (default: 60 seconds)
        """
        if self._running:
            logger.warning("⚠️  Background monitoring already running")
            return
        
        self._running = True
        
        def monitor_loop():
            logger.info(f"🚀 Started IMAP background monitoring (interval: {interval_seconds}s)")
            while self._running:
                try:
                    self.fetch_and_process_all_users()
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                
                # Wait for next interval
                for _ in range(interval_seconds):
                    if not self._running:
                        break
                    time.sleep(1)
            
            logger.info("🛑 Stopped IMAP background monitoring")
        
        self._thread = threading.Thread(target=monitor_loop, daemon=True)
        self._thread.start()
    
    def stop_background_monitoring(self):
        """Stop background monitoring thread."""
        if not self._running:
            return
        
        logger.info("🛑 Stopping IMAP background monitoring...")
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
