import time
import random
import csv
import pymysql  # 添加MySQL连接库
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyquery import PyQuery as pq
from db_config import DB_CONFIG  # 导入数据库配置
import threading
import os
from selenium.webdriver.common.keys import Keys
import psutil
import subprocess

# 全局变量
driver = None  # WebDriver实例
wait = None  # WebDriverWait实例
current_page = 1  # 当前爬取页码
count = 1  # 爬取的商品数量
search_keyword = ""  # 搜索关键词
csv_rows = []  # 存储每一行数据
filename = ""  # CSV文件名
stop_flag = False  # 停止标志
is_waiting_login = False  # 是否等待用户登录
crawl_status = "pending"  # 爬取状态: pending, running, waiting_login, completed, error
db_conn = None  # MySQL数据库连接对象

def setup_browser():
    """初始化浏览器"""
    global driver, wait
    print("="*50)
    print("[浏览器] 正在启动Chrome浏览器...")
    print(f"[浏览器] 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[浏览器] 线程ID: {threading.get_ident()}")
    
    # 首先检查是否已有driver实例在运行
    if driver is not None:
        try:
            # 尝试获取当前URL，检查driver是否仍然有效
            current_url = driver.current_url
            print(f"[浏览器] 检测到已有Chrome实例在运行，URL: {current_url}")
            print("[浏览器] 将重用已有的Chrome实例")
            print("="*50)
            return True
        except Exception as e:
            print(f"[浏览器] 现有Chrome实例已失效: {e}")
            print("[浏览器] 将关闭失效实例并创建新的Chrome实例")
            try:
                driver.quit()
            except:
                pass
            driver = None
    
    # 指定ChromeDriver的路径
    chromedriver_path = "F:\\chromedriver\\chromedriver.exe"
    print(f"[浏览器] 使用ChromeDriver路径: {chromedriver_path}")
    
    # 确保ChromeDriver存在
    if not os.path.exists(chromedriver_path):
        print(f"[浏览器] 错误: ChromeDriver不存在于路径: {chromedriver_path}")
        print(f"[浏览器] 尝试使用默认路径继续")
        chromedriver_path = ""  # 将路径设为空，让Selenium尝试自动查找
    else:
        print(f"[浏览器] ChromeDriver文件大小: {os.path.getsize(chromedriver_path) / 1024:.2f} KB")
    
    # 添加ChromeDriver路径到系统环境变量
    try:
        os.environ["PATH"] += os.pathsep + "F:\\chromedriver"
    except Exception as path_error:
        print(f"[浏览器] 添加ChromeDriver到PATH失败: {path_error}, 但将继续尝试")
    
    # 配置Chrome选项
    options = webdriver.ChromeOptions()
    
    # 优化选项，降低首次启动时的资源占用
    print("[配置] 添加Chrome启动选项...")
    try:
        options.add_experimental_option("excludeSwitches", ['enable-automation'])
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # 防止闪烁问题的额外选项
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-browser-side-navigation")
    except Exception as option_error:
        print(f"[浏览器] 设置Chrome选项失败: {option_error}, 但将使用基本选项继续")
    
    browser_initialized = False
    
    try:
        print("[启动] 正在创建Chrome实例...")
        
        # 主要方法启动Chrome
        try:
            print("[启动] 使用Service对象启动Chrome...")
            from selenium.webdriver.chrome.service import Service
            service = Service(executable_path=chromedriver_path)
            
            # 直接启动浏览器
            driver = webdriver.Chrome(service=service, options=options)
            print("[成功] Chrome实例已创建")
            browser_initialized = True
        except Exception as chrome_error:
            print(f"[错误] 创建Chrome实例失败: {chrome_error}")
            
            # 在使用备用方法前检查是否有Chrome实例已在运行
            chrome_running = False
            try:
                import psutil
                chrome_count = 0
                for proc in psutil.process_iter(['pid', 'name']):
                    if 'chrome' in proc.info['name'].lower():
                        chrome_count += 1
                
                if chrome_count > 2:  # 通常会有至少2个Chrome进程(浏览器和一个标签页)
                    print(f"[警告] 检测到 {chrome_count} 个Chrome进程，可能已有实例在运行")
                    chrome_running = True
            except:
                print("[警告] 无法检测Chrome进程，将继续尝试启动")
            
            # 如果没有检测到运行的Chrome实例或检测失败，尝试备用方法
            if not chrome_running:
                print("[尝试] 使用备用方法启动Chrome...")
                try:
                    # 不使用service对象尝试启动
                    driver = webdriver.Chrome(options=options)
                    print("[成功] 使用备用方法成功启动Chrome")
                    browser_initialized = True
                except Exception as backup_error:
                    print(f"[错误] 备用方法也失败: {backup_error}")
                    print("[严重] 无法启动Chrome浏览器，请检查安装和配置")
                    return False
            else:
                print("[错误] 检测到Chrome实例已在运行，无法启动新实例")
                return False
            
        # 如果成功初始化浏览器，继续设置
        if browser_initialized:
            try:
                print("[配置] 禁用webdriver指纹识别...")
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                                    {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
            except Exception as cdp_error:
                print(f"[警告] 禁用webdriver指纹识别失败: {cdp_error}, 但将继续")

            try:
                print("[窗口] 最大化浏览器窗口")
                driver.maximize_window()
            except Exception as window_error:
                print(f"[警告] 最大化窗口失败: {window_error}, 但将继续")

            try:
                print("[网络] 正在打开淘宝首页...")
                driver.get('https://www.taobao.com')
                print(f"[信息] 页面已加载，标题: {driver.title}")
            except Exception as nav_error:
                print(f"[错误] 打开淘宝首页失败: {nav_error}")
                print("[错误] 网络连接可能有问题，请检查网络设置")
                # 即使打开淘宝首页失败也继续初始化
            
            try:
                print("[等待] 设置页面元素等待超时时间: 20秒")
                wait = WebDriverWait(driver, 20)
                print("[成功] 浏览器已启动，淘宝首页已打开")
            except Exception as wait_error:
                print(f"[警告] 设置等待超时失败: {wait_error}, 但将继续")
            
            print("="*50)
            return True
    except Exception as e:
        print(f"[严重错误] 启动浏览器过程中出现未处理的异常: {str(e)}")
        print("[建议] 请检查Chrome浏览器是否正常安装，或是否已有Chrome正在运行")
        print(f"[建议] 请确认ChromeDriver路径是否正确：{chromedriver_path}")
        # 清理任何可能创建的无效实例
        if driver:
            try:
                driver.quit()
            except:
                pass
            driver = None
    
    print("="*50)
    return browser_initialized  # 返回浏览器初始化状态

def search_goods(keyword):
    """在淘宝首页输入关键词并点击搜索"""
    try:
        print("="*50)
        print(f"[搜索] 正在淘宝首页搜索关键词: {keyword}")
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("[等待] 等待搜索框加载...")
        input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#q")))
        print("[等待] 等待搜索按钮加载...")
        submit = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '#J_TSearchForm > div.search-button > button')
        ))
        
        print("[输入] 在搜索框中输入关键词...")
        input_box.send_keys(keyword)
        print("[点击] 点击搜索按钮...")
        submit.click()
        print("[等待] 等待2秒...")
        time.sleep(2)
        
        # 检查是否有新的标签页打开
        print("[检查] 检查是否有新的标签页打开...")
        current_handles = driver.window_handles
        if len(current_handles) > 1:
            print(f"[发现] 检测到多个标签页: {len(current_handles)}个")
            # 获取当前页面标题
            current_title = driver.title
            print(f"[当前] 当前标签页标题: {current_title}")
            
            # 遍历所有标签页，寻找包含搜索关键词或"搜索"的页面
            for handle in current_handles:
                driver.switch_to.window(handle)
                page_title = driver.title
                print(f"[标签] 检查标签页: {page_title}")
                
                if keyword in page_title or "搜索" in page_title:
                    print(f"[选择] 已切换到搜索结果标签页: {page_title}")
                    break
            else:
                # 如果没有找到匹配的标签页，切换到最后一个标签页（通常是最新打开的）
                driver.switch_to.window(current_handles[-1])
                print(f"[默认] 未找到匹配标签页，切换到最新标签页: {driver.title}")
        else:
            print("[信息] 只有一个标签页，继续使用当前页面")
            
        print("[状态] 搜索完成，正在等待结果加载")
        print("[提示] 如需登录淘宝账号，请在浏览器中完成登录")
        print("="*50)
    except Exception as exc:
        print("="*50)
        print(f"[错误] 搜索操作失败: {str(exc)}")
        print("[建议] 请检查网络连接是否正常，或淘宝网站是否发生变化")
        print("="*50)


def init_search(keyword):
    """初始化搜索，会处理淘宝首页的搜索过程"""
    global is_waiting_login
    try:
        print("="*50, flush=True)
        print(f"[操作] 初始化搜索关键词: {keyword}", flush=True)
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        
        # 始终设置is_waiting_login为True，确保用户需要点击确认登录按钮
        is_waiting_login = True
        print("[状态] 已设置等待登录状态为True，需要用户点击确认登录按钮", flush=True)
        
        # 尝试检查当前页面是否已经是搜索结果页
        current_url = driver.current_url
        current_title = driver.title
        print(f"[状态] 当前页面URL: {current_url}", flush=True)
        print(f"[状态] 当前页面标题: {current_title}", flush=True)
        
        # 判断是否已经在搜索结果页
        if (keyword in current_title and "搜索" in current_title) or "search" in current_url.lower():
            print(f"[状态] 当前页面已经是搜索结果页，无需重新搜索", flush=True)
            # 重新点击搜索以确保结果最新
            try:
                # 尝试在当前页面更新搜索关键词
                input_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#q")))
                input_box.clear()  # 清除现有内容
                input_box.send_keys(keyword)  # 输入新关键词
                
                # 点击搜索按钮
                submit = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, '#J_TSearchForm > div.search-button > button')
                ))
                submit.click()
                print(f"[操作] 已更新搜索关键词为: {keyword}", flush=True)
                time.sleep(2)  # 等待搜索结果加载
            except Exception as e:
                print(f"[警告] 更新搜索关键词失败: {e}，将继续使用当前页面", flush=True)
            
            # 检查是否需要真实登录（仅供参考，但仍然要求用户点击确认按钮）
            actually_needs_login = check_login_required()
            if actually_needs_login:
                print("[提示] 检测到需要登录淘宝账号，请在浏览器中完成登录后点击'确认登录'按钮", flush=True)
            else:
                print("[提示] 未检测到登录需求，但仍需点击'确认登录'按钮继续爬取", flush=True)
            
            # 无论如何，都要求用户点击确认登录按钮
            print("[状态] 等待用户点击确认登录按钮继续爬取", flush=True)
            return True
        
        # 如果不是搜索结果页，则打开淘宝首页并搜索
        print(f"[操作] 当前不是搜索结果页，打开淘宝首页并执行搜索", flush=True)
        
        # 首先尝试打开淘宝首页
        try:
            driver.get('https://www.taobao.com')
            print(f"[打开] 淘宝首页: {driver.title}", flush=True)
        except Exception as nav_error:
            print(f"[错误] 打开淘宝首页失败: {nav_error}", flush=True)
            print("[尝试] 继续使用当前页面进行搜索", flush=True)
        
        # 搜索商品
        search_result = search_goods(keyword)
        
        # 检查是否需要真实登录（仅供参考，但仍然要求用户点击确认按钮）
        actually_needs_login = check_login_required()
        if actually_needs_login:
            print("[提示] 检测到需要登录淘宝账号，请在浏览器中完成登录后点击'确认登录'按钮", flush=True)
        else:
            print("[提示] 未检测到登录需求，但仍需点击'确认登录'按钮继续爬取", flush=True)
        
        # 不管是否真的需要登录，都要求用户确认
        print("[状态] 等待用户点击确认登录按钮继续爬取", flush=True)
        
        return True  # 即使搜索失败也返回True，让用户有机会登录
    except Exception as e:
        print("="*50, flush=True)
        print(f"[错误] 初始化搜索过程中发生异常: {str(e)}", flush=True)
        print("[建议] 请检查网络连接或网站是否正常", flush=True)
        print("="*50, flush=True)
        return False

def confirm_login():
    """确认用户已登录，开始搜索关键词并准备开始爬取数据"""
    global search_keyword, wait, driver, is_waiting_login
    
    # 收到确认登录请求时立即将is_waiting_login设置为False
    is_waiting_login = False
    print("="*50, flush=True)
    print(f"[状态] 确认登录请求已收到，is_waiting_login 已设置为 {is_waiting_login}", flush=True)
    
    if not search_keyword:
        print("[错误] 搜索关键词为空，无法执行搜索", flush=True)
        print("="*50, flush=True)
        return False
    
    try:
        print(f"[操作] 确认登录成功，开始搜索关键词: {search_keyword}", flush=True)
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("="*50, flush=True)
        
        # 执行搜索操作 - 在淘宝中输入关键词并搜索
        print("[操作] 执行搜索关键词", flush=True)
        search_goods(search_keyword)
        
        # 确保当前标签页是搜索结果页
        current_title = driver.title
        print(f"[检查] 当前页面标题: {current_title}", flush=True)
        
        if search_keyword not in current_title and "搜索" not in current_title:
            print("[警告] 当前标签页可能不是搜索结果页，尝试查找正确的标签页...", flush=True)
            found_correct_tab = False
            
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                page_title = driver.title
                print(f"[检查] 标签页标题: {page_title}", flush=True)
                
                if search_keyword in page_title or "搜索" in page_title:
                    print(f"[成功] 已找到并切换到搜索结果标签页: {page_title}", flush=True)
                    found_correct_tab = True
                    break
            
            if not found_correct_tab:
                print("[警告] 未找到匹配的搜索结果标签页，将使用当前页面继续", flush=True)
        else:
            print(f"[确认] 当前标签页是搜索结果页，标题: {current_title}", flush=True)
        
        # 等待搜索结果加载 - 尝试多种选择器
        print("[状态] 正在等待搜索结果加载...", flush=True)
        success = False
        selectors = [
            "div.content--CUnfXXxv",  # 原来的选择器
            "div.items",  # 通用的商品列表选择器
            "div.item",   # 单个商品项选择器
            "div.m-itemlist",  # 老版本的商品列表选择器
            ".J_ItemList",  # 另一个可能的商品列表选择器
            "div.main-content",  # 主内容区域选择器
            "div.doubleCard--gO3Bz6bu"  # 新版淘宝页面结构选择器
        ]
        
        for selector in selectors:
            try:
                print(f"[尝试] 使用选择器: {selector}", flush=True)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                print(f"[成功] 搜索结果加载完成，找到匹配元素: {selector}", flush=True)
                success = True
                break
            except Exception as e:
                print(f"[失败] 选择器 {selector} 未找到匹配元素: {str(e)[:100]}...", flush=True)
                continue
        
        if not success:
            # 如果所有选择器都失败，尝试等待页面中任何商品卡片加载
            try:
                print("[尝试] 使用XPath查找可能的商品元素...", flush=True)
                # 使用XPath选择包含链接和图片的元素
                wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(.//a, '') and contains(.//img, '')]")))
                print("[成功] 通过XPath找到可能的商品元素", flush=True)
                success = True
            except Exception as e:
                print(f"[失败] XPath查找失败: {str(e)[:100]}...", flush=True)
        
        # 检查页面标题，确认是否是搜索结果页
        page_title = driver.title
        print(f"[信息] 当前页面标题: {page_title}", flush=True)
        if not success and "搜索" in page_title:
            print(f"[成功] 通过页面标题确认已到达搜索结果页", flush=True)
            success = True
        
        if success:
            # 保存当前页面源码用于调试
            try:
                save_path = f"crawler_data/taobao_{search_keyword}_page1_{time.strftime('%Y%m%d_%H%M%S')}.html"
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"[诊断] 已保存搜索结果页面源码到: {save_path}", flush=True)
            except Exception as e:
                print(f"[警告] 保存页面源码失败: {str(e)}", flush=True)
                
            print("="*50, flush=True)
            print("[状态] 搜索结果已加载，准备开始爬取数据", flush=True)
            print("[提示] 等待continue_crawl函数执行爬取操作", flush=True)
            print("="*50, flush=True)
            return True
        else:
            print("="*50, flush=True)
            print("[错误] 搜索结果加载失败，请检查网页结构或网络连接", flush=True)
            print("[建议] 请手动检查浏览器中的页面是否正确加载", flush=True)
            print("="*50, flush=True)
            return False
            
    except Exception as e:
        print("="*50, flush=True)
        print(f"[错误] 确认登录后执行搜索失败: {str(e)}", flush=True)
        print("[建议] 请检查网络连接或淘宝网站是否正常", flush=True)
        print("="*50, flush=True)
        return False

def notify_crawl_complete(message, success=True):
    """通知前端爬取已完成，需要用户确认"""
    global crawl_status
    try:
        # 爬取完成后更新状态
        if success:
            crawl_status = "completed"
            status_message = f"爬取已完成：{message}"
        else:
            crawl_status = "error"
            status_message = f"爬取出错：{message}"
            
        print("="*50, flush=True)
        print(f"[通知] {status_message}", flush=True)
        print("[提示] 用户需要点击\"中止爬取\"按钮来结束爬虫进程", flush=True)
        print("="*50, flush=True)
        
        # 保存通知信息到文件，供前端轮询读取
        try:
            with open("crawler_status.json", "w", encoding="utf-8") as f:
                import json
                json.dump({
                    "status": crawl_status,
                    "message": status_message,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "items_count": count - 1 if count > 0 else 0
                }, f, ensure_ascii=False)
        except Exception as e:
            print(f"[错误] 保存爬取状态信息失败: {e}", flush=True)
            
    except Exception as e:
        print(f"[错误] 通知爬取完成失败: {e}", flush=True)

def continue_crawl(page_start, page_end):
    """在用户确认登录后继续爬取过程"""
    global current_page, stop_flag, is_waiting_login
    
    # 在调用之前保证is_waiting_login已经设置为False
    if is_waiting_login:
        print("="*50, flush=True)
        print("[警告] continue_crawl被调用时is_waiting_login仍为True", flush=True)
        print("[操作] 强制设置is_waiting_login为False", flush=True)
        is_waiting_login = False
        print("="*50, flush=True)
    
    def crawl_thread():
        try:
            # 在线程函数中需要声明使用外部的全局变量
            global current_page, count, search_keyword, crawl_status
            
            # 设置爬虫状态为运行中
            crawl_status = "running"
            
            print("="*50, flush=True)
            print(f"[开始] 数据爬取线程启动", flush=True)
            print(f"[范围] 爬取页面: {page_start} 至 {page_end}", flush=True)
            print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
            print("="*50, flush=True)
            
            # 确保当前标签页是搜索结果页
            print("[检查] 确保当前标签页是搜索结果页", flush=True)
            current_title = driver.title
            print(f"[当前] 页面标题: {current_title}", flush=True)
            
            if search_keyword not in current_title and "搜索" not in current_title:
                print("[警告] 当前可能不是搜索结果页，尝试查找正确的标签页", flush=True)
                found_correct_tab = False
                
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    page_title = driver.title
                    print(f"[检查] 标签页: {page_title}", flush=True)
                    
                    if search_keyword in page_title or "搜索" in page_title:
                        print(f"[成功] 已切换到正确的搜索结果页: {page_title}", flush=True)
                        found_correct_tab = True
                        break
                
                if not found_correct_tab:
                    print("[错误] 未找到搜索结果页面，爬取可能会失败", flush=True)
                    print("[尝试] 尝试重新搜索关键词...", flush=True)
                    
                    # 尝试重新搜索
                    try:
                        # 切换到第一个标签页（通常是淘宝首页）
                        driver.switch_to.window(driver.window_handles[0])
                        search_goods(search_keyword)
                        print("[恢复] 已重新执行搜索操作", flush=True)
                    except Exception as search_error:
                        print(f"[失败] 重新搜索失败: {str(search_error)}", flush=True)
                        print("[警告] 将继续使用当前页面，但可能无法正确爬取数据", flush=True)
            else:
                print(f"[确认] 当前正在搜索结果页: {current_title}", flush=True)
            
            # 如果不是从第1页开始，需要跳转到指定页
            if page_start > 1:
                print(f"[操作] 准备跳转到指定起始页: {page_start}", flush=True)
                turn_pageStart(page_start)
                current_page = page_start
            else:
                current_page = 1
                
            # 开始爬取数据
            print(f"[操作] 开始爬取第 {current_page} 页数据", flush=True)
            get_goods(current_page)
            
            # 继续爬取后续页面
            total_pages = page_end - current_page
            current_idx = 0
            max_retry = 3  # 每页翻页最大尝试次数
            
            for page in range(current_page + 1, page_end + 1):
                if stop_flag:
                    print("="*50, flush=True)
                    print("[中止] 检测到停止标志，提前终止爬虫流程", flush=True)
                    print("="*50, flush=True)
                    notify_crawl_complete(f"用户手动中止了爬取，已完成到第 {current_page} 页", success=False)
                    break
                    
                current_idx += 1
                print("="*50, flush=True)
                print(f"[进度] 正在处理第 {current_idx}/{total_pages} 页 (第 {page} 页)", flush=True)
                print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
                print("="*50, flush=True)
                
                # 尝试翻页并验证是否成功
                page_turning_success = False
                retry_count = 0
                
                while not page_turning_success and retry_count < max_retry:
                    if retry_count > 0:
                        print(f"[重试] 第 {retry_count} 次尝试翻页到第 {page} 页", flush=True)
                    
                    # 调用翻页函数，现在它会返回一个布尔值表示是否真正翻页
                    page_turning_success = page_turning(page)
                    
                    if not page_turning_success:
                        retry_count += 1
                        print(f"[警告] 翻页可能未成功，页面内容未变化 (尝试 {retry_count}/{max_retry})", flush=True)
                        
                        if retry_count < max_retry:
                            print("[恢复] 尝试使用其他方法翻页...", flush=True)
                            
                            # 使用更直接的方法尝试跳转
                            try:
                                # 尝试直接跳转到指定页码
                                turn_pageStart(page)
                                # 等待页面加载
                                time.sleep(5)
                                
                                # 检查URL是否含有页码参数，作为简单验证
                                if "page=" in driver.current_url or "s=" in driver.current_url:
                                    print("[成功] 通过直接跳转到达新页面", flush=True)
                                    page_turning_success = True
                                else:
                                    print("[警告] 直接跳转后URL无明显页码参数", flush=True)
                            except Exception as e:
                                print(f"[错误] 直接跳转失败: {str(e)}", flush=True)
                            
                            # 如果仍然失败，尝试直接修改URL
                            if not page_turning_success:
                                try:
                                    current_url = driver.current_url
                                    if "s=" in current_url:
                                        import re
                                        s_match = re.search(r's=(\d+)', current_url)
                                        if s_match:
                                            s_value = int(s_match.group(1))
                                            # 强制设置为下一页对应的s值
                                            new_s = (page - 1) * 44  # 假设每页44个商品
                                            new_url = re.sub(r's=\d+', f's={new_s}', current_url)
                                            print(f"[尝试] 直接修改URL参数: {new_url}", flush=True)
                                            driver.get(new_url)
                                            time.sleep(5)
                                            page_turning_success = True
                                except Exception as e:
                                    print(f"[错误] 通过URL修改翻页失败: {str(e)}", flush=True)
                    else:
                        print(f"[成功] 已成功翻页到第 {page} 页", flush=True)
                
                if not page_turning_success:
                    print(f"[错误] 无法翻页到第 {page} 页，尝试了{max_retry}次均失败", flush=True)
                    print("[决定] 将终止爬取过程", flush=True)
                    notify_crawl_complete(f"翻页失败，无法继续爬取。已成功爬取到第 {current_page} 页", success=False)
                    break
                
                # 更新当前页码
                current_page = page
                
                # 爬取新页面数据
                get_goods(current_page)
            
            # 完成爬取，打印统计信息
            print("="*50, flush=True)
            print("="*50, flush=True)
            print("[完成] 产品数据爬取完毕，已保存到MySQL数据库", flush=True)
            print(f"[统计] 共爬取 {count-1} 条商品数据", flush=True)
            print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
            print("="*50, flush=True)
            print("="*50, flush=True)
            
            # 发送爬取完成通知
            notify_crawl_complete(f"所有页面爬取完成，共爬取 {count-1} 条商品数据")
            
        except Exception as e:
            print("="*50, flush=True)
            print(f"[错误] 爬虫线程执行过程中出现异常: {str(e)}", flush=True)
            print("="*50, flush=True)
            
            # 发送错误通知
            notify_crawl_complete(f"爬取过程出错: {str(e)}", success=False)
            
            # 确保状态更新
            crawl_status = "error"
    
    # 启动新线程执行爬取过程
    thread = threading.Thread(target=crawl_thread)
    thread.daemon = True
    thread.start()
    print(f"[信息] 已在后台启动数据爬取线程，爬取页面 {page_start} 至 {page_end}", flush=True)
    return True

def close_browser():
    """关闭浏览器并重置全局变量"""
    global driver, wait, stop_flag, is_waiting_login, current_page, count, crawl_status
    try:
        print("="*50)
        print("[操作] 正在关闭浏览器...")
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[状态] 当前爬虫状态: {crawl_status}")
        
        # 先设置停止标志，确保所有爬取线程能够检测到并停止
        stop_flag = True
        
        # 关闭数据库连接
        if db_conn and db_conn.open:
            try:
                db_conn.close()
                print("[数据库] 数据库连接已关闭")
            except Exception as e:
                print(f"[警告] 关闭数据库连接出错: {str(e)}")
        
        # 关闭浏览器
        if driver:
            try:
                # 先关闭所有非主标签页
                if len(driver.window_handles) > 1:
                    print(f"[浏览器] 检测到 {len(driver.window_handles)} 个标签页，正在逐个关闭...")
                    main_handle = driver.window_handles[0]
                    for handle in driver.window_handles[1:]:
                        try:
                            driver.switch_to.window(handle)
                            driver.close()
                            print(f"[浏览器] 已关闭一个标签页")
                        except Exception as e:
                            print(f"[警告] 关闭标签页出错: {str(e)}")
                    # 切回主标签页
                    driver.switch_to.window(main_handle)
                
                # 最后退出浏览器
                driver.quit()
                print("[浏览器] 浏览器已完全关闭")
                
                # 清理可能的残留进程（仅适用于Windows）
                try:
                    # 尝试终止可能的残留chromedriver进程
                    import subprocess
                    subprocess.run("taskkill /f /im chromedriver.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except:
                    pass  # 忽略可能的错误
            except Exception as e:
                print(f"[警告] 关闭浏览器出错: {str(e)}")
        
        # 重置全局变量
        driver = None
        wait = None
        is_waiting_login = False
        current_page = 1
        # 如果爬虫状态是running，设置为completed来表示手动结束
        if crawl_status == "running":
            crawl_status = "completed"
        print("[状态] 所有全局状态已重置")
        print("="*50)
        return True
    except Exception as e:
        print("="*50)
        print(f"[错误] 关闭浏览器过程中发生异常: {str(e)}")
        # 强制清理状态
        driver = None
        wait = None
        print("="*50)
        return False

def start_crawl(keyword, page_start, page_end):
    """开始爬取过程，先初始化浏览器然后执行搜索"""
    global search_keyword, current_page, crawl_status, driver, stop_flag
    try:
        print("="*50, flush=True)
        print(f"[开始] 淘宝商品爬虫启动", flush=True)
        print(f"[参数] 关键词: {keyword}, 页面范围: {page_start} - {page_end}", flush=True)
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        
        # 确保stop_flag为False
        stop_flag = False
        
        # 重置状态变量
        search_keyword = keyword
        current_page = 0  # 确保从0开始，因为后续会增加到1
        crawl_status = "running"
        
        # 创建必要的目录
        for dir_path in ["crawler_data", "crawler_debug"]:
            try:
                os.makedirs(dir_path, exist_ok=True)
            except Exception as e:
                print(f"[警告] 创建目录 {dir_path} 失败: {e}", flush=True)
        
        # 检查浏览器是否已经初始化
        if driver is None:
            print("[状态] 浏览器未初始化，正在设置...", flush=True)
            try:
                setup_result = setup_browser()
                if not setup_result:
                    print("[警告] 浏览器设置返回失败状态，但将尝试继续爬取", flush=True)
                    # 如果设置浏览器失败，返回False中止爬取
                    return False
                else:
                    print("[状态] 浏览器已成功设置", flush=True)
            except Exception as browser_error:
                print(f"[警告] 浏览器设置出现异常: {str(browser_error)}", flush=True)
                print("[警告] 无法继续爬取，请重试", flush=True)
                return False
        else:
            print("[状态] 浏览器已初始化，重用现有浏览器", flush=True)
            # 验证浏览器是否仍然可用
            try:
                current_url = driver.current_url
                print(f"[状态] 当前浏览器URL: {current_url}", flush=True)
            except Exception as e:
                print(f"[警告] 现有浏览器实例已失效: {e}", flush=True)
                print("[状态] 尝试重新初始化浏览器...", flush=True)
                try:
                    driver = None  # 重置driver变量
                    setup_result = setup_browser()
                    if not setup_result:
                        print("[错误] 重新初始化浏览器失败，无法继续爬取", flush=True)
                        return False
                    print("[状态] 浏览器已成功重新初始化", flush=True)
                except Exception as reinit_error:
                    print(f"[错误] 重新初始化浏览器出现异常: {str(reinit_error)}", flush=True)
                    return False
        
        # 定义初始化线程函数
        def init_thread():
            try:
                print("[线程] 爬虫初始化线程已启动", flush=True)
                # 初始化搜索
                if not init_search(keyword):
                    print("[错误] 初始化搜索失败", flush=True)
                    return False
                
                # 只设置等待状态，但不要继续爬取
                # 无论如何都要等待用户点击确认登录按钮
                if is_waiting_login:
                    print("[状态] 等待用户登录，爬虫暂停", flush=True)
                    print("="*50, flush=True)
                    return True
                else:
                    # 这段逻辑不会被执行，因为init_search总是会设置is_waiting_login为True
                    # 不要在这里执行continue_crawl
                    print("[状态] 无需登录，仍然需要用户点击确认登录按钮", flush=True)
                    return True
            except Exception as e:
                print("="*50, flush=True)
                print(f"[错误] 初始化线程发生异常: {str(e)}", flush=True)
                print("="*50, flush=True)
                return False
        
        # 启动初始化线程
        thread = threading.Thread(target=init_thread)
        thread.daemon = True
        thread.start()
    
        print(f"[信息] 爬虫已在后台启动，正在初始化搜索...", flush=True)
        print(f"[提示] 如需登录淘宝账号，请在浏览器中完成操作", flush=True)
        print("="*50, flush=True)
        return True
    except Exception as e:
        print("="*50, flush=True)
        print(f"[错误] 启动爬虫时发生异常: {str(e)}", flush=True)
        print("="*50, flush=True)
        return False

def stop_crawling():
    """
    设置停止标志，停止爬虫流程。
    """
    global stop_flag, db_conn
    
    print("="*50, flush=True)
    print("[操作] 正在停止爬虫...", flush=True)
    print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    
    stop_flag = True
    print("[状态] 停止标志已设置为 True", flush=True)
    print("[信息] 爬虫将在当前页处理完毕后终止", flush=True)
    print("="*50, flush=True)
    
    return True

def get_goods(page):
    """
    解析当前页面的商品数据，并直接保存到MySQL数据库。
    使用特定的选择器提取淘宝商品信息。
    """
    global count, db_conn, search_keyword
    try:
        print("="*50, flush=True)
        print(f"[爬取] 当前处理第 {page} 页", flush=True)
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print("[操作] 获取页面源码并解析...", flush=True)
        
        # 获取页面源码
        html = driver.page_source
        doc = pq(html)
        
        # 尝试多种选择器以适应不同的淘宝页面结构
        selectors = [
            'div.content--CUnfXXxv > div > div',  # 原选择器
            'div[data-index]',                    # 备用选择器1
            'div.doubleCard--gO3Bz6bu',          # 新版淘宝页面结构选择器
            'a.doubleCardWrapperAdapt--mEcC7olq', # 新版淘宝卡片包装选择器
            'div.tbpc-col a[data-spm-protocol="i"]', # 新版淘宝行项目选择器
            'div.item',                          # 通用商品项选择器
            'div.J_MouserOnverReq'               # 经典淘宝商品项选择器
        ]

        items = []
        used_selector = ""
        
        # 尝试所有选择器直到找到商品项
        for selector in selectors:
            print(f"[查找] 尝试使用选择器 '{selector}' 查找商品元素...", flush=True)
            items_found = list(doc(selector).items())
            if items_found:
                items = items_found
                used_selector = selector
                print(f"[成功] 使用选择器 '{selector}' 找到 {len(items)} 个商品", flush=True)
                break
                
        if not items:
                print("[警告] 未找到任何商品，尝试诊断页面...", flush=True)
                try:
                    # 保存截图和HTML用于诊断
                    screenshot_path = f"search_page_{page}.png"
                    driver.save_screenshot(screenshot_path)
                    print(f"[诊断] 已保存页面截图到 {screenshot_path}", flush=True)
                    
                    html_path = f"search_page_{page}.html"
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"[诊断] 已保存页面HTML到 {html_path}", flush=True)
                    
                    # 检查淘宝是否显示验证码或登录提示
                    if "验证码" in html or "滑块" in html:
                        print("[警告] 检测到可能的验证码或滑块，请人工处理", flush=True)
                    if "登录" in html and "密码" in html:
                        print("[警告] 检测到登录页面，可能需要重新登录", flush=True)
                    
                    # 如果没有商品，可能是其他原因阻止了爬取
                    global is_waiting_login
                    if "登录" in html:
                        is_waiting_login = True
                        print("[状态] 检测到需要登录，已更新is_waiting_login = True", flush=True)
                except Exception as e:
                    print(f"[错误] 诊断过程出错: {e}", flush=True)
                
                print("[操作] 尝试刷新页面后重试...", flush=True)
                driver.refresh()
                time.sleep(5)
                print("="*50, flush=True)
                return
        
        # 确保数据库连接
        if db_conn is None or not db_conn.open:
            print("[数据库] 重新建立数据库连接...", flush=True)
            connect_to_db()
            
        cursor = db_conn.cursor()
        products_saved = 0
        total_items = len(items)
        print(f"[开始] 处理 {total_items} 个商品数据...", flush=True)
        
        # 根据使用的选择器选择合适的数据提取方法
        for i, item in enumerate(items):
            # 打印进度
            if i % 5 == 0 or i == total_items - 1:
                print(f"[进度] 正在处理第 {i+1}/{total_items} 个商品 ({((i+1)/total_items*100):.1f}%)", flush=True)
            
            try:
                # 根据不同的页面结构，尝试不同的选择器提取数据
                if used_selector == 'div.doubleCard--gO3Bz6bu' or used_selector == 'a.doubleCardWrapperAdapt--mEcC7olq' or used_selector.startswith('div.tbpc-col'):
                    # 新版淘宝页面结构
                    title = item.find('.title--qJ7Xg_90 span').text()
                    price_int = item.find('.priceInt--yqqZMJ5a').text()
                    price_float = item.find('.priceFloat--XpixvyQ1').text()
                    price = price_int + price_float if price_int and price_float else price_int or "0"
                    
                    deal = item.find('.realSales--XZJiepmt').text()
                    if deal:
                        deal = deal.replace("万", "0000").split("人")[0].split("+")[0]
                    else:
                        deal = "0"
                        
                    location = item.find('.procity--wlcT2xH9 span').text()
                    shop = item.find('.shopNameText--DmtlsDKm').text()
                    
                    shipping_text = item.find('.subIconWrapper--Vl8zAdQn').text()
                    postText = "包邮" if shipping_text and "包邮" in shipping_text else "/"
                    
                    # 提取URL和图片
                    if used_selector == 'a.doubleCardWrapperAdapt--mEcC7olq':
                        t_url = item.attr('href') or ""
                    else:
                        t_url = item.find('a.doubleCardWrapperAdapt--mEcC7olq').attr('href') or ""
                    
                    shop_url = item.find('.shopName--hdF527QA').attr('href') or ""
                    img_url = item.find('img.mainPic--Ds3X7I8z').attr('src') or ""
                else:
                    # 原始淘宝页面结构
                    title = item.find('.title--qJ7Xg_90 span').text()
                    if not title:
                        print(f"[尝试] 第 {i+1} 个商品标题提取失败，尝试备用选择器...", flush=True)
                        title_elems = item.find('a.title') or item.find('.title')
                        if title_elems:
                            title = title_elems.text() or title_elems.attr('title') or ""
                    
                    price_int = item.find('.priceInt--yqqZMJ5a').text()
                    price_float = item.find('.priceFloat--XpixvyQ1').text()
                    price = price_int + price_float if price_int and price_float else "0"
                    
                    deal = item.find('.realSales--XZJiepmt').text()
                    if deal:
                        deal = deal.replace("万", "0000").split("人")[0].split("+")[0]
                    else:
                        deal = "0"
                        
                    location = item.find('.procity--wlcT2xH9 span').text()
                    shop = item.find('.shopNameText--DmtlsDKm').text()
                    
                    shipping_text = item.find('.subIconWrapper--Vl8zAdQn').text()
                    postText = "包邮" if shipping_text and "包邮" in shipping_text else "/"
                    
                    # 提取URL和图片
                    t_url = item.find('.doubleCardWrapperAdapt--mEcC7olq').attr('href') or ""
                    shop_url = item.find('.TextAndPic--grkZAtsC a').attr('href') or ""
                    img_url = item.find('img.mainPic--Ds3X7I8z').attr('src') or ""
                
                # 如果标题为空，尝试通用选择器
                if not title:
                    print(f"[尝试] 商品 {i+1} 标题提取失败，尝试通用选择器", flush=True)
                    title = item.find('div[class*="title"] span').text() or item.find('div[class*="title"]').text() or ""
                    
                if not title:
                    print(f"[跳过] 无法提取第 {i+1} 个商品的标题，跳过", flush=True)
                    continue
            
                # 补全URL
                if t_url and t_url.startswith("//"):
                    t_url = "https:" + t_url
                if shop_url and shop_url.startswith("//"):
                    shop_url = "https:" + shop_url
                if img_url and img_url.startswith("//"):
                    img_url = "https:" + img_url
                
                # 调试信息
                print(f"[信息] 商品 {i+1}: 标题={title[:20]}..., 价格={price}, 销量={deal}", flush=True)
                    
                # 检查数据有效性，价格为必须字段
                if price == "0" or not price:
                    print(f"[警告] 商品 {i+1} 价格提取失败，尝试提取页面上的价格字符...", flush=True)
                    price_text = item.text()
                    # 尝试从文本中提取价格 (¥后面的数字)
                    import re
                    price_match = re.search(r'¥\s*(\d+(?:\.\d+)?)', price_text)
                    if price_match:
                        price = price_match.group(1)
                        print(f"[恢复] 从文本中提取到价格: {price}", flush=True)
                    else:
                        price = "0"
            
            # 直接插入到数据库表
                # 插入到taobao_products表
                cursor.execute("""
                    INSERT INTO taobao_products 
                    (item_id, title, price, sales, location, shop_name, free_shipping, product_url, shop_url, image_url, search_keyword)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, 
                    (count, title, float(price) if price and price != "0" else 0, 
                    int(deal) if deal and deal.isdigit() else 0, 
                    location, shop, postText, t_url, shop_url, img_url, search_keyword)
                )
                
                # 同时插入到taobao_data表
                cursor.execute("""
                    INSERT INTO taobao_data 
                    (title, price, deal_count, location, shop_name, post_text, title_url, shop_url, img_url, comment_total, comment_fetched)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, 
                    (title, float(price) if price and price != "0" else 0, 
                    int(deal) if deal and deal.isdigit() else 0, 
                    location, shop, postText, t_url, shop_url, img_url, 0, 0)
                )
                
                count += 1
                products_saved += 1
                if products_saved % 5 == 0 or products_saved == total_items:
                    print(f"[存储] 已成功保存 {products_saved}/{total_items} 个商品到数据库", flush=True)
            except Exception as e:
                print(f"[错误] 处理或保存商品时出错: {str(e)}", flush=True)
                continue
        
        # 提交事务
        db_conn.commit()
        print("="*50, flush=True)
    except Exception as e:
        print(f"[错误] 获取商品数据失败: {str(e)}", flush=True)
        print("="*50, flush=True)


def page_turning(page_number):
    """翻页至下一页"""
    global wait, driver, current_page
    try:
        print("="*50, flush=True)
        print(f"[翻页] 正在翻页到第 {page_number} 页", flush=True)
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        
        # 获取并记录当前页码，确保我们知道翻页前的状态
        actual_current_page = get_current_page_number()
        print(f"[记录] 翻页前实际页码为: {actual_current_page}, 目标页码为: {page_number}", flush=True)
        
        # 如果当前页面已经是目标页码，则不需要翻页
        if actual_current_page == page_number:
            print(f"[提示] 当前页面已经是第 {page_number} 页，无需翻页", flush=True)
            current_page = page_number  # 确保全局变量更新
            return True
        
        # 获取翻页前的第一个商品标题和URL，用于后续验证是否真的翻页了
        prev_page_items = []
        try:
            html_before = driver.page_source
            doc_before = pq(html_before)
            # 获取当前页面的前3个商品标题和URL
            selectors = [
                'div.content--CUnfXXxv > div > div',
                'div[data-index]',
                'div.doubleCard--gO3Bz6bu',
                'a.doubleCardWrapperAdapt--mEcC7olq',
                'div.tbpc-col a[data-spm-protocol="i"]',
                'div.item',
                'div.J_MouserOnverReq'
            ]
            
            # 先保存当前em元素内的页码，用于验证翻页前
            current_em_page = "unknown"
            try:
                em_elements = driver.find_elements(By.XPATH, "//em[contains(@data-spm-anchor-id, 'a21n57.1.0.i')]")
                if em_elements:
                    current_em_page = em_elements[0].text.strip()
                    print(f"[当前] <em>元素显示的当前页码: {current_em_page}", flush=True)
            except Exception as e:
                print(f"[警告] 获取当前<em>元素页码失败: {e}", flush=True)
                
            for selector in selectors:
                items = list(doc_before(selector).items())
                if items:
                    for i, item in enumerate(items[:3]):  # 只取前3个
                        title = item.find('.title--qJ7Xg_90 span').text() or item.text()
                        url = item.find('a').attr('href') or item.attr('href') or ""
                        if title or url:
                            prev_page_items.append((title[:20], url[:30]))
                    if prev_page_items:
                        print(f"[验证] 翻页前获取到 {len(prev_page_items)} 个商品信息用于比对", flush=True)
                        break
        except Exception as e:
            print(f"[警告] 获取翻页前商品信息失败: {e}", flush=True)

        # 滚动到页面底部，确保分页元素可见
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(1, 2))
        
        # 先获取可能需要保存的信息
        try:
            screenshot_path = f"crawler_debug/page_{page_number-1}_before_turning.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            driver.save_screenshot(screenshot_path)
            print(f"[调试] 已保存翻页前截图: {screenshot_path}", flush=True)
        except Exception as e:
            print(f"[警告] 保存截图失败: {e}", flush=True)
        
        # 尝试各种翻页方式
        clicked = False  # 标记是否成功点击了翻页按钮
        
        # 方式1: 直接尝试查找并点击目标页码按钮
        try:
            print("[尝试] 查找并点击目标页码按钮", flush=True)
            # 查找包含目标页码的按钮
            page_buttons = driver.find_elements(By.XPATH, f"//button[text()='{page_number}'] | //a[text()='{page_number}'] | //li[text()='{page_number}']")
            
            if page_buttons:
                for button in page_buttons:
                    try:
                        print(f"[找到] 页码按钮: {button.text.strip()}", flush=True)
                        driver.execute_script("arguments[0].click();", button)
                        print(f"[点击] 已点击页码按钮: {page_number}", flush=True)
                        clicked = True
                        time.sleep(3)  # 等待页面加载
                        
                        # 验证页码是否变化
                        if confirm_page_change(page_number):
                            print(f"[成功] 已成功通过直接点击页码按钮翻到第 {page_number} 页", flush=True)
                            return True
                        break
                    except Exception as e:
                        print(f"[失败] 点击页码按钮出错: {e}", flush=True)
        except Exception as e:
            print(f"[警告] 尝试直接点击页码按钮失败: {e}", flush=True)
        
        # 方式2: 使用"下一页"按钮
        if not clicked or get_current_page_number() != page_number:
            try:
                print("[尝试] 使用下一页按钮翻页", flush=True)
                next_page_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '下一页')] | //a[contains(text(), '下一页')] | //span[contains(@class, 'next-btn-helper')]/ancestor::button | //span[contains(@class, 'next-btn-helper')]/ancestor::a | //span[text()='下一页']/parent::*")
                
                if next_page_btns:
                    for btn in next_page_btns:
                        try:
                            print(f"[找到] 下一页按钮: {btn.tag_name} - {btn.text.strip() or '无文本'}", flush=True)
                            driver.execute_script("arguments[0].click();", btn)
                            print("[点击] 已点击下一页按钮", flush=True)
                            clicked = True
                            time.sleep(3)  # 等待页面加载
                            
                            # 验证页码是否变化
                            if confirm_page_change(page_number):
                                print(f"[成功] 已成功通过下一页按钮翻到第 {page_number} 页", flush=True)
                                return True
                            break
                        except Exception as e:
                            print(f"[失败] 点击下一页按钮出错: {e}", flush=True)
            except Exception as e:
                print(f"[警告] 尝试使用下一页按钮失败: {e}", flush=True)
        
        # 方式3: 使用页码输入框跳转
        if not clicked or get_current_page_number() != page_number:
            try:
                print("[尝试] 使用页码输入框跳转", flush=True)
                result = turn_pageStart(page_number)
                time.sleep(3)  # 等待页面加载
                
                # 验证页码是否变化
                if confirm_page_change(page_number):
                    print(f"[成功] 已成功通过页码输入框跳转到第 {page_number} 页", flush=True)
                    return True
            except Exception as e:
                print(f"[警告] 使用页码输入框跳转失败: {e}", flush=True)
        
        # 如果所有方法都失败，但至少尝试了翻页，再次检查页码
        if clicked:
            # 再次获取并确认当前页码
            final_page = get_current_page_number()
            if final_page != actual_current_page:
                print(f"[注意] 页面已改变，但不是目标页码。原页码: {actual_current_page}, 当前页码: {final_page}, 目标页码: {page_number}", flush=True)
                return True  # 页面确实变化了，虽然不是目标页
            else:
                print(f"[失败] 所有翻页方法都尝试了，但页码未变化。当前仍然是第 {final_page} 页", flush=True)
                return False
        else:
            print("[失败] 未能点击任何翻页按钮", flush=True)
            return False
            
    except Exception as exc:
        print(f"[错误] 翻页过程中出现异常: {str(exc)}", flush=True)
        print("[失败] 翻页未成功", flush=True)
        return False


def turn_pageStart(page_number):
    """
    通过页码输入框直接跳转到指定页
    """
    global wait, driver, current_page
    try:
        print("="*50, flush=True)
        print(f"[跳转] 尝试直接跳转到第 {page_number} 页", flush=True)
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        
        # 滚动到页面底部，确保分页元素可见
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(1, 2))
        
        # 获取并记录当前页码，确保我们知道跳转前的状态
        actual_current_page = get_current_page_number()
        print(f"[记录] 跳转前实际页码为: {actual_current_page}, 目标页码为: {page_number}", flush=True)
        
        # 如果当前页面已经是目标页码，则不需要跳转
        if actual_current_page == page_number:
            print(f"[提示] 当前页面已经是第 {page_number} 页，无需跳转", flush=True)
            current_page = page_number  # 确保全局变量更新
            return True
        
        # 尝试找到页码输入框和跳转按钮 - 使用淘宝特定的选择器
        try:
            # 使用用户提供的精确选择器
            input_selectors = [
                "//span[contains(@class, 'next-pagination-jump-input')]/input",
                "//input[@aria-label='请输入跳转到第几页']",
                # 保留通用选择器作为备用
                "//input[@type='text' and contains(@class, 'page')]",
                "//input[contains(@placeholder, '页码')]",
                "//input[contains(@class, 'jump')]",
                "//input[contains(@class, 'pagination')]"
            ]
            
            # 精确的确认按钮选择器
            confirm_button_selectors = [
                "//button[contains(@class, 'next-pagination-jump-go')]",
                "//span[contains(@class, 'next-btn-helper') and contains(text(), '确定')]/parent::button",
                # 备用通用选择器
                "//button[contains(text(), '确定') or contains(text(), '跳转')]",
                "//span[contains(text(), '确定') or contains(text(), '跳转')]/parent::button"
            ]
            
            input_found = False
            input_elem = None
            
            # 首先尝试找到输入框
            for selector in input_selectors:
                inputs = driver.find_elements(By.XPATH, selector)
                if inputs:
                    for inp in inputs:
                        try:
                            print(f"[找到] 页码输入框: {inp.get_attribute('class') or 'unknown class'}", flush=True)
                            # 清除输入框并输入页码
                            inp.clear()
                            inp.send_keys(str(page_number))
                            input_found = True
                            input_elem = inp
                            print(f"[输入] 已在输入框中输入页码: {page_number}", flush=True)
                            break
                        except Exception as e:
                            print(f"[失败] 操作输入框失败: {e}", flush=True)
                
                if input_found:
                    break
            
            # 如果找到了输入框，尝试点击确认按钮
            if input_found and input_elem:
                confirm_clicked = False
                
                # 尝试所有确认按钮选择器
                for btn_selector in confirm_button_selectors:
                    confirm_buttons = driver.find_elements(By.XPATH, btn_selector)
                    if confirm_buttons:
                        for btn in confirm_buttons:
                            try:
                                print(f"[找到] 跳转确认按钮: {btn.text.strip() or '无文本'}, 类: {btn.get_attribute('class') or 'unknown'}", flush=True)
                                driver.execute_script("arguments[0].click();", btn)
                                print(f"[点击] 已点击跳转确认按钮", flush=True)
                                confirm_clicked = True
                                time.sleep(3)  # 等待页面加载
                                
                                # 验证页码是否变化
                                if confirm_page_change(page_number):
                                    print(f"[成功] 已成功通过页码输入框跳转到第 {page_number} 页", flush=True)
                                    return True
                                break
                            except Exception as e:
                                print(f"[失败] 点击跳转按钮失败: {e}", flush=True)
                    
                    if confirm_clicked:
                        break
                
                # 如果未找到或点击失败，尝试按Enter键
                if not confirm_clicked:
                    try:
                        print("[尝试] 没有找到确认按钮或点击失败，尝试按Enter键", flush=True)
                        input_elem.send_keys(Keys.ENTER)
                        time.sleep(3)  # 等待页面加载
                        
                        # 验证页码是否变化
                        if confirm_page_change(page_number):
                            print(f"[成功] 已成功通过Enter键跳转到第 {page_number} 页", flush=True)
                            return True
                    except Exception as e:
                        print(f"[失败] Enter键跳转失败: {e}", flush=True)
            else:
                print("[警告] 未找到页码输入框", flush=True)
        
        except Exception as e:
            print(f"[警告] 查找页码输入框失败: {e}", flush=True)
        
        # 如果常规方法失败，尝试使用JavaScript直接修改URL
        try:
            print("[尝试] 使用JavaScript直接修改URL参数", flush=True)
            current_url = driver.current_url
            if "s=" in current_url:
                import re
                # 计算s参数的值，通常是(页码-1)*每页商品数
                new_s_value = (page_number - 1) * 44  # 假设每页44个商品
                new_url = re.sub(r's=(\d+)', f's={new_s_value}', current_url)
                
                if new_url != current_url:
                    print(f"[URL] 修改URL参数: {current_url} -> {new_url}", flush=True)
                    driver.get(new_url)
                    time.sleep(3)  # 等待页面加载
                    
                    # 验证页码是否变化
                    if confirm_page_change(page_number):
                        print(f"[成功] 已成功通过修改URL跳转到第 {page_number} 页", flush=True)
                        return True
        except Exception as e:
            print(f"[警告] JavaScript修改URL失败: {e}", flush=True)
        
        # 如果所有方法都失败，返回失败
        print("[失败] 所有跳转方法都尝试了，但未能成功跳转", flush=True)
        return False
    except Exception as e:
        print(f"[错误] 页码跳转过程中出现异常: {str(e)}", flush=True)
        return False

def crawler_from_page(pageStart, pageEnd):
    """
    根据起始页和终止页爬取商品数据，并保存到MySQL数据库。
    如果在爬虫过程中触发了停止标志，则提前退出并保存当前数据。
    """
    global count, csv_rows, current_page, search_keyword, filename, stop_flag, db_conn
    header = ['序号', '商品名称', '价格', '成交量', '商家位置', '商家名称', '是否包邮', 'Title_URL', 'Shop_URL',
              'Img_URL', '评论']
    csv_rows.append(header)
    count += 1  # 表头占用一行

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.content--CUnfXXxv")))
        print("搜索结果加载成功。")
    except Exception as e:
        print("搜索结果加载超时：", e)

    if pageStart != 1:
        turn_pageStart(pageStart)
        current_page = pageStart
    else:
        current_page = 1

    get_goods(current_page)
    for page in range(current_page + 1, pageEnd + 1):
        if stop_flag:
            print("检测到停止标志，提前终止爬虫流程。")
            break
        page_turning(page)
        current_page = page
        get_goods(current_page)

    # 数据已经存储在 csv_rows 中，现在将其保存到MySQL
    filename = "{}_{}_FromTB.csv".format(search_keyword, time.strftime('%Y%m%d-%H%M', time.localtime(time.time())))
    save_to_mysql()
    print("产品数据爬取完毕，已保存到MySQL数据库")
    return filename


def connect_to_db():
    """连接到MySQL数据库并创建所需的表"""
    global db_conn
    try:
        print("="*50)
        print("[数据库] 正在连接MySQL数据库...")
        print(f"[配置] 主机: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"[配置] 数据库: {DB_CONFIG['database']}")
        print(f"[配置] 用户名: {DB_CONFIG['user']}")
        print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 首先检查MySQL服务是否运行
        try:
            temp_conn = pymysql.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                port=DB_CONFIG['port']
            )
            print("[成功] MySQL服务连接成功")
            temp_conn.close()
        except Exception as e:
            print(f"[错误] MySQL服务连接失败: {str(e)}")
            raise Exception("MySQL服务未运行或连接被拒绝")
            
        # 检查数据库是否存在，如果不存在则创建
        try:
            # 连接到MySQL服务器
            temp_conn = pymysql.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                port=DB_CONFIG['port']
            )
            temp_cursor = temp_conn.cursor()
            
            # 检查数据库是否存在
            temp_cursor.execute(f"SHOW DATABASES LIKE '{DB_CONFIG['database']}'")
            if not temp_cursor.fetchone():
                print(f"[信息] 数据库'{DB_CONFIG['database']}'不存在，尝试创建...")
                try:
                    temp_cursor.execute(f"CREATE DATABASE {DB_CONFIG['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    print(f"[成功] 已创建数据库: {DB_CONFIG['database']}")
                except Exception as e:
                    print(f"[错误] 创建数据库失败: {str(e)}")
                    if "denied" in str(e).lower():
                        print("[诊断] 您的MySQL用户没有创建数据库的权限")
                        print("[建议] 请使用管理员账户登录MySQL并执行以下命令:")
                        print(f"     CREATE DATABASE {DB_CONFIG['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                        print(f"     GRANT ALL PRIVILEGES ON {DB_CONFIG['database']}.* TO '{DB_CONFIG['user']}'@'localhost';")
                        print("     FLUSH PRIVILEGES;")
                    raise
            temp_conn.close()
        except Exception as e:
            print(f"[错误] 检查/创建数据库失败: {str(e)}")
            raise
        
        # 连接到MySQL数据库
        db_conn = pymysql.connect(**DB_CONFIG)
        cursor = db_conn.cursor()
        
        # 创建商品数据表
        print("[数据库] 正在检查并创建必要的数据表...")
        
        # 创建taobao_products表
        create_products_table_sql = """
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
        """
        cursor.execute(create_products_table_sql)
        
        # 创建taobao_data表
        create_data_table_sql = """
        CREATE TABLE IF NOT EXISTS taobao_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255),
            price DECIMAL(10,2),
            deal_count INT,
            location VARCHAR(100),
            shop_name VARCHAR(100),
            post_text VARCHAR(10),
            title_url TEXT,
            shop_url TEXT,
            img_url TEXT,
            comment_total INT DEFAULT 0,
            comment_fetched INT DEFAULT 0,
            fetch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_data_table_sql)
        
        # 创建评论表
        create_comments_table_sql = """
        CREATE TABLE IF NOT EXISTS product_comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT,
            comment_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX (product_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_comments_table_sql)
        
        db_conn.commit()
        
        # 检查表是否创建成功
        cursor.execute("SHOW TABLES LIKE 'taobao_products'")
        if cursor.fetchone():
            print("[成功] taobao_products表已存在或创建成功")
        else:
            print("[警告] taobao_products表可能未成功创建")
            
        cursor.execute("SHOW TABLES LIKE 'taobao_data'")
        if cursor.fetchone():
            print("[成功] taobao_data表已存在或创建成功")
        else:
            print("[警告] taobao_data表可能未成功创建")
        
        cursor.close()
        print("[成功] 数据库连接成功并完成表结构检查")
        print("="*50)
        return True
    except pymysql.err.OperationalError as e:
        error_code = e.args[0]
        print("="*50)
        if error_code == 1049:  # 数据库不存在
            print(f"[错误] 数据库'{DB_CONFIG['database']}'不存在")
            print("[建议] 请手动创建数据库或赋予当前用户创建数据库的权限")
        elif error_code == 1045:  # 访问被拒绝
            print("[错误] 数据库访问被拒绝")
            print("[诊断] 用户名或密码错误，或没有访问权限")
            print("[建议] 请检查配置文件中的用户名和密码是否正确")
        elif error_code == 2003:  # 无法连接到服务器
            print("[错误] 无法连接到MySQL服务器")
            print("[诊断] MySQL服务可能未启动或地址/端口错误")
            print("[建议] 请检查MySQL服务状态或配置")
        else:
            print(f"[错误] 数据库连接或表创建失败: {str(e)}")
            print("[建议] 请检查MySQL服务是否正常运行，以及用户名密码是否正确")
        print("="*50)
        if db_conn:
            db_conn.close()
            db_conn = None
        return False
    except Exception as e:
        print("="*50)
        print(f"[严重错误] 数据库连接或表创建失败: {str(e)}")
        print("[建议] 请检查MySQL服务是否正常运行，以及用户名密码是否正确")
        print(f"[建议] 确保数据库'{DB_CONFIG['database']}'已存在，或用户有创建数据库的权限")
        print("="*50)
        if db_conn:
            db_conn.close()
            db_conn = None
        return False
        
def save_to_mysql():
    """
    将爬取的商品数据保存到MySQL数据库的taobao_products表中
    """
    global db_conn, search_keyword, count
    
    print("="*50, flush=True)
    print("[数据库] 正在保存数据到MySQL...", flush=True)
    print(f"[时间] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    
    try:
        # 如果数据库连接不存在或已关闭，重新建立连接
        if db_conn is None or not db_conn.open:
            print("[数据库] 数据库连接不存在或已关闭，重新连接...", flush=True)
            connect_to_db()
            
        if db_conn and db_conn.open:
            # 获取总商品数量，确保count变量准确
            cursor = db_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM taobao_products WHERE search_keyword = %s", (search_keyword,))
            actual_count = cursor.fetchone()[0]
            
            # 更新全局count变量，确保与数据库一致
            # 由于count初始为1（表头占用一行），所以实际商品数量是count-1
            # 而数据库中的实际数量是actual_count
            if actual_count > 0:
                count = actual_count + 1  # +1是因为count在代码中表示的是序号，从1开始
                print(f"[统计] 数据库中实际商品数量: {actual_count}", flush=True)
                print(f"[统计] 更新全局count变量为: {count}", flush=True)
            
            print(f"[成功] 已成功将 {actual_count} 条商品数据保存到MySQL数据库", flush=True)
            
            # 记录搜索日志
            try:
                cursor.execute("""
                INSERT INTO search_logs (search_keyword, product_count, search_time)
                VALUES (%s, %s, NOW())
                """, (search_keyword, actual_count))
                db_conn.commit()
                print("[日志] 搜索记录已添加到日志表", flush=True)
            except Exception as log_error:
                print(f"[警告] 无法记录搜索日志: {str(log_error)}", flush=True)
                
            cursor.close()
        else:
            print("[错误] 无法连接到数据库，数据未能保存", flush=True)
            
    except Exception as e:
        print(f"[错误] 保存数据到MySQL失败: {str(e)}", flush=True)
        if db_conn and db_conn.open:
            try:
                db_conn.rollback()
                print("[恢复] 已回滚数据库事务", flush=True)
            except:
                pass
    
    print("="*50, flush=True)
    return

def save_csv():
    """将 csv_rows 数据写入 CSV 文件（备份用）"""
    global filename, csv_rows
    try:
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(csv_rows)
        print("CSV 文件保存成功（备份）：", filename)
    except Exception as e:
        print("文件写入错误：", e)


def get_comments_for_product(product_url):
    """
    针对天猫商品页面：
    - 加载页面后等待15秒
    - 尝试点击"展开"按钮（使用更新后的选择器），若点击失败则跳过该商品
    - 循环等待评论加载，最多等待40秒或加载到50条评论后结束，
      最后将评论用 "\n---\n" 拼接后返回
    完成后关闭标签页并切换回原页面。
    """
    comment_text = ""
    # 补全 URL 协议头
    if product_url.startswith("//"):
        product_url = "https:" + product_url

    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(product_url)
        # 等待15秒，确保页面加载完成
        time.sleep(15)

        # 尝试点击天猫的"展开"按钮（更新后的选择器，根据实际情况调整）
        try:
            expand_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div.tm-reviews > div.expand-btn")
                )
            )
            expand_button.click()
            print("天猫：点击展开按钮成功。")
            time.sleep(3)
        except Exception as e:
            print("天猫：无法点击展开按钮，跳过该商品。")
            return ""

        # 循环等待评论加载，最多等待40秒或评论数量达到50条后结束
        start_time = time.time()
        comments = []
        while time.time() - start_time < 40:
            comment_elems = driver.find_elements(
                By.CSS_SELECTOR,
                "div.tm-reviews > div.review-item"
            )
            comments = [elem.text.strip() for elem in comment_elems if elem.text.strip()]
            if len(comments) >= 50:
                break
            time.sleep(3)
        comment_text = "\n---\n".join(comments)
        print("天猫：获取评论成功，共计 {} 条评论".format(len(comments)))
    except Exception as e:
        print("天猫：获取评论信息错误：", e)
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    return comment_text


def update_comments():
    """
    遍历所有商品数据，对每个商品通过 Title_URL 打开页面抓取评论，
    并将评论信息更新到对应数据行的评论字段中。
    """
    global db_conn
    
    for row in csv_rows[1:]:
        product_url = row[7]  # Title_URL 在第8列（索引7）
        comment = get_comments_for_product(product_url)
        row[-1] = comment
        
        # 同时更新数据库中的评论
        if db_conn and db_conn.open and comment:
            try:
                cursor = db_conn.cursor()
                # 查找产品ID
                cursor.execute("SELECT id FROM taobao_products WHERE item_id = %s", (row[0],))
                product_id = cursor.fetchone()
                
                if product_id:
                    # 删除旧的评论
                    cursor.execute("DELETE FROM product_comments WHERE product_id = %s", (product_id[0],))
                    
                    # 插入新评论
                    comments = comment.split("\n---\n")
                    for comment_text in comments:
                        if comment_text.strip():
                            cursor.execute("""
                                INSERT INTO product_comments (product_id, comment_text)
                                VALUES (%s, %s)
                                """, 
                                (product_id[0], comment_text)
                            )
                    
                    # 提交事务
                    db_conn.commit()
                    print("已更新商品序号 {} 的评论信息到数据库。".format(row[0]))
            except Exception as e:
                print("更新评论到数据库失败:", e)
                if db_conn and db_conn.open:
                    db_conn.rollback()
        else:
            print("已更新商品序号 {} 的评论信息。".format(row[0]))
            
        time.sleep(random.uniform(2, 4))


def start_comment_scraping():
    """
    开始爬取评论信息，并更新MySQL数据库。
    此函数通常由 GUI 调用。
    """
    update_comments()
    # 保持CSV备份
    save_csv()
    print("评论爬取完毕，数据库已更新。")


def get_goods_from_db(page=1, limit=100):
    """从数据库获取商品数据，供API调用"""
    try:
        conn = None
        try:
            print(f"[数据库] 尝试从数据库获取第{page}页商品数据，每页{limit}条")
            # 确保数据库连接
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 构建查询 - 从taobao_data表获取数据
            offset = (page - 1) * limit
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
            
            # 执行查询
            print(f"[数据库] 执行查询: LIMIT {limit} OFFSET {offset}")
            cursor.execute(query, (limit, offset))
            goods = cursor.fetchall()
            print(f"[数据库] 查询成功，获取到{len(goods)}条商品数据")
            
            # 处理日期格式
            for item in goods:
                if 'fetch_time' in item and item['fetch_time']:
                    item['fetch_time'] = item['fetch_time'].strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.close()
            return goods
            
        finally:
            if conn and conn.open:
                conn.close()
                print("[数据库] 数据库连接已关闭")
                
    except Exception as e:
        print(f"[错误] 从数据库获取商品数据失败: {e}")
        # 如果发生异常，尝试记录到日志
        try:
            import logging
            logging.error(f"从数据库获取商品数据失败: {e}")
        except:
            pass  # 如果日志记录失败，继续执行
        return []


def clear_database():
    """清空数据库表"""
    try:
        conn = None
        try:
            # 确保数据库连接
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # 禁用外键检查，以便能够清空有外键关联的表
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # 获取所有表名
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            # 打印所有表名，用于调试
            print(f"数据库中的表: {[t[0] for t in tables]}")
            
            # 清空product_comments表（如果存在）
            try:
                cursor.execute("TRUNCATE TABLE product_comments")
                print("已清空product_comments表")
            except Exception as e:
                print(f"清空product_comments表失败: {e}")
            
            # 清空taobao_products表
            try:
                cursor.execute("TRUNCATE TABLE taobao_products")
                print("已清空taobao_products表")
            except Exception as e:
                print(f"清空taobao_products表失败: {e}")
                
            # 清空taobao_data表（如果存在）
            try:
                cursor.execute("TRUNCATE TABLE taobao_data")
                print("已清空taobao_data表")
            except Exception as e:
                print(f"清空taobao_data表失败: {e}")
            
            # 恢复外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            # 提交事务
            conn.commit()
            
            cursor.close()
            print("数据库清空成功")
            return True
            
        finally:
            if conn and conn.open:
                conn.close()
                
    except Exception as e:
        print(f"清空数据库失败: {e}")
        if conn and conn.open:
            try:
                # 恢复外键检查（以防发生异常时没有恢复）
                conn.cursor().execute("SET FOREIGN_KEY_CHECKS = 1")
                conn.commit()
            except:
                pass
            conn.close()
        return False


def confirm_page_change(expected_page):
    """
    确认页面是否成功切换到预期的页码
    """
    global driver
    try:
        print(f"[验证] 正在验证页面是否成功切换到第{expected_page}页", flush=True)
        # 等待页面加载完成
        time.sleep(random.uniform(2, 3))
        
        # 先截图记录当前页面状态，以便于调试
        try:
            screenshot_path = f"crawler_debug/page_change_verification_{time.strftime('%H%M%S')}.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            driver.save_screenshot(screenshot_path)
            print(f"[调试] 已保存页面验证截图: {screenshot_path}", flush=True)
        except Exception as e:
            print(f"[警告] 保存截图失败: {e}", flush=True)
        
        # 使用多种方法验证当前页码
        current_page_number = get_current_page_number()
        if current_page_number == expected_page:
            print(f"[成功] 页面已切换到第{expected_page}页", flush=True)
            return True
        
        # 如果通过get_current_page_number无法准确获取，尝试手动检查页面中的页码信息
        url_check = False
        try:
            # 检查URL中是否包含预期页码的信息
            current_url = driver.current_url
            if "s=" in current_url:
                import re
                s_match = re.search(r's=(\d+)', current_url)
                if s_match:
                    s_value = int(s_match.group(1))
                    # 通常s参数是(页码-1)*每页商品数(44)
                    url_page = (s_value // 44) + 1
                    url_check = (url_page == expected_page)
                    print(f"[URL检查] URL参数s={s_value}对应页码{url_page}, 预期页码{expected_page}, 匹配: {url_check}", flush=True)
        except Exception as e:
            print(f"[警告] URL页码检查失败: {e}", flush=True)
        
        # 判断页面是否包含预期页码的显示
        display_check = False
        try:
            # 使用XPath查找页面中包含预期页码的显示元素
            page_elements = driver.find_elements(By.XPATH, 
                f"//em[contains(text(), '{expected_page}')] | "
                f"//li[contains(@class, 'current') and contains(text(), '{expected_page}')] | "
                f"//button[contains(@class, 'current') and contains(text(), '{expected_page}')] | "
                f"//span[contains(@class, 'next-pagination-jump-input')]/input[@value='{expected_page}']"
            )
            
            if page_elements:
                display_check = True
                print(f"[显示检查] 页面中包含预期页码{expected_page}的显示元素", flush=True)
        except Exception as e:
            print(f"[警告] 页面显示页码检查失败: {e}", flush=True)
        
        # 如果至少有一种验证方法通过，则认为页面已切换成功
        if url_check or display_check:
            print(f"[成功] 通过辅助检查确认页面已切换到第{expected_page}页 (URL检查: {url_check}, 显示检查: {display_check})", flush=True)
            return True
        
        # 尝试检查页面内容以确认是否发生了变化
        content_changed = False
        try:
            # 获取新页面的第一个商品标题或其他特征，与之前页面比较
            # 这部分逻辑在page_turning函数中已经实现
            print("[内容检查] 页面内容可能已发生变化，但无法确认是否切换到了指定页码", flush=True)
            content_changed = True  # 假设内容已经变化
        except Exception as e:
            print(f"[警告] 页面内容检查失败: {e}", flush=True)
        
        # 根据综合判断返回结果
        if current_page_number != expected_page and not url_check and not display_check:
            print(f"[失败] 页面未成功切换到第{expected_page}页，当前仍在第{current_page_number}页", flush=True)
            return False
        else:
            # 如果至少内容有变化，也认为是成功的（即使可能不是目标页码）
            print(f"[部分成功] 页面可能已切换，但无法确认是否为第{expected_page}页", flush=True)
            return content_changed
            
    except Exception as e:
        print(f"[错误] 验证页面切换时出错: {e}", flush=True)
        return False

def get_current_page_number():
    """
    获取当前页面的实际页码
    """
    try:
        # 方法1: 通过URL参数获取
        current_url = driver.current_url
        if "s=" in current_url:
            import re
            s_match = re.search(r's=(\d+)', current_url)
            if s_match:
                s_value = int(s_match.group(1))
                # 通常s参数是(页码-1)*每页商品数(44)
                page = (s_value // 44) + 1
                print(f"[页码] 从URL参数s={s_value}获取到页码: {page}", flush=True)
                return page
        
        # 方法2: 从淘宝分页输入框获取当前值
        try:
            # 尝试精确匹配淘宝分页输入框
            input_elements = driver.find_elements(By.XPATH, "//span[contains(@class, 'next-pagination-jump-input')]/input | //input[@aria-label='请输入跳转到第几页']")
            if input_elements:
                for input_elem in input_elements:
                    value = input_elem.get_attribute('value')
                    if value and value.isdigit():
                        page = int(value)
                        print(f"[页码] 从分页输入框获取到页码: {page}", flush=True)
                        return page
        except Exception as e:
            print(f"[警告] 从分页输入框获取页码失败: {e}", flush=True)
        
        # 方法3: 通过页码高亮元素获取
        try:
            # 查找高亮的页码元素 - 淘宝特定的
            highlighted_selectors = [
                "//li[contains(@class, 'next-current')]",  # 新版淘宝分页
                "//button[contains(@class, 'next-current')]", # 另一种分页样式
                "//div[contains(@class, 'pagination')]//*[contains(@class, 'active') or contains(@class, 'current')]",
                # 通用选择器
                "//li[@class='active' or @class='current' or contains(@class, 'selected')]",
                "//em[contains(@class, 'current')]",
                "//button[contains(@class, 'selected') or contains(@class, 'active')]"
            ]
            
            for selector in highlighted_selectors:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    for elem in elements:
                        page_text = elem.text.strip()
                        if page_text.isdigit():
                            page = int(page_text)
                            print(f"[页码] 从高亮元素获取到页码: {page}", flush=True)
                            return page
        except Exception as e:
            print(f"[警告] 通过高亮元素获取页码失败: {e}", flush=True)
        
        # 方法4: 查找em元素
        try:
            em_elements = driver.find_elements(By.XPATH, "//em[contains(@data-spm-anchor-id, 'a21n57.1.0.i')]")
            if em_elements:
                for em in em_elements:
                    page_text = em.text.strip()
                    if page_text.isdigit():
                        page = int(page_text)
                        print(f"[页码] 从em元素获取到页码: {page}", flush=True)
                        return page
        except Exception as e:
            print(f"[警告] 通过em元素获取页码失败: {e}", flush=True)
        
        # 方法5: 尝试从页面上的任何可能包含页码的元素获取信息
        try:
            # 查找任何可能包含当前页码的文本，如 "第X页" 或 "Page X of Y"
            page_texts = driver.find_elements(By.XPATH, "//*[contains(text(), '第') and contains(text(), '页')] | //*[contains(text(), 'Page')]")
            if page_texts:
                for text_elem in page_texts:
                    text = text_elem.text.strip()
                    # 尝试从中文文本 "第X页" 提取
                    import re
                    match = re.search(r'第\s*(\d+)\s*页', text)
                    if match:
                        page = int(match.group(1))
                        print(f"[页码] 从页面文本获取到页码: {page}", flush=True)
                        return page
                    
                    # 尝试从英文文本 "Page X of Y" 提取
                    match = re.search(r'Page\s*(\d+)', text)
                    if match:
                        page = int(match.group(1))
                        print(f"[页码] 从页面文本获取到页码: {page}", flush=True)
                        return page
        except Exception as e:
            print(f"[警告] 通过页面文本获取页码失败: {e}", flush=True)
        
        # 默认返回当前全局变量中保存的页码
        print(f"[页码] 无法从页面元素获取页码，使用当前跟踪的页码: {current_page}", flush=True)
        return current_page
    except Exception as e:
        print(f"[错误] 获取当前页码时出错: {e}", flush=True)
        return current_page

def check_login_required():
    """检查当前页面是否需要登录淘宝"""
    try:
        print("[检查] 检查是否需要登录淘宝...", flush=True)
        
        # 检查页面中是否存在登录按钮或登录提示
        page_source = driver.page_source
        login_indicators = [
            "请登录", "亲，请登录", "登录", "密码登录", "扫码登录",
            "login-scratch-button", "login-form", "login-box",
            "login-title", "login-links", "login-password"
        ]
        
        # 检查页面标题是否包含登录相关文字
        if "登录" in driver.title or "login" in driver.title.lower():
            print("[检测] 检测到登录页面，需要用户登录", flush=True)
            return True
            
        # 检查页面源码中是否包含登录相关文字或元素
        for indicator in login_indicators:
            if indicator in page_source:
                print(f"[检测] 页面中检测到登录指示词: {indicator}", flush=True)
                return True
        
        # 尝试检查是否存在登录按钮元素
        try:
            login_elements = driver.find_elements(By.XPATH, 
                "//a[contains(text(), '请登录') or contains(text(), '登录') or contains(@class, 'login')]")
            if login_elements and len(login_elements) > 0:
                print(f"[检测] 检测到 {len(login_elements)} 个可能的登录元素", flush=True)
                return True
        except Exception as e:
            print(f"[警告] 查找登录元素时出错: {e}", flush=True)
        
        # 检查登录成功指示 - 比如页面上是否显示个人信息
        try:
            # 检查是否有"我的淘宝"等登录后才会显示的元素
            loggedin_elements = driver.find_elements(By.XPATH, 
                "//a[contains(text(), '我的淘宝') or contains(text(), '购物车') or contains(text(), '我的订单')]")
            if loggedin_elements and len(loggedin_elements) > 0:
                print("[检测] 检测到已登录状态元素，无需登录", flush=True)
                return False
        except Exception as e:
            print(f"[警告] 检查登录状态元素时出错: {e}", flush=True)
        
        # 默认不需要登录
        print("[检测] 未检测到明确需要登录的特征，暂定为无需登录", flush=True)
        return False
    except Exception as e:
        print(f"[错误] 检查登录需求时发生异常: {e}", flush=True)
        # 出错时默认需要登录
        return True

if __name__ == '__main__':
    # 作为单独调试时可以在此添加测试代码
    pass
