"""Orquestração da análise por IA: contexto, chamada, validação com retry, insight e custo.

Pipeline de Análise seções 4 a 6. Falha nunca é silenciosa: ou nasce um insight, ou nasce
um AiCall com erro e uma notificação.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.ai.context import BuiltContext, build_context
from lognix.ai.models import AiCall, AiCallStatus, AiPurpose, CostSource, Insight, Severity
from lognix.ai.openrouter import OpenRouterProvider
from lognix.ai.prompts import ANALYZE_SYSTEM, ANALYZE_VERSION, retry_message
from lognix.ai.provider import AiError, AiProvider, AiResult, RateLimitedError
from lognix.ai.schemas import INSIGHT_SCHEMA, SchemaError, validate_insight
from lognix.analysis.models import LogLevel, Pattern, TriggerFired
from lognix.containers.models import Container
from lognix.events.models import DockerEvent
from lognix.loki.client import LogLine
from lognix.metrics import ai_calls_total, ai_semaphore_waiting
from lognix.notifications.models import NotificationType
from lognix.notifications.service import notify
from lognix.settings import service as settings_service

log = logging.getLogger(__name__)

EVENT_WINDOW = timedelta(minutes=10)
RATE_LIMIT_PAUSE = timedelta(minutes=5)
_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


class AiDisabledError(Exception):
    """A IA não está ativa. Não é erro: o trigger fica registrado sem insight."""


@dataclass
class AiOutcome:
    insight: Insight | None
    calls: list[AiCall]
    error: str | None = None


class AiRuntime:
    """Guarda o provider montado e o limite de chamadas simultâneas."""

    def __init__(self) -> None:
        self._provider: AiProvider | None = None
        self._key_fingerprint: str | None = None
        self._semaphore = asyncio.Semaphore(3)
        self._concurrency = 3
        self._paused_until: datetime | None = None

    async def provider_for(self, db: AsyncSession) -> tuple[AiProvider, str]:
        """Provider e modelo atuais. Recria se a chave mudou."""
        if not await settings_service.ai_is_active(db):
            raise AiDisabledError
        api_key = await settings_service.get(db, settings_service.AI_API_KEY)
        model = await settings_service.get(db, settings_service.AI_MODEL)
        if not api_key or not model:
            raise AiDisabledError
        fingerprint = str(hash(api_key))
        if self._provider is None or fingerprint != self._key_fingerprint:
            if self._provider is not None:
                await self._provider.aclose()
            self._provider = OpenRouterProvider(api_key)
            self._key_fingerprint = fingerprint
        concurrency = await settings_service.get_int(db, settings_service.AI_CONCURRENCY, 3)
        if concurrency != self._concurrency:
            self._semaphore = asyncio.Semaphore(concurrency)
            self._concurrency = concurrency
        return self._provider, model

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    def pause(self, seconds: float | None = None) -> None:
        delta = timedelta(seconds=seconds) if seconds else RATE_LIMIT_PAUSE
        self._paused_until = datetime.now(UTC) + delta

    @property
    def paused_until(self) -> datetime | None:
        if self._paused_until and self._paused_until <= datetime.now(UTC):
            self._paused_until = None
        return self._paused_until

    async def reset(self) -> None:
        if self._provider is not None:
            await self._provider.aclose()
        self._provider = None
        self._key_fingerprint = None
        self._paused_until = None


_runtime: AiRuntime | None = None


def get_runtime() -> AiRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AiRuntime()
    return _runtime


def set_runtime(runtime: AiRuntime | None) -> None:
    global _runtime
    _runtime = runtime


def parse_json_object(text: str) -> Any:
    """Extrai o objeto JSON da resposta. Texto em volta é descartado se houver um só objeto."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(stripped)
    if match is None:
        raise SchemaError("a resposta não contém um objeto JSON")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"JSON inválido: {exc}") from exc


async def analyze_trigger(
    db: AsyncSession,
    *,
    container: Container,
    trigger: TriggerFired,
    lines: list[LogLine],
    levels: dict[int, LogLevel],
    new_pattern_templates: list[str],
    state: dict[str, Any] | None = None,
) -> AiOutcome:
    """Explica um trigger. Devolve o insight ou o motivo de não ter saído nenhum."""
    runtime = get_runtime()
    paused = runtime.paused_until
    if paused is not None:
        return AiOutcome(None, [], f"IA pausada por limite de uso até {paused.isoformat()}")
    try:
        provider, model = await runtime.provider_for(db)
    except AiDisabledError:
        return AiOutcome(None, [], None)

    events = list(
        (
            await db.execute(
                select(DockerEvent)
                .where(
                    DockerEvent.container_id == container.id,
                    DockerEvent.occurred_at >= trigger.window_start - EVENT_WINDOW,
                    DockerEvent.occurred_at <= trigger.window_end,
                )
                .order_by(DockerEvent.occurred_at)
            )
        ).scalars()
    )
    patterns = list(
        (await db.execute(select(Pattern).where(Pattern.container_id == container.id))).scalars()
    )
    max_input = await settings_service.get_int(db, settings_service.AI_MAX_INPUT_TOKENS, 12000)
    max_output = await settings_service.get_int(db, settings_service.AI_MAX_OUTPUT_TOKENS, 1500)

    context = build_context(
        container=container,
        trigger=trigger,
        lines=lines,
        levels=levels,
        events=events,
        patterns=patterns,
        new_pattern_templates=new_pattern_templates,
        state=state,
        max_input_tokens=max_input,
    )

    calls: list[AiCall] = []
    ai_semaphore_waiting.inc()
    try:
        async with runtime.semaphore:
            ai_semaphore_waiting.dec()
            outcome = await _call_with_retry(
                db,
                provider=provider,
                model=model,
                container=container,
                trigger=trigger,
                context=context,
                max_output=max_output,
                calls=calls,
            )
    except BaseException:
        ai_semaphore_waiting.dec()
        raise
    return outcome


async def _call_with_retry(
    db: AsyncSession,
    *,
    provider: AiProvider,
    model: str,
    container: Container,
    trigger: TriggerFired,
    context: BuiltContext,
    max_output: int,
    calls: list[AiCall],
) -> AiOutcome:
    user_text = context.user_text
    previous_text = ""
    last_error = ""

    for attempt in range(2):  # uma tentativa e um retry de esquema
        is_retry = attempt == 1
        prompt = (
            user_text
            if not is_retry
            else f"{user_text}\n\n{retry_message(previous_text, last_error)}"
        )
        started = time.perf_counter()
        try:
            result = await provider.complete(
                system=ANALYZE_SYSTEM,
                user=prompt,
                schema=INSIGHT_SCHEMA,
                model=model,
                max_output_tokens=max_output,
            )
        except RateLimitedError as exc:
            get_runtime().pause(exc.retry_after)
            call = _record_call(
                db,
                container,
                trigger,
                model,
                AiCallStatus.error,
                exc.message,
                latency_ms=int((time.perf_counter() - started) * 1000),
                schema_retry=is_retry,
            )
            calls.append(call)
            await _notify_error(db, container, exc.message)
            return AiOutcome(None, calls, exc.message)
        except AiError as exc:
            call = _record_call(
                db,
                container,
                trigger,
                model,
                AiCallStatus.error,
                exc.message,
                latency_ms=int((time.perf_counter() - started) * 1000),
                schema_retry=is_retry,
            )
            calls.append(call)
            await _notify_error(db, container, exc.message)
            return AiOutcome(None, calls, exc.message)

        try:
            data = validate_insight(parse_json_object(result.text), max_index=context.max_index())
        except SchemaError as exc:
            last_error, previous_text = str(exc), result.text
            calls.append(
                _record_call(
                    db,
                    container,
                    trigger,
                    model,
                    AiCallStatus.error,
                    f"resposta fora do esquema: {exc}",
                    result=result,
                    schema_retry=is_retry,
                )
            )
            if is_retry:
                message = f"A IA respondeu fora do formato duas vezes: {exc}"
                await _notify_error(db, container, message)
                return AiOutcome(None, calls, message)
            continue

        insight = Insight(
            container_id=container.id,
            trigger_id=trigger.id,
            severity=Severity(data["severity"]),
            title=data["title"],
            summary=data["summary"],
            probable_cause=data["probable_cause"],
            suggested_action=data["suggested_action"],
            confidence=Decimal(str(data["confidence"])),
            needs_code=data["needs_code"],
            evidence=context.resolve(data["evidence_refs"]),
            context_truncated=context.truncated,
            sent_context=context.user_text,
        )
        db.add(insight)
        await db.flush()
        trigger.insight_id = insight.id
        call = _record_call(
            db,
            container,
            trigger,
            model,
            AiCallStatus.ok,
            None,
            result=result,
            schema_retry=is_retry,
        )
        call.insight_id = insight.id
        calls.append(call)
        await db.commit()
        await db.refresh(insight)
        log.info(
            "insight criado",
            extra={
                "container": container.name,
                "severity": insight.severity.value,
                "confidence": float(insight.confidence),
                "tokens_in": result.input_tokens,
                "cost_usd": float(result.cost_usd),
            },
        )
        return AiOutcome(insight, calls)

    return AiOutcome(None, calls, last_error or "falha desconhecida")


def _record_call(
    db: AsyncSession,
    container: Container,
    trigger: TriggerFired,
    model: str,
    status: AiCallStatus,
    error: str | None,
    *,
    result: AiResult | None = None,
    latency_ms: int = 0,
    schema_retry: bool = False,
) -> AiCall:
    call = AiCall(
        id=uuid.uuid4(),
        trigger_id=trigger.id,
        container_id=container.id,
        model=result.model if result else model,
        purpose=AiPurpose.analyze,
        prompt_version=ANALYZE_VERSION,
        input_tokens=result.input_tokens if result else 0,
        output_tokens=result.output_tokens if result else 0,
        cost_usd=result.cost_usd if result else Decimal(0),
        cost_source=result.cost_source if result else CostSource.unknown,
        latency_ms=result.latency_ms if result else latency_ms,
        schema_retry=schema_retry,
        status=status,
        error=error[:2000] if error else None,
    )
    db.add(call)
    ai_calls_total.labels(status.value, AiPurpose.analyze.value).inc()
    return call


async def _notify_error(db: AsyncSession, container: Container, message: str) -> None:
    await notify(
        db,
        NotificationType.ai_error,
        f"Falha na análise de {container.name}",
        container_id=container.id,
        payload={"error": message[:500]},
    )
    await db.commit()
