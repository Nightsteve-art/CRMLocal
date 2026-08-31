import os
import tempfile
from crm import create_app
from crm.extensions import db
from crm.models import User, Counterparty, Proposal, Order, OrderItem, StockItem, StockTransaction, MaterialRequest, SewingTask, KanbanCard

fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+path,'SECRET_KEY':'test'})
c=app.test_client()
checks=[]
def check(name, cond, detail=''):
    checks.append((name,bool(cond),detail)); print(('PASS' if cond else 'FAIL'),name,detail)

# Public/auth
r=c.get('/dashboard'); check('auth redirect',r.status_code==302 and '/login' in r.location,str(r.status_code))
r=c.post('/login',data={'username':'admin','password':'wrong'}); check('bad login rejected',r.status_code==200 and 'Неверный'.encode() in r.data)
r=c.post('/login',data={'username':'admin','password':'admin123'},follow_redirects=True); check('admin login',r.status_code==200 and 'Рабочая панель'.encode() in r.data)
# Every GET page
for p in ['/dashboard','/counterparties','/proposals','/orders','/warehouse','/materials','/sewing','/production','/users']:
 r=c.get(p); check('GET '+p,r.status_code==200,str(r.status_code))
# Counterparty
r=c.post('/counterparties',data={'name':'ООО Клиент','kind':'client','contact_person':'Иван','email':'a@b.ru','phone':'123'}); check('create counterparty',r.status_code==302)
with app.app_context(): cp=Counterparty.query.filter_by(name='ООО Клиент').first(); check('counterparty persisted',cp is not None); cp_id=cp.id
r=c.post(f'/counterparties/{cp_id}/edit',data={'name':'ООО Клиент 2','kind':'client','contact_person':'Петр','email':'x@y.ru','phone':'456','address':'Москва','notes':'VIP'}); check('edit counterparty',r.status_code==302)
# Proposal
r=c.post('/proposals',data={'title':'КП тест','counterparty_id':cp_id,'amount':'12500','deadline':'2026-12-31'}); check('create proposal',r.status_code==302)
with app.app_context(): pr=Proposal.query.first(); check('proposal persisted',pr and pr.amount==12500); pr_id=pr.id
r=c.post(f'/proposals/{pr_id}/status',data={'status':'approved'}); check('proposal status',r.status_code==302)
# Order
r=c.post('/orders',data={'title':'Заказ тест','counterparty_id':cp_id,'proposal_id':pr_id,'priority':'high','deadline':'2026-12-30','manager':'Admin'}); check('create order',r.status_code==302,r.location or '')
with app.app_context(): order=Order.query.first(); order_id=order.id
r=c.get(f'/orders/{order_id}'); check('order detail',r.status_code==200 and 'Заказ тест'.encode() in r.data)
r=c.post(f'/orders/{order_id}/items',data={'name':'Изделие','sku':'SKU','quantity':'4','unit':'шт','unit_price':'100'}); check('add order item',r.status_code==302)
r=c.post(f'/orders/{order_id}/status',data={'status':'production'}); check('order status',r.status_code==302)
# Warehouse
r=c.post('/warehouse',data={'sku':'MAT-1','name':'Ткань','category':'Ткань','quantity':'10','min_quantity':'2','unit':'м','location':'A1'}); check('create stock',r.status_code==302)
with app.app_context(): stock=StockItem.query.first(); stock_id=stock.id
for op,qty in [('reserve','3'),('release','1'),('in','5'),('out','4')]:
 r=c.post(f'/warehouse/{stock_id}/operation',data={'operation':op,'quantity':qty,'comment':'test'}); check('stock '+op,r.status_code==302)
# overdraw
r=c.post(f'/warehouse/{stock_id}/operation',data={'operation':'out','quantity':'999'}); check('stock rejects overdraw',r.status_code==302)
# Material, sewing, kanban
r=c.post('/materials',data={'order_id':order_id,'stock_item_id':stock_id,'material_name':'Ткань','quantity':'2','unit':'м','needed_by':'2026-10-01'}); check('material request',r.status_code==302)
with app.app_context(): mr=MaterialRequest.query.first(); mr_id=mr.id
r=c.post(f'/materials/{mr_id}/status',data={'status':'issued'}); check('material status',r.status_code==302)
r=c.post('/sewing',data={'title':'Пошив','order_id':order_id,'assignee':'Анна','quantity':'4','priority':'high','deadline':'2026-10-05'}); check('sewing task',r.status_code==302)
with app.app_context(): sew=SewingTask.query.first(); sew_id=sew.id
r=c.post(f'/sewing/{sew_id}/status',data={'status':'done'}); check('sewing status',r.status_code==302)
r=c.post('/production',data={'title':'Производство','order_id':order_id,'column':'backlog','assignee':'Цех','priority':'high','due_date':'2026-10-10'}); check('kanban create',r.status_code==302)
with app.app_context(): card=KanbanCard.query.first(); card_id=card.id
r=c.patch(f'/api/production/cards/{card_id}',json={'column':'progress','position':2}); check('kanban move',r.status_code==200 and r.json=={'ok':True})
# Role access
r=c.post('/users',data={'username':'manager','email':'m@x.ru','full_name':'Менеджер','password':'pass123','role':'manager'}); check('create user',r.status_code==302)
c.get('/logout'); c.post('/login',data={'username':'manager','password':'pass123'}); r=c.get('/users'); check('non-admin user blocked',r.status_code==302 and '/dashboard' in r.location)
# Persistence assertions
with app.app_context():
 check('order item persisted',OrderItem.query.count()==1)
 check('stock balance correct',StockItem.query.get(stock_id).quantity==11 and StockItem.query.get(stock_id).reserved==2,str((StockItem.query.get(stock_id).quantity,StockItem.query.get(stock_id).reserved)))
 check('transactions persisted',StockTransaction.query.count()==4,str(StockTransaction.query.count()))
 check('statuses persisted',Proposal.query.get(pr_id).status=='approved' and Order.query.get(order_id).status=='production' and MaterialRequest.query.get(mr_id).status=='issued' and SewingTask.query.get(sew_id).status=='done' and KanbanCard.query.get(card_id).column=='progress')
print('\nTOTAL',sum(x[1] for x in checks),'/',len(checks))
if not all(x[1] for x in checks): raise SystemExit(1)
os.remove(path)
