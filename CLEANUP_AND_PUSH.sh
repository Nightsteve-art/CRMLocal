#!/bin/bash

# 1. Удалить все старые шаблоны из Git
git rm --cached templates/calculator_new.html 2>/dev/null || true
git rm --cached templates/counterparties_new.html 2>/dev/null || true
git rm --cached templates/create_counterparty_new.html 2>/dev/null || true
git rm --cached templates/create_material_request_new.html 2>/dev/null || true
git rm --cached templates/create_order_new.html 2>/dev/null || true
git rm --cached templates/create_proposal_new.html 2>/dev/null || true
git rm --cached templates/create_sewing_task_new.html 2>/dev/null || true
git rm --cached templates/create_stock_item_new.html 2>/dev/null || true
git rm --cached templates/create_user_new.html 2>/dev/null || true
git rm --cached templates/dashboard_new.html 2>/dev/null || true
git rm --cached templates/edit_material_request_new.html 2>/dev/null || true
git rm --cached templates/edit_proposal_new.html 2>/dev/null || true
git rm --cached templates/edit_stock_item_new.html 2>/dev/null || true
git rm --cached templates/edit_user_new.html 2>/dev/null || true
git rm --cached templates/edit_counterparty_new.html 2>/dev/null || true
git rm --cached templates/edit_order_new.html 2>/dev/null || true
git rm --cached templates/import_stock_new.html 2>/dev/null || true
git rm --cached templates/index_new.html 2>/dev/null || true
git rm --cached templates/kanban_new.html 2>/dev/null || true
git rm --cached templates/kanban_board.html 2>/dev/null || true
git rm --cached templates/layout_new.html 2>/dev/null || true
git rm --cached templates/list_counterparties_new.html 2>/dev/null || true
git rm --cached templates/login_new.html 2>/dev/null || true
git rm --cached templates/main_new.html 2>/dev/null || true
git rm --cached templates/material_requests_new.html 2>/dev/null || true
git rm --cached templates/materials_new.html 2>/dev/null || true
git rm --cached templates/orders_new.html 2>/dev/null || true
git rm --cached templates/proposals_new.html 2>/dev/null || true
git rm --cached templates/sewing_new.html 2>/dev/null || true
git rm --cached templates/sewing_tasks_new.html 2>/dev/null || true
git rm --cached templates/stock_operation_new.html 2>/dev/null || true
git rm --cached templates/users_new.html 2>/dev/null || true
git rm --cached templates/view_counterparty_new.html 2>/dev/null || true
git rm --cached templates/view_order_new.html 2>/dev/null || true
git rm --cached templates/view_proposal_new.html 2>/dev/null || true
git rm --cached templates/view_sewing_task_new.html 2>/dev/null || true
git rm --cached templates/view_stock_item_new.html 2>/dev/null || true
git rm --cached templates/warehouse_new.html 2>/dev/null || true
git rm --cached templates/order_passport.html 2>/dev/null || true

echo "✅ Удалены все *_new.html файлы из Git Index"
