from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from neo4j import GraphDatabase
import json
import sqlite3
import hashlib
from datetime import datetime
from functools import wraps
from ai_q_and_a import natural_language_to_cypher, query_neo4j, cypher_result_to_natural_language

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Neo4j连接配置
class Neo4jConnection:
    def __init__(self, uri, user, password):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("✅ Neo4j连接成功!")
        except Exception as e:
            print(f"❌ Neo4j连接失败: {e}")
            self.driver = None
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def get_initial_graph_data(self):
        """获取初始图谱数据 - AFFECTED_BY和GROWS_IN关系"""
        if not self.driver:
            raise Exception("Neo4j连接未建立")
            
        with self.driver.session() as session:
            # 查询AFFECTED_BY关系
            affected_by_query = "MATCH p=()-[:AFFECTED_BY]->() RETURN p LIMIT 25"
            grows_in_query = "MATCH p=()-[:GROWS_IN]->() RETURN p LIMIT 25"
            
            nodes = {}
            relationships = []
            
            # 处理AFFECTED_BY关系
            affected_result = session.run(affected_by_query)
            for record in affected_result:
                path = record["p"]
                start_node = path.start_node
                end_node = path.end_node
                relationship = path.relationships[0]
                
                # 添加节点
                nodes[start_node.id] = {
                    "id": start_node.id,
                    "labels": list(start_node.labels),
                    "properties": dict(start_node)
                }
                nodes[end_node.id] = {
                    "id": end_node.id,
                    "labels": list(end_node.labels),
                    "properties": dict(end_node)
                }
                
                # 添加关系
                relationships.append({
                    "source": start_node.id,
                    "target": end_node.id,
                    "type": relationship.type,
                    "properties": dict(relationship)
                })
            
            # 处理GROWS_IN关系
            grows_result = session.run(grows_in_query)
            for record in grows_result:
                path = record["p"]
                start_node = path.start_node
                end_node = path.end_node
                relationship = path.relationships[0]
                
                # 添加节点
                nodes[start_node.id] = {
                    "id": start_node.id,
                    "labels": list(start_node.labels),
                    "properties": dict(start_node)
                }
                nodes[end_node.id] = {
                    "id": end_node.id,
                    "labels": list(end_node.labels),
                    "properties": dict(end_node)
                }
                
                # 添加关系
                relationships.append({
                    "source": start_node.id,
                    "target": end_node.id,
                    "type": relationship.type,
                    "properties": dict(relationship)
                })
            
            return {"nodes": list(nodes.values()), "relationships": relationships}

    def get_nodes_and_relationships(self, limit=50):
        """获取节点和关系数据"""
        if not self.driver:
            raise Exception("Neo4j连接未建立")
            
        with self.driver.session() as session:
            # 获取节点
            nodes_query = f"""
            MATCH (n) 
            RETURN id(n) as id, labels(n) as labels, properties(n) as properties
            LIMIT {limit}
            """
            nodes_result = session.run(nodes_query)
            nodes = []
            node_ids = set()
            
            for record in nodes_result:
                node_id = record["id"]
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "labels": record["labels"],
                    "properties": record["properties"]
                })
            
            # 获取这些节点之间的关系
            if node_ids:
                relationships_query = """
                MATCH (n)-[r]->(m) 
                WHERE id(n) IN $node_ids AND id(m) IN $node_ids
                RETURN id(n) as source, id(m) as target, type(r) as type, properties(r) as properties
                """
                relationships_result = session.run(relationships_query, node_ids=list(node_ids))
                relationships = []
                
                for record in relationships_result:
                    relationships.append({
                        "source": record["source"],
                        "target": record["target"],
                        "type": record["type"],
                        "properties": record["properties"]
                    })
            else:
                relationships = []
            
            return {"nodes": nodes, "relationships": relationships}

    def search_by_entity_and_property(self, entity_type, property_key, property_value, limit=50):
        """根据实体类型和属性搜索"""
        if not self.driver:
            raise Exception("Neo4j连接未建立")
            
        with self.driver.session() as session:
            query = f"""
            MATCH (n:{entity_type})
            WHERE n.{property_key} = $value
            WITH n
            LIMIT $limit
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, r, m
            """
            
            result = session.run(query, value=property_value, limit=limit)
            
            nodes = {}
            relationships = []
            
            for record in result:
                # 处理主节点
                main_node = record["n"]
                nodes[main_node.id] = {
                    "id": main_node.id,
                    "labels": list(main_node.labels),
                    "properties": dict(main_node)
                }
                
                # 处理关系和相关节点
                if record["m"]:
                    rel = record["r"]
                    related_node = record["m"]
                    
                    # 添加相关节点
                    nodes[related_node.id] = {
                        "id": related_node.id,
                        "labels": list(related_node.labels),
                        "properties": dict(related_node)
                    }
                    
                    # 添加关系
                    relationships.append({
                        "source": main_node.id,
                        "target": related_node.id,
                        "type": rel.type,
                        "properties": dict(rel)
                    })
            
            return {"nodes": list(nodes.values()), "relationships": relationships}

    def get_view_data(self, view_type):
        """根据视图类型获取数据"""
        if not self.driver:
            raise Exception("Neo4j连接未建立")
            
        with self.driver.session() as session:
            nodes = {}
            relationships = []
            
            if view_type == "wheat-region":
                # 小麦-地区视图
                query = "MATCH p=()-[:GROWS_IN]->() RETURN p LIMIT 1000"
                result = session.run(query)
                
                for record in result:
                    path = record["p"]
                    start_node = path.start_node
                    end_node = path.end_node
                    relationship = path.relationships[0]
                    
                    # 添加节点
                    nodes[start_node.id] = {
                        "id": start_node.id,
                        "labels": list(start_node.labels),
                        "properties": dict(start_node)
                    }
                    nodes[end_node.id] = {
                        "id": end_node.id,
                        "labels": list(end_node.labels),
                        "properties": dict(end_node)
                    }
                    
                    # 添加关系
                    relationships.append({
                        "source": start_node.id,
                        "target": end_node.id,
                        "type": relationship.type,
                        "properties": dict(relationship)
                    })
                    
            elif view_type == "wheat-disease":
                # 小麦-病害视图
                query = "MATCH p=()-[:AFFECTED_BY]->() RETURN p LIMIT 100"
                result = session.run(query)
                
                for record in result:
                    path = record["p"]
                    start_node = path.start_node
                    end_node = path.end_node
                    relationship = path.relationships[0]
                    
                    # 添加节点
                    nodes[start_node.id] = {
                        "id": start_node.id,
                        "labels": list(start_node.labels),
                        "properties": dict(start_node)
                    }
                    nodes[end_node.id] = {
                        "id": end_node.id,
                        "labels": list(end_node.labels),
                        "properties": dict(end_node)
                    }
                    
                    # 添加关系
                    relationships.append({
                        "source": start_node.id,
                        "target": end_node.id,
                        "type": relationship.type,
                        "properties": dict(relationship)
                    })
                    
            else:
                # 默认图谱概览视图
                return self.get_initial_graph_data()
            
            return {"nodes": list(nodes.values()), "relationships": relationships}

def init_user_database():
    """初始化用户数据库"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # 创建用户行为记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            activity_type TEXT NOT NULL,
            activity_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_list (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 用户数据库初始化完成")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "请先登录", "redirect": "/login"}), 401
        return f(*args, **kwargs)
    return decorated_function

def log_user_activity(user_id, activity_type, activity_data=None):
    """记录用户行为"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_activities (user_id, activity_type, activity_data)
            VALUES (?, ?, ?)
        ''', (user_id, activity_type, json.dumps(activity_data) if activity_data else None))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"记录用户行为失败: {e}")

def hash_password(password):
    """对密码进行哈希处理"""
    return hashlib.sha256(password.encode()).hexdigest()

neo4j_conn = Neo4jConnection(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="Rhea@123"
)

@app.route('/')
def index():
    """主页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    """登录页面"""
    return render_template('login.html')

@app.route('/register')
def register():
    """注册页面"""
    return render_template('register.html')

@app.route('/admin')
@login_required
def admin_panel():
    """管理员面板"""
    # 管理员检查
    if session.get('username') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """用户登录API"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({"error": "请提供用户名和密码"}), 400
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # 查找用户
        cursor.execute('''
            SELECT id, username, password_hash FROM user_list 
            WHERE username = ?
        ''', (username,))
        
        user = cursor.fetchone()
        
        if user and user[2] == hash_password(password):
            # 登录成功
            session['user_id'] = user[0]
            session['username'] = user[1]
            
            # 更新最后登录时间
            cursor.execute('''
                UPDATE user_list SET last_login = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (user[0],))
            
            conn.commit()
            conn.close()
            
            # 记录登录行为
            log_user_activity(user[0], 'login', {'username': username})
            
            return jsonify({"message": "登录成功", "username": username})
        else:
            conn.close()
            return jsonify({"error": "用户名或密码错误"}), 401
            
    except Exception as e:
        return jsonify({"error": f"登录失败: {str(e)}"}), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    """用户注册API"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not username or not email or not password:
            return jsonify({"error": "请提供所有必需信息"}), 400
        
        if len(password) < 6:
            return jsonify({"error": "密码长度至少6位"}), 400
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # 检查用户名是否已存在
        cursor.execute('SELECT id FROM user_list WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "用户名已存在"}), 400
        
        # 检查邮箱是否已存在
        cursor.execute('SELECT id FROM user_list WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "邮箱已被注册"}), 400
        
        # 创建新用户
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO user_list (username, email, password_hash)
            VALUES (?, ?, ?)
        ''', (username, email, password_hash))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 记录注册行为
        log_user_activity(user_id, 'register', {'username': username, 'email': email})
        
        return jsonify({"message": "注册成功"})
        
    except Exception as e:
        return jsonify({"error": f"注册失败: {str(e)}"}), 500

@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    """用户登出API"""
    user_id = session.get('user_id')
    username = session.get('username')
    
    # 记录登出行为
    log_user_activity(user_id, 'logout', {'username': username})
    
    session.clear()
    return jsonify({"message": "登出成功"})

@app.route('/api/user/info')
@login_required
def get_user_info():
    """获取当前用户信息"""
    return jsonify({
        "user_id": session.get('user_id'),
        "username": session.get('username')
    })

@app.route('/api/graph-data')
@login_required
def get_graph_data():
    """获取图谱数据的API"""
    try:
        print("📡 收到图谱数据请求...")
        
        if not neo4j_conn.driver:
            return jsonify({"error": "Neo4j数据库连接失败，请检查连接配置"}), 500
        
        data = neo4j_conn.get_initial_graph_data()
        print(f"📊 返回数据: {len(data['nodes'])} 个节点, {len(data['relationships'])} 个关系")
        
        # 记录用户行为
        log_user_activity(session.get('user_id'), 'view_graph', {
            'nodes_count': len(data['nodes']),
            'relationships_count': len(data['relationships'])
        })
        
        return jsonify(data)
        
    except Exception as e:
        error_msg = f"数据库查询失败: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route('/api/search', methods=['POST'])
@login_required
def search_entities():
    """根据属性搜索实体"""
    try:
        data = request.get_json()
        entity_type = data.get('entity_type')
        property_key = data.get('property_key')
        property_value = data.get('property_value')
        limit = data.get('limit', 50)
        
        if not property_key or not property_value:
            return jsonify({"error": "请提供属性名和属性值"}), 400
        
        if not neo4j_conn.driver:
            return jsonify({"error": "Neo4j数据库连接失败"}), 500
        
        result = neo4j_conn.search_by_entity_and_property(entity_type, property_key, property_value, limit)
        
        print(f"🔍 搜索结果: {len(result['nodes'])} 个节点, {len(result['relationships'])} 个关系")
        # print(f"🔍 搜索结果: {len(result['nodes'])} 个节点")

        
        # 记录搜索行为
        log_user_activity(session.get('user_id'), 'search', {
            'entity_type': entity_type,
            'property_key': property_key,
            'property_value': property_value,
            'results_count': len(result['nodes'])
        })
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"搜索失败: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route('/api/question', methods=['POST'])
@login_required
def ask_question():
    """智能问答接口"""
    try:
        data = request.get_json()
        question = data.get('question')
        
        if not question:
            return jsonify({"error": "请提供问题"}), 400
        
        print(f"🤔 收到问题: {question}")
        
        # 1. 将自然语言转换为Cypher查询
        cypher = natural_language_to_cypher(question)
        print(f"🔍 生成的Cypher: {cypher}")
        
        # 2. 执行Neo4j查询
        result = query_neo4j(cypher)
        print(f"📊 查询结果: {len(result) if result else 0} 条记录")
        
        # 3. 将结果转换为自然语言回答
        answer = cypher_result_to_natural_language(result, question)
        print(f"💬 生成回答: {answer[:100]}...")
        
        # 记录问答行为
        log_user_activity(session.get('user_id'), 'question', {
            'question': question,
            'cypher': cypher,
            'results_count': len(result) if result else 0
        })
        
        return jsonify({
            "question": question,
            "cypher": cypher,
            "result": result,
            "answer": answer
        })
        
    except Exception as e:
        error_msg = f"问答失败: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route('/api/node/<int:node_id>')
@login_required
def get_node_details(node_id):
    """获取节点详细信息"""
    try:
        if not neo4j_conn.driver:
            return jsonify({"error": "Neo4j数据库连接失败"}), 500
            
        with neo4j_conn.driver.session() as session:
            query = """
            MATCH (n) 
            WHERE id(n) = $node_id
            RETURN id(n) as id, labels(n) as labels, properties(n) as properties
            """
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if record:
                # 记录查看节点行为
                log_user_activity(session.get('user_id'), 'view_node', {
                    'node_id': node_id,
                    'labels': record["labels"]
                })
                
                return jsonify({
                    "id": record["id"],
                    "labels": record["labels"],
                    "properties": record["properties"]
                })
            else:
                return jsonify({"error": "Node not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def health_check():
    """健康检查端点"""
    try:
        if neo4j_conn.driver:
            with neo4j_conn.driver.session() as session:
                session.run("RETURN 1")
            return jsonify({"status": "healthy", "neo4j": "connected"})
        else:
            return jsonify({"status": "unhealthy", "neo4j": "disconnected"}), 500
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/api/view/<view_type>')
@login_required
def get_view_data(view_type):
    """获取特定视图的数据"""
    try:
        print(f"📡 收到视图数据请求: {view_type}")
        
        if not neo4j_conn.driver:
            return jsonify({"error": "Neo4j数据库连接失败，请检查连接配置"}), 500
        
        data = neo4j_conn.get_view_data(view_type)
        print(f"📊 返回{view_type}视图数据: {len(data['nodes'])} 个节点, {len(data['relationships'])} 个关系")
        
        # 记录视图切换行为
        log_user_activity(session.get('user_id'), 'change_view', {
            'view_type': view_type,
            'nodes_count': len(data['nodes']),
            'relationships_count': len(data['relationships'])
        })
        
        return jsonify(data)
        
    except Exception as e:
        error_msg = f"视图数据查询失败: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route('/api/admin/users')
@login_required
def get_all_users():
    """获取所有用户信息（管理员功能）"""
    if session.get('username') != 'admin':  # 管理员权限检查
        return jsonify({"error": "权限不足"}), 403
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, email, created_at, last_login 
            FROM user_list 
            ORDER BY created_at DESC
        ''')
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'created_at': row[3],
                'last_login': row[4]
            })
        
        conn.close()
        return jsonify(users)
        
    except Exception as e:
        return jsonify({"error": f"获取用户列表失败: {str(e)}"}), 500

@app.route('/api/admin/activities')
@login_required
def get_user_activities():
    """获取用户行为记录（管理员功能）"""
    if session.get('username') != 'admin':  # 管理员权限检查
        return jsonify({"error": "权限不足"}), 403
    
    try:
        user_id = request.args.get('user_id')
        limit = request.args.get('limit', 100)
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        if user_id:
            # 获取特定用户的行为记录
            cursor.execute('''
                SELECT ua.id, ua.user_id, ul.username, ua.activity_type, 
                       ua.activity_data, ua.timestamp
                FROM user_activities ua
                JOIN user_list ul ON ua.user_id = ul.id
                WHERE ua.user_id = ?
                ORDER BY ua.timestamp DESC
                LIMIT ?
            ''', (user_id, limit))
        else:
            # 获取所有用户的行为记录
            cursor.execute('''
                SELECT ua.id, ua.user_id, ul.username, ua.activity_type, 
                       ua.activity_data, ua.timestamp
                FROM user_activities ua
                JOIN user_list ul ON ua.user_id = ul.id
                ORDER BY ua.timestamp DESC
                LIMIT ?
            ''', (limit,))
        
        activities = []
        for row in cursor.fetchall():
            activity_data = json.loads(row[4]) if row[4] else {}
            activities.append({
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'activity_type': row[3],
                'activity_data': activity_data,
                'timestamp': row[5]
            })
        
        conn.close()
        return jsonify(activities)
        
    except Exception as e:
        return jsonify({"error": f"获取行为记录失败: {str(e)}"}), 500

# 初始化数据库和Neo4j连接
init_user_database()

if __name__ == '__main__':
    print("🚀 启动知识图谱可视化系统...")
    print("📍 访问地址: http://localhost:5000")
    print("🔧 健康检查: http://localhost:5000/api/health")
    app.run(debug=True, host='0.0.0.0', port=5000)
