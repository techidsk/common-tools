from pathlib import Path
from src.folder_diff import FolderDiff, FolderDiffConfig


def main():
    # Configure the paths
    config = FolderDiffConfig(
        source_dir=Path(r"C:\Users\molook\Desktop\finish"),
        target_dir=Path(r"C:\Users\molook\Desktop\output\KTC"),
        output_dir=Path(r"C:\Users\molook\Desktop\diff"),
        # 忽略这些后缀的文件
        ignore_extensions=["tmp", ".log", ".cache", ".db"],
        # 只比对文件名（不含后缀），这样可以匹配不同格式的同名文件
        compare_stem_only=True,
    )

    # Create FolderDiff instance
    diff = FolderDiff(config)

    # Find differences
    new_files, modified_files, deleted_files = diff.find_differences()

    # Print summary
    print(f"New files: {len(new_files)}")
    print(f"Modified files: {len(modified_files)}")
    print(f"Deleted files: {len(deleted_files)}")

    # Save differences
    diff.save_differences()


if __name__ == "__main__":
    main()
