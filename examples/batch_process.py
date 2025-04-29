import asyncio
from pathlib import Path
from typing import List, Dict
import random
from loguru import logger
from datetime import datetime

from src.dispatcher import TaskDispatcher, TaskDispatcherConfig
from src.retriever import FileRetriever, FileRetrieverConfig
from modules.io.image import load_image_to_base64
from src.workflow import WorkflowConfig, WorkflowManager


async def process_folder_images(
    dispatcher: TaskDispatcher,
    workflow_manager: WorkflowManager,
    folder_path: Path,
    batch_size: int = 3,
    output_root: Path = Path("outputs")
) -> List[str]:
    """批量处理文件夹中的图片
    
    Args:
        dispatcher: 任务分发器
        workflow_manager: 工作流管理器
        folder_path: 目标文件夹路径
        batch_size: 并发批处理大小
        output_root: 输出根目录
    """
    # 准备输出目录
    folder_name = folder_path.name
    current_date = datetime.now().strftime("%Y-%m-%d")
    output_path = output_root / "daily" / current_date / folder_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 查找参考图片
    ref_image1_path, ref_image2_path = workflow_manager.find_reference_images(folder_path)
    if ref_image1_path:
        logger.info(f"找到参考图片1: {ref_image1_path}")
    if ref_image2_path:
        logger.info(f"找到参考图片2: {ref_image2_path}")
    
    # 配置文件检索器
    retriever_config = FileRetrieverConfig(
        target_folders=[folder_path],
        folder_keywords=["zebra"],  # 根据需要设置关键词
        image_extensions={".png", ".jpg", ".jpeg", ".webp"},
    )
    retriever = FileRetriever(retriever_config)
    
    # 获取所有符合条件的图片
    image_files = retriever.scan_folders()
    if not image_files:
        logger.warning(f"未找到符合条件的图片: {folder_path}")
        return []

    logger.info(f"找到 {len(image_files)} 个文件待处理")
    
    async def process_batch(batch: List[Path]) -> List[str]:
        """处理一批图片"""
        tasks = []
        for img_path in batch:
            # 准备工作流
            prompt = workflow_manager.prepare_workflow(
                main_image_path=img_path,
                ref_image1_path=ref_image1_path,
                ref_image2_path=ref_image2_path,
                randomize_seed=True
            )
            
            # 创建任务
            task = dispatcher.process_task(
                prompt=prompt,
                task_name=f"{folder_name}/{img_path.stem}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return [path for sublist in results for path in sublist]

    # 按批次处理所有图片
    all_results = []
    total_batches = (len(image_files) - 1) // batch_size + 1
    
    for i in range(0, len(image_files), batch_size):
        batch = image_files[i:i + batch_size]
        current_batch = i // batch_size + 1
        logger.info(f"处理批次 {current_batch}/{total_batches}")
        
        try:
            results = await process_batch(batch)
            all_results.extend(results)
            logger.success(f"批次 {current_batch} 完成，生成了 {len(results)} 个文件")
        except Exception as e:
            logger.error(f"批次 {current_batch} 处理失败: {e}")
            continue
        
    return all_results


async def main():
    config = TaskDispatcherConfig()
    dispatcher = TaskDispatcher(config)
    
    # 配置工作流管理器
    workflow_config = WorkflowConfig(
        workflow_path=Path("modules/comfyui/workflows/1219_v2.json"),
        image_node_id="5",
        ref_image1_node_id="12",
        ref_image2_node_id="490",
        ref_image2_switch_node_id="523",
        resize_short_edge=1536
    )
    workflow_manager = WorkflowManager(workflow_config)
    
    try:
        target_folder = Path(r"F:/Work/WCY/WCY-AI需求12.14/B55031511  牛仔裤N30731511")
        results = await process_folder_images(
            dispatcher=dispatcher,
            workflow_manager=workflow_manager,
            folder_path=target_folder,
            batch_size=3,
            output_root=Path("outputs")
        )
        
        logger.info(f"处理完成，共生成了 {len(results)} 个文件")
        logger.info("生成的文件列表:")
        for path in results:
            logger.info(f"  - {path}")
            
    finally:
        await dispatcher.close()


if __name__ == "__main__":
    asyncio.run(main()) 