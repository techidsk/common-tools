# 服务器管理

## 注册服务器

注册新的服务器节点。

### 请求

```http
POST /servers/register
```

### 请求体

```json
{
    "name": "server1",
    "url": "http://localhost:8001",
    "type": "local",
    "enabled": true,
    "batch_size": 5
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 服务器名称，必须唯一 |
| url | string | 是 | 服务器地址 |
| type | string | 是 | 服务器类型：local/remote |
| enabled | boolean | 是 | 是否启用 |
| batch_size | number | 是 | 批处理大小 |

### 响应

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

### 错误码

- 400: 请求参数错误
- 409: 服务器名称已存在

## 获取服务器列表

获取所有已注册的服务器列表。

### 请求

```http
GET /servers
```

### 响应

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