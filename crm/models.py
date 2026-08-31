from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db


def now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now, nullable=False)

class User(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), default="manager", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    def set_password(self, value): self.password_hash = generate_password_hash(value)
    def check_password(self, value): return check_password_hash(self.password_hash, value)

class Counterparty(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    kind = db.Column(db.String(32), default="client")
    contact_person = db.Column(db.String(160))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)

class Proposal(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    counterparty_id = db.Column(db.Integer, db.ForeignKey("counterparty.id"), nullable=False)
    status = db.Column(db.String(50), default="draft", nullable=False)
    amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(8), default="RUB")
    deadline = db.Column(db.Date)
    description = db.Column(db.Text)
    counterparty = db.relationship("Counterparty", backref="proposals")

class Order(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    counterparty_id = db.Column(db.Integer, db.ForeignKey("counterparty.id"), nullable=False)
    proposal_id = db.Column(db.Integer, db.ForeignKey("proposal.id"))
    status = db.Column(db.String(50), default="new", nullable=False, index=True)
    priority = db.Column(db.String(20), default="normal")
    deadline = db.Column(db.Date)
    manager = db.Column(db.String(160))
    notes = db.Column(db.Text)
    counterparty = db.relationship("Counterparty", backref="orders")
    proposal = db.relationship("Proposal", backref="orders")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

class OrderItem(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    name = db.Column(db.String(240), nullable=False)
    sku = db.Column(db.String(100))
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(30), default="шт")
    unit_price = db.Column(db.Float, default=0)

class StockItem(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(240), nullable=False, index=True)
    category = db.Column(db.String(100))
    quantity = db.Column(db.Float, default=0)
    reserved = db.Column(db.Float, default=0)
    min_quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(30), default="шт")
    location = db.Column(db.String(100))
    transactions = db.relationship("StockTransaction", backref="item", cascade="all, delete-orphan")
    @property
    def available(self): return self.quantity - self.reserved

class StockTransaction(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_item_id = db.Column(db.Integer, db.ForeignKey("stock_item.id"), nullable=False)
    operation = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    document = db.Column(db.String(120))
    comment = db.Column(db.Text)
    user_name = db.Column(db.String(160))

class MaterialRequest(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    stock_item_id = db.Column(db.Integer, db.ForeignKey("stock_item.id"))
    material_name = db.Column(db.String(240), nullable=False)
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(30), default="шт")
    status = db.Column(db.String(30), default="requested")
    needed_by = db.Column(db.Date)
    comment = db.Column(db.Text)
    order = db.relationship("Order", backref="material_requests")
    stock_item = db.relationship("StockItem")

class SewingTask(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(240), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    assignee = db.Column(db.String(160))
    status = db.Column(db.String(30), default="queued")
    priority = db.Column(db.String(20), default="normal")
    quantity = db.Column(db.Float, default=1)
    deadline = db.Column(db.Date)
    notes = db.Column(db.Text)
    order = db.relationship("Order", backref="sewing_tasks")

class KanbanCard(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(240), nullable=False)
    description = db.Column(db.Text)
    column = db.Column(db.String(30), default="backlog", nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    assignee = db.Column(db.String(160))
    priority = db.Column(db.String(20), default="normal")
    due_date = db.Column(db.Date)
    position = db.Column(db.Integer, default=0)
    order = db.relationship("Order", backref="kanban_cards")
