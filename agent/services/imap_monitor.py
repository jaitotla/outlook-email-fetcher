"""
IMAP Email Monitor Service
Polls a mailbox for new emails in a time window [last_check, now] and returns
them in the format expected by the label pipeline (LogEmailRequest schema).
"""
import imaplib
import email
import re
import logging
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

# Import SettingsManager to load per-user IMAP credentials
try:
    from .settings_manager import SettingsManager
except ImportError:
    from settings_manager import SettingsManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output types (mirror the LogEmailRequest / EmailMessage schemas in main.py
# so the caller can pass the result directly to the label endpoint)
# ---------------------------------------------------------------------------

def _decode_str(raw) -> str:
    """Decode an email header value that may be bytes or str."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode(errors="replace")
    return str(raw)


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


def _extract_to_addresses(msg) -> List[str]:
    """Return a list of recipient addresses from the To/CC headers."""
    addrs: List[str] = []
    for header in ("To", "Cc"):
        value = msg.get(header, "")
        if value:
            for part in value.split(","):
                part = part.strip()
                if part:
                    addrs.append(_extract_email_address(part))
    return addrs or [""]


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


def _parse_timestamp(msg) -> str:
    """Return an ISO-8601 UTC timestamp string from the email Date header."""
    date_str = msg.get("Date", "")
    try:
        dt = parsedate_to_datetime(date_str)
        # Normalise to UTC
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Core monitor class
# ---------------------------------------------------------------------------

class IMAPEmailMonitor:
    """
    Monitor an IMAP mailbox for new emails within a time window.

    Usage with direct credentials::

        monitor = IMAPEmailMonitor(
            username="user@gmail.com",
            app_password="xxxx xxxx xxxx xxxx",
            imap_host="imap.gmail.com",   # optional, defaults to Gmail
        )
        result = monitor.fetch_new_emails(last_check=None)

    Usage with SettingsManager (recommended)::

        monitor = IMAPEmailMonitor(
            user_id="user@gmail.com",  # loads credentials from SettingsManager
        )
        result = monitor.fetch_new_emails(last_check=None)

    Settings keys required when using user_id:
    - ``imap_username`` or ``email`` — email address for IMAP login
    - ``imap_app_password`` — IMAP app password (Gmail: 16-char)
    - ``imap_host`` (optional) — defaults to "imap.gmail.com"
    - ``imap_port`` (optional) — defaults to 993

    Each item in the returned list is ready to be POSTed to /api/label-email::

        {
            "user_id": "user@gmail.com",
            "thread_id": "<canonical-thread-or-message-id>",
            "messages": [
                {
                    "message_id": "<msg-id>",
                    "from_address": "sender@example.com",
                    "to": ["recipient@example.com"],
                    "subject": "Hello",
                    "timestamp": "2026-04-30T10:00:00Z",
                    "body": "Plain text body …"
                }
            ]
        }
    """

    def __init__(
        self,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        last_check: Optional[datetime] = None,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Parameters
        ----------
        username:     Email address (IMAP login). If not provided, loads from 
                      SettingsManager using user_id.
        app_password: IMAP app password (Gmail: 16-char app password). If not 
                      provided, loads from SettingsManager using user_id.
        last_check:   Window start. Pass None to use the current time (no
                      prior window → first call fetches nothing; subsequent
                      calls fetch mail since construction time).
        imap_host:    IMAP server hostname (default: "imap.gmail.com").
        imap_port:    IMAP SSL port (default: 993).
        user_id:      User ID for loading credentials from SettingsManager.
                      If provided and username/app_password are None, credentials
                      will be loaded from settings.

        Raises
        ------
        ValueError:   If neither (username + app_password) nor user_id is provided,
                      or if settings cannot be loaded for the user_id.
        """
        # Priority 1: Use provided credentials directly
        if username and app_password:
            self.username: str = username.strip()
            self._app_password: str = app_password.strip()
            logger.info(f"IMAPEmailMonitor initialized with direct credentials for {self.username}")
        
        # Priority 2: Load from SettingsManager using user_id
        elif user_id:
            settings_mgr = SettingsManager(user_id)
            settings = settings_mgr.get_settings(setting_type="general")
            
            if not settings:
                raise ValueError(
                    f"Cannot load settings for user_id '{user_id}'. "
                    "Ensure settings are saved via /api/settings endpoint first."
                )
            
            # Extract credentials from settings
            # Try multiple possible key names for flexibility
            self.username = (
                settings.get("imap_username") or 
                settings.get("email") or 
                settings.get("user_email") or
                user_id  # fallback to user_id itself (often the email)
            ).strip()
            
            self._app_password = settings.get("imap_app_password", "").strip()
            
            if not self._app_password:
                raise ValueError(
                    f"Missing 'imap_app_password' in settings for user '{user_id}'. "
                    "Please configure IMAP credentials in settings."
                )
            
            # Allow settings to override IMAP host/port
            imap_host = settings.get("imap_host", imap_host)
            imap_port = int(settings.get("imap_port", imap_port))
            
            logger.info(
                f"IMAPEmailMonitor initialized from SettingsManager for {self.username} "
                f"(host: {imap_host}, port: {imap_port})"
            )
        
        # Priority 3: Error if no credentials available
        else:
            raise ValueError(
                "Either (username + app_password) or user_id must be provided. "
                "Use user_id to load credentials from SettingsManager."
            )

        self.imap_host: str = imap_host
        self.imap_port: int = imap_port

        # If no last_check supplied, default to *now* so the first window is empty.
        now_utc = datetime.now(timezone.utc)
        self.last_check: datetime = (
            last_check.astimezone(timezone.utc)
            if last_check is not None
            else now_utc
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_new_emails(
        self, last_check: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails received between *last_check* (or ``self.last_check``)
        and *now*, grouped by thread.

        Parameters
        ----------
        last_check: Override the instance-level last_check for this call only.
                    Pass ``None`` to use the stored value.

        Returns
        -------
        List of dicts, each shaped as a ``LogEmailRequest`` payload (ready for
        the ``/api/label-email`` endpoint).  Updates ``self.last_check`` to
        *now* on success.
        """
        window_start = (
            last_check.astimezone(timezone.utc)
            if last_check is not None
            else self.last_check
        )
        window_end = datetime.now(timezone.utc)

        logger.info(
            "IMAPEmailMonitor: checking %s for mail since %s",
            self.username,
            window_start.isoformat(),
        )

        try:
            raw_messages = self._imap_fetch_since(window_start)
        except Exception as exc:
            logger.error("IMAPEmailMonitor: IMAP error — %s", exc, exc_info=True)
            return []

        # Group messages by thread_id (X-GM-THRID → canonical hex, else Message-ID)
        threads: Dict[str, Dict[str, Any]] = {}

        for raw in raw_messages:
            parsed = self._parse_message(raw)
            if parsed is None:
                continue

            tid = parsed["thread_id"]
            if tid not in threads:
                threads[tid] = {
                    "user_id": self.username,
                    "thread_id": tid,
                    "messages": [],
                }
            threads[tid]["messages"].append(parsed["message"])

        # Update the rolling cursor only on success
        self.last_check = window_end

        result = list(threads.values())
        logger.info(
            "IMAPEmailMonitor: found %d new message(s) in %d thread(s)",
            sum(len(t["messages"]) for t in result),
            len(result),
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _imap_fetch_since(self, since_dt: datetime) -> List[bytes]:
        """
        Connect to IMAP, search for messages received on or after *since_dt*,
        and return their raw RFC-822 bytes.

        IMAP SINCE granularity is per-day; we post-filter by the exact
        datetime below in ``_parse_message``.
        """
        # IMAP SINCE criterion needs "DD-Mon-YYYY" in English
        since_str = since_dt.strftime("%d-%b-%Y")

        raw_messages: List[bytes] = []
        imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        try:
            imap.login(self.username, self._app_password)
            imap.select("INBOX", readonly=True)

            status, data = imap.search(None, f"SINCE {since_str}")
            if status != "OK" or not data[0]:
                return []

            for num in data[0].split():
                status, msg_data = imap.fetch(num, "(RFC822)")
                if status == "OK" and msg_data and msg_data[0]:
                    raw_messages.append(msg_data[0][1])
        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

        return raw_messages

    def _parse_message(
        self, raw_bytes: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single RFC-822 message and return a dict with keys
        ``thread_id`` and ``message`` (shaped as ``EmailMessage``), or
        ``None`` if the message is older than ``self.last_check``.
        """
        try:
            msg = email.message_from_bytes(raw_bytes)
        except Exception:
            return None

        # --- timestamp ---------------------------------------------------------
        timestamp_str = _parse_timestamp(msg)
        try:
            msg_dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            msg_dt = datetime.now(timezone.utc)

        # Post-filter: skip messages older than the window start
        if msg_dt < self.last_check:
            return None

        # --- headers -----------------------------------------------------------
        subject = _decode_header_value(msg.get("Subject", "(no subject)"))
        from_raw = _decode_header_value(msg.get("From", ""))
        from_address = _extract_email_address(from_raw)
        to_addresses = _extract_to_addresses(msg)

        # --- message ID --------------------------------------------------------
        message_id: str = (msg.get("Message-ID") or "").strip()
        if message_id.startswith("<") and message_id.endswith(">"):
            message_id = message_id[1:-1]

        # --- thread ID ---------------------------------------------------------
        # Gmail IMAP exposes X-GM-THRID (large decimal) when using the FETCH
        # X-GM-THRID extension; fall back to References, then Message-ID.
        gm_thrid = (msg.get("X-GM-THRID") or "").strip()
        references = (msg.get("References") or "").strip().split()
        in_reply_to = (msg.get("In-Reply-To") or "").strip()

        if gm_thrid and re.fullmatch(r"\d{10,20}", gm_thrid):
            # Convert Gmail's decimal thread ID to lowercase hex (canonical form)
            thread_id = format(int(gm_thrid), "x")
        elif references:
            # Oldest reference is the root of the thread
            thread_id = references[0].strip("<>")
        elif in_reply_to:
            thread_id = in_reply_to.strip("<>")
        else:
            thread_id = message_id or f"unknown-{timestamp_str}"

        # --- body --------------------------------------------------------------
        body = _get_plain_body(msg)

        return {
            "thread_id": thread_id,
            "message": {
                "message_id": message_id,
                "from_address": from_address,
                "to": to_addresses,
                "subject": subject,
                "timestamp": timestamp_str,
                "body": body,
            },
        }
