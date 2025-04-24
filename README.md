# common-tools
个人用的开发库


## 说明
使用 uv 创建 venv

### 安装 UV
```bash
# With pip.
pip install uv
```

To create a virtual environment:

```
uv venv  # Create a virtual environment at `.venv`.

uv venv --python 3.12  # Create a virtual environment at `.venv` with python 3.12.
```
To activate the virtual environment:

###  On macOS and Linux.
```
source .venv/bin/activate
```

### On Windows.
```
.venv\Scripts\activate
```

在 powershell 中使用 venv
```
.\.venv\Scripts\Activate.ps1
```

### 安装依赖
```
uv pip install -r requirements.txt 
```

## 模块

### 批量生成模块
用于 api 批量生成。

分为
1. 检索器，检索需要处理的素材。
2. 提示词拼接器。
3. 分发器，将任务分发到各个节点。
4. 获取结果，获取各个节点处理结果。

#### TODO
[ ] 自动开启 autodl
[ ] 自动拉取判断模型

# Common Tools API

## 开发说明

1. 启动服务：
```bash
# 开发模式（带热重载）
uvicorn src.api.main:app --reload

# 生产模式
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

2. 访问文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

3. 环境要求：
- Python 3.12
- FastAPI
- Pydantic v2
- Loguru
- Black

4. 目录结构：
```
src/
  api/
    main.py          # FastAPI 应用入口
    database.py      # 数据库配置
    crud.py          # 数据库操作
    server_manager.py # 服务器管理
    task_manager.py  # 任务管理
    routes/          # API 路由
    models/          # 数据模型
```

5. 开发规范：
- 使用 Black 进行代码格式化
- 使用 Loguru 进行日志记录
- 使用 Pydantic v2 进行数据验证
- 使用 SQLAlchemy 进行数据库操作

## API 文档

详细的 API 文档请参考 [docs/api.md](docs/api.md)

### 服务器管理

#### 注册服务器
```http
POST /servers/register
```

请求体：
```json
{
    "name": "server1",
    "url": "http://localhost:8001",
    "type": "local",
    "enabled": true,
    "batch_size": 5
}
```

响应：
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

#### 获取服务器列表
```http
GET /servers
```

响应：
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

### 批处理任务

#### 检查服务器可用性
```http
POST /batch/check-server
```

请求体：
```json
{
    "workflow_name": "workflow1",
    "target_folders": ["/path/to/folders"],
    "folder_keywords": ["keyword1", "keyword2"],
    "selected_server": "server1",
    "output_root": "/path/to/output"
}
```

响应：
```json
{
    "available": true,
    "server_name": "server1",
    "batch_size": 5,
    "message": "服务器可用"
}
```

#### 启动批处理任务
```http
POST /batch/process
```

请求体：
```json
{
    "workflow_name": "workflow1",
    "target_folders": ["/path/to/folders"],
    "folder_keywords": ["keyword1", "keyword2"],
    "selected_server": "server1",
    "output_root": "/path/to/output"
}
```

响应：
```json
{
    "task_id": "uuid-string",
    "status": "pending",
    "message": "批处理任务已启动",
    "created_at": "2024-03-26T10:00:00",
    "server_name": "server1"
}
```

#### 获取任务状态
```http
GET /batch/tasks/{task_id}
```

响应：
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

#### 获取任务列表
```http
GET /batch/tasks
```

响应：
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

### 数据模型

#### TaskStatus 枚举
```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

#### ServerStatus 枚举
```python
class ServerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
```

# Workflow API

一个简单的工作流管理API系统。

## 功能特性

- 工作流管理（创建、查询、更新、删除）
- 工作流节点管理（创建、查询、更新、删除）
- 异步SQLite数据库
- FastAPI + SQLModel + Pydantic
- 完整的类型提示
- OpenAPI文档

## 技术栈

- Python 3.12
- FastAPI
- SQLModel
- Pydantic v2
- aiosqlite
- uvicorn
- loguru

## 安装

1. 克隆项目

```bash
git clone https://github.com/yourusername/workflow-api.git
cd workflow-api
```

2. 使用 uv 安装依赖

```bash
uv venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows

uv pip install -r requirements.txt
```

## 运行

```bash
cd src
python run.py
```

服务器将在 http://localhost:8000 启动

- API文档：http://localhost:8000/docs
- ReDoc文档：http://localhost:8000/redoc

## API接口

### 工作流

- `POST /workflows` - 创建工作流
- `GET /workflows` - 获取工作流列表
- `GET /workflows/{workflow_id}` - 获取工作流详情
- `PUT /workflows/{workflow_id}` - 更新工作流
- `DELETE /workflows/{workflow_id}` - 删除工作流

### 工作流节点

- `POST /workflows/nodes` - 创建工作流节点
- `GET /workflows/{workflow_id}/nodes` - 获取工作流节点列表
- `PUT /workflows/nodes/{node_id}` - 更新工作流节点
- `DELETE /workflows/nodes/{node_id}` - 删除工作流节点

## 开发

1. 安装开发依赖

```bash
uv pip install -r requirements-dev.txt
```

2. 运行测试

```bash
pytest
```

3. 代码格式化

```bash
black src
```

## 许可证

MIT


## 启动服务

```
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```