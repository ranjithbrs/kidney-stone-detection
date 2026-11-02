"""
Clinical Database User Password Migration Utility (Phase 2D Hardened)
Batch-migrates all legacy plaintext passwords in MySQL regtb to secure cryptographic hashes.
Features:
- Automated JSON backup before any row modification
- Atomic transaction management with explicit rollback on error
- Safe dry-run simulation mode
- Status verification helper (detects presence of unmigrated accounts)

Usage:
    python -m scripts.migrate_passwords [--dry-run] [--no-backup]
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
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


def create_table_backup(rows, backup_dir=None):
    """
    Creates a timestamped JSON backup of regtb rows prior to modification.
    Returns path of the created backup file.
    """
    if backup_dir is None:
        backup_dir = os.path.join(ROOT_DIR, "database", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"regtb_backup_{timestamp}.json")

    backup_data = [
        {"uid": r[0], "UserName": r[1], "Password": r[2]}
        for r in rows
    ]

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2)

    logging.info(f"Created pre-migration table backup: {backup_file}")
    return backup_file


def verify_migration_status(connection=None):
    """
    Inspects regtb to determine whether any legacy plaintext passwords remain.
    Returns dict with summary statistics.
    """
    owns_conn = False
    conn = connection
    if conn is None:
        try:
            conn = get_db_connection()
            owns_conn = True
        except mysql.connector.Error as err:
            logging.error(f"Cannot connect to database to verify status: {err}")
            return {"status": "error", "message": str(err), "total": 0, "unmigrated": 0, "all_migrated": False}

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT uid, UserName, Password FROM regtb")
        rows = cursor.fetchall()

        total = len(rows)
        unmigrated = sum(1 for _, _, pwd in rows if not is_hashed(pwd))
        migrated = total - unmigrated

        return {
            "status": "success",
            "total": total,
            "migrated": migrated,
            "unmigrated": unmigrated,
            "all_migrated": (unmigrated == 0)
        }
    except mysql.connector.Error as err:
        logging.error(f"Error querying regtb: {err}")
        return {"status": "error", "message": str(err), "total": 0, "unmigrated": 0, "all_migrated": False}
    finally:
        if owns_conn and conn and conn.is_connected():
            conn.close()


def batch_migrate_passwords(dry_run=False, backup=True, connection=None, backup_dir=None):
    """
    Scans the regtb table, creates a backup, and updates unhashed plaintext
    passwords with salted PBKDF2/Scrypt cryptographic hashes.
    Includes atomic rollback on error.
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
        "backup_path": None,
        "dry_run": dry_run,
        "status": "success"
    }

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT uid, UserName, Password FROM regtb")
        rows = cursor.fetchall()
        stats["total"] = len(rows)

        # Create backup before executing updates if not dry run
        if not dry_run and backup and rows:
            stats["backup_path"] = create_table_backup(rows, backup_dir=backup_dir)

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
        logging.error(f"Database error during migration. Rolling back: {err}")
        try:
            conn.rollback()
            logging.info("Transaction rollback successful.")
        except Exception as rb_err:
            logging.warning(f"Rollback failed: {rb_err}")
        stats["status"] = "error"
        stats["message"] = str(err)
    finally:
        if owns_conn and conn and conn.is_connected():
            conn.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate plaintext user passwords to secure cryptographic hashes.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without modifying database rows.")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a pre-migration JSON backup.")
    args = parser.parse_args()

    logging.info(f"Starting password migration{' (DRY RUN)' if args.dry_run else ''}...")
    res = batch_migrate_passwords(dry_run=args.dry_run, backup=(not args.no_backup))
    logging.info(f"Migration completed. Results: {res}")


if __name__ == "__main__":
    main()
