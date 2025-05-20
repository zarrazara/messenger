from flask import Flask, render_template, redirect, request, url_for
from flask_socketio import SocketIO, emit, join_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Message
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
socketio = SocketIO(app, async_mode='eventlet')  # render-friendly
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_chat_partners(user_id):
    sent = db.session.query(Message.recipient_id).filter(Message.sender_id == user_id)
    received = db.session.query(Message.sender_id).filter(Message.recipient_id == user_id)
    user_ids = sent.union(received).distinct().all()
    ids = [uid[0] for uid in user_ids]
    return User.query.filter(User.id.in_(ids)).all()


@socketio.on('join')
def on_join(data):
    user_id = data['user_id']
    room = f"user_{user_id}"
    join_room(room)


@socketio.on('send_message')
def handle_send_message(data):
    content = data.get('message')
    recipient_id = data.get('recipient_id')
    if not content or not recipient_id:
        return

    sender_id = current_user.id
    msg = Message(sender_id=sender_id, recipient_id=recipient_id, body=content)
    db.session.add(msg)
    db.session.commit()

    # Отправка получателю
    room = f"user_{recipient_id}"
    emit('receive_message', {
        'username': current_user.username,
        'message': content
    }, to=room)

    # И отправителю
    sender_room = f"user_{sender_id}"
    emit('receive_message', {
        'username': current_user.username,
        'message': content
    }, to=sender_room)


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('chat'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/chat')
@login_required
def chat():
    chat_partners = get_chat_partners(current_user.id)
    return render_template('chat_list.html', chat_partners=chat_partners)


@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat_with_user(user_id):
    other_user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        msg_body = request.form.get('message')
        if msg_body:
            msg = Message(sender_id=current_user.id, recipient_id=other_user.id, body=msg_body)
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('chat_with_user', user_id=user_id))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', other_user=other_user, messages=messages)


@app.route('/users')
@login_required
def users_list():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('users.html', users=users)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000)
