import asyncio
from pathlib import Path
from typing import Any, List, Optional
from loguru import logger
from src.service import ServiceConfig, BatchProcessor
from pydantic import BaseModel, Field
import time
import random
from asyncio import Semaphore


class ProcessingConfig(BaseModel):
    """处理任务的配置模型"""
    target_folder: Path
    node_config_path: Path
    generations_per_style: int = 10
    size_suffix: str = ""
    max_retries: int = 3
    retry_delay: float = 2.0


async def create_service_config(config: ProcessingConfig) -> ServiceConfig:
    """创建服务配置"""
    return ServiceConfig(
        target_folders=[config.target_folder],
        input_mapping={
            "model_image": {
                "path": "模特",
                "description": "模特图片输入",
                "required": True,
                "is_main": False,
                "random_select": True,
            },
            "reference_image": {
                "path": "款式",
                "description": "款式图片输入",
                "required": True,
                "is_main": True,
                "max_generations_per_input": 10,
                "min_generations_per_input": 1,
                "generations_per_style": config.generations_per_style,
            },
        },
        workflow_path=Path(r"modules\comfyui\workflows\pl_0327_api.json"),
        node_config_path=config.node_config_path,
        servers=[
            "http://10.31.0.141:9199",
            "http://10.31.0.138:8188",
            "http://10.31.0.138:8189",
            "http://10.31.0.139:8188",
            "http://10.31.0.139:8189",
        ],
        output_root=Path("outputs"),
        batch_size=5,
    )


async def process_task(config: ProcessingConfig, semaphore: Semaphore) -> None:
    """处理单个任务，包含重试逻辑和资源限制"""
    task_id = f"{config.target_folder.name}_{int(time.time())}"
    logger.info(f"[{task_id}] 等待资源获取...")
    
    async with semaphore:
        logger.info(f"[{task_id}] 开始处理任务: {config.target_folder}")
        service_config = await create_service_config(config)
        processor = BatchProcessor(service_config)

        for attempt in range(1, config.max_retries + 1):
            try:
                await processor.run()
                logger.info(f"[{task_id}] 完成处理任务: {config.target_folder}")
                return
            except Exception as e:
                if "database is locked" in str(e):
                    if attempt < config.max_retries:
                        # 添加随机抖动避免所有任务同时重试
                        jitter = random.uniform(0.1, 1.0)
                        retry_time = config.retry_delay * attempt + jitter
                        logger.warning(
                            f"[{task_id}] 数据库锁定错误，将在 {retry_time:.2f} 秒后重试 "
                            f"(尝试 {attempt}/{config.max_retries}): {str(e)}"
                        )
                        await asyncio.sleep(retry_time)
                    else:
                        logger.error(
                            f"[{task_id}] 达到最大重试次数，任务失败: {config.target_folder}, 错误: {str(e)}"
                        )
                        raise
                else:
                    logger.error(f"[{task_id}] 处理任务时发生错误: {str(e)}")
                    raise


async def main() -> None:
    """主函数"""
    # 设置日志
    logger.add("debug.log", level="DEBUG", rotation="100 MB", retention="1 week")

    # 定义处理任务
    tasks = [
        ProcessingConfig(
            target_folder=Path(r"D:\ftp\客户素材\P-pl\0327_批量测试\1500乘2000"),
            node_config_path=Path(r"modules\comfyui\workflows\pl_0327_config.json"),
            generations_per_style=10,
        ),
        ProcessingConfig(
            target_folder=Path(r"D:\ftp\客户素材\P-pl\0327_批量测试\1500乘1500"),
            node_config_path=Path(r"modules\comfyui\workflows\pl_0327_config_sq.json"),
            generations_per_style=20,
        ),
    ]
    
    # 创建一个信号量来限制并发任务数量（避免数据库锁定问题）
    # 使用较小的并发数避免数据库锁争用
    concurrency_limit = 1  # 设置为1开始，根据实际情况可以调整
    semaphore = Semaphore(concurrency_limit)
    
    logger.info(f"开始批处理，并发限制为 {concurrency_limit}")
    
    try:
        # 串行执行任务以避免数据库锁争用
        if concurrency_limit == 1:
            for config in tasks:
                await process_task(config, semaphore)
        else:
            # 以受控的并发方式执行任务
            await asyncio.gather(
                *(process_task(config, semaphore) for config in tasks)
            )
        logger.success("所有任务已完成")
    except Exception as e:
        logger.error(f"执行过程中发生错误: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
