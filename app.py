import sqlite3
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app, origins=["https://trace-fronted-delta.online", "https://www.trace-fronted-delta.online", "https://trace-fronted-delta.vercel.app"])

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trace_memory.db')

# 升级版数据库连接器：支持通过列名获取数据，防止索引错乱
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # 行迹表 (100% 兼容你的旧数据)
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
    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_code TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            avatar_url TEXT
        )
    ''')
    # 静默升级老数据库（为你之前的旧账号增加头像列）
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except Exception:
        pass 
        
    conn.commit()
    conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        user_code = data.get('user_code', '').strip()
        password = data.get('password', '').strip()
        
        conn = get_db_connection()
        row = conn.execute("SELECT password_hash, avatar_url FROM users WHERE user_code = ?", (user_code,)).fetchone()
        conn.close()

        if row and check_password_hash(row['password_hash'], password):
            return jsonify({"status": "success", "message": "欢迎回归星空", "avatar": row['avatar_url']}), 200
        else:
            return jsonify({"status": "error", "message": "账号或密钥错误，如果是新漫游者请选择[开辟新空域]"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        user_code = data.get('user_code', '').strip()
        password = data.get('password', '').strip()

        if not user_code or not password:
            return jsonify({"status": "error", "message": "账号与密钥不能为空"}), 400

        conn = get_db_connection()
        if conn.execute("SELECT user_code FROM users WHERE user_code = ?", (user_code,)).fetchone():
            conn.close()
            return jsonify({"status": "error", "message": "该账号已被其他漫游者借用，请换一个专属标识"}), 409
            
        hashed_pw = generate_password_hash(password)
        conn.execute("INSERT INTO users (user_code, password_hash) VALUES (?, ?)", (user_code, hashed_pw))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "全新记忆空域已开辟"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/add_node', methods=['POST'])
def add_node():
    try:
        data = request.json
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO travel_nodes (user_code, visit_date, visit_time, city, location_name, companion, diary_text, photo_urls, expense)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data.get('user_code'), data.get('visit_date'), data.get('visit_time', ''), data.get('city'), 
              data.get('location_name', ''), data.get('companion', ''), data.get('diary_text', ''), data.get('photo_urls', ''), data.get('expense')))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/update_node', methods=['POST'])
def update_node():
    try:
        data = request.json
        conn = get_db_connection()
        conn.execute('''
            UPDATE travel_nodes 
            SET visit_date=?, visit_time=?, city=?, location_name=?, companion=?, diary_text=?, expense=?, photo_urls=?
            WHERE node_id=? AND user_code=?
        ''', (data.get('visit_date'), data.get('visit_time', ''), data.get('city'), 
              data.get('location_name', ''), data.get('companion', ''), data.get('diary_text', ''), 
              data.get('expense'), data.get('photo_urls', ''), data.get('node_id'), data.get('user_code')))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete_node', methods=['POST'])
def delete_node():
    try:
        data = request.json
        conn = get_db_connection()
        conn.execute("DELETE FROM travel_nodes WHERE node_id=? AND user_code=?", (data.get('node_id'), data.get('user_code')))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get_nodes', methods=['GET'])
def get_nodes():
    try:
        user_code = request.args.get('user_code')
        if not user_code: return jsonify({"status": "success", "data": []}), 200
        
        conn = get_db_connection()
        rows = conn.execute("SELECT * FROM travel_nodes WHERE user_code = ? ORDER BY visit_date DESC, visit_time DESC", (user_code,)).fetchall()
        conn.close()

        nodes_list = []
        for row in rows:
            raw_photos = row['photo_urls']
            photo_array = raw_photos.split('|||') if (raw_photos and raw_photos.strip() != "") else []
            nodes_list.append({
                "node_id": row['node_id'], "visit_date": row['visit_date'], "visit_time": row['visit_time'],
                "city": row['city'], "location_name": row['location_name'], "companion": row['companion'],
                "photo_urls": photo_array, "diary_text": row['diary_text'], "expense": row['expense']
            })
        return jsonify({"status": "success", "data": nodes_list}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/update_avatar', methods=['POST'])
def update_avatar():
    try:
        data = request.json
        conn = get_db_connection()
        conn.execute("UPDATE users SET avatar_url=? WHERE user_code=?", (data.get('avatar_url'), data.get('user_code')))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error"}), 500

@app.route('/api/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        # 预留飞书 Webhook 接口
        return jsonify({"status": "success", "message": "星空监测员已收到您的反馈！"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)