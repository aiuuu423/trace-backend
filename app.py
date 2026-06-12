import sqlite3
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True)

DB_FILE = 'trace_memory.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

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

@app.route('/api/get_nodes', methods=['GET'])
def get_nodes():
    try:
        user_code = request.args.get('user_code', None)
        if not user_code: return jsonify({"status": "success", "data": []}), 200

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # 核心优化：ORDER BY visit_date DESC 实现人类记忆的倒叙回溯
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

if __name__ == '__main__':
    init_db()
    print("🚀 《行迹》终极倒叙网关就绪，监听 5000 端口...")
    app.run(debug=True, port=5000)