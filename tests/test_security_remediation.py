"""
Automated Security Regression & Remediation Test Suite (Phase 1, 2, & 2D Hardened)
Validates:
1. Repository-wide secret and credential scan (root, src/, tests/, docs/, database/)
2. Elimination of hardcoded secrets and default credentials in App.py
3. SQL parameterization integrity (verification of SQL injection defense)
4. Cryptographic password hashing and verification via werkzeug.security
5. Dynamic secure token generation for Flask SECRET_KEY
6. Session authentication safeguards on protected administrative & user routes
7. Gitignore protection for environment and secret files
8. Template .env.example verification
9. Runtime Anti-CSRF token enforcement on all state-changing POST endpoints (including /logout)
10. Session fixation immunity and CSRF token rotation upon authentication
11. Hardened session cookie configuration attributes
12. Production FLASK_SECRET_KEY enforcement safeguard via isolated subprocess execution
13. Database error masking & zero schema/table disclosure to client
14. Behavioral SQL injection payload rejection via parameterized query execution
15. Patient PII email masking for operational log compliance (HIPAA/GDPR)
16. Centralized route authorization decorators and role separation (user cannot access admin)
17. Offline password migration utility with pre-migration JSON backups and rollback
18. Runtime session cookie inspection (Expires, HttpOnly, SameSite=Lax, Secure in prod)
19. Strict cryptographic verification: elimination of legacy plaintext login fallback
20. Cross-session CSRF token rejection and post-logout token invalidation
"""

import os
import re
import sys
import json
import shutil
import tempfile
import subprocess
import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta

# Add project root and src to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from App import app, mask_email, login_required, admin_required
from scripts.migrate_passwords import (
    is_hashed,
    batch_migrate_passwords,
    create_table_backup,
    verify_migration_status
)


class TestSecurityRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    # ==========================================================================
    # Phase 1 Remediation Tests
    # ==========================================================================

    def test_SEC_01_repo_wide_secret_and_credential_scan(self):
        """SEC-01: Comprehensive repository-wide scan verifies zero active hardcoded secrets."""
        secret_patterns = [
            (re.compile(r's\.login\(.+,\s*["\'][a-z]{4}\s+[a-z]{4}\s+[a-z]{4}\s+[a-z]{4}["\']\)', re.IGNORECASE), "Exposed SMTP app password in s.login"),
            (re.compile(r'SECRET_KEY\s*=\s*["\'][a-zA-Z0-9_-]{16,}["\']'), "Hardcoded static SECRET_KEY string"),
            (re.compile(r'uname\s*==\s*["\']admin["\']\s+and\s+pas\s*==\s*["\']admin["\']'), "Hardcoded default admin credentials"),
            (re.compile(r'-----BEGIN\s+(RSA|EC|DSA|OPENSSH)?\s*PRIVATE\s+KEY-----'), "Private encryption key committed"),
            (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS Access Key ID committed")
        ]

        excluded_dirs = {'.venv', '.git', '__pycache__', '.idea', '.vscode', 'train', 'valid', 'test', 'images', 'labels'}
        target_exts = {'.py', '.sql', '.yaml', '.yml', '.json', '.toml', '.md', '.txt', '.sh', '.bat'}

        scanned_files = 0
        violations = []

        for root, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('.')]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in target_exts and not file.startswith('.env'):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, ROOT_DIR)

                if "TESTING_GAP_AUDIT_REPORT.md" in rel_path or "test_results.json" in rel_path or "security_hardening" in rel_path:
                    continue

                scanned_files += 1
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        for pattern, desc in secret_patterns:
                            matches = pattern.findall(content)
                            if matches:
                                violations.append(f"{rel_path}: {desc}")
                except Exception:
                    pass

        self.assertGreater(scanned_files, 15, "Scanner must inspect project files")
        self.assertEqual(len(violations), 0, f"Exposed secrets detected:\n" + "\n".join(violations))

    def test_SEC_02_app_py_source_code_remediation(self):
        """SEC-02: App.py contains zero static secrets and uses environment configuration."""
        app_path = os.path.join(ROOT_DIR, "App.py")
        with open(app_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertNotIn("app.config['SECRET_KEY'] = '7d441f27", code, "Hardcoded SECRET_KEY remains in App.py")
        self.assertIn("os.environ.get('FLASK_SECRET_KEY')", code, "App.py does not read FLASK_SECRET_KEY from environment")
        self.assertNotIn("request.form['uname'] == 'admin' and request.form['pas'] == 'admin'", code)
        self.assertIn("ADMIN_USERNAME", code)
        self.assertNotIn("tdyr kebi", code, "Compromised Gmail app password still in App.py")
        self.assertIn("os.environ.get('SMTP_PASSWORD'", code)
        self.assertIn("from dotenv import load_dotenv", code, "App.py must import load_dotenv directly from dotenv")
        self.assertNotIn("except ImportError:", code, "App.py must not silently ignore ImportError for dotenv")
        self.assertIn("override=False", code, "App.py must specify override=False when loading .env")

    def test_SEC_03_sql_injection_defense_parameterization(self):
        """SEC-03: App.py uses parameterized queries, eliminating string interpolation SQL injection."""
        app_path = os.path.join(ROOT_DIR, "App.py")
        with open(app_path, "r", encoding="utf-8") as f:
            code = f.read()

        dangerous_concat_1 = "where UserName='"
        dangerous_concat_2 = "VALUES ('"
        self.assertNotIn(dangerous_concat_1, code, "Vulnerable SQL concatenation detected in App.py")
        self.assertNotIn(dangerous_concat_2, code, "Vulnerable INSERT concatenation detected in App.py")

        self.assertIn("WHERE UserName = %s", code, "Parameterized query missing for UserName lookup")
        self.assertIn("VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", code, "Parameterized query missing for user registration")

    def test_SEC_04_cryptographic_password_hashing(self):
        """SEC-04: Password hashing uses secure cryptographic salt and non-invertible derivation."""
        password = "ClinicalSecurePassword2026!"
        h1 = generate_password_hash(password)
        h2 = generate_password_hash(password)

        self.assertNotEqual(h1, h2, "Password hash must be salted")
        self.assertTrue(check_password_hash(h1, password), "Valid password must verify successfully")
        self.assertFalse(check_password_hash(h1, "WrongPassword"), "Incorrect password must be rejected")
        self.assertNotIn(password, h1, "Plaintext password leaked in hash representation")

    def test_SEC_05_dynamic_flask_secret_key_generation(self):
        """SEC-05: Flask SECRET_KEY generates secure random 32-byte token when env var is absent."""
        self.assertIsNotNone(self.app.config['SECRET_KEY'], "Flask SECRET_KEY must be populated")
        self.assertGreaterEqual(len(self.app.config['SECRET_KEY']), 32, "SECRET_KEY must have adequate entropy")

    def test_SEC_06_unauthenticated_session_protection(self):
        """SEC-06: Protected administrative and user dashboards redirect unauthenticated sessions."""
        res_admin = self.client.get('/AdminHome', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302, "Unauthenticated access to /AdminHome must redirect")
        self.assertIn('/AdminLogin', res_admin.headers.get('Location', ''))

        res_user = self.client.get('/UserHome', follow_redirects=False)
        self.assertEqual(res_user.status_code, 302, "Unauthenticated access to /UserHome must redirect")
        self.assertIn('/UserLogin', res_user.headers.get('Location', ''))

    def test_SEC_07_env_and_secret_files_ignored_by_git(self):
        """SEC-07: .gitignore strictly ignores .env, .env.*, and cryptographic key files."""
        gitignore_path = os.path.join(ROOT_DIR, ".gitignore")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_patterns = [".env", ".env.*", "!.env.example", "*.pem", "*.key"]
        for pat in required_patterns:
            self.assertIn(pat, content, f".gitignore missing pattern: {pat}")

    def test_SEC_08_env_example_template_exists_without_secrets(self):
        """SEC-08: .env.example exists as template and contains zero real secrets."""
        example_path = os.path.join(ROOT_DIR, ".env.example")
        self.assertTrue(os.path.exists(example_path), ".env.example template must exist")
        with open(example_path, "r", encoding="utf-8") as f:
            example_content = f.read()

        self.assertNotIn("tdyr kebi", example_content)
        self.assertNotIn("7d441f27d441f27567d441f2b6176a", example_content)
        self.assertIn("FLASK_SECRET_KEY=", example_content)
        self.assertIn("DB_PASSWORD=", example_content)
        self.assertIn("SMTP_USERNAME=example@gmail.com", example_content)
        self.assertIn("MAIL_SENDER=example@gmail.com", example_content)
        self.assertIn("SMTP_PASSWORD=", example_content)
        for line in example_content.splitlines():
            if line.startswith("SMTP_PASSWORD="):
                self.assertEqual(line.strip(), "SMTP_PASSWORD=", "SMTP_PASSWORD in .env.example must have no assigned value")

    # ==========================================================================
    # Phase 2 & 2D Security Hardening & Behavioral Regression Tests
    # ==========================================================================

    def test_SEC_09_csrf_protection_runtime_enforcement(self):
        """SEC-09: Native CSRF protection rejects state-changing requests missing valid token (HTTP 400)."""
        # POST without CSRF token must return 400
        res_no_csrf = self.client.post('/adminlogin', data={'uname': 'admin', 'pas': 'test'})
        self.assertEqual(res_no_csrf.status_code, 400)

        res_user_no_csrf = self.client.post('/userlogin', data={'uname': 'user', 'pas': 'test'})
        self.assertEqual(res_user_no_csrf.status_code, 400)

        res_newuser_no_csrf = self.client.post('/newuser', data={'uname': 'user', 'pas': 'test', 'email': 'a@b.com'})
        self.assertEqual(res_newuser_no_csrf.status_code, 400)

        res_logout_no_csrf = self.client.post('/logout')
        self.assertEqual(res_logout_no_csrf.status_code, 400, "POST /logout without CSRF token must return 400")

        # GET request establishes token
        self.client.get('/AdminLogin')
        with self.client.session_transaction() as sess:
            valid_csrf = sess.get('_csrf_token')

        self.assertIsNotNone(valid_csrf)

        # POST with valid CSRF token passes verification
        res_with_csrf = self.client.post('/adminlogin', data={
            'uname': 'nonexistent_admin',
            'pas': 'wrong_password',
            'csrf_token': valid_csrf
        })
        self.assertEqual(res_with_csrf.status_code, 200)

    def test_SEC_10_session_fixation_and_csrf_rotation(self):
        """SEC-10: Authentication clears pre-auth session state and rotates CSRF token to prevent fixation."""
        self.client.get('/AdminLogin')
        with self.client.session_transaction() as sess:
            sess['pre_auth_trap'] = 'active_trap'
            initial_csrf = sess.get('_csrf_token')

        test_admin_user = 'audit_admin'
        test_admin_pass = 'SecTest2026!Pass'
        admin_hash = generate_password_hash(test_admin_pass)

        with patch.dict(os.environ, {'ADMIN_USERNAME': test_admin_user, 'ADMIN_PASSWORD_HASH': admin_hash}):
            with patch('App.get_db_connection') as mock_db:
                mock_conn = MagicMock()
                mock_cur = MagicMock()
                mock_cur.fetchall.return_value = []
                mock_conn.cursor.return_value = mock_cur
                mock_conn.is_connected.return_value = True
                mock_db.return_value = mock_conn

                res_login = self.client.post('/adminlogin', data={
                    'uname': test_admin_user,
                    'pas': test_admin_pass,
                    'csrf_token': initial_csrf
                })
                self.assertEqual(res_login.status_code, 200)

                with self.client.session_transaction() as post_sess:
                    self.assertNotIn('pre_auth_trap', post_sess)
                    self.assertTrue(post_sess.get('admin'))
                    self.assertNotEqual(post_sess.get('_csrf_token'), initial_csrf)

    def test_SEC_11_session_cookie_security_configuration(self):
        """SEC-11: Session cookies configured with HttpOnly, SameSite=Lax, and restricted lifetime."""
        self.assertTrue(self.app.config.get('SESSION_COOKIE_HTTPONLY'))
        self.assertEqual(self.app.config.get('SESSION_COOKIE_SAMESITE'), 'Lax')
        self.assertEqual(self.app.config.get('PERMANENT_SESSION_LIFETIME'), timedelta(minutes=30))

    def test_SEC_12_production_secret_key_enforcement_subprocess(self):
        """SEC-12: Enforces that FLASK_SECRET_KEY is mandatory when running in production via isolated subprocess."""
        # Subprocess without key -> Failure
        env_fail = os.environ.copy()
        env_fail['FLASK_ENV'] = 'production'
        env_fail['FLASK_SECRET_KEY'] = ''

        proc_fail = subprocess.run(
            [sys.executable, "-c", "import App"],
            cwd=ROOT_DIR,
            env=env_fail,
            capture_output=True,
            text=True
        )
        self.assertNotEqual(proc_fail.returncode, 0, "Subprocess in production mode must fail without FLASK_SECRET_KEY")
        self.assertIn("CRITICAL SECURITY ERROR: FLASK_SECRET_KEY", proc_fail.stderr)

        # Subprocess with key -> Success
        env_pass = os.environ.copy()
        env_pass['FLASK_ENV'] = 'production'
        env_pass['FLASK_SECRET_KEY'] = 'c028246dfa98e5f3248641bc38d770851ec39b3425b0496152ba85e2b8655077'

        proc_pass = subprocess.run(
            [sys.executable, "-c", "import sys, App; sys.exit(0 if App.app.config['SECRET_KEY'] else 1)"],
            cwd=ROOT_DIR,
            env=env_pass,
            capture_output=True,
            text=True
        )
        self.assertEqual(proc_pass.returncode, 0, f"Subprocess in production mode must boot with persistent key. Stderr: {proc_pass.stderr}")

    def test_SEC_13_database_error_masking_runtime(self):
        """SEC-13: Database exceptions are sanitized and never expose table or schema metadata to client."""
        self.client.get('/AdminLogin')
        with self.client.session_transaction() as sess:
            csrf_token = sess.get('_csrf_token')

        test_admin_user = 'audit_admin_err'
        test_admin_pass = 'SecTest2026!Pass'
        admin_hash = generate_password_hash(test_admin_pass)

        with patch.dict(os.environ, {'ADMIN_USERNAME': test_admin_user, 'ADMIN_PASSWORD_HASH': admin_hash}):
            with patch('App.get_db_connection') as mock_db:
                mock_db.side_effect = mysql.connector.Error(
                    msg="Table '1kidneystoneyolodb.regtb' doesn't exist on host 10.0.0.15",
                    errno=1146
                )

                res = self.client.post('/adminlogin', data={
                    'uname': test_admin_user,
                    'pas': test_admin_pass,
                    'csrf_token': csrf_token
                })

                html = res.data.decode('utf-8')
                self.assertNotIn("1kidneystoneyolodb", html)
                self.assertNotIn("10.0.0.15", html)
                self.assertNotIn("doesn't exist", html)
                self.assertIn("A database error occurred", html)

    def test_SEC_14_behavioral_sql_injection_payload_rejection(self):
        """SEC-14: Submitting active SQL injection payloads is handled safely by parameterized queries."""
        malicious_payloads = [
            "' OR '1'='1' --",
            "admin' #",
            "' UNION SELECT 1, 'admin', 'male', '30', 'hacker@evil.com', '123', 'addr', 'admin', 'hash' --",
            "\"; DROP TABLE regtb; --"
        ]

        for payload in malicious_payloads:
            self.client.get('/UserLogin')
            with self.client.session_transaction() as sess:
                csrf = sess.get('_csrf_token')

            with patch('App.get_db_connection') as mock_db:
                mock_conn = MagicMock()
                mock_cur = MagicMock()
                mock_cur.fetchone.return_value = None
                mock_conn.cursor.return_value = mock_cur
                mock_conn.is_connected.return_value = True
                mock_db.return_value = mock_conn

                res = self.client.post('/userlogin', data={
                    'uname': payload,
                    'pas': 'random_password',
                    'csrf_token': csrf
                })

                mock_cur.execute.assert_called_with(
                    "SELECT uid, name, gender, age, email, mobile, address, UserName, Password FROM regtb WHERE UserName = %s",
                    (payload,)
                )
                self.assertEqual(res.status_code, 200)
                self.assertIn("UserName or Password is wrong", res.data.decode('utf-8'))

    def test_SEC_15_pii_sanitization_in_logs(self):
        """SEC-15: mask_email redacts patient email addresses for privacy compliance (HIPAA/GDPR)."""
        test_cases = [
            ("patient.doe@hospital.org", "pa***e@hospital.org"),
            ("john@clinic.com", "jo***n@clinic.com"),
            ("ab@c.com", "a***@c.com"),
            ("x@domain.org", "x***@domain.org"),
            ("", "***"),
            ("invalid_email", "***"),
            (None, "***")
        ]

        for input_email, expected_mask in test_cases:
            masked = mask_email(input_email)
            self.assertEqual(masked, expected_mask)
            if input_email and '@' in input_email and len(input_email.split('@')[0]) > 2:
                self.assertNotIn(input_email.split('@')[0], masked)

    def test_SEC_16_route_authorization_decorators_and_role_separation(self):
        """SEC-16: Route decorators block unauthorized access, and normal users cannot access admin."""
        # 1. Unauthenticated /AdminHome blocked
        with self.client.session_transaction() as sess:
            sess.clear()

        res_admin = self.client.get('/AdminHome', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn('/AdminLogin', res_admin.headers.get('Location', ''))

        # 2. Regular user session logged in -> Must still be blocked from /AdminHome
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['uname'] = 'regular_patient_user'
            sess['user_id'] = 42

        res_regular_user = self.client.get('/AdminHome', follow_redirects=False)
        self.assertEqual(res_regular_user.status_code, 302, "Regular user must be blocked from /AdminHome")
        self.assertIn('/AdminLogin', res_regular_user.headers.get('Location', ''))

        # 3. Authenticated Admin permitted
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['admin'] = True

        with patch('App.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cur
            mock_conn.is_connected.return_value = True
            mock_db.return_value = mock_conn

            res_admin_auth = self.client.get('/AdminHome')
            self.assertEqual(res_admin_auth.status_code, 200)

    def test_SEC_17_offline_password_migration_utility_with_backup_and_rollback(self):
        """SEC-17: Password migration utility creates JSON backup, detects plaintext, and supports rollback."""
        valid_pbkdf2 = generate_password_hash("test_password_123")
        self.assertTrue(is_hashed(valid_pbkdf2))
        self.assertFalse(is_hashed("plaintext_pass"))
        self.assertFalse(is_hashed("mark"))

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            (1, 'hashed_user', valid_pbkdf2),
            (2, 'plain_user1', 'mypassword1'),
            (3, 'plain_user2', 'mypassword2')
        ]
        mock_conn.cursor.return_value = mock_cur
        mock_conn.is_connected.return_value = True

        # Test dry run
        stats_dry = batch_migrate_passwords(dry_run=True, connection=mock_conn)
        self.assertEqual(stats_dry['total'], 3)
        self.assertEqual(stats_dry['already_hashed'], 1)
        self.assertEqual(stats_dry['upgraded'], 2)
        self.assertTrue(stats_dry['dry_run'])

        # Test live migration with backup
        temp_backup_dir = tempfile.mkdtemp()
        try:
            stats_live = batch_migrate_passwords(dry_run=False, connection=mock_conn, backup_dir=temp_backup_dir)
            self.assertEqual(stats_live['total'], 3)
            self.assertEqual(stats_live['upgraded'], 2)
            self.assertIsNotNone(stats_live['backup_path'])
            self.assertTrue(os.path.exists(stats_live['backup_path']))

            # Inspect backup JSON contents
            with open(stats_live['backup_path'], 'r', encoding='utf-8') as f:
                backup_json = json.load(f)
            self.assertEqual(len(backup_json), 3)
            self.assertEqual(backup_json[1]['UserName'], 'plain_user1')

            # Verify commit was executed
            mock_conn.commit.assert_called()
        finally:
            shutil.rmtree(temp_backup_dir, ignore_errors=True)

        # Test rollback on database failure
        mock_failing_conn = MagicMock()
        mock_failing_cur = MagicMock()
        mock_failing_cur.fetchall.return_value = [(1, 'user', 'plain')]
        mock_failing_cur.execute.side_effect = [None, mysql.connector.Error(msg="Disk full")]
        mock_failing_conn.cursor.return_value = mock_failing_cur

        stats_err = batch_migrate_passwords(dry_run=False, connection=mock_failing_conn, backup=False)
        self.assertEqual(stats_err['status'], 'error')
        mock_failing_conn.rollback.assert_called()

    def test_SEC_18_runtime_session_cookie_headers_and_expiration(self):
        """SEC-18: Verifies Set-Cookie header attributes in actual HTTP responses under dev and prod modes."""
        # 1. Dev configuration: HttpOnly, SameSite=Lax, permanent expiration
        self.client.get('/AdminLogin')
        with self.client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        test_user = "admin_cookie_test"
        test_pass = "CookieSecret2026!"
        test_hash = generate_password_hash(test_pass)

        with patch.dict(os.environ, {'ADMIN_USERNAME': test_user, 'ADMIN_PASSWORD_HASH': test_hash}):
            with patch('App.get_db_connection') as mock_db:
                mock_conn = MagicMock()
                mock_cur = MagicMock()
                mock_cur.fetchall.return_value = []
                mock_conn.cursor.return_value = mock_cur
                mock_conn.is_connected.return_value = True
                mock_db.return_value = mock_conn

                res_dev = self.client.post('/adminlogin', data={
                    'uname': test_user,
                    'pas': test_pass,
                    'csrf_token': csrf
                })

        cookies_dev = res_dev.headers.getlist('Set-Cookie')
        cookie_dev_str = "; ".join(cookies_dev)
        self.assertIn("HttpOnly", cookie_dev_str)
        self.assertIn("SameSite=Lax", cookie_dev_str)
        self.assertTrue("Expires=" in cookie_dev_str or "Max-Age=" in cookie_dev_str, "Expires/Max-Age must be set for permanent session")

        # 2. Production configuration: Secure flag present
        self.app.config['SESSION_COOKIE_SECURE'] = True
        try:
            client_prod = self.app.test_client()
            client_prod.get('/AdminLogin')
            with client_prod.session_transaction() as sess:
                csrf_prod = sess['_csrf_token']

            with patch.dict(os.environ, {'ADMIN_USERNAME': test_user, 'ADMIN_PASSWORD_HASH': test_hash}):
                with patch('App.get_db_connection') as mock_db:
                    mock_conn = MagicMock()
                    mock_cur = MagicMock()
                    mock_cur.fetchall.return_value = []
                    mock_conn.cursor.return_value = mock_cur
                    mock_conn.is_connected.return_value = True
                    mock_db.return_value = mock_conn

                    res_prod = client_prod.post('/adminlogin', data={
                        'uname': test_user,
                        'pas': test_pass,
                        'csrf_token': csrf_prod
                    })

            cookies_prod = res_prod.headers.getlist('Set-Cookie')
            cookie_prod_str = "; ".join(cookies_prod)
            self.assertIn("Secure", cookie_prod_str)
            self.assertIn("HttpOnly", cookie_prod_str)
            self.assertIn("SameSite=Lax", cookie_prod_str)
        finally:
            self.app.config['SESSION_COOKIE_SECURE'] = False

    def test_SEC_19_strict_hash_verification_no_plaintext_fallback(self):
        """SEC-19: Plaintext login fallback is completely removed; plaintext stored passwords fail authentication."""
        self.client.get('/UserLogin')
        with self.client.session_transaction() as sess:
            csrf = sess['_csrf_token']

        # Stored password in database is legacy plaintext "plain_pass"
        with patch('App.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = (1, 'LegacyUser', 'male', '30', 'leg@med.org', '123', 'addr', 'leg_user', 'plain_pass')
            mock_conn.cursor.return_value = mock_cur
            mock_conn.is_connected.return_value = True
            mock_db.return_value = mock_conn

            # User attempts to log in with matching plaintext password "plain_pass"
            res = self.client.post('/userlogin', data={
                'uname': 'leg_user',
                'pas': 'plain_pass',
                'csrf_token': csrf
            })

            # Without fallback, check_password_hash("plain_pass", "plain_pass") returns False
            # Login must fail!
            self.assertEqual(res.status_code, 200)
            self.assertIn("UserName or Password is wrong", res.data.decode('utf-8'))

    def test_SEC_20_csrf_cross_session_and_token_reuse_rejection(self):
        """SEC-20: CSRF tokens cannot be used across different sessions or after being tampered with."""
        # Client 1 establishes Session 1
        client1 = self.app.test_client()
        client1.get('/AdminLogin')
        with client1.session_transaction() as sess1:
            token1 = sess1['_csrf_token']

        # Client 2 establishes Session 2
        client2 = self.app.test_client()
        client2.get('/AdminLogin')
        with client2.session_transaction() as sess2:
            token2 = sess2['_csrf_token']

        self.assertNotEqual(token1, token2)

        # Cross-session attack: Client 2 tries to use Token 1 in Session 2
        res_cross = client2.post('/adminlogin', data={
            'uname': 'admin',
            'pas': 'test',
            'csrf_token': token1
        })
        self.assertEqual(res_cross.status_code, 400, "Cross-session CSRF token must be rejected with 400")

        # Tampered token attack: Client 1 uses corrupted token
        res_tampered = client1.post('/adminlogin', data={
            'uname': 'admin',
            'pas': 'test',
            'csrf_token': token1 + "tamper"
        })
        self.assertEqual(res_tampered.status_code, 400, "Tampered CSRF token must be rejected with 400")

    def test_SEC_21_dotenv_loading_and_environment_variable_precedence(self):
        """SEC-21: load_dotenv loads .env securely without overriding existing environment variables."""
        import tempfile
        from dotenv import load_dotenv

        # Test precedence: existing OS environment variable takes priority over .env
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_env = os.path.join(tmpdir, ".env")
            with open(temp_env, "w", encoding="utf-8") as f:
                f.write("SMTP_USERNAME=file_val@gmail.com\n")
                f.write("NEW_CKD_FEATURE_FLAG=enabled\n")

            with patch.dict(os.environ, {"SMTP_USERNAME": "existing_os_user@gmail.com"}, clear=False):
                os.environ.pop("NEW_CKD_FEATURE_FLAG", None)

                # Load with override=False (the standard configuration in App.py)
                load_dotenv(dotenv_path=temp_env, override=False)

                # Existing variable must be preserved (NOT overwritten)
                self.assertEqual(os.environ.get("SMTP_USERNAME"), "existing_os_user@gmail.com")
                # Missing variable must be loaded from .env
                self.assertEqual(os.environ.get("NEW_CKD_FEATURE_FLAG"), "enabled")

    def test_SEC_22_smtp_graceful_disablement_when_unconfigured(self):
        """SEC-22: sendmail gracefully skips email dispatch and returns False when SMTP is unconfigured."""
        from flask import session
        from App import sendmail

        # Case A: Both SMTP_USERNAME and SMTP_PASSWORD missing
        with patch.dict(os.environ, {"SMTP_USERNAME": "", "SMTP_PASSWORD": ""}):
            with self.app.test_request_context():
                session['email'] = 'patient@example.com'
                with self.assertLogs(level='WARNING') as cm:
                    result = sendmail("Critical alert message")
                    self.assertFalse(result, "sendmail must return False when credentials are not configured")
                    self.assertTrue(any("SMTP notification skipped: SMTP_USERNAME or SMTP_PASSWORD not configured" in o for o in cm.output))

        # Case B: Password missing
        with patch.dict(os.environ, {"SMTP_USERNAME": "test_user@example.com", "SMTP_PASSWORD": ""}):
            with self.app.test_request_context():
                session['email'] = 'patient@example.com'
                result = sendmail("Critical alert message")
                self.assertFalse(result, "sendmail must return False when password is empty")

        # Case C: Recipient email missing from session
        with patch.dict(os.environ, {"SMTP_USERNAME": "test_user@example.com", "SMTP_PASSWORD": "dummy_password_for_test"}):
            with self.app.test_request_context():
                result = sendmail("Critical alert message")
                self.assertFalse(result, "sendmail must return False when session recipient email is missing")

    def test_SEC_23_smtp_password_privacy_and_pii_logging(self):
        """SEC-23: SMTP password is never logged or exposed; recipient emails are redacted."""
        from flask import session
        from App import sendmail, mask_email

        # Verify email masking function
        masked = mask_email("test_team_account@example.com")
        self.assertEqual(masked, "te***t@example.com")
        self.assertNotIn("test_team_account", masked)

        masked_short = mask_email("ab@gmail.com")
        self.assertEqual(masked_short, "a***@gmail.com")

        # Verify that even on failure, the SMTP password is never in logs
        dummy_secret = "secret_pw_12345"
        with patch.dict(os.environ, {
            "SMTP_USERNAME": "test_user@example.com",
            "SMTP_PASSWORD": dummy_secret,
            "MAIL_SENDER": "test_user@example.com"
        }):
            with self.app.test_request_context():
                session['email'] = 'patient_secret_ident@example.com'
                with patch('smtplib.SMTP') as mock_smtp_class:
                    mock_server = MagicMock()
                    mock_server.login.side_effect = Exception("Authentication failed 535")
                    mock_smtp_class.return_value = mock_server

                    with self.assertLogs(level='INFO') as cm:
                        result = sendmail("Test Alert")
                        self.assertFalse(result)
                        all_logs = " ".join(cm.output)
                        self.assertNotIn(dummy_secret, all_logs, "SMTP password must never appear in log records")
                        self.assertNotIn("patient_secret_ident@example.com", all_logs)


def run_security_tests():
    print("=" * 80)
    print("PHASE 1, 2, 2D & SMTP: COMPREHENSIVE SECURITY REGRESSION TEST SUITE (23 TESTS)")
    print("=" * 80)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSecurityRemediation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_security_tests()
    sys.exit(0 if success else 1)
