import json
import os
import random
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import dpath
from loguru import logger
from pydantic import BaseModel, Field

from modules.io.image import load_image_to_base64


class NodeConfig(BaseModel):
    """节点配置项"""

    path: Union[str, List[str]] = Field(..., description="节点路径")
    value: Any = Field(None, description="节点值")
    type: Optional[List[Any]] = Field(
        None, description="值类型，如 ['random', [0, 9999999999]]"
    )
    bypass: Optional[Dict] = Field(None, description="bypass 配置")


class WorkflowConfig(BaseModel):
    """工作流配置"""

    workflow_path: Path = Field(..., description="工作流JSON文件路径")
    node_config_path: Path = Field(..., description="节点配置JSON文件路径")


class WorkflowManager:
    """工作流管理器"""

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self._workflow: Optional[dict] = None
        self._node_config: Optional[Dict[str, NodeConfig]] = None
        self._resize_edge: Optional[int] = None
        self._input_mapping: Optional[Dict[str, dict]] = None

    def set_input_mapping(self, input_mapping: Dict[str, dict]):
        """设置输入映射配置"""
        self._input_mapping = input_mapping

    def prepare_workflow_inputs(self, input_groups: Dict[str, List[Path]]) -> dict:
        """根据输入映射准备工作流输入参数

        Args:
            input_groups: 按输入类型分组的图片路径字典，如:
                {
                    "reference_image": [Path("style1.jpg"), Path("style2.jpg")],
                    "model_image": [Path("model1.jpg")]
                }

        Returns:
            准备好的工作流输入参数字典
        """
        if not self._input_mapping:
            raise ValueError("未设置输入映射配置")

        # 准备所有输入图片的 base64 数据
        workflow_inputs = {}
        for input_type, paths in input_groups.items():
            if input_type in self._input_mapping:
                config = self._input_mapping[input_type]
                # 获取工作流中实际使用的参数名称
                param_name = config.get("workflow_param", input_type)
                # 如果只有一张图片，直接使用字符串
                # 如果有多张图片，使用列表
                if len(paths) == 1:
                    workflow_inputs[param_name] = self.prepare_image(paths[0])
                else:
                    workflow_inputs[param_name] = [self.prepare_image(p) for p in paths]

        return workflow_inputs

    def load_workflow(self) -> dict:
        """加载工作流"""
        if self._workflow is None:
            try:
                with open(self.config.workflow_path, "r", encoding="utf-8") as f:
                    self._workflow = json.load(f)
                logger.info(f"工作流加载成功: {self.config.workflow_path}")
                self._load_node_config()
            except Exception as e:
                logger.error(f"工作流加载失败: {e}")
                raise
        return self._workflow

    def _load_node_config(self):
        """加载节点配置"""
        try:
            with open(self.config.node_config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            # 将配置数据转换为 NodeConfig 对象
            self._node_config = {
                key: NodeConfig(**value) if isinstance(value, dict) else value
                for key, value in config_data.items()
            }
            logger.info(f"节点配置加载成功: {self.config.node_config_path}")
        except Exception as e:
            logger.error(f"节点配置加载失败: {e}")
            raise

    def _set_node_value(self, workflow: dict, path: Union[str, List[str]], value: Any):
        """设置节点值"""
        if isinstance(path, list):
            for p in path:
                dpath.set(workflow, p, value, "/")
        else:
            dpath.set(workflow, path, value, "/")

    def _process_node_config(
        self, workflow: dict, key: str, config: NodeConfig, **kwargs
    ):
        """处理节点配置"""
        # 如果有指定值，使用指定值
        if key in kwargs:
            value = kwargs[key]
        # 否则使用配置中的默认值
        elif config.value is not None:
            value = config.value
        # 如果配置了类型为随机数
        elif config.type and config.type[0] == "random":
            min_val, max_val = config.type[1]
            value = random.randint(min_val, max_val)
        else:
            return
        
        self._set_node_value(workflow, config.path, value)

        # 处理 bypass 配置
        if config.bypass:
            for node in config.bypass.get("nodes", []):
                self._set_node_value(workflow, node["path"], node["value"])


    def _set_node_random_seed(self, workflow: dict, config: NodeConfig):
        """从 workflow 中提取可能的 random seed 节点位置信息，并确保随机性
        
        如果在配置中指定了 seed 节点，则会收集所有可能的随机种子节点位置，
        并在需要时为它们设置随机值。如果需要统一随机种子，可以在配置中单独设置。
        
        Args:
            workflow: 工作流数据
            config: 当前处理的节点配置
        """
        # 检查是否需要处理随机种子
        if not hasattr(self, "_node_config"):
            return
            
        # 如果当前节点是 seed 节点，则不需要额外处理
        if config == self._node_config.get("seed"):
            return
            
        # 查找当前节点中的随机种子
        seed_paths = []
        
        # 检查当前节点是否包含 seed 或 noise_seed 输入
        if isinstance(config.path, str):
            node_path = config.path.split("/")[0]  # 获取节点名称
            logger.debug(f"检查节点 {node_path} 的随机种子")
            
            # 检查是否有 seed 输入
            seed_path = f"{node_path}/inputs/seed"
            current_seed = dpath.get(workflow, seed_path, default=None)
            if current_seed is not None:
                seed_paths.append(seed_path)
                logger.debug(f"找到 seed 路径: {seed_path}, 当前值: {current_seed}")
                
            # 检查是否有 noise_seed 输入
            noise_seed_path = f"{node_path}/inputs/noise_seed"
            current_noise_seed = dpath.get(workflow, noise_seed_path, default=None)
            if current_noise_seed is not None:
                seed_paths.append(noise_seed_path)
                logger.debug(f"找到 noise_seed 路径: {noise_seed_path}, 当前值: {current_noise_seed}")
        
        # 如果找到了随机种子节点，并且没有在 seed 配置中指定，则为它们设置随机值
        if seed_paths and "seed" not in self._node_config:
            for path in seed_paths:
                # 生成一个随机种子值
                random_seed = random.randint(0, 999999999)
                # 设置随机种子值
                dpath.set(workflow, path, random_seed, "/")
                logger.info(f"设置随机种子: {path} = {random_seed}")
        
        # 如果存在 seed 配置，则更新其路径列表
        if "seed" in self._node_config:
            seed_config = self._node_config["seed"]
            seed_list = []
            
            if isinstance(seed_config.path, str):
                seed_list = [seed_config.path]
            elif isinstance(seed_config.path, list):
                seed_list = seed_config.path.copy()
    
            # 从工作流中提取所有可能的种子节点
            for k, _ in workflow.items():
                seed_value = dpath.get(workflow, f"{k}/inputs/seed", default=None)
                if seed_value is not None:
                    seed_list.append(f"{k}/inputs/seed")
                    logger.debug(f"收集到 seed 路径: {k}/inputs/seed, 当前值: {seed_value}")
    
                noise_seed_value = dpath.get(workflow, f"{k}/inputs/noise_seed", default=None)
                if noise_seed_value is not None:
                    seed_list.append(f"{k}/inputs/noise_seed")
                    logger.debug(f"收集到 noise_seed 路径: {k}/inputs/noise_seed, 当前值: {noise_seed_value}")
    
            # 去重
            seed_list = list(set(seed_list))
            logger.debug(f"更新 seed 配置路径列表: {seed_list}")
            
            # 更新配置中的路径
            seed_config.path = seed_list
            
            # 如果种子类型为空，则创建随机种子类型
            if not seed_config.type:
                seed_config.type = ["random", [0, 999999999]]
                logger.debug("创建随机种子类型配置")

    def prepare_workflow(self, **kwargs) -> dict:
        """准备工作流

        Args:
            **kwargs: 节点值映射，如 image="base64...", scene="base64...", model_name="v1.5"
        """
        workflow = deepcopy(self.load_workflow())

        if not self._node_config:
            raise ValueError("未加载节点配置")

        # 处理所有配置项
        for key, config in self._node_config.items():
            if isinstance(config, NodeConfig):
                self._process_node_config(workflow, key, config, **kwargs)

        # self._set_node_random_seed(workflow)

        return workflow

    def _get_resize_edge(self) -> int:
        """获取图片缩放尺寸"""
        if self._resize_edge is not None:
            return self._resize_edge

        env_resize = os.environ.get("RESIZE_SHORT_EDGE")
        if env_resize:
            try:
                self._resize_edge = int(env_resize)
                return self._resize_edge
            except ValueError:
                logger.warning(f"环境变量 RESIZE_SHORT_EDGE 值无效: {env_resize}")

        self._resize_edge = 1024
        return self._resize_edge

    def prepare_image(self, image_path: Path) -> str:
        """准备图片的 base64 编码"""
        return load_image_to_base64(
            str(image_path), resize_short_edge=self._get_resize_edge()
        )
