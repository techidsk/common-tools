from datetime import datetime
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

from src.compute import (
    AutoDLConfig,
    AutoDLRegion,
    ComputeServiceFactory,
)
from src.compute import (
    CloudProvider as BaseCloudProvider,
)


class CloudProvider(str, Enum):
    """云服务提供商枚举"""

    AUTODL = "autodl"


class InstanceStatus(str, Enum):
    """实例状态枚举"""

    RUNNING = "running"
    STOPPED = "stopped"
    PENDING = "pending"
    TERMINATED = "terminated"
    ERROR = "error"


class CloudInstance(BaseModel):
    """云实例信息模型"""

    instance_id: str
    name: str | None = None
    status: InstanceStatus
    provider: CloudProvider
    region: str
    gpu_type: str | None = None
    gpu_count: int | None = None
    memory_gb: int | None = None
    hourly_price: float | None = None
    created_at: datetime
    last_check: datetime = Field(default_factory=datetime.now)


class CloudBalance(BaseModel):
    """云平台余额信息模型"""

    provider: CloudProvider
    balance: float
    currency: str = "CNY"
    last_check: datetime = Field(default_factory=datetime.now)


async def fetch_autodl_resources() -> tuple[CloudBalance, list[CloudInstance]]:
    """获取 AutoDL 的余额和实例信息"""
    # 创建 AutoDL 配置
    autodl_config = AutoDLConfig(
        region=AutoDLRegion.WEST_DC2,
        cuda_version=122,
        min_memory_gb=32,
        max_memory_gb=256,
        min_cpu_cores=16,
        max_cpu_cores=64,
        min_price=100,
        max_price=9000,
    )

    # 获取 adapter
    adapter = await ComputeServiceFactory.get_adapter(
        BaseCloudProvider.AUTODL, autodl_config
    )

    # 获取余额
    balance_data = await adapter._fetch_balance()
    balance = CloudBalance(
        provider=CloudProvider.AUTODL,
        balance=balance_data["assets"] / 1000,  # 转换为元
    )

    # 获取实例列表
    raw_instances = await adapter.list_instances()
    instances = []

    for machine in raw_instances:
        if not machine.details:
            continue

        instances.append(
            CloudInstance(
                instance_id=machine.instance_id,
                status=InstanceStatus(machine.status.lower()),
                provider=CloudProvider.AUTODL,
                region=autodl_config.region.value,
                gpu_type=machine.details.get("gpu_type"),
                gpu_count=machine.details.get("gpu_count", 1),
                memory_gb=machine.details.get("memory_gb"),
                hourly_price=machine.details.get("price"),
                created_at=datetime.now(),  # TODO: 从实例详情中获取创建时间
            )
        )

    return balance, instances


async def check_cloud_resources():
    """检查云平台资源的主任务"""
    logger.info("Starting AutoDL resources check")

    try:
        balance, instances = await fetch_autodl_resources()

        # 输出余额信息
        logger.info(
            f"=== AutoDL 账户余额信息 ===\n"
            f"查询时间: {balance.last_check.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"当前可用余额: {balance.currency} {balance.balance:.2f}\n"
            f"========================"
        )

        # 输出实例信息
        logger.info(f"Found {len(instances)} instances:")
        for instance in instances:
            logger.info(
                f"Instance {instance.instance_id}:\n"
                f"  Status: {instance.status.value}\n"
                f"  GPU: {instance.gpu_type} x{instance.gpu_count}\n"
                f"  Memory: {instance.memory_gb}GB\n"
                f"  Price: ¥{instance.hourly_price}/hour"
            )

        # TODO: 可以在这里添加数据存储逻辑

    except Exception as e:
        logger.error(f"Error checking AutoDL resources: {e}")
        logger.exception(e)
