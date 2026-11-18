"""
=============================================================================
NEFROAI-X: Production Full-Stack Clinical Decision Support System Launcher
=============================================================================
This script launches the complete decoupled full-stack application:
- Backend: FastAPI Asynchronous REST API (Port 8000)
- Frontend: React 18 + Vite Production Single Page Application (SPA)
- Cloud/Local Vault: SQLite / PostgreSQL with SHA-256 Attestation
- Real-Time Inference: 4-Family Stacking Ensemble + KDIGO Staging + AKI Guard

Run with:
    .venv\\Scripts\\python.exe run_app.py

Access:
    Web Application:   http://127.0.0.1:8000/
    Interactive Docs:  http://127.0.0.1:8000/docs
    API Health:        http://127.0.0.1:8000/api/health
=============================================================================
"""

import os
import sys

# Ensure project root and src/ are in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import uvicorn


def verify_frontend_build():
    """Verify that the React frontend is compiled in frontend/dist."""
    dist_dir = os.path.join(ROOT_DIR, "frontend", "dist")
    index_html = os.path.join(dist_dir, "index.html")
    if not (os.path.isdir(dist_dir) and os.path.isfile(index_html)):
        print("\n" + "!" * 72)
        print(" [WARNING] frontend/dist/index.html was not found.")
        print(" Building the React frontend now using 'npm run build'...")
        print("!" * 72 + "\n")
        import subprocess
        subprocess.run(["npm", "--prefix", "frontend", "run", "build"], check=True)


def main():
    verify_frontend_build()

    print("\n" + "=" * 74)
    print("  🩺 NEFROAI-X CLINICAL DECISION SUPPORT SYSTEM (CDSS)")
    print("  Full-Stack Production Service (FastAPI + React 18 SPA)")
    print("=" * 74)
    print("  🌐 Clinical Web Portal:     http://127.0.0.1:8000/")
    print("  📖 Interactive Swagger API: http://127.0.0.1:8000/docs")
    print("  🛡️ Clinical Health Check:   http://127.0.0.1:8000/api/health")
    print("=" * 74)
    print("  Press Ctrl+C in this terminal window to stop the server.")
    print("=" * 74 + "\n")

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
