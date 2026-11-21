from flask import Flask, request, redirect
from concurrent.futures import ThreadPoolExecutor
import subprocess, re, datetime, socket, time, os, sqlite3, urllib.request

app = Flask(__name__)
os.makedirs("data", exist_ok=True)
DB_FILE = "data/monitor.db"
LOG_FILE = "data/events.log"
last_state = {}
scan_results = []

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS targets (id INTEGER PRIMARY KEY, name TEXT, target TEXT UNIQUE)")
        db.execute("CREATE TABLE IF NOT EXISTS stats (target TEXT PRIMARY KEY, total INTEGER DEFAULT 0, ok_count INTEGER DEFAULT 0)")
        if db.execute("SELECT COUNT(*) FROM targets").fetchone()[0] == 0:
            defaults = [("Офис Подсеть 50", "192.168.50.1"), ("Офис Подсеть 3", "192.168.3.1"), ("Роутер Веб", "http://192.168.3.1"), ("Google DNS", "8.8.8.8"), ("Google DNS Порт", "8.8.8.8:53")]
            db.executemany("INSERT OR IGNORE INTO targets (name, target) VALUES (?, ?)", defaults)

def log_event(msg):
    ts = datetime.datetime.now().strftime("%d-%m %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def check_single(row):
    name, target = row["name"], row["target"]
    start = time.time()
    state, info = "OFFLINE", "Нет ответа"
    if target.startswith("http://") or target.startswith("https://"):
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "NetMon/1.0"})
            with urllib.request.urlopen(req, timeout=2) as r:
                ms = round((time.time() - start) * 1000, 1)
                code = r.getcode()
                state = "ONLINE" if code < 400 else "WARNING"
                info = f"HTTP {code} ({ms} ms)"
        except Exception as e:
            info = f"HTTP ошибка"
    elif ":" in target:
        ip, port = target.split(":", 1)
        try:
            with socket.create_connection((ip, int(port)), timeout=1.5):
                ms = round((time.time() - start) * 1000, 1)
                state, info = "ONLINE", f"TCP ok ({ms} ms)"
        except Exception:
            info = "TCP порт закрыт"
    else:
        res = subprocess.run(["ping", "-c", "3", "-i", "0.2", "-W", "1", target], capture_output=True, text=True)
        loss_m = re.search(r"(\d+)% packet loss", res.stdout)
        loss = int(loss_m.group(1)) if loss_m else 100
        rtt_m = re.search(r"min/avg/max[^=]*=\s*[\d.]+/([\d.]+)", res.stdout)
        avg_ms = float(rtt_m.group(1)) if rtt_m else 0.0
        if loss == 100:
            state, info = "OFFLINE", "Потери: 100%"
        elif loss > 0 or avg_ms > 150:
            state, info = "WARNING", f"{avg_ms} ms | Потери: {loss}%"
        else:
            state, info = "ONLINE", f"{avg_ms} ms | Потери: 0%"
    return name, target, state, info

@app.route("/add", methods=["POST"])
def add_target():
    name = request.form.get("name", "").strip()
    target = request.form.get("target", "").strip()
    if name and target:
        with get_db() as db:
            db.execute("INSERT OR IGNORE INTO targets (name, target) VALUES (?, ?)", (name, target))
        log_event(f"Добавлен узел: {name} ({target})")
    return redirect("./")

@app.route("/delete", methods=["POST"])
def delete_target():
    t = request.form.get("target", "").strip()
    with get_db() as db:
        db.execute("DELETE FROM targets WHERE target = ?", (t,))
        db.execute("DELETE FROM stats WHERE target = ?", (t,))
    last_state.pop(t, None)
    log_event(f"Удален узел: {t}")
    return redirect("./")

@app.route("/scan", methods=["POST"])
def scan_net():
    global scan_results
    subnet = request.form.get("subnet", "192.168.3").strip().rstrip(".")
    ips = [f"{subnet}.{i}" for i in range(1, 255)]
    def ping_fast(ip):
        r = subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL)
        return ip if r.returncode == 0 else None
    with ThreadPoolExecutor(max_workers=60) as ex:
        scan_results = [ip for ip in ex.map(ping_fast, ips) if ip]
    log_event(f"Скан подсети {subnet}.0/24: найдено {len(scan_results)} устройств")
    return redirect("./")

@app.route("/clear", methods=["POST"])
def clear_log():
    open(LOG_FILE, "w").close()
    return redirect("./")

@app.route("/")
def index():
    init_db()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    with get_db() as db:
        targets = db.execute("SELECT * FROM targets").fetchall()
    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(check_single, targets))
    rows, has_offline = "", False
    with get_db() as db:
        for name, target, state, info in results:
            is_up = 1 if state != "OFFLINE" else 0
            db.execute("INSERT INTO stats (target, total, ok_count) VALUES (?, 1, ?) ON CONFLICT(target) DO UPDATE SET total = total + 1, ok_count = ok_count + ?", (target, is_up, is_up))
            st = db.execute("SELECT total, ok_count FROM stats WHERE target = ?", (target,)).fetchone()
            uptime = round((st["ok_count"] / st["total"]) * 100, 1) if st["total"] else 100.0
            prev = last_state.get(target)
            if prev is not None and prev != state:
                log_event(f"{name} ({target}): {prev} -> {state}")
            last_state[target] = state
            if state == "OFFLINE": has_offline = True
            color = "#00ff00" if state == "ONLINE" else ("#ffbb00" if state == "WARNING" else "#ff4444")
            del_btn = f"<form method='post' action='delete' style='margin:0'><input type='hidden' name='target' value='{target}'><button type='submit' style='background:#441111;color:#ff6666;border:1px solid #662222;cursor:pointer'>✖</button></form>"
            rows += f"<tr><td>{name}</td><td>{target}</td><td style='color:{color};font-weight:bold'>{state}</td><td>{info}</td><td>{uptime}%</td><td style='text-align:center'>{del_btn}</td></tr>"
    events = "".join(reversed(open(LOG_FILE, encoding="utf-8").readlines()[-10:])) if os.path.exists(LOG_FILE) else ""
    scan_html = ""
    if scan_results:
        btns = " ".join([f"<form method='post' action='add' style='display:inline;margin:3px'><input type='hidden' name='name' value='Узел {ip}'><input type='hidden' name='target' value='{ip}'><button type='submit' style='background:#1a3a5c;color:#fff;border:1px solid #2b5b8c;padding:4px 8px;cursor:pointer'>+ {ip}</button></form>" for ip in scan_results])
        scan_html = f"<div style='margin:10px 0;padding:10px;background:#1a1d24;border:1px solid #334'><b>Найдено в сети ({len(scan_results)}):</b><br>{btns}</div>"
    beep_js = "<script>if(localStorage.getItem('alarm')==='1'){let c=new AudioContext(),o=c.createOscillator();o.connect(c.destination);o.frequency.value=600;o.start();setTimeout(()=>o.stop(),250);}</script>" if has_offline else ""
    return f"<meta charset='utf-8'><meta http-equiv='refresh' content='15'><body style='background:#121212;color:#eee;font-family:monospace;padding:20px'><h2>Мониторинг сети офиса ({now}) <button onclick='location.reload()' style='margin-left:10px;padding:5px 10px;cursor:pointer'>Проверить</button> <label style='font-size:13px;margin-left:15px;cursor:pointer'><input type='checkbox' id='alm' onchange=\"localStorage.setItem('alarm',this.checked?'1':'0')\"> Звук тревоги</label></h2><script>document.getElementById('alm').checked=localStorage.getItem('alarm')==='1'</script>{beep_js}<form method='post' action='add' style='display:inline-block;margin-right:20px'><input name='name' placeholder='Название' required style='padding:5px;background:#222;color:#eee;border:1px solid #555'> <input name='target' placeholder='IP, IP:порт или http://...' required style='padding:5px;background:#222;color:#eee;border:1px solid #555'> <button type='submit' style='padding:5px 12px;background:#1b4d1b;color:#fff;border:1px solid #2e7d32;cursor:pointer'>+ Добавить</button></form><form method='post' action='scan' style='display:inline-block'><input name='subnet' value='192.168.3' size='10' style='padding:5px;background:#222;color:#eee;border:1px solid #555'> <button type='submit' style='padding:5px 12px;background:#1a3a5c;color:#fff;border:1px solid #2b5b8c;cursor:pointer'>🔍 Скан подсети</button></form>{scan_html}<table border='1' cellpadding='9' style='margin-top:15px;border-collapse:collapse;border-color:#444'><tr><th>Узел</th><th>Адрес / Порт / URL</th><th>Статус</th><th>Отклик и потери</th><th>Аптайм</th><th>Удалить</th></tr>{rows}</table><h3>Журнал событий: <form method='post' action='clear' style='display:inline'><button type='submit' style='padding:2px 8px;font-size:12px;cursor:pointer'>Очистить</button></form></h3><pre style='background:#1e1d1d;padding:10px;border:1px solid #333'>{events or 'Пока смен статусов не было'}</pre></body>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
