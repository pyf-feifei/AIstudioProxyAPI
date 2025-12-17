"""
测试负载均衡功能
"""
import pytest
import asyncio
from api_utils.instance_manager import (
    MultiInstanceManager,
    BrowserInstance,
    LoadBalanceStrategy,
)
from api_utils.load_balancer import LoadBalancer


@pytest.fixture
def mock_browser():
    """模拟浏览器对象"""
    class MockBrowser:
        def __init__(self):
            self.version = "test"
    
    return MockBrowser()


@pytest.fixture
def mock_page():
    """模拟页面对象"""
    class MockPage:
        pass
    
    return MockPage()


@pytest.fixture
def instance_manager():
    """创建实例管理器"""
    return MultiInstanceManager()


@pytest.mark.asyncio
async def test_round_robin_strategy(instance_manager, mock_browser, mock_page):
    """测试轮询策略"""
    instance_manager.set_strategy(LoadBalanceStrategy.ROUND_ROBIN)
    
    # 添加3个实例
    for i in range(3):
        instance = BrowserInstance(
            id=f"instance_{i}",
            auth_file=f"auth_{i}.json",
            browser=mock_browser,
            page=mock_page,
            is_ready=True,
        )
        instance_manager.add_instance(instance)
    
    # 测试轮询
    instances = []
    for _ in range(6):
        inst = await instance_manager.get_next_instance()
        instances.append(inst.id)
    
    # 应该按顺序轮询
    assert instances == [
        "instance_0", "instance_1", "instance_2",
        "instance_0", "instance_1", "instance_2"
    ]


@pytest.mark.asyncio
async def test_least_connections_strategy(instance_manager, mock_browser, mock_page):
    """测试最少连接策略"""
    instance_manager.set_strategy(LoadBalanceStrategy.LEAST_CONNECTIONS)
    
    # 添加3个实例，设置不同的请求数
    for i in range(3):
        instance = BrowserInstance(
            id=f"instance_{i}",
            auth_file=f"auth_{i}.json",
            browser=mock_browser,
            page=mock_page,
            is_ready=True,
            request_count=i,  # 实例0请求数最少
        )
        instance_manager.add_instance(instance)
    
    # 应该选择请求数最少的实例
    instance = await instance_manager.get_next_instance()
    assert instance.id == "instance_0"
    assert instance.request_count == 0


@pytest.mark.asyncio
async def test_enabled_instances_only(instance_manager, mock_browser, mock_page):
    """测试只返回启用的实例"""
    # 添加3个实例，禁用其中一个
    for i in range(3):
        instance = BrowserInstance(
            id=f"instance_{i}",
            auth_file=f"auth_{i}.json",
            browser=mock_browser,
            page=mock_page,
            is_ready=True,
            enabled=(i != 1),  # 禁用实例1
        )
        instance_manager.add_instance(instance)
    
    enabled = instance_manager.get_enabled_instances()
    assert len(enabled) == 2
    assert all(inst.id != "instance_1" for inst in enabled)


@pytest.mark.asyncio
async def test_load_balancer_integration():
    """测试负载均衡器集成"""
    from api_utils.instance_manager import instance_manager
    
    # 重置管理器
    instance_manager.instances.clear()
    instance_manager.current_index = 0
    
    # 添加测试实例
    class MockBrowser:
        pass
    
    class MockPage:
        pass
    
    instance = BrowserInstance(
        id="test_instance",
        auth_file="test.json",
        browser=MockBrowser(),
        page=MockPage(),
        is_ready=True,
    )
    instance_manager.add_instance(instance)
    
    # 测试获取实例
    balancer = LoadBalancer()
    inst = await balancer.get_instance()
    assert inst is not None
    assert inst.id == "test_instance"
    
    # 测试标记请求
    balancer.mark_request_start(inst)
    assert inst.request_count == 1
    
    # 测试获取统计
    stats = balancer.get_stats()
    assert stats["total_instances"] == 1
    assert stats["enabled_instances"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




