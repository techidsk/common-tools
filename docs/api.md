# API 文档

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
  - 400: 请求参数错误（URL格式无效或batch_size不大于0）
  - 409: 服务器名称已存在
  - 500: 服务器内部错误

#### 1.2 获取服务器列表
- **接口**: `GET /servers`
- **描述**: 获取所有已注册的服务器列表
- **参数**:
  - `skip`: 跳过记录数 (默认 0)
  - `limit`: 返回记录数 (默认 100，最大 100)
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
- **错误码**:
  - 500: 服务器内部错误

#### 1.3 获取服务器详情
- **接口**: `GET /servers/{server_id}`
- **描述**: 获取指定服务器的详细信息
- **响应**: 返回服务器详情
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
  - 404: 服务器不存在

#### 1.4 更新服务器
- **接口**: `PUT /servers/{server_id}`
- **描述**: 更新服务器信息
- **请求体**:
```json
{
    "url": "http://localhost:8002",
    "enabled": false,
    "batch_size": 10
}
```
- **响应**: 返回更新后的服务器信息
- **错误码**:
  - 404: 服务器不存在
  - 500: 服务器内部错误

#### 1.5 删除服务器
- **接口**: `DELETE /servers/{server_id}`
- **描述**: 删除指定的服务器
- **响应**:
```json
{
    "message": "Server deleted successfully"
}
```
- **错误码**:
  - 404: 服务器不存在
  - 500: 服务器内部错误

#### 1.6 更新服务器状态
- **接口**: `PUT /servers/{server_id}/status`
- **描述**: 更新服务器状态
- **请求体**:
```json
"online" // 可选值: "online", "offline", "busy", "maintenance"
```
- **响应**: 返回更新后的服务器信息
- **错误码**:
  - 404: 服务器不存在
  - 500: 服务器内部错误

#### 1.7 检查服务器健康状态
- **接口**: `GET /servers/{server_id}/health`
- **描述**: 检查服务器健康状态
- **响应**:
```json
{
    "status": "healthy" // 或 "unhealthy"
}
```
- **错误码**:
  - 404: 服务器不存在
  - 500: 服务器内部错误

#### 1.8 获取可用服务器列表
- **接口**: `GET /servers/available`
- **描述**: 获取当前可用的服务器列表
- **响应**: 返回可用服务器列表
- **错误码**:
  - 500: 服务器内部错误

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
  - 400: 服务器不可用（已禁用、非在线状态、正在处理其他任务）
  - 404: 服务器或工作流不存在
  - 500: 服务器内部错误

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
  - 400: 请求参数错误（服务器已禁用）
  - 404: 服务器或工作流不存在
  - 503: 服务器不可用（非在线状态、正在处理其他任务）
  - 500: 服务器内部错误

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
    "server_name": "server1",
    "results": null,
    "error": null
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
        "server_name": "server1",
        "results": null,
        "error": null
    }
]
```

#### 2.5 创建任务
- **接口**: `POST /batch`
- **描述**: 创建新任务
- **请求体**:
```json
{
    "name": "测试任务",
    "description": "这是一个测试任务",
    "workflow_id": 1,
    "parameters": {
        "key1": "value1",
        "key2": "value2"
    }
}
```
- **响应**: 返回创建的任务信息
- **错误码**:
  - 400: 请求参数错误
  - 404: 工作流不存在
  - 500: 服务器内部错误

#### 2.6 获取任务详情
- **接口**: `GET /batch/{task_id}`
- **描述**: 获取指定任务的详细信息
- **响应**: 返回任务详情
- **错误码**:
  - 404: 任务不存在

#### 2.7 更新任务
- **接口**: `PUT /batch/{task_id}`
- **描述**: 更新任务信息
- **请求体**:
```json
{
    "name": "更新的任务名称",
    "description": "更新的任务描述",
    "parameters": {
        "key1": "new_value1"
    }
}
```
- **响应**: 返回更新后的任务信息
- **错误码**:
  - 404: 任务不存在
  - 500: 服务器内部错误

#### 2.8 删除任务
- **接口**: `DELETE /batch/{task_id}`
- **描述**: 删除指定的任务
- **响应**:
```json
{
    "message": "Task deleted successfully"
}
```
- **错误码**:
  - 404: 任务不存在
  - 500: 服务器内部错误

#### 2.9 执行任务
- **接口**: `POST /batch/{task_id}/execute`
- **描述**: 在指定服务器上执行任务
- **请求体**:
```json
{
    "server_id": 1
}
```
- **响应**: 返回任务执行记录
- **错误码**:
  - 404: 任务或服务器不存在
  - 400: 服务器不在线
  - 500: 服务器内部错误

#### 2.10 获取任务执行历史
- **接口**: `GET /batch/{task_id}/executions`
- **描述**: 获取任务的执行历史记录
- **参数**:
  - `skip`: 跳过记录数 (默认 0)
  - `limit`: 返回记录数 (默认 100，最大 100)
- **响应**: 返回执行历史记录列表
- **错误码**:
  - 404: 任务不存在
  - 500: 服务器内部错误

#### 2.11 获取执行记录详情
- **接口**: `GET /batch/executions/{execution_id}`
- **描述**: 获取指定执行记录的详细信息
- **响应**: 返回执行记录详情
- **错误码**:
  - 404: 执行记录不存在

#### 2.12 更新执行状态
- **接口**: `PUT /batch/executions/{execution_id}/status`
- **描述**: 更新执行记录的状态
- **请求体**:
```json
{
    "status": "completed",
    "error_message": null,
    "result": {
        "processed_files": 10,
        "success_count": 9,
        "fail_count": 1
    }
}
```
- **响应**: 返回更新后的执行记录
- **错误码**:
  - 404: 执行记录不存在
  - 500: 服务器内部错误

### 3. 工作流管理

#### 3.1 创建工作流
- **接口**: `POST /workflows/`
- **描述**: 创建新的工作流
- **请求体**:
```json
{
    "name": "测试工作流",
    "description": "这是一个测试工作流",
    "scenario": "图像处理",
    "version": "1.0.0",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {}
}
```
- **响应**: 返回创建的工作流信息
```json
{
    "id": 1,
    "name": "测试工作流",
    "description": "这是一个测试工作流",
    "scenario": "图像处理",
    "version": "1.0.0",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {},
    "parent_id": null,
    "status": "normal",
    "created_at": "2024-03-27T10:00:00",
    "updated_at": "2024-03-27T10:00:00"
}
```
- **错误码**:
  - 400: 请求参数错误或工作流名称和版本已存在
  - 500: 服务器内部错误

#### 3.2 获取工作流列表
- **接口**: `GET /workflows/`
- **描述**: 获取工作流列表
- **参数**:
  - `status`: 工作流状态 (normal/hidden)
  - `scenario`: 场景描述
  - `skip`: 跳过记录数 (默认 0)
  - `limit`: 返回记录数 (默认 100)
- **响应**: 返回工作流列表
```json
[
    {
        "id": 1,
        "name": "测试工作流",
        "description": "这是一个测试工作流",
        "scenario": "图像处理",
        "version": "1.0.0",
        "workflow_config": {
            "nodes": []
        },
        "node_config": {
            "nodes": []
        },
        "input_mapping": {},
        "output_mapping": {},
        "parameters": {},
        "parent_id": null,
        "status": "normal",
        "created_at": "2024-03-27T10:00:00",
        "updated_at": "2024-03-27T10:00:00"
    }
]
```
- **错误码**:
  - 500: 服务器内部错误

#### 3.3 获取工作流详情
- **接口**: `GET /workflows/{workflow_id}`
- **描述**: 获取指定工作流的详细信息
- **响应**: 返回工作流详细信息
```json
{
    "id": 1,
    "name": "测试工作流",
    "description": "这是一个测试工作流",
    "scenario": "图像处理",
    "version": "1.0.0",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {},
    "parent_id": null,
    "status": "normal",
    "created_at": "2024-03-27T10:00:00",
    "updated_at": "2024-03-27T10:00:00"
}
```
- **错误码**:
  - 404: 工作流不存在

#### 3.4 创建新版本
- **接口**: `POST /workflows/{workflow_id}/versions`
- **描述**: 创建工作流的新版本
- **请求体**:
```json
{
    "description": "更新了工作流配置",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {}
}
```
- **响应**: 返回新版本的工作流信息
```json
{
    "id": 2,
    "name": "测试工作流",
    "description": "更新了工作流配置",
    "scenario": "图像处理",
    "version": "1.0.1",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {},
    "parent_id": 1,
    "status": "normal",
    "created_at": "2024-03-27T10:30:00",
    "updated_at": "2024-03-27T10:30:00"
}
```
- **错误码**:
  - 400: 请求参数错误或版本已存在
  - 404: 原工作流不存在
  - 500: 服务器内部错误

#### 3.5 获取版本历史
- **接口**: `GET /workflows/{workflow_id}/versions`
- **描述**: 获取工作流的所有版本历史
- **响应**: 返回版本历史列表
```json
[
    {
        "id": 1,
        "name": "测试工作流",
        "description": "这是一个测试工作流",
        "scenario": "图像处理",
        "version": "1.0.0",
        "workflow_config": {
            "nodes": []
        },
        "node_config": {
            "nodes": []
        },
        "input_mapping": {},
        "output_mapping": {},
        "parameters": {},
        "parent_id": null,
        "status": "normal",
        "created_at": "2024-03-27T10:00:00",
        "updated_at": "2024-03-27T10:00:00"
    },
    {
        "id": 2,
        "name": "测试工作流",
        "description": "更新了工作流配置",
        "scenario": "图像处理",
        "version": "1.0.1",
        "workflow_config": {
            "nodes": []
        },
        "node_config": {
            "nodes": []
        },
        "input_mapping": {},
        "output_mapping": {},
        "parameters": {},
        "parent_id": 1,
        "status": "normal",
        "created_at": "2024-03-27T10:30:00",
        "updated_at": "2024-03-27T10:30:00"
    }
]
```
- **错误码**:
  - 404: 工作流或版本不存在
  - 500: 服务器内部错误

#### 3.6 隐藏工作流
- **接口**: `PUT /workflows/{workflow_id}/hide`
- **描述**: 隐藏指定的工作流（将状态设置为hidden）
- **响应**: 返回更新后的工作流信息
```json
{
    "id": 1,
    "name": "测试工作流",
    "description": "这是一个测试工作流",
    "scenario": "图像处理",
    "version": "1.0.0",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {},
    "parent_id": null,
    "status": "hidden",
    "created_at": "2024-03-27T10:00:00",
    "updated_at": "2024-03-27T11:00:00"
}
```
- **错误码**:
  - 404: 工作流不存在
  - 500: 服务器内部错误

#### 3.7 显示工作流
- **接口**: `PUT /workflows/{workflow_id}/show`
- **描述**: 显示指定的工作流（将状态设置为normal）
- **响应**: 返回更新后的工作流信息
```json
{
    "id": 1,
    "name": "测试工作流",
    "description": "这是一个测试工作流",
    "scenario": "图像处理",
    "version": "1.0.0",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {},
    "parent_id": null,
    "status": "normal",
    "created_at": "2024-03-27T10:00:00",
    "updated_at": "2024-03-27T11:30:00"
}
```
- **错误码**:
  - 404: 工作流不存在
  - 500: 服务器内部错误

#### 3.8 更新工作流
- **接口**: `PUT /workflows/{workflow_id}`
- **描述**: 更新工作流信息
- **请求体**:
```json
{
    "name": "更新后的工作流",
    "description": "更新了工作流描述",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {}
}
```
- **响应**: 返回更新后的工作流信息
```json
{
    "id": 1,
    "name": "更新后的工作流",
    "description": "更新了工作流描述",
    "scenario": "图像处理",
    "version": "1.0.0",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {},
    "parent_id": null,
    "status": "normal",
    "created_at": "2024-03-27T10:00:00",
    "updated_at": "2024-03-27T12:00:00"
}
```
- **错误码**:
  - 400: 请求参数错误
  - 404: 工作流不存在
  - 500: 服务器内部错误

#### 3.9 删除工作流
- **接口**: `DELETE /workflows/{workflow_id}`
- **描述**: 删除指定的工作流
- **响应**: 
```json
{
    "message": "Workflow deleted successfully"
}
```
- **错误码**:
  - 404: 工作流不存在
  - 500: 服务器内部错误

#### 3.10 归档工作流
- **接口**: `PUT /workflows/{workflow_id}/archive`
- **描述**: 归档指定的工作流
- **响应**: 返回更新后的工作流信息
- **错误码**:
  - 404: 工作流不存在
  - 500: 服务器内部错误

#### 3.11 激活工作流
- **接口**: `PUT /workflows/{workflow_id}/activate`
- **描述**: 激活归档的工作流
- **响应**: 返回更新后的工作流信息
- **错误码**:
  - 404: 工作流不存在
  - 500: 服务器内部错误

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

### 4. 创建工作流
```bash
curl -X POST http://localhost:8000/workflows/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试工作流",
    "description": "这是一个测试工作流",
    "scenario": "图像处理",
    "version": "1.0.0",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {}
  }'
```

### 5. 创建工作流新版本
```bash
curl -X POST http://localhost:8000/workflows/1/versions \
  -H "Content-Type: application/json" \
  -d '{
    "description": "更新了工作流配置",
    "workflow_config": {
        "nodes": []
    },
    "node_config": {
        "nodes": []
    },
    "input_mapping": {},
    "output_mapping": {},
    "parameters": {}
  }'
```

## 注意事项

1. 服务器注册
   - 服务器名称必须唯一
   - 服务器URL必须是有效的HTTP/HTTPS URL
   - batch_size 必须大于0

2. 批处理任务
   - 启动任务前建议先调用检查接口
   - 任务状态会定期更新
   - 任务完成后会自动释放服务器资源

3. 工作流管理
   - 创建新版本时会自动递增版本号
   - 工作流名称和版本的组合必须唯一
   - 隐藏工作流后在列表接口需要指定status参数才能查询

4. 错误处理
   - 所有接口都会返回标准化的错误信息
   - 建议实现错误重试机制
   - 注意处理网络超时情况

## 更新日志

### 2024-03-26
- 初始版本
- 实现基本的服务器管理和批处理功能
- 添加服务器状态检查机制

### 2024-03-27
- 添加工作流管理功能
- 优化文档结构

### 2024-04-09
- 更新接口实现，增加错误处理
- 优化API参数验证
- 添加更多服务器管理和批处理任务接口
- 完善工作流版本管理
- 更新文档结构 