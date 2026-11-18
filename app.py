from flask import Flask
import redis

app = Flask(__name__)
cache = redis.Redis(host='redis', port=6379)

@app.route('/')
def hello():
    count = cache.incr('hits')
    return f'<meta charset="utf-8"><h1 style="color: #00aa00;">DevOps lab: Микросервисы работают!</h1><p>Эта страница открыта <b>{count}</b> раз(а). Данные сохранены в базе Redis.</p>'
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
