import asyncio
import os
from loguru import logger
from typing import Optional, List
from datetime import datetime

from src.compute import (
    ComputeService,
    ComputeServiceFactory,
    CloudProvider,
    SystemRequirements,
    UnifiedGPUModel,
    GPURequirements,
    AutoDLConfig,
    AutoDLRegion,
    MachineSpec
)
from src.compute.autodl_adapter import AutoDLAdapter

async def get_available_gpus(autodl_config: AutoDLConfig) -> List[MachineSpec]:
    """获取 AutoDL 当前可用的 GPU"""
    # 获取 adapter
    adapter = await ComputeServiceFactory.get_adapter(CloudProvider.AUTODL, autodl_config)
    
    # 获取所有机器
    machines = await adapter.list_instances()
    
    # 打印可用 GPU 信息
    logger.info("Available GPUs:")
    for machine in machines:
        if not machine.details:
            continue
            
        gpu_info = machine.details.get("gpu_type")
        gpu_count = machine.details.get("gpu_count", 1)
        memory = machine.details.get("memory_gb")
        price = machine.details.get("price")
        
        logger.info(
            f"GPU: {gpu_info}, Count: {gpu_count}, "
            f"Memory: {memory}GB, Price: ￥{price}/h"
        )
    
    return machines

async def create_autodl_instance(
    autodl_config: AutoDLConfig,
    gpu_model: UnifiedGPUModel,
    name: str = "test-instance"
) -> Optional[MachineSpec]:
    """创建 AutoDL 实例"""
    service = ComputeService()
    service.add_cloud_config(CloudProvider.AUTODL, autodl_config)
    
    # 定义系统要求
    requirements = SystemRequirements(
        min_cpu_cores=16,
        min_memory_gb=32,
        min_disk_gb=100,
        gpu_requirements=GPURequirements(
            model=gpu_model,
            count=1,
            min_memory_gb=24,
            min_cuda_version="12.0"
        )
    )
    
    # 查找符合要求的机器
    machines = await service.find_suitable_machines(
        requirements=requirements,
        provider=CloudProvider.AUTODL,
        count=1
    )
    
    if not machines:
        logger.error("No suitable machines found")
        return None
    
    # 注册并初始化机器
    initialized_machines = await service.register_and_initialize_machines(machines)
    if not initialized_machines:
        logger.error("Failed to initialize machine")
        return None
    
    # 部署服务
    service_config = {
        "name": name,
        "service_url": "http://{ip}:8000",
        "health_check_url": "http://{ip}:8000/health",
        "environment": {
            "CUDA_VISIBLE_DEVICES": "0"
        }
    }
    
    services = await service.deploy_services(initialized_machines, service_config)
    if not services:
        logger.error("Failed to deploy service")
        return None
    
    logger.info(f"Successfully created instance: {services[0].machine_id}")
    return initialized_machines[0]

async def format_balance_info(autodl_config: AutoDLConfig) -> None:
    """格式化显示 AutoDL 账户余额信息"""
    adapter: AutoDLAdapter = await ComputeServiceFactory.get_adapter(CloudProvider.AUTODL, autodl_config)
    balance = await adapter._fetch_balance()
    
    if not balance:
        logger.error("Failed to fetch balance information")
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 转换金额（除以1000转换为元）
    available_balance = balance['assets'] / 1000
    
    logger.info("=== AutoDL 账户余额信息 ===")
    logger.info(f"查询时间: {current_time}")
    logger.info(f"当前可用余额: ¥{available_balance:.2f}")
    logger.info("========================")

async def main():
    try:
        # 创建 AutoDL 配置 (会自动从环境变量读取)
        autodl_config = AutoDLConfig(
            region=AutoDLRegion.WEST_DC2,
            cuda_version=122,
            min_memory_gb=32,
            max_memory_gb=256,
            min_cpu_cores=16,
            max_cpu_cores=64,
            min_price=100,
            max_price=9000
        )
        
        # 添加余额查询
        await format_balance_info(autodl_config)
        
        # 获取可用 GPU
        logger.info("Fetching available GPUs...")
        available_machines = await get_available_gpus(autodl_config)
        
        if not available_machines:
            logger.warning("No available machines found")
            return
        
        logger.info(f"Available machines: {available_machines}")
        # for machine in available_machines:
        #     logger.info(f"Found machine: {machine.instance_id}")
        #     logger.info(f"Status: {machine.status}")
        #     if machine.details:
        #         logger.info("Details:")
        #         for key, value in machine.details.items():
        #             logger.info(f"  {key}: {value}")
        #     logger.info("---")
        
        # # 创建新实例
        # if input("Do you want to create a new instance? (y/N): ").lower() == 'y':
        #     logger.info("Creating new instance...")
        #     instance = await create_autodl_instance(
        #         autodl_config=autodl_config,
        #         gpu_model=UnifiedGPUModel.RTX_4090,
        #         name="ml-training"
        #     )
            
        #     if instance:
        #         logger.info(f"Instance created successfully:")
        #         logger.info(f"ID: {instance.instance_id}")
        #         logger.info(f"Status: {instance.status}")
        #         if instance.details:
        #             logger.info(f"GPU: {instance.details.get('gpu_type')}")
        #             logger.info(f"Public IP: {instance.details.get('public_ip')}")
        #             logger.info(f"Private IP: {instance.details.get('private_ip')}")
    
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.exception(e)

if __name__ == "__main__":
    asyncio.run(main()) 