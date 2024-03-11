from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from passlib.hash import sha256_crypt
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'MFDS'
conn = sqlite3.connect('goals.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        goal TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        deadline DATETIME,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')


conn.commit()

cursor.execute('SELECT COUNT(*) FROM users')
user_count = cursor.fetchone()[0]

if user_count == 0:
    print("No registered users. Redirecting to the registration page.")

def update_expired_goals():
    current_datetime = datetime.now()
    cursor.execute('UPDATE goals SET status = "expired" WHERE deadline <= ?', (current_datetime,))
    conn.commit()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('goals'))
    return redirect(url_for('register'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('goals'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        user = cursor.fetchone()

        if user and sha256_crypt.verify(password, user[2]):
            session['user_id'] = user[0]
            flash('Login successful!', 'success')
            update_expired_goals()  # Check and update expired goals
            return redirect(url_for('goals'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('goals'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed_password = sha256_crypt.hash(password)

        cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Username already exists. Please choose a different username.', 'error')
        else:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/goals')
def goals():
    if 'user_id' not in session:
        flash('Please log in to view your goals.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']

    update_expired_goals()  # Check and update expired goals

    cursor.execute('SELECT * FROM goals WHERE user_id=?', (user_id,))
    user_goals = cursor.fetchall()

    # Fetch user-specific statistics
    cursor.execute('SELECT COUNT(*) FROM goals WHERE user_id=? AND status="completed"', (user_id,))
    completed_goals_count = cursor.fetchone()[0]

    return render_template('goals.html', goals=user_goals, completed_goals_count=completed_goals_count)

@app.route('/add_goal', methods=['POST'])
def add_goal():
    if 'user_id' not in session:
        flash('Please log in to add goals.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    goal_text = request.form['goal']
    deadline_date = request.form['deadline_date']
    deadline_time = request.form['deadline_time']

    deadline_str = f'{deadline_date} {deadline_time}'
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')

    cursor.execute('INSERT INTO goals (user_id, goal, deadline) VALUES (?, ?, ?)', (user_id, goal_text, deadline))
    conn.commit()

    flash('Goal added successfully!', 'success')
    return redirect(url_for('goals'))

@app.route('/remove_goal/<int:goal_id>')
def remove_goal(goal_id):
    if 'user_id' not in session:
        flash('Please log in to remove goals.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']

    cursor.execute('SELECT * FROM goals WHERE id=? AND user_id=?', (goal_id, user_id))
    goal = cursor.fetchone()

    if not goal:
        flash('Invalid goal ID or unauthorized access.', 'error')
        return redirect(url_for('goals'))

    cursor.execute('DELETE FROM goals WHERE id=? AND user_id=?', (goal_id, user_id))
    conn.commit()

    flash('Goal removed successfully!', 'success')
    return redirect(url_for('goals'))

@app.route('/update_status/<int:goal_id>/<status>')
def update_status(goal_id, status):
    if 'user_id' not in session:
        flash('Please log in to update goal status.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']

    if status == 'completed':
        cursor.execute('''
            UPDATE goals 
            SET status=?, deadline=datetime("now", "localtime", "+2 hours") 
            WHERE id=? AND user_id=?
        ''', (status, goal_id, user_id))
        conn.commit()
    elif status == 'removed':
        cursor.execute('DELETE FROM goals WHERE id=? AND user_id=?', (goal_id, user_id))
        conn.commit()
    elif status == 'pending':
        cursor.execute('UPDATE goals SET status=? WHERE id=? AND user_id=?', (status, goal_id, user_id))
        conn.commit()

    flash('Goal status updated successfully!', 'success')
    return redirect(url_for('goals'))

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    flash('Logout successful!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
       app.run(debug=True)

