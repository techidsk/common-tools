from pathlib import Path
from typing import List

from src.retriever import FileRetriever, FileRetrieverConfig

config = FileRetrieverConfig(
    target_folders=[Path(r"C:\Users\molook\Desktop\批量图")],
    # folder_keywords=[
    #     "zebra",
    # ],
    # image_keywords=["zebra"],
)


def handle_new_files(files: List[Path]):
    for file in files:
        print(f"发现新文件: {file} - {file.name}")
        pass


retriever = FileRetriever(config)
retriever.start(callback=handle_new_files)
