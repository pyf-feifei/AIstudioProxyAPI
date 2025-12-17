"""
配置页面路由
"""
import os
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ..dependencies import get_logger
from .. import auth_utils
import logging


async def verify_config_page_access(request: Request):
    """验证配置页面的访问权限
    
    如果配置了 API 密钥，则需要提供有效的 API 密钥
    如果没有配置 API 密钥，则允许访问（向后兼容）
    """
    # 如果未配置 API 密钥，允许访问
    auth_utils.initialize_keys()
    if not auth_utils.API_KEYS:
        return True
    
    # 从请求头获取 API 密钥
    api_key = None
    
    # 1. 优先检查标准的 Authorization: Bearer <token> 头
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        api_key = auth_header[7:]  # 移除 "Bearer " 前缀
    
    # 2. 回退到自定义的 X-API-Key 头
    if not api_key:
        api_key = request.headers.get("X-API-Key")
    
    # 验证 API 密钥
    if not api_key or not auth_utils.verify_api_key(api_key):
        # 对于页面访问，返回 401 但允许前端处理登录
        # 前端会显示登录界面
        raise HTTPException(
            status_code=401,
            detail="需要有效的 API 密钥才能访问配置页面"
        )
    
    return True


async def get_config_page(
    request: Request,
    logger: logging.Logger = Depends(get_logger)
):
    """返回配置管理页面
    
    始终返回 HTML 页面，让前端处理登录逻辑
    如果配置了 API 密钥但未提供，前端会显示登录界面
    """
    config_html_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "static", "config.html"
    )
    if not os.path.exists(config_html_path):
        logger.error(f"config.html not found at {config_html_path}")
        raise HTTPException(status_code=404, detail="config.html not found")
    return FileResponse(config_html_path)

