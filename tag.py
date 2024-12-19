"""
说明，修改txt标签内容
"""

from pathlib import Path


def add_tag(file_path: str, tag: str, at_start: bool):
    """根据 at_start 的值将标签添加到文件的开头或末尾"""
    file = Path(file_path)
    # 读取现有内容
    existing_content = file.read_text() if file.exists() else ""

    if at_start:
        # 将新标签添加到文件开头
        new_content = tag + existing_content
    else:
        # 将新标签添加到文件末尾
        new_content = existing_content + tag

    # 写入更新后的内容
    with file.open("w") as f:
        f.write(new_content)


if __name__ == "__main__":
    folder = "./text/2"

    for file in Path(folder).iterdir():
        if file.is_file():
            add_tag(file, "snclora, ", at_start=True)
