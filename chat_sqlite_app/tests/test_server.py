"""
Tests unitaires pour le serveur HTTP et le routage des requêtes.
Teste les réponses JSON, les codes HTTP, et le service des fichiers statiques.
"""

import io
import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from chat_sqlite_app.database import init_db
from chat_sqlite_app.server import ChatRequestHandler, STATIC_DIR


class MockSocket:
    def __init__(self, data: bytes):
        self.rfile = io.BytesIO(data)
        self.wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return self.rfile
        return self.wfile

    def sendall(self, data: bytes):
        self.wfile.write(data)


def execute_mock_request(method: str, path: str, body: dict = None, db_path: str = None) -> tuple[int, dict, bytes]:
    """Exécute une requête simulée à travers ChatRequestHandler sans ouvrir de socket réseau."""
    body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
    raw_request = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: localhost\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body_bytes)}\r\n\r\n"
    ).encode("utf-8") + body_bytes

    sock = MockSocket(raw_request)
    mock_server = MagicMock()

    # Configuration temporaire du db_path
    if db_path:
        ChatRequestHandler.db_path = db_path

    # Création du handler avec les streams simulés
    handler = ChatRequestHandler(sock, ("127.0.0.1", 12345), mock_server)
    sock.wfile.seek(0)
    raw_response = sock.wfile.read()

    # Décoder le code HTTP
    status_line = raw_response.split(b"\r\n")[0].decode("utf-8")
    status_code = int(status_line.split(" ")[1])

    # Extraire le corps
    headers_and_body = raw_response.split(b"\r\n\r\n", 1)
    response_body = headers_and_body[1] if len(headers_and_body) > 1 else b""

    try:
        json_data = json.loads(response_body.decode("utf-8"))
    except Exception:
        json_data = None

    return status_code, json_data, response_body


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    ChatRequestHandler.db_path = path
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            pass


def test_server_create_and_list_users(temp_db):
    status, data, _ = execute_mock_request("POST", "/api/users", {"username": "Sophie", "email": "sophie@test.com"}, temp_db)
    assert status == 201
    assert data["username"] == "Sophie"

    status, users, _ = execute_mock_request("GET", "/api/users", None, temp_db)
    assert status == 200
    assert any(u["username"] == "Sophie" for u in users)


def test_server_create_conversation_and_messages(temp_db):
    # Créer un utilisateur
    status, user, _ = execute_mock_request("POST", "/api/users", {"username": "Marc"}, temp_db)
    sender_id = user["id"]

    # Créer une conversation
    status, conv, _ = execute_mock_request("POST", "/api/conversations", {"title": "Salon Serveur"}, temp_db)
    assert status == 201
    conv_id = conv["id"]

    # Ajouter un message
    status, msg, _ = execute_mock_request("POST", "/api/messages", {
        "conversation_id": conv_id,
        "sender_id": sender_id,
        "content": "Test message via serveur"
    }, temp_db)
    assert status == 201
    assert msg["content"] == "Test message via serveur"

    # Récupérer les messages
    status, msgs, _ = execute_mock_request("GET", f"/api/conversations/{conv_id}/messages", None, temp_db)
    assert status == 200
    assert len(msgs) == 1
    assert msgs[0]["sender_username"] == "Marc"


def test_server_message_auto_create_conversation(temp_db):
    status, user, _ = execute_mock_request("POST", "/api/users", {"username": "Claire"}, temp_db)
    sender_id = user["id"]

    # Envoi avec conversation_id inexistant ou None
    status, msg, _ = execute_mock_request("POST", "/api/messages", {
        "conversation_id": None,
        "sender_id": sender_id,
        "content": "Message spontané",
        "conversation_title": "Salon Auto Généré"
    }, temp_db)
    assert status == 201
    assert msg["conversation_auto_created"] is True
    assert msg["conversation_title"] == "Salon Auto Généré"


def test_server_serve_index_html(temp_db):
    status, _, body = execute_mock_request("GET", "/", None, temp_db)
    assert status == 200
    assert b"SQLite Chat" in body
