import mysql.connector
from mysql.connector import Error
from loguru import logger
import os
import dotenv
dotenv.load_dotenv()

def get_connection():
    """获取数据库连接"""
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "comfyui_batch")
    
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )

def create_database():
    """创建数据库"""
    try:
        # 获取数据库配置
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "3306"))
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        database = os.getenv("DB_NAME", "comfyui_batch")

        # 连接到MySQL服务器
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password
        )

        if connection.is_connected():
            cursor = connection.cursor()
            
            # 创建数据库
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
            logger.info(f"Database {database} created successfully")

    except Error as e:
        logger.error(f"Error while creating database: {e}")
        raise
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL connection closed")

def update_tables(cursor):
    """更新数据库表结构"""
    # 更新servers表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            url VARCHAR(255) NOT NULL,
            status ENUM('online', 'offline', 'busy', 'error') NOT NULL DEFAULT 'offline',
            last_check TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    logger.info("Servers table updated successfully")

    # 更新workflows表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            scenario TEXT NOT NULL,
            version VARCHAR(50) NOT NULL,
            workflow_config JSON NOT NULL DEFAULT ('{}'),
            node_config JSON NOT NULL DEFAULT ('{}'),
            input_mapping JSON NOT NULL DEFAULT ('{}'),
            output_mapping JSON NOT NULL DEFAULT ('{}'),
            parameters JSON NOT NULL DEFAULT ('{}'),
            status ENUM('normal', 'hidden') NOT NULL DEFAULT 'normal',
            parent_id INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES workflows(id)
        )
    """)
    logger.info("Workflows table updated successfully")

    # 更新tasks表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            workflow_id INT NOT NULL,
            workflow_config JSON NOT NULL,
            status ENUM('pending', 'running', 'completed', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        )
    """)
    logger.info("Tasks table updated successfully")

    # 更新task_executions表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_executions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_id INT NOT NULL,
            server_id INT NOT NULL,
            status ENUM('pending', 'running', 'completed', 'failed', 'cancelled') NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            error_message TEXT NULL,
            result JSON NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (server_id) REFERENCES servers(id)
        )
    """)
    logger.info("Task executions table updated successfully")

def drop_tables(cursor):
    """删除所有表"""
    # 按照外键依赖的反序删除表
    cursor.execute("DROP TABLE IF EXISTS task_executions")
    cursor.execute("DROP TABLE IF EXISTS tasks")
    cursor.execute("DROP TABLE IF EXISTS workflows")
    cursor.execute("DROP TABLE IF EXISTS servers")
    logger.info("All tables dropped successfully")

def init_database(drop_existing: bool = False):
    """初始化数据库
    
    Args:
        drop_existing (bool): 是否删除现有表
    """
    try:
        # 创建数据库（如果不存在）
        create_database()
        
        # 连接到数据库
        connection = get_connection()
        if connection.is_connected():
            cursor = connection.cursor()
            
            # 如果需要，删除现有表
            if drop_existing:
                drop_tables(cursor)
            
            # 更新表结构
            update_tables(cursor)
            
            logger.info("Database initialization completed successfully")

    except Error as e:
        logger.error(f"Error while initializing database: {e}")
        raise
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL connection closed")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialize database")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables before creating new ones")
    args = parser.parse_args()
    
    init_database(drop_existing=args.drop) 