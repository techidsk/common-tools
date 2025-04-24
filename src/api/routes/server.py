from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from loguru import logger
from datetime import time, datetime

from src.api.database import get_db
from src.api.crud import ServerCRUD
from src.api.models.workflow import ServerConfig, ServerCreate, ServerUpdate
from src.api.models.database import ServerStatus
from src.api.server_manager import server_manager

router = APIRouter(
    prefix="/servers",
    tags=["servers"]
)

@router.post("/register", response_model=ServerConfig)
async def create_server(
    server_data: ServerCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建服务器
    
    根据API文档, POST /servers/register 负责注册新的服务器节点
    """
    try:
        # 检查服务器名称是否已存在
        existing_server = await ServerCRUD.get_server_by_name(db, server_data.name)
        if existing_server:
            logger.warning(f"Server with name {server_data.name} already exists")
            raise HTTPException(
                status_code=409, 
                detail=f"服务器名称已存在: {server_data.name}"
            )
        
        # 检查服务器URL是否有效
        if not server_data.url or not server_data.url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400, 
                detail="服务器URL必须是有效的HTTP/HTTPS URL"
            )
            
        # 检查batch_size是否大于0
        if server_data.batch_size <= 0:
            raise HTTPException(
                status_code=400, 
                detail="batch_size 必须大于0"
            )
            
        # 创建服务器
        server = await ServerCRUD.create_server(db, server_data)
        logger.info(f"Created new server: {server.name} ({server.url})")
        return server
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"Failed to create server: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ServerConfig])
async def list_servers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    获取服务器列表
    
    根据API文档, GET /servers 返回所有已注册的服务器列表
    """
    try:
        servers = await ServerCRUD.list_servers(db, skip, limit)
        return servers
    except Exception as e:
        logger.error(f"Failed to list servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{server_id}", response_model=ServerConfig)
async def get_server(
    server_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取服务器详情"""
    server = await ServerCRUD.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@router.put("/{server_id}", response_model=ServerConfig)
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新服务器"""
    server = await ServerCRUD.update_server(db, server_id, server_data)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除服务器"""
    success = await ServerCRUD.delete_server(db, server_id)
    if not success:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"message": "Server deleted successfully"}

@router.put("/{server_id}/status", response_model=ServerConfig)
async def update_server_status(
    server_id: int,
    status: ServerStatus,
    db: AsyncSession = Depends(get_db)
):
    """更新服务器状态"""
    server = await ServerCRUD.update_server_status(db, server_id, status)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@router.get("/{server_id}/health")
async def check_server_health(server_id: int):
    """检查服务器健康状态"""
    server = await server_manager.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    try:
        is_healthy = await server_manager.check_server_health(server)
        return {"status": "healthy" if is_healthy else "unhealthy"}
    except Exception as e:
        logger.error(f"Failed to check server health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/available", response_model=List[ServerConfig])
async def list_available_servers(
    current_time: Optional[time] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取当前时间可用的服务器列表"""
    # 如果没有提供时间，使用当前时间
    if current_time is None:
        current_time = datetime.now().time()
        
    try:
        # 这里需要在ServerCRUD中添加一个新方法
        servers = await ServerCRUD.list_available_servers(db, current_time)
        return servers
    except Exception as e:
        logger.error(f"Failed to list available servers: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 