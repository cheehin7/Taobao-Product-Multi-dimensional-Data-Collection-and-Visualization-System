import pandas as pd
import jieba
import pymysql
import re
import logging
import os
import json
from gensim import corpora, models
import numpy as np
from db_config import DB_CONFIG

logger = logging.getLogger(__name__)

# 添加LDA分析结果缓存路径
LDA_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lda_results.json')

def analyze_lda(topic_count=3, save_csv=False, csv_path='lda_results.csv', force_refresh=False):
    """
    使用LDA模型对评论进行主题分析
    支持缓存机制，可以加载之前的分析结果。
    
    Args:
        topic_count: 主题数量，默认为3
        save_csv: 是否保存CSV结果文件
        csv_path: CSV保存路径
        force_refresh: 是否强制刷新，忽略缓存
        
    Returns:
        dict: 包含以下键值对的字典
            - success: 是否成功分析
            - positive_topics: 积极评论主题关键词列表
            - negative_topics: 消极评论主题关键词列表
            - error: 错误信息(如果失败)
    """
    try:
        # 如果不强制刷新且缓存文件存在，则从缓存加载
        if not force_refresh and os.path.exists(LDA_CACHE_PATH):
            try:
                with open(LDA_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    logger.info(f"从缓存加载LDA主题分析结果: {LDA_CACHE_PATH}")
                    return {
                        'success': True,
                        'positive_topics': cache_data['positive_topics'],
                        'negative_topics': cache_data['negative_topics'],
                        'from_cache': True
                    }
            except Exception as e:
                logger.warning(f"读取LDA主题分析缓存失败，将重新分析: {e}")
    
        # 连接数据库获取评论数据
        conn = pymysql.connect(**DB_CONFIG)
        
        # 查询评论内容和评分
        sql = '''
            SELECT c.id, c.comment_text, c.username, 
            CASE WHEN c.is_default = 1 THEN 5 ELSE 3 END as score
            FROM product_comments c
            WHERE c.comment_text IS NOT NULL AND c.comment_text != ''
        '''
        
        df = pd.read_sql(sql, conn)
        conn.close()
        
        # 如果没有数据，返回失败
        if df.empty:
            logger.warning("没有找到评论数据，无法进行LDA主题分析")
            return {
                'success': False,
                'error': '没有找到评论数据'
            }
            
        # 将评论根据评分分为积极和消极
        # 提取积极评论（评分4-5分）
        positive_df = df[df['score'] >= 4].copy()
        positive_df.drop_duplicates(subset=['comment_text'], keep='first', inplace=True)
        
        # 提取消极评论（评分1-3分）
        negative_df = df[df['score'] <= 3].copy()
        negative_df.drop_duplicates(subset=['comment_text'], keep='first', inplace=True)
        
        # 额外清洗逻辑 - 过滤包含明显积极词汇的消极评论和明显消极词汇的积极评论
        positive_words = ['好评'] # 只保留最明显的积极词
        negative_words = ['差评', '退货'] # 只保留最明显的消极词
        
        # 重新筛选积极评论 - 移除包含明显消极词的评论
        def contains_negative_words(text):
            return any(word in text for word in negative_words)
        
        # 只在数据量充足时进行筛选
        if len(positive_df) > 5:
            positive_df = positive_df[~positive_df['comment_text'].apply(contains_negative_words)]
        
        # 重新筛选消极评论 - 移除包含明显积极词的评论
        def contains_positive_words(text):
            return any(word in text for word in positive_words)
        
        # 只在数据量充足时进行筛选
        if len(negative_df) > 5:
            negative_df = negative_df[~negative_df['comment_text'].apply(contains_positive_words)]
            
        # 清洗文本内容，移除非评论信息，但保留更多内容
        def clean_comment_text(text):
            # 移除"系统默认好评"等固定文本
            if text.strip() == "系统默认好评" or text.strip() == "系统默认评价":
                return ""
            
            # 移除"图三丽欧"等非评论内容，但保留其他内容
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
        positive_df['comment_text'] = positive_df['comment_text'].apply(clean_comment_text)
        negative_df['comment_text'] = negative_df['comment_text'].apply(clean_comment_text)
        
        # 移除清洗后为空的评论
        positive_df = positive_df[positive_df['comment_text'].str.len() > 3]
        negative_df = negative_df[negative_df['comment_text'].str.len() > 3]
        
        # 如果积极或消极评论数量不足，返回警告
        if len(positive_df) < 2 or len(negative_df) < 2:
            logger.warning(f"评论数量不足，积极评论：{len(positive_df)}，消极评论：{len(negative_df)}")
            return {
                'success': False,
                'error': f'评论数量不足，无法进行有效的主题分析。积极评论：{len(positive_df)}，消极评论：{len(negative_df)}'
            }
        
        # 自定义分词函数
        def cut_text(text):
            return ' '.join(jieba.cut(text))
        
        # 对评论进行分词
        positive_texts = positive_df['comment_text'].apply(cut_text)
        negative_texts = negative_df['comment_text'].apply(cut_text)
        
        # 加载停用词
        stopwords_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stopwords.txt')
        try:
            with open(stopwords_path, encoding='utf-8') as f:
                stop_words = f.read().splitlines()
                stop_words = [' ', ''] + stop_words  # 添加空格和空字符串到停用词
        except Exception as e:
            logger.error(f"加载停用词失败: {str(e)}")
            stop_words = [' ', '']
        
        # 处理积极评论
        positive_words = []
        for text in positive_texts:
            # 将分词后的文本按空格分割成词列表
            words = text.split(' ')
            # 过滤停用词
            filtered_words = [word for word in words if word not in stop_words and len(word) > 1]
            positive_words.append(filtered_words)
        
        # 处理消极评论
        negative_words = []
        for text in negative_texts:
            words = text.split(' ')
            filtered_words = [word for word in words if word not in stop_words and len(word) > 1]
            negative_words.append(filtered_words)
        
        # 创建词典和语料
        positive_dict = corpora.Dictionary(positive_words)
        positive_corpus = [positive_dict.doc2bow(text) for text in positive_words]
        
        negative_dict = corpora.Dictionary(negative_words)
        negative_corpus = [negative_dict.doc2bow(text) for text in negative_words]
        
        # 训练LDA模型
        positive_lda = models.LdaModel(positive_corpus, num_topics=topic_count, id2word=positive_dict)
        negative_lda = models.LdaModel(negative_corpus, num_topics=topic_count, id2word=negative_dict)
        
        # 获取主题关键词
        positive_themes = positive_lda.show_topics()
        negative_themes = negative_lda.show_topics()
        
        # 正则表达式提取中文词
        pattern = re.compile(r'[\u4e00-\u9fa5]+')
        
        # 提取积极评论主题关键词
        positive_topics = []
        for i in range(topic_count):
            keywords = pattern.findall(positive_themes[i][1])
            # 如果主题为空，使用一个默认值
            if not keywords:
                keywords = ["无主题"]
            positive_topics.append(keywords)
        
        # 提取消极评论主题关键词
        negative_topics = []
        for i in range(topic_count):
            keywords = pattern.findall(negative_themes[i][1])
            # 如果主题为空，使用一个默认值
            if not keywords:
                keywords = ["无主题"]
            negative_topics.append(keywords)
        
        # 可选保存为CSV
        if save_csv:
            # 创建一个DataFrame存储主题关键词
            topics_df = pd.DataFrame()
            for i in range(topic_count):
                topics_df[f'积极主题{i+1}'] = pd.Series(positive_topics[i] if i < len(positive_topics) else [])
                topics_df[f'消极主题{i+1}'] = pd.Series(negative_topics[i] if i < len(negative_topics) else [])
            
            topics_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"LDA主题分析结果已保存到 {csv_path}")
        
        # 保存结果到缓存文件
        try:
            cache_data = {
                'positive_topics': positive_topics,
                'negative_topics': negative_topics
            }
            with open(LDA_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"LDA主题分析结果已缓存到 {LDA_CACHE_PATH}")
        except Exception as e:
            logger.warning(f"保存LDA主题分析结果到缓存失败: {e}")
        
        return {
            'success': True,
            'positive_topics': positive_topics,
            'negative_topics': negative_topics,
            'from_cache': False
        }
        
    except Exception as e:
        logger.error(f"LDA主题分析失败: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# 如果直接运行此脚本，执行LDA主题分析
if __name__ == "__main__":
    results = analyze_lda(save_csv=True)
    if results['success']:
        print("分析成功")
        print("积极评论主题：")
        for i, topic in enumerate(results['positive_topics']):
            print(f"主题{i+1}: {', '.join(topic)}")
        
        print("\n消极评论主题：")
        for i, topic in enumerate(results['negative_topics']):
            print(f"主题{i+1}: {', '.join(topic)}")
    else:
        print(f"分析失败: {results['error']}")
