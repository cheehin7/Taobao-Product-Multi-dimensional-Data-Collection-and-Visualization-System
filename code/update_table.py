import pymysql

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'taobao_data',
    'port': 3306,
    'charset': 'utf8mb4'
}

def update_table_structure():
    """更新taobao_products表结构，添加缺失的字段"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SHOW TABLES LIKE 'taobao_products'")
        if not cursor.fetchone():
            print("表taobao_products不存在，请先初始化数据库")
            return
        
        # 检查并添加comment_count字段
        cursor.execute("SHOW COLUMNS FROM taobao_products LIKE 'comment_count'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE taobao_products ADD COLUMN comment_count INT DEFAULT 0 AFTER search_keyword")
            print("已添加comment_count字段")
        else:
            print("comment_count字段已存在")
        
        # 检查并添加comment_fetched字段
        cursor.execute("SHOW COLUMNS FROM taobao_products LIKE 'comment_fetched'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE taobao_products ADD COLUMN comment_fetched INT DEFAULT 0 AFTER comment_count")
            print("已添加comment_fetched字段")
        else:
            print("comment_fetched字段已存在")
        
        # 检查并添加free_shipping字段
        cursor.execute("SHOW COLUMNS FROM taobao_products LIKE 'free_shipping'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE taobao_products ADD COLUMN free_shipping VARCHAR(10) AFTER shop_name")
            print("已添加free_shipping字段")
        else:
            print("free_shipping字段已存在")
        
        conn.commit()
        
        # 显示更新后的表结构
        cursor.execute("DESCRIBE taobao_products")
        fields = cursor.fetchall()
        print("\ntaobao_products 表当前结构:")
        for field in fields:
            print(f"- {field[0]}: {field[1]}")
            
    except Exception as e:
        print(f"更新表结构时出错: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("开始更新taobao_products表结构...")
    update_table_structure()
    print("表结构更新完成。") 