"""Política de persistência mem0 — lógica pura, sem HTTP nem dependência LiteLLM."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Sequence

from orchestration.types import ChatMessage

# Pedido explícito de armazenar (não confundir com pergunta "lembra o que…")
_REMEMBER_PREFIX = re.compile(
    r"^(?:"
    r"(?:por\s+favor\s*,?\s*)?"
    r"(?:me\s+)?lembr(?:a(?:r|-se)?|e(?:-se)?)\s+(?:isso|disso|que)\s*"
    r")",
    re.IGNORECASE,
)

_REMEMBER_STORE = re.compile(
    r"(?:"
    r"(?:me\s+)?lembr(?:a(?:r|-se)?|e(?:-se)?)\b|"
    r"(?:me\s+)?lembr(?:a|e)\s+que\b|"
    r"memoriz(?:a|e|ar)\b|"
    r"n[aã]o\s+esque(?:ça|ca)\b|"
    r"guarda(?:r)?\s+(?:isso|que|na\s+mem[oó]ria|para\s+depois)\b|"
    r"anota(?:r)?\s+(?:isso|que|na\s+mem[oó]ria|para\s+depois)\b|"
    r"salva(?:r)?\s+(?:isso|que|na\s+mem[oó]ria|para\s+depois)\b|"
    r"registra(?:r)?\s+(?:isso|que|na\s+mem[oó]ria)\b|"
    r"arquiva(?:r)?\s+(?:isso|que|na\s+mem[oó]ria)\b|"
    r"grava(?:r)?\s+(?:isso|que|na\s+mem[oó]ria)\b|"
    r"remember\s+(?:that|to)\b"
    r")",
    re.IGNORECASE,
)

_RECALL_QUERY = re.compile(
    r"(?:"
    r"o\s+que\s+(?:voc[eê]|vc)\s+sabe\s+sobre\s+mim|"
    r"qual\s+(?:é|e|a\s+)?(?:minha\s+)?data\s+de\s+nascimento|"
    r"quando\s+(?:eu\s+)?nasci\b|"
    r"qual\s+(?:é|e)\s+(?:a\s+)?minha\b|"
    r"(?:voc[eê]|vc)\s+lembra\b|"
    r"what\s+do\s+you\s+(?:know|remember)\s+about\s+me"
    r")",
    re.IGNORECASE,
)

_GENERIC_QUERY = re.compile(
    r"^\s*(?:"
    r"o\s+que\s+(?:é|e)\b|"
    r"what\s+is\b|"
    r"como\s+(?:funciona|fazer|faço|faco)\b|"
    r"how\s+(?:do|does|to)\b|"
    r"explique\b|"
    r"explain\b|"
    r"defina\b|"
    r"define\b|"
    r"qual\s+(?:a\s+)?diferen[cç]a\b"
    r")",
    re.IGNORECASE,
)

_PERSONAL_SIGNAL = re.compile(
    r"(?:"
    r"\beu\s+(?:sou|gosto|prefiro|odeio|trabalho|moro|tenho|uso|faço|faco)\b|"
    r"\b(?:meu|minha|meus|minhas)\s+\w+"
    r"|\b(?:sou|trabalho|moro|nasci|tenho|gosto|prefiro|odeio|chamo-me)\b"
    r"|prefiro\b|gosto\s+de\b|n[aã]o\s+gosto\b|"
    r"meu\s+nome\s+(?:é|e)\b|me\s+chamo\b|"
    r"trabalho\s+(?:como|em|na)\b|"
    r"moro\s+em\b|"
    r"tenho\s+\d+\s+anos\b|"
    r"\bnasci(?:\s+em|\s+no|\s+na)?\b|"
    r"\bnascimento\b|"
    r"\b(?:nos\s+)?casamos\b|"
    r"\bcasamento\b|"
    r"\b(?:minha|nossa)\s+esposa\b|"
    r"\b(?:meu|nosso)\s+marido\b"
    r")",
    re.IGNORECASE,
)

_COMMITMENT_SIGNAL = re.compile(
    r"(?:"
    r"\b(?:amanh[aã]|semana\s+que\s+vem|pr[oó]xim[oa]s?\s+dias?)\b|"
    r"\b(?:reuni[aã]o|compromisso|deadline|entrega)\b|"
    r"\b(?:combinei|marquei|agendei)\b"
    r")",
    re.IGNORECASE,
)

_TRIVIAL = re.compile(
    r"^(?:oi|ol[aá]|hey|hi|hello|obrigad[oa]|valeu|ok(?:ay)?|sim|n[aã]o|thanks|thank\s+you)[\s!.?]*$",
    re.IGNORECASE,
)

_COT_MARKERS = re.compile(
    r"(?:</?think>|chain\s+of\s+thought|passo\s+a\s+passo\s*:)",
    re.IGNORECASE,
)

# Requisições internas do cliente de chat (ex: geração de título do LibreChat)
_SYSTEM_REQUEST = re.compile(
    r"^\s*(?:"
    r"provide\s+a\s+concise\b|"
    r"generate\s+a\s+(?:concise\s+)?(?:short\s+)?title\b|"
    r"give\s+(?:me\s+)?a\s+(?:concise\s+)?(?:short\s+)?title\b"
    r")",
    re.IGNORECASE,
)

_MIN_SUBSTANTIVE_LEN = 12


@dataclass(frozen=True)
class MemoryPersistContext:
    """Contexto para decisão POST-CALL (sem I/O)."""

    user_id: str
    rag_was_triggered: bool = False
    existing_memory_texts: tuple[str, ...] = field(default_factory=tuple)


def message_text(message: ChatMessage) -> str:
    """Extrai texto de mensagem (string ou partes multimodais)."""
    if isinstance(message.content, str):
        return message.content.strip()
    parts: list[str] = []
    for part in message.content:
        if isinstance(part, dict) and part.get("type") == "text":
            parts.append(str(part.get("text", "")))
    return " ".join(parts).strip()


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip()


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"\w+", _normalize(text)))


def _is_near_duplicate(candidate: str, existing: Sequence[str], *, threshold: float = 0.85) -> bool:
    cand_tokens = _token_set(candidate)
    if not cand_tokens:
        return False
    norm_cand = _normalize(candidate)
    for memory in existing:
        norm_mem = _normalize(memory)
        if norm_cand == norm_mem or norm_cand in norm_mem or norm_mem in norm_cand:
            return True
        mem_tokens = _token_set(memory)
        if not mem_tokens:
            continue
        overlap = len(cand_tokens & mem_tokens) / len(cand_tokens | mem_tokens)
        if overlap >= threshold:
            return True
    return False


def _is_trivial_message(text: str) -> bool:
    return len(text) < 3 or bool(_TRIVIAL.match(text.strip()))


def is_system_request(conversation: Sequence[ChatMessage]) -> bool:
    """Detecta requisições internas do cliente (ex: geração de título do LibreChat)."""
    user_messages = [m for m in conversation if m.role == "user"]
    if not user_messages:
        return False
    return bool(_SYSTEM_REQUEST.match(message_text(user_messages[-1])))


def should_skip_mem0_search(conversation: Sequence[ChatMessage]) -> bool:
    """Evita embedder/mem0 em saudações e acks (economia ~1–2 s)."""
    user_messages = [m for m in conversation if m.role == "user"]
    if not user_messages:
        return True
    return _is_trivial_message(message_text(user_messages[-1]))


def normalize_direct_memory_text(text: str) -> str:
    """Texto mais curto e buscável (remove prefixo 'Lembre que…')."""
    stripped = _REMEMBER_PREFIX.sub("", text.strip()).strip()
    stripped = re.sub(r"^[,:;\s]+", "", stripped)
    return stripped or text.strip()


def _is_generic_query(text: str) -> bool:
    return bool(_GENERIC_QUERY.search(text.strip()))


def _has_explicit_remember_request(text: str) -> bool:
    if _RECALL_QUERY.search(text):
        return False
    return bool(_REMEMBER_STORE.search(text))


def _has_personal_fact_signal(text: str) -> bool:
    return bool(_PERSONAL_SIGNAL.search(text))


def _has_commitment_signal(text: str) -> bool:
    return bool(_COMMITMENT_SIGNAL.search(text))


def _looks_like_chain_of_thought(response: str) -> bool:
    return bool(_COT_MARKERS.search(response))


def _recent_user_text(conversation: Sequence[ChatMessage], *, max_messages: int = 3) -> str:
    user_texts = [message_text(m) for m in conversation if m.role == "user" and message_text(m)]
    if not user_texts:
        return ""
    return " ".join(user_texts[-max_messages:])


def should_persist(
    conversation: Sequence[ChatMessage],
    response: str,
    ctx: MemoryPersistContext,
) -> bool:
    """
    Decide se a troca atual deve ser persistida no mem0.

    Critérios: docs/memory-flow.md e docs/orchestration.md.
    """
    _ = ctx.user_id  # contrato: isolamento validado no hook; policy recebe para API estável

    if not conversation:
        return False

    user_messages = [m for m in conversation if m.role == "user"]
    if not user_messages:
        return False

    last_user = message_text(user_messages[-1])
    if not last_user:
        return False

    recent_user = _recent_user_text(conversation)

    if _is_trivial_message(last_user):
        return False

    if _RECALL_QUERY.search(last_user):
        return False

    if _SYSTEM_REQUEST.match(last_user):
        return False

    if _looks_like_chain_of_thought(response):
        return False

    if _is_near_duplicate(last_user, ctx.existing_memory_texts):
        return False

    explicit = _has_explicit_remember_request(recent_user) or _has_explicit_remember_request(
        last_user
    )
    personal = _has_personal_fact_signal(last_user) or _has_personal_fact_signal(recent_user)
    commitment = _has_commitment_signal(last_user)

    if explicit or personal or commitment:
        return True

    if ctx.rag_was_triggered:
        return False

    if _is_generic_query(last_user):
        return False

    if len(last_user) < _MIN_SUBSTANTIVE_LEN:
        return False

    return False


def direct_memory_text(
    conversation: Sequence[ChatMessage],
    ctx: MemoryPersistContext,
) -> str | None:
    """
    Texto para gravar no mem0 com infer=false.

    Evita extração via LLM (Qwen thinking deixa content vazio → JSON inválido).
    """
    _ = ctx.user_id

    if not conversation:
        return None

    user_messages = [m for m in conversation if m.role == "user"]
    if not user_messages:
        return None

    last_user = message_text(user_messages[-1])
    if not last_user or _is_trivial_message(last_user):
        return None

    if _RECALL_QUERY.search(last_user):
        return None

    if _SYSTEM_REQUEST.match(last_user):
        return None

    recent_user = _recent_user_text(conversation)
    explicit = _has_explicit_remember_request(recent_user) or _has_explicit_remember_request(
        last_user
    )
    personal = _has_personal_fact_signal(last_user) or _has_personal_fact_signal(recent_user)

    if not explicit and not personal:
        return None

    if _is_near_duplicate(last_user, ctx.existing_memory_texts):
        return None

    return normalize_direct_memory_text(last_user)
