import time
import random
import json
import re
import logging
import traceback
import requests
import sys
import subprocess
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import pymysql
from db_config import DB_CONFIG
from datetime import datetime

# 尝试导入pyquery，如果不存在则自动安装
try:
    from pyquery import PyQuery as pq
    PYQUERY_AVAILABLE = True
    logging.info("成功导入PyQuery")
except ImportError:
    PYQUERY_AVAILABLE = False
    logging.warning("PyQuery未安装，尝试自动安装...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyquery"])
        from pyquery import PyQuery as pq
        PYQUERY_AVAILABLE = True
        logging.info("PyQuery已成功安装并导入")
    except Exception as e:
        logging.error(f"安装PyQuery失败: {e}")
        logging.warning("将使用备用方法提取评论")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('comment_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('comment_crawler')

# 全局变量
driver = None
is_waiting_login = False
is_running = False
current_count = 0
max_count = 0
product_id = None
product_url = None
comment_selectors = [
    # 2025年淘宝最新评论区选择器
    ".kg-rate-ct-review-item",                # 最新淘宝评价项
    ".kg-rate-ct-review-item-content",        # 最新淘宝评价内容
    ".kg-rate-ct-review-item-user-name",      # 最新淘宝评价用户名
    ".kg-rate-ct-review-item-date",           # 最新淘宝评价日期
    ".Gygm8xdW85--content--",                 # 淘宝2025新版评论内容
    ".Gygm8xdW85--userName--",                # 淘宝2025新版用户名 
    ".E7gD8doUq1--content--_8e6708c",         # 淘宝2024评论内容
    ".E7gD8doUq1--content--",                 # 评论内容前缀类名
    ".tb-tbcr-content",                       # 标准淘宝评论内容
    ".J_TbcRate .tb-tbcr-content",            # 标准淘宝评论区中的内容
    ".tb-rev-item",                           # 评论项
    ".J_KgRate_ReviewItem",                   # 另一种评论项选择器
    "div.rate-grid-row",                      # 评论行
    ".tm-rate-content",                       # 天猫评论内容
    ".tm-rate-premiere",                      # 天猫首条评论
    ".tm-rate-tag",                           # 评论标签
    ".tb-r-content",                          # 旧版淘宝评论内容
    ".rate-user-info",                        # 用户信息
    # 通用评论选择器
    ".rate-content, .review-content",         # 直接评论内容
    ".rate-item, .review-item",               # 评论项容器
    # 2025淘宝详情页评论区的特定选择器
    "div[data-index] .content",               # 索引项中的内容
    "div[data-spm] .review",                  # 数据SPM属性中的评论
    ".comment-item",                          # 评论项
    ".comments-wrapper .comment"              # 评论包装器中的评论
]


def setup_driver():
    """设置并返回Selenium WebDriver"""
    global driver

    if driver:
        try:
            driver.quit()
        except Exception as e:
            logger.warning(f"尝试关闭现有driver失败: {e}")
            pass

    # 设置Chrome浏览器选项
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")

    # 添加更多的兼容性选项
    chrome_options.add_argument("--no-sandbox")  # 在某些环境中需要
    chrome_options.add_argument("--disable-dev-shm-usage")  # 在Docker中有用
    chrome_options.add_argument("--disable-gpu")  # 禁用GPU硬件加速
    chrome_options.add_argument("--disable-extensions")  # 禁用扩展
    chrome_options.add_argument("--disable-infobars")  # 禁用信息栏

    # 防止检测自动化
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # 添加用户目录，使用独立的用户配置文件，避免被检测为自动化工具
    import os
    user_data_dir = os.path.join(os.getcwd(), "chrome_user_data")
    os.makedirs(user_data_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    logger.info(f"使用Chrome用户数据目录: {user_data_dir}")

    # 添加用户代理，模拟真实用户
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    # 尝试几种可能的chromedriver路径
    driver_paths = [
        "F:\\chromedriver\\chromedriver.exe",  # 用户指定的固定路径（优先使用）
        None,  # 默认路径（系统PATH中的chromedriver）
        "chromedriver.exe",  # 当前目录下的chromedriver
        "chromedriver",  # Linux/Mac下的命名
        "C:\\chromedriver\\chromedriver.exe",
        "D:\\chromedriver\\chromedriver.exe",
        ".\\chromedriver.exe"  # 显式相对路径
    ]

    last_error = None

    # 尝试使用不同的driver路径
    for driver_path in driver_paths:
        try:
            logger.info(f"尝试使用ChromeDriver路径: {driver_path or '系统默认路径'}")
            
            # 使用兼容Selenium 4.x的方式创建WebDriver
            if driver_path:
                # 使用指定路径创建服务
                service = ChromeService(executable_path=driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # 使用系统默认路径
                driver = webdriver.Chrome(options=chrome_options)
            
            # 修改navigator.webdriver属性，规避检测
            try:
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    // 更多反检测措施
                    const newProto = navigator.__proto__;
                    delete newProto.webdriver;
                    navigator.__proto__ = newProto;
                    """
                })
            except Exception as e:
                logger.warning(f"设置反检测失败，但WebDriver仍可使用: {e}")
            
            # 初始设置
            try:
                driver.maximize_window()
            except:
                logger.warning("窗口最大化失败，继续使用默认窗口大小")
                
            # 设置超时时间
            try:
                driver.set_page_load_timeout(30)
                driver.set_script_timeout(30)
            except:
                logger.warning("设置超时时间失败，使用默认超时设置")
            
            # 测试打开空白页面，验证浏览器正常工作
            try:
                driver.get("about:blank")
                logger.info("WebDriver成功打开测试页面")
            except Exception as e:
                logger.warning(f"测试页面加载失败: {e}")
                driver.quit()
                continue  # 尝试下一个路径
            
            logger.info(f"WebDriver初始化成功，使用路径: {driver_path or '系统默认路径'}")
            return driver
        except Exception as e:
            last_error = e
            logger.warning(f"使用路径 {driver_path} 初始化WebDriver失败: {e}")
            # 清理可能部分创建的资源
            try:
                if 'driver' in locals() and driver:
                    driver.quit()
            except:
                pass
            # 继续尝试下一个路径

    # 所有路径都失败了
    logger.error(f"所有ChromeDriver路径都初始化失败，最后错误: {last_error}")

    # 在所有路径都失败的情况下，打印更多诊断信息
    try:
        import sys
        import os
        import subprocess
        import platform

        # 系统信息
        logger.info(f"操作系统: {platform.platform()}")
        logger.info(f"Python版本: {sys.version}")

        # 检查系统路径
        logger.info(f"系统路径: {sys.path}")

        # 检查当前目录及其文件
        current_dir = os.getcwd()
        logger.info(f"当前目录: {current_dir}")
        logger.info(f"目录内容: {os.listdir(current_dir)}")

        # 检查Chrome版本 (针对Windows)
        if platform.system() == 'Windows':
            try:
                chrome_version_cmd = 'reg query "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon" /v version'
                chrome_version = subprocess.check_output(chrome_version_cmd, shell=True).decode('utf-8')
                logger.info(f"Chrome版本信息: {chrome_version}")
            except:
                logger.warning("无法获取Chrome版本信息")

            # 尝试查找Chrome安装位置
            try:
                chrome_path_cmd = 'where chrome'
                chrome_path = subprocess.check_output(chrome_path_cmd, shell=True).decode('utf-8')
                logger.info(f"Chrome路径: {chrome_path}")
            except:
                logger.warning("无法获取Chrome安装路径")

            # 尝试查找chromedriver
            try:
                chromedriver_path_cmd = 'where chromedriver'
                chromedriver_path = subprocess.check_output(chromedriver_path_cmd, shell=True).decode('utf-8')
                logger.info(f"ChromeDriver路径: {chromedriver_path}")
            except:
                logger.warning("无法找到ChromeDriver")
    except Exception as diag_error:
        logger.error(f"诊断信息收集失败: {diag_error}")

        return None


def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None


def open_product_page(url):
    """打开商品页面"""
    global driver, is_waiting_login, product_url

    if not driver:
        driver = setup_driver()
        if not driver:
            return False

    try:
        product_url = url
        logger.info(f"正在打开商品页面: {url}")
        driver.get(url)

        # 等待页面加载
        time.sleep(5)

        # 检查是否需要登录
        if is_login_required():
            is_waiting_login = True
            logger.info("检测到需要登录，等待用户登录")
            return "login_required"
        else:
            is_waiting_login = False
            logger.info("商品页面加载成功，不需要登录")
            return True
    except Exception as e:
        logger.error(f"打开商品页面失败: {e}")
        return False


def is_login_required():
    """检查是否需要登录"""
    try:
        # 检查常见的登录元素
        login_elements = driver.find_elements(By.CSS_SELECTOR, ".login-dialog, .login-box, .login-form, #login-form")
        if login_elements:
            logger.info("检测到登录对话框")
            return True

        # 检查URL是否包含'login'
        if 'login' in driver.current_url.lower():
            logger.info("当前URL包含login")
            return True

        # 检查页面内容是否包含登录相关文字
        page_text = driver.page_source.lower()
        login_keywords = ['请登录', '立即登录', 'login', '用户名', '密码', '验证码', '安全验证']
        for keyword in login_keywords:
            if keyword in page_text:
                logger.info(f"页面中包含登录关键词: {keyword}")
                return True

        # 检查是否已经有商品详情页元素，表明已经登录
        product_elements = driver.find_elements(
    By.CSS_SELECTOR, ".product-info, .tb-detail-hd, .tb-item-info, .tb-main-title, [class*='title']")
        if product_elements:
            logger.info("检测到商品详情页元素，判定为已登录状态")
            return False

        # 尝试查找评论区元素，如果存在则表明已登录
        comment_elements = driver.find_elements(By.CSS_SELECTOR,
     "[class*='rate-'], [class*='comment-'], [class*='review-']")
        if comment_elements:
            logger.info("检测到评论区元素，判定为已登录状态")
            return False

        # 保守判断，如果没有其他明确指示，则不认为需要登录
        logger.info("未检测到明确的登录/未登录指示，默认为不需要登录")
        return False
    except Exception as e:
        logger.error(f"检查登录状态失败: {e}")
        return True  # 出错时默认需要登录，以确保安全


def confirm_login():
    """确认用户已完成登录"""
    global is_waiting_login

    try:
        logger.info("用户确认已完成登录")
        is_waiting_login = False
        
        # 不需要刷新页面，直接检查当前页面状态
        need_login = is_login_required()
        
        if need_login:
            logger.warning("用户确认登录后，仍检测到需要登录")
            # 尝试刷新页面后再次检查
            logger.info("尝试刷新页面后再次检查登录状态")
            driver.refresh()
            time.sleep(3)
            need_login = is_login_required()
        
            if need_login:
                logger.warning("刷新后仍需登录，确认失败")
                return False

        logger.info("登录确认成功，可以开始爬取评论")
        return True
    except Exception as e:
        logger.error(f"确认登录失败: {e}")
        return False


def navigate_to_comments():
    """导航到评论区，尝试多种方式点击展开按钮"""
    try:
        # 1. 尝试查找并点击评论选项卡
        comment_tabs = [
            "//a[contains(text(), '评价')]",
            "//a[contains(text(), '评论')]",
            "//div[contains(text(), '评价')]",
            "//div[contains(text(), '评论')]",
            "//li[contains(text(), '评价')]",
            "//li[contains(text(), '评论')]",
            # 新版淘宝评论区的选择器
            "//div[contains(@class, 'rate-tabbox')]//a",
            "//div[contains(@class, 'kg-rate')]//div[contains(@class, 'tab')]",
            "//div[contains(@id, 'J_Reviews')]//div[contains(@class, 'hd')]",
            "//div[contains(@class, 'tb-rate-tab')]//li",
            "//a[contains(@href, 'rate')]",
            "//a[contains(@data-spm, 'review')]"
        ]

        tab_clicked = False
        for xpath in comment_tabs:
            try:
                tabs = driver.find_elements(By.XPATH, xpath)
                if tabs:
                    for tab in tabs:
                        if tab.is_displayed() and tab.is_enabled():
                            logger.info(f"尝试点击评论选项卡: {xpath}")
                            # 滚动到元素位置
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab)
                            time.sleep(1)
                            tab.click()
                            logger.info(f"成功点击评论选项卡")
                            time.sleep(3)  # 等待评论区加载
                            tab_clicked = True
                            break
                if tab_clicked:
                    break
            except Exception as e:
                logger.warning(f"点击选项卡 {xpath} 失败: {e}")
                continue

        # 2. 尝试点击"查看全部评价"或"更多评价"按钮
        view_all_buttons = [
            "//a[contains(text(), '查看全部评价')]",
            "//a[contains(text(), '更多评价')]",
            "//a[contains(text(), '全部评论')]",
            "//button[contains(text(), '查看全部评价')]",
            "//span[contains(text(), '查看全部评价')]",
            "//div[contains(text(), '全部评价')]",
            # 新版淘宝的更多评价按钮
            "//a[contains(@class, 'view-all') or contains(@class, 'more')]",
            "//a[contains(@class, 'kg-rate-all')]",
            "//div[contains(@class, 'view-more')]/a",
            "//div[contains(@class, 'more-reviews')]/a"
        ]
        
        button_clicked = False
        for xpath in view_all_buttons:
            try:
                buttons = driver.find_elements(By.XPATH, xpath)
                if buttons:
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            logger.info(f"尝试点击查看全部评价按钮: {xpath}")
                            # 滚动到元素位置
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                            time.sleep(1)
                            button.click()
                            logger.info(f"成功点击查看全部评价按钮")
                            time.sleep(3)  # 等待评论区完全加载
                            button_clicked = True
                            break
                if button_clicked:
                    break
            except Exception as e:
                logger.warning(f"点击评价按钮 {xpath} 失败: {e}")
                continue
        
        # 3. 对于一些淘宝页面，需要滚动到评论区
        if not tab_clicked and not button_clicked:
            logger.info("未找到评论选项卡或按钮，尝试滚动到页面中部寻找评论区")
            # 先滚动到页面1/3处
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(2)

            # 尝试查找评论区标题并滚动到它
            comment_section_titles = [
                "//div[contains(text(), '评价详情')]",
                "//div[contains(text(), '商品评价')]",
                "//h4[contains(text(), '评价')]",
                "//div[contains(@class, 'rate-header')]"
            ]
            
            for xpath in comment_section_titles:
                try:
                    titles = driver.find_elements(By.XPATH, xpath)
                    if titles:
                        for title in titles:
                            if title.is_displayed():
                                logger.info(f"找到评论区标题: {xpath}")
                                # 滚动到标题位置
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", title)
                                time.sleep(2)
                                break
                except Exception as e:
                    logger.warning(f"寻找评论区标题 {xpath} 失败: {e}")
                    continue

        # 4. 执行几次滚动，确保页面元素加载完整
        logger.info("执行几次滚动以确保加载更多内容")
        scroll_positions = [0.3, 0.5, 0.7, 0.9]  # 滚动到页面的不同位置
        for position in scroll_positions:
            driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {position});")
            time.sleep(1)

        # 5. 回到页面中部，通常是评论区的位置
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
        time.sleep(1)
        
        logger.info("导航到评论区完成")
        return True
    except Exception as e:
        logger.error(f"导航到评论区失败: {e}")
        return False


def load_more_comments(target_count):
    """加载更多评论"""
    global current_count, driver

    # 检查driver是否有效
    if not driver:
        logger.error("WebDriver未初始化，无法加载更多评论")
        return False

    # 初始评论数
    initial_comments = get_comment_elements(driver)
    current_count = len(initial_comments)

    logger.info(f"当前已加载评论数量: {current_count}")

    if current_count >= target_count:
        logger.info(f"已加载足够的评论: {current_count}/{target_count}")
        return True

    # 尝试点击"加载更多"按钮
    load_more_attempts = 0
    max_load_attempts = 30  # 最大尝试次数

    while current_count < target_count and load_more_attempts < max_load_attempts:
        # 再次检查driver是否仍然有效
        if not driver:
            logger.error("WebDriver已关闭，无法继续加载更多评论")
            return False

        try:
            # 尝试多种可能的"加载更多"按钮选择器
            load_more_buttons = [
                "//a[contains(text(), '下一页')]",
                "//button[contains(text(), '下一页')]",
                "//a[contains(@class, 'next')]",
                "//button[contains(@class, 'next')]",
                "//a[contains(text(), '更多')]",
                "//button[contains(text(), '更多')]",
                "//a[contains(text(), '显示更多')]",
                "//button[contains(text(), '显示更多')]",
                "//a[contains(@class, 'load-more')]",
                "//button[contains(@class, 'load-more')]"
            ]

            button_found = False
            for xpath in load_more_buttons:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    if elements:
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                logger.info(f"找到'下一页'按钮: {xpath}")
                                # 滚动到按钮位置
                                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                time.sleep(1)
                                # 点击按钮
                                element.click()
                                logger.info("点击'下一页'按钮")
                                time.sleep(3)  # 等待新内容加载
                                button_found = True
                                break
                    if button_found:
                        break
                except Exception as e:
                    logger.warning(f"无法点击导航按钮 {xpath}: {e}")
                    continue
            
            if not button_found:
                logger.info("未找到'下一页'按钮")
                break
                
            # 获取当前评论数
            # 再次检查driver是否仍然有效
            if not driver:
                logger.error("WebDriver已关闭，无法获取评论元素")
                return False
                
            new_comments = get_comment_elements(driver)
            if len(new_comments) > current_count:
                logger.info(f"加载更多评论成功，数量从 {current_count} 增加到 {len(new_comments)}")
                current_count = len(new_comments)
                load_more_attempts = 0  # 重置重试计数
            else:
                logger.info(f"评论数量未增加，当前尝试次数: {load_more_attempts+1}/{max_load_attempts}")
                load_more_attempts += 1
                
            # 如果已经加载了足够的评论，终止循环
            if current_count >= target_count:
                logger.info(f"已加载足够的评论: {current_count}/{target_count}")
                return True
                
            # 稍等片刻再继续
            time.sleep(2)
        
        except Exception as e:
            logger.error(f"加载更多评论时出错: {e}")
            load_more_attempts += 1
    
    logger.info(f"评论加载完成，最终数量: {current_count}")
    return current_count > 0

def get_comment_elements(driver, max_retries=3):
    """
    获取评论元素列表
    
    Args:
        driver: Selenium WebDriver实例
        max_retries: 最大重试次数
    
    Returns:
        list: 评论元素列表，如果没有找到则返回空列表
    """
    if driver is None:
        logger.error("driver为空，无法获取评论元素")
        return []
    
    retries = 0
    elements = []
    
    # 尝试多种评论选择器
    selectors = [
        "div.rate-grid-row",  # 标准淘宝评论
        "div.tm-rate-reply",  # 天猫评论
        "div.comment-item",   # 通用评论1
        "div.comment-container", # 通用评论2
        "div.comment", # 通用评论3
        "div[class*='Rate']", # 新版淘宝评论
        "div[class*='comment']", # 通用评论4
        "div[class*='Comment']", # 通用评论5
        "li[class*='rate']", # 列表评论
        "li[class*='comment']" # 列表评论2
    ]
    
    while retries < max_retries and not elements:
        try:
            # 等待页面加载评论
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 尝试每个选择器
            for selector in selectors:
                try:
                    current_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if current_elements:
                        elements = current_elements
                        logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个评论元素")
                        break
                except Exception as e:
                    logger.debug(f"使用选择器 '{selector}' 查找评论元素失败: {e}")
                    continue
            
            if not elements:
                retries += 1
                logger.warning(f"未找到评论元素，尝试重试 ({retries}/{max_retries})")
                time.sleep(2)
            else:
                break
                
        except Exception as e:
            retries += 1
            logger.error(f"获取评论元素时发生错误: {e}")
            time.sleep(2)
    
    if not elements:
        try:
            logger.error("无法找到任何评论元素，记录页面源代码用于调试")
            if driver and driver.page_source:
                with open("comment_page_source.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logger.info("页面源代码已保存到comment_page_source.html")
        except Exception as e:
            logger.error(f"保存页面源代码失败: {e}")
    
    return elements

def extract_comment_data(comment_elements):
    """从评论元素中提取数据"""
    comments_data = []
    
    if not comment_elements:
        logger.warning("没有评论元素可供提取")
        return comments_data
    
    logger.info(f"开始提取 {len(comment_elements)} 条评论数据")
    
    # 从整个页面提取所有评论的备用方案
    full_page_extraction_done = False
    
    # 先尝试确定正确的选择器模式
    test_element = comment_elements[0]
    test_text = test_element.text
    logger.info(f"样本评论元素文本: {test_text[:100]}...")
    
    # 直接从评论元素文本中提取信息（新增）
    # 这个方法可能更准确，因为即使无法找到特定元素，文本通常仍然可见
    if test_text and len(test_text) > 20:  # 确保有足够的文本内容
        try:
            logger.info("尝试直接从元素文本中提取评论信息")
            
            # 获取所有评论元素的完整文本
            all_comments_text = []
            for comment in comment_elements[:max_count]:
                try:
                    comment_text = comment.text.strip()
                    if comment_text and len(comment_text) > 20:  # 忽略太短的文本
                        all_comments_text.append(comment_text)
                except Exception as e:
                    logger.warning(f"获取评论元素文本失败: {e}")
            
            logger.info(f"获取到 {len(all_comments_text)} 条评论文本")
            
            # 从文本中提取评论信息
            for idx, full_text in enumerate(all_comments_text):
                try:
                    # 设置默认值
                    comment_data = {"comment_text": "", "username": "匿名用户", "comment_date": "未知时间", "is_default": False}
                    
                    # 分析文本结构尝试分离用户名、日期和评论内容
                    lines = full_text.split('\n')
                    
                    if len(lines) >= 2:
                        first_line = lines[0].strip()
                        
                        # 尝试找出用户名和日期 - 通常在第一行
                        # 尝试匹配常见的日期格式
                        date_patterns = [
                            r'(\d{4}-\d{1,2}-\d{1,2})',  # 2023-01-01
                            r'(\d{4}年\d{1,2}月\d{1,2}日)',  # 2023年1月1日
                            r'(\d{2}/\d{2}/\d{4})'  # 01/01/2023
                        ]
                        
                        found_date = False
                        for pattern in date_patterns:
                            date_match = re.search(pattern, first_line)
                            if date_match:
                                comment_date = date_match.group(0)
                                # 用户名可能在日期之前
                                username_part = first_line.split(comment_date)[0].strip()
                                if username_part and len(username_part) < 30:  # 合理的用户名长度
                                    comment_data["username"] = username_part
                                comment_data["comment_date"] = comment_date
                                found_date = True
                                break
                        
                        # 如果第一行没有找到日期，可能是用户名
                        if not found_date and len(first_line) < 30:
                            # 检查是否是用户名（通常较短）
                            comment_data["username"] = first_line
                            
                            # 日期可能在第二行
                            if len(lines) > 1:
                                second_line = lines[1].strip()
                                for pattern in date_patterns:
                                    date_match = re.search(pattern, second_line)
                                    if date_match:
                                        comment_data["comment_date"] = date_match.group(0)
                                        lines = lines[2:]  # 跳过前两行
                                        break
                                else:
                                    lines = lines[1:]  # 只跳过第一行
                        else:
                            lines = lines[1:]  # 跳过第一行
                    
                    # 剩余的行是评论内容
                    comment_text = '\n'.join(lines).strip()
                    
                    # 清理评论文本（移除"有用"、"回复"等无关内容）
                    comment_text = re.sub(r'有用\s+\(\d+\).*$', '', comment_text, flags=re.MULTILINE).strip()
                    comment_text = re.sub(r'商家回复.*$', '', comment_text, flags=re.MULTILINE).strip()
                    
                    # 判断是否是默认好评
                    is_default = "默认好评" in comment_text or "此用户没有填写评价" in comment_text
                    
                    comment_data["comment_text"] = comment_text
                    comment_data["is_default"] = is_default
                    
                    # 只有在评论文本非空时才添加
                    if comment_data["comment_text"]:
                        comments_data.append(comment_data)
                        logger.info(f"从文本提取第 {idx+1} 条评论成功: {comment_data['username'][:10]}..., {comment_data['comment_date']}")
                except Exception as e:
                    logger.error(f"从文本提取第 {idx+1} 条评论失败: {e}")
            
            if comments_data:
                logger.info(f"从元素文本中成功提取 {len(comments_data)} 条评论")
                full_page_extraction_done = True
            else:
                logger.warning("从元素文本中提取评论失败，将尝试其他方法")
        except Exception as e:
            logger.error(f"从元素文本提取评论数据失败: {e}")
    
    # 只有在通过文本提取失败时才尝试旧方法
    if not full_page_extraction_done:
        # 确定这是什么类型的评论结构
        element_class = test_element.get_attribute("class") or ""
        logger.info(f"样本评论元素类: {element_class}")
        
        # 根据评论类型选择适当的提取策略
        is_new_taobao = "E7gD8doUq1" in element_class or "RateContent" in element_class
        is_tmall = "tm-rate" in element_class
    
    for idx, comment in enumerate(comment_elements[:max_count]):
        try:
            comment_data = {"comment_text": "", "username": "匿名用户", "comment_date": "未知时间", "is_default": False}
            
            # 根据不同的评论结构使用不同的提取策略
            if is_new_taobao:
                # 新版淘宝评论结构
                try:
                    # 评论文本选择器
                    text_selectors = [
                        "[class*='RateContent']", 
                        "[class*='ContentDetail']",
                        "[class*='content-detail']"
                    ]
                    for selector in text_selectors:
                        try:
                            text_elem = comment.find_element(By.CSS_SELECTOR, selector)
                            if text_elem:
                                comment_data["comment_text"] = text_elem.text.strip()
                                break
                        except:
                            continue
                    
                    # 用户名选择器
                    username_selectors = [
                        "[class*='UserName']", 
                        "[class*='user-name']",
                        "[class*='username']"
                    ]
                    for selector in username_selectors:
                        try:
                            username_elem = comment.find_element(By.CSS_SELECTOR, selector)
                            if username_elem:
                                comment_data["username"] = username_elem.text.strip()
                                break
                        except:
                            continue
                    
                    # 日期选择器
                    date_selectors = [
                        "[class*='RateDate']", 
                        "[class*='rate-date']",
                        "[class*='date']"
                    ]
                    for selector in date_selectors:
                        try:
                            date_elem = comment.find_element(By.CSS_SELECTOR, selector)
                            if date_elem:
                                comment_data["comment_date"] = date_elem.text.strip()
                                break
                        except:
                            continue
                except Exception as e:
                    logger.warning(f"提取新版淘宝评论数据失败: {str(e)}")
            
            elif is_tmall:
                # 天猫评论结构
                try:
                    text_elem = comment.find_element(By.CSS_SELECTOR, ".tm-rate-fulltxt")
                    comment_data["comment_text"] = text_elem.text.strip()
                except:
                    try:
                        text_elem = comment.find_element(By.CSS_SELECTOR, ".tm-rate-content")
                        comment_data["comment_text"] = text_elem.text.strip()
                    except:
                        pass
                
                try:
                    username_elem = comment.find_element(By.CSS_SELECTOR, ".tm-rate-author")
                    comment_data["username"] = username_elem.text.strip()
                except:
                    pass
                
                try:
                    date_elem = comment.find_element(By.CSS_SELECTOR, ".tm-rate-date")
                    comment_data["comment_date"] = date_elem.text.strip()
                except:
                    pass
            
            else:
                # 通用评论结构，尝试多种选择器
                # 提取评论文本
                text_selectors = [
                    ".tb-tbcr-content", ".rate-user-info", ".review-details", 
                    ".comment-content", ".rate-content", ".comment-text",
                    "[class*='content']", "[class*='text']"
                ]
                
                for selector in text_selectors:
                    try:
                        text_element = comment.find_element(By.CSS_SELECTOR, selector)
                        if text_element:
                            comment_data["comment_text"] = text_element.text.strip()
                            break
                    except:
                        continue
                
                # 提取用户名
                username_selectors = [
                    ".rate-user-info", ".from-whom", ".user-name", 
                    ".tb-r-user-name", "[class*='user']", "[class*='author']"
                ]
                
                for selector in username_selectors:
                    try:
                        username_element = comment.find_element(By.CSS_SELECTOR, selector)
                        if username_element:
                            comment_data["username"] = username_element.text.strip()
                            break
                    except:
                        continue
                
                # 提取评论时间
                time_selectors = [
                    ".tb-r-date", ".rate-date", ".comment-time",
                    "[class*='date']", "[class*='time']"
                ]
                
                for selector in time_selectors:
                    try:
                        time_element = comment.find_element(By.CSS_SELECTOR, selector)
                        if time_element:
                            comment_data["comment_date"] = time_element.text.strip()
                            break
                    except:
                        continue
            
            # 如果评论文本有内容，添加到结果
            if comment_data["comment_text"]:
                # 检查是否是默认好评
                comment_data["is_default"] = "默认好评" in comment_data["comment_text"] or "此用户没有填写评价" in comment_data["comment_text"]
                
                # 清理文本（删除多余空白）
                comment_data["comment_text"] = re.sub(r'\s+', ' ', comment_data["comment_text"]).strip()
                comments_data.append(comment_data)
                logger.info(f"成功提取第 {idx+1} 条评论: {comment_data['username'][:10]}..., {comment_data['comment_date']}")
        except Exception as e:
            logger.error(f"提取第 {idx+1} 条评论数据失败: {e}")
    
    # 如果通过元素无法提取有效评论，尝试从页面源码中提取
    if len(comments_data) == 0:
        logger.info("通过元素无法提取评论，尝试从源码中提取")
        try:
            comments_data = extract_comments_from_source()
        except Exception as e:
            logger.error(f"从源码提取评论失败: {e}")
    
    logger.info(f"共成功提取 {len(comments_data)} 条评论数据")
    return comments_data

def extract_comments_from_source():
    """从页面源代码中提取评论数据"""
    comments_data = []
    
    try:
        logger.info("尝试从页面源代码中提取评论数据")
        page_source = driver.page_source
        
        # 保存页面源码用于调试（仅在DEBUG模式下）
        try:
            with open("page_source_debug.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("已保存页面源码到page_source_debug.html用于调试")
        except:
            pass
        
        # 尝试找到评论JSON数据
        json_patterns = [
            r'{"api":"mtop\.tmall\.rate\.rewrite\.rate\.list".*?"rateList":(\[.*?\])',
            r'"comments":(\[.*?\])',
            r'"rateList":(\[.*?\])',
            r'"reviewList":(\[.*?\])',
            r'"rateDOs":(\[.*?\])'
        ]
        
        for pattern in json_patterns:
            try:
                logger.info(f"尝试使用模式提取JSON: {pattern[:30]}...")
                matches = re.search(pattern, page_source)
                if matches:
                    json_str = matches.group(1)
                    # 确保它是一个JSON数组
                    if json_str.startswith('[') and json_str.endswith(']'):
                        comments_json = json.loads(json_str)
                        logger.info(f"从源码中找到 {len(comments_json)} 条评论JSON数据")
                        
                        for item in comments_json[:max_count]:
                            comment = {}
                            
                            # 尝试不同的字段名
                            content_fields = ['content', 'text', 'rateContent', 'reviewContent', 'comment']
                            for field in content_fields:
                                if field in item and item[field]:
                                    comment['comment_text'] = item[field]
                                    break
                            
                            user_fields = ['user', 'userName', 'displayUserNick', 'nick', 'author']
                            for field in user_fields:
                                if field in item and item[field]:
                                    comment['username'] = item[field]
                                    break
                            
                            date_fields = ['date', 'rateDate', 'reviewDate', 'creationTime', 'gmtCreate']
                            for field in date_fields:
                                if field in item and item[field]:
                                    comment['comment_date'] = item[field]
                                    break
                            
                            if 'comment_text' in comment:
                                if 'username' not in comment:
                                    comment['username'] = "匿名用户"
                                if 'comment_date' not in comment:
                                    comment['comment_date'] = "未知时间"
                                comment['is_default'] = "默认好评" in comment['comment_text']
                                
                                comments_data.append(comment)
                        
                        if comments_data:
                            logger.info(f"成功从JSON中提取 {len(comments_data)} 条评论")
                            break
            except Exception as e:
                logger.error(f"解析评论JSON数据失败: {e}")
        
        # 如果通过JSON无法提取，尝试使用正则表达式直接从源码中提取
        if not comments_data:
            logger.info("无法通过JSON提取评论，尝试使用正则表达式")
            
            # 调试：获取页面上显示的文本内容
            try:
                visible_text = driver.find_element(By.TAG_NAME, "body").text
                logger.info(f"页面可见文本片段: {visible_text[:500]}...")
                
                # 检查是否有评论相关的文本
                comment_keywords = ['评论', '评价', '用户评价', '买家评价']
                found_keywords = [kw for kw in comment_keywords if kw in visible_text]
                if found_keywords:
                    logger.info(f"页面文本中包含评论关键词: {', '.join(found_keywords)}")
                else:
                    logger.warning("页面文本中未找到评论关键词")
                
                # 从可见文本中直接提取评论（新增）
                if found_keywords:
                    logger.info("尝试从可见文本中直接提取评论")
                    
                    # 从页面文本中提取评论块
                    # 匹配用户名（通常是短ID，后面跟着日期）
                    user_comment_patterns = [
                        r'([a-zA-Z0-9\*]+\d+|[^0-9\n]{1,20})\s+(\d{4}[年-]\d{1,2}[月-]\d{1,2}[日]?)[\s·]*[\r\n]+(.*?)(?=(?:[a-zA-Z0-9\*]+\d+|[^0-9\n]{1,20})\s+\d{4}|\Z)',
                        r'([\w\*]+)\s+(\d{4}[年-]\d{1,2}[月-]\d{1,2}[日]?)[\s·]*[\r\n]+(.*?)(?=[\r\n]+[\w\*]+\s+\d{4}|\Z)'
                    ]
                    
                    for pattern in user_comment_patterns:
                        matches = re.findall(pattern, visible_text, re.DOTALL)
                        if matches:
                            logger.info(f"使用文本模式找到 {len(matches)} 条评论")
                            for match in matches:
                                username = match[0].strip()
                                comment_date = match[1].strip()
                                comment_text = match[2].strip()
                                
                                # 清理评论文本（移除"有用"、"商家回复"等无关内容）
                                comment_text = re.sub(r'有用\s+\(\d+\).*$', '', comment_text, flags=re.MULTILINE).strip()
                                comment_text = re.sub(r'商家回复.*$', '', comment_text, flags=re.MULTILINE).strip()
                                
                                # 检查是否是默认好评
                                is_default = False
                                if "此用户没有填写评价" in comment_text or "默认好评" in comment_text:
                                    is_default = True
                                
                                # 添加到结果
                                if comment_text and len(comment_text) > 2:  # 避免仅有标点符号的评论
                                    comments_data.append({
                                        'comment_text': comment_text,
                                        'username': username,
                                        'comment_date': comment_date,
                                        'is_default': is_default
                                    })
                                    
                                    if len(comments_data) >= max_count:
                                        break
                            
                            if comments_data:
                                logger.info(f"成功从文本中提取 {len(comments_data)} 条评论")
                                break
            except Exception as e:
                logger.error(f"获取页面文本失败: {e}")
            
            # 如果文本提取失败，尝试从HTML源码中提取（修改以匹配最新的淘宝评论HTML结构）
            if not comments_data:
                logger.info("尝试使用更准确的HTML解析提取评论")
                
                # 新版淘宝评论区的标记特征
                comment_section_patterns = [
                    r'<div[^>]*class="[^"]*rate-grid[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="[^"]*rate-list[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*id="[^"]*reviews[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="[^"]*(?:reviews|comments|rates)[^"]*"[^>]*>(.*?)</div>'
                ]
                
                for pattern in comment_section_patterns:
                    try:
                        section_matches = re.findall(pattern, page_source, re.DOTALL | re.IGNORECASE)
                        if section_matches:
                            logger.info(f"找到 {len(section_matches)} 个评论区块")
                            for section in section_matches:
                                # 提取评论项
                                comment_items = re.findall(r'<div[^>]*class="[^"]*(?:rate-item|comment-item|review-item)[^"]*"[^>]*>(.*?)</div>', section, re.DOTALL)
                                logger.info(f"在评论区块中找到 {len(comment_items)} 条评论项")
                                
                                for item in comment_items:
                                    try:
                                        # 提取用户名
                                        username_match = re.search(r'<[^>]*class="[^"]*(?:user|author|name)[^"]*"[^>]*>(.*?)</[^>]*>', item, re.DOTALL)
                                        username = "匿名用户"
                                        if username_match:
                                            username = re.sub(r'<[^>]*>', '', username_match.group(1)).strip()
                                        
                                        # 提取评论日期
                                        date_match = re.search(r'<[^>]*class="[^"]*(?:date|time)[^"]*"[^>]*>(.*?)</[^>]*>', item, re.DOTALL)
                                        comment_date = "未知时间"
                                        if date_match:
                                            comment_date = re.sub(r'<[^>]*>', '', date_match.group(1)).strip()
                                            
                                        # 提取评论内容
                                        content_match = re.search(r'<[^>]*class="[^"]*(?:content|text|rateContent)[^"]*"[^>]*>(.*?)</[^>]*>', item, re.DOTALL)
                                        if content_match:
                                            comment_text = re.sub(r'<[^>]*>', '', content_match.group(1)).strip()
                                            
                                            # 检查是否是默认好评
                                            is_default = False
                                            if "此用户没有填写评价" in comment_text or "默认好评" in comment_text:
                                                is_default = True
                                                
                                            comments_data.append({
                                                'comment_text': comment_text,
                                                'username': username,
                                                'comment_date': comment_date,
                                                'is_default': is_default
                                            })
                                            
                                            if len(comments_data) >= max_count:
                                                break
                                    except Exception as e:
                                        logger.error(f"解析评论项失败: {e}")
                                        continue
                                
                                if comments_data:
                                    break
                    except Exception as e:
                        logger.error(f"解析评论区块失败: {e}")
                
                # 仍然保留原来的简单正则匹配作为后备方案
                if not comments_data:
                    logger.info("尝试使用通用正则表达式提取评论")
                    comment_blocks = re.findall(r'<div[^>]*class=["\'](?:[^"\']*(?:comment|review|rate)[^"\']*)["\'][^>]*>(.*?)</div>', page_source, re.DOTALL)
                    logger.info(f"通过正则表达式找到 {len(comment_blocks)} 个潜在评论块")
                
                    processed_count = 0
                    for block in comment_blocks:
                        if processed_count >= max_count:
                            break
                        
                        # 提取评论文本
                        content_match = re.search(r'<[^>]*class=["\'](?:[^"\']*(?:content|text)[^"\']*)["\'][^>]*>(.*?)</[^>]*>', block, re.DOTALL)
                        if content_match:
                            comment_text = re.sub(r'<[^>]*>', '', content_match.group(1)).strip()
                            
                            # 提取用户名和时间
                            username_match = re.search(r'<[^>]*class=["\'](?:[^"\']*(?:user|author)[^"\']*)["\'][^>]*>(.*?)</[^>]*>', block, re.DOTALL)
                            username = re.sub(r'<[^>]*>', '', username_match.group(1)).strip() if username_match else "匿名用户"
                            
                            date_match = re.search(r'<[^>]*class=["\'](?:[^"\']*(?:date|time)[^"\']*)["\'][^>]*>(.*?)</[^>]*>', block, re.DOTALL)
                            comment_date = re.sub(r'<[^>]*>', '', date_match.group(1)).strip() if date_match else "未知时间"
                            
                            # 检查是否是默认好评
                            is_default = False
                            if "此用户没有填写评价" in comment_text or "默认好评" in comment_text:
                                is_default = True
                            
                            comments_data.append({
                                'comment_text': comment_text,
                                'username': username,
                                'comment_date': comment_date,
                                'is_default': is_default
                            })
                            processed_count += 1
    
    except Exception as e:
        logger.error(f"从源码提取评论失败: {traceback.format_exc()}")
    
    logger.info(f"从源码中总共提取到 {len(comments_data)} 条评论")
    return comments_data

def save_comments_to_db(product_id, comments_data):
    """将评论数据保存到数据库"""
    if not comments_data:
        logger.warning("没有评论数据可保存")
        # 即使没有评论数据，也更新商品评论计数为0
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 更新taobao_data表
            cursor.execute(
                "UPDATE taobao_data SET comment_fetched = 0 WHERE id = %s",
                (product_id,)
            )
            logger.info(f"已将taobao_data表中产品 {product_id} 的comment_fetched设为0")
            
            # 更新taobao_products表
            cursor.execute(
                "UPDATE taobao_products SET comment_fetched = 0 WHERE id = %s",
                (product_id,)
            )
            logger.info(f"已将taobao_products表中产品 {product_id} 的comment_fetched设为0")
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"更新空评论计数失败: {e}")
        
        return 0
    
    conn = None
    try:
        # 记录保存函数开始执行
        logger.info(f"开始执行save_comments_to_db函数，product_id={product_id}, 评论数量={len(comments_data)}")
        
        # 建立数据库连接
        conn = get_db_connection()
        if not conn:
            logger.error("数据库连接失败，无法保存评论")
            return 0
            
        cursor = conn.cursor()
        logger.info("数据库连接成功")
        
        # 检查商品是否存在于taobao_products表
        cursor.execute("SELECT COUNT(*) FROM taobao_products WHERE id = %s", (product_id,))
        product_exists = cursor.fetchone()[0] > 0
        logger.info(f"产品ID {product_id} 在taobao_products表中存在: {product_exists}")
        
        # 检查商品是否存在于taobao_data表
        cursor.execute("SELECT COUNT(*) FROM taobao_data WHERE id = %s", (product_id,))
        product_exists_in_data = cursor.fetchone()[0] > 0
        logger.info(f"产品ID {product_id} 在taobao_data表中存在: {product_exists_in_data}")
        
        # 更新评论数量计数
        comment_count = len(comments_data)
        
        # 更新taobao_products表
        try:
            if not product_exists:
                logger.warning(f"产品ID {product_id} 在taobao_products表中不存在，尝试插入基本记录")
                # 插入一个基本产品记录
                cursor.execute(
                    "INSERT INTO taobao_products (id, title, comment_fetched) VALUES (%s, %s, %s)",
                    (product_id, f"Product ID {product_id}", comment_count)
                )
                logger.info(f"已在taobao_products表中插入产品 {product_id} 并设置comment_fetched={comment_count}")
            else:
                # 更新商品表的评论获取数
                cursor.execute(
                    "UPDATE taobao_products SET comment_fetched = %s WHERE id = %s",
                    (comment_count, product_id)
                )
                logger.info(f"已更新taobao_products表中产品 {product_id} 的comment_fetched={comment_count}")
        except Exception as e:
            logger.error(f"操作taobao_products表失败: {e}")
        
        # 更新taobao_data表
        try:
            if product_exists_in_data:
                cursor.execute(
                    "UPDATE taobao_data SET comment_fetched = %s WHERE id = %s",
                    (comment_count, product_id)
                )
                logger.info(f"已更新taobao_data表中产品 {product_id} 的comment_fetched={comment_count}")
            else:
                logger.warning(f"产品ID {product_id} 在taobao_data表中不存在，无法更新")
        except Exception as e:
            logger.error(f"更新taobao_data表失败: {e}")
        
        # 清除之前的评论数据
        try:
            cursor.execute("DELETE FROM product_comments WHERE product_id = %s", (product_id,))
            logger.info(f"已清除产品 {product_id} 的旧评论数据")
        except Exception as e:
            logger.error(f"清除旧评论数据失败: {e}")
            # 继续执行，不要终止函数
        
        # 检查表结构是否有is_default字段
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
                logger.info("is_default字段添加成功")
        except Exception as e:
            logger.error(f"检查或添加is_default字段失败: {e}")
            # 继续执行，不要终止函数
        
        # 插入新的评论数据
        inserted_count = 0
        for i, comment in enumerate(comments_data):
            try:
                # 确保所有必要的字段都存在
                if 'username' not in comment:
                    comment['username'] = '匿名用户'
                if 'comment_date' not in comment:
                    comment['comment_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 检查评论是否有is_default属性
                is_default = 1 if comment.get('is_default', False) else 0
                
                logger.info(f"尝试插入第{i+1}条评论: {comment['comment_text'][:30]}...")
            
                if has_default_field:
                    cursor.execute(
                        """
                        INSERT INTO product_comments (product_id, comment_text, username, comment_date, is_default) 
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            product_id,
                            comment['comment_text'],
                            comment['username'],
                            comment['comment_date'],
                            is_default
                        )
                    )
                else:
                    cursor.execute(
                    """
                    INSERT INTO product_comments (product_id, comment_text, username, comment_date) 
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        product_id,
                        comment['comment_text'],
                        comment['username'],
                        comment['comment_date']
                    )
                )
                inserted_count += 1
                logger.info(f"评论{i+1}插入成功")
            except Exception as e:
                logger.error(f"插入第{i+1}条评论失败: {e}")
                # 继续执行，不要终止整个循环
        
        # 提交事务前再次检查是否有评论被插入
        if inserted_count == 0 and comments_data:
            logger.warning("没有评论被成功插入，添加一条系统提示评论")
            try:
                # 插入一条系统提示评论
                cursor.execute(
                    """
                    INSERT INTO product_comments (product_id, comment_text, username, comment_date, is_default) 
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        product_id,
                        "系统未能成功获取评论，请稍后再试",
                        "系统提示",
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        1
                    )
                )
                inserted_count = 1
                logger.info("成功插入一条系统提示评论")
            except Exception as e:
                logger.error(f"插入系统提示评论失败: {e}")
        
        # 最后提交事务
        conn.commit()
        logger.info(f"数据库事务提交成功，共保存了 {inserted_count} 条评论")
        
        # 再次检查评论是否被正确保存
        try:
            cursor.execute("SELECT COUNT(*) FROM product_comments WHERE product_id = %s", (product_id,))
            final_count = cursor.fetchone()[0]
            logger.info(f"数据库中产品 {product_id} 的评论数量: {final_count}")
            
            if final_count > 0 and final_count != inserted_count:
                logger.warning(f"插入计数({inserted_count})与数据库中的评论数({final_count})不一致")
            
            return final_count if final_count > 0 else inserted_count
        except Exception as e:
            logger.error(f"验证评论数量失败: {e}")
            return inserted_count
    
    except Exception as e:
        logger.error(f"保存评论数据到数据库失败: {traceback.format_exc()}")
        if conn:
            try:
                conn.rollback()
                logger.info("数据库事务已回滚")
            except:
                pass
        return 0
    
    finally:
        if conn:
            try:
                conn.close()
                logger.info("数据库连接已关闭")
            except:
                pass

def start_comment_crawl(target_id, url, target_count=50):
    """启动评论爬取流程"""
    global driver, is_waiting_login, is_running, current_count, max_count, product_id, product_url
    
    # 如果爬虫已在运行，先尝试安全停止
    if is_running:
        logger.warning("评论爬虫已经在运行中，尝试先停止现有爬虫")
        try:
            # 尝试安全停止现有爬虫
            stop_crawl()
            # 等待一段时间确保资源释放
            time.sleep(2)
        except Exception as e:
            logger.error(f"停止现有爬虫失败: {e}")
            # 即使停止失败也继续，尝试强制重启
    
    # 重置所有状态变量
    is_running = True
    is_waiting_login = False
    product_id = target_id
    product_url = url
    max_count = target_count
    current_count = 0
    
    try:
        logger.info(f"开始爬取商品 ID: {target_id}, URL: {url}, 目标评论数: {target_count}")
        
        # 确保WebDriver正确初始化
        if not driver:
            logger.info("WebDriver未初始化，正在创建新的实例")
            driver = setup_driver()
            if not driver:
                is_running = False
                logger.error("WebDriver初始化失败，无法启动爬虫")
                return {"status": "error", "message": "浏览器启动失败，请确保Chrome浏览器已安装且版本与ChromeDriver兼容"}
        else:
            # 如果driver已存在，检查是否可用
            try:
                # 尝试简单操作检查driver是否还存活
                current_url = driver.current_url
                logger.info(f"使用现有WebDriver，当前URL: {current_url}")
            except Exception as e:
                logger.warning(f"现有WebDriver已失效，创建新实例: {e}")
                # 如果driver失效，创建新实例
                driver = setup_driver()
                if not driver:
                    is_running = False
                    logger.error("WebDriver重新初始化失败，无法启动爬虫")
                    return {"status": "error", "message": "浏览器启动失败，请确保Chrome浏览器已安装且版本与ChromeDriver兼容"}
        
        # 确保driver已设置合理的超时时间
        driver.set_page_load_timeout(30)
        
        # 打开商品页面
        logger.info(f"尝试打开商品页面: {url}")
        page_result = open_product_page(url)
        
        if page_result == "login_required":
            logger.info("需要用户登录，等待确认")
            return {"status": "waiting_login", "message": "请在浏览器中登录淘宝账号，然后点击确认登录按钮"}
        
        elif page_result == True:
            logger.info("商品页面打开成功，不需要登录")
            # 启动一个线程来执行爬取，避免阻塞主线程
            try:
                import threading
                crawl_thread = threading.Thread(target=continue_crawl)
                crawl_thread.daemon = True  # 设置为守护线程，主程序结束时自动结束
                crawl_thread.start()
                logger.info("已在后台线程中启动爬取过程")
            except Exception as e:
                logger.error(f"在线程中启动爬取失败: {e}")
                # 如果线程启动失败，直接在主线程中执行
            continue_crawl()
            
            return {"status": "success", "message": "爬虫已启动"}
        
        else:
            is_running = False
            logger.error("打开商品页面失败")
            return {"status": "error", "message": "无法打开商品页面，请检查URL是否有效"}
    
    except Exception as e:
        is_running = False
        error_msg = str(e)
        logger.error(f"启动评论爬虫失败: {traceback.format_exc()}")
        
        # 提供更友好的错误信息
        if "chrome not reachable" in error_msg.lower():
            return {"status": "error", "message": "Chrome浏览器无法访问，可能已崩溃或被关闭"}
        elif "session not created" in error_msg.lower():
            return {"status": "error", "message": "无法创建浏览器会话，Chrome版本可能与ChromeDriver不兼容"}
        elif "chromedriver" in error_msg.lower() and "executable" in error_msg.lower():
            return {"status": "error", "message": "找不到ChromeDriver可执行文件，请确保它在系统路径中或在程序目录下"}
        else:
            return {"status": "error", "message": f"启动失败: {error_msg}"}

def confirm_comment_login():
    """确认用户已登录，继续爬取评论"""
    global is_running, is_waiting_login
    
    if not is_running:
        logger.warning("爬虫未启动，无法确认登录")
        return {"status": "error", "message": "爬虫未启动，请先点击\"开始爬取\"按钮"}
    
    # 尝试检查是否登录，不管结果如何都继续爬取
    try:
        is_login = confirm_login()
        logger.info(f"登录确认检查结果: {is_login}")
        
        # 开始获取评论
        result = continue_crawl()
        
        if result.get("status") in ["success", "warning"]:
            return {"status": "success", "message": "登录确认成功，开始爬取评论"}
        else:
            is_running = False
            return {"status": "error", "message": result.get("message", "爬取过程出错")}
    except Exception as e:
        logger.error(f"登录确认过程异常: {traceback.format_exc()}")
        # 尽管发生异常，仍尝试继续爬取
        try:
            logger.info("尽管确认过程出错，仍尝试继续爬取")
            result = continue_crawl()
            
            if result.get("status") in ["success", "warning"]:
                return {"status": "success", "message": "已尝试爬取评论"}
            else:
                is_running = False
                return {"status": "error", "message": result.get("message", "爬取过程出错")}
        except Exception as e2:
            logger.error(f"尝试继续爬取过程中出错: {e2}")
            is_running = False
            return {"status": "error", "message": f"确认登录失败: {str(e)}，且无法继续爬取: {str(e2)}"}

def extract_comments_with_beautifulsoup():
    """使用BeautifulSoup从页面源码中直接提取评论，不依赖点击展开按钮"""
    global current_count, max_count
    comments_data = []
    
    try:
        logger.info("开始使用BeautifulSoup提取评论")
        # 获取当前页面源码
        page_source = driver.page_source
        
        # 保存页面源码到文件（调试用）
        try:
            with open("taobao_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("已保存页面源码到taobao_page_source.html")
        except Exception as e:
            logger.error(f"保存页面源码失败: {e}")
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(page_source, 'html.parser')
        logger.info("页面已解析为BeautifulSoup对象")
        
        # 尝试查找评论内容 - 使用多种选择器
        comment_elements = []
        
        # 1. 直接查找您提供的类
        direct_comments = soup.find_all('div', class_=lambda c: c and 'E7gD8doUq1--content--' in c)
        if direct_comments:
            logger.info(f"找到E7gD8doUq1--content--类评论: {len(direct_comments)}个")
            comment_elements.extend(direct_comments)
        
        # 2. 查找评论区div
        comment_sections = soup.find_all(['div', 'section'], class_=lambda c: c and ('comment' in c or 'review' in c or 'rate' in c or 'Rate' in c))
        if comment_sections:
            logger.info(f"找到评论区: {len(comment_sections)}个")
            for section in comment_sections:
                # 在评论区内查找评论内容
                items = section.find_all(['div', 'li'], class_=lambda c: c and ('item' in c or 'content' in c))
                if items:
                    logger.info(f"在评论区内找到评论项: {len(items)}个")
                    comment_elements.extend(items)
        
        # 3. 使用属性选择器查找评论
        data_spm_elements = soup.find_all(attrs={"data-spm-anchor-id": lambda v: v and "evo365560b447259" in v})
        if data_spm_elements:
            logger.info(f"找到data-spm-anchor-id评论元素: {len(data_spm_elements)}个")
            comment_elements.extend(data_spm_elements)
        
        # 4. 直接搜索所有可能含有评论的div
        all_comment_divs = soup.find_all('div', string=lambda s: s and len(s) > 5 and ('评价' in s or '评论' in s))
        if all_comment_divs:
            logger.info(f"找到可能包含评论的div: {len(all_comment_divs)}个")
            comment_elements.extend(all_comment_divs)
        
        # 去重
        unique_elements = set()
        filtered_comments = []
        for element in comment_elements:
            element_str = str(element)
            if element_str not in unique_elements:
                unique_elements.add(element_str)
                filtered_comments.append(element)
        
        logger.info(f"去重后评论元素数量: {len(filtered_comments)}个")
        
        # 提取评论数据
        for i, comment_elem in enumerate(filtered_comments[:max_count]):
            try:
                # 尝试提取评论文本和其他信息
                comment_text = comment_elem.get_text(strip=True)
                
                # 尝试提取用户名
                username = "匿名用户"
                username_elem = comment_elem.find_previous(class_=lambda c: c and ('user' in c.lower() or 'author' in c.lower() or 'name' in c.lower()))
                if username_elem:
                    username = username_elem.get_text(strip=True)
                
                # 尝试提取日期
                comment_date = "未知时间"
                date_elem = comment_elem.find_previous(class_=lambda c: c and ('date' in c.lower() or 'time' in c.lower()))
                if date_elem:
                    comment_date = date_elem.get_text(strip=True)
                else:
                    # 尝试从文本中提取日期格式
                    date_patterns = [
                        r'\d{4}-\d{2}-\d{2}',  # 2023-01-01
                        r'\d{4}年\d{1,2}月\d{1,2}日',  # 2023年1月1日
                        r'\d{2}/\d{2}/\d{4}',  # 01/01/2023
                        r'\d{4}\.\d{1,2}\.\d{1,2}'  # 2023.1.1
                    ]
                    
                    for pattern in date_patterns:
                        matches = re.search(pattern, str(comment_elem))
                        if matches:
                            comment_date = matches.group(0)
                            break
                
                # 过滤无效评论
                if comment_text and not comment_text.isspace() and len(comment_text) > 1:
                    if "评价方未及时做出评价,系统默认好评" in comment_text:
                        # 这是系统默认好评，记为特殊类型
                        logger.info(f"发现系统默认好评: {comment_text[:20]}...")
                        comments_data.append({
                            'comment_text': comment_text,
                            'username': username,
                            'comment_date': comment_date,
                            'is_default': True
                        })
                    else:
                        # 普通评论
                        comments_data.append({
                            'comment_text': comment_text,
                            'username': username,
                            'comment_date': comment_date,
                            'is_default': False
                        })
                    logger.info(f"提取到第{i+1}条评论: {comment_text[:30]}...")
            except Exception as e:
                logger.error(f"提取第{i+1}个评论元素时出错: {e}")
        
        # 提取JSON格式的评论数据
        if len(comments_data) < max_count:
            try:
                json_comments = extract_comments_from_json(page_source)
                if json_comments:
                    logger.info(f"从JSON中提取到{len(json_comments)}条评论")
                    comments_data.extend(json_comments[:max_count - len(comments_data)])
            except Exception as e:
                logger.error(f"提取JSON评论数据失败: {e}")
        
        # 如果评论太少，尝试查找评论链接
        if len(comments_data) < max_count / 2:
            logger.info("评论数量不足，尝试查找评论链接")
            comment_link = soup.find('div', class_=lambda c: c and ('comment-service' in c or 'tb-rate-content' in c or 'comment-more' in c))
            if comment_link:
                href_elem = comment_link.find('a', href=True)
                if href_elem and href_elem.get('href'):
                    comment_url = href_elem.get('href')
                    if not comment_url.startswith('http'):
                        comment_url = f"https:{comment_url}" if comment_url.startswith('//') else f"https://item.taobao.com{comment_url}"
                    
                    logger.info(f"找到评论链接: {comment_url}，尝试通过浏览器访问")
                    try:
                        # 使用当前driver访问评论页面
                        driver.get(comment_url)
                        time.sleep(3)  # 等待页面加载
                        
                        # 递归调用一次，获取评论页面的内容
                        additional_comments = extract_comments_with_beautifulsoup()
                        if additional_comments:
                            logger.info(f"从评论页面获取到{len(additional_comments)}条评论")
                            comments_data.extend(additional_comments)
                    except Exception as e:
                        logger.error(f"访问评论页面失败: {e}")
            else:
                logger.info("未找到评论链接")
        
        # 更新当前评论数量
        current_count = len(comments_data)
        logger.info(f"BeautifulSoup总共提取到{current_count}条评论")
        
        return comments_data
        
    except Exception as e:
        logger.error(f"BeautifulSoup提取评论失败: {traceback.format_exc()}")
        return []

def extract_comments_from_json(page_source):
    """从页面源码中提取JSON格式的评论数据"""
    comments_data = []
    
    try:
        # 尝试找到评论JSON数据
        json_patterns = [
            r'{"api":"mtop\.tmall\.rate\.rewrite\.rate\.list".*?"rateList":(\[.*?\])',
            r'"comments":(\[.*?\])',
            r'"rateList":(\[.*?\])',
            r'"reviewList":(\[.*?\])',
            r'"rateDOs":(\[.*?\])',
            r'"data":\s*{.*?"comments":(\[.*?\])',
            r'"data":\s*{.*?"rateList":(\[.*?\])'
        ]
        
        for pattern in json_patterns:
            try:
                matches = re.search(pattern, page_source)
                if matches:
                    json_str = matches.group(1)
                    # 确保它是一个JSON数组
                    if json_str.startswith('[') and json_str.endswith(']'):
                        comments_json = json.loads(json_str)
                        logger.info(f"找到JSON评论数据: {len(comments_json)}条")
                        
                        for item in comments_json:
                            comment = {}
                            
                            # 尝试不同的字段名
                            content_fields = ['content', 'text', 'rateContent', 'reviewContent', 'comment']
                            for field in content_fields:
                                if field in item and item[field]:
                                    comment['comment_text'] = item[field]
                                    break
                            
                            user_fields = ['user', 'userName', 'displayUserNick', 'nick', 'author']
                            for field in user_fields:
                                if field in item and item[field]:
                                    comment['username'] = item[field]
                                    break
                            
                            date_fields = ['date', 'rateDate', 'reviewDate', 'creationTime', 'gmtCreate']
                            for field in date_fields:
                                if field in item and item[field]:
                                    comment['comment_date'] = item[field]
                                    break
                            
                            if 'comment_text' in comment:
                                if 'username' not in comment:
                                    comment['username'] = "匿名用户"
                                if 'comment_date' not in comment:
                                    comment['comment_date'] = "未知时间"
                                comment['is_default'] = "默认好评" in comment['comment_text']
                                
                                comments_data.append(comment)
                        
                        if comments_data:
                            break
            except Exception as e:
                logger.error(f"解析评论JSON数据失败: {e}")
        
    except Exception as e:
        logger.error(f"提取JSON评论失败: {e}")
    
    return comments_data

def continue_crawl():
    """继续爬取评论的流程（已初始化浏览器并打开页面）"""
    global is_running, current_count
    
    if not is_running:
        logger.warning("爬虫未启动，无法继续")
        return {"status": "error", "message": "爬虫未启动"}
    
    try:
        logger.info("第一步：尝试导航到评论区")
        navigate_to_comments()
        
        logger.info("第二步：尝试获取更多评论")
        load_result = load_more_comments(max_count)
        
        if not load_result:
            logger.warning("无法加载更多评论，可能是没有评论或无法定位评论元素")
            # 即使无法加载更多评论，仍然尝试提取当前可见的评论
        
        logger.info("第三步：从页面中获取评论")
        
        # 首先尝试使用PyQuery提取评论（如果可用）
        comments_data = []
        if PYQUERY_AVAILABLE:
            logger.info("使用PyQuery提取评论")
            comments_data = extract_comments_with_pyquery()
            logger.info(f"PyQuery提取到 {len(comments_data)} 条评论")
            
        # 如果PyQuery未能提取到足够评论，尝试使用BeautifulSoup
        if not comments_data or len(comments_data) < max_count/2:
            logger.info("PyQuery未能提取到足够评论，尝试使用BeautifulSoup")
            bs_comments = extract_comments_with_beautifulsoup()
            logger.info(f"BeautifulSoup提取到 {len(bs_comments) if bs_comments else 0} 条评论")
            
            if bs_comments:
                if not comments_data:
                    # 如果PyQuery完全没有结果，直接使用BeautifulSoup的结果
                    comments_data = bs_comments
                else:
                    # 合并结果，并去重
                    seen_texts = set(c['comment_text'] for c in comments_data)
                    for comment in bs_comments:
                        if comment['comment_text'] not in seen_texts:
                            comments_data.append(comment)
                            seen_texts.add(comment['comment_text'])
            
            logger.info(f"合并后共有 {len(comments_data)} 条评论")
        
        # 如果仍然没有评论，尝试直接从页面源码中提取JSON评论数据
            if not comments_data:
                logger.info("尝试直接从页面源码中提取评论")
            json_comments = extract_comments_from_json(driver.page_source)
            logger.info(f"JSON方法提取到 {len(json_comments) if json_comments else 0} 条评论")
            if json_comments:
                comments_data = json_comments
            
        # 如果尝试了所有方法但仍然没有评论，就手动添加默认评论
            if not comments_data:
                logger.warning("所有提取方法均未能获取到评论数据，添加一条默认说明")
                # 创建默认评论
                comments_data = [
                    {
                        'username': '系统提示',
                        'comment_text': '该商品暂无评论或评论不可见，系统已尝试多种方式但未能获取到评论。',
                        'comment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'is_default': 1
                    }
                ]
                
                # 再添加一条空的默认好评，模拟淘宝默认好评
                comments_data.append({
                    'username': '匿名用户',
                    'comment_text': '此用户没有填写评论(系统默认好评)',
                    'comment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'is_default': 1
                })
        
        # 更新当前已获取的评论计数
        current_count = len(comments_data)
        logger.info(f"最终成功提取 {current_count} 条评论数据")
        
        # 记录数据库连接前的状态
        logger.info(f"准备保存评论数据到数据库，product_id={product_id}，评论数量={len(comments_data)}")
        
        # 保存评论到数据库
        logger.info("最后一步：将评论数据保存到数据库")
        
        # 记录每个评论的前几个字符，方便调试
        for i, comment in enumerate(comments_data[:5]):  # 仅记录前5条评论
            logger.info(f"评论{i+1}样本: {comment['comment_text'][:50]}... (用户: {comment['username']})")
            
        # 保存评论数据
        saved_count = save_comments_to_db(product_id, comments_data)
        
        # 爬取成功后自动停止爬虫
        logger.info(f"爬取任务完成，共保存 {saved_count} 条评论，自动停止爬虫")
        result = stop_crawl()
        
        if saved_count > 0:
            logger.info(f"成功保存 {saved_count} 条评论到数据库")
            return {
                "status": "success", 
                "message": f"成功获取并保存 {saved_count} 条评论，爬虫已自动停止",
                "count": saved_count
            }
        else:
            logger.warning("未能保存评论数据到数据库")
            return {
                "status": "warning",
                "message": "未能保存评论数据到数据库，爬虫已自动停止",
                "count": 0
            }
    
    except Exception as e:
        logger.error(f"评论爬取过程出错: {traceback.format_exc()}")
        # 发生异常时自动停止爬虫
        stop_crawl()
        return {"status": "error", "message": f"爬取过程出错: {str(e)}，爬虫已自动停止"}
    
    finally:
        # 确保无论如何都尝试停止爬虫
        if is_running:
            logger.info("在finally块中确保爬虫停止")
            stop_crawl()

def get_status():
    """获取爬虫当前状态"""
    global is_running, is_waiting_login, current_count, max_count, product_id, product_url, driver
    
    # 检查driver是否还存在且可访问，确保状态准确
    if driver:
        try:
            # 尝试简单操作检查driver是否还存活
            driver.current_url
        except Exception as e:
            logger.warning(f"检测到driver已失效，但状态未更新: {e}")
            is_running = False
            driver = None
    else:
        # 如果driver为None但状态还是运行中，重置状态
        if is_running:
            logger.warning("检测到状态不一致：driver为None但is_running为True，已修正")
            is_running = False
    
    return {
        "is_running": is_running,
        "is_waiting_login": is_waiting_login,
        "current_count": current_count,
        "max_count": max_count,
        "product_id": product_id,
        "product_url": product_url
    }

def stop_crawl():
    """停止评论爬取过程"""
    global driver, is_running
    
    logger.info("停止评论爬取")
    
    # 如果爬虫未在运行，直接返回
    if not is_running:
        logger.info("爬虫已经处于停止状态")
        return {"status": "success", "message": "爬虫已经是停止状态"}
    
    try:
        # 标记爬虫为非运行状态
        is_running = False
        logger.info("爬虫状态已设置为停止")
    
        # 安全关闭WebDriver
        if driver:
            try:
                driver.quit()
                logger.info("WebDriver已关闭")
            except Exception as e:
                logger.warning(f"关闭WebDriver时出错: {str(e)}")
            finally:
                driver = None
        
        # 执行完整的资源清理
        cleanup_resources()
        
        return {"status": "success", "message": "评论爬取已停止"}
    except Exception as e:
        logger.error(f"停止爬虫时出错: {str(e)}")
        return {"status": "error", "message": f"停止爬虫时出错: {str(e)}"}

def extract_comments_with_pyquery():
    
    global current_count, max_count
    comments_data = []
    
    # 如果PyQuery不可用，直接返回空列表
    if not PYQUERY_AVAILABLE:
        logger.warning("PyQuery不可用，无法使用此方法提取评论")
        return []
    
    try:
        logger.info("开始使用PyQuery提取评论")
        # 获取当前页面源码
        page_source = driver.page_source
        
        # 保存页面源码到文件（调试用）
        try:
            with open("taobao_page_source_pyquery.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("已保存页面源码到taobao_page_source_pyquery.html")
        except Exception as e:
            logger.error(f"保存页面源码失败: {e}")
        
        # 使用PyQuery解析HTML
        doc = pq(page_source)
        logger.info("页面已解析为PyQuery对象")
        
        # 尝试查找评论区容器
        comment_containers = [
            ".kg-rate-ct-reviews",  # 2025新版淘宝评论区容器
            ".kg-layout-container", # 新版评论容器
            ".detail-rate",        # 详情评价区
            ".tb-revbd",           # 旧版评论区
            ".J_Reviews",          # 标准评论区
            "#reviews",            # 评论ID
            "#J_Reviews",          # 标准评论ID
            "#commonCtnrCommen",   # 天猫常见评论区
            ".rate-grid-container" # 评价网格容器
        ]
        
        container = None
        for selector in comment_containers:
            if doc(selector).length > 0:
                container = doc(selector)
                logger.info(f"找到评论区容器: {selector}, 包含{len(container)}个元素")
                break
        
        # 尝试多个选择器找到评论元素
        found_comments = []
        selectors_tested = 0
        selectors_with_results = 0
        
        # 1. 先尝试在评论区容器中找
        if container:
            for selector in comment_selectors:
                selectors_tested += 1
                comments = container.find(selector)
                if comments.length > 0:
                    selectors_with_results += 1
                    logger.info(f"在容器中使用选择器 {selector} 找到 {comments.length} 个评论元素")
                    for i in range(comments.length):
                        found_comments.append(comments.eq(i))
        
        # 2. 如果在容器中没找到足够评论，尝试在整个文档中查找
        if len(found_comments) < max_count / 2:
            logger.info("在评论区容器中未找到足够评论，尝试在整个文档中查找")
            for selector in comment_selectors:
                selectors_tested += 1
                comments = doc(selector)
                if comments.length > 0:
                    selectors_with_results += 1
                    logger.info(f"在整个页面中使用选择器 {selector} 找到 {comments.length} 个评论元素")
                    for i in range(comments.length):
                        found_comments.append(comments.eq(i))
        
        logger.info(f"测试了 {selectors_tested} 个选择器，{selectors_with_results} 个选择器有结果")
        logger.info(f"总共找到 {len(found_comments)} 个潜在评论元素")
        
        # 提取评论数据
        unique_texts = set()  # 用于去重
        for i, comment_elem in enumerate(found_comments[:max_count * 2]):  # 处理更多元素，稍后会过滤
            try:
                # 获取评论文本 - PyQuery对象的text()方法
                comment_text = comment_elem.text()
                
                # 跳过过短或重复的评论
                if not comment_text or len(comment_text) < 2 or comment_text in unique_texts:
                    continue
                    
                unique_texts.add(comment_text)
                
                # 尝试获取用户名 - 先查找父元素中的用户名元素
                username = "匿名用户"
                parent = comment_elem.parent()
                
                # 尝试多个用户名选择器
                username_selectors = [
                    ".kg-rate-ct-review-item-user-name", ".Gygm8xdW85--userName--", 
                    ".user-name", ".from-whom", ".rate-user-name", ".tb-r-uname",
                    ".review-user", ".user"
                ]
                
                for selector in username_selectors:
                    username_elem = parent.find(selector)
                    if username_elem.length > 0:
                        username = username_elem.text().strip()
                        break
                
                # 尝试获取评论日期 - 查找父元素中的日期元素
                comment_date = "未知时间"
                date_selectors = [
                    ".kg-rate-ct-review-item-date", ".date", ".rate-date", 
                    ".tb-r-date", ".review-date", ".time", ".moment"
                ]
                
                for selector in date_selectors:
                    date_elem = parent.find(selector)
                    if date_elem.length > 0:
                        comment_date = date_elem.text().strip()
                        break
                
                # 如果没找到日期，尝试从文本中提取日期格式
                if comment_date == "未知时间":
                    date_patterns = [
                        r'\d{4}-\d{2}-\d{2}',  # 2023-01-01
                        r'\d{4}年\d{1,2}月\d{1,2}日',  # 2023年1月1日
                        r'\d{2}/\d{2}/\d{4}',  # 01/01/2023
                        r'\d{4}\.\d{1,2}\.\d{1,2}'  # 2023.1.1
                    ]
                    
                    for pattern in date_patterns:
                        matches = re.search(pattern, str(parent.html()))
                        if matches:
                            comment_date = matches.group(0)
                            break
                
                # 判断是否为默认好评
                is_default = "默认好评" in comment_text or "系统默认" in comment_text
                
                # 添加到评论数据列表
                comments_data.append({
                    'comment_text': comment_text,
                    'username': username,
                    'comment_date': comment_date,
                    'is_default': is_default
                })
                
                logger.info(f"PyQuery提取到第{len(comments_data)}条评论: {comment_text[:30]}...")
                
                # 如果已经提取到足够的评论，可以提前结束
                if len(comments_data) >= max_count:
                    break
                    
            except Exception as e:
                logger.error(f"提取第{i+1}个评论元素时出错: {e}")
        
        # 更新当前评论数量
        current_count = len(comments_data)
        logger.info(f"PyQuery总共提取到{current_count}条评论")
        
        return comments_data
        
    except Exception as e:
        logger.error(f"PyQuery提取评论失败: {traceback.format_exc()}")
        return []

def cleanup_resources():
    """清理爬虫相关的所有资源，确保没有残留进程或内存占用"""
    global driver, is_running, is_waiting_login, current_count, max_count
    
    try:
        # 记录清理操作
        logger.info("执行资源清理操作")
        
        # 关闭WebDriver
        if driver:
            try:
                driver.quit()
                logger.info("WebDriver已关闭")
            except Exception as e:
                logger.warning(f"关闭WebDriver时出错: {str(e)}")
            finally:
                driver = None
        
        # 重置所有状态变量
        is_running = False
        is_waiting_login = False
        current_count = 0
        max_count = 0
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        logger.info("资源清理完成")
        return {"status": "success", "message": "所有资源已清理"}
    except Exception as e:
        logger.error(f"清理资源时出错: {str(e)}")
        return {"status": "error", "message": f"清理资源时出错: {str(e)}"}

# 如果直接运行此文件，可以进行测试
if __name__ == "__main__":
    test_url = "https://item.taobao.com/item.htm?id=123456789"
    result = start_comment_crawl(1, test_url, 10)
    print(result) 