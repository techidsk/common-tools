"""
读取对应目录的文件夹，需要depth为2，将所有图片复制到指定的目录地址
"""

import os
import shutil
from pathlib import Path

import tqdm


from images import resize_image


def copy_files(path, target_path):
    Path(target_path).mkdir(parents=True, exist_ok=True)

    for root, dirs, files in os.walk(path):
        print(root)
        print(dirs)
        print(files)
        for file in files:
            if file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".png"):
                src = os.path.join(root, file)
                dst = os.path.join(target_path, file)
                shutil.copyfile(src, dst)


def loop_folder(folder_path, func):
    """遍历文件夹"""

    folder = Path(folder_path)

    for file in tqdm.tqdm(folder.iterdir(), desc="Processing files"):
        if file.is_dir():
            loop_folder(file, func)
        else:
            func(file.as_posix())


def rename_file(filename, keyword: str = "resized_"):
    """移除名字中关键字，重命名文件"""
    new_filename = filename.replace(keyword, "")
    os.rename(filename, new_filename)
    return new_filename


def add_caption(file: str, content: str = "a curtain"):
    """给图片添加caption"""
    # 获取文件名，创建相同文件名的txt文件, 将content 保存到txt文件中
    filename = os.path.basename(file)
    caption_file = file.replace(filename, filename.replace(".jpg", ".txt"))
    with open(caption_file, "w") as f:
        f.write(content)


if __name__ == "__main__":
    path = r"C:\Sample\Curtain\3_curtain"
    target_path = r"C:\Users\molook\Desktop\panfa4\cropped"

    # copy_files(path, target_path)

    loop_folder(target_path, lambda file: add_caption(file, content="zly woman"))