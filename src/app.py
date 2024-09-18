import os
import logging
import uuid
import re
from datetime import datetime, timedelta, UTC
from typing import Type
from sqlalchemy.sql import func

from flask import Flask, abort, jsonify, render_template, request, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.sql.functions import current_user

from config import DevelopmentConfig, ProductionConfig

MAX_USERNAME_LENGTH = 20
MAX_MESSAGE_LENGTH = 200
DEFAULT_USERNAME = "Guest"

db = SQLAlchemy()
socket_io = SocketIO(cors_allowed_origins="*")


class BaseVerifier:
    checks = {}
    default = ""

    def __init__(self, text):
        self.valid = True
        for error, check in self.checks.items():
            if not check(text):
                self.valid = False
        self.text = text if self.valid else self.default


class MessageVerifier(BaseVerifier):
    checks = {
        "Message should be between 1 and 200": lambda text: 1 <= len(text) <= MAX_MESSAGE_LENGTH
    }
    default = " "


class UsernameVerifier(BaseVerifier):
    checks = {
        "Username should be between 1 and 20 characters": lambda text: 1 <= len(text) <= MAX_USERNAME_LENGTH,
        "The System user cannot be used": lambda text: text.lower() != 'system',
    }
    default = DEFAULT_USERNAME


class ChatroomError(ValueError):
    pass


class Chatroom(db.Model):
    id = db.Column(db.String, primary_key=True)
    messages = db.relationship('Message', backref='chatroom', lazy=True)
    users = db.relationship('User', backref='chatroom', lazy=True)

class User(db.Model):
    id = db.Column(db.String, primary_key=True)
    chatroom_id = db.Column(db.String, db.ForeignKey('chatroom.id'), nullable=False)
    username = db.Column(db.String, nullable=False)
    messages = db.relationship('Message', backref='user', lazy=True)
    addr = db.Column(db.String, nullable=False)
    is_system = db.Column(db.Boolean, default=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chatroom_id = db.Column(
        db.String,
        db.ForeignKey('chatroom.id'),
        nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('user.id'), nullable=False)  # Reference User by id
    content = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.DateTime, default=func.now())  # Use func.now() for proper SQLAlchemy default


# Configure logging
logging.basicConfig(level=logging.INFO)


def wsgi(*args):
    app = Flask(__name__)

    # Load configuration
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    CORS(app)
    db.init_app(app)
    socket_io.init_app(app)

    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=app.config['STORAGE_URI'],
        storage_options={"socket_connect_timeout": 30},
        default_limits=app.config['LIMITER_DEFAULTS'],
        strategy="fixed-window",  # or "moving-window"
    )

    with app.app_context():
        db.create_all()



    @app.route('/')
    def index():
        room_id = request.args.get('room_code', '')
        return render_template('index.html', room_id=room_id)

    @app.route('/room/<code>', methods=['GET'])
    def chatroom(code):
        try:
            chat_room = get_room(code)

            return render_template('chatroom.html', code=chat_room.id)
        except ChatroomError as e:
            return abort(404, description=str(e))

    @app.route('/create_room', methods=['POST'])
    def create_room():
        code = str(uuid.uuid4())
        new_room = Chatroom(id=code)

        db.session.add(new_room)
        db.session.commit()
        logging.info(f'Room created: {code}')
        return jsonify({'code': code})

    # Socket event handlers
    @socket_io.on('join')
    def on_join(data):
        username = UsernameVerifier(sanitize_input(data.get('username', DEFAULT_USERNAME)))
        code = data.get('code', '')
        try:
            chat_room = get_room(code)
            user = add_user(request.sid, chat_room.id, username.text, request.remote_addr)
            join_room(chat_room.id)
            previous_messages = Message.query.filter_by(chatroom_id=chat_room.id).all()
            current_users = User.query.filter_by(chatroom_id=chat_room.id).all()
            current_users = sorted(current_users, key=lambda u: u.username)
            for msg in previous_messages:
                emit('update', {'username': User.query.filter_by(chatroom_id=chat_room.id, id=msg.user_id).first().username, 'message': msg.content})
            for _user in current_users:
                if not _user.is_system:
                    emit('user_join', {'username': _user.username})
            system_msg(chat_room.id, f"{username.text} has joined the chat")
        except ChatroomError as e:
            emit('error', {'error': 'Chatroom not found'})
            return abort(404, description=str(e))

    @socket_io.on('new_message')
    def on_new_message(data):
        username = UsernameVerifier(sanitize_input(data.get('username', DEFAULT_USERNAME)))
        message = MessageVerifier(sanitize_input(data.get('message', "")))
        code = data.get('code', '')
        new_message(code, username.text, message.text)

    @socket_io.on('disconnect')
    def on_disconnect():
        user = User.query.filter_by(id=request.sid).first()
        if user:
            leave_room(user.chatroom_id)
            emit('user_leave', {'username': user.username})
            system_msg(user.chatroom_id, f'{user.username} has disconnected.')
            del_user(user)

    return app


def get_room(code) -> Type[Chatroom]:
    room = Chatroom.query.filter_by(id=code).first()
    if room:
        return room
    else:
        raise ChatroomError(f"Room with code {code} not found")


def add_user(socket_id, chatroom_id, username, sock_addr, is_system=False):
    user = User.query.filter_by(chatroom_id=chatroom_id, username=username).first()
    if not user:
        user = User(id=socket_id, chatroom_id=chatroom_id, username=username, addr=sock_addr, is_system=is_system)
        db.session.add(user)
        db.session.commit()
    return user

def del_user(user: User):
    if user:
        db.session.delete(user)
        db.session.commit()


def new_message(chatroom_id, username, message):
    user = User.query.filter_by(username=username, chatroom_id=chatroom_id).first()
    if not user:
        print(user)
    new_msg = Message(chatroom_id=chatroom_id, user_id=user.id, content=message)  # Use user_id instead of username
    socket_io.emit('update', {'username': username, 'message': message}, room=chatroom_id)
    db.session.add(new_msg)
    db.session.commit()

def system_msg(chatroom_id, message):
    # Find or create a system user
    system_user = User.query.filter_by(is_system=True, chatroom_id=chatroom_id).first()
    if not system_user:
        system_user = User(id=str(uuid.uuid4()), chatroom_id=chatroom_id, username='System', is_system=True, addr='system')
        db.session.add(system_user)
        db.session.commit()

    new_msg = Message(chatroom_id=chatroom_id, user_id=system_user.id, content=message)
    socket_io.emit('update', {'username': 'System', 'message': message}, room=chatroom_id)
    db.session.add(new_msg)
    db.session.commit()

def sanitize_input(input_str):
    # Basic sanitization to allow only alphanumeric and space
    return re.sub(r'[^a-zA-Z0-9\s]', '', input_str)


if __name__ == '__main__':
    app = wsgi()
    socket_io.run(app, '0.0.0.0', port=10000, log_output=True, use_reloader=False, allow_unsafe_werkzeug=True)