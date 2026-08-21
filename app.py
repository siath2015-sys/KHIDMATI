from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tax_queue_full_system_secret_2026'

def get_db_connection():
    conn = sqlite3.connect('tax-queue-full.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS centers (id INTEGER PRIMARY KEY AUTOINCREMENT, center_name TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_name TEXT NOT NULL, FOREIGN KEY (center_id) REFERENCES centers (id))')
    conn.execute('''CREATE TABLE IF NOT EXISTS queue_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_id INTEGER, 
        ticket_number TEXT NOT NULL, status TEXT DEFAULT "WAITING", is_priority INTEGER DEFAULT 0, 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, called_at TIMESTAMP)''')
    conn.execute('CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, is_active INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, is_active INTEGER DEFAULT 0)')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, 
        role TEXT NOT NULL, center_id INTEGER, service_id INTEGER,
        FOREIGN KEY (center_id) REFERENCES centers(id), FOREIGN KEY (service_id) REFERENCES services(id))''')
    
    # حساب افتراضي أولي
    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', 'admin123', 'system_admin'))
        conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('director', 'dir123', 'directorate'))
        conn.execute('INSERT OR IGNORE INTO centers (id, center_name) VALUES (1, ?)', ('المركز الجواري للضرائب - ميلة',))
        conn.execute('INSERT OR IGNORE INTO services (id, center_id, service_name) VALUES (1, 1, ?)', ('مصلحة الاستقبال والتسجيل',))
        conn.execute('INSERT OR IGNORE INTO users (username, password, role, center_id) VALUES (?, ?, ?, ?)', ('manager_mila', 'man123', 'center_admin', 1))
        conn.execute('INSERT OR IGNORE INTO users (username, password, role, center_id, service_id) VALUES (?, ?, ?, ?, ?)', ('agent1', 'agent123', 'employee', 1, 1))
        conn.commit()
    conn.close()

init_db()

# ==========================================
# 0. شاشة الدخول الموحدة
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def home():
    error = None
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['center_id'] = user['center_id']
            session['service_id'] = user['service_id']
            
            if user['role'] == 'system_admin': return redirect(url_for('system_dashboard'))
            elif user['role'] == 'directorate': return redirect(url_for('directorate_dashboard'))
            elif user['role'] == 'center_admin': return redirect(url_for('center_dashboard'))
            elif user['role'] == 'employee': return redirect(url_for('employee_window'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة.'
            
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تسجيل الدخول - نظام الطوابير</title>
        <style>
            body { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color: #fff; font-family: Tahoma; display: flex; flex-direction: column; justify-content: space-between; align-items: center; height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
            .card { background: #1e293b; padding: 35px; border-radius: 15px; width: 100%; max-width: 400px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }
            input { width: 90%; padding: 12px; margin: 10px 0; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #fff; font-size: 15px; }
            button { width: 92%; padding: 12px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; margin-top: 10px; }
            button:hover { background: #1d4ed8; }
            .footer { color: #94a3b8; font-size: 13px; text-align: center; }
        </style></head>
        <body><div></div>
        <div class="card">
            <h2>تسجيل الدخول للنظام</h2>
            {% if error %}<div style="color:#ef4444; background:rgba(239,68,68,0.1); padding:10px; border-radius:6px; margin-bottom:15px; font-weight:bold;">{{ error }}</div>{% endif %}
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم" required autocomplete="off"><br>
                <input type="password" name="password" placeholder="كلمة المرور" required><br>
                <button type="submit">دخول</button>
            </form>
            <div style="margin-top: 15px;"><a href="/centers" style="color: #38bdf8; font-size: 13px; text-decoration: none;">عرض شاشات ومراكز الاستقبال (Kiosk / Display)</a></div>
        </div>
        <div class="footer">من إنجاز: عتامنة الطاهر - المديرية الولائية للضرائب ميلة</div>
        </body></html>
    ''', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ==========================================
# 1. لوحة تحكم المسؤول العام (System Admin)
# ==========================================
@app.route('/system-dashboard', methods=['GET', 'POST'])
def system_dashboard():
    if session.get('role') != 'system_admin': return "غير مسموح!", 403
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add_center':
                c_name = request.form.get('center_name')
                if c_name: conn.execute('INSERT INTO centers (center_name) VALUES (?)', (c_name,)); conn.commit()
            elif action == 'delete_center':
                conn.execute('DELETE FROM centers WHERE id = ?', (request.form.get('center_id'),)); conn.commit()
            elif action == 'add_service':
                c_id, s_name = request.form.get('center_id'), request.form.get('service_name')
                if c_id and s_name: conn.execute('INSERT INTO services (center_id, service_name) VALUES (?, ?)', (c_id, s_name)); conn.commit()
            elif action == 'delete_service':
                conn.execute('DELETE FROM services WHERE id = ?', (request.form.get('service_id'),)); conn.commit()
            elif action == 'add_user':
                uname, pwd, role = request.form.get('username'), request.form.get('password'), request.form.get('role')
                c_id = request.form.get('center_id') or None
                s_id = request.form.get('service_id') or None
                if uname and pwd and role:
                    conn.execute('INSERT INTO users (username, password, role, center_id, service_id) VALUES (?, ?, ?, ?, ?)', (uname, pwd, role, c_id, s_id)); conn.commit()
            elif action == 'delete_user':
                conn.execute('DELETE FROM users WHERE id = ? AND role != "system_admin"', (request.form.get('user_id'),)); conn.commit()
            elif action == 'add_announcement':
                content = request.form.get('content')
                if content: conn.execute('INSERT INTO announcements (content, is_active) VALUES (?, 0)', (content,)); conn.commit()
            elif action == 'set_active_announcement':
                conn.execute('UPDATE announcements SET is_active = 0')
                conn.execute('UPDATE announcements SET is_active = 1 WHERE id = ?', (request.form.get('announcement_id'),)); conn.commit()
            elif action == 'delete_announcement':
                conn.execute('DELETE FROM announcements WHERE id = ?', (request.form.get('announcement_id'),)); conn.commit()
        except Exception as e: pass

    centers = conn.execute('SELECT * FROM centers').fetchall()
    services = conn.execute('SELECT s.*, c.center_name FROM services s JOIN centers c ON s.center_id = c.id').fetchall()
    users = conn.execute('SELECT u.*, c.center_name FROM users u LEFT JOIN centers c ON u.center_id = c.id').fetchall()
    announcements = conn.execute('SELECT * FROM announcements').fetchall()
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة تحكم المسؤول العام</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .container { max-width: 1100px; margin: auto; }
            .card { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            input, select { padding: 8px; margin: 5px; background: #0f172a; color: #fff; border: 1px solid #475569; border-radius: 6px; }
            button { padding: 8px 12px; background: #10b981; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 8px; text-align: center; border-bottom: 1px solid #334155; font-size: 13px; } th { color: #f59e0b; }
            .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .btn-exit { background: #ef4444; padding: 8px 15px; border-radius: 6px; color: #fff; text-decoration: none; font-weight: bold; }
        </style></head>
        <body><div class="container">
        <div class="top"><h2>🛠️ لوحة تحكم المسؤول العام (System Admin)</h2><a href="/logout" class="btn-exit">خروج</a></div>
        
        <div class="card">
            <h3>إدارة المراكز</h3>
            <form method="POST"><input type="hidden" name="action" value="add_center"><input type="text" name="center_name" placeholder="اسم المركز الجديد" required><button type="submit">إضافة</button></form>
            <table><tr><th>المعرف</th><th>الاسم</th><th>إجراء</th></tr>
            {% for c in centers %}<tr><td>{{ c.id }}</td><td>{{ c.center_name }}</td><td><form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_center"><input type="hidden" name="center_id" value="{{ c.id }}"><button type="submit" style="background:#ef4444;">حذف</button></form></td></tr>{% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>إدارة المصالح</h3>
            <form method="POST"><input type="hidden" name="action" value="add_service">
            <select name="center_id" required><option value="">اختر المركز</option>{% for c in centers %}<option value="{{ c.id }}">{{ c.center_name }}</option>{% endfor %}</select>
            <input type="text" name="service_name" placeholder="اسم المصلحة" required><button type="submit">إضافة</button></form>
            <table><tr><th>المصلحة</th><th>المركز</th><th>إجراء</th></tr>
            {% for s in services %}<tr><td>{{ s.service_name }}</td><td>{{ s.center_name }}</td><td><form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_service"><input type="hidden" name="service_id" value="{{ s.id }}"><button type="submit" style="background:#ef4444;">حذف</button></form></td></tr>{% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>إدارة المستخدمين</h3>
            <form method="POST"><input type="hidden" name="action" value="add_user">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <select name="role" required><option value="employee">عون نداء</option><option value="center_admin">مسؤول مركز</option><option value="directorate">مديرية</option></select>
            <select name="center_id"><option value="">المركز (اختياري)</option>{% for c in centers %}<option value="{{ c.id }}">{{ c.center_name }}</option>{% endfor %}</select>
            <button type="submit">إضافة مستخدم</button></form>
            <table><tr><th>المستخدم</th><th>الدور</th><th>المركز</th><th>إجراء</th></tr>
            {% for u in users %}<tr><td>{{ u.username }}</td><td>{{ u.role }}</td><td>{{ u.center_name or '-' }}</td><td>{% if u.role != 'system_admin' %}<form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_user"><input type="hidden" name="user_id" value="{{ u.id }}"><button type="submit" style="background:#ef4444;">حذف</button></form>{% endif %}</td></tr>{% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>إدارة الإعلانات الترويجية</h3>
            <form method="POST"><input type="hidden" name="action" value="add_announcement"><input type="text" name="content" placeholder="نص الإعلان..." required style="width:60%"><button type="submit">إضافة</button></form>
            <table><tr><th>النص</th><th>الحالة</th><th>إجراء</th></tr>
            {% for a in announcements %}<tr><td>{{ a.content }}</td><td>{% if a.is_active == 1 %}<span style="color:#10b981;">نشط</span>{% else %}<form method="POST" style="display:inline;"><input type="hidden" name="action" value="set_active_announcement"><input type="hidden" name="announcement_id" value="{{ a.id }}"><button type="submit" style="background:#f59e0b;">تفعيل</button></form>{% endif %}</td><td><form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_announcement"><input type="hidden" name="announcement_id" value="{{ a.id }}"><button type="submit" style="background:#ef4444;">حذف</button></form></td></tr>{% endfor %}
            </table>
        </div></div></body></html>
    ''', centers=centers, services=services, users=users, announcements=announcements)

# ==========================================
# 2. لوحة تحكم المديرية (Directorate Dashboard)
# ==========================================
@app.route('/directorate-dashboard')
def directorate_dashboard():
    if session.get('role') not in ['system_admin', 'directorate']: return "غير مسموح!", 403
    conn = get_db_connection()
    centers = conn.execute('SELECT * FROM centers').fetchall()
    stats = conn.execute('''
        SELECT c.center_name, 
               COUNT(t.id) as total,
               SUM(CASE WHEN t.status = 'WAITING' THEN 1 ELSE 0 END) as waiting,
               SUM(CASE WHEN t.status = 'COMPLETED' THEN 1 ELSE 0 END) as completed
        FROM centers c LEFT JOIN queue_tokens t ON c.id = t.center_id GROUP BY c.id
    ''').fetchall()
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة تحكم المديرية والإحصائيات</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .container { max-width: 1000px; margin: auto; }
            .card { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            th, td { padding: 10px; text-align: center; border-bottom: 1px solid #334155; } th { color: #38bdf8; }
            .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        </style></head>
        <body><div class="container">
        <div class="top"><h2>📊 لوحة تحكم المديرية - إحصائيات النشاط العام</h2><a href="/logout" style="background:#ef4444; color:#fff; padding:8px 15px; text-decoration:none; border-radius:6px; font-weight:bold;">خروج</a></div>
        <div class="card">
            <h3>ملخص طوابير المراكز الجوارية للضرائب</h3>
            <table>
                <tr><th>المركز</th><th>إجمالي التذاكر المسحوبة</th><th>قيد الانتظار</th><th>المكتملة</th></tr>
                {% for s in stats %}
                <tr>
                    <td>{{ s.center_name }}</td>
                    <td>{{ s.total or 0 }}</td>
                    <td style="color:#f59e0b;">{{ s.waiting or 0 }}</td>
                    <td style="color:#10b981;">{{ s.completed or 0 }}</td>
                </tr>
                {% endfor %}
            </table>
        </div></div></body></html>
    ''', stats=stats)

# ==========================================
# 3. لوحة تحكم مسؤول المركز (Center Manager)
# ==========================================
@app.route('/center-dashboard', methods=['GET', 'POST'])
def center_dashboard():
    if session.get('role') not in ['system_admin', 'center_admin']: return "غير مسموح!", 403
    center_id = session.get('center_id')
    conn = get_db_connection()
    
    if request.method == 'POST' and request.form.get('action') == 'reset_center_queue':
        conn.execute('DELETE FROM queue_tokens WHERE center_id = ?', (center_id,))
        conn.commit()

    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    services = conn.execute('SELECT * FROM services WHERE center_id = ?', (center_id,)).fetchall()
    tokens = conn.execute('SELECT t.*, s.service_name FROM queue_tokens t JOIN services s ON t.service_id = s.id WHERE t.center_id = ? ORDER BY t.id DESC LIMIT 20', (center_id,)).fetchall()
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة تحكم مسؤول المركز</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .container { max-width: 1000px; margin: auto; }
            .card { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            th, td { padding: 8px; text-align: center; border-bottom: 1px solid #334155; font-size: 13px; } th { color: #f59e0b; }
            .btn { display: inline-block; background: #3b82f6; color: #fff; padding: 10px 15px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-left: 10px; }
            .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        </style></head>
        <body><div class="container">
        <div class="top"><h2>🏢 لوحة تحكم مسؤول المركز: {{ center.center_name }}</h2><a href="/logout" style="background:#ef4444; color:#fff; padding:8px 15px; text-decoration:none; border-radius:6px; font-weight:bold;">خروج</a></div>
        
        <div class="card">
            <h3>روابط الشاشات التشغيلية</h3>
            <a href="/display/{{ center.id }}" class="btn" target="_blank">📺 عرض الشاشة العامة</a>
            <a href="/kiosk/{{ center.id }}" class="btn" style="background:#10b981;" target="_blank">🎫 جهاز سحب التذاكر (Kiosk)</a>
            <form method="POST" style="display:inline; float:left;" onsubmit="return confirm('تأكيد تصفير كافة تذاكر المركز؟');">
                <input type="hidden" name="action" value="reset_center_queue">
                <button type="submit" style="background:#ef4444; padding:10px 15px; border:none; border-radius:6px; color:#fff; font-weight:bold; cursor:pointer;">⚠️ تصفير طابور المركز</button>
            </form>
        </div>

        <div class="card">
            <h3>حركة التذاكر الأخيرة في المركز</h3>
            <table><tr><th>رقم التذكرة</th><th>المصلحة</th><th>الحالة</th><th>الوقت</th></tr>
            {% for t in tokens %}
            <tr>
                <td><b>{{ t.ticket_number }}</b></td>
                <td>{{ t.service_name }}</td>
                <td style="color: {% if t.status == 'WAITING' %}#f59e0b{% elif t.status == 'CALLED' %}#38bdf8{% else %}#10b981{% endif %};">{{ t.status }}</td>
                <td>{{ t.created_at }}</td>
            </tr>
            {% endfor %}
            </table>
        </div></div></body></html>
    ''', center=center, services=services, tokens=tokens)

# ==========================================
# 4. نافذة الموظف / العون (Employee Window)
# ==========================================
@app.route('/employee-window', methods=['GET', 'POST'])
def employee_window():
    if session.get('role') not in ['system_admin', 'employee']: return "غير مسموح!", 403
    center_id = session.get('center_id')
    service_id = session.get('service_id')
    
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'call_next':
            # إنهاء الحالي إن وجد
            conn.execute('UPDATE queue_tokens SET status = "COMPLETED" WHERE center_id = ? AND service_id = ? AND status = "CALLED"', (center_id, service_id))
            # جلب التالي (الأولوية أولاً ثم الأقدم)
            nxt = conn.execute('SELECT * FROM queue_tokens WHERE center_id = ? AND service_id = ? AND status = "WAITING" ORDER BY is_priority DESC, id ASC LIMIT 1', (center_id, service_id)).fetchone()
            if nxt:
                conn.execute('UPDATE queue_tokens SET status = "CALLED", called_at = CURRENT_TIMESTAMP WHERE id = ?', (nxt['id'],))
            conn.commit()
        elif action == 'recall':
            pass # إعادة النداء
        elif action == 'complete':
            conn.execute('UPDATE queue_tokens SET status = "COMPLETED" WHERE center_id = ? AND service_id = ? AND status = "CALLED"', (center_id, service_id))
            conn.commit()

    current_ticket = conn.execute('SELECT * FROM queue_tokens WHERE center_id = ? AND service_id = ? AND status = "CALLED" ORDER BY called_at DESC LIMIT 1', (center_id, service_id)).fetchone()
    waiting_count = conn.execute('SELECT COUNT(*) FROM queue_tokens WHERE center_id = ? AND service_id = ? AND status = "WAITING"', (center_id, service_id)).fetchone()[0]
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>نافذة العون والموظف</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 30px; border-radius: 12px; width: 450px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .btn { display: block; width: 100%; padding: 14px; margin: 10px 0; border-radius: 8px; border: none; font-size: 16px; font-weight: bold; cursor: pointer; color: #fff; }
            .btn-call { background: #2563eb; } .btn-complete { background: #10b981; }
        </style></head>
        <body>
        <div class="box">
            <h2>🖥️ نافذة نداء العون</h2>
            <div style="background: #334155; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <div style="font-size: 14px; color: #94a3b8;">التذكرة الحالية المناداة:</div>
                <div style="font-size: 32px; font-weight: bold; color: #38bdf8; margin: 5px 0;">{{ current_ticket.ticket_number if current_ticket else '---' }}</div>
                <div style="font-size: 13px; color: #cbd5e1;">التذاكر في الانتظار: <b>{{ waiting_count }}</b></div>
            </div>
            <form method="POST">
                <input type="hidden" name="action" value="call_next">
                <button type="submit" class="btn btn-call">📢 نداء التذكرة التالية</button>
            </form>
            <form method="POST">
                <input type="hidden" name="action" value="complete">
                <button type="submit" class="btn btn-complete">✅ إنهاء الخدمة الحالية</button>
            </form>
            <a href="/logout" style="color: #94a3b8; font-size: 13px; display: inline-block; margin-top: 15px; text-decoration: none;">تسجيل الخروج</a>
        </div>
        </body></html>
    ''', current_ticket=current_ticket, waiting_count=waiting_count)

# ==========================================
# 5. شاشة العرض العامة (Display Screen) وجهاز السحب (Kiosk)
# ==========================================
@app.route('/centers')
def public_centers():
    conn = get_db_connection()
    centers = conn.execute('SELECT * FROM centers').fetchall()
    conn.close()
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>المراكز المتاحة</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 30px; border-radius: 12px; width: 400px; text-align: center; }
            .btn { display: block; background: #3b82f6; color: #fff; padding: 12px; margin: 10px 0; border-radius: 8px; text-decoration: none; font-weight: bold; }
        </style></head>
        <body><div class="box">
            <h2>🏢 اختر المركز المطلوب</h2>
            {% for c in centers %}
                <div style="background:#334155; padding:12px; border-radius:8px; margin-bottom:10px;">
                    <div style="font-weight:bold; margin-bottom:8px;">{{ c.center_name }}</div>
                    <a class="btn" href="/display/{{ c.id }}">📺 الشاشة العامة</a>
                    <a class="btn" style="background:#10b981;" href="/kiosk/{{ c.id }}">🎫 سحب تذكرة (Kiosk)</a>
                </div>
            {% endfor %}
            <a href="/" style="color:#cbd5e1; font-size:13px;">العودة للدخول</a>
        </div></body></html>
    ''', centers=centers)

@app.route('/kiosk/<int:center_id>', methods=['GET', 'POST'])
def kiosk(center_id):
    conn = get_db_connection()
    services = conn.execute('SELECT * FROM services WHERE center_id = ?', (center_id,)).fetchall()
    ticket = None
    if request.method == 'POST':
        service_id = request.form.get('service_id')
        is_priority = 1 if request.form.get('is_priority') else 0
        last_t = conn.execute('SELECT COUNT(*) FROM queue_tokens WHERE center_id = ? AND service_id = ?', (center_id, service_id)).fetchone()[0] + 1
        ticket_number = f"A-{last_t:03d}"
        conn.execute('INSERT INTO queue_tokens (center_id, service_id, ticket_number, is_priority) VALUES (?, ?, ?, ?)', (center_id, service_id, ticket_number, is_priority))
        conn.commit()
        ticket = ticket_number
    conn.close()
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>سحب تذكرة</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 35px; border-radius: 15px; width: 400px; text-align: center; }
            button { width: 100%; padding: 15px; background: #10b981; color: #fff; border: none; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 10px; }
            select { width: 100%; padding: 12px; margin: 10px 0; background: #0f172a; color: #fff; border-radius: 8px; border: 1px solid #475569; }
        </style></head>
        <body><div class="box">
            <h2>🎫 جهاز سحب التذاكر</h2>
            {% if ticket %}
                <div style="background:#10b981; padding:20px; border-radius:10px; margin-bottom:15px;">
                    <div style="font-size:16px;">رقم تذكرتك:</div>
                    <div style="font-size:40px; font-weight:bold;">{{ ticket }}</div>
                </div>
                <a href="/kiosk/{{ center_id }}" style="color:#38bdf8; display:inline-block; margin-top:10px;">سحب تذكرة جديدة</a>
            {% else %}
                <form method="POST">
                    <select name="service_id" required><option value="">اختر المصلحة المطلوبة</option>{% for s in services %}<option value="{{ s.id }}">{{ s.service_name }}</option>{% endfor %}</select>
                    <label style="display:block; margin:15px 0; text-align:right;"><input type="checkbox" name="is_priority" value="1"> فئة ذات أولوية (كبار السن / ذوي الاحتياجات الخاصة)</label>
                    <button type="submit">طبع التذكرة</button>
                </form>
            {% endif %}
            <div style="margin-top:20px;"><a href="/centers" style="color:#94a3b8; font-size:13px;">العودة لاختيار المركز</a></div>
        </div></body></html>
    ''', services=services, ticket=ticket, center_id=center_id)

@app.route('/display/<int:center_id>')
def display(center_id):
    conn = get_db_connection()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    current = conn.execute('SELECT t.*, s.service_name FROM queue_tokens t JOIN services s ON t.service_id = s.id WHERE t.center_id = ? AND t.status = "CALLED" ORDER BY t.called_at DESC LIMIT 1', (center_id,)).fetchone()
    announcement = conn.execute('SELECT content FROM announcements WHERE is_active = 1 LIMIT 1').fetchone()
    conn.close()
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>شاشة العرض</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; text-align: center; margin: 0; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; height: 100vh; box-sizing: border-box; }
            .header { font-size: 28px; font-weight: bold; color: #38bdf8; padding: 10px; background: #1e293b; border-radius: 10px; }
            .main-box { background: #1e293b; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 60%; margin: auto; border: 2px solid #3b82f6; }
            .ticker { background: #f59e0b; color: #000; padding: 12px; font-weight: bold; border-radius: 8px; font-size: 18px; }
        </style></head>
        <body>
        <div class="header">🏢 نظام التوجيه والنداء - {{ center.center_name }}</div>
        <div class="main-box">
            <div style="font-size: 24px; color: #cbd5e1;">التذكرة الحالية قيد النداء</div>
            <div style="font-size: 90px; font-weight: bold; color: #10b981; margin: 20px 0;">{{ current.ticket_number if current '---' }}</div>
            <div style="font-size: 22px; color: #f59e0b;">المصلحة: {{ current.service_name if current else 'في الانتظار...' }}</div>
        </div>
        <div class="ticker">📢 إعلان: {{ announcement.content if announcement else 'مرحباً بكم في مصالح الضرائب.' }}</div>
        </body></html>
    ''', center=center, current=current, announcement=announcement)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
