from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.config import Settings

log = logging.getLogger(__name__)
_mode_log_once: set[str] = set()


@dataclass(frozen=True)
class OpenAIResponse:
    """
    Thin, SDK-stable shape for what the rest of the app needs.

    If OpenAI SDK changes, adjust ONLY this module.
    """

    output_text: str
    raw: dict[str, Any] | None = None


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        mock_mode: bool = False,
    ) -> None:
        self._api_key = (api_key or "").strip() or None
        self._model = model
        self._base_url = (base_url or "").strip() or None
        self._mock_mode = mock_mode

        self._client: OpenAI | None = None
        if self._api_key and not self._mock_mode:
            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)

        self._log_mode_once()

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIResponsesClient":
        api_key = (settings.openai_api_key or "").strip() or None
        forced = settings.agent_mock_mode
        mock_mode = (forced == "on") or (forced == "auto" and not api_key)
        return cls(
            api_key=api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            mock_mode=mock_mode,
        )

    @property
    def is_mock(self) -> bool:
        return self._mock_mode or not self._api_key

    def _log_mode_once(self) -> None:
        key = f"{self.is_mock}:{self._model}:{bool(self._base_url)}"
        if key in _mode_log_once:
            return
        _mode_log_once.add(key)
        if self.is_mock:
            log.warning("OpenAI MODE disabled -> MOCK MODE (missing key or forced). model=%s", self._model)
        else:
            log.info("OpenAI MODE enabled. model=%s", self._model)

    def _mock_stub(self) -> OpenAIResponse:
        stub = {
            "category": "other",
            "priority": "medium",
            "summary": "Mock: wiadomość wymaga przygotowania odpowiedzi.",
            "needs_human_approval": False,
            "recommended_action": "draft_for_review",
            "draft_reply": "Dzień dobry! Dziękuję za wiadomość — wrócę z odpowiedzią po weryfikacji szczegółów. Pozdrawiam.",
            "reasoning_notes": "Tryb mock: wygenerowano bezpieczny draft odpowiedzi.",
            "suggested_tool": "none",
            "confidence": 0.6,
        }
        return OpenAIResponse(output_text=json.dumps(stub, ensure_ascii=False), raw={"mock": True})

    def create_response_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        json_schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> OpenAIResponse:
        """
        Calls OpenAI Responses API and returns the model's output_text.

        The agent layer is responsible for defining the target JSON schema and parsing the result.
        """

        if self.is_mock:
            return self._mock_stub()

        assert self._client is not None  # for type checkers

        try:
            # NOTE: Responses API shape can evolve; keep this call isolated here.
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "AgentResult",
                        "schema": json_schema,
                        "strict": True,
                    }
                },
                temperature=temperature,
            )

            output_text = getattr(response, "output_text", None)
            if not output_text:
                try:
                    output_text = response.output[0].content[0].text  # type: ignore[attr-defined]
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError("Could not extract output_text from OpenAI response") from exc

            raw: dict[str, Any] | None = None
            try:
                raw = response.model_dump()  # type: ignore[attr-defined]
            except Exception:
                raw = None

            return OpenAIResponse(output_text=output_text, raw=raw)
        except Exception as exc:  # noqa: BLE001
            log.exception("OpenAI Responses API call failed; falling back to MOCK stub")
            fallback = self._mock_stub()
            return OpenAIResponse(output_text=fallback.output_text, raw={"fallback": "mock_stub", "error": str(exc)})

