import json
from pathlib import Path
from PIL import Image
import io
import base64

from loguru import logger


def load_json(file_path: str | Path) -> dict:
    """
    Read and parse a JSON file.

    Args:
        file_path: Path to the JSON file (string or Path object)

    Returns:
        Dict containing the parsed JSON data

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    # Convert string path to Path object if necessary
    path = Path(file_path) if isinstance(file_path, str) else file_path

    # Check if file exists
    if not path.exists():
        logger.error(f"JSON file not found: {path}")
        raise FileNotFoundError(f"File not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            logger.debug(f"Successfully read JSON file: {path}")
            return data

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {path}: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Error reading JSON file {path}: {str(e)}")
        raise


