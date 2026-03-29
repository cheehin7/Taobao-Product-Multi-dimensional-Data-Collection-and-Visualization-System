"""
评论爬虫包装器
用于确保能够正确导入评论爬虫模块
"""

import os
import sys

# 添加当前工作目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加code目录到Python路径
code_dir = os.path.join(current_dir, 'code')
if os.path.exists(code_dir) and code_dir not in sys.path:
    sys.path.insert(0, code_dir)

# 尝试从当前目录导入
try:
    import comment_crawler
    print("成功从当前目录导入comment_crawler模块")
except ImportError:
    # 尝试从code目录导入
    try:
        sys.path.insert(0, code_dir)
        from code import comment_crawler
        print("成功从code目录导入comment_crawler模块")
    except ImportError:
        print("无法导入comment_crawler模块")
        raise

# 导出所有函数和变量
from comment_crawler import (
    setup_driver, get_db_connection, open_product_page, is_login_required,
    confirm_login, navigate_to_comments, load_more_comments, get_comment_elements,
    extract_comment_data, extract_comments_from_source, save_comments_to_db,
    start_comment_crawl, confirm_comment_login, continue_crawl, get_status, stop_crawl
) 