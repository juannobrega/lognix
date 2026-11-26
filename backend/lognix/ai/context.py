"""Montagem e redução do contexto enviado à IA. Pipeline de Análise, seções 2 e 3.

Os blocos vão numerados com índices globais por tipo. A IA cita evidências por índice; o
backend resolve de volta para as linhas e eventos reais. Nada do que a IA escreve vira
evidência diretamente.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lognix.analysis.models import LogLevel, Pattern, TriggerFired, TriggerType
from lognix.containers.models import Container
from lognix.events.models import DockerEvent, DockerEventType
from lognix.loki.client import LogLine

MAX_ERROR_LINES = 100
MAX_CONTEXT_LINES = 50
MAX_EVENTS = 20
MAX_PATTERNS = 10
MAX_LINE_CHARS = 2000
# Aproximação suficiente para orçar o prompt sem depender do tokenizador do modelo.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def truncate_middle(line: str, limit: int = MAX_LINE_CHARS) -> str:
    if len(line) <= limit:
        return line
    head = limit // 2 - 20
    return f"{line[:head]}\n  […{len(line) - limit} caracteres omitidos…]\n{line[-head:]}"


@dataclass
class Evidence:
    """Uma evidência citável, com o dado real por trás do índice."""

    kind: str
    index: int
    text: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuiltContext:
    system_blocks: list[str]
    user_text: str
    evidences: dict[str, list[Evidence]]
    truncated: bool
    estimated_tokens: int

    def max_index(self) -> dict[str, int]:
        return {kind: len(items) for kind, items in self.evidences.items()}

    def resolve(self, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Converte índices em evidências reais. Índices inválidos já foram barrados."""
        out: list[dict[str, Any]] = []
        for ref in refs:
            items = self.evidences.get(str(ref["kind"]), [])
            index = int(ref["index"])
            if 0 <= index < len(items):
                ev = items[index]
                out.append({"kind": ev.kind, "index": ev.index, "text": ev.text, **ev.payload})
        return out


def _fmt_ts(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1e9, tz=UTC).strftime("%H:%M:%S.%f")[:-3]


def _event_text(ev: DockerEvent) -> str:
    bits = [ev.type.value]
    if ev.exit_code is not None:
        bits.append(f"exit code {ev.exit_code}")
    if ev.type == DockerEventType.redeploy:
        bits.append(f"{ev.previous_image or '?'} → {ev.new_image or '?'}")
    action = (ev.attributes or {}).get("action")
    if action and action != ev.type.value:
        bits.append(str(action))
    return f"{ev.occurred_at.strftime('%H:%M:%S')} {' · '.join(bits)}"


def build_context(
    *,
    container: Container,
    trigger: TriggerFired,
    lines: list[LogLine],
    levels: dict[int, LogLevel],
    events: list[DockerEvent],
    patterns: list[Pattern],
    new_pattern_templates: list[str],
    state: dict[str, Any] | None,
    max_input_tokens: int,
) -> BuiltContext:
    """Monta o contexto na ordem de prioridade do Pipeline e corta até caber no orçamento."""
    error_idx = [i for i, ln in enumerate(lines) if levels.get(i) == LogLevel.error]
    if trigger.type == TriggerType.error and error_idx:
        first_error = error_idx[0]
        focus = error_idx[:MAX_ERROR_LINES]
        before = list(range(max(0, first_error - MAX_CONTEXT_LINES), first_error))
    else:
        # Evento crítico, anomalia ou manual: as últimas linhas da janela são o foco.
        focus = error_idx[:MAX_ERROR_LINES] or list(range(max(0, len(lines) - 100), len(lines)))
        before = list(
            range(
                max(0, (focus[0] if focus else len(lines)) - MAX_CONTEXT_LINES),
                focus[0] if focus else 0,
            )
        )

    error_evs = [
        Evidence(
            "log_line",
            n,
            truncate_middle(lines[i].line),
            {"ts_ns": str(lines[i].ts_ns), "at": _fmt_ts(lines[i].ts_ns)},
        )
        for n, i in enumerate(focus)
    ]
    # Sempre, não só quando estoura: linha idêntica repetida é custo puro, sem informação nova.
    error_evs = _collapse_identical(error_evs)
    context_lines = [truncate_middle(lines[i].line) for i in before]
    event_evs = [
        Evidence("docker_event", n, _event_text(ev), {"type": ev.type.value})
        for n, ev in enumerate(events[-MAX_EVENTS:])
    ]
    top_patterns = sorted(patterns, key=lambda p: p.count_total, reverse=True)[:MAX_PATTERNS]
    new_set = set(new_pattern_templates)
    for p in patterns:
        if p.template in new_set and p not in top_patterns:
            top_patterns.append(p)
    pattern_evs = [
        Evidence(
            "pattern",
            n,
            p.template,
            {"count": p.count_total, "level": p.level.value, "new": p.template in new_set},
        )
        for n, p in enumerate(top_patterns)
    ]

    redeploy = next((e for e in reversed(events) if e.type == DockerEventType.redeploy), None)
    truncated = False

    def render(
        ctx_lines: list[str], errs: list[Evidence], pats: list[Evidence], evs: list[Evidence]
    ) -> str:
        parts: list[str] = []
        env = (container.env or {}).get("safe") or {}
        parts.append(
            "[PROJETO]\n"
            f"nome: {container.name}\n"
            f"host: {container.host.name}\n"
            f"imagem: {container.image}\n"
            f"compose: {container.compose_project or '-'} / {container.compose_service or '-'}\n"
            + (
                f"variáveis: {', '.join(f'{k}={v}' for k, v in sorted(env.items()))}\n"
                if env
                else ""
            )
        )
        window = f"{trigger.window_start.isoformat()} até {trigger.window_end.isoformat()}"
        parts.append(
            f"[TRIGGER]\ntipo: {trigger.type.value}\n"
            f"motivo: {trigger.note or '-'}\njanela: {window}\n"
        )
        if errs:
            body = "\n".join(f"  [log_line {e.index}] {e.payload['at']} {e.text}" for e in errs)
            parts.append(f"[LINHAS DE ERRO] ({len(errs)})\n{body}\n")
        if ctx_lines:
            body = "\n".join(f"  {line}" for line in ctx_lines)
            parts.append(
                f"[CONTEXTO ANTERIOR] ({len(ctx_lines)} linhas antes do primeiro erro)\n{body}\n"
            )
        if evs:
            body = "\n".join(f"  [docker_event {e.index}] {e.text}" for e in evs)
            parts.append(f"[EVENTOS DOCKER]\n{body}\n")
        if pats:
            body = "\n".join(
                f"  [pattern {e.index}] {e.payload['count']}x "
                f"{'NOVO ' if e.payload['new'] else ''}{e.text}"
                for e in pats
            )
            parts.append(f"[PADRÕES]\n{body}\n")
        if redeploy is not None:
            parts.append(
                f"[REDEPLOY]\n  {redeploy.occurred_at.isoformat()}: "
                f"{redeploy.previous_image or '?'} → {redeploy.new_image or '?'}\n"
            )
        if state:
            parts.append(
                "[ESTADO ATUAL]\n"
                f"  estado: {state.get('state', '-')}\n"
                f"  reinícios: {state.get('restart_count', '-')}\n"
                f"  healthcheck: {state.get('health', '-')}\n"
            )
        return "\n".join(parts)

    text = render(context_lines, error_evs, pattern_evs, event_evs)
    # Ordem de corte do Pipeline seção 3. Blocos de projeto, trigger, redeploy e estado ficam.
    while estimate_tokens(text) > max_input_tokens:
        truncated = True
        if context_lines:
            context_lines = context_lines[len(context_lines) // 2 :]
        elif len(error_evs) > 10:
            error_evs = _collapse_repeats(error_evs)
        elif len(pattern_evs) > 3:
            pattern_evs = [e for e in pattern_evs if e.payload["new"]][:3] or pattern_evs[:3]
        elif len(event_evs) > 3:
            event_evs = event_evs[-3:]
        elif len(error_evs) > 3:
            error_evs = error_evs[:3]
        else:
            break
        text = render(context_lines, error_evs, pattern_evs, event_evs)

    return BuiltContext(
        system_blocks=[],
        user_text=text,
        evidences={"log_line": error_evs, "docker_event": event_evs, "pattern": pattern_evs},
        truncated=truncated,
        estimated_tokens=estimate_tokens(text),
    )


_NUM = re.compile(r"\d+")


def _collapse(items: list[Evidence], *, chave: Callable[[Evidence], str]) -> list[Evidence]:
    """Junta linhas sob a mesma chave, guardando quantas foram e em que intervalo.

    O intervalo importa: cem cópias da mesma linha em dois segundos é um estouro, e em duas
    horas é um gotejamento. Mandar os cem carimbos de hora separados não diz isso melhor — diz
    pior, porque enterra o padrão em repetição.
    """
    primeiro: dict[str, Evidence] = {}
    contagem: dict[str, int] = {}
    ultimo_at: dict[str, str] = {}
    for ev in items:
        k = chave(ev)
        contagem[k] = contagem.get(k, 0) + 1
        primeiro.setdefault(k, ev)
        ultimo_at[k] = str(ev.payload.get("at") or "")
    saida: list[Evidence] = []
    for n, (k, ev) in enumerate(primeiro.items()):
        vezes = contagem[k]
        if vezes == 1:
            saida.append(Evidence("log_line", n, ev.text, ev.payload))
            continue
        inicio, fim = str(ev.payload.get("at") or ""), ultimo_at[k]
        quando = f" entre {inicio} e {fim}" if inicio and fim and inicio != fim else ""
        texto = f"{ev.text}   (repetida {vezes} vezes{quando})"
        saida.append(Evidence("log_line", n, texto, {**ev.payload, "repeats": vezes}))
    return saida


def _collapse_identical(items: list[Evidence]) -> list[Evidence]:
    """Junta linhas **exatamente** iguais. Seguro de aplicar sempre.

    A centésima cópia idêntica não ensina nada ao modelo, e custa o mesmo que a primeira: num
    container que cospe o mesmo erro em laço, isso sozinho derruba o contexto em mais de 90%.
    A contagem informa mais do que a repetição, porque vira dado.

    Diferente de `_collapse_repeats`, aqui nada que difira é fundido — dois erros sobre ids
    diferentes continuam sendo duas linhas, porque o id pode ser exatamente a pista.
    """
    return _collapse(items, chave=lambda ev: ev.text)


def _collapse_repeats(items: list[Evidence]) -> list[Evidence]:
    """Junta linhas com a mesma *forma*, ignorando números. Só no corte por orçamento.

    Mais agressivo: funde "falhou para o usuário 12" com "falhou para o usuário 99". Perde o
    valor específico, que às vezes é a pista — por isso só entra quando o contexto não cabe.
    """
    return _collapse(items, chave=lambda ev: _NUM.sub("<n>", ev.text)[:300])
