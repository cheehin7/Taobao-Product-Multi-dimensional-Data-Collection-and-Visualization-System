"""
最小化版本的Flask应用，用于测试API路由
"""
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return "API测试服务器正常运行"

@app.route('/api/test', methods=['GET', 'POST'])
def test_api():
    """测试API路由"""
    return jsonify({
        'success': True,
        'message': 'API路由正常工作',
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/comments/start', methods=['POST'])
def test_comments_start():
    """测试评论爬取启动API"""
    return jsonify({
        'success': True,
        'status': 'waiting_login',
        'message': '评论爬取测试API正常工作'
    })

if __name__ == '__main__':
    print("\n===================== 已注册的API路由 =====================")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]")
    print("==========================================================\n")
    
    print("测试服务器启动中...")
    print("访问地址: http://127.0.0.1:5001")
    print("按 Ctrl+C 停止服务器")
    
    app.run(host='127.0.0.1', port=5001, debug=True) 