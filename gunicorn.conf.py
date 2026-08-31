# Конфигурация Gunicorn для EKO Production

# Количество воркеров = (2 * CPU ядра) + 1
workers = 3  # Для 1 ядра
worker_class = 'sync'
worker_connections = 1000

# Биндинг
bind = '127.0.0.1:8000'

# Таймауты
timeout = 120
keepalive = 5

# Логи
accesslog = '/var/log/gunicorn/access.log'
errorlog = '/var/log/gunicorn/error.log'
loglevel = 'info'

# Перезагрузка
reload = False
preload_app = True

# Производительность
max_requests = 1000
max_requests_jitter = 50

# Безопасность
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
