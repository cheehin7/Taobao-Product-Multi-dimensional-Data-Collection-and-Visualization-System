import jieba
from matplotlib import pyplot as plt
from wordcloud import WordCloud
from PIL import Image
import numpy as np
import pandas as pd
import pymysql
import os
import logging
from db_config import DB_CONFIG

logger = logging.getLogger(__name__)

# r''单引号里面不需要转义
def generate_wordcloud(output_path='static/images/beautifulcloud.png', force_refresh=False):
    """
    生成评论词云图并保存到指定路径
    
    Args:
        output_path: 输出文件路径，默认保存到static/images/beautifulcloud.png
        force_refresh: 是否强制刷新生成词云，忽略已有词云图
        
    Returns:
        bool: 是否成功生成词云
    """
    try:
        # 如果不强制刷新，且词云图已存在，直接返回成功
        if not force_refresh and os.path.exists(output_path):
            logger.info(f"词云图已存在且不需要强制刷新: {output_path}")
            return True
    
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 设置中文字体路径
        font = r'C:\Windows\Fonts\simfang.ttf'
        
        # 分词函数
        def tcg(texts):
            cut = jieba.cut(texts)  # 分词
            string = ' '.join(cut)
            return string
        
        # 从数据库获取评论数据
        try:
            # 连接数据库
            conn = pymysql.connect(**DB_CONFIG)
            
            # 查询评论内容
            # 从product_comments表中读取评论数据
            sql = '''
                SELECT comment_text FROM product_comments 
                WHERE comment_text IS NOT NULL AND comment_text != ''
            '''
            
            df = pd.read_sql(sql, conn)
            conn.close()
            
            # 如果没有数据，返回失败
            if df.empty:
                logger.warning("没有找到评论数据，无法生成词云")
                return False
                
            # 移除重复内容
            df.drop_duplicates(keep='first', inplace=True)
            # 移除空值
            df = df.dropna()
            
            # 清洗评论文本，移除非评论信息
            def clean_comment_text(text):
                # 移除系统生成的默认好评文本
                if text.strip() == "系统默认好评" or text.strip() == "系统默认评价":
                    return ""
                
                import re
                # 移除"图三丽欧"等非评论内容，但保留更多内容
                text = re.sub(r'图.{1,5}丽欧', '', text)
                text = re.sub(r'用户.*?评价', '', text)    # 移除"用户xxx评价"
                text = re.sub(r'方未.*?评价', '', text)    # 移除"方未xxx评价"
                
                # 不移除以下内容，以保留更多评论
                # text = re.sub(r'[a-zA-Z0-9]+', '', text)  # 不移除英文和数字
                # text = re.sub(r'系统默认.*?', '', text)    # 不完全移除系统默认
                
                # 去除多余空格，但保留单词间的空格
                text = re.sub(r'\s+', ' ', text).strip()
                return text
                
            # 应用清洗函数
            df['comment_text'] = df['comment_text'].apply(clean_comment_text)
            
            # 移除清洗后为空的评论
            df = df[df['comment_text'].str.len() > 3]
            
            # 如果清洗后没有数据，返回失败
            if df.empty:
                logger.warning("清洗后没有有效评论数据，无法生成词云")
                return False
            
            # 提取评论文本
            text = df['comment_text'].tolist()
            text = ''.join(str(text))
            string = tcg(text)
            
            # 加载停用词
            stop_words = []
            stopwords_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stopwords.txt')
            
            with open(stopwords_path, encoding='utf-8') as f:  # 可根据需要打开停用词库，然后加上不想显示的词语
                con = f.readlines()
                stop_words = set()
                for i in con:
                    i = i.replace("\n", "")
                    stop_words.add(i)
                    
            # 初始化词云
            wc = WordCloud(
                collocations=False,
                background_color='white',
                width=500,
                scale=8,
                height=500,
                font_path=font,
                max_words=2000,
                max_font_size=50,
                stopwords=stop_words
            )
            
            # 生成词云
            wc.generate(string)
            plt.figure(figsize=(10, 8))
            plt.imshow(wc)
            plt.axis('off')
            
            # 保存图片
            wc.to_file(output_path)
            plt.close()
            
            logger.info(f"成功生成词云图并保存到 {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"数据库操作失败: {str(e)}")
            return False
    
    except Exception as e:
        logger.error(f"生成词云失败: {str(e)}")
        return False


# 如果直接运行此脚本，生成词云
if __name__ == "__main__":
    generate_wordcloud()
