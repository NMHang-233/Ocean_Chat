from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_admin import Admin
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Chat, ChatMember, Message, Reaction
from admin import AdminView, UserAdminView, ChatAdminView, MessageAdminView
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ban-hay-doi-secret-key-nay-trong-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Cấu hình upload file (chat)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'mov', 'avi', 'pdf', 'doc', 'docx', 'txt', 'zip'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Cấu hình avatar
app.config['AVATAR_FOLDER'] = 'static/avatars'
ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_avatar(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

admin = Admin(app, name='OceanChat Admin', template_mode='bootstrap4')
admin.add_view(UserAdminView(User, db.session))
admin.add_view(ChatAdminView(Chat, db.session))
admin.add_view(MessageAdminView(Message, db.session))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_user_chats(user_id):
    chats = Chat.query.join(ChatMember).filter(ChatMember.user_id == user_id).all()
    result = []
    for chat in chats:
        last_msg = Message.query.filter_by(chat_id=chat.id).order_by(Message.timestamp.desc()).first()
        other_user = None
        if chat.chat_type == 'private':
            other_member = ChatMember.query.filter(ChatMember.chat_id == chat.id, ChatMember.user_id != user_id).first()
            if other_member:
                other_user = User.query.get(other_member.user_id)
        result.append({
            'chat': chat,
            'last_message': last_msg,
            'other_user': other_user,
            'name': chat.name if chat.name else (other_user.username if other_user else 'Chat riêng')
        })
    return result

def can_send_message(user_id, chat_id):
    chat = Chat.query.get(chat_id)
    if not chat:
        return False
    if chat.chat_type == 'channel':
        member = ChatMember.query.filter_by(user_id=user_id, chat_id=chat_id).first()
        return member and member.role == 'admin'
    else:
        return ChatMember.query.filter_by(user_id=user_id, chat_id=chat_id).first() is not None

@app.route('/')
@login_required
def index():
    chats = get_user_chats(current_user.id)
    return render_template('index.html', chats=chats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if not user.agreed_terms:
                flash('Vui lòng chấp nhận điều khoản trước khi đăng nhập.', 'warning')
                return redirect(url_for('terms', user_id=user.id))
            login_user(user)
            return redirect(url_for('index'))
        flash('Sai tên đăng nhập hoặc mật khẩu', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        agree_terms = 'agree_terms' in request.form
        
        if not agree_terms:
            flash('Bạn phải đồng ý với điều khoản sử dụng', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại', 'danger')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            password=generate_password_hash(password),
            agreed_terms=False,
            is_admin=False
        )
        db.session.add(user)
        db.session.commit()
        
        session['pending_user_id'] = user.id
        return redirect(url_for('terms'))
    
    return render_template('register.html')

@app.route('/terms', methods=['GET', 'POST'])
def terms():
    if 'pending_user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['pending_user_id'])
    if not user:
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        if 'accept' in request.form:
            user.agreed_terms = True
            db.session.commit()
            session.pop('pending_user_id')
            flash('Đăng ký thành công! Hãy đăng nhập.', 'success')
            return redirect(url_for('login'))
        else:
            db.session.delete(user)
            db.session.commit()
            session.pop('pending_user_id')
            flash('Bạn phải chấp nhận điều khoản để sử dụng dịch vụ.', 'danger')
            return redirect(url_for('register'))
    
    return render_template('terms.html', username=user.username)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/chat/<int:chat_id>')
@login_required
def chat_room(chat_id):
    membership = ChatMember.query.filter_by(user_id=current_user.id, chat_id=chat_id).first()
    if not membership:
        flash('Bạn không phải thành viên của phòng chat này', 'danger')
        return redirect(url_for('index'))
    
    chat = Chat.query.get(chat_id)
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.timestamp.asc()).all()
    
    members = []
    for member in chat.members:
        user = User.query.get(member.user_id)
        members.append({
            'id': user.id,
            'username': user.username,
            'role': member.role
        })
    
    other_user = None
    if chat.chat_type == 'private':
        other_member = ChatMember.query.filter(ChatMember.chat_id == chat_id, ChatMember.user_id != current_user.id).first()
        if other_member:
            other_user = User.query.get(other_member.user_id)
    
    chat_name = chat.name if chat.name else (other_user.username if other_user else 'Chat riêng')
    
    return render_template('chat.html', 
                         chat=chat, 
                         messages=messages, 
                         members=members,
                         chat_name=chat_name,
                         can_send=can_send_message(current_user.id, chat_id))

@app.route('/create_chat', methods=['POST'])
@login_required
def create_chat():
    chat_type = request.form['type']
    name = request.form.get('name', '')
    
    if chat_type == 'private':
        other_username = request.form['other_username']
        other_user = User.query.filter_by(username=other_username).first()
        if not other_user:
            flash('Không tìm thấy người dùng', 'danger')
            return redirect(url_for('index'))
        
        user1_chats = [m.chat_id for m in ChatMember.query.filter_by(user_id=current_user.id).all()]
        user2_chats = [m.chat_id for m in ChatMember.query.filter_by(user_id=other_user.id).all()]
        common = set(user1_chats) & set(user2_chats)
        for chat_id in common:
            chat = Chat.query.get(chat_id)
            if chat and chat.chat_type == 'private':
                return redirect(url_for('chat_room', chat_id=chat_id))
        
        chat = Chat(chat_type='private')
        db.session.add(chat)
        db.session.flush()
        db.session.add(ChatMember(user_id=current_user.id, chat_id=chat.id, role='member'))
        db.session.add(ChatMember(user_id=other_user.id, chat_id=chat.id, role='member'))
        db.session.commit()
        return redirect(url_for('chat_room', chat_id=chat.id))
    
    elif chat_type == 'group':
        chat = Chat(chat_type='group', name=name)
        db.session.add(chat)
        db.session.flush()
        db.session.add(ChatMember(user_id=current_user.id, chat_id=chat.id, role='member'))
        member_ids = request.form.getlist('members')
        for uid in member_ids:
            if int(uid) != current_user.id:
                db.session.add(ChatMember(user_id=int(uid), chat_id=chat.id, role='member'))
        db.session.commit()
        return redirect(url_for('chat_room', chat_id=chat.id))
    
    elif chat_type == 'channel':
        chat = Chat(chat_type='channel', name=name)
        db.session.add(chat)
        db.session.flush()
        db.session.add(ChatMember(user_id=current_user.id, chat_id=chat.id, role='admin'))
        member_ids = request.form.getlist('members')
        for uid in member_ids:
            if int(uid) != current_user.id:
                db.session.add(ChatMember(user_id=int(uid), chat_id=chat.id, role='member'))
        db.session.commit()
        return redirect(url_for('chat_room', chat_id=chat.id))
    
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    chat_id = request.form.get('chat_id')
    
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    import time
    filename = f"{int(time.time())}_{name}{ext}"
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    file_url = url_for('static', filename=f'uploads/{filename}')
    
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        file_type = 'image'
    elif ext in ['mp4', 'webm', 'mov', 'avi']:
        file_type = 'video'
    else:
        file_type = 'document'
    
    msg = Message(
        chat_id=chat_id,
        user_id=current_user.id,
        content=f"📎 {file.filename}",
        file_url=file_url,
        file_type=file_type
    )
    db.session.add(msg)
    db.session.commit()
    
    socketio.emit('new_message', {
        'id': msg.id,
        'username': current_user.username,
        'content': msg.content,
        'file_url': msg.file_url,
        'file_type': msg.file_type,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'user_id': current_user.id
    }, room=f'chat_{chat_id}')
    
    return jsonify({'success': True, 'file_url': file_url})

@app.route('/react/<int:message_id>', methods=['POST'])
@login_required
def add_reaction(message_id):
    emoji = request.json.get('emoji')
    message = Message.query.get(message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    existing = Reaction.query.filter_by(message_id=message_id, user_id=current_user.id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        action = 'removed'
    else:
        old = Reaction.query.filter_by(message_id=message_id, user_id=current_user.id).first()
        if old:
            db.session.delete(old)
        reaction = Reaction(message_id=message_id, user_id=current_user.id, emoji=emoji)
        db.session.add(reaction)
        db.session.commit()
        action = 'added'
    
    reactions = {}
    for r in Reaction.query.filter_by(message_id=message_id).all():
        reactions[r.emoji] = reactions.get(r.emoji, 0) + 1
    
    socketio.emit('reaction_update', {
        'message_id': message_id,
        'reactions': reactions,
        'user_id': current_user.id,
        'emoji': emoji,
        'action': action
    }, room=f'chat_{message.chat_id}')
    
    return jsonify({'success': True, 'reactions': reactions})

@app.route('/search_users')
@login_required
def search_users():
    query = request.args.get('q', '')
    users = User.query.filter(User.username.contains(query), User.id != current_user.id).limit(10).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])

# ================= TRANG CÁ NHÂN & TÌM KIẾM =================

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        birthday_str = request.form.get('birthday')
        if birthday_str:
            current_user.birthday = datetime.strptime(birthday_str, '%Y-%m-%d')
        else:
            current_user.birthday = None
        current_user.hometown = request.form.get('hometown')
        current_user.interests = request.form.get('interests')
        current_user.bio = request.form.get('bio')
        db.session.commit()
        flash('Cập nhật thông tin thành công!', 'success')
        return redirect(url_for('profile', username=current_user.username))
    return render_template('edit_profile.html')

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        flash('Không có file', 'danger')
        return redirect(url_for('edit_profile'))
    file = request.files['avatar']
    if file.filename == '':
        flash('Chưa chọn file', 'danger')
        return redirect(url_for('edit_profile'))
    if file and allowed_avatar(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        filename = f"{current_user.id}_{int(datetime.now().timestamp())}{ext}"
        filepath = os.path.join(app.config['AVATAR_FOLDER'], filename)
        file.save(filepath)
        # Xóa avatar cũ nếu không phải default
        if current_user.avatar != 'default_avatar.png':
            old_path = os.path.join(app.config['AVATAR_FOLDER'], current_user.avatar)
            if os.path.exists(old_path):
                os.remove(old_path)
        current_user.avatar = filename
        db.session.commit()
        flash('Ảnh đại diện đã cập nhật!', 'success')
    else:
        flash('Định dạng không cho phép (chỉ PNG, JPG, GIF, WEBP)', 'danger')
    return redirect(url_for('edit_profile'))

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    users = User.query.filter(User.username.contains(query), User.id != current_user.id).limit(20).all()
    groups = Chat.query.filter(Chat.name.contains(query), Chat.chat_type.in_(['group', 'channel'])).limit(10).all()
    return render_template('search_results.html', query=query, users=users, groups=groups)

# ================= SOCKET.IO EVENTS =================

@socketio.on('join')
def handle_join(data):
    chat_id = data['chat_id']
    join_room(f'chat_{chat_id}')
    emit('user_joined', {'username': current_user.username}, room=f'chat_{chat_id}')

@socketio.on('leave')
def handle_leave(data):
    chat_id = data['chat_id']
    leave_room(f'chat_{chat_id}')
    emit('user_left', {'username': current_user.username}, room=f'chat_{chat_id}')

@socketio.on('send_message')
def handle_send_message(data):
    chat_id = data['chat_id']
    content = data['content'].strip()
    if not content:
        return
    
    if not can_send_message(current_user.id, chat_id):
        emit('error', {'msg': 'Bạn không có quyền gửi tin nhắn trong kênh này'})
        return
    
    msg = Message(
        chat_id=chat_id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(msg)
    db.session.commit()
    
    emit('new_message', {
        'id': msg.id,
        'username': current_user.username,
        'content': msg.content,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'user_id': current_user.id,
        'file_url': None,
        'file_type': None
    }, room=f'chat_{chat_id}')

@socketio.on('typing')
def handle_typing(data):
    chat_id = data['chat_id']
    is_typing = data['typing']
    emit('user_typing', {
        'username': current_user.username,
        'typing': is_typing
    }, room=f'chat_{chat_id}', include_self=False)

@socketio.on('call_offer')
def handle_call_offer(data):
    target_user_id = data['target_user_id']
    emit('call_offer', {
        'offer': data['offer'],
        'from_user_id': current_user.id,
        'from_username': current_user.username
    }, room=f'user_{target_user_id}')

@socketio.on('call_answer')
def handle_call_answer(data):
    target_user_id = data['target_user_id']
    emit('call_answer', {
        'answer': data['answer'],
        'from_user_id': current_user.id
    }, room=f'user_{target_user_id}')

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    target_user_id = data['target_user_id']
    emit('ice_candidate', {
        'candidate': data['candidate'],
        'from_user_id': current_user.id
    }, room=f'user_{target_user_id}')

@socketio.on('join_user_room')
def handle_join_user_room():
    join_room(f'user_{current_user.id}')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                password=generate_password_hash('admin123'),
                is_admin=True,
                agreed_terms=True,
                avatar='default_avatar.png'
            )
            db.session.add(admin_user)
            db.session.commit()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)