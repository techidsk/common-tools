from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from loguru import logger
from pydantic import BaseModel
import inspect

from src.api.database import get_db
from src.api.crud import WorkflowCRUD
from src.api.models.workflow import WorkflowConfig, WorkflowCreate, WorkflowUpdate
from src.api.models.database import WorkflowStatus

# 添加调试日志
logger.debug("Loaded modules in workflow.py:")
logger.debug(f"WorkflowConfig from: {inspect.getmodule(WorkflowConfig)}")
logger.debug(f"WorkflowCreate from: {inspect.getmodule(WorkflowCreate)}")
logger.debug(f"WorkflowStatus from: {inspect.getmodule(WorkflowStatus)}")

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"]
)

class VersionRequest(BaseModel):
    description: Optional[str] = None
    workflow_config: Dict[str, Any] = {}
    node_config: Dict[str, Any] = {}
    input_mapping: Dict[str, Any] = {}
    output_mapping: Dict[str, Any] = {}
    parameters: Dict[str, Any] = {}

@router.post("/", response_model=WorkflowConfig)
async def create_workflow(
    workflow: WorkflowCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的工作流
    
    根据API文档, POST /workflows/ 用于创建新的工作流
    """
    try:
        # 添加调试日志
        logger.debug(f"Creating workflow with data: {workflow.dict()}")
        logger.debug(f"Workflow model type: {type(workflow)}")
        
        # 检查工作流名称和版本是否已存在
        existing_workflow = await WorkflowCRUD.get_workflow_by_name_and_version(
            db, workflow.name, workflow.version
        )
        if existing_workflow:
            logger.warning(f"Workflow already exists: {workflow.name} v{workflow.version}")
            raise HTTPException(
                status_code=400,
                detail=f"工作流名称和版本已存在: {workflow.name} v{workflow.version}"
            )
        
        # 添加调试日志
        logger.debug("About to create workflow in database")
        logger.debug(f"Using database session: {db}")
        logger.debug(f"WorkflowCRUD module: {inspect.getmodule(WorkflowCRUD)}")
        
        # 创建工作流
        db_workflow = await WorkflowCRUD.create_workflow(db, workflow)
        logger.info(f"Created new workflow: {workflow.name} v{workflow.version}")
        logger.debug(f"Created workflow type: {type(db_workflow)}")
        logger.debug(f"Created workflow data: {db_workflow.dict() if hasattr(db_workflow, 'dict') else str(db_workflow)}")
        return db_workflow
    except Exception as e:
        logger.error(f"Failed to create workflow: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error traceback:", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[WorkflowConfig])
async def list_workflows(
    skip: int = 0,
    limit: int = 100,
    status: Optional[WorkflowStatus] = None,
    scenario: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    获取工作流列表
    
    根据API文档, GET /workflows/ 返回工作流列表，可以通过status和scenario过滤
    """
    try:
        workflows = await WorkflowCRUD.list_workflows(
            db,
            skip=skip,
            limit=limit,
            status=status,
            scenario=scenario
        )
        return workflows
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{workflow_id}", response_model=WorkflowConfig)
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取工作流详情
    
    根据API文档, GET /workflows/{workflow_id} 返回指定工作流的详细信息
    """
    workflow = await WorkflowCRUD.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.post("/{workflow_id}/versions", response_model=WorkflowConfig)
async def create_new_version(
    workflow_id: int,
    version_data: VersionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    创建工作流的新版本
    
    根据API文档, POST /workflows/{workflow_id}/versions 创建工作流的新版本
    """
    try:
        # 检查原工作流是否存在
        original = await WorkflowCRUD.get_workflow(db, workflow_id)
        if not original:
            raise HTTPException(status_code=404, detail="Original workflow not found")

        # 生成新版本号
        current_version = original.version
        version_parts = current_version.split('.')
        new_version = f"{version_parts[0]}.{version_parts[1]}.{int(version_parts[2]) + 1}"
        
        # 检查新版本是否已存在
        existing = await WorkflowCRUD.get_workflow_by_name_and_version(
            db, original.name, new_version
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Version {new_version} already exists"
            )

        # 准备更新数据
        updates = {
            "description": version_data.description if version_data.description else original.description,
            "workflow_config": version_data.workflow_config,
            "node_config": version_data.node_config,
            "input_mapping": version_data.input_mapping,
            "output_mapping": version_data.output_mapping,
            "parameters": version_data.parameters
        }

        # 创建新版本
        new_workflow = await WorkflowCRUD.create_new_version(
            db, workflow_id, new_version, updates
        )
        logger.info(f"Created new version {new_version} for workflow {original.name}")
        return new_workflow
    except Exception as e:
        logger.error(f"Failed to create new version: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{workflow_id}/versions", response_model=List[WorkflowConfig])
async def get_workflow_versions(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取工作流的所有版本历史
    
    根据API文档, GET /workflows/{workflow_id}/versions 返回版本历史列表
    """
    try:
        versions = await WorkflowCRUD.get_workflow_versions(db, workflow_id)
        if not versions:
            raise HTTPException(status_code=404, detail="Workflow or versions not found")
        return versions
    except Exception as e:
        logger.error(f"Failed to get workflow versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{workflow_id}/hide", response_model=WorkflowConfig)
async def hide_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    隐藏工作流
    
    根据API文档, PUT /workflows/{workflow_id}/hide 隐藏指定的工作流（将状态设置为hidden）
    """
    try:
        workflow = await WorkflowCRUD.hide_workflow(db, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        logger.info(f"Hidden workflow: {workflow.name} v{workflow.version}")
        return workflow
    except Exception as e:
        logger.error(f"Failed to hide workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{workflow_id}/show", response_model=WorkflowConfig)
async def show_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    显示工作流
    
    根据API文档, PUT /workflows/{workflow_id}/show 显示指定的工作流（将状态设置为normal）
    """
    try:
        workflow = await WorkflowCRUD.show_workflow(db, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        logger.info(f"Displayed workflow: {workflow.name} v{workflow.version}")
        return workflow
    except Exception as e:
        logger.error(f"Failed to show workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{workflow_id}", response_model=WorkflowConfig)
async def update_workflow(
    workflow_id: int,
    workflow: WorkflowUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新工作流信息
    
    根据API文档, PUT /workflows/{workflow_id} 更新工作流信息
    """
    try:
        # 检查工作流是否存在
        existing_workflow = await WorkflowCRUD.get_workflow(db, workflow_id)
        if not existing_workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # 更新工作流
        updated_workflow = await WorkflowCRUD.update_workflow(db, workflow_id, workflow)
        logger.info(f"Updated workflow: {workflow_id}")
        return updated_workflow
    except Exception as e:
        logger.error(f"Failed to update workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    删除指定的工作流
    
    根据API文档, DELETE /workflows/{workflow_id} 删除指定的工作流
    """
    try:
        # 检查工作流是否存在
        existing_workflow = await WorkflowCRUD.get_workflow(db, workflow_id)
        if not existing_workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        # 删除工作流
        success = await WorkflowCRUD.delete_workflow(db, workflow_id)
        if success:
            logger.info(f"Workflow {workflow_id} deleted")
            return {"message": "Workflow deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete workflow")
    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{workflow_id}/archive", response_model=WorkflowConfig)
async def archive_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    归档工作流
    
    根据API文档, PUT /workflows/{workflow_id}/archive 归档指定的工作流
    """
    try:
        workflow = await WorkflowCRUD.archive_workflow(db, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        logger.info(f"Archived workflow: {workflow.name} v{workflow.version}")
        return workflow
    except Exception as e:
        logger.error(f"Failed to archive workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{workflow_id}/activate", response_model=WorkflowConfig)
async def activate_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    激活归档的工作流
    
    根据API文档, PUT /workflows/{workflow_id}/activate 激活归档的工作流
    """
    try:
        workflow = await WorkflowCRUD.activate_workflow(db, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        logger.info(f"Activated workflow: {workflow.name} v{workflow.version}")
        return workflow
    except Exception as e:
        logger.error(f"Failed to activate workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 