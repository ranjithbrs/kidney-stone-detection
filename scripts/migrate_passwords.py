"""
Clinical Database User Password Migration Utility (Phase 2)
Batch-migrates all legacy plaintext passwords in MySQL regtb to secure cryptographic hashes.
Usage:
    python -m scripts.migrate_passwords [--dry-run]
"""

import os
import sys
import argparse
import logging
from werkzeug.security import generate_password_hash
import mysql.connector

# Ensure root dir is in path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Known cryptographic hash prefixes produced by werkzeug.security
HASH_PREFIXES = ("pbkdf2:sha256:", "scrypt:", "argon2:", "pbkdf2:sha1:")


def is_hashed(password_str):
    """Returns True if the string matches recognized cryptographic password hash formats."""
    if not isinstance(password_str, str):
        return False
    return any(password_str.startswith(prefix) for prefix in HASH_PREFIXES)


def get_db_connection():
    """Connects to MySQL using environment configuration."""
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


def batch_migrate_passwords(dry_run=False, connection=None):
    """
    Scans the regtb table, identifies unhashed plaintext passwords,
    and updates them with salted PBKDF2/Scrypt cryptographic hashes.
    """
    owns_conn = False
    conn = connection
    if conn is None:
        try:
            conn = get_db_connection()
            owns_conn = True
        except mysql.connector.Error as err:
            logging.error(f"Cannot connect to database for migration: {err}")
            return {"status": "error", "message": str(err), "upgraded": 0, "total": 0}

    stats = {
        "total": 0,
        "already_hashed": 0,
        "upgraded": 0,
        "dry_run": dry_run,
        "status": "success"
    }

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT uid, UserName, Password FROM regtb")
        rows = cursor.fetchall()
        stats["total"] = len(rows)

        for uid, username, raw_password in rows:
            if is_hashed(raw_password):
                stats["already_hashed"] += 1
            else:
                secure_hash = generate_password_hash(raw_password)
                if not dry_run:
                    update_cursor = conn.cursor()
                    update_cursor.execute(
                        "UPDATE regtb SET Password = %s WHERE uid = %s",
                        (secure_hash, uid)
                    )
                stats["upgraded"] += 1
                logging.info(f"{'[DRY RUN] Would upgrade' if dry_run else 'Upgraded'} user '{username}' (UID: {uid}) to secure hash.")

        if not dry_run:
            conn.commit()
            logging.info(f"Committed {stats['upgraded']} password upgrade(s) to database.")

    except mysql.connector.Error as err:
        logging.error(f"Database error during migration: {err}")
        stats["status"] = "error"
        stats["message"] = str(err)
    finally:
        if owns_conn and conn and conn.is_connected():
            conn.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate plaintext user passwords to secure cryptographic hashes.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without modifying database rows.")
    args = parser.parse_args()

    logging.info(f"Starting password migration{' (DRY RUN)' if args.dry_run else ''}...")
    res = batch_migrate_passwords(dry_run=args.dry_run)
    logging.info(f"Migration completed. Results: {res}")


if __name__ == "__main__":
    main()
