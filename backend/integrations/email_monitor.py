"""Email monitoring integration — IMAP/SMTP client.

Supports reading unread emails, searching, reading full messages,
sending emails, and monitoring inbox for new messages.

Configuration is stored in ~/.may/email.json (encrypted at rest in future).

Usage:
    email = EmailClient()
    unread = await email.get_unread(max_items=10)
    await email.send_email(to="user@example.com", subject="Hello", body="Hi there~")
"""

from __future__ import annotations

import asyncio
import email as _email
import email.header
import email.utils
import json
import logging
import os
import imaplib
import smtplib
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

logger = logging.getLogger("may.integrations.email")

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".may", "email.json")


@dataclass
class EmailMessage:
    """A single email message."""
    uid: str = ""
    subject: str = ""
    from_addr: str = ""
    to_addrs: str = ""
    date: str = ""
    body: str = ""
    snippet: str = ""          # First 200 chars of body
    has_attachments: bool = False
    is_read: bool = False
    folder: str = "INBOX"

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "subject": self.subject,
            "from": self.from_addr,
            "to": self.to_addrs,
            "date": self.date,
            "body": self.body[:5000],  # Cap body at 5000 chars
            "snippet": self.snippet,
            "has_attachments": self.has_attachments,
            "is_read": self.is_read,
            "folder": self.folder,
        }

    def to_briefing_text(self) -> str:
        """Format as brief text for morning briefing."""
        return f"{self.subject} — from {self.from_addr} ({self.date})"


@dataclass
class EmailConfig:
    """Email server configuration."""
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    email_address: str = ""
    password: str = ""          # App password for Gmail/Outlook
    use_ssl: bool = True
    enabled: bool = False

    def save(self):
        """Save config to disk."""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({
                "imap_host": self.imap_host,
                "imap_port": self.imap_port,
                "smtp_host": self.smtp_host,
                "smtp_port": self.smtp_port,
                "email_address": self.email_address,
                "password": self.password,
                "use_ssl": self.use_ssl,
                "enabled": self.enabled,
            }, f, indent=2)

    @classmethod
    def load(cls) -> "EmailConfig":
        """Load config from disk."""
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
                return cls(
                    imap_host=data.get("imap_host", ""),
                    imap_port=data.get("imap_port", 993),
                    smtp_host=data.get("smtp_host", ""),
                    smtp_port=data.get("smtp_port", 587),
                    email_address=data.get("email_address", ""),
                    password=data.get("password", ""),
                    use_ssl=data.get("use_ssl", True),
                    enabled=data.get("enabled", False),
                )
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()


# Common email provider presets
PROVIDER_PRESETS = {
    "gmail": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_ssl": True,
        "help": "Use an App Password (Google Account → Security → 2FA → App Passwords)",
    },
    "outlook": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "use_ssl": True,
        "help": "Use your Microsoft account password or App Password",
    },
    "yahoo": {
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "use_ssl": True,
        "help": "Use an App Password (Yahoo Account → Security → App Passwords)",
    },
}


def _decode_header(header_val: str) -> str:
    """Decode an email header that may be encoded."""
    if not header_val:
        return ""
    try:
        decoded_parts = email.header.decode_header(header_val)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)
    except Exception:
        return header_val


def _extract_body(msg: _email.message.Message) -> str:
    """Extract plain text body from an email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Basic HTML → text (strip tags)
                    import re
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body.strip()


def _has_attachments(msg: _email.message.Message) -> bool:
    """Check if an email has attachments."""
    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                return True
    return False


class EmailClient:
    """IMAP/SMTP email client with monitoring support."""

    def __init__(self, config: EmailConfig | None = None):
        self._config = config or EmailConfig.load()

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(
            self._config.imap_host and self._config.email_address and self._config.password
        )

    def configure(self, provider: str | None = None, **kwargs):
        """Configure email connection.

        Args:
            provider: Preset name ('gmail', 'outlook', 'yahoo') or None for custom
            **kwargs: Override specific settings (imap_host, smtp_host, email_address, password, etc.)
        """
        if provider and provider in PROVIDER_PRESETS:
            preset = PROVIDER_PRESETS[provider]
            for k, v in preset.items():
                if k != "help":
                    setattr(self._config, k, v)

        for k, v in kwargs.items():
            if hasattr(self._config, k):
                setattr(self._config, k, v)

        self._config.enabled = True
        self._config.save()
        logger.info("Email configured: %s@%s", self._config.email_address, self._config.imap_host)

    def get_status(self) -> dict:
        """Get email integration status."""
        return {
            "enabled": self.enabled,
            "email_address": self._config.email_address if self.enabled else "",
            "imap_host": self._config.imap_host if self.enabled else "",
            "has_password": bool(self._config.password),
            "providers": list(PROVIDER_PRESETS.keys()),
        }

    async def get_unread(self, max_items: int = 10, folder: str = "INBOX") -> list[EmailMessage]:
        """Get unread emails from the inbox.

        Args:
            max_items: Maximum number of emails to return
            folder: IMAP folder name

        Returns:
            List of EmailMessage objects
        """
        if not self.enabled:
            return []

        loop = asyncio.get_running_loop()

        def _fetch():
            messages = []
            try:
                conn = self._get_imap_sync()
                conn.select(folder)

                # Search for unseen messages
                status, data = conn.search(None, "UNSEEN")
                if status != "OK":
                    return []

                msg_ids = data[0].split()
                # Get the last N (most recent) messages
                msg_ids = msg_ids[-max_items:] if len(msg_ids) > max_items else msg_ids

                for mid in msg_ids:
                    status, msg_data = conn.fetch(mid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw = msg_data[0][1]
                    msg = _email.message_from_bytes(raw)

                    body = _extract_body(msg)
                    messages.append(EmailMessage(
                        uid=mid.decode(),
                        subject=_decode_header(msg.get("Subject", "")),
                        from_addr=_decode_header(msg.get("From", "")),
                        to_addrs=_decode_header(msg.get("To", "")),
                        date=msg.get("Date", ""),
                        body=body,
                        snippet=body[:200] if body else "",
                        has_attachments=_has_attachments(msg),
                        is_read=False,
                        folder=folder,
                    ))
            except Exception as e:
                logger.error("Failed to fetch unread emails: %s", e)
            return messages

        return await loop.run_in_executor(None, _fetch)

    def _get_imap_sync(self) -> imaplib.IMAP4_SSL:
        """Synchronous IMAP connection (for use in executors)."""
        if self._config.use_ssl:
            conn = imaplib.IMAP4_SSL(self._config.imap_host, self._config.imap_port)
        else:
            conn = imaplib.IMAP4(self._config.imap_host, self._config.imap_port)
        conn.login(self._config.email_address, self._config.password)
        return conn

    async def get_unread_count(self, folder: str = "INBOX") -> int:
        """Get the count of unread emails."""
        if not self.enabled:
            return 0

        loop = asyncio.get_running_loop()

        def _count():
            try:
                conn = self._get_imap_sync()
                conn.select(folder)
                status, data = conn.search(None, "UNSEEN")
                if status == "OK":
                    return len(data[0].split()) if data[0].strip() else 0
            except Exception as e:
                logger.error("Failed to count unread emails: %s", e)
            return 0

        return await loop.run_in_executor(None, _count)

    async def search_emails(self, query: str, folder: str = "INBOX",
                            max_items: int = 10) -> list[EmailMessage]:
        """Search emails by subject or body text.

        Args:
            query: Search text
            folder: IMAP folder
            max_items: Max results

        Returns:
            List of matching EmailMessage objects
        """
        if not self.enabled:
            return []

        loop = asyncio.get_running_loop()

        def _search():
            messages = []
            try:
                conn = self._get_imap_sync()
                conn.select(folder)

                # IMAP SUBJECT search
                status, data = conn.search(None, f'SUBJECT "{query}"')
                if status != "OK":
                    return []

                msg_ids = data[0].split()
                msg_ids = msg_ids[-max_items:] if len(msg_ids) > max_items else msg_ids

                for mid in msg_ids:
                    status, msg_data = conn.fetch(mid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw = msg_data[0][1]
                    msg = _email.message_from_bytes(raw)
                    body = _extract_body(msg)

                    messages.append(EmailMessage(
                        uid=mid.decode(),
                        subject=_decode_header(msg.get("Subject", "")),
                        from_addr=_decode_header(msg.get("From", "")),
                        to_addrs=_decode_header(msg.get("To", "")),
                        date=msg.get("Date", ""),
                        body=body,
                        snippet=body[:200] if body else "",
                        has_attachments=_has_attachments(msg),
                        folder=folder,
                    ))
            except Exception as e:
                logger.error("Failed to search emails: %s", e)
            return messages

        return await loop.run_in_executor(None, _search)

    async def read_email(self, uid: str, folder: str = "INBOX") -> EmailMessage | None:
        """Read a specific email by UID.

        Args:
            uid: Email UID
            folder: IMAP folder

        Returns:
            EmailMessage with full body, or None if not found
        """
        if not self.enabled:
            return None

        loop = asyncio.get_running_loop()

        def _read():
            try:
                conn = self._get_imap_sync()
                conn.select(folder)

                status, msg_data = conn.fetch(uid.encode(), "(RFC822)")
                if status != "OK" or not msg_data[0]:
                    return None

                raw = msg_data[0][1]
                msg = _email.message_from_bytes(raw)
                body = _extract_body(msg)

                return EmailMessage(
                    uid=uid,
                    subject=_decode_header(msg.get("Subject", "")),
                    from_addr=_decode_header(msg.get("From", "")),
                    to_addrs=_decode_header(msg.get("To", "")),
                    date=msg.get("Date", ""),
                    body=body,
                    snippet=body[:200] if body else "",
                    has_attachments=_has_attachments(msg),
                    folder=folder,
                )
            except Exception as e:
                logger.error("Failed to read email %s: %s", uid, e)
                return None

        return await loop.run_in_executor(None, _read)

    async def send_email(self, to: str, subject: str, body: str,
                         cc: str = "", bcc: str = "") -> bool:
        """Send an email via SMTP.

        Args:
            to: Recipient email address(es), comma-separated
            subject: Email subject
            body: Email body (plain text)
            cc: CC recipients (comma-separated, optional)
            bcc: BCC recipients (comma-separated, optional)

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False

        loop = asyncio.get_running_loop()

        def _send():
            try:
                msg = MIMEMultipart()
                msg["From"] = self._config.email_address
                msg["To"] = to
                msg["Subject"] = subject
                if cc:
                    msg["Cc"] = cc

                msg.attach(MIMEText(body, "plain"))

                # Build recipient list
                recipients = [addr.strip() for addr in to.split(",")]
                if cc:
                    recipients.extend([addr.strip() for addr in cc.split(",")])
                if bcc:
                    recipients.extend([addr.strip() for addr in bcc.split(",")])

                if self._config.use_ssl:
                    server = smtplib.SMTP_SSL(self._config.smtp_host, self._config.smtp_port)
                else:
                    server = smtplib.SMTP(self._config.smtp_host, self._config.smtp_port)
                    server.starttls()

                server.login(self._config.email_address, self._config.password)
                server.sendmail(self._config.email_address, recipients, msg.as_string())
                server.quit()

                logger.info("Email sent to %s: %s", to, subject)
                return True
            except Exception as e:
                logger.error("Failed to send email: %s", e)
                return False

        return await loop.run_in_executor(None, _send)

    async def get_folders(self) -> list[str]:
        """List available IMAP folders."""
        if not self.enabled:
            return []

        loop = asyncio.get_running_loop()

        def _list():
            try:
                conn = self._get_imap_sync()
                status, folders = conn.list()
                if status == "OK":
                    result = []
                    for f in folders:
                        if isinstance(f, bytes):
                            name = f.decode().split(' "/" ')[-1].strip('"')
                            result.append(name)
                    return result
            except Exception as e:
                logger.error("Failed to list folders: %s", e)
            return []

        return await loop.run_in_executor(None, _list)

    async def get_recent(self, max_items: int = 5, folder: str = "INBOX") -> list[EmailMessage]:
        """Get the most recent emails (read or unread)."""
        if not self.enabled:
            return []

        loop = asyncio.get_running_loop()

        def _fetch():
            messages = []
            try:
                conn = self._get_imap_sync()
                conn.select(folder)

                status, data = conn.search(None, "ALL")
                if status != "OK":
                    return []

                msg_ids = data[0].split()
                # Get the last N (most recent)
                msg_ids = msg_ids[-max_items:] if len(msg_ids) > max_items else msg_ids

                for mid in msg_ids:
                    status, msg_data = conn.fetch(mid, "(FLAGS RFC822.HEADER)")
                    if status != "OK" or not msg_data[0]:
                        continue

                    # Check if read
                    flags = msg_data[0][0].decode() if msg_data[0][0] else ""
                    is_read = "\\Seen" in flags

                    # Get headers only (faster than full RFC822)
                    header_data = msg_data[0][1] if len(msg_data[0]) > 1 else None
                    if header_data:
                        msg = _email.message_from_bytes(header_data)
                        messages.append(EmailMessage(
                            uid=mid.decode(),
                            subject=_decode_header(msg.get("Subject", "")),
                            from_addr=_decode_header(msg.get("From", "")),
                            to_addrs=_decode_header(msg.get("To", "")),
                            date=msg.get("Date", ""),
                            is_read=is_read,
                            folder=folder,
                        ))
            except Exception as e:
                logger.error("Failed to fetch recent emails: %s", e)
            return messages

        return await loop.run_in_executor(None, _fetch)
