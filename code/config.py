import os

class Config:
    # 设置数据库配置（假设使用MySQL）
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = '123456'
    MYSQL_DB = 'taobao_data'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
