from pathlib import Path
import base64
from PIL import Image
import io
from loguru import logger


def load_image_to_base64(
    image_path: str | Path, resize_short_edge: int | None = None
) -> str:
    """
    Load an image file and convert it to base64 string.

    Args:
        image_path: Path to the image file
        resize_short_edge: If provided, resize image keeping aspect ratio so shortest edge matches this value

    Returns:
        Base64 encoded string of the image
    """
    try:
        # 确保路径是 Path 对象
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image file not found: {path}")
            raise FileNotFoundError(f"Image file not found: {path}")

        # 打开图片

        image = Image.open(path)

        # 如果图片是 RGBA 模式，转换为 RGB
        if image.mode == "RGBA":
            # 创建白色背景
            background = Image.new("RGB", image.size, (255, 255, 255))
            # 将 RGBA 图片合成到白色背景上
            background.paste(image, mask=image.split()[3])  # 使用 alpha 通道作为 mask
            image = background

        # 如果需要调整大小
        if resize_short_edge:
            # 获取当前尺寸
            width, height = image.size
            # 计算缩放比例
            scale = resize_short_edge / min(width, height)
            # 计算新尺寸
            new_width = int(width * scale)
            new_height = int(height * scale)
            # 调整大小
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 转换为 base64
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=95)
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return img_str

    except Exception as e:
        logger.error(f"Failed to load/process image {image_path}: {str(e)}")
        raise


def get_image_mime_type(file_path: str | Path) -> str:
    """
    Get the MIME type of an image based on its extension.

    Args:
        file_path: Path to the image file

    Returns:
        str: MIME type string
    """
    extension = Path(file_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_types.get(extension, "application/octet-stream")


def get_image_data_uri(image_path: str | Path) -> str | None:
    """
    Create a complete data URI for an image including the MIME type.

    Args:
        image_path: Path to the image file

    Returns:
        Optional[str]: Complete data URI string or None if loading fails

    Example:
        >>> data_uri = get_image_data_uri("path/to/image.jpg")
        >>> if data_uri:
        >>>     print("Data URI created successfully")
    """
    base64_str = load_image_to_base64(image_path)
    if not base64_str:
        return None

    mime_type = get_image_mime_type(image_path)
    return f"data:{mime_type};base64,{base64_str}"
