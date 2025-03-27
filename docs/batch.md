# 批处理任务

## 检查服务器可用性

检查指定服务器是否可用于批处理任务。

### 请求

```http
POST /batch/check-server
```

### 请求体

```json
{
    "workflow_name": "workflow1",
    "target_folders": ["/path/to/folders"],
    "folder_keywords": ["keyword1", "keyword2"],
    "selected_server": "server1",
    "output_root": "/path/to/output"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workflow_name | string | 是 | 工作流名称 |
| target_folders | string[] | 是 | 目标文件夹列表 |
| folder_keywords | string[] | 否 | 文件夹关键词列表 |
| selected_server | string | 是 | 选择的服务器名称 |
| output_root | string | 是 | 输出根目录 |

### 响应

```json
{
    "available": true,
    "server_name": "server1",
    "batch_size": 5,
    "message": "服务器可用"
}
```

### 错误码

- 400: 服务器不可用
- 404: 服务器或工作流不存在

## 启动批处理任务

启动新的批处理任务。

### 请求

```http
POST /batch/process
```

### 请求体

同检查服务器可用性接口。

### 响应

```json
{
    "task_id": "uuid-string",
    "status": "pending",
    "message": "批处理任务已启动",
    "created_at": "2024-03-26T10:00:00",
    "server_name": "server1"
}
```

### 错误码

- 400: 请求参数错误
- 404: 服务器或工作流不存在
- 503: 服务器不可用

## 获取任务状态

获取指定任务的状态信息。

### 请求

```http
GET /batch/tasks/{task_id}
```

### 响应

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

### 错误码

- 404: 任务不存在

## 获取任务列表

获取所有任务的状态列表。

### 请求

```http
GET /batch/tasks
```

### 响应

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