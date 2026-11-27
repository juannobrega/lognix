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

from lognix.ai import dedupe, registry
from lognix.ai.context import BuiltContext, build_context
from lognix.ai.models import (
    AiCall,
    AiCallStatus,
    AiProviderConfig,
    AiPurpose,
    CostSource,
    Insight,
    Severity,
)
from lognix.ai.prompts import ANALYZE_SYSTEM, ANALYZE_VERSION, retry_message
from lognix.ai.provider import AiError, AiProvider, AiResult, RateLimitedError
from lognix.ai.schemas import INSIGHT_SCHEMA, SchemaError, validate_insight
from lognix.analysis.models import LogLevel, Pattern, TriggerFired
from lognix.containers.models import Container
from lognix.events.models import DockerEvent
from lognix.integrations import alerts
from lognix.loki.client import LogLine
from lognix.metrics import ai_calls_skipped, ai_calls_total, ai_semaphore_waiting
from lognix.notifications.models import NotificationType
from lognix.notifications.service import notify
from lognix.settings import service as settings_service

log = logging.getLogger(__name__)

EVENT_WINDOW = timedelta(minutes=10)
RATE_LIMIT_PAUSE = timedelta(minutes=5)
_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


class AiDisabledError(Exception):
    """IA desligada ou sem provider pronto. Não é erro: o trigger fica registrado sem insight."""


class AiPausedError(Exception):
    """Todos os providers estão pausados por limite de uso."""

    def __init__(self, until: datetime) -> None:
        super().__init__(f"IA pausada por limite de uso até {until.isoformat()}")
        self.until = until


@dataclass
class AiOutcome:
    insight: Insight | None
    calls: list[AiCall]
    error: str | None = None
    #: O problema já tinha insight ativo: contamos a ocorrência e não chamamos a IA.
    deduped: bool = False
    #: Se o próximo provider da cadeia deve ser tentado.
    should_fallback: bool = False


class AiRuntime:
    """Limita chamadas simultâneas e guarda a pausa por limite de uso, por provider."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(3)
        self._concurrency = 3
        self._paused: dict[uuid.UUID, datetime] = {}

    async def chain(self, db: AsyncSession) -> list[AiProviderConfig]:
        """Providers utilizáveis, na ordem de fallback, pulando os pausados."""
        if not await settings_service.get_bool(db, settings_service.AI_ENABLED):
            raise AiDisabledError
        concurrency = await settings_service.get_int(db, settings_service.AI_CONCURRENCY, 3)
        if concurrency != self._concurrency:
            self._semaphore = asyncio.Semaphore(concurrency)
            self._concurrency = concurrency
        usable = await registry.usable_chain(db)
        if not usable:
            raise AiDisabledError
        available = [p for p in usable if self.paused_until(p.id) is None]
        if not available:
            raise AiPausedError(min(self._paused[p.id] for p in usable if p.id in self._paused))
        return available

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    def pause(self, provider_id: uuid.UUID, seconds: float | None = None) -> None:
        self._paused[provider_id] = datetime.now(UTC) + (
            timedelta(seconds=seconds) if seconds else RATE_LIMIT_PAUSE
        )

    def paused_until(self, provider_id: uuid.UUID) -> datetime | None:
        until = self._paused.get(provider_id)
        if until is not None and until <= datetime.now(UTC):
            del self._paused[provider_id]
            return None
        return until

    def paused_all(self) -> dict[str, datetime]:
        now = datetime.now(UTC)
        return {str(k): v for k, v in self._paused.items() if v > now}

    async def reset(self) -> None:
        self._paused.clear()


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
    """Explica um trigger. Percorre a cadeia de providers até um responder."""
    runtime = get_runtime()
    try:
        chain = await runtime.chain(db)
    except AiDisabledError:
        return AiOutcome(None, [], None)
    except AiPausedError as exc:
        return AiOutcome(None, [], str(exc))

    # Deduplicação **antes** da cadeia, de propósito: a economia inteira está em não fazer a
    # chamada. Encolher o contexto corta porcentagem; não chamar corta a chamada. Ver ADR 016.
    amostras = [str(a.get("line", "")) for a in (trigger.sample_lines or []) if isinstance(a, dict)]
    chave_dedupe = dedupe.chave(trigger, amostras)
    existente = await dedupe.insight_ativo(db, container_id=container.id, dedupe_key=chave_dedupe)
    if existente is not None and not await dedupe.houve_redeploy(
        db, container_id=container.id, depois_de=existente.last_seen_at or existente.created_at
    ):
        dedupe.registrar_ocorrencia(existente, trigger)
        ai_calls_skipped.inc()
        log.info(
            "insight já ativo para este problema; ocorrência somada sem chamar a IA",
            extra={
                "container": container.name,
                "insight": str(existente.id),
                "ocorrencias": existente.occurrences,
            },
        )
        return AiOutcome(existente, [], None, deduped=True)

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
    last_error: str | None = None
    ai_semaphore_waiting.inc()
    try:
        async with runtime.semaphore:
            ai_semaphore_waiting.dec()
            for attempt, provider_config in enumerate(chain):
                try:
                    client = _open(runtime, provider_config)
                except AiError as exc:
                    last_error = exc.message
                    calls.append(
                        _record_call(
                            db,
                            container,
                            trigger,
                            provider_config,
                            provider_config.default_model or "",
                            AiCallStatus.error,
                            exc.message,
                            attempt=attempt,
                        )
                    )
                    continue
                try:
                    outcome = await _call_with_retry(
                        db,
                        provider=client,
                        provider_config=provider_config,
                        model=provider_config.default_model or "",
                        container=container,
                        trigger=trigger,
                        context=context,
                        max_output=max_output,
                        calls=calls,
                        attempt=attempt,
                        dedupe_key=chave_dedupe,
                    )
                finally:
                    await client.aclose()
                if outcome.insight is not None:
                    if attempt > 0:
                        log.info(
                            "insight veio do fallback",
                            extra={"provider": provider_config.name, "attempt": attempt},
                        )
                    return outcome
                last_error = outcome.error
                if not outcome.should_fallback:
                    break
    except BaseException:
        ai_semaphore_waiting.dec()
        raise

    if last_error:
        await _notify_error(db, container, last_error)
    return AiOutcome(None, calls, last_error)


async def _call_with_retry(
    db: AsyncSession,
    *,
    provider: AiProvider,
    provider_config: AiProviderConfig,
    model: str,
    container: Container,
    trigger: TriggerFired,
    context: BuiltContext,
    max_output: int,
    calls: list[AiCall],
    attempt: int,
    dedupe_key: str,
) -> AiOutcome:
    """Uma tentativa num provider, com um retry se a resposta vier fora do esquema."""
    user_text = context.user_text
    previous_text = ""
    last_error = ""

    for round_index in range(2):
        is_retry = round_index == 1
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
            get_runtime().pause(provider_config.id, exc.retry_after)
            calls.append(
                _record_call(
                    db,
                    container,
                    trigger,
                    provider_config,
                    model,
                    AiCallStatus.error,
                    exc.message,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    schema_retry=is_retry,
                    attempt=attempt,
                )
            )
            await db.commit()
            # Limite de uso é do provider, não do pedido: vale tentar o próximo.
            return AiOutcome(None, calls, exc.message, should_fallback=True)
        except AiError as exc:
            calls.append(
                _record_call(
                    db,
                    container,
                    trigger,
                    provider_config,
                    model,
                    AiCallStatus.error,
                    exc.message,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    schema_retry=is_retry,
                    attempt=attempt,
                )
            )
            await db.commit()
            return AiOutcome(None, calls, exc.message, should_fallback=True)

        result = await registry.apply_price(db, provider_config, model, result)
        try:
            data = validate_insight(parse_json_object(result.text), max_index=context.max_index())
        except SchemaError as exc:
            last_error, previous_text = str(exc), result.text
            calls.append(
                _record_call(
                    db,
                    container,
                    trigger,
                    provider_config,
                    model,
                    AiCallStatus.error,
                    f"resposta fora do esquema: {exc}",
                    result=result,
                    schema_retry=is_retry,
                    attempt=attempt,
                )
            )
            await db.commit()
            if is_retry:
                message = f"A IA respondeu fora do formato duas vezes: {exc}"
                # Outro modelo pode acertar o formato: vale a pena tentar o próximo.
                return AiOutcome(None, calls, message, should_fallback=True)
            continue

        insight = Insight(
            container_id=container.id,
            trigger_id=trigger.id,
            # Sem a chave aqui, nada deduplica depois: é ela que o próximo ciclo procura.
            dedupe_key=dedupe_key,
            occurrences=1,
            last_seen_at=trigger.window_end,
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
            provider_config,
            model,
            AiCallStatus.ok,
            None,
            result=result,
            schema_retry=is_retry,
            attempt=attempt,
        )
        call.insight_id = insight.id
        calls.append(call)
        await db.commit()
        await db.refresh(insight)
        # Só aqui, onde o insight **nasce**: recorrência atualiza a contagem do que já existe
        # e não manda nada. Ver ADR 020.
        await alerts.avisar_do_insight(db, insight, container.name, container.host.name)
        log.info(
            "insight criado",
            extra={
                "container": container.name,
                "provider": provider_config.name,
                "severity": insight.severity.value,
                "confidence": float(insight.confidence),
                "cost_usd": float(result.cost_usd),
            },
        )
        return AiOutcome(insight, calls)

    return AiOutcome(None, calls, last_error or "falha desconhecida", should_fallback=True)


def _open(runtime: AiRuntime, provider_config: AiProviderConfig) -> AiProvider:
    """Abre o cliente do provider. O runtime pode substituir isso nos testes."""
    opener = getattr(runtime, "provider_for_config", None)
    if opener is not None:
        return opener(provider_config)  # type: ignore[no-any-return]
    return registry.open_provider(provider_config)


def _record_call(
    db: AsyncSession,
    container: Container,
    trigger: TriggerFired,
    provider_config: AiProviderConfig,
    model: str,
    status: AiCallStatus,
    error: str | None,
    *,
    result: AiResult | None = None,
    latency_ms: int = 0,
    schema_retry: bool = False,
    attempt: int = 0,
) -> AiCall:
    call = AiCall(
        id=uuid.uuid4(),
        trigger_id=trigger.id,
        container_id=container.id,
        provider_id=provider_config.id,
        provider=provider_config.kind,
        provider_name=provider_config.name,
        attempt=attempt,
        fell_back=attempt > 0,
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
    ai_calls_total.labels(status.value, AiPurpose.analyze.value, provider_config.kind).inc()
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
