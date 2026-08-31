#!/bin/bash
echo "=== Перезапуск EKO Production CRM ==="

echo "1. Останавливаем сервисы..."
systemctl stop eko-production
systemctl stop nginx

echo "2. Ждем 3 секунды..."
sleep 3

echo "3. Запускаем сервисы..."
systemctl start eko-production
systemctl start nginx

echo "4. Проверяем статус..."
sleep 2

echo "=== Статус EKO Production ==="
systemctl status eko-production --no-pager | head -20

echo ""
echo "=== Статус Nginx ==="
systemctl status nginx --no-pager | head -20

echo ""
echo "=== Проверка доступности ==="
curl -s -o /dev/null -w "HTTP код: %{http_code}\nВремя ответа: %{time_total} сек\n" http://127.0.0.1:8000

echo ""
echo "Перезапуск завершен!"
