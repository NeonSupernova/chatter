import logging
import uuid
import re
from datetime import datetime, timedelta, UTC
from typing import Type

from flask import Flask, abort, jsonify, render_template, request, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.orm import Session


MAX_USERNAME_LENGTH = 20
MAX_MESSAGE_LENGTH = 200
DEFAULT_USERNAME = "Guest"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatrooms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)
limiter = Limiter(
    get_remote_address,  # You can adjust this to use a custom key if needed
    app=app,
    default_limits=["200 per day", "50 per hour"],  # Example default limits
)
socket_io = SocketIO(app)
db = SQLAlchemy(app)

class BaseVerifier:
    checks = {}
    default = ""
    def __init__(self, text):
        self.valid = True
        for error, check in self.checks.items():
            if not check(text):
                self.valid = False
        if self.valid:
            self.text = text
        else:
            self.text = self.default


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


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chatroom_id = db.Column(
        db.String,
        db.ForeignKey('chatroom.id'),
        nullable=False)
    username = db.Column(db.String, nullable=False)
    content = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(UTC))


# Configure logging
logging.basicConfig(level=logging.INFO)

# Function to sanitize input
def sanitize_input(input_str):
    # Basic sanitization to allow only alphanumeric and space
    return re.sub(r'[^a-zA-Z0-9\s]', '', input_str)

with app.app_context():
    db.create_all()

def get_room(code) -> Type[Chatroom]:
    room = Chatroom.query.filter_by(id=code).first()
    if room:
        return room
    else:
        raise ChatroomError(f"Room with code {code} not found")

def new_message(chatroom_id, username, message):
    new_msg = Message(chatroom_id=chatroom_id, username=username, content=message)
    socket_io.emit('update', {'username': username, 'message': message})
    db.session.add(new_msg)
    db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room/<code>', methods=['GET'])
def chatroom(code):
    try:
        chat_room = get_room(code)
        return render_template('chatroom.html', code=chat_room.id)
    except ChatroomError as e:
        return abort(404, description=e)


@app.route('/create_room', methods=['POST'])
def create_room():
    code = str(uuid.uuid4())
    new_room = Chatroom(id=code)

    with Session(db.engine) as session:
        session.add(new_room)
        session.commit()

    logging.info(f'Room created: {code}')
    return jsonify({'code': code})

@socket_io.on('join')
def on_join(data):
    print("SOMEONE JOINED")
    username = UsernameVerifier(sanitize_input(data.get('username', DEFAULT_USERNAME)))
    code = data.get('code', '')
    try:
        chat_room = get_room(code)
        join_room(chat_room.id)
        previous_messages = Message.query.filter_by(chatroom_id=chat_room.id).all()
        for msg in previous_messages:
            emit('update', {'username': msg.username, 'message': msg.content})
        new_message(chat_room.id, 'System', f"{username.text} has joined the chat")
    except ChatroomError as e:
        emit('error', {'error': 'Chatroom not found'})
        return abort(404, description=e)

@socket_io.on('new_message')
def on_new_message(data):
    username = UsernameVerifier(sanitize_input(data.get('username', DEFAULT_USERNAME)))
    message = MessageVerifier(sanitize_input(data.get('message', "")))
    code = data.get('code', '')
    new_message(code, username.text, message.text)

@socket_io.on('disconnect')
def on_disconnect():
    # Retrieve user details if stored in the session or elsewhere
    # Perform any cleanup if necessary
    emit('update', {'username': 'System', 'message': 'A user has disconnected.'})

if __name__ == '__main__':
    socket_io.run(app, '0.0.0.0', port=80, log_output=True, use_reloader=False, allow_unsafe_werkzeug=True)
