"""
多实例初始化逻辑
"""
import asyncio
import logging
import os
import glob
from typing import List, Optional

from playwright.async_api import Browser as AsyncBrowser

from api_utils.instance_manager import BrowserInstance, instance_manager
from browser_utils.initialization.core import (
    initialize_page_logic,
    enable_temporary_chat_mode,
)
from browser_utils.model_management import _handle_initial_model_state_and_storage
from launcher.config import SAVED_AUTH_DIR, ACTIVE_AUTH_DIR

logger = logging.getLogger("MultiInstanceInit")


async def initialize_multiple_browsers(
    playwright_manager,
    auth_files: Optional[List[str]] = None,
    base_port: int = 9222,
) -> bool:
    """
    初始化多个浏览器实例
    
    Args:
        playwright_manager: Playwright 管理器
        auth_files: 认证文件列表，如果为 None 则从 saved 目录读取
        base_port: 基础端口号，每个实例端口递增
    
    Returns:
        是否成功初始化至少一个实例
    """
    if auth_files is None:
        # 多实例模式：优先从 saved 目录读取所有认证文件
        # saved/ 目录是所有认证文件的存储库（主要来源）
        # active/ 目录是单实例模式的激活文件，多实例模式也会读取以兼容
        auth_files = []
        seen_basenames = set()  # 用于去重
        
        # 优先从 saved 目录读取（主要来源）
        if os.path.exists(SAVED_AUTH_DIR):
            pattern = os.path.join(SAVED_AUTH_DIR, "*.json")
            files = glob.glob(pattern)
            auth_files.extend(files)
            seen_basenames.update(os.path.basename(f) for f in files)
            logger.info(f"从 saved/ 目录找到 {len(files)} 个认证文件")
        
        # 也从 active 目录读取（兼容单实例模式）
        if os.path.exists(ACTIVE_AUTH_DIR):
            pattern = os.path.join(ACTIVE_AUTH_DIR, "*.json")
            files = glob.glob(pattern)
            # 避免重复（如果 active 中的文件也在 saved 中）
            for f in files:
                if os.path.basename(f) not in seen_basenames:
                    auth_files.append(f)
                    seen_basenames.add(os.path.basename(f))
            logger.info(f"从 active/ 目录找到 {len(files)} 个认证文件（去重后）")
        
        if not auth_files:
            logger.warning("未找到认证文件，使用单实例模式")
            return False
    
    logger.info(f"开始初始化 {len(auth_files)} 个浏览器实例...")
    
    # 检查是否启用多实例模式
    use_multi_instance = os.environ.get("ENABLE_MULTI_INSTANCE", "false").lower() == "true"
    if not use_multi_instance and len(auth_files) > 1:
        logger.info("多实例模式未启用，仅使用第一个认证文件")
        auth_files = auth_files[:1]
    
    success_count = 0
    
    for idx, auth_file in enumerate(auth_files):
        if not os.path.exists(auth_file):
            logger.warning(f"认证文件不存在: {auth_file}")
            continue
        
        instance_id = f"instance_{idx}"
        port = base_port + idx
        
        try:
            # 注意：当前实现使用同一个 WebSocket 端点
            # 真正的多实例需要启动多个 Camoufox 进程，每个使用不同的端口和认证文件
            # 这里先实现简化版本：使用同一个浏览器实例，但支持不同的认证文件切换
            ws_endpoint = os.environ.get("CAMOUFOX_WS_ENDPOINT")
            
            if not ws_endpoint:
                logger.warning(f"实例 {instance_id} 缺少 WebSocket 端点，跳过")
                continue
            
            # 对于简化版本，我们使用同一个浏览器实例，但记录不同的认证文件
            # 这样可以在错误恢复时切换到不同的认证文件
            
            logger.info(f"连接实例 {instance_id} (端口: {port}, 认证: {os.path.basename(auth_file)})")
            
            # 连接到浏览器
            browser = await playwright_manager.firefox.connect(ws_endpoint, timeout=30000)
            logger.info(f"实例 {instance_id} 浏览器连接成功")
            
            # 初始化页面
            page, is_ready = await initialize_page_logic(
                browser,
                storage_state_path=auth_file,
            )
            
            if is_ready:
                await _handle_initial_model_state_and_storage(page)
                await enable_temporary_chat_mode(page)
                
                # 创建实例对象
                instance = BrowserInstance(
                    id=instance_id,
                    auth_file=auth_file,
                    browser=browser,
                    page=page,
                    ws_endpoint=ws_endpoint,
                    port=port,
                    is_ready=True,
                )
                
                instance_manager.add_instance(instance)
                success_count += 1
                logger.info(f"实例 {instance_id} 初始化成功")
            else:
                logger.error(f"实例 {instance_id} 页面初始化失败")
                await browser.close()
        
        except Exception as e:
            logger.error(f"初始化实例 {instance_id} 时出错: {e}", exc_info=True)
    
    if success_count > 0:
        logger.info(f"成功初始化 {success_count}/{len(auth_files)} 个浏览器实例")
        return True
    else:
        logger.error("未能初始化任何浏览器实例")
        return False


async def initialize_single_browser_fallback(
    playwright_manager,
    auth_file: Optional[str] = None,
) -> bool:
    """
    单实例回退初始化（向后兼容）
    """
    from api_utils.app import _initialize_page_logic
    
    ws_endpoint = os.environ.get("CAMOUFOX_WS_ENDPOINT")
    if not ws_endpoint:
        logger.warning("未找到 WebSocket 端点，无法初始化浏览器")
        return False
    
    try:
        browser = await playwright_manager.firefox.connect(ws_endpoint, timeout=30000)
        page, is_ready = await _initialize_page_logic(browser)
        
        if is_ready:
            # 创建单实例对象用于兼容
            instance = BrowserInstance(
                id="default",
                auth_file=auth_file or "",
                browser=browser,
                page=page,
                ws_endpoint=ws_endpoint,
                port=int(os.environ.get("DEFAULT_CAMOUFOX_PORT", "9222")),
                is_ready=True,
            )
            instance_manager.add_instance(instance)
            return True
    except Exception as e:
        logger.error(f"单实例初始化失败: {e}", exc_info=True)
    
    return False

