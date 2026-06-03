"""
LiteLLM Proxy — registro de hooks New_Chat (F4.5).

Único módulo em config/litellm/ que importa litellm.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth

from hooks.llama_fallback import llama_offline_from_failure
from hooks.observability import log_event, request_id_from_metadata
from hooks.post_call import run_post_call
from hooks.pre_call import run_pre_call
from orchestration.user_id import InvalidUserIdError


class NewChatProxyHandler(CustomLogger):
    """Callbacks do proxy: validação X-User-Id + delegação para hooks finos."""

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict[str, Any],
        call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
            "pass_through_endpoint",
            "rerank",
        ],
    ) -> Optional[dict[str, Any]]:
        del user_api_key_dict, cache, call_type
        try:
            return run_pre_call(data)
        except InvalidUserIdError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": str(exc)},
            ) from exc

    async def async_post_call_success_hook(
        self,
        data: dict[str, Any],
        user_api_key_dict: UserAPIKeyAuth,
        response: Any,
    ) -> Any:
        del user_api_key_dict
        return run_post_call(data, response)

    async def async_post_call_failure_hook(
        self,
        request_data: dict[str, Any],
        original_exception: Exception,
        user_api_key_dict: UserAPIKeyAuth,
        traceback_str: Optional[str] = None,
    ) -> Optional[HTTPException]:
        del user_api_key_dict, traceback_str

        meta = request_data.get("metadata")
        request_id = request_id_from_metadata(meta if isinstance(meta, dict) else None)
        if not request_id:
            litellm_id = request_data.get("litellm_call_id")
            if isinstance(litellm_id, str) and litellm_id.strip():
                request_id = litellm_id.strip()

        offline_exc = llama_offline_from_failure(original_exception, request_data)
        if offline_exc is not None:
            log_event(
                "llama_offline",
                request_id=request_id,
                error_type=type(original_exception).__name__,
            )
            return offline_exc

        log_event(
            "inference_failure",
            request_id=request_id,
            error_type=type(original_exception).__name__,
            error=str(original_exception)[:500],
        )
        return None

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """
        Dispara para requests com stream=True (async_post_call_success_hook
        só roda quando stream=False). LiteLLM passa kwargs = model_call_details
        e response_obj = ModelResponse final (montado dos chunks).
        """
        del start_time, end_time

        if not kwargs.get("stream"):
            return

        metadata: dict[str, Any] = {}
        litellm_params = kwargs.get("litellm_params")
        if isinstance(litellm_params, dict):
            md = litellm_params.get("metadata")
            if isinstance(md, dict):
                metadata = md
        if not metadata and isinstance(kwargs.get("metadata"), dict):
            metadata = kwargs["metadata"]

        run_post_call({"metadata": metadata}, response_obj)


proxy_handler_instance = NewChatProxyHandler()
