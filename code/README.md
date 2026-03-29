# 淘宝网商品数据爬取与分析系统

这是一个基于Python的淘宝网商品数据爬取与分析系统。通过该系统，你可以爬取淘宝网上的商品信息，并对数据进行分析和可视化展示。

## 功能特点

- 基于Selenium的淘宝商品数据爬虫
- 自动保存HTML源码和页面截图
- 多种选择器确保爬取成功率
- 页面分析与数据可视化
- 价格分布分析
- 商品信息词云展示
- 用户友好的Web界面

## 系统要求

- Python 3.8+
- MySQL 5.7+
- Chrome浏览器
- ChromeDriver (与Chrome版本匹配)

## 安装

1. 克隆仓库到本地

```bash
git clone [仓库地址]
cd taobao_system
```

2. 创建并激活虚拟环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. 安装依赖

```bash
pip install -r code/requirements.txt
```

4. 配置数据库

编辑 `code/app.py` 文件中的数据库配置：

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # 修改为你的数据库密码
    'database': 'taobao',
    'port': 3306
}
```

5. 初始化数据库

```bash
mysql -u root -p < code/init_db.sql
```

## 使用方法

1. 启动Web应用

```bash
cd code
python app.py
```

2. 打开浏览器访问 http://localhost:5000

3. 使用爬虫功能：
   - 在数据爬取页面输入关键词和页面范围
   - 点击"开始爬取"按钮
   - 在打开的浏览器中登录淘宝
   - 登录成功后，点击"确认登录"按钮
   - 系统将自动搜索并爬取数据

4. 数据分析：
   - 价格分析页面可查看商品价格分布
   - 词云分析页面可查看商品标题关键词分布

## 系统架构

- `app.py`: Web应用主程序
- `taobao_crawler.py`: 淘宝爬虫模块
- `datafx_ciyun.py`: 词云分析模块
- `templates/`: HTML模板文件
- `static/`: 静态资源文件
- `crawler_data/`: 爬取的HTML和截图存储目录

## 注意事项

1. 本系统仅供学习和研究使用，请勿用于商业用途
2. 爬取数据时请遵守淘宝网的使用条款和政策
3. 建议每次爬取页数不要过多，避免IP被限制
4. 确保ChromeDriver版本与Chrome浏览器版本匹配
5. 首次使用时需要手动登录淘宝账号

## 故障排除

1. 如果浏览器无法启动，请检查ChromeDriver是否正确安装
2. 如果爬取失败，可能是选择器变化导致，可查看保存的HTML源码进行分析
3. 数据库连接失败，请检查数据库配置和权限设置
4. 如果无法爬取数据，可能是淘宝反爬虫机制更新，需要调整爬虫策略 