import pymysql
import os
import traceback

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'port': 3306,
    'charset': 'utf8mb4'
}

def execute_sql(cursor, sql, message="执行SQL"):
    """执行SQL并处理异常"""
    try:
        cursor.execute(sql)
        print(f"{message}成功")
        return True
    except Exception as e:
        error_message = str(e)
        if "already exists" in error_message or "Duplicate" in error_message:
            print(f"{message}：对象已存在，忽略错误")
        else:
            print(f"{message}出错: {error_message}")
        return False

def init_database():
    """初始化数据库和表"""
    conn = None
    try:
        # 连接MySQL服务器（不指定数据库）
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 创建数据库
        execute_sql(cursor, 
                    "CREATE DATABASE IF NOT EXISTS taobao_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", 
                    "创建数据库")
        
        # 关闭当前连接
        cursor.close()
        conn.close()
        
        # 重新连接，这次包含数据库名
        db_config = DB_CONFIG.copy()
        db_config['database'] = 'taobao_data'
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        
        print("连接到taobao_data数据库")
        
        # 创建商品数据表
        create_taobao_products_sql = """
        CREATE TABLE IF NOT EXISTS taobao_products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            item_id INT,
            title VARCHAR(255),
            price DECIMAL(10,2),
            sales INT,
            location VARCHAR(100),
            shop_name VARCHAR(100),
            free_shipping VARCHAR(10),
            product_url TEXT,
            shop_url TEXT,
            image_url TEXT,
            search_keyword VARCHAR(100),
            comment_count INT DEFAULT 0,
            comment_fetched INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        execute_sql(cursor, create_taobao_products_sql, "创建taobao_products表")
        
        # 创建评论表
        create_product_comments_sql = """
        CREATE TABLE IF NOT EXISTS product_comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT,
            comment_text TEXT,
            username VARCHAR(100),
            comment_date VARCHAR(50),
            is_default TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES taobao_products(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        execute_sql(cursor, create_product_comments_sql, "创建product_comments表")
        
        # 检查评论表中是否需要添加列
        try:
            # 检查username列是否存在
            cursor.execute("SHOW COLUMNS FROM product_comments LIKE 'username'")
            if not cursor.fetchone():
                execute_sql(cursor, 
                           "ALTER TABLE product_comments ADD COLUMN username VARCHAR(100) AFTER comment_text", 
                           "添加username列")
            
            # 检查comment_date列是否存在
            cursor.execute("SHOW COLUMNS FROM product_comments LIKE 'comment_date'")
            if not cursor.fetchone():
                execute_sql(cursor, 
                           "ALTER TABLE product_comments ADD COLUMN comment_date VARCHAR(50) AFTER username", 
                           "添加comment_date列")
            
            # 检查is_default列是否存在
            cursor.execute("SHOW COLUMNS FROM product_comments LIKE 'is_default'")
            if not cursor.fetchone():
                execute_sql(cursor, 
                           "ALTER TABLE product_comments ADD COLUMN is_default TINYINT(1) DEFAULT 0 AFTER comment_date", 
                           "添加is_default列")
        except Exception as e:
            print(f"检查或添加评论表列时出错: {e}")
        
        # 创建taobao_data表
        create_taobao_data_sql = """
        CREATE TABLE IF NOT EXISTS taobao_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255),
            price DECIMAL(10,2),
            deal_count INT,
            shop_name VARCHAR(100),
            location VARCHAR(100),
            post_text VARCHAR(50),
            comment_total INT DEFAULT 0,
            comment_fetched INT DEFAULT 0,
            fetch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title_url TEXT,
            shop_url TEXT,
            keyword VARCHAR(100)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        execute_sql(cursor, create_taobao_data_sql, "创建taobao_data表")
        
        # 尝试添加索引（忽略已存在的情况）
        try:
            cursor.execute("SHOW INDEX FROM taobao_products WHERE Key_name = 'idx_search_keyword'")
            if not cursor.fetchone():
                execute_sql(cursor, "ALTER TABLE taobao_products ADD INDEX idx_search_keyword (search_keyword(100))", 
                            "添加search_keyword索引")
            else:
                print("search_keyword索引已存在")
        except Exception as e:
            print(f"检查search_keyword索引时出错: {e}")
        
        try:
            cursor.execute("SHOW INDEX FROM taobao_products WHERE Key_name = 'idx_created_at'")
            if not cursor.fetchone():
                execute_sql(cursor, "ALTER TABLE taobao_products ADD INDEX idx_created_at (created_at)", 
                            "添加created_at索引")
            else:
                print("created_at索引已存在")
        except Exception as e:
            print(f"检查created_at索引时出错: {e}")
                
        # 添加系统设置表
        create_system_settings_sql = """
        CREATE TABLE IF NOT EXISTS system_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(100) UNIQUE,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        execute_sql(cursor, create_system_settings_sql, "创建system_settings表")
            
        # 插入默认系统设置
        setting_data = [
            ('system_table', 'taobao_data'),
            ('location_field', 'location'),
            ('free_shipping_field', 'post_text')
        ]
        
        for key, value in setting_data:
            try:
                cursor.execute("""
                INSERT INTO system_settings (setting_key, value) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE value = %s
                """, (key, value, value))
                print(f"系统设置 {key} 已添加或更新")
            except Exception as e:
                print(f"插入系统设置 {key} 时出错: {e}")
                
        conn.commit()
        print("数据库提交更改成功")
        
        # 显示创建的表
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("\n数据库中的表:")
        for table in tables:
            print(f"- {table[0]}")
            
        # 为每个表显示字段信息
        for table_name in [t[0] for t in tables]:
            try:
                cursor.execute(f"DESCRIBE {table_name}")
                fields = cursor.fetchall()
                print(f"\n{table_name} 表结构:")
                for field in fields:
                    print(f"- {field[0]}: {field[1]}")
            except Exception as e:
                print(f"获取表 {table_name} 结构时出错: {e}")
        
        print("\n数据库初始化成功完成")
        
    except Exception as e:
        print(f"初始化数据库时出错: {e}")
        print(traceback.format_exc())
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

if __name__ == "__main__":
    print("开始初始化数据库...")
    init_database()
    print("数据库初始化结束。") 