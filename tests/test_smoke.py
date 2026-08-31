from crm import create_app
from crm.extensions import db


def make_app():
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test"})

def test_login_and_pages():
    app=make_app(); client=app.test_client()
    response=client.post('/login',data={'username':'admin','password':'admin123'},follow_redirects=True)
    assert response.status_code==200
    assert 'Рабочая панель'.encode('utf-8') in response.data
    for path in ['/counterparties','/proposals','/orders','/warehouse','/materials','/sewing','/production','/users']:
        assert client.get(path).status_code==200

def test_core_workflow():
    app=make_app(); client=app.test_client(); client.post('/login',data={'username':'admin','password':'admin123'})
    assert client.post('/counterparties',data={'name':'Тестовый клиент','kind':'client'}).status_code==302
    assert client.post('/orders',data={'title':'Тестовый заказ','counterparty_id':'1','priority':'normal'}).status_code==302
    assert client.post('/warehouse',data={'sku':'MAT-1','name':'Материал','quantity':'10','min_quantity':'2','unit':'м'}).status_code==302
