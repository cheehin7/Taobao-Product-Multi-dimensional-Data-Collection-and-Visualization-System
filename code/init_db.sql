-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS taobao_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE taobao_data;

-- 创建商品数据表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建评论表
CREATE TABLE IF NOT EXISTS product_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT,
    comment_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES taobao_products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 添加索引以提高查询性能
ALTER TABLE taobao_products ADD INDEX idx_search_keyword (search_keyword(100));
ALTER TABLE taobao_products ADD INDEX idx_created_at (created_at); 