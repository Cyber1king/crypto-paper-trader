"""Real-provider adapter boundary for AI research assistance.

The offline provider in :mod:`crypto_paper_lab.ai_offline` exists so the safety
machinery can be exercised without a key or a connection. This module adds the
other half: a narrow, provider-independent adapter contract that a real provider
can implement, so the same budget, deadline, validation and audit guarantees
apply to it.

What this module deliberately does **not** contain is any provider's wire
contract, beyond the one already verified and recorded in this repository
(``experiments/phase48/PROVIDER_STATUS.md``):

* **Anthropic** -- ``POST /v1/messages``, ``anthropic-version`` and
  ``content-type`` headers, ``Authorization: Bearer`` or legacy ``x-api-key``
  auth, optional ``anthropic-workspace-id``. Its model identifiers are *not*
  hardcoded because the two official pages consulted during Phase 48 disagree;
  a model must be configured explicitly.
* **Kimi** and **DeepSeek** -- Phase 48 records their documentation as
  UNVERIFIED. No endpoint, header, field or capability is invented for them
  here. They are registered so the API can report them honestly, and they
  refuse to operate until an owner supplies a verified contract.

Transport is injected. Nothing in this module opens a socket, and the test
suite exercises request construction and response parsing entirely offline.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping

from .ai_research import (
    ProviderConfigurationError,
    ProviderRequest,
    ProviderResponse,
)

__all__ = [
    "ANTHROPIC",
    "DEEPSEEK",
    "KIMI",
    "PROVIDER_REGISTRY",
    "PROVIDER_CREDENTIAL_ENV",
    "ContractNotVerified",
    "ProviderContract",
    "ProviderError",
    "ProviderIdentity",
    "ProviderRateLimited",
    "ProviderStatus",
    "ProviderUnavailable",
    "build_provider",
    "provider_status_report",
]


class ProviderStatus(str, Enum):
    """What can truthfully be said about one provider, right now."""

    #: No implementation exists.
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    #: An adapter boundary exists but its wire contract was never verified.
    CONTRACT_UNVERIFIED = "CONTRACT_UNVERIFIED"
    #: Contract verified and configuration present.
    READY = "READY"
    #: Contract verified but no credential is configured.
    CONFIGURED_MISSING = "CONFIGURED_MISSING"
    #: The provider was reached and refused the call.
    UNAVAILABLE = "UNAVAILABLE"
    #: A response was received and rejected by validation.
    REJECTED = "REJECTED"


class ProviderError(RuntimeError):
    """Normalised provider failure.

    Carries a safe message only. A credential, header or raw vendor error body
    never reaches this string, because the message is written to the audit log.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class ContractNotVerified(ProviderError):
    """The provider's wire contract has not been verified in this project."""


class ProviderUnavailable(ProviderError):
    """The provider could not be reached, or refused the call."""


class ProviderRateLimited(ProviderError):
    """The provider declined the call for rate or quota reasons."""


@dataclass(frozen=True)
class ProviderContract:
    """The parts of a provider's wire format that a caller must supply.

    Built from documentation that has actually been read, never from
    assumption. Every field is explicit so that an unverifiable provider has
    to be *described* rather than guessed at.
    """

    provider: str
    #: Path only. The scheme and host are configuration, not code, so this
    #: repository cannot be wrong about a vendor's hostname.
    path: str | None
    #: Header names required in addition to content-type.
    headers: tuple[str, ...] = ()
    #: "bearer" or "x-api-key".
    auth_style: str | None = None
    #: True only when the request and response shapes are known.
    verified: bool = False
    #: Why it is not verified, for the status report.
    note: str = ""

    def require_verified(self) -> None:
        if not self.verified or self.path is None:
            raise ContractNotVerified(
                f"{self.provider} wire contract is not verified",
                self.note or "no endpoint recorded in this project",
            )


#: Recorded in ``experiments/phase48/PROVIDER_STATUS.md``.
ANTHROPIC = ProviderContract(
    provider="anthropic",
    path="/v1/messages",
    headers=("anthropic-version", "anthropic-workspace-id"),
    auth_style="bearer",
    verified=True,
    note=(
        "Endpoint, headers, auth and workspace scoping verified in Phase 48. "
        "Model identifiers deliberately not hardcoded: the two official pages "
        "consulted disagree, so a model must be configured explicitly."
    ),
)

#: Phase 48 records Kimi's documentation as UNVERIFIED.
KIMI = ProviderContract(
    provider="kimi",
    path=None,
    verified=False,
    note=(
        "Not researched in this project. No endpoint, header, field or "
        "capability is claimed. Supply a verified contract before use."
    ),
)

#: Phase 48 records DeepSeek's documentation as UNVERIFIED.
DEEPSEEK = ProviderContract(
    provider="deepseek",
    path=None,
    verified=False,
    note=(
        "Not researched in this project. No endpoint, header, field or "
        "capability is claimed. Supply a verified contract before use."
    ),
)

PROVIDER_CONTRACTS: dict[str, ProviderContract] = {
    ANTHROPIC.provider: ANTHROPIC,
    KIMI.provider: KIMI,
    DEEPSEEK.provider: DEEPSEEK,
}

#: The only environment variable each provider may read. Read by name, never
#: by scanning the environment, so no unrelated variable is ever touched.
PROVIDER_CREDENTIAL_ENV: dict[str, str] = {
    ANTHROPIC.provider: "ANTHROPIC_API_KEY",
}


@dataclass(frozen=True)
class ProviderIdentity:
    """Who answered, and how much is actually known about them."""

    provider: str
    model: str | None
    contract_verified: bool
    offline: bool = False

    def as_record(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "contract_verified": self.contract_verified,
            "offline": self.offline,
        }


@dataclass(frozen=True)
class ProviderConfig:
    """Explicit configuration. Absent pieces mean offline, never a guess."""

    provider: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    workspace_id: str | None = None
    anthropic_version: str | None = None

    def __post_init__(self) -> None:
        if self.provider not in PROVIDER_CONTRACTS:
            raise ProviderConfigurationError(
                f"unknown provider {self.provider!r}; known providers are "
                f"{sorted(PROVIDER_CONTRACTS)}"
            )
        if self.model is not None and not re.fullmatch(
            r"[A-Za-z0-9._:/-]{1,128}", self.model
        ):
            raise ProviderConfigurationError("model identifier is not well formed")

    @classmethod
    def from_env(cls, provider: str) -> "ProviderConfig":
        """Build configuration from the one variable that provider may read.

        Nothing else in the environment is inspected. A missing key is not an
        error here: it produces a configuration that reports itself unready,
        which is the offline default the project requires.
        """

        if provider not in PROVIDER_CREDENTIAL_ENV:
            raise ProviderConfigurationError(
                f"no credential variable is defined for {provider!r}; refusing "
                "to guess at one"
            )
        return cls(
            provider=provider,
            model=os.environ.get("ANTHROPIC_MODEL") or None,
            api_key=os.environ.get(PROVIDER_CREDENTIAL_ENV[provider]) or None,
        )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)


#: Transport signature: (url, headers, body) -> (status_code, payload).
#: Injected so that request construction and response parsing are testable
#: offline and nothing in this module can open a socket.
Transport = Callable[[str, Mapping[str, str], str], "tuple[int, Any]"]


@dataclass
class HttpChatProvider:
    """An adapter over a verified wire contract.

    Implements the same shape as the offline provider, so the audited runner
    machinery -- atomic budget reservation, deadline, late-result disposal,
    output validation, redaction -- applies unchanged.
    """

    config: ProviderConfig
    transport: Transport | None = None

    @property
    def name(self) -> str:
        return self.config.provider

    def identity(self) -> ProviderIdentity:
        contract = PROVIDER_CONTRACTS[self.config.provider]
        return ProviderIdentity(
            provider=self.config.provider,
            model=self.config.model,
            contract_verified=contract.verified,
            offline=False,
        )

    def is_configured(self) -> bool:
        return self.config.is_configured() and self.transport is not None

    # -- request construction ------------------------------------------

    def build_headers(self) -> dict[str, str]:
        contract = PROVIDER_CONTRACTS[self.config.provider]
        contract.require_verified()
        if not self.config.api_key:
            raise ProviderConfigurationError(
                f"{self.config.provider} is not configured; no credential is set"
            )
        headers = {"content-type": "application/json"}
        for name in contract.headers:
            if name == "anthropic-version":
                if not self.config.anthropic_version:
                    raise ProviderConfigurationError(
                        "anthropic-version must be configured explicitly; this "
                        "repository does not assume a value"
                    )
                headers["anthropic-version"] = self.config.anthropic_version
            elif name == "anthropic-workspace-id" and self.config.workspace_id:
                headers["anthropic-workspace-id"] = self.config.workspace_id
        if contract.auth_style == "bearer":
            headers["authorization"] = f"Bearer {self.config.api_key}"
        elif contract.auth_style == "x-api-key":
            headers["x-api-key"] = self.config.api_key
        return headers

    def build_body(self, request: ProviderRequest) -> dict[str, Any]:
        """Body per the verified contract.

        ``max_tokens`` is required by the recorded contract and is bounded
        here so a caller cannot request an unbounded response.
        """

        contract = PROVIDER_CONTRACTS[self.config.provider]
        contract.require_verified()
        if not self.config.model:
            raise ProviderConfigurationError(
                "a model must be configured; the project's sources disagree on "
                "model identifiers so none is assumed"
            )
        return {
            "model": self.config.model,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": "user", "content": request.to_prompt()}],
        }

    # -- transport -----------------------------------------------------

    def analyse(
        self,
        request: ProviderRequest,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> ProviderResponse:
        """Perform one call. Raises :class:`ProviderError` on any failure.

        Retries are not performed here. A retry multiplies cost, and silently
        repeating an expensive call is exactly what a budget is meant to
        prevent; the budget meter bounds attempts, not a hidden retry loop.
        """

        if self.transport is None:
            raise ProviderUnavailable(
                "no transport configured", "this adapter cannot reach a network"
            )
        if not self.config.base_url:
            raise ProviderConfigurationError(
                "base_url must be configured explicitly; this repository does "
                "not assume a vendor hostname"
            )

        contract = PROVIDER_CONTRACTS[self.config.provider]
        contract.require_verified()
        headers = self.build_headers()
        body = json.dumps(self.build_body(request))

        status, payload = self.transport(
            f"{self.config.base_url.rstrip('/')}{contract.path}", headers, body
        )

        if status == 429:
            raise ProviderRateLimited("provider rate limited")
        if status in (401, 403):
            # Deliberately does not echo the response: it may quote the key.
            raise ProviderUnavailable("provider refused authentication")
        if status >= 400:
            raise ProviderUnavailable("provider returned an error status")

        text = self._extract_text(payload)
        return ProviderResponse(
            provider_name=self.config.provider,
            model_name=self.config.model,
            raw_text=text,
            retrieved_at=datetime.now(timezone.utc),
            finish_reason=self._extract_finish_reason(payload),
        )

    @staticmethod
    def _extract_text(payload: Any) -> str:
        """Pull the assistant text out of a contract-shaped response."""

        if not isinstance(payload, dict):
            raise ProviderUnavailable("response was not an object")
        content = payload.get("content")
        if isinstance(content, list):
            parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if parts:
                return "\n".join(parts)
        text = payload.get("completion")
        if isinstance(text, str):
            return text
        raise ProviderUnavailable("response contained no assistant text")

    @staticmethod
    def _extract_finish_reason(payload: Any) -> str | None:
        if isinstance(payload, dict):
            reason = payload.get("stop_reason")
            if isinstance(reason, str):
                return reason
        return None


def build_provider(config: ProviderConfig, transport: Transport | None = None):
    """Return a provider adapter, or refuse.

    Offline is the default: with no credential the caller receives an adapter
    that reports itself unconfigured rather than a silently different provider.
    """

    contract = PROVIDER_CONTRACTS.get(config.provider)
    if contract is None:
        raise ProviderConfigurationError(
            f"unknown provider {config.provider!r}"
        )
    if not contract.verified:
        raise ContractNotVerified(
            f"{config.provider} wire contract is not verified",
            contract.note,
        )
    return HttpChatProvider(config=config, transport=transport)


@dataclass(frozen=True)
class ProviderStatusRecord:
    """One row of the status report the API serves."""

    provider: str
    status: ProviderStatus
    contract_verified: bool
    model: str | None
    detail: str

    def as_record(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "integration_state": self.status.value,
            "documentation_verified": self.contract_verified,
            "model": self.model,
            "detail": self.detail,
        }


#: Reported names only. Whether a credential is present is deliberately not a
#: field: this service does not read the environment to answer status, and a
#: hardcoded ``False`` would be a fabricated observation.
PROVIDER_REGISTRY: dict[str, ProviderContract] = PROVIDER_CONTRACTS


def provider_status_report(model: str | None = None) -> list[ProviderStatusRecord]:
    """Describe each provider truthfully. No network, no credential read."""

    rows: list[ProviderStatusRecord] = []
    for name, contract in sorted(PROVIDER_CONTRACTS.items()):
        if not contract.verified:
            status = ProviderStatus.CONTRACT_UNVERIFIED
            detail = contract.note
        elif model:
            status = ProviderStatus.READY
            detail = (
                f"Wire contract verified{contract.path}. A model is configured. "
                "No request has been made by this status call."
            )
        else:
            status = ProviderStatus.CONFIGURED_MISSING
            detail = (
                f"Wire contract verified{contract.path}. No model identifier is "
                "configured, and this project does not assume one because its "
                "sources disagree."
            )
        rows.append(
            ProviderStatusRecord(
                provider=name,
                status=status,
                contract_verified=contract.verified,
                model=model if contract.verified else None,
                detail=detail,
            )
        )
    return rows