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
    # إضافة جداول الفيديوهات والإعلانات لتجنب أخطاء 500 في لوحة التحكم
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            is_active INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            is_active INTEGER DEFAULT 0
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


# --- واجهة تسجيل الدخول ---
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

@app.route('/system/dashboard-stats', methods=['GET', 'POST'])
def dashboard_stats():
    # السماح لمسؤول النظام أو المديرية بالدخول
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
        <!-- مكتبة الرسوم البيانية Chart.js -->
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
    center = conn.execute("SELECT * FROM centers WHERE id = ?", (center_id,)).fetchone()
    services = conn.execute("SELECT * FROM services WHERE center_id = ?", (center_id,)).fetchall()
    conn.close()
    if not center:
        return "المركز غير موجود", 404

    return render_template_string("""
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>سحب التذاكر - {{ center.center_name }}</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 30px; text-align: center; }
            .container { max-width: 700px; margin: auto; background: #1e293b; padding: 40px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
            h1 { color: #f59e0b; margin-bottom: 25px; }
            .service-btn { display: block; width: 100%; padding: 20px; margin: 15px 0; background: #2563eb; color: #fff; font-size: 20px; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; transition: 0.2s; text-decoration: none; }
            .service-btn:hover { background: #1d4ed8; transform: translateY(-2px); }
        </style></head>
        <body>
        <div class="container">
            <h1>🎫 جهاز سحب التذاكر</h1>
            <h3 style="color: #38bdf8; margin-bottom: 30px;">{{ center.center_name }}</h3>
            <p>اختر المصلحة المطلوبة لسحب تذكرة:</p>
            {% for s in services %}
            <a href="/api/issue-ticket/{{ center.id }}/{{ s.id }}" class="service-btn">{{ s.service_name }}</a>
            {% endfor %}
        </div>
        </body></html>
    """, center=center, services=services)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
