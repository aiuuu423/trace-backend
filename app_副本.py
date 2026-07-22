import sqlite3
import traceback
import os
import requests
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, origins=[
    "https://trace-fronted-delta.online",
    "https://www.trace-fronted-delta.online",
    "https://trace-fronted-delta.vercel.app",
    "http://127.0.0.1:5500",
    "http://localhost:5500"
])

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trace_memory.db')

# ==========================================
# 🌟 V1.4 物理图片存储基建
# ==========================================
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'heic'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # 行迹表
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
            latitude REAL,
            longitude REAL,
            province TEXT,
            formMode TEXT,
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
    
    # 🚨 核心增长线：若公共演示舱无数据，则自动静默注入官方星图样板
    cursor.execute("SELECT COUNT(*) FROM travel_nodes WHERE user_code = 'demo_explorer'")
    if cursor.fetchone()[0] == 0:
        mock_photo_paris = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><rect width='200' height='200' fill='%23f97316'/><text x='50%25' y='50%25' font-size='16' fill='white' dominant-baseline='middle' text-anchor='middle'>Sunset Paris</text></svg>"
        mock_photo_bj = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><rect width='200' height='200' fill='%23dc2626'/><text x='50%25' y='50%25' font-size='16' fill='white' dominant-baseline='middle' text-anchor='middle'>Forbidden City</text></svg>"
        mock_photo_sh = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><rect width='200' height='200' fill='%232563eb'/><text x='50%25' y='50%25' font-size='16' fill='white' dominant-baseline='middle' text-anchor='middle'>Cyber Bund</text></svg>"

        demo_nodes = [
            ('demo_explorer', '2026-05-12', '19:15', '巴黎市', '埃菲尔铁塔下', '独自漫游', '塞纳河畔的微风夹杂着烘焙的香气...', mock_photo_paris, 120.0, 48.8584, 2.2945, '海外', 'global'),
            ('demo_explorer', '2026-06-18', '05:40', '北京市', '景山公园万春亭', '与旧友', '赶在破晓前登顶，看金色的晨光...', mock_photo_bj, 15.0, 39.9243, 116.3967, '北京市', 'domestic')
        ]
        cursor.executemany('''
            INSERT INTO travel_nodes (user_code, visit_date, visit_time, city, location_name, companion, diary_text, photo_urls, expense, latitude, longitude, province, formMode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', demo_nodes)

    conn.commit()
    conn.close()

# ==========================================
# 🌟 路由与接口
# ==========================================

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
        # 拦截 NoneType 错误
        if data is None:
            return jsonify({"error": "No JSON payload received"}), 400

        if data.get('user_code') == 'demo_explorer':
            return jsonify({"status": "error", "message": "🔒 演示舱仅供观星，无法篡改他人的星轨哦"}), 403
            
        conn = get_db_connection()
        # 修复：补齐了全部字段
        conn.execute('''
            INSERT INTO travel_nodes (user_code, visit_date, visit_time, city, location_name, companion, diary_text, photo_urls, expense, latitude, longitude, province, formMode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('user_code'), data.get('visit_date'), data.get('visit_time', ''), 
            data.get('city'), data.get('location_name', ''), data.get('companion', ''), 
            data.get('diary_text', ''), data.get('photo_urls', ''), data.get('expense'), 
            data.get('latitude'), data.get('longitude'), data.get('province', ''), data.get('formMode', '')
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/update_node', methods=['POST'])
def update_node():
    try:
        data = request.json
        if data is None:
            return jsonify({"error": "No JSON payload received"}), 400

        if data.get('user_code') == 'demo_explorer':
            return jsonify({"status": "error", "message": "🔒 演示舱仅供观星，无法篡改他人的星轨哦"}), 403
            
        conn = get_db_connection()
        conn.execute('''
            UPDATE travel_nodes
            SET visit_date=?, visit_time=?, city=?, location_name=?, companion=?, diary_text=?, expense=?, photo_urls=?, latitude=?, longitude=?, province=?, formMode=?
            WHERE node_id=? AND user_code=?
        ''', (
            data.get('visit_date'), data.get('visit_time', ''), data.get('city'),
            data.get('location_name', ''), data.get('companion', ''), data.get('diary_text', ''),
            data.get('expense'), data.get('photo_urls', ''), data.get('latitude'), data.get('longitude'),
            data.get('province', ''), data.get('formMode', ''),
            data.get('node_id'), data.get('user_code')
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete_node', methods=['POST'])
def delete_node():
    try:
        data = request.json
        if data.get('user_code') == 'demo_explorer':
            return jsonify({"status": "error", "message": "🔒 演示舱仅供观星，无法篡改他人的星轨哦"}), 403
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
                "photo_urls": photo_array, "diary_text": row['diary_text'], "expense": row['expense'],
                "latitude": row['latitude'], "longitude": row['longitude'],
                "province": row['province'] if 'province' in row.keys() else '',
                "formMode": row['formMode'] if 'formMode' in row.keys() else ''
            })
        return jsonify({"status": "success", "data": nodes_list}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "未检测到文件流"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "文件名为空"}), 400

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        return jsonify({"status": "success", "url": f"/uploads/{unique_filename}"})

    return jsonify({"status": "error", "message": "不支持的文件格式"}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/update_avatar', methods=['POST'])
def update_avatar():
    try:
        data = request.json
        if data.get('user_code') == 'demo_explorer':
            return jsonify({"status": "error", "message": "🔒 演示舱仅供观星，无法修改公共面容哦"}), 403
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
        user_code = data.get('user_code', '匿名漫游者')
        fb_type = data.get('type', '未分类')
        content = data.get('content', '')
        if not content:
            return jsonify({"status": "error", "message": "吐槽内容不能为空哦"}), 400

        FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/81a23155-ca57-4e19-abcc-27dad30d36d7"
        msg_text = f"🚨 收到来自漫游舱的新反馈！\n\n👤 漫游者：{user_code}\n🏷️ 类型：{fb_type}\n💬 内容：{content}"
        payload = {"msg_type": "text", "content": {"text": msg_text}}
        res = requests.post(FEISHU_WEBHOOK_URL, json=payload)

        if res.status_code == 200:
            return jsonify({"status": "success", "message": "发射成功！星空监测员已收到"}), 200
        else:
            return jsonify({"status": "error", "message": "发射失败，飞书机器人信号微弱"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 🌟 修复版：终极数据库修复通道
# ==========================================
@app.route('/api/upgrade_db')
def upgrade_db():
    messages = []
    try:
        conn = get_db_connection()
        c = conn.cursor()

        columns_to_add = {
            "latitude": "REAL",
            "longitude": "REAL",
            "province": "TEXT",
            "formMode": "TEXT",
            "avatar_url": "TEXT"
        }
        
        # 修正：表名是 travel_nodes
        for col_name, col_type in columns_to_add.items():
            if col_name == "avatar_url":
                target_table = "users"
            else:
                target_table = "travel_nodes"
                
            try:
                c.execute(f"ALTER TABLE {target_table} ADD COLUMN {col_name} {col_type}")
                messages.append(f"✅ 成功在 {target_table} 添加字段: {col_name}")
            except sqlite3.OperationalError as e:
                messages.append(f"ℹ️ 字段跳过 (可能已存在): {col_name} - {str(e)}")
            except Exception as e:
                messages.append(f"❌ 字段失败: {col_name} - {str(e)}")

        conn.commit()
        conn.close()

        return "<br>".join(messages) + "<br><br><b>🎉 补丁运行完毕！请返回网站测试！</b>"
    except Exception as e:
        return f"🚨 发生致命错误: {str(e)}"

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)