import pymysql
import logging
import hashlib
from db_config import DB_CONFIG

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_users_table():
    """创建用户表，如果不存在的话"""
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 创建users表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            role VARCHAR(20) DEFAULT 'user',
            register_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP NULL,
            status TINYINT DEFAULT 1 COMMENT '1-活跃, 0-禁用'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        cursor.execute(create_table_sql)
        logger.info("用户表创建成功或已存在")
        
        # 检查是否有admin用户，如果没有则创建
        check_admin_sql = "SELECT * FROM users WHERE username = 'admin'"
        cursor.execute(check_admin_sql)
        admin = cursor.fetchone()
        
        if not admin:
            # 使用SHA-256加密密码
            admin_password = hashlib.sha256('admin'.encode()).hexdigest()
            
            insert_admin_sql = """
            INSERT INTO users (username, password, role, status) 
            VALUES ('admin', %s, 'admin', 1)
            """
            
            cursor.execute(insert_admin_sql, (admin_password,))
            conn.commit()
            logger.info("管理员账户创建成功")
        else:
            logger.info("管理员账户已存在")
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"创建用户表出错: {e}")
        return False

if __name__ == "__main__":
    create_users_table()
    logger.info("用户表初始化完成") 