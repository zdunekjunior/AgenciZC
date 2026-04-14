from __future__ import annotations

import base64
import logging
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any

from fastapi import HTTPException
from googleapiclient.errors import HttpError

from app.config import Settings
from app.integrations.gmail.client import GmailApiClient, GmailAuthConfig
from app.integrations.gmail.mappers import gmail_message_to_email_input, thread_to_context
from app.schemas.email import EmailInput

log = logging.getLogger(__name__)


class GmailNotConfiguredError(RuntimeError):
    pass


class GmailApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GmailService:
    def __init__(self, *, client: GmailApiClient) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "GmailService":
        def _req(val: str | None, name: str) -> str:
            v = (val or "").strip()
            if not v:
                raise GmailNotConfiguredError(f"Missing {name} in environment")
            return v

        auth = GmailAuthConfig(
            client_id=_req(settings.google_client_id, "GOOGLE_CLIENT_ID"),
            client_secret=_req(settings.google_client_secret, "GOOGLE_CLIENT_SECRET"),
            refresh_token=_req(settings.google_refresh_token, "GOOGLE_REFRESH_TOKEN"),
            redirect_uri=(settings.google_redirect_uri or "").strip() or None,
            access_token=(settings.google_access_token or "").strip() or None,
            user_email=(settings.gmail_user_email or "me").strip(),
        )
        return cls(client=GmailApiClient(auth=auth))

    def fetch_message(self, *, message_id: str) -> dict[str, Any]:
        try:
            return self._client.get_message(user_id=self._client.user_id, message_id=message_id)
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 404:
                raise GmailApiError("Gmail message not found", status_code=404) from exc
            log.exception("Gmail get_message failed")
            raise GmailApiError("Gmail API error while fetching message", status_code=status) from exc

    def fetch_thread(self, *, thread_id: str) -> dict[str, Any]:
        try:
            return self._client.get_thread(user_id=self._client.user_id, thread_id=thread_id)
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 404:
                raise GmailApiError("Gmail thread not found", status_code=404) from exc
            log.exception("Gmail get_thread failed")
            raise GmailApiError("Gmail API error while fetching thread", status_code=status) from exc

    def list_recent_messages(self, *, limit: int = 10) -> list[dict[str, Any]]:
        """
        Returns a list of message metadata dicts.
        """

        try:
            listing = self._client.list_messages(user_id=self._client.user_id, max_results=limit)
            msgs = listing.get("messages") or []
            if not isinstance(msgs, list):
                return []
            out: list[dict[str, Any]] = []
            for m in msgs:
                mid = m.get("id")
                if not mid:
                    continue
                meta = self._client.get_message_metadata(user_id=self._client.user_id, message_id=mid)
                out.append(meta)
            return out
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            log.exception("Gmail list_messages failed")
            raise GmailApiError("Gmail API error while listing messages", status_code=status) from exc

    def ensure_label(self, *, name: str) -> str:
        """
        Ensure a user label exists and return its id.
        """

        try:
            listing = self._client.list_labels(user_id=self._client.user_id)
            labels = listing.get("labels") or []
            if isinstance(labels, list):
                for lb in labels:
                    if (lb.get("name") or "") == name and lb.get("id"):
                        return str(lb["id"])
            created = self._client.create_label(user_id=self._client.user_id, name=name)
            label_id = created.get("id")
            if not label_id:
                raise GmailApiError("Gmail label creation returned no id")
            return str(label_id)
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            log.exception("Gmail ensure_label failed")
            raise GmailApiError("Gmail API error while ensuring label", status_code=status) from exc

    def apply_labels(self, *, message_id: str, label_names: list[str]) -> list[str]:
        """
        Applies labels (create if needed). Returns applied label names.
        """

        if not label_names:
            return []
        try:
            ids: list[str] = [self.ensure_label(name=n) for n in label_names]
            self._client.modify_message_labels(
                user_id=self._client.user_id,
                message_id=message_id,
                add_label_ids=ids,
            )
            return label_names
        except GmailApiError:
            raise
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            log.exception("Gmail apply_labels failed")
            raise GmailApiError("Gmail API error while applying labels", status_code=status) from exc

    def fetch_email_input(self, *, message_id: str) -> EmailInput:
        message = self.fetch_message(message_id=message_id)
        thread_id = message.get("threadId")
        ctx: list[str] = []
        if thread_id:
            try:
                thread = self.fetch_thread(thread_id=thread_id)
                ctx = thread_to_context(thread, limit=5)
            except Exception:  # noqa: BLE001
                log.exception("Failed to fetch thread context; continuing without it")
                ctx = []
        return gmail_message_to_email_input(message, ctx)

    def create_reply_draft(self, *, original_message: dict[str, Any], draft_reply: str) -> str:
        """
        Creates a Gmail draft (RFC822 raw, base64url).
        Returns draft_id.
        """

        if not draft_reply.strip():
            raise HTTPException(status_code=400, detail="draft_reply is empty; draft not created")

        headers = {h["name"].lower(): h["value"] for h in (original_message.get("payload", {}).get("headers", []) or []) if h.get("name") and h.get("value")}
        subject = headers.get("subject", "").strip()
        from_raw = headers.get("from", "")
        to_raw = headers.get("to", "")
        msg_id = headers.get("message-id", "")
        refs = headers.get("references", "")

        _, from_email = parseaddr(from_raw)
        _, to_email = parseaddr(to_raw)

        reply = EmailMessage()
        reply["To"] = from_email or ""
        reply["From"] = to_email or ""
        reply["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}" if subject else "Re:"
        if msg_id:
            reply["In-Reply-To"] = msg_id
        if refs or msg_id:
            reply["References"] = (refs + " " + msg_id).strip()
        reply.set_content(draft_reply)

        raw_bytes = reply.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")

        created = self._client.create_draft(
            user_id=self._client.user_id,
            raw_rfc822_base64url=raw_b64,
            thread_id=original_message.get("threadId"),
        )
        draft_id = created.get("id")
        if not draft_id:
            raise HTTPException(status_code=502, detail="Gmail draft creation returned no draft id")
        return draft_id

