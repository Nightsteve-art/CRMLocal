const $=(s,p=document)=>p.querySelector(s), $$=(s,p=document)=>[...p.querySelectorAll(s)];
$('[data-menu]')?.addEventListener('click',()=>$('.sidebar')?.classList.toggle('open'));
function modal(id,open=true){const el=document.getElementById(id),bg=$('[data-modal-bg]');el?.classList.toggle('open',open);bg?.classList.toggle('open',open)}
$$('[data-open]').forEach(x=>x.onclick=()=>modal(x.dataset.open));$$('[data-close]').forEach(x=>x.onclick=()=>modal(x.closest('.modal').id,false));$('[data-modal-bg]')?.addEventListener('click',()=>{$$('.modal.open').forEach(x=>modal(x.id,false))});
$$('[data-filter]').forEach(input=>input.addEventListener('input',()=>{const q=input.value.toLowerCase();$$('[data-row]').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(q))}));
$$('.kanban-card').forEach(card=>{card.draggable=true;card.addEventListener('dragstart',()=>card.classList.add('dragging'));card.addEventListener('dragend',()=>card.classList.remove('dragging'))});
$$('.kanban-col').forEach(col=>{col.addEventListener('dragover',e=>e.preventDefault());col.addEventListener('drop',async e=>{e.preventDefault();const card=$('.dragging');if(!card)return;col.append(card);await fetch(`/api/production/cards/${card.dataset.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({column:col.dataset.column})})})});
setTimeout(()=>$$('.toast').forEach(x=>x.remove()),4500);
