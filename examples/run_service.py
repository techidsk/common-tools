import asyncio
from pathlib import Path
from service import BatchProcessor, ServiceConfig

async def main():
    config = ServiceConfig(
        target_folders=[Path("path/to/folder")],
        workflow_path=Path("workflow.json"),
        node_config_path=Path("node_config.json"),
    )
    
    processor = BatchProcessor(config)
    
    try:
        await processor.run()
    except Exception as e:
        logger.error(f"处理失败: {str(e)}")
    finally:
        await processor.dispatcher.close()

if __name__ == "__main__":
    asyncio.run(main()) 