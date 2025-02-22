from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, validator, ConfigDict, field_validator
import os


class GPUVendor(str, Enum):
    """GPU 厂商"""
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"


class UnifiedGPUModel(str, Enum):
    """统一的 GPU 型号"""
    # NVIDIA GeForce 系列
    RTX_4090 = "RTX 4090"
    RTX_4080 = "RTX 4080"
    RTX_3090 = "RTX 3090"
    RTX_3080 = "RTX 3080"
    
    # NVIDIA Tesla/Data Center 系列
    A100 = "A100"
    A10 = "A10"
    V100 = "V100"
    T4 = "T4"
    
    # AMD 系列
    MI250 = "MI250"
    MI100 = "MI100"
    
    @property
    def vendor(self) -> GPUVendor:
        """获取 GPU 厂商"""
        if self.name.startswith(("RTX", "A", "V", "T")):
            return GPUVendor.NVIDIA
        elif self.name.startswith("MI"):
            return GPUVendor.AMD
        return GPUVendor.NVIDIA  # 默认 NVIDIA


class GPUMapping(BaseModel):
    """GPU 映射配置"""
    model: UnifiedGPUModel
    aws_name: Optional[str] = None  # AWS 上的名称
    azure_name: Optional[str] = None  # Azure 上的名称
    autodl_name: Optional[str] = None  # AutoDL 上的名称
    gcp_name: Optional[str] = None  # GCP 上的名称
    memory_gb: int  # 显存大小
    compute_capability: Optional[float] = None  # NVIDIA GPU 计算能力
    min_cuda_version: Optional[str] = None  # 最低支持的 CUDA 版本
    
    class Config:
        use_enum_values = True


class GPURequirements(BaseModel):
    """GPU 需求"""
    model: UnifiedGPUModel
    count: int = 1
    min_memory_gb: Optional[int] = None
    min_cuda_version: Optional[str] = None
    
    class Config:
        use_enum_values = True


class GPUMappingRegistry:
    """GPU 映射注册表"""
    _mappings: Dict[UnifiedGPUModel, GPUMapping] = {
        UnifiedGPUModel.RTX_4090: GPUMapping(
            model=UnifiedGPUModel.RTX_4090,
            autodl_name="RTX 4090",
            memory_gb=24,
            compute_capability=8.9,
            min_cuda_version="12.0"
        ),
        UnifiedGPUModel.RTX_3090: GPUMapping(
            model=UnifiedGPUModel.RTX_3090,
            autodl_name="RTX 3090",
            memory_gb=24,
            compute_capability=8.6,
            min_cuda_version="11.0"
        ),
        UnifiedGPUModel.A100: GPUMapping(
            model=UnifiedGPUModel.A100,
            aws_name="g5.xlarge",  # AWS 实例类型
            azure_name="Standard_NC24ads_A100_v4",  # Azure 实例类型
            gcp_name="a2-highgpu-1g",  # GCP 实例类型
            memory_gb=80,
            compute_capability=8.0,
            min_cuda_version="11.0"
        ),
        UnifiedGPUModel.V100: GPUMapping(
            model=UnifiedGPUModel.V100,
            aws_name="p3.2xlarge",
            azure_name="Standard_NC6s_v3",
            gcp_name="n1-standard-8",
            memory_gb=16,
            compute_capability=7.0,
            min_cuda_version="10.0"
        ),
    }
    
    @classmethod
    def get_mapping(cls, model: UnifiedGPUModel) -> Optional[GPUMapping]:
        """获取 GPU 映射"""
        return cls._mappings.get(model)
    
    @classmethod
    def get_provider_name(
        cls,
        model: UnifiedGPUModel,
        provider: "CloudProvider"
    ) -> Optional[str]:
        """获取特定云平台上的 GPU 名称"""
        mapping = cls.get_mapping(model)
        if not mapping:
            return None
            
        match provider:
            case CloudProvider.AWS:
                return mapping.aws_name
            case CloudProvider.AZURE:
                return mapping.azure_name
            case CloudProvider.AUTODL:
                return mapping.autodl_name
            case CloudProvider.GCP:
                return mapping.gcp_name
            case _:
                return None
    
    @classmethod
    def register_mapping(cls, mapping: GPUMapping) -> None:
        """注册新的 GPU 映射"""
        cls._mappings[mapping.model] = mapping


class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ALICLOUD = "alicloud"
    AUTODL = "autodl"


class AutoDLRegion(str, Enum):
    """AutoDL 区域"""
    WEST_DC2 = "westDC2"
    NORTH_DC1 = "northDC1"


class AutoDLGPUType(str, Enum):
    """AutoDL GPU类型"""
    RTX_4090 = "RTX 4090"
    RTX_4090D = "RTX 4090D"
    RTX_3090 = "RTX 3090"


class AutoDLConfig(BaseModel):
    """AutoDL 配置"""
    api_key: str = Field(default_factory=lambda: os.getenv("AUTODL__API_KEY", ""))
    base_url: str = Field(default_factory=lambda: os.getenv("AUTODL__BASE_URL", "https://api.autodl.com"))
    region: AutoDLRegion = AutoDLRegion.WEST_DC2
    cuda_version: int = 122
    gpu_types: list[AutoDLGPUType] = Field(
        default=[AutoDLGPUType.RTX_3090, AutoDLGPUType.RTX_4090D, AutoDLGPUType.RTX_4090]
    )
    min_memory_gb: int = Field(default=8)
    max_memory_gb: int = Field(default=256)
    min_cpu_cores: int = Field(default=12)
    max_cpu_cores: int = Field(default=100)
    min_price: int = Field(default=100)
    max_price: int = Field(default=9000)

    @field_validator("api_key")
    def validate_api_key(cls, v: str) -> str:
        """验证 API Key"""
        if not v:
            raise ValueError("AUTODL__API_KEY environment variable is required")
        return v

    @field_validator("base_url")
    def validate_base_url(cls, v: str) -> str:
        """验证 base URL"""
        if not v:
            raise ValueError("AUTODL__BASE_URL environment variable is required")
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v


class AutoDLInstanceDetails(BaseModel):
    """AutoDL 实例详细信息"""
    deployment_uuid: str
    container_uuid: Optional[str]
    gpu_type: AutoDLGPUType
    gpu_count: int
    memory_gb: int
    cpu_cores: int
    price: float
    status: str
    public_ip: Optional[str]
    private_ip: Optional[str]
    region: AutoDLRegion
    image_uuid: str


class MachineStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


class GPUSpec(BaseModel):
    """GPU规格要求"""
    model: str  # 例如: "NVIDIA A100", "NVIDIA V100"
    memory: int  # GPU内存大小(GB)
    min_cuda_version: str  # 最低CUDA版本要求
    count: int = 1  # GPU数量


class SystemRequirements(BaseModel):
    """系统要求"""
    min_cpu_cores: int
    min_memory_gb: int
    min_disk_gb: int
    gpu_requirements: GPURequirements
    python_version: str = "3.12"
    required_packages: List[str] = Field(default_factory=list)


class InitializationScript(BaseModel):
    """初始化脚本配置"""
    cuda_setup: str = Field(default="")  # CUDA安装脚本
    python_setup: str = Field(default="")  # Python环境设置脚本
    package_install: str = Field(default="")  # 包安装脚本
    service_setup: str = Field(default="")  # 服务设置脚本
    custom_script: str = Field(default="")  # 自定义脚本

    def generate_full_script(self) -> str:
        """生成完整的初始化脚本"""
        scripts = [
            "#!/bin/bash",
            "set -e",  # 遇到错误立即退出
            
            "# 初始化日志",
            'exec 1> >(logger -s -t $(basename $0)) 2>&1',
            
            "# CUDA设置",
            self.cuda_setup,
            
            "# Python环境设置",
            self.python_setup,
            
            "# 包安装",
            self.package_install,
            
            "# 服务设置",
            self.service_setup,
            
            "# 自定义脚本",
            self.custom_script
        ]
        
        return "\n\n".join(script for script in scripts if script.strip())


class MachineSpec(BaseModel):
    """机器规格"""
    instance_id: str
    provider: CloudProvider
    region: str
    instance_type: str
    status: MachineStatus = MachineStatus.UNKNOWN
    last_check: datetime = Field(default_factory=datetime.now)
    startup_script: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    # 新增字段
    requirements: SystemRequirements
    initialization: Optional[InitializationScript] = None
    health_check_url: Optional[str] = None  # 服务健康检查URL
    service_urls: List[str] = Field(default_factory=list)  # 服务URL列表
    tags: Dict[str, str] = Field(default_factory=dict)  # 机器标签
    
    @validator('region')
    def validate_region(cls, v: str, values: Dict[str, Any]) -> str:
        """验证区域是否符合云服务商的格式"""
        provider = values.get('provider')
        if provider == CloudProvider.AWS:
            # AWS区域格式: us-east-1
            if not v.replace("-", "").isalnum():
                raise ValueError("Invalid AWS region format")
        elif provider == CloudProvider.AZURE:
            # Azure区域格式: eastus
            if not v.isalnum():
                raise ValueError("Invalid Azure region format")
        return v


class ServiceRegistration(BaseModel):
    """服务注册信息"""
    machine_id: str
    service_name: str
    service_url: str
    health_check_url: str
    status: str
    last_check: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict) 