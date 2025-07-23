from flask import Flask, render_template, request, redirect, url_for, flash, abort,make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import sqlite3
import csv
from fpdf import FPDF
from io import StringIO
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
import os

# if os.environ.get('RENDER') == 'true':
#     # Use PostgreSQL in Render
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://task_tracker_db_kz0d_user:QKbK26YMMN6KktNZrAcn4aiaUftmohAr@dpg-d20hi47gi27c73ckorr0-a/task_tracker_db_kz0d'
# else:
#     # Use SQLite locally
#     app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ---------------- Models ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    is_complete = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    duration_seconds = db.Column(db.Integer, default=0)  # ⏱️ For time tracking

# ---------------- Load User ----------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#--------------------------------------


@app.route('/export/csv')
@login_required
def export_csv():
    tasks = Task.query.filter_by(user_id=current_user.id).all()

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['ID', 'Title', 'Description', 'Category', 'Status', 'Created At', 'Duration (s)'])

    # Write task rows
    for task in tasks:
        writer.writerow([
            task.id,
            task.title,
            task.description or '',
            task.category or '',
            'Completed' if task.is_complete else 'Pending',
            task.created_at.strftime('%Y-%m-%d %H:%M'),
            task.duration_seconds
        ])

    # Generate response
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=tasks.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/export/pdf')
@login_required
def export_pdf():
    tasks = Task.query.filter_by(user_id=current_user.id).all()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Task Report", ln=1, align='C')
    pdf.ln(10)

    for task in tasks:
        status = "Completed" if task.is_complete else "Pending"  # ✅ ← emoji removed
        pdf.cell(200, 10, txt=f"{task.title} ({status})", ln=1)
        pdf.multi_cell(0, 10, f"Description: {task.description or 'No description'}", align='L')
        pdf.cell(0, 10, txt=f"Category: {task.category or 'Uncategorized'}", ln=1)
        pdf.cell(0, 10, txt=f"Created At: {task.created_at.strftime('%Y-%m-%d %H:%M')}", ln=1)
        pdf.cell(0, 10, txt=f"Time Tracked: {task.duration_seconds} sec", ln=1)
        pdf.ln(5)

    response = make_response(pdf.output(dest='S').encode('latin1'))
    response.headers['Content-Disposition'] = 'attachment; filename=tasks.pdf'
    response.headers['Content-Type'] = 'application/pdf'
    return response


# ---------------- Utility ----------------
def add_missing_column():
    with sqlite3.connect("instance/users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(task)")
        columns = [col[1] for col in cursor.fetchall()]
        if "duration_seconds" not in columns:
            print("⏱️ Adding duration_seconds column …")
            cursor.execute("ALTER TABLE task ADD COLUMN duration_seconds INTEGER DEFAULT 0")
            print("✅ Column added.")

# ---------------- Routes ----------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        else:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Invalid credentials')
            return redirect(url_for('login'))

        login_user(user)  #Login first

        # then record login timestamp
        user.last_login_at = datetime.utcnow()
        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.')
    return redirect(url_for('login'))
# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    total = Task.query.filter_by(user_id=current_user.id).count()
    completed = Task.query.filter_by(user_id=current_user.id, is_complete=True).count()
    pending = Task.query.filter_by(user_id=current_user.id, is_complete=False).count()
    
    total_time = db.session.query(db.func.sum(Task.duration_seconds)).filter_by(user_id=current_user.id).scalar() or 0

    return render_template("dashboard.html", total=total, completed=completed, pending=pending, total_time=total_time)

@app.route('/tasks')
@login_required
def tasks():
    # --- read filter values from query string ---
    search_query  = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all')
    sort_option   = request.args.get('sort', 'latest')

    # --- base query restricted to current user ---
    query = Task.query.filter_by(user_id=current_user.id)

    # 🔍 search
    if search_query:
        query = query.filter(
            Task.title.ilike(f'%{search_query}%') |
            Task.description.ilike(f'%{search_query}%')
        )

    # ✅ status filter
    if status_filter == 'completed':
        query = query.filter_by(is_complete=True)
    elif status_filter == 'pending':
        query = query.filter_by(is_complete=False)

    # 🔽 sorting
    if sort_option == 'oldest':
        query = query.order_by(Task.created_at.asc())
    elif sort_option == 'title':
        query = query.order_by(Task.title.asc())
    else:                                # 'latest'
        query = query.order_by(Task.created_at.desc())

    all_tasks = query.all()

    # group by category
    grouped_tasks = {}
    for task in all_tasks:
        key = task.category or "Uncategorized"
        grouped_tasks.setdefault(key, []).append(task)

    return render_template(
        'tasks.html',
        grouped_tasks=grouped_tasks
    )

@app.route('/add-task', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        category = request.form.get('category')
        new_task = Task(title=title, description=description, category=category, user_id=current_user.id)
        db.session.add(new_task)
        db.session.commit()
        flash("Task added successfully!")
        return redirect(url_for('tasks'))

    return render_template('add_task.html')

@app.route('/edit-task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("You don't have permission to edit this task.")
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form.get('description')
        task.category = request.form.get('category')
        db.session.commit()
        flash("Task updated successfully!")
        return redirect(url_for('tasks'))

    return render_template('edit_task.html', task=task)

@app.route('/delete-task/<int:task_id>')
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("You don't have permission to delete this task.")
        return redirect(url_for('tasks'))

    db.session.delete(task)
    db.session.commit()
    flash("Task deleted!")
    return redirect(url_for('tasks'))

@app.route('/toggle-task/<int:task_id>')
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    task.is_complete = not task.is_complete
    db.session.commit()
    flash('Task status updated!')
    return redirect(url_for('tasks'))

@app.route('/log_time/<int:task_id>', methods=['POST'])
@login_required
def log_time(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return {"error": "Unauthorized"}, 403

    seconds = int(request.json.get("seconds", 0))
    task.duration_seconds += seconds
    db.session.commit()
    return {"status": "ok", "new_total": task.duration_seconds}

@app.route('/analytics')
@login_required
def analytics():
    total = Task.query.filter_by(user_id=current_user.id).count()
    completed = Task.query.filter_by(user_id=current_user.id, is_complete=True).count()
    pending = Task.query.filter_by(user_id=current_user.id, is_complete=False).count()

    today = datetime.utcnow().date()
    last_7_days = [today - timedelta(days=i) for i in reversed(range(7))]
    labels = [day.strftime('%a') for day in last_7_days]
    completed_counts = []
    pending_counts = []

    for day in last_7_days:
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        completed_day = Task.query.filter(Task.user_id == current_user.id, Task.created_at >= day_start, Task.created_at <= day_end, Task.is_complete == True).count()
        pending_day = Task.query.filter(Task.user_id == current_user.id, Task.created_at >= day_start, Task.created_at <= day_end, Task.is_complete == False).count()
        completed_counts.append(completed_day)
        pending_counts.append(pending_day)

    return render_template('analytics.html',
                           total=total,
                           completed=completed,
                           pending=pending,
                           labels=labels,
                           completed_counts=completed_counts,
                           pending_counts=pending_counts)


# ---------------- App Launch ----------------
# Create all tables (like 'user') if they don't exist
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        add_missing_column()
    app.run(debug=True, port=5050)
 