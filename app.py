import sqlite3
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from werkzeug.security import generate_password_hash, check_password_hash

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

# 升级版数据库连接器：支持通过列名获取数据，防止索引错乱
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

    # 静默升级老数据库
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE travel_nodes ADD COLUMN latitude REAL")
        cursor.execute("ALTER TABLE travel_nodes ADD COLUMN longitude REAL")
    except Exception:
        pass

    # 🚨 核心增长线：若公共演示舱无数据，则自动静默注入 3 条充满诗意的官方星图样板
    cursor.execute("SELECT COUNT(*) FROM travel_nodes WHERE user_code = 'demo_explorer'")
    if cursor.fetchone()[0] == 0:
        # 为了让新用户一进来就能完美看到你的[照片堆叠与发散动画]，我们内置了精美的矢量艺术 Base64 占位图
        mock_photo_paris = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><rect width='200' height='200' fill='%23f97316'/><text x='50%25' y='50%25' font-size='16' fill='white' dominant-baseline='middle' text-anchor='middle'>Sunset Paris</text></svg>"
        mock_photo_bj = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><rect width='200' height='200' fill='%23dc2626'/><text x='50%25' y='50%25' font-size='16' fill='white' dominant-baseline='middle' text-anchor='middle'>Forbidden City</text></svg>"
        mock_photo_sh = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><rect width='200' height='200' fill='%232563eb'/><text x='50%25' y='50%25' font-size='16' fill='white' dominant-baseline='middle' text-anchor='middle'>Cyber Bund</text></svg>"

        demo_nodes = [
            ('demo_explorer', '2026-05-12', '19:15', '巴黎市', '埃菲尔铁塔下', '独自漫游', '塞纳河畔的微风夹杂着烘焙的香气，日落余晖将铁塔染成迷人的橘粉色。那一刻，时空仿佛在慢镜头里静止，浪漫本身不需要旁白。', mock_photo_paris, 120.0, 48.8584, 2.2945),
            ('demo_explorer', '2026-06-18', '05:40', '北京市', '景山公园万春亭', '与旧友', '赶在破晓前登顶，看金色的晨光一寸寸铺满故宫浩瀚的琉璃瓦。古老的紫禁城在紫气晨雾中缓缓苏醒，巍峨而静谧。', mock_photo_bj, 15.0, 39.9243, 116.3967),
            ('demo_explorer', '2026-07-07', '21:30', '上海市', '外滩观景台', '独自漫游', '黄浦江两岸霓虹交错，陆家嘴的万丈摩天轮与十里洋场的万国建筑对望。都市的赛博朋克与历史的厚重感在江风中完美交融。', mock_photo_sh, 85.0, 31.2405, 121.4896)
        ]
        cursor.executemany('''
            INSERT INTO travel_nodes (user_code, visit_date, visit_time, city, location_name, companion, diary_text, photo_urls, expense, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', demo_nodes)

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
        # 🚨 物理拦截：坚决阻止任何人篡改官方样板演示星图
        if data.get('user_code') == 'demo_explorer':
            return jsonify({"status": "error", "message": "🔒 演示舱仅供观星，无法篡改他人的星轨哦"}), 403
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO travel_nodes (user_code, visit_date, visit_time, city, location_name, companion, diary_text, photo_urls, expense, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data.get('user_code'), data.get('visit_date'), data.get('visit_time', ''), data.get('city'),
              data.get('location_name', ''), data.get('companion', ''), data.get('diary_text', ''),
              data.get('photo_urls', ''), data.get('expense'), data.get('latitude'), data.get('longitude')))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/update_node', methods=['POST'])
def update_node():
    try:
        data = request.json
        if data.get('user_code') == 'demo_explorer':
            return jsonify({"status": "error", "message": "🔒 演示舱仅供观星，无法篡改他人的星轨哦"}), 403
        conn = get_db_connection()
        conn.execute('''
            UPDATE travel_nodes
            SET visit_date=?, visit_time=?, city=?, location_name=?, companion=?, diary_text=?, expense=?, photo_urls=?, latitude=?, longitude=?
            WHERE node_id=? AND user_code=?
        ''', (data.get('visit_date'), data.get('visit_time', ''), data.get('city'),
              data.get('location_name', ''), data.get('companion', ''), data.get('diary_text', ''),
              data.get('expense'), data.get('photo_urls', ''), data.get('latitude'), data.get('longitude'),
              data.get('node_id'), data.get('user_code')))
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
                "latitude": row['latitude'], "longitude": row['longitude']
            })
        return jsonify({"status": "success", "data": nodes_list}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

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
# 将 app.py 最下方的 submit_feedback 函数替换为以下内容：
@app.route('/api/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        user_code = data.get('user_code', '匿名漫游者')
        fb_type = data.get('type', '未分类')
        content = data.get('content', '')

        if not content:
            return jsonify({"status": "error", "message": "吐槽内容不能为空哦"}), 400

        # ====== 已经为你填入专属的飞书机器人链接 ======
        FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/81a23155-ca57-4e19-abcc-27dad30d36d7"

        # ====== 组装原生的消息卡片格式 ======
        msg_text = f"🚨 收到来自漫游舱的新反馈！\n\n👤 漫游者：{user_code}\n🏷️ 类型：{fb_type}\n💬 内容：{content}"
        payload = {
            "msg_type": "text",
            "content": {
                "text": msg_text
            }
        }

        # ====== 发送至飞书群 ======
        res = requests.post(FEISHU_WEBHOOK_URL, json=payload)

        if res.status_code == 200:
            return jsonify({"status": "success", "message": "发射成功！星空监测员已收到"}), 200
        else:
            return jsonify({"status": "error", "message": "发射失败，飞书机器人信号微弱"}), 500

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)