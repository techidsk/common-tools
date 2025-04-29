from typing import Dict, Optional
from datetime import datetime
import asyncio
from loguru import logger
from src.api.models.batch import TaskStatus, TaskStatusResponse


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self._tasks: Dict[str, TaskStatusResponse] = {}
        self._workflow_configs: Dict[str, dict] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 3600  # 1小时清理一次
    
    async def start(self) -> None:
        """启动任务管理器"""
        logger.info("Starting task manager...")
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_old_tasks())
    
    async def stop(self) -> None:
        """停止任务管理器"""
        logger.info("Stopping task manager...")
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            self._cleanup_task = None
    
    async def _cleanup_old_tasks(self) -> None:
        """清理旧任务"""
        while True:
            try:
                current_time = datetime.now()
                # 清理超过24小时的已完成或失败任务
                for task_id, task in list(self._tasks.items()):
                    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        if (current_time - task.updated_at).total_seconds() > 86400:  # 24小时
                            del self._tasks[task_id]
                            logger.debug(f"Cleaned up old task: {task_id}")
            except Exception as e:
                logger.error(f"Error during task cleanup: {e}")
            
            await asyncio.sleep(self._cleanup_interval)
    
    async def get_status(self) -> dict:
        """获取任务管理器状态"""
        return {
            "total_tasks": len(self._tasks),
            "active_tasks": len([t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]),
            "cleanup_running": bool(self._cleanup_task and not self._cleanup_task.done())
        }
    
    def register_workflow(self, name: str, config: dict) -> None:
        """注册工作流配置"""
        self._workflow_configs[name] = config
    
    def get_workflow_config(self, name: str) -> Optional[dict]:
        """获取工作流配置"""
        return self._workflow_configs.get(name)
    
    def create_task(self, task_id: str, workflow_name: str) -> TaskStatusResponse:
        """创建新任务"""
        task = TaskStatusResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="任务已创建",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            progress=0.0
        )
        self._tasks[task_id] = task
        return task
    
    def get_task(self, task_id: str) -> Optional[TaskStatusResponse]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str,
        progress: float = None,
        results: list = None,
        error: str = None
    ) -> Optional[TaskStatusResponse]:
        """更新任务状态"""
        if task_id not in self._tasks:
            return None
            
        task = self._tasks[task_id]
        task.status = status
        task.message = message
        task.updated_at = datetime.now()
        
        if progress is not None:
            task.progress = progress
        if results is not None:
            task.results = results
        if error is not None:
            task.error = error
            
        return task
    
    def list_tasks(self) -> list[TaskStatusResponse]:
        """列出所有任务"""
        return list(self._tasks.values())


# 创建全局任务管理器实例
task_manager = TaskManager() 