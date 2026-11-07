import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        # 雲端永久保存模式 (PostgreSQL)
        return psycopg2.connect(DATABASE_URL)
    else:
        # 本地測試模式 (SQLite)
        conn = sqlite3.connect('leave_system_final.db')
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # PostgreSQL 終極相容語法
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "users" (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                "password" TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leave_requests (
                id SERIAL PRIMARY KEY,
                user_info TEXT NOT NULL,
                reason TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        # SQLite 語法
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leave_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_info TEXT NOT NULL,
                reason TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    # 預設建立最高管理員
    cursor.execute('SELECT * FROM "users" WHERE username=\'admin\'')
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute('INSERT INTO "users" (name, username, "password", role) VALUES (%s, %s, %s, %s)',
                       ('系統管理員', 'admin', hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()

# 註冊頁面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO "users" (name, username, "password", role) VALUES (%s, %s, %s, %s)',
                           (name, username, hashed_password, role))
            conn.commit()
            flash('註冊成功，請登入！', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('帳號已存在，請換一個！', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

# 登入頁面 (✨ 終極修復：回歸最原生、最相容的原始欄位抓取，絕不因驅動類型卡死)
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        # 欄位依序：0:id, 1:name, 2:username, 3:password, 4:role
        cursor.execute('SELECT id, name, username, "password", role FROM "users" WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()
        
        # 100% 安全：直接使用標準 Tuple 數字索引，不管是 PostgreSQL 還是 SQLite 都絕不報錯
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['name'] = user[1]
            session['role'] = user[4]
            
            if session['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('apply_leave'))
        else:
            flash('帳號或密碼錯誤！', 'danger')
            
    return render_template('login.html')

# 員工請假申請頁面
@app.route('/apply', methods=['GET', 'POST'])
def apply_leave():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        user_info = request.form['user_info']
        reason = request.form['reason']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO leave_requests (user_info, reason) VALUES (%s, %s)", (user_info, reason))
        conn.commit()
        conn.close()
        
        flash('請假申請已送出！', 'success')
        return redirect(url_for('apply_leave'))
        
    return render_template('apply.html', name=session['name'])

# 管理員後台 (✨ 終極修復：用最安全的 Tuple 索引傳遞資料給前端)
@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('權限不足，無法查看管理員後台！', 'danger')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_info, reason, applied_at FROM leave_requests ORDER BY applied_at DESC")
    records = cursor.fetchall()
    conn.close()
    
    # 將撈出來的每一列直接轉成標準的 List 傳給前端，保證相容性
    formatted_records = [list(r) for r in records]
    return render_template('admin.html', records=formatted_records)

# 登出
@app.route('/logout')
def logout():
    session.clear()
    flash('您已成功登出！', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
