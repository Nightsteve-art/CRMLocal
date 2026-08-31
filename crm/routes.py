from datetime import datetime
from functools import wraps
from urllib.parse import urlsplit
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from .extensions import db
from .models import (User, Counterparty, Proposal, Order, OrderItem, StockItem,
                     StockTransaction, MaterialRequest, SewingTask, KanbanCard)

bp = Blueprint("main", __name__)
ORDER_STATUSES = ["new", "approved", "materials", "production", "quality", "ready", "shipped", "closed"]
PROPOSAL_STATUSES = ["draft", "sent", "approved", "rejected"]
KANBAN_COLUMNS = [("backlog", "Бэклог"), ("planned", "Запланировано"), ("progress", "В работе"), ("review", "Проверка"), ("done", "Готово")]

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Недостаточно прав", "error")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)
    return wrapped

def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Некорректная дата")

def parse_positive_number(value, label="Количество", allow_zero=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: укажите число")
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{label} должно быть больше нуля")
    return number

def is_safe_next_url(target):
    if not target:
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc and target.startswith("/")

def set_enum_value(item, field, value, allowed):
    if value not in allowed:
        abort(400, description="Недопустимое значение статуса")
    setattr(item, field, value)

def next_number(prefix, model):
    return f"{prefix}-{datetime.now():%Y%m%d}-{model.query.count()+1:04d}"

@bp.context_processor
def globals_context():
    return {"current_user": db.session.get(User, session.get("user_id")) if session.get("user_id") else None,
            "order_statuses": ORDER_STATUSES, "proposal_statuses": PROPOSAL_STATUSES}

@bp.route("/")
def index(): return redirect(url_for("main.dashboard") if session.get("user_id") else url_for("main.login"))

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if user and user.is_active and user.check_password(request.form.get("password", "")):
            session.clear(); session.update(user_id=user.id, role=user.role, full_name=user.full_name)
            next_url = request.args.get("next")
            return redirect(next_url if is_safe_next_url(next_url) else url_for("main.dashboard"))
        flash("Неверный логин или пароль", "error")
    return render_template("login.html")

@bp.route("/logout")
def logout(): session.clear(); return redirect(url_for("main.login"))

@bp.route("/dashboard")
@login_required
def dashboard():
    stats = {"orders": Order.query.count(), "active_orders": Order.query.filter(Order.status.notin_(["closed", "shipped"])).count(),
             "proposals": Proposal.query.count(), "stock": StockItem.query.count(),
             "shortages": StockItem.query.filter(StockItem.quantity-StockItem.reserved <= StockItem.min_quantity).count(),
             "sewing": SewingTask.query.filter(SewingTask.status != "done").count()}
    return render_template("dashboard.html", stats=stats,
        orders=Order.query.order_by(Order.updated_at.desc()).limit(7).all(),
        requests=MaterialRequest.query.filter(MaterialRequest.status != "issued").order_by(MaterialRequest.created_at.desc()).limit(5).all())

@bp.route("/counterparties", methods=["GET", "POST"])
@login_required
def counterparties():
    if request.method == "POST":
        db.session.add(Counterparty(name=request.form["name"], kind=request.form.get("kind","client"),
            contact_person=request.form.get("contact_person"), email=request.form.get("email"), phone=request.form.get("phone"), address=request.form.get("address")))
        db.session.commit(); flash("Контрагент создан", "success"); return redirect(url_for("main.counterparties"))
    q=request.args.get("q",""); query=Counterparty.query
    if q: query=query.filter(or_(Counterparty.name.ilike(f"%{q}%"), Counterparty.contact_person.ilike(f"%{q}%")))
    return render_template("counterparties.html", items=query.order_by(Counterparty.name).all())

@bp.route("/counterparties/<int:item_id>/edit", methods=["POST"])
@login_required
def counterparty_edit(item_id):
    item=Counterparty.query.get_or_404(item_id)
    for key in ("name","kind","contact_person","email","phone","address","notes"): setattr(item,key,request.form.get(key))
    db.session.commit(); flash("Контрагент обновлён", "success"); return redirect(url_for("main.counterparties"))

@bp.route("/proposals", methods=["GET", "POST"])
@login_required
def proposals():
    if request.method == "POST":
        db.session.add(Proposal(number=request.form.get("number") or next_number("KP",Proposal), title=request.form["title"],
            counterparty_id=request.form["counterparty_id"], status="draft", amount=parse_positive_number(request.form.get("amount") or 0, "Сумма", allow_zero=True),
            deadline=parse_date(request.form.get("deadline")), description=request.form.get("description")))
        db.session.commit(); flash("КП создано", "success"); return redirect(url_for("main.proposals"))
    return render_template("proposals.html", items=Proposal.query.order_by(Proposal.created_at.desc()).all(), counterparties=Counterparty.query.order_by(Counterparty.name).all())

@bp.route("/proposals/<int:item_id>/status", methods=["POST"])
@login_required
def proposal_status(item_id):
    item=Proposal.query.get_or_404(item_id); set_enum_value(item, "status", request.form.get("status"), PROPOSAL_STATUSES); db.session.commit(); return redirect(url_for("main.proposals"))

@bp.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    if request.method == "POST":
        order=Order(number=request.form.get("number") or next_number("ORD",Order), title=request.form["title"], counterparty_id=request.form["counterparty_id"],
          proposal_id=request.form.get("proposal_id") or None, status="new", priority=request.form.get("priority","normal"),
          deadline=parse_date(request.form.get("deadline")), manager=request.form.get("manager"), notes=request.form.get("notes"))
        db.session.add(order); db.session.commit(); flash("Заказ создан", "success"); return redirect(url_for("main.order_detail", item_id=order.id))
    status=request.args.get("status"); query=Order.query
    if status: query=query.filter_by(status=status)
    return render_template("orders.html", items=query.order_by(Order.created_at.desc()).all(), counterparties=Counterparty.query.all(), proposals=Proposal.query.all())

@bp.route("/orders/<int:item_id>")
@login_required
def order_detail(item_id): return render_template("order_detail.html", item=Order.query.get_or_404(item_id), stock=StockItem.query.order_by(StockItem.name).all())

@bp.route("/orders/<int:item_id>/status", methods=["POST"])
@login_required
def order_status(item_id):
    item=Order.query.get_or_404(item_id); set_enum_value(item, "status", request.form.get("status"), ORDER_STATUSES); db.session.commit(); return redirect(url_for("main.order_detail",item_id=item.id))

@bp.route("/orders/<int:item_id>/items", methods=["POST"])
@login_required
def order_item_add(item_id):
    item=Order.query.get_or_404(item_id); item.items.append(OrderItem(name=request.form["name"],sku=request.form.get("sku"),quantity=parse_positive_number(request.form.get("quantity") or 1),unit=request.form.get("unit","шт"),unit_price=parse_positive_number(request.form.get("unit_price") or 0, "Цена", allow_zero=True)))
    db.session.commit(); return redirect(url_for("main.order_detail",item_id=item.id))

@bp.route("/warehouse", methods=["GET", "POST"])
@login_required
def warehouse():
    if request.method == "POST":
        db.session.add(StockItem(sku=request.form["sku"], name=request.form["name"], category=request.form.get("category"), quantity=parse_positive_number(request.form.get("quantity") or 0, "Остаток", allow_zero=True), min_quantity=parse_positive_number(request.form.get("min_quantity") or 0, "Минимальный остаток", allow_zero=True), unit=request.form.get("unit","шт"), location=request.form.get("location")))
        db.session.commit(); flash("Позиция добавлена", "success"); return redirect(url_for("main.warehouse"))
    q=request.args.get("q",""); query=StockItem.query
    if q: query=query.filter(or_(StockItem.name.ilike(f"%{q}%"),StockItem.sku.ilike(f"%{q}%")))
    return render_template("warehouse.html", items=query.order_by(StockItem.name).all())

@bp.route("/warehouse/<int:item_id>/operation", methods=["POST"])
@login_required
def stock_operation(item_id):
    item=StockItem.query.get_or_404(item_id)
    qty=parse_positive_number(request.form.get("quantity"))
    operation=request.form.get("operation")
    if operation not in {"in", "out", "reserve", "release"}:
        abort(400, description="Недопустимая складская операция")
    if operation=="in": item.quantity += qty
    elif operation=="out":
        if qty>item.available: flash("Недостаточно доступного остатка", "error"); return redirect(url_for("main.warehouse"))
        item.quantity -= qty
    elif operation=="reserve":
        if qty>item.available: flash("Недостаточно доступного остатка для резерва", "error"); return redirect(url_for("main.warehouse"))
        item.reserved += qty
    elif operation=="release":
        if qty>item.reserved: flash("Нельзя снять резерв больше текущего", "error"); return redirect(url_for("main.warehouse"))
        item.reserved -= qty
    db.session.add(StockTransaction(item=item,operation=operation,quantity=qty,comment=request.form.get("comment"),user_name=session.get("full_name")))
    db.session.commit(); flash("Остаток обновлён", "success"); return redirect(url_for("main.warehouse"))

@bp.route("/materials", methods=["GET", "POST"])
@login_required
def materials():
    if request.method=="POST":
        db.session.add(MaterialRequest(number=next_number("MR",MaterialRequest),order_id=request.form.get("order_id") or None,stock_item_id=request.form.get("stock_item_id") or None,material_name=request.form["material_name"],quantity=parse_positive_number(request.form.get("quantity") or 1),unit=request.form.get("unit","шт"),needed_by=parse_date(request.form.get("needed_by")),comment=request.form.get("comment")))
        db.session.commit(); return redirect(url_for("main.materials"))
    return render_template("materials.html",items=MaterialRequest.query.order_by(MaterialRequest.created_at.desc()).all(),orders=Order.query.all(),stock=StockItem.query.all())

@bp.route("/materials/<int:item_id>/status", methods=["POST"])
@login_required
def material_status(item_id):
    item=MaterialRequest.query.get_or_404(item_id); set_enum_value(item, "status", request.form.get("status"), ["requested", "approved", "ordered", "received", "issued"]); db.session.commit(); return redirect(url_for("main.materials"))

@bp.route("/sewing", methods=["GET", "POST"])
@login_required
def sewing():
    if request.method=="POST":
        db.session.add(SewingTask(number=next_number("SEW",SewingTask),title=request.form["title"],order_id=request.form.get("order_id") or None,assignee=request.form.get("assignee"),priority=request.form.get("priority","normal"),quantity=parse_positive_number(request.form.get("quantity") or 1),deadline=parse_date(request.form.get("deadline")),notes=request.form.get("notes")))
        db.session.commit(); return redirect(url_for("main.sewing"))
    return render_template("sewing.html",items=SewingTask.query.order_by(SewingTask.created_at.desc()).all(),orders=Order.query.all())

@bp.route("/sewing/<int:item_id>/status", methods=["POST"])
@login_required
def sewing_status(item_id):
    item=SewingTask.query.get_or_404(item_id); set_enum_value(item, "status", request.form.get("status"), ["queued", "progress", "quality", "done"]); db.session.commit(); return redirect(url_for("main.sewing"))

@bp.route("/production", methods=["GET", "POST"])
@login_required
def production():
    if request.method=="POST":
        column=request.form.get("column","backlog")
        if column not in dict(KANBAN_COLUMNS):
            abort(400, description="Недопустимый этап Kanban")
        db.session.add(KanbanCard(title=request.form["title"],description=request.form.get("description"),column=column,order_id=request.form.get("order_id") or None,assignee=request.form.get("assignee"),priority=request.form.get("priority","normal"),due_date=parse_date(request.form.get("due_date"))))
        db.session.commit(); return redirect(url_for("main.production"))
    cards=KanbanCard.query.order_by(KanbanCard.position,KanbanCard.created_at).all()
    return render_template("production.html",columns=KANBAN_COLUMNS,cards=cards,orders=Order.query.all())

@bp.route("/api/production/cards/<int:item_id>", methods=["PATCH"])
@login_required
def move_card(item_id):
    item=KanbanCard.query.get_or_404(item_id)
    data=request.get_json(silent=True) or {}
    column=data.get("column",item.column)
    if column not in dict(KANBAN_COLUMNS):
        return jsonify(ok=False, error="Недопустимый этап"), 400
    try:
        position=max(0, int(data.get("position",item.position)))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Некорректная позиция"), 400
    item.column=column; item.position=position; db.session.commit(); return jsonify(ok=True)

@bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method=="POST":
        user=User(username=request.form["username"],email=request.form["email"],full_name=request.form["full_name"],role=request.form.get("role","manager")); user.set_password(request.form["password"]); db.session.add(user); db.session.commit(); return redirect(url_for("main.users"))
    return render_template("users.html",items=User.query.order_by(User.full_name).all())
