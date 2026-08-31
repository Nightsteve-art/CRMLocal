// JavaScript для управления заказами
document.addEventListener('DOMContentLoaded', function() {
    // Инициализация - добавляем первую позицию при загрузке
    addOrderItem();
    
    // Валидация формы
    const form = document.getElementById('orderForm');
    if (form) {
        form.addEventListener('submit', validateOrderForm);
    }
    
    // Обработка клавиш
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            form.dispatchEvent(new Event('submit'));
        }
    });
});

let itemCounter = 0;

// Добавление позиции заказа
function addOrderItem() {
    const container = document.getElementById('orderItemsContainer');
    const template = document.getElementById('orderItemTemplate');
    const clone = template.content.cloneNode(true);
    
    itemCounter++;
    
    // Обновляем номер позиции
    const itemNumber = clone.querySelector('.item-number');
    if (itemNumber) {
        itemNumber.textContent = itemCounter;
    }
    
    // Обновляем имена полей для корректной отправки формы
    const inputs = clone.querySelectorAll('[name]');
    inputs.forEach(input => {
        const name = input.getAttribute('name');
        if (name.includes('[]')) {
            input.setAttribute('name', name);
        }
    });
    
    container.appendChild(clone);
    updateItemsCount();
}

// Удаление позиции заказа
function removeOrderItem(button) {
    const item = button.closest('.order-item');
    if (item) {
        item.remove();
        itemCounter--;
        updateItemsCount();
        renumberItems();
    }
}

// Обновление счетчика позиций
function updateItemsCount() {
    const counter = document.getElementById('itemsCount');
    if (counter) {
        const items = document.querySelectorAll('.order-item').length;
        counter.textContent = `${items} ${getPluralForm(items, 'позиция', 'позиции', 'позиций')}`;
        
        // Блокируем кнопку отправки если нет позиций
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = items === 0;
        }
    }
}

// Перенумерация позиций
function renumberItems() {
    const items = document.querySelectorAll('.order-item');
    items.forEach((item, index) => {
        const itemNumber = item.querySelector('.item-number');
        if (itemNumber) {
            itemNumber.textContent = index + 1;
        }
    });
}

// Валидация формы заказа
function validateOrderForm(e) {
    let isValid = true;
    const errorMessages = [];
    
    // Проверяем наличие хотя бы одной позиции
    const items = document.querySelectorAll('.order-item');
    if (items.length === 0) {
        errorMessages.push('Добавьте хотя бы одну позицию в заказ');
        isValid = false;
    }
    
    // Проверяем каждую позицию
    items.forEach((item, index) => {
        const name = item.querySelector('.item-name');
        const quantity = item.querySelector('.item-quantity');
        
        if (name && !name.value.trim()) {
            errorMessages.push(`Позиция #${index + 1}: укажите наименование`);
            markInvalid(name);
            isValid = false;
        } else if (name) {
            markValid(name);
        }
        
        if (quantity) {
            const qty = parseFloat(quantity.value);
            if (isNaN(qty) || qty <= 0) {
                errorMessages.push(`Позиция #${index + 1}: укажите корректное количество`);
                markInvalid(quantity);
                isValid = false;
            } else {
                markValid(quantity);
            }
        }
    });
    
    if (!isValid) {
        e.preventDefault();
        
        // Показываем ошибки
        showValidationErrors(errorMessages);
        
        // Прокручиваем к первой ошибке
        const firstError = document.querySelector('.invalid');
        if (firstError) {
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            firstError.focus();
        }
    }
}

// Вспомогательные функции
function markInvalid(element) {
    element.classList.add('invalid');
    element.style.borderColor = 'var(--status-red)';
    
    let error = element.parentNode.querySelector('.error-message');
    if (!error) {
        error = document.createElement('div');
        error.className = 'error-message';
        error.style.cssText = `
            color: var(--status-red);
            font-size: 0.75rem;
            margin-top: 0.25rem;
        `;
        element.parentNode.appendChild(error);
    }
}

function markValid(element) {
    element.classList.remove('invalid');
    element.style.borderColor = '';
    
    const error = element.parentNode.querySelector('.error-message');
    if (error) error.remove();
}

function showValidationErrors(messages) {
    // Удаляем старые уведомления об ошибках
    const oldNotifications = document.querySelectorAll('.validation-error');
    oldNotifications.forEach(n => n.remove());
    
    // Создаем новое уведомление
    if (messages.length > 0) {
        const notification = document.createElement('div');
        notification.className = 'validation-error';
        notification.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            background: var(--status-red-light);
            color: var(--status-red);
            border: 2px solid var(--status-red);
            border-radius: var(--radius-lg);
            padding: 1rem 1.5rem;
            z-index: 10000;
            animation: slideInRight 0.3s ease;
            max-width: 400px;
            box-shadow: var(--shadow-xl);
            font-weight: 600;
        `;
        
        let html = `<div style="display: flex; align-items: flex-start; gap: 0.75rem;">
            <i class="fas fa-exclamation-triangle" style="font-size: 1.25rem; margin-top: 0.125rem;"></i>
            <div>
                <div style="font-weight: 700; margin-bottom: 0.5rem;">Исправьте ошибки:</div>
                <ul style="margin: 0; padding-left: 1rem; font-weight: normal;">`;
        
        messages.slice(0, 5).forEach(msg => {
            html += `<li style="margin-bottom: 0.25rem;">${msg}</li>`;
        });
        
        if (messages.length > 5) {
            html += `<li>... и еще ${messages.length - 5} ошибок</li>`;
        }
        
        html += `</ul></div></div>`;
        notification.innerHTML = html;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}

function getPluralForm(number, one, two, five) {
    number = Math.abs(number);
    number %= 100;
    if (number >= 5 && number <= 20) {
        return five;
    }
    number %= 10;
    if (number === 1) {
        return one;
    }
    if (number >= 2 && number <= 4) {
        return two;
    }
    return five;
}

// Функция для предварительного просмотра заказа
function previewOrder() {
    const items = [];
    const orderItems = document.querySelectorAll('.order-item');
    
    orderItems.forEach((item, index) => {
        const name = item.querySelector('.item-name').value;
        const quantity = item.querySelector('.item-quantity').value;
        const category = item.querySelector('.item-category').value;
        const workshop = item.querySelector('.item-workshop').value;
        
        if (name && quantity) {
            items.push({
                name,
                quantity: parseFloat(quantity),
                category,
                workshop: workshop || 'Не указан'
            });
        }
    });
    
    if (items.length === 0) {
        alert('Нет данных для предпросмотра');
        return;
    }
    
    // Здесь можно добавить логику для отображения предпросмотра
    console.log('Предпросмотр заказа:', items);
    
    // Простой alert для демонстрации
    let message = 'Предпросмотр заказа:\n\n';
    items.forEach((item, index) => {
        message += `${index + 1}. ${item.name} - ${item.quantity} (${item.category})\n`;
    });
    
    alert(message);
}