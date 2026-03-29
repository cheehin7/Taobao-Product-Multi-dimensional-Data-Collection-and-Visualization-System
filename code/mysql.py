import pymysql

def init_database():
    """
    初始化数据库和表结构
    """
    # 连接MySQL（不指定数据库）
    conn = pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='123456',
        charset='utf8mb4'
    )
    
    cursor = conn.cursor()
    
    try:
        # 创建数据库
        cursor.execute("CREATE DATABASE IF NOT EXISTS comment1")
        cursor.execute("USE comment1")
        
        # 创建数据表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `data` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `nickname` VARCHAR(255),
            `score` VARCHAR(10),
            `content` TEXT,
            `productColor` VARCHAR(255),
            `creationTime` DATETIME,
            `imageCount` INT
        )
        """)
        
        # 创建用户表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `users` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `username` VARCHAR(255) UNIQUE,
            `password` VARCHAR(255)
        )
        """)
        
        conn.commit()
        print("数据库初始化成功！")
        
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    init_database()