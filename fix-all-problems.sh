#!/bin/bash
echo "=== ИСПРАВЛЕНИЕ ВСЕХ ПРОБЛЕМ EKO PRODUCTION ==="

# 1. Убиваем Apache
echo "1. Уничтожаем Apache..."
sudo systemctl stop apache2 2>/dev/null
sudo pkill -9 apache2 2>/dev/null
sudo systemctl disable apache2 2>/dev/null
sudo systemctl mask apache2 2>/dev/null

# 2. Освобождаем порты
echo "2. Освобождаем порты 80 и 443..."
sudo fuser -k 80/tcp 2>/dev/null
sudo fuser -k 443/tcp 2>/dev/null

# 3. Перезапускаем Nginx
echo "3. Настраиваем Nginx..."
sudo systemctl stop nginx 2>/dev/null
sudo systemctl start nginx
sudo systemctl enable nginx

# 4. Перезапускаем Gunicorn
echo "4. Перезапускаем приложение..."
sudo systemctl restart eko-production

# 5. Проверяем
echo "5. Проверяем систему..."
sleep 3

echo "=== ОТЧЕТ ==="
echo "1. Веб-серверы:"
sudo systemctl status nginx --no-pager | grep "Active:"
sudo systemctl status apache2 --no-pager 2>/dev/null | grep "Active:" || echo "Apache: не активен (отлично!)"

echo ""
echo "2. Порт 80:"
sudo ss -tulpn | grep :80 || echo "Ничего не слушает порт 80!"

echo ""
echo "3. Приложение:"
sudo systemctl status eko-production --no-pager | grep "Active:"

echo ""
echo "4. Тестируем главную страницу:"
curl -s -o /dev/null -w "Главная: %{http_code} за %{time_total} сек\n" http://eko-production.ru/

echo ""
echo "5. Тестируем типичные маршруты:"
for route in "/login" "/dashboard" "/warehouse" "/sewing"; do
    curl -s -o /dev/null -w "$route: %{http_code}\n" "http://eko-production.ru$route" &
done
wait

echo ""
echo "=== ИСПРАВЛЕНИЕ ЗАВЕРШЕНО ==="
