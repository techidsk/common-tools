from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from ..models.workflow import WorkflowStatus, WorkflowNodeType

class WorkflowBase(BaseModel):
    """工作流基础模型"""
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    status: WorkflowStatus = Field(default=WorkflowStatus.NORMAL, description="工作流状态")
    workflow_json_file: Optional[str] = Field(None, description="工作流JSON文件")
    user_id: Optional[int] = Field(None, description="用户ID")
    preview: Optional[str] = Field(None, description="预览图片URL")

class WorkflowCreate(WorkflowBase):
    """创建工作流请求模型"""
    pass

class WorkflowUpdate(BaseModel):
    """更新工作流请求模型"""
    name: Optional[str] = Field(None, description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    status: Optional[WorkflowStatus] = Field(None, description="工作流状态")

class WorkflowNodeBase(BaseModel):
    """工作流节点基础模型"""
    name: str = Field(..., description="节点名称")
    description: Optional[str] = Field(None, description="节点描述")
    node_type: WorkflowNodeType = Field(..., description="节点类型")
    config: Dict = Field(default_factory=dict, description="节点配置")

class WorkflowNodeCreate(WorkflowNodeBase):
    """创建工作流节点请求模型"""
    workflow_id: int = Field(..., description="工作流ID")

class WorkflowNodeUpdate(BaseModel):
    """更新工作流节点请求模型"""
    name: Optional[str] = Field(None, description="节点名称")
    description: Optional[str] = Field(None, description="节点描述")
    config: Optional[Dict] = Field(None, description="节点配置")

class WorkflowNodeResponse(WorkflowNodeBase):
    """工作流节点响应模型"""
    id: int = Field(..., description="节点ID")
    workflow_id: int = Field(..., description="工作流ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    class Config:
        from_attributes = True

class WorkflowResponse(WorkflowBase):
    """工作流响应模型"""
    id: int = Field(..., description="工作流ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    nodes: List[WorkflowNodeResponse] = Field(default_factory=list, description="工作流节点列表")

    class Config:
        from_attributes = True 