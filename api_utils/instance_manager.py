"""
多实例管理器 - 管理多个浏览器实例和负载均衡
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from playwright.async_api import Browser as AsyncBrowser, Page as AsyncPage

logger = logging.getLogger("InstanceManager")


class LoadBalanceStrategy(str, Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"  # 轮询
    RANDOM = "random"  # 随机
    LEAST_CONNECTIONS = "least_connections"  # 最少连接


@dataclass
class BrowserInstance:
    """浏览器实例信息"""
    id: str
    auth_file: str
    browser: AsyncBrowser
    page: Optional[AsyncPage] = None
    ws_endpoint: str = ""
    port: int = 0
    is_ready: bool = False
    request_count: int = 0
    error_count: int = 0
    enabled: bool = True
    last_used: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class MultiInstanceManager:
    """多实例管理器"""
    
    def __init__(self, strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN):
        self.instances: Dict[str, BrowserInstance] = {}
        self.strategy = strategy
        self.current_index = 0
        self.lock = asyncio.Lock()
    
    def add_instance(self, instance: BrowserInstance) -> None:
        """添加浏览器实例"""
        self.instances[instance.id] = instance
        logger.info(f"添加浏览器实例: {instance.id} (认证文件: {os.path.basename(instance.auth_file)})")
    
    def remove_instance(self, instance_id: str) -> None:
        """移除浏览器实例"""
        if instance_id in self.instances:
            del self.instances[instance_id]
            logger.info(f"移除浏览器实例: {instance_id}")
    
    def get_enabled_instances(self) -> List[BrowserInstance]:
        """获取所有启用的实例"""
        return [inst for inst in self.instances.values() if inst.enabled and inst.is_ready]
    
    async def get_next_instance(self) -> Optional[BrowserInstance]:
        """根据策略获取下一个可用实例"""
        async with self.lock:
            enabled = self.get_enabled_instances()
            if not enabled:
                logger.warning("没有可用的浏览器实例")
                return None
            
            if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
                instance = enabled[self.current_index % len(enabled)]
                self.current_index = (self.current_index + 1) % len(enabled)
                return instance
            
            elif self.strategy == LoadBalanceStrategy.RANDOM:
                import random
                return random.choice(enabled)
            
            elif self.strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
                return min(enabled, key=lambda x: x.request_count)
            
            return enabled[0] if enabled else None
    
    def mark_request_start(self, instance_id: str) -> None:
        """标记请求开始"""
        if instance_id in self.instances:
            self.instances[instance_id].request_count += 1
            self.instances[instance_id].last_used = asyncio.get_event_loop().time()
    
    def mark_request_error(self, instance_id: str) -> None:
        """标记请求错误"""
        if instance_id in self.instances:
            self.instances[instance_id].error_count += 1
    
    def get_stats(self) -> Dict[str, Dict[str, any]]:
        """获取所有实例的统计信息"""
        return {
            instance_id: {
                "id": inst.id,
                "auth_file": os.path.basename(inst.auth_file),
                "is_ready": inst.is_ready,
                "enabled": inst.enabled,
                "request_count": inst.request_count,
                "error_count": inst.error_count,
                "port": inst.port,
            }
            for instance_id, inst in self.instances.items()
        }
    
    def set_strategy(self, strategy: LoadBalanceStrategy) -> None:
        """设置负载均衡策略"""
        self.strategy = strategy
        logger.info(f"负载均衡策略已更改为: {strategy.value}")
    
    def enable_instance(self, instance_id: str, enabled: bool) -> None:
        """启用/禁用实例"""
        if instance_id in self.instances:
            self.instances[instance_id].enabled = enabled
            logger.info(f"实例 {instance_id} 已{'启用' if enabled else '禁用'}")


# 全局实例管理器
instance_manager = MultiInstanceManager()




