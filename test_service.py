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
            Path(r"C:\baidunetdiskdownload\2025SS\1\group_4"),
            Path(r"C:\baidunetdiskdownload\2025SS\1\group_5"),
            Path(r"C:\baidunetdiskdownload\2025SS\1\group_6"),
            Path(r"C:\baidunetdiskdownload\2025SS\1\group_7"),
            Path(r"C:\baidunetdiskdownload\2025SS\1\group_8"),
            Path(r"C:\baidunetdiskdownload\2025SS\1\group_9"),
            Path(r"C:\baidunetdiskdownload\2025SS\1\group_10"),
        ],
        # 定义输入映射
        input_mapping={
            "model_image": {  # 工作流中的模特图输入节点名称
                "path": "模特",  # 模特图文件夹路径
                "description": "模特图片输入",
                "required": True,
                "is_main": False,
                "random_select": True,  # 是否随机选择图片
            },
            "reference_image": {  # 工作流中的参考图输入节点名称
                "path": "款式",  # 款式文件夹路径
                "description": "款式图片输入",
                "required": True,
                "is_main": True,
                "max_generations_per_input": 2,  # 每个款式最多生成的图片数量
                "min_generations_per_input": 1,  # 每个款式至少生成的图片数量
            },
        },
        # 工作流配置
        workflow_path=Path(
            "modules\comfyui\workflows\wcy-0219-api.json"
        ),  # 需要替换为实际的工作流文件路径
        node_config_path=Path(
            "modules\comfyui\workflows\wcy-0219-config.json"
        ),  # 需要替换为实际的配置文件路径
        # ComfyUI 服务器配置
        servers=[
            # "http://10.31.0.141:9199",
            "http://10.31.0.138:8188",
            "http://10.31.0.138:8189",
            "http://10.31.0.139:8188",
            "http://10.31.0.139:8189",
            "http://10.31.0.142:8188",
            "http://10.31.0.142:8189",
            "https://u181579-962b-f901ff5d.westx.seetacloud.com:8443",
            "https://u181579-a468-dd518e9b.westx.seetacloud.com:8443",
            "https://u181579-8a25-2226aa5e.westx.seetacloud.com:8443",
            "https://u181579-a7bc-ce416f48.westx.seetacloud.com:8443",
        ],  # 替换为实际的服务器地址
        # 输出配置
        output_root=Path("outputs"),
        batch_size=10,  # 同时处理2张图片
    )

    # 创建处理器实例
    processor = BatchProcessor(config)

    # 运行处理
    await processor.run()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
