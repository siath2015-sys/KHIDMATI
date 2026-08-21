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
    conn = sqlite3.connect('tax-queue-db.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS centers (id INTEGER PRIMARY KEY AUTOINCREMENT, center_name TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_name TEXT NOT NULL, FOREIGN KEY (center_id) REFERENCES centers (id))')
    conn.execute('CREATE TABLE IF NOT EXISTS queue_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_id INTEGER, ticket_number TEXT NOT NULL, status TEXT DEFAULT "WAITING", is_priority INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, called_at TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, is_active INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, is_active INTEGER DEFAULT 0)')
    
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
    
    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', 'admin123', 'system_admin'))
        conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('directorate', 'dir123', 'directorate'))
        
        conn.execute('INSERT OR IGNORE INTO centers (id, center_name) VALUES (1, ?)', ('المركز الجواري للضرائب - ميلة',))
        conn.execute('INSERT OR IGNORE INTO services (id, center_id, service_name) VALUES (1, 1, ?)', ('مصلحة الاستقبال والتسجيل',))
        
        conn.execute('INSERT OR IGNORE INTO users (username, password, role, center_id) VALUES (?, ?, ?, ?)', ('manager_mila', 'man123', 'center_admin', 1))
        conn.execute('INSERT OR IGNORE INTO users (username, password, role, center_id, service_id) VALUES (?, ?, ?, ?, ?)', ('agent1', 'agent123', 'employee', 1, 1))
        
        conn.commit()
    conn.close()

init_db()

# ==========================================
# 0. الصفحة الرئيسية (شاشة الدخول)
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
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>الدخول إلى نظام التذاكر</title>
        <style>
            body { background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); color: #1e293b; font-family: Tahoma; display: flex; flex-direction: column; justify-content: space-between; align-items: center; height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
            .login-container { display: flex; flex-direction: column; align-items: center; justify-content: center; flex-grow: 1; width: 100%; }
            .card { background: #ffffff; padding: 35px; border-radius: 15px; width: 100%; max-width: 420px; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.3); border: 1px solid #e2e8f0; }
            input { width: 92%; padding: 14px; margin: 10px 0; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; color: #0f172a; font-size: 15px; box-sizing: border-box; }
            button { width: 92%; padding: 14px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; margin-top: 10px; }
            button:hover { background: #1d4ed8; }
            .footer-signature { text-align: center; color: #cbd5e1; font-size: 13px; line-height: 1.6; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); width: 100%; max-width: 600px; }
        </style></head>
        <body>
        <div></div>
        <div class="login-container">
            <div class="card">
                <h3 style="margin-top: 5px; margin-bottom: 20px; color: #1e293b; font-size: 20px;">الدخول إلى نظام التذاكر</h3>
                {% if error %}<div style="color:#ef4444; background:rgba(239,68,68,0.1); padding:10px; border-radius:6px; margin-bottom:15px; font-weight:bold; font-size: 14px;">{{ error }}</div>{% endif %}
                <form method="POST">
                    <input type="text" name="username" placeholder="اسم المستخدم" required autocomplete="off"><br>
                    <input type="password" name="password" placeholder="كلمة المرور" required><br>
                    <button type="submit">تسجيل الدخول</button>
                </form>
                <div style="margin-top: 15px;">
                    <a href="/centers" style="color: #64748b; font-size: 13px; text-decoration: none;">الانتقال إلى واجهة المراكز (عرض وشاشات الكيوسك)</a>
                </div>
            </div>
        </div>
        <div class="footer-signature">
            من إنجاز: <b>عتامنة الطاهر</b> - تقني سامي إعلام آلي<br>المديرية الولائية للضرائب ميلة
        </div>
        </body></html>
    ''', error=error)

@app.route('/centers')
def centers_page():
    conn = get_db_connection()
    centers = conn.execute('SELECT * FROM centers').fetchall()
    conn.close()
    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>منظومة إدارة الطوابير</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e293b; padding: 40px; border-radius: 20px; text-align: center; width: 450px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .btn { display: block; background: #3b82f6; color: #fff; padding: 12px; margin: 10px 0; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .btn-green { background: #10b981; }
        </style></head>
        <body>
        <div class="box">
            <h2>🏢 مراكز الخدمات المتاحة</h2>
            {% for c in centers %}
                <div style="background: #334155; padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: right;">
                    <div style="font-weight: bold; font-size: 16px; margin-bottom: 10px;">{{ c.center_name }}</div>
                    <a class="btn" href="/display/{{ c.id }}">📺 شاشة العرض العامة</a>
                    <a class="btn btn-green" href="/kiosk/{{ c.id }}">🎫 جهاز سحب التذاكر (Kiosk)</a>
                </div>
            {% endfor %}
            <a href="/" style="color: #cbd5e1; font-size: 13px; display: inline-block; margin-top: 15px;">العودة لصفحة تسجيل الدخول</a>
        </div>
        </body></html>
    ''', centers=centers)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ==========================================
# 1. لوحة تحكم المسؤول الشاملة (System Dashboard)
# ==========================================
@app.route('/system-dashboard', methods=['GET', 'POST'])
def system_dashboard():
    if session.get('role') != 'system_admin':
        return "غير مصرح لك بالوصول إلى لوحة تحكم المسؤول!", 403

    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action')
        try:
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
                c_id = request.form.get('center_id') or None
                s_id = request.form.get('service_id') or None
                if uname and pwd and role:
                    conn.execute('INSERT INTO users (username, password, role, center_id, service_id) VALUES (?, ?, ?, ?, ?)', (uname, pwd, role, c_id, s_id)); conn.commit()
            elif action == 'delete_user':
                conn.execute('DELETE FROM users WHERE id = ? AND role != "system_admin"', (request.form.get('user_id'),)); conn.commit()

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
        except Exception as e:
            print(f"Error: {e}")

    centers = conn.execute('SELECT * FROM centers').fetchall()
    services = conn.execute('SELECT s.*, c.center_name FROM services s JOIN centers c ON s.center_id = c.id').fetchall()
    users = conn.execute('SELECT u.*, c.center_name, s.service_name FROM users u LEFT JOIN centers c ON u.center_id = c.id LEFT JOIN services s ON u.service_id = s.id').fetchall()
    videos = conn.execute('SELECT * FROM videos').fetchall()
    announcements = conn.execute('SELECT * FROM announcements').fetchall()
    conn.close()

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم الشاملة</title>
        <script>
            function confirmResetTickets(centerId, centerName) {
                if (confirm('هل أنت متأكد من رغبة في تصفير وإعادة ضبط طابور المركز: ' + centerName + '؟')) {
                    fetch('/api/reset-tickets/' + centerId, { method: 'POST', headers: {'Content-Type': 'application/json'} })
                    .then(res => res.json()).then(data => { alert(data.message); location.reload(); });
                }
            }
        </script>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; }
            .container { max-width: 1200px; margin: auto; }
            .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .logout-btn { background: #ef4444; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .card { background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
            input, select { padding: 10px; margin: 8px; background: #0f172a; color: #fff; border: 1px solid #475569; border-radius: 8px; box-sizing: border-box; font-size: 14px; }
            button { padding: 10px 15px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; background: #0f172a; }
            th, td { padding: 10px; text-align: center; border-bottom: 1px solid #334155; font-size: 13px; } th { color: #f59e0b; }
            .btn-dash { display: inline-block; background: #10b981; color: #fff; padding: 10px 15px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-left: 10px; }
        </style></head>
        <body><div class="container">
        <div class="top-bar">
            <h2>🛠️ لوحة تحكم مسؤول النظام</h2>
            <a href="/logout" class="logout-btn">تسجيل الخروج 🚪</a>
        </div>

        <div class="card">
            <a href="/directorate-dashboard" class="btn-dash" style="background: #3b82f6;">📊 لوحة إحصائيات المديرية</a>
        </div>

        <div class="card">
            <h3>📢 إدارة الشريط الإعلاني المتحرك</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add_announcement">
                <input type="text" name="content" placeholder="نص الإعلان الجديد..." required style="width: 70%;">
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
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="set_active_announcement"><input type="hidden" name="announcement_id" value="{{ a.id }}"><button type="submit" style="background:#f59e0b; padding:5px 10px;">تفعيل</button></form>
                        {% endif %}
                    </td>
                    <td>
                        <form method="POST" style="display:inline;" onsubmit="return confirm('هل أنت متأكد من الحذف؟');"><input type="hidden" name="action" value="delete_announcement"><input type="hidden" name="announcement_id" value="{{ a.id }}"><button type="submit" style="background:#ef4444; padding:5px 10px;">حذف</button></form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>🎬 إدارة الفيديوهات الترويجية</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add_video">
                <input type="text" name="title" placeholder="عنوان الفيديو" required style="width: 30%;">
                <input type="text" name="url" placeholder="رابط اليوتيوب" required style="width: 45%;">
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
                        <form method="POST" style="display:inline;"><input type="hidden" name="action" value="set_active_video"><input type="hidden" name="video_id" value="{{ v.id }}"><button type="submit" style="background:#f59e0b; padding:5px 10px;">تفعيل</button></form>
                        {% endif %}
                    </td>
                    <td>
                        <form method="POST" style="display:inline;" onsubmit="return confirm('هل أنت متأكد من الحذف؟');"><input type="hidden" name="action" value="delete_video"><input type="hidden" name="video_id" value="{{ v.id }}"><button type="submit" style="background:#ef4444; padding:5px 10px;">حذف</button></form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>🏢 إدارة المراكز</h3>
            <form method="POST" style="margin-bottom:15px;">
                <input type="hidden" name="action" value="add_center">
                <input type="text" name="center_name" placeholder="اسم المركز الجديد" required style="width: 40%;">
                <button type="submit" style="background:#10b981;">إضافة المركز</button>
            </form>
            <table>
                <tr><th>معرف</th><th>اسم المركز</th><th>تعديل الاسم</th><th>إعادة ضبط الطابور</th><th>حذف</th></tr>
                {% for c in centers %}
                <tr>
                    <td>{{ c.id }}</td>
                    <td>
                        <form method="POST" style="display:inline;">
                            <input type="hidden" name="action" value="edit_center">
                            <input type="hidden" name="center_id" value="{{ c.id }}">
                            <input type="text" name="center_name" value="{{ c.center_name }}" style="width: 55%; padding: 6px;">
                            <button type="submit" style="background:#3b82f6; padding: 6px 10px;">حفظ</button>
                        </form>
                    </td>
                    <td><button type="button" onclick="confirmResetTickets({{ c.id }}, '{{ c.center_name }}')" style="background:#d97706; padding:6px 10px;">⚠️ تصفير</button></td>
                    <td>
                        <form method="POST" style="display:inline;" onsubmit="return confirm('هل أنت متأكد من حذف المركز؟');"><input type="hidden" name="action" value="delete_center"><input type="hidden" name="center_id" value="{{ c.id }}"><button type="submit" style="background:#ef4444; padding:6px 10px;">حذف</button></form>
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
                <tr><th>المصلحة</th><th>المركز التابع له</th><th>إجراء</th></tr>
                {% for s in services %}
                <tr>
                    <td>
                        <form method="POST" style="display:inline;">
                            <input type="hidden" name="action" value="edit_service">
                            <input type="hidden" name="service_id" value="{{ s.id }}">
                            <input type="text" name="service_name" value="{{ s.service_name }}" style="width: 55%; padding: 6px;">
                            <button type="submit" style="background:#3b82f6; padding: 6px 10px;">حفظ</button>
                        </form>
                    </td>
                    <td>{{ s.center_name }}</td>
                    <td>
                        <form method="POST" style="display:inline;" onsubmit="return confirm('هل أنت متأكد من الحذف؟');"><input type="hidden" name="action" value="delete_service"><input type="hidden" name="service_id" value="{{ s.id }}"><button type="submit" style="background:#ef4444; padding:6px 10px;">حذف</button></form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>👥 إدارة المستخدمين والصلاحيات</h3>
            <form method="POST" style="margin-bottom:15px;">
                <input type="hidden" name="action" value="add_user">
                <input type="text" name="username" placeholder="اسم المستخدم" required style="width: 20%;">
                <input type="password" name="password" placeholder="كلمة المرور" required style="width: 20%;">
                <select name="role" required style="width: 18%;"><option value="employee">عون نداء</option><option value="center_admin">مسؤول مركز</option><option value="directorate">مديرية عامة</option></select>
                <select name="center_id" style="width: 20%;"><option value="">المركز (اختياري)</option>{% for c in centers %}<option value="{{ c.id }}">{{ c.center_name }}</option>{% endfor %}</select>
                <button type="submit" style="background:#10b981; margin-top: 5px;">إضافة مستخدم</button>
            </form>
            <table>
                <tr><th>اسم المستخدم</th><th>الدور</th><th>المركز</th><th>إجراء</th></tr>
                {% for u in users %}
                <tr>
                    <td>{{ u.username }}</td>
                    <td>{{ u.role }}</td>
                    <td>{{ u.center_name or '-' }}</td>
                    <td>
                        {% if u.role != 'system_admin' %}
                        <form method="POST" style="display:inline;" onsubmit="return confirm('هل أنت متأكد من حذف المستخدم؟');"><input type="hidden" name="action" value="delete_user"><input type="hidden" name="user_id" value="{{ u.id }}"><button type="submit" style="background:#ef4444; padding:5px 10px;">حذف</button></form>
                        {% else %}
                        <span style="color:#64748b;">محمي</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div></div></body></html>
    ''', centers=centers, services=services, users=users, videos=videos, announcements=announcements)

# بقية المسارات الإضافية (الإحصائيات والشاشات)
@app.route('/directorate-dashboard')
def directorate_dashboard():
    if session.get('role') not in ['system_admin', 'directorate']:
        return "غير مصرح لك بالوصول!", 403
    return redirect(url_for('system_dashboard'))

@app.route('/api/reset-tickets/<int:center_id>', methods=['POST'])
def reset_tickets(center_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM queue_tokens WHERE center_id = ?', (center_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'تم تصفير طابور المركز بنجاح.'})

@app.route('/display/<int:center_id>')
def display_screen(center_id):
    conn = get_db_connection()
    center = conn.execute('SELECT * FROM centers WHERE id = ?', (center_id,)).fetchone()
    conn.close()
    return f"شاشة العرض للمركز: {center['center_name'] if center else ''}"

@app.route('/kiosk/<int:center_id>')
def kiosk_machine(center_id):
    return redirect(url_for('centers_page'))

@app.route('/employee-window')
def employee_window():
    return redirect(url_for('home'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
