"""
对比文件夹内容
"""

import shutil
from pathlib import Path
from typing import Optional

from loguru import logger
from pydantic import BaseModel


class FolderDiffConfig(BaseModel):
    source_dir: Path
    target_dir: Path
    output_dir: Path
    ignore_extensions: Optional[list[str]] = None
    compare_stem_only: bool = False  # 是否只比对文件名（不含后缀）

    def model_post_init(self, __context) -> None:
        """Normalize ignore_extensions to always start with dot."""
        if self.ignore_extensions:
            self.ignore_extensions = [
                f".{ext.lstrip('.')}" for ext in self.ignore_extensions
            ]


class FolderDiff:
    """Compare two folders and save the differences to a specified location."""

    def __init__(self, config: FolderDiffConfig):
        self.config = config
        self._validate_paths()

    def _validate_paths(self) -> None:
        """Validate that source and target directories exist."""
        if not self.config.source_dir.exists():
            raise ValueError(
                f"Source directory does not exist: {self.config.source_dir}"
            )
        if not self.config.target_dir.exists():
            raise ValueError(
                f"Target directory does not exist: {self.config.target_dir}"
            )

    def _should_ignore_file(self, path: Path) -> bool:
        """Check if file should be ignored based on its extension."""
        if not self.config.ignore_extensions:
            return False
        return path.suffix.lower() in self.config.ignore_extensions

    def _get_relative_paths(self, base_path: Path) -> set[Path]:
        """Get all relative paths in a directory."""
        return {
            p.relative_to(base_path)
            for p in base_path.rglob("*")
            if p.is_file() and not self._should_ignore_file(p)
        }

    def _get_stem_map(self, paths: set[Path]) -> dict[str, Path]:
        """Create a mapping of file stems to their full paths."""
        result = {}
        for path in paths:
            # 使用父目录+stem作为键，以保持目录结构的唯一性
            key = str(path.parent / path.stem)
            if key in result:
                logger.warning(f"Duplicate stem found: {key}")
            result[key] = path
        return result

    def find_differences(self) -> tuple[set[Path], set[Path], set[Path]]:
        """Find files that are different between source and target directories.

        Returns:
            tuple containing:
            - new_files: Files that exist in target but not in source
            - modified_files: Files that exist in both but are different
            - deleted_files: Files that exist in source but not in target
        """
        source_files = self._get_relative_paths(self.config.source_dir)
        target_files = self._get_relative_paths(self.config.target_dir)

        if self.config.compare_stem_only:
            # 使用stem比对模式
            source_stems = self._get_stem_map(source_files)
            target_stems = self._get_stem_map(target_files)

            # 比对stem
            source_keys = set(source_stems.keys())
            target_keys = set(target_stems.keys())

            new_keys = target_keys - source_keys
            deleted_keys = source_keys - target_keys
            common_keys = source_keys & target_keys

            new_files = {target_stems[k] for k in new_keys}
            deleted_files = {source_stems[k] for k in deleted_keys}

            # 对于相同stem的文件，比对内容
            modified_files = set()
            for key in common_keys:
                source_file = self.config.source_dir / source_stems[key]
                target_file = self.config.target_dir / target_stems[key]

                if source_file.stat().st_size != target_file.stat().st_size:
                    modified_files.add(source_stems[key])
                    continue

                with open(source_file, "rb") as sf, open(target_file, "rb") as tf:
                    if sf.read() != tf.read():
                        modified_files.add(source_stems[key])
        else:
            # 使用原有的完整路径比对模式
            new_files = target_files - source_files
            deleted_files = source_files - target_files
            common_files = source_files & target_files

            modified_files = set()
            for rel_path in common_files:
                source_file = self.config.source_dir / rel_path
                target_file = self.config.target_dir / rel_path
                if source_file.stat().st_size != target_file.stat().st_size:
                    modified_files.add(rel_path)
                    continue

                with open(source_file, "rb") as sf, open(target_file, "rb") as tf:
                    if sf.read() != tf.read():
                        modified_files.add(rel_path)

        return new_files, modified_files, deleted_files

    def save_differences(self) -> None:
        """Save files that exist in source but are missing in target directory."""
        new_files, modified_files, deleted_files = self.find_differences()

        # Create output directory if it doesn't exist
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # 只保存source中有但target中没有的文件
        if deleted_files:
            logger.info(f"Found {len(deleted_files)} files missing in target")

            for rel_path in deleted_files:
                source_file = self.config.source_dir / rel_path
                output_file = self.config.output_dir / rel_path

                # Create parent directories if they don't exist
                output_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy the file from source
                shutil.copy2(source_file, output_file)
                logger.info(f"Copied missing file from source: {rel_path}")
        else:
            logger.info("No files missing in target")
