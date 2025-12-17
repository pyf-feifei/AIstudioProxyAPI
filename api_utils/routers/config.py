"""
配置管理 API - 认证文件和负载均衡配置
"""
import logging
import os
import glob
import json
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from pydantic import BaseModel

from api_utils.instance_manager import instance_manager, LoadBalanceStrategy
from launcher.config import SAVED_AUTH_DIR, ACTIVE_AUTH_DIR
from .. import auth_utils

logger = logging.getLogger("ConfigAPI")

router = APIRouter(prefix="/api/config", tags=["config"])


async def verify_config_access(request: Request):
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
        raise HTTPException(
            status_code=401,
            detail="需要有效的 API 密钥才能访问配置页面。请使用 'Authorization: Bearer <your_key>' 或 'X-API-Key: <your_key>' 头。"
        )
    
    return True


class AuthFileInfo(BaseModel):
    """认证文件信息"""
    filename: str
    path: str
    size: int
    enabled: bool = True


class LoadBalanceConfig(BaseModel):
    """负载均衡配置"""
    strategy: str
    enabled_instances: int
    total_instances: int


class InstanceStats(BaseModel):
    """实例统计信息"""
    id: str
    auth_file: str
    is_ready: bool
    enabled: bool
    request_count: int
    error_count: int
    port: int


@router.get("/auth-files", response_model=List[AuthFileInfo])
async def list_auth_files(_: bool = Depends(verify_config_access)):
    """列出所有认证文件
    
    返回 saved/ 和 active/ 目录中的所有认证文件
    - saved/ 目录：所有认证文件的存储库（主要来源）
    - active/ 目录：单实例模式的激活文件
    """
    auth_files = []
    seen_basenames = set()  # 用于去重
    
    # 优先列出 saved 目录中的文件（主要来源）
    if os.path.exists(SAVED_AUTH_DIR):
        pattern = os.path.join(SAVED_AUTH_DIR, "*.json")
        for file_path in glob.glob(pattern):
            try:
                basename = os.path.basename(file_path)
                if basename not in seen_basenames:
                    stat = os.stat(file_path)
                    auth_files.append({
                        "filename": basename,
                        "path": file_path,
                        "size": stat.st_size,
                        "enabled": True,
                    })
                    seen_basenames.add(basename)
            except Exception as e:
                logger.warning(f"读取认证文件信息失败 {file_path}: {e}")
    
    # 也列出 active 目录中的文件（如果不在 saved 中）
    if os.path.exists(ACTIVE_AUTH_DIR):
        pattern = os.path.join(ACTIVE_AUTH_DIR, "*.json")
        for file_path in glob.glob(pattern):
            try:
                basename = os.path.basename(file_path)
                if basename not in seen_basenames:
                    stat = os.stat(file_path)
                    auth_files.append({
                        "filename": basename,
                        "path": file_path,
                        "size": stat.st_size,
                        "enabled": True,
                    })
                    seen_basenames.add(basename)
            except Exception as e:
                logger.warning(f"读取认证文件信息失败 {file_path}: {e}")
    
    return auth_files


@router.post("/auth-files/upload")
async def upload_auth_file(file: UploadFile = File(...), _: bool = Depends(verify_config_access)):
    """上传认证文件"""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="文件必须是 JSON 格式")
    
    try:
        content = await file.read()
        # 验证 JSON 格式
        json.loads(content.decode("utf-8"))
        
        # 保存到 saved 目录
        os.makedirs(SAVED_AUTH_DIR, exist_ok=True)
        file_path = os.path.join(SAVED_AUTH_DIR, file.filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"认证文件已上传: {file.filename}")
        return {"message": "文件上传成功", "path": file_path}
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 JSON 文件")
    except Exception as e:
        logger.error(f"上传认证文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.delete("/auth-files/{filename}")
async def delete_auth_file(filename: str, _: bool = Depends(verify_config_access)):
    """删除认证文件"""
    # 安全检查：只允许删除 saved 目录下的文件
    file_path = os.path.join(SAVED_AUTH_DIR, filename)
    
    if not file_path.startswith(os.path.abspath(SAVED_AUTH_DIR)):
        raise HTTPException(status_code=403, detail="不允许删除此文件")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        os.remove(file_path)
        logger.info(f"认证文件已删除: {filename}")
        return {"message": "文件删除成功"}
    except Exception as e:
        logger.error(f"删除认证文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/load-balance", response_model=LoadBalanceConfig)
async def get_load_balance_config(_: bool = Depends(verify_config_access)):
    """获取负载均衡配置"""
    enabled = instance_manager.get_enabled_instances()
    return {
        "strategy": instance_manager.strategy.value,
        "enabled_instances": len(enabled),
        "total_instances": len(instance_manager.instances),
    }


@router.post("/load-balance/strategy")
async def set_load_balance_strategy(request: dict, _: bool = Depends(verify_config_access)):
    """设置负载均衡策略"""
    strategy = request.get("strategy")
    if not strategy:
        raise HTTPException(status_code=400, detail="缺少 strategy 参数")
    try:
        strategy_enum = LoadBalanceStrategy(strategy)
        instance_manager.set_strategy(strategy_enum)
        return {"message": f"负载均衡策略已设置为: {strategy}"}
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的策略: {strategy}。可选值: {[s.value for s in LoadBalanceStrategy]}"
        )


@router.get("/instances", response_model=List[InstanceStats])
async def list_instances(_: bool = Depends(verify_config_access)):
    """列出所有实例及其统计信息"""
    stats = instance_manager.get_stats()
    return list(stats.values())


@router.post("/instances/{instance_id}/enable")
async def enable_instance(instance_id: str, enabled: bool = True, _: bool = Depends(verify_config_access)):
    """启用/禁用实例"""
    instance_manager.enable_instance(instance_id, enabled)
    return {"message": f"实例 {instance_id} 已{'启用' if enabled else '禁用'}"}


@router.get("/stats")
async def get_stats(_: bool = Depends(verify_config_access)):
    """获取详细统计信息"""
    return {
        "load_balance": {
            "strategy": instance_manager.strategy.value,
            "total_instances": len(instance_manager.instances),
            "enabled_instances": len(instance_manager.get_enabled_instances()),
        },
        "instances": instance_manager.get_stats(),
        "auth_files": await list_auth_files(),
    }

