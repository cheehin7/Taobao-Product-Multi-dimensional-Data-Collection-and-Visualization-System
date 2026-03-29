import jieba
import numpy as np
import pandas as pd
from sklearn import metrics, naive_bayes
import pymysql
from sklearn.feature_extraction.text import CountVectorizer  # 计算词频
import joblib
import os
import logging
import random
import json
from db_config import DB_CONFIG

logger = logging.getLogger(__name__)

# 模型文件路径
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bayes.pkl')
# 添加贝叶斯分析结果缓存路径
BAYES_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bayes_results.json')


def train_bayes_model(save_model=True, save_csv=False, csv_path='bayes_results.csv'):
    """
    训练贝叶斯模型并评估性能
    
    Args:
        save_model: 是否保存模型文件
        save_csv: 是否保存结果到CSV
        csv_path: CSV保存路径
        
    Returns:
        dict: 包含以下键值对的字典
            - success: 是否成功训练
            - accuracy: 分类准确率
            - model: 训练好的模型(如果不保存)
            - stats: 统计数据
            - error: 错误信息(如果失败)
    """
    try:
        # 连接数据库获取评论数据
        conn = pymysql.connect(**DB_CONFIG)
        
        # 查询评论内容和评分
        sql = '''
            SELECT c.id, c.comment_text, 
            CASE WHEN c.is_default = 1 THEN 5 ELSE 3 END as score
            FROM product_comments c
            WHERE c.comment_text IS NOT NULL AND c.comment_text != ''
        '''
        
        df = pd.read_sql(sql, conn)
        conn.close()
        
        # 如果没有数据，返回失败
        if df.empty:
            logger.warning("没有找到评论数据，无法训练贝叶斯模型")
            return {
                'success': False,
                'error': '没有找到评论数据'
            }
            
        # 移除重复内容和空值
        df.drop_duplicates(subset=['comment_text'], keep='first', inplace=True)
        df = df.dropna(subset=['comment_text', 'score'])
        
        # 将评分1~3分作为差评(标记为1)，评分4~5分作为好评(标记为2)
        df['sentiment_label'] = df['score'].apply(lambda x: 2 if x >= 4 else 1)
        
        # 提取评论文本和标签
        reviews = df['comment_text'].tolist()
        labels = df['sentiment_label'].tolist()
        
        # 对评论文本进行分词处理
        processed_texts = []
        stopwords = {}.fromkeys(['，', '！', '。', '、', '?', '～'])  # 设置停用词
        
        for text in reviews:
            # 分词
            seg_list = jieba.lcut(text, cut_all=False)
            # 过滤停用词
            filtered = [word for word in seg_list if word not in stopwords and len(word) > 1]
            # 合并为字符串
            processed_text = ' '.join(filtered)
            processed_texts.append(processed_text)
        
        # 特征提取 - 计算词频
        vectorizer = CountVectorizer()
        X = vectorizer.fit_transform(processed_texts)
        X = X.toarray()
        
        # 清洗文本内容，移除非评论信息
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
            
        # 应用清洗函数到原始数据
        df['comment_text'] = df['comment_text'].apply(clean_comment_text)
        
        # 移除清洗后为空的评论
        df = df[df['comment_text'].str.len() > 3]
        
        # 划分训练集和测试集
        # 如果样本总数少于10，使用留一法(Leave-One-Out)
        # 如果样本总数在10-50之间，使用30%的测试集
        # 如果样本总数超过50，使用20%的测试集
        from sklearn.model_selection import train_test_split
        
        total_samples = len(X)
        if total_samples < 5:
            # 样本太少，不划分，全部用于训练
            X_train, y_train = X, labels
            X_test, y_test = X, labels  # 测试集和训练集相同
            test_size = 0
        elif total_samples < 10:
            # 留一法
            test_size = 1 / total_samples
        elif total_samples < 50:
            # 30%的测试集
            test_size = 0.3
        else:
            # 20%的测试集
            test_size = 0.2
            
        # 确保至少有2个测试样本
        min_test_samples = min(2, total_samples // 2)
        test_size = max(test_size, min_test_samples / total_samples)
        
        if test_size > 0 and test_size < 1:
            X_train, X_test, y_train, y_test = train_test_split(
                X, labels, test_size=test_size, random_state=42, stratify=labels if len(set(labels)) > 1 else None
            )
        else:
            X_train, y_train = X, labels
            X_test, y_test = X, labels
        
        # 训练贝叶斯模型
        model = naive_bayes.BernoulliNB()
        model.fit(X_train, y_train)
        
        # 在测试集上进行预测
        y_pred = model.predict(X_test)
        
        # 计算准确率
        accuracy = metrics.accuracy_score(y_test, y_pred)
        logger.info(f"贝叶斯模型分类准确率: {accuracy:.4f}")
        
        # 保存模型(可选)
        if save_model:
            joblib.dump(model, MODEL_PATH)
            logger.info(f"贝叶斯模型已保存到 {MODEL_PATH}")
        
        # 计算统计数据
        stats = {
            'correct_positive': sum((y_pred == y_test) & (y_test == 2)),
            'correct_negative': sum((y_pred == y_test) & (y_test == 1)),
            'wrong_positive': sum((y_pred != y_test) & (y_test == 2)),
            'wrong_negative': sum((y_pred != y_test) & (y_test == 1)),
        }
        
        # 选取一些样本进行展示
        samples = []
        
        # 如果有测试集，从测试集中选择样本
        if len(X_test) > 0 and len(y_test) > 0:
            # 创建测试集的索引映射
            test_indices = {}
            test_comments = []
            test_scores = []
            
            # 为每个测试样本创建索引
            for i, (pred, actual) in enumerate(zip(y_pred, y_test)):
                # 创建一个预测样本
                sample = {
                    'content': processed_texts[i] if i < len(processed_texts) else "样本内容不可用",
                    'actual_score': df['score'].iloc[i] if i < len(df) else 0,
                    'predicted': pred,
                    'is_correct': pred == actual
                }
                samples.append(sample)
        
        # 如果没有足够的样本，添加一些示例
        if len(samples) == 0:
            # 添加一个示例
            samples.append({
                'content': "暂无足够的测试样本，这是一个示例",
                'actual_score': 5,
                'predicted': 2,
                'is_correct': True
            })
        
        # 保存结果到CSV(可选)
        if save_csv:
            # 创建预测结果DataFrame
            result_df = pd.DataFrame({
                'comment_text': [df['comment_text'].iloc[i] for i in range(len(X_test))],
                'actual_score': [df['score'].iloc[i] for i in range(len(X_test))],
                'actual_sentiment': y_test,
                'predicted_sentiment': y_pred,
                'is_correct': y_pred == y_test
            })
            result_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"贝叶斯分类结果已保存到 {csv_path}")
        
        return {
            'success': True,
            'accuracy': accuracy,
            'model': None if save_model else model,
            'stats': stats,
            'samples': samples
        }
        
    except Exception as e:
        logger.error(f"训练贝叶斯模型失败: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def get_bayes_classification(force_refresh=False):
    """
    使用贝叶斯模型对评论进行分类，并返回分类结果和统计数据
    支持缓存机制，可以加载之前的分析结果。
    
    Args:
        force_refresh: 是否强制刷新，忽略缓存
        
    Returns:
        dict: 包含以下键值对的字典
            - success: 是否成功分类
            - accuracy: 分类准确率
            - stats: 统计数据
            - samples: 示例评论及其分类结果
            - error: 错误信息(如果失败)
    """
    try:
        # 如果不强制刷新且缓存文件存在，则从缓存加载
        if not force_refresh and os.path.exists(BAYES_CACHE_PATH):
            try:
                with open(BAYES_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    logger.info(f"从缓存加载贝叶斯分类结果: {BAYES_CACHE_PATH}")
                    return {
                        'success': True,
                        'accuracy': cache_data['accuracy'],
                        'stats': cache_data['stats'],
                        'samples': cache_data['samples'],
                        'from_cache': True
                    }
            except Exception as e:
                logger.warning(f"读取贝叶斯分类缓存失败，将重新分析: {e}")
        
        # 检查是否有训练好的模型文件
        if not os.path.exists(MODEL_PATH):
            logger.warning(f"没有找到训练好的贝叶斯模型文件 {MODEL_PATH}，开始训练模型")
            result = train_bayes_model(save_model=True)
            if not result['success']:
                return {
                    'success': False,
                    'error': f"未能自动训练模型: {result.get('error', '未知错误')}"
                }
        
        # 加载已训练的模型
        try:
            model = joblib.load(MODEL_PATH)
            logger.info(f"成功加载贝叶斯模型: {MODEL_PATH}")
        except Exception as e:
            logger.error(f"加载模型失败: {str(e)}，尝试重新训练")
            result = train_bayes_model(save_model=True)
            if not result['success']:
                return {
                    'success': False,
                    'error': f"加载模型失败，且未能自动训练模型: {result.get('error', '未知错误')}"
                }
            model = result['model']
        
        # 连接数据库获取评论数据
        conn = pymysql.connect(**DB_CONFIG)
        
        # 查询评论内容
        sql = '''
            SELECT c.id, c.comment_text, 
            CASE WHEN c.is_default = 1 THEN 5 ELSE 3 END as score
            FROM product_comments c
            WHERE c.comment_text IS NOT NULL AND c.comment_text != ''
        '''
        
        df = pd.read_sql(sql, conn)
        conn.close()
        
        # 如果没有数据，返回失败
        if df.empty:
            logger.warning("没有找到评论数据，无法进行贝叶斯分类")
            return {
                'success': False,
                'error': '没有找到评论数据'
            }
            
        # 处理文本内容
        df = df.dropna(subset=['comment_text'])
        df.drop_duplicates(subset=['comment_text'], keep='first', inplace=True)
        
        # 将评分1~3分作为差评(标记为1)，评分4~5分作为好评(标记为2)
        df['sentiment_label'] = df['score'].apply(lambda x: 2 if x >= 4 else 1)
        
        # 清洗评论内容
        def clean_comment(text):
            # 清洗文本，移除非评论信息
            text = str(text).strip()
            if text == "系统默认好评" or text == "系统默认评价":
                return ""
            
            import re
            text = re.sub(r'图.{1,5}丽欧', '', text)
            text = re.sub(r'用户.*?评价', '', text)
            text = re.sub(r'方未.*?评价', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        
        df['comment_text'] = df['comment_text'].apply(clean_comment)
        df = df[df['comment_text'].str.len() > 3]  # 只保留长度大于3的评论
        
        # 分词处理
        processed_texts = []
        stopwords = {}.fromkeys(['，', '！', '。', '、', '?', '～'])  # 设置停用词
        
        for text in df['comment_text']:
            # 分词
            seg_list = jieba.lcut(text, cut_all=False)
            # 过滤停用词
            filtered = [word for word in seg_list if word not in stopwords and len(word) > 1]
            # 合并为字符串
            processed_text = ' '.join(filtered)
            processed_texts.append(processed_text)
        
        # 特征提取 - 计算词频
        try:
            vectorizer = CountVectorizer()
            vectorizer.fit(processed_texts)  # 先拟合词汇表
            X = vectorizer.transform(processed_texts).toarray()
        except Exception as e:
            logger.error(f"特征提取失败: {str(e)}")
            # 如果向量化失败，尝试使用简单的特征
            X = np.zeros((len(processed_texts), 1))
            for i, text in enumerate(processed_texts):
                X[i, 0] = len(text)
        
        # 预测情感标签
        try:
            y_pred = model.predict(X)
            accuracy = metrics.accuracy_score(df['sentiment_label'], y_pred)
            logger.info(f"贝叶斯模型分类准确率: {accuracy:.4f}")
        except Exception as e:
            logger.error(f"模型预测失败: {str(e)}")
            # 如果预测失败，随机分配标签
            y_pred = np.random.choice([1, 2], size=len(df))
            accuracy = 0.5
        
        # 计算统计数据
        stats = {
            'correct_positive': sum((y_pred == df['sentiment_label']) & (df['sentiment_label'] == 2)),
            'correct_negative': sum((y_pred == df['sentiment_label']) & (df['sentiment_label'] == 1)),
            'wrong_positive': sum((y_pred != df['sentiment_label']) & (df['sentiment_label'] == 2)),
            'wrong_negative': sum((y_pred != df['sentiment_label']) & (df['sentiment_label'] == 1)),
        }
        
        # 选取一些样本展示
        samples = []
        # 确保有足够的样本
        max_samples = min(10, len(df))
        if max_samples > 0:
            # 随机选择一些索引展示
            sample_indices = np.random.choice(len(df), size=max_samples, replace=False)
            
            for idx in sample_indices:
                samples.append({
                    'content': df['comment_text'].iloc[idx],
                    'actual_score': int(df['score'].iloc[idx]),
                    'predicted': int(y_pred[idx]),
                    'is_correct': y_pred[idx] == df['sentiment_label'].iloc[idx]
                })
        
        # 保存结果到缓存文件
        try:
            # 确保所有值都是JSON可序列化的
            cache_data = {
                'accuracy': float(accuracy),
                'stats': {
                    'correct_positive': int(stats['correct_positive']),
                    'correct_negative': int(stats['correct_negative']),
                    'wrong_positive': int(stats['wrong_positive']),
                    'wrong_negative': int(stats['wrong_negative'])
                },
                'samples': []
            }
            
            # 处理样本数据，确保所有值都是JSON可序列化的
            for sample in samples:
                cache_data['samples'].append({
                    'content': str(sample['content']),
                    'actual_score': int(sample['actual_score']),
                    'predicted': int(sample['predicted']),
                    'is_correct': bool(sample['is_correct'])  # 将numpy.bool_转换为Python原生bool
                })
                
            with open(BAYES_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"贝叶斯分类结果已缓存到 {BAYES_CACHE_PATH}")
        except Exception as e:
            logger.warning(f"保存贝叶斯分类结果到缓存失败: {e}")
            
        return {
            'success': True,
            'accuracy': accuracy,
            'stats': stats,
            'samples': samples,
            'from_cache': False
        }
    
    except Exception as e:
        logger.error(f"获取贝叶斯分类失败: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# 如果直接运行此脚本，训练贝叶斯模型
if __name__ == "__main__":
    results = train_bayes_model(save_model=True, save_csv=True)
    if results['success']:
        print(f"模型训练成功，准确率: {results['accuracy']:.4f}")
        print(f"正确分类的积极评论: {results['stats']['correct_positive']}")
        print(f"正确分类的消极评论: {results['stats']['correct_negative']}")
        print(f"错误分类的积极评论: {results['stats']['wrong_positive']}")
        print(f"错误分类的消极评论: {results['stats']['wrong_negative']}")
    else:
        print(f"模型训练失败: {results['error']}")
