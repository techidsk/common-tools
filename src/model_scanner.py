"""
通过工作流文件来获取所需要的模型信息，可以通过共享空间拉取模型。
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import json

from pydantic import BaseModel, Field
from loguru import logger


class ModelType(Enum):
    """模型类型枚举"""

    CHECKPOINT = "checkpoints"
    LORA = "loras"
    CONTROLNET = "controlnet"
    VAE = "vae"
    UPSCALER = "upscale_models"
    EMBEDDING = "embeddings"
    CLIP = "clip"
    CLIP_VISION = "clip_vision"
    UNET = "unet"
    STYLE_MODEL = "style_models"
    OTHER = "others"


class ModelPathMapping:
    """模型路径映射"""

    # 节点类型到模型类型的映射
    NODE_TYPE_MAPPING = {
        "CheckpointLoaderSimple": {"ckpt_name": ModelType.CHECKPOINT},
        "LoraLoader": {"lora_name": ModelType.LORA},
        "ControlNetLoader": {"control_net_name": ModelType.CONTROLNET},
        "VAELoader": {"vae_name": ModelType.VAE},
        "UpscaleModelLoader": {"model_name": ModelType.UPSCALER},
        "CLIPLoader": {"clip_name": ModelType.CLIP},
        "UnetLoader": {"unet_name": ModelType.UNET},
        "DualCLIPLoaderGGUF": {
            "clip_name1": ModelType.CLIP,
            "clip_name2": ModelType.CLIP,
        },
        "UnetLoaderGGUF": {"unet_name": ModelType.UNET},
        "CLIPVisionLoader": {"clip_name": ModelType.CLIP_VISION},
        "StyleModelLoader": {"style_model_name": ModelType.STYLE_MODEL},
    }

    @classmethod
    def get_model_type(cls, class_type: str, field_name: str) -> ModelType:
        """获取模型类型"""
        if class_type in cls.NODE_TYPE_MAPPING:
            return cls.NODE_TYPE_MAPPING[class_type].get(field_name, ModelType.OTHER)
        return ModelType.OTHER

    @classmethod
    def get_model_path(cls, model_type: ModelType, filename: str) -> str:
        """获取模型完整路径"""
        return f"models/{model_type.value}/{filename}"


class ModelInfo(BaseModel):
    """模型信息"""

    class_type: str = Field(..., description="节点类型")
    type: str = Field(..., description="输入字段名")
    path: str = Field(..., description="模型完整路径")
    model_type: ModelType = Field(..., description="模型类型")

    @property
    def filename(self) -> str:
        """获取文件名"""
        return Path(self.path).name

    @property
    def full_path(self) -> str:
        """获取完整路径"""
        return ModelPathMapping.get_model_path(self.model_type, self.path)


class ModelScanResult(BaseModel):
    """模型扫描结果"""

    workflow_path: Path = Field(..., description="工作流文件路径")
    models: List[ModelInfo] = Field(default_factory=list, description="所有模型信息")

    def to_dict(self) -> dict:
        return {
            "workflow_path": str(self.workflow_path),
            "models": [m.model_dump() for m in self.models],
        }

    def filter_by_extension(self, extensions: Set[str]) -> List[ModelInfo]:
        """按文件扩展名筛选模型"""
        return [
            model
            for model in self.models
            if Path(model.path).suffix.lower() in {ext.lower() for ext in extensions}
        ]


class ModelScanner:
    """模型扫描器"""

    MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}

    def __init__(self, workflow_path: Path):
        self.workflow_path = workflow_path
        self._workflow: Optional[dict] = None

    def load_workflow(self) -> dict:
        """加载工作流"""
        if self._workflow is None:
            try:
                with open(self.workflow_path, "r", encoding="utf-8") as f:
                    self._workflow = json.load(f)
                logger.info(f"工作流加载成功: {self.workflow_path}")
            except Exception as e:
                logger.error(f"工作流加载失败: {e}")
                raise
        return self._workflow

    def _is_model_path(self, value: str) -> bool:
        """检查是否为模型文件路径"""
        try:
            path = Path(value)
            return path.suffix.lower() in self.MODEL_EXTENSIONS
        except:
            return False

    def _extract_model_info(self, node_id: str, node: dict) -> List[ModelInfo]:
        """提取节点中的所有模型信息"""
        model_infos = []
        try:
            class_type = node.get("class_type", "")
            inputs = node.get("inputs", {})

            for field_name, value in inputs.items():
                if not isinstance(value, str):
                    continue

                if self._is_model_path(value):
                    # 获取模型类型
                    model_type = ModelPathMapping.get_model_type(class_type, field_name)

                    model_infos.append(
                        ModelInfo(
                            class_type=class_type,
                            type=field_name,
                            path=value,
                            model_type=model_type,
                        )
                    )

        except Exception as e:
            logger.error(f"提取模型信息失败 - 节点 {node_id}: {e}")

        return model_infos

    def scan(self, extensions: Optional[Set[str]] = None) -> ModelScanResult:
        """扫描工作流中的模型

        Args:
            extensions: 可选的扩展名过滤，如 {".safetensors", ".ckpt"}
        """
        workflow = self.load_workflow()
        result = ModelScanResult(workflow_path=self.workflow_path)

        for node_id, node in workflow.items():
            model_infos = self._extract_model_info(node_id, node)

            # 如果指定了扩展名过滤
            if extensions:
                model_infos = [
                    info
                    for info in model_infos
                    if Path(info.path).suffix.lower()
                    in {ext.lower() for ext in extensions}
                ]

            result.models.extend(model_infos)

        return result

    def scan_to_json(
        self,
        output_path: Optional[Path] = None,
        extensions: Optional[Set[str]] = None,
        include_full_path: bool = True,
    ) -> str:
        """扫描并输出为 JSON"""
        result = self.scan(extensions=extensions)

        # 转换为字典时包含完整路径
        output_dict = {
            "workflow_path": str(result.workflow_path),
            "models": [
                {
                    **m.model_dump(),
                    "full_path": m.full_path if include_full_path else None,
                }
                for m in result.models
            ],
        }

        json_str = json.dumps(output_dict, indent=2, ensure_ascii=False)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.info(f"扫描结果已保存到: {output_path}")

        return json_str
