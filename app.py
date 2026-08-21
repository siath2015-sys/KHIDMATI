from datetime import datetime
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'tax_queue_system_secret_key_2026'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS centers (id INTEGER PRIMARY KEY AUTOINCREMENT, center_name TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_name TEXT NOT NULL, FOREIGN KEY (center_id) REFERENCES centers (id))')
    conn.execute('CREATE TABLE IF NOT EXISTS queue_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_id INTEGER, ticket_number TEXT NOT NULL, status TEXT DEFAULT "WAITING", is_priority INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, called_at TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, is_active INTEGER DEFAULT 1)')
    
    # جدول المستخدمين لضمان تسجيل الدخول باسم المستخدم وكلمة المرور وصلاحيات دقيقة
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            center_id INTEGER,
            service_id INTEGER,
            FOREIGN KEY (center_id) REFERENCES centers(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # إدخال حسابات افتراضية للاختبار إذا كان الجدول فارغاً
    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        # مسؤول عام
        conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', 'admin123', 'system_admin'))
        # مديرية
        conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('directorate', 'dir123', 'directorate'))
        
        # مركز ومصلحة افتراضية للاختبار
        conn.execute('INSERT OR IGNORE INTO centers (id, center_name) VALUES (1, ?)', ('المركز الجواري للضرائب - ميلة',))
        conn.execute('INSERT OR IGNORE INTO services (id, center_id, service_name) VALUES (1, 1, ?)', ('مصلحة الاستقبال والتسجيل',))
        
        # مسؤول مركز
        conn.execute('INSERT OR IGNORE INTO users (username, password, role, center_id) VALUES (?, ?, ?, ?)', ('manager_mila', 'man123', 'center_manager', 1))
        # عون مصلحة
        conn.execute('INSERT OR IGNORE INTO users (username, password, role, center_id, service_id) VALUES (?, ?, ?, ?, ?)', ('agent1', 'agent123', 'employee', 1, 1))
        
        conn.commit()
    conn.close()

init_db()

# ==========================================
# 0. الصفحة الرئيسية وتوجيه الدخول
# ==========================================
@app.route('/')
def home():
    conn = get_db_connection()
    centers = conn.execute('SELECT * FROM centers').fetchall()
    conn.close()
    
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>منظومة إدارة الطوابير</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 40px; border-radius: 20px; text-align: center; width: 450px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; margin-bottom: 20px; }
            .btn { display: block; background: #3b82f6; color: #fff; padding: 12px; margin: 10px 0; border-radius: 8px; text-decoration: none; font-weight: bold; transition: 0.2s; }
            .btn:hover { background: #2563eb; }
            .btn-green { background: #10b981; }
            .btn-green:hover { background: #059669; }
        </style></head>
        <body>
        <div class="box">
            <h2>🏢 مراكز الخدمات المتاحة</h2>
            <p style="color: #94a3b8; font-size: 14px; margin-bottom: 20px;">اختر المركز للانتقال إلى واجهة العرض أو سحب التذاكر</p>
            {% for c in centers %}
                <div style="background: #334155; padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: right;">
                    <div style="font-weight: bold; font-size: 16px; margin-bottom: 10px;">{{ c.center_name }}</div>
                    <a class="btn" href="/display/{{ c.id }}">📺 شاشة العرض العامة</a>
                    <a class="btn btn-green" href="/kiosk/{{ c.id }}">🎫 جهاز سحب التذاكر (Kiosk)</a>
                </div>
            {% endfor %}
            <a href="/login" style="color: #cbd5e1; font-size: 13px; display: inline-block; margin-top: 15px; text-decoration: underline;">تسجيل دخول المستخدمين / المسؤولين</a>
        </div>
        </body></html>
    ''', centers=centers)

# ==========================================
# 1. شاشة تسجيل الدخول الموحدة (User Name & Password)
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['center_id'] = user['center_id']
            session['service_id'] = user['service_id']
            
            # توجيه حسب الصلاحية
            if user['role'] == 'system_admin':
                return redirect(url_for('system_dashboard'))
            elif user['role'] == 'directorate':
                return redirect(url_for('directorate_dashboard'))
            elif user['role'] == 'center_manager':
                return redirect(url_for('center_manager_dashboard'))
            elif user['role'] == 'employee':
                return redirect(url_for('employee_interface'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة!'

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تسجيل الدخول للنظام</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 35px; border-radius: 15px; width: 380px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; text-align: center; margin-bottom: 20px; }
            label { display: block; margin-top: 15px; font-size: 14px; color: #cbd5e1; }
            input { width: 100%; padding: 12px; margin-top: 5px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #fff; font-size: 14px; box-sizing: border-box; }
            button { width: 100%; background: #3b82f6; color: #fff; border: none; padding: 12px; margin-top: 25px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 15px; }
            button:hover { background: #2563eb; }
            .error { background: rgba(239,68,68,0.2); border: 1px solid #ef4444; color: #f87171; padding: 10px; border-radius: 6px; text-align: center; margin-bottom: 15px; font-size: 13px; }
        </style></head>
        <body>
        <div class="box">
            <h2>🔐 تسجيل الدخول</h2>
            {% if error %}<div class="error">{{ error }}</div>{% endif %}
            <form method="POST">
                <label>اسم المستخدم (Username):</label>
                <input type="text" name="username" placeholder="أدخل اسم المستخدم" required>
                
                <label>كلمة المرور (Password):</label>
                <input type="password" name="password" placeholder="أدخل كلمة المرور" required>
                
                <button type="submit">دخول</button>
            </form>
            <div style="text-align: center; margin-top: 20px;"><a href="/" style="color:#94a3b8; font-size:13px; text-decoration:none;">← العودة للرئيسية</a></div>
        </div>
        </body></html>
    ''')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# 2. لوحة تحكم المسؤول العام (System Admin)
# ==========================================
@app.route('/system-dashboard', methods=['GET', 'POST'])
def system_dashboard():
    if session.get('role') != 'system_admin':
        return "غير مصرح لك بالوصول!", 403
    
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_center':
            name = request.form.get('center_name')
            if name:
                conn.execute('INSERT INTO centers (center_name) VALUES (?)', (name,))
                conn.commit()
        elif action == 'add_user':
            uname = request.form.get('username')
            pwd = request.form.get('password')
            role = request.form.get('role')
            c_id = request.form.get('center_id') or None
            s_id = request.form.get('service_id') or None
            if uname and pwd and role:
                conn.execute('INSERT INTO users (username, password, role, center_id, service_id) VALUES (?, ?, ?, ?, ?)', 
                             (uname, pwd, role, c_id, s_id))
                conn.commit()
        return redirect(url_for('system_dashboard'))

    centers = conn.execute('SELECT * FROM centers').fetchall()
    users = conn.execute('SELECT u.*, c.center_name FROM users u LEFT JOIN centers c ON u.center_id = c.id').fetchall()
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة تحكم مسؤول النظام</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; text-align: center; margin-bottom: 25px; }
            .section { background: #334155; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
            input, select { width: 100%; padding: 10px; margin-top: 8px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #fff; box-sizing: border-box; }
            button { background: #10b981; color: #fff; border: none; padding: 10px 20px; margin-top: 10px; border-radius: 6px; font-weight: bold; cursor: pointer; }
            button:hover { background: #059669; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #0f172a; border-radius: 6px; overflow: hidden; }
            th, td { padding: 10px; text-align: center; border-bottom: 1px solid #334155; font-size: 13px; }
            th { color: #f59e0b; }
        </style></head>
        <body>
        <div class="container">
            <h2>⚙️ لوحة تحكم مسؤول النظام (System Admin)</h2>
            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <a href="/system/dashboard-stats" class="btn" style="background:#3b82f6; text-decoration:none; padding:10px 15px; border-radius:6px; font-weight:bold;">📊 إحصائيات المديرية العامة</a>
                <a href="/system/all-displays" class="btn" style="background:#8b5cf6; text-decoration:none; padding:10px 15px; border-radius:6px; font-weight:bold;">🖥️ مراقبة كل الشاشات</a>
                <a href="/logout" style="background:#ef4444; color:#fff; padding:10px 15px; border-radius:6px; text-decoration:none; font-weight:bold; margin-right:auto;">تسجيل الخروج 🚪</a>
            </div>

            <div class="section">
                <h3>🏢 إضافة مركز جواري جديد</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="add_center">
                    <input type="text" name="center_name" placeholder="اسم المركز" required>
                    <button type="submit">إضافة المركز</button>
                </form>
            </div>

            <div class="section">
                <h3>👤 إضافة مستخدم جديد (مدير مركز، عون، مديرية...)</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="add_user">
                    <input type="text" name="username" placeholder="اسم المستخدم" required>
                    <input type="password" name="password" placeholder="كلمة المرور" required>
                    <select name="role">
                        <option value="system_admin">مسؤول نظام (System Admin)</option>
                        <option value="directorate">مديرية (Directorate)</option>
                        <option value="center_manager">مسؤول مركز (Center Manager)</option>
                        <option value="employee">عون مصلحة (Employee)</option>
                    </select>
                    <select name="center_id">
                        <option value="">-- اختر المركز (اختياري) --</option>
                        {% for c in centers %}
                        <option value="{{ c.id }}">{{ c.center_name }}</option>
                        {% endfor %}
                    </select>
                    <button type="submit">إضافة المستخدم</button>
                </form>
            </div>

            <div class="section">
                <h3>📋 قائمة المستخدمين المسجلين</h3>
                <table>
                    <tr><th>المستخدم</th><th>الصلاحية</th><th>المركز المرتبط</th></tr>
                    {% for u in users %}
                    <tr>
                        <td>{{ u.username }}</td>
                        <td style="color:#38bdf8;">{{ u.role }}</td>
                        <td>{{ u.center_name or 'عام' }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
        </body></html>
    ''', centers=centers, users=users)

# ==========================================
# 3. شاشة إحصائيات المديرية العامة (Directorate Dashboard)
# ==========================================
@app.route('/directorate-dashboard')
def directorate_dashboard():
    if session.get('role') != 'directorate':
        return "غير مصرح لك بالوصول!", 403
    return redirect('/system/dashboard-stats')

@app.route('/system/dashboard-stats', methods=['GET', 'POST'])
def dashboard_stats():
    if session.get('role') not in ['system_admin', 'directorate']:
        return "غير مصرح لك بالوصول!", 403
        
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    conn = get_db_connection()
    query = '''
        SELECT c.center_name, 
               COUNT(t.id) as total_tickets,
               SUM(CASE WHEN t.status = 'COMPLETED' OR t.status = 'CALLED' THEN 1 ELSE 0 END) as served_tickets,
               SUM(CASE WHEN t.status = 'WAITING' THEN 1 ELSE 0 END) as waiting_tickets
        FROM centers c
        LEFT JOIN services s ON c.id = s.center_id
        LEFT JOIN queue_tokens t ON s.id = t.service_id
    '''
    params = []
    if start_date and end_date:
        query += ' WHERE DATE(t.created_at) BETWEEN ? AND ?'
        params.extend([start_date, end_date])
        
    query += ' GROUP BY c.id, c.center_name'
    stats = conn.execute(query, params).fetchall()
    conn.close()

    centers_names = [row['center_name'] for row in stats]
    total_counts = [row['total_tickets'] for row in stats]
    served_counts = [row['served_tickets'] for row in stats]

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة إحصائيات المديرية</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; margin: 0; }
            .container { max-width: 1200px; margin: auto; }
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; background: #1e293b; padding: 15px 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            .top-bar h2 { margin: 0; font-size: 20px; color: #fff; }
            .logout-btn, .back-btn { background: #ef4444; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; gap: 8px; font-size: 14px; }
            .back-btn { background: #3b82f6; }
            .filter-box { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 20px; display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }
            .filter-box input { padding: 10px; background: #0f172a; color: #fff; border: 1px solid #475569; border-radius: 8px; }
            .btn { padding: 10px 20px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; text-decoration: none; }
            .table-container { background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; background: #0f172a; border-radius: 8px; overflow: hidden; }
            th, td { padding: 14px; text-align: center; border-bottom: 1px solid #334155; font-size: 14px; } 
            th { color: #f59e0b; background: #1e293b; }
            .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
            .chart-card { background: #1e293b; padding: 20px; border-radius: 12px; }
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body><div class="container">
        <div class="top-bar">
            <h2>📊 لوحة القيادة وإحصائيات المديرية (Tableau de Bord)</h2>
            <div>
                {% if session.get('role') == 'system_admin' %}
                    <a href="/system-dashboard" class="back-btn">⬅️ العودة للوحة التحكم</a>
                {% else %}
                    <a href="/logout" class="logout-btn"><span>تسجيل الخروج</span> 🚪</a>
                {% endif %}
            </div>
        </div>

        <form method="GET" class="filter-box">
            <span>من تاريخ: <input type="date" name="start_date" value="{{ start_date }}"></span>
            <span>إلى تاريخ: <input type="date" name="end_date" value="{{ end_date }}"></span>
            <button type="submit" class="btn">تصفية الإحصائيات 🔍</button>
            <a href="/system/dashboard-stats" class="btn" style="background: #64748b;">إعادة تعيين</a>
        </form>

        <div class="table-container">
            <h3>📋 جدول ملخص نشاط المراكز</h3>
            <table>
                <thead>
                    <tr><th>اسم المركز</th><th>إجمالي التذاكر</th><th>التذاكر المعالجة</th><th>التذاكر في الانتظار</th></tr>
                </thead>
                <tbody>
                    {% for row in stats %}
                    <tr>
                        <td>{{ row.center_name }}</td>
                        <td style="color: #38bdf8; font-weight: bold;">{{ row.total_tickets }}</td>
                        <td style="color: #10b981; font-weight: bold;">{{ row.served_tickets }}</td>
                        <td style="color: #f59e0b; font-weight: bold;">{{ row.waiting_tickets }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="charts-grid">
            <div class="chart-card"><canvas id="barChart"></canvas></div>
            <div class="chart-card"><canvas id="pieChart"></canvas></div>
        </div>

        <script>
            const centers = {{ centers_names | tojson }};
            const totals = {{ total_counts | tojson }};
            const served = {{ served_counts | tojson }};
            new Chart(document.getElementById('barChart'), {
                type: 'bar',
                data: { labels: centers, datasets: [{ label: 'إجمالي التذاكر', data: totals, backgroundColor: '#3b82f6' }, { label: 'المعالجة', data: served, backgroundColor: '#10b981' }] },
                options: { responsive: true, plugins: { legend: { labels: { color: '#fff' } } } }
            });
            new Chart(document.getElementById('pieChart'), {
                type: 'doughnut',
                data: { labels: centers, datasets: [{ data: totals, backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'] }] },
                options: { responsive: true, plugins: { legend: { labels: { color: '#fff' } } } }
            });
        </script>
        </div></body></html>
    ''', stats=stats, start_date=start_date, end_date=end_date, centers_names=centers_names, total_counts=total_counts, served_counts=served_counts)

# ==========================================
# 4. لوحة تحكم مسؤول المركز (Center Manager Dashboard)
# ==========================================
@app.route('/center-manager', methods=['GET', 'POST'])
def center_manager_dashboard():
    if session.get('role') != 'center_manager' and session.get('role') != 'system_admin':
        return "غير مصرح لك بالوصول!", 403
        
    center_id = session.get('center_id')
    if not center_id:
        return "لم يتم تعيين مركز لهذا المسؤول!", 400

    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_service':
            s_name = request.form.get('service_name')
            if s_name:
                conn.execute('INSERT INTO services (center_id, service_name) VALUES (?, ?)', (center_id, s_name))
                conn.commit()
        elif action == 'update_announcement':
            content = request.form.get('content')
            if content:
                conn.execute('UPDATE announcements SET is_active = 0')
                conn.execute('INSERT INTO announcements (content, is_active) VALUES (?, 1)', (content,))
                conn.commit()
        return redirect(url_for('center_manager_dashboard'))

    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    services = conn.execute('SELECT * FROM services WHERE center_id = ?', (center_id,)).fetchall()
    
    # إحصائيات خاصة بالمركز
    stats = conn.execute('''
        SELECT COUNT(t.id) as total,
               SUM(CASE WHEN t.status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN t.status = 'WAITING' THEN 1 ELSE 0 END) as waiting
        FROM queue_tokens t JOIN services s ON t.service_id = s.id WHERE s.center_id = ?
    ''', (center_id,)).fetchone()
    
    announcement = conn.execute('SELECT * FROM announcements WHERE is_active = 1 LIMIT 1').fetchone()
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>إدارة المركز - {{ center.center_name }}</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .container { max-width: 900px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; text-align: center; margin-bottom: 20px; }
            .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: #334155; padding: 15px; border-radius: 8px; text-align: center; }
            .stat-num { font-size: 24px; font-weight: bold; color: #10b981; margin-top: 5px; }
            .section { background: #334155; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
            input { width: 100%; padding: 10px; margin-top: 8px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #fff; box-sizing: border-box; }
            button { background: #10b981; color: #fff; border: none; padding: 10px 20px; margin-top: 10px; border-radius: 6px; font-weight: bold; cursor: pointer; }
            .links-row { display: flex; gap: 10px; margin-top: 15px; }
            .btn-link { flex: 1; padding: 12px; text-align: center; background: #3b82f6; color: #fff; border-radius: 8px; text-decoration: none; font-weight: bold; }
        </style></head>
        <body>
        <div class="container">
            <h2>🏢 لوحة تحكم مسؤول المركز: {{ center.center_name }}</h2>
            
            <div class="stats-grid">
                <div class="stat-card"><div>إجمالي التذاكر</div><div class="stat-num" style="color:#38bdf8;">{{ stats.total or 0 }}</div></div>
                <div class="stat-card"><div>المعالجة</div><div class="stat-num" style="color:#10b981;">{{ stats.completed or 0 }}</div></div>
                <div class="stat-card"><div>في الانتظار</div><div class="stat-num" style="color:#f59e0b;">{{ stats.waiting or 0 }}</div></div>
            </div>

            <div class="links-row">
                <a href="/display/{{ center.id }}" target="_blank" class="btn-link">📺 فتح شاشة العرض العامة</a>
                <a href="/kiosk/{{ center.id }}" target="_blank" class="btn-link" style="background:#10b981;">🎫 فتح جهاز سحب التذاكر (Kiosk)</a>
            </div>

            <div class="section" style="margin-top:20px;">
                <h3>📌 إضافة مصلحة جديدة بالمركز</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="add_service">
                    <input type="text" name="service_name" placeholder="اسم المصلحة (مثال: مصلحة الجباية)" required>
                    <button type="submit">إضافة المصلحة</button>
                </form>
            </div>

            <div class="section">
                <h3>📢 تحديث شريط الإعلانات الخاص بالمركز</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="update_announcement">
                    <input type="text" name="content" value="{{ announcement.content if announcement else '' }}" placeholder="نص الشريط الإخباري..." required>
                    <button type="submit">تحديث الإعلان</button>
                </form>
            </div>

            <div style="text-align: center; margin-top: 20px;">
                <a href="/logout" style="background:#ef4444; color:#fff; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold;">تسجيل الخروج 🚪</a>
            </div>
        </div>
        </body></html>
    ''', center=center, services=services, stats=stats, announcement=announcement)

# ==========================================
# 5. شاشة العرض العامة (Display Screen)
# ==========================================
@app.route('/display/<int:center_id>')
def display_screen(center_id):
    conn = get_db_connection()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    conn.close()
    if not center: return "المركز غير موجود", 404
        
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>شاشة العرض - {{ center.center_name }}</title>
        <style>
            body { background: linear-gradient(135deg, #0284c7 0%, #0891b2 50%, #0d9488 100%); color: #fff; font-family: Tahoma; margin: 0; padding: 10px; height: 100vh; display: flex; flex-direction: column; box-sizing: border-box; overflow: hidden; }
            .official-header { background: #ffffff; color: #0f172a; padding: 10px 20px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.15); }
            .center-badge { color: #0284c7; font-size: 22px; font-weight: bold; }
            .main-content { display: flex; gap: 15px; flex-grow: 1; margin-top: 10px; }
            .right-panel { flex: 1; display: flex; flex-direction: column; gap: 10px; }
            .current-box { background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(10px); border-radius: 12px; padding: 15px; text-align: center; border: 2px solid rgba(255, 255, 255, 0.3); }
            .current-ticket { font-size: 85px; font-weight: 900; color: #fff; margin: 0; }
            .current-service { font-size: 20px; color: #fbbf24; font-weight: bold; margin-top: 8px; }
            .history-box { background: rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 10px; flex-grow: 1; }
            .history-item { background: rgba(0, 0, 0, 0.25); padding: 8px 12px; border-radius: 6px; margin-bottom: 5px; display: flex; justify-content: space-between; font-size: 14px; border-right: 4px solid #fbbf24; }
            .ticker-wrap { background: #ffffff; color: #dc2626; padding: 10px 15px; border-radius: 8px; margin-top: 8px; overflow: hidden; white-space: nowrap; font-size: 18px; font-weight: bold; }
        </style></head>
        <body>
        <header class="official-header"><div class="center-badge">🏢 {{ center.center_name }}</div></header>
        <div class="main-content">
            <div class="right-panel">
                <div class="current-box">
                    <div style="font-size: 14px; font-weight: bold;">التذكرة الحالية قيد النداء</div>
                    <div id="currTicket" class="current-ticket">---</div>
                    <div id="currService" class="current-service">لا توجد تذكرة حالية</div>
                </div>
                <div class="history-box">
                    <div style="text-align:center; font-weight:bold; margin-bottom:8px;">آخر التذاكر المنداة</div>
                    <div id="historyList" style="overflow-y:auto;"></div>
                </div>
            </div>
        </div>
        <div class="ticker-wrap"><div id="announcementTicker">مرحباً بكم في المركز الجواري للضرائب</div></div>
        <script>
            function fetchDisplayData() {
                fetch('/api/display-data/{{ center.id }}').then(res => res.json()).then(data => {
                    if (data.current) {
                        document.getElementById('currTicket').innerText = data.current.ticket_number;
                        document.getElementById('currService').innerText = data.current.service_name;
                    } else {
                        document.getElementById('currTicket').innerText = '---';
                        document.getElementById('currService').innerText = 'لا توجد تذكرة حالية';
                    }
                    let historyList = document.getElementById('historyList'); historyList.innerHTML = '';
                    if (data.history) {
                        data.history.forEach(h => {
                            let item = document.createElement('div'); item.className = 'history-item';
                            item.innerHTML = `<span><b>${h.ticket_number}</b> (${h.service_name})</span> <span style="color:#4ade80;">منجز</span>`;
                            historyList.appendChild(item);
                        });
                    }
                    if (data.active_announcement) {
                        document.getElementById('announcementTicker').innerText = data.active_announcement.content;
                    }
                });
            }
            setInterval(fetchDisplayData, 2000); fetchDisplayData();
        </script></body></html>
    ''', center=center)

@app.route('/api/display-data/<int:center_id>')
def api_display_data(center_id):
    conn = get_db_connection()
    current = conn.execute('SELECT t.ticket_number, s.service_name, t.called_at FROM queue_tokens t JOIN services s ON t.service_id = s.id WHERE t.center_id = ? AND t.called_at IS NOT NULL ORDER BY t.called_at DESC LIMIT 1', (center_id,)).fetchone()
    history = conn.execute('SELECT t.ticket_number, s.service_name FROM queue_tokens t JOIN services s ON t.service_id = s.id WHERE t.center_id = ? AND t.status IN ("CALLED", "COMPLETED") ORDER BY t.called_at DESC LIMIT 5', (center_id,)).fetchall()
    active_announcement = conn.execute('SELECT * FROM announcements WHERE is_active = 1 LIMIT 1').fetchone()
    conn.close()
    return jsonify({
        'current': dict(current) if current else None,
        'history': [dict(h) for h in history],
        'active_announcement': dict(active_announcement) if active_announcement else None
    })

# ==========================================
# 6. جهاز سحب التذاكر (Kiosk)
# ==========================================
@app.route('/kiosk/<int:center_id>')
def kiosk_machine(center_id):
    conn = get_db_connection()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    services = conn.execute('SELECT * FROM services WHERE center_id = ?', (center_id,)).fetchall()
    conn.close()
    
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>سحب تذكرة - {{ center.center_name }}</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 40px; border-radius: 20px; text-align: center; width: 420px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .priority-box { background: rgba(245, 158, 11, 0.15); border: 2px dashed #f59e0b; padding: 12px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; gap: 10px; }
            .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; }
            .ticket-card { background: #fff; color: #000; padding: 25px; border-radius: 14px; width: 340px; text-align: center; }
            .ticket-number { font-size: 55px; font-weight: 900; color: #0284c7; margin: 10px 0; }
        </style></head>
        <body>
        <div class="box">
            <h2>🎫 سحب تذكرة - {{ center.center_name }}</h2>
            <div class="priority-box">
                <input type="checkbox" id="isPriority" style="width:20px; height:20px;">
                <label for="isPriority" style="color: #fbbf24; font-weight: bold; cursor:pointer;">♿ ذوي الاحتياجات الخاصة</label>
            </div>
            {% for s in services %}
            <button onclick="issueTicket({{ s.id }})" style="display:block; width:100%; background:#3b82f6; color:#fff; padding:15px; margin:12px 0; border:none; border-radius:8px; font-weight:bold; font-size:16px; cursor:pointer;">{{ s.service_name }}</button>
            {% endfor %}
        </div>
        <div id="ticketModal" class="modal">
            <div class="ticket-card">
                <h3>{{ center.center_name }}</h3>
                <div id="ticketServiceName" style="font-weight:bold; color:#15803d; margin:10px 0;"></div>
                <div class="ticket-number" id="modalTicketNum">--</div>
                <button onclick="window.print()" style="background:#10b981; color:#fff; border:none; padding:10px; width:100%; border-radius:6px; font-weight:bold; cursor:pointer;">🖨️ طباعة</button>
                <button onclick="closeModal()" style="background:#ef4444; color:#fff; border:none; padding:8px; width:100%; border-radius:6px; font-weight:bold; margin-top:8px; cursor:pointer;">إغلاق</button>
            </div>
        </div>
        <script>
            function issueTicket(sId){
                let isPriority = document.getElementById('isPriority').checked ? 1 : 0;
                fetch('/api/issue-ticket/' + sId, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({is_priority: isPriority})
                }).then(res => res.json()).then(data => {
                    if(data.success){
                        document.getElementById('modalTicketNum').innerText = data.ticket_number;
                        document.getElementById('ticketServiceName').innerText = data.service_name;
                        document.getElementById('ticketModal').style.display = 'flex';
                    }
                });
            }
            function closeModal(){ document.getElementById('ticketModal').style.display = 'none'; window.location.reload(); }
        </script></body></html>
    ''', center=center, services=services)

@app.route('/api/issue-ticket/<int:service_id>', methods=['POST'])
def api_issue_ticket(service_id):
    conn = get_db_connection()
    service = conn.execute('SELECT * FROM services WHERE id = ?', (service_id,)).fetchone()
    data = request.get_json(silent=True) or request.form
    is_priority = 1 if data.get('is_priority') in [1, '1', True, 'true'] else 0
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    last_ticket = conn.execute('SELECT ticket_number, created_at FROM queue_tokens WHERE service_id = ? ORDER BY id DESC LIMIT 1', (service_id,)).fetchone()
    
    next_num = 1
    if last_ticket and last_ticket['created_at'] and last_ticket['created_at'].split(' ')[0] == today_str:
        try: next_num = int(last_ticket['ticket_number'].split('-')[1]) + 1
        except: next_num = 1

    prefix = "P" if is_priority else "T"
    ticket_number = f"{prefix}-{next_num:03d}"
    
    conn.execute('INSERT INTO queue_tokens (center_id, service_id, ticket_number, status, is_priority) VALUES (?, ?, ?, "WAITING", ?)', 
                 (service['center_id'], service_id, ticket_number, is_priority))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'ticket_number': ticket_number, 'service_name': service['service_name']})

# ==========================================
# 7. شاشة النداء (Employee Interface)
# ==========================================
@app.route('/employee-interface')
def employee_interface():
    if session.get('role') != 'employee':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    service = conn.execute('SELECT * FROM services WHERE id = ?', (session['service_id'],)).fetchone()
    conn.close()
    if not service: return redirect(url_for('login'))

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>عون النداء</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .container { width: 450px; background: #1e293b; padding: 30px; border-radius: 15px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .ticket-box { font-size: 55px; color: #38bdf8; font-weight: bold; margin: 15px 0; background: #0f172a; padding: 15px; border-radius: 10px; border: 2px solid #334155; }
            button { width: 100%; padding: 14px; margin: 8px 0; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; color: #fff; }
        </style></head>
        <body><div class="container">
        <h2>🖥 نافذة المصلحة: {{ service.service_name }}</h2>
        <div class="ticket-box" id="currentTicket">---</div>
        <button style="background: #10b981;" onclick="callNext()">📢 نداء التالية</button>
        <button style="background: #3b82f6;" onclick="completeTicket()">✅ إنهاء التذكرة الحالية</button>
        <br><a href="/logout" style="color:#f87171; display:inline-block; margin-top:15px; text-decoration:none; font-weight:bold;">تسجيل الخروج 🚪</a>
        </div>
        <script>
            function updateStatus() { 
                fetch('/api/employee-status/{{ service.id }}').then(res=>res.json()).then(d=>{
                    document.getElementById('currentTicket').innerText = d.current_ticket || '---';
                }); 
            }
            function callNext() { 
                fetch('/api/call-next/{{ service.id }}', {method:'POST'}).then(res=>res.json()).then(data => {
                    if(data.success) { updateStatus(); } else { alert('لا توجد تذاكر في الانتظار حالياً!'); }
                }); 
            }
            function completeTicket() { 
                fetch('/api/complete-ticket/{{ service.id }}', {method: 'POST'}).then(()=> { updateStatus(); }); 
            }
            setInterval(updateStatus, 2000); updateStatus();
        </script></body></html>
    ''', service=service)

@app.route('/api/employee-status/<int:service_id>')
def api_employee_status(service_id):
    conn = get_db_connection()
    t = conn.execute('SELECT ticket_number FROM queue_tokens WHERE service_id = ? AND status = "CALLED" ORDER BY called_at DESC LIMIT 1', (service_id,)).fetchone()
    conn.close()
    return jsonify({'current_ticket': t['ticket_number'] if t else None})

@app.route('/api/call-next/<int:service_id>', methods=['POST'])
def api_call_next(service_id):
    conn = get_db_connection()
    conn.execute('UPDATE queue_tokens SET status = "COMPLETED" WHERE service_id = ? AND status = "CALLED"', (service_id,))
    next_t = conn.execute('SELECT * FROM queue_tokens WHERE service_id = ? AND status = "WAITING" ORDER BY is_priority DESC, id ASC LIMIT 1', (service_id,)).fetchone()
    if not next_t:
        conn.commit()
        conn.close()
        return jsonify({'success': False})
    conn.execute('UPDATE queue_tokens SET status = "CALLED", called_at = CURRENT_TIMESTAMP WHERE id = ?', (next_t['id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'ticket_number': next_t['ticket_number']})

@app.route('/api/complete-ticket/<int:service_id>', methods=['POST'])
def api_complete_ticket(service_id):
    conn = get_db_connection()
    conn.execute('UPDATE queue_tokens SET status = "COMPLETED" WHERE service_id = ? AND status = "CALLED"', (service_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==========================================
# 8. مراقبة شاشات كل المراكز (System Admin)
# ==========================================
@app.route('/system/all-displays')
def system_all_displays():
    if session.get('role') != 'system_admin':
        return "غير مصرح لك بالوصول!", 403
    conn = get_db_connection()
    centers = conn.execute('SELECT * FROM centers').fetchall()
    conn.close()
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>مراقبة شاشات كل المراكز</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background: #1e293b; padding: 15px 20px; border-radius: 10px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
            .center-card { background: #1e293b; border-radius: 12px; padding: 15px; border: 1px solid #334155; }
            .center-title { font-size: 18px; font-weight: bold; color: #f59e0b; margin-bottom: 10px; display: flex; justify-content: space-between; }
            .current-box { background: #0f172a; padding: 10px; border-radius: 8px; text-align: center; }
            .ticket-num { font-size: 35px; color: #10b981; font-weight: bold; margin: 5px 0; }
            .btn { padding: 5px 10px; background: #3b82f6; color: #fff; border-radius: 5px; text-decoration: none; font-size: 12px; }
        </style></head>
        <body>
        <div class="header">
            <h2>🖥️ مراقبة شاشات العرض لجميع المراكز</h2>
            <a href="/system-dashboard" style="color: #f87171; text-decoration: none; font-weight: bold;">العودة لوحة التحكم 🔙</a>
        </div>
        <div class="grid">
            {% for c in centers %}
            <div class="center-card">
                <div class="center-title">
                    <span>🏢 {{ c.center_name }}</span>
                    <a href="/display/{{ c.id }}" target="_blank" class="btn">الشاشة الكاملة ↗</a>
                </div>
                <div class="current-box">
                    <div style="font-size: 12px; color: #94a3b8;">التذكرة الحالية</div>
                    <div class="ticket-num" id="t-{{ c.id }}">---</div>
                    <div style="font-size: 14px; color: #38bdf8;" id="s-{{ c.id }}">بانتظار النداء...</div>
                </div>
            </div>
            {% endfor %}
        </div>
        <script>
            function updateAllDisplays() {
                {% for c in centers %}
                fetch('/api/display-data/{{ c.id }}').then(res => res.json()).then(data => {
                    if(data.current) {
                        document.getElementById('t-{{ c.id }}').innerText = data.current.ticket_number;
                        document.getElementById('s-{{ c.id }}').innerText = data.current.service_name;
                    } else {
                        document.getElementById('t-{{ c.id }}').innerText = '---';
                        document.getElementById('s-{{ c.id }}').innerText = 'لا توجد تذكرة نشطة';
                    }
                });
                {% endfor %}
            }
            setInterval(updateAllDisplays, 3000); updateAllDisplays();
        </script>
        </body></html>
    ''', centers=centers)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
