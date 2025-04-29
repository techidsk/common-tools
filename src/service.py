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
import json
import random
import traceback
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger
from prefect import flow, get_run_logger, task
from pydantic import BaseModel, Field

from src.dispatcher import ComfyUIServer, TaskDispatcher, TaskDispatcherConfig
from src.retriever import FileRetriever, FileRetrieverConfig
from src.workflow import WorkflowManager


class WorkflowConfigProvider(ABC):
    @abstractmethod
    async def get_workflow(self, workflow_id: Union[int, str]) -> Dict[str, Any]:
        """获取工作流配置"""
        pass
    
    @abstractmethod
    async def get_node_config(self, config_id: Union[int, str]) -> Dict[str, Any]:
        """获取节点配置"""
        pass

# 数据库配置提供器 - 连接到你现有的API
class DatabaseConfigProvider(WorkflowConfigProvider):
    def __init__(self, crud_service):
        self.crud_service = crud_service
    
    async def get_workflow(self, workflow_id: int) -> Dict[str, Any]:
        workflow = await self.crud_service.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow with ID {workflow_id} not found")
        return workflow.config  # 假设你的WorkflowConfig模型有一个config字段
    
    async def get_node_config(self, config_id: int) -> Dict[str, Any]:
        node_config = await self.crud_service.get_node_config(config_id)
        if not node_config:
            raise ValueError(f"Node config with ID {config_id} not found")
        return node_config.config

# 文件系统配置提供器 - 用于本地开发
class FileSystemConfigProvider(WorkflowConfigProvider):
    def __init__(self, workflow_path: Path, node_config_path: Path):
        self.workflow_path = workflow_path
        self.node_config_path = node_config_path
    
    async def get_workflow(self, workflow_id: Union[int, str] = None) -> Dict[str, Any]:
        with open(self.workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    async def get_node_config(self, config_id: Union[int, str] = None) -> Dict[str, Any]:
        with open(self.node_config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

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
            "style_image": {  # 款式图片
                "path": "款式",
                "is_main": true,
                "generations_per_style": 10,  # 每个款式文件夹生成的图片数量
                "max_generations_per_image": 2,  # 每张源图片最多使用次数
                "min_generations_per_image": 1   # 每张源图片最少使用次数
            },
            "model_image": {
                "path": "模特",
                "random_select": true  # 随机选择模特图片
            }
        }
        """
    )

    # 工作流配置 - 可以是ID或文件路径
    workflow_source: str = Field(default="db", description="工作流配置来源: 'db' 或 'file'")
    workflow_id: Optional[int] = Field(default=None, description="工作流ID（数据库模式）")
    node_config_id: Optional[int] = Field(default=None, description="节点配置ID（数据库模式）")
    workflow_path: Optional[Path] = Field(default=None, description="工作流JSON文件路径（文件模式）")
    node_config_path: Optional[Path] = Field(default=None, description="节点配置JSON文件路径（文件模式）")

    # 输出配置
    output_root: Path = Field(default=Path("outputs"), description="输出根目录")
    batch_size: int | None = Field(default=None, description="批处理大小，默认等于服务器数量")

    # 服务器配置
    servers: List[str] = Field(..., description="服务器列表")

    def model_post_init(self, __context):
        """初始化后验证配置"""
        if not self.servers:
            raise ValueError("服务器列表不能为空")
        
        if self.batch_size is None:
            self.batch_size = len(self.servers)
            
        # 验证工作流配置
        if self.workflow_source == "db":
            if self.workflow_id is None:
                raise ValueError("使用数据库模式时，必须提供工作流ID")
        elif self.workflow_source == "file":
            if self.workflow_path is None or self.node_config_path is None:
                raise ValueError("使用文件模式时，必须提供工作流和节点配置文件路径")

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

    def __init__(self, config: ServiceConfig, db=None, workflow_crud=None):
        self.config = config
        self.db = db
        self._setup_components(workflow_crud)

    def _setup_components(self, workflow_crud=None):
        """初始化各个组件"""
        # 文件检索器
        self.retriever = FileRetriever(
            FileRetrieverConfig(
                target_folders=self.config.target_folders,
                folder_keywords=self.config.folder_keywords,
                image_extensions=self.config.image_extensions,
            )
        )

        # 创建配置提供器
        if self.config.workflow_source == "db":
            if workflow_crud is None:
                raise ValueError("使用数据库模式时，必须提供workflow_crud实例")
            self.config_provider = DatabaseConfigProvider(workflow_crud)
        else:  # 文件模式
            self.config_provider = FileSystemConfigProvider(
                self.config.workflow_path,
                self.config.node_config_path
            )
        
        # 修改工作流管理器初始化，使用配置提供器
        self.workflow_manager = WorkflowManager(self.config_provider)
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
                # for img in images:
                #     logger.info(f"  - {img}")
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
            logger.info(f"主输入类型配置: {main_config}")
            
            # 获取生成配置
            generations_per_style = main_config.get("generations_per_style", 10)  # 每个款式生成数量
            max_per_image = main_config.get("max_generations_per_input", 7)  # 每张图片最多使用次数
            min_per_image = main_config.get("min_generations_per_input", 1)  # 每张图片最少使用次数

            # 创建任务队列
            task_queue = []
            
            # 按文件夹组织主输入图片
            style_folders = {}
            for main_path in main_images:
                folder = main_path.parent
                if folder not in style_folders:
                    style_folders[folder] = []
                style_folders[folder].append(main_path)

            # 处理每个款式文件夹
            for style_folder, style_images in style_folders.items():
                image_count = len(style_images)
                
                # 初始化生成次数列表
                generation_times = [min_per_image] * image_count  # 先给每个图片分配最小次数
                remaining = generations_per_style - (min_per_image * image_count)  # 计算剩余需要分配的次数
                
                # 计算每张图片还可以分配多少次
                max_additional = max_per_image - min_per_image
                
                # 计算平均应该分配的次数
                if remaining > 0:
                    base_additional = remaining // image_count
                    extra_count = remaining % image_count
                    
                    # 先平均分配
                    for i in range(image_count):
                        generation_times[i] += base_additional
                    
                    # 随机分配剩余的次数
                    if extra_count > 0:
                        # 随机选择图片进行分配
                        indices = list(range(image_count))
                        random.shuffle(indices)
                        for i in range(extra_count):
                            generation_times[indices[i]] += 1
                
                actual_total = sum(generation_times)
                # logger.info(
                #     f"\n处理款式文件夹: {style_folder.name}\n"
                #     f"- 源图片数量: {image_count}\n"
                #     f"- 目标生成数量: {generations_per_style}\n"
                #     f"- 实际生成数量: {actual_total}\n"
                #     f"- 各图片生成次数: {generation_times}\n"
                #     f"- 最大允许次数: {max_per_image}\n"
                #     f"- 最小要求次数: {min_per_image}"
                # )

                # 为每张图片创建对应次数的任务
                for img_idx, (style_image, times) in enumerate(zip(style_images, generation_times)):
                    for i in range(times):
                        # 准备输入图片组合
                        image_paths = {main_input_type: style_image}

                        # 为其他输入类型选择图片
                        for input_type, images in input_images.items():
                            if input_type != main_input_type:
                                config = self.config.input_mapping[input_type]
                                is_folder = config.get("is_folder", False)
                                random_folder = config.get("random_folder", False)
                                
                                if is_folder and random_folder:
                                    # If is_folder and random_folder are set, randomly select an image from a random subfolder.
                                    
                                    target_folder_name = config.get("path") # e.g., "模特"
                                    if not target_folder_name:
                                        logger.error(f"Input type '{input_type}' is configured for folder selection but has no 'path' defined.")
                                        image_paths[input_type] = None
                                        continue

                                    # Determine the base directory (e.g., ".../batch_1/模特") relative to the main image
                                    model_image_base_dir = None
                                    try:
                                        # Assumes '模特' and '款式' folders are siblings
                                        model_image_base_dir = style_image.parent.parent / target_folder_name
                                        if not model_image_base_dir.is_dir():
                                            # Raise error to trigger fallback or log clearly
                                            raise FileNotFoundError(f"Calculated base directory '{model_image_base_dir}' does not exist or is not a directory.")
                                    except Exception as e: # Catch potential issues with path calculation or FileNotFoundError
                                        logger.warning(f"Could not determine base directory for '{input_type}' based on '{style_image.name}'. Error: {e}. Trying fallback using provided image list.")
                                        # Fallback: Try to infer from the 'images' list if path calculation failed
                                        if images:
                                            # Find the common ancestor directory containing the target_folder_name
                                            potential_base_dir = None
                                            test_path = images[0]
                                            # Iterate upwards to find the parent containing the target folder name
                                            current = test_path.parent
                                            while current != current.parent: # Stop at root
                                                check_dir = current / target_folder_name
                                                if check_dir.is_dir() and target_folder_name in str(images[0]): # Check if target exists as sibling and image path contains the name
                                                     potential_base_dir = check_dir
                                                     break
                                                # Check if the current directory *is* the target directory name itself
                                                if current.name == target_folder_name and current.is_dir():
                                                     potential_base_dir = current
                                                     break
                                                current = current.parent # Go up one level

                                            if potential_base_dir and potential_base_dir.is_dir():
                                                 model_image_base_dir = potential_base_dir
                                                 logger.info(f"Using fallback base directory: {model_image_base_dir}")
                                            else:
                                                 logger.error(f"Could not determine base directory for '{input_type}' using fallback method from image {images[0]}.")
                                                 image_paths[input_type] = None
                                        else:
                                            logger.error(f"Could not determine base directory for '{input_type}', and no images provided for fallback.")
                                            image_paths[input_type] = None
                                    
                                    # Ensure we have a valid directory before proceeding
                                    if not model_image_base_dir or not model_image_base_dir.is_dir():
                                        logger.error(f"Failed to establish a valid base directory for input type '{input_type}'.")
                                        image_paths[input_type] = None
                                        continue

                                    # Find subdirectories within the base directory
                                    subfolders = [d for d in model_image_base_dir.iterdir() if d.is_dir()]
                                    
                                    chosen_folder = None
                                    if subfolders:
                                        # Case 1: Subfolders exist, pick one randomly
                                        chosen_folder = random.choice(subfolders)
                                        logger.debug(f"Randomly selected subfolder: {chosen_folder}")
                                    else:
                                        # Case 2: No subfolders, use the base directory itself as the folder to select images from
                                        # This directly addresses the user's reported issue scenario.
                                        logger.debug(f"Input type '{input_type}' directory {model_image_base_dir} has no subfolders. Selecting images directly from this directory.")
                                        chosen_folder = model_image_base_dir

                                    # Find valid image files in the chosen folder (either a subfolder or the base directory)
                                    folder_images = [f for f in chosen_folder.iterdir() if f.is_file() and f.suffix.lower() in self.config.image_extensions]
                                    
                                    if not folder_images:
                                         logger.warning(f"Selected folder {chosen_folder} for input type '{input_type}' contains no valid images matching extensions {self.config.image_extensions}.")
                                         image_paths[input_type] = None 
                                         # Consider adding logic here to try another subfolder if one was chosen and was empty.
                                         continue
                                         
                                    # Select a random image from the list
                                    image_paths[input_type] = random.choice(folder_images)
                                    logger.debug(f"Selected image for '{input_type}': {image_paths[input_type].name} from folder {chosen_folder.name}")
                                    
                                elif config.get("random_select", False):
                                    # Original random selection logic (from the flat list of images for this type)
                                    if images:
                                        image_paths[input_type] = random.choice(images)
                                    else:
                                        logger.warning(f"Input type '{input_type}' is configured for random selection, but no images found.")
                                        image_paths[input_type] = None # Handle missing images
                                else:
                                    # Original sequential selection logic
                                    if images:
                                        image_paths[input_type] = images[i % len(images)]
                                    else:
                                         logger.warning(f"Input type '{input_type}' has no images for sequential selection.")
                                         image_paths[input_type] = None # Handle missing images

                        # Filter out None paths before adding to queue
                        valid_image_paths = {k: v for k, v in image_paths.items() if v is not None}
                        # Check if all required inputs are present
                        if len(valid_image_paths) != len(self.config.input_mapping): 
                             # Find missing keys for better logging
                             missing_keys = set(self.config.input_mapping.keys()) - set(valid_image_paths.keys())
                             logger.warning(f"Skipping task for {style_image.name} (gen {i+1}) due to missing input images for types: {missing_keys}. Required: {list(self.config.input_mapping.keys())}, Found: {list(valid_image_paths.keys())}")
                             continue # Skip this specific generation task

                        # Add the task with validated paths to the queue
                        task_queue.append((style_image, valid_image_paths, i + 1, times))

            # 显示实际要处理的任务数量
            total_tasks = len(task_queue)
            logger.info(f"总共创建了 {total_tasks} 个任务")

            # 处理任务队列
            all_results = []
            active_tasks = set()
            processed_count = 0

            async def process_combined_images(main_path: Path, image_paths: dict[str, Path], server: ComfyUIServer):
                """处理一组输入图片"""
                try:
                    # 将单个路径转换为列表格式
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

            for task_idx, (main_path, image_paths, gen_idx, total_gens) in enumerate(task_queue):
                server = available_servers[task_idx % server_count]
                
                # 记录处理信息
                paths_info = ", ".join(f"{k}: {v.name}" for k, v in image_paths.items())
                main_desc = self.config.input_mapping[main_input_type]["description"]
                logger.info(f"处理{main_desc} {main_path.name} (第 {gen_idx}/{total_gens} 次生成): {paths_info}")
                
                # 创建新任务
                task = asyncio.create_task(process_combined_images(main_path, image_paths, server))
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
                                logger.info(f"进度: {processed_count}/{total_tasks}")
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
                            logger.info(f"进度: {processed_count}/{total_tasks}")
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
                logger.error(f"任务失败 {path} - 服务器: {server.url}, 状态: {status}")
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
