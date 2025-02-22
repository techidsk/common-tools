import os
import sys
from pathlib import Path
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.retriever import FileRetriever, FileRetrieverConfig

config = FileRetrieverConfig(
    target_folders=[Path(r"C:\Users\molook\Desktop\线稿图")],
    # folder_keywords=["output", "generated"],
    # image_keywords=["final", "complete"],
    polling_interval=2.0,
)


def handle_new_files(files: List[Path]):
    for file in files:
        print(f"发现新文件: {file}")


retriever = FileRetriever(config)
retriever.start_polling(callback=handle_new_files)
