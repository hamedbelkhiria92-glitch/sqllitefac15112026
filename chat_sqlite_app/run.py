"""
Script principal de lancement de l'application Chat SQLite.
Démarre le serveur HTTP et donne accès immédiat à l'interface HTML/CSS.
"""

import sys
import os

# Ajout du dossier au PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from chat_sqlite_app.server import run_server

if __name__ == "__main__":
    port = 8000
    host = "127.0.0.1"
    run_server(host=host, port=port)
