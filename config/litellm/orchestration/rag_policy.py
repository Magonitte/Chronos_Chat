"""Política de acionamento de RAG — sem HTTP, lógica pura (ADR 002)."""

from __future__ import annotations

import re

from orchestration.types import UserContext

# Frases e padrões estruturados (referência a documentos / pedido explícito).
# Não usar keywords soltas de tópico (ex.: "receita", "python").
_DOCUMENT_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bnos?\s+meus\s+documentos\b",
        r"\bno\s+(?:meu\s+)?(?:pdf|livro|documento|arquivo|ebook|epub)\b",
        r"\bna\s+(?:minha\s+)?(?:pasta|biblioteca|coleção)\b",
        r"\bbuscar\s+(?:nos?\s+)?(?:meus\s+)?documentos\b",
        r"\bconsultar\s+(?:o\s+)?(?:pdf|livro|documento|arquivo)\b",
        r"\bsegundo\s+o\s+(?:pdf|livro|documento)\b",
        r"\bde\s+acordo\s+com\s+o\s+(?:pdf|livro|documento)\b",
        r"\bo\s+que\s+diz\s+o\s+(?:pdf|livro|documento)\b",
        r"\b\w[\w\-.]*\.(?:pdf|epub|txt|md)\b",
    )
)

_EXPLICIT_RAG_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:use|usar|ativar)\s+(?:o\s+)?rag\b",
        r"\bbuscar\s+nos?\s+documentos\b",
        r"\bpesquisar\s+nos?\s+documentos\b",
    )
)


def has_document_reference(query: str) -> bool:
    """Detecta referência explícita a documentos (frases compostas, não keyword de tópico)."""
    text = query.strip()
    if not text:
        return False
    return any(
        pattern.search(text)
        for pattern in (*_DOCUMENT_REFERENCE_PATTERNS, *_EXPLICIT_RAG_REQUEST_PATTERNS)
    )


def should_trigger(query: str, ctx: UserContext) -> bool:
    """Decide se o PRE-CALL deve chamar rag_client.retrieve."""
    if not ctx.rag_enabled:
        return False
    if ctx.active_workspace:
        return True
    if has_document_reference(query):
        return True
    return False
