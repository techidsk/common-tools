"""
图像预处理模块

该模块提供了图像文件的预处理功能，包括调整图像大小、保持宽高比例、
批量处理目录中的图像等。支持多线程并行处理以提高效率。

主要组件:
- ImagePreprocessorConfig: 图像预处理器的配置类
- ImagePreprocessor: 图像预处理器实现类

使用示例:
    config = ImagePreprocessorConfig(min_side_size=800, quality=90)
    preprocessor = ImagePreprocessor(config)
    
    # 处理单个图像
    processed_file = preprocessor.preprocess("path/to/image.jpg")
    
    # 处理整个目录
    processed_files = preprocessor.process_directory("path/to/images/")
"""

from pathlib import Path
from typing import Any, List
from pydantic import BaseModel, Field
from PIL import Image
import math
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

from .base import BasePreprocessor, PreprocessorConfig


class ImagePreprocessorConfig(PreprocessorConfig):
    """Configuration for image preprocessor"""
    target_size: tuple[int, int] | None = None
    formats: List[str] = Field(default=["jpg", "jpeg", "png"])
    quality: int = Field(default=95, ge=1, le=100)
    min_side_size: int = Field(default=1024, description="Target size for the shorter side while maintaining aspect ratio")
    max_workers: int = Field(default=max(1, multiprocessing.cpu_count() - 1))
    output_prefix: str = Field(default="", description="Prefix to add to processed image filenames")


class ImagePreprocessor(BasePreprocessor):
    """Preprocessor for image data"""
    
    def __init__(self, config: ImagePreprocessorConfig):
        super().__init__(config)
        self.config: ImagePreprocessorConfig = config
    
    def validate_input(self, data: Path | str) -> bool:
        """
        Validate if the input is a valid image file
        
        Args:
            data: Path to image file
            
        Returns:
            bool: True if valid image file, False otherwise
        """
        path = Path(data)
        return (
            path.exists() and 
            path.is_file() and 
            path.suffix.lower().lstrip('.') in self.config.formats
        )
    
    def calculate_new_size(self, width: int, height: int) -> tuple[int, int]:
        """
        Calculate new dimensions maintaining aspect ratio
        
        Args:
            width: Original width
            height: Original height
            
        Returns:
            tuple[int, int]: New (width, height)
        """
        if width <= self.config.min_side_size and height <= self.config.min_side_size:
            return width, height
            
        # Find shorter side
        if width < height:
            # Width is shorter side
            ratio = self.config.min_side_size / width
            new_width = self.config.min_side_size
            new_height = math.floor(height * ratio)
        else:
            # Height is shorter side
            ratio = self.config.min_side_size / height
            new_height = self.config.min_side_size
            new_width = math.floor(width * ratio)
            
        return new_width, new_height
    
    def preprocess(self, data: Path | str) -> Path:
        """
        Preprocess image file
        
        Args:
            data: Path to image file
            
        Returns:
            Path: Path to preprocessed image file
        """
        if not self.validate_input(data):
            raise ValueError(f"Invalid input file: {data}")
            
        input_path = Path(data)
        
        # 保持原始路径，只修改文件名
        if self.config.output_prefix:
            output_file = input_path.parent / f"{self.config.output_prefix}{input_path.name}"
        else:
            output_file = input_path
        
        try:
            # Open and process image
            with Image.open(input_path) as img:
                # Calculate new size
                new_width, new_height = self.calculate_new_size(img.width, img.height)
                
                # Only resize if dimensions changed
                logger.info(f"{input_path} Resizing image from {img.width}x{img.height} to {new_width}x{new_height}")
                if new_width != img.width or new_height != img.height:
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"Resized image from {img.width}x{img.height} to {new_width}x{new_height}")
                    
                    # 只有在实际进行了调整时才保存
                    if output_file == input_path:
                        # 如果没有前缀且是原路径，创建临时文件
                        temp_file = input_path.parent / f"temp_{input_path.name}"
                        img.save(temp_file, quality=self.config.quality, optimize=True)
                        # 替换原文件
                        temp_file.replace(output_file)
                    else:
                        img.save(output_file, quality=self.config.quality, optimize=True)
                    
                    logger.info(f"Saved processed image to {output_file}")
                else:
                    logger.info(f"Image {input_path.name} already meets size requirements, skipping")
            
            return output_file
        except Exception as e:
            logger.error(f"Error processing {input_path}: {str(e)}")
            raise
        
    def process_directory(self, directory: Path | str) -> List[Path]:
        """
        Process all valid images in a directory using concurrent processing
        
        Args:
            directory: Path to directory containing images
            
        Returns:
            List[Path]: List of paths to processed images
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        # Collect all valid image files first
        image_files = []
        for format in self.config.formats:
            # 同时搜索小写和大写扩展名
            image_files.extend(list(directory.rglob(f"*.{format}")))
            image_files.extend(list(directory.rglob(f"*.{format.upper()}")))
        
        if not image_files:
            logger.warning(f"No valid images found in directory: {directory}")
            return []
        
        logger.info(f"Found {len(image_files)} images to process")
        processed_files = []
        failed_files = []
        
        # Process images concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            logger.info(f"Starting concurrent processing with {self.config.max_workers} workers")
            
            # Submit all tasks
            future_to_file = {
                executor.submit(self.preprocess, str(image_file)): image_file
                for image_file in image_files
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_file):
                original_file = future_to_file[future]
                try:
                    processed_file = future.result()
                    processed_files.append(processed_file)
                    logger.debug(f"Successfully processed: {original_file}")
                except Exception as e:
                    failed_files.append(original_file)
                    logger.error(f"Failed to process {original_file}: {str(e)}")
        
        # Log summary
        total = len(image_files)
        success = len(processed_files)
        failed = len(failed_files)
        logger.info(f"Processing complete: {success}/{total} successful, {failed} failed")
        
        if failed_files:
            logger.warning("Failed files: " + ", ".join(str(f) for f in failed_files))
        
        return processed_files 