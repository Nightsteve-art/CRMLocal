from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timezone
import json
import requests
import pandas as pd
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy.orm import Session  # Добавить в импорты

app = Flask(__name__)
app.config['SECRET_KEY'] = 'eko-production-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eko_production.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 16MB max file size
app.config['ITEMS_PER_PAGE'] = 10  # Пагинация: 10 элементов на странице

# Настройки Telegram
app.config['TELEGRAM_BOT_TOKEN'] = '8442743583:AAECJ_HJblsLy_unMY6KknN5tWstNueuZZo'
app.config['TELEGRAM_CHAT_ID'] = '-5236774313'      # Склад
app.config['TELEGRAM_SEWING_CHAT_ID'] = '-5176195113' # Чат Швейки
app.config['TELEGRAM_ZAKAZ_CHAT_ID'] = '-1003770806206'   # Чат заказов

# Создаем папку для загрузок если нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Определение ролей и их прав
ROLES = {
    'admin': {
        'name': 'Администратор',
        'permissions': ['*'],  # Все права
        'modules': ['dashboard', 'counterparties', 'warehouse', 'sewing', 
                   'production', 'shipping', 'orders', 'users']
    },
    'storekeeper': {
        'name': 'Кладовщик',
        'permissions': ['warehouse:read', 'warehouse:write', 
                       'shipping:read', 'shipping:write', 
                       'orders:read', 'orders:write'],
        'modules': ['warehouse', 'shipping', 'orders']
    },
    'seamstress': {
        'name': 'Швея',
        'permissions': ['sewing:read', 'sewing:write', 'warehouse:read'],
        'modules': ['sewing', 'warehouse']
    },
    'engineer': {
        'name': 'Инженер',
        'permissions': ['production:read', 'production:write', 
                       'orders:read', 'orders:write', 
                       'shipping:read', 'warehouse:read'],
        'modules': ['production', 'orders', 'shipping', 'warehouse']
    },
    'manager': {
        'name': 'Руководитель',
        'permissions': ['*:read'],  # Чтение всех модулей
        'modules': ['dashboard', 'counterparties', 'warehouse', 'sewing', 
                   'production', 'shipping', 'orders'],
        'no_delete': True  # Не может удалять
    }
}

# Добавить в модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200))
    role = db.Column(db.String(50), default='seamstress', index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # def has_permission(self, permission):
        # """Проверка прав пользователя"""
        # if self.role == 'admin':
            # return True
        
        # role_config = ROLES.get(self.role, {})
        # permissions = role_config.get('permissions', [])
        
        # # Проверка на право удаления для руководителя
        # if self.role == 'manager' and permission.endswith(':delete'):
            # return False
        
        # # Проверка прав
        # if '*' in permissions or f'{permission}:*' in permissions:
            # return True
        
        # return permission in permissions
    
    # def has_module_access(self, module_name):
        # """Проверка доступа к модулю"""
        # if self.role == 'admin':
            # return True
        
        # role_config = ROLES.get(self.role, {})
        # modules = role_config.get('modules', [])
        
        # return module_name in modules
    
    # def can_delete(self):
        # """Может ли пользователь удалять"""
        # role_config = ROLES.get(self.role, {})
        # return not role_config.get('no_delete', False)
        
    def has_permission(self, permission):
        return True  # всем пользователям разрешено всё

    def has_module_access(self, module_name):
        return True  # всем пользователям доступны все модули

    def can_delete(self):
        return True  # всем пользователям разрешено удаление
    
    def get_role_name(self):
        """Получить название роли"""
        role_config = ROLES.get(self.role, {})
        return role_config.get('name', self.role)
    
    def __repr__(self):
        return f'<User {self.username}>'

# Модели базы данных
class Counterparty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    contact_person = db.Column(db.String(200), index=True)
    email = db.Column(db.String(200), index=True)
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    proposals = db.relationship('Proposal', backref='counterparty', lazy=True)

class Proposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    counterparty_id = db.Column(db.Integer, db.ForeignKey('counterparty.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False, index=True)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='Запрос КП', index=True)  # Запрос КП, В работе, Готов к отгрузке, Исполнено
    file_path = db.Column(db.String(500))
    file_name = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)
    
    # Дополнительные поля
    proposal_number = db.Column(db.String(100), index=True)
    amount = db.Column(db.Float, index=True)
    currency = db.Column(db.String(10), default='RUB')
    deadline = db.Column(db.Date, index=True)

class StockItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(100), nullable=False, index=True, unique=True)  # Артикул/Код
    name = db.Column(db.String(300), nullable=False, index=True)  # Название
    description = db.Column(db.Text)  # Описание
    quantity = db.Column(db.Float, default=0, nullable=False)  # Текущее количество
    unit = db.Column(db.String(50), default='шт')  # Единица измерения
    category = db.Column(db.String(100), index=True)  # Категория
    min_stock = db.Column(db.Float, default=0)  # Минимальный запас
    location = db.Column(db.String(100))  # Место хранения
    
    # Финансовые параметры (опционально)
    cost_price = db.Column(db.Float)  # Себестоимость
    selling_price = db.Column(db.Float)  # Цена продажи
    
    # Системные поля
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), index=True)
    
    # История операций (связь)
    transactions = db.relationship('StockTransaction', backref='stock_item', lazy=True, 
                                  cascade='all, delete-orphan')

class StockTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_item_id = db.Column(db.Integer, db.ForeignKey('stock_item.id'), nullable=False, index=True)
    transaction_type = db.Column(db.String(20), nullable=False, index=True)  # 'in' - приход, 'out' - расход
    quantity = db.Column(db.Float, nullable=False)  # Количество
    before_quantity = db.Column(db.Float, nullable=False)  # Количество до операции
    after_quantity = db.Column(db.Float, nullable=False)  # Количество после операции
    document_number = db.Column(db.String(100), index=True)  # Номер документа
    document_type = db.Column(db.String(50))  # Тип документа (накладная, заказ и т.д.)
    counterparty_id = db.Column(db.Integer, db.ForeignKey('counterparty.id'))  # Связанный контрагент
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposal.id'))  # Связанное КП
    notes = db.Column(db.Text)  # Примечания
    user_id = db.Column(db.String(100), default='admin')  # Кто выполнил операцию
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
class SewingTask(db.Model):
    """Задача швейного производства"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Связь с КП
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposal.id'), nullable=True, index=True)
    proposal = db.relationship('Proposal', backref='sewing_tasks')
    
    # Основная информация
    task_name = db.Column(db.String(300), nullable=False, index=True)  # Наименование объекта
    shipment_date = db.Column(db.Date, index=True)  # Дата отгрузки
    product_name = db.Column(db.String(300), nullable=False)  # Наименование изделия
    product_size = db.Column(db.String(100))  # Размеры изделия
    quantity = db.Column(db.Float, nullable=False, default=1)  # Количество
    color = db.Column(db.String(100))  # Цвет
    
    # Статусы
    status = db.Column(db.String(50), default='Новая', index=True)  # Новая, В работе, Исполнено
    
    # Системные поля
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), index=True)
    created_by = db.Column(db.String(100), default='admin')  # Кто создал
    completed_at = db.Column(db.DateTime)  # Дата исполнения
    
    # Примечания
    notes = db.Column(db.Text)

class MaterialRequest(db.Model):
    """Запрос материала для швейного производства"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Основная информация
    material = db.Column(db.String(300), nullable=False, index=True)  # Материал
    quantity = db.Column(db.Float, nullable=False)  # Количество
    color = db.Column(db.String(100))  # Цвет
    size = db.Column(db.String(100))  # Размеры
    
    # Статусы
    status = db.Column(db.String(50), default='В работе', index=True)  # В работе, Исполнено
    
    # Telegram информация
    telegram_message_id = db.Column(db.String(100))  # ID сообщения в Telegram
    telegram_sent_at = db.Column(db.DateTime)  # Когда отправлено в Telegram
    
    # Связи
    sewing_task_id = db.Column(db.Integer, db.ForeignKey('sewing_task.id'), nullable=True)
    sewing_task = db.relationship('SewingTask', backref='material_requests')
    
    # Системные поля
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), index=True)
    created_by = db.Column(db.String(100), default='admin')  # Кто создал
    
    # Примечания
    notes = db.Column(db.Text)
    
# ---------- Модели для общей Kanban-доски ----------
class KanbanProject(db.Model):
    __tablename__ = 'kanban_projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    columns = db.relationship('KanbanColumn', backref='project', lazy=True, cascade='all, delete-orphan')
    cards = db.relationship('KanbanCard', backref='project', lazy=True, cascade='all, delete-orphan')
    fields = db.relationship('KanbanField', backref='project', lazy=True, cascade='all, delete-orphan')

class KanbanColumn(db.Model):
    __tablename__ = 'kanban_columns'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('kanban_projects.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    cards = db.relationship('KanbanCard', backref='column', lazy=True, cascade='all, delete-orphan')

class KanbanCard(db.Model):
    __tablename__ = 'kanban_cards'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('kanban_projects.id'), nullable=False)
    column_id = db.Column(db.Integer, db.ForeignKey('kanban_columns.id'), nullable=False)
    # Динамические поля (храним в JSON)
    data = db.Column(db.JSON, nullable=False, default=dict)
    # Системные поля
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    comments = db.relationship('KanbanComment', backref='card', lazy=True, cascade='all, delete-orphan')
    files = db.relationship('KanbanFile', backref='card', lazy=True, cascade='all, delete-orphan')

class KanbanComment(db.Model):
    __tablename__ = 'kanban_comments'
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('kanban_cards.id'), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    files = db.relationship('KanbanFile', backref='comment', lazy=True, cascade='all, delete-orphan')

class KanbanFile(db.Model):
    __tablename__ = 'kanban_files'
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('kanban_cards.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('kanban_comments.id'), nullable=True)
    filename = db.Column(db.String(300), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)   # путь к файлу на диске
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    uploaded_by = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class KanbanField(db.Model):
    __tablename__ = 'kanban_fields'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('kanban_projects.id'), nullable=False)
    field_key = db.Column(db.String(100), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    field_type = db.Column(db.String(50), default='text')
    options = db.Column(db.Text)  # JSON строка для select
    show_on_card = db.Column(db.Boolean, default=True)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('project_id', 'field_key', name='unique_field_per_project'),)

class KanbanTemplate(db.Model):
    __tablename__ = 'kanban_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    columns_config = db.Column(db.JSON)   # список названий колонок
    fields_config = db.Column(db.JSON)    # список полей
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# Конфигурация пользователей (в реальном приложении хранить в базе)
USERS = {
    'admin': {
        'password': 'Alex4815162342',
        'role': 'admin',
        'email': 'admin@eko-production.ru',
        'full_name': 'Александриди А.С.'
    }
}

# Функция для отправки уведомлений в Telegram
def send_telegram_notification(message):
    """
    Отправляет сообщение в Telegram
    """
    try:
        token = app.config.get('TELEGRAM_BOT_TOKEN')
        chat_id = app.config.get('TELEGRAM_CHAT_ID')
        
        if not token or not chat_id:
            print("Telegram token или chat_id не настроены")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"Telegram уведомление отправлено успешно")
            return True
        else:
            print(f"Ошибка отправки в Telegram: {response.status_code}")
            return False
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False

# Функция для проверки низкого остатка и отправки уведомления
def check_low_stock_and_notify(item, operation_type):
    """
    Проверяет, стал ли остаток ниже минимального после операции
    и отправляет уведомление в Telegram если да
    """
    try:
        # ФИКС: Всегда отправляем уведомление при достижении 0
        # или если остаток ниже минимального
        should_notify = False
        reason = ""
        
        if item.quantity == 0:
            should_notify = True
            reason = "Товар закончился (остаток 0)"
        elif item.min_stock > 0 and item.quantity <= item.min_stock:
            should_notify = True
            reason = f"Остаток ниже минимального ({item.min_stock} {item.unit})"
        
        if should_notify:
            # Отправляем уведомление
            message = f"⚠️ <b>НИЗКИЙ ЗАПАС!</b>\n\n"
            message += f"<b>Товар:</b> {item.name}\n"
            message += f"<b>Артикул:</b> {item.sku}\n"
            message += f"<b>Текущий остаток:</b> {item.quantity} {item.unit}\n"
            message += f"<b>Причина:</b> {reason}\n"
            
            if item.min_stock > 0:
                message += f"<b>Минимальный запас:</b> {item.min_stock} {item.unit}\n"
            
            message += f"<b>Операция:</b> {operation_type}\n"
            message += f"<b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            
            if item.location:
                message += f"<b>Место хранения:</b> {item.location}\n"
            
            # Добавляем ссылку на позицию
            base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
            item_url = f"{base_url}/warehouse/{item.id}"
            message += f"\n🔗 <a href='{item_url}'>Перейти к товару</a>"
            
            # Отправляем уведомление
            result = send_telegram_notification(message)
            if result:
                print(f"Уведомление отправлено для товара {item.sku}: {reason}")
            return result
    except Exception as e:
        print(f"Ошибка при проверке остатка: {e}")
    return False

# Фильтр для форматирования даты
@app.template_filter('format_date')
def format_date(value):
    if value:
        # Конвертируем в локальное время если нужно
        if value.tzinfo:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.strftime('%d.%m.%Y %H:%M')
    return ''

@app.template_filter('format_date_short')
def format_date_short(value):
    if value:
        return value.strftime('%d.%m.%Y')
    return ''

# Добавить функции проверки прав
def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            user = db.session.get(User, session['user_id'])
            if not user or not user.has_permission(permission):
                flash('У вас нет прав для выполнения этого действия', 'error')
                return redirect(url_for('home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def module_access_required(module_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            user = db.session.get(User, session['user_id'])
            if not user or not user.has_module_access(module_name):
                flash('У вас нет доступа к этому модулю', 'error')
                return redirect(url_for('home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def delete_permission_required():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            user = db.session.get(User, session['user_id'])
            if not user or not user.can_delete():
                flash('У вас нет прав для удаления', 'error')
                return redirect(request.referrer or url_for('home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Обновить существующий декоратор login_required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Используем Session.get() вместо Query.get()
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_active:
            session.clear()
            flash('Ваша учетная запись не активна', 'error')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

# Главная страница - редирект
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

# Главная страница с плитками
@app.route('/home')
@login_required
def home():
    # Статистика для отображения на главной (только нужные данные)
    stats = {
        'total': Proposal.query.count(),
        'stock_items': StockItem.query.count(),
        'sewing_tasks': SewingTask.query.count(),
        'orders': Order.query.count(),
    }
    
    return render_template('index.html', stats=stats)

# Обновить функцию login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Используем filter_by с first() вместо Query.get()
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['full_name'] = user.full_name
            session['logged_in'] = True
            
            flash(f'Добро пожаловать, {user.full_name or user.username}!', 'success')
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Неверный логин или пароль')
    
    return render_template('login.html')

# Дашборд с коммерческими предложениями
@app.route('/dashboard')
@login_required
@module_access_required('dashboard')
def dashboard():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    counterparty_id = request.args.get('counterparty_id', type=int)
    search_query = request.args.get('search', '')
    
    query = Proposal.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if counterparty_id:
        query = query.filter_by(counterparty_id=counterparty_id)
    
    if search_query:
        query = query.filter(Proposal.title.contains(search_query))
    
    # Сортировка по дате создания (новые сверху)
    proposals = query.order_by(Proposal.created_at.desc()).paginate(
        page=page, 
        per_page=app.config['ITEMS_PER_PAGE'],
        error_out=False
    )
    
    counterparties = Counterparty.query.order_by(Counterparty.name).all()
    
    # Статистика по статусам
    stats = {
        'total': Proposal.query.count(),
        'request': Proposal.query.filter_by(status='Запрос КП').count(),
        'in_progress': Proposal.query.filter_by(status='В работе').count(),
        'ready': Proposal.query.filter_by(status='Готов к отгрузке').count(),
        'completed': Proposal.query.filter_by(status='Исполнено').count()
    }
    
    return render_template('dashboard.html', 
                         proposals=proposals, 
                         counterparties=counterparties,
                         stats=stats,
                         status_filter=status_filter,
                         selected_counterparty=counterparty_id,
                         search_query=search_query)

@app.route('/calculator')
@login_required
def calculator():
    """Калькулятор хоккейного борта и стекла"""
    return render_template('calculator.html')

# Создать контрагента
@app.route('/counterparty/create', methods=['GET', 'POST'])
@login_required
def create_counterparty():
    if request.method == 'POST':
        name = request.form.get('name')
        contact_person = request.form.get('contact_person')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        if name:
            counterparty = Counterparty(
                name=name,
                contact_person=contact_person,
                email=email,
                phone=phone,
                address=address
            )
            db.session.add(counterparty)
            db.session.commit()
            return redirect(url_for('counterparties'))
    
    return render_template('create_counterparty.html')

# Страница всех контрагентов
@app.route('/counterparties')
@login_required
def counterparties():
    counterparties_list = Counterparty.query.order_by(Counterparty.name).all()
    return render_template('counterparties.html', counterparties=counterparties_list)

# Создать КП
@app.route('/proposal/create', methods=['GET', 'POST'])
@login_required
def create_proposal():
    if request.method == 'POST':
        counterparty_id = request.form.get('counterparty_id')
        title = request.form.get('title')
        description = request.form.get('description')
        status = request.form.get('status', 'Запрос КП')
        proposal_number = request.form.get('proposal_number')
        amount = request.form.get('amount')
        currency = request.form.get('currency', 'RUB')
        deadline = request.form.get('deadline')
        
        # Обработка файла
        file = request.files.get('file')
        file_path = None
        file_name = None
        
        if file and file.filename:
            filename = secure_filename(file.filename)
            # Добавляем timestamp для уникальности
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_name = file.filename
        
        # Конвертация суммы
        try:
            amount_float = float(amount) if amount else None
        except:
            amount_float = None
        
        # Конвертация даты
        deadline_date = None
        if deadline:
            try:
                deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
            except:
                pass
        
        proposal = Proposal(
            counterparty_id=counterparty_id,
            title=title,
            description=description,
            status=status,
            file_path=file_path,
            file_name=file_name,
            proposal_number=proposal_number,
            amount=amount_float,
            currency=currency,
            deadline=deadline_date
        )
        
        db.session.add(proposal)
        db.session.commit()
        
        return redirect(url_for('dashboard'))
    
    counterparties = Counterparty.query.order_by(Counterparty.name).all()
    return render_template('create_proposal.html', counterparties=counterparties)

# Просмотр КП
@app.route('/proposal/<int:proposal_id>')
@login_required
def view_proposal(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    return render_template('view_proposal.html', proposal=proposal)

# Скачать файл
@app.route('/proposal/<int:proposal_id>/download')
@login_required
def download_proposal(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    if proposal.file_path and os.path.exists(proposal.file_path):
        return send_file(proposal.file_path, 
                        as_attachment=True, 
                        download_name=proposal.file_name or os.path.basename(proposal.file_path))
    return "Файл не найден", 404

# API для предпросмотра файла
@app.route('/proposal/<int:proposal_id>/preview')
@login_required
def preview_proposal(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    if proposal.file_path and os.path.exists(proposal.file_path):
        # Определяем MIME-тип по расширению
        ext = os.path.splitext(proposal.file_path)[1].lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
        }
        
        mimetype = mime_types.get(ext, 'application/octet-stream')
        
        return send_file(
            proposal.file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=proposal.file_name or os.path.basename(proposal.file_path)
        )
    return "Файл не найден", 404

# Обновить статус КП
@app.route('/proposal/<int:proposal_id>/update_status', methods=['POST'])
@login_required
def update_status(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    new_status = request.json.get('status')
    
    if new_status in ['Запрос КП', 'В работе', 'Готов к отгрузке', 'Исполнено']:
        proposal.status = new_status
        db.session.commit()
        return jsonify({'success': True, 'new_status': new_status})
    
    return jsonify({'success': False, 'error': 'Неверный статус'})

# Удалить КП
@app.route('/proposal/<int:proposal_id>/delete', methods=['POST'])
@login_required
def delete_proposal(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    
    # Удаляем файл если есть
    if proposal.file_path and os.path.exists(proposal.file_path):
        os.remove(proposal.file_path)
    
    db.session.delete(proposal)
    db.session.commit()
    
    return jsonify({'success': True})

# Редактировать КП
@app.route('/proposal/<int:proposal_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_proposal(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    
    if request.method == 'POST':
        proposal.counterparty_id = request.form.get('counterparty_id')
        proposal.title = request.form.get('title')
        proposal.description = request.form.get('description')
        proposal.status = request.form.get('status')
        proposal.proposal_number = request.form.get('proposal_number')
        
        # Обработка суммы
        amount = request.form.get('amount')
        try:
            proposal.amount = float(amount) if amount else None
        except:
            proposal.amount = None
        
        proposal.currency = request.form.get('currency', 'RUB')
        
        # Обработка даты
        deadline = request.form.get('deadline')
        if deadline:
            try:
                proposal.deadline = datetime.strptime(deadline, '%Y-%m-%d').date()
            except:
                proposal.deadline = None
        else:
            proposal.deadline = None
        
        # Обработка нового файла
        file = request.files.get('file')
        if file and file.filename:
            # Удаляем старый файл если есть
            if proposal.file_path and os.path.exists(proposal.file_path):
                os.remove(proposal.file_path)
            
            filename = secure_filename(file.filename)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            proposal.file_path = file_path
            proposal.file_name = file.filename
        
        db.session.commit()
        return redirect(url_for('view_proposal', proposal_id=proposal.id))
    
    counterparties = Counterparty.query.order_by(Counterparty.name).all()
    deadline_str = proposal.deadline.strftime('%Y-%m-%d') if proposal.deadline else ''
    return render_template('edit_proposal.html', 
                         proposal=proposal, 
                         counterparties=counterparties,
                         deadline_str=deadline_str)
                         
                         
@app.route('/production/kanban')
@login_required
@module_access_required('production')
def production_kanban():
    """Страница кастомизируемой Kanban-доски (клиентская, с localStorage)"""
    return render_template('kanban_board.html')

@app.route('/production')
@login_required
@module_access_required('production')
def production():
    """Новая Kanban‑доска (перенаправление или прямой рендер)"""
    return render_template('kanban_board.html')
    
# ---------- API для Kanban ----------
@app.route('/api/kanban/projects', methods=['GET'])
@login_required
def get_kanban_projects():
    projects = KanbanProject.query.order_by(KanbanProject.created_at).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'createdAt': p.created_at.isoformat()
    } for p in projects])

@app.route('/api/kanban/projects', methods=['POST'])
@login_required
def create_kanban_project():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name required'}), 400
    project = KanbanProject(name=name)
    db.session.add(project)
    db.session.commit()
    # Создаём колонки по умолчанию
    default_columns = ['Проектирование', 'Распил', 'Сварка', 'Покраска', 'Сборка', 'Готово']
    for idx, col_name in enumerate(default_columns):
        col = KanbanColumn(project_id=project.id, name=col_name, order_index=idx)
        db.session.add(col)
    db.session.commit()
    return jsonify({'id': project.id, 'name': project.name})

@app.route('/api/kanban/projects/<int:project_id>', methods=['PUT'])
@login_required
def rename_kanban_project(project_id):
    data = request.json
    new_name = data.get('name')
    project = KanbanProject.query.get_or_404(project_id)
    project.name = new_name
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/kanban/projects/<int:project_id>', methods=['DELETE'])
@login_required
def delete_kanban_project(project_id):
    project = KanbanProject.query.get_or_404(project_id)
    # Проверка, что не последний проект
    if KanbanProject.query.count() <= 1:
        return jsonify({'error': 'Cannot delete the last project'}), 400
    db.session.delete(project)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/kanban/projects/<int:project_id>/columns', methods=['GET'])
@login_required
def get_kanban_columns(project_id):
    columns = KanbanColumn.query.filter_by(project_id=project_id).order_by(KanbanColumn.order_index).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'order': c.order_index
    } for c in columns])

@app.route('/api/kanban/projects/<int:project_id>/columns', methods=['POST'])
@login_required
def add_kanban_column(project_id):
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name required'}), 400
    max_order = db.session.query(db.func.max(KanbanColumn.order_index)).filter_by(project_id=project_id).scalar() or 0
    column = KanbanColumn(project_id=project_id, name=name, order_index=max_order+1)
    db.session.add(column)
    db.session.commit()
    return jsonify({'id': column.id, 'name': column.name, 'order': column.order_index})

@app.route('/api/kanban/columns/<int:column_id>', methods=['PUT'])
@login_required
def update_kanban_column(column_id):
    data = request.json
    column = KanbanColumn.query.get_or_404(column_id)
    if 'name' in data:
        column.name = data['name']
    if 'order' in data:
        column.order_index = data['order']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/kanban/columns/<int:column_id>', methods=['DELETE'])
@login_required
def delete_kanban_column(column_id):
    column = KanbanColumn.query.get_or_404(column_id)
    # Переносим карточки этой колонки в первую колонку (или удаляем)
    first_column = KanbanColumn.query.filter_by(project_id=column.project_id).order_by(KanbanColumn.order_index).first()
    if first_column and first_column.id != column.id:
        KanbanCard.query.filter_by(column_id=column_id).update({'column_id': first_column.id})
    else:
        # Если это единственная колонка, удаляем и карточки
        KanbanCard.query.filter_by(column_id=column_id).delete()
    db.session.delete(column)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/kanban/projects/<int:project_id>/cards', methods=['GET'])
@login_required
def get_kanban_cards(project_id):
    cards = KanbanCard.query.filter_by(project_id=project_id).all()
    result = []
    for card in cards:
        # Загружаем комментарии и файлы
        comments = [{
            'id': c.id,
            'author': c.author,
            'text': c.text,
            'isUrgent': c.is_urgent,
            'timestamp': c.created_at.isoformat(),
            'files': [{'name': f.filename, 'url': url_for('download_kanban_file', file_id=f.id)} for f in c.files]
        } for c in card.comments]
        result.append({
            'id': card.id,
            'columnId': card.column_id,
            'data': card.data,  # все динамические поля
            'comments': comments,
            'createdAt': card.created_at.isoformat(),
            'updatedAt': card.updated_at.isoformat()
        })
    return jsonify(result)
    
@app.route('/api/kanban/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_kanban_comment(comment_id):
    comment = KanbanComment.query.get_or_404(comment_id)
    # Проверка прав: только автор или администратор
    if comment.author != session.get('full_name', session.get('username')) and session.get('role') != 'admin':
        return jsonify({'error': 'Нет прав на удаление'}), 403
    # Удаляем связанные файлы с диска
    for file in comment.files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'kanban', file.filepath)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(file)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True})
   



@app.route('/api/kanban/cards/<int:card_id>', methods=['PUT'])
@login_required
def update_kanban_card(card_id):
    data = request.json
    card = KanbanCard.query.get_or_404(card_id)
    if 'columnId' in data:
        card.column_id = data['columnId']
    if 'data' in data:
        card.data = data['data']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/kanban/cards/<int:card_id>', methods=['DELETE'])
@login_required
def delete_kanban_card(card_id):
    card = KanbanCard.query.get_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/kanban/cards/<int:card_id>/comments', methods=['POST'])
@login_required
def add_kanban_comment(card_id):
    # Проверяем, пришли данные как JSON или как form-data
    if request.is_json:
        data = request.json
        text = data.get('text')
        is_urgent = data.get('isUrgent', False)
        files_data = data.get('files', [])
        # ... обработка base64 (как было)
    else:
        # FormData
        text = request.form.get('text')
        is_urgent = request.form.get('isUrgent') == 'true'
        uploaded_files = request.files.getlist('files')
        
        comment = KanbanComment(
            card_id=card_id,
            author=session.get('full_name', session.get('username', 'admin')),
            text=text,
            is_urgent=is_urgent
        )
        db.session.add(comment)
        db.session.flush()
        
        for file in uploaded_files:
            if file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                saved_filename = f"kanban_{card_id}_{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'kanban', saved_filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                
                kanban_file = KanbanFile(
                    card_id=card_id,
                    comment_id=comment.id,
                    filename=filename,
                    filepath=saved_filename,
                    file_size=os.path.getsize(file_path),
                    mime_type=file.content_type,
                    uploaded_by=session.get('username', 'admin')
                )
                db.session.add(kanban_file)
        
        db.session.commit()
        
        return jsonify({
            'id': comment.id,
            'author': comment.author,
            'text': comment.text,
            'isUrgent': comment.is_urgent,
            'timestamp': comment.created_at.isoformat(),
            'files': [{'name': f.filename, 'url': url_for('download_kanban_file', file_id=f.id)} for f in comment.files]
        }), 201

@app.route('/api/kanban/files/<int:file_id>')
@login_required
def download_kanban_file(file_id):
    kanban_file = KanbanFile.query.get_or_404(file_id)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'kanban', kanban_file.filepath)
    if not os.path.exists(file_path):
        return "Файл не найден", 404
    return send_file(file_path, as_attachment=True, download_name=kanban_file.filename)

@app.route('/api/kanban/projects/<int:project_id>/fields', methods=['GET'])
@login_required
def get_kanban_fields(project_id):
    fields = KanbanField.query.filter_by(project_id=project_id).order_by(KanbanField.order_index).all()
    return jsonify([{
        'id': f.id,
        'key': f.field_key,
        'label': f.label,
        'type': f.field_type,
        'options': json.loads(f.options) if f.options else [],
        'showOnCard': f.show_on_card,
        'order': f.order_index
    } for f in fields])

@app.route('/api/kanban/projects/<int:project_id>/fields', methods=['POST'])
@login_required
def create_kanban_field(project_id):
    data = request.json
    field = KanbanField(
        project_id=project_id,
        field_key=data['key'],
        label=data['label'],
        field_type=data.get('type', 'text'),
        options=json.dumps(data.get('options', [])),
        show_on_card=data.get('showOnCard', True),
        order_index=data.get('order', 0)
    )
    db.session.add(field)
    db.session.commit()
    return jsonify({'id': field.id})

@app.route('/api/kanban/fields/<int:field_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_kanban_field(field_id):
    field = KanbanField.query.get_or_404(field_id)
    if request.method == 'PUT':
        data = request.json
        if 'label' in data: field.label = data['label']
        if 'type' in data: field.field_type = data['type']
        if 'options' in data: field.options = json.dumps(data['options'])
        if 'showOnCard' in data: field.show_on_card = data['showOnCard']
        if 'order' in data: field.order_index = data['order']
        db.session.commit()
        return jsonify({'success': True})
    else:  # DELETE
        db.session.delete(field)
        db.session.commit()
        return jsonify({'success': True})

# Аналогично для шаблонов (KanbanTemplate) – сохраняем/загружаем конфигурацию
@app.route('/api/kanban/templates', methods=['GET'])
@login_required
def get_kanban_templates():
    templates = KanbanTemplate.query.order_by(KanbanTemplate.created_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'description': t.description,
        'columns': t.columns_config,
        'fields': t.fields_config
    } for t in templates])

@app.route('/api/kanban/templates', methods=['POST'])
@login_required
def create_kanban_template():
    data = request.json
    template = KanbanTemplate(
        name=data['name'],
        description=data.get('description', ''),
        columns_config=data.get('columns', []),
        fields_config=data.get('fields', []),
        created_by=session['user_id']
    )
    db.session.add(template)
    db.session.commit()
    return jsonify({'id': template.id})

@app.route('/api/kanban/templates/<int:template_id>', methods=['DELETE'])
@login_required
def delete_kanban_template(template_id):
    template = KanbanTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True})
    
@app.route('/api/kanban/cards', methods=['GET', 'POST'])
@login_required
def kanban_cards():
    if request.method == 'GET':
        # Получение всех карточек текущего проекта (или всех)
        project_id = request.args.get('project_id', type=int)
        if not project_id:
            return jsonify({'error': 'project_id required'}), 400
        cards = KanbanCard.query.filter_by(project_id=project_id).all()
        return jsonify([{
            'id': c.id,
            'projectId': c.project_id,
            'columnId': c.column_id,
            'data': c.data,
            'createdAt': c.created_at.isoformat(),
            'updatedAt': c.updated_at.isoformat(),
            'comments': [{
                'id': cm.id,
                'author': cm.author,
                'text': cm.text,
                'isUrgent': cm.is_urgent,
                'timestamp': cm.created_at.isoformat(),
                'files': [{'name': f.filename, 'url': url_for('download_kanban_file', file_id=f.id)} for f in cm.files]
            } for cm in c.comments]
        } for c in cards])
    
    elif request.method == 'POST':
        data = request.json
        project_id = data.get('projectId')
        column_id = data.get('columnId')
        card_data = data.get('data', {})
        if not project_id or not column_id:
            return jsonify({'error': 'projectId and columnId required'}), 400
        card = KanbanCard(project_id=project_id, column_id=column_id, data=card_data)
        db.session.add(card)
        db.session.commit()
        return jsonify({'id': card.id, 'data': card.data}), 201

# ============================================
# МАРШРУТЫ МОДУЛЯ "СКЛАД"
# ============================================

# Главная страница склада
@app.route('/warehouse')
@login_required
@module_access_required('warehouse')
def warehouse():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    low_stock_filter = request.args.get('low_stock', type=int)
    zero_stock_filter = request.args.get('zero_stock', type=int)
    
    query = StockItem.query
    
    if search_query:
        # Регистронезависимый поиск по частичному совпадению
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                StockItem.sku.like(search_pattern),
                StockItem.name.like(search_pattern),
                StockItem.description.like(search_pattern)
            )
        )
    
    # Фильтр низкого остатка
    if low_stock_filter:
        query = query.filter(
            StockItem.quantity <= StockItem.min_stock,
            StockItem.min_stock > 0
        )
    
    # Фильтр нулевого остатка
    if zero_stock_filter:
        query = query.filter(StockItem.quantity == 0)
    
    # Сортировка по названию
    items = query.order_by(StockItem.name).paginate(
        page=page,
        per_page=app.config['ITEMS_PER_PAGE'],
        error_out=False
    )
    
    # Статистика
    stats = {
        'total': StockItem.query.count(),
        'low_stock': StockItem.query.filter(
            StockItem.quantity <= StockItem.min_stock,
            StockItem.min_stock > 0
        ).count(),
        'zero_stock': StockItem.query.filter(StockItem.quantity == 0).count(),
        'total_value': db.session.query(db.func.sum(StockItem.quantity * StockItem.cost_price)).scalar() or 0
    }
    
    return render_template('warehouse.html',
                         items=items,
                         stats=stats,
                         search_query=search_query,
                         low_stock_filter=low_stock_filter,
                         zero_stock_filter=zero_stock_filter)

# Создание новой позиции
@app.route('/warehouse/create', methods=['GET', 'POST'])
@login_required
@permission_required('warehouse:write')
def create_stock_item():
    if request.method == 'POST':
        sku = request.form.get('sku')
        name = request.form.get('name')
        description = request.form.get('description')
        quantity = float(request.form.get('quantity', 0))
        unit = request.form.get('unit', 'шт')
        category = request.form.get('category')
        min_stock = float(request.form.get('min_stock', 0))
        location = request.form.get('location')
        
        # Проверяем уникальность SKU
        existing = StockItem.query.filter_by(sku=sku).first()
        if existing:
            flash(f'Позиция с артикулом {sku} уже существует!', 'error')
            return redirect(url_for('create_stock_item'))
        
        # Создаем позицию БЕЗ коммита
        item = StockItem(
            sku=sku,
            name=name,
            description=description,
            quantity=0,  # Сначала устанавливаем 0
            unit=unit,
            category=category,
            min_stock=min_stock,
            location=location
        )
        
        # Добавляем в сессию, но НЕ коммитим
        db.session.add(item)
        
        # Сразу делаем flush, чтобы получить id
        db.session.flush()
        
        # Создаем запись в истории если начальное количество > 0
        if quantity > 0:
            transaction = StockTransaction(
                stock_item_id=item.id,  # Теперь item.id существует
                transaction_type='in',
                quantity=quantity,
                before_quantity=0,
                after_quantity=quantity,
                document_number='Начальный остаток',
                document_type='Инициализация',
                notes='Начальный остаток при создании',
                user_id=session.get('username', 'admin')
            )
            db.session.add(transaction)
            
            # Обновляем количество позиции
            item.quantity = quantity
        
        # Теперь коммитим всё вместе
        db.session.commit()
        
        # Проверяем низкий остаток и отправляем уведомление
        if min_stock > 0 and quantity <= min_stock:
            check_low_stock_and_notify(item, 'Создание товара')
        
        flash(f'Позиция "{name}" успешно создана!', 'success')
        return redirect(url_for('warehouse'))
    
    # Генерация следующего SKU если не указан
    last_item = StockItem.query.order_by(StockItem.id.desc()).first()
    next_sku = f"SKU-{(last_item.id + 1 if last_item else 1):04d}" if not request.args.get('sku') else None
    
    return render_template('create_stock_item.html', next_sku=next_sku)

# Просмотр позиции
@app.route('/warehouse/<int:item_id>')
@login_required
def view_stock_item(item_id):
    item = StockItem.query.get_or_404(item_id)
    
    # Получаем историю операций
    transactions = StockTransaction.query.filter_by(stock_item_id=item_id)\
        .order_by(StockTransaction.created_at.desc())\
        .limit(50)\
        .all()
    
    return render_template('view_stock_item.html', 
                         item=item, 
                         transactions=transactions)

# Редактирование позиции
@app.route('/warehouse/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_stock_item(item_id):
    item = StockItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        old_quantity = item.quantity
        old_min_stock = item.min_stock
        
        item.sku = request.form.get('sku')
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        item.unit = request.form.get('unit', 'шт')
        item.category = request.form.get('category')
        
        # Получаем новое значение минимального запаса
        new_min_stock_str = request.form.get('min_stock')
        new_min_stock = float(new_min_stock_str) if new_min_stock_str else 0
        item.min_stock = new_min_stock
        
        item.location = request.form.get('location')
        
        db.session.commit()
        
        # Проверяем низкий остаток после изменения
        # Создаем запись в истории только если изменился минимальный запас
        if new_min_stock != old_min_stock:
            transaction = StockTransaction(
                stock_item_id=item.id,
                transaction_type='adjustment',
                quantity=0,
                before_quantity=old_quantity,
                after_quantity=item.quantity,
                document_number='Редактирование',
                document_type='Корректировка',
                notes=f'Изменен минимальный запас: {old_min_stock} → {new_min_stock}',
                user_id=session.get('username', 'admin')
            )
            db.session.add(transaction)
            db.session.commit()
        
        # Проверяем и отправляем уведомление если нужно
        check_low_stock_and_notify(item, 'Редактирование товара')
        
        flash(f'Позиция "{item.name}" обновлена!', 'success')
        return redirect(url_for('view_stock_item', item_id=item.id))
    
    return render_template('edit_stock_item.html', item=item)

# Операция прихода
@app.route('/warehouse/<int:item_id>/in', methods=['GET', 'POST'])
@login_required
def stock_in(item_id):
    item = StockItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        quantity = float(request.form.get('quantity', 0))
        document_number = request.form.get('document_number')
        document_type = request.form.get('document_type')
        counterparty_id = request.form.get('counterparty_id')
        notes = request.form.get('notes')
        
        if quantity <= 0:
            flash('Количество должно быть больше 0!', 'error')
            return redirect(url_for('stock_in', item_id=item_id))
        
        # Обновляем количество
        before_quantity = item.quantity
        item.quantity += quantity
        after_quantity = item.quantity
        
        # Создаем запись в истории
        transaction = StockTransaction(
            stock_item_id=item.id,  # item.id гарантированно существует
            transaction_type='in',
            quantity=quantity,
            before_quantity=before_quantity,
            after_quantity=after_quantity,
            document_number=document_number,
            document_type=document_type,
            counterparty_id=counterparty_id if counterparty_id else None,
            notes=notes,
            user_id=session.get('username', 'admin')
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # Проверяем низкий остаток после прихода и отправляем уведомление
        check_low_stock_and_notify(item, 'Приход товара')
        
        flash(f'Приход {quantity} {item.unit} на "{item.name}" зарегистрирован!', 'success')
        return redirect(url_for('view_stock_item', item_id=item.id))
    
    counterparties = Counterparty.query.order_by(Counterparty.name).all()
    return render_template('stock_operation.html', 
                         item=item, 
                         operation='in',
                         counterparties=counterparties,
                         title='Приход товара')

# Операция расхода
@app.route('/warehouse/<int:item_id>/out', methods=['GET', 'POST'])
@login_required
def stock_out(item_id):
    item = StockItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        quantity = float(request.form.get('quantity', 0))
        document_number = request.form.get('document_number')
        document_type = request.form.get('document_type')
        counterparty_id = request.form.get('counterparty_id')
        proposal_id = request.form.get('proposal_id')
        notes = request.form.get('notes')
        
        if quantity <= 0:
            flash('Количество должно быть больше 0!', 'error')
            return redirect(url_for('stock_out', item_id=item_id))
        
        if item.quantity < quantity:
            flash(f'Недостаточно товара! Доступно: {item.quantity} {item.unit}', 'error')
            return redirect(url_for('stock_out', item_id=item_id))
        
        # Обновляем количество
        before_quantity = item.quantity
        item.quantity -= quantity
        after_quantity = item.quantity
        
        # Создаем запись в истории
        transaction = StockTransaction(
            stock_item_id=item.id,
            transaction_type='out',
            quantity=quantity,
            before_quantity=before_quantity,
            after_quantity=after_quantity,
            document_number=document_number,
            document_type=document_type,
            counterparty_id=counterparty_id if counterparty_id else None,
            proposal_id=proposal_id if proposal_id else None,
            notes=notes,
            user_id=session.get('username', 'admin')
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # Проверяем низкий остаток после расхода и отправляем уведомление
        check_low_stock_and_notify(item, 'Расход товара')
        
        flash(f'Расход {quantity} {item.unit} с "{item.name}" зарегистрирован!', 'success')
        return redirect(url_for('view_stock_item', item_id=item.id))
    
    counterparties = Counterparty.query.order_by(Counterparty.name).all()
    proposals = Proposal.query.order_by(Proposal.created_at.desc()).limit(100).all()
    return render_template('stock_operation.html', 
                         item=item, 
                         operation='out',
                         counterparties=counterparties,
                         proposals=proposals,
                         title='Расход товара')

# Удаление позиции
@app.route('/warehouse/<int:item_id>/delete', methods=['POST'])
@login_required
@delete_permission_required()
@permission_required('warehouse:delete')
def delete_stock_item(item_id):
    item = StockItem.query.get_or_404(item_id)
    
    try:
        # Удаляем все связанные транзакции
        StockTransaction.query.filter_by(stock_item_id=item_id).delete()
        
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Ошибка при удалении позиции {item_id}: {e}')
        return jsonify({'success': False, 'error': str(e)})

# Импорт из Excel
@app.route('/warehouse/import', methods=['GET', 'POST'])
@login_required
def import_stock():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран!', 'error')
            return redirect(url_for('import_stock'))
        
        file = request.files['file']
        if file.filename == '':
            flash('Файл не выбран!', 'error')
            return redirect(url_for('import_stock'))
        
        if file and allowed_file(file.filename):
            try:
                # Определяем формат файла
                if file.filename.endswith('.xlsx'):
                    df = pd.read_excel(file)
                elif file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    flash('Неподдерживаемый формат файла!', 'error')
                    return redirect(url_for('import_stock'))
                
                # Проверяем необходимые колонки
                required_columns = ['sku', 'name', 'quantity']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    flash(f'Отсутствуют обязательные колонки: {", ".join(missing_columns)}', 'error')
                    return redirect(url_for('import_stock'))
                
                imported_count = 0
                updated_count = 0
                errors = []
                
                for index, row in df.iterrows():
                    try:
                        sku = str(row['sku']).strip()
                        name = str(row['name']).strip()
                        quantity = float(row['quantity']) if pd.notna(row['quantity']) else 0
                        
                        # Проверяем существование позиции
                        existing = StockItem.query.filter_by(sku=sku).first()
                        
                        if existing:
                            # Обновляем существующую
                            existing.name = name
                            existing.quantity = quantity
                            if 'description' in df.columns and pd.notna(row['description']):
                                existing.description = str(row['description']).strip()
                            if 'unit' in df.columns and pd.notna(row['unit']):
                                existing.unit = str(row['unit']).strip()
                            if 'category' in df.columns and pd.notna(row['category']):
                                existing.category = str(row['category']).strip()
                            if 'min_stock' in df.columns and pd.notna(row['min_stock']):
                                existing.min_stock = float(row['min_stock'])
                            if 'location' in df.columns and pd.notna(row['location']):
                                existing.location = str(row['location']).strip()
                            
                            # Проверяем низкий остаток
                            check_low_stock_and_notify(existing, 'Импорт из Excel')
                            
                            updated_count += 1
                        else:
                            # Создаем новую
                            item = StockItem(
                                sku=sku,
                                name=name,
                                quantity=quantity,
                                unit=str(row['unit']).strip() if 'unit' in df.columns and pd.notna(row['unit']) else 'шт',
                                category=str(row['category']).strip() if 'category' in df.columns and pd.notna(row['category']) else None,
                                description=str(row['description']).strip() if 'description' in df.columns and pd.notna(row['description']) else None,
                                min_stock=float(row['min_stock']) if 'min_stock' in df.columns and pd.notna(row['min_stock']) else 0,
                                location=str(row['location']).strip() if 'location' in df.columns and pd.notna(row['location']) else None
                            )
                            db.session.add(item)
                            
                            # Проверяем низкий остаток
                            check_low_stock_and_notify(item, 'Импорт из Excel')
                            
                            imported_count += 1
                            
                    except Exception as e:
                        errors.append(f"Строка {index + 2}: {str(e)}")
                
                db.session.commit()
                
                if errors:
                    flash(f'Импорт завершен с ошибками: {", ".join(errors[:5])}', 'warning')
                
                flash(f'Импорт завершен! Добавлено: {imported_count}, Обновлено: {updated_count}', 'success')
                return redirect(url_for('warehouse'))
                
            except Exception as e:
                flash(f'Ошибка при импорте: {str(e)}', 'error')
                return redirect(url_for('import_stock'))
        
        else:
            flash('Допустимые форматы: .xlsx, .csv', 'error')
            return redirect(url_for('import_stock'))
    
    return render_template('import_stock.html')

# Экспорт в Excel
@app.route('/warehouse/export')
@login_required
def export_stock():
    items = StockItem.query.order_by(StockItem.category, StockItem.name).all()
    
    # Создаем DataFrame
    data = []
    for item in items:
        data.append({
            'Артикул': item.sku,
            'Название': item.name,
            'Количество': item.quantity,
            'Единица': item.unit,
            'Категория': item.category or '',
            'Описание': item.description or '',
            'Мин. запас': item.min_stock,
            'Место хранения': item.location or '',
            'Себестоимость': item.cost_price or '',
            'Цена продажи': item.selling_price or '',
            'Дата создания': item.created_at.strftime('%d.%m.%Y %H:%M')
        })
    
    df = pd.DataFrame(data)
    
    # Создаем Excel файл в памяти
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Склад', index=False)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'stock_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )

# API для получения позиций по SKU
@app.route('/api/stock/search')
@login_required
def search_stock():
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return jsonify([])
    
    # ФИКС: Регистронезависимый поиск
    search_pattern = f"%{query}%"
    
    items = StockItem.query.filter(
        db.or_(
            StockItem.sku.like(search_pattern),
            StockItem.name.like(search_pattern)
        )
    ).limit(limit).all()
    
    result = [{
        'id': item.id,
        'sku': item.sku,
        'name': item.name,
        'quantity': item.quantity,
        'unit': item.unit,
        'location': item.location
    } for item in items]
    
    return jsonify(result)

# API для получения информации о позиции
@app.route('/api/stock/<int:item_id>')
@login_required
def get_stock_item(item_id):
    item = StockItem.query.get_or_404(item_id)
    
    return jsonify({
        'id': item.id,
        'sku': item.sku,
        'name': item.name,
        'quantity': item.quantity,
        'unit': item.unit,
        'category': item.category,
        'location': item.location,
        'min_stock': item.min_stock,
        'cost_price': item.cost_price,
        'selling_price': item.selling_price
    })

# Функция проверки расширения файла
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls', 'csv'}

# Выйти
@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))
    
    # Управление пользователями (только для администратора)
@app.route('/users')
@login_required
@permission_required('users:read')
def user_management():
    users = User.query.order_by(User.username).all()
    return render_template('users.html', users=users, ROLES=ROLES)

# Создание пользователя
@app.route('/users/create', methods=['GET', 'POST'])
@login_required
@permission_required('users:write')
def create_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        # Проверка совпадения паролей
        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('create_user'))
        
        # Проверка длины пароля
        if len(password) < 8:
            flash('Пароль должен содержать минимум 8 символов', 'error')
            return redirect(url_for('create_user'))
        
        # Проверка уникальности
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует', 'error')
            return redirect(url_for('create_user'))
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'error')
            return redirect(url_for('create_user'))
        
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'Пользователь {full_name or username} успешно создан', 'success')
        return redirect(url_for('user_management'))
    
    return render_template('create_user.html', ROLES=ROLES)


# Редактирование пользователя
@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('users:write')
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('user_management'))
    
    # Убрали проверку на редактирование самого себя
    # if user.id == session['user_id']:
    #     flash('Вы не можете редактировать свою учетную запись', 'error')
    #     return redirect(url_for('user_management'))
    
    if request.method == 'POST':
        user.email = request.form.get('email')
        user.full_name = request.form.get('full_name')
        
        # Только администратор может менять роль
        current_user_obj = db.session.get(User, session['user_id'])
        if current_user_obj.role == 'admin':
            user.role = request.form.get('role')
        
        user.is_active = bool(request.form.get('is_active'))
        
        password = request.form.get('password')
        if password:
            user.set_password(password)
        
        db.session.commit()
        
        # Если пользователь редактировал самого себя, обновляем данные в сессии
        if user.id == session['user_id']:
            session['full_name'] = user.full_name
            session['role'] = user.role
        
        flash(f'Данные пользователя {user.full_name} обновлены', 'success')
        return redirect(url_for('user_management'))
    
    return render_template('edit_user.html', user=user, ROLES=ROLES)

# Удаление пользователя
@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@permission_required('users:delete')
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Пользователь не найден'})
    
    # Нельзя удалить самого себя
    if user.id == session['user_id']:
        return jsonify({'success': False, 'error': 'Нельзя удалить свою учетную запись'})
    
    # Нельзя удалить последнего администратора
    if user.role == 'admin' and User.query.filter_by(role='admin').count() <= 1:
        return jsonify({'success': False, 'error': 'Нельзя удалить последнего администратора'})
    
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# API для получения контрагентов
@app.route('/api/counterparties')
@login_required
def get_counterparties():
    counterparties = Counterparty.query.order_by(Counterparty.name).all()
    result = [{'id': c.id, 'name': c.name} for c in counterparties]
    return jsonify(result)

# API для получения информации о контрагенте
@app.route('/api/counterparty/<int:id>')
@login_required
def get_counterparty(id):
    counterparty = Counterparty.query.get_or_404(id)
    return jsonify({
        'id': counterparty.id,
        'name': counterparty.name,
        'contact_person': counterparty.contact_person,
        'email': counterparty.email,
        'phone': counterparty.phone,
        'address': counterparty.address,
        'created_at': counterparty.created_at.isoformat() if counterparty.created_at else None
    })
        
@app.route('/warehouse/search/suggestions')
@login_required
def warehouse_search_suggestions():
    """API для получения подсказок при поиске товаров"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 1:
        return jsonify([])
    
    try:
        # ФИКС: Регистронезависимый поиск для SQLite
        search_pattern = f'%{query}%'
        
        items = StockItem.query.filter(
            db.or_(
                StockItem.sku.like(search_pattern),
                StockItem.name.like(search_pattern)
            )
        ).limit(10).all()
        
        suggestions = []
        for item in items:
            suggestions.append({
                'sku': item.sku,
                'name': item.name,
                'quantity': item.quantity,
                'unit': item.unit
            })
        
        return jsonify(suggestions)
        
    except Exception as e:
        app.logger.error(f'Ошибка при поиске подсказок: {e}')
        return jsonify([])

        
# API для получения следующего номера КП
@app.route('/api/proposals/next-number')
@login_required
def get_next_proposal_number():
    try:
        # Находим последний номер КП
        last_proposal = Proposal.query.filter(
            Proposal.proposal_number.isnot(None),
            Proposal.proposal_number != ''
        ).order_by(Proposal.id.desc()).first()
        
        if last_proposal and last_proposal.proposal_number:
            try:
                # Пытаемся извлечь число из номера
                import re
                match = re.search(r'(\d+)', last_proposal.proposal_number)
                if match:
                    last_number = int(match.group(1))
                    next_number = f"KP-{last_number + 1:04d}-{datetime.now().strftime('%d%m%Y')}"
                else:
                    next_number = f"KP-0001-{datetime.now().strftime('%d%m%Y')}"
            except:
                next_number = f"KP-0001-{datetime.now().strftime('%d%m%Y')}"
        else:
            next_number = f"KP-0001-{datetime.now().strftime('%d%m%Y')}"
            
        return jsonify({'next_number': next_number})
    except Exception as e:
        return jsonify({'next_number': f"KP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"})
        
# ============================================
# МАРШРУТЫ МОДУЛЯ "ШВЕЙКА"
# ============================================

# Главная страница швейки
@app.route('/sewing')
@login_required
@module_access_required('sewing')
def sewing():
    """Главная страница модуля Швейка"""
    # Статистика
    stats = {
        'total_tasks': SewingTask.query.count(),
        'new_tasks': SewingTask.query.filter_by(status='Новая').count(),
        'in_progress_tasks': SewingTask.query.filter_by(status='В работе').count(),
        'completed_tasks': SewingTask.query.filter_by(status='Исполнено').count(),
        'active_material_requests': MaterialRequest.query.filter_by(status='В работе').count(),
    }
    
    # Последние задачи
    recent_tasks = SewingTask.query.order_by(SewingTask.created_at.desc()).limit(5).all()
    
    # Активные запросы материалов
    active_requests = MaterialRequest.query.filter_by(status='В работе').order_by(
        MaterialRequest.created_at.desc()
    ).limit(5).all()
    
    return render_template('sewing.html', 
                         stats=stats,
                         recent_tasks=recent_tasks,
                         active_requests=active_requests)

# Создание задачи
@app.route('/sewing/task/create', methods=['GET', 'POST'])
@login_required
@permission_required('sewing:write')
def create_sewing_task():
    """Создание новой задачи швейного производства"""
    
    # Получаем КП со статусом "В работе" для выпадающего списка
    active_proposals = Proposal.query.filter_by(status='В работе').order_by(
        Proposal.created_at.desc()
    ).all()
    
    if request.method == 'POST':
        task_name = request.form.get('task_name')
        proposal_id = request.form.get('proposal_id')
        shipment_date_str = request.form.get('shipment_date')
        product_name = request.form.get('product_name')
        product_size = request.form.get('product_size')
        quantity = float(request.form.get('quantity', 1))
        color = request.form.get('color')
        notes = request.form.get('notes')
        
        # Преобразование даты отгрузки
        shipment_date = None
        if shipment_date_str:
            try:
                shipment_date = datetime.strptime(shipment_date_str, '%Y-%m-%d').date()
            except:
                pass
        
        # Инициализируем proposal как None
        proposal = None
        
        # Если выбрано КП, получаем его данные
        if proposal_id and proposal_id != 'none':
            proposal = Proposal.query.get(proposal_id)
            if proposal:
                # Автозаполнение даты отгрузки из КП, если не указана
                if not shipment_date and proposal.deadline:
                    shipment_date = proposal.deadline
                # Автозаполнение названия из КП, если не указано
                if not task_name:
                    task_name = f"Заказ по КП: {proposal.title}"
        
        # Убедимся, что task_name есть (если все еще None, задаем дефолтное значение)
        if not task_name:
            task_name = f"Задача от {datetime.now().strftime('%d.%m.%Y')}"
        
        # Создаем задачу
        task = SewingTask(
            task_name=task_name,
            proposal_id=proposal_id if proposal_id and proposal_id != 'none' else None,
            shipment_date=shipment_date,
            product_name=product_name,
            product_size=product_size,
            quantity=quantity,
            color=color,
            notes=notes,
            created_by=session.get('username', 'admin'),
            status='Новая'
        )
        
        db.session.add(task)
        db.session.commit()
        
        # Отправляем уведомление в Telegram о создании задачи
        telegram_message = f"🆕 <b>НОВАЯ ЗАДАЧА ШВЕЙНОГО ЦЕХА</b>\n\n"
        telegram_message += f"<b>Задача:</b> {task_name}\n"
        
        if proposal:
            telegram_message += f"<b>КП:</b> {proposal.title}\n"
        
        telegram_message += f"<b>Изделие:</b> {product_name}\n"
        telegram_message += f"<b>Количество:</b> {quantity} шт.\n"
        
        if color:
            telegram_message += f"<b>Цвет:</b> {color}\n"
        
        if shipment_date:
            telegram_message += f"<b>Дата отгрузки:</b> {shipment_date.strftime('%d.%m.%Y')}\n"
        
        telegram_message += f"<b>Статус:</b> Новая\n"
        telegram_message += f"<b>Создал:</b> {session.get('username', 'admin')}\n"
        telegram_message += f"<b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        
        # Добавляем ссылку на задачу
        base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
        task_url = f"{base_url}/sewing/task/{task.id}"
        telegram_message += f"\n🔗 <a href='{task_url}'>Перейти к задаче</a>"
        
        # Отправляем уведомление в основной чат (или в специальный чат швейки)
        send_telegram_notification_to_chat(telegram_message, app.config.get('TELEGRAM_SEWING_CHAT_ID'))
        
        flash(f'Задача "{task_name}" успешно создана! Уведомление отправлено в Telegram.', 'success')
        return redirect(url_for('view_sewing_task', task_id=task.id))
    
    return render_template('create_sewing_task.html', 
                         active_proposals=active_proposals)

# Просмотр задачи
@app.route('/sewing/task/<int:task_id>')
@login_required
def view_sewing_task(task_id):
    """Просмотр задачи швейного производства"""
    task = SewingTask.query.get_or_404(task_id)
    
    # Получаем связанные запросы материалов
    material_requests = MaterialRequest.query.filter_by(sewing_task_id=task_id).order_by(
        MaterialRequest.created_at.desc()
    ).all()
    
    return render_template('view_sewing_task.html',
                         task=task,
                         material_requests=material_requests)

# Обновление статуса задачи
@app.route('/sewing/task/<int:task_id>/update_status', methods=['POST'])
@login_required
def update_sewing_task_status(task_id):
    """Обновление статуса задачи швейного производства"""
    task = SewingTask.query.get_or_404(task_id)
    new_status = request.json.get('status')
    notes = request.json.get('notes', '')
    
    if new_status in ['Новая', 'В работе', 'Исполнено']:
        old_status = task.status
        task.status = new_status
        task.updated_at = datetime.now(timezone.utc)
        
        # Если статус изменился на "Исполнено"
        if new_status == 'Исполнено' and old_status != 'Исполнено':
            task.completed_at = datetime.now(timezone.utc)
            
            # Отправляем уведомление в Telegram
            telegram_message = f"✅ <b>ЗАДАЧА ИСПОЛНЕНА</b>\n\n"
            telegram_message += f"<b>Задача:</b> {task.task_name}\n"
            
            if task.proposal:
                telegram_message += f"<b>КП:</b> {task.proposal.title}\n"
            
            telegram_message += f"<b>Изделие:</b> {task.product_name}\n"
            telegram_message += f"<b>Количество:</b> {task.quantity} шт.\n"
            
            if task.color:
                telegram_message += f"<b>Цвет:</b> {task.color}\n"
            
            telegram_message += f"<b>Статус:</b> {old_status} → {new_status}\n"
            telegram_message += f"<b>Исполнитель:</b> {session.get('username', 'admin')}\n"
            
            if notes:
                telegram_message += f"<b>Примечание:</b> {notes}\n"
            
            telegram_message += f"<b>Время исполнения:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            
            # Добавляем ссылку на задачу
            base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
            task_url = f"{base_url}/sewing/task/{task.id}"
            telegram_message += f"\n🔗 <a href='{task_url}'>Перейти к задаче</a>"
            
            send_telegram_notification_to_chat(telegram_message, app.config.get('TELEGRAM_SEWING_CHAT_ID'))
        
        # Если добавили примечание
        if notes:
            if task.notes:
                task.notes += f"\n--- {datetime.now().strftime('%d.%m.%Y %H:%M')} ---\n{notes}"
            else:
                task.notes = f"--- {datetime.now().strftime('%d.%m.%Y %H:%M')} ---\n{notes}"
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'new_status': new_status,
            'completed_at': task.completed_at.strftime('%d.%m.%Y %H:%M') if task.completed_at else None
        })
    
    return jsonify({'success': False, 'error': 'Неверный статус'})
    
# Список задач
@app.route('/sewing/tasks')
@login_required
def sewing_tasks():
    """Список всех задач швейного производства"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    
    query = SewingTask.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(
            db.or_(
                SewingTask.task_name.contains(search_query),
                SewingTask.product_name.contains(search_query),
                SewingTask.product_size.contains(search_query)
            )
        )
    
    # Сортировка по дате создания (новые сверху)
    tasks = query.order_by(SewingTask.created_at.desc()).paginate(
        page=page, 
        per_page=app.config['ITEMS_PER_PAGE'],
        error_out=False
    )
    
    return render_template('sewing_tasks.html',
                         tasks=tasks,
                         status_filter=status_filter,
                         search_query=search_query)

# Создание запроса материала
@app.route('/sewing/material_request/create', methods=['GET', 'POST'])
@login_required
def create_material_request():
    """Создание запроса материала"""
    
    # Получаем активные задачи для привязки
    active_tasks = SewingTask.query.filter(
        SewingTask.status.in_(['Новая', 'В работе'])
    ).order_by(SewingTask.created_at.desc()).all()
    
    if request.method == 'POST':
        material = request.form.get('material')
        quantity = request.form.get('quantity')
        color = request.form.get('color')
        size = request.form.get('size')
        sewing_task_id = request.form.get('sewing_task_id')
        notes = request.form.get('notes')
        
        # Проверяем обязательные поля
        if not material:
            flash('Поле "Материал" обязательно для заполнения!', 'error')
            return redirect(url_for('create_material_request'))
        
        if not quantity:
            flash('Поле "Количество" обязательно для заполнения!', 'error')
            return redirect(url_for('create_material_request'))
        
        try:
            quantity_float = float(quantity)
        except ValueError:
            flash('Количество должно быть числом!', 'error')
            return redirect(url_for('create_material_request'))
        
        # Создаем запрос
        request_obj = MaterialRequest(
            material=material,
            quantity=quantity_float,
            color=color if color else None,
            size=size if size else None,
            sewing_task_id=sewing_task_id if sewing_task_id and sewing_task_id != 'none' else None,
            notes=notes if notes else None,
            created_by=session.get('username', 'admin'),
            status='В работе'
        )
        
        db.session.add(request_obj)
        db.session.commit()
        
        # Отправляем уведомление в Telegram чат "ЕКО-Швейка"
        telegram_message = f"🆕 <b>НОВЫЙ ЗАПРОС МАТЕРИАЛА</b>\n\n"
        telegram_message += f"<b>Материал:</b> {material}\n"
        telegram_message += f"<b>Количество:</b> {quantity_float}\n"
        
        if color:
            telegram_message += f"<b>Цвет:</b> {color}\n"
        if size:
            telegram_message += f"<b>Размеры:</b> {size}\n"
        
        if sewing_task_id and sewing_task_id != 'none':
            task = SewingTask.query.get(sewing_task_id)
            if task:
                telegram_message += f"<b>Задача:</b> {task.task_name}\n"
        
        if notes:
            telegram_message += f"<b>Примечание:</b> {notes}\n"
        
        telegram_message += f"\n👤 <b>Запросил:</b> {session.get('username', 'admin')}"
        telegram_message += f"\n📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        # Отправляем в специальный чат для швейки
        telegram_sent = send_telegram_notification_to_chat(telegram_message, app.config.get('TELEGRAM_SEWING_CHAT_ID'))
        
        if telegram_sent:
            # Сохраняем время отправки
            request_obj.telegram_sent_at = datetime.now(timezone.utc)
            db.session.commit()
        
        flash(f'Запрос материала "{material}" создан и отправлен в Telegram!', 'success')
        return redirect(url_for('material_requests'))
    
    return render_template('create_material_request.html',
                         active_tasks=active_tasks)
                         
@app.route('/sewing/material_request/<int:request_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_material_request(request_id):
    """Редактирование запроса материала"""
    request_obj = MaterialRequest.query.get_or_404(request_id)
    
    # Получаем активные задачи для привязки
    active_tasks = SewingTask.query.filter(
        SewingTask.status.in_(['Новая', 'В работе'])
    ).order_by(SewingTask.created_at.desc()).all()
    
    if request.method == 'POST':
        material = request.form.get('material')
        quantity = float(request.form.get('quantity', 1))
        color = request.form.get('color')
        size = request.form.get('size')
        sewing_task_id = request.form.get('sewing_task_id')
        notes = request.form.get('notes')
        status = request.form.get('status')
        
        # Обновляем запрос
        old_status = request_obj.status
        request_obj.material = material
        request_obj.quantity = quantity
        request_obj.color = color
        request_obj.size = size
        request_obj.sewing_task_id = sewing_task_id if sewing_task_id and sewing_task_id != 'none' else None
        request_obj.notes = notes
        
        # Если статус изменился, обновляем
        if status and status in ['В работе', 'Исполнено']:
            request_obj.status = status
        
        request_obj.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        # Отправляем уведомление в Telegram если статус изменился
        if old_status != request_obj.status:
            message = f"🔄 <b>ИЗМЕНЕНИЕ СТАТУСА ЗАПРОСА</b>\n\n"
            message += f"<b>Материал:</b> {material}\n"
            message += f"<b>Количество:</b> {quantity}\n"
            message += f"<b>Статус:</b> {old_status} → {request_obj.status}\n"
            
            if sewing_task_id and sewing_task_id != 'none':
                task = SewingTask.query.get(sewing_task_id)
                if task:
                    message += f"<b>Задача:</b> {task.task_name}\n"
            
            if notes:
                message += f"<b>Примечание:</b> {notes}\n"
            
            message += f"\n👤 <b>Изменил:</b> {session.get('username', 'admin')}"
            message += f"\n📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            send_telegram_notification_to_chat(message, SEWING_TELEGRAM_CHAT_ID)
        
        flash(f'Запрос материала "{material}" обновлен!', 'success')
        
        # Возвращаем редирект
        if request_obj.sewing_task_id:
            return redirect(url_for('view_sewing_task', task_id=request_obj.sewing_task_id))
        else:
            return redirect(url_for('material_requests'))
    
    # GET запрос - отображаем форму
    return render_template('edit_material_request.html',
                         request=request_obj,
                         active_tasks=active_tasks)

# Функция для отправки в конкретный чат Telegram
def send_telegram_notification_to_chat(message, chat_id=None):
    """
    Отправляет сообщение в указанный чат Telegram или в чат по умолчанию
    """
    try:
        token = app.config.get('TELEGRAM_BOT_TOKEN')
        
        if not token:
            print("Telegram token не настроен")
            return False
        
        # Используем chat_id из параметра или из конфигурации
        if chat_id:
            target_chat_id = chat_id
        else:
            # Если указан чат швейки, используем его, иначе основной чат
            target_chat_id = app.config.get('TELEGRAM_SEWING_CHAT_ID', app.config.get('TELEGRAM_CHAT_ID'))
        
        if not target_chat_id:
            print("Telegram chat_id не настроен")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': target_chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"Telegram уведомление отправлено в чат {target_chat_id}")
            return True
        else:
            print(f"Ошибка отправки в Telegram: {response.status_code}")
            return False
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False

# Обновление статуса запроса материала
@app.route('/sewing/material_request/<int:request_id>/update_status', methods=['POST'])
@login_required
def update_material_request_status(request_id):
    """Обновление статуса запроса материала"""
    request_obj = MaterialRequest.query.get_or_404(request_id)
    new_status = request.json.get('status')
    notes = request.json.get('notes', '')
    
    if new_status in ['В работе', 'Исполнено']:
        old_status = request_obj.status
        request_obj.status = new_status
        request_obj.updated_at = datetime.now(timezone.utc)
        
        # Если добавили примечание
        if notes:
            if request_obj.notes:
                request_obj.notes += f"\n--- {datetime.now().strftime('%d.%m.%Y %H:%M')} ---\n{notes}"
            else:
                request_obj.notes = f"--- {datetime.now().strftime('%d.%m.%Y %H:%M')} ---\n{notes}"
        
        db.session.commit()
        
        # Отправляем уведомление в Telegram при смене статуса
        if old_status != new_status:
            # Создаем сообщение для Telegram
            telegram_message = f"🔄 <b>ИЗМЕНЕНИЕ СТАТУСА ЗАПРОСА</b>\n\n"
            telegram_message += f"<b>Материал:</b> {request_obj.material}\n"
            telegram_message += f"<b>Количество:</b> {request_obj.quantity}\n"
            telegram_message += f"<b>Статус:</b> {old_status} → {new_status}\n"
            
            if request_obj.sewing_task:
                telegram_message += f"<b>Задача:</b> {request_obj.sewing_task.task_name}\n"
            
            if notes:
                telegram_message += f"<b>Примечание:</b> {notes}\n"
            
            telegram_message += f"\n👤 <b>Изменил:</b> {session.get('username', 'admin')}"
            telegram_message += f"\n📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            # Добавляем ссылку на задачу, если есть
            if request_obj.sewing_task:
                base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
                task_url = f"{base_url}/sewing/task/{request_obj.sewing_task.id}"
                telegram_message += f"\n🔗 <a href='{task_url}'>Перейти к задаче</a>"
            
            # Отправляем в чат швейки
            send_telegram_notification_to_chat(telegram_message, app.config.get('TELEGRAM_SEWING_CHAT_ID'))
        
        return jsonify({
            'success': True, 
            'new_status': new_status
        })
    
    return jsonify({'success': False, 'error': 'Неверный статус'})

# Список запросов материалов
@app.route('/sewing/material_requests')
@login_required
def material_requests():
    """Список запросов материалов"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    
    query = MaterialRequest.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(
            db.or_(
                MaterialRequest.material.contains(search_query),
                MaterialRequest.color.contains(search_query)
            )
        )
    
    # Сортировка по дате создания (новые сверху)
    requests = query.order_by(MaterialRequest.created_at.desc()).paginate(
        page=page, 
        per_page=app.config['ITEMS_PER_PAGE'],
        error_out=False
    )
    
    return render_template('material_requests.html',
                         requests=requests,
                         status_filter=status_filter,
                         search_query=search_query)

# Удаление задачи
@app.route('/sewing/task/<int:task_id>/delete', methods=['POST'])
@login_required
@delete_permission_required()
@permission_required('sewing:delete')
def delete_sewing_task(task_id):
    """Удаление задачи швейного производства"""
    task = SewingTask.query.get_or_404(task_id)
    
    try:
        # Удаляем связанные запросы материалов
        MaterialRequest.query.filter_by(sewing_task_id=task_id).delete()
        
        db.session.delete(task)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Ошибка при удалении задачи {task_id}: {e}')
        return jsonify({'success': False, 'error': str(e)})

# Удаление запроса материала
@app.route('/sewing/material_request/<int:request_id>/delete', methods=['POST'])
@login_required
def delete_material_request(request_id):
    """Удаление запроса материала"""
    request_obj = MaterialRequest.query.get_or_404(request_id)
    
    try:
        db.session.delete(request_obj)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Ошибка при удалении запроса материала {request_id}: {e}')
        return jsonify({'success': False, 'error': str(e)})     

# Редактирование задачи
@app.route('/sewing/task/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sewing_task(task_id):
    """Редактирование задачи швейного производства"""
    task = SewingTask.query.get_or_404(task_id)
    
    # Получаем КП со статусом "В работе" для выпадающего списка
    active_proposals = Proposal.query.filter_by(status='В работе').order_by(
        Proposal.created_at.desc()
    ).all()
    
    if request.method == 'POST':
        task.task_name = request.form.get('task_name')
        proposal_id = request.form.get('proposal_id')
        shipment_date_str = request.form.get('shipment_date')
        task.product_name = request.form.get('product_name')
        task.product_size = request.form.get('product_size')
        task.quantity = float(request.form.get('quantity', 1))
        task.color = request.form.get('color')
        task.notes = request.form.get('notes')
        
        # Обработка proposal_id
        if proposal_id and proposal_id != 'none':
            task.proposal_id = proposal_id
        else:
            task.proposal_id = None
        
        # Преобразование даты отгрузки
        if shipment_date_str:
            try:
                task.shipment_date = datetime.strptime(shipment_date_str, '%Y-%m-%d').date()
            except:
                task.shipment_date = None
        else:
            task.shipment_date = None
        
        task.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        flash(f'Задача "{task.task_name}" успешно обновлена!', 'success')
        return redirect(url_for('view_sewing_task', task_id=task.id))
    
    # Преобразование даты для отображения в форме
    shipment_date_str = task.shipment_date.strftime('%Y-%m-%d') if task.shipment_date else ''
    
    return render_template('edit_sewing_task.html', 
                         task=task,
                         active_proposals=active_proposals,
                         shipment_date_str=shipment_date_str)

# Добавляем контекстные процессоры - они должны быть на уровне с другими декораторами
@app.context_processor
def inject_user_and_permissions():
    def get_current_user():
        if 'user_id' in session:
            return db.session.get(User, session['user_id'])
        return None
    
    current_user = get_current_user()
    
    return dict(
        current_user=current_user,
        has_permission=lambda perm: current_user.has_permission(perm) if current_user else False,
        has_module_access=lambda module: current_user.has_module_access(module) if current_user else False,
        can_delete=lambda: current_user.can_delete() if current_user else False,
        ROLES=ROLES
    )
    
    # ============================================
# МОДУЛЬ "ЗАКАЗЫ" - МОДЕЛИ И МАРШРУТЫ
# ============================================

# Модели для заказов
class Order(db.Model):
    """Заказ на материалы и расходники"""
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(100), unique=True, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    manager_name = db.Column(db.String(200))
    status = db.Column(db.String(50), default='размещен', index=True)  # размещен, в работе, исполнено
    request_invoice = db.Column(db.Boolean, default=False)  # Запрос счета
    invoice_path = db.Column(db.String(500))  # Путь к счету
    invoice_file_name = db.Column(db.String(300))
    total_items = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    telegram_message_id = db.Column(db.String(100))
    telegram_sent_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), index=True)
    completed_at = db.Column(db.DateTime)
    
    # Связи
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    manager_user = db.relationship('User', foreign_keys=[manager_id])
    
    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(db.Model):
    """Позиция в заказе"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    name = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    link = db.Column(db.String(500))
    photo = db.Column(db.String(300))
    workshop = db.Column(db.String(100))
    category = db.Column(db.String(50))  # на склад, расходники
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<OrderItem {self.name} ({self.quantity})>'

# Функция для отправки уведомлений в указанный чат Telegram
def send_telegram_order_notification(message, chat_id="-1003770806206"):
    """Отправляет уведомление о заказе в указанный чат Telegram"""
    try:
        token = app.config.get('TELEGRAM_BOT_TOKEN')
        
        if not token:
            print("Telegram token не настроен")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            message_id = data.get('result', {}).get('message_id')
            print(f"Telegram уведомление отправлено в чат {chat_id}")
            return message_id
        else:
            print(f"Ошибка отправки в Telegram: {response.status_code}")
            return False
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False

# Генерация номера заказа
def generate_order_number():
    """Генерирует уникальный номер заказа"""
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    
    # Находим последний заказ за сегодня
    last_order = Order.query.filter(Order.order_number.like(f'ORD-{today}-%')).order_by(
        Order.id.desc()
    ).first()
    
    if last_order and last_order.order_number:
        try:
            last_num = int(last_order.order_number.split('-')[-1])
            next_num = last_num + 1
        except:
            next_num = 1
    else:
        next_num = 1
    
    return f"ORD-{today}-{next_num:03d}"

# ============================================
# МАРШРУТЫ МОДУЛЯ "ЗАКАЗЫ"
# ============================================

# Главная страница заказов
@app.route('/orders')
@login_required
@module_access_required('orders')
def orders():
    """Список всех заказов"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    
    query = Order.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(
            db.or_(
                Order.order_number.contains(search_query),
                Order.manager_name.contains(search_query)
            )
        )
    
    # Сортировка по дате создания (новые сверху)
    orders_list = query.order_by(Order.created_at.desc()).paginate(
        page=page, 
        per_page=app.config['ITEMS_PER_PAGE'],
        error_out=False
    )
    
    # Статистика
    stats = {
        'total': Order.query.count(),
        'placed': Order.query.filter_by(status='размещен').count(),
        'in_work': Order.query.filter_by(status='в работе').count(),
        'completed': Order.query.filter_by(status='исполнено').count(),
    }
    
    return render_template('orders.html',
                         orders=orders_list,
                         stats=stats,
                         status_filter=status_filter,
                         search_query=search_query)

# Создание заказа
@app.route('/orders/create', methods=['GET', 'POST'])
@login_required
def create_order():
    """Создание нового заказа"""
    if request.method == 'POST':
        try:
            # Создаем заказ
            order_number = generate_order_number()
            order = Order(
                order_number=order_number,
                created_by=session['user_id'],
                manager_name=request.form.get('manager_name', ''),
                notes=request.form.get('notes', ''),
                total_items=0  # Будет обновлено после добавления позиций
            )
            
            db.session.add(order)
            db.session.flush()  # Получаем ID заказа
            
            # Обрабатываем позиции заказа
            items_data = request.form.getlist('items[]')
            names = request.form.getlist('item_name[]')
            quantities = request.form.getlist('item_quantity[]')
            links = request.form.getlist('item_link[]')
            workshops = request.form.getlist('item_workshop[]')
            categories = request.form.getlist('item_category[]')
            photos = request.files.getlist('item_photo[]')
            
            item_count = 0
            
            for i in range(len(names)):
                name = names[i].strip()
                quantity_str = quantities[i].strip()
                
                if name and quantity_str:
                    try:
                        quantity = float(quantity_str)
                        if quantity <= 0:
                            continue
                    except ValueError:
                        continue
                    
                    # Обработка фото
                    photo_filename = None
                    photo = photos[i] if i < len(photos) else None
                    if photo and photo.filename:
                        filename = secure_filename(photo.filename)
                        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                        filename = f"{order.id}_{timestamp}_{filename}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'orders', filename)
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        photo.save(file_path)
                        photo_filename = filename
                    
                    # Создаем позицию
                    order_item = OrderItem(
                        order_id=order.id,
                        name=name,
                        quantity=quantity,
                        link=links[i].strip() if i < len(links) else '',
                        workshop=workshops[i].strip() if i < len(workshops) else '',
                        category=categories[i] if i < len(categories) else 'расходники',
                        photo=photo_filename
                    )
                    
                    db.session.add(order_item)
                    item_count += 1
            
            if item_count == 0:
                db.session.rollback()
                flash('Добавьте хотя бы одну позицию в заказ!', 'error')
                return redirect(url_for('create_order'))
            
            order.total_items = item_count
            db.session.commit()
            
            # Отправляем уведомление в Telegram
            telegram_message = f"🆕 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
            telegram_message += f"<b>Номер заказа:</b> {order_number}\n"
            telegram_message += f"<b>Количество позиций:</b> {item_count}\n"
            
            if order.manager_name:
                telegram_message += f"<b>Менеджер:</b> {order.manager_name}\n"
            
            if order.notes:
                telegram_message += f"<b>Примечание:</b> {order.notes[:100]}...\n"
            
            telegram_message += f"<b>Статус:</b> размещен\n"
            telegram_message += f"<b>Создал:</b> {session.get('full_name', session.get('username', 'admin'))}\n"
            telegram_message += f"<b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            
            # Добавляем первые 3 позиции в уведомление
            telegram_message += f"<b>Позиции:</b>\n"
            first_items = order.items[:3]
            for idx, item in enumerate(first_items, 1):
                telegram_message += f"{idx}. {item.name} - {item.quantity} {item.category}\n"
            
            if item_count > 3:
                telegram_message += f"... и еще {item_count - 3} позиций\n"
            
            # Добавляем ссылку на заказ
            base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
            order_url = f"{base_url}/orders/{order.id}"
            telegram_message += f"\n🔗 <a href='{order_url}'>Перейти к заказу</a>"
            
            # Отправляем уведомление
            message_id = send_telegram_order_notification(telegram_message)
            if message_id:
                order.telegram_message_id = str(message_id)
                order.telegram_sent_at = datetime.now(timezone.utc)
                db.session.commit()
            
            flash(f'Заказ {order_number} успешно создан! Уведомление отправлено в Telegram.', 'success')
            return redirect(url_for('view_order', order_id=order.id))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Ошибка создания заказа: {e}')
            flash(f'Ошибка создания заказа: {str(e)}', 'error')
            return redirect(url_for('create_order'))
    
    return render_template('create_order.html')

# Просмотр заказа
@app.route('/orders/<int:order_id>')
@login_required
def view_order(order_id):
    """Просмотр деталей заказа"""
    order = Order.query.get_or_404(order_id)
    
    # Получаем всех пользователей для назначения менеджера
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    
    return render_template('view_order.html',
                         order=order,
                         users=users)

# Обновление статуса заказа
@app.route('/orders/<int:order_id>/update_status', methods=['POST'])
@login_required
def update_order_status(order_id):
    """Обновление статуса заказа"""
    order = Order.query.get_or_404(order_id)
    new_status = request.json.get('status')
    notes = request.json.get('notes', '')
    manager_id = request.json.get('manager_id')
    request_invoice = request.json.get('request_invoice', False)
    
    if new_status in ['размещен', 'в работе', 'исполнено']:
        old_status = order.status
        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)
        
        # Обновляем менеджера если указан
        if manager_id:
            manager = User.query.get(manager_id)
            if manager:
                order.manager_id = manager.id
                order.manager_name = manager.full_name or manager.username
        
        # Запрос счета при смене статуса на "в работе"
        if new_status == 'в работе' and request_invoice:
            order.request_invoice = True
            notes += "\n[Запрошен счет]"
        
        # Если статус изменился на "исполнено"
        if new_status == 'исполнено' and old_status != 'исполнено':
            order.completed_at = datetime.now(timezone.utc)
            
            # Создаем позиции на складе для товаров категории "на склад"
            for item in order.items:
                if item.category == 'на склад':
                    # Проверяем существование товара на складе
                    existing_item = StockItem.query.filter_by(name=item.name).first()
                    
                    if existing_item:
                        # Обновляем количество
                        before_quantity = existing_item.quantity
                        existing_item.quantity += item.quantity
                        after_quantity = existing_item.quantity
                        
                        # Создаем запись в истории
                        transaction = StockTransaction(
                            stock_item_id=existing_item.id,
                            transaction_type='in',
                            quantity=item.quantity,
                            before_quantity=before_quantity,
                            after_quantity=after_quantity,
                            document_number=order.order_number,
                            document_type='Заказ',
                            notes=f'Автоматическое создание из заказа {order.order_number}',
                            user_id=session.get('username', 'admin')
                        )
                        db.session.add(transaction)
                        
                        # Проверяем низкий остаток
                        check_low_stock_and_notify(existing_item, 'Заказ выполнен')
                    else:
                        # Создаем новую позицию
                        sku = f"ORD-{order.id}-{item.id}"
                        stock_item = StockItem(
                            sku=sku,
                            name=item.name,
                            quantity=item.quantity,
                            unit='шт',
                            category='Из заказа',
                            min_stock=0,
                            location='Основной склад',
                            created_at=datetime.now(timezone.utc)
                        )
                        db.session.add(stock_item)
                        db.session.flush()
                        
                        # Создаем запись в истории
                        transaction = StockTransaction(
                            stock_item_id=stock_item.id,
                            transaction_type='in',
                            quantity=item.quantity,
                            before_quantity=0,
                            after_quantity=item.quantity,
                            document_number=order.order_number,
                            document_type='Заказ',
                            notes=f'Создание из заказа {order.order_number}',
                            user_id=session.get('username', 'admin')
                        )
                        db.session.add(transaction)
        
        # Если добавили примечание
        if notes:
            if order.notes:
                order.notes += f"\n--- {datetime.now().strftime('%d.%m.%Y %H:%M')} ---\n{notes}"
            else:
                order.notes = f"--- {datetime.now().strftime('%d.%m.%Y %H:%M')} ---\n{notes}"
        
        db.session.commit()
        
        # Отправляем уведомление в Telegram при смене статуса
        if old_status != new_status:
            telegram_message = f"🔄 <b>ИЗМЕНЕНИЕ СТАТУСА ЗАКАЗА</b>\n\n"
            telegram_message += f"<b>Номер заказа:</b> {order.order_number}\n"
            telegram_message += f"<b>Статус:</b> {old_status} → {new_status}\n"
            
            if order.manager_name:
                telegram_message += f"<b>Менеджер:</b> {order.manager_name}\n"
            
            if notes:
                telegram_message += f"<b>Примечание:</b> {notes}\n"
            
            if new_status == 'в работе' and order.request_invoice:
                telegram_message += f"\n⚠️ <b>Требуется счет!</b>\n"
            
            telegram_message += f"\n👤 <b>Изменил:</b> {session.get('full_name', session.get('username', 'admin'))}"
            telegram_message += f"\n📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            # Добавляем ссылку на заказ
            base_url = request.host_url.rstrip('/') if request else 'http://localhost:5000'
            order_url = f"{base_url}/orders/{order.id}"
            telegram_message += f"\n🔗 <a href='{order_url}'>Перейти к заказу</a>"
            
            send_telegram_order_notification(telegram_message)
        
        return jsonify({
            'success': True, 
            'new_status': new_status,
            'manager_name': order.manager_name,
            'completed_at': order.completed_at.strftime('%d.%m.%Y %H:%M') if order.completed_at else None,
            'request_invoice': order.request_invoice
        })
    
    return jsonify({'success': False, 'error': 'Неверный статус'})

# Загрузка счета
@app.route('/orders/<int:order_id>/upload_invoice', methods=['POST'])
@login_required
def upload_order_invoice(order_id):
    """Загрузка счета для заказа"""
    order = Order.query.get_or_404(order_id)
    
    if 'invoice_file' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не выбран'})
    
    file = request.files['invoice_file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'})
    
    # Удаляем старый файл если есть
    if order.invoice_path and os.path.exists(order.invoice_path):
        os.remove(order.invoice_path)
    
    # Сохраняем новый файл
    filename = secure_filename(file.filename)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"invoice_{order.order_number}_{timestamp}_{filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'invoices', filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    file.save(file_path)
    
    order.invoice_path = file_path
    order.invoice_file_name = file.filename
    order.request_invoice = False  # Снимаем флаг запроса
    db.session.commit()
    
    # Отправляем уведомление в Telegram
    telegram_message = f"📄 <b>СЧЕТ ПРИКРЕПЛЕН</b>\n\n"
    telegram_message += f"<b>Номер заказа:</b> {order.order_number}\n"
    telegram_message += f"<b>Файл:</b> {file.filename}\n"
    telegram_message += f"\n👤 <b>Загрузил:</b> {session.get('full_name', session.get('username', 'admin'))}"
    telegram_message += f"\n📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    send_telegram_order_notification(telegram_message)
    
    return jsonify({'success': True, 'file_name': file.filename})

# Скачивание счета
@app.route('/orders/<int:order_id>/download_invoice')
@login_required
def download_order_invoice(order_id):
    """Скачивание счета заказа"""
    order = Order.query.get_or_404(order_id)
    
    if order.invoice_path and os.path.exists(order.invoice_path):
        return send_file(
            order.invoice_path,
            as_attachment=True,
            download_name=order.invoice_file_name or os.path.basename(order.invoice_path)
        )
    
    return "Файл не найден", 404

# Добавление позиции к заказу
@app.route('/orders/<int:order_id>/add_item', methods=['POST'])
@login_required
def add_order_item(order_id):
    """Добавление позиции к существующему заказу"""
    order = Order.query.get_or_404(order_id)
    
    name = request.form.get('name')
    quantity = request.form.get('quantity')
    
    if not name or not quantity:
        return jsonify({'success': False, 'error': 'Заполните все обязательные поля'})
    
    try:
        quantity_float = float(quantity)
        if quantity_float <= 0:
            return jsonify({'success': False, 'error': 'Количество должно быть больше 0'})
    except ValueError:
        return jsonify({'success': False, 'error': 'Некорректное количество'})
    
    # Обработка фото
    photo_filename = None
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"{order.id}_{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'orders', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            photo.save(file_path)
            photo_filename = filename
    
    # Создаем позицию
    order_item = OrderItem(
        order_id=order.id,
        name=name,
        quantity=quantity_float,
        link=request.form.get('link', ''),
        workshop=request.form.get('workshop', ''),
        category=request.form.get('category', 'расходники'),
        photo=photo_filename,
        notes=request.form.get('notes', '')
    )
    
    db.session.add(order_item)
    order.total_items += 1
    order.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # Отправляем уведомление в Telegram
    telegram_message = f"➕ <b>ДОБАВЛЕНА ПОЗИЦИЯ К ЗАКАЗУ</b>\n\n"
    telegram_message += f"<b>Номер заказа:</b> {order.order_number}\n"
    telegram_message += f"<b>Позиция:</b> {name}\n"
    telegram_message += f"<b>Количество:</b> {quantity}\n"
    telegram_message += f"<b>Категория:</b> {order_item.category}\n"
    telegram_message += f"\n👤 <b>Добавил:</b> {session.get('full_name', session.get('username', 'admin'))}"
    telegram_message += f"\n📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    send_telegram_order_notification(telegram_message)
    
    return jsonify({
        'success': True,
        'item': {
            'id': order_item.id,
            'name': order_item.name,
            'quantity': order_item.quantity,
            'category': order_item.category,
            'workshop': order_item.workshop,
            'link': order_item.link,
            'photo': order_item.photo
        }
    })

# Удаление позиции заказа
@app.route('/orders/item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_order_item(item_id):
    """Удаление позиции из заказа"""
    item = OrderItem.query.get_or_404(item_id)
    order = item.order
    
    # Удаляем файл фото если есть
    if item.photo:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'orders', item.photo)
        if os.path.exists(photo_path):
            os.remove(photo_path)
    
    db.session.delete(item)
    order.total_items -= 1
    if order.total_items < 0:
        order.total_items = 0
    order.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify({'success': True})

# Удаление заказа
@app.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
@delete_permission_required()
def delete_order(order_id):
    """Удаление заказа"""
    order = Order.query.get_or_404(order_id)
    
    try:
        # Удаляем файлы фото позиций
        for item in order.items:
            if item.photo:
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'orders', item.photo)
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        
        # Удаляем счет если есть
        if order.invoice_path and os.path.exists(order.invoice_path):
            os.remove(order.invoice_path)
        
        db.session.delete(order)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Ошибка при удалении заказа {order_id}: {e}')
        return jsonify({'success': False, 'error': str(e)})

# API для получения фото позиции
@app.route('/orders/item/photo/<filename>')
@login_required
def get_order_item_photo(filename):
    """Получение фото позиции заказа"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'orders', filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "Файл не найден", 404

# Обновление информации о заказе
@app.route('/orders/<int:order_id>/update_info', methods=['POST'])
@login_required
def update_order_info(order_id):
    """Обновление информации о заказе"""
    order = Order.query.get_or_404(order_id)
    
    manager_name = request.form.get('manager_name')
    notes = request.form.get('notes')
    
    if manager_name is not None:
        order.manager_name = manager_name
    
    if notes is not None:
        order.notes = notes
    
    order.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify({'success': True, 'manager_name': order.manager_name})

# Копировать заказ
@app.route('/orders/<int:order_id>/copy', methods=['POST'])
@login_required
def copy_order(order_id):
    """Создание копии заказа"""
    original_order = Order.query.get_or_404(order_id)
    
    try:
        # Создаем новый заказ
        new_order_number = generate_order_number()
        new_order = Order(
            order_number=new_order_number,
            created_by=session['user_id'],
            manager_name=original_order.manager_name,
            notes=f"Копия заказа {original_order.order_number}\n{original_order.notes or ''}",
            total_items=0
        )
        
        db.session.add(new_order)
        db.session.flush()
        
        # Копируем позиции
        for original_item in original_order.items:
            new_item = OrderItem(
                order_id=new_order.id,
                name=original_item.name,
                quantity=original_item.quantity,
                link=original_item.link,
                workshop=original_item.workshop,
                category=original_item.category,
                notes=original_item.notes
                # ФОТО НЕ КОПИРУЕМ - только ссылки
            )
            db.session.add(new_item)
            new_order.total_items += 1
        
        db.session.commit()
        
        # Отправляем уведомление в Telegram
        telegram_message = f"📋 <b>СКОПИРОВАН ЗАКАЗ</b>\n\n"
        telegram_message += f"<b>Новый заказ:</b> {new_order_number}\n"
        telegram_message += f"<b>На основе:</b> {original_order.order_number}\n"
        telegram_message += f"<b>Количество позиций:</b> {new_order.total_items}\n"
        telegram_message += f"\n👤 <b>Создал:</b> {session.get('full_name', session.get('username', 'admin'))}"
        telegram_message += f"\n📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        send_telegram_order_notification(telegram_message)
        
        flash(f'Заказ {new_order_number} создан как копия!', 'success')
        return jsonify({'success': True, 'new_order_id': new_order.id})
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Ошибка копирования заказа {order_id}: {e}')
        return jsonify({'success': False, 'error': str(e)})

# Контекстный процессор для текущего времени
@app.context_processor
def inject_now():
    return {'now': datetime.now(timezone.utc).date()}

# Добавить в конец app.py перед запуском
def init_database():
    """Инициализация базы данных и создание администратора по умолчанию"""
    with app.app_context():
        db.create_all()
        
        # Создаем папки для загрузок
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'orders'), exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'invoices'), exist_ok=True)
        
        # Создать администратора если его нет
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@eko-production.ru',
                full_name='Александриди А.С.',
                role='admin'
            )
            admin.set_password('Alex4815162342')
            db.session.add(admin)
            db.session.commit()
            print("✅ Администратор создан: admin / Alex4815162342")

if __name__ == '__main__':
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)