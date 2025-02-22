"""
资源分组示例
"""

import sys
from pathlib import Path

from loguru import logger

# 添加src目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from src.asset_splitter import AssetSplitter, AssetSplitterConfig


def main():
    # 配置日志格式
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # 示例1：基本用法 - 带保留目录
    logger.info("示例1：基本用法 - 将资源分成3组，同时保留特定目录")
    config = AssetSplitterConfig(
        source_dir="assets/source",  # 源目录
        output_base_dir="assets/output/basic",  # 输出目录
        group_count=3,  # 分成3组
        parent_dirs=["款式A", "款式B"],  # 要处理的父文件夹
        reserved_dirs=["model", "common"],  # 在每个分组中都保留的目录
    )
    
    splitter = AssetSplitter(config)
    splitter.process()

    # 示例2：多个保留目录
    logger.info("\n示例2：使用多个保留目录")
    config = AssetSplitterConfig(
        source_dir="assets/source",
        output_base_dir="assets/output/multi_reserved",
        group_count=2,
        parent_dirs=["款式A"],
        reserved_dirs=["model", "common", "reference"],  # 多个保留目录
    )
    
    splitter = AssetSplitter(config)
    splitter.process()

    # 示例3：不使用保留目录
    logger.info("\n示例3：不使用保留目录")
    config = AssetSplitterConfig(
        source_dir="assets/source",
        output_base_dir="assets/output/no_reserved",
        group_count=4,
        parent_dirs=["款式A", "款式B"],  # 只处理这些目录
        reserved_dirs=[],  # 不保留任何目录
    )
    
    splitter = AssetSplitter(config)
    splitter.process()

    # 示例4：自定义分组前缀和保留目录
    logger.info("\n示例4：自定义分组前缀和保留目录")
    config = AssetSplitterConfig(
        source_dir="assets/source",
        output_base_dir="assets/output/custom",
        group_count=2,
        group_prefix="batch_",  # 自定义分组前缀
        parent_dirs=["款式A", "款式B"],
        reserved_dirs=["model"],  # 只保留模特目录
    )
    
    splitter = AssetSplitter(config)
    splitter.process()


if __name__ == "__main__":
    main() 