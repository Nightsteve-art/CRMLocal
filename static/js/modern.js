// Modern UI Components JavaScript

class Modal {
  constructor(element) {
    this.modal = element;
    this.closeBtn = element.querySelector('.modal__close');
    this.init();
  }

  init() {
    this.closeBtn?.addEventListener('click', () => this.close());
    this.modal.addEventListener('click', (e) => {
      if (e.target === this.modal) this.close();
    });
  }

  open() {
    this.modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  close() {
    this.modal.classList.remove('active');
    document.body.style.overflow = 'auto';
  }
}

class Dropdown {
  constructor(element) {
    this.dropdown = element;
    this.trigger = element.querySelector('.dropdown__trigger');
    this.menu = element.querySelector('.dropdown__menu');
    this.init();
  }

  init() {
    this.trigger.addEventListener('click', () => this.toggle());
    this.menu.querySelectorAll('.dropdown__item').forEach(item => {
      item.addEventListener('click', () => this.close());
    });
    document.addEventListener('click', (e) => {
      if (!this.dropdown.contains(e.target)) this.close();
    });
  }

  toggle() {
    this.menu.classList.toggle('active');
  }

  close() {
    this.menu.classList.remove('active');
  }
}

class Tabs {
  constructor(element) {
    this.container = element;
    this.tabs = element.querySelectorAll('.tab');
    this.contents = element.querySelectorAll('.tab-content');
    this.init();
  }

  init() {
    this.tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => this.activate(index));
    });
  }

  activate(index) {
    this.tabs.forEach(t => t.classList.remove('active'));
    this.contents.forEach(c => c.classList.remove('active'));
    this.tabs[index].classList.add('active');
    this.contents[index].classList.add('active');
  }
}

class Alert {
  constructor(element) {
    this.alert = element;
    const closeBtn = element.querySelector('.alert__close');
    closeBtn?.addEventListener('click', () => this.close());
  }

  close() {
    this.alert.style.animation = 'fadeOut 0.2s ease-out';
    setTimeout(() => this.alert.remove(), 200);
  }

  static show(message, type = 'primary', duration = 5000) {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} slide-in`;
    alert.innerHTML = `
      <div class="alert__icon">ℹ️</div>
      <div>${message}</div>
      <button class="alert__close">✕</button>
    `;
    document.body.appendChild(alert);
    
    const instance = new Alert(alert);
    if (duration) {
      setTimeout(() => instance.close(), duration);
    }
    return instance;
  }
}

class DataTable {
  constructor(element) {
    this.table = element;
    this.rows = element.querySelectorAll('tbody tr');
    this.setupSorting();
  }

  setupSorting() {
    const headers = this.table.querySelectorAll('th');
    headers.forEach((header, index) => {
      if (header.dataset.sort !== 'false') {
        header.style.cursor = 'pointer';
        header.addEventListener('click', () => this.sortColumn(index));
      }
    });
  }

  sortColumn(index) {
    const rows = Array.from(this.rows);
    const isAsc = this.table.dataset.sortAsc === 'true';
    
    rows.sort((a, b) => {
      const aVal = a.cells[index].textContent.trim();
      const bVal = b.cells[index].textContent.trim();
      
      if (!isNaN(aVal) && !isNaN(bVal)) {
        return isAsc ? aVal - bVal : bVal - aVal;
      }
      return isAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });

    rows.forEach(row => this.table.querySelector('tbody').appendChild(row));
    this.table.dataset.sortAsc = !isAsc;
  }
}

class Notification {
  static show(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };
    
    notification.className = `notification notification-${type} slide-in`;
    notification.innerHTML = `
      <span>${icons[type]}</span>
      <span>${message}</span>
    `;
    
    const container = document.getElementById('notifications') || 
      (function() {
        const div = document.createElement('div');
        div.id = 'notifications';
        div.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 10000; max-width: 400px;';
        document.body.appendChild(div);
        return div;
      })();
    
    container.appendChild(notification);
    
    if (duration) {
      setTimeout(() => {
        notification.style.animation = 'fadeOut 0.2s ease-out';
        setTimeout(() => notification.remove(), 200);
      }, duration);
    }
    
    return notification;
  }
}

class Form {
  constructor(formElement) {
    this.form = formElement;
    this.setupValidation();
  }

  setupValidation() {
    this.form.addEventListener('submit', (e) => {
      if (!this.validate()) {
        e.preventDefault();
      }
    });
  }

  validate() {
    let isValid = true;
    this.form.querySelectorAll('[required]').forEach(field => {
      this.clearError(field);
      if (!field.value.trim()) {
        this.setError(field, 'Это поле обязательно');
        isValid = false;
      } else if (field.type === 'email' && !this.isValidEmail(field.value)) {
        this.setError(field, 'Введите корректный email');
        isValid = false;
      }
    });
    return isValid;
  }

  isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  setError(field, message) {
    field.classList.add('error');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'form-group__error';
    errorDiv.textContent = message;
    field.parentElement.appendChild(errorDiv);
  }

  clearError(field) {
    field.classList.remove('error');
    const errorDiv = field.parentElement.querySelector('.form-group__error');
    errorDiv?.remove();
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  // Modals
  document.querySelectorAll('.modal').forEach(el => new Modal(el));
  
  // Dropdowns
  document.querySelectorAll('.dropdown').forEach(el => new Dropdown(el));
  
  // Tabs
  document.querySelectorAll('[class*="tabs"]').forEach(el => new Tabs(el));
  
  // Tables
  document.querySelectorAll('table').forEach(el => new DataTable(el));
  
  // Forms
  document.querySelectorAll('form').forEach(el => new Form(el));
  
  // Toggle sidebar on mobile
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.layout__sidebar');
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
      sidebar?.classList.toggle('active');
    });
  }
});

// Export for use in other scripts
window.Modal = Modal;
window.Dropdown = Dropdown;
window.Tabs = Tabs;
window.Alert = Alert;
window.Notification = Notification;
window.Form = Form;
window.DataTable = DataTable;
