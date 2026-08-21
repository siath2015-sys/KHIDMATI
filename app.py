from flask import Flask, render_template, request, jsonify, redirect, url_for, session, render_template_string
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tax_hierarchy_role_secret_2026'

def get_db_connection():
    conn = sqlite3.connect('tax-queue-db.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS centers (id INTEGER PRIMARY KEY AUTOINCREMENT, center_name TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_name TEXT NOT NULL, FOREIGN KEY (center_id) REFERENCES centers (id) ON DELETE CASCADE)')
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, center_id INTEGER, service_id INTEGER, FOREIGN KEY (center_id) REFERENCES centers (id) ON DELETE CASCADE, FOREIGN KEY (service_id) REFERENCES services (id) ON DELETE CASCADE)')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS queue_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            center_id INTEGER, 
            service_id INTEGER, 
            ticket_number TEXT NOT NULL, 
            status TEXT DEFAULT "WAITING", 
            is_priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            called_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (center_id) REFERENCES centers (id), 
            FOREIGN KEY (service_id) REFERENCES services (id) ON DELETE CASCADE
        )
    ''')
    conn.execute('CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, is_active INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, is_active INTEGER DEFAULT 0)')
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = 'system_admin'")
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', ('admin_system', 'root_2026', 'system_admin'))
        conn.commit()
    conn.close()

init_db()

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
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
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>الدخول إلى نظام التذاكر</title>
        <script>
            window.addEventListener("pageshow", function (event) {
                if (event.persisted) { window.location.reload(); }
            });
        </script>
        <style>
            body { 
                background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
                color: #1e293b; 
                font-family: Tahoma; 
                display: flex; 
                flex-direction: column; 
                justify-content: space-between; 
                align-items: center; 
                height: 100vh; 
                margin: 0; 
                padding: 20px; 
                box-sizing: border-box; 
            }
            .login-container { display: flex; flex-direction: column; align-items: center; justify-content: center; flex-grow: 1; width: 100%; }
            .card { 
                background: #ffffff; 
                padding: 35px; 
                border-radius: 15px; 
                width: 100%; 
                max-width: 420px; 
                text-align: center; 
                box-shadow: 0 15px 35px rgba(0,0,0,0.3); 
                border: 1px solid #e2e8f0; 
            }
            .logo-img { height: 75px; object-fit: contain; margin-bottom: 15px; }
            input { 
                width: 92%; 
                padding: 14px; 
                margin: 10px 0; 
                border-radius: 8px; 
                border: 1px solid #cbd5e1; 
                background: #f8fafc; 
                color: #0f172a; 
                font-size: 15px; 
                box-sizing: border-box; 
            }
            input:focus { border-color: #3b82f6; outline: none; background: #fff; }
            button { 
                width: 92%; 
                padding: 14px; 
                background: #2563eb; 
                color: #fff; 
                border: none; 
                border-radius: 8px; 
                font-weight: bold; 
                font-size: 16px; 
                cursor: pointer; 
                margin-top: 10px; 
                transition: 0.2s; 
            }
            button:hover { background: #1d4ed8; }
            .footer-signature { text-align: center; color: #cbd5e1; font-size: 13px; line-height: 1.6; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); width: 100%; max-width: 600px; }
        </style></head>
        
        <body>
        <div></div>
        
        <div class="login-container">
            <div class="card">
                <img src="/static/header_logo.png" alt="شعار المديرية العامة للضرائب" class="logo-img" onerror="this.src='https://i.ibb.co/6y4G894/header-logo.png'">
                <h3 style="margin-top: 5px; margin-bottom: 20px; color: #1e293b; font-size: 20px;">الدخول إلى نظام التذاكر</h3>
                
                {% if error %}<div style="color:#ef4444; background:rgba(239,68,68,0.1); padding:10px; border-radius:6px; margin-bottom:15px; font-weight:bold; font-size: 14px;">{{ error }}</div>{% endif %}
                
                <form method="POST">
                    <input type="text" name="username" placeholder="اسم المستخدم" required autocomplete="off"><br>
                    <input type="password" name="password" placeholder="كلمة المرور" required><br>
                    <button type="submit">تسجيل الدخول</button>
                </form>
            </div>
        </div>

        <div class="footer-signature">
            من إنجاز: <b>عتامنة الطاهر</b> - تقني سامي إعلام آلي<br>
            المديرية الولائية للضرائب ميلة
        </div>
        
        </body></html>
    ''', error=error)

@app.route('/system-dashboard', methods=['GET', 'POST'])
def system_dashboard():
    if session.get('role') != 'system_admin':
        return "غير مصرح لك بالوصول إلى لوحة تحكم المسؤول!", 403[cite: 1]

    conn = get_db_connection()
       
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_center':
            c_name = request.form.get('center_name')
            if c_name: conn.execute('INSERT INTO centers (center_name) VALUES (?)', (c_name,)); conn.commit()
        elif action == 'edit_center':
            c_id, c_name = request.form.get('center_id'), request.form.get('center_name')
            if c_id and c_name: conn.execute('UPDATE centers SET center_name = ? WHERE id = ?', (c_name, c_id)); conn.commit()
        elif action == 'delete_center':
            conn.execute('DELETE FROM centers WHERE id = ?', (request.form.get('center_id'),)); conn.commit()
            
        elif action == 'add_service':
            c_id, s_name = request.form.get('center_id'), request.form.get('service_name')
            if c_id and s_name: conn.execute('INSERT INTO services (center_id, service_name) VALUES (?, ?)', (c_id, s_name)); conn.commit()
        elif action == 'edit_service':
            s_id, s_name = request.form.get('service_id'), request.form.get('service_name')
            if s_id and s_name: conn.execute('UPDATE services SET service_name = ? WHERE id = ?', (s_name, s_id)); conn.commit()
        elif action == 'delete_service':
            conn.execute('DELETE FROM services WHERE id = ?', (request.form.get('service_id'),)); conn.commit()
            
        elif action == 'add_user':
            uname, pwd, role = request.form.get('username'), request.form.get('password'), request.form.get('role')
            c_id, s_id = request.form.get('center_id') or None, request.form.get('service_id') or None
            if uname and pwd and role:
                try: conn.execute('INSERT INTO users (username, password, role, center_id, service_id) VALUES (?, ?, ?, ?, ?)', (uname, pwd, role, c_id, s_id)); conn.commit()
                except: pass
        elif action == 'delete_user':
            conn.execute('DELETE FROM users WHERE id = ?', (request.form.get('user_id'),)); conn.commit()
            
        elif action == 'add_video':
            v_title, v_url = request.form.get('title'), request.form.get('url')
            if v_title and v_url: conn.execute('INSERT INTO videos (title, url, is_active) VALUES (?, ?, 0)', (v_title, v_url)); conn.commit()
        elif action == 'delete_video':
            conn.execute('DELETE FROM videos WHERE id = ?', (request.form.get('video_id'),)); conn.commit()
        elif action == 'set_active_video':
            v_id = request.form.get('video_id')
            conn.execute('UPDATE videos SET is_active = 0')
            conn.execute('UPDATE videos SET is_active = 1 WHERE id = ?', (v_id,))
            conn.commit()
            
        elif action == 'add_announcement':
            content = request.form.get('content')
            if content: conn.execute('INSERT INTO announcements (content, is_active) VALUES (?, 0)', (content,)); conn.commit()
        elif action == 'delete_announcement':
            conn.execute('DELETE FROM announcements WHERE id = ?', (request.form.get('announcement_id'),)); conn.commit()
        elif action == 'set_active_announcement':
            a_id = request.form.get('announcement_id')
            conn.execute('UPDATE announcements SET is_active = 0')
            conn.execute('UPDATE announcements SET is_active = 1 WHERE id = ?', (a_id,))
            conn.commit()

    centers = conn.execute('SELECT * FROM centers').fetchall()
    services = conn.execute('SELECT s.*, c.center_name FROM services s JOIN centers c ON s.center_id = c.id').fetchall()
    users = conn.execute('SELECT u.*, c.center_name, s.service_name FROM users u LEFT JOIN centers c ON u.center_id = c.id LEFT JOIN services s ON u.service_id = s.id').fetchall()
    videos = conn.execute('SELECT * FROM videos').fetchall()
    announcements = conn.execute('SELECT * FROM announcements').fetchall()
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم الشاملة</title>
        <script>
            window.addEventListener("pageshow", function (event) {
                if (event.persisted) { window.location.reload(); }
            });

            function confirmResetTickets(centerId, centerName) {
                if (confirm('هل أنت متأكد من رغبة في تصفير وإعادة ضبط طابور المركز: ' + centerName + '؟')) {
                    fetch('/api/reset-tickets/' + centerId, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'}
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            alert(data.message);
                            location.reload();
                        } else {
                            alert(data.message);
                        }
                    })
                    .catch(err => {
                        alert('حدث خطأ في الاتصال بالخادم.');
                    });
                }
            }
        </script>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .container { max-width: 1200px; margin: auto; }
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .logout-btn { background: #ef4444; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; display: flex; align-items: center; gap: 8px; box-shadow: 0 4px 10px rgba(239,68,68,0.3); transition: 0.2s; }
            .logout-btn:hover { background: #dc2626; }
            .card { background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            input, select { padding: 12px; margin: 8px; background: #0f172a; color: #fff; border: 1px solid #475569; border-radius: 8px; box-sizing: border-box; font-size: 14px; }
            button { padding: 12px 20px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 14px; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; background: #0f172a; }
            th, td { padding: 12px; text-align: center; border-bottom: 1px solid #334155; font-size: 14px; } th { color: #f59e0b; }
            .btn-dash { display: inline-block; background: #10b981; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-left: 10px; }
        </style></head>
        <body><div class="container">
        
        <div class="top-bar">
            <h2>🛠️ لوحة تحكم مسؤول النظام (التحكم الكامل بالحذف والتعديل والإضافة)</h2>
            <a href="/logout" class="logout-btn"><span>تسجيل الخروج</span> 🚪</a>
        </div>
        
         <div class="card">
            <a href="/system/all-displays" target="_blank" class="btn-dash">🖥️ عرض شاشات كل المراكز</a>
            <a href="/system/dashboard-stats" target="_blank" class="btn-dash" style="background: #3b82f6;">📊 لوحة إحصائيات المديرية (Tableau de Bord)</a>
        </div> 

       <div class="card">
            <h3>📢 إدارة الشريط الإعلاني المتحرك</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add_announcement">
                <input type="text" name="content" placeholder="نص الإعلان أو الشريط المتحرك الجديد..." required style="width: 72%;">
                <button type="submit" style="background:#10b981;">إضافة إعلان</button>
            </form>
            <table>
                <tr><th>نص الإعلان</th><th>الحالة</th><th>إجراء</th></tr>
                {% for a in announcements %}
                <tr>
                    <td>{{ a.content }}</td>
                    <td>
                        {% if a.is_active == 1 %}<span style="color:#10b981; font-weight:bold;">نشط حالياً ⭐</span>
                        {% else %}
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="set_active_announcement"><input type="hidden" name="announcement_id" value="{{ a.id }}"><button type="submit" style="background:#f59e0b; padding:5px 12px; font-size:12px;">تفعيل</button></form>
                        {% endif %}
                    </td>
                    <td>
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_announcement"><input type="hidden" name="announcement_id" value="{{ a.id }}"><button type="submit" style="background:#ef4444; padding:5px 12px; font-size:12px;">حذف</button></form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
       
        <div class="card">
            <h3>🎬 إدارة الفيديوهات الترويجية للشاشات (قائمة التشغيل المتسلسلة)</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add_video">
                <input type="text" name="title" placeholder="عنوان الفيديو" required style="width: 28%;">
                <input type="text" name="url" placeholder="رابط الفيديو (رابط يوتيوب كامل أو معرف الفيديو)" required style="width: 48%;">
                <button type="submit" style="background:#10b981;">إضافة فيديو</button>
            </form>
            <table>
                <tr><th>العنوان</th><th>الرابط</th><th>الحالة</th><th>إجراء</th></tr>
                {% for v in videos %}
                <tr>
                    <td>{{ v.title }}</td>
                    <td style="color:#38bdf8; font-size:12px;">{{ v.url }}</td>
                    <td>
                        {% if v.is_active == 1 %}<span style="color:#10b981; font-weight:bold;">نشط حالياً ⭐</span>
                        {% else %}
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="set_active_video"><input type="hidden" name="video_id" value="{{ v.id }}"><button type="submit" style="background:#f59e0b; padding:5px 12px; font-size:12px;">تفعيل</button></form>
                        {% endif %}
                    </td>
                    <td>
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_video"><input type="hidden" name="video_id" value="{{ v.id }}"><button type="submit" style="background:#ef4444; padding:5px 12px; font-size:12px;">حذف</button></form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>🏢 إدارة المراكز وإعادة ضبط الطوابير</h3>
            <form method="POST" style="margin-bottom:15px;">
                <input type="hidden" name="action" value="add_center">
                <input type="text" name="center_name" placeholder="اسم المركز الجديد" required style="width: 40%;">
                <button type="submit" style="background:#10b981;">إضافة المركز</button>
            </form>
            <table>
                <tr><th>معرف المركز</th><th>اسم المركز</th><th>تعديل الاسم</th><th>إعادة ضبط الطابور</th><th>حذف المركز</th></tr>
                {% for c in centers %}
                <tr>
                    <td>{{ c.id }}</td>
                    <td>
                        <form method="POST" style="display:inline;">
                            <input type="hidden" name="action" value="edit_center">
                            <input type="hidden" name="center_id" value="{{ c.id }}">
                            <input type="text" name="center_name" value="{{ c.center_name }}" style="width: 60%; padding: 8px;">
                            <button type="submit" style="background:#3b82f6; padding: 8px 15px; font-size:12px;">حفظ</button>
                        </form>
                    </td>
                    <td>
                        <button type="button" onclick="confirmResetTickets({{ c.id }}, '{{ c.center_name }}')" style="background:#d97706; padding:8px 15px; font-size:12px;">⚠️ تصفير الطابور</button>
                    </td>
                    <td>
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_center"><input type="hidden" name="center_id" value="{{ c.id }}"><button type="submit" style="background:#ef4444; padding:8px 15px; font-size:12px;">حذف</button></form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>📌 إدارة المصالح</h3>
            <form method="POST" style="margin-bottom:15px;">
                <input type="hidden" name="action" value="add_service">
                <select name="center_id" required style="width: 30%;"><option value="">اختر المركز</option>{% for c in centers %}<option value="{{ c.id }}">{{ c.center_name }}</option>{% endfor %}</select>
                <input type="text" name="service_name" placeholder="اسم المصلحة" required style="width: 40%;">
                <button type="submit" style="background:#10b981;">إضافة المصلحة</button>
            </form>
            <table>
                <tr><th>المصلحة</th><th>المركز التابع له</th><th>تعديل الاسم</th><th>حذف</th></tr>
                {% for s in services %}
                <tr>
                    <td>
                        <form method="POST" style="display:inline;">
                            <input type="hidden" name="action" value="edit_service">
                            <input type="hidden" name="service_id" value="{{ s.id }}">
                            <input type="text" name="service_name" value="{{ s.service_name }}" style="width: 60%; padding: 8px;">
                            <button type="submit" style="background:#3b82f6; padding: 8px 15px; font-size:12px;">حفظ</button>
                        </form>
                    </td>
                    <td>{{ s.center_name }}</td>
                    <td>تعديل مباشر</td>
                    <td>
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_service"><input type="hidden" name="service_id" value="{{ s.id }}"><button type="submit" style="background:#ef4444; padding:8px 15px; font-size:12px;">حذف</button></form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>👥 إدارة المستخدمين والصلاحيات</h3>
            <form method="POST" style="margin-bottom:15px;">
                <input type="hidden" name="action" value="add_user">
                <input type="text" name="username" placeholder="اسم المستخدم" required style="width: 22%;">
                <input type="password" name="password" placeholder="كلمة المرور" required style="width: 22%;">
                <select name="role" required style="width: 20%;"><option value="employee">عون نداء</option><option value="center_admin">مسؤول مركز</option><option value="directorate">مديرية عامة</option></select>
                <select name="center_id" style="width: 25%;"><option value="">اختر المركز</option>{% for c in centers %}<option value="{{ c.id }}">{{ c.center_name }}</option>{% endfor %}</select>
                <select name="service_id" style="width: 30%;"><option value="">اختر المصلحة</option>{% for s in services %}<option value="{{ s.id }}">{{ s.center_name }} - {{ s.service_name }}</option>{% endfor %}</select>
                <button type="submit" style="background:#10b981; margin-top: 10px;">إضافة مستخدم</button>
            </form>
            <table>
                <tr><th>اسم المستخدم</th><th>الدور</th><th>المركز</th><th>المصلحة</th><th>إجراء</th></tr>
                {% for u in users %}
                <tr>
                    <td>{{ u.username }}</td>
                    <td>{{ u.role }}</td>
                    <td>{{ u.center_name or '-' }}</td>
                    <td>{{ u.service_name or '-' }}</td>
                    <td>
                        {% if u.role != 'system_admin' %}
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="delete_user"><input type="hidden" name="user_id" value="{{ u.id }}"><button type="submit" style="background:#ef4444; padding:5px 12px; font-size:12px;">حذف</button></form>
                        {% else %}
                        <span style="color:#64748b;">محمي</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div></div></body></html>
    ''', centers=centers, services=services, users=users, videos=videos, announcements=announcements)

@app.route('/directorate-dashboard')
def directorate_dashboard():
    if session.get('role') != 'directorate':
        return "غير مصرح لك بالوصول!", 403
    return redirect('/system/dashboard-stats')

@app.route('/center-dashboard')
def center_dashboard():
    if session.get('role') != 'center_admin': 
        return "غير مصرح لك!", 403
    center_id = session.get('center_id')
    
    conn = get_db_connection()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    services = conn.execute('SELECT * FROM services WHERE center_id = ?', (center_id,)).fetchall()
    total_tokens = conn.execute('SELECT COUNT(*) as cnt FROM queue_tokens WHERE center_id = ?', (center_id,)).fetchone()['cnt']
    completed_tokens = conn.execute('SELECT COUNT(*) as cnt FROM queue_tokens WHERE center_id = ? AND status = "COMPLETED"', (center_id,)).fetchone()['cnt']
    waiting_tokens = conn.execute('SELECT COUNT(*) as cnt FROM queue_tokens WHERE center_id = ? AND status = "WAITING"', (center_id,)).fetchone()['cnt']
    
    metrics = conn.execute('''
        SELECT 
            s.service_name,
            COUNT(t.id) as total_served,
            ROUND(AVG((JULIANDAY(t.called_at) - JULIANDAY(t.created_at)) * 24 * 60), 1) as avg_waiting_minutes,
            ROUND(AVG((JULIANDAY(t.completed_at) - JULIANDAY(t.called_at)) * 24 * 60), 1) as avg_service_minutes
        FROM services s
        LEFT JOIN queue_tokens t ON s.id = t.service_id AND t.status = 'COMPLETED'
        WHERE s.center_id = ?
        GROUP BY s.id, s.service_name
    ''', (center_id,)).fetchall()
    
    conn.close()
    center_name = center['center_name'] if center else 'غير متوفر'

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة تحكم المركز</title>
        <script>
            window.addEventListener("pageshow", function (event) {
                if (event.persisted) { window.location.reload(); }
            });
        </script>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; margin: 0; }
            .container { max-width: 1000px; margin: auto; }
            .card { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: #1e293b; padding: 20px; border-radius: 12px; text-align: center; border: 1px solid #334155; }
            .stat-num { font-size: 30px; font-weight: bold; color: #38bdf8; margin-top: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #0f172a; }
            th, td { padding: 12px; text-align: center; border-bottom: 1px solid #334155; font-size: 14px; } th { color: #f59e0b; }
            .logout { float: left; color: #f87171; text-decoration: none; font-weight: bold; }
            .btn { padding: 6px 12px; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 13px; }
        </style></head>
        <body><div class="container">
        <a href="/logout" class="logout">تسجيل الخروج 🚪</a>
        <h2>🏢 لوحة تحكم المركز: {{ center_name }}</h2>
        <div class="stats-grid">
            <div class="stat-card"><div>إجمالي التذاكر</div><div class="stat-num">{{ total_tokens }}</div></div>
            <div class="stat-card"><div>التذاكر المنجزة</div><div class="stat-num" style="color:#10b981;">{{ completed_tokens }}</div></div>
            <div class="stat-card"><div>في الانتظار</div><div class="stat-num" style="color:#f59e0b;">{{ waiting_tokens }}</div></div>
        </div>
        
        <div class="card">
            <h3>⏱️ متوسط الأوقات المستغرفة لكل مصلحة (بالدقائق)</h3>
            <table>
                <tr><th>اسم المصلحة</th><th>التذاكر المنجزة</th><th>متوسط وقت الانتظار</th><th>متوسط زمن الخدمة</th></tr>
                {% for m in metrics %}
                <tr>
                    <td><b>{{ m.service_name }}</b></td>
                    <td style="color: #10b981;">{{ m.total_served or 0 }}</td>
                    <td style="color: #f59e0b;">{{ m.avg_waiting_minutes if m.avg_waiting_minutes is not none else '---' }} دقيقة</td>
                    <td style="color: #38bdf8;">{{ m.avg_service_minutes if m.avg_service_minutes is not none else '---' }} دقيقة</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>📌 المصالح التابعة للمركز</h3>
            <table>
                <tr><th>رقم المصلحة</th><th>اسم المصلحة</th><th>إجراء</th></tr>
                {% for s in services %}
                <tr><td>{{ s.id }}</td><td><b>{{ s.service_name }}</b></td><td><a href="/kiosk/{{ center_id }}" target="_blank" class="btn" style="background:#10b981;">جهاز سحب التذاكر 🎫</a></td></tr>
                {% endfor %}
            </table>
        </div>
        {% if center_id %}
        <div class="card" style="text-align: center;">
            <h3>🖥️ شاشة العرض الخاصة بالمركز</h3>
            <a href="/display/{{ center_id }}" target="_blank" class="btn" style="padding: 10px 20px; font-size: 16px; background: #f59e0b; color: #000; font-weight: bold;">فتح شاشة العرض للمركز 🖥️</a>
        </div>
        {% endif %}</div></body></html>
    ''', center_name=center_name, center_id=center_id, services=services, total_tokens=total_tokens, completed_tokens=completed_tokens, waiting_tokens=waiting_tokens, metrics=metrics)

@app.route('/display/<int:center_id>')
def display_screen(center_id):
    conn = get_db_connection()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    conn.close()
    if not center: 
        return "المركز غير موجود", 404
        
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>شاشة العرض - {{ center.center_name }}</title>
        <script src="https://www.youtube.com/iframe_api"></script>
        <!-- مكتبة توليد QR Code -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <script>
            window.addEventListener("pageshow", function (event) {
                if (event.persisted) { window.location.reload(); }
            });
        </script>
        <style>
            :root { --gov-blue: #0284c7; --gov-green: #0d9488; --gold: #fbbf24; }
            body { 
                background: linear-gradient(135deg, #0284c7 0%, #0891b2 50%, #0d9488 100%); 
                color: #fff; 
                font-family: 'Segoe UI', Tahoma; 
                margin: 0; 
                padding: 10px; 
                height: 100vh; 
                display: flex; 
                flex-direction: column; 
                box-sizing: border-box;
                overflow: hidden; 
            }
            .official-header { 
                background: #ffffff; 
                color: #0f172a;
                border-bottom: 3px solid #cbd5e1; 
                padding: 8px 20px; 
                border-radius: 12px; 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            }
            .center-badge { color: #0284c7; font-size: 20px; font-weight: bold; }
            .header-left { display: flex; align-items: center; gap: 15px; }
            
            .datetime-box { background: #f8fafc; border: 1px solid #cbd5e1; padding: 5px 15px; border-radius: 8px; text-align: center; }
            .current-time { font-size: 16px; font-weight: bold; color: #0f172a; font-family: monospace; }
            .current-date { font-size: 11px; color: #64748b; }

            .main-content { display: flex; gap: 15px; flex-grow: 1; margin-top: 10px; height: calc(100vh - 115px); }
            .right-panel { flex: 1; display: flex; flex-direction: column; gap: 10px; }
            
            .current-box { background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(10px); border-radius: 12px; padding: 10px; text-align: center; border: 2px solid rgba(255, 255, 255, 0.3); display: flex; flex-direction: column; align-items: center; justify-content: center; }
            .current-ticket { font-size: 80px; font-weight: 900; color: #fff; text-shadow: 0 0 30px rgba(255,255,255,0.6); margin: 0; line-height: 1; }
            .current-service { font-size: 18px; color: var(--gold); font-weight: bold; margin-top: 5px; margin-bottom: 8px; }
            
            .qr-direct-container { display: flex; align-items: center; justify-content: center; gap: 12px; background: rgba(255, 255, 255, 0.9); padding: 6px 15px; border-radius: 10px; width: fit-content; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
            .qr-text-side { text-align: right; }
            .qr-title-main { font-size: 13px; font-weight: 800; color: #0f172a; margin-bottom: 2px; }
            .qr-sub-text { font-size: 11px; color: #475569; font-weight: 600; }

            .pulse { animation: pulse-animation 1.5s infinite; }
            @keyframes pulse-animation { 0% { transform: scale(1); } 50% { transform: scale(1.04); } 100% { transform: scale(1); } }
            
            .history-box { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 12px; padding: 10px; border: 2px solid rgba(255, 255, 255, 0.2); flex-grow: 1; display: flex; flex-direction: column; }
            .history-title { font-size: 14px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px; margin-bottom: 6px; text-align: center; font-weight: bold; }
            .history-item { background: rgba(0, 0, 0, 0.25); color: #fff; padding: 6px 10px; border-radius: 6px; margin-bottom: 5px; display: flex; justify-content: space-between; font-size: 13px; border-right: 4px solid var(--gold); }
            
            .video-section { flex: 2; display: flex; flex-direction: column; background: #000; border-radius: 12px; overflow: hidden; border: 3px solid rgba(255, 255, 255, 0.3); }
            .video-container { flex-grow: 1; width: 100%; display: flex; align-items: center; justify-content: center; position: relative; }
            
            .video-controls { background: #1e293b; padding: 8px 15px; display: flex; gap: 10px; justify-content: center; align-items: center; border-top: 1px solid #334155; }
            .video-controls button { background: #0284c7; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: bold; transition: 0.2s; }
            .video-controls button:hover { background: #0ea5e9; }
            
            .ticker-wrap { background: #ffffff; color: #dc2626; padding: 8px 15px; border-radius: 8px; margin-top: 8px; overflow: hidden; white-space: nowrap; font-size: 18px; border: 2px solid #cbd5e1; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
            .ticker { display: inline-block; padding-left: 100%; animation: ticker 28s linear infinite; }
            @keyframes ticker { 0% { transform: translate(0, 0); } 100% { transform: translate(-100%, 0); } }
        </style></head>
        <body>
        <header class="official-header">
            <img src="/static/header_logo.png" style="height:45px; object-fit:contain;" onerror="this.style.display='none'">
            <div class="center-badge">🏢 {{ center.center_name }}</div>
            <div class="header-left">
                <div class="datetime-box">
                    <div class="current-time" id="liveTime">--:--:--</div>
                    <div class="current-date" id="liveDate">----/--/--</div>
                </div>
            </div>
        </header>

        <div class="main-content">
            <div class="right-panel">
                <div class="current-box">
                    <div style="font-size: 13px; color: #e2e8f0; font-weight: bold; margin-bottom: 2px;">التذكرة الحالية قيد النداء</div>
                    <div id="currTicket" class="current-ticket">---</div>
                    <div id="currService" class="current-service">لا توجد تذكرة حالية</div>
                    
                    <div class="qr-direct-container">
                        <div id="qrcode" style="width: 75px; height: 75px;"></div>
                        <div class="qr-text-side">
                            <div class="qr-title-main">تابع دورك عبر هاتفك</div>
                            <div class="qr-sub-text">وجه كاميرا الهاتف هنا</div>
                        </div>
                    </div>
                </div>

                <div class="history-box">
                    <div class="history-title">آخر التذاكر المنداة</div>
                    <div id="historyList" style="overflow-y:auto; flex-grow:1;"></div>
                </div>
            </div>
            
            <div class="video-section">
                <div class="video-container" id="videoBox"><p style="color:#94a3b8;">جاري تحميل مشغل الفيديوهات...</p></div>
                <div class="video-controls">
                    <button onclick="togglePlayPause()">⏸ إيقاف / تشغيل</button>
                    <button onclick="toggleMuteUnmute()">🔇 كتم / إفلات الصوت</button>
                    <button onclick="playNextVideo()">⏭ الفيديو التالي</button>
                </div>
            </div>
        </div>
        
        <div class="ticker-wrap"><div class="ticker" id="announcementTicker">مرحباً بكم في مديرية الضرائب لولاية ميلة - المركز الجواري يرحب بكم</div></div>

        <script>
            window.onload = function() {
    // ضع رابط موقعك الحقيقي هنا مباشرة
    let trackUrl = "https://khidma-6ozh.onrender.com/track/{{ center.id }}"; 
    
    new QRCode(document.getElementById("qrcode"), {
        text: trackUrl,
        width: 75,
        height: 75,
        colorDark : "#0f172a",
        colorLight : "#ffffff",
        correctLevel : QRCode.CorrectLevel.H
    });
};

            function updateClock() {
                const now = new Date();
                document.getElementById('liveTime').innerText = now.toLocaleTimeString('ar-DZ');
                document.getElementById('liveDate').innerText = now.toLocaleDateString('ar-DZ', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
            }
            setInterval(updateClock, 1000); updateClock();

            let lastSpokenTicket = "";
            let chimeAudio = new Audio('/static/beep.mp3');
            let playlist = [], currentVideoIndex = 0, player = null, ytApiReady = false, isMutedByUser = false;

            function onYouTubeIframeAPIReady() { ytApiReady = true; if (playlist.length > 0) initPlayerForCurrentVideo(); }
            
            function muteVideo() { if (player && typeof player.mute === 'function' && !isMutedByUser) player.mute(); }
            function unmuteVideo() { if (player && typeof player.unMute === 'function' && !isMutedByUser) player.unMute(); }

            function togglePlayPause() {
                if (!player) return;
                let state = player.getPlayerState();
                if (state === YT.PlayerState.PLAYING) { player.pauseVideo(); } else { player.playVideo(); }
            }

            function toggleMuteUnmute() {
                if (!player) return;
                if (player.isMuted()) { player.unMute(); isMutedByUser = false; } else { player.mute(); isMutedByUser = true; }
            }

            function formatTicketForSpeech(ticketStr) {
                if (!ticketStr || ticketStr === '---') return '';
                let matches = ticketStr.match(/\d+/);
                return matches ? `رقم ${parseInt(matches[0], 10)}` : ticketStr;
            }

            function playAnnouncementSoundAndSpeech(ticketNum, serviceName) {
                muteVideo(); 
                chimeAudio.play().then(() => {
                    setTimeout(() => speak(ticketNum, serviceName), 800);
                }).catch(e => speak(ticketNum, serviceName));

                let ticketEl = document.getElementById('currTicket');
                ticketEl.classList.add('pulse');
                setTimeout(() => ticketEl.classList.remove('pulse'), 5000);
            }

            function speak(ticketNum, serviceName) {
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    let utterance = new SpeechSynthesisUtterance(`التذكرة ${formatTicketForSpeech(ticketNum)}, إلى مصلحة, ${serviceName}`);
                    utterance.lang = 'ar-SA'; 
                    utterance.rate = 0.85;
                    utterance.onend = () => { unmuteVideo(); }; 
                    window.speechSynthesis.speak(utterance);
                } else {
                    unmuteVideo();
                }
            }

            function getYouTubeId(url) {
                if (!url) return null;
                if (url.length === 11 && !url.includes('/')) return url;
                let match = url.match(/^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/);
                return (match && match[2].length === 11) ? match[2] : null;
            }

            function updatePlaylist(newVideos) {
                if (!newVideos || newVideos.length === 0) return;
                if (newVideos.map(v => v.url).join(',') !== playlist.map(v => v.url).join(',')) {
                    playlist = newVideos; currentVideoIndex = 0; initPlayerForCurrentVideo();
                }
            }

            function initPlayerForCurrentVideo() {
                if (playlist.length === 0) return;
                let currentVid = playlist[currentVideoIndex], ytId = getYouTubeId(currentVid.url), vBox = document.getElementById('videoBox');
                if (ytId) {
                    if (!ytApiReady) return;
                    if (!player) {
                        vBox.innerHTML = '<div id="yt-player" style="width:100%; height:100%;"></div>';
                        player = new YT.Player('yt-player', { height: '100%', width: '100%', videoId: ytId, playerVars: { 'autoplay': 1, 'controls': 0, 'mute': 1, 'rel': 0, 'loop': 1 }, events: { 'onReady': e => e.target.playVideo(), 'onStateChange': e => { if (e.data === YT.PlayerState.ENDED) playNextVideo(); } } });
                    } else { player.loadVideoById(ytId); }
                } else {
                    vBox.innerHTML = `<video id="localVideo" src="${currentVid.url}" autoplay muted style="width:100%; height:100%; object-fit:cover;"></video>`;
                    document.getElementById('localVideo').onended = playNextVideo;
                }
            }
            function playNextVideo() { if (playlist.length > 0) { currentVideoIndex = (currentVideoIndex + 1) % playlist.length; initPlayerForCurrentVideo(); } }

            function fetchDisplayData() {
                fetch('/api/display-data/{{ center.id }}').then(res => res.json()).then(data => {
                    if (data.current) {
                        let tNum = data.current.ticket_number, sName = data.current.service_name;
                        document.getElementById('currTicket').innerText = tNum;
                        document.getElementById('currService').innerText = sName;
                        let uniqueKey = tNum + '-' + data.current.called_at;
                        if (lastSpokenTicket !== uniqueKey) { lastSpokenTicket = uniqueKey; playAnnouncementSoundAndSpeech(tNum, sName); }
                    } else {
                        document.getElementById('currTicket').innerText = '---';
                        document.getElementById('currService').innerText = 'لا توجد تذكرة حالية';
                    }
                    let historyList = document.getElementById('historyList'); historyList.innerHTML = '';
                    if (data.history) {
                        data.history.forEach(h => {
                            let item = document.createElement('div'); item.className = 'history-item';
                            item.innerHTML = `<span><b>${h.ticket_number}</b> (${h.service_name})</span> <span style="color:#4ade80; font-size:12px; font-weight:bold;">منجز</span>`;
                            historyList.appendChild(item);
                        });
                    }
                    if (data.videos) updatePlaylist(data.videos);
                    if (data.active_announcement) document.getElementById('announcementTicker').innerText = data.active_announcement.content;
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
    videos = conn.execute('SELECT * FROM videos').fetchall()
    active_announcement = conn.execute('SELECT * FROM announcements WHERE is_active = 1 LIMIT 1').fetchone()
    conn.close()
    return jsonify({
        'current': dict(current) if current else None,
        'history': [dict(h) for h in history],
        'videos': [dict(v) for v in videos],
        'active_announcement': dict(active_announcement) if active_announcement else None
    })

@app.route('/kiosk/<int:center_id>')
def kiosk_machine(center_id):
    conn = get_db_connection()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    services = conn.execute('SELECT * FROM services WHERE center_id = ?', (center_id,)).fetchall()
    conn.close()
    
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>سحب تذكرة - {{ center.center_name }}</title>
        <!-- مكتبة توليد QR Code -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; direction: rtl; }
            .box { background: #1e293b; padding: 40px; border-radius: 20px; text-align: center; width: 420px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .priority-box { background: rgba(245, 158, 11, 0.15); border: 2px dashed #f59e0b; padding: 12px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; gap: 10px; cursor: pointer; }
            .priority-box label { color: #fbbf24; font-weight: bold; font-size: 15px; cursor: pointer; }
            .priority-box input { width: 20px; height: 20px; accent-color: #f59e0b; cursor: pointer; }
            
            .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; }
            .ticket-card { background: #fff; color: #000; padding: 25px; border-radius: 14px; width: 340px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); font-family: Tahoma; }
            .ticket-card h2 { margin: 0 0 5px; color: #1e293b; font-size: 20px; }
            
            .service-highlight {
                background: #f0fdf4;
                border: 2px dashed #16a34a;
                color: #15803d;
                font-size: 19px;
                font-weight: 900;
                padding: 12px 10px;
                border-radius: 10px;
                margin: 12px 0;
                box-shadow: 0 4px 10px rgba(22, 163, 74, 0.1);
            }

            .ticket-number { font-size: 50px; font-weight: 900; color: #0284c7; margin: 5px 0; letter-spacing: 2px; }
            .ticket-info { font-size: 13px; color: #64748b; margin-bottom: 10px; }
            #qrcode { display: flex; justify-content: center; margin: 10px 0; }
            .btn-print { background: #10b981; color: #fff; border: none; padding: 12px 20px; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; width: 100%; margin-top: 10px; }
            .btn-close { background: #ef4444; color: #fff; border: none; padding: 8px 15px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 8px; }
            
            @media print {
                body * { visibility: hidden; }
                .ticket-card, .ticket-card * { visibility: visible; }
                .ticket-card { position: absolute; left: 0; top: 0; width: 100%; box-shadow: none; border: none; }
                .btn-print, .btn-close { display: none; }
            }
        </style></head>
        <body>
        
        <div class="box">
            <h2>🎫 سحب تذكرة - {{ center.center_name }}</h2>
            
            <div class="priority-box">
                <input type="checkbox" id="isPriority">
                <label for="isPriority">♿ ذوي الاحتياجات الخاصة (أولوية في الطابور)</label>
            </div>

            {% for s in services %}
            <button onclick="issueTicket({{ s.id }})" style="display:block; width:100%; background:#3b82f6; color:#fff; padding:15px; margin:12px 0; border:none; border-radius:8px; font-weight:bold; font-size:16px; cursor:pointer;">{{ s.service_name }}</button>
            {% endfor %}
        </div>

        <div id="ticketModal" class="modal">
            <div class="ticket-card">
                <h2>{{ center.center_name }}</h2>
                <div class="service-highlight" id="ticketServiceName">--</div>
                <div class="ticket-number" id="modalTicketNum">--</div>
                <div class="ticket-info" id="modalPriorityText"></div>
                <p style="font-size: 12px; font-weight: bold; margin: 5px 0; color: #334155;">📷 امسح الرمز لمتابعة دورك عن بعد:</p>
                <div id="qrcode"></div>
                <button class="btn-print" onclick="window.print()">🖨️ طباعة التذكرة</button>
                <button class="btn-close" onclick="closeModal()">إغلاق وإنهاء</button>
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
                        document.getElementById('ticketServiceName').innerText = data.service_name || 'خدمة عامة';
                        document.getElementById('modalPriorityText').innerHTML = data.is_priority ? '<span style="color: #d97706; font-weight: bold;">(تذكرة أولوية - ذوي الاحتياجات الخاصة)</span>' : '';
                        
                        document.getElementById('qrcode').innerHTML = "";
                        let trackUrl = window.location.origin + '/track/' + data.ticket_id;
                        new QRCode(document.getElementById("qrcode"), {
                            text: trackUrl,
                            width: 110,
                            height: 110
                        });

                        document.getElementById('ticketModal').style.display = 'flex';
                        document.getElementById('isPriority').checked = false; 
                    }
                });
            }

            function closeModal(){
                document.getElementById('ticketModal').style.display = 'none';
                window.location.reload(); 
            }
        </script>
        </body></html>
    ''', center=center, services=services)

@app.route('/api/issue-ticket/<int:service_id>', methods=['POST'])
def api_issue_ticket(service_id):
    conn = get_db_connection()
    service = conn.execute('SELECT * FROM services WHERE id = ?', (service_id,)).fetchone()
    
    data = request.get_json(silent=True) or request.form
    is_priority = 1 if data.get('is_priority') in [1, '1', True, 'true'] else 0
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    last_ticket = conn.execute('''
        SELECT ticket_number, created_at 
        FROM queue_tokens 
        WHERE service_id = ? 
        ORDER BY id DESC 
        LIMIT 1
    ''', (service_id,)).fetchone()
    
    next_num = 1
    if last_ticket and last_ticket['created_at']:
        last_date = last_ticket['created_at'].split(' ')[0]
        if last_date == today_str:
            try:
                last_num_str = last_ticket['ticket_number'].split('-')[1]
                next_num = int(last_num_str) + 1
            except:
                next_num = 1

    prefix = "P" if is_priority else "T"
    ticket_number = f"{prefix}-{next_num:03d}"
    
    cursor = conn.execute(
        'INSERT INTO queue_tokens (center_id, service_id, ticket_number, status, is_priority) VALUES (?, ?, ?, "WAITING", ?)', 
        (service['center_id'], service_id, ticket_number, is_priority)
    )
    new_ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'ticket_id': new_ticket_id,
        'ticket_number': ticket_number, 
        'service_name': service['service_name'],
        'is_priority': is_priority
    })

@app.route('/employee-window')
def employee_window():
    if session.get('role') != 'employee': return "غير مصرح لك!", 403
    conn = get_db_connection()
    service = conn.execute('SELECT * FROM services WHERE id = ?', (session['service_id'],)).fetchone()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (session['center_id'],)).fetchone()
    conn.close()
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>عون النداء</title>
        <script>
            window.addEventListener("pageshow", function (event) {
                if (event.persisted) { window.location.reload(); }
            });
        </script>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .container { width: 480px; background: #1e293b; padding: 30px; border-radius: 15px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .ticket-box { font-size: 50px; color: #38bdf8; font-weight: bold; margin: 15px 0; background: #0f172a; padding: 15px; border-radius: 10px; border: 2px solid #334155; }
            button { width: 100%; padding: 14px; margin: 8px 0; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; color: #fff; transition: 0.2s; }
            button:hover { opacity: 0.9; }
            .alert-box { padding: 10px; border-radius: 6px; margin-bottom: 15px; font-weight: bold; font-size: 14px; display: none; }
        </style></head>
        <body><div class="container">
        <h2>🖥 نافذة المصلحة: {{ service.service_name }}</h2>
        <div id="alertBox" class="alert-box"></div>
        <div class="ticket-box" id="currentTicket">---</div>
        <button style="background: #10b981;" onclick="callNext()">📢 نداء التالية</button>
        <button style="background: #f59e0b; color: #000;" onclick="recallCurrent()">🔊 إعادة النداء</button>
        <button style="background: #3b82f6;" onclick="completeTicket()">✅ إنهاء التذكرة الحالية</button>
        <br><a href="/logout" style="color:#f87171; display:inline-block; margin-top:15px; font-weight:bold; text-decoration:none;">تسجيل الخروج 🚪</a>
        </div>
        <script>
            let lastTicket = "", chimeAudio = new Audio('/static/beep.mp3');
            function showAlert(msg, color) {
                let box = document.getElementById('alertBox'); box.innerText = msg;
                box.style.background = color === 'green' ? 'rgba(16, 185, 129, 0.2)' : color === 'orange' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)';
                box.style.color = color === 'green' ? '#34d399' : color === 'orange' ? '#fbbf24' : '#f87171';
                box.style.display = 'block'; setTimeout(() => { box.style.display = 'none'; }, 3500);
            }
            function formatTicketForSpeech(ticketStr) {
                if (!ticketStr || ticketStr === '---') return '';
                let matches = ticketStr.match(/\d+/);
                return matches ? `رقم ${parseInt(matches[0], 10)}` : ticketStr;
            }
            function speakMessage(textMsg, isWarning = false) {
                if (!isWarning) { chimeAudio.play().then(() => setTimeout(() => executeSpeech(textMsg), 800)).catch(e => executeSpeech(textMsg)); }
                else { executeSpeech(textMsg); }
            }
            function executeSpeech(textMsg) {
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    let utterance = new SpeechSynthesisUtterance(textMsg);
                    utterance.lang = 'ar-SA'; utterance.rate = 0.85;
                    window.speechSynthesis.speak(utterance);
                }
            }
            function updateStatus(shouldSpeak = false) { 
                fetch('/api/employee-status/{{ session.service_id }}').then(res=>res.json()).then(d=>{
                    let curr = d.current_ticket || '---';
                    document.getElementById('currentTicket').innerText = curr;
                    if(curr !== '---' && curr !== lastTicket && shouldSpeak) {
                        lastTicket = curr;
                        speakMessage(`التذكرة ${formatTicketForSpeech(curr)}, إلى مصلحة, {{ service.service_name }}`);
                    }
                }); 
            }
            function callNext() { 
                fetch('/api/call-next/{{ session.service_id }}', {method:'POST'}).then(res=>res.json()).then(data => {
                    if(data.success) { showAlert('تم نداء التذكرة التالية بنجاح!', 'green'); updateStatus(true); }
                    else { showAlert('لا توجد أي تذاكر في الانتظار حالياً!', 'orange'); speakMessage('لا توجد أي تذاكر في الانتظار حالياً', true); }
                }); 
            }
            function recallCurrent() {
                let curr = document.getElementById('currentTicket').innerText;
                if(curr !== '---') { speakMessage(`التذكرة ${formatTicketForSpeech(curr)}, إلى مصلحة, {{ service.service_name }}`); showAlert('جاري إعادة النداء الصوتي...', 'green'); }
                else { showAlert('لا توجد تذكرة حالية لإعادة نداءها.', 'orange'); speakMessage('لا توجد تذكرة حالية لإعادة نداءها', true); }
            }
            function completeTicket() { 
                fetch('/api/complete-ticket/{{ session.service_id }}', {method:'POST'}).then(()=> { showAlert('تم إنهاء التذكرة الحالية.', 'green'); lastTicket = ""; updateStatus(false); }); 
            }
            setInterval(() => updateStatus(false), 2000); updateStatus(false);
        </script></body></html>
    ''', service=service, center=center)

@app.route('/api/employee-status/<int:service_id>')
def api_employee_status(service_id):
    conn = get_db_connection()
    t = conn.execute('SELECT ticket_number FROM queue_tokens WHERE service_id = ? AND status = "CALLED" ORDER BY called_at DESC LIMIT 1', (service_id,)).fetchone()
    conn.close()
    return jsonify({'current_ticket': t['ticket_number'] if t else None})

@app.route('/api/call-next/<int:service_id>', methods=['POST'])
def api_call_next(service_id):
    conn = get_db_connection()
    next_t = conn.execute('''
        SELECT * FROM queue_tokens 
        WHERE service_id = ? AND status = "WAITING" 
        ORDER BY is_priority DESC, id ASC 
        LIMIT 1
    ''', (service_id,)).fetchone()
    
    if next_t:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE queue_tokens SET status = "CALLED", called_at = ? WHERE id = ?', (now, next_t['id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False})

@app.route('/api/complete-ticket/<int:service_id>', methods=['POST'])
def api_complete_ticket(service_id):
    conn = get_db_connection()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
        UPDATE queue_tokens 
        SET status = "COMPLETED", completed_at = ? 
        WHERE service_id = ? AND status = "CALLED"
    ''', (now, service_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

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
            .logout-btn, .back-btn { background: #ef4444; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 4px 10px rgba(239,68,68,0.3); transition: 0.2s; font-size: 14px; }
            .back-btn { background: #3b82f6; box-shadow: 0 4px 10px rgba(59,130,246,0.3); }
            .logout-btn:hover { background: #dc2626; }
            .back-btn:hover { background: #2563eb; }
            .filter-box { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 20px; display: flex; gap: 15px; align-items: center; flex-wrap: wrap; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            .filter-box input { padding: 10px; background: #0f172a; color: #fff; border: 1px solid #475569; border-radius: 8px; font-size: 14px; }
            .btn { padding: 10px 20px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 14px; text-decoration: none; }
            .table-container { background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; background: #0f172a; border-radius: 8px; overflow: hidden; }
            th, td { padding: 14px; text-align: center; border-bottom: 1px solid #334155; font-size: 14px; } 
            th { color: #f59e0b; background: #1e293b; }
            .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
            .chart-card { background: #1e293b; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body><div class="container">
        
        <div class="top-bar">
            <h2>📊 لوحة القيادة وإحصائيات المراكز (Tableau de Bord)</h2>
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
                    <tr>
                        <th>اسم المركز</th>
                        <th>إجمالي التذاكر</th>
                        <th>التذاكر المعالجة</th>
                        <th>التذاكر في الانتظار</th>
                    </tr>
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
            <div class="chart-card">
                <canvas id="barChart"></canvas>
            </div>
            <div class="chart-card">
                <canvas id="pieChart"></canvas>
            </div>
        </div>

        <script>
            const centers = {{ centers_names | tojson }};
            const totals = {{ total_counts | tojson }};
            const served = {{ served_counts | tojson }};

            new Chart(document.getElementById('barChart'), {
                type: 'bar',
                data: {
                    labels: centers,
                    datasets: [
                        { label: 'إجمالي التذاكر', data: totals, backgroundColor: '#3b82f6' },
                        { label: 'المعالجة', data: served, backgroundColor: '#10b981' }
                    ]
                },
                options: { responsive: true, plugins: { legend: { labels: { color: '#fff' } } }, scales: { x: { ticks: { color: '#fff' } }, y: { ticks: { color: '#fff' } } } }
            });

            new Chart(document.getElementById('pieChart'), {
                type: 'doughnut',
                data: {
                    labels: centers,
                    datasets: [{
                        data: totals,
                        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
                    }]
                },
                options: { responsive: true, plugins: { legend: { labels: { color: '#fff' } } } }
            });
        </script>
        </div></body></html>
    ''', stats=stats, start_date=start_date, end_date=end_date, centers_names=centers_names, total_counts=total_counts, served_counts=served_counts)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; margin: 0; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background: #1e293b; padding: 15px 20px; border-radius: 10px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
            .center-card { background: #1e293b; border-radius: 12px; padding: 15px; border: 1px solid #334155; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            .center-title { font-size: 18px; font-weight: bold; color: #f59e0b; margin-bottom: 10px; border-bottom: 1px solid #334155; padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
            .current-box { background: #0f172a; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #475569; margin-bottom: 10px; }
            .ticket-num { font-size: 35px; color: #10b981; font-weight: bold; margin: 5px 0; }
            .service-name { font-size: 14px; color: #38bdf8; }
            .btn { padding: 5px 10px; background: #3b82f6; color: #fff; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; font-size: 12px; }
            .back-link { color: #f87171; text-decoration: none; font-weight: bold; }
        </style></head>
        <body>
        <div class="header">
            <h2>🖥️ مراقبة شاشات العرض لجميع المراكز</h2>
            <a href="/system-dashboard" class="back-link">العودة لوحة التحكم 🔙</a>
        </div>
        <div class="grid">
            {% for c in centers %}
            <div class="center-card" id="center-box-{{ c.id }}">
                <div class="center-title">
                    <span>🏢 {{ c.center_name }}</span>
                    <a href="/display/{{ c.id }}" target="_blank" class="btn">الشاشة الكاملة ↗</a>
                </div>
                <div class="current-box">
                    <div style="font-size: 12px; color: #94a3b8;">التذكرة الحالية</div>
                    <div class="ticket-num" id="t-{{ c.id }}">---</div>
                    <div class="service-name" id="s-{{ c.id }}">بانتظار النداء...</div>
                </div>
            </div>
            {% endfor %}
        </div>
        <script>
            function updateAllDisplays() {
                {% for c in centers %}
                fetch('/api/display-data/{{ c.id }}')
                    .then(res => res.json())
                    .then(data => {
                        if(data.current) {
                            document.getElementById('t-{{ c.id }}').innerText = data.current.ticket_number;
                            document.getElementById('s-{{ c.id }}').innerText = data.current.service_name;
                        } else {
                            document.getElementById('t-{{ c.id }}').innerText = '---';
                            document.getElementById('s-{{ c.id }}').innerText = 'لا توجد تذكرة نشطة';
                        }
                    }).catch(err => console.error(err));
                {% endfor %}
            }
            setInterval(updateAllDisplays, 3000);
            updateAllDisplays();
        </script>
        </body></html>
    ''', centers=centers)

@app.route('/api/reset-tickets/<int:center_id>', methods=['POST'])
def reset_tickets(center_id):
    data = request.get_json(silent=True) or {}
    reset_type = data.get('type', 'daily')
    
    conn = get_db_connection()
    try:
        if reset_type == 'full':
            conn.execute('DELETE FROM queue_tokens WHERE center_id = ?', (center_id,))
            message = "تم تنفيذ التصفير الكلي لجميع تذاكر المركز بنجاح."
        else:
            today_str = datetime.now().strftime('%Y-%m-%d')
            conn.execute('''
                DELETE FROM queue_tokens 
                WHERE center_id = ? 
                AND DATE(created_at) = ?
            ''', (center_id, today_str))
            message = f"تم تصفير طابور اليوم ({today_str}) للمركز بنجاح."
            
        conn.commit()
        success = True
    except Exception as e:
        conn.rollback()
        success = False
        message = f"حدث خطأ أثناء عملية التصفير: {str(e)}"
    finally:
        conn.close()
        
    return jsonify({'success': success, 'message': message})
    @app.route('/track/<int:center_id>')
def track_page(center_id):
    conn = get_db_connection()
    # جلب معلومات المركز ديناميكياً بناءً على الـ ID الموجود في الرابط
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    
    if not center:
        conn.close()
        return "<h2 style='text-align:center; font-family:Tahoma; margin-top:50px; color:#ef4444;'>عذراً، هذا المركز غير موجود.</h2>", 404

    # جلب التذكرة الحالية قيد النداء لهذا المركز
    current_ticket = conn.execute('''
        SELECT t.*, s.service_name 
        FROM queue_tokens t 
        JOIN services s ON t.service_id = s.id 
        WHERE t.center_id = ? AND t.status = 'CALLED' 
        ORDER BY t.called_at DESC LIMIT 1
    ''', (center_id,)).fetchone()

    # جلب آخر التذاكر المنجزة أو قائمة الانتظار المصغرة ليعلم المواطن دوره
    waiting_count = conn.execute('''
        SELECT COUNT(*) as cnt FROM queue_tokens 
        WHERE center_id = ? AND status = 'WAITING'
    ''', (center_id,)).fetchone()['cnt']

    conn.close()

    # تصميم صفحة المتابعة التي ستفتح في هاتف المواطن
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>متابعة الدور - {{ center.center_name }}</title>
            <meta http-equiv="refresh" content="10"> <!-- تحديث تلقائي للصفحة كل 10 ثواني -->
            <style>
                body { background: #0f172a; color: #fff; font-family: 'Segoe UI', Tahoma; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; box-sizing: border-box; }
                .card { background: #1e293b; padding: 25px; border-radius: 16px; text-align: center; width: 100%; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }
                .center-title { font-size: 18px; color: #38bdf8; font-weight: bold; margin-bottom: 15px; border-bottom: 2px solid #334155; padding-bottom: 10px; }
                .ticket-box { background: #0f172a; border-radius: 12px; padding: 20px; margin: 15px 0; border: 2px solid #0ea5e9; }
                .ticket-num { font-size: 60px; font-weight: 900; color: #fbbf24; margin: 5px 0; }
                .service-name { font-size: 16px; color: #cbd5e1; font-weight: bold; }
                .info-badge { background: rgba(14, 165, 233, 0.15); color: #38bdf8; padding: 10px; border-radius: 8px; font-size: 14px; margin-top: 15px; font-weight: bold; }
                .footer-note { font-size: 12px; color: #64748b; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="center-title">🏢 {{ center.center_name }}</div>
                
                <div style="font-size: 14px; color: #94a3b8;">التذكرة الحالية قيد النداء</div>
                
                <div class="ticket-box">
                    {% if current_ticket %}
                        <div class="ticket-num">{{ current_ticket.ticket_number }}</div>
                        <div class="service-name">مصلحة: {{ current_ticket.service_name }}</div>
                    {% else %}
                        <div class="ticket-num" style="font-size: 35px; color: #94a3b8;">---</div>
                        <div class="service-name">لا توجد تذكرة منداءة حالياً</div>
                    {% endif %}
                </div>

                <div class="info-badge">
                    ⏳ عدد التذاكر في قائمة الانتظار حالياً: <span style="color: #fbbf24; font-size: 18px;">{{ waiting_count }}</span>
                </div>

                <div class="footer-note">تتحدث هذه الصفحة تلقائياً لمتابعة دورك بسلاسة.</div>
            </div>
        </body>
        </html>
    ''', center=center, current_ticket=current_ticket, waiting_count=waiting_count)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
