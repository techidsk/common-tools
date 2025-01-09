import asyncio
import os
from pathlib import Path
from prefect import flow
from src.service import BatchProcessor, ServiceConfig

# 设置环境变量以处理编码问题
os.environ["PYTHONIOENCODING"] = "utf-8"


@flow(
    name="comfyui-batch-process",
    # 添加日志配置
    log_prints=True,
)
async def main_flow(
    target_folders: list[str],
    workflow_path: str,
    node_config_path: str,
    batch_size: int = 5,
    folder_keywords: list[str] = None,
    servers: list[str] = None,
):
    """主工作流

    Args:
        target_folders: 目标文件夹列表
        workflow_path: 工作流配置文件路径
        node_config_path: 节点配置文件路径
        batch_size: 批处理大小
        folder_keywords: 文件夹关键词列表
        servers: 服务器列表
    """
    config = ServiceConfig(
        target_folders=[Path(p) for p in target_folders],
        folder_keywords=folder_keywords or [],
        workflow_path=Path(workflow_path),
        node_config_path=Path(node_config_path),
        batch_size=batch_size,
        servers=servers or [],
    )

    processor = BatchProcessor(config)
    await processor.run()


if __name__ == "__main__":
    # 设置部署配置
    deployment_config = {
        "target_folders": ["C:/Users/molook/Desktop/线稿图"],
        "workflow_path": "modules/comfyui/workflows/ktc_0108_v1.json",
        "node_config_path": "modules/comfyui/workflows/ktc_config.json",
        "batch_size": 5,
        "folder_keywords": [],
        "servers": [
            "https://u181579-b0ad-41f1b729.westx.seetacloud.com:8443",
            "https://u181579-980d-70588562.westx.seetacloud.com:8443/v1",
            "https://u181579-980d-70588562.westx.seetacloud.com:8443/v2",
            "https://u181579-980d-70588562.westx.seetacloud.com:8443/v3",
            "https://u181579-980d-70588562.westx.seetacloud.com:8443/v4",
        ],
    }

    # main_flow.serve(name="comfyui-batch-process", parameters=deployment_config)

    asyncio.run(main_flow(**deployment_config))
