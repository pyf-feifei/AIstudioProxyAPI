from typing import cast

from logging_utils import set_request_id
from models import ChatCompletionRequest

from .context_types import RequestContext


async def initialize_request_context(
    req_id: str, request: ChatCompletionRequest
) -> RequestContext:
    from api_utils.server_state import state
    from api_utils.load_balancer import load_balancer

    set_request_id(req_id)
    state.logger.info("开始处理请求...")
    state.logger.info(f"  请求参数 - Model: {request.model}, Stream: {request.stream}")

    # 尝试使用负载均衡器获取实例
    instance = await load_balancer.get_instance()
    if instance and instance.page:
        # 使用负载均衡选择的实例
        page_instance = instance.page
        is_page_ready = instance.is_ready
        load_balancer.mark_request_start(instance)
        state.logger.debug(f"使用负载均衡实例: {instance.id}")
    else:
        # 回退到单实例模式
        page_instance = state.page_instance
        is_page_ready = state.is_page_ready
        state.logger.debug("使用默认单实例")

    context: RequestContext = cast(
        RequestContext,
        {
            "logger": state.logger,
            "page": page_instance,
            "is_page_ready": is_page_ready,
            "parsed_model_list": state.parsed_model_list,
            "current_ai_studio_model_id": state.current_ai_studio_model_id,
            "model_switching_lock": state.model_switching_lock,
            "page_params_cache": state.page_params_cache,
            "params_cache_lock": state.params_cache_lock,
            "is_streaming": request.stream,
            "model_actually_switched": False,
            "requested_model": request.model,
            "model_id_to_use": None,
            "needs_model_switching": False,
        },
    )

    return context
