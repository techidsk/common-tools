import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query
from loguru import logger
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from src.service import ServiceConfig, BatchProcessor
from src.api.models.batch import (
    BatchProcessRequest, BatchProcessResponse,
    WorkflowConfig, TaskStatusResponse, TaskStatus,
    ServerAvailabilityResponse
)
from src.api.models.server import ServerStatus
from src.api.task_manager import task_manager
from src.api.server_manager import server_manager
from src.api.database import get_db
from src.api.crud import TaskCRUD, TaskExecutionCRUD, ServerCRUD
from src.api.models.database import Task, TaskExecution
from src.api.models.workflow import TaskConfig, TaskCreate, TaskUpdate, TaskExecutionConfig, ServerConfig

router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/check-server", response_model=ServerAvailabilityResponse)
async def check_server(request: BatchProcessRequest):
    """
    检查服务器可用性
    
    根据API文档, POST /batch/check-server 检查指定服务器是否可用于批处理任务
    """
    try:
        # 获取工作流配置
        workflow_config = task_manager.get_workflow_config(request.workflow_name)
        if not workflow_config:
            raise HTTPException(
                status_code=404,
                detail=f"未找到工作流配置: {request.workflow_name}"
            )
        
        # 检查选择的服务器是否可用
        server = server_manager.get_server(request.selected_server)
        if not server:
            raise HTTPException(
                status_code=404,
                detail=f"未找到服务器: {request.selected_server}"
            )
        
        if not server.enabled:
            raise HTTPException(
                status_code=400,
                detail=f"服务器 {request.selected_server} 已禁用"
            )
        
        if server.status != ServerStatus.ONLINE:
            raise HTTPException(
                status_code=400,
                detail=f"服务器 {request.selected_server} 当前状态为 {server.status}"
            )
        
        if server.current_task_id is not None:
            raise HTTPException(
                status_code=400,
                detail=f"服务器 {request.selected_server} 正在处理其他任务"
            )
        
        # 创建配置进行验证
        config = ServiceConfig(
            target_folders=[Path(p) for p in request.target_folders],
            workflow_path=Path(workflow_config["workflow_path"]),
            node_config_path=Path(workflow_config["node_config_path"]),
            batch_size=server.batch_size,  # 使用服务器的batch_size
            folder_keywords=request.folder_keywords or [],
            servers=[server.url],
            input_mapping=workflow_config["input_mapping"],
            output_root=Path(request.output_root)
        )
        
        # 创建处理器实例进行验证
        processor = BatchProcessor(config)
        await processor.dispatcher.close()
        
        return ServerAvailabilityResponse(
            available=True,
            server_name=server.name,
            batch_size=server.batch_size,
            message="服务器可用"
        )
        
    except Exception as e:
        logger.error(f"检查服务器失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"检查服务器失败: {str(e)}"
        )


@router.post("/process", response_model=BatchProcessResponse)
async def batch_process(
    request: BatchProcessRequest,
    background_tasks: BackgroundTasks
):
    """
    启动批处理任务
    
    根据API文档, POST /batch/process 启动新的批处理任务
    """
    try:
        # 获取工作流配置
        workflow_config = task_manager.get_workflow_config(request.workflow_name)
        if not workflow_config:
            raise HTTPException(
                status_code=404,
                detail=f"未找到工作流配置: {request.workflow_name}"
            )
        
        # 检查选择的服务器是否可用
        server = server_manager.get_server(request.selected_server)
        if not server:
            raise HTTPException(
                status_code=404,
                detail=f"未找到服务器: {request.selected_server}"
            )
        
        if not server.enabled:
            raise HTTPException(
                status_code=400,
                detail=f"服务器 {request.selected_server} 已禁用"
            )
        
        if server.status != ServerStatus.ONLINE:
            raise HTTPException(
                status_code=503,
                detail=f"服务器 {request.selected_server} 当前状态为 {server.status}"
            )
        
        if server.current_task_id is not None:
            raise HTTPException(
                status_code=503,
                detail=f"服务器 {request.selected_server} 正在处理其他任务"
            )
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 分配任务到服务器
        if not server_manager.assign_task(server.name, task_id):
            raise HTTPException(
                status_code=503,
                detail=f"无法分配任务到服务器: {server.name}"
            )
        
        # 创建配置
        config = ServiceConfig(
            target_folders=[Path(p) for p in request.target_folders],
            workflow_path=Path(workflow_config["workflow_path"]),
            node_config_path=Path(workflow_config["node_config_path"]),
            batch_size=server.batch_size,  # 使用服务器的batch_size
            folder_keywords=request.folder_keywords or [],
            servers=[server.url],
            input_mapping=workflow_config["input_mapping"],
            output_root=Path(request.output_root)
        )
        
        # 创建处理器实例
        processor = BatchProcessor(config)
        
        # 创建任务记录
        task = task_manager.create_task(task_id, request.workflow_name)
        
        # 在后台运行处理任务
        async def run_processor():
            try:
                # 更新任务状态为运行中
                task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.RUNNING,
                    message="任务正在处理中",
                    progress=0.0,
                    server_name=server.name
                )
                
                logger.info(f"开始处理任务 {task_id} 在服务器 {server.name}")
                await processor.run()
                
                # 更新任务状态为完成
                task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    message="任务处理完成",
                    progress=1.0,
                    server_name=server.name
                )
                
                logger.info(f"任务 {task_id} 处理完成")
            except Exception as e:
                # 更新任务状态为失败
                task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    message=f"任务处理失败: {str(e)}",
                    error=str(e),
                    server_name=server.name
                )
                logger.error(f"任务 {task_id} 处理失败: {str(e)}")
            finally:
                # 释放服务器
                server_manager.release_task(server.name)
                await processor.dispatcher.close()
        
        # 添加后台任务
        background_tasks.add_task(run_processor)
        
        return BatchProcessResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="批处理任务已启动",
            created_at=task.created_at,
            server_name=server.name
        )
        
    except Exception as e:
        logger.error(f"创建批处理任务失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"创建批处理任务失败: {str(e)}"
        )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    根据API文档, GET /batch/tasks/{task_id} 获取指定任务的状态信息
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"未找到任务: {task_id}"
        )
    return task


@router.get("/tasks", response_model=List[TaskStatusResponse])
async def list_tasks():
    """
    获取任务列表
    
    根据API文档, GET /batch/tasks 获取所有任务的状态列表
    """
    return task_manager.list_tasks()


@router.post("/", response_model=TaskConfig)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建任务"""
    return await TaskCRUD.create_task(db, task_data)


@router.get("/{task_id}", response_model=TaskConfig)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取任务详情"""
    task = await TaskCRUD.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskConfig)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新任务"""
    task = await TaskCRUD.update_task(db, task_id, task_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除任务"""
    success = await TaskCRUD.delete_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}


@router.get("/", response_model=List[TaskConfig])
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取任务列表"""
    return await TaskCRUD.list_tasks(db, skip, limit)


@router.post("/{task_id}/execute", response_model=TaskExecutionConfig)
async def execute_task(
    task_id: int,
    server_id: int,
    db: AsyncSession = Depends(get_db)
):
    """执行任务"""
    # 检查任务是否存在
    task = await TaskCRUD.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查服务器是否存在且在线
    server = await ServerCRUD.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if server.status != ServerStatus.ONLINE:
        raise HTTPException(status_code=400, detail="Server is not online")
    
    # 创建执行记录
    execution = await TaskExecutionCRUD.create_execution(
        db, task_id, server_id, TaskStatus.RUNNING
    )
    
    # TODO: 异步执行任务
    # 这里应该启动一个后台任务来执行实际的工作
    
    return execution


@router.get("/{task_id}/executions", response_model=List[TaskExecutionConfig])
async def list_task_executions(
    task_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取任务执行历史"""
    return await TaskExecutionCRUD.list_task_executions(db, task_id, skip, limit)


@router.get("/executions/{execution_id}", response_model=TaskExecutionConfig)
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取执行记录详情"""
    execution = await TaskExecutionCRUD.get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.put("/executions/{execution_id}/status", response_model=TaskExecutionConfig)
async def update_execution_status(
    execution_id: int,
    status: TaskStatus,
    error_message: Optional[str] = None,
    result: Optional[dict] = None,
    db: AsyncSession = Depends(get_db)
):
    """更新执行状态"""
    execution = await TaskExecutionCRUD.update_execution_status(
        db, execution_id, status, error_message, result
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution 