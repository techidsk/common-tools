from typing import Optional, List, Dict
from sqlmodel import select, Session
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import (
    Workflow, 
    WorkflowNode, 
    WorkflowStatus,
    WorkflowNodeType
)

async def create_workflow(
    session: AsyncSession,
    *,
    name: str,
    description: Optional[str] = None,
    status: WorkflowStatus = WorkflowStatus.NORMAL,
) -> Workflow:
    """创建工作流"""
    workflow = Workflow(
        name=name,
        description=description,
        status=status,
    )
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return workflow

async def get_workflow(
    session: AsyncSession,
    workflow_id: int,
) -> Optional[Workflow]:
    """获取工作流"""
    workflow = await session.get(Workflow, workflow_id)
    return workflow

async def get_workflows(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[WorkflowStatus] = None,
) -> List[Workflow]:
    """获取工作流列表"""
    query = select(Workflow)
    if status:
        query = query.where(Workflow.status == status)
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()

async def update_workflow(
    session: AsyncSession,
    *,
    workflow_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[WorkflowStatus] = None,
) -> Optional[Workflow]:
    """更新工作流"""
    workflow = await session.get(Workflow, workflow_id)
    if not workflow:
        return None
    
    if name:
        workflow.name = name
    if description is not None:
        workflow.description = description
    if status:
        workflow.status = status
    
    await session.commit()
    await session.refresh(workflow)
    return workflow

async def delete_workflow(
    session: AsyncSession,
    workflow_id: int,
) -> bool:
    """删除工作流"""
    workflow = await session.get(Workflow, workflow_id)
    if not workflow:
        return False
    
    await session.delete(workflow)
    await session.commit()
    return True

# 工作流节点操作
async def create_workflow_node(
    session: AsyncSession,
    *,
    workflow_id: int,
    name: str,
    node_type: str,
    description: Optional[str] = None,
    config: Optional[Dict] = None,
) -> Optional[WorkflowNode]:
    """创建工作流节点"""
    workflow = await session.get(Workflow, workflow_id)
    if not workflow:
        return None
    
    node = WorkflowNode(
        workflow_id=workflow_id,
        name=name,
        node_type=node_type,
        description=description,
        config=config or {},
    )
    session.add(node)
    await session.commit()
    await session.refresh(node)
    return node

async def get_workflow_nodes(
    session: AsyncSession,
    workflow_id: int,
) -> List[WorkflowNode]:
    """获取工作流节点列表"""
    query = select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
    result = await session.execute(query)
    return result.scalars().all()

async def update_workflow_node(
    session: AsyncSession,
    *,
    node_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    config: Optional[Dict] = None,
) -> Optional[WorkflowNode]:
    """更新工作流节点"""
    node = await session.get(WorkflowNode, node_id)
    if not node:
        return None
    
    if name:
        node.name = name
    if description is not None:
        node.description = description
    if config is not None:
        node.config = config
    
    await session.commit()
    await session.refresh(node)
    return node

async def delete_workflow_node(
    session: AsyncSession,
    node_id: int,
) -> bool:
    """删除工作流节点"""
    node = await session.get(WorkflowNode, node_id)
    if not node:
        return False
    
    await session.delete(node)
    await session.commit()
    return True 