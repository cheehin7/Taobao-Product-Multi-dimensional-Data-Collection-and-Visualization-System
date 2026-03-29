import os
import time
import random
import json
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyquery import PyQuery as pq
import pymysql
from config import *
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
import re
from selenium.webdriver.common.keys import Keys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='crawler.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# 全局变量
driver = None
wait = None
search_keyword = None
stop_flag = False
is_waiting_login = False
current_page = 0
item_count = 0
scraper = None  # 初始化全局变量 scraper

class TaobaoScraper:
    def __init__(self, keyword, page_start=1, page_end=1):
        """初始化爬虫实例"""
        self.keyword = keyword
        self.page_start = page_start
        self.page_end = page_end
        self.driver = None
        self.is_running = False
        self.is_waiting_login = False
        self.current_page = 0
        self.item_count = 0
        self.stop_flag = False
        
        # 数据库配置
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '123456',
            'database': 'taobao_data',  # 修改为taobao_data
            'port': 3306,
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        # 初始化日志
        self.logger = logging.getLogger(__name__)
        
        # 检查MySQL服务是否运行
        if not self._check_mysql_service():
            raise Exception("MySQL服务未启动或无法连接")
            
        # 创建数据库（如果不存在）
        if not self._create_database():
            raise Exception("创建数据库失败，请检查MySQL用户权限")
            
        # 初始化数据库表
        if not self._init_database():
            raise Exception("初始化数据库表失败")
            
    def _check_mysql_service(self):
        """检查MySQL服务是否运行"""
        try:
            # 尝试连接MySQL服务器（不指定数据库）
            conn = pymysql.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                port=self.db_config['port']
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            self.logger.info(f"MySQL服务正常运行，版本: {version[0]}")
            print(f"[爬虫系统] MySQL服务正常运行，版本: {version[0]}")
                return True
                
        except pymysql.Error as e:
            error_code = e.args[0]
            if error_code == 2003:  # Can't connect to MySQL server
                self.logger.error("MySQL服务未启动")
                print("[爬虫系统] MySQL服务未启动，请先启动MySQL服务")
            elif error_code == 1045:  # Access denied
                self.logger.error("MySQL用户名或密码错误")
                print("[爬虫系统] MySQL用户名或密码错误，请检查配置")
            else:
                self.logger.error(f"连接MySQL服务失败: {e}")
                print(f"[爬虫系统] 连接MySQL服务失败: {e}")
            return False
            
    def _create_database(self):
        """创建数据库（如果不存在）"""
        try:
            # 连接MySQL服务器（不指定数据库）
            conn = pymysql.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                port=self.db_config['port']
            )
            
            cursor = conn.cursor()
            
            # 检查数据库是否存在
            cursor.execute("SHOW DATABASES LIKE %s", (self.db_config['database'],))
            if not cursor.fetchone():
                # 创建数据库
                cursor.execute(f"CREATE DATABASE {self.db_config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                self.logger.info(f"数据库 {self.db_config['database']} 创建成功")
                print(f"[爬虫系统] 数据库 {self.db_config['database']} 创建成功")
            else:
                self.logger.info(f"数据库 {self.db_config['database']} 已存在")
                print(f"[爬虫系统] 数据库 {self.db_config['database']} 已存在")
            
            conn.commit()
            cursor.close()
            conn.close()
            
                    return True
            
        except pymysql.Error as e:
            error_code = e.args[0]
            if error_code == 1044:  # Access denied
                self.logger.error("没有创建数据库的权限")
                print("[爬虫系统] 没有创建数据库的权限，请检查MySQL用户权限")
            elif error_code == 1007:  # Can't create database
                self.logger.error("数据库已存在")
                print(f"[爬虫系统] 数据库 {self.db_config['database']} 已存在")
                return True  # 数据库已存在，视为成功
            else:
                self.logger.error(f"创建数据库失败: {e}")
                print(f"[爬虫系统] 创建数据库失败: {e}")
            return False

    def _init_database(self):
        """初始化数据库表"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # 创建商品数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS taobao_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255),
                    price DECIMAL(10,2),
                    deal_count VARCHAR(50),
                    location VARCHAR(100),
                    shop_name VARCHAR(100),
                    post_text VARCHAR(10),
                    comment_total INT DEFAULT 0,
                    comment_fetched INT DEFAULT 0,
                    fetch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title_url TEXT,
                    shop_url TEXT,
                    img_url TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info("数据库表初始化成功")
            print("[爬虫系统] 数据库表初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化数据库失败: {e}")
            print(f"[爬虫系统] 初始化数据库失败: {e}")
            if 'conn' in locals() and conn:
                conn.close()
            return False

    def _backup_database(self):
        """备份数据库数据"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor(dictionary=True)
            
            # 获取所有商品数据
            cursor.execute("""
                SELECT 
                    d.*,
                    p.title_url,
                    p.shop_url,
                    p.fetch_time
                FROM data d
                LEFT JOIN product_links p ON d.id = p.product_id
            """)
            
            data = cursor.fetchall()
            
            # 保存为JSON文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(os.getcwd(), 'database_backup')
            
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            backup_file = os.path.join(backup_dir, f'taobao_data_backup_{timestamp}.json')
            
            # 处理datetime对象
            for item in data:
                for key, value in item.items():
                    if isinstance(value, datetime):
                        item[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                        
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            cursor.close()
            conn.close()
            
            self.logger.info(f"数据库备份成功: {backup_file}")
            return True
            
                        except Exception as e:
            self.logger.error(f"备份数据库失败: {e}")
            if 'conn' in locals() and conn:
                conn.close()
            return False
            
    def _restore_database(self, backup_file):
        """从备份文件恢复数据库"""
        try:
            if not os.path.exists(backup_file):
                self.logger.error(f"备份文件不存在: {backup_file}")
                return False
                
            # 读取备份文件
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            conn = self.get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # 清空现有数据
            cursor.execute("TRUNCATE TABLE product_links")
            cursor.execute("TRUNCATE TABLE data")
            
            # 恢复数据
            for item in data:
                # 插入商品数据
                cursor.execute("""
                    INSERT INTO data (
                        title, price, deal, location, shop, post_text, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    item['title'],
                    item['price'],
                    item['deal'],
                    item['location'],
                    item['shop'],
                    item['post_text'],
                    item['created_at']
                ))
                
                product_id = cursor.lastrowid
                
                # 插入链接数据
                cursor.execute("""
                    INSERT INTO product_links (
                        product_id, title_url, shop_url, img_url, fetch_time
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    product_id,
                    item['title_url'],
                    item['shop_url'],
                    item['img_url'],
                    item['fetch_time']
                ))
                
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"数据库恢复成功，共恢复 {len(data)} 条记录")
            return True
            
                        except Exception as e:
            self.logger.error(f"恢复数据库失败: {e}")
            if 'conn' in locals() and conn:
                conn.rollback()
                conn.close()
            return False
            
    def get_db_connection(self):
        """获取数据库连接"""
        try:
            conn = pymysql.connect(**self.db_config)
            self.logger.info('成功连接到数据库')
            return conn
                except Exception as e:
            self.logger.error(f'数据库连接失败: {e}')
            return None
            
    def save_to_database(self, goods_list):
        """保存商品数据到数据库"""
        if not goods_list:
            return False
            
        try:
            conn = self.get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # 直接保存到taobao_data表
            for item in goods_list:
                sql = """
                    INSERT INTO taobao_data (
                        title, price, deal_count, location, shop_name, 
                        post_text, title_url, shop_url, img_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    item.get('title', ''),
                    item.get('price', '0'),
                    item.get('deal', '0'),
                    item.get('location', ''),
                    item.get('shop', ''),
                    item.get('post_text', '否'),
                    item.get('t_url', ''),
                    item.get('shop_url', ''),
                    item.get('img_url', '')
                ))
                
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"成功保存 {len(goods_list)} 条商品数据到数据库")
                        return True
            
        except Exception as e:
            self.logger.error(f"保存数据到数据库失败: {e}")
            if conn:
                conn.close()
            return False
            
    def get_goods_from_db(self, page=1, limit=100):
        """从数据库获取商品数据"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return []
                
            cursor = conn.cursor(dictionary=True)
            
            # 构建查询 - 直接从taobao_data表获取数据
            query = """
                SELECT 
                    id, 
                    title, 
                    price, 
                    deal_count, 
                    location, 
                    shop_name, 
                    post_text,
                    comment_total,
                    comment_fetched,
                    fetch_time,
                    title_url, 
                    shop_url, 
                    img_url
                FROM taobao_data
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """
            
            offset = (page - 1) * limit
            cursor.execute(query, (limit, offset))
            goods = cursor.fetchall()
            
            # 处理日期格式
            for item in goods:
                if item['fetch_time']:
                    item['fetch_time'] = item['fetch_time'].strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.close()
            conn.close()
            
            return goods
            
        except Exception as e:
            self.logger.error(f"从数据库获取商品数据失败: {e}")
            if conn:
                conn.close()
            return []
            
    def clear_database(self):
        """清空数据库"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # 清空数据表
            cursor.execute("TRUNCATE TABLE taobao_data")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info("数据库已清空")
            return True
            
        except Exception as e:
            self.logger.error(f"清空数据库失败: {e}")
            if conn:
                conn.close()
            return False

    def _init_driver(self):
        """初始化Chrome浏览器"""
        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 设置数据库配置
            self.db_config = {
                'host': 'localhost',
                'user': 'root',
                'password': '123456',
                'database': 'taobao_data',  # 修改为taobao_data
                'port': 3306,
                'charset': 'utf8mb4',
                'cursorclass': pymysql.cursors.DictCursor
            }
            
            # 创建数据库连接
            self.conn = pymysql.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            
            # 创建数据表
            self._create_table()
            
            # 初始化ChromeDriver
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            return True
        except Exception as e:
            self.logger.error(f"初始化Chrome浏览器失败: {e}")
            return False

    def confirm_login(self):
        """确认登录状态并开始搜索"""
        try:
            if not self.is_waiting_login:
                return False
                
            # 检查登录状态
            if self.confirm_login_status():
                self.is_waiting_login = False
                print("[爬虫系统] 登录状态已确认，开始搜索商品...")
                
                # 开始搜索商品
                if self.search_goods():
                    print("[爬虫系统] 搜索成功，开始爬取数据...")
                    
                    # 开始爬取数据
                    for page in range(self.page_start, self.page_end + 1):
                        if self.stop_flag:
                            break
                            
                        print(f"[爬虫系统] 正在爬取第 {page} 页数据...")
                        
                        # 如果不是第一页，需要翻页
                        if page > 1:
                            if not self.turn_page(page):
                                print(f"[爬虫系统] 翻到第 {page} 页失败")
                                continue
                        
                        # 获取商品数据
                        if self.get_goods(page):
                            print(f"[爬虫系统] 第 {page} 页数据爬取成功")
                        else:
                            print(f"[爬虫系统] 第 {page} 页数据爬取失败")
                            
                        # 随机延时，避免被封
                        time.sleep(random.uniform(2, 5))
                        
                    print("[爬虫系统] 所有页面爬取完成")
                    return True
                else:
                    print("[爬虫系统] 搜索失败")
                    return False
            else:
                print("[爬虫系统] 未检测到登录状态，请先完成登录")
                return False
                
            except Exception as e:
            self.logger.error(f"确认登录失败: {e}")
            print(f"[爬虫系统] 确认登录失败: {e}")
            return False
            
    def get_status(self):
        """获取爬虫状态"""
        return {
            'is_running': self.is_running,
            'current_page': self.current_page,
            'item_count': self.item_count,
            'is_waiting_login': self.is_waiting_login
        }

    def start_crawl(self):
        """启动爬虫"""
        try:
            # 初始化浏览器
            self.driver = self._init_driver()
            if not self.driver:
                return False
                
            # 设置运行状态
            self.is_running = True
            self.is_waiting_login = True
            
            # 访问淘宝首页
            print("[爬虫系统] 正在打开淘宝首页...")
            self.driver.get('https://www.taobao.com')
            
            # 等待页面加载
            time.sleep(3)
            
            print("[爬虫系统] 请在浏览器中完成登录操作")
            print("[爬虫系统] 登录完成后，请点击界面上的'确认登录'按钮")
            
            return True
            
        except Exception as e:
            self.logger.error(f"启动爬虫失败: {e}")
            print(f"[爬虫系统] 启动爬虫失败: {e}")
            if self.driver:
                self.driver.quit()
                self.driver = None
            self.is_running = False
            return False
            
    def stop_crawl(self):
        """停止爬虫"""
        self.stop_flag = True
        self.is_running = False
        
    def close_browser(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
        self.is_running = False
        self.is_waiting_login = False
        self.current_page = 0
        self.item_count = 0
        self.stop_flag = False

    def search_goods(keyword):
        """在淘宝首页输入关键词并点击搜索"""
        try:
            print("正在搜索: {}".format(keyword))
            input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#q")))
            submit = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '#J_TSearchForm > div.search-button > button')
            ))
            input_box.send_keys(keyword)
            submit.click()
            time.sleep(2)
            print("搜索完成，请在浏览器中完成登录（如需），搜索结果加载后继续下一步。")
        except Exception as exc:
            print("search_goods函数错误！Error：", exc)
            
            # 等待搜索结果加载
            time.sleep(5)
            
            # 处理多标签页情况
            handles = self.driver.window_handles
            if len(handles) > 1:
                print("[爬虫系统] 检测到多个标签页，切换到搜索结果页面...")
                # 切换到最新打开的标签页（搜索结果页）
                self.driver.switch_to.window(handles[-1])
                # 等待搜索结果页面加载
                time.sleep(3)
            
            # 等待商品列表加载
            try:
                # 尝试多个可能的商品列表选择器
                selectors = [
                    "div.J_MouserOnverReq",
                    "div.item",
                    "div.product",
                    "div[data-category='auctions']"
                ]
                
                for selector in selectors:
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        print(f"[爬虫系统] 找到商品列表元素: {selector}")
                                        break
                    except:
                        continue
                
                # 模拟滚动加载
                print("[爬虫系统] 开始滚动页面加载更多商品...")
                self._scroll_page()
                
                print("[爬虫系统] 搜索结果页面加载成功")
                return True
                
                            except Exception as e:
                print(f"[爬虫系统] 等待商品列表时出错: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"搜索商品失败: {e}")
            print(f"[爬虫系统] 搜索商品失败: {e}")
            return False
            
    def _scroll_page(self):
        """模拟页面滚动以加载更多内容"""
        try:
            # 获取页面高度
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            # 计算需要滚动的次数
            scroll_times = int(total_height / viewport_height) + 1
            
            print(f"[爬虫系统] 开始滚动页面，预计滚动 {scroll_times} 次...")
            
            # 逐次滚动
            for i in range(scroll_times):
                # 计算当前滚动位置
                current_position = i * viewport_height
                
                # 执行滚动
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                
                # 等待内容加载
                time.sleep(1)
                
                # 随机暂停，模拟人工操作
                if random.random() < 0.3:  # 30%的概率暂停
                    time.sleep(random.uniform(0.5, 1.5))
                
                print(f"[爬虫系统] 已完成第 {i+1}/{scroll_times} 次滚动")
            
            # 最后滚动回顶部
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            print("[爬虫系统] 页面滚动完成")
                
                except Exception as e:
            self.logger.error(f"页面滚动失败: {e}")
            print(f"[爬虫系统] 页面滚动失败: {e}")
            
    def confirm_login_status(self):
        """确认是否已登录"""
        try:
            # 检查是否在登录页面
            current_url = self.driver.current_url
            if 'login.taobao.com' in current_url:
                print("[爬虫系统] 当前在登录页面，请完成登录")
                return False
            
            # 检查是否有登录标志
            try:
                # 尝试查找登录后才会出现的元素
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "site-nav-login-info-nick"))
                )
                print("[爬虫系统] 已检测到登录状态")
                return True
            except:
                print("[爬虫系统] 未检测到登录状态")
                return False
            
        except Exception as e:
            self.logger.error(f"检查登录状态失败: {e}")
            print(f"[爬虫系统] 检查登录状态失败: {e}")
            return False
    
    def turn_page(self, page):
        """跳转到指定页"""
        try:
            print(f"[爬虫系统] 正在跳转至第{page}页")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            
            # 查找页码输入框
            pageInput = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="search-content-leftWrap"]/div[2]/div[4]/div/div/span[3]/input'))
            )
            pageInput.clear()
            pageInput.send_keys(page)
            
            # 点击确定按钮
            admit = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="search-content-leftWrap"]/div[2]/div[4]/div/div/button[3]'))
            )
            admit.click()
            
            print(f"[爬虫系统] 已跳转至第{page}页")
            time.sleep(random.uniform(2, 4))
            return True
            
                except Exception as e:
            self.logger.error(f"翻页失败: {e}")
            print(f"[爬虫系统] 翻页失败: {e}")
            return False
            
    def get_goods(self, page):
        """获取商品数据"""
        try:
            if not self.is_running:
                return False
            
            self.current_page = page
            print(f"[爬虫系统] 正在获取第 {page} 页数据...")
            
            # 等待商品列表加载
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.content--CUnfXXxv"))
                )
                print("[爬虫系统] 搜索结果加载成功")
        except Exception as e:
                print(f"[爬虫系统] 搜索结果加载超时: {e}")
            return False
    
            # 滚动页面以加载所有内容
            self._scroll_page()
            
            # 获取商品列表
            goods_list = []
            items = self.driver.find_elements(By.CSS_SELECTOR, "div.item")
            
            if not items:
                print("[爬虫系统] 未找到商品列表，尝试其他选择器")
                # 尝试其他可能的选择器
                selectors = [
                    "div.J_MouserOnverReq",
                    "div.product",
                    "div[data-category='auctions']"
                ]
                
                for selector in selectors:
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if items:
                        print(f"[爬虫系统] 使用选择器 {selector} 找到 {len(items)} 个商品")
                    break
                
            if not items:
                print("[爬虫系统] 未找到任何商品，可能是页面结构已变化")
            return False
    
            print(f"[爬虫系统] 找到 {len(items)} 个商品")
            
            # 提取商品数据
            for index, item in enumerate(items):
                try:
                    # 获取商品标题
                    title_element = item.find_element(By.CSS_SELECTOR, "div.title a")
                    title = title_element.text.strip()
                    title_url = title_element.get_attribute("href")
                    
                    # 获取商品价格
                    try:
                        price_element = item.find_element(By.CSS_SELECTOR, "div.price strong")
                        price = price_element.text.strip()
                except:
                        price = "0.00"
                    
                    # 获取成交量
                    try:
                        deal_element = item.find_element(By.CSS_SELECTOR, "div.deal-cnt")
                        deal = deal_element.text.strip()
                    except:
                        deal = "0"
                    
                    # 获取商家位置
                    try:
                        location_element = item.find_element(By.CSS_SELECTOR, "div.location")
                        location = location_element.text.strip()
                    except:
                        location = ""
                    
                    # 获取商家名称
                    try:
                        shop_element = item.find_element(By.CSS_SELECTOR, "div.shop a")
                        shop = shop_element.text.strip()
                        shop_url = shop_element.get_attribute("href")
                    except:
                        shop = ""
                        shop_url = ""
                    
                    # 获取是否包邮
                    try:
                        post_element = item.find_element(By.CSS_SELECTOR, "div.post-fee")
                        post_text = "是" if "包邮" in post_element.text else "否"
                    except:
                        post_text = "否"
                    
                    # 获取商品图片
                    try:
                        img_element = item.find_element(By.CSS_SELECTOR, "div.pic img")
                        img_url = img_element.get_attribute("src")
                    except:
                        img_url = ""
                    
                    # 构建商品数据
                    product = {
                        'page': page,
                        'title': title,
                        'price': price,
                        'deal': deal,
                        'location': location,
                        'shop': shop,
                        'post_text': post_text,
                        't_url': self._fix_url(title_url),
                        'shop_url': self._fix_url(shop_url),
                        'img_url': self._fix_url(img_url)
                    }
                    
                    goods_list.append(product)
                    
                except Exception as e:
                    self.logger.error(f"提取商品数据失败: {e}")
                    continue
            
            if goods_list:
                # 保存到数据库
                self.save_to_database(goods_list)
                self.item_count += len(goods_list)
                print(f"[爬虫系统] 成功保存 {len(goods_list)} 条商品数据到数据库")
            return True
            else:
                print("[爬虫系统] 未找到任何商品数据")
                return False
            
        except Exception as e:
            self.logger.error(f"获取商品数据失败: {e}")
            print(f"[爬虫系统] 获取商品数据失败: {e}")
            return False
            
    def _fix_url(self, url):
        """修复URL格式"""
        if not url:
            return ""
        if url.startswith('//'):
            return 'https:' + url
        if not url.startswith('http'):
            return 'https://' + url
        return url

# 以下是全局函数，用于和Flask应用交互

def start_search(keyword, page_start=1, page_end=2):
    """开始搜索 - 只打开浏览器并导航到淘宝首页，等待用户登录"""
    global scraper, search_keyword, stop_flag, is_waiting_login, current_page
    
    try:
        print(f"\n[爬虫系统] 正在启动爬虫，关键词：{keyword}，页码范围：{page_start}-{page_end}...")
        logger.info(f"开始搜索: {keyword}，页码范围: {page_start}-{page_end}")
        
        # 重置状态
        stop_flag = False
        is_waiting_login = True
        current_page = 0
        search_keyword = keyword
        
        # 关闭现有爬虫
        if scraper is not None:
            try:
                print("[爬虫系统] 正在关闭已有的爬虫实例...")
                scraper.close_browser()
                print("[爬虫系统] 已关闭旧爬虫实例")
            except Exception as e:
                logger.error(f"关闭现有爬虫失败: {e}")
                print(f"[爬虫系统] 关闭已有爬虫实例失败: {e}")
        
        # 创建新的爬虫实例
        print("[爬虫系统] 正在创建新的爬虫实例...")
        scraper = TaobaoScraper(keyword, page_start, page_end)
        
        # 启动爬虫 - 只打开浏览器和淘宝首页
        print("[爬虫系统] 爬虫实例创建成功，准备启动浏览器...")
        if scraper.start_crawl():
            print("[爬虫系统] 爬虫启动成功，浏览器已打开")
            print("[爬虫系统] ======================================")
            print("[爬虫系统] 请在浏览器中完成淘宝登录")
            print("[爬虫系统] 登录完成后请点击界面上的'确认登录'按钮")
            print("[爬虫系统] ======================================")
            logger.info(f"爬虫启动成功: {keyword}")
            return True
        else:
            print("[爬虫系统] 爬虫启动失败，请检查日志")
            logger.error(f"爬虫启动失败: {keyword}")
            return False
        
    except Exception as e:
        logger.error(f"开始搜索失败: {e}")
        print(f"[爬虫系统] 爬虫启动过程发生错误: {e}")
        # 记录详细的错误信息
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False

def confirm_login():
    """确认登录后开始搜索并爬取 - 仅在用户点击UI上的确认登录按钮后调用"""
    global scraper, is_waiting_login
    
    try:
        if scraper is not None:
            # 设置等待登录标志
            is_waiting_login = False
            
            print("\n[爬虫系统] 用户已确认登录，准备搜索关键词并开始爬取数据...")
            logger.info("用户确认已完成登录，开始搜索并爬取数据...")
            
            # 首先搜索关键词
            if not scraper.confirm_login():
                print("[爬虫系统] 搜索关键词失败，无法开始爬取")
                logger.error("搜索关键词失败")
                return False
            
            # 然后启动爬取线程
            result = scraper.start_crawl()
            if result:
                print("[爬虫系统] 爬取任务已在后台启动，数据将自动保存到数据库")
                print("[爬虫系统] 您可以在界面上查看爬取进度，也可以随时停止爬取")
                return True
            else:
                print("[爬虫系统] 启动爬取任务失败，请检查日志")
                return False
        else:
            logger.error("爬虫实例未初始化，无法确认登录")
            print("[爬虫系统] 错误：爬虫未正确初始化，请重新开始")
        return False
        
    except Exception as e:
        logger.error(f"确认登录失败: {e}")
        print(f"[爬虫系统] 确认登录过程发生错误: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False

def stop_crawler():
    """停止爬虫"""
    global stop_flag
    
    try:
        stop_flag = True
        print("\n[爬虫系统] 正在停止爬虫...")
        logger.info("爬虫已停止")
        print("[爬虫系统] 爬虫已成功停止，已爬取的数据已保存")
        return True
        
    except Exception as e:
        logger.error(f"停止爬虫失败: {e}")
        print(f"[爬虫系统] 停止爬虫时发生错误: {e}")
        return False

def close_browser():
    """关闭浏览器"""
    global scraper
    
    try:
        if scraper is not None:
            print("\n[爬虫系统] 正在关闭浏览器...")
            scraper.close_browser()
            scraper = None
            print("[爬虫系统] 浏览器已成功关闭")
        else:
            print("[爬虫系统] 没有需要关闭的浏览器实例")
        return True
        
    except Exception as e:
        logger.error(f"关闭浏览器失败: {e}")
        print(f"[爬虫系统] 关闭浏览器时发生错误: {e}")
        return False

def get_crawler_status():
    """获取爬虫状态"""
    return {
        'is_running': scraper is not None and not stop_flag,
        'current_page': current_page,
        'item_count': item_count,
        'is_waiting_login': is_waiting_login
    } 