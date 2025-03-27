# 数据模型

## 任务状态 (TaskStatus)

```python
class TaskStatus(str, Enum):
    PENDING = "pending"    # 等待中
    RUNNING = "running"    # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"      # 失败
```

## 服务器状态 (ServerStatus)

```python
class ServerStatus(str, Enum):
    ONLINE = "online"    # 在线
    OFFLINE = "offline"  # 离线
    ERROR = "error"      # 错误
```

## 服务器配置 (ServerConfig)

```python
class ServerConfig(BaseModel):
    name: str                    # 服务器名称
    url: str                     # 服务器地址
    type: str                    # 服务器类型：local/remote
    enabled: bool               # 是否启用
    batch_size: int             # 批处理大小
    status: ServerStatus        # 服务器状态
    current_task_id: str | None # 当前任务ID
```

## 批处理请求 (BatchProcessRequest)

```python
class BatchProcessRequest(BaseModel):
    workflow_name: str           # 工作流名称
    target_folders: list[str]    # 目标文件夹列表
    folder_keywords: list[str] | None  # 文件夹关键词列表
    selected_server: str         # 选择的服务器名称
    output_root: str            # 输出根目录
```

## 批处理响应 (BatchProcessResponse)

```python
class BatchProcessResponse(BaseModel):
    task_id: str                # 任务ID
    status: TaskStatus          # 任务状态
    message: str                # 状态消息
    created_at: datetime        # 创建时间
    server_name: str            # 服务器名称
``` 