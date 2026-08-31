// kanban.js — полноценная клиентская часть Kanban с синхронизацией через сервер
window.app = {};
// ------------------------- Глобальные переменные -------------------------
let currentProjectId = null;
let projects = [];
let columns = [];
let cards = [];
let fields = [];
let currentCardId = null;

// ------------------------- Вспомогательные функции -------------------------
function showError(msg) {
    alert('Ошибка: ' + msg);
    console.error(msg);
}

function escapeHtml(s) {
    if (!s) return '';
    let div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

function formatDate(d) {
    let x = new Date(d);
    if (isNaN(x)) return d;
    return x.toLocaleDateString('ru-RU', {day:'numeric', month:'short'});
}

function getDeadlineClass(deadline) {
    if (!deadline) return '';
    const today = new Date(); today.setHours(0,0,0,0);
    const d = new Date(deadline); d.setHours(0,0,0,0);
    if (d < today) return 'card-deadline-overdue';
    if ((d - today) / (86400000) <= 3) return 'card-deadline-soon';
    return '';
}

async function apiRequest(url, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);
    const response = await fetch(url, options);
    if (!response.ok) {
        let errMsg = `HTTP ${response.status}`;
        try { const err = await response.json(); errMsg = err.error || errMsg; } catch(e) {}
        throw new Error(errMsg);
    }
    return response.json();
}

// ------------------------- Загрузка данных -------------------------
async function loadProjects() {
    try {
        projects = await apiRequest('/api/kanban/projects');
        if (!currentProjectId && projects.length) currentProjectId = projects[0].id;
        renderProjectSelector();
    } catch(e) { showError('Загрузка проектов: ' + e.message); }
}

async function loadColumns() {
    if (!currentProjectId) return;
    try {
        columns = await apiRequest(`/api/kanban/projects/${currentProjectId}/columns`);
    } catch(e) { showError('Загрузка колонок: ' + e.message); }
}

async function loadCards() {
    if (!currentProjectId) return [];
    const data = await apiRequest(`/api/kanban/cards?project_id=${currentProjectId}`);
    cards = data;
    return cards;
}

async function loadFields() {
    if (!currentProjectId) return;
    try {
        fields = await apiRequest(`/api/kanban/projects/${currentProjectId}/fields`);
    } catch(e) { showError('Загрузка полей: ' + e.message); }
}

async function refreshAll() {
    await loadColumns();
    await loadCards();
    await loadFields();
    renderBoard();
    updateStats();
}

// ------------------------- Рендеринг -------------------------
function renderProjectSelector() {
    const container = document.getElementById('projectSelector');
    if (!container) return;
    if (!projects.length) {
        container.innerHTML = '<span class="text-sm text-slate-500">Нет проектов</span>';
        return;
    }
    const selectHtml = `
        <div class="flex items-center gap-2">
            <span class="text-sm">Проект:</span>
            <select id="projectSelect" class="text-sm border rounded-lg px-2 py-1">
                ${projects.map(p => `<option value="${p.id}" ${p.id === currentProjectId ? 'selected' : ''}>${escapeHtml(p.name)}</option>`).join('')}
            </select>
            <button onclick="app.openProjectModal()" class="p-1 text-slate-400 hover:text-ice-600"><i data-lucide="settings-2" class="w-4 h-4"></i></button>
        </div>
    `;
    container.innerHTML = selectHtml;
    document.getElementById('projectSelect')?.addEventListener('change', async (e) => {
        currentProjectId = parseInt(e.target.value);
        await refreshAll();
    });
    lucide.createIcons();
}

function renderBoard() {
    const board = document.getElementById('board');
    if (!board) return;
    board.innerHTML = '';
    const projectCards = cards.filter(c => c.projectId === currentProjectId);
    columns.forEach(col => {
        const colCards = projectCards.filter(c => c.columnId === col.id);
		colCards.sort((a, b) => {
        const statusA = a.data?.status || 'progress';
        const statusB = b.data?.status || 'progress';
        const priority = { attention: 1, progress: 2, done: 3 };
        return (priority[statusA] || 2) - (priority[statusB] || 2);
    });
        const colDiv = document.createElement('div');
        colDiv.className = 'flex flex-col max-h-full bg-slate-100/40 rounded-xl border border-slate-200';
        colDiv.dataset.columnId = col.id;
        colDiv.innerHTML = `
            <div class="column-header flex items-center justify-between px-3 py-2 bg-white rounded-t-xl border-b">
                <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold truncate">${escapeHtml(col.name)}</span>
                    <span class="px-1.5 py-0.5 text-xs bg-slate-100 rounded-md">${colCards.length}</span>
                </div>
                <div class="flex items-center gap-1">
                    <button onclick="app.moveColumn(${col.id}, -1)" class="move-column-btn p-1 text-slate-400 hover:text-ice-600" title="Влево"><i data-lucide="chevron-left" class="w-4 h-4"></i></button>
                    <button onclick="app.moveColumn(${col.id}, 1)" class="move-column-btn p-1 text-slate-400 hover:text-ice-600" title="Вправо"><i data-lucide="chevron-right" class="w-4 h-4"></i></button>
                    <button onclick="app.openCardModal(null, ${col.id})" class="p-1 text-slate-400 hover:text-ice-600"><i data-lucide="plus" class="w-4 h-4"></i></button>
                    <button onclick="app.deleteColumn(${col.id})" class="p-1 text-slate-400 hover:text-red-600"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
                </div>
            </div>
            <div class="column-scroll flex-1 overflow-y-auto p-2 space-y-2 min-h-[120px]"
                 ondragover="app.handleDragOver(event, ${col.id})"
                 ondragleave="app.handleDragLeave(event, ${col.id})"
                 ondrop="app.handleDrop(event, ${col.id})">
                ${colCards.map(c => renderCardHTML(c)).join('')}
            </div>
        `;
        board.appendChild(colDiv);
    });
    // Навесить drag&drop после добавления элементов
    cards.forEach(c => {
        const el = document.getElementById(`card-${c.id}`);
        if (el) {
            el.setAttribute('draggable', 'true');
            el.addEventListener('dragstart', e => app.handleDragStart(e, c.id));
            el.addEventListener('dragend', e => app.handleDragEnd(e, c.id));
        }
    });
    lucide.createIcons();
}


function renderCardHTML(card) {
    const data = card.data || {};
    const status = data.status || 'progress';
    const statusMap = {
        attention: { class: 'card-status-attention', badge: 'badge-attention', label: 'Требует внимания' },
        progress: { class: 'card-status-progress', badge: 'badge-progress', label: 'В работе' },
        done: { class: 'card-status-done', badge: 'badge-done', label: 'Исполнено' }
    };
    const st = statusMap[status] || statusMap.progress;
    const deadlineClass = getDeadlineClass(data.deadline);
    const total = parseFloat(data.quantityTotal) || 0;
    const completed = parseFloat(data.quantityCompleted) || 0;
    const progressPercent = total > 0 ? (completed / total) * 100 : 0;
    const lastComment = card.comments && card.comments.length ? card.comments[card.comments.length-1] : null;
    return `
        <div id="card-${card.id}" class="kanban-card rounded-lg border border-slate-200 p-3 shadow-sm group ${st.class} ${deadlineClass}" onclick="app.openCardModal(${card.id})">
            <div class="flex justify-between">
                <span class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${st.badge}">${st.label}</span>
                <button onclick="event.stopPropagation(); app.cloneCard(${card.id})" class="opacity-0 group-hover:opacity-100 text-slate-400"><i data-lucide="copy" class="w-3.5 h-3.5"></i></button>
            </div>
            <h4 class="text-sm font-semibold mt-1">${escapeHtml(data.title || 'Без названия')}</h4>
            ${data.client ? `<p class="text-xs text-slate-500 truncate">${escapeHtml(data.client)}</p>` : ''}
            ${total > 0 ? `
                <div class="mt-2"><div class="progress-bar"><div class="progress-fill" style="width:${progressPercent}%"></div></div>
                <div class="text-[10px] text-slate-500 mt-0.5">${completed}/${total} шт</div></div>
            ` : ''}
            <div class="flex justify-between items-center text-[10px] text-slate-400 mt-2 pt-1 border-t">
                ${data.deadline ? `📅 ${formatDate(data.deadline)}` : ''}
                <span>👤 ${data.assignee ? escapeHtml(data.assignee.split(' ')[0]) : '-'}</span>
            </div>
            ${lastComment ? `<div class="mt-2 text-xs text-slate-500 truncate border-t pt-1"><i data-lucide="message-circle" class="w-3 h-3 inline"></i> ${escapeHtml(lastComment.text.substring(0,50))}</div>` : ''}
        </div>
    `;
}

function updateStats() {
    const projectCards = cards.filter(c => c.projectId === currentProjectId);
    const done = projectCards.filter(c => c.data?.status === 'done').length;
    const statsEl = document.getElementById('boardStats');
    if (statsEl) statsEl.innerHTML = `Задач: ${projectCards.length} | Исполнено: ${done} | Колонок: ${columns.length}`;
}

// ------------------------- Drag & Drop -------------------------
let draggedCardId = null;

app.handleDragStart = (e, cardId) => {
    draggedCardId = cardId;
    e.dataTransfer.setData('text/plain', cardId);
    const el = document.getElementById(`card-${cardId}`);
    if (el) el.classList.add('card-ghost');
};
app.handleDragEnd = (e, cardId) => {
    draggedCardId = null;
    const el = document.getElementById(`card-${cardId}`);
    if (el) el.classList.remove('card-ghost');
    document.querySelectorAll('.column-drag-over').forEach(c => c.classList.remove('column-drag-over'));
};
app.handleDragOver = (e, colId) => {
    const colDiv = document.querySelector(`div[data-column-id="${colId}"] .column-scroll`);
    if (colDiv) colDiv.classList.add('column-drag-over');
    e.preventDefault();
};
app.handleDragLeave = (e, colId) => {
    const colDiv = document.querySelector(`div[data-column-id="${colId}"] .column-scroll`);
    if (colDiv) colDiv.classList.remove('column-drag-over');
};
app.handleDrop = async (e, columnId) => {
    e.preventDefault();
    const colDiv = document.querySelector(`div[data-column-id="${columnId}"] .column-scroll`);
    if (colDiv) colDiv.classList.remove('column-drag-over');
    const cardId = e.dataTransfer.getData('text/plain');
    if (!cardId) return;
    const card = cards.find(c => c.id == cardId);
    if (card && card.columnId !== columnId) {
        try {
            await apiRequest(`/api/kanban/cards/${cardId}`, 'PUT', { columnId });
            await refreshAll();
        } catch(e) { showError('Перемещение: ' + e.message); }
    }
};

// ------------------------- Колонки -------------------------
app.moveColumn = async (colId, direction) => {
    const idx = columns.findIndex(c => c.id === colId);
    if (idx === -1) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= columns.length) return;
    const newOrder = columns[newIdx].order;
    try {
        await apiRequest(`/api/kanban/columns/${colId}`, 'PUT', { order: newOrder });
        await refreshAll();
    } catch(e) { showError('Перемещение колонки: ' + e.message); }
};
app.deleteColumn = async (colId) => {
    const col = columns.find(c => c.id === colId);
    if (!col) return;
    if (!confirm(`Удалить колонку "${col.name}"? Все задачи будут перемещены в первую колонку.`)) return;
    try {
        await apiRequest(`/api/kanban/columns/${colId}`, 'DELETE');
        await refreshAll();
    } catch(e) { showError('Удаление колонки: ' + e.message); }
};
app.addColumnPrompt = async () => {
    let name = prompt('Название этапа:');
    if (name && name.trim()) {
        try {
            await apiRequest(`/api/kanban/projects/${currentProjectId}/columns`, 'POST', { name: name.trim() });
            await refreshAll();
        } catch(e) { showError('Добавление колонки: ' + e.message); }
    }
};

// ------------------------- Карточки -------------------------
app.openCardModal = async (cardId = null, columnId = null) => {
    currentCardId = cardId;
    const modal = document.getElementById('cardModal');
    const titleEl = document.getElementById('cardModalTitle');
    const deleteBtn = document.getElementById('deleteCardBtn');
    const fieldsContainer = document.getElementById('dynamicFields');
    
    if (!fieldsContainer) return;
    
    // Генерируем поля
    let fieldsHtml = `<div class="space-y-3">`;
    fields.sort((a,b) => a.order - b.order).forEach(field => {
        let value = '';
        if (cardId) {
            const card = cards.find(c => c.id === cardId);
            if (card && card.data) value = card.data[field.key] || '';
        }
        const label = escapeHtml(field.label);
        const fieldId = `field_${field.key}`;
        if (field.type === 'select') {
            let options = '';
            if (field.key === 'status') {
                options = `<option value="attention" ${value === 'attention' ? 'selected' : ''}>Требует внимания</option>
                           <option value="progress" ${value === 'progress' ? 'selected' : ''}>В работе</option>
                           <option value="done" ${value === 'done' ? 'selected' : ''}>Исполнено</option>`;
            } else if (field.options && Array.isArray(field.options)) {
                options = field.options.map(opt => `<option value="${escapeHtml(opt)}" ${value === opt ? 'selected' : ''}>${escapeHtml(opt)}</option>`).join('');
            }
            fieldsHtml += `<div><label class="block text-xs font-medium">${label}</label><select id="${fieldId}" class="w-full px-3 py-2 border rounded-lg text-sm">${options}</select></div>`;
        } else if (field.type === 'textarea') {
            fieldsHtml += `<div><label class="block text-xs font-medium">${label}</label><textarea id="${fieldId}" rows="2" class="w-full px-3 py-2 border rounded-lg text-sm">${escapeHtml(value)}</textarea></div>`;
        } else {
            fieldsHtml += `<div><label class="block text-xs font-medium">${label}</label><input type="${field.type}" id="${fieldId}" value="${escapeHtml(value)}" class="w-full px-3 py-2 border rounded-lg text-sm"></div>`;
        }
    });
    // Выбор колонки
    const colSelectHtml = `<div><label class="block text-xs font-medium">Этап</label><select id="cardColumn" class="w-full px-3 py-2 border rounded-lg text-sm">${columns.map(c => `<option value="${c.id}" ${(!cardId && columnId === c.id) || (cardId && cards.find(crd => crd.id === cardId)?.columnId === c.id) ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('')}</select></div>`;
    fieldsHtml += colSelectHtml + `</div>`;
    fieldsContainer.innerHTML = fieldsHtml;
    
    if (cardId) {
        titleEl.innerText = 'Редактирование задачи';
        deleteBtn.classList.remove('hidden');
        await app.renderComments(cardId);
    } else {
        titleEl.innerText = 'Новая задача';
        deleteBtn.classList.add('hidden');
        document.getElementById('commentsList').innerHTML = '';
    }
    modal.classList.remove('hidden');
    lucide.createIcons();
};
app.closeCardModal = () => {
    document.getElementById('cardModal').classList.add('hidden');
    currentCardId = null;
};
app.saveCard = async () => {
    const cardId = currentCardId;
    const columnId = parseInt(document.getElementById('cardColumn').value);
    
    let cardData = {};
    fields.forEach(field => {
        const el = document.getElementById(`field_${field.key}`);
        if (el) cardData[field.key] = el.value;
    });
    
    if (!cardData.title || cardData.title.trim() === '') {
        alert('Название задачи обязательно');
        return;
    }
    
    try {
        if (cardId) {
            await apiRequest(`/api/kanban/cards/${cardId}`, 'PUT', { data: cardData, columnId });
        } else {
            await apiRequest('/api/kanban/cards', 'POST', { projectId: currentProjectId, columnId, data: cardData });
        }
        await refreshAll();
        app.closeCardModal();
    } catch(e) {
        showError('Ошибка сохранения: ' + e.message);
    }
};

app.deleteCurrentCard = async () => {
    if (!currentCardId) return;
    if (confirm('Удалить задачу?')) {
        try {
            await apiRequest(`/api/kanban/cards/${currentCardId}`, 'DELETE');
            await refreshAll();
            app.closeCardModal();
        } catch(e) { showError('Удаление задачи: ' + e.message); }
    }
};
app.cloneCard = async (cardId) => {
    const original = cards.find(c => c.id === cardId);
    if (!original) return;
    const newData = { ...original.data, title: original.data.title + ' (копия)' };
    try {
        await apiRequest('/api/kanban/cards', 'POST', { projectId: currentProjectId, columnId: original.columnId, data: newData });
        await refreshAll();
    } catch(e) { showError('Копирование: ' + e.message); }
};

// ------------------------- Комментарии -------------------------
app.renderComments = async (cardId) => {
    const card = cards.find(c => c.id === cardId);
    const container = document.getElementById('commentsList');
    if (!container || !card) return;
    const sortedComments = [...(card.comments || [])].reverse();
    container.innerHTML = sortedComments.length ? sortedComments.map(cmt => `
        <div class="p-3 rounded-lg border ${cmt.isUrgent ? 'comment-urgent' : 'bg-white'}">
            <div class="flex justify-between items-start">
                <div>
                    <b class="text-sm">${escapeHtml(cmt.author)}</b>
                    ${cmt.isUrgent ? '<span class="ml-2 text-xs text-red-500">⚠️ Срочно</span>' : ''}
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-[10px] text-slate-400">${new Date(cmt.timestamp).toLocaleString()}</span>
                    <button type="button" onclick="app.deleteComment(${cmt.id}, ${cardId})" class="text-red-500 hover:text-red-700 p-1" title="Удалить">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>
                </div>
            </div>
            <p class="text-sm mt-1">${escapeHtml(cmt.text)}</p>
            ${cmt.files && cmt.files.length ? `<div class="flex flex-wrap gap-2 mt-2">${cmt.files.map(f => `<a href="${f.url}" target="_blank" class="text-xs text-ice-600">${escapeHtml(f.name)}</a>`).join('')}</div>` : ''}
        </div>
    `).join('') : '<div class="text-center text-slate-400 py-4">Нет комментариев</div>';
    lucide.createIcons();
};

app.addComment = async () => {
    const cardId = currentCardId;
    if (!cardId) return;
    const text = document.getElementById('newCommentText').value.trim();
    if (!text) return alert('Введите текст комментария');
    const isUrgent = document.getElementById('commentUrgent').checked;
    const filesInput = document.getElementById('commentFiles');
    
    if (filesInput.files.length === 0 && !text) {
        return alert('Введите текст или приложите файл');
    }

    const sendBtn = document.querySelector('#commentFiles + button');
    const originalText = sendBtn.innerHTML;
    sendBtn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> Загрузка...';
    sendBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('text', text);
        formData.append('isUrgent', isUrgent);
        for (let file of filesInput.files) {
            formData.append('files', file);
        }

        const response = await fetch(`/api/kanban/cards/${cardId}/comments`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) throw new Error(await response.text());

        await loadCards();
        await app.renderComments(cardId);
        
        document.getElementById('newCommentText').value = '';
        document.getElementById('commentUrgent').checked = false;
        filesInput.value = '';

        renderBoard();
    } catch (e) {
        console.error('Ошибка:', e);
        alert('Ошибка добавления комментария: ' + e.message);
    } finally {
        sendBtn.innerHTML = originalText;
        sendBtn.disabled = false;
        lucide.createIcons();
    }
};

app.deleteComment = async (commentId, cardId) => {
    if (!confirm('Удалить комментарий? Это действие необратимо.')) return;
    try {
        await apiRequest(`/api/kanban/comments/${commentId}`, 'DELETE');
        await loadCards();
        await app.renderComments(cardId);   // важно: app.renderComments
        renderBoard();
    } catch (e) {
        alert('Ошибка удаления: ' + e.message);
    }
};

// ------------------------- Проекты (список, переименование, удаление) -------------------------
app.openProjectModal = async () => {
    await renderProjectsList();
    document.getElementById('projectModal').classList.remove('hidden');
    lucide.createIcons();
};
app.closeProjectModal = () => {
    document.getElementById('projectModal').classList.add('hidden');
};
async function renderProjectsList() {
    const container = document.getElementById('projectsList');
    if (!container) return;
    container.innerHTML = projects.map(p => `
        <div class="flex justify-between items-center p-3 bg-slate-50 rounded">
            <div><b>${escapeHtml(p.name)}</b><div class="text-xs">${new Date(p.createdAt).toLocaleDateString()}</div></div>
            <div class="flex gap-1">
                <button onclick="app.renameProject(${p.id})" class="p-1 text-slate-500 hover:text-ice-600" title="Переименовать"><i data-lucide="pencil" class="w-4 h-4"></i></button>
                <button onclick="app.switchProject(${p.id})" class="p-1 text-ice-600"><i data-lucide="check" class="w-4 h-4"></i></button>
                <button onclick="app.deleteProject(${p.id})" class="p-1 text-red-500"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
            </div>
        </div>
    `).join('');
    lucide.createIcons();
}
app.createProject = async () => {
    let name = prompt('Название нового проекта');
    if (name && name.trim()) {
        try {
            await apiRequest('/api/kanban/projects', 'POST', { name: name.trim() });
            await loadProjects();
            await renderProjectsList();
            if (!currentProjectId && projects.length) currentProjectId = projects[0].id;
            await refreshAll();
        } catch(e) { showError('Создание проекта: ' + e.message); }
    }
};
app.renameProject = async (projectId) => {
    const project = projects.find(p => p.id === projectId);
    if (!project) return;
    let newName = prompt('Новое название проекта', project.name);
    if (newName && newName.trim() && newName.trim() !== project.name) {
        try {
            await apiRequest(`/api/kanban/projects/${projectId}`, 'PUT', { name: newName.trim() });
            await loadProjects();
            await renderProjectsList();
            renderProjectSelector();
        } catch(e) { showError('Переименование: ' + e.message); }
    }
};
app.switchProject = async (projectId) => {
    currentProjectId = projectId;
    await refreshAll();
    renderProjectSelector();
    app.closeProjectModal();
};
app.deleteProject = async (projectId) => {
    if (projects.length <= 1) {
        alert('Нельзя удалить последний проект');
        return;
    }
    if (!confirm('Удалить проект? Все связанные задачи также будут удалены.')) return;
    try {
        await apiRequest(`/api/kanban/projects/${projectId}`, 'DELETE');
        await loadProjects();
        if (currentProjectId === projectId) currentProjectId = projects[0]?.id || null;
        await refreshAll();
        renderProjectsList();
        renderProjectSelector();
    } catch(e) { showError('Удаление проекта: ' + e.message); }
};

// ------------------------- Сводка (Dashboard) -------------------------
app.openDashboardModal = async () => {
    await renderDashboard();
    document.getElementById('dashboardModal').classList.remove('hidden');
    lucide.createIcons();
};
app.closeDashboardModal = () => {
    document.getElementById('dashboardModal').classList.add('hidden');
};
async function renderDashboard() {
    const container = document.getElementById('dashboardContent');
    let html = '<div class="grid grid-cols-1 md:grid-cols-2 gap-4">';
    for (let proj of projects) {
        const projCards = cards.filter(c => c.projectId === proj.id);
        const total = projCards.length;
        const done = projCards.filter(c => c.data?.status === 'done').length;
        const attention = projCards.filter(c => c.data?.status === 'attention').length;
        const overdue = projCards.filter(c => c.data?.deadline && new Date(c.data.deadline) < new Date()).length;
        html += `
            <div class="stat-card">
                <h3 class="font-bold text-lg">${escapeHtml(proj.name)}</h3>
                <div class="grid grid-cols-2 gap-2 mt-2 text-sm">
                    <div>📋 Задач: ${total}</div>
                    <div>✅ Исполнено: ${done}</div>
                    <div>⚠️ Требуют внимания: ${attention}</div>
                    <div>🔴 Просрочено: ${overdue}</div>
                </div>
                <div class="w-full bg-slate-200 rounded-full h-2 mt-2"><div class="bg-ice-600 h-2 rounded-full" style="width:${total ? Math.round(done/total*100) : 0}%"></div></div>
            </div>
        `;
    }
    html += '</div>';
    container.innerHTML = html;
}

// ------------------------- Настройка полей -------------------------
app.openFieldEditorModal = async () => {
    await renderFieldsEditor();
    document.getElementById('fieldEditorModal').classList.remove('hidden');
    lucide.createIcons();
};
app.closeFieldEditorModal = () => {
    document.getElementById('fieldEditorModal').classList.add('hidden');
};
async function renderFieldsEditor() {
    const container = document.getElementById('fieldsList');
    if (!container) return;
    container.innerHTML = fields.sort((a,b) => a.order - b.order).map(f => `
        <div class="flex items-center gap-3 p-2 border rounded-lg bg-white" data-field-id="${f.id}">
            <i data-lucide="grip-vertical" class="w-4 h-4 text-slate-400 cursor-move"></i>
            <input type="text" value="${escapeHtml(f.label)}" class="flex-1 text-sm border rounded px-2 py-1 field-label" data-id="${f.id}">
            <select class="text-sm border rounded px-2 py-1 field-type" data-id="${f.id}">
                ${['text','number','date','textarea','select'].map(t => `<option ${f.type === t ? 'selected' : ''}>${t}</option>`).join('')}
            </select>
            <input type="checkbox" class="field-show" data-id="${f.id}" ${f.showOnCard ? 'checked' : ''}>
            <button onclick="app.removeField(${f.id})" class="text-red-500 p-1"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
        </div>
    `).join('');
    // Сохранение изменений (можно добавить обработчики)
    document.querySelectorAll('.field-label').forEach(inp => inp.addEventListener('change', async (e) => {
        const id = parseInt(inp.dataset.id);
        const newLabel = inp.value;
        try {
            await apiRequest(`/api/kanban/fields/${id}`, 'PUT', { label: newLabel });
            await loadFields();
        } catch(e) { showError('Ошибка обновления поля'); }
    }));
    document.querySelectorAll('.field-type').forEach(sel => sel.addEventListener('change', async (e) => {
        const id = parseInt(sel.dataset.id);
        const newType = sel.value;
        try {
            await apiRequest(`/api/kanban/fields/${id}`, 'PUT', { type: newType });
            await loadFields();
        } catch(e) { showError('Ошибка обновления типа'); }
    }));
    document.querySelectorAll('.field-show').forEach(chk => chk.addEventListener('change', async (e) => {
        const id = parseInt(chk.dataset.id);
        const show = chk.checked;
        try {
            await apiRequest(`/api/kanban/fields/${id}`, 'PUT', { showOnCard: show });
            await loadFields();
        } catch(e) { showError('Ошибка обновления видимости'); }
    }));
    lucide.createIcons();
}
app.addCustomField = async () => {
    const newKey = 'field_' + Date.now();
    try {
        await apiRequest(`/api/kanban/projects/${currentProjectId}/fields`, 'POST', {
            key: newKey,
            label: 'Новое поле',
            type: 'text',
            showOnCard: true,
            order: fields.length
        });
        await loadFields();
        await renderFieldsEditor();
    } catch(e) { showError('Добавление поля: ' + e.message); }
};
app.removeField = async (fieldId) => {
    if (!confirm('Удалить поле? Данные в карточках для этого поля будут потеряны.')) return;
    try {
        await apiRequest(`/api/kanban/fields/${fieldId}`, 'DELETE');
        await loadFields();
        await renderFieldsEditor();
    } catch(e) { showError('Удаление поля: ' + e.message); }
};

// ------------------------- Шаблоны -------------------------
app.openTemplatesModal = async () => {
    await renderTemplatesList();
    document.getElementById('templatesModal').classList.remove('hidden');
    lucide.createIcons();
};
app.closeTemplatesModal = () => {
    document.getElementById('templatesModal').classList.add('hidden');
};
async function renderTemplatesList() {
    let templates = [];
    try {
        templates = await apiRequest('/api/kanban/templates');
    } catch(e) { showError('Загрузка шаблонов: ' + e.message); return; }
    const listContainer = document.getElementById('templatesList');
    const emptyMsg = document.getElementById('emptyTemplates');
    if (!templates.length) {
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        if (listContainer) listContainer.innerHTML = '';
        return;
    }
    if (emptyMsg) emptyMsg.classList.add('hidden');
    if (listContainer) {
        listContainer.innerHTML = templates.map(t => `
            <div class="flex justify-between p-2 border rounded">
                <div><div>${escapeHtml(t.name)}</div><div class="text-xs">${t.columns.length} этапов, ${t.fields?.length || 0} полей</div></div>
                <div>
                    <button onclick="app.applyTemplate(${t.id})" class="p-1 text-ice-600"><i data-lucide="check"></i></button>
                    <button onclick="app.deleteTemplate(${t.id})" class="p-1 text-red-500"><i data-lucide="trash-2"></i></button>
                </div>
            </div>
        `).join('');
    }
    lucide.createIcons();
}
app.openSaveTemplateModal = () => {
    document.getElementById('saveTemplateModal').classList.remove('hidden');
    document.getElementById('templateNameInput').value = '';
};
app.closeSaveTemplateModal = () => {
    document.getElementById('saveTemplateModal').classList.add('hidden');
};
app.confirmSaveTemplate = async () => {
    const name = document.getElementById('templateNameInput').value.trim();
    if (!name) return alert('Введите название шаблона');
    const columnsConfig = columns.map(c => c.name);
    const fieldsConfig = fields.map(f => ({
        key: f.key, label: f.label, type: f.type, options: f.options, showOnCard: f.showOnCard, order: f.order
    }));
    try {
        await apiRequest('/api/kanban/templates', 'POST', { name, columns: columnsConfig, fields: fieldsConfig });
        app.closeSaveTemplateModal();
        alert('Шаблон сохранён');
    } catch(e) { showError('Ошибка сохранения шаблона'); }
};
app.applyTemplate = async (templateId) => {
    let template;
    try {
        const templates = await apiRequest('/api/kanban/templates');
        template = templates.find(t => t.id === templateId);
        if (!template) throw new Error('Шаблон не найден');
    } catch(e) { showError('Загрузка шаблона: ' + e.message); return; }
    if (!confirm(`Применить шаблон "${template.name}"? Текущие колонки и поля будут заменены.`)) return;
    try {
        // Удалить существующие колонки
        for (let col of columns) await apiRequest(`/api/kanban/columns/${col.id}`, 'DELETE');
        for (let colName of template.columns) {
            await apiRequest(`/api/kanban/projects/${currentProjectId}/columns`, 'POST', { name: colName });
        }
        // Удалить существующие поля
        for (let field of fields) await apiRequest(`/api/kanban/fields/${field.id}`, 'DELETE');
        for (let f of template.fields) {
            await apiRequest(`/api/kanban/projects/${currentProjectId}/fields`, 'POST', {
                key: f.key, label: f.label, type: f.type, options: f.options || [], showOnCard: f.showOnCard, order: f.order
            });
        }
        await refreshAll();
        app.closeTemplatesModal();
    } catch(e) { showError('Применение шаблона: ' + e.message); }
};
app.deleteTemplate = async (templateId) => {
    if (!confirm('Удалить шаблон?')) return;
    try {
        await apiRequest(`/api/kanban/templates/${templateId}`, 'DELETE');
        await renderTemplatesList();
    } catch(e) { showError('Удаление шаблона: ' + e.message); }
};

// ------------------------- Инициализация -------------------------
async function init() {
    console.log('Инициализация Kanban');
    await loadProjects();
    if (projects.length) {
        await refreshAll();
    } else {
        // Создаём проект по умолчанию
        try {
            await apiRequest('/api/kanban/projects', 'POST', { name: 'Основной проект' });
            await loadProjects();
            await refreshAll();
        } catch(e) { showError('Создание проекта по умолчанию: ' + e.message); }
    }
    lucide.createIcons();
}

// Глобальный объект app (должен быть доступен для onclick)
window.app = {
    openProjectModal: app.openProjectModal,
    closeProjectModal: app.closeProjectModal,
    createProject: app.createProject,
    renameProject: app.renameProject,
    switchProject: app.switchProject,
    deleteProject: app.deleteProject,
    openDashboardModal: app.openDashboardModal,
    closeDashboardModal: app.closeDashboardModal,
    openFieldEditorModal: app.openFieldEditorModal,
    closeFieldEditorModal: app.closeFieldEditorModal,
    addCustomField: app.addCustomField,
    removeField: app.removeField,
    openTemplatesModal: app.openTemplatesModal,
    closeTemplatesModal: app.closeTemplatesModal,
    openSaveTemplateModal: app.openSaveTemplateModal,
    closeSaveTemplateModal: app.closeSaveTemplateModal,
    confirmSaveTemplate: app.confirmSaveTemplate,
    applyTemplate: app.applyTemplate,
    deleteTemplate: app.deleteTemplate,
    openCardModal: app.openCardModal,
    closeCardModal: app.closeCardModal,
    saveCard: app.saveCard,
    deleteCurrentCard: app.deleteCurrentCard,
    cloneCard: app.cloneCard,
    addComment: app.addComment,
    renderComments: app.renderComments,
	deleteComment: app.deleteComment,
    addColumnPrompt: app.addColumnPrompt,
    deleteColumn: app.deleteColumn,
    moveColumn: app.moveColumn,
    handleDragStart: app.handleDragStart,
    handleDragEnd: app.handleDragEnd,
    handleDragOver: app.handleDragOver,
    handleDragLeave: app.handleDragLeave,
    handleDrop: app.handleDrop,
    refreshAll: refreshAll,
    closeImagePreview: () => document.getElementById('imagePreviewModal')?.classList.add('hidden')
};
app.init = async function() {
    console.log('Инициализация Kanban...');
    await loadProjects();
    if (projects.length) {
        await refreshAll();
    } else {
        // Создать проект по умолчанию, если нет
        await apiRequest('/api/kanban/projects', 'POST', { name: 'Основной проект' });
        await loadProjects();
        await refreshAll();
    }
    lucide.createIcons();
};
// Запуск после загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
    init().catch(console.error);
});