from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from wtforms import PasswordField
from werkzeug.security import generate_password_hash

class AdminView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        from flask import redirect, url_for, flash
        flash('Bạn cần quyền admin để truy cập', 'danger')
        return redirect(url_for('index'))

class UserAdminView(AdminView):
    column_list = ['id', 'username', 'is_admin', 'agreed_terms', 'created_at']
    column_searchable_list = ['username']
    column_filters = ['is_admin', 'agreed_terms']
    form_columns = ['username', 'password', 'is_admin', 'agreed_terms']
    form_extra_fields = {
        'password': PasswordField('Mật khẩu')
    }
    
    def on_model_change(self, form, model, is_created):
        if form.password.data:
            model.password = generate_password_hash(form.password.data)

class ChatAdminView(AdminView):
    column_list = ['id', 'name', 'chat_type', 'created_at']
    column_searchable_list = ['name']
    column_filters = ['chat_type']

class MessageAdminView(AdminView):
    column_list = ['id', 'chat_id', 'user_id', 'content', 'timestamp']
    column_searchable_list = ['content']
    column_filters = ['chat_id', 'user_id']