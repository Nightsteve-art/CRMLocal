"""
Extended database models for Eko-Production CRM
Adds S1-S8 functionality: Order Passport, Documents, Dependencies, Installations
"""

from app import db
from datetime import datetime
from enum import Enum

# S1: Order/Project Passport Models
class OrderStatus(Enum):
    DRAFT = "draft"
    PROPOSAL_PREPARATION = "proposal_preparation"
    PROPOSAL_SENT = "proposal_sent"
    PROPOSAL_ACCEPTED = "proposal_accepted"
    CONTRACT_PENDING = "contract_pending"
    CONTRACT_SIGNED = "contract_signed"
    PRODUCTION_PREP = "production_prep"
    AWAITING_MATERIALS = "awaiting_materials"
    IN_PRODUCTION = "in_production"
    COMPLETION = "completion"
    READY_TO_SHIP = "ready_to_ship"
    SHIPPED = "shipped"
    INSTALLATION = "installation"
    FINAL_BILLING = "final_billing"
    CLOSED = "closed"

class Order(db.Model):
    """Enhanced Order model with full passport capabilities"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    counterparty_id = db.Column(db.Integer, db.ForeignKey('counterparty.id'), nullable=False)
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposal.id'))
    kanban_project_id = db.Column(db.Integer, db.ForeignKey('kanban_project.id'))
    
    # Order Details
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    specification = db.Column(db.JSON)  # Product specs as JSON
    
    # Status and Workflow
    status = db.Column(db.String(50), nullable=False, default=OrderStatus.DRAFT.value)
    contract_date = db.Column(db.DateTime)
    shipment_date = db.Column(db.DateTime)
    installation_date = db.Column(db.DateTime)
    
    # Progress Tracking
    completion_percent = db.Column(db.Integer, default=0)
    risk_count = db.Column(db.Integer, default=0)
    blocked_reason = db.Column(db.Text)
    
    # Metadata
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relations
    counterparty = db.relationship('Counterparty', backref=db.backref('orders', lazy=True))
    proposal = db.relationship('Proposal', backref=db.backref('orders', lazy=True))
    kanban_project = db.relationship('KanbanProject', backref=db.backref('orders', lazy=True))
    comments = db.relationship('OrderComment', backref='order', lazy=True, cascade='all, delete-orphan')
    materials = db.relationship('MaterialRequirement', backref='order', lazy=True, cascade='all, delete-orphan')
    installation = db.relationship('Installation', backref='order', uselist=False, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.number}>'

# S3: Document Versioning
class DocumentStatus(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"

class Document(db.Model):
    """Document versioning for drawings, specs, patents"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    kanban_project_id = db.Column(db.Integer, db.ForeignKey('kanban_project.id'))
    
    name = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(50), nullable=False)  # drawing, spec, passport, assembly, etc.
    version = db.Column(db.Integer, default=1)
    status = db.Column(db.String(50), nullable=False, default=DocumentStatus.DRAFT.value)
    
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer)
    file_hash = db.Column(db.String(64))  # SHA256 for change tracking
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    change_reason = db.Column(db.Text)  # Why was this document changed/approved
    
    # Relations
    order = db.relationship('Order', backref=db.backref('documents', lazy=True))
    kanban_project = db.relationship('KanbanProject', backref=db.backref('documents', lazy=True))
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_documents')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_documents')
    
    def __repr__(self):
        return f'<Document {self.name} v{self.version}>'

# S3: Task Dependencies
class TaskDependency(db.Model):
    """Manage task dependencies and blocking relationships"""
    __tablename__ = 'task_dependencies'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('kanban_card.id'), nullable=False)
    depends_on_task_id = db.Column(db.Integer, db.ForeignKey('kanban_card.id'), nullable=False)
    
    dependency_type = db.Column(db.String(50), default='blocking')  # blocking, related, etc.
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relations
    task = db.relationship('KanbanCard', foreign_keys=[task_id], backref='dependencies')
    depends_on = db.relationship('KanbanCard', foreign_keys=[depends_on_task_id])
    
    def __repr__(self):
        return f'<TaskDependency {self.task_id} -> {self.depends_on_task_id}>'

# S4: Material Requirements and Procurement
class MaterialRequirement(db.Model):
    """Tracks material needs per order"""
    __tablename__ = 'material_requirements'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    stock_item_id = db.Column(db.Integer, db.ForeignKey('stock_item.id'))
    
    material_name = db.Column(db.String(255), nullable=False)
    required_qty = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20))  # kg, m, pcs, etc.
    issued_qty = db.Column(db.Float, default=0)
    reserved_qty = db.Column(db.Float, default=0)
    available_qty = db.Column(db.Float, default=0)
    
    status = db.Column(db.String(50), default='pending')  # pending, available, ordered, shortage
    shortage_qty = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    order = db.relationship('Order', backref='order_materials')
    stock_item = db.relationship('StockItem', backref='material_requirements')
    
    def __repr__(self):
        return f'<MaterialRequirement {self.material_name} x{self.required_qty}>'

class InstallationKit(db.Model):
    """Checklist for installation kit completeness"""
    __tablename__ = 'installation_kits'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    
    status = db.Column(db.String(50), default='pending')  # pending, complete, shipped
    
    has_assembly_drawing = db.Column(db.Boolean, default=False)
    has_passport = db.Column(db.Boolean, default=False)
    has_hardware_kit = db.Column(db.Boolean, default=False)
    has_installation_guide = db.Column(db.Boolean, default=False)
    has_spare_parts = db.Column(db.Boolean, default=False)
    
    notes = db.Column(db.Text)
    checked_at = db.Column(db.DateTime)
    checked_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    order = db.relationship('Order', backref='installation_kit')
    checker = db.relationship('User', backref='checked_installation_kits')
    
    @property
    def is_complete(self):
        return all([
            self.has_assembly_drawing,
            self.has_passport,
            self.has_hardware_kit,
            self.has_installation_guide,
            self.has_spare_parts
        ])

# S5: Communications
class OrderComment(db.Model):
    """Comments/discussion thread on orders"""
    __tablename__ = 'order_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    body = db.Column(db.Text, nullable=False)
    mentions = db.Column(db.JSON)  # List of user IDs mentioned
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    edited_reason = db.Column(db.String(255))
    
    # Relations
    order = db.relationship('Order', backref='order_comments')
    author = db.relationship('User', backref='order_comments')
    attachments = db.relationship('OrderCommentFile', backref='comment', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<OrderComment by {self.author_id} on order {self.order_id}>'

class OrderCommentFile(db.Model):
    """File attachments to order comments"""
    __tablename__ = 'order_comment_files'
    
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('order_comments.id'), nullable=False)
    
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer)
    
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relations
    comment = db.relationship('OrderComment', backref='files')

# S6: Installation and Finishing
class Installation(db.Model):
    """Installation jobs and tracking"""
    __tablename__ = 'installations'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    
    contractor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    brigade = db.Column(db.String(255))  # Team name/number
    
    address = db.Column(db.Text, nullable=False)
    planned_date = db.Column(db.DateTime)
    actual_date = db.Column(db.DateTime)
    
    status = db.Column(db.String(50), default='pending')  # pending, scheduled, in_progress, complete, issues
    checklist = db.Column(db.JSON)  # {item: bool, ...}
    notes = db.Column(db.Text)
    
    act_file_path = db.Column(db.String(512))  # Path to signed act/report
    act_signed_at = db.Column(db.DateTime)
    
    issues_found = db.Column(db.Text)  # Client complaints/issues
    resolution_status = db.Column(db.String(50))  # open, in_progress, resolved
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    order = db.relationship('Order', backref='installations')
    contractor = db.relationship('User', backref='installations')
    photos = db.relationship('InstallationPhoto', backref='installation', lazy=True, cascade='all, delete-orphan')

class InstallationPhoto(db.Model):
    """Photo documentation of installation"""
    __tablename__ = 'installation_photos'
    
    id = db.Column(db.Integer, primary_key=True)
    installation_id = db.Column(db.Integer, db.ForeignKey('installations.id'), nullable=False)
    
    file_path = db.Column(db.String(512), nullable=False)
    caption = db.Column(db.String(255))
    stage = db.Column(db.String(50))  # before, during, after, issue
    
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relations
    installation = db.relationship('Installation', backref='photos')

# Audit & Logging
class AuditLog(db.Model):
    """Track all changes to orders and sensitive actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    action = db.Column(db.String(100), nullable=False)  # create, update, delete, approve, etc.
    entity_type = db.Column(db.String(50), nullable=False)  # Order, Document, Installation, etc.
    entity_id = db.Column(db.Integer)
    
    old_value = db.Column(db.JSON)  # Previous state
    new_value = db.Column(db.JSON)  # Current state
    change_reason = db.Column(db.Text)
    
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45))
    
    # Relations
    order = db.relationship('Order', backref='audit_entries')
    user = db.relationship('User', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.action} on {self.entity_type} by {self.user_id}>'
