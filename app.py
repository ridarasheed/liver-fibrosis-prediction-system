import numpy as np
import joblib
from flask import Flask, render_template, request, redirect, url_for, session
from flask import flash
from db_connection import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecret"

model = joblib.load("lr_model.pkl")
scaler = joblib.load("scaler.pkl")

from werkzeug.security import generate_password_hash


@app.route('/test_db')
def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return "Database connection successful!"
    except Exception as e:
        return f"Database connection failed: {e}"

@app.route('/admin_home')
def admin_home():

    if 'type' not in session or session.get('type') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total users
    cursor.execute("SELECT COUNT(*) FROM login WHERE type='user'")
    total_users = cursor.fetchone()[0]

    # Total feedback
    cursor.execute("SELECT COUNT(*) FROM feedback")
    total_feedback = cursor.fetchone()[0]

    # Pending feedback
    cursor.execute("SELECT COUNT(*) FROM feedback WHERE response IS NULL")
    pending_feedback = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return render_template(
        'admin/admin_home.html',
        total_users=total_users,
        total_feedback=total_feedback,
        pending_feedback=pending_feedback
    )

@app.route('/adm_users')
def adm_users():

    if 'type' not in session or session.get('type') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            u.user_id,
            u.name,
            u.dob,
            u.mail AS email,
            l.login_id,
            l.status
        FROM users as u
        JOIN login as l ON u.login_id = l.login_id
        WHERE l.type = 'user'
    """)

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/adm_users.html', users=users)

@app.route('/admin/deactivate_user/<int:login_id>')
def deactivate_user(login_id):

    if 'type' not in session or session.get('type') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE login 
        SET status = 'inactive'
        WHERE login_id = %s
    """, (login_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('adm_users'))

@app.route('/admin/activate_user/<int:login_id>')
def activate_user(login_id):

    if 'type' not in session or session.get('type') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE login 
        SET status = 'active'
        WHERE login_id = %s
    """, (login_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('adm_users'))

@app.route('/adm_feed')
def adm_feed():

    if 'type' not in session or session.get('type') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT f.fid,
               f.feedback,
               f.response,
               f.fdate,
               l.username
        FROM feedback f
        JOIN login l ON f.login_id = l.login_id
        ORDER BY f.fdate DESC
    """)

    feedbacks = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin/adm_feed.html', feedbacks=feedbacks)

#--------------FEEDBACK REPLY------------------------------
@app.route('/reply_feedback', methods=['POST'])
def reply_feedback():

    if 'type' not in session or session.get('type') != 'admin':
        return redirect(url_for('login'))

    fid = request.form.get('fid')
    response = request.form.get('response')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE feedback
        SET response = %s
        WHERE fid = %s
    """, (response, fid))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('adm_feed'))

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM login WHERE username=%s"
        cursor.execute(query, (username,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user['pswrd'], password):

            if user['status'] == 'inactive':
                flash("Your account has been deactivated. Contact admin.", "warning")
                return redirect(url_for('login'))
            
            session['username'] = user['username']
            session['login_id'] = user['login_id']
            session['type'] = user['type']

            if user['type'] == 'admin':
                return redirect(url_for('admin_home'))
            else:
                return redirect(url_for('home'))
        else:
            flash("Invalid username or password", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

# ---------------- HOME PAGE ----------------
@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))

    return render_template('users/home.html')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        name = request.form.get('name')
        #gender = request.form.get('gender')
        dob = request.form.get('dob')
        username = request.form.get('username')  # email
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash("Passwords do not match!","error")
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("SELECT * FROM login WHERE username=%s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            flash("User already exists!","warning")
            return redirect(url_for('register'))

        # 1️⃣ Insert into login table
        cursor.execute(
            "INSERT INTO login (username, pswrd, type) VALUES (%s, %s, %s)",
            (username, hashed_password, 'user')
        )

        # Get generated login_id
        login_id = cursor.lastrowid

        # 2️⃣ Insert into users table
        cursor.execute(
            "INSERT INTO users (login_id, name, dob, mail) VALUES (%s, %s, %s, %s)",
            (login_id, name, dob, username)
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Registered successfully !","success")
        return redirect(url_for('login'))

    return render_template('register.html')

# ---------------- PREDICTION PAGE ----------------
@app.route('/prediction')
def prediction():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session.get('username')
    return render_template('users/prediction.html', name=username)


# ---------------- PREDICT LOGIC ----------------
@app.route('/predict', methods=['POST'])
def predict():
    if 'login_id' not in session:
        return redirect(url_for('login'))

    login_id = session.get('login_id')
    # Collect form data (make sure names match HTML form!)
    features = [
        int(request.form.get('Age')),
        int(request.form.get('Gender')),
        float(request.form.get('Total_Bilirubin')),
        float(request.form.get('Direct_Bilirubin')),
        float(request.form.get('Alkaline_Phosphotase')),
        float(request.form.get('Alamine_Aminotransferase')),
        float(request.form.get('Aspartate_Aminotransferase')),
        float(request.form.get('Total_Protiens')),
        float(request.form.get('Albumin')),
        float(request.form.get('Albumin_and_Globulin_Ratio'))
    ]

    features_array = np.array([features])

    # Scale input
    features_scaled = scaler.transform(features_array)

    # Predict
    probability = model.predict_proba(features_scaled)[0][1]
    percent = round(probability * 100, 2)

    if percent <= 30:
        risk_level = "Low Risk"
    elif 30 < percent <= 60:
        risk_level = "Moderate Risk"
    else:
        risk_level = "High Risk"

    result = f"{risk_level} ({percent}% probability)"

    conn = get_db_connection()
    cursor = conn.cursor()

    login_id = session.get('login_id')

    cursor.execute("""
    INSERT INTO details (
        login_id,
        age,
        gender,
        total_billirubin,
        direct_billirubin,
        alp,
        alt,
        ast,
        total_proteins,
        albumin,
        albumin_globulin,
        result,
        sub_date
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        login_id,
        features[0],
        features[1],
        features[2],
        features[3],
        features[4],
        features[5],
        features[6],
        features[7],
        features[8],
        features[9],
        result
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return render_template('users/result.html', result=result)

@app.route('/result')
def result():
    return render_template('users/result.html')


# ---------------- HISTORY ----------------
@app.route('/history')
def history():
    if 'login_id' not in session:
        return redirect(url_for('login'))

    login_id = session.get('login_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT age,
            gender,
            total_billirubin,
            direct_billirubin,
            total_proteins,
            alt,
            ast,
            albumin,
            albumin_globulin,
            result
        FROM details
        WHERE login_id = %s
        ORDER BY sub_date DESC
    """, (login_id,))

    history = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('users/history.html', history=history)


# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot', methods=['GET', 'POST'])
def forgot():

    if request.method == 'POST':

        username = request.form.get('username')
        dob = request.form.get('dob')
        new_password = request.form.get('new_password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if user exists with username and DOB
        cursor.execute(
            "SELECT login.* FROM login JOIN users ON login.login_id = users.login_id WHERE login.username=%s AND users.dob=%s",
            (username, dob)
        )

        user = cursor.fetchone()

        if user:

            # Hash new password
            hashed_password = generate_password_hash(new_password)

            cursor.execute(
                "UPDATE login SET pswrd=%s WHERE username=%s",
                (hashed_password, username)
            )

            conn.commit()

            flash("Password reset successful. Please login.", "success")

            cursor.close()
            conn.close()

            return redirect(url_for('login'))

        else:
            flash("Invalid username or date of birth", "error")

        cursor.close()
        conn.close()

    return render_template('users/forgot.html')

# ---------------- CHANGE PASSWORD ----------------
@app.route('/chng_pswrd', methods=['GET', 'POST'])
def chng_pswrd():

    if 'username' not in session:
        return redirect(url_for('login'))

    username = session.get('username')

    if request.method == 'POST':

        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT pswrd FROM login WHERE username = %s", (username,))
        record = cursor.fetchone()

        if record is None:
            flash("User not found!", "error")
            return redirect(url_for('chng_pswrd'))

        if record is None:
            cursor.close()
            conn.close()
            return "User not found!"

        if not check_password_hash(record['pswrd'], current_password):
            flash("Current password is incorrect!", "error")
            cursor.close()
            conn.close()
            return redirect(url_for('chng_pswrd'))

        #  check new & confirm
        if new_password != confirm_password:
            flash("New passwords do not match!", "warning")
            cursor.close()
            conn.close()
            return redirect(url_for('chng_pswrd'))

        # Hash & update
        hashed_password = generate_password_hash(new_password)

        cursor.execute(
            "UPDATE login SET pswrd = %s WHERE username = %s",
            (hashed_password, username)
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Password updated successfully!", "success")
        return redirect(url_for('login'))

    return render_template('/chng_pswrd.html')
#---------------USERS FEEDBACK-----------------
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():

    if 'login_id' not in session:
        return redirect(url_for('login'))

    login_id = session.get('login_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':

        message = request.form.get('feedback')

        cursor.execute("""
            INSERT INTO feedback (login_id, feedback)
            VALUES (%s, %s)
        """, (login_id, message))

        conn.commit()

    # Fetch user's feedback + responses
    cursor.execute("""
        SELECT feedback, response, fdate
        FROM feedback
        WHERE login_id = %s
        ORDER BY fdate DESC limit 2
    """, (login_id,))

    user_feedbacks = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'users/feedback.html',
        user_feedbacks=user_feedbacks
    )

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True)
    
