import asyncio
from typing import Optional
from pathlib import Path
import aiohttp
from loguru import logger

from .models import MachineSpec, MachineStatus, InitializationScript


class MachineInitializer:
    """机器初始化器"""
    
    def __init__(self):
        self.initialization_timeout = 1800  # 30分钟超时
        self.health_check_interval = 30  # 30秒检查一次
    
    def generate_cuda_setup(self, cuda_version: str) -> str:
        """生成CUDA安装脚本"""
        return f"""
# 安装CUDA {cuda_version}
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/{cuda_version}/local_installers/cuda-repo-ubuntu2204-{cuda_version}-local_*.deb
sudo dpkg -i cuda-repo-ubuntu2204-{cuda_version}-local_*.deb
sudo cp /var/cuda-repo-ubuntu2204-{cuda_version}-local/cuda-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install cuda-{cuda_version}
"""

    def generate_python_setup(self, python_version: str) -> str:
        """生成Python环境设置脚本"""
        return f"""
# 安装Python {python_version}
sudo apt-get update
sudo apt-get install -y python{python_version} python{python_version}-venv python3-pip

# 创建虚拟环境
python{python_version} -m venv /opt/venv
source /opt/venv/bin/activate

# 升级pip
pip install --upgrade pip
"""

    def generate_package_install(self, packages: list[str]) -> str:
        """生成包安装脚本"""
        return f"""
# 安装Python包
pip install {' '.join(packages)}
"""

    def generate_service_setup(self, machine: MachineSpec) -> str:
        """生成服务设置脚本"""
        return f"""
# 创建服务目录
sudo mkdir -p /opt/service
sudo chown -R ubuntu:ubuntu /opt/service

# 创建服务配置
cat << EOF > /etc/systemd/system/compute-service.service
[Unit]
Description=Compute Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/service
Environment=PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/opt/venv/bin/python -m compute_service
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable compute-service
sudo systemctl start compute-service
"""

    async def initialize_machine(self, machine: MachineSpec) -> bool:
        """
        初始化机器
        
        Args:
            machine: 机器规格
        
        Returns:
            bool: 是否初始化成功
        """
        try:
            # 生成初始化脚本
            init_script = InitializationScript(
                cuda_setup=self.generate_cuda_setup(machine.requirements.gpu_spec.min_cuda_version),
                python_setup=self.generate_python_setup(machine.requirements.python_version),
                package_install=self.generate_package_install(machine.requirements.required_packages),
                service_setup=self.generate_service_setup(machine)
            )
            
            # 设置初始化脚本
            machine.initialization = init_script
            machine.startup_script = init_script.generate_full_script()
            
            # 更新状态
            machine.status = MachineStatus.INITIALIZING
            
            # 等待初始化完成
            success = await self._wait_for_initialization(machine)
            if success:
                machine.status = MachineStatus.READY
            else:
                machine.status = MachineStatus.ERROR
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to initialize machine {machine.instance_id}: {e}")
            machine.status = MachineStatus.ERROR
            return False

    async def _wait_for_initialization(self, machine: MachineSpec) -> bool:
        """等待初始化完成"""
        if not machine.health_check_url:
            logger.warning(f"No health check URL provided for machine {machine.instance_id}")
            return True
        
        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    async with session.get(machine.health_check_url) as response:
                        if response.status == 200:
                            return True
                except Exception as e:
                    logger.debug(f"Health check failed for {machine.instance_id}: {e}")
                
                if asyncio.get_event_loop().time() - start_time > self.initialization_timeout:
                    logger.error(f"Initialization timeout for machine {machine.instance_id}")
                    return False
                
                await asyncio.sleep(self.health_check_interval)


class ServiceDeployer:
    """服务部署器"""
    
    def __init__(self):
        self.deployment_timeout = 600  # 10分钟超时
        self.check_interval = 10  # 10秒检查一次
    
    async def deploy_service(self, machine: MachineSpec, service_config: dict) -> bool:
        """
        部署服务
        
        Args:
            machine: 机器规格
            service_config: 服务配置
        
        Returns:
            bool: 是否部署成功
        """
        try:
            # 这里添加服务部署逻辑
            # 例如：
            # 1. 上传服务代码
            # 2. 安装依赖
            # 3. 启动服务
            # 4. 等待服务就绪
            
            # 示例实现
            machine.service_urls.append(service_config['service_url'])
            machine.health_check_url = service_config['health_check_url']
            
            # 等待服务就绪
            return await self._wait_for_service(machine)
            
        except Exception as e:
            logger.error(f"Failed to deploy service to machine {machine.instance_id}: {e}")
            return False
    
    async def _wait_for_service(self, machine: MachineSpec) -> bool:
        """等待服务就绪"""
        if not machine.health_check_url:
            return True
        
        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    async with session.get(machine.health_check_url) as response:
                        if response.status == 200:
                            return True
                except Exception as e:
                    logger.debug(f"Service health check failed for {machine.instance_id}: {e}")
                
                if asyncio.get_event_loop().time() - start_time > self.deployment_timeout:
                    logger.error(f"Service deployment timeout for machine {machine.instance_id}")
                    return False
                
                await asyncio.sleep(self.check_interval) 