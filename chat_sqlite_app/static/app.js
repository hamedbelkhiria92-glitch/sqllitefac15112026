/**
 * Logique client du Chat SQLite.
 * Gère l'interaction avec l'API REST FastAPI, le rendu dynamique du DOM,
 * l'assainissement strict contre les failles XSS, et la gestion d'état.
 */

// État global de l'application
const state = {
    currentUserId: null,
    currentConversationId: null,
    currentConversationTitle: "",
    users: [],
    conversations: [],
    pollTimer: null,
};

// Sélecteurs DOM
const dom = {
    currentUserSelect: document.getElementById("currentUserSelect"),
    btnOpenUserModal: document.getElementById("btnOpenUserModal"),
    conversationsList: document.getElementById("conversationsList"),
    btnOpenConvModal: document.getElementById("btnOpenConvModal"),
    userCount: document.getElementById("userCount"),
    usersPillList: document.getElementById("usersPillList"),
    chatHeader: document.getElementById("chatHeader"),
    currentConvTitle: document.getElementById("currentConvTitle"),
    currentConvSubtitle: document.getElementById("currentConvSubtitle"),
    messagesContainer: document.getElementById("messagesContainer"),
    messageForm: document.getElementById("messageForm"),
    messageInput: document.getElementById("messageInput"),
    autoCreateToggle: document.getElementById("autoCreateToggle"),
    autoCreateTitle: document.getElementById("autoCreateTitle"),
    btnRefreshMessages: document.getElementById("btnRefreshMessages"),
    // Modales
    userModal: document.getElementById("userModal"),
    addUserForm: document.getElementById("addUserForm"),
    btnCloseUserModal: document.getElementById("btnCloseUserModal"),
    btnCancelUserModal: document.getElementById("btnCancelUserModal"),
    convModal: document.getElementById("convModal"),
    addConvForm: document.getElementById("addConvForm"),
    btnCloseConvModal: document.getElementById("btnCloseConvModal"),
    btnCancelConvModal: document.getElementById("btnCancelConvModal"),
    docModal: document.getElementById("docModal"),
    btnShowDocModal: document.getElementById("btnShowDocModal"),
    btnCloseDocModal: document.getElementById("btnCloseDocModal"),
    btnOkDocModal: document.getElementById("btnOkDocModal"),
    toast: document.getElementById("toast"),
};

// ============================================================================
// SÉCURITÉ : ASSAINISSEMENT CONTRE LES FAILLES XSS (Cross-Site Scripting)
// ============================================================================
/**
 * Échappe systématiquement les caractères HTML dangereux afin d'empêcher
 * l'exécution de code JavaScript arbitraire (XSS).
 */
function escapeHtml(text) {
    if (!text) return "";
    const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
    };
    return text.toString().replace(/[&<>"']/g, (m) => map[m]);
}

/**
 * Affiche une notification Toast élégante.
 */
function showToast(message, type = "info") {
    dom.toast.textContent = message;
    dom.toast.className = `toast ${type}`;
    dom.toast.classList.remove("hidden");
    setTimeout(() => {
        dom.toast.classList.add("hidden");
    }, 3500);
}

// ============================================================================
// CHARGEMENT INITIAL DES DONNÉES
// ============================================================================
async function initApp() {
    await fetchUsers();
    await fetchConversations();

    // Sélectionne automatiquement la première conversation si existante
    if (state.conversations.length > 0 && !state.currentConversationId) {
        selectConversation(state.conversations[0].id, state.conversations[0].title);
    }

    // Polling toutes les 4 secondes pour rafraîchir les messages
    state.pollTimer = setInterval(() => {
        if (state.currentConversationId && !document.hidden) {
            fetchMessages(state.currentConversationId, false);
        }
    }, 4000);
}

// ============================================================================
// 1. GESTION DES UTILISATEURS
// ============================================================================
async function fetchUsers() {
    try {
        const response = await fetch("/api/users");
        if (!response.ok) throw new Error("Erreur de récupération des utilisateurs");
        state.users = await response.json();
        renderUserSelect();
        renderUserPills();
    } catch (err) {
        console.error(err);
        showToast("Impossible de charger les utilisateurs.", "error");
    }
}

function renderUserSelect() {
    dom.currentUserSelect.innerHTML = "";
    if (state.users.length === 0) {
        dom.currentUserSelect.innerHTML = `<option value="" disabled selected>Aucun utilisateur</option>`;
        state.currentUserId = null;
        return;
    }

    state.users.forEach((user, idx) => {
        const option = document.createElement("option");
        option.value = user.id;
        option.textContent = user.username + (user.email ? ` (${user.email})` : "");
        dom.currentUserSelect.appendChild(option);
    });

    if (!state.currentUserId && state.users.length > 0) {
        state.currentUserId = state.users[0].id;
        dom.currentUserSelect.value = state.currentUserId;
    } else if (state.currentUserId) {
        dom.currentUserSelect.value = state.currentUserId;
    }
}

function renderUserPills() {
    dom.userCount.textContent = state.users.length;
    dom.usersPillList.innerHTML = "";
    state.users.forEach((u) => {
        const pill = document.createElement("span");
        pill.className = "user-pill";
        pill.textContent = `@${u.username}`;
        dom.usersPillList.appendChild(pill);
    });
}

dom.currentUserSelect.addEventListener("change", (e) => {
    state.currentUserId = parseInt(e.target.value, 10);
    // Rafraîchir l'affichage des messages pour mettre à jour les bulles "Moi" / "Autre"
    if (state.currentConversationId) {
        fetchMessages(state.currentConversationId, false);
    }
});

// ============================================================================
// 3. GESTION DES CONVERSATIONS
// ============================================================================
async function fetchConversations() {
    try {
        const response = await fetch("/api/conversations");
        if (!response.ok) throw new Error("Erreur de chargement des conversations");
        state.conversations = await response.json();
        renderConversations();
    } catch (err) {
        console.error(err);
        showToast("Impossible de charger les conversations.", "error");
    }
}

function renderConversations() {
    dom.conversationsList.innerHTML = "";
    if (state.conversations.length === 0) {
        dom.conversationsList.innerHTML = `
            <div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem; text-align: center;">
                Aucun salon. Créez-en un !
            </div>
        `;
        return;
    }

    state.conversations.forEach((conv) => {
        const item = document.createElement("div");
        item.className = `conversation-item ${conv.id === state.currentConversationId ? "active" : ""}`;
        item.onclick = () => selectConversation(conv.id, conv.title);

        item.innerHTML = `
            <div class="conv-item-left">
                <span class="conv-item-icon">💬</span>
                <span class="conv-title">${escapeHtml(conv.title)}</span>
            </div>
            <span class="conv-badge" title="Nombre de messages">${conv.message_count || 0}</span>
        `;
        dom.conversationsList.appendChild(item);
    });
}

function selectConversation(convId, convTitle) {
    state.currentConversationId = convId;
    state.currentConversationTitle = convTitle;
    dom.currentConvTitle.textContent = convTitle;
    dom.currentConvSubtitle.textContent = `Salon #${convId}`;
    
    // Si l'option auto-create était cochée, on la décoche lors d'une sélection explicite
    dom.autoCreateToggle.checked = false;
    dom.autoCreateTitle.classList.add("hidden");

    renderConversations();
    fetchMessages(convId, true);
}

// ============================================================================
// 4. RÉCUPÉRATION DES MESSAGES
// ============================================================================
async function fetchMessages(convId, shouldScroll = false) {
    try {
        const response = await fetch(`/api/conversations/${convId}/messages`);
        if (!response.ok) {
            if (response.status === 404) return;
            throw new Error("Erreur lors de la récupération des messages");
        }
        const messages = await response.json();
        renderMessages(messages, shouldScroll);
    } catch (err) {
        console.error(err);
    }
}

function renderMessages(messages, shouldScroll) {
    if (!messages || messages.length === 0) {
        dom.messagesContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🌱</div>
                <p>Aucun message dans ce salon. Soyez le premier à écrire !</p>
            </div>
        `;
        return;
    }

    // Pour éviter de re-scroller si l'utilisateur est en train de lire
    const isScrolledToBottom =
        dom.messagesContainer.scrollHeight - dom.messagesContainer.clientHeight <=
        dom.messagesContainer.scrollTop + 50;

    dom.messagesContainer.innerHTML = "";

    messages.forEach((msg) => {
        const isMine = state.currentUserId && msg.sender_id === state.currentUserId;
        const wrapper = document.createElement("div");
        wrapper.className = `message-wrapper ${isMine ? "mine" : "theirs"}`;

        const senderName = document.createElement("div");
        senderName.className = "message-sender-name";
        senderName.textContent = isMine ? "Vous" : msg.sender_username;

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        bubble.textContent = msg.content; // textContent protège automatiquement contre les XSS

        const timestamp = document.createElement("div");
        timestamp.className = "message-timestamp";
        timestamp.textContent = formatTimestamp(msg.created_at);

        wrapper.appendChild(senderName);
        wrapper.appendChild(bubble);
        wrapper.appendChild(timestamp);

        dom.messagesContainer.appendChild(wrapper);
    });

    if (shouldScroll || isScrolledToBottom) {
        dom.messagesContainer.scrollTop = dom.messagesContainer.scrollHeight;
    }
}

function formatTimestamp(isoStr) {
    if (!isoStr) return "";
    try {
        const d = new Date(isoStr.replace(" ", "T") + "Z");
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
        return isoStr;
    }
}

// ============================================================================
// 2. ENVOYER UN MESSAGE (AVEC OPTION CRÉATION AUTOMATIQUE)
// ============================================================================
dom.messageForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const content = dom.messageInput.value.trim();
    if (!content) return;

    if (!state.currentUserId) {
        showToast("Veuillez d'abord sélectionner ou créer un utilisateur.", "error");
        return;
    }

    const isAutoCreate = dom.autoCreateToggle.checked;
    let targetConvId = state.currentConversationId;
    let autoTitle = dom.autoCreateTitle.value.trim() || undefined;

    // Si le mode auto-create est activé, on passe conversation_id = null
    if (isAutoCreate) {
        targetConvId = null;
    } else if (!targetConvId) {
        showToast("Veuillez sélectionner une conversation ou cocher l'auto-création.", "error");
        return;
    }

    try {
        const response = await fetch("/api/messages", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                conversation_id: targetConvId,
                sender_id: state.currentUserId,
                content: content,
                conversation_title: autoTitle,
            }),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Erreur lors de l'envoi");
        }

        const msgData = await response.json();
        dom.messageInput.value = "";

        if (msgData.conversation_auto_created) {
            showToast(`Conversation auto-créée : "${msgData.conversation_title}" !`, "success");
            await fetchConversations();
            selectConversation(msgData.conversation_id, msgData.conversation_title);
        } else {
            await fetchMessages(state.currentConversationId, true);
            await fetchConversations();
        }
    } catch (err) {
        console.error(err);
        showToast(err.message, "error");
    }
});

// Envoi rapide avec la touche "Entrée" (Maj+Entrée pour nouvelle ligne)
dom.messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        dom.messageForm.dispatchEvent(new Event("submit"));
    }
});

dom.autoCreateToggle.addEventListener("change", (e) => {
    if (e.target.checked) {
        dom.autoCreateTitle.classList.remove("hidden");
        dom.autoCreateTitle.focus();
    } else {
        dom.autoCreateTitle.classList.add("hidden");
    }
});

dom.btnRefreshMessages.addEventListener("click", () => {
    if (state.currentConversationId) {
        fetchMessages(state.currentConversationId, false);
        fetchConversations();
        showToast("Messages actualisés", "info");
    }
});

// ============================================================================
// MODALES (AJOUT UTILISATEUR & CRÉATION CONVERSATION)
// ============================================================================
// Modale Utilisateur
dom.btnOpenUserModal.onclick = () => {
    dom.userModal.classList.remove("hidden");
    document.getElementById("newUsername").focus();
};
dom.btnCloseUserModal.onclick = () => dom.userModal.classList.add("hidden");
dom.btnCancelUserModal.onclick = () => dom.userModal.classList.add("hidden");

dom.addUserForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("newUsername").value.trim();
    const email = document.getElementById("newUserEmail").value.trim() || null;

    try {
        const response = await fetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, email }),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Erreur d'ajout de l'utilisateur");
        }

        const newUser = await response.json();
        showToast(`Utilisateur @${newUser.username} créé avec succès !`, "success");
        dom.addUserForm.reset();
        dom.userModal.classList.add("hidden");

        await fetchUsers();
        state.currentUserId = newUser.id;
        dom.currentUserSelect.value = newUser.id;
    } catch (err) {
        showToast(err.message, "error");
    }
});

// Modale Conversation
dom.btnOpenConvModal.onclick = () => {
    dom.convModal.classList.remove("hidden");
    document.getElementById("newConvTitle").focus();
};
dom.btnCloseConvModal.onclick = () => dom.convModal.classList.add("hidden");
dom.btnCancelConvModal.onclick = () => dom.convModal.classList.add("hidden");

dom.addConvForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("newConvTitle").value.trim();

    try {
        const response = await fetch("/api/conversations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Erreur de création de la conversation");
        }

        const newConv = await response.json();
        showToast(`Salon "${newConv.title}" créé avec succès !`, "success");
        dom.addConvForm.reset();
        dom.convModal.classList.add("hidden");

        await fetchConversations();
        selectConversation(newConv.id, newConv.title);
    } catch (err) {
        showToast(err.message, "error");
    }
});

// Modale Rapport Technique (Optimisation & Sécurité)
dom.btnShowDocModal.onclick = () => dom.docModal.classList.remove("hidden");
dom.btnCloseDocModal.onclick = () => dom.docModal.classList.add("hidden");
dom.btnOkDocModal.onclick = () => dom.docModal.classList.add("hidden");

// Fermer les modales en cliquant en dehors
window.onclick = (e) => {
    if (e.target === dom.userModal) dom.userModal.classList.add("hidden");
    if (e.target === dom.convModal) dom.convModal.classList.add("hidden");
    if (e.target === dom.docModal) dom.docModal.classList.add("hidden");
};

// Démarrer l'application dès le chargement du DOM
document.addEventListener("DOMContentLoaded", initApp);
