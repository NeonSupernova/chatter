import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from enum import verify
from typing import Type, Any

from flask import Flask, abort, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session


MAX_USERNAME_LENGTH = 20
MAX_MESSAGE_LENGTH = 200
DEFAULT_USERNAME = "Guest"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatrooms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)
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
        "Message should be between 1 and 200": lambda text: len(text) == 0 or len(text) > MAX_MESSAGE_LENGTH
    }
    default = " "


class UsernameVerifier(BaseVerifier):
    checks = {
        "Message should be between 1 and 200": lambda message: len(message) == 0 or len(message) > MAX_USERNAME_LENGTH,
        "the System user cannot be used": lambda text: text.lower() == 'system',
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


rate_limit = defaultdict(lambda: {'last_message_time': datetime.min, 'message_count': 0})

# Configure logging
logging.basicConfig(level=logging.INFO)

# Function to sanitize input
def sanitize_input(input_str):
    return input_str
    #return ''.join(e for e in input_str if e.isalnum() or e.isspace())

with app.app_context():
    db.create_all()

def get_room(code) -> Type[Chatroom]:
    with Session(db.engine) as session:
        room = session.query(Chatroom).filter_by(id=code).first()
        if room:
            return room
        else:
            raise ChatroomError(f"Room with code {code} not found")

def new_message(chatroom_id, username, message):
    new_msg = Message(chatroom_id=chatroom_id, username=username, content=message)
    #socket_io.emit('new_message', {'username': username, 'message': message}, room=chatroom_id)
    with Session(db.engine) as session:
        session.add(new_msg)
        session.commit()


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

@app.route('/api/room/<code>/messages', methods=['GET', 'POST'])
def messages(code):
    try:
        chat_room = get_room(code)
    except ChatroomError as e:
        return abort(404, description=e)
    
    if request.method == 'POST':
        data = request.json
        username = UsernameVerifier(sanitize_input(data.get('username', DEFAULT_USERNAME)))
        message = MessageVerifier(sanitize_input(data.get('message', '')))

        # Rate limiting check
        now = datetime.now()
        if now - rate_limit[username.text]['last_message_time'] < timedelta(seconds=5):
            rate_limit[username.text]['message_count'] += 1
            if rate_limit[username.text]['message_count'] > 3:
                return jsonify({'error': 'Rate limit exceeded. Please wait.'}), 429
        else:
            rate_limit[username.text] = {'last_message_time': now, 'message_count': 1}

        new_message(chat_room.id, username.text, message.text)
        return jsonify({'status': 'Message sent'}), 201
    else:
        return jsonify({'status': 'Message not sent.'}), 200


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
    username = UsernameVerifier(sanitize_input(data.get('username', DEFAULT_USERNAME)))
    #message = MessageVerifier(sanitize_input(data.get('message', '')))
    code = data.get('code', '')
    try:
        chat_room = get_room(code)
        join_room(chat_room.id)
        new_message(chat_room.id, 'System', f"{username.text} has joined the chat")
        previous_messages = Message.query.filter_by(chatroom_id=chat_room.id).all()
        for msg in previous_messages:
            emit('new_message', {'username': msg.username, 'message': msg.content})
    except ChatroomError as e:
        emit('error', {'error': 'Chatroom not found'})
        return abort(404, description=e)


@socket_io.on('disconnect')
def on_disconnect():
    # Handle user disconnection events if needed
    pass

if __name__ == '__main__':
    socket_io.run(app, '0.0.0.0', port=80, log_output=True, use_reloader=False, allow_unsafe_werkzeug=True)
