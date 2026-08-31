"""
Integration layers for email, Telegram, and AI features
S7-S8 functionality
"""

import smtplib
import os
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import json
from functools import wraps

# Email Integration
class EmailService:
    """SMTP email service for CRM notifications and document delivery"""
    
    def __init__(self, host=None, port=None, username=None, password=None):
        self.host = host or os.getenv('MAIL_SERVER', 'smtp.yandex.ru')
        self.port = port or int(os.getenv('MAIL_PORT', 587))
        self.username = username or os.getenv('MAIL_USERNAME')
        self.password = password or os.getenv('MAIL_PASSWORD')
        self.from_email = os.getenv('MAIL_USERNAME')
        self.from_name = 'Eko-Production CRM'
    
    def send_proposal(self, to_email, proposal_title, proposal_file_path):
        """Send proposal to client"""
        subject = f"Коммерческое предложение: {proposal_title}"
        body = f"""
        Уважаемый клиент,
        
        Направляем Вам коммерческое предложение для рассмотрения.
        
        Просим ознакомиться с приложенным файлом и сообщить о Вашем решении.
        
        С уважением,
        Eko-Production Team
        """
        return self._send_with_attachment(to_email, subject, body, proposal_file_path)
    
    def send_contract(self, to_email, contract_number, contract_file_path):
        """Send contract for signature"""
        subject = f"Контракт #{contract_number} на подпись"
        body = f"""
        Уважаемый клиент,
        
        Направляем договор для подписания.
        Прошу вернуть подписанный документ в течение 3 рабочих дней.
        
        С уважением,
        Eko-Production Team
        """
        return self._send_with_attachment(to_email, subject, body, contract_file_path)
    
    def send_installation_notification(self, to_email, installation_date, address):
        """Notify client of installation date"""
        subject = "Уведомление о монтаже"
        body = f"""
        Уважаемый клиент,
        
        Монтаж запланирован на: {installation_date}
        Место: {address}
        
        Пожалуйста, обеспечьте доступ на объект в указанное время.
        
        С уважением,
        Eko-Production Team
        """
        return self._send_email(to_email, subject, body)
    
    def send_final_act(self, to_email, act_file_path, order_number):
        """Send final act of completion"""
        subject = f"Акт выполнения работ #{order_number}"
        body = f"""
        Уважаемый клиент,
        
        Направляем акт об окончании монтажа.
        Прошу подписать и вернуть нам для окончательного расчета.
        
        С уважением,
        Eko-Production Team
        """
        return self._send_with_attachment(to_email, subject, body, act_file_path)
    
    def _send_email(self, to_email, subject, body):
        """Generic email sender"""
        try:
            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            server = smtplib.SMTP(self.host, self.port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            return True, "Email sent successfully"
        except Exception as e:
            return False, str(e)
    
    def _send_with_attachment(self, to_email, subject, body, file_path):
        """Send email with file attachment"""
        try:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Attach file
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(file_path)}')
                msg.attach(part)
            
            server = smtplib.SMTP(self.host, self.port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            return True, "Email with attachment sent successfully"
        except Exception as e:
            return False, str(e)

# Telegram Integration
class TelegramBot:
    """Telegram bot for CRM notifications and commands"""
    
    def __init__(self, token=None):
        self.token = token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.warehouse_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.sewing_chat_id = os.getenv('TELEGRAM_SEWING_CHAT_ID')
        self.orders_chat_id = os.getenv('TELEGRAM_ZAKAZ_CHAT_ID')
    
    def send_message(self, chat_id, text):
        """Send text message to chat"""
        url = f"{self.api_url}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        try:
            response = requests.post(url, data=data, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram error: {e}")
            return False
    
    def notify_new_order(self, order_number, description):
        """Notify warehouse of new order"""
        text = f"📦 <b>Новый заказ!</b>\n\n#{order_number}\n{description}"
        return self.send_message(self.warehouse_chat_id, text)
    
    def notify_sewing_task(self, task_name, order_number):
        """Notify sewing department of new task"""
        text = f"✂️ <b>Новая задача для швейки</b>\n\n{task_name}\nЗаказ: #{order_number}"
        return self.send_message(self.sewing_chat_id, text)
    
    def notify_material_shortage(self, material_name, needed_qty):
        """Alert of material shortage"""
        text = f"⚠️ <b>Дефицит материала!</b>\n\n{material_name}\nНужно: {needed_qty}"
        return self.send_message(self.warehouse_chat_id, text)
    
    def notify_installation_schedule(self, order_number, date, address):
        """Notify installers of scheduled job"""
        text = f"🏗️ <b>Монтаж запланирован</b>\n\nЗаказ: #{order_number}\nДата: {date}\nМесто: {address}"
        return self.send_message(self.orders_chat_id, text)
    
    def daily_summary(self, summary_data):
        """Send daily summary to management"""
        text = f"""
        📊 <b>Ежедневная сводка</b>
        
        Задачи просрочены: {summary_data.get('overdue', 0)}
        В работе: {summary_data.get('in_progress', 0)}
        Дефицитов: {summary_data.get('shortages', 0)}
        Риск срыва: {summary_data.get('at_risk', 0)}
        Монтажей на неделю: {summary_data.get('installations', 0)}
        """
        return self.send_message(self.orders_chat_id, text)

# AI Assistant Module (S8)
class AIAssistant:
    """AI-powered recommendations and forecasting"""
    
    @staticmethod
    def predict_completion_date(order, historical_data=None):
        """Forecast order completion based on production history"""
        if not historical_data:
            return None
        
        # Simple model: average cycle time by stage
        avg_cycle_days = sum([h.get('days_to_completion', 14) for h in historical_data]) / len(historical_data)
        
        from datetime import timedelta
        estimated = datetime.utcnow() + timedelta(days=avg_cycle_days)
        return estimated
    
    @staticmethod
    def calculate_material_requirements(specification):
        """Calculate material needs from product specification"""
        # Based on product type and dimensions
        requirements = []
        
        if specification.get('product_type') == 'hockey_board':
            width = specification.get('width', 0)
            height = specification.get('height', 0)
            depth = specification.get('depth', 0)
            
            # Metal frame
            perimeter = (width + height) * 2
            metal_needed = perimeter * 2  # Two rails
            requirements.append({
                'material': 'Metal frame (40x20)',
                'quantity': metal_needed,
                'unit': 'm'
            })
            
            # Plastics
            plastic_area = width * height
            requirements.append({
                'material': 'Plastic boards',
                'quantity': plastic_area,
                'unit': 'm2'
            })
            
            # Fasteners
            requirements.append({
                'material': 'Rivets/bolts',
                'quantity': (perimeter / 10) * 4,  # ~4 fasteners per 10m
                'unit': 'pcs'
            })
            
            # Glazing (optional)
            if specification.get('has_glazing'):
                glass_area = width * (height * 0.4)
                requirements.append({
                    'material': 'Tempered glass',
                    'quantity': glass_area,
                    'unit': 'm2'
                })
        
        return requirements
    
    @staticmethod
    def generate_proposal_draft(client_data, product_specs):
        """Generate proposal text from template"""
        draft = f"""
        КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ
        
        Дата: {datetime.now().strftime('%d.%m.%Y')}
        Клиент: {client_data.get('name')}
        
        ТОВАРЫ И УСЛУГИ:
        
        {product_specs.get('product_type', 'Хоккейные борта')}
        Размеры: {product_specs.get('width', 'N/A')} x {product_specs.get('height', 'N/A')} x {product_specs.get('depth', 'N/A')}
        Опции: {product_specs.get('options', 'стандартные')}
        
        УСЛОВИЯ:
        - Срок производства: 14 дней
        - Доставка: 7 дней
        - Оплата: 50% авансом, 50% при отгрузке
        - Гарантия: 12 месяцев
        
        Цена подлежит уточнению.
        """
        return draft.strip()
    
    @staticmethod
    def suggest_shipping_optimization(orders):
        """Recommend shipment consolidation"""
        suggestions = []
        
        # Group by destination for consolidation
        from itertools import groupby
        orders_sorted = sorted(orders, key=lambda x: x.counterparty.city if hasattr(x.counterparty, 'city') else 'Unknown')
        
        for city, group in groupby(orders_sorted, key=lambda x: x.counterparty.city if hasattr(x.counterparty, 'city') else 'Unknown'):
            group_list = list(group)
            if len(group_list) > 1:
                suggestions.append({
                    'city': city,
                    'orders': [o.number for o in group_list],
                    'potential_savings': f"{len(group_list) - 1} отдельных доставок можно объединить"
                })
        
        return suggestions
    
    @staticmethod
    def identify_at_risk_orders(orders, current_date=None):
        """Flag orders approaching deadline"""
        if current_date is None:
            current_date = datetime.utcnow()
        
        at_risk = []
        for order in orders:
            if order.shipment_date and (order.shipment_date - current_date).days < 3:
                at_risk.append({
                    'order': order.number,
                    'days_left': (order.shipment_date - current_date).days,
                    'status': order.status,
                    'completion': order.completion_percent
                })
        
        return at_risk
