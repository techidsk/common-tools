"""
文件预处理模块

该模块提供了文件的批量预处理功能，包括文件重命名、格式筛选等。
支持多线程并行处理以提高效率。

主要组件:
- FilePreprocessorConfig: 文件预处理器的配置类
- FilePreprocessor: 文件预处理器实现类

使用示例:
    config = FilePreprocessorConfig(
        formats=["txt", "pdf"],
        prefix="doc_",
        rename_strategy="sequence",  # 使用序列重命名
        sequence_start=1,           # 序列从1开始
        sequence_padding=3,         # 序列数字补零到3位
        max_workers=4
    )
    preprocessor = FilePreprocessor(config)
    
    # 处理整个目录
    processed_files = preprocessor.process_directory("path/to/files/")
"""

from pathlib import Path
from typing import List, Literal
from pydantic import BaseModel, Field
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import shutil
import uuid
from datetime import datetime
import re

from .base import BasePreprocessor, PreprocessorConfig


class FilePreprocessorConfig(PreprocessorConfig):
    """Configuration for file preprocessor"""
    formats: List[str] = Field(default=["*"], description="List of file formats to process. Use ['*'] for all formats")
    prefix: str = Field(default="", description="Prefix to add to processed file names")
    suffix: str = Field(default="", description="Suffix to add before file extension")
    remove_original: bool = Field(default=False, description="Whether to remove original files after processing")
    max_workers: int = Field(default=max(1, multiprocessing.cpu_count() - 1))
    
    # 重命名策略配置
    rename_strategy: Literal["keep", "uuid", "sequence", "timestamp"] = Field(
        default="keep",
        description="Rename strategy: keep (original name), uuid, sequence, or timestamp"
    )
    sequence_start: int = Field(default=1, description="Starting number for sequence strategy")
    sequence_padding: int = Field(default=3, description="Number of digits to pad sequence numbers to")
    timestamp_format: str = Field(default="%Y%m%d_%H%M%S", description="Timestamp format for timestamp strategy")
    keep_original_ext: bool = Field(default=True, description="Whether to keep original file extension")
    

class FilePreprocessor(BasePreprocessor):
    """Preprocessor for batch file operations"""
    
    def __init__(self, config: FilePreprocessorConfig):
        super().__init__(config)
        self.config: FilePreprocessorConfig = config
        self._sequence_counter = self.config.sequence_start
    
    def validate_input(self, data: Path | str) -> bool:
        """
        Validate if the input is a valid file
        
        Args:
            data: Path to file
            
        Returns:
            bool: True if valid file, False otherwise
        """
        path = Path(data)
        if not path.exists() or not path.is_file():
            return False
            
        # Check if format matches any in the config
        if "*" in self.config.formats:
            return True
            
        return path.suffix.lower().lstrip('.') in self.config.formats
    
    def _generate_uuid_name(self) -> str:
        """Generate a UUID-based filename"""
        return str(uuid.uuid4())
    
    def _generate_sequence_name(self) -> str:
        """Generate a sequence-based filename"""
        sequence = str(self._sequence_counter).zfill(self.config.sequence_padding)
        self._sequence_counter += 1
        return sequence
    
    def _generate_timestamp_name(self) -> str:
        """Generate a timestamp-based filename"""
        return datetime.now().strftime(self.config.timestamp_format)
    
    def generate_new_filename(self, file_path: Path) -> Path:
        """
        Generate new filename based on configuration and rename strategy
        
        Args:
            file_path: Original file path
            
        Returns:
            Path: New file path
        """
        # Get original extension
        original_ext = file_path.suffix
        
        # Generate base name according to strategy
        if self.config.rename_strategy == "keep":
            base_name = file_path.stem
        elif self.config.rename_strategy == "uuid":
            base_name = self._generate_uuid_name()
        elif self.config.rename_strategy == "sequence":
            base_name = self._generate_sequence_name()
        elif self.config.rename_strategy == "timestamp":
            base_name = self._generate_timestamp_name()
        else:
            base_name = file_path.stem
        
        # Apply prefix and suffix
        final_name = f"{self.config.prefix}{base_name}{self.config.suffix}"
        
        # Add extension
        if self.config.keep_original_ext:
            final_name = f"{final_name}{original_ext}"
        
        return file_path.parent / final_name
    
    def preprocess(self, data: Path | str) -> Path:
        """
        Preprocess single file (rename with prefix/suffix)
        
        Args:
            data: Path to file
            
        Returns:
            Path: Path to preprocessed file
        """
        if not self.validate_input(data):
            raise ValueError(f"Invalid input file: {data}")
            
        input_path = Path(data)
        output_path = self.generate_new_filename(input_path)
        
        try:
            # Skip if input and output paths are the same
            if input_path == output_path:
                logger.debug(f"Skipping {input_path} as no changes needed")
                return input_path
                
            # Handle file already exists
            counter = 1
            while output_path.exists():
                stem = output_path.stem
                # Remove any existing counter suffix
                stem = re.sub(r'_\(\d+\)$', '', stem)
                new_name = f"{stem}_({counter}){output_path.suffix}"
                output_path = output_path.parent / new_name
                counter += 1
                
            # Copy or move the file
            if self.config.remove_original:
                shutil.move(input_path, output_path)
                logger.info(f"Moved {input_path} to {output_path}")
            else:
                shutil.copy2(input_path, output_path)
                logger.info(f"Copied {input_path} to {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error processing {input_path}: {str(e)}")
            raise 