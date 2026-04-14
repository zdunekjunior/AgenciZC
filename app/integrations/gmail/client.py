from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build


@dataclass(frozen=True)
class GmailAuthConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    user_email: str  # "me" is allowed by Gmail API
    redirect_uri: str | None = None
    access_token: str | None = None


class GmailApiClient:
    """
    Thin adapter over Google API client.
    Keep Google SDK usage isolated here so it can be swapped later.
    """

    def __init__(self, *, auth: GmailAuthConfig) -> None:
        self._auth = auth
        self._service: Resource | None = None

    @property
    def user_id(self) -> str:
        return self._auth.user_email

    def _credentials(self) -> Credentials:
        creds = Credentials(
            token=self._auth.access_token,
            refresh_token=self._auth.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._auth.client_id,
            client_secret=self._auth.client_secret,
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        # Ensure we have a valid access token.
        if not creds.valid:
            creds.refresh(Request())
        return creds

    def service(self) -> Resource:
        if self._service is None:
            self._service = build("gmail", "v1", credentials=self._credentials(), cache_discovery=False)
        return self._service

    def get_message(self, *, user_id: str, message_id: str) -> dict[str, Any]:
        return (
            self.service()
            .users()
            .messages()
            .get(userId=user_id, id=message_id, format="full")
            .execute()
        )

    def get_message_metadata(self, *, user_id: str, message_id: str) -> dict[str, Any]:
        return (
            self.service()
            .users()
            .messages()
            .get(
                userId=user_id,
                id=message_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "To", "Date"],
            )
            .execute()
        )

    def list_messages(self, *, user_id: str, max_results: int = 10) -> dict[str, Any]:
        return self.list_messages_with_query(user_id=user_id, max_results=max_results, query=None)

    def list_messages_with_query(self, *, user_id: str, max_results: int = 10, query: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"userId": user_id, "maxResults": max_results}
        if query:
            kwargs["q"] = query
        return self.service().users().messages().list(**kwargs).execute()

    def get_thread(self, *, user_id: str, thread_id: str) -> dict[str, Any]:
        return (
            self.service()
            .users()
            .threads()
            .get(userId=user_id, id=thread_id, format="full")
            .execute()
        )

    def create_draft(self, *, user_id: str, raw_rfc822_base64url: str, thread_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"message": {"raw": raw_rfc822_base64url}}
        if thread_id:
            body["message"]["threadId"] = thread_id
        return self.service().users().drafts().create(userId=user_id, body=body).execute()

    def list_labels(self, *, user_id: str) -> dict[str, Any]:
        return self.service().users().labels().list(userId=user_id).execute()

    def create_label(self, *, user_id: str, name: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
            "type": "user",
        }
        return self.service().users().labels().create(userId=user_id, body=body).execute()

    def modify_message_labels(
        self,
        *,
        user_id: str,
        message_id: str,
        add_label_ids: list[str] | None = None,
        remove_label_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids
        return self.service().users().messages().modify(userId=user_id, id=message_id, body=body).execute()

