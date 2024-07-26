""" 简单处理图片的通用工具 """

import time
import uuid
from pathlib import Path

from loguru import logger
from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

PREFIX = "renamed_"


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
    quality: int = 90,
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


if __name__ == "__main__":
    # rename_image(r"C:\Users\ecpkn\Desktop\NewUI\0_0.png")

    # loop_folder(
    #     r"C:\Users\ecpkn\Desktop\NewUI",
    #     handle_image,
    # )
    listen_folder(r"C:\Users\ecpkn\Desktop\NewUI")
