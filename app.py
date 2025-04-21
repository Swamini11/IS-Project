from flask import Flask, request, render_template, redirect, url_for, session
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret-key'
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DB Initialization ---
def init_db():
    conn = sqlite3.connect('site_data.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )''')

    # Create admin table
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )''')

    # Create issues table
    cursor.execute('''CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        location TEXT,
        description TEXT,
        image_path TEXT,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # Create feedback table
    cursor.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        comment TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # Insert default users and admin if they don't already exist
    cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'user1', 'pass1')")
    cursor.execute("INSERT OR IGNORE INTO admin (id, username, password) VALUES (1, 'admin', 'admin123')")
    cursor.execute("INSERT OR IGNORE INTO admin (id, username, password) VALUES (2, 'admin2', 'admin*123')")
    #cursor.execute("DELETE from feedback")
    
    conn.commit()
    conn.close()


# --- Routes ---
@app.route('/')
def home():
    return render_template('home.html')  # Add a link to the registration page

@app.route('/login_choice', methods=['POST'])
def login_choice():
    role = request.form['role']  # Get the selected role from the form
    if role == 'user':
        return redirect(url_for('user_login'))  # Redirect to user login
    elif role == 'admin':
        return redirect(url_for('admin_login'))  # Redirect to admin login
    else:
        return redirect(url_for('home'))  # Default redirect to home if something goes wrong


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the user already exists
        conn = sqlite3.connect('site_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            # If user exists, show a message
            return render_template('register.html', message="Username already exists.")
        
        # If the user doesn't exist, add them to the database
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()

        # Redirect to login page after successful registration
        return redirect(url_for('user_login'))

    return render_template('register.html')


@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('site_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            return redirect(url_for('user_dashboard'))
        else:
            return render_template('user_login.html', message='Invalid credentials')
    return render_template('user_login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('site_data.db')
        cursor = conn.cursor()

        # 🚨 VULNERABLE TO SQL INJECTION (for demo purposes only)
        query = f"SELECT * FROM admin WHERE username = '{username}' AND password = '{password}'"
        cursor.execute(query)

        admin = cursor.fetchone()
        conn.close()
        if admin:
            session['admin_id'] = admin[0]
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', message='Invalid credentials')
    return render_template('admin_login.html')


@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    return render_template('user_dashboard.html')

@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    if request.method == 'POST':
        location = request.form['location']
        description = request.form['description']
        file = request.files.get('image')
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
        conn = sqlite3.connect('site_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO issues (user_id, location, description, image_path) VALUES (?, ?, ?, ?)",
                       (session['user_id'], location, description, filename))
        conn.commit()
        conn.close()
        return redirect(url_for('user_dashboard'))
    return render_template('report_issue.html')

@app.route('/my_issues', methods=['GET'])
def my_issues():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    issues = []
    city = request.args.get('city')  # Supports ?city=...

    conn = sqlite3.connect('site_data.db')
    cursor = conn.cursor()

    if city:
        # WARNING: Vulnerable to SQL injection
        query = f"""
            SELECT location, description, image_path, status
            FROM issues
            WHERE user_id = {session['user_id']} AND location LIKE '%{city}%'
        """
        cursor.execute(query)
    else:
        cursor.execute("""
            SELECT location, description, image_path, status
            FROM issues
            WHERE user_id = ?
        """, (session['user_id'],))

    issues = cursor.fetchall()
    conn.close()

    return render_template('user_issues.html', issues=issues, city=city)



@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    issues = []
    feedbacks = []

    # Get city filter (from GET or POST)
    if request.method == 'POST':
        city = request.form.get('location')
    else:
        city = request.args.get('city')

    conn = sqlite3.connect('site_data.db')
    cursor = conn.cursor()

    if city:
        cursor.execute("""
            SELECT issues.id, users.username, location, description, image_path, status
            FROM issues
            JOIN users ON issues.user_id = users.id
            WHERE location LIKE ?
        """, ('%' + city + '%',))
    else:
        cursor.execute("""
            SELECT issues.id, users.username, location, description, image_path, status
            FROM issues
            JOIN users ON issues.user_id = users.id
        """)
    
    issues = cursor.fetchall()

    # Always fetch feedbacks
    cursor.execute("""
        SELECT feedback.id, users.username, feedback.comment
        FROM feedback
        JOIN users ON feedback.user_id = users.id
    """)
    feedbacks = cursor.fetchall()

    conn.close()

    return render_template('admin_dashboard.html', issues=issues, feedbacks=feedbacks, city=city)





@app.route('/update_status/<int:issue_id>', methods=['POST'])
def update_status(issue_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    new_status = request.form['status']  # read from POST form
    conn = sqlite3.connect('site_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE issues SET status = ? WHERE id = ?", (new_status, issue_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        comment = request.form['comment']
        conn = sqlite3.connect('site_data.db')
        cursor = conn.cursor()
        try:
            cursor.executescript(f"INSERT INTO feedback (user_id, comment) VALUES ({session['user_id']}, '{comment}');")
            conn.commit()
        except Exception as e:
            print("SQL Injection Error:", e)
        conn.close()
        return redirect(url_for('user_login'))

    return render_template('feedback.html')


@app.route('/logout')
def logout():
    # Check if it's a user or admin session and clear it
    if 'user_id' in session:
        session.pop('user_id', None)  # Remove the user session
        return redirect(url_for('user_login'))  # Redirect to user login page
    
    elif 'admin_id' in session:
        session.pop('admin_id', None)  # Remove the admin session
        return redirect(url_for('admin_login'))  # Redirect to admin login page
    
    # If no user or admin session is found, redirect to the home page
    return redirect(url_for('home'))



# --- Run App ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
