"""
负载均衡器 - 请求分发逻辑
"""
import logging
from typing import Optional

from api_utils.instance_manager import instance_manager, BrowserInstance

logger = logging.getLogger("LoadBalancer")


class LoadBalancer:
    """负载均衡器"""
    
    @staticmethod
    async def get_instance() -> Optional[BrowserInstance]:
        """获取下一个可用的浏览器实例"""
        instance = await instance_manager.get_next_instance()
        if instance:
            logger.debug(f"选择实例: {instance.id} (请求数: {instance.request_count})")
        return instance
    
    @staticmethod
    def mark_request_start(instance: BrowserInstance) -> None:
        """标记请求开始"""
        instance_manager.mark_request_start(instance.id)
    
    @staticmethod
    def mark_request_error(instance: BrowserInstance) -> None:
        """标记请求错误"""
        instance_manager.mark_request_error(instance.id)
    
    @staticmethod
    def get_stats() -> dict:
        """获取负载均衡统计信息"""
        return {
            "strategy": instance_manager.strategy.value,
            "total_instances": len(instance_manager.instances),
            "enabled_instances": len(instance_manager.get_enabled_instances()),
            "instances": instance_manager.get_stats(),
        }


# 全局负载均衡器实例
load_balancer = LoadBalancer()




