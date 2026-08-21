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

app = Flask(__name__)
app.secret_key = (
    "your_secret_key_here"  # استبدل هذا بمفتاح سري آمن في البيئة الحقيقية
)


def get_db_connection():
  conn = sqlite3.connect("database.db")
  conn.row_factory = sqlite3.Row
  return conn


# دالة تهيئة قاعدة البيانات الأساسية عند بدء التشغيل
def init_db():
  conn = get_db_connection()
  # جدول المراكز
  conn.execute("""
        CREATE TABLE IF NOT EXISTS centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_name TEXT NOT NULL
        )
    """)
  # جدول المصالح / الخدمات
  conn.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_id INTEGER,
            service_name TEXT NOT NULL,
            FOREIGN KEY (center_id) REFERENCES centers (id)
        )
    """)
  # جدول تذاكر الطابور
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
  conn.close()


# صفحة تسجيل الدخول (مثلية مبسطة لتوجيه الأدوار)
@app.route("/login", methods=["GET", "POST"])
def login():
  if request.method == "POST":
    role = request.form.get("role")
    session["role"] = role
    if role == "system_admin":
      return redirect(url_for("system_dashboard"))
    elif role == "employee":
      session["service_id"] = 1  .get(
          "service_id", 1
      )  # افتراضي للتجربة
      session["center_id"] = 1
      return redirect(url_for("employee_window"))
    elif role == "directorate":
      return redirect(url_for("dashboard_stats"))
  return render_template_string("""
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تسجيل الدخول</title>
        <style>body{background:#0f172a;color:#fff;font-family:Tahoma;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
        .box{background:#1e293b;padding:30px;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.5);width:320px;text-align:center;}
        select,button{width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;font-size:14px;}
        button{background:#3b82f6;color:#fff;font-weight:bold;cursor:pointer;}</style></head>
        <body><div class="box"><h2>تسجيل الدخول للنظام</h2>
        <form method="POST">
            <select name="role">
                <option value="system_admin">مسؤول النظام (System Admin)</option>
                <option value="employee">عون مصلحة (Employee)</option>
                <option value="directorate">مديرية (Directorate)</option>
            </select>
            <button type="submit">دخول</button>
        </form></div></body></html>
    """)


@app.route("/")
def index():
  return redirect(url_for("login"))


@app.route("/logout")
def logout():
  session.clear()
  return redirect(url_for("login"))


@app.route("/system-dashboard")
def system_dashboard():
  if session.get("role") != "system_admin":
    return "غير مصرح لك بالوصول!", 403
  return render_template_string("""
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة تحكم النظام</title>
        <style>body{background:#0f172a;color:#fff;font-family:Tahoma;padding:30px;text-align:center;}
        a{display:inline-block;padding:12px 20px;margin:10px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold;}
        .logout{background:#ef4444;}</style></head>
        <body>
        <h1>لوحة تحكم مسؤول النظام</h1>
        <div>
            <a href="/system/dashboard-stats">📊 إحصائيات المديرية</a>
            <a href="/system/all-displays">🖥 مراقبة جميع الشاشات</a>
            <a href="/logout" class="logout">تسجيل الخروج 🚪</a>
        </div>
        </body></html>
    """)


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
    return (
        "لم يتم العثور على بيانات المصلحة أو المركز المرتبط بالجلسة.",
        400,
    )

  return render_template_string(
      """
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
      'SELECT ticket_number FROM queue_tokens WHERE service_id = ? AND status ='
      ' "CALLED" ORDER BY called_at DESC LIMIT 1',
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

  centers_names = [row["center_name"] for row in stats]
  total_counts = [row["total_tickets"] for row in stats]
  served_counts = [row["served_tickets"] for row in stats]

  return render_template_string(
      """
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
            <h2>📊 لوحة القيادة وإحصائيات المراكز</h2>
            <div>
                {% if session.get('role') == 'system_admin' %}
                    <a href="/system-dashboard" class="back-btn">⬅️ العودة للوحة التحكم</a>
                {% else %}
                    <a href="/logout" class="logout-btn">تسجيل الخروج 🚪</a>
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
                data: { labels: centers, datasets: [{ data: totals, backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'] }] },
                options: { responsive: true, plugins: { legend: { labels: { color: '#fff' } } } }
            });
        </script></div></body></html>
    """,
      stats=stats,
      start_date=start_date,
      end_date=end_date,
      centers_names=centers_names,
      total_counts=total_counts,
      served_counts=served_counts,
  )


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
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; margin: 0; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background: #1e293b; padding: 15px 20px; border-radius: 10px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
            .center-card { background: #1e293b; border-radius: 12px; padding: 15px; border: 1px solid #334155; }
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
    """,
      centers=centers,
  )


# مسار جلب بيانات الشاشة لكل مركز
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
      {"current": {"ticket_number": t["ticket_number"], "service_name": t["service_name"]} if t else None}
  )


# صفحة الشاشة الكاملة للمركز الواحد
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
        <style>body{background:#000;color:#fff;font-family:Tahoma;text-align:center;padding:50px;}
        h1{color:#f59e0b;font-size:40px;}
        .big-ticket{font-size:120px;color:#10b981;font-weight:bold;background:#111;padding:30px;border-radius:20px;border:4px solid #333;margin:30px auto;width:600px;}
        .service{font-size:35px;color:#38bdf8;}</style></head>
        <body>
            <h1>🏢 {{ center.center_name }}</h1>
            <div class="service" id="serviceName">جاري الانتظار...</div>
            <div class="big-ticket" id="displayTicket">---</div>
        <script>
            let lastTicket = "";
            function fetchCurrentTicket() {
                fetch('/api/display-data/{{ center.id }}')
                    .then(res => res.json())
                    .then(data => {
                        if(data.current) {
                            document.getElementById('displayTicket').innerText = data.current.ticket_number;
                            document.getElementById('serviceName').innerText = data.current.service_name;
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


@app.route("/api/reset-tickets/<int:center_id>", methods=["POST"])
def reset_tickets(center_id):
  data = request.get_json(silent=True) or {}
  reset_type = data.get("type", "daily")

  conn = get_db_connection()
  try:
    if reset_type == "full":
      conn.execute("DELETE FROM queue_tokens WHERE center_id = ?", (center_id,))
      message = "تم تنفيذ التصفير الكلي لجميع تذاكر المركز بنجاح."
    else:
      today_str = datetime.now().strftime("%Y-%m-%d")
      conn.execute(
          """
                DELETE FROM queue_tokens 
                WHERE center_id = ? 
                AND DATE(created_at) = ?
            """,
          (center_id, today_str),
      )
      message = f"تم تصفير طابور اليوم ({today_str}) للمركز بنجاح."

    conn.commit()
    success = True
  except Exception as e:
    conn.rollback()
    success = False
    message = f"حدث خطأ أثناء عملية التصفير: {str(e)}"
  finally:
    conn.close()

  return jsonify({"success": success, "message": message})


if __name__ == "__main__":
  init_db()  # إنشاء الجداول تلقائياً عند التشغيل لأول مرة
  app.run(host="0.0.0.0", port=5000, debug=True)
