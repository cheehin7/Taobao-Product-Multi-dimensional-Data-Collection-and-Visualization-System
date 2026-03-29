import time
import random
import json
import re
import logging
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import pymysql
from db_config import DB_CONFIG

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
    # 淘宝商品详情页评论区选择器
    ".tb-rev-item",  # 评论项
    ".J_KgRate_ReviewItem", # 另一种评论项选择器
    "div.rate-grid-row", # 评论行
    ".tm-rate-content", # 天猫评论内容
    ".tm-rate-premiere", # 天猫首条评论
    ".tm-rate-tag", # 评论标签
    ".tm-rate-reply", # 评论回复
    ".rate-user-info" # 用户信息
]

def setup_driver():
    """设置并返回Selenium WebDriver"""
    global driver
    
    if driver:
        try:
            driver.quit()
        except:
            pass
    
    # 设置Chrome浏览器选项
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    try:
        # 实例化Chrome浏览器
        driver = webdriver.Chrome(options=chrome_options)
        # 修改navigator.webdriver属性，规避检测
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
            """
        })
        logger.info("WebDriver初始化成功")
        return driver
    except Exception as e:
        logger.error(f"WebDriver初始化失败: {e}")
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
            return True
        
        # 检查URL是否包含'login'
        if 'login' in driver.current_url.lower():
            return True
        
        # 检查页面内容是否包含登录相关文字
        page_text = driver.page_source.lower()
        login_keywords = ['请登录', '立即登录', 'login', '用户名', '密码', '验证码', '安全验证']
        for keyword in login_keywords:
            if keyword in page_text:
                return True
        
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
        
        # 刷新页面
        driver.refresh()
        time.sleep(3)
        
        # 检查是否仍需登录
        if is_login_required():
            logger.warning("用户确认登录后，仍检测到需要登录")
            return False
        
        logger.info("登录确认成功，可以开始爬取评论")
        return True
    except Exception as e:
        logger.error(f"确认登录失败: {e}")
        return False

def navigate_to_comments():
    """导航到评论区"""
    try:
        # 尝试查找并点击评论选项卡
        comment_tabs = [
            "//a[contains(text(), '评价')]",
            "//a[contains(text(), '评论')]",
            "//div[contains(text(), '评价')]",
            "//div[contains(text(), '评论')]",
            "//li[contains(text(), '评价')]",
            "//li[contains(text(), '评论')]"
        ]
        
        for xpath in comment_tabs:
            try:
                tab = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                tab.click()
                logger.info(f"成功点击评论选项卡: {xpath}")
                time.sleep(3)
                return True
            except:
                continue
        
        # 如果没有找到评论选项卡，尝试直接滚动到评论区
        logger.info("未找到评论选项卡，尝试滚动到评论区")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)
        return True
    except Exception as e:
        logger.error(f"导航到评论区失败: {e}")
        return False

def load_more_comments(target_count):
    """加载更多评论"""
    global current_count
    
    # 初始评论数
    initial_comments = get_comment_elements()
    current_count = len(initial_comments)
    
    logger.info(f"当前已加载评论数量: {current_count}")
    
    if current_count >= target_count:
        logger.info(f"已加载足够的评论: {current_count}/{target_count}")
        return True
    
    # 尝试点击"加载更多"按钮
    load_more_attempts = 0
    max_load_attempts = 30  # 最大尝试次数
    
    while current_count < target_count and load_more_attempts < max_load_attempts:
        try:
            # 查找"加载更多"按钮
            load_more_buttons = [
                "//a[contains(text(), '加载更多')]",
                "//button[contains(text(), '加载更多')]",
                "//div[contains(text(), '加载更多')]",
                "//span[contains(text(), '加载更多')]",
                "//a[contains(text(), '显示更多')]",
                "//button[contains(text(), '显示更多')]",
                "//a[contains(@class, 'J_ReviewsRate')]",
                ".rate-paginator"
            ]
            
            clicked = False
            for selector in load_more_buttons:
                try:
                    # 滚动到页面底部
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                    
                    # 尝试查找并点击按钮
                    if selector.startswith('//'):
                        button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    
                    button.click()
                    clicked = True
                    logger.info(f"点击'加载更多'按钮: {selector}")
                    time.sleep(2)
                    break
                except:
                    continue
            
            if not clicked:
                # 如果找不到"加载更多"按钮，尝试分页器
                try:
                    # 尝试点击下一页
                    next_page = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".rate-paginator a:last-child"))
                    )
                    next_page.click()
                    clicked = True
                    logger.info("点击'下一页'按钮")
                    time.sleep(2)
                except:
                    logger.info("未找到'下一页'按钮")
            
            # 点击完等待加载
            time.sleep(random.uniform(2, 4))
            
            # 更新评论数量
            comments = get_comment_elements()
            new_count = len(comments)
            
            if new_count > current_count:
                logger.info(f"已加载更多评论: {current_count} -> {new_count}")
                current_count = new_count
                load_more_attempts = 0  # 重置尝试次数
            else:
                load_more_attempts += 1
                logger.info(f"评论数量未增加，当前尝试次数: {load_more_attempts}/{max_load_attempts}")
                
                if load_more_attempts >= 3:
                    # 尝试不同的滚动位置
                    scroll_positions = [0.5, 0.8, 0.3, 0.7]
                    position = scroll_positions[load_more_attempts % len(scroll_positions)]
                    driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {position});")
                    time.sleep(1)
        
        except Exception as e:
            load_more_attempts += 1
            logger.error(f"加载更多评论失败: {e}")
            time.sleep(random.uniform(2, 4))
    
    final_count = len(get_comment_elements())
    logger.info(f"评论加载完成，最终数量: {final_count}/{target_count}")
    
    return final_count > 0

def get_comment_elements():
    """获取所有评论元素"""
    all_comments = []
    
    for selector in comment_selectors:
        try:
            comments = driver.find_elements(By.CSS_SELECTOR, selector)
            if comments:
                logger.info(f"使用选择器 '{selector}' 找到 {len(comments)} 条评论")
                all_comments = comments
                break
        except:
            continue
    
    if not all_comments:
        logger.warning("未找到评论元素，尝试使用备用方法")
        try:
            # 备用方法：查找包含可能是评论的div元素
            potential_comments = driver.find_elements(By.CSS_SELECTOR, "div.tb-rev-item, div.comment-item, div.review-item")
            if potential_comments:
                logger.info(f"使用备用选择器找到 {len(potential_comments)} 条潜在评论")
                all_comments = potential_comments
        except:
            pass
    
    return all_comments

def extract_comment_data(comment_elements):
    """从评论元素中提取数据"""
    comments_data = []
    
    if not comment_elements:
        logger.warning("没有评论元素可供提取")
        return comments_data
    
    for idx, comment in enumerate(comment_elements[:max_count]):
        try:
            # 提取评论文本
            comment_text = ""
            text_selectors = [
                ".tb-tbcr-content", ".rate-user-info", ".review-details", 
                ".comment-content", ".tm-rate-fulltxt", ".rate-content"
            ]
            
            for selector in text_selectors:
                try:
                    text_element = comment.find_element(By.CSS_SELECTOR, selector)
                    if text_element:
                        comment_text = text_element.text.strip()
                        break
                except:
                    continue
            
            # 如果没有通过选择器找到，尝试直接获取元素文本
            if not comment_text:
                comment_text = comment.text.strip()
            
            # 提取用户名
            username = ""
            username_selectors = [
                ".rate-user-info", ".from-whom", ".user-name", 
                ".tb-r-user-name", ".tm-rate-author"
            ]
            
            for selector in username_selectors:
                try:
                    username_element = comment.find_element(By.CSS_SELECTOR, selector)
                    if username_element:
                        username = username_element.text.strip()
                        break
                except:
                    continue
            
            # 提取评论时间
            comment_time = ""
            time_selectors = [
                ".tb-r-date", ".rate-date", ".tm-rate-date", ".comment-time"
            ]
            
            for selector in time_selectors:
                try:
                    time_element = comment.find_element(By.CSS_SELECTOR, selector)
                    if time_element:
                        comment_time = time_element.text.strip()
                        break
                except:
                    continue
            
            # 如果还是没提取到时间，尝试从文本中匹配日期格式
            if not comment_time:
                full_text = comment.text
                date_patterns = [
                    r'\d{4}-\d{2}-\d{2}',  # 2023-01-01
                    r'\d{4}年\d{1,2}月\d{1,2}日',  # 2023年1月1日
                    r'\d{2}/\d{2}/\d{4}'  # 01/01/2023
                ]
                
                for pattern in date_patterns:
                    matches = re.search(pattern, full_text)
                    if matches:
                        comment_time = matches.group(0)
                        break
            
            # 只有当评论文本存在时才添加到结果中
            if comment_text:
                comments_data.append({
                    'comment_text': comment_text,
                    'username': username if username else "匿名用户",
                    'comment_date': comment_time if comment_time else "未知时间"
                })
                logger.info(f"成功提取第 {idx+1} 条评论: {username}, {comment_time}")
            
        except Exception as e:
            logger.error(f"提取第 {idx+1} 条评论数据失败: {e}")
    
    # 如果通过上述方法无法提取有效评论，尝试从页面源码中提取
    if len(comments_data) == 0:
        logger.info("通过元素无法提取评论，尝试从源码中提取")
        comments_data = extract_comments_from_source()
    
    return comments_data

def extract_comments_from_source():
    """从页面源代码中提取评论数据"""
    comments_data = []
    
    try:
        page_source = driver.page_source
        
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
                                
                                comments_data.append(comment)
                        
                        if comments_data:
                            break
            except Exception as e:
                logger.error(f"解析评论JSON数据失败: {e}")
        
        # 如果通过JSON无法提取，尝试使用正则表达式直接从源码中提取
        if not comments_data:
            logger.info("尝试使用正则表达式从源码中提取评论")
            
            # 简单匹配评论区块
            comment_blocks = re.findall(r'<div[^>]*class=["\'](?:[^"\']*(?:comment|review|rate)[^"\']*)["\'][^>]*>(.*?)</div>', page_source, re.DOTALL)
            
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
                    
                    comments_data.append({
                        'comment_text': comment_text,
                        'username': username,
                        'comment_date': comment_date
                    })
                    processed_count += 1
    
    except Exception as e:
        logger.error(f"从源码提取评论失败: {e}")
    
    return comments_data

def save_comments_to_db(product_id, comments_data):
    """将评论数据保存到数据库"""
    if not comments_data:
        logger.warning("没有评论数据可保存")
        return 0
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 更新商品表的评论获取数
        cursor.execute(
            "UPDATE taobao_products SET comment_fetched = %s WHERE id = %s",
            (len(comments_data), product_id)
        )
        
        # 清除之前的评论数据
        cursor.execute("DELETE FROM product_comments WHERE product_id = %s", (product_id,))
        
        # 插入新的评论数据
        for comment in comments_data:
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
        
        conn.commit()
        logger.info(f"成功保存 {len(comments_data)} 条评论到数据库")
        return len(comments_data)
    
    except Exception as e:
        logger.error(f"保存评论数据到数据库失败: {e}")
        if conn:
            conn.rollback()
        return 0
    
    finally:
        if conn:
            conn.close()

def start_comment_crawl(target_id, url, target_count=50):
    """启动评论爬取流程"""
    global driver, is_waiting_login, is_running, current_count, max_count, product_id, product_url
    
    if is_running:
        logger.warning("评论爬虫已经在运行中")
        return {"status": "error", "message": "评论爬虫已经在运行中"}
    
    is_running = True
    product_id = target_id
    product_url = url
    max_count = target_count
    current_count = 0
    
    try:
        logger.info(f"开始爬取商品 ID: {target_id}, URL: {url}, 目标评论数: {target_count}")
        
        # 设置WebDriver
        if not driver:
            driver = setup_driver()
            if not driver:
                is_running = False
                return {"status": "error", "message": "WebDriver初始化失败"}
        
        # 打开商品页面
        page_result = open_product_page(url)
        
        if page_result == "login_required":
            logger.info("需要用户登录，等待确认")
            return {"status": "waiting_login", "message": "请在浏览器中登录后点击确认"}
        
        elif page_result == True:
            logger.info("商品页面打开成功，不需要登录")
            # 直接开始爬取评论
            continue_crawl()
            return {"status": "success", "message": "爬虫已启动"}
        
        else:
            is_running = False
            logger.error("打开商品页面失败")
            return {"status": "error", "message": "打开商品页面失败"}
    
    except Exception as e:
        is_running = False
        logger.error(f"启动评论爬虫失败: {e}")
        return {"status": "error", "message": f"启动失败: {str(e)}"}

def confirm_comment_login():
    """确认用户已登录，继续爬取评论"""
    global is_running
    
    if not is_running:
        logger.warning("评论爬虫未运行")
        return {"status": "error", "message": "评论爬虫未运行"}
    
    if confirm_login():
        # 继续爬取流程
        continue_crawl()
        return {"status": "success", "message": "登录确认成功，开始爬取评论"}
    else:
        is_running = False
        return {"status": "error", "message": "登录确认失败，请重新尝试"}

def continue_crawl():
    """继续爬取评论的流程"""
    global is_running, current_count, max_count, product_id
    
    try:
        # 导航到评论区
        if not navigate_to_comments():
            logger.error("无法导航到评论区")
            is_running = False
            return {"status": "error", "message": "无法导航到评论区"}
        
        # 加载更多评论
        if not load_more_comments(max_count):
            logger.warning("加载评论失败或没有评论")
        
        # 提取评论数据
        comments = get_comment_elements()
        logger.info(f"找到 {len(comments)} 条评论元素")
        
        # 有效评论数上限为max_count
        comments = comments[:max_count] if len(comments) > max_count else comments
        
        # 提取评论数据
        comments_data = extract_comment_data(comments)
        logger.info(f"成功提取 {len(comments_data)} 条评论数据")
        
        # 保存到数据库
        saved_count = save_comments_to_db(product_id, comments_data)
        
        # 更新状态
        is_running = False
        
        return {
            "status": "success", 
            "message": f"评论爬取完成，成功保存 {saved_count} 条评论",
            "count": saved_count
        }
    
    except Exception as e:
        logger.error(f"爬取评论过程中出错: {e}")
        is_running = False
        return {"status": "error", "message": f"爬取过程中出错: {str(e)}"}

def get_status():
    """获取爬虫当前状态"""
    return {
        "is_running": is_running,
        "is_waiting_login": is_waiting_login,
        "current_count": current_count,
        "max_count": max_count,
        "product_id": product_id,
        "product_url": product_url
    }

def stop_crawl():
    """停止爬虫"""
    global is_running, driver
    
    is_running = False
    
    if driver:
        try:
            driver.quit()
            driver = None
            logger.info("评论爬虫已停止，浏览器已关闭")
            return {"status": "success", "message": "评论爬虫已停止"}
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
            return {"status": "error", "message": f"关闭浏览器失败: {str(e)}"}
    
    return {"status": "success", "message": "评论爬虫已停止"}

# 如果直接运行此文件，可以进行测试
if __name__ == "__main__":
    test_url = "https://item.taobao.com/item.htm?id=123456789"
    result = start_comment_crawl(1, test_url, 10)
    print(result) 