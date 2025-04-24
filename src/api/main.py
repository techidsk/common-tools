from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from contextlib import asynccontextmanager

from src.api.routes import workflow, batch, server
from src.api.database import init_db
from src.api.server_manager import server_manager
from src.api.task_manager import task_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("Starting up Common Tools API...")
    await init_db()
    server_manager.start_status_check()
    await task_manager.start()
    
    yield
    
    # 关闭
    logger.info("Shutting down Common Tools API...")
    server_manager.stop_status_check()
    await task_manager.stop()

app = FastAPI(
    title="Common Tools API",
    description="通用工具服务 API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建批处理API主路由
batch_api_router = APIRouter(prefix="/batch")

# 注册子路由
batch_api_router.include_router(workflow.router)
batch_api_router.include_router(batch.router)
batch_api_router.include_router(server.router)

# 注册主路由到应用
app.include_router(batch_api_router)

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    await init_db()

@app.get("/")
async def root():
    """根路径，返回服务信息"""
    return {
        "name": "Common Tools API",
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # 检查数据库连接
        await init_db()
        
        # 检查服务器管理器状态
        server_status = await server_manager.check_all_servers()
        
        # 检查任务管理器状态
        task_status = await task_manager.get_status()
        
        return {
            "status": "healthy",
            "database": "connected",
            "server_manager": server_status,
            "task_manager": task_status
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        } 