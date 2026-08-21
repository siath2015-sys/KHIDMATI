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
app.secret_key = "tax_queue_secure_secret_key_2026"

# اسم قاعدة البيانات الثابت ليتوافق مع النسخة المحلية والسحابية
DB_NAME = "tax-queue-db"


def get_db_connection():
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  conn = get_db_connection()

  # إنشاء الجداول الأساسية
  conn.execute("""
        CREATE TABLE IF NOT EXISTS centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_name TEXT NOT NULL
        )
    """)
  conn.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_id INTEGER,
            service_name TEXT NOT NULL,
            FOREIGN KEY (center_id) REFERENCES centers (id)
        )
    """)
  conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            center_id INTEGER,
            service_id INTEGER,
            FOREIGN KEY (center_id) REFERENCES centers (id),
            FOREIGN KEY (service_id) REFERENCES services (id)
        )
    """)
  conn.execute("""
        CREATE TABLE IF NOT EXISTS queue_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_id INTEGER,
            service_id INTEGER,
            ticket_number TEXT NOT NULL,
            status TEXT DEFAULT 'WAITING',
            is_priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            called_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (center_id) REFERENCES centers (id),
            FOREIGN KEY (service_id) REFERENCES services (id)
        )
    """)
  conn.commit()

  # إدراج مركز افتراضي ومصلحتين افتراضيتين إذا كان الجدول فارغاً
  center_count = conn.execute("SELECT COUNT(*) FROM centers").fetchone()[0]
  if center_count == 0:
    conn.execute(
        "INSERT INTO centers (center_name) VALUES (?)",
        ("مركز الضرائب - ميلة الرئيسي",),
    )
    conn.execute(
        "INSERT INTO services (center_id, service_name) VALUES (?, ?)",
        (1, "مصلحة التمحيص والرقابة الجبائية"),
    )
    conn.execute(
        "INSERT INTO services (center_id, service_name) VALUES (?, ?)",
        (1, "مصلحة الاستقبال ووعاء الضريبة"),
    )
    conn.commit()

  # إدراج مستخدمين افتراضيين لكل الأدوار لتسهيل الاختبار الفوري
  user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
  if user_count == 0:
    default_users = [
        ("admin", "admin123", "system_admin", None, None),
        ("dir", "dir123", "directorate", None, None),
        ("center", "center123", "center_admin", 1, None),
        ("emp", "emp123", "employee", 1, 1),
    ]
    conn.executemany(
        """
            INSERT OR IGNORE INTO users (username, password, role, center_id, service_id)
            VALUES (?, ?, ?, ?, ?)
        """,
        default_users,
    )
    conn.commit()

  conn.close()


# استدعاء دالة تهيئة قاعدة البيانات عند بدء التشغيل
init_db()


# ترويسات منع التخزين المؤقت لجميع الردود
@app.after_request
def add_header(response):
  response.headers["Cache-Control"] = (
      "no-cache, no-store, must-revalidate, public, max-age=0"
  )
  response.headers["Pragma"] = "no-cache"
  response.headers["Expires"] = "0"
  return response


@app.route("/")
def index():
  return redirect(url_for("login"))


@app.route("/logout")
def logout():
  session.clear()
  return redirect(url_for("login"))


# --- واجهة تسجيل الدخول الجديدة بالاعتماد على قاعدة البيانات ---
@app.route("/login", methods=["GET", "POST"])
def login():
  error = None
  if request.method == "POST":
    username = request.form.get("username")
    password = request.form.get("password")

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password),
    ).fetchone()
    conn.close()

    if user:
      session["user_id"] = user["id"]
      session["username"] = user["username"]
      session["role"] = user["role"]
      session["center_id"] = user["center_id"]
      session["service_id"] = user["service_id"]

      if user["role"] == "system_admin":
        return redirect(url_for("system_dashboard"))
      elif user["role"] == "directorate":
        return redirect(url_for("dashboard_stats"))
      elif user["role"] == "center_admin":
        return redirect(
            url_for("kiosk_station", center_id=user["center_id"] or 1)
        )
      elif user["role"] == "employee":
        return redirect(url_for("employee_window"))
    else:
      error = "اسم المستخدم أو كلمة المرور غير صحيحة."

  return render_template_string(
      """
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
    """,
      error=error,
  )


# --- لوحة تحكم مسؤول النظام ---
@app.route('/system-dashboard', methods=['GET', 'POST'])
def system_dashboard():
    if session.get('role') != 'system_admin':
        return "غير مصرح لك بالوصول إلى لوحة تحكم المسؤول!", 403

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
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة تحكم المسؤول</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 40px; text-align: center; }
            h1 { color: #f59e0b; margin-bottom: 30px; }
            .menu-grid { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; max-width: 900px; margin: auto; }
            a { display: inline-block; padding: 20px 25px; background: #1e293b; border: 1px solid #334155; color: #38bdf8; text-decoration: none; border-radius: 15px; font-weight: bold; font-size: 16px; transition: 0.3s; box-shadow: 0 4px 15px rgba(0,0,0,0.3); width: 260px; box-sizing: border-box; }
            a:hover { background: #3b82f6; color: #fff; transform: translateY(-3px); }
            .logout { background: #7f1d1d; color: #f87171; border-color: #991b1b; }
            .logout:hover { background: #ef4444; color: #fff; }
        </style></head>
        <body>
        <h1>🛠️ لوحة تحكم مسؤول النظام المركزية</h1>
        <div class="menu-grid">
            <a href="/system/dashboard-stats">📊 إحصائيات وتقارير المديرية</a>
            <a href="/system/all-displays">🖥️ مراقبة الشاشات اللحظية</a>
            <a href="/kiosk/1" target="_blank">🎟️ جهاز سحب التذاكر (Kiosk)</a>
            <a href="/display/1" target="_blank">📺 شاشة عرض المركز الرئيسي</a>
            <a href="/logout" class="logout">تسجيل الخروج 🚪</a>
        </div>
        </body></html>
    ''')

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
@app.route("/kiosk/<int:center_id>")
def kiosk_station(center_id):
  conn = get_db_connection()
  center = conn.execute(
      "SELECT * FROM centers WHERE id = ?", (center_id,)
  ).fetchone()
  services = conn.execute(
      "SELECT * FROM services WHERE center_id = ?", (center_id,)
  ).fetchall()
  conn.close()
  if not center:
    return "المركز غير موجود", 404

  return render_template_string(
      """
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>سحب التذاكر - {{ center.center_name }}</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 30px; text-align: center; }
            .container { max-width: 700px; margin: auto; background: #1e293b; padding: 40px; border-radius: 20px; border: 1px solid #334155; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            h1 { color: #f59e0b; margin-bottom: 10px; font-size: 26px; }
            p { color: #94a3b8; margin-bottom: 30px; }
            .services-grid { display: grid; gap: 15px; margin-bottom: 25px; }
            .service-btn { background: #0f172a; border: 2px solid #3b82f6; color: #fff; padding: 20px; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; transition: 0.3s; text-align: right; display: flex; justify-content: space-between; align-items: center; }
            .service-btn:hover { background: #3b82f6; transform: translateY(-2px); }
            .priority-box { margin-top: 20px; background: rgba(245, 158, 11, 0.1); border: 1px dashed #f59e0b; padding: 15px; border-radius: 10px; text-align: right; }
            .ticket-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; }
            .ticket-card { background: #fff; color: #000; padding: 30px; border-radius: 15px; width: 320px; text-align: center; font-family: monospace; }
            .ticket-number { font-size: 55px; font-weight: bold; color: #2563eb; margin: 15px 0; }
            .print-btn { background: #10b981; color: #fff; border: none; padding: 12px 20px; font-size: 16px; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 15px; }
        </style></head>
        <body>
        <div class="container">
            <h1>🏢 {{ center.center_name }}</h1>
            <p>يرجى اختيار المصلحة المطلوبة لاستخراج تذكرة الانتظار:</p>
            <div class="services-grid">
                {% for s in services %}
                <button class="service-btn" onclick="generateTicket({{ s.id }})">
                    <span>📋 {{ s.service_name }}</span>
                    <span style="font-size: 14px; background: #3b82f6; padding: 5px 10px; border-radius: 6px;">اختر</span>
                </button>
                {% endfor %}
            </div>
            <div class="priority-box">
                <label style="cursor: pointer; color: #fbbf24; font-weight: bold; display: flex; align-items: center; gap: 10px;">
                    <input type="checkbox" id="priorityCheck" style="width: 20px; height: 20px;"> ذوو الاحتياجات الخاصة / حالات استعجالية
                </label>
            </div>
        </div>

        <div class="ticket-modal" id="ticketModal">
            <div class="ticket-card">
                <div style="font-weight: bold; font-size: 14px; color: #666;">مديرية الضرائب لولاية ميلة</div>
                <div id="modalServiceName" style="font-size: 13px; color: #333; margin-top: 5px;"></div>
                <hr style="border: 1px dashed #ccc; margin: 15px 0;">
                <div style="font-size: 12px; color: #666;">رقم التذكرة الخاصة بك</div>
                <div class="ticket-number" id="modalTicketNum">T-01</div>
                <div id="modalPriorityText" style="color: #d97706; font-weight: bold; font-size: 12px; margin-bottom: 10px;"></div>
                <div style="font-size: 11px; color: #888;" id="modalTime"></div>
                <button class="print-btn" onclick="closeModal()">تم / طباعة التذكرة 🖨️</button>
            </div>
        </div>

        <script>
            function generateTicket(serviceId) {
                let isPriority = document.getElementById('priorityCheck').checked ? 1 : 0;
                fetch('/api/generate-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({center_id: {{ center.id }}, service_id: serviceId, is_priority: isPriority})
                })
                .then(res => res.json())
                .then(data => {
                    if(data.success) {
                        document.getElementById('modalTicketNum').innerText = data.ticket_number;
                        document.getElementById('modalServiceName').innerText = data.service_name;
                        document.getElementById('modalPriorityText').innerText = isPriority ? '★ تذكرة أولوية (Priority) ★' : '';
                        document.getElementById('modalTime').innerText = new Date().toLocaleString();
                        document.getElementById('ticketModal').style.display = 'flex';
                        document.getElementById('priorityCheck').checked = false;
                    }
                });
            }
            function closeModal() {
                document.getElementById('ticketModal').style.display = 'none';
            }
        </script>
        </body></html>
    """,
      center=center,
      services=services,
  )


@app.route("/api/generate-ticket", methods=["POST"])
def api_generate_ticket():
  data = request.json
  center_id = data.get("center_id")
  service_id = data.get("service_id")
  is_priority = data.get("is_priority", 0)

  conn = get_db_connection()
  last_t = conn.execute(
      "SELECT COUNT(*) as cnt FROM queue_tokens WHERE service_id = ?",
      (service_id,),
  ).fetchone()
  next_num = last_t["cnt"] + 1
  ticket_number = f"T-{next_num:03d}"

  service = conn.execute(
      "SELECT service_name FROM services WHERE id = ?", (service_id,)
  ).fetchone()

  conn.execute(
      """
        INSERT INTO queue_tokens (center_id, service_id, ticket_number, is_priority, status)
        VALUES (?, ?, ?, ?, 'WAITING')
    """,
      (center_id, service_id, ticket_number, is_priority),
  )
  conn.commit()
  conn.close()

  return jsonify({
      "success": True,
      "ticket_number": ticket_number,
      "service_name": service["service_name"] if service else "مصلحة جبائية",
  })


# --- واجهة عون الاستقبال (Employee Window) ---
@app.route("/employee-window")
def employee_window():
  if session.get("role") != "employee":
    return "غير مصرح لك!", 403
  conn = get_db_connection()
  service = conn.execute(
      "SELECT * FROM services WHERE id = ?", (session.get("service_id", 1),)
  ).fetchone()
  center = conn.execute(
      "SELECT * FROM centers WHERE id = ?", (session.get("center_id", 1),)
  ).fetchone()
  conn.close()
  if not service or not center:
    return "بيانات المصلحة غير موجودة", 400

  return render_template_string(
      """
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>نافذة العون - {{ service.service_name }}</title>
        <script>
            window.addEventListener("pageshow", function (event) {
                if (event.persisted) { window.location.reload(); }
            });
        </script>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .container { width: 500px; background: #1e293b; padding: 35px; border-radius: 20px; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.5); border: 1px solid #334155; }
            h2 { color: #f59e0b; margin-top: 0; font-size: 20px; }
            .ticket-box { font-size: 60px; color: #38bdf8; font-weight: bold; margin: 20px 0; background: #0f172a; padding: 20px; border-radius: 15px; border: 2px solid #475569; letter-spacing: 2px; }
            button { width: 100%; padding: 15px; margin: 10px 0; font-size: 16px; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; color: #fff; transition: 0.2s; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            button:hover { opacity: 0.9; transform: translateY(-1px); }
            .alert-box { padding: 12px; border-radius: 8px; margin-bottom: 15px; font-weight: bold; font-size: 14px; display: none; }
        </style></head>
        <body><div class="container">
        <h2>🖥️ نافذة المصلحة: {{ service.service_name }}</h2>
        <div id="alertBox" class="alert-box"></div>
        <div style="font-size: 13px; color: #94a3b8;">رقم التذكرة الحالية قيد المعالجة</div>
        <div class="ticket-box" id="currentTicket">---</div>
        <button style="background: #10b981;" onclick="callNext()">📢 نداء التذكرة التالية</button>
        <button style="background: #f59e0b; color: #000;" onclick="recallCurrent()">🔊 إعادة النداء الصوتي</button>
        <button style="background: #3b82f6;" onclick="completeTicket()">✅ إنهاء التذكرة الحالية</button>
        <br><a href="/logout" style="color:#f87171; display:inline-block; margin-top:15px; font-weight:bold; text-decoration:none;">تسجيل الخروج 🚪</a>
        </div>
        <script>
            let lastTicket = "", chimeAudio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
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
    """,
      service=service,
      center=center,
  )


@app.route("/api/employee-status/<int:service_id>")
def api_employee_status(service_id):
  conn = get_db_connection()
  t = conn.execute(
      'SELECT ticket_number FROM queue_tokens WHERE service_id = ? AND status = "CALLED" ORDER BY called_at DESC LIMIT 1',
      (service_id,),
  ).fetchone()
  conn.close()
  return jsonify({"current_ticket": t["ticket_number"] if t else None})


@app.route("/api/call-next/<int:service_id>", methods=["POST"])
def api_call_next(service_id):
  conn = get_db_connection()
  next_t = conn.execute(
      """
        SELECT * FROM queue_tokens 
        WHERE service_id = ? AND status = "WAITING" 
        ORDER BY is_priority DESC, id ASC 
        LIMIT 1
    """,
      (service_id,),
  ).fetchone()

  if next_t:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        'UPDATE queue_tokens SET status = "CALLED", called_at = ? WHERE id = ?',
        (now, next_t["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})
  else:
    conn.close()
    return jsonify({"success": False})


@app.route("/api/complete-ticket/<int:service_id>", methods=["POST"])
def api_complete_ticket(service_id):
  conn = get_db_connection()
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  conn.execute(
      """
        UPDATE queue_tokens 
        SET status = "COMPLETED", completed_at = ? 
        WHERE service_id = ? AND status = "CALLED"
    """,
      (now, service_id),
  )
  conn.commit()
  conn.close()
  return jsonify({"success": True})


# --- شاشة العرض المباشر (Display Screen) ---
@app.route("/display/<int:center_id>")
def display_screen(center_id):
  conn = get_db_connection()
  center = conn.execute(
      "SELECT * FROM centers WHERE id = ?", (center_id,)
  ).fetchone()
  conn.close()
  if not center:
    return "المركز غير موجود", 404
  return render_template_string(
      """
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>شاشة العرض - {{ center.center_name }}</title>
        <style>
            body { background: #000; color: #fff; font-family: Tahoma; text-align: center; padding: 40px; margin: 0; }
            h1 { color: #f59e0b; font-size: 45px; margin-bottom: 10px; }
            .big-ticket { font-size: 130px; color: #10b981; font-weight: bold; background: #111; padding: 30px; border-radius: 25px; border: 4px solid #333; margin: 30px auto; width: 650px; box-shadow: 0 0 40px rgba(16,185,129,0.2); }
            .service { font-size: 40px; color: #38bdf8; margin-top: 20px; font-weight: bold; }
        </style></head>
        <body>
            <h1>🏢 {{ center.center_name }}</h1>
            <div class="service" id="serviceName">جاري الانتظار...</div>
            <div class="big-ticket" id="displayTicket">---</div>
        <script>
            let lastSpokenTicket = "";
            let chimeAudio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
            
            function formatTicketForSpeech(ticketStr) {
                if (!ticketStr || ticketStr === '---') return '';
                let matches = ticketStr.match(/\d+/);
                return matches ? `رقم ${parseInt(matches[0], 10)}` : ticketStr;
            }

            function speakDisplay(textMsg) {
                chimeAudio.play().then(() => {
                    setTimeout(() => {
                        if ('speechSynthesis' in window) {
                            window.speechSynthesis.cancel();
                            let utterance = new SpeechSynthesisUtterance(textMsg);
                            utterance.lang = 'ar-SA';
                            utterance.rate = 0.85;
                            window.speechSynthesis.speak(utterance);
                        }
                    }, 800);
                }).catch(e => {
                    if ('speechSynthesis' in window) {
                        let utterance = new SpeechSynthesisUtterance(textMsg);
                        utterance.lang = 'ar-SA';
                        utterance.rate = 0.85;
                        window.speechSynthesis.speak(utterance);
                    }
                });
            }

            function fetchCurrentTicket() {
                fetch('/api/display-data/{{ center.id }}')
                    .then(res => res.json())
                    .then(data => {
                        if(data.current) {
                            let curr = data.current.ticket_number;
                            let serv = data.current.service_name;
                            document.getElementById('displayTicket').innerText = curr;
                            document.getElementById('serviceName').innerText = serv;
                            
                            if(curr !== lastSpokenTicket) {
                                lastSpokenTicket = curr;
                                speakDisplay(`التذكرة ${formatTicketForSpeech(curr)}, إلى مصلحة, ${serv}`);
                            }
                        } else {
                            document.getElementById('displayTicket').innerText = '---';
                            document.getElementById('serviceName').innerText = 'بانتظار نداء التذكرة القادمة';
                        }
                    });
            }
            setInterval(fetchCurrentTicket, 2000);
            fetchCurrentTicket();
        </script></body></html>
    """,
      center=center,
  )


# --- مراقبة شاشات كل المراكز (System All Displays) ---
@app.route("/system/all-displays")
def system_all_displays():
  if session.get("role") != "system_admin":
    return "غير مصرح لك بالوصول!", 403
  conn = get_db_connection()
  centers = conn.execute("SELECT * FROM centers").fetchall()
  conn.close()
  return render_template_string(
      """
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>مراقبة شاشات كل المراكز</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 25px; margin: 0; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; background: #1e293b; padding: 15px 25px; border-radius: 12px; border: 1px solid #334155; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
            .center-card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            .center-title { font-size: 18px; font-weight: bold; color: #f59e0b; margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
            .current-box { background: #0f172a; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #475569; margin-bottom: 15px; }
            .ticket-num { font-size: 40px; color: #10b981; font-weight: bold; margin: 8px 0; }
            .service-name { font-size: 14px; color: #38bdf8; }
            .btn { padding: 6px 12px; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 12px; font-weight: bold; }
            .back-link { color: #f87171; text-decoration: none; font-weight: bold; }
        </style></head>
        <body>
        <div class="header">
            <h2>🖥️ مراقبة شاشات العرض المباشرة لجميع المراكز</h2>
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
    """,
      centers=centers,
  )


@app.route("/api/display-data/<int:center_id>")
def api_display_data(center_id):
  conn = get_db_connection()
  t = conn.execute(
      """
        SELECT t.ticket_number, s.service_name FROM queue_tokens t
        JOIN services s ON t.service_id = s.id
        WHERE t.center_id = ? AND t.status = 'CALLED'
        ORDER BY t.called_at DESC LIMIT 1
    """,
      (center_id,),
  ).fetchone()
  conn.close()
  return jsonify(
      {
          "current": {
              "ticket_number": t["ticket_number"],
              "service_name": t["service_name"],
          }
          if t
          else None
      }
  )


# --- لوحة إحصائيات وتقارير المديرية ---
@app.route("/system/dashboard-stats", methods=["GET", "POST"])
def dashboard_stats():
  if session.get("role") not in ["system_admin", "directorate"]:
    return "غير مصرح لك بالوصول!", 403

  start_date = request.args.get("start_date", "")
  end_date = request.args.get("end_date", "")

  conn = get_db_connection()
  query = """
        SELECT c.center_name, 
               COUNT(t.id) as total_tickets,
               SUM(CASE WHEN t.status = 'COMPLETED' OR t.status = 'CALLED' THEN 1 ELSE 0 END) as served_tickets,
               SUM(CASE WHEN t.status = 'WAITING' THEN 1 ELSE 0 END) as waiting_tickets
        FROM centers c
        LEFT JOIN services s ON c.id = s.center_id
        LEFT JOIN queue_tokens t ON s.id = t.service_id
    """
  params = []
  if start_date and end_date:
    query += " WHERE DATE(t.created_at) BETWEEN ? AND ?"
    params.extend([start_date, end_date])

  query += " GROUP BY c.id, c.center_name"
  stats = conn.execute(query, params).fetchall()
  conn.close()

  return render_template_string(
      """
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة إحصائيات وتقارير المديرية</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 30px; margin: 0; }
            .container { max-width: 1000px; margin: auto; background: #1e293b; padding: 30px; border-radius: 20px; border: 1px solid #334155; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            h1 { color: #f59e0b; text-align: center; margin-bottom: 25px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #0f172a; border-radius: 10px; overflow: hidden; }
            th, td { padding: 15px; text-align: center; border-bottom: 1px solid #334155; }
            th { background: #334155; color: #38bdf8; }
            tr:hover { background: rgba(59,130,246,0.1); }
            .back-btn { display: inline-block; margin-bottom: 20px; padding: 10px 20px; background: #3b82f6; color: #fff; text-decoration: none; border-radius: 8px; font-weight: bold; }
        </style></head>
        <body>
        <div class="container">
            <a href="/system-dashboard" class="back-btn">⬅ العودة لوحة التحكم</a>
            <h1>📊 إحصائيات مراكز الضرائب</h1>
            <table>
                <tr>
                    <th>اسم المركز</th>
                    <th>إجمالي التذاكر</th>
                    <th>المعروضة / المنجزة</th>
                    <th>في الانتظار</th>
                </tr>
                {% for row in stats %}
                <tr>
                    <td>{{ row.center_name }}</td>
                    <td>{{ row.total_tickets }}</td>
                    <td style="color: #34d399;">{{ row.served_tickets }}</td>
                    <td style="color: #fbbf24;">{{ row.waiting_tickets }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        </body></html>
    """,
      stats=stats,
  )


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port, debug=False)
