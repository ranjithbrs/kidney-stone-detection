"""
Clinical Decision Support / Legacy Portal Server
Security Remediated Implementation:
- Parameterized SQL queries (mitigates SQL injection)
- Cryptographic password hashing & verification via werkzeug.security
- Environment-variable configuration for secrets, database, and SMTP
- Dynamic secure token generation for Flask SECRET_KEY
- Removal of hardcoded plaintext credentials and email passwords
- Safe session-based access control and database connection pooling/cleanup
"""

import os
import sys
import secrets
import logging
from flask import Flask, render_template, flash, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

# Initialize Flask Application
app = Flask(__name__)

# Configure Flask SECRET_KEY securely:
# Priority 1: Read from environment variable FLASK_SECRET_KEY
# Priority 2: Generate a cryptographically secure 32-byte hex token per process instance
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_db_connection():
    """
    Establishes a MySQL database connection using configuration from environment variables.
    Never hardcodes database credentials in source code.
    """
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = int(os.environ.get('DB_PORT', '3306'))
    db_user = os.environ.get('DB_USER', 'root')
    db_password = os.environ.get('DB_PASSWORD', '')
    db_name = os.environ.get('DB_NAME', '1kidneystoneyolodb')

    return mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name
    )


@app.route("/")
def homepage():
    """Public home landing page."""
    return render_template('index.html')


# ==============================================================================
# Admin Portal Routes (Secured)
# ==============================================================================

@app.route("/AdminLogin")
def AdminLogin():
    """Renders the Administrator login interface."""
    return render_template('AdminLogin.html')


@app.route("/adminlogin", methods=['GET', 'POST'])
def adminlogin():
    """
    Secured administrator authentication:
    - Removes hardcoded plaintext 'admin' / 'admin'
    - Validates credentials against environment-configured username and secure hash
    - Uses parameterized queries for database audits
    """
    if request.method == 'POST':
        uname = request.form.get('uname', '').strip()
        pas = request.form.get('pas', '')

        # Environment-based administrator credentials
        admin_expected_user = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_pass_hash = os.environ.get('ADMIN_PASSWORD_HASH', '')

        # Verify credentials
        is_authenticated = False
        if uname == admin_expected_user:
            if admin_pass_hash:
                is_authenticated = check_password_hash(admin_pass_hash, pas)
            else:
                # If no hash is provisioned in environment, warn and reject login
                logging.warning("ADMIN_PASSWORD_HASH not configured in environment. Default admin login blocked for security.")
                flash("Administrator access disabled: password hash not configured in environment.")
                return render_template('AdminLogin.html')

        if is_authenticated:
            session['admin'] = True
            conn = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                # Parameterized query selecting safe columns (never expose password hashes in UI)
                cur.execute("SELECT uid, name, gender, age, email, mobile, address, UserName FROM regtb")
                data = cur.fetchall()
                flash("You are Logged In as Administrator.")
                return render_template('AdminHome.html', data=data)
            except mysql.connector.Error as err:
                logging.error(f"Database error during admin login: {err}")
                flash(f"Database connection error: {err.msg}")
                return render_template('AdminLogin.html')
            finally:
                if conn and conn.is_connected():
                    conn.close()
        else:
            flash("Username or Password is wrong")
            return render_template('AdminLogin.html')

    return render_template('AdminLogin.html')


@app.route("/AdminHome")
def AdminHome():
    """
    Administrator dashboard with mandatory session verification.
    """
    if not session.get('admin'):
        flash("Please log in as Administrator to access this area.")
        return redirect(url_for('AdminLogin'))

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT uid, name, gender, age, email, mobile, address, UserName FROM regtb")
        data = cur.fetchall()
        return render_template('AdminHome.html', data=data)
    except mysql.connector.Error as err:
        logging.error(f"Database error in AdminHome: {err}")
        flash(f"Database connection error: {err.msg}")
        return render_template('AdminHome.html', data=[])
    finally:
        if conn and conn.is_connected():
            conn.close()


# ==============================================================================
# User Management & Registration Routes (Secured)
# ==============================================================================

@app.route("/NewUser")
def NewUser():
    """Renders user registration form."""
    return render_template('NewUser.html')


@app.route("/newuser", methods=['GET', 'POST'])
def newuser():
    """
    Secured user registration:
    - Input sanitization and validation
    - Cryptographic password hashing via werkzeug.security (never stores plaintext)
    - Fully parameterized SQL INSERT query (prevents SQL injection)
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', '').strip()
        age = request.form.get('age', '').strip()
        email = request.form.get('email', '').strip()
        mobile = request.form.get('mobile', '').strip()
        address = request.form.get('address', '').strip()
        uname = request.form.get('uname', '').strip()
        pas = request.form.get('pas', '')

        # Basic input validation safeguards
        if not uname or not pas or not email:
            flash("Username, password, and email are required fields.")
            return render_template('NewUser.html')

        # Hash password securely using PBKDF2 / Argon2 / Scrypt
        hashed_password = generate_password_hash(pas)

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if username already exists
            cursor.execute("SELECT uid FROM regtb WHERE UserName = %s", (uname,))
            existing = cursor.fetchone()
            if existing:
                flash("Username is already taken. Please choose another.")
                return render_template('NewUser.html')

            # Fully parameterized INSERT statement
            insert_query = """
                INSERT INTO regtb (name, gender, age, email, mobile, address, UserName, Password)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (name, gender, age, email, mobile, address, uname, hashed_password))
            conn.commit()
            flash('New User Registered successfully')

            # Fetch sanitized user list
            cursor.execute("SELECT uid, name, gender, age, email, mobile, address, UserName FROM regtb")
            data = cursor.fetchall()
            return render_template('UserLogin.html', data=data)

        except mysql.connector.Error as err:
            logging.error(f"Database error during user registration: {err}")
            flash(f"Database error during registration: {err.msg}")
            return render_template('NewUser.html')
        finally:
            if conn and conn.is_connected():
                conn.close()

    return render_template('NewUser.html')


@app.route("/UserLogin")
def UserLogin():
    """Renders user login interface."""
    return render_template('UserLogin.html')


@app.route("/userlogin", methods=['GET', 'POST'])
def userlogin():
    """
    Secured user authentication:
    - Fully parameterized SELECT query (prevents SQL injection)
    - Cryptographic password hash verification
    - Transparent backward-compatible migration for legacy plaintext passwords
    """
    if request.method == 'POST':
        uname = request.form.get('uname', '').strip()
        pas = request.form.get('pas', '')

        if not uname or not pas:
            flash("Please enter both username and password.")
            return render_template('UserLogin.html')

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Parameterized query fetching record by username
            cursor.execute(
                "SELECT uid, name, gender, age, email, mobile, address, UserName, Password FROM regtb WHERE UserName = %s",
                (uname,)
            )
            data = cursor.fetchone()

            if data is None:
                flash("UserName or Password is wrong...!")
                return render_template('UserLogin.html')

            stored_password = data[8]
            is_valid = False

            # Verify with werkzeug.security
            try:
                is_valid = check_password_hash(stored_password, pas)
            except Exception:
                is_valid = False

            # Transparent backward-compatibility check for existing legacy plaintext records
            if not is_valid and stored_password == pas:
                is_valid = True
                # Automatically upgrade legacy password to secure cryptographic hash
                try:
                    upgraded_hash = generate_password_hash(pas)
                    cursor.execute("UPDATE regtb SET Password = %s WHERE UserName = %s", (upgraded_hash, uname))
                    conn.commit()
                    logging.info(f"Successfully upgraded legacy plaintext password to secure hash for user: {uname}")
                except mysql.connector.Error as update_err:
                    logging.warning(f"Failed to auto-upgrade legacy password: {update_err}")

            if not is_valid:
                flash("UserName or Password is wrong...!")
                return render_template('UserLogin.html')

            # Set user session variables
            session['uname'] = uname
            session['user_id'] = data[0]
            session['email'] = data[4]
            session['mob'] = data[5]
            session['add'] = data[6]

            # Fetch sanitized user list
            cursor.execute("SELECT uid, name, gender, age, email, mobile, address, UserName FROM regtb WHERE UserName = %s", (uname,))
            user_data = cursor.fetchall()
            flash("You are Logged In...!")
            return render_template('UserHome.html', data=user_data)

        except mysql.connector.Error as err:
            logging.error(f"Database error during user login: {err}")
            flash(f"Database connection error: {err.msg}")
            return render_template('UserLogin.html')
        finally:
            if conn and conn.is_connected():
                conn.close()

    return render_template('UserLogin.html')


@app.route("/UserHome")
def UserHome():
    """
    User home portal with session authentication safeguard.
    """
    if 'uname' not in session:
        flash("Session expired or invalid. Please log in.")
        return redirect(url_for('UserLogin'))

    uname = session['uname']
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Parameterized query
        cur.execute("SELECT uid, name, gender, age, email, mobile, address, UserName FROM regtb WHERE UserName = %s", (uname,))
        data = cur.fetchall()
        return render_template('UserHome.html', data=data)
    except mysql.connector.Error as err:
        logging.error(f"Database error in UserHome: {err}")
        flash(f"Database error: {err.msg}")
        return render_template('UserHome.html', data=[])
    finally:
        if conn and conn.is_connected():
            conn.close()


@app.route("/logout")
def logout():
    """Clears user session cleanly."""
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('homepage'))


# ==============================================================================
# SMTP Alerting (Secured & Environment-Configured)
# ==============================================================================

def sendmail(message, attachment_path="alert.jpg"):
    """
    Secured email dispatch:
    - Never hardcodes SMTP credentials or email passwords
    - Reads credentials from environment variables (SMTP_USERNAME, SMTP_PASSWORD)
    - Gracefully skips email dispatch if credentials are not configured in environment
    """
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USERNAME', '').strip()
    smtp_pass = os.environ.get('SMTP_PASSWORD', '').strip()
    fromaddr = os.environ.get('MAIL_SENDER', smtp_user).strip()

    if not smtp_user or not smtp_pass or not fromaddr:
        logging.warning("SMTP notification skipped: SMTP_USERNAME or SMTP_PASSWORD not configured in environment.")
        return False

    toaddr = session.get('email')
    if not toaddr:
        logging.warning("SMTP notification skipped: recipient email address not found in active session.")
        return False

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = "Clinical Alert Notification"
    msg.attach(MIMEText(message, 'plain'))

    # Attach file if present
    if attachment_path and os.path.exists(attachment_path):
        try:
            with open(attachment_path, "rb") as attachment:
                p = MIMEBase('application', 'octet-stream')
                p.set_payload(attachment.read())
                encoders.encode_base64(p)
                p.add_header('Content-Disposition', f"attachment; filename={os.path.basename(attachment_path)}")
                msg.attach(p)
        except Exception as e:
            logging.error(f"Failed to attach file {attachment_path}: {e}")

    server = None
    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(fromaddr, toaddr, msg.as_string())
        logging.info(f"Alert email successfully dispatched to {toaddr}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email alert: {e}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


# ==============================================================================
# Application Entry Point
# ==============================================================================

if __name__ == '__main__':
    # Configurable binding parameters from environment
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    app.run(
        host=host,
        port=port,
        debug=debug
    )
