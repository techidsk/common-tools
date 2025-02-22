
import sys
from pathlib import Path

from loguru import logger

from src.asset_splitter import AssetSplitter, AssetSplitterConfig


logger.info("示例1：基本用法 - 将资源分成3组")
config = AssetSplitterConfig(
    source_dir=r"C:\baidunetdiskdownload\2025SS\1",  # 源目录
    output_base_dir=r"C:\baidunetdiskdownload\2025SS\1",  # 输出目录
    group_count=10,  # 分成3组
    parent_dirs=["款式"],  # 要处理的父文件夹
    reserved_dirs=["模特"],  # 在每个分组中都保留的目录  
)

splitter = AssetSplitter(config)
splitter.process()  