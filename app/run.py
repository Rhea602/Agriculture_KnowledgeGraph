# 启动脚本
from app import app, neo4j_conn
import atexit

def cleanup():
    """程序退出时清理资源"""
    neo4j_conn.close()

# 注册退出时的清理函数
atexit.register(cleanup)

if __name__ == '__main__':
    print("🚀 启动知识图谱可视化系统...")
    print("📍 请在浏览器中访问: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
