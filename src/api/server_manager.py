from typing import Dict, List, Optional
from datetime import datetime
import asyncio
import aiohttp
from loguru import logger

from src.api.models.server import ServerConfig, ServerGroup, ServerStatus


class ServerManager:
    """服务器管理器"""
    
    def __init__(self):
        self._servers: Dict[str, ServerConfig] = {}
        self._groups: Dict[str, ServerGroup] = {}
        self._check_interval = 60  # 服务器状态检查间隔（秒）
        self._check_task: Optional[asyncio.Task] = None
    
    def register_server(self, server: ServerConfig) -> None:
        """注册服务器"""
        self._servers[server.name] = server
    
    def register_group(self, group: ServerGroup) -> None:
        """注册服务器组"""
        self._groups[group.name] = group
    
    def get_server(self, name: str) -> Optional[ServerConfig]:
        """获取服务器配置"""
        return self._servers.get(name)
    
    def get_group(self, name: str) -> Optional[ServerGroup]:
        """获取服务器组配置"""
        return self._groups.get(name)
    
    def list_servers(self) -> List[ServerConfig]:
        """列出所有服务器"""
        return list(self._servers.values())
    
    def list_groups(self) -> List[ServerGroup]:
        """列出所有服务器组"""
        return list(self._groups.values())
    
    def get_available_servers(self) -> List[ServerConfig]:
        """获取可用的服务器列表"""
        return [
            server for server in self._servers.values()
            if server.enabled and server.status == ServerStatus.ONLINE
        ]
    
    def get_servers_by_group(self, group_name: str) -> List[ServerConfig]:
        """获取指定组的所有服务器"""
        group = self._groups.get(group_name)
        if not group or not group.enabled:
            return []
        
        return [
            server for server_name in group.servers
            if (server := self._servers.get(server_name)) and server.enabled
        ]
    
    def get_available_server(self) -> Optional[ServerConfig]:
        """获取一个可用的服务器"""
        available_servers = [
            server for server in self._servers.values()
            if server.enabled 
            and server.status == ServerStatus.ONLINE 
            and server.current_task_id is None
        ]
        return available_servers[0] if available_servers else None
    
    def assign_task(self, server_name: str, task_id: str) -> bool:
        """分配任务到服务器"""
        server = self._servers.get(server_name)
        if not server or not server.enabled or server.status != ServerStatus.ONLINE:
            return False
        
        if server.current_task_id is not None:
            return False
        
        server.current_task_id = task_id
        server.status = ServerStatus.BUSY
        return True
    
    def release_task(self, server_name: str) -> None:
        """释放服务器任务"""
        server = self._servers.get(server_name)
        if server:
            server.current_task_id = None
            server.status = ServerStatus.ONLINE
    
    async def check_server_status(self, server: ServerConfig) -> None:
        """检查服务器状态"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{server.url}/health") as response:
                    if response.status == 200:
                        if server.current_task_id is None:
                            server.status = ServerStatus.ONLINE
                        server.error_message = None
                    else:
                        server.status = ServerStatus.ERROR
                        server.error_message = f"HTTP {response.status}"
        except Exception as e:
            server.status = ServerStatus.ERROR
            server.error_message = str(e)
        
        server.last_check_time = datetime.now().isoformat()
    
    async def check_all_servers(self) -> None:
        """检查所有服务器状态"""
        while True:
            try:
                for server in self._servers.values():
                    if server.enabled:
                        await self.check_server_status(server)
            except Exception as e:
                logger.error(f"检查服务器状态时出错: {str(e)}")
            
            await asyncio.sleep(self._check_interval)
    
    def start_status_check(self) -> None:
        """启动状态检查任务"""
        if self._check_task is None or self._check_task.done():
            self._check_task = asyncio.create_task(self.check_all_servers())
    
    def stop_status_check(self) -> None:
        """停止状态检查任务"""
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()
            self._check_task = None


# 创建全局服务器管理器实例
server_manager = ServerManager() 