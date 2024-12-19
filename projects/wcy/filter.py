import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.comfyui.req import single_task


def filter_original_image_folders(target_path: str | Path) -> Dict[str, List[str]]:
    """
    遍历目标文件夹，检查每个子文件夹内的文件名是否包含"原图"


        target_path: 目标文件夹路径

    Returns:
        包含两个键值对的字典：
        - 'original': 包含"原图"文件的文件夹路径列表
        - 'others': 不包含"原图"文件的文件夹路径列表
    """
    root_path = Path(target_path)

    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"Invalid directory path: {target_path}")

    result = {"original": [], "others": []}

    # 遍历所有子文件夹
    for folder_path in root_path.iterdir():
        if not folder_path.is_dir():
            continue

        # 检查文件夹内的文件
        has_original = False
        for file_path in folder_path.iterdir():
            if (
                file_path.is_file()
                and "原图" in file_path.name
                and file_path.name.startswith("原图")
            ):
                has_original = True
                break

        # 根据是否包含"原图"文件分类
        folder_str = str(folder_path)
        if has_original:
            result["original"].append(folder_str)
        else:
            result["others"].append(folder_str)

    return result


def find_changed_files(target_path: str | Path) -> list[dict]:
    """
    查找目标文件夹中包含"换装"的文件

    Args:
        target_path: 目标文件夹路径

    Returns:
        list[dict]: 包含文件信息的列表，每项包含folder和changed_file
    """
    root_path = Path(target_path)

    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"Invalid directory path: {target_path}")

    changed_files_info = []

    # 遍历所有子文件夹
    for folder_path in root_path.iterdir():
        if not folder_path.is_dir():
            continue

        # 在每个文件夹中查找换装文件
        for file_path in folder_path.iterdir():
            if not file_path.is_file():
                continue

            file_name = file_path.name
            if "换装" in file_name:
                # 获取不带扩展名的文件名
                base_name = file_path.stem
                
                # 检查所有可能的扩展名
                actual_file = None
                for ext in ['.png', '.jpg', '.jpeg']:
                    possible_file = folder_path / f"{base_name}{ext}"
                    if possible_file.exists():
                        actual_file = possible_file
                        break
                
                if actual_file:
                    changed_files_info.append(
                        {
                            "folder": str(folder_path),
                            "changed_file": actual_file.name,
                        }
                    )

    return changed_files_info


async def process_files(target_folder: str, limit: int = 3) -> None:
    """
    处理目标文件夹中的换装文件

    Args:
        target_folder: 目标文件夹路径
        limit: 处理文件的最大数量，默认为3
    """
    try:
        # 获取换装文件列表
        changed_files = find_changed_files(target_folder)
        selected_files = changed_files[:limit]

        # 处理文件
        for file_info in selected_files:
            folder = file_info["folder"]
            changed_file = file_info["changed_file"]
            print(f"Processing - folder: {folder}, file: {changed_file}")
            await single_task(folder, changed_file)

    except Exception as e:
        print(f"Error processing files: {e}")
        raise

if __name__ == "__main__":
    async def process_batch():
        try:
            target_folder = r"F:/Work/WCY/WCY-AI需求12.14"
            changed_files = find_changed_files(target_folder)
            selected_files = changed_files[3:]
            
            for file_info in selected_files:
                folder = file_info["folder"]
                changed_file = file_info["changed_file"]
                print(f"Processing - folder: {folder}, file: {changed_file}")
                await single_task(folder, changed_file)

        except Exception as e:
            print(f"Error: {e}")
            raise

    async def main():
        # 执行第一次
        print("Starting first batch...")
        await process_batch()
        
        # 执行第二次
        print("Starting second batch...")
        await process_batch()
        
        # 执行第三次
        print("Starting third batch...")
        await process_batch()

    # 只在最外层使用一次 asyncio.run()
    asyncio.run(main())