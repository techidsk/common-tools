import asyncio
import traceback
from pathlib import Path
from typing import List

from loguru import logger
from prefect import flow, get_run_logger, task
from pydantic import BaseModel, Field

from src.dispatcher import ComfyUIServer, TaskDispatcher, TaskDispatcherConfig
from src.retriever import FileRetriever, FileRetrieverConfig
from src.workflow import WorkflowConfig, WorkflowManager


class ServiceConfig(BaseModel):
    """服务配置"""

    # 文件检索配置
    target_folders: List[Path] = Field(..., description="目标文件夹列表")
    folder_keywords: List[str] = Field(default_factory=list, description="文件夹关键词")
    image_extensions: set[str] = Field(
        default_factory=lambda: {".png", ".jpg", ".jpeg", ".webp"}, description="图片扩展名"
    )

    # 工作流配置
    workflow_path: Path = Field(..., description="工作流JSON文件路径")
    node_config_path: Path = Field(..., description="节点配置JSON文件路径")

    # 输出配置
    output_root: Path = Field(default=Path("outputs"), description="输出根目录")
    batch_size: int = Field(default=3, description="批处理大小")

    # 服务器配置
    servers: List[str] = Field(default_factory=list, description="服务器列表")


class BatchProcessor:
    """批处理服务"""

    def __init__(self, config: ServiceConfig):
        self.config = config
        self._setup_components()

    def _setup_components(self):
        """初始化各个组件"""
        # 文件检索器
        self.retriever = FileRetriever(
            FileRetrieverConfig(
                target_folders=self.config.target_folders,
                folder_keywords=self.config.folder_keywords,
                image_extensions=self.config.image_extensions,
            )
        )

        # 工作流管理器
        self.workflow_manager = WorkflowManager(
            WorkflowConfig(
                workflow_path=self.config.workflow_path,
                node_config_path=self.config.node_config_path,
            )
        )

        # 任务分发器
        if self.config.servers:
            self.servers = [ComfyUIServer(**{"url": server}) for server in self.config.servers]

        self.dispatcher = TaskDispatcher(TaskDispatcherConfig(
            servers=self.servers or [],
        ))

    async def _check_servers(self) -> bool:
        """检查服务器状态"""
        if not self.dispatcher.available_servers:
            if not await self.dispatcher.ensure_initialized():
                logger.error("服务器初始化失败")
                return False

        return len(self.dispatcher.available_servers) > 0

    @task(name="scan_folders", retries=3, cache_key_fn=None, cache_policy=None)
    async def scan_folders(self) -> List[Path]:
        """扫描文件夹获取图片列表"""
        logger = get_run_logger()
        image_files = self.retriever.scan_folders()
        logger.info(f"找到 {len(image_files)} 个文件待处理")
        return image_files

    @task(name="process_batch", cache_key_fn=None, cache_policy=None)
    async def process_batch(self, batch: List[Path]) -> List[str]:
        """处理一批图片"""
        logger = get_run_logger()

        try:
            # 检查服务器状态
            if not await self._check_servers():
                logger.error("没有可用的服务器，终止批处理")
                return []

            # 获取可用的服务器并转换为列表
            available_servers = list(self.dispatcher.available_servers)
            server_count = len(available_servers)
            logger.info(f"当前可用服务器数量: {server_count}")

            # 创建所有任务
            tasks = []
            for idx, img_path in enumerate(batch):
                server_idx = idx % server_count
                server = available_servers[server_idx]
                
                logger.info(f"分配任务 - 图片: {img_path.name} -> 服务器: {server.url}")
                
                # 准备工作流
                image_base64 = self.workflow_manager.prepare_image(img_path)
                prompt = self.workflow_manager.prepare_workflow(
                    image=image_base64,
                    output_folder=str(self.config.output_root),
                )

                # 创建任务并立即提交
                tasks.append(
                    asyncio.create_task(
                        self._process_single_image(img_path, server, prompt)
                    )
                )

            if not tasks:
                logger.warning("没有可处理的任务")
                return []

            # 并发执行所有任务，使用 as_completed 立即处理完成的任务
            all_paths = []
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    if isinstance(result, list):
                        all_paths.extend(result)
                        logger.info(f"任务完成，生成了 {len(result)} 个文件")
                except Exception as e:
                    logger.error(f"任务执行失败: {str(e)}")

            logger.info(f"批次处理完成，生成了 {len(all_paths)} 个文件")
            return all_paths

        except Exception as e:
            logger.error(f"批处理过程中出错: {str(e)}", exc_info=True)
            return []

    async def _process_single_image(
        self, path: Path, server: ComfyUIServer, prompt: dict
    ) -> List[str]:
        """处理单张图片的完整流程"""
        logger = get_run_logger()
        try:
            logger.info(f"使用服务器 {server.url} 处理图片 {path.name}")
            
            # 提交任务到服务器
            prompt_id = await self.dispatcher.queue_prompt_to_server(prompt, server)
            
            # 获取结果
            output_images, status = await self.dispatcher.get_result(prompt_id, server)

            if status != "SUCCESS":
                logger.error(f"任务失败 - 服务器: {server.url}, 状态: {status}")
                return []

            # 保存结果
            return self.dispatcher.save_images(
                output_images,
                task_name=f"{path.parent.name}",
                output_filename=f"{path.stem}",
            )

        except Exception as e:
            logger.error(f"处理图片失败 - {path}, 服务器: {server.url}, 错误: {str(e)}")
            traceback.print_exc()
            return []

    @flow(name="batch_process_flow", cache_result_in_memory=None)
    async def process_folder(self, folder_path: Path) -> List[str]:
        """处理整个文件夹"""
        logger = get_run_logger()
        logger.info(f"开始处理文件夹: {folder_path}")

        try:
            # 扫描文件夹
            image_files = await self.scan_folders()
            if not image_files:
                logger.warning(f"未找到符合条件的图片: {folder_path}")
                return []

            # 获取可用的服务器
            if not await self._check_servers():
                logger.error("没有可用的服务器，终止处理")
                return []

            available_servers = list(self.dispatcher.available_servers)
            server_count = len(available_servers)
            logger.info(f"当前可用服务器数量: {server_count}")

            # 创建任务队列
            all_results = []
            active_tasks = set()
            total_files = len(image_files)
            processed_count = 0

            async def process_single_image(img_path: Path, server: ComfyUIServer):
                """处理单张图片"""
                try:
                    image_base64 = self.workflow_manager.prepare_image(img_path)
                    prompt = self.workflow_manager.prepare_workflow(
                        image=image_base64,
                        output_folder=str(self.config.output_root),
                    )
                    return await self._process_single_image(img_path, server, prompt)
                except Exception as e:
                    logger.error(f"处理失败 {img_path}: {str(e)}")
                    return []

            # 处理所有图片
            for i, img_path in enumerate(image_files):
                server = available_servers[i % server_count]
                
                # 创建新任务
                task = asyncio.create_task(process_single_image(img_path, server))
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)

                # 如果活动任务数达到批处理大小，等待一个任务完成
                while len(active_tasks) >= self.config.batch_size:
                    done, _ = await asyncio.wait(
                        active_tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for completed_task in done:
                        try:
                            result = await completed_task
                            if isinstance(result, list):
                                all_results.extend(result)
                                processed_count += 1
                                logger.info(f"进度: {processed_count}/{total_files}")
                        except Exception as e:
                            logger.error(f"任务执行失败: {str(e)}")

            # 等待剩余的任务完成
            if active_tasks:
                for completed_task in asyncio.as_completed(active_tasks):
                    try:
                        result = await completed_task
                        if isinstance(result, list):
                            all_results.extend(result)
                            processed_count += 1
                            logger.info(f"进度: {processed_count}/{total_files}")
                    except Exception as e:
                        logger.error(f"任务执行失败: {str(e)}")

            logger.info(f"文件夹处理完成，共生成 {len(all_results)} 个文件")
            return all_results

        finally:
            await self.dispatcher.close()

    @flow(name="main_flow", cache_result_in_memory=None)
    async def run(self) -> None:
        """运行主流程"""
        logger = get_run_logger()

        # 检查服务器状态
        if not await self._check_servers():
            logger.error("没有可用的服务器，终止处理")
            return

        logger.info(
            f"开始处理，可用服务器数量: {len(self.dispatcher.available_servers)}"
        )

        for folder in self.config.target_folders:
            try:
                results = await self.process_folder(folder)
                logger.info(f"文件夹 {folder} 处理完成，生成了 {len(results)} 个文件")
            except Exception as e:
                logger.error(f"处理文件夹 {folder} 时出错: {e}")
