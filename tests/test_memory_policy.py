"""Testes da memory_policy (pytest puro, sem HTTP/LiteLLM)."""

import pytest

from orchestration.memory_policy import (
    MemoryPersistContext,
    direct_memory_text,
    message_text,
    normalize_direct_memory_text,
    should_persist,
    should_skip_mem0_search,
)
from orchestration.types import ChatMessage


def _ctx(**kwargs: object) -> MemoryPersistContext:
    return MemoryPersistContext(user_id="jean", **kwargs)  # type: ignore[arg-type]


def _user(content: str) -> ChatMessage:
    return ChatMessage(role="user", content=content)


def _assistant(content: str) -> ChatMessage:
    return ChatMessage(role="assistant", content=content)


def test_message_text_plain_string() -> None:
    assert message_text(ChatMessage(role="user", content="  olá  ")) == "olá"


def test_message_text_multimodal_parts() -> None:
    msg = ChatMessage(
        role="user",
        content=[
            {"type": "text", "text": "descreva"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}},
        ],
    )
    assert message_text(msg) == "descreva"


@pytest.mark.parametrize(
    "content",
    [
        "O que é Python?",
        "Como funciona o asyncio?",
        "Explique a teoria da relatividade",
    ],
)
def test_should_not_persist_generic_questions(content: str) -> None:
    conv = [_user(content)]
    assert should_persist(conv, "Python é uma linguagem...", _ctx()) is False


@pytest.mark.parametrize(
    "content",
    ["oi", "Olá!", "obrigado", "ok"],
)
def test_should_not_persist_trivial_messages(content: str) -> None:
    conv = [_user(content)]
    assert should_persist(conv, "Olá! Como posso ajudar?", _ctx()) is False


def test_should_persist_explicit_remember_request() -> None:
    conv = [_user("Lembra que eu prefiro respostas curtas")]
    assert should_persist(conv, "Anotado, vou ser breve.", _ctx()) is True


def test_should_persist_lembre_se_disso() -> None:
    conv = [_user("Eu gosto muito da minha esposa (Tatiane)! Lembre-se disso.")]
    assert should_persist(conv, "Combinado!", _ctx()) is True


def test_should_persist_lembre_disso_sem_hifen() -> None:
    conv = [_user("Meu time favorito é o Atletico! Lembre disso.")]
    assert should_persist(conv, "Anotado!", _ctx()) is True


def test_should_persist_lembre_isso() -> None:
    conv = [_user("Prefiro dark mode sempre. Lembre isso.")]
    assert should_persist(conv, "Ok!", _ctx()) is True


@pytest.mark.parametrize(
    "content",
    [
        "Salva isso: meu time é o Atlético",
        "Guarda na memória que nasci em 1992",
        "Anota aí que meu nome é Jean",
        "Registra isso: minha esposa é Tatiane",
        "Arquiva na memória que trabalho como engenheiro",
        "Grava na memória que tenho 33 anos",
    ],
)
def test_should_persist_remember_variants_pt_br(content: str) -> None:
    conv = [_user(content)]
    assert should_persist(conv, "Anotado!", _ctx()) is True


@pytest.mark.parametrize(
    "content",
    [
        "Sou o Jean",
        "Trabalho como engenheiro em São Paulo",
        "Moro em Curitiba",
        "Nasci em 1992",
        "Tenho 33 anos",
        "Gosto de café",
    ],
)
def test_should_persist_personal_fact_without_remember_verb(content: str) -> None:
    conv = [_user(content)]
    assert should_persist(conv, "Ok!", _ctx()) is True


def test_should_persist_birth_date_lembre_se() -> None:
    conv = [_user("Lembre-se que eu nasci em 01/08/1992")]
    assert should_persist(conv, "Entendido. Sua data de nascimento foi registrada.", _ctx()) is True


def test_should_persist_wedding_date() -> None:
    conv = [_user("Nós nos casamos no dia 20/09/2014")]
    assert should_persist(conv, "Guardado com carinho!", _ctx()) is True


def test_should_persist_personal_preference() -> None:
    conv = [_user("Eu gosto de café sem açúcar")]
    assert should_persist(conv, "Entendido!", _ctx()) is True


def test_should_persist_commitment() -> None:
    conv = [_user("Tenho reunião amanhã às 10h com o time")]
    assert should_persist(conv, "Boa reunião!", _ctx()) is True


def test_should_not_persist_when_user_asks_birth_date() -> None:
    conv = [_user("Quando eu nasci?")]
    assert should_persist(conv, "Nao sei ainda...", _ctx()) is False


def test_should_not_persist_recall_query_without_new_fact() -> None:
    conv = [_user("O que você sabe sobre mim?")]
    assert should_persist(conv, "Você mencionou café...", _ctx()) is False


def test_should_not_persist_when_rag_only_turn() -> None:
    conv = [_user("Resuma o capítulo 3 do PDF sobre finanças")]
    assert (
        should_persist(
            conv,
            "O capítulo trata de...",
            _ctx(rag_was_triggered=True),
        )
        is False
    )


def test_should_persist_personal_fact_even_when_rag_triggered() -> None:
    conv = [_user("Eu trabalho como engenheiro e preciso do trecho do manual")]
    assert (
        should_persist(
            conv,
            "Segue o trecho...",
            _ctx(rag_was_triggered=True),
        )
        is True
    )


# ---------------------------------------------------------------------------
# _SYSTEM_REQUEST filter — LibreChat title generation must not be persisted
# ---------------------------------------------------------------------------

_LIBRECHAT_TITLE_PROMPT = (
    "Provide a concise, 5-word-or-less title for the conversation, "
    "using title case conventions. Only return the title itself.\n\n"
    "Conversation:\nUser: Lembre disso: meu nome é Tatiane\nAI: User Name Is Tatiane"
)


def test_is_system_request_title_generation() -> None:
    from orchestration.memory_policy import is_system_request

    assert is_system_request([_user(_LIBRECHAT_TITLE_PROMPT)]) is True


def test_is_system_request_normal_message_false() -> None:
    from orchestration.memory_policy import is_system_request

    assert is_system_request([_user("Lembre que meu nome é Jean")]) is False


def test_is_system_request_empty_conversation() -> None:
    from orchestration.memory_policy import is_system_request

    assert is_system_request([]) is False


def test_should_not_persist_librechat_title_prompt() -> None:
    conv = [_user(_LIBRECHAT_TITLE_PROMPT)]
    assert should_persist(conv, "User Name Is Tatiane", _ctx()) is False


def test_direct_memory_text_skips_librechat_title_prompt() -> None:
    conv = [_user(_LIBRECHAT_TITLE_PROMPT)]
    assert direct_memory_text(conv, _ctx()) is None


def test_should_not_persist_chain_of_thought_response() -> None:
    conv = [_user("Eu prefiro Python")]
    response = "passo a passo:\n1. analisar preferência\nResposta final."
    assert should_persist(conv, response, _ctx()) is False


def test_should_not_persist_near_duplicate_memory() -> None:
    conv = [_user("Eu prefiro café sem açúcar")]
    existing = ("Prefiro cafe sem acucar",)
    assert should_persist(conv, "Ok!", _ctx(existing_memory_texts=existing)) is False


def test_should_not_persist_empty_conversation() -> None:
    assert should_persist([], "resposta", _ctx()) is False


def test_should_not_persist_assistant_only_conversation() -> None:
    conv = [_assistant("Olá, como posso ajudar?")]
    assert should_persist(conv, "Mais alguma coisa?", _ctx()) is False


def test_direct_memory_text_explicit_remember_mother() -> None:
    text = "Lembre que o nome de minha mãe é Gertrudes"
    conv = [_user(text)]
    assert direct_memory_text(conv, _ctx()) == "o nome de minha mãe é Gertrudes"


def test_normalize_direct_memory_text_strips_remember_prefix() -> None:
    assert (
        normalize_direct_memory_text("Lembre que o nome de minha mãe é Gertrudes")
        == "o nome de minha mãe é Gertrudes"
    )


def test_normalize_direct_memory_text_lembre_disso_com_dois_pontos() -> None:
    assert normalize_direct_memory_text("Lembre disso: meu nome é Jean") == "meu nome é Jean"


def test_normalize_direct_memory_text_lembre_isso_com_virgula() -> None:
    assert normalize_direct_memory_text("Lembre isso, prefiro Python") == "prefiro Python"


def test_normalize_direct_memory_text_lembre_se_disso_com_virgula() -> None:
    assert normalize_direct_memory_text("Lembre-se disso, gosto de café") == "gosto de café"


@pytest.mark.parametrize("content", ["oi", "obrigado", "ok"])
def test_should_skip_mem0_search_on_trivial(content: str) -> None:
    assert should_skip_mem0_search([_user(content)]) is True


def test_should_not_skip_mem0_search_on_recall() -> None:
    assert should_skip_mem0_search([_user("Qual o nome de minha mãe?")]) is False


def test_direct_memory_text_skips_recall_query() -> None:
    conv = [_user("O que você sabe sobre mim?")]
    assert direct_memory_text(conv, _ctx()) is None


def test_direct_memory_text_skips_duplicate() -> None:
    conv = [_user("Lembre que o nome de minha mãe é Gertrudes")]
    existing = ("Lembre que o nome de minha mae e Gertrudes",)
    assert direct_memory_text(conv, _ctx(existing_memory_texts=existing)) is None
