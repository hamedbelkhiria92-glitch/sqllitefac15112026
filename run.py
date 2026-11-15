"""
Point d'entrée racine pour exécuter l'application Chat SQLite.
Usage : python run.py
"""

import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from chat_sqlite_app.server import run_server

if __name__ == "__main__":
    run_server(host="127.0.0.1", port=8000)
