# 内网 API 文档

## 基础信息

- 基础URL: `http://localhost:8000`
- 文档地址: 
  - Swagger UI: `http://localhost:8000/docs`
  - ReDoc: `http://localhost:8000/redoc`

## 接口列表

### 1. 服务器管理

#### 1.1 注册服务器
- **接口**: `POST /servers/register`
- **描述**: 注册新的服务器节点
- **请求体**:
```json
{
    "name": "server1",
    "url": "http://localhost:8001",
    "type": "local",
    "enabled": true,
    "batch_size": 5
}
```
- **响应**:
```json
{
    "name": "server1",
    "url": "http://localhost:8001",
    "type": "local",
    "enabled": true,
    "batch_size": 5,
    "status": "offline",
    "current_task_id": null
}
```
- **错误码**:
  - 400: 请求参数错误
  - 409: 服务器名称已存在

#### 1.2 获取服务器列表
- **接口**: `GET /servers`
- **描述**: 获取所有已注册的服务器列表
- **响应**:
```json
[
    {
        "name": "server1",
        "url": "http://localhost:8001",
        "type": "local",
        "enabled": true,
        "batch_size": 5,
        "status": "offline",
        "current_task_id": null
    }
]
```

### 2. 批处理任务

#### 2.1 检查服务器可用性
- **接口**: `POST /batch/check-server`
- **描述**: 检查指定服务器是否可用于批处理任务
- **请求体**:
```json
{
    "workflow_name": "workflow1",
    "target_folders": ["/path/to/folders"],
    "folder_keywords": ["keyword1", "keyword2"],
    "selected_server": "server1",
    "output_root": "/path/to/output"
}
```
- **响应**:
```json
{
    "available": true,
    "server_name": "server1",
    "batch_size": 5,
    "message": "服务器可用"
}
```
- **错误码**:
  - 400: 服务器不可用
  - 404: 服务器或工作流不存在

#### 2.2 启动批处理任务
- **接口**: `POST /batch/process`
- **描述**: 启动新的批处理任务
- **请求体**: 同检查服务器可用性
- **响应**:
```json
{
    "task_id": "uuid-string",
    "status": "pending",
    "message": "批处理任务已启动",
    "created_at": "2024-03-26T10:00:00",
    "server_name": "server1"
}
```
- **错误码**:
  - 400: 请求参数错误
  - 404: 服务器或工作流不存在
  - 503: 服务器不可用

#### 2.3 获取任务状态
- **接口**: `GET /batch/tasks/{task_id}`
- **描述**: 获取指定任务的状态信息
- **响应**:
```json
{
    "task_id": "uuid-string",
    "status": "running",
    "message": "任务正在处理中",
    "created_at": "2024-03-26T10:00:00",
    "updated_at": "2024-03-26T10:01:00",
    "progress": 0.5,
    "server_name": "server1"
}
```
- **错误码**:
  - 404: 任务不存在

#### 2.4 获取任务列表
- **接口**: `GET /batch/tasks`
- **描述**: 获取所有任务的状态列表
- **响应**:
```json
[
    {
        "task_id": "uuid-string",
        "status": "running",
        "message": "任务正在处理中",
        "created_at": "2024-03-26T10:00:00",
        "updated_at": "2024-03-26T10:01:00",
        "progress": 0.5,
        "server_name": "server1"
    }
]
```

## 数据模型

### 任务状态 (TaskStatus)
```python
class TaskStatus(str, Enum):
    PENDING = "pending"    # 等待中
    RUNNING = "running"    # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"      # 失败
```

### 服务器状态 (ServerStatus)
```python
class ServerStatus(str, Enum):
    ONLINE = "online"    # 在线
    OFFLINE = "offline"  # 离线
    ERROR = "error"      # 错误
```

## 使用示例

### 1. 注册服务器
```bash
curl -X POST http://localhost:8000/servers/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "server1",
    "url": "http://localhost:8001",
    "type": "local",
    "enabled": true,
    "batch_size": 5
  }'
```

### 2. 启动批处理任务
```bash
curl -X POST http://localhost:8000/batch/process \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "workflow1",
    "target_folders": ["/path/to/folders"],
    "folder_keywords": ["keyword1", "keyword2"],
    "selected_server": "server1",
    "output_root": "/path/to/output"
  }'
```

### 3. 获取任务状态
```bash
curl http://localhost:8000/batch/tasks/task-uuid-string
```

## 注意事项

1. 服务器注册
   - 服务器名称必须唯一
   - 服务器URL必须可访问
   - batch_size 必须大于0

2. 批处理任务
   - 启动任务前建议先调用检查接口
   - 任务状态会定期更新
   - 任务完成后会自动释放服务器资源

3. 错误处理
   - 所有接口都会返回标准化的错误信息
   - 建议实现错误重试机制
   - 注意处理网络超时情况

## 更新日志

### 2024-03-26
- 初始版本
- 实现基本的服务器管理和批处理功能
- 添加服务器状态检查机制 