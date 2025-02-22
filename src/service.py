"""基于 ComfyUI 服务器的图片批处理服务模块。

本模块提供了一个强大的服务，用于在多个 ComfyUI 服务器上批量处理图片。
主要功能包括：
- 根据可配置的条件扫描文件夹中的图片
- 管理和分发任务到多个 ComfyUI 服务器
- 处理工作流配置和图片处理任务
- 提供可配置批量大小的异步批处理
- 将处理结果保存到指定的输出目录

核心组件：
- ServiceConfig：服务配置模型
- BatchProcessor：主服务类，负责协调整个处理流程
- 工作流管理和任务分发功能
- 使用 loguru 进行错误处理和日志记录

本服务设计为可扩展和容错的，支持：
- 多服务器端点
- 并发任务处理
- 自动服务器健康检查
- 可配置的重试机制
- 详细的日志和错误报告

使用示例：
    ```python
    config = ServiceConfig(
        target_folders=[Path("input_folder")],
        workflow_path=Path("workflow.json"),
        node_config_path=Path("node_config.json"),
        servers=["http://localhost:8188"]
    )
    processor = BatchProcessor(config)
    await processor.run()
    ```
"""

import asyncio
import traceback
from pathlib import Path
from typing import List
from math import ceil

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
    input_mapping: dict[str, dict] = Field(
        default_factory=dict,
        description="""
        工作流输入映射配置，定义每个输入节点对应的图片来源，格式如：
        {
            "model_image": {  # 输入类型标识符
                "path": "模特",  # 对应的文件夹路径
                "description": "模特图输入",  # 描述信息
                "required": true,  # 是否必需
                "workflow_param": "image1",  # 工作流中实际使用的参数名称，可选，默认使用输入类型标识符
                "is_main": false,  # 是否是主导输入类型，决定处理循环的主体
                "total_generations": 10,  # 总生成数量限制
                "generations_per_input": 3  # 每个输入的生成次数
            },
            "reference_image": {
                "path": "款式",
                "description": "款式图片输入",
                "required": true,
                "workflow_param": "image2",
                "is_main": true
            }
        }
        """
    )

    # 工作流配置
    workflow_path: Path = Field(..., description="工作流JSON文件路径")
    node_config_path: Path = Field(..., description="节点配置JSON文件路径")

    # 输出配置
    output_root: Path = Field(default=Path("outputs"), description="输出根目录")
    batch_size: int = Field(default=3, description="批处理大小")

    # 服务器配置
    servers: List[str] = Field(default_factory=list, description="服务器列表")

    def get_input_type(self, path: Path) -> str:
        """根据路径获取输入类型"""
        path_str = str(path)
        for input_name, config in self.input_mapping.items():
            path_pattern = config["path"]
            # 检查文件夹路径匹配
            if path_pattern in path_str and f"\\{path_pattern}\\" in path_str:
                return input_name
        return "unknown"


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
        # 设置输入映射
        self.workflow_manager.set_input_mapping(self.config.input_mapping)

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

    @flow(name="batch_process_flow", cache_result_in_memory=None)
    async def process_folder(self, folder_path: Path) -> List[str]:
        """处理整个文件夹"""
        logger = get_run_logger()
        logger.info(f"开始处理文件夹: {folder_path}")

        try:
            # 扫描文件夹并按输入类型分组
            image_files = await self.scan_folders()
            if not image_files:
                logger.warning(f"未找到符合条件的图片: {folder_path}")
                return []

            # 将图片按输入类型分组
            input_groups = {}
            for img_path in image_files:
                input_type = self.config.get_input_type(img_path)
                if input_type not in input_groups:
                    input_groups[input_type] = []
                input_groups[input_type].append(img_path)
            
            # 打印详细的分组信息
            logger.info("=" * 50)
            logger.info("发现的图片分组信息：")
            for input_type, images in input_groups.items():
                logger.info(f"\n[{input_type}] 类型，共 {len(images)} 张图片:")
                for img in images:
                    logger.info(f"  - {img}")
            logger.info("=" * 50)

            # 检查必需的输入是否都存在
            missing_inputs = []
            for input_name, input_config in self.config.input_mapping.items():
                if input_config.get("required", False) and input_name not in input_groups:
                    missing_inputs.append(input_name)
            
            if missing_inputs:
                logger.error(f"缺少必需的输入类型: {', '.join(missing_inputs)}")
                return []

            # 获取所有必需的输入图片组
            input_images = {}
            for input_name, input_config in self.config.input_mapping.items():
                if input_config.get("required", True):
                    images = input_groups.get(input_name, [])
                    if not images:
                        logger.error(f"缺少输入类型 {input_name} 的图片")
                        return []
                    input_images[input_name] = images

            # 打印任务处理信息
            logger.info("\n任务处理信息：")
            for input_name, images in input_images.items():
                logger.info(f"{self.config.input_mapping[input_name]['description']}: {len(images)} 张图片")
            logger.info("=" * 50)

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
            processed_count = 0

            # 获取主输入类型（用于确定要处理的图片数量）
            try:
                main_input_type = next(name for name, config in self.config.input_mapping.items() 
                                     if config.get("is_main", False))
            except StopIteration:
                # 如果没有设置 is_main，使用第一个输入类型作为主输入
                logger.warning("未找到设置了 is_main: true 的输入类型，将使用第一个输入类型作为主输入")
                main_input_type = next(iter(self.config.input_mapping))
            
            logger.info(f"使用 {main_input_type} 作为主输入类型")
            main_images = input_images[main_input_type]
            
            # 获取主输入类型的配置
            main_config = self.config.input_mapping[main_input_type]
            
            # 获取生成次数的配置
            min_generations = main_config.get("min_generations", 1)  # 每个输入的最小生成次数
            max_generations = main_config.get("max_generations", 1)  # 每个输入的最大生成次数
            total_limit = main_config.get("total_generations", None)  # 总生成数量限制
            
            # 计算实际需要生成的总数
            total_inputs = len(main_images)
            max_possible_generations = total_inputs * max_generations
            
            if total_limit is not None and total_limit > 0:
                actual_total = min(total_limit, max_possible_generations)
                # 重新计算每个输入的最大生成次数
                adjusted_max_per_input = min(max_generations, ceil(actual_total / total_inputs))
                logger.info(f"由于总数限制 {total_limit}，每个输入的最大生成次数调整为 {adjusted_max_per_input}")
            else:
                actual_total = max_possible_generations
                adjusted_max_per_input = max_generations
            
            logger.info(
                f"生成配置:\n"
                f"- 输入图片数量: {total_inputs}\n"
                f"- 每个输入最小生成次数: {min_generations}\n"
                f"- 每个输入最大生成次数: {adjusted_max_per_input}\n"
                f"- 预计总生成数量: {actual_total}"
            )

            # 处理所有主输入图片
            import random
            task_count = 0
            generated_count = 0
            remaining_total = actual_total

            async def process_combined_images(main_path: Path, image_paths: dict[str, Path], server: ComfyUIServer):
                """处理一组输入图片"""
                try:
                    # 准备输入图片组
                    input_groups = {
                        input_type: [path] for input_type, path in image_paths.items()
                    }
                    
                    # 使用工作流管理器准备输入参数
                    workflow_inputs = self.workflow_manager.prepare_workflow_inputs(input_groups)
                    workflow_inputs["output_folder"] = str(self.config.output_root)
                    
                    # 准备工作流
                    prompt = self.workflow_manager.prepare_workflow(**workflow_inputs)
                    
                    # 生成输出文件名
                    # 获取主输入类型的路径作为基础
                    main_input_path = image_paths[main_input_type]
                    output_parts = [main_input_path.parent.name, main_input_path.stem]
                    
                    # 添加其他输入类型的信息
                    for input_type, path in image_paths.items():
                        if input_type != main_input_type:
                            output_parts.extend([input_type, path.stem])
                    output_name = "_".join(output_parts)
                    
                    # 处理并保存结果
                    return await self._process_single_image(
                        path=main_input_path,
                        server=server,
                        prompt=prompt,
                        output_name=output_name
                    )
                except Exception as e:
                    logger.error(f"处理失败: {str(e)}")
                    return []

            for main_path in main_images:
                if remaining_total <= 0:
                    logger.info("已达到总生成数量限制")
                    break
                    
                # 为当前输入计算生成次数
                max_for_current = min(adjusted_max_per_input, remaining_total)
                if max_for_current < min_generations:
                    logger.warning(f"剩余配额不足以满足最小生成次数要求，将生成 {max_for_current} 次")
                    generations_for_this_input = max_for_current
                else:
                    generations_for_this_input = random.randint(min_generations, max_for_current)
                
                logger.info(f"将为 {main_path.name} 生成 {generations_for_this_input} 张图片")
                remaining_total -= generations_for_this_input

                # 对每个主输入图片生成指定次数
                for gen_idx in range(generations_for_this_input):
                    # 为每个输入类型选择图片
                    image_paths = {main_input_type: main_path}
                    for input_type, images in input_images.items():
                        if input_type != main_input_type:
                            # 检查是否需要随机选择
                            if self.config.input_mapping[input_type].get("random_select", False):
                                image_paths[input_type] = random.choice(images)
                            else:
                                # 如果不随机，使用索引选择（可以根据需要修改选择逻辑）
                                image_paths[input_type] = images[gen_idx % len(images)]
                    
                    server = available_servers[task_count % server_count]
                    task_count += 1
                    
                    # 记录处理信息
                    paths_info = ", ".join(f"{k}: {v.name}" for k, v in image_paths.items())
                    main_desc = self.config.input_mapping[main_input_type]["description"]
                    logger.info(f"处理{main_desc} {main_path.name} (第 {gen_idx + 1}/{generations_for_this_input} 次生成): {paths_info}")
                    
                    # 创建新任务
                    task = asyncio.create_task(process_combined_images(main_path, image_paths, server))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                    generated_count += 1

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
                                    logger.info(f"进度: {processed_count}/{actual_total}")
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
                            logger.info(f"进度: {processed_count}/{actual_total}")
                    except Exception as e:
                        logger.error(f"任务执行失败: {str(e)}")

            logger.info(f"文件夹处理完成，共生成 {len(all_results)} 个文件")
            return all_results

        finally:
            await self.dispatcher.close()

    async def _process_single_image(
        self, path: Path, server: ComfyUIServer, prompt: dict, output_name: str = None
    ) -> List[str]:
        """处理单张图片的完整流程"""
        logger = get_run_logger()
        try:
            logger.info(f"使用服务器 {server.url} 处理图片组合")
            
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
                task_name=path.parent.name,
                output_filename=output_name or path.stem,
            )

        except Exception as e:
            logger.error(f"处理图片失败 - {path}, 服务器: {server.url}, 错误: {str(e)}")
            traceback.print_exc()
            return []

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
