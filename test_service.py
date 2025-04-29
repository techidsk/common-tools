import asyncio
from pathlib import Path
from loguru import logger
from src.service import ServiceConfig, BatchProcessor


async def main():
    # 设置更详细的日志级别
    logger.add("debug.log", level="DEBUG")

    # 创建配置
    config = ServiceConfig(
        # 指定目标文件夹
        target_folders=[
            Path(r"D:\ftp\客户素材\A-Aitu\20250421_女装\20250422批处理素材\batch_2"),
        ],
        # 定义输入映射
        input_mapping={
            "model_image": {  # 工作流中的模特图输入节点名称
                "path": "模特",  # 模特图文件夹路径
                "description": "模特图片输入",
                "required": True,
                "is_main": True,
                "random_select": True,  # 是否随机选择图片
                "is_folder": False,
                "random_folder": False,
                "min_generations_per_input": 1,  # 每个款式至少生成的图片数量
                "max_generations_per_input": 1,  # 每个款式最多生成的图片数量
                "generations_per_style": 16,  # 每个款式文件夹生成的图片数量
            },
            "reference_image": {  # 工作流中的参考图输入节点名称
                "path": "款式",  # 款式文件夹路径
                "description": "款式图片输入",
                "required": True,
                "is_main": False,
                # "min_generations_per_input": 2,  # 每个款式至少生成的图片数量
                # "max_generations_per_input": 6,  # 每个款式最多生成的图片数量
                # "generations_per_style": 8,  # 每个款式文件夹生成的图片数量
            },
        },
        # 工作流配置
        workflow_source="file",
        workflow_path=Path(
            "modules\comfyui\workflows\jeep-0421_api.json"
        ),  # 需要替换为实际的工作流文件路径
        node_config_path=Path(
            "modules\comfyui\workflows\jeep-0421_config.json"
        ),  # 需要替换为实际的配置文件路径
        servers=[
            "https://u181579-b77b-f36fdd20.westx.seetacloud.com:8443",
            "https://u181579-8961-bcf8d392.westx.seetacloud.com:8443",
            "https://u181579-8a25-b63d98df.westx.seetacloud.com:8443",
            "https://u181579-b77b-af531005.westx.seetacloud.com:8443",
        ],
        output_root=Path("outputs"),
    )

    # 创建处理器实例
    processor = BatchProcessor(config)

    # 运行处理
    await processor.run()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
