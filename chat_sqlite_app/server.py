"""
Serveur Web HTTP autonome (Bibliothèque standard Python).
Aucune dépendance externe requise (fonctionne nativement partout).
Fournit :
- L'API REST JSON pour les utilisateurs, conversations et messages
- Le service des fichiers statiques (HTML, CSS, JS)
"""

import json
import os
import mimetypes
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Tuple, Dict, Any, Optional

from chat_sqlite_app.database import init_db, DEFAULT_DB_PATH
from chat_sqlite_app.services import (
    add_user,
    create_conversation,
    add_message_to_conversation,
    get_conversation_messages,
    get_all_users,
    get_all_conversations,
    UserNotFoundError,
    ConversationNotFoundError,
    ServiceException,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class ChatRequestHandler(BaseHTTPRequestHandler):
    """Gestionnaire de requêtes HTTP pour l'application Chat SQLite."""
    db_path: str = DEFAULT_DB_PATH

    def _send_json(self, status_code: int, data: Any):
        """Envoie une réponse JSON avec les en-têtes de sécurité appropriés."""
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, status_code: int, message: str):
        self._send_json(status_code, {"detail": message})

    def _read_json_body(self) -> Dict[str, Any]:
        """Lit et désérialise le corps de la requête JSON."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def do_OPTIONS(self):
        """Gère les requêtes préliminaires CORS."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        """Routage des requêtes GET."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # 1. Page d'accueil HTML
        if path == "/" or path == "/index.html":
            self._serve_static_file(os.path.join(STATIC_DIR, "index.html"))
            return

        # 2. Fichiers statiques (/static/style.css, /static/app.js)
        if path.startswith("/static/"):
            relative_path = path[len("/static/"):]
            file_path = os.path.join(STATIC_DIR, relative_path)
            self._serve_static_file(file_path)
            return

        # 3. API : Lister les utilisateurs
        if path == "/api/users":
            users = get_all_users(self.db_path)
            self._send_json(200, users)
            return

        # 4. API : Lister les conversations
        if path == "/api/conversations":
            conversations = get_all_conversations(self.db_path)
            self._send_json(200, conversations)
            return

        # 5. API : Récupérer les messages d'une conversation (/api/conversations/{id}/messages)
        if path.startswith("/api/conversations/") and path.endswith("/messages"):
            parts = path.split("/")
            try:
                conv_id = int(parts[3])
                limit = int(query["limit"][0]) if "limit" in query else None
                offset = int(query["offset"][0]) if "offset" in query else 0
                messages = get_conversation_messages(conv_id, limit=limit, offset=offset, db_path=self.db_path)
                self._send_json(200, messages)
            except ValueError:
                self._send_error_json(400, "Identifiant de conversation invalide.")
            except ConversationNotFoundError as e:
                self._send_error_json(404, str(e))
            return

        self._send_error_json(404, "Ressource introuvable")

    def do_POST(self):
        """Routage des requêtes POST."""
        path = urllib.parse.urlparse(self.path).path

        try:
            body = self._read_json_body()
        except Exception as e:
            self._send_error_json(400, f"JSON malformé : {e}")
            return

        # 1. API : Ajouter un utilisateur (Exigence 1)
        if path == "/api/users":
            username = body.get("username")
            email = body.get("email")
            try:
                user = add_user(username=username, email=email, db_path=self.db_path)
                self._send_json(201, user)
            except ValueError as e:
                self._send_error_json(400, str(e))
            except ServiceException as e:
                self._send_error_json(500, str(e))
            return

        # 2. API : Créer une conversation (Exigence 3)
        if path == "/api/conversations":
            title = body.get("title")
            try:
                conv = create_conversation(title=title, db_path=self.db_path)
                self._send_json(201, conv)
            except ValueError as e:
                self._send_error_json(400, str(e))
            return

        # 3. API : Ajouter un message (Exigence 2 : avec auto-création)
        if path == "/api/messages":
            conv_id = body.get("conversation_id")
            sender_id = body.get("sender_id")
            content = body.get("content")
            auto_title = body.get("conversation_title")

            if sender_id is None:
                self._send_error_json(400, "Le champ 'sender_id' est obligatoire.")
                return

            try:
                msg = add_message_to_conversation(
                    conversation_id=conv_id,
                    sender_id=int(sender_id),
                    content=content or "",
                    default_title=auto_title,
                    db_path=self.db_path
                )
                self._send_json(201, msg)
            except UserNotFoundError as e:
                self._send_error_json(404, str(e))
            except ValueError as e:
                self._send_error_json(400, str(e))
            return

        self._send_error_json(404, "Route introuvable")

    def _serve_static_file(self, file_path: str):
        """Sert un fichier statique de manière sécurisée en prévenant le path traversal."""
        # Prévention du Path Traversal
        real_static_dir = os.path.realpath(STATIC_DIR)
        real_file_path = os.path.realpath(file_path)
        if not real_file_path.startswith(real_static_dir):
            self._send_error_json(403, "Accès interdit")
            return

        if not os.path.isfile(real_file_path):
            self._send_error_json(404, "Fichier non trouvé")
            return

        mime_type, _ = mimetypes.guess_type(real_file_path)
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(real_file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "javascript" in mime_type else mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error_json(500, f"Erreur lecture fichier : {e}")

    def log_message(self, format, *args):
        """Silencie les logs verbeux en console pour garder la sortie propre."""
        pass


def run_server(host: str = "127.0.0.1", port: int = 8000, db_path: str = DEFAULT_DB_PATH):
    """Initialise la base et lance le serveur HTTP."""
    init_db(db_path)

    # Données d'exemple si premier démarrage
    users = get_all_users(db_path)
    if not users:
        u1 = add_user("Alice", "alice@example.com", db_path=db_path)
        u2 = add_user("Bob", "bob@example.com", db_path=db_path)
        c1 = create_conversation("Général", db_path=db_path)
        add_message_to_conversation(c1["id"], u1["id"], "Bienvenue sur le chat SQLite !", db_path=db_path)
        add_message_to_conversation(c1["id"], u2["id"], "Merci Alice, interface ultra réactive !", db_path=db_path)

    server_address = (host, port)
    httpd = HTTPServer(server_address, ChatRequestHandler)
    print("=" * 65)
    print(f"🚀 Serveur Chat SQLite actif sur http://{host}:{port}")
    print(f"📂 Fichiers statiques servis depuis : {STATIC_DIR}")
    print(f"💾 Base de données SQLite : {db_path}")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
