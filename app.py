from flask import Flask, request, redirect
import subprocess, re, datetime, socket, time, os

app = Flask(__name__)
last_state = {}
LOG_FILE = "events.log"
TARGETS_FILE = "targets.txt"

def log_event(msg):
    ts = datetime.datetime.now().strftime("%d-%m %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def check_target(target):
    if ":" in target:
        ip, port = target.split(":", 1)
        start = time.time()
        try:
            with socket.create_connection((ip, int(port)), timeout=1):
                ms = round((time.time() - start) * 1000, 1)
                return True, f"TCP-порт ok ({ms} ms)"
        except Exception:
            return False, "TCP-порт закрыт"
    res = subprocess.run(["ping", "-c", "1", "-W", "1", target], capture_output=True, text=True)
    if res.returncode == 0:
        match = re.search(r"time=([\d.]+)", res.stdout)
        ms = match.group(1) if match else "<1"
        return True, f"Ping {ms} ms"
    return False, "Ping таймаут"

@app.route("/add", methods=["POST"])
def add_target():
    name = request.form.get("name", "").strip()
    target = request.form.get("target", "").strip()
    if name and target:
        with open(TARGETS_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{name} | {target}\n")
        log_event(f"Добавлен узел: {name} ({target})")
    return redirect("./")

@app.route("/delete", methods=["POST"])
def delete_target():
    target_to_del = request.form.get("target", "").strip()
    if os.path.exists(TARGETS_FILE):
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(TARGETS_FILE, "w", encoding="utf-8") as f:
            for line in lines:
                if "|" in line and line.split("|", 1)[1].strip() == target_to_del:
                    continue
                f.write(line)
        last_state.pop(target_to_del, None)
        log_event(f"Удален узел: {target_to_del}")
    return redirect("./")

@app.route("/clear", methods=["POST"])
def clear_log():
    open(LOG_FILE, "w").close()
    return redirect("./")

@app.route("/")
def index():
    now = datetime.datetime.now().strftime("%H:%M:%S")
    rows = ""
    if os.path.exists(TARGETS_FILE):
        with open(TARGETS_FILE, encoding="utf-8") as f:
            for line in f:
                if "|" not in line: continue
                name, target = [x.strip() for x in line.split("|", 1)]
                ok, info = check_target(target)
                prev = last_state.get(target)
                if prev is not None and prev != ok:
                    log_event(f"{name} ({target}) сменил статус на {'ONLINE' if ok else 'OFFLINE'}")
                last_state[target] = ok
                color = "#00ff00" if ok else "#ff4444"
                status = "ONLINE" if ok else "OFFLINE"
                del_btn = f"<form method='post' action='delete' style='margin:0'><input type='hidden' name='target' value='{target}'><button type='submit' style='background:#441111;color:#ff6666;border:1px solid #662222;cursor:pointer'>✖</button></form>"
                rows += f"<tr><td>{name}</td><td>{target}</td><td style='color:{color};font-weight:bold'>{status}</td><td>{info}</td><td style='text-align:center'>{del_btn}</td></tr>"
    events = ""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            events = "".join(reversed(f.readlines()[-10:]))
    add_form = "<form method='post' action='add' style='margin-bottom:15px'><input name='name' placeholder='Название (напр. Принтер)' required style='padding:6px;background:#222;color:#eee;border:1px solid #555'> <input name='target' placeholder='IP или IP:порт' required style='padding:6px;background:#222;color:#eee;border:1px solid #555'> <button type='submit' style='padding:6px 14px;background:#1b4d1b;color:#fff;border:1px solid #2e7d32;cursor:pointer'>+ Добавить</button></form>"
    clear_btn = "<form method='post' action='clear' style='display:inline;margin-left:15px'><button type='submit' style='padding:3px 8px;font-size:12px;cursor:pointer'>Очистить</button></form>"
    return f"<meta charset='utf-8'><meta http-equiv='refresh' content='15'><body style='background:#121212;color:#eee;font-family:monospace;padding:20px'><h2>Мониторинг сети офиса (обновлено в {now}) <button onclick='location.reload()' style='margin-left:15px;padding:6px 12px;cursor:pointer'>Проверить сейчас</button></h2>{add_form}<table border='1' cellpadding='10' style='border-collapse:collapse;border-color:#444'><tr><th>Узел</th><th>Адрес / Порт</th><th>Статус</th><th>Отклик</th><th>Удалить</th></tr>{rows}</table><h3>Журнал событий:{clear_btn}</h3><pre style='background:#1e1d1d;padding:10px;border:1px solid #333'>{events or 'Пока смен статусов не было'}</pre></body>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
