import uvicorn
from loguru import logger
from src.api.main import app

if __name__ == "__main__":
    # 配置日志
    logger.add("api.log", rotation="500 MB")
    
    # 启动服务
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式下启用热重载
        log_level="info"
    ) 