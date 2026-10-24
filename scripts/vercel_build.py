"""Build the single-origin frontend/API deployment."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("Node.js and npm are required to build the frontend.")
    subprocess.run([npm, "--prefix", "frontend", "ci"], check=True)
    subprocess.run([npm, "--prefix", "frontend", "run", "build"], check=True)
    database = Path("data/sample.db")
    if not database.exists():
        subprocess.run([sys.executable, "data/seed.py", "--path", str(database)], check=True)
    if os.environ.get("VERCEL") == "1":
        subprocess.run([sys.executable, "-m", "scripts.setup_database"], check=True)


if __name__ == "__main__":
    main()
