"""
资源分组工具，用于将特定父文件夹下的资源文件夹平均分配到多个组中
"""

import re
import shutil
from pathlib import Path
from math import ceil
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from loguru import logger
from pydantic import BaseModel, Field


class AssetSplitterConfig(BaseModel):
    """资源分组配置"""

    source_dir: Path = Field(..., description="源文件夹路径")
    output_base_dir: Path = Field(..., description="输出基础目录路径")
    group_count: int = Field(default=2, ge=1, description="分组数量")
    group_prefix: str = Field(default="group_", description="分组文件夹前缀")
    parent_dirs: List[str] = Field(
        default_factory=list,
        description="要处理的父文件夹名称列表，例如: ['款式A', '款式B']",
    )
    reserved_dirs: List[str] = Field(
        default_factory=list,
        description="需要在每个分组中完整保留的目录名称列表，例如: ['model', 'common']",
    )
    file_extensions: set[str] = Field(
        default_factory=lambda: {".png", ".jpg", ".jpeg", ".webp"},
        description="支持的文件格式",
    )
    max_workers: int = Field(
        default=4,
        ge=1,
        description="最大线程数",
    )

    def model_post_init(self, __context) -> None:
        """标准化文件扩展名格式"""
        self.file_extensions = {
            f".{ext.lstrip('.')}" for ext in self.file_extensions
        }
        if not self.parent_dirs:
            raise ValueError("parent_dirs cannot be empty")


class AssetSplitter:
    """资源分组器"""

    def __init__(self, config: AssetSplitterConfig):
        self.config = config
        self._validate_paths()
        self._copy_count = 0
        self._copy_lock = threading.Lock()

    def _validate_paths(self) -> None:
        """验证路径有效性"""
        if not self.config.source_dir.exists():
            raise ValueError(
                f"Source directory does not exist: {self.config.source_dir}"
            )
        
        # 验证所有父文件夹是否存在
        for parent_dir in self.config.parent_dirs:
            dir_path = self.config.source_dir / parent_dir
            if not dir_path.exists():
                raise ValueError(f"Parent directory does not exist: {dir_path}")
        
        # 验证所有保留目录是否存在
        for reserved_dir in self.config.reserved_dirs:
            dir_path = self.config.source_dir / reserved_dir
            if not dir_path.exists():
                raise ValueError(f"Reserved directory does not exist: {dir_path}")
        
        # 确保输出目录存在
        self.config.output_base_dir.mkdir(parents=True, exist_ok=True)

    def _collect_style_dirs(self, parent_dir: str) -> List[Path]:
        """收集指定父文件夹下的所有子文件夹"""
        parent_path = self.config.source_dir / parent_dir
        dirs = [d for d in parent_path.iterdir() if d.is_dir()]
        return sorted(dirs)  # 排序以确保结果可重现

    def _copy_directory(self, source: Path, target: Path, desc: str) -> None:
        """复制单个目录"""
        try:
            shutil.copytree(source, target, dirs_exist_ok=True)
            with self._copy_lock:
                self._copy_count += 1
                if self._copy_count % 10 == 0:  # 每复制10个目录输出一次进度
                    logger.info(f"Copied {self._copy_count} directories")
            logger.debug(f"Copied {desc}")
        except Exception as e:
            logger.error(f"Error copying {desc}: {e}")
            raise

    def _create_group_structure(self, group_idx: int, style_dirs_map: dict[str, List[Path]]) -> None:
        """创建分组目录结构并复制文件"""
        # 创建组目录
        group_dir = self.config.output_base_dir / f"{self.config.group_prefix}{group_idx}"
        group_dir.mkdir(parents=True, exist_ok=True)
        
        # 准备所有复制任务
        copy_tasks = []
        
        # 添加保留目录的复制任务
        for reserved_dir in self.config.reserved_dirs:
            source_dir = self.config.source_dir / reserved_dir
            if source_dir.exists():
                target_dir = group_dir / reserved_dir
                desc = f"reserved directory: {reserved_dir} to group {group_idx}"
                copy_tasks.append((source_dir, target_dir, desc))
        
        # 添加款式目录的复制任务
        for parent_dir, style_dirs in style_dirs_map.items():
            parent_target_dir = group_dir / parent_dir
            parent_target_dir.mkdir(parents=True, exist_ok=True)
            
            for style_dir in style_dirs:
                target_dir = parent_target_dir / style_dir.name
                desc = f"directory: {parent_dir}/{style_dir.name} to group {group_idx}"
                copy_tasks.append((style_dir, target_dir, desc))

        # 使用线程池并行复制
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # 提交所有复制任务
            future_to_task = {
                executor.submit(self._copy_directory, src, dst, desc): desc
                for src, dst, desc in copy_tasks
            }
            
            # 等待所有任务完成，并处理可能的异常
            for future in as_completed(future_to_task):
                try:
                    future.result()
                except Exception as e:
                    desc = future_to_task[future]
                    logger.error(f"Failed to copy {desc}: {e}")

    def process(self) -> None:
        """处理资源分组"""
        # 重置复制计数器
        self._copy_count = 0
        
        # 收集所有父文件夹下的子文件夹
        all_style_dirs_map = {}
        total_dirs = 0
        
        for parent_dir in self.config.parent_dirs:
            style_dirs = self._collect_style_dirs(parent_dir)
            if not style_dirs:
                logger.warning(f"No subdirectories found in {parent_dir}")
                continue
                
            all_style_dirs_map[parent_dir] = style_dirs
            dir_count = len(style_dirs)
            total_dirs += dir_count
            logger.info(f"Found {dir_count} subdirectories in {parent_dir}")

        if not total_dirs:
            logger.warning("No directories to process")
            return

        dirs_per_group = ceil(total_dirs / self.config.group_count)
        logger.info(f"Will create {self.config.group_count} groups with approximately {dirs_per_group} directories each")
        if self.config.reserved_dirs:
            logger.info(f"Each group will include reserved directories: {', '.join(self.config.reserved_dirs)}")
        logger.info(f"Using {self.config.max_workers} threads for copying")

        # 为每个组准备文件夹映射
        for group_idx in range(self.config.group_count):
            group_style_dirs_map = {}
            
            # 为每个父文件夹计算分配到当前组的子文件夹
            for parent_dir, style_dirs in all_style_dirs_map.items():
                parent_total = len(style_dirs)
                parent_dirs_per_group = ceil(parent_total / self.config.group_count)
                
                start_idx = group_idx * parent_dirs_per_group
                end_idx = min((group_idx + 1) * parent_dirs_per_group, parent_total)
                
                if start_idx >= parent_total:
                    continue
                    
                group_style_dirs_map[parent_dir] = style_dirs[start_idx:end_idx]
            
            if not group_style_dirs_map:
                continue
                
            # 记录当前组的分配情况
            group_summary = ", ".join(
                f"{parent}: {len(dirs)}" 
                for parent, dirs in group_style_dirs_map.items()
            )
            logger.info(f"Processing group {group_idx + 1} - {group_summary}")
            
            self._create_group_structure(group_idx + 1, group_style_dirs_map)

        logger.info(f"Asset grouping completed successfully. Total directories copied: {self._copy_count}") 