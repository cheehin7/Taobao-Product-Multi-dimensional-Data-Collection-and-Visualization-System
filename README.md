# 淘宝商品多维度数据采集与可视化系统
(Taobao Product Multi-dimensional Data Collection and Visualization System)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.2.3-green.svg)
![Selenium](https://img.shields.io/badge/Selenium-4.8.2-orange.svg)
![MySQL](https://img.shields.io/badge/MySQL-5.7+-lightgrey.svg)
![NLP](https://img.shields.io/badge/NLP-Jieba%20%7C%20SnowNLP-yellow.svg)

## 📖 项目简介 (Introduction)
本项目是一个端到端的电商数据智能分析与可视化系统。系统通过自动化爬虫获取淘宝商品元数据及海量用户评价，利用自然语言处理（NLP）技术对评价内容进行情感倾向分析和主题挖掘，并以 Web 系统的形式提供从数据采集、清洗、存储到多维度数据可视化分析的完整闭环。本项目可为电商选品、竞品分析和用户反馈挖掘提供有力的数据支撑。

## ✨ 核心功能 (Key Features)

*   🕸️ **自动化数据采集 (Automated Web Scraping)**
    *   基于 Selenium 和 ChromeDriver 设计动态网页爬虫，模拟真实用户浏览。
    *   突破淘宝复杂登录校验机制，支持复用浏览器实例防反爬。
    *   自动化提取商品价格、销量、发货地及用户评论。
*   🧠 **自然语言处理与机器学习 (NLP & Machine Learning)**
    *   **情感分析**：基于 Scikit-learn 构建朴素贝叶斯（Naive Bayes）分类器，对海量商品评价进行正负面情感预测。
    *   **主题挖掘**：引入 Gensim 构建 LDA（Latent Dirichlet Allocation）主题模型，挖掘长文本评论中的潜在核心反馈点。
    *   **分词与词云**：结合 Jieba 分词与 WordCloud 自动生成评论关键词云图。
*   📊 **多维度数据可视化 (Data Visualization)**
    *   提供美观的 Web 界面，直观展示商品价格分布、销量排行、发货地统计等。
    *   利用本地 JSON 缓存机制（如 NLP 分析结果缓存），大幅降低重复计算开销，提升页面响应速度。
*   💻 **全栈 Web 架构 (Full-stack Web System)**
    *   基于 Flask 框架搭建后端服务，提供 RESTful API。
    *   多线程异步执行爬虫任务，保证前端界面交互流畅。
    *   MySQL 关系型数据库持久化存储商品与评论数据。

## 🛠️ 技术栈 (Tech Stack)

*   **后端开发**：Python 3.8+, Flask, RESTful API
*   **数据采集**：Selenium WebDriver, BeautifulSoup4, PyQuery, Requests
*   **数据存储**：MySQL, PyMySQL
*   **算法与NLP**：Scikit-learn (朴素贝叶斯), Gensim (LDA), SnowNLP, Jieba
*   **数据分析**：Pandas, Numpy
*   **数据可视化**：Matplotlib, WordCloud, 前端模板渲染 (Jinja2)

## 🚀 快速开始 (Getting Started)

### 1. 环境准备
*   安装 Python 3.8 或以上版本。
*   安装 MySQL 数据库 (5.7+)。
*   安装 Chrome 浏览器及对应版本的 [ChromeDriver](https://chromedriver.chromium.org/downloads)。

### 2. 克隆与依赖安装
```bash
# 激活虚拟环境 (可选)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 安装项目依赖
pip install -r code/requirements.txt
```

### 3. 数据库配置
编辑 `code/db_config.py` 或 `code/app.py` 中的数据库连接信息：
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # 修改为你的数据库密码
    'database': 'taobao_data',
    'port': 3306
}
```
在 MySQL 中导入初始数据库表结构：
```bash
mysql -u root -p < code/init_db.sql
```

### 4. 运行系统
```bash
cd code
python app.py
```
启动成功后，在浏览器中访问: `http://localhost:5000`

## 💡 使用说明 (Usage)
1.  **数据采集**：进入“数据爬取”页面，输入商品关键词和需要爬取的页数。
2.  **淘宝授权**：系统会自动调起 Chrome 浏览器，首次运行需手动扫码或密码登录淘宝，随后点击界面的“确认登录”开始自动化采集。
3.  **结果分析**：采集完成后，进入分析模块查看价格分布、情感分析结果、LDA主题词模型以及评论词云。

## ⚠️ 免责声明
本项目仅供计算机/电子信息工程专业毕业设计学习、研究和技术交流使用。请严格遵守目标网站的 `robots.txt` 协议及相关法律法规，请勿将本系统用于任何商业用途或恶意高频抓取。
