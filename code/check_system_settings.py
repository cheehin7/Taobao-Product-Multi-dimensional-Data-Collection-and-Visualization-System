import pymysql

print("检查系统设置表")
print("-" * 30)

try:
    # 连接数据库
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='123456',
        database='taobao_data',
        port=3306,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # 查看系统设置表结构
    print("系统设置表结构:")
    cursor.execute("DESCRIBE system_settings")
    fields = cursor.fetchall()
    for field in fields:
        print(field)
    
    # 查看表内容
    print("\n系统设置表内容:")
    cursor.execute("SELECT * FROM system_settings")
    settings = cursor.fetchall()
    if settings:
        for setting in settings:
            print(setting)
    else:
        print("表为空，没有数据")
    
    # 关闭连接
    conn.close()
    
except Exception as e:
    print(f"发生错误: {e}")
    
print("\n检查完成") 