import sqlite3
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# 放行跨域，确保前后端连通
CORS(app, origins=[
    "https://trace-fronted-delta.online",
    "https://www.trace-fronted-delta.online",
    "https://trace-fronted-delta.vercel.app"
])

# 确保在云端环境下绝对路径准确
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trace_memory.db')

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 建立行迹节点表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS travel_nodes (
            node_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_code TEXT NOT NULL,
            visit_date TEXT NOT NULL,
            visit_time TEXT,
            city TEXT NOT NULL,
            location_name TEXT,
            companion TEXT,
            photo_urls TEXT,  
            diary_text TEXT,
            expense REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 建立用户鉴权表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_code TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# 1. 登录与注册聚合接口
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        user_code = data.get('user_code', '').strip()
        password = data.get('password', '').strip()
        
        if not user_code or not password:
            return jsonify({"status": "error", "message": "需提供暗号与密钥"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE user_code = ?", (user_code,))
        row = cursor.fetchone()

        if row:
            if check_password_hash(row[0], password):
                conn.close()
                return jsonify({"status": "success", "message": "身份核验通过，欢迎回归"}), 200
            else:
                conn.close()
                return jsonify({"status": "error", "message": "身份核验失败，密钥错误"}), 401
        else:
            hashed_pw = generate_password_hash(password)
            cursor.execute("INSERT INTO users (user_code, password_hash) VALUES (?, ?)", (user_code, hashed_pw))
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "message": "全新记忆空域已开辟"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 2. 录入接口 (增)
@app.route('/api/add_node', methods=['POST'])
def add_node():
    try:
        data = request.json
        if not data: return jsonify({"status": "error", "message": "无效数据"}), 400
        
        user_code = data.get('user_code')
        visit_date = data.get('visit_date')
        city = data.get('city')
        
        if not user_code or not visit_date or not city:
            return jsonify({"status": "error", "message": "缺失核心标识"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO travel_nodes (user_code, visit_date, visit_time, city, location_name, companion, diary_text, photo_urls, expense)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_code, visit_date, data.get('visit_time', ''), city, 
              data.get('location_name', ''), data.get('companion', ''), data.get('diary_text', ''), data.get('photo_urls', ''), data.get('expense', None)))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "行迹归仓"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 3. 修改接口 (改) - V1.2新增
@app.route('/api/update_node', methods=['POST'])
def update_node():
    try:
        data = request.json
        if not data or not data.get('node_id') or not data.get('user_code'):
            return jsonify({"status": "error", "message": "缺少必要标识"}), 400
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE travel_nodes 
            SET visit_date=?, visit_time=?, city=?, location_name=?, companion=?, diary_text=?, expense=?, photo_urls=?
            WHERE node_id=? AND user_code=?
        ''', (data.get('visit_date'), data.get('visit_time', ''), data.get('city'), 
              data.get('location_name', ''), data.get('companion', ''), data.get('diary_text', ''), 
              data.get('expense', None), data.get('photo_urls', ''), data.get('node_id'), data.get('user_code')))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "记忆已修正"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 4. 删除接口 (删) - V1.2新增
@app.route('/api/delete_node', methods=['POST'])
def delete_node():
    try:
        data = request.json
        if not data or not data.get('node_id') or not data.get('user_code'):
            return jsonify({"status": "error", "message": "缺少必要标识"}), 400
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM travel_nodes WHERE node_id=? AND user_code=?", (data.get('node_id'), data.get('user_code')))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "记忆已擦除"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 5. 查询接口 (查) - 完整还原 V1.1 的序列化逻辑
@app.route('/api/get_nodes', methods=['GET'])
def get_nodes():
    try:
        user_code = request.args.get('user_code', None)
        if not user_code: return jsonify({"status": "success", "data": []}), 200

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # 必须按照严格顺序 SELECT，否则索引会错乱
        cursor.execute('''
            SELECT node_id, visit_date, visit_time, city, location_name, companion, photo_urls, diary_text, expense 
            FROM travel_nodes 
            WHERE user_code = ? 
            ORDER BY visit_date DESC, visit_time DESC
        ''', (user_code,))
        rows = cursor.fetchall()
        conn.close()

        nodes_list = []
        for row in rows:
            raw_photos = row[6] 
            # 这里的 photo 处理逻辑是前端展示照片的核心，绝不能省
            photo_array = raw_photos.split('|||') if (raw_photos and raw_photos.strip() != "") else []
            node = {
                "node_id": row[0], "visit_date": row[1], "visit_time": row[2],
                "city": row[3], "location_name": row[4], "companion": row[5],
                "photo_urls": photo_array, "diary_text": row[7], "expense": row[8]
            }
            nodes_list.append(node)
        return jsonify({"status": "success", "data": nodes_list}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)