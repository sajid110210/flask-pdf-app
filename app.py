
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

DATABASE = 'database.db'

class User(UserMixin):
    def __init__(self, id_, username, password, is_admin):
        self.id = id_
        self.username = username
        self.password = password
        self.is_admin = is_admin

# User loader callback
@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password, is_admin FROM users WHERE id=?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(*user)
    return None

# DB init function
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    filename TEXT,
                    status TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                    )''')
    # Insert default admin if not exists
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)', ('admin', 'admin', 1))
    conn.commit()
    conn.close()


@app.route('/')
@login_required
def index():
    if current_user.is_admin:
        # Admin view: show all uploads
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT uploads.id, users.username, uploads.filename, uploads.status FROM uploads 
                          LEFT JOIN users ON uploads.user_id = users.id''')
        uploads = cursor.fetchall()
        conn.close()
        return render_template('admin.html', uploads=uploads)
    else:
        # User view: show user's uploads
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, filename, status FROM uploads WHERE user_id=?', (current_user.id,))
        uploads = cursor.fetchall()
        conn.close()
        return render_template('user.html', uploads=uploads)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password, is_admin FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        if user and user[2] == password:
            user_obj = User(*user)
            login_user(user_obj)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        # Insert into DB with status 'Processing'
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO uploads (user_id, filename, status) VALUES (?, ?, ?)', 
                       (current_user.id, filename, 'Processing'))
        conn.commit()
        conn.close()
        flash('File uploaded successfully')
    else:
        flash('Only PDF files allowed')
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
    