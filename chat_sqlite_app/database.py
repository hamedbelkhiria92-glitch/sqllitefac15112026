"""
Module de gestion de la base de données SQLite.
Fournit la connexion sécurisée, la gestion des transactions,
l'initialisation des tables et l'application des index d'optimisation.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "chat.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Crée une connexion SQLite configurée avec :
    - Activation stricte des clés étrangères (PRAGMA foreign_keys = ON)
    - Mode WAL (Write-Ahead Logging) pour de meilleures performances de concurrence
    - Row factory permettant d'accéder aux colonnes sous forme de dictionnaire
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Sécurité & Intégrité : SQLite désactive les clés étrangères par défaut
    conn.execute("PRAGMA foreign_keys = ON;")
    # Optimisation : mode WAL pour lecture/écriture simultanée plus rapide
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """
    Gestionnaire de contexte pour assurer l'ouverture, le commit automatique
    ou le rollback en cas d'erreur, puis la fermeture propre de la connexion.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Initialise le schéma de la base de données :
    - Table users
    - Table conversations
    - Table messages
    - Index d'optimisation pour accélérer les requêtes fréquentes
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # 1. Table Utilisateurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Table Conversations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Table Messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # Index d'optimisation :
        # - idx_messages_conversation : accélère la récupération ordonnée des messages d'une conversation (requête 4)
        # - idx_messages_sender : accélère la recherche par expéditeur ou les jointures
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation 
            ON messages(conversation_id, created_at);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_sender 
            ON messages(sender_id);
        """)
