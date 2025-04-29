# 数据模型

## 基础枚举

### TaskStatus
任务状态枚举。

```python
class TaskStatus(str, Enum):
    PENDING = "pending"    # 等待中
    RUNNING = "running"    # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"      # 失败
```

### ServerStatus
服务器状态枚举。

```python
class ServerStatus(str, Enum):
    ONLINE = "online"    # 在线
    OFFLINE = "offline"  # 离线
    ERROR = "error"      # 错误
```

### WorkflowStatus
工作流状态枚举。

```python
class WorkflowStatus(str, Enum):
    NORMAL = "normal"  # 正常状态
    HIDDEN = "hidden"  # 隐藏状态
```

## 数据库模型

### Server
服务器模型，用于存储服务器节点信息。

```python
class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    url = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    batch_size = Column(Integer, default=5)
    status = Column(Enum(ServerStatus), default=ServerStatus.OFFLINE)
    current_task_id = Column(String(255), nullable=True)
    last_check = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    task_executions = relationship("TaskExecution", back_populates="server")
```

### Task
任务模型，用于存储批处理任务信息。

```python
class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    workflow_id = Column(Integer, ForeignKey("workflows.id"))
    workflow_config = Column(JSON, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    workflow = relationship("Workflow", back_populates="tasks")
    executions = relationship("TaskExecution", back_populates="task")
```

### TaskExecution
任务执行记录模型，用于存储任务执行历史。

```python
class TaskExecution(Base):
    __tablename__ = "task_executions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), ForeignKey("tasks.id"))
    server_id = Column(Integer, ForeignKey("servers.id"))
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    task = relationship("Task", back_populates="executions")
    server = relationship("Server", back_populates="task_executions")
```

### Workflow
工作流模型，用于存储工作流配置和状态信息。

```python
class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    scenario = Column(String(255), nullable=False)  # 场景描述
    version = Column(String(50), nullable=False)    # 版本号
    workflow_config = Column(JSON, nullable=False)  # 工作流配置
    node_config = Column(JSON, nullable=False)      # 节点配置
    input_mapping = Column(JSON, default={})        # 输入映射
    output_mapping = Column(JSON, default={})       # 输出映射
    parameters = Column(JSON, default={})           # 参数配置
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.NORMAL)  # 工作流状态
    parent_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)  # 父版本ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tasks = relationship("Task", back_populates="workflow")
    parent = relationship("Workflow", remote_side=[id], backref="versions")
```

## Pydantic 模型

### ServerConfig
服务器配置 Pydantic 模型。

```python
class ServerConfig(BaseModel):
    name: str
    url: str
    type: str
    enabled: bool = True
    batch_size: int = 5
```

### TaskConfig
任务配置 Pydantic 模型。

```python
class TaskConfig(BaseModel):
    name: str
    workflow_id: int
    workflow_config: dict
    status: TaskStatus = TaskStatus.PENDING
```

### TaskExecutionConfig
任务执行记录 Pydantic 模型。

```python
class TaskExecutionConfig(BaseModel):
    task_id: str
    server_id: int
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[dict] = None
```

### WorkflowConfig
工作流配置 Pydantic 模型。

```python
class WorkflowConfig(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    scenario: str
    version: str
    workflow_config: dict
    node_config: dict
    input_mapping: dict = {}
    output_mapping: dict = {}
    parameters: dict = {}
    status: Optional[WorkflowStatus] = None
    parent_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "测试工作流",
                "description": "这是一个测试工作流",
                "scenario": "图像处理",
                "version": "1.0.0",
                "workflow_config": {"nodes": []},
                "node_config": {"nodes": []},
                "input_mapping": {},
                "output_mapping": {},
                "parameters": {}
            }
        }
    }
```

此模型既用于API响应，也用于创建新工作流。当用于创建新工作流时，`id`、`status`、`created_at`和`updated_at`字段会被忽略。

### WorkflowCreate
创建工作流请求的 Pydantic 模型。

```python
class WorkflowCreate(BaseModel):
    name: str
    description: str
    scenario: str
    version: str
    workflow_config: dict
    node_config: dict
    input_mapping: dict = {}
    output_mapping: dict = {}
    parameters: dict = {}
```

### WorkflowUpdate
更新工作流请求的 Pydantic 模型。

```python
class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_config: Optional[dict] = None
    node_config: Optional[dict] = None
    input_mapping: Optional[dict] = None
    output_mapping: Optional[dict] = None
    parameters: Optional[dict] = None
```

## 字段说明

### Server 字段
- `id`: 服务器ID
- `name`: 服务器名称
- `url`: 服务器URL
- `type`: 服务器类型
- `enabled`: 是否启用
- `batch_size`: 批处理大小
- `status`: 服务器状态
- `current_task_id`: 当前任务ID
- `last_check`: 最后检查时间
- `created_at`: 创建时间
- `updated_at`: 更新时间

### Task 字段
- `id`: 任务ID
- `name`: 任务名称
- `workflow_id`: 关联的工作流ID
- `workflow_config`: 工作流配置
- `status`: 任务状态
- `created_at`: 创建时间
- `updated_at`: 更新时间

### TaskExecution 字段
- `id`: 执行记录ID
- `task_id`: 关联的任务ID
- `server_id`: 关联的服务器ID
- `status`: 执行状态
- `started_at`: 开始时间
- `completed_at`: 完成时间
- `error_message`: 错误信息
- `result`: 执行结果
- `created_at`: 创建时间
- `updated_at`: 更新时间

### Workflow 字段
- `id`: 工作流ID
- `name`: 工作流名称
- `description`: 工作流描述
- `scenario`: 场景描述
- `version`: 版本号
- `workflow_config`: 工作流配置
- `node_config`: 节点配置
- `input_mapping`: 输入映射
- `output_mapping`: 输出映射
- `parameters`: 参数配置
- `status`: 工作流状态
- `parent_id`: 父版本ID
- `created_at`: 创建时间
- `updated_at`: 更新时间 