from datetime import datetime
import httpx
from typing import Optional, List
from enum import Enum
from loguru import logger
import traceback

from src.feishu import send_message_to_feishu

from .models import (
    MachineSpec, MachineStatus, CloudProvider,
    AutoDLConfig, AutoDLInstanceDetails, AutoDLRegion,
    UnifiedGPUModel, GPUMappingRegistry, GPURequirements
)
from .adapters import CloudAdapter


class API(str, Enum):
    """AutoDL API 路径"""
    fetch_balance = "/api/v1/dev/wallet/balance"
    fetch_images = "/api/v1/dev/image/private/list"
    create_deployment = "/api/v1/dev/deployment"
    fetch_deployments = "/api/v1/dev/deployment/list"
    fetch_container_events = "/api/v1/dev/deployment/container/event/list"
    fetch_containers = "/api/v1/dev/deployment/container/list"
    stop_container = "/api/v1/dev/deployment/container/stop"
    set_replicas = "/api/v1/dev/deployment/replica_num"
    stop_deployment = "/api/v1/dev/deployment/operate"
    delete_deployment = "/api/v1/dev/deployment"
    fetch_gpu_stock = "/api/v1/dev/machine/region/gpu_stock"


class AutoDLAdapter(CloudAdapter[AutoDLInstanceDetails]):
    """AutoDL 适配器"""
    
    def __init__(self, config: AutoDLConfig):
        super().__init__(config)
        self.headers = {
            "Authorization": config.api_key,
            "Content-Type": "application/json",
        }
        self.httpx_timeout = 30.0

    async def initialize(self) -> None:
        """初始化 AutoDL 客户端"""
        try:
            # 验证凭据
            balance = await self._fetch_balance()
            if balance is None:
                raise ValueError("Failed to validate AutoDL credentials")
            logger.info("AutoDL client initialized successfully")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize AutoDL client: {e}")
            raise

    async def get_instance_status(self, instance_id: str) -> MachineStatus:
        """获取实例状态"""
        await self.ensure_initialized()
        try:
            deployment = await self._fetch_deployment(instance_id)
            if not deployment:
                return MachineStatus.UNKNOWN
            
            status = deployment.get("status", "").lower()
            return self._convert_autodl_status(status)
        except Exception as e:
            logger.error(f"Failed to get AutoDL instance status: {e}")
            return MachineStatus.UNKNOWN

    async def list_instances(self) -> list[MachineSpec]:
        """列出所有实例"""
        await self.ensure_initialized()
        try:
            deployments = await self._fetch_deployments()
            instances = []
            
            for deployment in deployments:
                containers = await self._fetch_containers(deployment["image_uuid"])
                for container in containers:
                    instance = self._convert_to_machine_spec(deployment, container)
                    if instance:
                        instances.append(instance)
            
            return instances
        except Exception as e:
            logger.error(f"Failed to list AutoDL instances: {e}")
            return []

    async def register_instance(self, instance_id: str, instance_type: str) -> bool:
        """注册实例"""
        await self.ensure_initialized()
        try:
            # 在 AutoDL 中创建部署
            config: AutoDLConfig = self.config  # type: ignore
            result = await self._create_deployment(
                name=f"compute-{instance_id}",
                image_uuid=instance_type,  # 在 AutoDL 中，instance_type 对应 image_uuid
                gpu_requirements=GPURequirements(model=instance_type, count=1)  # 使用配置中的第一个 GPU 类型
            )
            return bool(result and result.get("deployment_uuid"))
        except Exception as e:
            logger.error(f"Failed to register AutoDL instance: {e}")
            return False

    async def get_instance_details(self, instance_id: str) -> Optional[AutoDLInstanceDetails]:
        """获取实例详细信息"""
        await self.ensure_initialized()
        try:
            deployment = await self._fetch_deployment(instance_id)
            if not deployment:
                return None
            
            containers = await self._fetch_containers(instance_id)
            if not containers:
                return None
            
            container = containers[0]  # 使用第一个容器
            config: AutoDLConfig = self.config  # type: ignore
            
            return AutoDLInstanceDetails(
                deployment_uuid=instance_id,
                container_uuid=container.get("container_uuid"),
                gpu_type=container.get("gpu_type", UnifiedGPUModel.RTX_3090),
                gpu_count=container.get("gpu_count", 1),
                memory_gb=container.get("memory_size", config.min_memory_gb),
                cpu_cores=container.get("cpu_cores", config.min_cpu_cores),
                price=container.get("price", 0.0),
                status=deployment.get("status", "Unknown"),
                public_ip=container.get("public_ip"),
                private_ip=container.get("private_ip"),
                region=config.region,
                image_uuid=container.get("image_uuid", "")
            )
        except Exception as e:
            logger.error(f"Failed to get AutoDL instance details: {e}")
            return None

    async def start_instance(self, instance_id: str) -> bool:
        """启动实例"""
        await self.ensure_initialized()
        try:
            result = await self._start_deployment(instance_id)
            return bool(result and result.get("success"))
        except Exception as e:
            logger.error(f"Failed to start AutoDL instance: {e}")
            return False

    async def stop_instance(self, instance_id: str) -> bool:
        """停止实例"""
        await self.ensure_initialized()
        try:
            result = await self._stop_deployment(instance_id)
            return bool(result and result.get("success"))
        except Exception as e:
            logger.error(f"Failed to stop AutoDL instance: {e}")
            return False

    def _convert_autodl_status(self, status: str) -> MachineStatus:
        """转换 AutoDL 状态到标准状态"""
        status_map = {
            "running": MachineStatus.RUNNING,
            "stopped": MachineStatus.STOPPED,
            "failed": MachineStatus.ERROR,
            "pending": MachineStatus.INITIALIZING,
            "terminated": MachineStatus.TERMINATED
        }
        return status_map.get(status.lower(), MachineStatus.UNKNOWN)

    def _convert_to_machine_spec(
        self,
        deployment: dict,
        container: dict
    ) -> Optional[MachineSpec]:
        """转换 AutoDL 部署信息到标准机器规格"""
        try:
            config: AutoDLConfig = self.config  # type: ignore
            return MachineSpec(
                instance_id=deployment["deployment_uuid"],
                provider=CloudProvider.AUTODL,
                region=config.region,
                instance_type=container.get("image_uuid", ""),
                status=self._convert_autodl_status(deployment.get("status", "")),
                last_check=datetime.now(),
                details={
                    "container_uuid": container.get("container_uuid"),
                    "gpu_type": container.get("gpu_type"),
                    "gpu_count": container.get("gpu_count", 1),
                    "memory_gb": container.get("memory_size"),
                    "cpu_cores": container.get("cpu_cores"),
                    "price": container.get("price"),
                    "public_ip": container.get("public_ip"),
                    "private_ip": container.get("private_ip")
                }
            )
        except Exception as e:
            logger.error(f"Failed to convert AutoDL deployment to MachineSpec: {e}")
            return None

    def _convert_gpu_model(self, gpu_requirements: GPURequirements) -> Optional[str]:
        """转换统一 GPU 型号到 AutoDL GPU 名称"""
        return GPUMappingRegistry.get_provider_name(
            gpu_requirements.model,
            CloudProvider.AUTODL
        )

    # AutoDL API 调用方法
    async def _fetch_balance(self) -> Optional[dict]:
        """获取账户余额"""
        async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
            try:
                config: AutoDLConfig = self.config  # type: ignore
                logger.info(f"Fetching balance from {config.base_url}{API.fetch_balance.value}")
                response = await client.post(
                    url=f"{config.base_url}{API.fetch_balance.value}",
                    headers=self.headers,
                    json={}
                )
                response.raise_for_status()
                logger.info(f"Balance: {response.json()}")
                balance = response.json()
                if balance.get("code") == "Success":  
                    return balance.get("data")
                else:
                    logger.error(f"Failed to fetch balance: {balance.get('msg')}")
                    return None
            except Exception as e:
                logger.error(f"Failed to fetch balance: {e}")
                return None

    async def _fetch_deployments(self, page: int = 1, page_size: int = 100) -> list[dict]:
        """获取所有部署"""
        async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
            try:
                config: AutoDLConfig = self.config  # type: ignore
                response = await client.post(
                    url=f"{config.base_url}{API.fetch_deployments.value}",
                    json={"page": page, "page_size": page_size},
                    headers=self.headers
                )
                response.raise_for_status()
                logger.info(f"Deployments: {response.json()}")
                return response.json().get("data", {}).get("list", [])
            except Exception as e:
                logger.error(f"Failed to fetch deployments: {e}")
                return []

    async def _fetch_deployment(self, deployment_uuid: str) -> Optional[dict]:
        """获取特定部署信息"""
        deployments = await self._fetch_deployments()
        for deployment in deployments:
            if deployment.get("deployment_uuid") == deployment_uuid:
                return deployment
        return None

    async def _fetch_containers(
        self,
        deployment_uuid: str,
        released: bool = False
    ) -> list[dict]:
        """获取容器信息"""
        async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
            try:
                config: AutoDLConfig = self.config  # type: ignore
                response = await client.post(
                    url=f"{config.base_url}{API.fetch_containers.value}",
                    json={
                        "deployment_uuid": deployment_uuid,
                        "released": released,
                        "page": 1,
                        "page_size": 10
                    },
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json().get("data", {}).get("list", [])
            except Exception as e:
                logger.error(f"Failed to fetch containers: {e}")
                return []

    async def _create_deployment(
        self,
        name: str,
        image_uuid: str,
        gpu_requirements: GPURequirements
    ) -> Optional[dict]:
        """创建部署"""
        async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
            try:
                config: AutoDLConfig = self.config  # type: ignore
                gpu_name = self._convert_gpu_model(gpu_requirements)
                if not gpu_name:
                    raise ValueError(f"Unsupported GPU model: {gpu_requirements.model}")
                
                data = {
                    "name": name,
                    "deployment_type": "Job",
                    "container_template": {
                        "region_sign": config.region,
                        "cuda_v": config.cuda_version,
                        "gpu_name_set": [gpu_name],
                        "gpu_num": gpu_requirements.count,
                        "memory_size_from": config.min_memory_gb,
                        "memory_size_to": config.max_memory_gb,
                        "cpu_num_from": config.min_cpu_cores,
                        "cpu_num_to": config.max_cpu_cores,
                        "price_from": config.min_price,
                        "price_to": config.max_price,
                        "image_uuid": image_uuid,
                        "cmd": "sleep infinity"
                    }
                }
                response = await client.post(
                    url=f"{config.base_url}{API.create_deployment.value}",
                    json=data,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to create deployment: {e}")
                return None

    async def _start_deployment(self, deployment_uuid: str) -> Optional[dict]:
        """启动部署"""
        async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
            try:
                config: AutoDLConfig = self.config  # type: ignore
                response = await client.post(
                    url=f"{config.base_url}{API.start_deployment.value}",
                    json={"deployment_uuid": deployment_uuid, "operate": "start"},
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to start deployment: {e}")
                return None

    async def _stop_deployment(self, deployment_uuid: str) -> Optional[dict]:
        """停止部署"""
        async with httpx.AsyncClient(timeout=self.httpx_timeout) as client:
            try:
                config: AutoDLConfig = self.config  # type: ignore
                response = await client.post(
                    url=f"{config.base_url}{API.stop_deployment.value}",
                    json={"deployment_uuid": deployment_uuid, "operate": "stop"},
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to stop deployment: {e}")
                return None 