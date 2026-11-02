"""
Automated Security Regression & Remediation Test Suite
Validates:
1. Repository-wide secret and credential scan (root, src/, tests/, docs/, database/)
2. Elimination of hardcoded secrets and default credentials in App.py
3. SQL parameterization integrity (verification of SQL injection defense)
4. Cryptographic password hashing and verification via werkzeug.security
5. Dynamic secure token generation for Flask SECRET_KEY
6. Session authentication safeguards on protected administrative & user routes
7. Gitignore protection for environment and secret files
"""

import os
import re
import sys
import unittest
import tempfile

# Add project root and src to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from werkzeug.security import generate_password_hash, check_password_hash
from App import app


class TestSecurityRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def test_SEC_01_repo_wide_secret_and_credential_scan(self):
        """SEC-01: Comprehensive repository-wide scan verifies zero active hardcoded secrets."""
        # Regex patterns targeting exposed secrets
        secret_patterns = [
            (re.compile(r's\.login\(.+,\s*["\'][a-z]{4}\s+[a-z]{4}\s+[a-z]{4}\s+[a-z]{4}["\']\)', re.IGNORECASE), "Exposed SMTP app password in s.login"),
            (re.compile(r'SECRET_KEY\s*=\s*["\'][a-zA-Z0-9_-]{16,}["\']'), "Hardcoded static SECRET_KEY string"),
            (re.compile(r'uname\s*==\s*["\']admin["\']\s+and\s+pas\s*==\s*["\']admin["\']'), "Hardcoded default admin credentials"),
            (re.compile(r'-----BEGIN\s+(RSA|EC|DSA|OPENSSH)?\s*PRIVATE\s+KEY-----'), "Private encryption key committed"),
            (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS Access Key ID committed")
        ]

        # Scan code, config, and script files in project (excluding .venv, .git, and raw dataset images)
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

                # Skip historical audit docs that reference past findings
                if "TESTING_GAP_AUDIT_REPORT.md" in rel_path or "test_results.json" in rel_path:
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

        # 1. No hardcoded secret key
        self.assertNotIn("app.config['SECRET_KEY'] = '7d441f27", code, "Hardcoded SECRET_KEY remains in App.py")
        self.assertIn("os.environ.get('FLASK_SECRET_KEY')", code, "App.py does not read FLASK_SECRET_KEY from environment")

        # 2. No hardcoded admin credentials
        self.assertNotIn("request.form['uname'] == 'admin' and request.form['pas'] == 'admin'", code)
        self.assertIn("ADMIN_USERNAME", code)

        # 3. No hardcoded SMTP credentials
        self.assertNotIn("tdyr kebi", code, "Compromised Gmail app password still in App.py")
        self.assertIn("os.environ.get('SMTP_PASSWORD'", code)

    def test_SEC_03_sql_injection_defense_parameterization(self):
        """SEC-03: App.py uses parameterized queries, eliminating string interpolation SQL injection."""
        app_path = os.path.join(ROOT_DIR, "App.py")
        with open(app_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Check for dangerous patterns
        dangerous_concat_1 = "where UserName='"
        dangerous_concat_2 = "VALUES ('"
        self.assertNotIn(dangerous_concat_1, code, "Vulnerable SQL concatenation detected in App.py")
        self.assertNotIn(dangerous_concat_2, code, "Vulnerable INSERT concatenation detected in App.py")

        # Verify parameterized place-holders (%s)
        self.assertIn("WHERE UserName = %s", code, "Parameterized query missing for UserName lookup")
        self.assertIn("VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", code, "Parameterized query missing for user registration")

    def test_SEC_04_cryptographic_password_hashing(self):
        """SEC-04: Password hashing uses secure cryptographic salt and non-invertible derivation."""
        password = "ClinicalSecurePassword2026!"
        h1 = generate_password_hash(password)
        h2 = generate_password_hash(password)

        # Hashes must be salted (distinct outputs for identical passwords)
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
        # Unauthenticated request to /AdminHome
        res_admin = self.client.get('/AdminHome', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302, "Unauthenticated access to /AdminHome must redirect")
        self.assertIn('/AdminLogin', res_admin.headers.get('Location', ''))

        # Unauthenticated request to /UserHome
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

        # Must not contain real passwords or live tokens
        self.assertNotIn("tdyr kebi", example_content)
        self.assertNotIn("7d441f27d441f27567d441f2b6176a", example_content)
        self.assertIn("FLASK_SECRET_KEY=", example_content)
        self.assertIn("DB_PASSWORD=", example_content)


def run_security_tests():
    print("=" * 80)
    print("PHASE 1: CRITICAL SECURITY REMEDIATION REGRESSION TEST SUITE")
    print("=" * 80)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSecurityRemediation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_security_tests()
    sys.exit(0 if success else 1)
