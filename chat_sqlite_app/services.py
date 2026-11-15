"""
Module des services métier pour l'application de messagerie.
Implémente les fonctions requises :
1. add_user (Ajouter un nouvel utilisateur)
2. add_message_to_conversation (Ajouter un message avec création automatique de conversation)
3. create_conversation (Créer une nouvelle conversation)
4. get_conversation_messages (Récupérer les messages d'une conversation)
"""

import re
import sqlite3
from typing import Optional, List, Dict, Any

from .database import get_db, DEFAULT_DB_PATH


class ServiceException(Exception):
    """Exception de base pour les erreurs métier."""
    pass


class UserNotFoundError(ServiceException):
    """Levée lorsqu'un utilisateur recherché n'existe pas."""
    pass


class ConversationNotFoundError(ServiceException):
    """Levée lorsqu'une conversation recherchée n'existe pas."""
    pass


# ============================================================================
# 1. AJOUTER UN NOUVEL UTILISATEUR
# ============================================================================
def add_user(
    username: str, 
    email: Optional[str] = None, 
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Crée et enregistre un nouvel utilisateur dans la base de données.

    Sécurité et validation :
    - Vérification contre les chaînes vides ou espaces seuls
    - Validation du format d'email si fourni
    - Utilisation de requêtes SQL préparées (évite les injections SQL)
    - Gestion sécurisée des conflits d'unicité (username déjà utilisé)

    :param username: Nom d'utilisateur unique (ex: 'alice')
    :param email: Adresse email optionnelle
    :param db_path: Chemin vers le fichier SQLite
    :return: Dictionnaire représentant l'utilisateur créé
    :raises ValueError: Si les données sont invalides ou si l'utilisateur existe déjà
    """
    if not username or not username.strip():
        raise ValueError("Le nom d'utilisateur ne peut pas être vide.")
    
    clean_username = username.strip()
    clean_email = email.strip() if email and email.strip() else None

    if clean_email:
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, clean_email):
            raise ValueError(f"Format d'email invalide : '{clean_email}'")

    try:
        with get_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, email)
                VALUES (?, ?)
                RETURNING id, username, email, created_at;
                """,
                (clean_username, clean_email)
            )
            row = cursor.fetchone()
            return dict(row)
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e) or "users.username" in str(e):
            raise ValueError(f"Le nom d'utilisateur '{clean_username}' est déjà utilisé.")
        raise ServiceException(f"Erreur d'intégrité de la base de données : {e}")


# ============================================================================
# 3. CRÉER UNE NOUVELLE CONVERSATION
# ============================================================================
def create_conversation(
    title: str, 
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Crée une nouvelle conversation avec un titre donné.

    :param title: Titre du salon ou sujet de la conversation
    :param db_path: Chemin vers le fichier SQLite
    :return: Dictionnaire représentant la conversation créée
    :raises ValueError: Si le titre est vide
    """
    if not title or not title.strip():
        raise ValueError("Le titre de la conversation ne peut pas être vide.")

    clean_title = title.strip()

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conversations (title)
            VALUES (?)
            RETURNING id, title, created_at;
            """,
            (clean_title,)
        )
        row = cursor.fetchone()
        return dict(row)


# ============================================================================
# 2. AJOUTER UN MESSAGE À UNE CONVERSATION (AVEC CRÉATION AUTO SI INEXISTANTE)
# ============================================================================
def add_message_to_conversation(
    conversation_id: Optional[int],
    sender_id: int,
    content: str,
    default_title: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Ajoute un message à une conversation.
    Conformité avec l'exigence 2 :
    "Si la conversation n'existe pas, elle doit être créée automatiquement avant l'ajout du message."

    Gestion :
    - Si conversation_id est None ou n'existe pas en base :
      une nouvelle conversation est créée automatiquement dans la même transaction.
    - Vérifie que l'expéditeur (sender_id) existe bien.
    - Vérifie que le contenu n'est pas vide.
    - Utilise des requêtes paramétrées pour éliminer tout risque d'injection SQL.

    :param conversation_id: ID de la conversation cible (ou None pour créer)
    :param sender_id: ID de l'utilisateur expéditeur
    :param content: Texte du message
    :param default_title: Titre de la conversation si création automatique
    :param db_path: Chemin SQLite
    :return: Dictionnaire contenant le message inséré et les infos de conversation
    """
    if not content or not content.strip():
        raise ValueError("Le contenu du message ne peut pas être vide.")
    
    clean_content = content.strip()

    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # 1. Vérifier que l'expéditeur existe
        cursor.execute("SELECT id, username FROM users WHERE id = ?", (sender_id,))
        sender = cursor.fetchone()
        if not sender:
            raise UserNotFoundError(f"L'utilisateur expéditeur avec l'ID {sender_id} n'existe pas.")

        target_conv_id = conversation_id

        # 2. Vérifier si la conversation existe déjà
        conv_exists = False
        if target_conv_id is not None:
            cursor.execute("SELECT id, title FROM conversations WHERE id = ?", (target_conv_id,))
            conv_row = cursor.fetchone()
            if conv_row:
                conv_exists = True
                conv_title = conv_row["title"]

        # 3. Création automatique si inexistante (Exigence 2)
        auto_created = False
        if not conv_exists:
            auto_created = True
            new_title = (
                default_title.strip() if default_title and default_title.strip()
                else f"Conversation #{target_conv_id}" if target_conv_id is not None
                else "Nouvelle conversation"
            )
            cursor.execute(
                "INSERT INTO conversations (title) VALUES (?) RETURNING id, title;",
                (new_title,)
            )
            new_conv = cursor.fetchone()
            target_conv_id = new_conv["id"]
            conv_title = new_conv["title"]

        # 4. Insérer le message
        cursor.execute(
            """
            INSERT INTO messages (conversation_id, sender_id, content)
            VALUES (?, ?, ?)
            RETURNING id, conversation_id, sender_id, content, created_at;
            """,
            (target_conv_id, sender_id, clean_content)
        )
        msg_row = cursor.fetchone()

        result = dict(msg_row)
        result["conversation_title"] = conv_title
        result["sender_username"] = sender["username"]
        result["conversation_auto_created"] = auto_created
        return result


# ============================================================================
# 4. RÉCUPÉRER LES MESSAGES D'UNE CONVERSATION
# ============================================================================
def get_conversation_messages(
    conversation_id: int,
    limit: Optional[int] = None,
    offset: int = 0,
    db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """
    Récupère tous les messages associés à une conversation donnée.

    Optimisations intégrées :
    - Évite le problème N+1 : utilise une jointure SQL (INNER JOIN users) pour récupérer
      en un seul aller-retour SQL le message ET le pseudo de l'auteur.
    - Exploite l'index 'idx_messages_conversation' (conversation_id, created_at).
    - Support de la pagination optionnelle (LIMIT / OFFSET) pour les gros volumes de messages.

    :param conversation_id: ID de la conversation
    :param limit: Nombre maximum de messages à retourner (None = tous)
    :param offset: Décalage de pagination
    :param db_path: Chemin SQLite
    :return: Liste chronologique ordonnée des messages avec détails de l'expéditeur
    :raises ConversationNotFoundError: Si la conversation n'existe pas
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # Vérifier l'existence de la conversation
        cursor.execute("SELECT id, title FROM conversations WHERE id = ?", (conversation_id,))
        conv = cursor.fetchone()
        if not conv:
            raise ConversationNotFoundError(f"La conversation #{conversation_id} n'existe pas.")

        sql = """
            SELECT 
                m.id,
                m.conversation_id,
                m.sender_id,
                u.username AS sender_username,
                u.email AS sender_email,
                m.content,
                m.created_at
            FROM messages m
            INNER JOIN users u ON m.sender_id = u.id
            WHERE m.conversation_id = ?
            ORDER BY m.created_at ASC, m.id ASC
        """
        params: list = [conversation_id]

        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ============================================================================
# FONCTIONS UTILITAIRES POUR L'INTERFACE GRAPHIQUE
# ============================================================================
def get_all_users(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Récupère la liste de tous les utilisateurs triés par ordre alphabétique."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, created_at FROM users ORDER BY username ASC;")
        return [dict(row) for row in cursor.fetchall()]


def get_all_conversations(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Récupère la liste des conversations avec le nombre de messages et le dernier message.
    Optimisé avec sous-requêtes/jointures d'agrégation.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id, 
                c.title, 
                c.created_at,
                COUNT(m.id) AS message_count,
                MAX(m.created_at) AS last_message_at
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id, c.title, c.created_at
            ORDER BY COALESCE(MAX(m.created_at), c.created_at) DESC;
        """)
        return [dict(row) for row in cursor.fetchall()]
