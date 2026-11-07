import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
# 引入 pg8000 作為 PostgreSQL 的驅動，確保雲端獨立資料庫連線
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')

# 檢查是否有雲端資料庫網址 (Render 會自動提供 DATABASE_URL)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        # 雲端永久保存模式 (PostgreSQL)
        conn = psycopg2.connect(DATABASE_URL)
    else:
        # 本地電腦測試模式 (SQLite)
        conn = sqlite3.connect('leave_system_final.db')
    return conn

# 初始化資料庫
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # PostgreSQL 語法
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
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
    
    # 預設建立最高管理員帳號
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO users (name, username, password, role) VALUES (%s, %s, %s, %s)" if DATABASE_URL else "INSERT INTO users (name, username, password, role) VALUES (?, ?, ?, ?)",
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
            cursor.execute("INSERT INTO users (name, username, password, role) VALUES (%s, %s, %s, %s)" if DATABASE_URL else "INSERT INTO users (name, username, password, role) VALUES (?, ?, ?, ?)",
                           (name, username, hashed_password, role))
            conn.commit()
            flash('註冊成功，請登入！', 'success')
            return redirect(url_for('login'))
        except (sqlite3.IntegrityError, psycopg2.IntegrityError):
            flash('帳號已存在，請換一個！', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

# 登入頁面
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, username, password, role FROM users WHERE username = %s" if DATABASE_URL else "SELECT id, name, username, password, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
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
        cursor.execute("INSERT INTO leave_requests (user_info, reason) VALUES (%s, %s)" if DATABASE_URL else "INSERT INTO leave_requests (user_info, reason) VALUES (?, ?)", (user_info, reason))
        conn.commit()
        conn.close()
        
        flash('請假申請已送出！', 'success')
        return redirect(url_for('apply_leave'))
        
    return render_template('apply.html', name=session['name'])

# 管理員後台
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
    
    return render_template('admin.html', records=records)

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
