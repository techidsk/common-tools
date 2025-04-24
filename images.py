""" 简单处理图片的通用工具 """

import time
import uuid
from pathlib import Path

from loguru import logger
from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from PIL import ImageOps

PREFIX = "renamed_"


def resize_image(image_path: str, new_size: int = 1024):
    """调整成短边1024"""

    image_file = Path(image_path)
    image = Image.open(image_file)

    # Get current dimensions
    original_width, original_height = image.size

    # Determine the resizing scale factor
    scale = min(new_size / original_width, new_size / original_height)

    # Compute new dimensions
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)

    # Resize the image
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Save the resized image
    resized_image.save(
        f"{Path(image_path).parent} / resized_{image_file.name}", quality=95
    )

    return f"resized_{image_file.name}"


def rename_image(
    image_path: str,
):
    """重命名图片"""

    image_file = Path(image_path)

    if image_file.stem.startswith(PREFIX):
        return

    new_name = PREFIX + uuid.uuid4().hex + image_file.suffix
    logger.debug(f"rename image: {image_path} to {new_name}")

    new_path = image_file.parent / new_name
    image_file.rename(new_path)
    return new_path


def loop_folder(
    folder_path: str,
    func: callable,
):
    """遍历文件夹"""

    folder = Path(folder_path)

    for file in folder.iterdir():
        if file.is_dir():
            loop_folder(file, func)
        else:
            func(file)


def convert_image(
    image_path: str,
    target_type: str = "jpeg",
    quality: int = 98,
):
    """转换图片格式"""
    try:
        image_file = Path(image_path)
        # 跳过 jpeg 和 jpg 格式
        if image_file.suffix in [".jpeg", ".jpg"]:
            return

        new_name = image_file.stem + "." + target_type

        new_path = image_file.parent / new_name

        image = Image.open(image_file)
        image.save(new_path, target_type, quality=quality)

        # 删除源文件
        image_file.unlink()
    except Exception as e:
        logger.info(e)


def handle_image(image_path: str):
    new_path = rename_image(image_path)
    if new_path:
        convert_image(new_path)


def listen_folder(folder_path):
    path = Path(folder_path)
    if not path.is_dir():
        raise ValueError(f"The provided path {folder_path} is not a directory.")

    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=True)
    observer.start()
    print(f"Started monitoring {folder_path}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def handle_folder_change(path):
    # 处理文件夹变化的函数
    print(f"Handling changes in: {path}")


class MyHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            print(f"Directory modified: {event.src_path}")
            # 在这里调用你想要执行的函数
            handle_folder_change(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            print(f"Directory created: {event.src_path}")
            # 在这里调用你想要执行的函数
            handle_folder_change(event.src_path)
        else:
            print(f"File modified: {event.src_path}")
            # 在这里调用你想要执行的函数
            handle_image(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            print(f"Directory deleted: {event.src_path}")
            # 在这里调用你想要执行的函数
            handle_folder_change(event.src_path)


def expand_image_edges(
    image_path: str,
    padding: int = 20,
    fill_color: tuple = (255, 255, 255),  # 默认白色
    top: bool = True,
    bottom: bool = True,
    left: bool = True,
    right: bool = True,
):
    """扩充图片边缘

    Args:
        image_path: 图片路径
        padding: 边缘填充像素数
        fill_color: 填充颜色，RGB格式的元组，默认白色 (255, 255, 255)
        top: 是否填充上边缘
        bottom: 是否填充下边缘
        left: 是否填充左边缘
        right: 是否填充右边缘
    """
    try:
        image_file = Path(image_path)
        image = Image.open(image_file)

        # 如果图片是 RGBA 模式，需要先转换为 RGB
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, fill_color)
            background.paste(image, mask=image.split()[3])
            image = background

        # 计算每个方向的填充像素
        border = (
            padding if left else 0,  # 左
            padding if top else 0,  # 上
            padding if right else 0,  # 右
            padding if bottom else 0,  # 下
        )

        # 扩充边缘
        expanded_image = ImageOps.expand(image, border=border, fill=fill_color)

        # 保存图片
        new_name = f"expanded_{image_file.stem}{image_file.suffix}"
        new_path = image_file.parent / new_name
        expanded_image.save(new_path, quality=95)

        return new_path
    except Exception as e:
        logger.error(f"扩充图片边缘失败: {e}")
        return None


if __name__ == "__main__":
    # rename_image(r"C:\Users\ecpkn\Desktop\NewUI\0_0.png")

    loop_folder(
        # r"C:\Sample\Curtain\3_curtain",
        r"D:\ftp\客户素材\W-WCY\2503_批量任务\最后交图\第一批交图",
        handle_image,
    )
    # listen_folder(r"C:\Users\ecpkn\Desktop\NewUI")
