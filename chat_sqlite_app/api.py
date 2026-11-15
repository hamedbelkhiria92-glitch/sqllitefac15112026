"""
API REST FastAPI pour l'application de messagerie Chat SQLite.
Connecte l'interface graphique HTML/CSS/JS aux services backend.
"""

import os
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .database import init_db, DEFAULT_DB_PATH
from .services import (
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

# Initialisation de la DB au cycle de vie de l'application
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DEFAULT_DB_PATH)
    # Pré-remplissage avec quelques données initiales si vide pour tester immédiatement l'interface
    users = get_all_users()
    if not users:
        u1 = add_user("Alice", "alice@test.com")
        u2 = add_user("Bob", "bob@test.com")
        c1 = create_conversation("Général")
        add_message_to_conversation(c1["id"], u1["id"], "Bienvenue sur le chat SQLite !")
        add_message_to_conversation(c1["id"], u2["id"], "Merci Alice, l'interface est ultra fluide !")
    yield

app = FastAPI(
    title="Chat SQLite API",
    description="Backend de messagerie avec stockage SQLite optimisé et sécurisé",
    version="1.0.0",
    lifespan=lifespan
)

# ---------------------------------------------------------------------------
# Modèles de requêtes Pydantic (Sécurité & Validation stricte des données)
# ---------------------------------------------------------------------------
class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="Pseudo unique")
    email: Optional[str] = Field(None, max_length=100, description="Email optionnel")


class ConversationCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Titre du salon")


class MessageCreateRequest(BaseModel):
    conversation_id: Optional[int] = Field(None, description="ID de la conversation (None = auto-création)")
    sender_id: int = Field(..., description="ID de l'expéditeur")
    content: str = Field(..., min_length=1, max_length=5000, description="Contenu textuel du message")
    conversation_title: Optional[str] = Field(None, description="Titre facultatif en cas de création automatique")


# ---------------------------------------------------------------------------
# Routes API
# ---------------------------------------------------------------------------
@app.get("/api/users", summary="Lister les utilisateurs")
def api_get_users():
    return get_all_users()


@app.post("/api/users", status_code=status.HTTP_201_CREATED, summary="Ajouter un nouvel utilisateur")
def api_add_user(payload: UserCreateRequest):
    try:
        user = add_user(payload.username, payload.email)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/conversations", summary="Lister toutes les conversations")
def api_get_conversations():
    return get_all_conversations()


@app.post("/api/conversations", status_code=status.HTTP_201_CREATED, summary="Créer une nouvelle conversation")
def api_create_conversation(payload: ConversationCreateRequest):
    try:
        conv = create_conversation(payload.title)
        return conv
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/conversations/{conversation_id}/messages", summary="Récupérer les messages d'une conversation")
def api_get_messages(conversation_id: int, limit: Optional[int] = None, offset: int = 0):
    try:
        messages = get_conversation_messages(conversation_id, limit=limit, offset=offset)
        return messages
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.post("/api/messages", status_code=status.HTTP_201_CREATED, summary="Ajouter un message à une conversation (avec création auto)")
def api_add_message(payload: MessageCreateRequest):
    try:
        msg = add_message_to_conversation(
            conversation_id=payload.conversation_id,
            sender_id=payload.sender_id,
            content=payload.content,
            default_title=payload.conversation_title
        )
        return msg
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# Fichiers statiques et Page d'accueil HTML/CSS
# ---------------------------------------------------------------------------
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Interface statique introuvable"}
