from pathlib import Path
from typing import List, Set, Callable
from loguru import logger
from pydantic import BaseModel, Field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import os


class FileRetrieverConfig(BaseModel):
    """文件检索器配置"""

    target_folders: List[Path] = Field(
        default_factory=list, description="目标文件夹列表"
    )
    folder_keywords: List[str] = Field(
        default_factory=list, description="文件夹关键词过滤列表"
    )
    image_extensions: Set[str] = Field(
        default_factory=lambda: {".png", ".jpg", ".jpeg", ".webp"},
        description="支持的图片格式",
    )
    image_keywords: List[str] = Field(
        default_factory=list, description="图片文件名关键词过滤列表"
    )
    watch_mode: bool = Field(default=False, description="是否启用文件监控模式")


class FileEventHandler(FileSystemEventHandler):
    """文件事件处理器"""

    def __init__(
        self, retriever: "FileRetriever", callback: Callable[[List[Path]], None]
    ):
        self.retriever = retriever
        self.callback = callback

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent):
            return

        file_path = Path(event.src_path)
        if not file_path.is_file():
            return

        if self.retriever._is_valid_image(file_path):
            self.callback([file_path])


class FileRetriever:
    """文件检索器"""

    def __init__(self, config: FileRetrieverConfig):
        self.config = config
        self._processed_files: Set[Path] = set()
        self._observer = Observer() if config.watch_mode else None

    def _is_valid_image(self, file_path: Path) -> bool:
        """检查文件是否为有效的图片
        
        支持完整路径匹配和中文文件名
        """
        # 检查扩展名 (修改为更严格的大小写不敏感比较)
        file_extension = file_path.suffix.lower()
        if file_extension not in {ext.lower() for ext in self.config.image_extensions}:
            logger.trace(f"跳过非图片文件: {file_path} (扩展名: {file_extension})")
            return False

        # 检查文件名关键词
        if self.config.image_keywords:
            # 转换为字符串并统一为小写，处理完整路径
            path_str = str(file_path.absolute()).lower()
            return any(keyword.lower() in path_str for keyword in self.config.image_keywords)

        return True

    def _is_valid_folder(self, folder_path: Path) -> bool:
        """检查文件夹是否符合关键词要求
        
        检查是否为目标文件夹下的指定子文件夹
        """
        if not self.config.folder_keywords:
            return True

        # 检查是否为目标文件夹的子文件夹
        for target_folder in self.config.target_folders:
            try:
                relative = folder_path.relative_to(target_folder)
                parts = relative.parts
                logger.trace(f"检查文件夹: {folder_path}, 相对路径: {parts}")
                # 检查路径中的每个部分是否包含关键词
                return any(
                    any(keyword.lower() in part.lower() for part in parts)
                    for keyword in self.config.folder_keywords
                )
            except ValueError:
                continue

        logger.debug(f"未找到匹配的文件夹: {folder_path}")
        return False

    def scan_folders(self) -> List[Path]:
        """扫描文件夹获取图片列表"""
        all_files = []
        for folder in self.config.target_folders:
            logger.info(f"处理文件夹: {folder}")
            if not folder.exists():
                continue

            # 递归扫描所有子文件夹
            for root, _, files in os.walk(folder):
                root_path = Path(root)
                # 检查是否匹配关键词
                if self.config.folder_keywords and not any(
                    keyword in str(root_path) for keyword in self.config.folder_keywords
                ):
                    continue

                for file in files:
                    file_path = root_path / file
                    if file_path.suffix.lower() in self.config.image_extensions:
                        all_files.append(file_path)

        return all_files

    def start(self, callback=None):
        """开始检查文件

        Args:
            callback: 回调函数，接收新文件列表作为参数
        """
        logger.info("开始文件检索...")

        try:
            # 首次扫描现有文件
            new_files = self.scan_folders()
            if new_files and callback:
                callback(new_files)

            # 如果启用了监控模式，设置文件监控
            if self.config.watch_mode and self._observer:
                event_handler = FileEventHandler(self, callback)
                for folder in self.config.target_folders:
                    if folder.exists():
                        self._observer.schedule(
                            event_handler, str(folder), recursive=True
                        )

                self._observer.start()
                logger.info("文件监控已启动")
                try:
                    self._observer.join()
                except KeyboardInterrupt:
                    self._observer.stop()
                    self._observer.join()
                    logger.info("文件监控已停止")

            return new_files

        except Exception as e:
            logger.error(f"检索过程中发生错误: {e}")
            if self._observer and self._observer.is_alive():
                self._observer.stop()
                self._observer.join()
