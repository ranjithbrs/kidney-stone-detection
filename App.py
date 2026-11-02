"""
Clinical Decision Support / Legacy Portal Server
Security Hardened Implementation (Phase 2):
- Parameterized SQL queries (mitigates SQL injection)
- Cryptographic password hashing & verification via werkzeug.security
- Environment-variable configuration for secrets, database, and SMTP
- Persistent production FLASK_SECRET_KEY enforcement & multi-worker drift mitigation
- Built-in timing-resistant CSRF protection with automatic token injection
- Session fixation immunity (session ID regeneration & clearance on auth)
- Hardened session cookies (HttpOnly, Secure in prod, SameSite=Lax, strict timeout)
- Information disclosure mitigation (sanitized database error flashes)
- Centralized route authorization decorators (@login_required, @admin_required)
- PII-redacted operational logging (masked patient email addresses)
"""

import os
import sys
import secrets
import hmac
import logging
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, flash, request, session, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

# Securely load local .env if present (preserves existing environment variables)
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass

# Initialize Flask Application
app = Flask(__name__)

# Environment and Secret Key Management:
# In production mode (FLASK_ENV=production), require persistent FLASK_SECRET_KEY
# to prevent multi-worker WSGI session invalidation drift.
FLASK_ENV = os.environ.get('FLASK_ENV', 'development').lower()
flask_secret = os.environ.get('FLASK_SECRET_KEY')
if FLASK_ENV == 'production' and not flask_secret:
    raise RuntimeError("CRITICAL SECURITY ERROR: FLASK_SECRET_KEY environment variable must be set in production mode.")

app.config['SECRET_KEY'] = flask_secret or secrets.token_hex(32)

# Session Cookie Hardening Configuration
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't') or FLASK_ENV == 'production',
    SESSION_COOKIE_SAMESITE=os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax'),
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', '30')))
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ==============================================================================
# Native Anti-CSRF Middleware
# ==============================================================================

def generate_csrf_token():
    """Generates and persists a cryptographically secure CSRF token in the session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


@app.context_processor
def inject_csrf_token():
    """Injects csrf_token helper callable into all Jinja2 template contexts."""
    return dict(csrf_token=generate_csrf_token)


@app.before_request
def verify_csrf_token():
    """
    Enforces anti-CSRF token verification for all state-changing HTTP requests.
    Exempts safe HTTP methods (GET, HEAD, OPTIONS) and explicit testing bypasses.
    """
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        if app.config.get('WTF_CSRF_ENABLED') is False or app.config.get('DISABLE_CSRF_FOR_TESTING') is True:
            return
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        expected = session.get('_csrf_token')
        if not token or not expected or not hmac.compare_digest(token, expected):
            logging.warning(f"CSRF validation failed for IP {request.remote_addr} on path {request.path}")
            abort(400, description="CSRF token missing or invalid.")


# ==============================================================================
# Centralized Access Control Decorators
# ==============================================================================

def login_required(f):
    """Enforces active user session authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'uname' not in session:
            flash("Session expired or invalid. Please log in.")
            return redirect(url_for('UserLogin'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Enforces active administrator session authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin'):
            flash("Please log in as Administrator to access this area.")
            return redirect(url_for('AdminLogin'))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# Database Helper
# ==============================================================================

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
    - Protects against session fixation by clearing session and rotating CSRF token
    - Sanitizes error messages to prevent sensitive schema disclosure
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
            # Session fixation protection: clear pre-existing anonymous session and rotate CSRF token
            session.clear()
            session['_csrf_token'] = secrets.token_hex(32)
            session.permanent = True  # Enable Flask permanent session (30-min lifetime)
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
                logging.error(f"Database error during admin login: {err}", exc_info=True)
                flash("A database error occurred. Please contact the clinical system administrator.")
                return render_template('AdminLogin.html')
            finally:
                if conn and conn.is_connected():
                    conn.close()
        else:
            flash("Username or Password is wrong")
            return render_template('AdminLogin.html')

    return render_template('AdminLogin.html')


@app.route("/AdminHome")
@admin_required
def AdminHome():
    """
    Administrator dashboard with mandatory session verification via decorator.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT uid, name, gender, age, email, mobile, address, UserName FROM regtb")
        data = cur.fetchall()
        return render_template('AdminHome.html', data=data)
    except mysql.connector.Error as err:
        logging.error(f"Database error in AdminHome: {err}", exc_info=True)
        flash("A database error occurred. Please contact the clinical system administrator.")
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
    - Sanitized database error handling
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
            logging.error(f"Database error during user registration: {err}", exc_info=True)
            flash("A database error occurred during registration. Please contact the clinical system administrator.")
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
    - Transparent backward-compatible migration for legacy plaintext passwords with deprecation logging
    - Session fixation protection via session clearance & CSRF token regeneration
    - Sanitized database error handling
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

            # Strict cryptographic verification (legacy plaintext fallback fully deprecated and removed)
            try:
                is_valid = check_password_hash(stored_password, pas)
            except Exception:
                is_valid = False

            if not is_valid:
                flash("UserName or Password is wrong...!")
                return render_template('UserLogin.html')

            # Session fixation protection: clear pre-existing anonymous session and rotate CSRF token
            session.clear()
            session['_csrf_token'] = secrets.token_hex(32)
            session.permanent = True  # Enable Flask permanent session (30-min lifetime)

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
            logging.error(f"Database error during user login: {err}", exc_info=True)
            flash("A database error occurred. Please contact the clinical system administrator.")
            return render_template('UserLogin.html')
        finally:
            if conn and conn.is_connected():
                conn.close()

    return render_template('UserLogin.html')


@app.route("/UserHome")
@login_required
def UserHome():
    """
    User home portal with session authentication safeguard via decorator.
    """
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
        logging.error(f"Database error in UserHome: {err}", exc_info=True)
        flash("A database error occurred. Please contact the clinical system administrator.")
        return render_template('UserHome.html', data=[])
    finally:
        if conn and conn.is_connected():
            conn.close()


@app.route("/logout", methods=['GET', 'POST'])
def logout():
    """
    Clears user session cleanly.
    State-changing POST requests enforce strict CSRF verification.
    """
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('homepage'))


# ==============================================================================
# SMTP Alerting (Secured & Environment-Configured)
# ==============================================================================

def mask_email(email_str):
    """Masks patient email address for privacy-compliant logging (HIPAA/GDPR)."""
    if not email_str or '@' not in email_str:
        return "***"
    parts = email_str.split('@')
    user_part = parts[0]
    domain_part = parts[1]
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[:2] + "***" + user_part[-1]
    return f"{masked_user}@{domain_part}"


def sendmail(message, attachment_path="alert.jpg"):
    """
    Secured email dispatch:
    - Never hardcodes SMTP credentials or email passwords
    - Reads credentials from environment variables (SMTP_USERNAME, SMTP_PASSWORD)
    - Gracefully skips email dispatch if credentials are not configured in environment
    - Redacts patient PII from operational log entries
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
        logging.info(f"Alert email successfully dispatched to {mask_email(toaddr)}")
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
