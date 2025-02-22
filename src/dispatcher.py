import asyncio
import io
import json
import os
import uuid
from datetime import datetime
from itertools import cycle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import dotenv
import httpx
from loguru import logger
from PIL import Image
from pydantic import BaseModel, Field, model_validator

from modules.comfyui.redis_client import ComfyUIRedisClient

# 加载环境变量
dotenv.load_dotenv()


class ComfyUIServer(BaseModel):
    """ComfyUI 服务器配置"""

    url: str = Field(
        description="服务器完整URL，例如: http://localhost:8188 或 https://example.com:8188"
    )

    @property
    def host(self) -> str:
        """从 URL 中获取主机名"""
        from urllib.parse import urlparse

        return urlparse(self.url).hostname or ""

    @property
    def port(self) -> int:
        """从 URL 中获取端口号"""
        from urllib.parse import urlparse

        return urlparse(self.url).port or 80

    def __hash__(self) -> int:
        """使对象可哈希，基于 URL"""
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        """比较两个服务器是否相同，基于 URL"""
        if not isinstance(other, ComfyUIServer):
            return NotImplemented
        return self.url == other.url


class TaskDispatcherConfig(BaseModel):
    """任务分发器配置"""

    servers: List[ComfyUIServer] = Field(default=None)
    redis_config: dict = Field(
        default_factory=lambda: {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": int(os.getenv("REDIS_DB", "0")),
            "password": os.getenv("REDIS_PASSWORD", ""),
        }
    )
    output_path: Path = Field(default=Path("outputs/daily"), description="输出目录")
    resize_short_edge: int = Field(
        default=int(os.environ.get("RESIZE_SHORT_EDGE", 1536)),
        description="调整图片短边大小",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_redis_config(cls, values: dict) -> dict:
        """验证并确保 Redis 配置正确加载"""
        if "redis_config" not in values:
            values["redis_config"] = {
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "db": int(os.getenv("REDIS_DB", "0")),
                "password": os.getenv("REDIS_PASSWORD", ""),
            }
        logger.info(f"Redis configuration: {values['redis_config']}")
        return values

    @model_validator(mode="before")
    @classmethod
    def ensure_servers(cls, values: dict) -> dict:
        """确保服务器配置被加载"""
        if not values.get("servers"):
            values["servers"] = cls._load_servers_from_env()
        return values

    @classmethod
    def _load_servers_from_env(cls) -> List[ComfyUIServer]:
        """从环境变量加载服务器配置"""
        servers = []

        # 处理主服务器配置
        servers.extend(cls._get_server_from_env())

        # 处理额外的服务器配置（2-5号服务器）
        for i in range(2, 6):
            servers.extend(cls._get_server_from_env(suffix=f"_{i}"))

        if not servers:
            raise ValueError("未找到任何 ComfyUI 服务器配置")

        return servers

    @staticmethod
    def _get_server_from_env(suffix: str = "") -> List[ComfyUIServer]:
        """从环境变量获取单个服务器配置

        Args:
            suffix: 环境变量后缀，例如 "_2" 用于第二个服务器
        """
        servers = []

        # 尝试从完整 URL 配置获取
        url = os.environ.get(f"COMFYUI_URL{suffix}")
        if url:
            servers.append(ComfyUIServer(url=url))
            return servers

        # 尝试从 host 和 port 构建 URL
        host = os.environ.get(f"COMFYUI_HOST{suffix}")
        port = os.environ.get(f"COMFYUI_PORT{suffix}")
        if host and port:
            servers.append(ComfyUIServer(url=f"http://{host}:{port}"))

        return servers


class TaskDispatcher:
    """ComfyUI 任务分发器"""

    def __init__(self, config: TaskDispatcherConfig):
        self.config = config
        self.available_servers: set[ComfyUIServer] = set()
        self.server_cycle = None
        self.redis_client = ComfyUIRedisClient(**self.config.redis_config)
        self._initialization_lock = asyncio.Lock()
        self._initialized = False
        self._initialization_task = None  # 新增：用于跟踪初始化任务
        
        logger.info(f"初始化任务分发器，配置的服务器数量: {len(self.config.servers)}")

    async def ensure_initialized(self) -> bool:
        """确保初始化完成"""
        async with self._initialization_lock:
            if self._initialized:
                return True
            
            if self._initialization_task is None:
                self._initialization_task = asyncio.create_task(self._initialize())
            
            try:
                await asyncio.wait_for(self._initialization_task, timeout=60)
                return True
            except Exception as e:
                logger.error(f"初始化失败: {str(e)}")
                return False

    async def _initialize(self) -> None:
        """初始化所有服务器"""
        if self._initialized:
            return

        tasks = []
        for server in self.config.servers:
            logger.debug(f"开始检查服务器: {server.url}")
            tasks.append(self._check_server_status(server))
        
        # 并发检查所有服务器
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for server, result in zip(self.config.servers, results):
            try:
                if isinstance(result, Exception):
                    logger.error(f"服务器 {server.url} 初始化失败: {str(result)}")
                elif result is True:
                    self.available_servers.add(server)
                    logger.info(f"服务器 {server.url} 初始化成功")
                else:
                    logger.warning(f"服务器 {server.url} 初始化失败")
            except Exception as e:
                logger.error(f"处理服务器 {server.url} 结果时出错: {str(e)}")

        # 设置服务器循环
        if self.available_servers:
            self.server_cycle = cycle(list(self.available_servers))
            self._initialized = True
            logger.info(f"初始化完成，可用服务器数量: {len(self.available_servers)}")
        else:
            logger.error("没有可用的服务器！")
            raise RuntimeError("No available servers")

    async def _check_server_status(self, server: ComfyUIServer, max_retries: int = 3) -> bool:
        """检查服务器状态"""
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                    response = await client.get(f"{server.url}/system_stats")
                    if response.status_code == 200:
                        logger.info(f"服务器 {server.url} 检查成功")
                        return True
                    logger.warning(f"服务器 {server.url} 返回状态码: {response.status_code}")
            except Exception as e:
                logger.error(f"检查服务器状态失败 {server.url} (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # 重试前等待1秒
                    continue
            return False
        return False

    async def get_next_server(self) -> ComfyUIServer:
        """获取下一个可用的服务器"""
        if not self._initialized:
            await self._initialize()  # 确保初始化完成
        return next(self.server_cycle)

    async def queue_prompt(self, prompt: dict) -> Tuple[str, ComfyUIServer]:
        """提交任务到 ComfyUI 并返回任务ID和服务器信息"""
        server = await self.get_next_server()
        data = json.dumps({"prompt": prompt}).encode("utf-8")
        logger.info(f"提交任务到服务器: {server.url}")

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{server.url}/prompt", content=data)
            result = response.json()
            prompt_id = result.get("prompt_id")

            if prompt_id:
                await self.redis_client.set_task_status(prompt_id, "PENDING")
                logger.info(f"任务已提交 - ID: {prompt_id}, 服务器: {server.url}")
                return prompt_id, server
            raise Exception("无法从响应中获取 prompt_id")

    async def get_history(self, prompt_id: str, server: ComfyUIServer) -> dict:
        """获取任务历史"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{server.url}/history/{prompt_id}")
            return response.json()

    async def get_image(self, image_data: dict, server: ComfyUIServer) -> bytes:
        """下载生成的图片"""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{server.url}/view",
                params={
                    "filename": image_data["filename"],
                    "subfolder": image_data.get("subfolder", ""),
                    "type": image_data["type"],
                },
            )
            return response.content

    def save_images(
        self,
        images: Dict[str, List[bytes]],
        task_name: str,
        output_filename: str = None,
    ) -> List[str]:
        """保存图片到本地"""
        if not images:
            return []

        saved_paths = []
        current_date = datetime.now().strftime("%Y-%m-%d")
        output_path = self.config.output_path / current_date / task_name
        output_path.mkdir(parents=True, exist_ok=True)

        for node_id, image_list in images.items():
            for idx, image_data in enumerate(image_list):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = output_filename or f"{timestamp}_{node_id}_{idx}_{str(uuid.uuid4())[:8]}.jpg"
                if not filename.endswith(".jpg"):
                    filename = filename + uuid.uuid4().hex + ".jpg"
                file_path = output_path / filename

                image = Image.open(io.BytesIO(image_data))
                image.save(file_path, format="PNG")
                saved_paths.append(str(file_path))
                logger.info(f"图片已保存: {file_path}")

        return saved_paths

    async def get_result(
        self,
        prompt_id: str,
        server: ComfyUIServer,
        max_retries: int = 60,
        retry_delay: int = 5,
    ) -> Tuple[Optional[Dict[str, List[bytes]]], str]:
        """获取任务结果"""
        # 检查缓存
        task_status = await self.redis_client.get_task_status(prompt_id)
        if task_status and task_status["status"] == "COMPLETED":
            return task_status["image_paths"], "SUCCESS"

        for attempt in range(max_retries):
            try:
                history = await self.get_history(prompt_id, server)
                history = history[prompt_id]

                if "outputs" not in history:
                    await asyncio.sleep(retry_delay)
                    continue

                outputs = history["outputs"]
                output_images = {}

                # 处理图片
                tasks = []
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        for image in node_output["images"]:
                            task = asyncio.ensure_future(self.get_image(image, server))
                            tasks.append((node_id, task))

                # 获取图片数据
                for node_id, task in tasks:
                    image_output = await task
                    if node_id in output_images:
                        output_images[node_id].append(image_output)
                    else:
                        output_images[node_id] = [image_output]

                if output_images:
                    await self.redis_client.set_task_status(
                        prompt_id, "COMPLETED", {"image_paths": []}
                    )
                    return output_images, "SUCCESS"

            except Exception as e:
                # logger.error(f"获取结果时出错: {str(e)}")
                if attempt == max_retries - 1:
                    await self.redis_client.set_task_status(
                        prompt_id, "FAILED", {"error": str(e)}
                    )
                    return None, "FAILED"

                await asyncio.sleep(retry_delay)

        await self.redis_client.set_task_status(prompt_id, "TIMEOUT")
        return None, "TIMEOUT"

    async def process_task(self, prompt: dict, task_name: str) -> List[str]:
        """处理完整的图片生成任务"""
        try:
            # 提交任务
            prompt_id, server = await self.queue_prompt(prompt)
            logger.info(f"任务已提交 - ID: {prompt_id}, 名称: {task_name}")

            # 获取结果
            output_images, status = await self.get_result(prompt_id, server)
            if status != "SUCCESS":
                logger.error(f"任务失败，状态: {status}")
                return []

            # 保存图片
            return self.save_images(output_images, task_name)

        except Exception as e:
            logger.error(f"处理任务时出错: {str(e)}")
            return []

    async def close(self):
        """关闭资源"""
        await self.redis_client.close()

    async def queue_prompt_to_server(self, prompt: dict, server: ComfyUIServer) -> str:
        """提交任务到指定的 ComfyUI 服务器"""
        try:
            data = json.dumps({"prompt": prompt}).encode("utf-8")
            logger.info(f"提交任务到服务器: {server.url}")

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(f"{server.url}/prompt", content=data)
                    response.raise_for_status()  # 检查 HTTP 状态码
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP 请求失败: 状态码 {e.response.status_code}, URL: {server.url}")
                    raise Exception(f"服务器返回错误状态码: {e.response.status_code}, 响应内容: {e.response.text}")
                except httpx.RequestError as e:
                    logger.error(f"请求失败: {str(e)}")
                    raise Exception(f"无法连接到服务器 {server.url}: {str(e)}")

                try:
                    result = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"解析响应 JSON 失败: {str(e)}, 响应内容: {response.text}")
                    raise Exception(f"服务器返回的响应不是有效的 JSON 格式: {str(e)}")

                prompt_id = result.get("prompt_id")
                if not prompt_id:
                    error_msg = f"服务器响应中缺少 prompt_id: {result}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

                await self.redis_client.set_task_status(prompt_id, "PENDING")
                logger.info(f"任务已提交 - ID: {prompt_id}, 服务器: {server.url}")
                return prompt_id

        except Exception as e:
            logger.error(f"提交任务到服务器 {server.url} 时发生错误: {str(e)}")
            raise Exception(f"提交任务失败: {str(e)}") from e

    async def _check_servers(self) -> bool:
        """检查服务器状态"""
        if not self._initialized:
            try:
                # 等待初始化完成
                await asyncio.wait_for(self._initialize(), timeout=30)
            except (asyncio.TimeoutError, RuntimeError) as e:
                logger.error(f"服务器初始化失败: {str(e)}")
                return False

        return len(self.available_servers) > 0
