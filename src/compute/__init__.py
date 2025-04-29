"""
计算服务模块

这个模块提供了管理和初始化计算资源的功能，支持多个云平台。
"""

from .models import (
    CloudProvider,
    MachineStatus,
    GPUSpec,
    SystemRequirements,
    MachineSpec,
    ServiceRegistration,
    UnifiedGPUModel,
    GPURequirements,
    AutoDLConfig,
    AutoDLInstanceDetails,
    AutoDLRegion,
    AutoDLGPUType
)
from .service import ComputeService, ComputeServiceFactory
from .adapters import (
    CloudConfig,
    AWSConfig,
    AzureConfig
)

__all__ = [
    'CloudProvider',
    'MachineStatus',
    'GPUSpec',
    'SystemRequirements',
    'MachineSpec',
    'ServiceRegistration',
    'ComputeService',
    'ComputeServiceFactory',
    'CloudConfig',
    'AWSConfig',
    'AzureConfig',
    'UnifiedGPUModel',
    'GPURequirements',
    'AutoDLConfig',
    'AutoDLInstanceDetails',
    'AutoDLRegion',
    'AutoDLGPUType'
] 