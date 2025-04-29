import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from .models import (
    CloudProvider, MachineSpec, MachineStatus,
    SystemRequirements, ServiceRegistration, AutoDLConfig
)
from .adapters import (
    CloudAdapter, CloudConfig,
    AWSAdapter, AzureAdapter
)
from .autodl_adapter import AutoDLAdapter
from .initializer import MachineInitializer, ServiceDeployer


class ComputeServiceFactory:
    _adapters: Dict[CloudProvider, CloudAdapter[Any]] = {}

    @classmethod
    async def get_adapter(cls, provider: CloudProvider, config: CloudConfig) -> CloudAdapter[Any]:
        if provider not in cls._adapters:
            adapter = cls._create_adapter(provider, config)
            await adapter.initialize()
            cls._adapters[provider] = adapter
        return cls._adapters[provider]

    @classmethod
    def _create_adapter(cls, provider: CloudProvider, config: CloudConfig) -> CloudAdapter[Any]:
        match provider:
            case CloudProvider.AWS:
                return AWSAdapter(config)
            case CloudProvider.AZURE:
                return AzureAdapter(config)
            case CloudProvider.AUTODL:
                if not isinstance(config, AutoDLConfig):
                    raise ValueError("AutoDL provider requires AutoDLConfig")
                return AutoDLAdapter(config)
            case _:
                raise ValueError(f"Unsupported cloud provider: {provider}")


class ComputeService:
    def __init__(self, check_interval: int = 300):
        """
        初始化计算服务
        
        Args:
            check_interval: 检查机器状态的间隔时间（秒）
        """
        self.check_interval = check_interval
        self.registered_machines: dict[str, MachineSpec] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._configs: dict[CloudProvider, CloudConfig] = {}
        self.initializer = MachineInitializer()
        self.deployer = ServiceDeployer()
        self.services: list[ServiceRegistration] = []

    def add_cloud_config(self, provider: CloudProvider, config: CloudConfig) -> None:
        """
        添加云平台配置
        
        Args:
            provider: 云平台提供商
            config: 云平台配置
        """
        self._configs[provider] = config

    async def find_suitable_machines(
        self,
        requirements: SystemRequirements,
        provider: Optional[CloudProvider] = None,
        count: int = 1
    ) -> list[MachineSpec]:
        """
        查找符合要求的机器
        
        Args:
            requirements: 系统要求
            provider: 可选的云平台提供商
            count: 需要的机器数量
        
        Returns:
            list[MachineSpec]: 符合要求的机器列表
        """
        suitable_machines = []
        machines = await self.get_available_machines(provider)
        
        for machine in machines:
            if len(suitable_machines) >= count:
                break
                
            # 检查机器是否符合要求
            if self._check_machine_requirements(machine, requirements):
                suitable_machines.append(machine)
        
        return suitable_machines

    def _check_machine_requirements(
        self,
        machine: MachineSpec,
        requirements: SystemRequirements
    ) -> bool:
        """检查机器是否符合要求"""
        if not machine.details:
            return False
            
        # 检查CPU
        if machine.details.get('cpu_cores', 0) < requirements.min_cpu_cores:
            return False
            
        # 检查内存
        if machine.details.get('memory_gb', 0) < requirements.min_memory_gb:
            return False
            
        # 检查磁盘
        if machine.details.get('disk_gb', 0) < requirements.min_disk_gb:
            return False
            
        # 检查GPU
        gpu_details = machine.details.get('gpu', {})
        if not gpu_details:
            return False
            
        if gpu_details.get('model') != requirements.gpu_spec.model:
            return False
            
        if gpu_details.get('memory', 0) < requirements.gpu_spec.memory:
            return False
            
        if gpu_details.get('count', 0) < requirements.gpu_spec.count:
            return False
        
        return True

    async def register_and_initialize_machines(
        self,
        machines: list[MachineSpec]
    ) -> list[MachineSpec]:
        """
        注册并初始化机器
        
        Args:
            machines: 要注册的机器列表
        
        Returns:
            list[MachineSpec]: 成功初始化的机器列表
        """
        initialized_machines = []
        
        for machine in machines:
            # 注册机器
            if await self.register_machine(machine):
                # 初始化机器
                if await self.initializer.initialize_machine(machine):
                    initialized_machines.append(machine)
                else:
                    logger.error(f"Failed to initialize machine {machine.instance_id}")
            else:
                logger.error(f"Failed to register machine {machine.instance_id}")
        
        return initialized_machines

    async def deploy_services(
        self,
        machines: list[MachineSpec],
        service_config: dict
    ) -> list[ServiceRegistration]:
        """
        部署服务到机器
        
        Args:
            machines: 目标机器列表
            service_config: 服务配置
        
        Returns:
            list[ServiceRegistration]: 服务注册信息列表
        """
        deployed_services = []
        
        for machine in machines:
            if await self.deployer.deploy_service(machine, service_config):
                service = ServiceRegistration(
                    machine_id=machine.instance_id,
                    service_name=service_config['name'],
                    service_url=service_config['service_url'],
                    health_check_url=service_config['health_check_url'],
                    status="running",
                    metadata={
                        'provider': machine.provider,
                        'region': machine.region,
                        'instance_type': machine.instance_type
                    }
                )
                self.services.append(service)
                deployed_services.append(service)
            else:
                logger.error(f"Failed to deploy service to machine {machine.instance_id}")
        
        return deployed_services

    async def setup_compute_cluster(
        self,
        requirements: SystemRequirements,
        service_config: dict,
        machine_count: int = 1,
        provider: Optional[CloudProvider] = None
    ) -> list[ServiceRegistration]:
        """
        设置计算集群
        
        Args:
            requirements: 系统要求
            service_config: 服务配置
            machine_count: 需要的机器数量
            provider: 可选的云平台提供商
        
        Returns:
            list[ServiceRegistration]: 服务注册信息列表
        """
        # 1. 查找合适的机器
        suitable_machines = await self.find_suitable_machines(
            requirements,
            provider,
            machine_count
        )
        
        if len(suitable_machines) < machine_count:
            logger.warning(
                f"Only found {len(suitable_machines)} suitable machines, "
                f"requested {machine_count}"
            )
        
        # 2. 注册并初始化机器
        initialized_machines = await self.register_and_initialize_machines(
            suitable_machines
        )
        
        if not initialized_machines:
            logger.error("No machines were successfully initialized")
            return []
        
        # 3. 部署服务
        return await self.deploy_services(initialized_machines, service_config)

    # ... (其他现有方法保持不变) ... 