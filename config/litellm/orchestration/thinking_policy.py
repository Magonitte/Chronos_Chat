"""Politica de ativacao de thinking — automatica por contexto (F10)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping

from orchestration.types import ChatMessage

_TRIVIAL = re.compile(
    r"^(?:oi|ol[aá]|oii+|hey|hi|hello|e a[ií]|fala|fala[eilm]?\s*"
    r"(a[ií]|comigo|cmg)?|bom\s*dia|boa\s*(tarde|noite)|tudo\s*"
    r"(bem|certo|em\s*cima|joia|ok)?|como\s*(vai|vão|est[aá]|"
    r"t[aá]|anda|estamos|c[\'e]est|ta|tão)?|iae|eae|salve|opa|"
    r"oba|obrigad[oa]|valeu|vlw|flw|ok|okay|sim|n[aã]o|thanks|"
    r"thank\s*you|certo|entendi|entendo|compreendo|saquei|show|"
    r"legal|massa|bacana|beleza|blz|joia|boa|falou|at[eé]\s*"
    r"(mais|logo|breve)|tchau|bye|adeus|xau|int[eé]|fui|abandonar|"
    r"sair|exit|quit)[\s!?.]*$",
    re.IGNORECASE,
)

_RECALL = re.compile(
    r"(?:o\s+que\s+(?:voc[eê]|vc)\s+(?:sabe|lembra|recorda)\s+sobre\s+mim|"
    r"(?:voc[eê]|vc)\s+(?:lembra|recorda|sabe)\b|"
    r"qual\s+(?:[ée]|a\s+)?minha\b|"
    r"quando\s+(?:eu\s+)?nasci|"
    r"data\s+de\s+nascimento|"
    r"what\s+do\s+you\s+(?:know|remember)\s+about\s+me)",
    re.IGNORECASE,
)

_MEMORY_COMMAND = re.compile(
    r"(?:(?:me\s+)?lembr(?:a(?:r|-se)?|e(?:-se)?)\s+(?:isso|disso|que)\b|"
    r"lembr(?:a|e)\s+que\b|memoriz(?:a|e|ar)\b|"
    r"n[aã]o\s+esque(?:ça|ca)\b|"
    r"guarda(?:r)?\s+(?:isso|que|na\s+mem[oó]ria|para\s+depois)\b|"
    r"anota(?:r)?\s+(?:isso|que|na\s+mem[oó]ria)\b|"
    r"salva(?:r)?\s+(?:isso|que|na\s+mem[oó]ria)\b|"
    r"registra(?:r)?\s+(?:isso|que)\b|"
    r"arquiva(?:r)?\s+(?:isso|que)\b|"
    r"grava(?:r)?\s+(?:isso|que)\b|"
    r"remember\s+(?:that|to)\b|"
    r"save\s+(?:this|that|to\s+memory)\b)",
    re.IGNORECASE,
)

_COMPLEX_QUERY = re.compile(
    r"(?:analis(?:e|ar|ando)\b|expliqu(?:e|ar|ando)\b|"
    r"compar(?:e|ar|ando|ação|ativo)\b|diferen[çc]a\b|"
    r"por\s+qu[ée]\b|como\s+funciona\b|por\s+que\s+motivo\b|"
    r"resolv(?:a|er|endo)\b|calcul(?:e|ar|ando)\b|"
    r"implement(?:e|ar|ando)\b|c[oó]digo\b|script\b|debug\b|"
    r"erro\b|traceback\b|traduz(?:a|ir|indo)\b|resum(?:a|ir|indo)\b|"
    r"s[íi]ntese\b|conclus[aã]o\b|recomenda[çc](?:[aã]o|ões)\b|"
    r"avalia[çc](?:[aã]o|ões)\b|impacto\b|consequ[êe]ncia\b|"
    r"causa\b|efeito\b|trade[-\s]?off\b|vantagem\b|desvantagem\b|"
    r"pr[oó]s?\s+e\s+contras?\b|otimiz(?:e|ar|ando)\b|"
    r"refator(?:e|ar|ando)\b|corrij(?:a|ir|indo)\b|"
    r"melhori(?:a|as)\b|arquitetur(?:a|as)\b|"
    r"design\s+pattern\b|algoritm(?:o|os)\b)",
    re.IGNORECASE,
)

DEFAULT_THINKING_ENABLED = True
DEFAULT_THINKING_RAG_CHUNKS = 3
DEFAULT_THINKING_MIN_CONVERSATION_TURNS = 6
DEFAULT_THINKING_MAX_TOKENS = 3072


@dataclass(frozen=True)
class ThinkingContext:
    """Contexto para decisao de ativacao de thinking por request."""

    query: str
    conversation: tuple[ChatMessage, ...]
    rag_chunk_count: int
    has_images: bool
    is_system_request: bool


def _env_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key, "").strip().lower()
    if not raw:
        return default
    return raw not in ("false", "0", "no", "off")


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _is_trivial(query: str) -> bool:
    return bool(_TRIVIAL.search(query.strip()))


def _is_recall(query: str) -> bool:
    return bool(_RECALL.search(query.strip()))


def _is_memory_command(query: str) -> bool:
    return bool(_MEMORY_COMMAND.search(query.strip()))


def _is_complex(query: str) -> bool:
    return bool(_COMPLEX_QUERY.search(query.strip()))


def _count_turns(conversation: tuple[ChatMessage, ...]) -> int:
    """Conta turnos (user + assistant), ignora system."""
    count = 0
    for msg in conversation:
        if msg.role in ("user", "assistant"):
            count += 1
    return count


def should_enable(
    ctx: ThinkingContext,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """
    Decide se thinking deve ser ativado para este request.

    Barreiras rapidas primeiro, avaliacao contextual depois.
    environ opcional para injecao em testes (default os.environ).
    """
    env = environ if environ is not None else os.environ

    if not _env_bool(env, "NEWCHAT_THINKING_ENABLED", True):
        return False

    if ctx.is_system_request:
        return False

    if _is_trivial(ctx.query):
        return False

    if _is_recall(ctx.query):
        return False

    if _is_memory_command(ctx.query):
        return False

    if ctx.rag_chunk_count >= _env_int(env, "NEWCHAT_THINKING_RAG_CHUNKS", DEFAULT_THINKING_RAG_CHUNKS) and not _is_trivial(ctx.query):
        return True

    if _is_complex(ctx.query) or len(ctx.query) > 80:
        return True

    if _count_turns(ctx.conversation) >= _env_int(env, "NEWCHAT_THINKING_MIN_CONVERSATION_TURNS", DEFAULT_THINKING_MIN_CONVERSATION_TURNS) and not _is_trivial(ctx.query):
        return True

    if ctx.has_images and len(ctx.query) > 30:
        return True

    return False
