# Common Tools API 文档

## 简介

这是一个用于管理批处理任务的 API 服务。主要功能包括：

- 服务器管理：注册和管理处理服务器
- 批处理任务：创建和管理批处理任务
- 任务监控：实时查看任务状态和进度

## 快速开始

1. 启动服务：
```bash
uvicorn src.main:app --reload
```

2. 访问地址：
- API 服务：http://localhost:8000
- 文档地址：http://localhost:8000/docs

## 目录

- [服务器管理](server.md) - 服务器注册和管理
- [批处理任务](batch.md) - 批处理任务的创建和管理
- [数据模型](models.md) - 数据结构和类型定义 