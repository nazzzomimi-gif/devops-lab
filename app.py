from flask import Flask
import subprocess, re, datetime

app = Flask(__name__)

def check_host(ip):
    res = subprocess.run(["ping", "-c", "1", "-w", "1", ip], capture_output=True, text=True)
    if res.returncode == 0:
        match = re.search(r"time=([\d.]+)", res.stdout)
        ms = match.group(1) if match else "<1"
        return True, f"{ms} ms"
    return False, "Таймаут"

@app.route("/")
def index():
    now = datetime.datetime.now().strftime("%H:%M:%S")
    rows = ""
    with open("targets.txt", encoding="utf-8") as f:
        for line in f:
            if "|" not in line: continue
            name, ip = [x.strip() for x in line.split("|", 1)]
            ok, info = check_host(ip)
            color = "#00ff00" if ok else "#ff4444"
            status = "ONLINE" if ok else "OFFLINE"
            rows += f"<tr><td>{name}</td><td>{ip}</td><td style='color:{color};font-weight:bold'>{status}</td><td>{info}</td></tr>"

    return f"""<meta charset='utf-8'><meta http-equiv='refresh' content='15'>
    <body style='background:#121212;color:#eee;font-family:monospace;padding:20px'>
    <h2>Мониторинг сети офиса (обновлено в {now})</h2>
    <table border='1' cellpadding='10' style='border-collapse:collapse;border-color:#444'>
    <tr><th>Узел</th><th>IP-адрес</th><th>Статус</th><th>Пинг</th></tr>{rows}
    </table></body>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
