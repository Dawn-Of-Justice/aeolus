"""
scripts/run_dashboard.py
Start the Aeolus Streamlit dashboard.

Usage:
  python scripts/run_dashboard.py
  # or directly:
  streamlit run aeolus/dashboard/app.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
app_path = ROOT / "aeolus" / "dashboard" / "app.py"

try:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            "8500",
            "--browser.serverAddress",
            "localhost",
        ],
        cwd=ROOT,
    )
except KeyboardInterrupt:
    pass
