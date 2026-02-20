from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
import hashlib
import random
import string
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'firemess-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# База данных
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация БД
with get_db() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     phone TEXT UNIQUE,
                     password TEXT,
                     name TEXT,
                     status TEXT DEFAULT 'offline',
                     last_seen TIMESTAMP)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS messages
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     sender TEXT,
                     receiver TEXT,
                     text TEXT,
                     time TIMESTAMP,
                     is_read BOOLEAN DEFAULT 0)''')

online_users = {}

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'users_online': len(online_users)
    })

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    phone = data.get('phone')
    password = hashlib.sha256(data.get('password').encode()).hexdigest()
    name = data.get('name')
    
    try:
        with get_db() as conn:
            conn.execute('INSERT INTO users (phone, password, name, last_seen) VALUES (?, ?, ?, ?)',
                        (phone, password, name, datetime.now()))
        return jsonify({'success': True, 'code': '123456'})  # Для демо
    except:
        return jsonify({'error': 'User exists'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    phone = data.get('phone')
    password = hashlib.sha256(data.get('password').encode()).hexdigest()
    
    with get_db() as conn:
        user = conn.execute('SELECT phone, name FROM users WHERE phone=? AND password=?',
                          (phone, password)).fetchone()
    
    if user:
        return jsonify({'success': True, 'user': dict(user)})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/users')
def get_users():
    phone = request.args.get('phone')
    with get_db() as conn:
        users = conn.execute('''SELECT phone, name, status, last_seen 
                               FROM users WHERE phone != ?''', (phone,)).fetchall()
    return jsonify({'users': [dict(u) for u in users]})

@app.route('/api/messages')
def get_messages():
    user = request.args.get('user')
    contact = request.args.get('contact')
    
    with get_db() as conn:
        messages = conn.execute('''SELECT * FROM messages 
                                 WHERE (sender=? AND receiver=?) 
                                 OR (sender=? AND receiver=?)
                                 ORDER BY time DESC LIMIT 50''',
                              (user, contact, contact, user)).fetchall()
    return jsonify({'messages': [dict(m) for m in messages]})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('user_online')
def handle_online(data):
    phone = data['phone']
    online_users[phone] = request.sid
    emit('user_status', {'phone': phone, 'status': 'online'}, broadcast=True)

@socketio.on('send_message')
def handle_message(data):
    with get_db() as conn:
        conn.execute('INSERT INTO messages (sender, receiver, text, time) VALUES (?, ?, ?, ?)',
                   (data['sender'], data['receiver'], data['text'], datetime.now()))
    
    if data['receiver'] in online_users:
        emit('new_message', data, room=online_users[data['receiver']])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
