from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol, TypeVar, Generic
from datetime import datetime
from dataclasses import dataclass

from pydantic import BaseModel, Field
from loguru import logger

from .models import MachineSpec, MachineStatus, CloudProvider


class CloudConfig(BaseModel):
    """云平台配置基类"""
    region: str
    credentials: dict[str, Any]


class AWSConfig(CloudConfig):
    """AWS 配置"""
    access_key_id: str
    secret_access_key: str
    session_token: Optional[str] = None
    instance_tags: dict[str, str] = Field(default_factory=dict)
    vpc_id: Optional[str] = None
    subnet_id: Optional[str] = None


class AzureConfig(CloudConfig):
    """Azure 配置"""
    subscription_id: str
    client_id: str
    client_secret: str
    tenant_id: str
    resource_group: str
    location: str = Field(alias="region")


@dataclass
class AWSInstanceDetails:
    """AWS 实例详细信息"""
    vpc_id: Optional[str]
    subnet_id: Optional[str]
    security_groups: list[str]
    tags: dict[str, str]
    public_ip: Optional[str]
    private_ip: Optional[str]


@dataclass
class AzureInstanceDetails:
    """Azure 实例详细信息"""
    resource_group: str
    location: str
    network_profile: Any
    os_profile: Any
    public_ip: Optional[str]
    private_ip: Optional[str]


# 使用泛型来处理平台特定的实例详情
T = TypeVar('T')

class CloudAdapter(ABC, Generic[T]):
    """云平台适配器基类"""
    
    def __init__(self, config: CloudConfig):
        self.config = config
        self._client: Any = None
        self._initialized: bool = False
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化云平台客户端"""
        pass
    
    @abstractmethod
    async def get_instance_status(self, instance_id: str) -> MachineStatus:
        """获取实例状态"""
        pass
    
    @abstractmethod
    async def list_instances(self) -> list[MachineSpec]:
        """列出所有实例"""
        pass
    
    @abstractmethod
    async def register_instance(self, instance_id: str, instance_type: str) -> bool:
        """注册实例"""
        pass

    @abstractmethod
    async def get_instance_details(self, instance_id: str) -> Optional[T]:
        """获取实例详细信息"""
        pass

    @abstractmethod
    async def start_instance(self, instance_id: str) -> bool:
        """启动实例"""
        pass

    @abstractmethod
    async def stop_instance(self, instance_id: str) -> bool:
        """停止实例"""
        pass

    async def ensure_initialized(self) -> None:
        """确保客户端已初始化"""
        if not self._initialized:
            await self.initialize()
            self._initialized = True


class AWSAdapter(CloudAdapter[AWSInstanceDetails]):
    """AWS 适配器"""
    
    async def initialize(self) -> None:
        try:
            import boto3
            config: AWSConfig = self.config  # type: ignore
            session = boto3.Session(
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=config.secret_access_key,
                aws_session_token=config.session_token,
                region_name=config.region
            )
            self._client = session.client('ec2')
            self._ec2_resource = session.resource('ec2')
            logger.info("AWS client initialized successfully")
        except ImportError:
            logger.error("boto3 not installed. Please install it with: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS client: {e}")
            raise

    async def get_instance_status(self, instance_id: str) -> MachineStatus:
        await self.ensure_initialized()
        try:
            response = self._client.describe_instance_status(InstanceIds=[instance_id])
            if not response['InstanceStatuses']:
                # 如果没有状态信息，尝试直接获取实例信息
                instance = self._ec2_resource.Instance(instance_id)
                return self._convert_aws_status(instance.state['Name'])
            
            status = response['InstanceStatuses'][0]['InstanceState']['Name']
            return self._convert_aws_status(status)
        except Exception as e:
            logger.error(f"Failed to get AWS instance status: {e}")
            return MachineStatus.UNKNOWN

    async def list_instances(self) -> list[MachineSpec]:
        await self.ensure_initialized()
        try:
            instances = []
            filters = []
            
            # 添加VPC过滤器
            aws_config: AWSConfig = self.config  # type: ignore
            if aws_config.vpc_id:
                filters.append({'Name': 'vpc-id', 'Values': [aws_config.vpc_id]})
            
            # 添加标签过滤器
            for key, value in aws_config.instance_tags.items():
                filters.append({'Name': f'tag:{key}', 'Values': [value]})
            
            response = self._client.describe_instances(Filters=filters)
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append(
                        MachineSpec(
                            instance_id=instance['InstanceId'],
                            provider=CloudProvider.AWS,
                            region=self.config.region,
                            instance_type=instance['InstanceType'],
                            status=self._convert_aws_status(instance['State']['Name']),
                            last_check=datetime.now()
                        )
                    )
            return instances
        except Exception as e:
            logger.error(f"Failed to list AWS instances: {e}")
            return []

    async def get_instance_details(self, instance_id: str) -> Optional[AWSInstanceDetails]:
        await self.ensure_initialized()
        try:
            instance = self._ec2_resource.Instance(instance_id)
            return AWSInstanceDetails(
                vpc_id=instance.vpc_id,
                subnet_id=instance.subnet_id,
                security_groups=[sg['GroupId'] for sg in instance.security_groups],
                tags={tag['Key']: tag['Value'] for tag in instance.tags or []},
                public_ip=instance.public_ip_address,
                private_ip=instance.private_ip_address
            )
        except Exception as e:
            logger.error(f"Failed to get AWS instance details: {e}")
            return None

    async def start_instance(self, instance_id: str) -> bool:
        await self.ensure_initialized()
        try:
            self._client.start_instances(InstanceIds=[instance_id])
            return True
        except Exception as e:
            logger.error(f"Failed to start AWS instance: {e}")
            return False

    async def stop_instance(self, instance_id: str) -> bool:
        await self.ensure_initialized()
        try:
            self._client.stop_instances(InstanceIds=[instance_id])
            return True
        except Exception as e:
            logger.error(f"Failed to stop AWS instance: {e}")
            return False

    def _convert_aws_status(self, aws_status: str) -> MachineStatus:
        status_map = {
            'running': MachineStatus.RUNNING,
            'stopped': MachineStatus.STOPPED,
            'terminated': MachineStatus.TERMINATED,
            'stopping': MachineStatus.STOPPED,
            'pending': MachineStatus.RUNNING,
            'shutting-down': MachineStatus.TERMINATED
        }
        return status_map.get(aws_status, MachineStatus.UNKNOWN)


class AzureAdapter(CloudAdapter[AzureInstanceDetails]):
    """Azure 适配器"""
    
    async def initialize(self) -> None:
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.network import NetworkManagementClient
            
            config: AzureConfig = self.config  # type: ignore
            credential = ClientSecretCredential(
                tenant_id=config.tenant_id,
                client_id=config.client_id,
                client_secret=config.client_secret
            )
            
            self._compute_client = ComputeManagementClient(
                credential=credential,
                subscription_id=config.subscription_id
            )
            self._network_client = NetworkManagementClient(
                credential=credential,
                subscription_id=config.subscription_id
            )
            logger.info("Azure clients initialized successfully")
        except ImportError:
            logger.error("Azure SDK not installed. Please install required packages.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Azure client: {e}")
            raise

    async def get_instance_status(self, instance_id: str) -> MachineStatus:
        await self.ensure_initialized()
        try:
            parts = self._parse_resource_id(instance_id)
            vm = self._compute_client.virtual_machines.get(
                resource_group_name=parts['resource_group'],
                vm_name=parts['name'],
                expand='instanceView'
            )
            
            status = vm.instance_view.statuses[-1].code
            return self._convert_azure_status(status)
        except Exception as e:
            logger.error(f"Failed to get Azure instance status: {e}")
            return MachineStatus.UNKNOWN

    async def get_instance_details(self, instance_id: str) -> Optional[AzureInstanceDetails]:
        await self.ensure_initialized()
        try:
            parts = self._parse_resource_id(instance_id)
            vm = self._compute_client.virtual_machines.get(
                resource_group_name=parts['resource_group'],
                vm_name=parts['name'],
                expand='instanceView'
            )
            
            # 获取网络接口信息
            nic_id = vm.network_profile.network_interfaces[0].id
            nic_parts = self._parse_resource_id(nic_id)
            nic = self._network_client.network_interfaces.get(
                resource_group_name=nic_parts['resource_group'],
                network_interface_name=nic_parts['name']
            )
            
            public_ip = None
            if nic.ip_configurations[0].public_ip_address:
                pip_id = nic.ip_configurations[0].public_ip_address.id
                pip_parts = self._parse_resource_id(pip_id)
                pip = self._network_client.public_ip_addresses.get(
                    resource_group_name=pip_parts['resource_group'],
                    public_ip_address_name=pip_parts['name']
                )
                public_ip = pip.ip_address
            
            return AzureInstanceDetails(
                resource_group=parts['resource_group'],
                location=vm.location,
                network_profile=vm.network_profile,
                os_profile=vm.os_profile,
                public_ip=public_ip,
                private_ip=nic.ip_configurations[0].private_ip_address
            )
        except Exception as e:
            logger.error(f"Failed to get Azure instance details: {e}")
            return None

    def _parse_resource_id(self, resource_id: str) -> dict[str, str]:
        """解析Azure资源ID"""
        parts = resource_id.split('/')
        return {
            'subscription': parts[2],
            'resource_group': parts[4],
            'type': parts[7],
            'name': parts[8]
        }

    async def start_instance(self, instance_id: str) -> bool:
        await self.ensure_initialized()
        try:
            parts = self._parse_resource_id(instance_id)
            self._compute_client.virtual_machines.begin_start(
                resource_group_name=parts['resource_group'],
                vm_name=parts['name']
            ).result()
            return True
        except Exception as e:
            logger.error(f"Failed to start Azure instance: {e}")
            return False

    async def stop_instance(self, instance_id: str) -> bool:
        await self.ensure_initialized()
        try:
            parts = self._parse_resource_id(instance_id)
            self._compute_client.virtual_machines.begin_deallocate(
                resource_group_name=parts['resource_group'],
                vm_name=parts['name']
            ).result()
            return True
        except Exception as e:
            logger.error(f"Failed to stop Azure instance: {e}")
            return False

    def _convert_azure_status(self, azure_status: str) -> MachineStatus:
        status_map = {
            'PowerState/running': MachineStatus.RUNNING,
            'PowerState/stopped': MachineStatus.STOPPED,
            'PowerState/deallocated': MachineStatus.TERMINATED,
            'PowerState/starting': MachineStatus.RUNNING,
            'PowerState/stopping': MachineStatus.STOPPED
        }
        return status_map.get(azure_status, MachineStatus.UNKNOWN) 