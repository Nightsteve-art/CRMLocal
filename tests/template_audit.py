import os,tempfile
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from crm import create_app
from crm.extensions import db
from crm.models import Counterparty,Order,StockItem
fd,path=tempfile.mkstemp('.db');os.close(fd)
app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+path,'SECRET_KEY':'x'})
c=app.test_client();c.post('/login',data={'username':'admin','password':'admin123'})
# Seed records needed to render action forms
c.post('/counterparties',data={'name':'Client'})
c.post('/orders',data={'title':'Order','counterparty_id':'1'})
c.post('/warehouse',data={'sku':'S','name':'Stock','quantity':'1'})
paths=['/dashboard','/counterparties','/proposals','/orders','/orders/1','/warehouse','/materials','/sewing','/production','/users']
rules=list(app.url_map.iter_rules())
allowed={r.rule:r.methods for r in rules}
issues=[]; links=0; forms=0
for pathurl in paths:
 r=c.get(pathurl); soup=BeautifulSoup(r.data,'html.parser')
 for tag in soup.select('a[href],link[href],script[src]'):
  u=tag.get('href') or tag.get('src'); p=urlparse(u).path
  if not p or p.startswith('/static/'):
   if p.startswith('/static/'):
    sr=c.get(p); links+=1
    if sr.status_code!=200: issues.append((pathurl,'static',p,sr.status_code))
   continue
  if p=='/logout': continue
  links+=1; rr=c.get(p)
  if rr.status_code>=400: issues.append((pathurl,'link',p,rr.status_code))
 for form in soup.select('form'):
  forms+=1; action=urlparse(form.get('action') or pathurl).path; method=(form.get('method') or 'get').upper()
  matching=[rule for rule in rules if rule.rule==action or ('<' in rule.rule and action.startswith(rule.rule.split('<')[0]))]
  if not matching: issues.append((pathurl,'form-no-route',action,method))
  elif not any(method in rule.methods for rule in matching): issues.append((pathurl,'form-method',action,method))
print('pages',len(paths),'links/assets',links,'forms',forms,'issues',issues)
assert not issues
# Compile all templates explicitly
for name in app.jinja_env.list_templates(): app.jinja_env.get_template(name)
print('templates',len(app.jinja_env.list_templates()),'compiled OK')
os.remove(path)
