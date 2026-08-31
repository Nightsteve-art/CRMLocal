#!/bin/bash
echo "=== Исправление отступов в app.py ==="

# Создаем backup
cp /var/www/eko-production/app.py /var/www/eko-production/app.py.backup.$(date +%s)

# Используем autopep8 для исправления отступов
cd /var/www/eko-production
source venv/bin/activate

# Установите autopep8 если нет
pip install autopep8 2>/dev/null || true

# Исправляем отступы
echo "Исправляем отступы..."
autopep8 --in-place --aggressive --aggressive app.py

# Или используем simpler method
echo "Альтернативный метод исправления..."
python3 -c "
import re
with open('app.py', 'r') as f:
    content = f.read()
    
# Исправляем распространенные ошибки
# 1. Табы -> 4 пробела
content = content.replace('\t', '    ')
    
# 2. Ищем строки с комментариями docstring без отступов
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'def ' in line and i+1 < len(lines):
        next_line = lines[i+1]
        if next_line.strip().startswith('\"\"\"') and not next_line.startswith('    '):
            # Добавляем отступ к docstring
            lines[i+1] = '    ' + next_line.lstrip()
    
content = '\n'.join(lines)
with open('app.py', 'w') as f:
    f.write(content)
print('Исправления применены')
"

# Проверяем синтаксис
echo "Проверяем синтаксис..."
python3 -m py_compile app.py && echo "✅ Синтаксис корректен" || echo "❌ Есть ошибки"

echo "Готово!"
