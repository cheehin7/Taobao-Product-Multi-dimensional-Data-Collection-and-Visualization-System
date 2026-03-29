from snownlp import SnowNLP
import pandas as pd
import pymysql
import numpy as np
import logging
import os
import json
from db_config import DB_CONFIG

logger = logging.getLogger(__name__)

# 添加缓存文件路径
SENTIMENT_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sentiment_results.json')

def analyze_sentiment(save_csv=False, csv_path='nlp_results.csv', force_refresh=False):
    """
    对评论进行情感分析，返回分析结果和统计数据。
    支持缓存机制，可以加载之前的分析结果。
    
    Args:
        save_csv: 是否保存CSV结果文件
        csv_path: CSV保存路径
        force_refresh: 是否强制刷新，忽略缓存
        
    Returns:
        dict: 包含以下键值对的字典
            - success: 是否成功分析
            - data: 分析后的DataFrame(如果成功)
            - stats: 统计数据，包含情感分布计数
            - error: 错误信息(如果失败)
    """
    try:
        # 如果不强制刷新且缓存文件存在，则从缓存加载
        if not force_refresh and os.path.exists(SENTIMENT_CACHE_PATH):
            try:
                with open(SENTIMENT_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    logger.info(f"从缓存加载情感分析结果: {SENTIMENT_CACHE_PATH}")
                    return {
                        'success': True,
                        'stats': cache_data,
                        'from_cache': True
                    }
            except Exception as e:
                logger.warning(f"读取情感分析缓存失败，将重新分析: {e}")
        
        # 连接数据库获取评论数据
        conn = pymysql.connect(**DB_CONFIG)
        
        # 查询评论内容
        sql = '''
            SELECT c.id, c.comment_text, c.username, 
            CASE WHEN c.is_default = 1 THEN 5 ELSE 4 END as score
            FROM product_comments c
            WHERE c.comment_text IS NOT NULL AND c.comment_text != ''
        '''
        
        df = pd.read_sql(sql, conn)
        conn.close()
        
        # 如果没有数据，返回失败
        if df.empty:
            logger.warning("没有找到评论数据，无法进行情感分析")
            return {
                'success': False,
                'error': '没有找到评论数据'
            }
            
        # 移除重复内容和空值
        df.drop_duplicates(subset=['comment_text'], keep='first', inplace=True)
        df = df.dropna(subset=['comment_text'])
        
        # 提取评论文本
        content = df['comment_text'].tolist()
        
        # 使用SnowNLP进行情感分析，得到0-1之间的情感得分
        sentiment_scores = []
        for text in content:
            try:
                score = SnowNLP(text).sentiments
                sentiment_scores.append(score)
            except Exception as e:
                logger.error(f"处理评论时出错: {str(e)}, 评论内容: {text[:30]}...")
                sentiment_scores.append(0.5)  # 出错时使用默认值0.5(中性)
        
        # 添加情感分析结果到DataFrame
        df['sentiment_score'] = sentiment_scores
        
        # 给情感分数分类
        def categorize_sentiment(score):
            if score <= 0.4:
                return '消极'
            elif score >= 0.6:
                return '积极'
            else:
                return '中性'
        
        df['sentiment_category'] = df['sentiment_score'].apply(categorize_sentiment)
        
        # 计算统计数据
        stats = {
            'sentiment_ranges': ['0.0-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.4', '0.4-0.5', 
                                '0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8-0.9', '0.9-1.0'],
            'sentiment_counts': [0] * 10,  # 初始化为0
            'negative_count': len(df[df['sentiment_score'] <= 0.4]),
            'neutral_count': len(df[(df['sentiment_score'] > 0.4) & (df['sentiment_score'] < 0.6)]),
            'positive_count': len(df[df['sentiment_score'] >= 0.6])
        }
        
        # 统计各分数区间的评论数量
        for i in range(10):
            lower = i * 0.1
            upper = (i + 1) * 0.1
            count = len(df[(df['sentiment_score'] >= lower) & (df['sentiment_score'] < upper)])
            stats['sentiment_counts'][i] = count
            
        # 可选保存为CSV
        if save_csv:
            result_df = df[['username', 'comment_text', 'sentiment_score', 'sentiment_category']]
            result_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"情感分析结果已保存到 {csv_path}")
        
        # 保存结果到缓存文件
        try:
            with open(SENTIMENT_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            logger.info(f"情感分析结果已缓存到 {SENTIMENT_CACHE_PATH}")
        except Exception as e:
            logger.warning(f"保存情感分析结果到缓存失败: {e}")
        
        return {
            'success': True,
            'data': df,
            'stats': stats,
            'from_cache': False
        }
        
    except Exception as e:
        logger.error(f"情感分析失败: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# 如果直接运行此脚本，执行情感分析
if __name__ == "__main__":
    results = analyze_sentiment(save_csv=True)
    if results['success']:
        print(f"分析成功，共分析 {len(results['data'])} 条评论")
        print(f"积极评论: {results['stats']['positive_count']}")
        print(f"中性评论: {results['stats']['neutral_count']}")
        print(f"消极评论: {results['stats']['negative_count']}")
    else:
        print(f"分析失败: {results['error']}")
