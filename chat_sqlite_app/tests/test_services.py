"""
Tests unitaires pour les fonctions de service de l'application Chat SQLite.
Vérifie la robustesse, l'intégrité référentielle, et le respect strict des exigences.
"""

import os
import tempfile
import pytest

from chat_sqlite_app.database import init_db
from chat_sqlite_app.services import (
    add_user,
    create_conversation,
    add_message_to_conversation,
    get_conversation_messages,
    get_all_users,
    get_all_conversations,
    UserNotFoundError,
    ConversationNotFoundError,
)


@pytest.fixture
def temp_db():
    """Crée une base de données temporaire pour chaque test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            pass


# ============================================================================
# TESTS 1 : AJOUTER UN NOUVEL UTILISATEUR
# ============================================================================
def test_add_user_success(temp_db):
    user = add_user("Alice", "alice@example.com", db_path=temp_db)
    assert user["id"] is not None
    assert user["username"] == "Alice"
    assert user["email"] == "alice@example.com"
    assert user["created_at"] is not None


def test_add_user_without_email(temp_db):
    user = add_user("Bob", db_path=temp_db)
    assert user["id"] is not None
    assert user["username"] == "Bob"
    assert user["email"] is None


def test_add_user_duplicate_username_fails(temp_db):
    add_user("Charlie", "charlie@example.com", db_path=temp_db)
    with pytest.raises(ValueError, match="déjà utilisé"):
        add_user("Charlie", "autre@example.com", db_path=temp_db)


def test_add_user_empty_username_fails(temp_db):
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        add_user("   ", db_path=temp_db)


def test_add_user_invalid_email_fails(temp_db):
    with pytest.raises(ValueError, match="Format d'email invalide"):
        add_user("Dave", "invalid-email", db_path=temp_db)


# ============================================================================
# TESTS 3 : CRÉER UNE NOUVELLE CONVERSATION
# ============================================================================
def test_create_conversation_success(temp_db):
    conv = create_conversation("Projet Alpha", db_path=temp_db)
    assert conv["id"] is not None
    assert conv["title"] == "Projet Alpha"
    assert conv["created_at"] is not None


def test_create_conversation_empty_title_fails(temp_db):
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        create_conversation("   ", db_path=temp_db)


# ============================================================================
# TESTS 2 : AJOUTER UN MESSAGE AVEC CRÉATION AUTO SI INEXISTANTE
# ============================================================================
def test_add_message_to_existing_conversation(temp_db):
    alice = add_user("Alice", db_path=temp_db)
    conv = create_conversation("Général", db_path=temp_db)

    msg = add_message_to_conversation(
        conversation_id=conv["id"],
        sender_id=alice["id"],
        content="Bonjour à tous !",
        db_path=temp_db
    )

    assert msg["id"] is not None
    assert msg["conversation_id"] == conv["id"]
    assert msg["sender_id"] == alice["id"]
    assert msg["content"] == "Bonjour à tous !"
    assert msg["sender_username"] == "Alice"
    assert msg["conversation_auto_created"] is False


def test_add_message_auto_creates_conversation_when_id_none(temp_db):
    alice = add_user("Alice", db_path=temp_db)

    msg = add_message_to_conversation(
        conversation_id=None,
        sender_id=alice["id"],
        content="Premier message d'un nouveau fil",
        default_title="Support Technique",
        db_path=temp_db
    )

    assert msg["id"] is not None
    assert msg["conversation_id"] is not None
    assert msg["conversation_title"] == "Support Technique"
    assert msg["conversation_auto_created"] is True


def test_add_message_auto_creates_conversation_when_id_not_found(temp_db):
    alice = add_user("Alice", db_path=temp_db)

    # Conversation ID 99999 n'existe pas en base
    msg = add_message_to_conversation(
        conversation_id=99999,
        sender_id=alice["id"],
        content="Message avec ID inexistant",
        db_path=temp_db
    )

    assert msg["id"] is not None
    # Une nouvelle conversation doit avoir été créée automatiquement
    assert msg["conversation_id"] is not None
    assert msg["conversation_id"] != 99999
    assert msg["conversation_auto_created"] is True
    assert "Conversation #99999" in msg["conversation_title"]


def test_add_message_invalid_sender_fails(temp_db):
    conv = create_conversation("Général", db_path=temp_db)

    with pytest.raises(UserNotFoundError):
        add_message_to_conversation(
            conversation_id=conv["id"],
            sender_id=88888,  # Inexistant
            content="Hello",
            db_path=temp_db
        )


def test_add_message_empty_content_fails(temp_db):
    alice = add_user("Alice", db_path=temp_db)
    conv = create_conversation("Général", db_path=temp_db)

    with pytest.raises(ValueError, match="ne peut pas être vide"):
        add_message_to_conversation(
            conversation_id=conv["id"],
            sender_id=alice["id"],
            content="   ",
            db_path=temp_db
        )


# ============================================================================
# TESTS 4 : RÉCUPÉRER LES MESSAGES D'UNE CONVERSATION
# ============================================================================
def test_get_conversation_messages_chronological_order(temp_db):
    alice = add_user("Alice", db_path=temp_db)
    bob = add_user("Bob", db_path=temp_db)
    conv = create_conversation("Développement", db_path=temp_db)

    m1 = add_message_to_conversation(conv["id"], alice["id"], "Message 1", db_path=temp_db)
    m2 = add_message_to_conversation(conv["id"], bob["id"], "Message 2", db_path=temp_db)
    m3 = add_message_to_conversation(conv["id"], alice["id"], "Message 3", db_path=temp_db)

    messages = get_conversation_messages(conv["id"], db_path=temp_db)

    assert len(messages) == 3
    assert [m["content"] for m in messages] == ["Message 1", "Message 2", "Message 3"]
    assert [m["sender_username"] for m in messages] == ["Alice", "Bob", "Alice"]


def test_get_conversation_messages_pagination(temp_db):
    alice = add_user("Alice", db_path=temp_db)
    conv = create_conversation("Test Pagination", db_path=temp_db)

    for i in range(1, 6):
        add_message_to_conversation(conv["id"], alice["id"], f"Msg {i}", db_path=temp_db)

    # Page 1 (2 messages)
    page1 = get_conversation_messages(conv["id"], limit=2, offset=0, db_path=temp_db)
    assert len(page1) == 2
    assert page1[0]["content"] == "Msg 1"
    assert page1[1]["content"] == "Msg 2"

    # Page 2 (2 messages)
    page2 = get_conversation_messages(conv["id"], limit=2, offset=2, db_path=temp_db)
    assert len(page2) == 2
    assert page2[0]["content"] == "Msg 3"
    assert page2[1]["content"] == "Msg 4"


def test_get_conversation_messages_nonexistent_conv_fails(temp_db):
    with pytest.raises(ConversationNotFoundError):
        get_conversation_messages(12345, db_path=temp_db)


# ============================================================================
# TESTS UTILITAIRES POUR L'INTERFACE
# ============================================================================
def test_get_all_users_and_conversations(temp_db):
    add_user("Zoe", db_path=temp_db)
    add_user("Alex", db_path=temp_db)
    users = get_all_users(db_path=temp_db)
    assert len(users) == 2
    assert users[0]["username"] == "Alex"  # Tri alphabétique

    c1 = create_conversation("Room A", db_path=temp_db)
    c2 = create_conversation("Room B", db_path=temp_db)
    convs = get_all_conversations(db_path=temp_db)
    assert len(convs) == 2
