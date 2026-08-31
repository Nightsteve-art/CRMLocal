#!/bin/bash
echo "=== НАСТРОЙКА APACHE С НУЛЯ ==="

# 1. Удаляем блокировку
echo "1. Разблокируем Apache..."
sudo systemctl unmask apache2 2>/dev/null

# 2. Устанавливаем Apache если нет
echo "2. Устанавливаем Apache..."
if ! command -v apache2 &> /dev/null; then
    sudo apt update
    sudo apt install apache2 -y
fi

# 3. Останавливаем Nginx (временно)
echo "3. Останавливаем Nginx..."
sudo systemctl stop nginx 2>/dev/null

# 4. Включаем модули Apache
echo "4. Включаем модули Apache..."
sudo a2enmod proxy proxy_http rewrite headers 2>/dev/null

# 5. Создаем конфигурацию
echo "5. Создаем конфигурацию сайта..."
sudo cat > /etc/apache2/sites-available/eko-production.conf << 'EOL'
<VirtualHost *:80>
    ServerName eko-production.ru
    ServerAlias www.eko-production.ru
    
    # Очень простое проксирование
    ProxyPass / http://localhost:8000/
    ProxyPassReverse / http://localhost:8000/
    
    # Логи
    ErrorLog ${APACHE_LOG_DIR}/eko-error.log
    CustomLog ${APACHE_LOG_DIR}/eko-access.log combined
</VirtualHost>
EOL

# 6. Активируем сайт
echo "6. Активируем сайт..."
sudo a2dissite 000-default.conf 2>/dev/null
sudo a2ensite eko-production.conf

# 7. Запускаем Apache
echo "7. Запускаем Apache..."
sudo systemctl start apache2
sudo systemctl enable apache2

# 8. Проверяем Gunicorn
echo "8. Проверяем приложение..."
sudo systemctl restart eko-production

# 9. Тестируем
echo "9. Тестируем соединение..."
sleep 3
echo ""
echo "=== РЕЗУЛЬТАТ ==="
echo "Статус Apache:"
sudo systemctl status apache2 --no-pager | head -10
echo ""
echo "Порт 80:"
sudo netstat -tulpn | grep :80
echo ""
echo "Доступность сайта:"
curl -s -o /dev/null -w "HTTP код: %{http_code}\n" http://eko-production.ru || echo "Недоступен"
