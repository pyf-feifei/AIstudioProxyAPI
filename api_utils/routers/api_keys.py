import logging

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..dependencies import get_logger
from .. import auth_utils


class ApiKeyRequest(BaseModel):
    key: str


class ApiKeyTestRequest(BaseModel):
    key: str


async def verify_api_key_access(request: Request):
    """验证 API 密钥管理端点的访问权限
    
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
            detail="需要有效的 API 密钥才能访问此端点。请使用 'Authorization: Bearer <your_key>' 或 'X-API-Key: <your_key>' 头。"
        )
    
    return True


async def get_api_keys(
    request: Request,
    logger: logging.Logger = Depends(get_logger),
    _: bool = Depends(verify_api_key_access)
):
    from .. import auth_utils

    try:
        auth_utils.initialize_keys()
        keys_info = [{"value": key, "status": "有效"} for key in auth_utils.API_KEYS]
        return JSONResponse(
            content={"success": True, "keys": keys_info, "total_count": len(keys_info)}
        )
    except Exception as e:
        logger.error(f"获取API密钥列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def add_api_key(
    http_request: Request,
    request: ApiKeyRequest,
    logger: logging.Logger = Depends(get_logger),
    _: bool = Depends(verify_api_key_access)
):
    from .. import auth_utils

    key_value = request.key.strip()
    if not key_value or len(key_value) < 8:
        raise HTTPException(status_code=400, detail="无效的API密钥格式。")

    auth_utils.initialize_keys()
    if key_value in auth_utils.API_KEYS:
        raise HTTPException(status_code=400, detail="该API密钥已存在。")

    try:
        key_file_path = auth_utils.KEY_FILE_PATH
        with open(key_file_path, "a+", encoding="utf-8") as f:
            f.seek(0)
            if f.read():
                f.write("\n")
            f.write(key_value)

        auth_utils.initialize_keys()
        logger.info(f"API密钥已添加: {key_value[:4]}...{key_value[-4:]}")
        return JSONResponse(
            content={
                "success": True,
                "message": "API密钥添加成功",
                "key_count": len(auth_utils.API_KEYS),
            }
        )
    except Exception as e:
        logger.error(f"添加API密钥失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def test_api_key(
    request: ApiKeyTestRequest, logger: logging.Logger = Depends(get_logger)
):
    from .. import auth_utils

    key_value = request.key.strip()
    if not key_value:
        raise HTTPException(status_code=400, detail="API密钥不能为空。")

    auth_utils.initialize_keys()
    is_valid = auth_utils.verify_api_key(key_value)
    logger.info(
        f"API密钥测试: {key_value[:4]}...{key_value[-4:]} - {'有效' if is_valid else '无效'}"
    )
    return JSONResponse(
        content={
            "success": True,
            "valid": is_valid,
            "message": "密钥有效" if is_valid else "密钥无效或不存在",
        }
    )


async def delete_api_key(
    http_request: Request,
    request: ApiKeyRequest,
    logger: logging.Logger = Depends(get_logger),
    _: bool = Depends(verify_api_key_access)
):
    from .. import auth_utils

    key_value = request.key.strip()
    if not key_value:
        raise HTTPException(status_code=400, detail="API密钥不能为空。")

    auth_utils.initialize_keys()
    if key_value not in auth_utils.API_KEYS:
        raise HTTPException(status_code=404, detail="API密钥不存在。")

    try:
        key_file_path = auth_utils.KEY_FILE_PATH
        with open(key_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        with open(key_file_path, "w", encoding="utf-8") as f:
            f.writelines(line for line in lines if line.strip() != key_value)

        auth_utils.initialize_keys()
        logger.info(f"API密钥已删除: {key_value[:4]}...{key_value[-4:]}")
        return JSONResponse(
            content={
                "success": True,
                "message": "API密钥删除成功",
                "key_count": len(auth_utils.API_KEYS),
            }
        )
    except Exception as e:
        logger.error(f"删除API密钥失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
