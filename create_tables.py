import pymysql
from db_config import DB_CONFIG

def create_tables():
    """创建评论相关的数据库表"""
    conn = None
    try:
        # 连接到数据库
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查product_comments表是否存在
        cursor.execute("SHOW TABLES LIKE 'product_comments'")
        if not cursor.fetchone():
            print("正在创建product_comments表...")
            # 创建评论表
            cursor.execute("""
                CREATE TABLE product_comments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    product_id INT NOT NULL,
                    comment_text TEXT NOT NULL,
                    username VARCHAR(255) DEFAULT '匿名用户',
                    comment_date VARCHAR(50) DEFAULT '未知时间',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX (product_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            print("product_comments表创建成功！")
        else:
            print("product_comments表已存在，无需创建。")
        
        # 检查taobao_products表中是否有comment_fetched字段
        cursor.execute("SHOW TABLES LIKE 'taobao_products'")
        if cursor.fetchone():
            cursor.execute("SHOW COLUMNS FROM taobao_products LIKE 'comment_fetched'")
            if not cursor.fetchone():
                print("正在向taobao_products表添加comment_fetched字段...")
                cursor.execute("ALTER TABLE taobao_products ADD COLUMN comment_fetched INT DEFAULT 0")
                print("comment_fetched字段添加成功！")
            else:
                print("comment_fetched字段已存在，无需添加。")
        else:
            print("taobao_products表不存在，请先创建商品表！")
        
        # 提交事务
        conn.commit()
        print("所有表和字段创建/检查完成！")
        
    except Exception as e:
        print(f"创建表时出错: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_tables() 