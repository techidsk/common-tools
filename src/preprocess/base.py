from pathlib import Path
from typing import Any
from pydantic import BaseModel
from loguru import logger


class PreprocessorConfig(BaseModel):
    """Base configuration for preprocessors"""
    input_path: Path
    output_path: Path | None = None
    

class BasePreprocessor:
    """Base class for all preprocessors"""
    
    def __init__(self, config: PreprocessorConfig):
        self.config = config
        logger.info(f"Initialized {self.__class__.__name__} with config: {config}")
    
    def preprocess(self, data: Any) -> Any:
        """
        Base preprocess method that should be implemented by subclasses
        
        Args:
            data: Input data to preprocess
            
        Returns:
            Preprocessed data
        """
        raise NotImplementedError("Subclasses must implement preprocess method")
    
    def validate_input(self, data: Any) -> bool:
        """
        Validate input data
        
        Args:
            data: Input data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return True
    
    def cleanup(self) -> None:
        """Cleanup any temporary resources"""
        pass 