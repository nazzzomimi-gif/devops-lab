#!/bin/bash
{
  echo '<meta charset="utf-8">'
  echo '<meta http-equiv="refresh" content="10">'
  echo '<pre style="font-size: 16px; background: #1e1e1e; color: #00ff00; padding: 20px;">'
  echo "=== ОТЧЕТ СЕРВЕРА $(hostname) ==="
  echo "Дата и время: $(date)"
  echo "Время работы (Uptime): $(uptime -p)"
  echo "--- Память (RAM) ---"
  free -h | grep Mem
  echo "--- Диск (/) ---"
  df -h / | tail -n 1
  echo "--- Статус Nginx ---"
  systemctl is-active nginx
  echo '</pre>'
} > /var/www/html/index.html
