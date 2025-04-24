from datetime import datetime, time
from typing import Generic, List, Optional, Type, TypeVar, Dict

from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from src.api.models.database import (
    Server,
    ServerStatus,
    Task,
    TaskExecution,
    TaskStatus,
    Workflow,
    WorkflowStatus,
)
from src.api.models.workflow import (
    ServerConfig,
    ServerCreate,
    ServerUpdate,
    TaskConfig,
    TaskCreate,
    TaskExecutionConfig,
    TaskUpdate,
    WorkflowConfig,
    WorkflowCreate,
    WorkflowUpdate,
)

# 添加调试日志
logger.debug("Loaded models in crud.py:")
logger.debug(f"Workflow from: {Workflow.__module__}")
logger.debug(f"WorkflowConfig from: {WorkflowConfig.__module__}")
logger.debug(f"Task from: {Task.__module__}")

# 定义泛型类型变量
T = TypeVar("T", bound=SQLModel)
C = TypeVar("C", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


class BaseCRUD(Generic[T, C, U, R]):
    """通用CRUD基类，处理常见的数据库操作

    T: 数据库模型类型 (SQLModel)
    C: 创建模型类型 (Pydantic)
    U: 更新模型类型 (Pydantic)
    R: 响应模型类型 (Pydantic)
    """

    model: Type[T]
    create_model: Type[C]
    update_model: Type[U]
    response_model: Type[R]

    @classmethod
    async def create(cls, db: AsyncSession, obj_in: C) -> R:
        """通用创建方法"""
        try:
            # 从创建模型构建数据库模型
            db_obj = cls.model(**obj_in.model_dump())

            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)

            # 数据库模型转响应模型
            return cls.response_model.model_validate(db_obj)
        except Exception as e:
            logger.error(f"Error in {cls.__name__}.create: {str(e)}")
            await db.rollback()
            raise

    @classmethod
    async def get(cls, db: AsyncSession, id: int) -> Optional[R]:
        """通用获取方法"""
        try:
            result = await db.execute(select(cls.model).where(cls.model.id == id))
            db_obj = result.scalar_one_or_none()

            if db_obj is None:
                return None

            # 数据库模型转响应模型
            return cls.response_model.model_validate(db_obj)
        except Exception as e:
            logger.error(f"Error in {cls.__name__}.get: {str(e)}")
            raise

    @classmethod
    async def update(cls, db: AsyncSession, id: int, obj_in: U) -> Optional[R]:
        """通用更新方法"""
        try:
            result = await db.execute(select(cls.model).where(cls.model.id == id))
            db_obj = result.scalar_one_or_none()

            if db_obj is None:
                return None

            # 使用model_dump(exclude_unset=True)过滤空值
            update_data = obj_in.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_obj, key, value)

            await db.commit()
            await db.refresh(db_obj)

            # 数据库模型转响应模型
            return cls.response_model.model_validate(db_obj)
        except Exception as e:
            logger.error(f"Error in {cls.__name__}.update: {str(e)}")
            await db.rollback()
            raise

    @classmethod
    async def delete(cls, db: AsyncSession, id: int) -> bool:
        """通用删除方法"""
        try:
            result = await db.execute(select(cls.model).where(cls.model.id == id))
            db_obj = result.scalar_one_or_none()

            if db_obj is None:
                return False

            await db.delete(db_obj)
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error in {cls.__name__}.delete: {str(e)}")
            await db.rollback()
            raise

    @classmethod
    async def list(
        cls, db: AsyncSession, skip: int = 0, limit: int = 100, **filters
    ) -> List[R]:
        """通用列表方法，支持筛选"""
        try:
            query = select(cls.model)

            # 应用筛选条件
            for field, value in filters.items():
                if value is not None and hasattr(cls.model, field):
                    # 处理枚举类型
                    if hasattr(value, "value"):
                        query = query.where(getattr(cls.model, field) == value.value)
                    else:
                        query = query.where(getattr(cls.model, field) == value)

            # 应用分页
            query = query.offset(skip).limit(limit)

            result = await db.execute(query)
            db_objs = result.scalars().all()

            # 数据库模型列表转响应模型列表
            return [cls.response_model.model_validate(db_obj) for db_obj in db_objs]
        except Exception as e:
            logger.error(f"Error in {cls.__name__}.list: {str(e)}")
            raise


# 优化后的任务CRUD类
class TaskCRUD(BaseCRUD[Task, TaskCreate, TaskUpdate, TaskConfig]):
    """任务 CRUD 操作"""

    model = Task
    create_model = TaskCreate
    update_model = TaskUpdate
    response_model = TaskConfig


class TaskExecutionCRUD:
    @staticmethod
    async def create_execution(
        db: AsyncSession,
        task_id: int,
        server_id: int,
        status: TaskStatus = TaskStatus.RUNNING,
    ) -> TaskExecutionConfig:
        """创建任务执行记录"""
        execution = TaskExecution(
            task_id=task_id,
            server_id=server_id,
            status=status,
            started_at=datetime.utcnow(),
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        return TaskExecutionConfig.model_validate(execution)

    @staticmethod
    async def update_execution_status(
        db: AsyncSession,
        execution_id: int,
        status: TaskStatus,
        error_message: Optional[str] = None,
        result: Optional[Dict] = None,
    ) -> Optional[TaskExecutionConfig]:
        """更新执行状态"""
        execution = await TaskExecutionCRUD.get_execution(db, execution_id)
        if execution:
            execution.status = status
            execution.completed_at = (
                datetime.utcnow()
                if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
                else None
            )
            execution.error_message = error_message
            execution.result = result
            await db.commit()
            await db.refresh(execution)
            return TaskExecutionConfig.model_validate(execution)
        return None

    @staticmethod
    async def get_execution(
        db: AsyncSession, execution_id: int
    ) -> Optional[TaskExecutionConfig]:
        """获取执行记录详情"""
        result = await db.execute(
            select(TaskExecution).where(TaskExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if execution:
            return TaskExecutionConfig.model_validate(execution)
        return None

    @staticmethod
    async def list_task_executions(
        db: AsyncSession, task_id: int, skip: int = 0, limit: int = 100
    ) -> List[TaskExecutionConfig]:
        """获取任务执行历史"""
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == task_id)
            .offset(skip)
            .limit(limit)
        )
        executions = result.scalars().all()
        return [
            TaskExecutionConfig.model_validate(execution) for execution in executions
        ]


class ServerCRUD:
    @staticmethod
    async def create_server(
        db: AsyncSession, server_data: ServerCreate
    ) -> ServerConfig:
        """创建服务器记录"""
        server = Server(
            name=server_data.name,
            url=server_data.url,
            status=ServerStatus.OFFLINE,
            source=server_data.source,
            available_start=server_data.available_start,
            available_end=server_data.available_end,
        )
        db.add(server)
        await db.commit()
        await db.refresh(server)
        return ServerConfig.model_validate(server)

    @staticmethod
    async def update_server(
        db: AsyncSession, server_id: int, server_data: ServerUpdate
    ) -> Optional[ServerConfig]:
        """更新服务器信息"""
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()

        if not server:
            return None

        # 更新字段
        update_data = server_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(server, key, value)

        # 更新时间戳
        server.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(server)
        return ServerConfig.model_validate(server)

    @staticmethod
    async def delete_server(db: AsyncSession, server_id: int) -> bool:
        """删除服务器"""
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()

        if not server:
            return False

        await db.delete(server)
        await db.commit()
        return True

    @staticmethod
    async def update_server_status(
        db: AsyncSession, server_id: int, status: ServerStatus
    ) -> Optional[ServerConfig]:
        """更新服务器状态"""
        await db.execute(
            update(Server)
            .where(Server.id == server_id)
            .values(
                status=status,
                last_check=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        await db.commit()
        return await ServerCRUD.get_server(db, server_id)

    @staticmethod
    async def get_server(db: AsyncSession, server_id: int) -> Optional[ServerConfig]:
        """获取服务器详情"""
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if server:
            return ServerConfig.model_validate(server)
        return None

    @staticmethod
    async def list_servers(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[ServerConfig]:
        """获取服务器列表"""
        result = await db.execute(select(Server).offset(skip).limit(limit))
        servers = result.scalars().all()
        return [ServerConfig.model_validate(server) for server in servers]

    @staticmethod
    async def list_available_servers(
        db: AsyncSession, current_time: time, skip: int = 0, limit: int = 100
    ) -> List[ServerConfig]:
        """获取当前时间可用的服务器列表"""
        query = (
            select(Server)
            .where(
                (Server.status == ServerStatus.ONLINE)
                & (
                    # 如果没有设置可用时间，则视为全天可用
                    (
                        (Server.available_start.is_(None))
                        & (Server.available_end.is_(None))
                    )
                    |
                    # 如果开始时间小于结束时间，例如 9:00-18:00
                    (
                        (Server.available_start <= current_time)
                        & (Server.available_end >= current_time)
                    )
                    |
                    # 如果开始时间大于结束时间(跨午夜)，例如 22:00-6:00
                    (
                        (Server.available_start >= Server.available_end)
                        & (
                            (Server.available_start <= current_time)
                            | (Server.available_end >= current_time)
                        )
                    )
                )
            )
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)
        servers = result.scalars().all()
        return [ServerConfig.model_validate(server) for server in servers]


# 优化后的工作流CRUD类
class WorkflowCRUD(BaseCRUD[Workflow, WorkflowCreate, WorkflowUpdate, WorkflowConfig]):
    """工作流 CRUD 操作"""

    model = Workflow
    create_model = WorkflowCreate
    update_model = WorkflowUpdate
    response_model = WorkflowConfig

    @classmethod
    async def create_workflow(
        cls, db: AsyncSession, workflow_in: WorkflowCreate
    ) -> WorkflowConfig:
        """创建新工作流，增加了重名检查"""
        try:
            logger.debug(f"Creating workflow: {workflow_in.model_dump_json()}")

            # 检查同名同版本的工作流是否已存在
            existing = await cls.get_workflow_by_name_and_version(
                db, workflow_in.name, workflow_in.version
            )
            if existing:
                raise ValueError(
                    f"Workflow with name {workflow_in.name} and version {workflow_in.version} already exists"
                )

            # 使用通用方法创建
            db_workflow = Workflow(**workflow_in.model_dump())
            db_workflow.status = "normal"  # 默认状态为 normal

            logger.debug(f"Workflow object created: {db_workflow}")

            db.add(db_workflow)
            await db.commit()
            await db.refresh(db_workflow)

            logger.debug(f"Workflow saved with ID: {db_workflow.id}")

            # 使用model_validate自动处理字段映射
            return WorkflowConfig.model_validate(db_workflow)
        except Exception as e:
            logger.error(f"Error in create_workflow: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            await db.rollback()
            raise

    @classmethod
    async def get_workflow(
        cls, db: AsyncSession, workflow_id: int
    ) -> Optional[WorkflowConfig]:
        """通过ID获取工作流"""
        return await cls.get(db, workflow_id)

    @classmethod
    async def get_workflow_by_name_and_version(
        cls, db: AsyncSession, name: str, version: str
    ) -> Optional[WorkflowConfig]:
        """通过名称和版本获取工作流"""
        try:
            result = await db.execute(
                select(Workflow)
                .where(Workflow.name == name)
                .where(Workflow.version == version)
            )
            workflow = result.scalars().first()

            if workflow is None:
                return None

            # 使用model_validate自动处理字段映射
            return WorkflowConfig.model_validate(workflow)
        except Exception as e:
            logger.error(f"Error in get_workflow_by_name_and_version: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            raise

    @classmethod
    async def create_new_version(
        cls, db: AsyncSession, workflow_id: int, workflow_in: WorkflowConfig
    ) -> WorkflowConfig:
        """根据已有工作流创建新版本"""
        try:
            # 检查原工作流是否存在
            db_workflow = await cls.get_workflow(db, workflow_id)
            if not db_workflow:
                raise HTTPException(
                    status_code=404, detail=f"Workflow with id {workflow_id} not found"
                )

            # 创建新工作流的字典
            new_workflow_data = db_workflow.model_dump()

            # 更新需要改变的字段
            update_data = workflow_in.model_dump(exclude_unset=True)
            new_workflow_data.update(update_data)

            # 设置特定字段
            new_workflow_data["version"] = str(
                int(db_workflow.version) + 1
            )  # 增加版本号
            new_workflow_data["parent_id"] = workflow_id
            new_workflow_data["status"] = "normal"
            new_workflow_data.pop("id", None)  # 移除ID以创建新记录
            new_workflow_data.pop("created_at", None)
            new_workflow_data.pop("updated_at", None)

            # 创建新工作流
            new_workflow = Workflow(**new_workflow_data)

            db.add(new_workflow)
            await db.commit()
            await db.refresh(new_workflow)

            # 使用model_validate自动处理字段映射
            return WorkflowConfig.model_validate(new_workflow)
        except Exception as e:
            logger.error(f"Error in create_new_version: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            await db.rollback()
            raise

    @classmethod
    async def hide_workflow(
        cls, db: AsyncSession, workflow_id: int
    ) -> Optional[WorkflowConfig]:
        """隐藏工作流"""
        try:
            result = await db.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()
            if not workflow:
                return None

            workflow.status = "hidden"  # 使用字符串
            await db.commit()
            await db.refresh(workflow)

            # 使用model_validate自动处理字段映射
            return WorkflowConfig.model_validate(workflow)
        except Exception as e:
            logger.error(f"Error in hide_workflow: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            raise

    @classmethod
    async def show_workflow(
        cls, db: AsyncSession, workflow_id: int
    ) -> Optional[WorkflowConfig]:
        """显示工作流"""
        try:
            result = await db.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()
            if not workflow:
                return None

            workflow.status = "normal"  # 使用字符串
            await db.commit()
            await db.refresh(workflow)

            # 使用model_validate自动处理字段映射
            return WorkflowConfig.model_validate(workflow)
        except Exception as e:
            logger.error(f"Error in show_workflow: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            raise

    @classmethod
    async def list_workflows(
        cls,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status: Optional[WorkflowStatus] = None,
        scenario: Optional[str] = None,
    ) -> List[WorkflowConfig]:
        """获取工作流列表，支持筛选"""

        # 默认只显示正常状态的工作流
        if status is None:
            status = WorkflowStatus.NORMAL

        # 使用基类的list方法，传入筛选条件
        return await cls.list(
            db, skip=skip, limit=limit, status=status, scenario=scenario
        )

    @classmethod
    async def get_workflow_versions(
        cls, db: AsyncSession, workflow_id: int
    ) -> List[WorkflowConfig]:
        """获取工作流的所有版本"""
        try:
            workflow = await cls.get_workflow(db, workflow_id)
            if not workflow:
                return []

            # 获取所有相关版本（包括父版本和子版本）
            result = await db.execute(
                select(Workflow)
                .where(
                    (Workflow.id == workflow_id)
                    | (Workflow.parent_id == workflow_id)
                    | (Workflow.id == workflow.parent_id)
                )
                .order_by(Workflow.version)
            )
            workflows = result.scalars().all()

            # 使用model_validate自动处理字段映射
            return [WorkflowConfig.model_validate(w) for w in workflows]
        except Exception as e:
            logger.error(f"Error in get_workflow_versions: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            raise

    @classmethod
    async def delete_workflow(
        cls, db: AsyncSession, workflow_id: int, user_id: int = None
    ) -> bool:
        """
        逻辑删除工作流（将状态设置为hidden）

        只有以下情况允许删除：
        1. 当前用户是创建者（workflow.user_id == user_id）
        2. 当前用户是管理员（user_id == 1）
        3. 未提供user_id时跳过检查（内部调用）
        """
        try:
            # 先获取工作流信息
            result = await db.execute(
                select(cls.model).where(cls.model.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()

            if workflow is None:
                return False

            # 权限检查（仅当提供了user_id时进行）
            if user_id is not None and workflow.user_id != user_id and user_id != 1:
                logger.warning(
                    f"Permission denied: User {user_id} attempted to delete workflow {workflow_id} owned by user {workflow.user_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Permission denied: You can only delete workflows that you created",
                )

            # 执行逻辑删除：将状态设置为hidden
            workflow.status = "hidden"  # 或者使用枚举 WorkflowStatus.HIDDEN.value
            workflow.updated_at = datetime.utcnow()  # 更新修改时间

            await db.commit()
            await db.refresh(workflow)

            if user_id:
                logger.info(
                    f"Workflow {workflow_id} logically deleted (hidden) by user {user_id}"
                )
            else:
                logger.info(
                    f"Workflow {workflow_id} logically deleted (hidden) by system"
                )
            return True

        except HTTPException:
            # 重新抛出HTTP异常，让FastAPI处理
            raise
        except Exception as e:
            logger.error(f"Error in delete_workflow: {str(e)}")
            await db.rollback()
            raise

    @classmethod
    async def restore_workflow(
        cls, db: AsyncSession, workflow_id: int, user_id: int = None
    ) -> Optional[WorkflowConfig]:
        """恢复被逻辑删除的工作流"""
        try:
            # 获取工作流
            result = await db.execute(
                select(cls.model).where(cls.model.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()

            if not workflow:
                return None

            # 权限检查（仅当提供了user_id时进行）- 通常只有管理员可以恢复
            if user_id is not None and user_id != 1:
                logger.warning(
                    f"Permission denied: User {user_id} attempted to restore workflow {workflow_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Permission denied: Only administrators can restore workflows",
                )

            # 恢复工作流状态为normal
            workflow.status = "normal"  # 或者使用枚举 WorkflowStatus.NORMAL.value
            workflow.updated_at = datetime.utcnow()

            await db.commit()
            await db.refresh(workflow)

            logger.info(
                f"Workflow {workflow_id} restored by user {user_id or 'system'}"
            )
            return WorkflowConfig.model_validate(workflow)

        except Exception as e:
            logger.error(f"Error in restore_workflow: {str(e)}")
            await db.rollback()
            raise
