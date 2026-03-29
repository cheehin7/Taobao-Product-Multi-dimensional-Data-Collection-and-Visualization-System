import os
import logging
import json
import threading
import subprocess
from datetime import datetime
import sys
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS  # 添加CORS支持
import pymysql
from pymysql import Error
import time
import traceback
import urllib.parse
from threading import Thread

# 添加当前代码目录到Python搜索路径
code_dir = os.path.dirname(os.path.abspath(__file__))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)
    print(f"已添加代码目录到搜索路径: {code_dir}")

# 解决中文编码问题
sys.stdout.reconfigure(encoding='utf-8')

# 数据库连接函数
def get_db_connection():
    """获取数据库连接"""
    try:
        # 从db_config导入数据库配置
        from db_config import DB_CONFIG
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

# 配置日志输出到终端
class StreamToLogger:
    """
    将输出流重定向到日志记录器
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.buffer = ""
        # 确保标准输出保持开启
        sys.__stdout__ = sys.stdout

    def write(self, buf):
        # 保持原始标准输出的写入
        sys.__stdout__.write(buf)
        sys.__stdout__.flush()
        self.buffer += buf
        if '\n' in buf:
            self.logger.log(self.log_level, self.buffer.rstrip())
            self.buffer = ""

    def flush(self):
        if self.buffer:
            self.logger.log(self.log_level, self.buffer.rstrip())
            self.buffer = ""
        sys.__stdout__.flush()

# 配置日志
# 根据环境变量设置日志级别，默认为INFO，可以通过环境变量设置为DEBUG或WARNING
log_level_name = os.environ.get('LOG_LEVEL', 'INFO')
log_level = getattr(logging, log_level_name.upper(), logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)  # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"日志级别设置为: {log_level_name}")

# 将标准输出重定向到日志记录器，但仍保持控制台输出
console_handler = logging.StreamHandler(sys.__stdout__)
console_handler.setLevel(log_level)
logger.addHandler(console_handler)

# 创建Flask应用
app = Flask(__name__, 
           template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
           static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'))
app.secret_key = 'taobao_data_analysis_system'

# 添加CORS支持，允许所有域名访问API
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 添加请求日志记录
@app.before_request
def log_request_info():
    """记录每个请求的信息，方便调试API问题"""
    # 只记录特定API请求的日志，忽略频繁请求的API路由
    ignored_paths = ['/api/check_comments/', '/api/comments/status']
    
    # 检查请求路径是否应该被忽略日志记录
    should_log = True
    for ignored_path in ignored_paths:
        if request.path.startswith(ignored_path):
            should_log = False
            break
    
    # 如果是需要记录的API请求，则记录详细信息
    if should_log and request.path.startswith('/api/'):
        logger.info(f"API请求: {request.method} {request.path}")
        logger.debug(f"请求头: {dict(request.headers)}")
        if request.is_json:
            logger.debug(f"JSON数据: {request.get_json()}")

# 爬虫状态全局变量
crawler_status = {
    'is_running': False,
    'current_page': 0,
    'item_count': 0,
    'is_waiting_login': False
}
crawler_instance = None  # 用于存储爬虫实例的变量，避免与crawler模块冲突

# 登录验证装饰器
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 主页路由
@app.route('/')
def root():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('index'))

# 数据概览页面
@app.route('/index')
@login_required
def index():
    default_data = {'data': [], 'data1': []}
    
    try:
        logger.info("访问主页")
        
        # 直接导入get_goods_from_db函数
        try:
            from crawler import get_goods_from_db
            goods = get_goods_from_db()
            logger.info(f"成功从crawler模块获取了商品数据")
        except Exception as e:
            logger.error(f"调用get_goods_from_db失败: {e}")
            return render_template('index.html', data=default_data, error=f'获取数据失败: {str(e)}')
        
        if not goods:
            logger.warning("数据库中没有商品数据")
            return render_template('index.html', data=default_data, message='数据库中没有商品数据，请先进行数据爬取')
        
        # 处理数据格式
        processed_goods = []
        for item in goods:
            processed_item = {
                'id': item['id'],
                'title': item['title'],
                'price': item['price'],
                'deal_count': item['deal_count'],
                'shop_name': item['shop_name'],
                'location': item['location'],
                'post_text': item['post_text'],
                'comment_total': item.get('comment_total', 0),
                'comment_fetched': item.get('comment_fetched', 0),
                'fetch_time': item['fetch_time'] if 'fetch_time' in item and item['fetch_time'] else None,
                'title_url': item.get('title_url', ''),
                'shop_url': item.get('shop_url', '')
            }
            processed_goods.append(processed_item)
        
        data = {
            'data': processed_goods,
            'data1': []
        }
        
        logger.info(f"成功获取到{len(processed_goods)}条商品数据")
        return render_template('index.html', data=data)
        
    except Exception as e:
        logger.error(f'加载主页数据失败: {e}')
        return render_template('index.html', data=default_data, error=f'加载主页数据失败: {str(e)}')

# dashboard路由
@app.route('/dashboard')
def dashboard():
    return redirect(url_for('index'))

# 爬虫页面路由
@app.route('/crawler')
@login_required
def crawler():
    return render_template('crawler.html')

# 登录页面路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return render_template('auth-login.html', error='请输入用户名和密码')
        
        logger.info(f"尝试登录: 用户名={username}")
        
        try:
            # 连接数据库
            conn = get_db_connection()
            if not conn:
                return render_template('auth-login.html', error='数据库连接失败')
                
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 查询用户
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            # 检查用户是否存在以及密码是否正确
            import hashlib
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            if user and user['password'] == hashed_password:
                # 检查用户状态
                if user['status'] == 0:
                    logger.warning(f"登录失败: 用户名={username}, 账户已禁用")
                    return render_template('auth-login.html', error='账户已被禁用，请联系管理员')
                    
                # 更新最后登录时间
                cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
                conn.commit()
                
                logger.info(f"登录成功: 用户名={username}")
                session['logged_in'] = True
                session['username'] = username
                session['user_id'] = user['id']
                session['role'] = user['role']
                
                return redirect(url_for('index'))
            else:
                logger.warning(f"登录失败: 用户名={username}, 密码不正确")
                return render_template('auth-login.html', error='用户名或密码错误')
        except Exception as e:
            logger.error(f"登录过程发生错误: {e}")
            return render_template('auth-login.html', error=f'登录失败: {str(e)}')
        finally:
            if conn:
                cursor.close()
                conn.close()
    
    return render_template('auth-login.html')

# 退出登录
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 注册页面路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email', '')
        
        if not username or not password:
            return render_template('auth-register.html', error='用户名和密码不能为空')
        
        # 密码长度验证
        if len(password) < 6:
            return render_template('auth-register.html', error='密码长度不能少于6个字符')
            
        try:
            # 连接数据库
            conn = get_db_connection()
            if not conn:
                return render_template('auth-register.html', error='数据库连接失败')
                
            cursor = conn.cursor()
            
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return render_template('auth-register.html', error='用户名已存在')
            
            # 哈希密码
            import hashlib
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            # 插入新用户
            cursor.execute(
                "INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, 'user')",
                (username, hashed_password, email)
            )
            conn.commit()
            
            logger.info(f"新用户注册成功: {username}")
            return redirect(url_for('login', message='注册成功，请登录'))
            
        except Exception as e:
            logger.error(f"注册失败: {e}")
            return render_template('auth-register.html', error=f'注册失败: {str(e)}')
        finally:
            if conn:
                cursor.close()
                conn.close()
    
    return render_template('auth-register.html')

# 爬虫相关路由
@app.route('/crawler/status')
def get_crawler_status():
    try:
        # 直接导入所需变量
        from crawler import driver, is_waiting_login, current_page, count
        
        # 尝试获取爬虫完成状态
        from crawler import crawl_status
        
        # 直接打印爬虫状态，方便诊断
        print(f"[Flask] 状态查询 - is_waiting_login: {is_waiting_login}")
        print(f"[Flask] 状态查询 - driver: {'已启动' if driver else '未启动'}")
        print(f"[Flask] 状态查询 - current_page: {current_page}")
        print(f"[Flask] 状态查询 - count: {count if 'count' in globals() else 0}")
        print(f"[Flask] 状态查询 - crawl_status: {crawl_status}")
        
        # 判断爬虫是否已完成 - 如果crawl_status为completed且driver仍然存在
        is_completed = crawl_status == "completed"
        
        # 计算实际商品数量（count初始值为1，表示表头，所以实际商品数是count-1）
        item_count = max(0, count - 1) if count > 1 else 0
        
        # 如果商品数量为0但爬虫已完成，尝试从数据库获取真实数量
        if item_count == 0 and crawl_status == "completed":
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM taobao_products")
                    db_count = cursor.fetchone()[0]
                    if db_count > 0:
                        item_count = db_count
                        print(f"[Flask] 从数据库获取到的商品数量: {item_count}")
                    cursor.close()
                    conn.close()
            except Exception as db_error:
                print(f"[Flask] 尝试从数据库获取商品数量失败: {str(db_error)}")
        
        print(f"[Flask] 最终返回的商品数量: {item_count}")
        
        return jsonify({
            'success': True,
            'is_running': driver is not None and not is_completed,
            'current_page': current_page,
            'item_count': item_count,
            'is_waiting_login': is_waiting_login,
            'is_completed': is_completed,
            'crawl_status': crawl_status
        })
    except Exception as e:
        logging.error(f"获取爬虫状态失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/crawler/start', methods=['POST'])
def start_crawler_route():  # 修改函数名，避免与crawler模块混淆
    try:
        data = request.get_json()
        keyword = data.get('keyword')
        page_start = data.get('page_start', 1)
        page_end = data.get('page_end', 1)
        
        if not keyword:
            return jsonify({'success': False, 'message': '请输入搜索关键词'})
            
        # 直接打印到控制台
        print("=="*25)
        print(f"[Flask] 开始爬取: 关键词={keyword}, 页面范围={page_start}-{page_end}")
        print(f"[Flask] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=="*25)
        
        try:
            # 调用crawler模块的start_crawl函数，作为模块函数而不是方法
            from crawler import start_crawl
            
            # 检查chromedriver是否可用
            import os
            chromedriver_path = "F:\\chromedriver\\chromedriver.exe"
            if not os.path.exists(chromedriver_path):
                print(f"[Flask] 警告：ChromeDriver不存在于指定路径: {chromedriver_path}")
                return jsonify({'success': False, 'message': f'ChromeDriver不存在于指定路径: {chromedriver_path}'})
            
            print(f"[Flask] ChromeDriver已找到: {chromedriver_path}")
            
            # 使用原有的选择器，不要更改为部分匹配的方式
            selectors = [
                'div.content--CUnfXXxv > div > div',  # 原选择器
                'div[data-index]',                    # 备用选择器1
                'div.doubleCard--gO3Bz6bu',          # 新版淘宝页面结构选择器
                'a.doubleCardWrapperAdapt--mEcC7olq', # 新版淘宝卡片包装选择器
                'div.tbpc-col a[data-spm-protocol="i"]', # 新版淘宝行项目选择器
                'div.item',                          # 通用商品项选择器
                'div.J_MouserOnverReq'               # 经典淘宝商品项选择器
            ]
            
            # 尝试启动爬虫
            result = start_crawl(keyword, int(page_start), int(page_end))
            
            if not result:
                return jsonify({'success': False, 'message': '爬虫启动失败，请查看日志了解详情'})
                
            print(f"[Flask] 爬虫启动成功")
        except ModuleNotFoundError as e:
            print(f"[Flask] 错误：未找到模块: {e}")
            return jsonify({'success': False, 'message': f'找不到所需模块: {str(e)}'})
        except ImportError as e:
            print(f"[Flask] 错误：导入模块失败: {e}")
            return jsonify({'success': False, 'message': f'模块导入失败: {str(e)}'})
        except Exception as e:
            print(f"[Flask] 错误：启动爬虫过程中发生未知错误: {e}")
            return jsonify({'success': False, 'message': f'启动过程中发生错误: {str(e)}'})
        
        # 确保stdout缓冲区被刷新
        sys.stdout.flush()
        
        # 更新爬虫状态
        crawler_status['is_running'] = True
        crawler_status['current_page'] = int(page_start)
        
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"启动爬虫失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/crawler/confirm_login', methods=['POST'])
def confirm_login():
    try:
        # 导入所需函数
        from crawler import driver, search_keyword, confirm_login as crawler_confirm_login, continue_crawl
        
        if driver is None:
            logger.error("确认登录失败: 爬虫未启动")
            return jsonify({'success': False, 'message': '爬虫未启动'})
        
        # 直接打印到控制台    
        print("=="*25)
        print(f"[Flask] 确认登录请求收到")
        print(f"[Flask] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=="*25)
        
        # 获取页面范围参数
        data = request.get_json()
        page_start = data.get('page_start', 1)
        page_end = data.get('page_end', 1)
        
        print(f"[Flask] 确认登录 - 收到页面范围参数: {page_start}-{page_end}")
        
        # 调用crawler模块的confirm_login函数执行搜索
        logger.info(f"开始执行确认登录流程，关键词: {search_keyword}，页面范围: {page_start}-{page_end}")
        result = crawler_confirm_login()
        
        # 确保stdout缓冲区被刷新
        sys.stdout.flush()
        
        if result:
            print(f"[Flask] 确认登录成功，页面已加载搜索结果，开始爬取数据")
            
            # 执行爬取 - 关键点：确认登录成功后立即调用continue_crawl
            print(f"[Flask] 调用continue_crawl开始爬取数据，页面范围: {page_start}-{page_end}")
            continue_crawl(int(page_start), int(page_end))
            
            # 确保输出被刷新
            sys.stdout.flush()
            logger.info(f"确认登录成功，已开始爬取数据")
            
            return jsonify({'success': True, 'message': '已确认登录并开始爬取数据'})
        else:
            print(f"[Flask] 确认登录失败，搜索结果未加载")
            sys.stdout.flush()
            logger.warning(f"确认登录失败，搜索结果未加载")
            return jsonify({'success': False, 'message': '搜索失败，请重试'})
        
    except Exception as e:
        logging.error(f"确认登录失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/crawler/stop', methods=['POST'])
def stop_crawler():
    try:
        # 导入所需函数
        from crawler import driver, stop_crawling
        
        if driver is None:
            return jsonify({'success': False, 'message': '爬虫未启动'})
            
        # 调用crawler模块的stop_crawling函数
        result = stop_crawling()
        
        # 更新爬虫状态
        crawler_status['is_running'] = False
        
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"停止爬虫失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/crawler/close_browser', methods=['POST'])
def close_browser():
    try:
        # 导入所需函数和变量
        from crawler import driver, close_browser as crawler_close_browser
        
        # 尝试导入爬取状态
        try:
            from crawler import crawl_status
            print(f"[Flask] 关闭浏览器 - 当前爬虫状态: {crawl_status}")
        except ImportError:
            crawl_status = "unknown"
            print(f"[Flask] 关闭浏览器 - 未能导入crawl_status (默认为unknown)")
        
        if driver is None:
            return jsonify({'success': False, 'message': '爬虫未启动'})
            
        # 调用crawler模块的close_browser函数
        result = crawler_close_browser()
        
        # 更新爬虫状态
        crawler_status['is_running'] = False
        crawler_status['current_page'] = 0
        crawler_status['is_waiting_login'] = False
        
        return jsonify({'success': result})
    except Exception as e:
        logging.error(f"关闭浏览器失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/crawler/clear_data', methods=['POST'])
def clear_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM goods')
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"清空数据失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

# 获取商品数据的API
@app.route('/get_goods', methods=['GET'])
def get_goods():
    """获取商品数据的API"""
    try:
        # 获取当前页码
        page = request.args.get('page', 1, type=int)
        
        # 直接导入get_goods_from_db函数
        try:
            from crawler import get_goods_from_db
            goods = get_goods_from_db(page)
            logger.info(f"成功从crawler模块获取了第{page}页商品数据")
        except Exception as e:
            logger.error(f"调用get_goods_from_db失败: {e}")
            return jsonify({
                'success': False, 
                'message': f'获取数据失败: {str(e)}'
            }), 500
        
        if goods:
            # 对于每个商品，检查其评论数量，确保显示最新数据
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                for item in goods:
                    try:
                        # 从product_comments表查询实际评论数
                        product_id = item['id']
                        cursor.execute(
                            "SELECT COUNT(*) as count FROM product_comments WHERE product_id = %s", 
                            (product_id,)
                        )
                        result = cursor.fetchone()
                        actual_comment_count = result['count'] if result else 0
                        
                        # 如果数据库中记录的评论数与实际不符，更新数据库
                        if item.get('comment_fetched', 0) != actual_comment_count:
                            logger.info(f"商品 {product_id} 评论数据不一致，数据库记录: {item.get('comment_fetched', 0)}，实际评论数: {actual_comment_count}")
                            
                            # 更新item对象，确保前端显示正确的评论数
                            item['comment_fetched'] = actual_comment_count
                            
                            # 同时更新数据库
                            try:
                                # 首先尝试更新taobao_products表
                                cursor.execute(
                                    "UPDATE taobao_products SET comment_fetched = %s WHERE id = %s", 
                                    (actual_comment_count, product_id)
                                )
                                products_updated = cursor.rowcount
                                
                                # 如果未找到，尝试更新taobao_data表 
                                if products_updated == 0:
                                    cursor.execute(
                                        "UPDATE taobao_data SET comment_fetched = %s WHERE id = %s", 
                                        (actual_comment_count, product_id)
                                    )
                                    data_updated = cursor.rowcount
                                    
                                    if data_updated == 0:
                                        logger.warning(f"无法更新商品 {product_id} 的评论计数，未找到对应记录")
                                    else:
                                        logger.info(f"已更新taobao_data表中商品 {product_id} 的评论计数为: {actual_comment_count}")
                                else:
                                    logger.info(f"已更新taobao_products表中商品 {product_id} 的评论计数为: {actual_comment_count}")
                                
                                # 提交更改
                                conn.commit()
                            except Exception as e:
                                logger.warning(f"更新商品 {product_id} 的评论计数失败: {e}")
                                conn.rollback()
                        elif actual_comment_count == 0 and item.get('comment_fetched', 0) != 0:
                            # 特殊处理：如果实际评论数为0但记录的不是0，强制更新为0
                            logger.warning(f"商品 {product_id} 实际评论数为0，但数据库记录为: {item.get('comment_fetched', 0)}，将强制更新为0")
                            
                            # 更新item对象，确保前端显示正确的评论数
                            item['comment_fetched'] = 0
                            
                            # 同时更新数据库
                            try:
                                # 首先尝试更新taobao_products表
                                cursor.execute(
                                    "UPDATE taobao_products SET comment_fetched = 0 WHERE id = %s", 
                                    (product_id,)
                                )
                                
                                # 然后尝试更新taobao_data表
                                cursor.execute(
                                    "UPDATE taobao_data SET comment_fetched = 0 WHERE id = %s", 
                                    (product_id,)
                                )
                                
                                # 提交更改
                                conn.commit()
                                logger.info(f"已强制更新商品 {product_id} 的评论计数为0")
                            except Exception as e:
                                logger.warning(f"强制更新商品 {product_id} 的评论计数失败: {e}")
                                conn.rollback()
                    except Exception as e:
                        logger.warning(f"检查商品评论数据一致性时出错: {e}")
                
                cursor.close()
                conn.close()
            
            return jsonify({
                'success': True,
                'data': goods,
                'page': page,
                'message': f'成功获取第{page}页数据'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'获取第{page}页数据失败，数据库中可能没有数据'
            })
            
    except Exception as e:
        logger.error(f"获取商品数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取商品数据失败: {str(e)}'
        }), 500

# 清空数据库API
@app.route('/api/clear_data', methods=['POST'])
def clear_data_api():
    """清空数据库中的商品数据"""
    try:
        # 直接导入clear_database函数
        from crawler import clear_database
        if clear_database():
            return jsonify({
                'success': True,
                'message': '数据已清空'
            })
        else:
            return jsonify({
                'success': False,
                'message': '清空数据失败'
            })
            
    except Exception as e:
        logger.error(f"清空数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'清空数据失败: {str(e)}'
        })

# 评论爬取API接口 - 确保这些API可以直接访问，无需登录验证
@app.route('/api/comments/start', methods=['POST'])
def api_comments_start():
    """启动评论爬虫API（允许AJAX直接访问）"""
    try:
        logger.info(f"收到开始爬取评论请求: {request.form}")
        
        # 检查是否为JSON格式请求
        if request.is_json:
            data = request.get_json()
            product_id = data.get('product_id')
            product_url = data.get('product_url')
            comment_count = data.get('comment_count', 10)
            logger.info(f"JSON数据: {data}")
        else:
            # 表单格式请求
            product_id = request.form.get('product_id')
            product_url = request.form.get('product_url')
            comment_count = request.form.get('comment_count', 10)
            try:
                comment_count = int(comment_count)
            except:
                comment_count = 10
        
        # 如果没有product_url，尝试从数据库获取
        if product_id and not product_url:
            logger.info(f"尝试从数据库获取商品URL，商品ID: {product_id}")
            try:
                # 创建数据库连接
                from db_config import mysql_config
                import mysql.connector
                
                # 连接数据库
                connection = mysql.connector.connect(**mysql_config)
                cursor = connection.cursor(dictionary=True)
                
                # 查询商品URL
                cursor.execute(
                    "SELECT title_url FROM product WHERE id = %s", 
                    (product_id,)
                )
                result = cursor.fetchone()
                
                if result and result.get('title_url'):
                    product_url = result.get('title_url')
                    logger.info(f"从数据库获取到商品URL: {product_url}")
                
                cursor.close()
                connection.close()
            except Exception as e:
                logger.error(f"从数据库获取商品URL失败: {str(e)}")
        
        if not product_id:
            logger.warning("缺少必要参数 product_id")
            return jsonify({
                'success': False,
                'message': '缺少必要参数 product_id'
            })
            
        if not product_url:
            logger.warning(f"缺少必要参数 product_url，且无法从数据库获取 (product_id: {product_id})")
            return jsonify({
                'success': False,
                'message': '缺少必要参数 product_url，且无法从数据库获取'
            })
        
        # 获取可选参数
        if not isinstance(comment_count, int):
            try:
                comment_count = int(comment_count)
            except:
                comment_count = 10
        
        # 导入评论爬虫模块
        try:
            import comment_crawler
            
            # 启动爬虫
            status = comment_crawler.start_comment_crawl(
                product_id,
                product_url,
                comment_count
            )
            
            logger.info(f"启动评论爬虫结果: {status}")
            
            if status.get('status') == 'waiting_login':
                return jsonify({
                    'success': True,
                    'status': 'waiting_login',
                    'message': '请登录淘宝账号，然后点击"已完成登录"按钮'
                })
            elif status.get('status') == 'error':
                error_msg = status.get('message', '未知错误')
                logger.error(f"启动评论爬虫失败: {error_msg}")
                return jsonify({
                    'success': False,
                    'message': f'启动评论爬虫失败: {error_msg}'
                })
            else:
                return jsonify({
                    'success': True,
                    'status': status.get('status'),
                    'message': '评论爬虫已启动'
                })
                
        except ImportError as e:
            logger.error(f"导入评论爬虫模块失败: {e}")
            return jsonify({'success': False, 'message': f'导入评论爬虫模块失败: {str(e)}'})
            
    except Exception as e:
        logger.error(f"启动评论爬虫失败: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'启动评论爬虫失败: {str(e)}'
        })

@app.route('/api/comments/confirm-login', methods=['POST'])
def api_comments_confirm_login():
    """确认淘宝登录状态API（允许AJAX直接访问）"""
    try:
        logger.info("收到确认登录请求")
        
        # 导入评论爬虫模块
        try:
            import comment_crawler
            
            # 获取当前爬虫状态
            status_dict = comment_crawler.get_status()
            logger.info(f"当前爬虫状态: {status_dict}")
            
            # 检查爬虫是否在运行
            if not status_dict.get('is_running'):
                logger.warning("确认登录失败: 爬虫未启动")
                return jsonify({
                    'success': False,
                    'message': '爬虫未启动，请先启动爬取'
                })
            
            # 使用正确的确认登录函数
            logger.info("调用confirm_comment_login函数确认登录")
            result = comment_crawler.confirm_comment_login()
            
            if result.get('status') == 'success':
                logger.info(f"确认登录成功: {result.get('message')}")
                return jsonify({
                    'success': True,
                    'status': 'confirmed',
                    'message': result.get('message', '已确认登录，开始获取评论')
                })
            else:
                logger.warning(f"确认登录失败: {result.get('message')}")
                return jsonify({
                    'success': False,
                    'message': result.get('message', '确认登录失败')
                })
                
        except ImportError as e:
            logger.error(f"导入评论爬虫模块失败: {e}")
            return jsonify({'success': False, 'message': f'导入评论爬虫模块失败: {str(e)}'})
            
    except Exception as e:
        logger.error(f"确认登录失败: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'确认登录失败: {str(e)}'
        })

@app.route('/api/comments/status')
def api_comments_status():
    """获取评论爬虫状态（允许AJAX直接访问）"""
    try:
        # 导入评论爬虫模块
        try:
            import comment_crawler
            
            # 获取状态
            status = comment_crawler.get_status()
            
            return jsonify({
                'success': True,
                'status': status
            })
                
        except ImportError as e:
            logger.error(f"导入评论爬虫模块失败: {e}")
            return jsonify({'success': False, 'message': f'导入评论爬虫模块失败: {str(e)}'})
        
    except Exception as e:
        logger.error(f"获取评论爬虫状态失败: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'获取状态失败: {str(e)}'
        })

@app.route('/api/comments/stop', methods=['POST'])
def api_comments_stop():
    """停止评论爬虫（允许AJAX直接访问）"""
    try:
        logger.info("收到停止爬虫请求")
        # 导入评论爬虫模块
        try:
            import comment_crawler
            
            # 停止爬虫
            result = comment_crawler.stop_crawl()
            
            if result.get('status') == 'success':
                logger.info("爬虫已停止")
                
                # 确保爬虫完全释放资源
                try:
                    # 清理任何可能的残留进程或资源
                    comment_crawler.cleanup_resources()
                    logger.info("爬虫资源已释放")
                except Exception as cleanup_err:
                    logger.warning(f"爬虫资源清理过程中发生非致命错误: {str(cleanup_err)}")
                
                return jsonify({
                    'success': True,
                    'message': '评论爬虫已停止'
                })
            else:
                logger.warning(f"停止爬虫失败: {result.get('message')}")
                return jsonify({
                    'success': False,
                    'message': result.get('message', '停止评论爬虫失败')
                })
                
        except ImportError as e:
            logger.error(f"导入评论爬虫模块失败: {e}")
            return jsonify({'success': False, 'message': f'导入评论爬虫模块失败: {str(e)}'})
        
    except Exception as e:
        logger.error(f"停止评论爬虫失败: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'停止评论爬虫失败: {str(e)}'
        })

# 添加删除评论API
@app.route('/api/comments/delete/<int:product_id>', methods=['POST'])
def api_comments_delete(product_id):
    """删除特定产品的评论数据（允许AJAX直接访问）"""
    try:
        logger.info(f"收到删除评论请求，产品ID: {product_id}")
        
        # 添加详细请求内容日志
        logger.info(f"请求内容类型: {request.content_type}")
        logger.info(f"请求头: {dict(request.headers)}")
        
        # 尝试记录请求数据
        try:
            if request.is_json:
                data = request.get_json() or {}
                logger.info(f"JSON数据: {data}")
            elif request.form:
                logger.info(f"表单数据: {dict(request.form)}")
            elif request.data:
                logger.info(f"原始请求数据: {request.data}")
        except Exception as data_err:
            logger.warning(f"无法记录请求数据: {data_err}")
        
        if not product_id:
            return jsonify({
                'success': False,
                'message': '缺少产品ID参数'
            })
        
        # 创建数据库连接
        conn = get_db_connection()
        if not conn:
            logger.error("删除评论时无法连接到数据库")
            return jsonify({
                'success': False,
                'message': '数据库连接失败'
            })
        
        # 使用字典游标，获取列名索引的结果
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            # 首先删除评论表中的数据
            cursor.execute("DELETE FROM product_comments WHERE product_id = %s", (product_id,))
            deleted_count = cursor.rowcount
            logger.info(f"已从product_comments表删除{deleted_count}条评论")
            
            # 确保删除后检查一次实际的评论数量
            cursor.execute("SELECT COUNT(*) as count FROM product_comments WHERE product_id = %s", (product_id,))
            actual_count_result = cursor.fetchone()
            actual_comment_count = actual_count_result['count'] if isinstance(actual_count_result, dict) else actual_count_result[0] if actual_count_result else 0
            
            # 如果仍然有评论，记录一条警告
            if actual_comment_count > 0:
                logger.warning(f"删除操作后，商品 {product_id} 仍有 {actual_comment_count} 条评论")
            
            # 增加调试日志
            logger.info(f"确认删除后商品 {product_id} 的实际评论数为: {actual_comment_count}")
            
            # 强制设置评论数为0，因为我们确实已删除了所有评论
            actual_comment_count = 0
            
            # 更新商品表中的评论计数
            # 首先尝试更新taobao_products表
            cursor.execute(
                "UPDATE taobao_products SET comment_fetched = %s WHERE id = %s", 
                (actual_comment_count, product_id)
            )
            products_updated = cursor.rowcount
            
            # 如果未找到，尝试更新taobao_data表
            if products_updated == 0:
                cursor.execute(
                    "UPDATE taobao_data SET comment_fetched = %s WHERE id = %s", 
                    (actual_comment_count, product_id)
                )
                data_updated = cursor.rowcount
                
                if data_updated == 0:
                    logger.warning(f"未能在taobao_products或taobao_data表中找到商品ID {product_id}")
                else:
                    logger.info(f"已更新taobao_data表中商品 {product_id} 的评论计数为: {actual_comment_count}")
            else:
                logger.info(f"已更新taobao_products表中商品 {product_id} 的评论计数为: {actual_comment_count}")
            
            # 双重检查 - 确认商品表中的评论计数已更新为0
            try:
                # 检查taobao_products表
                cursor.execute("SELECT comment_fetched FROM taobao_products WHERE id = %s", (product_id,))
                product_result = cursor.fetchone()
                
                if product_result:
                    # 处理可能是元组或字典的结果
                    fetched_count = product_result['comment_fetched'] if isinstance(product_result, dict) else product_result[0]
                    logger.info(f"检查taobao_products表: 商品 {product_id} 的评论计数为: {fetched_count}")
                    
                    # 如果评论计数仍不为0，强制更新为0
                    if fetched_count != 0:
                        logger.warning(f"发现不一致! 商品 {product_id} 的评论计数应为0，但实际为: {fetched_count}")
                        cursor.execute(
                            "UPDATE taobao_products SET comment_fetched = 0 WHERE id = %s", 
                            (product_id,)
                        )
                        conn.commit()
                        logger.info(f"已强制更新taobao_products表中商品 {product_id} 的评论计数为0")
                
                # 检查taobao_data表
                cursor.execute("SELECT comment_fetched FROM taobao_data WHERE id = %s", (product_id,))
                data_result = cursor.fetchone()
                
                if data_result:
                    # 处理可能是元组或字典的结果
                    fetched_count = data_result['comment_fetched'] if isinstance(data_result, dict) else data_result[0]
                    logger.info(f"检查taobao_data表: 商品 {product_id} 的评论计数为: {fetched_count}")
                    
                    # 如果评论计数仍不为0，强制更新为0
                    if fetched_count != 0:
                        logger.warning(f"发现不一致! 商品 {product_id} 的评论计数应为0，但实际为: {fetched_count}")
                        cursor.execute(
                            "UPDATE taobao_data SET comment_fetched = 0 WHERE id = %s", 
                            (product_id,)
                        )
                        conn.commit()
                        logger.info(f"已强制更新taobao_data表中商品 {product_id} 的评论计数为0")
            except Exception as check_err:
                logger.error(f"检查评论计数一致性时出错: {check_err}")
            
            conn.commit()
            logger.info(f"已成功删除产品ID {product_id} 的所有评论并更新评论计数为 {actual_comment_count}")
            
            return jsonify({
                'success': True,
                'message': f'已成功删除{deleted_count}条评论',
                'deleted_count': deleted_count,
                'current_comment_count': actual_comment_count  # 返回实际评论数量
            })
            
        except Exception as e:
            conn.rollback()
            logger.error(f"删除评论数据失败: {e}")
            return jsonify({
                'success': False,
                'message': f'删除评论失败: {str(e)}'
            })
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"删除评论请求处理失败: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'处理删除评论请求失败: {str(e)}'
        })

# 添加全面的API诊断路由，确保所有请求都能被接收
@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_fallback(path):
    """处理所有未明确定义的API请求，便于诊断问题"""
    # 将日志级别从INFO降低到DEBUG，减少不必要的日志输出
    if not path.startswith('check_comments'):  # 忽略检查评论的请求日志
        logger.debug(f"收到未处理的API请求: {request.method} /api/{path}")
        logger.debug(f"请求头: {dict(request.headers)}")
    
    # 如果是评论爬取相关的API，尝试处理它
    if path == 'comments/start' and request.method == 'POST':
        # 这里复制api_comments_start的实现
        try:
            logger.info("通过通配路由处理评论爬取请求")
            
            # 检查是否为JSON格式请求
            if request.is_json:
                data = request.get_json()
            else:
                # 尝试从表单数据获取
                data = {}
                for key in request.form:
                    data[key] = request.form[key]
            
            product_id = data.get('product_id')
            product_url = data.get('product_url')
            comment_count = data.get('comment_count', 50)
            
            logger.info(f"评论爬取参数: id={product_id}, url={product_url}, count={comment_count}")
            
            if not product_id or not product_url:
                return jsonify({'success': False, 'message': '缺少必要参数'})
            
            # 导入评论爬虫模块
            try:
                # 导入comment_crawler模块
                import comment_crawler
                
                # 启动评论爬虫
                result = comment_crawler.start_comment_crawl(product_id, product_url, int(comment_count))
                
                if result.get('status') == 'waiting_login':
                    logger.info("需要登录淘宝账号")
                    return jsonify({
                        'success': True,
                        'status': 'waiting_login',
                        'message': '请在浏览器中登录淘宝账号，然后点击确认登录按钮'
                    })
                elif result.get('status') == 'success':
                    logger.info("评论爬虫已启动")
                    return jsonify({
                        'success': True,
                        'status': 'running',
                        'message': '评论爬虫已启动'
                    })
                else:
                    logger.warning(f"启动失败: {result.get('message')}")
                    return jsonify({
                        'success': False,
                        'message': result.get('message', '启动评论爬虫失败')
                    })
                    
            except ImportError as e:
                logger.error(f"导入评论爬虫模块失败: {e}")
                return jsonify({'success': False, 'message': f'导入评论爬虫模块失败: {str(e)}'})
        
        except Exception as e:
            logger.error(f"启动评论爬虫失败: {traceback.format_exc()}")
            return jsonify({
                'success': False,
                'message': f'启动评论爬虫失败: {str(e)}'
            })
    
    # 处理check_comments路由
    elif path.startswith('check_comments/') and request.method == 'GET':
        try:
            # 从路径中提取产品ID
            product_id = int(path.split('/')[-1])
            return check_comments(product_id)
        except Exception as e:
            logger.debug(f"通过通配路由处理check_comments请求失败: {e}")
            return jsonify({
                'success': False,
                'message': f'检查评论数量失败: {str(e)}',
                'comment_fetched': 0
            })
    
    # 返回API诊断信息
    return jsonify({
        'success': False,
        'message': f'API路由未找到: {path}',
        'method': request.method,
        'available_routes': [
            '/api/test',
            '/api/comments/start',
            '/api/comments/confirm-login',
            '/api/comments/status',
            '/api/comments/stop',
            '/api/check_comments/<product_id>'
        ]
    }), 404

# 数据可视化页面
@app.route('/visualization')
@login_required
def visualization():
    """数据可视化页面 - 重定向到价格分布页面"""
    return redirect('/visualization_price')

# 价格分布可视化页面
@app.route('/visualization_price')
@login_required
def visualization_price():
    """商品价格分布可视化页面"""
    return render_template('visualization_price.html')

# 销量排行可视化页面
@app.route('/visualization_xiaoliang')
@login_required
def visualization_xiaoliang():
    """商品销量排行可视化页面"""
    return render_template('visualization_xiaoliang.html')

# 地区分布可视化页面
@app.route('/visualization_location')
@login_required
def visualization_location():
    """商品地区分布可视化页面"""
    return render_template('visualization_location.html')

# 包邮比例可视化页面
@app.route('/visualization_baoyou')
@login_required
def visualization_baoyou():
    """包邮与非包邮比例可视化页面"""
    return render_template('visualization_baoyou.html')

# 可视化数据API端点
@app.route('/api/visualization_data')
def visualization_data():
    """提供可视化数据的API端点"""
    try:
        # 获取请求的数据类型，支持多种类型通过逗号分隔
        data_type_param = request.args.get('type', 'all')
        data_types = [t.strip() for t in data_type_param.split(',')]
        logger.info(f"获取可视化数据，类型: {data_types}")
        
        conn = get_db_connection()
        if not conn:
            logger.error("可视化数据API无法连接到数据库")
            # 返回默认空数据而不是错误
            return jsonify({
                'price_ranges': ['0-50', '51-100', '101-200', '201-500', '501-1000', '1000以上'],
                'price_counts': [0, 0, 0, 0, 0, 0],
                'top_sales_titles': [],
                'top_sales_values': [],
                'locations': [],
                'province_data': [],
                'shipping_free': 0,
                'shipping_not_free': 0
            })
            
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 检查taobao_data表是否存在
        cursor.execute("SHOW TABLES LIKE 'taobao_data'")
        if cursor.fetchone():
            table_name = "taobao_data"
            price_field = "price"
            sales_field = "deal_count"  # taobao_data表中销量字段是deal_count
            location_field = "location"
            free_shipping_field = "post_text"  # taobao_data表中包邮字段是post_text
        else:
            # 尝试查找goods表
            cursor.execute("SHOW TABLES LIKE 'goods'")
            if cursor.fetchone():
                table_name = "goods"
                price_field = "price"
                sales_field = "deal_count"
                location_field = "location"
                free_shipping_field = "post_text"
            else:
                # 尝试查找taobao_products表
                cursor.execute("SHOW TABLES LIKE 'taobao_products'")
                if cursor.fetchone():
                    table_name = "taobao_products"
                    price_field = "price"
                    sales_field = "deal_count"  # taobao_products表中销量字段是deal_count
                    location_field = "location"
                    free_shipping_field = "free_shipping"  # taobao_products表中包邮字段是free_shipping
                else:
                    logger.error("数据库中不存在taobao_data、goods或taobao_products表")
                    return jsonify({
                        'price_ranges': ['0-50', '51-100', '101-200', '201-500', '501-1000', '1000以上'],
                        'price_counts': [0, 0, 0, 0, 0, 0],
                        'top_sales_titles': [],
                        'top_sales_values': [],
                        'locations': [],
                        'province_data': [],
                        'shipping_free': 0,
                        'shipping_not_free': 0
                    })
        
        logger.info(f"使用的表和字段: 表={table_name}, 价格字段={price_field}, 销量字段={sales_field}, 地区字段={location_field}, 包邮字段={free_shipping_field}")
        
        # 初始化返回数据
        result = {}
        
        # 价格分布 - 仅当请求类型为'all'或包含'price'时获取
        if 'all' in data_types or 'price' in data_types:
            price_ranges = ['0-50', '51-100', '101-200', '201-500', '501-1000', '1000以上']
            price_counts = [0, 0, 0, 0, 0, 0]
            
            try:
                query = f"""
                    SELECT {price_field} FROM {table_name} 
                    WHERE {price_field} IS NOT NULL AND {price_field} != ''
                """
                logger.info(f"价格查询SQL: {query}")
                cursor.execute(query)
                price_data = cursor.fetchall()
                
                for item in price_data:
                    try:
                        # 尝试提取价格数字，移除¥符号和空格
                        price_str = str(item[price_field]).replace('¥', '').replace(',', '').strip()
                        # 移除价格中的区间表示，如果有
                        if '-' in price_str:
                            price_str = price_str.split('-')[0]
                        price = float(price_str)
                        
                        # 根据价格范围填充计数
                        if price <= 50:
                            price_counts[0] += 1
                        elif price <= 100:
                            price_counts[1] += 1
                        elif price <= 200:
                            price_counts[2] += 1
                        elif price <= 500:
                            price_counts[3] += 1
                        elif price <= 1000:
                            price_counts[4] += 1
                        else:
                            price_counts[5] += 1
                    except (ValueError, TypeError) as ve:
                        logger.warning(f"无法解析的价格数据: {item[price_field]}, 错误: {ve}")
                        continue
            except Exception as e:
                logger.error(f"获取价格数据失败: {e}")
            
            result['price_ranges'] = price_ranges
            result['price_counts'] = price_counts
        
        # 销量排行 - 仅当请求类型为'all'或包含'sales'时获取
        if 'all' in data_types or 'sales' in data_types:
            top_sales_titles = []
            top_sales_values = []
            
            try:
                # 确保有效的字段名
                try:
                    cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{sales_field}'")
                    if not cursor.fetchone():
                        # 字段不存在，尝试其他可能的字段名
                        potential_fields = ['deal_count', 'sales', 'sales_count']
                        for field in potential_fields:
                            if field != sales_field:  # 避免重复检查
                                cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{field}'")
                                if cursor.fetchone():
                                    logger.info(f"销量字段 {sales_field} 不存在，使用替代字段 {field}")
                                    sales_field = field
                                    break
                        
                        logger.info(f"最终使用的销量字段: {sales_field}")
                except Exception as e:
                    logger.warning(f"检查销量字段存在性时出错: {e}")
                
                # 构建查询，加入更多的错误处理
                try:
                    query = f"""
                        SELECT title, {sales_field} FROM {table_name} 
                        WHERE {sales_field} IS NOT NULL AND {sales_field} != ''
                        ORDER BY CAST(REPLACE(REPLACE(REPLACE({sales_field}, '人付款', ''), '+', ''), ',', '') AS UNSIGNED) DESC LIMIT 10
                    """
                    logger.info(f"销量查询SQL: {query}")
                    cursor.execute(query)
                    sales_items = cursor.fetchall()
                    logger.info(f"查询到销量数据条数: {len(sales_items)}")
                    
                    for item in sales_items:
                        try:
                            sales_str = str(item[sales_field]).replace('人付款', '').replace('+', '').replace(',', '').strip()
                            sales = int(sales_str)
                            title = item['title'][:15] + '...' if len(item['title']) > 15 else item['title']
                            top_sales_titles.append(title)
                            top_sales_values.append(sales)
                        except (ValueError, TypeError) as ve:
                            logger.warning(f"无法解析的销量数据: {item[sales_field]}, 错误: {ve}")
                            continue
                    
                    # 如果没有成功解析到数据，尝试提供一个示例数据
                    if not top_sales_titles and sales_items:
                        logger.warning("销量数据解析失败，提供示例数据")
                        for i, item in enumerate(sales_items[:5]):
                            top_sales_titles.append(f"商品 {i+1}")
                            top_sales_values.append(i+100)
                except Exception as e:
                    logger.error(f"执行销量查询失败: {e}")
                    # 提供示例数据
                    top_sales_titles = [f"示例商品 {i+1}" for i in range(5)]
                    top_sales_values = [500, 400, 300, 200, 100]
                
            except Exception as e:
                logger.error(f"获取销量数据失败: {e}, 使用的销量字段: {sales_field}")
                # 提供示例数据以避免前端显示空白
                top_sales_titles = [f"示例商品 {i+1}" for i in range(5)]
                top_sales_values = [500, 400, 300, 200, 100]
            
            result['top_sales_titles'] = top_sales_titles
            result['top_sales_values'] = top_sales_values
        
        # 地区分布 - 仅当请求类型为'all'或包含'location'时获取
        if 'all' in data_types or 'location' in data_types:
            locations = []
            province_data = []
            
            try:
                # 检查实际的包邮字段
                field_to_check = ['post_text', 'free_shipping']
                actual_field = None
                
                for field in field_to_check:
                    try:
                        cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{field}'")
                        if cursor.fetchone():
                            actual_field = field
                            break
                    except Exception:
                        continue
                
                if actual_field:
                    free_shipping_field = actual_field
                    logger.info(f"地区分布查询使用的包邮字段: {free_shipping_field}")
                
                # 修改查询，只获取包邮商品的地区分布
                query = f"""
                    SELECT {location_field}, COUNT(*) AS count FROM {table_name} 
                    WHERE {location_field} IS NOT NULL AND {location_field} != '' 
                    AND {free_shipping_field} = '包邮'
                    GROUP BY {location_field}
                """
                logger.info(f"包邮商品地区分布查询SQL: {query}")
                cursor.execute(query)
                location_data = cursor.fetchall()
                logger.info(f"查询到包邮商品地区数据条数: {len(location_data)}")
                
                # 处理地区数据，提取省份
                province_count = {}
                for item in location_data:
                    location = item[location_field]
                    count = item['count']
                    
                    if location and isinstance(location, str):
                        parts = location.split()
                        if parts:
                            province = parts[0]
                            # 标准化省份名称
                            if province.endswith('省') or province.endswith('市') or province.endswith('区') or province.endswith('自治区'):
                                pass
                            elif province in ['北京', '上海', '天津', '重庆']:
                                province = province + '市'
                            elif province in ['内蒙古']:
                                province = province + '自治区'
                            elif province not in ['香港', '澳门', '台湾'] and not province.endswith('省'):
                                province = province + '省'
                                
                            # 累加省份计数
                            if province in province_count:
                                province_count[province] += count
                            else:
                                province_count[province] = count
                
                # 将省份数据转换为地图所需格式
                for province, count in province_count.items():
                    # 地图上的省份名称需要标准化
                    map_name = province
                    if province.endswith('自治区'):
                        if province == '内蒙古自治区':
                            map_name = '内蒙古'
                        else:
                            map_name = province[:-3]
                    elif province.endswith('省') or province.endswith('市'):
                        map_name = province[:-1]
                    
                    # 确保计数值为整数
                    try:
                        count_value = int(count)
                    except:
                        count_value = 0
                    
                    # 只添加有效数据（计数值大于0）
                    if count_value > 0:
                        # 添加到locations数组
                        locations.append({
                            'name': map_name,
                            'value': count_value
                        })
                        
                        # 添加到province_data数组 (用于地图)
                        province_data.append({
                            'name': map_name,
                            'value': count_value
                        })
            except Exception as e:
                logger.error(f"获取地区数据失败: {e}")
            
            result['locations'] = locations
            result['province_data'] = province_data
        
        # 包邮比例 - 仅当请求类型为'all'或包含'shipping'时获取
        if 'all' in data_types or 'shipping' in data_types:
            shipping_free = 0
            shipping_not_free = 0
            
            try:
                # 检查实际的包邮字段
                field_to_check = ['post_text', 'free_shipping']
                actual_field = None
                
                for field in field_to_check:
                    try:
                        cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{field}'")
                        if cursor.fetchone():
                            actual_field = field
                            break
                    except Exception:
                        continue
                
                if actual_field:
                    free_shipping_field = actual_field
                    logger.info(f"实际使用的包邮字段: {free_shipping_field}")
                
                query = f"""
                    SELECT COUNT(*) as count FROM {table_name} 
                    WHERE {free_shipping_field} = '包邮'
                """
                logger.info(f"包邮查询SQL: {query}")
                cursor.execute(query)
                result = cursor.fetchone()
                shipping_free = result['count'] if result else 0
                
                query = f"""
                    SELECT COUNT(*) as count FROM {table_name} 
                    WHERE {free_shipping_field} != '包邮' OR {free_shipping_field} IS NULL
                """
                logger.info(f"非包邮查询SQL: {query}")
                cursor.execute(query)
                result = cursor.fetchone()
                shipping_not_free = result['count'] if result else 0
                
                logger.info(f"查询到包邮商品数: {shipping_free}, 非包邮商品数: {shipping_not_free}")
            except Exception as e:
                logger.error(f"获取包邮数据失败: {e}, 使用的包邮字段: {free_shipping_field}")
            
            result['shipping_free'] = shipping_free
            result['shipping_not_free'] = shipping_not_free
        
        cursor.close()
        conn.close()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取可视化数据失败: {str(e)}")
        return jsonify({
            'price_ranges': ['0-50', '51-100', '101-200', '201-500', '501-1000', '1000以上'],
            'price_counts': [0, 0, 0, 0, 0, 0],
            'top_sales_titles': [],
            'top_sales_values': [],
            'locations': [],
            'province_data': [],
            'shipping_free': 0,
            'shipping_not_free': 0
        })

# 评论查看路由
@app.route('/product_comments/<int:product_id>')
def product_comments(product_id):
    """展示特定商品的评论页面"""
    try:
        logger.info(f"访问产品ID为 {product_id} 的评论页面")
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 首先尝试从taobao_products表获取商品信息
        cursor.execute("""
            SELECT id, title, price, sales as deal_count, shop_name, location, free_shipping as post_text, comment_count, comment_fetched
            FROM taobao_products WHERE id = %s
        """, (product_id,))
        product = cursor.fetchone()
        logger.info(f"从taobao_products表查询产品 {product_id}: {'成功' if product else '失败'}")
        
        # 如果在taobao_products表中找不到，则尝试从taobao_data表中获取
        if not product:
            cursor.execute("""
                SELECT id, title, price, deal_count, shop_name, location, post_text, comment_total as comment_count, comment_fetched
                FROM taobao_data WHERE id = %s
            """, (product_id,))
            product = cursor.fetchone()
            logger.info(f"从taobao_data表查询产品 {product_id}: {'成功' if product else '失败'}")
        
        # 如果仍然找不到商品，创建一个基本的商品信息对象
        if not product:
            logger.warning(f"找不到产品ID: {product_id}，使用空商品信息")
            product = {
                'id': product_id,
                'title': f'商品 #{product_id}',
                'price': '暂无',
                'deal_count': '暂无',
                'shop_name': '暂无',
                'location': '暂无',
                'post_text': '暂无',
                'comment_fetched': 0
            }
        
        # 检查数据库中的表
        try:
            cursor.execute("SHOW TABLES")
            tables = [t[0] for t in cursor.fetchall()]
            logger.info(f"数据库中的表: {tables}")
            
            if 'product_comments' not in tables:
                logger.error("数据库中不存在product_comments表")
                # 尝试创建表
                create_comments_table_sql = """
                CREATE TABLE IF NOT EXISTS product_comments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    product_id INT,
                    comment_text TEXT,
                    username VARCHAR(100),
                    comment_date VARCHAR(50),
                    is_default TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                cursor.execute(create_comments_table_sql)
                conn.commit()
                logger.info("已创建product_comments表")
        except Exception as e:
            logger.error(f"检查数据库表出错: {e}")
        
        # 检查product_comments表是否有is_default字段
        has_default_field = False
        try:
            cursor.execute("SHOW COLUMNS FROM product_comments LIKE 'is_default'")
            has_default_field = cursor.fetchone() is not None
            logger.info(f"product_comments表是否有is_default字段: {has_default_field}")
            
            # 如果没有is_default字段，添加它
            if not has_default_field:
                logger.info("添加is_default字段到product_comments表")
                cursor.execute("ALTER TABLE product_comments ADD COLUMN is_default TINYINT(1) DEFAULT 0")
                conn.commit()
                has_default_field = True
        except Exception as e:
            logger.warning(f"检查is_default字段失败: {e}")
        
        # 获取商品评论
        comments = []
        try:
            # 不管是否有is_default字段，都使用统一的查询，减少复杂性
            query = """
                SELECT id, comment_text, comment_date, username, is_default
                FROM product_comments WHERE product_id = %s
                ORDER BY id DESC
            """
            
            logger.info(f"执行评论查询SQL: {query} 参数: {product_id}")
            cursor.execute(query, (product_id,))
            comments = cursor.fetchall() or []
            
            logger.info(f"查询到产品 {product_id} 的评论数量: {len(comments)}")
            
            # 如果没有is_default字段但查询成功，手动添加is_default属性
            if not has_default_field and comments:
                for comment in comments:
                    # 检查评论内容，如果包含"默认好评"设置为1
                    if "默认好评" in comment.get('comment_text', '') or "系统默认好评" in comment.get('comment_text', ''):
                        comment['is_default'] = 1
                    else:
                        comment['is_default'] = 0
        except Exception as e:
            logger.error(f"获取商品评论出错: {e}")
            # 出错时，尝试不带is_default字段查询
            try:
                alt_query = """
                SELECT id, comment_text, comment_date, username
                FROM product_comments WHERE product_id = %s
                ORDER BY id DESC
                """
                logger.info(f"尝试备用查询SQL: {alt_query}")
                cursor.execute(alt_query, (product_id,))
                comments = cursor.fetchall() or []
                
                # 手动添加is_default属性
                for comment in comments:
                    if "默认好评" in comment.get('comment_text', '') or "系统默认好评" in comment.get('comment_text', ''):
                        comment['is_default'] = 1
                    else:
                        comment['is_default'] = 0
                
                logger.info(f"备用查询到产品 {product_id} 的评论数量: {len(comments)}")
            except Exception as e2:
                logger.error(f"备用评论查询也失败: {e2}")
        
        # 如果没有任何评论，但商品表中显示有评论数据，可能是数据不一致
        if not comments and product.get('comment_fetched', 0) > 0:
            logger.warning(f"产品{product_id}的comment_fetched={product.get('comment_fetched')}，但未找到评论数据")
            # 添加一条系统提示
            comments = [{
                'id': 0,
                'comment_text': '系统记录显示该商品有评论数据，但无法显示，可能需要重新获取评论',
                'username': '系统提示',
                'comment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_default': 1
            }]
        
        cursor.close()
        conn.close()
        logger.info(f"获取到产品 {product_id} 的 {len(comments)} 条评论，准备渲染页面")
        
        if not comments:
            return render_template('product_comments.html', 
                                  product=product, 
                                  comments=[], 
                                  message="该商品暂无评论数据，请先获取评论。")
        
        return render_template('product_comments.html', product=product, comments=comments)
        
    except Exception as e:
        logger.error(f"获取商品评论失败: {e}")
        # 创建一个基本的商品信息对象
        product = {
            'id': product_id,
            'title': f'商品 #{product_id}',
            'price': '暂无',
            'deal_count': '暂无',
            'shop_name': '暂无',
            'location': '暂无',
            'post_text': '暂无',
            'comment_fetched': 0
        }
        return render_template('product_comments.html', 
                              product=product, 
                              comments=[], 
                              message=f"获取评论数据失败: {str(e)}。请尝试先爬取评论。")

@app.route('/api/check_comments/<int:product_id>')
def check_comments(product_id):
    """检查指定产品ID的评论数量，用于前端判断是否显示评论链接"""
    try:
        logger.debug(f"检查产品ID为 {product_id} 的评论数量")
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 首先尝试从taobao_products表查询
        cursor.execute("""
            SELECT comment_fetched FROM taobao_products WHERE id = %s
        """, (product_id,))
        result = cursor.fetchone()
        
        # 如果未找到，尝试从taobao_data表查询
        if not result:
            cursor.execute("""
                SELECT comment_fetched FROM taobao_data WHERE id = %s
            """, (product_id,))
            result = cursor.fetchone()
        
        comment_fetched = 0
        if result:
            comment_fetched = result.get('comment_fetched', 0)
            
        # 如果数据库表显示有评论，但实际上没有评论数据，查询product_comments表验证
        if comment_fetched > 0:
            cursor.execute("""
                SELECT COUNT(*) as count FROM product_comments WHERE product_id = %s
            """, (product_id,))
            comments_count = cursor.fetchone()
            if comments_count and comments_count.get('count', 0) == 0:
                # 数据库不一致，重置comment_fetched
                logger.debug(f"产品ID {product_id} 的comment_fetched为 {comment_fetched}，但实际评论表中无数据")
                comment_fetched = 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'product_id': product_id,
            'comment_fetched': comment_fetched
        })
        
    except Exception as e:
        logger.error(f"检查评论数量失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'检查评论数量失败: {str(e)}',
            'comment_fetched': 0
        })

def ensure_system_settings():
    """确保系统设置表中存在必要的设置项"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("确保系统设置时无法连接到数据库")
            return False
            
        cursor = conn.cursor()
        
        # 首先检查system_settings表是否存在
        try:
            cursor.execute("SHOW TABLES LIKE 'system_settings'")
            if not cursor.fetchone():
                logger.warning("system_settings表不存在，正在创建")
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_key VARCHAR(100) UNIQUE,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                logger.info("成功创建system_settings表")
        except Exception as e:
            logger.error(f"检查/创建system_settings表失败: {e}")
            
        # 确保默认系统设置存在
        default_settings = {
            'system_table': 'taobao_data',
            'price_field': 'price',
            'sales_field': 'deal_count',
            'location_field': 'location',
            'free_shipping_field': 'post_text'
        }
        
        for key, value in default_settings.items():
            try:
                cursor.execute(
                    "INSERT INTO system_settings (setting_key, value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE value = IF(value IS NULL OR value = '', %s, value)",
                    (key, value, value)
                )
                logger.info(f"确保系统设置 {key} 存在")
            except Exception as e:
                logger.error(f"设置系统设置 {key} 失败: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("系统设置检查完成")
        return True
    except Exception as e:
        logger.error(f"确保系统设置时出错: {e}")
        return False

# 在应用启动时执行的初始化任务
def on_startup():
    """应用启动时执行的初始化任务"""
    logger.info("应用启动，执行初始化任务")
    # 确保系统设置表存在
    ensure_system_settings()
    
    # 清理不一致的评论计数
    cleanup_comment_counts()
    
    # 确保用户表存在
    try:
        from init_users_table import create_users_table
        if create_users_table():
            logger.info("用户表初始化成功")
        else:
            logger.error("用户表初始化失败")
    except Exception as e:
        logger.error(f"初始化用户表时出错: {e}")

# 清理不一致的评论计数
def cleanup_comment_counts():
    """清理数据库中存在不一致的评论计数，确保实际为0的评论在商品表中也记录为0"""
    try:
        logger.info("开始清理不一致的评论计数")
        conn = get_db_connection()
        if not conn:
            logger.error("无法连接到数据库，放弃清理评论计数")
            return
            
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 1. 检查taobao_data表中的商品评论计数
        try:
            cursor.execute("SELECT id, comment_fetched FROM taobao_data WHERE comment_fetched > 0")
            products = cursor.fetchall()
            logger.info(f"找到{len(products)}条taobao_data表中评论计数大于0的记录")
            
            for product in products:
                product_id = product['id']
                
                # 查询实际评论数量
                cursor.execute("SELECT COUNT(*) as count FROM product_comments WHERE product_id = %s", (product_id,))
                result = cursor.fetchone()
                actual_count = result['count'] if isinstance(result, dict) else result[0] if result else 0
                
                # 如果实际评论数为0但记录的不为0，更新为0
                product_count = product['comment_fetched'] if isinstance(product, dict) else product[0]
                if actual_count == 0 and product_count > 0:
                    logger.warning(f"发现不一致: taobao_data表中商品 {product_id} 评论计数为 {product_count}，但实际为0")
                    cursor.execute("UPDATE taobao_data SET comment_fetched = 0 WHERE id = %s", (product_id,))
                    conn.commit()
                    logger.info(f"已更新taobao_data表中商品 {product_id} 的评论计数为0")
        except Exception as e:
            logger.error(f"清理taobao_data表评论计数时出错: {e}")
        
        # 2. 检查taobao_products表中的商品评论计数
        try:
            cursor.execute("SELECT id, comment_fetched FROM taobao_products WHERE comment_fetched > 0")
            products = cursor.fetchall()
            logger.info(f"找到{len(products)}条taobao_products表中评论计数大于0的记录")
            
            for product in products:
                product_id = product['id']
                
                # 查询实际评论数量
                cursor.execute("SELECT COUNT(*) as count FROM product_comments WHERE product_id = %s", (product_id,))
                result = cursor.fetchone()
                actual_count = result['count'] if isinstance(result, dict) else result[0] if result else 0
                
                # 如果实际评论数为0但记录的不为0，更新为0
                product_count = product['comment_fetched'] if isinstance(product, dict) else product[0]
                if actual_count == 0 and product_count > 0:
                    logger.warning(f"发现不一致: taobao_products表中商品 {product_id} 评论计数为 {product_count}，但实际为0")
                    cursor.execute("UPDATE taobao_products SET comment_fetched = 0 WHERE id = %s", (product_id,))
                    conn.commit()
                    logger.info(f"已更新taobao_products表中商品 {product_id} 的评论计数为0")
        except Exception as e:
            logger.error(f"清理taobao_products表评论计数时出错: {e}")
        
        cursor.close()
        conn.close()
        logger.info("评论计数清理完成")
    except Exception as e:
        logger.error(f"清理评论计数时出错: {e}")
        
# 确保应用启动时执行初始化
with app.app_context():
    on_startup()

# 添加清除数据库路由，用于前端页面中的清除数据库功能
@app.route('/clear_database', methods=['POST'])
def clear_database():
    """清空数据库中的所有数据"""
    try:
        logger.info("收到清空数据库请求")
        conn = get_db_connection()
        if not conn:
            logger.error("无法连接到数据库")
            return jsonify({
                'success': False,
                'message': '无法连接到数据库'
            })
            
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        logger.info(f"数据库中的表: {tables}")
        
        # 逐个清空相关表
        data_tables = ['taobao_data', 'goods', 'taobao_products', 'product_comments']
        cleared_tables = []
        
        for table in data_tables:
            if table in tables:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                    logger.info(f"已清空表: {table}")
                    cleared_tables.append(table)
                except Exception as e:
                    logger.error(f"清空表 {table} 失败: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if cleared_tables:
            return jsonify({
                'success': True,
                'message': f'已清空表: {", ".join(cleared_tables)}'
            })
        else:
            return jsonify({
                'success': False,
                'message': '没有找到可清空的数据表'
            })
            
    except Exception as e:
        logger.error(f"清空数据库失败: {e}")
        return jsonify({
            'success': False,
            'message': f'清空数据库失败: {str(e)}'
        })

# 评论分析 - 词云分析
@app.route('/comment_wordcloud')
@login_required
def comment_wordcloud():
    """
    评论词云分析页面 - 加载已有词云图，提高页面打开速度
    """
    try:
        # 确保static/images目录存在
        os.makedirs('static/images', exist_ok=True)
        # 直接加载已有词云图，不再每次重新生成
        word_cloud_path = 'static/images/beautifulcloud.png'
        # 如果词云图不存在，则第一次生成
        if not os.path.exists(word_cloud_path):
            from ciyun import generate_wordcloud
            generate_wordcloud()
            logger.info("词云图不存在，已生成初始词云图")
        else:
            logger.info("使用已有词云图，提高页面加载速度")
        
        return render_template('comment_wordcloud.html')
    except Exception as e:
        logger.error(f"加载词云分析页面失败: {e}")
        return render_template('comment_wordcloud.html', error=str(e))

@app.route('/generate_wordcloud', methods=['POST'])
@login_required
def generate_wordcloud_route():
    """
    生成评论词云图API
    """
    try:
        from ciyun import generate_wordcloud
        # 强制重新生成词云
        success = generate_wordcloud(force_refresh=True)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '生成词云失败，请检查是否有评论数据'})
    except Exception as e:
        logger.error(f"生成词云失败: {e}")
        return jsonify({'success': False, 'message': str(e)})

# 评论分析 - NLP情感分析
@app.route('/comment_sentiment')
@login_required
def comment_sentiment():
    """
    NLP情感分析页面
    """
    try:
        return render_template('comment_sentiment.html')
    except Exception as e:
        logger.error(f"加载情感分析页面失败: {e}")
        return render_template('comment_sentiment.html', error=str(e))

@app.route('/api/sentiment_analysis')
@login_required
def sentiment_analysis_api():
    """
    获取情感分析数据API
    """
    try:
        # 检查是否需要强制刷新
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        from nlp import analyze_sentiment
        results = analyze_sentiment(force_refresh=force_refresh)
        
        if results['success']:
            # 添加缓存信息
            cache_info = {'from_cache': results.get('from_cache', False)}
            return jsonify({**results['stats'], **cache_info})
        else:
            return jsonify({'error': results['error']}), 500
    except Exception as e:
        logger.error(f"获取情感分析数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_sentiment', methods=['POST'])
@login_required
def analyze_sentiment_route():
    """
    重新进行情感分析API
    """
    try:
        from nlp import analyze_sentiment
        # 强制刷新分析
        results = analyze_sentiment(save_csv=True, force_refresh=True)
        
        if results['success']:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': results['error']})
    except Exception as e:
        logger.error(f"情感分析失败: {e}")
        return jsonify({'success': False, 'message': str(e)})

# 评论分析 - LDA主题分析
@app.route('/comment_lda')
@login_required
def comment_lda():
    """
    LDA主题分析页面
    """
    try:
        return render_template('comment_lda.html')
    except Exception as e:
        logger.error(f"加载LDA主题分析页面失败: {e}")
        return render_template('comment_lda.html', error=str(e))

@app.route('/api/lda_topics')
@login_required
def lda_topics_api():
    """
    获取LDA主题分析数据API
    """
    try:
        # 检查是否需要强制刷新
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        from lda import analyze_lda
        results = analyze_lda(force_refresh=force_refresh)
        
        if results['success']:
            # 添加缓存信息
            cache_info = {'from_cache': results.get('from_cache', False)}
            return jsonify({
                'positive_topics': results['positive_topics'],
                'negative_topics': results['negative_topics'],
                **cache_info
            })
        else:
            return jsonify({'error': results['error']}), 500
    except Exception as e:
        logger.error(f"获取LDA主题分析数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_lda', methods=['POST'])
@login_required
def analyze_lda_route():
    """
    重新进行LDA主题分析API
    """
    try:
        from lda import analyze_lda
        # 强制刷新分析
        results = analyze_lda(save_csv=True, force_refresh=True)
        
        if results['success']:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': results['error']})
    except Exception as e:
        logger.error(f"LDA主题分析失败: {e}")
        return jsonify({'success': False, 'message': str(e)})

# 评论分析 - Bayes评论分类
@app.route('/comment_bayes')
@login_required
def comment_bayes():
    """
    Bayes评论分类页面
    """
    try:
        return render_template('comment_bayes.html')
    except Exception as e:
        logger.error(f"加载Bayes评论分类页面失败: {e}")
        return render_template('comment_bayes.html', error=str(e))

@app.route('/api/bayes_classification')
@login_required
def bayes_classification_api():
    """
    获取Bayes评论分类数据API
    """
    try:
        # 检查是否需要强制刷新
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        from bayes import get_bayes_classification
        results = get_bayes_classification(force_refresh=force_refresh)
        
        if results['success']:
            # 添加缓存信息
            cache_info = {'from_cache': results.get('from_cache', False)}
            return jsonify({
                'accuracy': results['accuracy'],
                'correct_positive': results['stats']['correct_positive'],
                'correct_negative': results['stats']['correct_negative'],
                'wrong_positive': results['stats']['wrong_positive'],
                'wrong_negative': results['stats']['wrong_negative'],
                'samples': results['samples'],
                **cache_info
            })
        else:
            return jsonify({'error': results['error']}), 500
    except Exception as e:
        logger.error(f"获取Bayes评论分类数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/train_bayes', methods=['POST'])
@login_required
def train_bayes_route():
    """
    重新训练Bayes模型API
    """
    try:
        from bayes import train_bayes_model, get_bayes_classification
        # 先训练模型
        train_results = train_bayes_model(save_model=True, save_csv=True)
        
        if train_results['success']:
            # 然后获取最新结果并强制刷新缓存
            get_bayes_classification(force_refresh=True)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': train_results['error']})
    except Exception as e:
        logger.error(f"训练Bayes模型失败: {e}")
        return jsonify({'success': False, 'message': str(e)})

# 添加用户管理相关路由
@app.route('/user_management')
@login_required
def user_management():
    """用户管理页面，仅管理员可见"""
    if session.get('role') != 'admin':
        flash('您没有访问此页面的权限', 'error')
        return redirect(url_for('index'))
        
    return render_template('user_management.html')

@app.route('/api/users')
@login_required
def get_users():
    """获取所有用户列表API，仅管理员可用"""
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': '您没有访问此API的权限'}), 403
        
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 查询所有用户，不返回密码
        cursor.execute("""
            SELECT id, username, email, role, register_time, last_login, status 
            FROM users ORDER BY id
        """)
        
        users = cursor.fetchall()
        
        # 格式化日期时间
        for user in users:
            if user['register_time']:
                user['register_time'] = user['register_time'].strftime('%Y-%m-%d %H:%M:%S')
            if user['last_login']:
                user['last_login'] = user['last_login'].strftime('%Y-%m-%d %H:%M:%S')
                
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """更新用户信息API，仅管理员可用"""
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': '您没有访问此API的权限'}), 403
        
    # 防止管理员修改自己的角色
    if user_id == session.get('user_id'):
        return jsonify({'success': False, 'message': '不能修改自己的角色'}), 400
        
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效的请求数据'}), 400
            
        # 获取要更新的字段
        role = data.get('role')
        status = data.get('status')
        
        if role not in ['admin', 'user']:
            return jsonify({'success': False, 'message': '无效的角色值'}), 400
            
        if status not in [0, 1]:
            return jsonify({'success': False, 'message': '无效的状态值'}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
        cursor = conn.cursor()
        
        # 更新用户信息
        cursor.execute("""
            UPDATE users SET role = %s, status = %s WHERE id = %s
        """, (role, status, user_id))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': '找不到指定用户'}), 404
            
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '用户信息更新成功'})
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/users/<int:user_id>/reset_password', methods=['POST'])
@login_required
def reset_user_password(user_id):
    """重置用户密码API，仅管理员可用"""
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': '您没有访问此API的权限'}), 403
        
    try:
        # 生成8位随机密码
        import random
        import string
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # 哈希密码
        import hashlib
        hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
        cursor = conn.cursor()
        
        # 更新用户密码
        cursor.execute("""
            UPDATE users SET password = %s WHERE id = %s
        """, (hashed_password, user_id))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': '找不到指定用户'}), 404
            
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '密码重置成功', 'new_password': new_password})
    except Exception as e:
        logger.error(f"重置用户密码失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# 主函数
if __name__ == '__main__':
    # 执行应用初始化操作
    with app.app_context():
        on_startup()
    
    # 显示所有已注册的API路由
    print("\n===================== 已注册的API路由 =====================")
    api_routes_count = 0
    api_routes = []
    for rule in app.url_map.iter_rules():
        if '/api/' in str(rule.rule):
            api_info = f"{rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]"
            api_routes.append(api_info)
            api_routes_count += 1
    
    # 按字母顺序排序并打印
    for route in sorted(api_routes):
        print(route)
    
    print(f"共计 {api_routes_count} 个API路由")
    print("==========================================================\n")
    
    print("="*60)
    print("                淘宝爬虫系统服务器")
    print("="*60)
    print("  * 正在启动服务器...")
    print("  * 访问地址: http://127.0.0.1:5001")
    print("  * 默认用户名: admin")
    print("  * 默认密码: admin")
    print("="*60)
    print("  * API路由已注册:")
    print("  * /api/test - 测试API连接")
    print("  * /api/comments/start - 启动评论爬取")
    print("  * /api/comments/confirm-login - 确认登录")
    print("  * /api/comments/status - 获取爬虫状态")
    print("  * /api/comments/stop - 停止爬虫")
    print("  * /api/visualization_data - 获取可视化数据")
    print("="*60)
    print("  * 运行日志将在此终端显示")
    print("  * 按 Ctrl+C 终止服务")
    print("="*60)
    
    try:
        # 确保app对象被正确创建
        app.run(debug=True, host='127.0.0.1', port=5001, threaded=True)
    except Exception as e:
        print(f"启动服务器失败: {e}")
        print("请检查端口是否被占用或者权限问题")
        print("如果端口被占用，请尝试关闭占用端口的程序，或者修改代码中的端口号")
        print("="*60)
