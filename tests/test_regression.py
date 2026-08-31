from crm import create_app
from crm.extensions import db
from crm.models import Counterparty, KanbanCard, StockItem, StockTransaction, User


def make_app():
    return create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test",
    })


def login(client, username="admin", password="admin123"):
    return client.post("/login", data={"username": username, "password": password})


def test_login_rejects_external_next_url():
    app = make_app()
    client = app.test_client()
    response = client.post(
        "/login?next=https://evil.example",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 302
    assert response.location.endswith("/dashboard")


def test_invalid_dates_and_statuses_return_400():
    app = make_app()
    client = app.test_client()
    login(client)
    client.post("/counterparties", data={"name": "Client"})
    assert client.post("/orders", data={"title": "Order", "counterparty_id": "1", "deadline": "bad"}).status_code == 400
    client.post("/orders", data={"title": "Order", "counterparty_id": "1"})
    assert client.post("/orders/1/status", data={"status": "invalid"}).status_code == 400
    assert client.post("/proposals", data={"title": "P", "counterparty_id": "1", "amount": "-1"}).status_code == 400


def test_inventory_rejects_negative_and_invalid_operations():
    app = make_app()
    client = app.test_client()
    login(client)
    client.post("/warehouse", data={"sku": "MAT", "name": "Material", "quantity": "10"})
    assert client.post("/warehouse/1/operation", data={"operation": "out", "quantity": "-5"}).status_code == 400
    assert client.post("/warehouse/1/operation", data={"operation": "reserve", "quantity": "11"}).status_code == 302
    assert client.post("/warehouse/1/operation", data={"operation": "unknown", "quantity": "1"}).status_code == 400
    with app.app_context():
        item = db.session.get(StockItem, 1)
        assert item.quantity == 10
        assert item.reserved == 0
        assert StockTransaction.query.count() == 0


def test_kanban_api_validates_payload_and_requires_login():
    app = make_app()
    client = app.test_client()
    assert client.patch("/api/production/cards/1", json={"column": "done"}).status_code == 302
    login(client)
    client.post("/production", data={"title": "Card", "column": "backlog"})
    assert client.patch("/api/production/cards/1", json={"column": "invalid"}).status_code == 400
    assert client.patch("/api/production/cards/1", json={"column": "done", "position": "bad"}).status_code == 400
    assert client.patch("/api/production/cards/1", json={"column": "done", "position": 1}).status_code == 200
    with app.app_context():
        assert db.session.get(KanbanCard, 1).column == "done"


def test_non_admin_cannot_open_users_page():
    app = make_app()
    client = app.test_client()
    login(client)
    client.post("/users", data={
        "username": "manager", "email": "manager@example.com", "full_name": "Manager",
        "password": "secret", "role": "manager",
    })
    client.get("/logout")
    login(client, "manager", "secret")
    response = client.get("/users")
    assert response.status_code == 302
    assert response.location.endswith("/dashboard")
