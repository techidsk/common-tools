"""
文件和图像预处理工具 (File and Image Preprocessing Tools)

该模块提供了批量处理文件和图像的工具函数，支持多种预处理操作，包括图像调整大小和文件重命名。
设计用于处理大量文件的场景，支持多线程并行处理以提高效率。

主要功能:
1. 图像预处理:
   - 调整图像大小，保持宽高比
   - 批量处理目录中的图像
   - 可选择是否删除原始图像
   - 支持质量设置

2. 文件预处理:
   - 多种重命名策略 (保持原名、UUID、序列号、时间戳)
   - 文件格式筛选
   - 添加前缀和后缀
   - 可选择是否删除原始文件

主要函数:
- process_images_in_directory: 处理目录中的所有图像文件
- process_files_in_directory: 处理目录中的所有文件，支持多种重命名策略

使用示例:
    # 图像处理示例
    processed, failed = process_images_in_directory(
        "path/to/images",
        min_side_size=1024,  # 设置短边尺寸
        max_workers=8,       # 设置并发数量
        delete_original=True,# 是否删除原图
        quality=95,          # 设置输出图片质量
        output_prefix="",    # 设置输出文件前缀
    )
    
    # 文件重命名示例
    processed, failed = process_files_in_directory(
        "path/to/files",
        formats=["jpg", "png"],  # 处理特定格式
        rename_strategy="sequence", # 使用序列重命名
        prefix="img_",          # 添加前缀
        sequence_start=1,       # 序列起始值
        sequence_padding=4,     # 序列数字位数
        remove_original=False,  # 保留原文件
    )
"""

from pathlib import Path
from typing import List, Literal
import time
import multiprocessing
import shutil
from loguru import logger
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

# 导入本地模块
try:
    from src.preprocess import ImagePreprocessor, ImagePreprocessorConfig
    from file import FilePreprocessor, FilePreprocessorConfig
except ImportError:
    # 如果从src导入失败，尝试直接导入
    from file import FilePreprocessor, FilePreprocessorConfig
    # 图像处理器可能不可用
    logger.warning("无法导入ImagePreprocessor，图像处理功能可能不可用")
    ImagePreprocessor = None
    ImagePreprocessorConfig = None


def process_images_in_directory(
    root_dir: str | Path,
    *,
    min_side_size: int = 3000,
    max_workers: int | None = None,
    delete_original: bool = False,
    quality: int = 95,
    output_prefix: str = "",
) -> tuple[List[Path], List[Path]]:
    """
    Process all images in directory and its subdirectories

    Args:
        root_dir: Root directory containing images
        min_side_size: Target size for the shorter side while maintaining aspect ratio
        max_workers: Number of worker threads for concurrent processing
        delete_original: Whether to delete original files after successful processing
        quality: Output image quality (1-100)
        output_prefix: Prefix to add to processed image filenames (empty for no prefix)

    Returns:
        tuple[List[Path], List[Path]]: (processed_files, failed_files)
    """
    root_dir = Path(root_dir)
    if not root_dir.exists():
        raise ValueError(f"Directory does not exist: {root_dir}")

    # Set default max_workers if None
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() - 1)

    logger.info(f"Starting image processing in: {root_dir}")
    logger.info(
        f"Configuration: min_side_size={min_side_size}, "
        f"max_workers={max_workers}, delete_original={delete_original}, "
        f"quality={quality}, output_prefix='{output_prefix}'"
    )

    # Create preprocessor
    config = ImagePreprocessorConfig(
        input_path=root_dir,
        output_path=root_dir,  # We'll process in-place
        min_side_size=min_side_size,
        max_workers=max_workers,
        quality=quality,
        output_prefix=output_prefix,
    )

    preprocessor = ImagePreprocessor(config)

    # Process each subdirectory
    all_processed_files = []
    all_failed_files = []
    start_time = time.time()

    try:
        # Get all image files recursively
        image_files = []
        for format in config.formats:
            image_files.extend(root_dir.rglob(f"*.{format}"))
            image_files.extend(root_dir.rglob(f"*.{format.upper()}"))

        if not image_files:
            logger.warning(f"No images found in {root_dir}")
            return [], []

        logger.info(f"Found {len(image_files)} images to process")

        # Process all images
        processed_files = preprocessor.process_directory(root_dir)
        all_processed_files.extend(processed_files)

        # Delete original files if requested
        if (
            delete_original and processed_files and output_prefix
        ):  # 只在有前缀时才删除原文件
            logger.info("Starting to delete original files...")
            deleted_count = 0

            for original_file in image_files:
                try:
                    # Only delete if processing was successful
                    processed_path = next(
                        (
                            p
                            for p in processed_files
                            if p.name == f"{output_prefix}{original_file.name}"
                        ),
                        None,
                    )
                    if processed_path and processed_path.exists():
                        original_file.unlink()
                        deleted_count += 1
                        if deleted_count % 10 == 0:  # Log every 10 files
                            logger.info(f"Deleted {deleted_count} original files...")
                except Exception as e:
                    logger.error(f"Failed to delete original file {original_file}: {e}")

            logger.info(f"Finished deleting {deleted_count} original files")

    except Exception as e:
        logger.error(f"Error during processing: {e}")

    # Log summary
    duration = time.time() - start_time
    logger.info(f"Processing completed in {duration:.2f} seconds")
    logger.info(f"Total processed: {len(all_processed_files)}")
    logger.info(f"Total failed: {len(all_failed_files)}")

    return all_processed_files, all_failed_files


def process_files_in_directory(
    root_dir: str | Path,
    *,
    formats: List[str] = ["*"],
    rename_strategy: Literal["keep", "uuid", "sequence", "timestamp"] = "keep",
    prefix: str = "",
    suffix: str = "",
    sequence_start: int = 1,
    sequence_padding: int = 3,
    timestamp_format: str = "%Y%m%d_%H%M%S",
    max_workers: int | None = None,
    remove_original: bool = False,
) -> tuple[List[Path], List[Path]]:
    """
    Process all files in directory and its subdirectories with renaming options

    Args:
        root_dir: Root directory containing files
        formats: List of file formats to process (default: ["*"] for all files)
        rename_strategy: Strategy for renaming files ("keep", "uuid", "sequence", "timestamp")
        prefix: Prefix to add to processed filenames
        suffix: Suffix to add before extension
        sequence_start: Starting number for sequence strategy
        sequence_padding: Number of digits to pad sequence numbers to
        timestamp_format: Format string for timestamp strategy
        max_workers: Number of worker threads for concurrent processing
        remove_original: Whether to remove original files after successful processing

    Returns:
        tuple[List[Path], List[Path]]: (processed_files, failed_files)
    """
    root_dir = Path(root_dir)
    if not root_dir.exists():
        raise ValueError(f"Directory does not exist: {root_dir}")

    # Set default max_workers if None
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() - 1)

    logger.info(f"Starting file processing in: {root_dir}")
    logger.info(
        f"Configuration: formats={formats}, "
        f"rename_strategy={rename_strategy}, "
        f"prefix='{prefix}', suffix='{suffix}', "
        f"max_workers={max_workers}, remove_original={remove_original}"
    )

    # Create preprocessor
    config = FilePreprocessorConfig(
        formats=formats,
        rename_strategy=rename_strategy,
        prefix=prefix,
        suffix=suffix,
        sequence_start=sequence_start,
        sequence_padding=sequence_padding,
        timestamp_format=timestamp_format,
        max_workers=max_workers,
        remove_original=remove_original,
    )

    preprocessor = FilePreprocessor(config)
    start_time = time.time()

    try:
        # Process directory
        processed_files = preprocessor.process_directory(root_dir)
        failed_files = []  # FilePreprocessor handles failures internally

        # Log summary
        duration = time.time() - start_time
        logger.info(f"Processing completed in {duration:.2f} seconds")
        logger.info(f"Total processed: {len(processed_files)}")

        return processed_files, failed_files

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        return [], []


if __name__ == "__main__":
    # Example usage for image processing
    source_dir_group = [
        r"D:\works\W-WCY\0306\p1\款式",
    ]
    
    # Process images
    for source_dir in source_dir_group:
        try:
            logger.info("=== Starting Image Processing ===")
            logger.info(f"Source directory: {source_dir}")

            processed, failed = process_images_in_directory(
                source_dir,
                min_side_size=3000,
                max_workers=8,
                delete_original=True,
                quality=95,
                output_prefix="",
            )

            logger.info("=== Processing Results ===")
            # if processed:
            #     logger.info(f"Successfully processed {len(processed)} files")
            #     logger.debug("Processed files:")
            #     for file in processed:
            #         logger.debug(f"  - {file}")

            if failed:
                logger.error(f"Failed to process {len(failed)} files")
                logger.error("Failed files:")
                for file in failed:
                    logger.error(f"  - {file}")

            logger.info("=== Processing Complete ===")

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise

