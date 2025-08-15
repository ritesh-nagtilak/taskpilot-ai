from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date, timedelta
import re
from functools import wraps
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
DATABASE = os.getenv('DATABASE_URL', 'instance/taskpilot.db')

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'General',
            priority TEXT DEFAULT 'Medium',
            due_date DATE,
            is_completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect('instance/taskpilot.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def process_chatbot_message(message, user_id):
    try:
        message = message.lower().strip()

        if any(word in message for word in ['show', 'list', 'display']) and 'task' in message:
            if 'today' in message:
                return get_today_tasks(user_id)
            elif 'completed' in message:
                return get_completed_tasks(user_id)
            elif 'pending' in message:
                return get_pending_tasks(user_id)
            else:
                return get_all_tasks(user_id)

        elif any(word in message for word in ['add', 'create', 'new']) and 'task' in message:
            return parse_add_task(message, user_id)

        elif any(word in message for word in ['complete', 'done', 'finish']) and 'task' in message:
            return parse_complete_task(message, user_id)

        elif any(word in message for word in ['delete', 'remove']) and 'task' in message:
            return parse_delete_task(message, user_id)

        elif any(word in message for word in ['help', 'commands']):
            return get_help_message()

        else:
            return "I'm not sure how to help with that. Type 'help' to see available commands."

    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}. Please try again."

def parse_add_task(message, user_id):
    patterns = [
        r'add\s+(?:high\s+priority\s+|urgent\s+|low\s+priority\s+)?task:?\s*(.+)',
        r'create\s+(?:high\s+priority\s+|urgent\s+|low\s+priority\s+)?task:?\s*(.+)',
        r'new\s+(?:high\s+priority\s+|urgent\s+|low\s+priority\s+)?task:?\s*(.+)'
    ]

    task_title = None
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            task_title = match.group(1).strip()
            break

    if not task_title:
        return "Please specify the task title. Example: 'Add task: Buy groceries'"

    due_date = None
    if 'today' in message:
        due_date = date.today()
    elif 'tomorrow' in message:
        due_date = date.today() + timedelta(days=1)

    priority = 'Medium'
    if 'high' in message or 'urgent' in message:
        priority = 'High'
    elif 'low' in message:
        priority = 'Low'

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO tasks (user_id, title, priority, due_date) VALUES (?, ?, ?, ?)',
        (user_id, task_title, priority, due_date)
    )
    conn.commit()
    conn.close()

    due_info = f" for {due_date}" if due_date else ""
    return f"✅ Task added: '{task_title}' ({priority} priority){due_info}"

def parse_complete_task(message, user_id):
    task_match = re.search(r'(?:complete|finish|done)\s+task\s*(\d+)', message, re.IGNORECASE)
    if task_match:
        task_id = int(task_match.group(1))
        conn = get_db_connection()
        result = conn.execute(
            'UPDATE tasks SET is_completed = 1 WHERE id = ? AND user_id = ?',
            (task_id, user_id)
        )
        conn.commit()

        if result.rowcount > 0:
            task = conn.execute('SELECT title FROM tasks WHERE id = ?', (task_id,)).fetchone()
            conn.close()
            return f"✅ Completed: '{task['title']}'"
        else:
            conn.close()
            return "Task not found."

    return "Please specify task ID. Example: 'Complete task 1'"

def parse_delete_task(message, user_id):
    task_match = re.search(r'(?:delete|remove)\s+task\s*(\d+)', message, re.IGNORECASE)
    if task_match:
        task_id = int(task_match.group(1))
        conn = get_db_connection()
        task = conn.execute('SELECT title FROM tasks WHERE id = ? AND user_id = ?', 
                          (task_id, user_id)).fetchone()

        if task:
            conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
            conn.commit()
            conn.close()
            return f"🗑️ Deleted: '{task['title']}'"
        else:
            conn.close()
            return "Task not found."

    return "Please specify task ID. Example: 'Delete task 1'"

def get_today_tasks(user_id):
    conn = get_db_connection()
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE user_id = ? AND due_date = ? ORDER BY priority DESC',
        (user_id, str(date.today()))
    ).fetchall()
    conn.close()

    if not tasks:
        return "No tasks due today."

    task_list = "📅 **Today's Tasks:**\n"
    for task in tasks:
        status = "✅" if task['is_completed'] else "⏳"
        task_list += f"{status} {task['title']} ({task['priority']})\n"

    return task_list

def get_completed_tasks(user_id):
    conn = get_db_connection()
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE user_id = ? AND is_completed = 1 ORDER BY updated_at DESC LIMIT 5',
        (user_id,)
    ).fetchall()
    conn.close()

    if not tasks:
        return "No completed tasks found."

    task_list = "✅ **Completed Tasks:**\n"
    for task in tasks:
        task_list += f"• {task['title']}\n"

    return task_list

def get_pending_tasks(user_id):
    conn = get_db_connection()
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE user_id = ? AND is_completed = 0 ORDER BY due_date ASC',
        (user_id,)
    ).fetchall()
    conn.close()

    if not tasks:
        return "No pending tasks."

    task_list = "⏳ **Pending Tasks:**\n"
    for task in tasks:
        due = f" (Due: {task['due_date']})" if task['due_date'] else ""
        task_list += f"• {task['title']}{due}\n"

    return task_list

def get_all_tasks(user_id):
    conn = get_db_connection()
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE user_id = ? ORDER BY is_completed, due_date ASC',
        (user_id,)
    ).fetchall()
    conn.close()

    if not tasks:
        return "No tasks yet. Try: 'Add task: Your task name'"

    pending = sum(1 for task in tasks if not task['is_completed'])
    completed = len(tasks) - pending

    return f"📊 **Summary:**\nTotal: {len(tasks)}\nPending: {pending}\nCompleted: {completed}"

def get_help_message():
    return '''🤖 **TaskPilot Commands:**

**View Tasks:**
• "Show my tasks" - All tasks
• "Show tasks for today" - Today's tasks
• "Show completed tasks" - Completed tasks
• "Show pending tasks" - Pending tasks

**Manage Tasks:**
• "Add task: [name]" - Create task
• "Add task: [name] tomorrow" - With due date
• "Add high priority task: [name]" - With priority
• "Complete task [id]" - Mark complete
• "Delete task [id]" - Remove task

**Examples:**
• "Add urgent task: Fix bug"
• "Show tasks for today"
• "Complete task 1"'''

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')

        conn = get_db_connection()
        if conn.execute('SELECT id FROM users WHERE username = ? OR email = ?', 
                       (username, email)).fetchone():
            flash('Username or email already exists.', 'error')
            conn.close()
            return render_template('register.html')

        conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, generate_password_hash(password)))
        conn.commit()
        conn.close()

        flash('Registration successful!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid credentials.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ? ORDER BY is_completed, due_date ASC',
                        (session['user_id'],)).fetchall()

    total = len(tasks)
    completed = sum(1 for task in tasks if task['is_completed'])
    pending = total - completed
    overdue = sum(1 for task in tasks if not task['is_completed'] and 
                 task['due_date'] and task['due_date'] < str(date.today()))

    stats = {'total': total, 'completed': completed, 'pending': pending, 'overdue': overdue}
    conn.close()

    return render_template('dashboard.html', tasks=tasks, stats=stats)

@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute(
            '''INSERT INTO tasks (user_id, title, description, category, priority, due_date)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (session['user_id'], request.form['title'], request.form.get('description', ''),
             request.form.get('category', 'General'), request.form.get('priority', 'Medium'),
             request.form.get('due_date') or None)
        )
        conn.commit()
        conn.close()

        flash('Task added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_task.html')

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?',
                       (task_id, session['user_id'])).fetchone()

    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        conn.execute(
            '''UPDATE tasks SET title = ?, description = ?, category = ?, priority = ?, 
               due_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?''',
            (request.form['title'], request.form.get('description', ''),
             request.form.get('category', 'General'), request.form.get('priority', 'Medium'),
             request.form.get('due_date') or None, task_id, session['user_id'])
        )
        conn.commit()
        conn.close()

        flash('Task updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('edit_task.html', task=task)

@app.route('/complete_task/<int:task_id>')
@login_required
def complete_task(task_id):
    conn = get_db_connection()
    conn.execute('UPDATE tasks SET is_completed = NOT is_completed WHERE id = ? AND user_id = ?',
                (task_id, session['user_id']))
    conn.commit()
    conn.close()

    flash('Task status updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_task/<int:task_id>')
@login_required
def delete_task(task_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, session['user_id']))
    conn.commit()
    conn.close()

    flash('Task deleted!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html')

@app.route('/chatbot/message', methods=['POST'])
@login_required
def chatbot_message():
    try:
        data = request.get_json()
        if not data or not data.get('message'):
            return jsonify({'response': 'Please enter a message.'})

        response = process_chatbot_message(data['message'], session['user_id'])
        return jsonify({'response': response})

    except Exception as e:
        return jsonify({'response': f'Error: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
