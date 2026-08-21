from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_it'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# دالة لإنشاء الجداول وإدخال بيانات تجريبية إذا لم تكن موجودة
def init_db():
    conn = get_db_connection()
    # جدول المراكز
    conn.execute('''
        CREATE TABLE IF NOT EXISTS centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_name TEXT NOT NULL
        )
    ''')
    # جدول المصالح
    conn.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_id INTEGER,
            service_name TEXT NOT NULL,
            FOREIGN KEY (center_id) REFERENCES centers (id)
        )
    ''')
    # جدول التذاكر
    conn.execute('''
        CREATE TABLE IF NOT EXISTS queue_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            center_id INTEGER,
            service_id INTEGER,
            ticket_number TEXT NOT NULL,
            status TEXT DEFAULT 'WAITING',
            is_priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            called_at TIMESTAMP
        )
    ''')
    # جدول الفيديوهات
    conn.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL
        )
    ''')
    # جدول التنبيهات المتحركة
    conn.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # التحقق من وجود مركز تجريبي على الأقل لضمان عدم ظهور خطأ فارغ
    center_count = conn.execute('SELECT COUNT(*) FROM centers').fetchone()[0]
    if center_count == 0:
        conn.execute('INSERT INTO centers (center_name) VALUES (?)', ('المركز الجواري للضرائب - ميلة',))
        conn.commit()
        # إضافة مصلحة افتراضية
        center_id = conn.execute('SELECT id FROM centers LIMIT 1').fetchone()[0]
        conn.execute('INSERT INTO services (center_id, service_name) VALUES (?, ?)', (center_id, 'مصلحة الاستقبال والتسجيل'))
        conn.commit()
        
    conn.close()

# تشغيل دالة التهيئة عند بدء تشغيل التطبيق
init_db()

# ==========================================
# 0. المسار الجذري (الصفحة الرئيسية)
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
            <a href="/employee-window" style="color: #cbd5e1; font-size: 13px; display: inline-block; margin-top: 15px; text-decoration: underline;">تسجيل دخول الموظفين / الأعوان</a>
        </div>
        </body></html>
    ''', centers=centers)

# ==========================================
# 1. مسار تسجيل الخروج
# ==========================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ==========================================
# 2. شاشة العرض العامة (Display Screen)
# ==========================================
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
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body { background: linear-gradient(135deg, #0284c7 0%, #0891b2 50%, #0d9488 100%); color: #fff; font-family: 'Segoe UI', Tahoma; margin: 0; padding: 10px; height: 100vh; display: flex; flex-direction: column; box-sizing: border-box; overflow: hidden; }
            .official-header { background: #ffffff; color: #0f172a; border-bottom: 3px solid #cbd5e1; padding: 8px 20px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.15); }
            .center-badge { color: #0284c7; font-size: 20px; font-weight: bold; }
            .header-left { display: flex; align-items: center; gap: 15px; }
            .datetime-box { background: #f8fafc; border: 1px solid #cbd5e1; padding: 5px 15px; border-radius: 8px; text-align: center; }
            .current-time { font-size: 16px; font-weight: bold; color: #0f172a; font-family: monospace; }
            .current-date { font-size: 11px; color: #64748b; }
            .main-content { display: flex; gap: 15px; flex-grow: 1; margin-top: 10px; height: calc(100vh - 115px); }
            .right-panel { flex: 1; display: flex; flex-direction: column; gap: 10px; }
            .current-box { background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(10px); border-radius: 12px; padding: 10px; text-align: center; border: 2px solid rgba(255, 255, 255, 0.3); display: flex; flex-direction: column; align-items: center; justify-content: center; }
            .current-ticket { font-size: 80px; font-weight: 900; color: #fff; text-shadow: 0 0 30px rgba(255,255,255,0.6); margin: 0; line-height: 1; }
            .current-service { font-size: 18px; color: #fbbf24; font-weight: bold; margin-top: 5px; margin-bottom: 8px; }
            .qr-direct-container { display: flex; align-items: center; justify-content: center; gap: 12px; background: rgba(255, 255, 255, 0.9); padding: 6px 15px; border-radius: 10px; width: fit-content; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
            .qr-text-side { text-align: right; }
            .qr-title-main { font-size: 13px; font-weight: 800; color: #0f172a; margin-bottom: 2px; }
            .qr-sub-text { font-size: 11px; color: #475569; font-weight: 600; }
            .pulse { animation: pulse-animation 1.5s infinite; }
            @keyframes pulse-animation { 0% { transform: scale(1); } 50% { transform: scale(1.04); } 100% { transform: scale(1); } }
            .history-box { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 12px; padding: 10px; border: 2px solid rgba(255, 255, 255, 0.2); flex-grow: 1; display: flex; flex-direction: column; }
            .history-title { font-size: 14px; color: #fff; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px; margin-bottom: 6px; text-align: center; font-weight: bold; }
            .history-item { background: rgba(0, 0, 0, 0.25); color: #fff; padding: 6px 10px; border-radius: 6px; margin-bottom: 5px; display: flex; justify-content: space-between; font-size: 13px; border-right: 4px solid #fbbf24; }
            .video-section { flex: 2; display: flex; flex-direction: column; background: #000; border-radius: 12px; overflow: hidden; border: 3px solid rgba(255, 255, 255, 0.3); }
            .video-container { flex-grow: 1; width: 100%; display: flex; align-items: center; justify-content: center; position: relative; }
            .video-controls { background: #1e293b; padding: 8px 15px; display: flex; gap: 10px; justify-content: center; align-items: center; border-top: 1px solid #334155; }
            .video-controls button { background: #0284c7; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: bold; }
            .ticker-wrap { background: #ffffff; color: #dc2626; padding: 8px 15px; border-radius: 8px; margin-top: 8px; overflow: hidden; white-space: nowrap; font-size: 18px; border: 2px solid #cbd5e1; font-weight: bold; }
            .ticker { display: inline-block; padding-left: 100%; animation: ticker 28s linear infinite; }
            @keyframes ticker { 0% { transform: translate(0, 0); } 100% { transform: translate(-100%, 0); } }
        </style></head>
        <body>
        <header class="official-header">
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
                <div class="video-container" id="videoBox"><p style="color:#94a3b8;">جاري تحميل المشغل...</p></div>
                <div class="video-controls">
                    <button onclick="togglePlayPause()">⏸ إيقاف / تشغيل</button>
                    <button onclick="toggleMuteUnmute()">🔇 كتم / إفلات الصوت</button>
                </div>
            </div>
        </div>
        <div class="ticker-wrap"><div class="ticker" id="announcementTicker">مرحباً بكم في المركز الجواري للضرائب</div></div>
        <script>
            window.onload = function() {
                let trackUrl = window.location.origin + "/kiosk/{{ center.id }}";
                new QRCode(document.getElementById("qrcode"), { text: trackUrl, width: 75, height: 75, colorDark: "#0f172a", colorLight: "#ffffff" });
            };
            function updateClock() {
                const now = new Date();
                document.getElementById('liveTime').innerText = now.toLocaleTimeString('ar-DZ');
                document.getElementById('liveDate').innerText = now.toLocaleDateString('ar-DZ', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
            }
            setInterval(updateClock, 1000); updateClock();

            let lastSpokenTicket = "";
            let chimeAudio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');

            function fetchDisplayData() {
                fetch('/api/display-data/{{ center.id }}').then(res => res.json()).then(data => {
                    if (data.current) {
                        let tNum = data.current.ticket_number, sName = data.current.service_name;
                        document.getElementById('currTicket').innerText = tNum;
                        document.getElementById('currService').innerText = sName;
                        let uniqueKey = tNum + '-' + data.current.called_at;
                        if (lastSpokenTicket !== uniqueKey) { 
                            lastSpokenTicket = uniqueKey; 
                            chimeAudio.play().catch(e => {});
                        }
                    } else {
                        document.getElementById('currTicket').innerText = '---';
                        document.getElementById('currService').innerText = 'لا توجد تذكرة حالية';
                    }
                    let historyList = document.getElementById('historyList'); historyList.innerHTML = '';
                    if (data.history) {
                        data.history.forEach(h => {
                            let item = document.createElement('div'); item.className = 'history-item';
                            item.innerHTML = `<span><b>${h.ticket_number}</b> (${h.service_name})</span> <span style="color:#4ade80; font-weight:bold;">منجز</span>`;
                            historyList.appendChild(item);
                        });
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
    conn.close()
    return jsonify({
        'current': dict(current) if current else None,
        'history': [dict(h) for h in history]
    })

# ==========================================
# 3. جهاز سحب التذاكر (Kiosk)
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
            body { background: #0f172a; color: #fff; font-family: Tahoma; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; direction: rtl; }
            .box { background: #1e293b; padding: 40px; border-radius: 20px; text-align: center; width: 420px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .priority-box { background: rgba(245, 158, 11, 0.15); border: 2px dashed #f59e0b; padding: 12px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; gap: 10px; cursor: pointer; }
            .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; }
            .ticket-card { background: #fff; color: #000; padding: 25px; border-radius: 14px; width: 340px; text-align: center; }
            .ticket-number { font-size: 50px; font-weight: 900; color: #0284c7; margin: 5px 0; }
            .btn-print { background: #10b981; color: #fff; border: none; padding: 12px; border-radius: 8px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 10px; }
            .btn-close { background: #ef4444; color: #fff; border: none; padding: 8px; border-radius: 8px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 8px; }
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
                <h2>{{ center.center_name }}</h2>
                <div id="ticketServiceName" style="font-weight:bold; color:#15803d; margin:10px 0;"></div>
                <div class="ticket-number" id="modalTicketNum">--</div>
                <button class="btn-print" onclick="window.print()">🖨️ طباعة التذكرة</button>
                <button class="btn-close" onclick="closeModal()">إغلاق</button>
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
                        document.getElementById('isPriority').checked = false;
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
    if last_ticket and last_ticket['created_at']:
        if last_ticket['created_at'].split(' ')[0] == today_str:
            try:
                next_num = int(last_ticket['ticket_number'].split('-')[1]) + 1
            except:
                next_num = 1

    prefix = "P" if is_priority else "T"
    ticket_number = f"{prefix}-{next_num:03d}"
    
    conn.execute('INSERT INTO queue_tokens (center_id, service_id, ticket_number, status, is_priority) VALUES (?, ?, ?, "WAITING", ?)', 
                 (service['center_id'], service_id, ticket_number, is_priority))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'ticket_number': ticket_number, 'service_name': service['service_name']})

# ==========================================
# 4. نافذة الموظف / العون (Employee Window)
# ==========================================
@app.route('/employee-window')
def employee_window():
    # للمعاينة السريعة بدون تعقيد تسجيل الدخول، سنقوم بتوجيهه افتراضياً للخدمة رقم 1 إن لم تكن الجلسة مفعلة
    if not session.get('service_id'):
        session['service_id'] = 1
        session['role'] = 'employee'
        
    conn = get_db_connection()
    service = conn.execute('SELECT * FROM services WHERE id = ?', (session['service_id'],)).fetchone()
    conn.close()
    
    if not service:
        return "لا توجد مصلحة محددة، يرجى ضبط الجدول.", 400

    return render_template_string('''
        <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>عون النداء</title>
        <style>
            body { background: #0f172a; color: #fff; font-family: Tahoma; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .container { width: 480px; background: #1e293b; padding: 30px; border-radius: 15px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .ticket-box { font-size: 50px; color: #38bdf8; font-weight: bold; margin: 15px 0; background: #0f172a; padding: 15px; border-radius: 10px; border: 2px solid #334155; }
            button { width: 100%; padding: 14px; margin: 8px 0; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; color: #fff; }
        </style></head>
        <body><div class="container">
        <h2>🖥 نافذة المصلحة: {{ service.service_name }}</h2>
        <div class="ticket-box" id="currentTicket">---</div>
        <button style="background: #10b981;" onclick="callNext()">📢 نداء التالية</button>
        <button style="background: #3b82f6;" onclick="completeTicket()">✅ إنهاء التذكرة</button>
        <br><a href="/logout" style="color:#f87171; display:inline-block; margin-top:15px; text-decoration:none;">خروج 🚪</a>
        </div>
        <script>
            function updateStatus() { 
                fetch('/api/employee-status/{{ service.id }}').then(res=>res.json()).then(d=>{
                    document.getElementById('currentTicket').innerText = d.current_ticket || '---';
                }); 
            }
            function callNext() { 
                fetch('/api/call-next/{{ service.id }}', {method:'POST'}).then(res=>res.json()).then(data => {
                    if(data.success) { updateStatus(); } else { alert('لا توجد تذاكر في الانتظار!'); }
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
    
    next_t = conn.execute('''
        SELECT * FROM queue_tokens WHERE service_id = ? AND status = "WAITING" 
        ORDER BY is_priority DESC, id ASC LIMIT 1
    ''', (service_id,)).fetchone()
    
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
