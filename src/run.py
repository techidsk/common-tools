import uvicorn
from loguru import logger

if __name__ == "__main__":
    logger.info("Starting Workflow API server...")
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1,
    ) 