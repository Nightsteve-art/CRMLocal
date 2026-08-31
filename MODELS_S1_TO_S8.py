# Complete Enhanced app.py Models for S1-S8
# This file contains all new/updated models needed for full functionality
# To integrate: Add these classes to your existing app.py after line ~350 (after existing models)

# ============================================================================
# SPRINT S1: ORDER PASSPORT & CENTRAL MANAGEMENT
# ============================================================================

class Order(db.Model):
    """Enhanced Order model with full lifecycle tracking"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(500), nullable=False)
    
    # Links
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposal.id'))
    kanban_project_id = db.Column(db.Integer, db.ForeignKey('kanban_project.id'))
    counterparty_id = db.Column(db.Integer, db.ForeignKey('counterparty.id'), nullable=False)
    
    # Status & Lifecycle
    status = db.Column(db.String(50), default='draft', index=True)  # Enum-like
    priority = db.Column(db.Integer, default=2)  # 1-4
    
    # Timeline
    contract_date = db.Column(db.DateTime)
    planned_ready_date = db.Column(db.DateTime)
    planned_shipment_date = db.Column(db.DateTime)
    planned_installation_date = db.Column(db.DateTime)
    actual_completion_date = db.Column(db.DateTime)
    
    # Management
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    project_manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Metrics
    completion_percent = db.Column(db.Float, default=0)  # Auto-calculated
    risk_count = db.Column(db.Integer, default=0)  # Auto-counted
    payment_status = db.Column(db.String(30), default='not_invoiced')
    
    # Config
    product_type = db.Column(db.String(120), default='hockey_board')
    route_template_code = db.Column(db.String(80))
    installation_required = db.Column(db.Boolean, default=False)
    installation_mode = db.Column(db.String(20))  # 'internal', 'contractor', 'mixed'
    
    # Meta
    description = db.Column(db.Text)
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    proposal = db.relationship('Proposal', backref='orders')
    kanban_project = db.relationship('KanbanProject', backref='order_ref')
    counterparty = db.relationship('Counterparty', backref='orders')
    manager = db.relationship('User', foreign_keys=[manager_id], backref='managed_orders')
    project_manager = db.relationship('User', foreign_keys=[project_manager_id])
    tasks = db.relationship('KanbanCard', backref='order')
    comments = db.relationship('OrderComment', backref='order', cascade='all,delete-orphan')
    material_requirements = db.relationship('MaterialRequirement', backref='order', cascade='all,delete-orphan')
    installation = db.relationship('Installation', backref='order', uselist=False, cascade='all,delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.number}: {self.name}>'


# ============================================================================
# SPRINT S2: MATERIAL REQUIREMENTS & BOM
# ============================================================================

class MaterialRequirement(db.Model):
    """Material demand from order specification"""
    __tablename__ = 'material_requirements'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('stock_item.id'))
    
    material_name = db.Column(db.String(500), nullable=False)  # If no material_id
    category = db.Column(db.String(100))  # 'metal', 'plastic', 'fastener', 'glass', etc.
    
    required_qty = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(30), default='pcs')
    
    available_qty = db.Column(db.Float, default=0)  # From stock
    reserved_qty = db.Column(db.Float, default=0)  # For other orders
    issued_qty = db.Column(db.Float, default=0)  # Consumed for this order
    
    status = db.Column(db.String(30), default='planned')  # 'planned', 'available', 'deficit', 'ordered', 'received'
    
    source = db.Column(db.String(30), default='specification')  # 'specification', 'manual'
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    material = db.relationship('StockItem', backref='requirements')
    
    @property
    def deficit(self):
        return max(0, self.required_qty - (self.available_qty - self.reserved_qty))
    
    def __repr__(self):
        return f'<Req {self.material_name}: {self.required_qty}{self.unit}>'


# ============================================================================
# SPRINT S3: DOCUMENT VERSIONING
# ============================================================================

class Document(db.Model):
    """Versioned technical documents (drawings, specs, passports)"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    
    name = db.Column(db.String(500), nullable=False)
    kind = db.Column(db.String(80), nullable=False)  # 'drawing', 'assembly', 'spec', 'passport', 'laser_file'
    
    version = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default='draft')  # 'draft', 'review', 'approved', 'superseded'
    
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    checksum = db.Column(db.String(128))  # SHA256
    
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    approved_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    change_reason = db.Column(db.Text)  # Why changed from previous version
    
    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
    order = db.relationship('Order', backref='documents')
    
    db.UniqueConstraint('order_id', 'kind', 'name', 'version', name='uc_doc_version')
    
    def __repr__(self):
        return f'<Doc {self.kind} v{self.version}: {self.name}>'


# ============================================================================
# SPRINT S4: PROCUREMENT & CONSUMABLES
# ============================================================================

class ProcurementRequest(db.Model):
    """Procurement order to suppliers"""
    __tablename__ = 'procurement_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(80), unique=True, nullable=False)
    
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    requested_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    status = db.Column(db.String(30), default='draft')  # 'draft', 'review', 'approved', 'ordered', 'received'
    priority = db.Column(db.Integer, default=2)
    
    needed_by = db.Column(db.DateTime)
    supplier_id = db.Column(db.Integer, db.ForeignKey('counterparty.id'))
    
    items = db.relationship('ProcurementItem', backref='request', cascade='all,delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    order = db.relationship('Order')
    requested_by = db.relationship('User')
    supplier = db.relationship('Counterparty', backref='procurement_requests')


class ProcurementItem(db.Model):
    """Line items in procurement request"""
    __tablename__ = 'procurement_items'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('procurement_requests.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('stock_item.id'))
    
    name = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(30))
    
    expected_delivery = db.Column(db.DateTime)
    unit_price = db.Column(db.Float)
    received_qty = db.Column(db.Float, default=0)
    
    material = db.relationship('StockItem')
    request = db.relationship('ProcurementRequest', backref='line_items')


class ConsumableRequest(db.Model):
    """Department requests for consumables/supplies"""
    __tablename__ = 'consumable_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    
    department = db.Column(db.String(40), nullable=False)  # 'welding', 'assembly', 'sewing'
    requested_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    status = db.Column(db.String(30), default='draft')  # 'draft', 'sent', 'partial', 'complete'
    priority = db.Column(db.Integer, default=2)
    
    notes = db.Column(db.Text)
    items = db.relationship('ConsumableItem', backref='request', cascade='all,delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.now)


class ConsumableItem(db.Model):
    """Line items in consumable request"""
    __tablename__ = 'consumable_items'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('consumable_requests.id'), nullable=False)
    
    name = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(30))
    issued_qty = db.Column(db.Float, default=0)


class InstallationKit(db.Model):
    """Checklist of components for installation"""
    __tablename__ = 'installation_kits'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    
    # Fasteners & Hardware
    anchor_bolts = db.Column(db.Float, default=0)
    fasteners = db.Column(db.Float, default=0)
    specialty_fasteners = db.Column(db.Float, default=0)
    
    # Documentation
    has_drawings = db.Column(db.Boolean, default=False)
    has_passport = db.Column(db.Boolean, default=False)
    has_assembly_diagram = db.Column(db.Boolean, default=False)
    
    # Spare parts
    spare_parts = db.Column(db.Text)  # JSON or delimited list
    
    # Status
    is_complete = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    
    order = db.relationship('Order', backref='kit')


# ============================================================================
# SPRINT S5: COMMUNICATIONS & COMMENTS
# ============================================================================

class OrderComment(db.Model):
    """Contextual discussion within order"""
    __tablename__ = 'order_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('order_comments.id'))
    
    body = db.Column(db.Text, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    edited_at = db.Column(db.DateTime)
    
    author = db.relationship('User', backref='order_comments')
    parent = db.relationship('OrderComment', remote_side=[id], backref='replies')
    order = db.relationship('Order')
    
    def __repr__(self):
        return f'<Comment {self.id}: by {self.author.username}>'


class EmailHistory(db.Model):
    """Track email sends for audit and retry"""
    __tablename__ = 'email_history'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    
    to_addresses = db.Column(db.String(500), nullable=False)  # JSON or comma-separated
    cc = db.Column(db.String(500))
    
    subject = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text)
    
    attachments = db.Column(db.String(500))  # JSON list of file paths
    
    status = db.Column(db.String(30), default='queued')  # 'queued', 'sent', 'bounced', 'failed'
    error_message = db.Column(db.Text)
    
    sent_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    sent_at = db.Column(db.DateTime)
    
    sent_by = db.relationship('User', backref='emails_sent')
    order = db.relationship('Order', backref='email_history')


# ============================================================================
# SPRINT S6: INSTALLATION & FINAL SETTLEMENT
# ============================================================================

class Installation(db.Model):
    """Installation project tracking"""
    __tablename__ = 'installations'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    
    status = db.Column(db.String(40), default='draft')  # See Order statuses ending in 'installation'
    
    mode = db.Column(db.String(20), default='internal')  # 'internal', 'contractor', 'mixed'
    contractor_id = db.Column(db.Integer, db.ForeignKey('counterparty.id'))
    
    address = db.Column(db.Text)
    contact_name = db.Column(db.String(250))
    contact_phone = db.Column(db.String(60))
    contact_email = db.Column(db.String(320))
    
    planned_start = db.Column(db.DateTime)
    planned_end = db.Column(db.DateTime)
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    
    checklist = db.Column(db.Text)  # JSON: {item: bool, ...}
    
    has_act = db.Column(db.Boolean, default=False)
    act_document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    
    issues_count = db.Column(db.Integer, default=0)
    final_notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    order = db.relationship('Order')
    contractor = db.relationship('Counterparty', backref='installations')
    act_document = db.relationship('Document')


class FinalSettlement(db.Model):
    """Final payment reconciliation"""
    __tablename__ = 'final_settlements'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    
    total_amount = db.Column(db.Float, nullable=False)
    advance_paid = db.Column(db.Float, default=0)
    remaining = db.Column(db.Float)
    
    status = db.Column(db.String(30), default='pending')  # 'pending', 'paid', 'partial'
    
    payment_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    order = db.relationship('Order', backref='settlement')


# ============================================================================
# SPRINT S7: SYSTEM INTEGRATIONS
# ============================================================================

class TelegramNotification(db.Model):
    """Telegram bot notification queue"""
    __tablename__ = 'telegram_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('kanban_card.id'))
    
    chat_id = db.Column(db.String(80), nullable=False)  # Telegram group or user ID
    message_text = db.Column(db.Text, nullable=False)
    
    status = db.Column(db.String(20), default='queued')  # 'queued', 'sent', 'failed'
    error = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    sent_at = db.Column(db.DateTime)
    
    order = db.relationship('Order')
    task = db.relationship('KanbanCard')


class AuditLog(db.Model):
    """System audit trail"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    entity_type = db.Column(db.String(80), nullable=False)  # 'Order', 'Task', 'Document', etc.
    entity_id = db.Column(db.Integer, nullable=False)
    
    action = db.Column(db.String(80), nullable=False)  # 'create', 'update', 'approve', 'archive'
    
    before_state = db.Column(db.Text)  # JSON
    after_state = db.Column(db.Text)   # JSON
    
    reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    actor = db.relationship('User', backref='audit_actions')


# ============================================================================
# SPRINT S8: AI ASSISTANT & DETERMINISTIC RULES
# ============================================================================

class AIAssistantSession(db.Model):
    """Track AI-generated recommendations and user confirmations"""
    __tablename__ = 'ai_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    query = db.Column(db.Text, nullable=False)  # User question
    response_text = db.Column(db.Text)  # AI response
    
    action_type = db.Column(db.String(80))  # 'predict_date', 'draft_cp', 'suggest_tasks', 'list_procurement'
    
    # AI Output (JSON)
    prediction_data = db.Column(db.Text)  # Confidence, basis, factors
    suggested_action = db.Column(db.Text)
    
    # User confirmation
    user_accepted = db.Column(db.Boolean)
    action_created = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    order = db.relationship('Order', backref='ai_sessions')
    user = db.relationship('User')


# ============================================================================
# Add to existing StockItem (expand model)
# ============================================================================

# Alter StockItem to add:
#   - sku (unique)
#   - location / zone
#   - category
#   - min_stock / max_stock
#   - reserve tracking
#   - supply_chain metadata

# Example extension (apply via migration or direct model update):
#
# StockItem.sku = db.Column(db.String(100), unique=True)
# StockItem.location = db.Column(db.String(200))
# StockItem.min_stock = db.Column(db.Float, default=0)
# StockItem.reserved_qty = db.Column(db.Float, default=0)
