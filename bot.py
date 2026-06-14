import logging
import re
import json
import os
import asyncio
import datetime
import time
import copy
from zoneinfo import ZoneInfo
from collections import defaultdict, deque

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ═══════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════
TOKEN    = os.getenv("BOT_TOKEN", "")
ADMIN_ID = 6740407761
DATA_FILE = "bot_data.json"
BOGOTA_TZ = ZoneInfo("America/Bogota")

# ── Centro de Mensajes — validación estricta ──────────────
VALID_TYPES = ["text", "photo", "video", "audio", "voice", "document"]
VALID_CATEGORIES = [
    "devocional", "versiculo", "audio", "musica",
    "estudio", "anuncio", "bienvenida", "reglas", "general"
]
TYPE_LABELS = {
    "text":     "📝 Texto",
    "photo":    "🖼 Imagen",
    "video":    "🎥 Video",
    "audio":    "🎵 Audio",
    "voice":    "🎙 Voz",
    "document": "📄 Documento",
}
CAT_LABELS = {
    "devocional": "📖 Devocional",
    "versiculo":  "✝️ Versículo",
    "audio":      "🎧 Audio",
    "musica":     "🎵 Música",
    "estudio":    "📚 Estudio",
    "anuncio":    "📢 Anuncio",
    "bienvenida": "👋 Bienvenida",
    "reglas":     "📋 Reglas",
    "general":    "📁 General",
}

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
#  DATOS POR DEFECTO
# ═══════════════════════════════════════════════════════
DEFAULT_DATA = {
    "welcome": "✨ ¡Bienvenido(a), {nombre}!\n\nYa formas parte de una comunidad de jóvenes que busca conocer más a Dios y vivir su fe cada día.\n\n🙏 Siéntete en casa.\n📖 Cristo nos une.\n\nBienvenido a *Fuera del Templo*.",
    "farewell": "📖 *{nombre}* ha continuado su camino fuera de esta comunidad.\n\nQue la gracia de Dios le acompañe, le fortalezca y le dirija en cada etapa de su vida.\n\n✝️ Que el Señor bendiga su caminar.",
    "night_hour": 22,
    "day_hour": 6,
    "night_mode_active": False,
    "night_mode_auto": True,
    "warnings": {},
    "last_welcome_id": {},
    "last_rules_id": {},
    "registered_chats": [],
    "dcc_review_queue": [],
    "dcc_learned_safe":   [],
    "dcc_learned_danger": [],
    "dcc_training_stats": {
        "aprobados": 0,
        "bloqueados": 0,
        "revisados": 0,
        "patrones_aprendidos": 0
    },
    "pastoral_response_enabled": True,
    "pastoral_response_text": "🙏 Estamos orando por ti. Dios puede ayudarte y darte fuerzas para vencer cualquier lucha. No estás solo.",
    "bad_words": [],
    "adult_domains": [
        "pornhub","xvideos","xnxx","redtube","youporn","xhamster","brazzers",
        "onlyfans","chaturbate","livejasmin","stripchat","cam4","myfreecams",
        "bongacams","nudist","erotic",
        "hentai","fetish","sexo","porno","nakedgirl","nsfw","rule34"
    ],
    "adult_keywords": [
        "desnudo","desnuda","sin ropa","foto caliente","video hot",
        "contenido adulto","pack","manda pack","envia pack","fotos intimas",
        "video intimo","sexting","nudes","nude","porno","pornografia",
        "masturbacion","orgasmo","relacion sexual","acto sexual"
    ],
    "custom_messages": [],
    "scheduled_messages": [],
    "welcome_config": {
        "enabled":        False,
        "image_file_id":  None,
        "message_text":   None,
        "show_rules":     True,
        "rules_delay":    2,
        "delete_previous": True
    },
    "last_welcome_image_id": {},
    "last_welcome_text_id":  {},
    "owner_security": {
        "enabled":         True,
        "secret_keyword":  "DTB",
        "session_timeout": 1800,
        "owners":          [6740407761]
    },
    "rules": "📖 *REGLAMENTO OFICIAL — FUERA DEL TEMPLO*\n\n*1. Cristo es el centro*\nToda participación alineada con los valores de Jesucristo. Se promoverá el amor, la verdad, la gracia y el respeto.\n\n*2. Respeto mutuo*\nNo insultos, burlas, humillaciones ni lenguaje ofensivo. Prohibido el acoso o agresión verbal.\n\n*3. Contenido apropiado*\n✅ Reflexiones bíblicas, devocionales, testimonios, música cristiana, mensajes de ánimo.\n❌ Contenido sexual, blasfemo, violento o contrario a la fe cristiana.\n\n*4. Debates doctrinales*\nCon respeto. Sin ataques a iglesias o denominaciones.\n\n*5. Sin spam ni enlaces*\nNo links sin autorización. No publicidad ni contenido repetitivo.\n\n*6. Privacidad*\nNo compartir datos personales de otros miembros sin autorización.\n\n*7. Ambiente edificante*\nEmpatía y apoyo mutuo. Sin chismes ni rumores destructivos.\n\n*8. Uso responsable*\nEvitar mensajes excesivos. Respetar momentos de reflexión y oración.\n\n*9. Sanciones*\n1️⃣ Llamado de atención → 2️⃣ Advertencia formal → 3️⃣ Restricción 24h → 4️⃣ Expulsión\n\n*10. Principios*\nAmor • Respeto • Humildad • Honestidad • Servicio • Fe\n\n✨ _Este grupo existe para glorificar a Dios._ 🙏📖✝️"
}

# ═══════════════════════════════════════════════════════
#  PERSISTENCIA
# ═══════════════════════════════════════════════════════
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        d = copy.deepcopy(DEFAULT_DATA)
        d.update(saved)
        return d
    return copy.deepcopy(DEFAULT_DATA)

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

data = load_data()

# ═══════════════════════════════════════════════════════
#  ANTI-SPAM
# ═══════════════════════════════════════════════════════
#  ANTI-SPAM
# ═══════════════════════════════════════════════════════
SPAM_WINDOW    = 10      # segundos de ventana deslizante
SPAM_LIMIT     = 3       # mensajes máximos en la ventana
SPAM_INACTIVE  = 1800    # segundos sin actividad para limpiar (30 min)

spam_tracker   = defaultdict(deque)   # {(chat_id, user_id): deque de timestamps}
spam_last_seen = {}                   # {(chat_id, user_id): timestamp última actividad}

def is_spamming(chat_id, user_id):
    key = (chat_id, user_id)
    now = time.time()
    spam_last_seen[key] = now          # registrar actividad
    q = spam_tracker[key]
    while q and now - q[0] > SPAM_WINDOW:
        q.popleft()
    q.append(now)
    return len(q) > SPAM_LIMIT

async def cleanup_spam_tracker(context: ContextTypes.DEFAULT_TYPE):
    """Elimina entradas inactivas de spam_tracker cada 30 minutos."""
    now = time.time()
    inactive = [
        key for key, last in spam_last_seen.items()
        if now - last > SPAM_INACTIVE
    ]
    for key in inactive:
        spam_tracker.pop(key, None)
        spam_last_seen.pop(key, None)
    if inactive:
        logger.info(f"🧹 spam_tracker: {len(inactive)} entradas inactivas eliminadas.")

# ═══════════════════════════════════════════════════════
#  DETECCIÓN DE CONTENIDO
# ═══════════════════════════════════════════════════════
URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|t\.me/\S+|bit\.ly/\S+"
    r"|\S+\.(com|net|org|io|me|tv|co|info|biz|xyz|club|site|online)\b)",
    re.IGNORECASE,
)

def is_adult(text):
    t = text.lower()
    return any(d in t for d in data["adult_domains"]) or \
           any(k in t for k in data["adult_keywords"])

def has_bad_word(text):
    t = text.lower()
    return any(w in t for w in data["bad_words"])

def has_link(text):
    return bool(URL_PATTERN.search(text))

# ═══════════════════════════════════════════════════════
#  DCC V1 — DISCERNIMIENTO CONTEXTUAL CRISTIANO
# ═══════════════════════════════════════════════════════

# ── Fase 3: Puntajes configurables ────────────────────
DCC_RISK_WORDS: dict[str, int] = {
    "porno":           10,
    "pornografía":     10,
    "pornografia":     10,
    "nudes":           10,
    "nude":            8,
    "onlyfans":        12,
    "pack":            8,
    "sexo":            8,
    "contenido adulto":12,
    "sexting":         10,
    "fotos íntimas":   10,
    "fotos intimas":   10,
    "video hot":       10,
    "desnudo":         7,
    "desnuda":         7,
}

DCC_SAFE_WORDS: dict[str, int] = {
    "oremos":          20,
    "oración":         15,
    "oracion":         15,
    "cristo":          15,
    "jesús":           15,
    "jesus":           15,
    "dios":            12,
    "libertó":         15,
    "liberto":         15,
    "ayuda":           10,
    "testimonio":      15,
    "restauración":    15,
    "restauracion":    15,
    "dejar":           8,
    "vencer":          8,
    "liberación":      12,
    "liberacion":      12,
    "sanidad":         12,
    "intercesión":     15,
    "intercesion":     15,
    "bíblica":         10,
    "biblica":         10,
    "escritura":       10,
}

# ── Fase 4: Frases ─────────────────────────────────────
DCC_DANGER_PHRASES: list[tuple[str, int]] = [
    ("manda pack",             25),
    ("envia pack",             25),
    ("envía pack",             25),
    ("envíame nudes",          25),
    ("te vendo contenido",     25),
    ("onlyfans gratis",        25),
    ("entra aquí",             15),
    ("tengo videos",           15),
    ("manda foto",             18),
    ("mándame foto",           18),
    ("contenido hot",          20),
    ("vendo fotos",            22),
    ("vendo videos",           22),
    ("únete a mi canal",       15),
    ("link de adultos",        20),
]

DCC_SAFE_PHRASES: list[tuple[str, int]] = [
    ("oremos por",             25),
    ("pidan oración",          25),
    ("pidan oracion",          25),
    ("cristo me libertó",      30),
    ("cristo me liberto",      30),
    ("dios me ayudó",          25),
    ("dios me ayudo",          25),
    ("necesito ayuda espiritual", 25),
    ("estoy luchando con",     20),
    ("quiero dejar",           20),
    ("oren por mí",            25),
    ("oren por mi",            25),
    ("la biblia enseña",       20),
    ("la escritura dice",      20),
    ("jesús enseñó",           20),
    ("jesus enseno",           20),
    ("qué dice la biblia",     20),
    ("que dice la biblia",     20),
    ("cómo vencer",            18),
    ("como vencer",            18),
    ("lucha espiritual",       20),
    ("testimonio de",          18),
    ("dios me restauró",       25),
    ("dios me restauro",       25),
]

# ── Fase 5: Umbrales ───────────────────────────────────
DCC_ALLOW_SCORE  = -5    # <= este valor → PERMITIR
DCC_REVIEW_SCORE = 5     # entre ALLOW y REVIEW → REVISAR
DCC_BLOCK_SCORE  = 5     # >= este valor → BLOQUEAR
DCC_REVIEW_MAX   = 500   # máximo de registros en cola

# ── Fase 2: Clasificación de contexto ─────────────────
_CTX_PATTERNS: dict[str, list[str]] = {
    "PRAYER":    ["oremos", "oración", "oracion", "intercedan", "oren por", "pidan oración",
                  "pidan oracion", "tiempo de oración"],
    "TESTIMONY": ["cristo me libertó", "dios me restauró", "ya no vivo en eso",
                  "testimonio", "dios me ayudó", "fui libre", "me liberó"],
    "TEACHING":  ["la biblia enseña", "la escritura dice", "jesús enseñó", "la palabra dice",
                  "en mateo", "en juan", "en génesis", "el señor dice"],
    "QUESTION":  ["es pecado", "qué dice la biblia", "cómo vencer", "me pueden ayudar",
                  "es correcto", "qué opinas", "cómo puedo"],
    "HELP":      ["necesito ayuda", "estoy luchando", "oren por mí", "oren por mi",
                  "estoy mal", "necesito oración", "ayúdenme"],
    "PROMOTION": ["vean este video", "entren aquí", "visiten esta página", "únanse a",
                  "sigan mi canal", "link en bio", "descarguen"],
    "EXCHANGE":  ["manda pack", "envíame fotos", "pásame el link", "mándame",
                  "te mando", "intercambiamos", "fotos íntimas"],
}

def analyze_context(text: str) -> str:
    """Fase 2: Clasifica el mensaje en una categoría de contexto."""
    t = text.lower()
    for ctx, patterns in _CTX_PATTERNS.items():
        if any(p in t for p in patterns):
            return ctx
    return "UNKNOWN"

def calculate_dcc_score(text: str) -> int:
    """Fase 3+4: Calcula el puntaje de riesgo del mensaje."""
    t     = text.lower()
    score = 0

    # Fase 4 — frases tienen prioridad (se evalúan primero)
    for phrase, pts in DCC_DANGER_PHRASES:
        if phrase in t:
            score += pts

    for phrase, pts in DCC_SAFE_PHRASES:
        if phrase in t:
            score -= pts

    # Fase 3 — palabras individuales
    for word, pts in DCC_RISK_WORDS.items():
        if word in t:
            score += pts

    for word, pts in DCC_SAFE_WORDS.items():
        if word in t:
            score -= pts

    return score

def dcc_classify(score: int) -> str:
    """Devuelve ALLOW, REVIEW o BLOCK según el puntaje."""
    if score <= DCC_ALLOW_SCORE:
        return "ALLOW"
    if score >= DCC_BLOCK_SCORE:
        return "BLOCK"
    return "REVIEW"

def dcc_queue_add(user_id: int, chat_id: int, username: str, text: str, score: int):
    """Fase 5: Guarda un mensaje en la cola de revisión."""
    queue = data.setdefault("dcc_review_queue", [])
    queue.append({
        "user_id":   user_id,
        "chat_id":   chat_id,
        "username":  username,
        "message":   text[:500],   # limitar longitud
        "score":     score,
        "timestamp": datetime.datetime.now(BOGOTA_TZ).strftime("%Y-%m-%dT%H:%M:%S"),
    })
    # Mantener máximo 500 registros — eliminar los más antiguos
    if len(queue) > DCC_REVIEW_MAX:
        data["dcc_review_queue"] = queue[-DCC_REVIEW_MAX:]
    save_data(data)

# ═══════════════════════════════════════════════════════
#  DCC V2 — FASES 6-10
# ═══════════════════════════════════════════════════════

# ── Fase 6: Entrada enriquecida a la cola ─────────────
def dcc_queue_add_v2(user_id: int, chat_id: int, username: str,
                     nombre: str, text: str, score: int,
                     classification: str, motivo: str):
    """Fase 6: Guarda registro enriquecido en dcc_review_queue."""
    import uuid as _uuid
    queue = data.setdefault("dcc_review_queue", [])
    queue.append({
        "id":             str(_uuid.uuid4())[:8],
        "fecha":          datetime.datetime.now(BOGOTA_TZ).strftime("%Y-%m-%dT%H:%M:%S"),
        "chat_id":        chat_id,
        "user_id":        user_id,
        "username":       username,
        "nombre":         nombre,
        "mensaje":        text[:500],
        "score":          score,
        "clasificacion":  classification,
        "motivo":         motivo,
        "confianza":      calculate_confidence(score),
    })
    if len(queue) > DCC_REVIEW_MAX:
        data["dcc_review_queue"] = queue[-DCC_REVIEW_MAX:]
    save_data(data)

# ── Fase 8: Índice de confianza ────────────────────────
def calculate_confidence(score: int) -> dict:
    """Fase 8: Calcula índice de confianza basado en score DCC."""
    # Normalizar score a rango 0-100
    # Score muy negativo = muy seguro (100%), muy positivo = muy peligroso (0%)
    clamped   = max(-50, min(50, score))
    safe_pct  = int(((50 - clamped) / 100) * 100)
    safe_pct  = max(0, min(100, safe_pct))

    if safe_pct >= 81:
        label = "SAFE"
        emoji = "🟢"
    elif safe_pct >= 61:
        label = "PROBABLE_SAFE"
        emoji = "🟡"
    elif safe_pct >= 41:
        label = "REVIEW"
        emoji = "🟠"
    elif safe_pct >= 21:
        label = "PROBABLE_DANGER"
        emoji = "🔴"
    else:
        label = "DANGER"
        emoji = "⛔"

    return {"pct": safe_pct, "label": label, "emoji": emoji}

# ── Fase 7: Memoria de patrones ────────────────────────
def dcc_score_with_memory(text: str) -> int:
    """Fase 7: Calcula score incluyendo patrones aprendidos."""
    score = calculate_dcc_score(text)
    t = text.lower()
    for pattern in data.get("dcc_learned_safe", []):
        if pattern.lower() in t:
            score -= 15
    for pattern in data.get("dcc_learned_danger", []):
        if pattern.lower() in t:
            score += 15
    return score

def dcc_learn_safe(text: str):
    """Fase 7: Aprende un patrón seguro del mensaje aprobado."""
    words = [w for w in text.lower().split() if len(w) > 4][:3]
    pattern = " ".join(words)
    if pattern and pattern not in data.get("dcc_learned_safe", []):
        data.setdefault("dcc_learned_safe", []).append(pattern)
        stats = data.setdefault("dcc_training_stats",
                    {"aprobados":0,"bloqueados":0,"revisados":0,"patrones_aprendidos":0})
        stats["aprobados"]           = stats.get("aprobados", 0) + 1
        stats["patrones_aprendidos"] = stats.get("patrones_aprendidos", 0) + 1
        save_data(data)

def dcc_learn_danger(text: str):
    """Fase 7: Aprende un patrón peligroso del mensaje marcado."""
    words = [w for w in text.lower().split() if len(w) > 3][:3]
    pattern = " ".join(words)
    if pattern and pattern not in data.get("dcc_learned_danger", []):
        data.setdefault("dcc_learned_danger", []).append(pattern)
        stats = data.setdefault("dcc_training_stats",
                    {"aprobados":0,"bloqueados":0,"revisados":0,"patrones_aprendidos":0})
        stats["bloqueados"]          = stats.get("bloqueados", 0) + 1
        stats["patrones_aprendidos"] = stats.get("patrones_aprendidos", 0) + 1
        save_data(data)

# ── Fase 9: Estadísticas de entrenamiento ──────────────
def dcc_stats_increment(key: str):
    stats = data.setdefault("dcc_training_stats",
                {"aprobados":0,"bloqueados":0,"revisados":0,"patrones_aprendidos":0})
    stats[key] = stats.get(key, 0) + 1
    save_data(data)

# ── Fase 10: Detección Pastoral ────────────────────────
PASTORAL_PATTERNS = [
    "quiero dejar", "necesito ayuda", "oren por mi", "oren por mí",
    "estoy luchando", "caí nuevamente", "cai nuevamente",
    "ayuda espiritual", "quiero cambiar", "necesito oración",
    "necesito oracion", "estoy mal", "me siento solo",
    "no puedo más", "no puedo mas", "necesito a dios",
    "quiero a dios", "quiero cambiar mi vida",
]

def is_pastoral_help(text: str) -> bool:
    """Fase 10: Detecta si el mensaje es una petición pastoral."""
    t = text.lower()
    return any(p in t for p in PASTORAL_PATTERNS)
    return data["warnings"].get(str(chat_id), {}).get(str(user_id), 0)

def add_warn(chat_id, user_id):
    cid, uid = str(chat_id), str(user_id)
    data["warnings"].setdefault(cid, {})[uid] = \
        data["warnings"].get(cid, {}).get(uid, 0) + 1
    save_data(data)
    return data["warnings"][cid][uid]

def reset_warn(chat_id, user_id):
    cid, uid = str(chat_id), str(user_id)
    if cid in data["warnings"]:
        data["warnings"][cid][uid] = 0
        save_data(data)

# ═══════════════════════════════════════════════════════
#  SANCIONES
# ═══════════════════════════════════════════════════════
async def sanction(msg, context, name, user_id, chat_id, count, reason):
    if count == 1:
        await msg.chat.send_message(
            f"⚠️ *{name}*, mensaje eliminado por: {reason}\n"
            f"_Llamado de atención (1/3). Por favor respeta el reglamento._ 🙏",
            parse_mode="Markdown")
    elif count == 2:
        await msg.chat.send_message(
            f"⚠️ *{name}*, segunda infracción por: {reason}\n"
            f"_Advertencia formal (2/3). Una más y serás restringido._ 🙏",
            parse_mode="Markdown")
    elif count == 3:
        until = datetime.datetime.now(datetime.timezone.utc) + \
                datetime.timedelta(hours=24)
        try:
            await context.bot.restrict_chat_member(
                chat_id, user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until)
        except Exception as e:
            logger.warning(f"Restringir: {e}")
        await msg.chat.send_message(
            f"🚫 *{name}* ha sido silenciado por 24 horas por: {reason}\n"
            f"_Restricción temporal (3/3)._ 🙏",
            parse_mode="Markdown")
    else:
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
        except Exception as e:
            logger.warning(f"Expulsar: {e}")
        await msg.chat.send_message(
            f"❌ *{name}* fue expulsado por reincidencia en: {reason}\n"
            f"_Que Dios guíe su camino._ 🙏✝️",
            parse_mode="Markdown")

def only_admin(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user and update.effective_user.id != ADMIN_ID:
            await update.message.reply_text(
                "⛔ Solo el administrador principal puede usar este comando.")
            return
        return await func(update, context)
    return wrapper

# ═══════════════════════════════════════════════════════
#  OWNER SECURITY LAYER V1
# ═══════════════════════════════════════════════════════
def owner_session_valid(context) -> bool:
    """Verifica si la sesión del propietario es válida y no ha expirado."""
    if not context.user_data.get("owner_session"):
        return False
    start = context.user_data.get("owner_session_start")
    if not start:
        return False
    timeout = data.get("owner_security", {}).get("session_timeout", 1800)
    if time.time() - start > timeout:
        context.user_data.pop("owner_session", None)
        context.user_data.pop("owner_session_start", None)
        return False
    return True

def is_owner(update, context) -> bool:
    """True solo si el usuario está en owners list y tiene sesión activa."""
    if not update.effective_user:
        return False
    owners = data.get("owner_security", {}).get("owners", [ADMIN_ID])
    return update.effective_user.id in owners and owner_session_valid(context)

def _open_owner_session(context):
    """Abre una sesión de propietario."""
    context.user_data["owner_session"] = True
    context.user_data["owner_session_start"] = time.time()

def _close_owner_session(context):
    """Cierra la sesión de propietario."""
    context.user_data.pop("owner_session", None)
    context.user_data.pop("owner_session_start", None)

async def _show_owner_panel(target, context):
    """Muestra el panel principal del propietario."""
    sec         = data.get("owner_security", {})
    timeout_min = sec.get("session_timeout", 1800) // 60
    n_owners    = len(sec.get("owners", [ADMIN_ID]))
    kb = [
        [InlineKeyboardButton("👋 Bienvenida Premium",  callback_data="wp_menu"),
         InlineKeyboardButton("📨 Centro de Mensajes",  callback_data="msg_center")],
        [InlineKeyboardButton("⏰ Programaciones",      callback_data="sched_menu"),
         InlineKeyboardButton("🌙 Horarios",            callback_data="schedule_menu")],
        [InlineKeyboardButton("🛡 Moderación",          callback_data="mod_menu"),
         InlineKeyboardButton("⚙️ Configuración",       callback_data="cfg_menu")],
        [InlineKeyboardButton("📚 Biblioteca",          callback_data="lib_soon"),
         InlineKeyboardButton("📊 Encuestas",           callback_data="enc_soon")],
        [InlineKeyboardButton("🔐 Seguridad",           callback_data="sec_menu")],
        [InlineKeyboardButton("🚪 Cerrar Sesión",       callback_data="owner_logout")],
    ]
    text = (
        f"👑 *Panel de Propietario — Fuera del Templo*\n\n"
        f"⏱ Sesión activa · Expira en {timeout_min} min\n"
        f"👥 Administradores autorizados: {n_owners}\n\n"
        f"Selecciona una sección:"
    )
    markup = InlineKeyboardMarkup(kb)
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await target.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════
#  REGISTRO AUTOMÁTICO AL SER HECHO ADMIN
# ═══════════════════════════════════════════════════════
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return
    new_s     = result.new_chat_member.status
    chat_id   = result.chat.id
    chat_name = result.chat.title or str(chat_id)

    if new_s == "administrator":
        cid = str(chat_id)
        if "registered_chats" not in data:
            data["registered_chats"] = []
        if cid not in data["registered_chats"]:
            data["registered_chats"].append(cid)
            save_data(data)
            logger.info(f"✅ Grupo registrado: {chat_name} ({chat_id})")
        try:
            await context.bot.send_message(
                chat_id,
                "✅ *¡Listo! Ya soy administrador de este grupo.*\n\n"
                "Desde ahora estaré moderando *Fuera del Templo* las 24 horas. 🛡️\n\n"
                "🚫 Anti-spam activo\n"
                "🔞 Anti-contenido adulto activo\n"
                "🌙 Modo Noche/Día automático activo\n"
                "📖 Bienvenidas y despedidas automáticas\n"
                "⚖️ Sistema de sanciones activo\n\n"
                "_Que Dios bendiga este espacio._ 🙏✝️",
                parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Mensaje activación: {e}")

    elif new_s in ("left", "kicked", "member"):
        cid = str(chat_id)
        if "registered_chats" in data and cid in data["registered_chats"]:
            data["registered_chats"].remove(cid)
            save_data(data)
            logger.info(f"❌ Grupo removido: {chat_name} ({chat_id})")

# ═══════════════════════════════════════════════════════
#  BIENVENIDA / DESPEDIDA
# ═══════════════════════════════════════════════════════
async def on_member_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return
    old_s   = result.old_chat_member.status
    new_s   = result.new_chat_member.status
    chat_id = result.chat.id
    user    = result.new_chat_member.user
    name    = user.first_name or user.username or str(user.id)

    if old_s in ("left", "kicked") and new_s == "member":
        wc = data.get("welcome_config", {})

        if wc.get("enabled") and wc.get("image_file_id") and wc.get("message_text"):
            # ── BIENVENIDA PREMIUM ──────────────────────────
            cid = str(chat_id)

            # Borrar mensajes anteriores si está configurado
            if wc.get("delete_previous", True):
                for key in ("last_welcome_image_id", "last_welcome_text_id", "last_rules_id"):
                    mid = data.get(key, {}).get(cid)
                    if mid:
                        try:
                            await context.bot.delete_message(chat_id, mid)
                        except Exception:
                            pass

            # Paso 1: imagen
            img_msg = await context.bot.send_photo(
                chat_id,
                photo=wc["image_file_id"])
            data.setdefault("last_welcome_image_id", {})[cid] = img_msg.message_id

            # Paso 2: mensaje personalizado
            text = wc["message_text"].replace("{nombre}", name)
            txt_msg = await context.bot.send_message(
                chat_id, text, parse_mode="Markdown")
            data.setdefault("last_welcome_text_id", {})[cid] = txt_msg.message_id

            # Paso 3: delay
            delay = wc.get("rules_delay", 2)
            if delay > 0:
                await asyncio.sleep(delay)

            # Paso 4: reglamento
            if wc.get("show_rules", True):
                r_msg = await context.bot.send_message(
                    chat_id, data["rules"], parse_mode="Markdown")
                data.setdefault("last_rules_id", {})[cid] = r_msg.message_id

            save_data(data)

        else:
            # ── BIENVENIDA SIMPLE (fallback) ────────────────
            for key in ("last_welcome_id", "last_rules_id"):
                mid = data.get(key, {}).get(str(chat_id))
                if mid:
                    try:
                        await context.bot.delete_message(chat_id, mid)
                    except Exception:
                        pass
            w = await context.bot.send_message(
                chat_id,
                data["welcome"].replace("{nombre}", name),
                parse_mode="Markdown")
            r = await context.bot.send_message(
                chat_id, data["rules"], parse_mode="Markdown")
            data["last_welcome_id"][str(chat_id)] = w.message_id
            data["last_rules_id"][str(chat_id)]   = r.message_id
            save_data(data)

    elif old_s == "member" and new_s in ("left", "kicked"):
        await context.bot.send_message(
            chat_id,
            data["farewell"].replace("{nombre}", name),
            parse_mode="Markdown")

# ═══════════════════════════════════════════════════════
#  MODERACIÓN TEXTO
# ═══════════════════════════════════════════════════════
async def moderate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text or not msg.from_user:
        return
    if msg.chat.type not in ("group", "supergroup"):
        return
    if context.user_data.get("pending_action"):
        return
    chat_id = msg.chat_id
    user    = msg.from_user
    user_id = user.id
    name    = user.first_name or user.username or "Miembro"
    text    = msg.text

    # Anti-spam
    if is_spamming(chat_id, user_id):
        try: await msg.delete()
        except Exception: pass
        await msg.chat.send_message(
            f"⚡ *{name}*, mensajes demasiado rápido. Espera unos segundos. 🙏",
            parse_mode="Markdown")
        return

    # Modo Noche — grupo cerrado completamente
    if data["night_mode_active"]:
        try: await msg.delete()
        except Exception: pass
        await msg.chat.send_message(
            f"🌙 *Grupo cerrado — Modo Noche.*\n\n"
            f"*{name}*, el grupo está en descanso. 😴\n"
            f"Se abrirá a las *{data['day_hour']}:00 AM*.\n\n"
            f"_Que el Señor te dé buen descanso._ 🙏✝️",
            parse_mode="Markdown")
        return

    # ── Detección de contenido — Capa 1 ───────────────
    has_link_flag    = has_link(text)
    has_bad_flag     = has_bad_word(text)
    has_adult_flag   = is_adult(text)

    # Links y lenguaje inapropiado: acción directa (sin DCC)
    if has_link_flag:
        try: await msg.delete()
        except Exception: pass
        count = add_warn(chat_id, user_id)
        await sanction(msg, context, name, user_id, chat_id, count,
                       "enlace no autorizado 🔗")
        return

    if has_bad_flag:
        try: await msg.delete()
        except Exception: pass
        count = add_warn(chat_id, user_id)
        await sanction(msg, context, name, user_id, chat_id, count,
                       "lenguaje inapropiado 🚫")
        return

    # ── DCC — Solo si is_adult() detecta contenido sensible ──
    if has_adult_flag:
        # Fase 10 — detección pastoral tiene prioridad absoluta
        if is_pastoral_help(text):
            if data.get("pastoral_response_enabled", True):
                pastoral_msg = data.get(
                    "pastoral_response_text",
                    "🙏 Estamos orando por ti. Dios puede ayudarte. No estás solo.")
                await msg.chat.send_message(pastoral_msg, parse_mode="Markdown")
            logger.info(f"DCC PASTORAL uid={user_id}")
            return

        # Fase 2 — analizar contexto
        ctx = analyze_context(text)

        # Fase 7 — score con memoria de patrones aprendidos
        score = dcc_score_with_memory(text)

        # Fase 8 — índice de confianza
        conf = calculate_confidence(score)

        # Fase 5 — clasificar
        verdict = dcc_classify(score)

        if verdict == "ALLOW":
            logger.info(f"DCC ALLOW uid={user_id} score={score} conf={conf['pct']}% ctx={ctx}")
            return

        if verdict == "REVIEW":
            # Fase 6 — guardar registro enriquecido
            username = user.username or user.first_name or str(user_id)
            motivo   = f"Score {score} | Contexto {ctx} | Confianza {conf['pct']}%"
            dcc_queue_add_v2(user_id, chat_id, username, name, text, score, verdict, motivo)
            # Fase 9 — estadística
            dcc_stats_increment("revisados")
            logger.info(f"DCC REVIEW uid={user_id} score={score} conf={conf['pct']}% ctx={ctx}")
            return

        # verdict == BLOCK
        logger.info(f"DCC BLOCK uid={user_id} score={score} conf={conf['pct']}% ctx={ctx}")
        # Fase 9 — estadística
        dcc_stats_increment("bloqueados")
        try: await msg.delete()
        except Exception: pass
        count = add_warn(chat_id, user_id)
        await sanction(msg, context, name, user_id, chat_id, count,
                       "contenido para adultos 🔞")

# ═══════════════════════════════════════════════════════
#  MODERACIÓN FOTOS Y VIDEOS
# ═══════════════════════════════════════════════════════
async def moderate_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    if msg.chat.type not in ("group", "supergroup"):
        return
    if context.user_data.get("pending_action"):
        return
    chat_id = msg.chat_id
    user    = msg.from_user
    user_id = user.id
    name    = user.first_name or user.username or "Miembro"
    caption = msg.caption or ""

    # Modo Noche
    if data["night_mode_active"]:
        try: await msg.delete()
        except Exception: pass
        return

    # Anti-spam
    if is_spamming(chat_id, user_id):
        try: await msg.delete()
        except Exception: pass
        await msg.chat.send_message(
            f"⚡ *{name}*, demasiados archivos seguidos. Espera unos segundos. 🙏",
            parse_mode="Markdown")
        return

    # Caption con contenido prohibido
    if is_adult(caption) or has_link(caption):
        try: await msg.delete()
        except Exception: pass
        count = add_warn(chat_id, user_id)
        await sanction(msg, context, name, user_id, chat_id, count,
                       "contenido no permitido 🔞")

# ═══════════════════════════════════════════════════════
#  MODERACIÓN STICKERS
# ═══════════════════════════════════════════════════════
async def moderate_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    if msg.chat.type not in ("group", "supergroup"):
        return
    if context.user_data.get("pending_action"):
        return
    name = msg.from_user.first_name or msg.from_user.username or "Miembro"

    if data["night_mode_active"]:
        try: await msg.delete()
        except Exception: pass
        return

    if is_spamming(msg.chat_id, msg.from_user.id):
        try: await msg.delete()
        except Exception: pass
        await msg.chat.send_message(
            f"⚡ *{name}*, demasiados stickers seguidos. 🙏",
            parse_mode="Markdown")

# ═══════════════════════════════════════════════════════
#  MODO NOCHE / DÍA AUTOMÁTICO
# ═══════════════════════════════════════════════════════
async def auto_night_check(context: ContextTypes.DEFAULT_TYPE):
    if not data.get("night_mode_auto", True):
        return

    now_h = datetime.datetime.now(BOGOTA_TZ).hour
    n = data["night_hour"]
    d = data["day_hour"]

    # Determinar si según la hora actual el grupo DEBERÍA estar cerrado
    if n > d:
        # Ejemplo: cierre 22, apertura 6 → noche = 22,23,0,1,2,3,4,5
        should_be_night = now_h >= n or now_h < d
    else:
        # Ejemplo: cierre 2, apertura 8 → noche = 2,3,4,5,6,7
        should_be_night = d > now_h >= n

    if should_be_night and not data["night_mode_active"]:
        data["night_mode_active"] = True
        save_data(data)
        logger.info("🌙 Modo noche activado automáticamente")
        for cid in data.get("registered_chats", []):
            try:
                await context.bot.send_message(
                    int(cid),
                    f"🌙 *El grupo entra en Modo Noche.*\n\n"
                    f"Es hora de descansar. 😴\n"
                    f"El grupo estará cerrado hasta las *{data['day_hour']}:00 AM*.\n\n"
                    f"_Que el Señor les dé un buen descanso a todos._ 🙏✝️",
                    parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Anuncio noche {cid}: {e}")

    elif not should_be_night and data["night_mode_active"]:
        data["night_mode_active"] = False
        save_data(data)
        logger.info("☀️ Modo día activado automáticamente")
        for cid in data.get("registered_chats", []):
            try:
                await context.bot.send_message(
                    int(cid),
                    f"☀️ *¡Buenos días! El grupo está abierto nuevamente.*\n\n"
                    f"_Que este nuevo día esté lleno de la presencia de Dios._ 🙏📖✝️",
                    parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Anuncio día {cid}: {e}")

# ═══════════════════════════════════════════════════════
#  FASE 3 — PROGRAMADOR DE MENSAJES
# ═══════════════════════════════════════════════════════

FREQ_LABELS = {
    "once":       "Una vez",
    "daily":      "Diario",
    "weekly":     "Semanal",
    "weekdays":   "Días laborables (L-V)",
    "weekends":   "Fines de semana (S-D)",
    "custom":     "Días personalizados",
}


# ═══════════════════════════════════════════════════════
#  ACTIVACIÓN DEL PANEL — PALABRA SECRETA
# ═══════════════════════════════════════════════════════
async def handle_secret_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Detecta la palabra secreta en chat privado.
    Verifica contra lista de owners. Ignora silenciosamente a no-autorizados.
    """
    msg = update.message
    if not msg or not msg.text or not msg.from_user:
        return
    # Fase 3 — solo chat privado
    if msg.chat.type != "private":
        return

    uid     = msg.from_user.id
    owners  = data.get("owner_security", {}).get("owners", [ADMIN_ID])
    keyword = data.get("owner_security", {}).get("secret_keyword", "DTB")
    text    = msg.text.strip()

    # Si el texto coincide con la keyword
    if text == keyword:
        if uid not in owners:
            # Ignorar silenciosamente — no revelar que la keyword existe
            return
        # Fase 1 — acceso autorizado
        _open_owner_session(context)
        await msg.reply_text(
            "👋 *Bienvenido jefe.*\n\n"
            "🔐 Acceso autorizado.\n\n"
            "Panel de control cargado correctamente.",
            parse_mode="Markdown")
        await _show_owner_panel(msg, context)
        return

    # Si es un owner pero la keyword es incorrecta — denegar sin revelar nada
    # (no responder a no-owners en ningún caso)

def _schedule_menu_kb():
    auto = data.get("night_mode_auto", True)
    estado = "✅ Activado" if auto else "❌ Desactivado"
    grupo  = "🌙 CERRADO" if data["night_mode_active"] else "☀️ ABIERTO"
    text = (
        f"🌙 *Horario Automático*\n\n"
        f"Estado: *{estado}*\n"
        f"Grupo ahora: *{grupo}*\n"
        f"🌙 Hora de cierre: *{data['night_hour']}:00*\n"
        f"☀️ Hora de apertura: *{data['day_hour']}:00*\n"
        f"🌎 Zona horaria: *America/Bogota*"
    )
    kb = [
        [InlineKeyboardButton("✏️ Cambiar hora de cierre",   callback_data="set_night_hour"),
         InlineKeyboardButton("✏️ Cambiar hora de apertura", callback_data="set_day_hour")],
        [InlineKeyboardButton("✅ Activar horario automático",   callback_data="auto_on")],
        [InlineKeyboardButton("❌ Desactivar horario automático", callback_data="auto_off")],
        [InlineKeyboardButton("⬅️ Volver",                      callback_data="back_panel")],
    ]
    return text, InlineKeyboardMarkup(kb)

DAYS_ES = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]

async def _show_day_picker(q, context):
    dias = context.user_data.get("sched_dias", [])
    kb = []
    for day in DAYS_ES:
        mark = "✅" if day in dias else "⬜"
        kb.append([InlineKeyboardButton(f"{mark} {day.capitalize()}", callback_data=f"sched_day_{day}")])
    kb.append([InlineKeyboardButton("✔️ Confirmar días", callback_data="sched_days_confirm")])
    kb.append([InlineKeyboardButton("⬅️ Volver",         callback_data="sched_create")])
    await q.edit_message_text(
        "⏰ *Crear Programación*\n\nPaso 3: Selecciona los días de envío:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown")

MSG_PAGE_SIZE = 8

def _msg_center_kb():
    kb = [
        [InlineKeyboardButton("➕ Crear mensaje",   callback_data="msg_create")],
        [InlineKeyboardButton("📋 Ver mensajes",    callback_data="msg_list_0")],
        [InlineKeyboardButton("✏️ Editar mensaje",  callback_data="msg_edit_list")],
        [InlineKeyboardButton("🗑 Eliminar mensaje", callback_data="msg_del_list")],
        [InlineKeyboardButton("⬅️ Volver",          callback_data="back_panel")],
    ]
    total = len(data.get("custom_messages", []))
    return f"📨 *CENTRO DE MENSAJES*\n\nMensajes guardados: *{total}*\n\nSelecciona una opción:", InlineKeyboardMarkup(kb)

async def _show_msg_center(q):
    text, kb = _msg_center_kb()
    await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

def _paginated_msg_kb(page: int, action_prefix: str, back_cb: str):
    """Genera teclado paginado de mensajes. action_prefix se antepone al id."""
    msgs = data.get("custom_messages", [])
    total = len(msgs)
    start = page * MSG_PAGE_SIZE
    end   = min(start + MSG_PAGE_SIZE, total)
    kb = []
    for m in msgs[start:end]:
        cat = CAT_LABELS.get(m.get("categoria","general"), "📁")
        kb.append([InlineKeyboardButton(
            f"{cat} {m['nombre']} ({m['tipo']})",
            callback_data=f"{action_prefix}{m['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"msg_page_{action_prefix}_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"msg_page_{action_prefix}_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Volver", callback_data=back_cb)])
    return kb, total, page

async def _save_new_message(q, context):
    """Paso 5: guarda el mensaje nuevo con todos los campos."""
    captured  = context.user_data.pop("cm_captured", {})
    nombre    = context.user_data.pop("cm_nombre", "Sin nombre")
    categoria = context.user_data.pop("cm_categoria", "general")
    context.user_data.pop("cm_tipo", None)

    tipo = captured.get("tipo", "text")
    if tipo not in VALID_TYPES:
        await q.edit_message_text("⚠️ Tipo no válido. Intenta de nuevo desde el panel.")
        return

    new_id = f"msg_{int(time.time())}"
    entry = {
        "id":        new_id,
        "nombre":    nombre,
        "tipo":      tipo,
        "contenido": captured.get("contenido", ""),
        "caption":   captured.get("caption"),
        "categoria": categoria,
        "tags":      [],
        "creado":    datetime.datetime.now(BOGOTA_TZ).strftime("%Y-%m-%dT%H:%M:%S"),
        "autor_id":  ADMIN_ID,
    }
    data.setdefault("custom_messages", []).append(entry)
    save_data(data)

    cat_label = CAT_LABELS.get(categoria, categoria)
    tipo_label = TYPE_LABELS.get(tipo, tipo)
    text, kb = _msg_center_kb()
    await q.edit_message_text(
        f"✅ *Mensaje guardado correctamente.*\n\n"
        f"📄 Nombre: *{nombre}*\n"
        f"🔖 Tipo: {tipo_label}\n"
        f"📂 Categoría: {cat_label}\n\n"
        f"ID: `{new_id}`",
        reply_markup=kb,
        parse_mode="Markdown")

def _wp_status_text():
    """Genera el texto de estado de Bienvenida Premium."""
    wc = data.get("welcome_config", {})
    enabled   = "✅ Activo"      if wc.get("enabled")        else "❌ Inactivo"
    image     = "✅ Configurada" if wc.get("image_file_id")  else "❌ No configurada"
    message   = "✅ Configurado" if wc.get("message_text")   else "❌ No configurado"
    rules     = "✅ Activadas"   if wc.get("show_rules", True) else "❌ Desactivadas"
    delay     = wc.get("rules_delay", 2)
    return (
        f"👋 *BIENVENIDA PREMIUM*\n\n"
        f"Sistema: {enabled}\n"
        f"Imagen: {image}\n"
        f"Mensaje: {message}\n"
        f"Reglas: {rules}\n"
        f"Delay: {delay} segundo(s)"
    )

def _wp_menu_kb():
    wc = data.get("welcome_config", {})
    rules_label = "📖 Desactivar Reglas" if wc.get("show_rules", True) else "📖 Activar Reglas"
    sys_label   = "❌ Desactivar Sistema" if wc.get("enabled") else "✅ Activar Sistema"
    sys_cb      = "wp_disable" if wc.get("enabled") else "wp_enable"
    kb = [
        [InlineKeyboardButton("🖼 Configurar Imagen",   callback_data="wp_set_image")],
        [InlineKeyboardButton("📝 Configurar Mensaje",  callback_data="wp_set_message")],
        [InlineKeyboardButton(rules_label,              callback_data="wp_toggle_rules")],
        [InlineKeyboardButton("⚙️ Estado",              callback_data="wp_status")],
        [InlineKeyboardButton(sys_label,                callback_data=sys_cb)],
        [InlineKeyboardButton("⬅️ Volver",              callback_data="back_panel")],
    ]
    return InlineKeyboardMarkup(kb)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    a = q.data

    # ── Módulo 10 — Solo chat privado ─────────────────
    if q.message and q.message.chat.type != "private":
        await q.answer(
            "⛔ Este panel solo está disponible en privado.",
            show_alert=True)
        return

    # ── Cierre de sesión (no requiere sesión activa) ───
    if a == "owner_logout":
        _close_owner_session(context)
        await q.edit_message_text(
            "🔒 *Sesión cerrada correctamente.*\n\n"
            "Para volver a ingresar utiliza tu palabra secreta.",
            parse_mode="Markdown")
        return

    # ── Protección: toda acción admin requiere sesión ──
    if not is_owner(update, context):
        await q.edit_message_text(
            "⛔ *Acceso denegado.*\n\n"
            "Tu sesión ha expirado o no tienes permisos.\n"
            "Envía la palabra secreta para acceder nuevamente.",
            parse_mode="Markdown")
        return

    # ── Volver al panel principal ──────────────────────
    if a == "back_panel":
        await _show_owner_panel(q, context)
        return

    # ── Próximamente ──────────────────────────────────
    if a in ("lib_soon", "enc_soon"):
        label = "📚 Biblioteca" if a == "lib_soon" else "📊 Encuestas"
        await q.edit_message_text(
            f"{label}\n\n🚧 *Próximamente*\n\nEste módulo estará disponible en una próxima fase.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver", callback_data="back_panel")
            ]]),
            parse_mode="Markdown")
        return

    # ── Moderación ────────────────────────────────────
    if a == "mod_menu":
        kb = [
            [InlineKeyboardButton("➕ Agregar Palabra",  callback_data="add_bad"),
             InlineKeyboardButton("🗑 Quitar Palabra",   callback_data="del_bad")],
            [InlineKeyboardButton("📋 Ver Palabras",     callback_data="list_bad"),
             InlineKeyboardButton("🔞 Ver Dominios",     callback_data="list_adult")],
            [InlineKeyboardButton("➕ Agregar Dominio",  callback_data="add_adult"),
             InlineKeyboardButton("🗑 Quitar Dominio",   callback_data="del_adult")],
            [InlineKeyboardButton("✏️ Bienvenida",       callback_data="edit_welcome"),
             InlineKeyboardButton("✏️ Despedida",        callback_data="edit_farewell")],
            [InlineKeyboardButton("⬅️ Volver",           callback_data="back_panel")],
        ]
        await q.edit_message_text(
            "🛡 *Moderación*\n\nSelecciona una opción:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    # ── Configuración general ─────────────────────────
    if a == "cfg_menu":
        await q.edit_message_text(
            "⚙️ *Configuración*\n\nSelecciona una opción:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Estado del Bot", callback_data="status")],
                [InlineKeyboardButton("⬅️ Volver",        callback_data="back_panel")],
            ]),
            parse_mode="Markdown")
        return

    # ── Seguridad ─────────────────────────────────────
    if a == "sec_menu":
        sec         = data.get("owner_security", {})
        timeout_min = sec.get("session_timeout", 1800) // 60
        n_owners    = len(sec.get("owners", [ADMIN_ID]))
        session_ok  = "✅ Activa" if owner_session_valid(context) else "❌ Inactiva"
        kb = [
            [InlineKeyboardButton("🔑 Cambiar Palabra Secreta",  callback_data="sec_change_keyword")],
            [InlineKeyboardButton("⏱ Cambiar Tiempo de Sesión",  callback_data="sec_change_timeout")],
            [InlineKeyboardButton("👥 Administradores",           callback_data="sec_admins")],
            [InlineKeyboardButton("🧠 DCC Review",               callback_data="dcc_menu")],
            [InlineKeyboardButton("📊 Estado",                    callback_data="sec_status")],
            [InlineKeyboardButton("⬅️ Volver",                    callback_data="back_panel")],
        ]
        await q.edit_message_text(
            f"🔐 *Seguridad del Propietario*\n\n"
            f"Estado: ✅ Activa\n"
            f"Sesión actual: {session_ok}\n"
            f"Tiempo de sesión: {timeout_min} minutos\n"
            f"Administradores autorizados: {n_owners}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    if a == "sec_status":
        sec         = data.get("owner_security", {})
        timeout_sec = sec.get("session_timeout", 1800)
        timeout_min = timeout_sec // 60
        n_owners    = len(sec.get("owners", [ADMIN_ID]))
        # Calculate remaining time
        session_active = owner_session_valid(context)
        if session_active:
            start     = context.user_data.get("owner_session_start", time.time())
            elapsed   = time.time() - start
            remaining = max(0, timeout_sec - elapsed)
            rem_min   = int(remaining // 60)
            rem_sec   = int(remaining % 60)
            session_line = f"✅ Activa — {rem_min}m {rem_sec}s restantes"
        else:
            session_line = "❌ Inactiva"
        owners_list = "\n".join(
            f"• `{uid}`{'  _(principal)_' if uid == ADMIN_ID else ''}"
            for uid in sec.get("owners", [ADMIN_ID])
        )
        await q.edit_message_text(
            f"🔐 *Estado de Seguridad*\n\n"
            f"Protección: ✅ Activa\n\n"
            f"Sesión actual: {session_line}\n"
            f"Tiempo máximo: {timeout_min} minutos\n"
            f"Palabra configurada: ✅\n\n"
            f"Administradores: {n_owners}\n"
            f"Propietario principal: `{ADMIN_ID}`\n\n"
            f"*IDs autorizados:*\n{owners_list}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver", callback_data="sec_menu")
            ]]),
            parse_mode="Markdown")
        return

    if a == "sec_change_keyword":
        context.user_data["pending_action"] = "sec_keyword"
        await q.edit_message_text(
            "🔑 *Cambiar Palabra Secreta*\n\n"
            "Escribe la nueva palabra secreta:\n"
            "_(mínimo 3 caracteres, máximo 50)_",
            parse_mode="Markdown")
        return

    if a == "sec_change_timeout":
        current = data.get("owner_security", {}).get("session_timeout", 1800) // 60
        kb = [
            [InlineKeyboardButton("15 minutos",  callback_data="sec_t_15"),
             InlineKeyboardButton("30 minutos",  callback_data="sec_t_30")],
            [InlineKeyboardButton("60 minutos",  callback_data="sec_t_60"),
             InlineKeyboardButton("120 minutos", callback_data="sec_t_120")],
            [InlineKeyboardButton("⬅️ Volver",   callback_data="sec_menu")],
        ]
        await q.edit_message_text(
            f"⏱ *Cambiar Tiempo de Sesión*\n\n"
            f"Tiempo actual: *{current} minutos*\n\n"
            f"Selecciona la nueva duración:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    if a.startswith("sec_t_"):
        minutes = int(a[len("sec_t_"):])
        data.setdefault("owner_security", {})["session_timeout"] = minutes * 60
        save_data(data)
        await q.edit_message_text(
            f"✅ Tiempo de sesión actualizado: *{minutes} minutos*.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver", callback_data="sec_menu")
            ]]),
            parse_mode="Markdown")
        return

    # ── Administradores ───────────────────────────────
    if a == "sec_admins":
        owners = data.get("owner_security", {}).get("owners", [ADMIN_ID])
        lines  = [f"• `{uid}`{'  _(propietario principal)_' if uid == ADMIN_ID else ''}"
                  for uid in owners]
        kb = [
            [InlineKeyboardButton("➕ Agregar",  callback_data="sec_add_admin"),
             InlineKeyboardButton("➖ Eliminar", callback_data="sec_remove_list")],
            [InlineKeyboardButton("⬅️ Volver",   callback_data="sec_menu")],
        ]
        await q.edit_message_text(
            f"👥 *Administradores autorizados*\n\n"
            f"Total: {len(owners)}\n\n"
            f"Propietario principal: `{ADMIN_ID}`\n\n" +
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    if a == "sec_add_admin":
        context.user_data["pending_action"] = "sec_add_admin_id"
        await q.edit_message_text(
            "➕ *Agregar Administrador*\n\n"
            "Escribe el *ID de Telegram* del nuevo administrador:\n"
            "_(solo números)_",
            parse_mode="Markdown")
        return

    if a == "sec_remove_list":
        owners = data.get("owner_security", {}).get("owners", [ADMIN_ID])
        removable = [uid for uid in owners if uid != ADMIN_ID]
        if not removable:
            await q.edit_message_text(
                "ℹ️ No hay administradores adicionales para eliminar.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="sec_admins")
                ]]))
            return
        kb = [[InlineKeyboardButton(f"🗑 {uid}", callback_data=f"sec_del_admin_{uid}")]
              for uid in removable]
        kb.append([InlineKeyboardButton("⬅️ Volver", callback_data="sec_admins")])
        await q.edit_message_text(
            "➖ *Selecciona el administrador a eliminar:*",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    if a.startswith("sec_del_admin_"):
        uid_str = a[len("sec_del_admin_"):]
        try:
            uid_int = int(uid_str)
        except ValueError:
            return
        # Fase 14 — protección del propietario principal
        if uid_int == ADMIN_ID:
            await q.edit_message_text(
                "⛔ *No se puede eliminar al propietario principal.*",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="sec_admins")
                ]]),
                parse_mode="Markdown")
            return
        # Confirmación
        context.user_data["sec_del_uid"] = uid_int
        await q.edit_message_text(
            f"⚠️ ¿Deseas eliminar al administrador `{uid_int}`?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Sí", callback_data="sec_del_confirm"),
                 InlineKeyboardButton("❌ No",  callback_data="sec_admins")],
            ]),
            parse_mode="Markdown")
        return

    if a == "sec_del_confirm":
        uid_int = context.user_data.pop("sec_del_uid", None)
        if uid_int and uid_int != ADMIN_ID:
            owners = data.get("owner_security", {}).get("owners", [])
            if uid_int in owners:
                owners.remove(uid_int)
                save_data(data)
                await q.edit_message_text(
                    f"✅ Administrador `{uid_int}` eliminado correctamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Volver", callback_data="sec_admins")
                    ]]),
                    parse_mode="Markdown")
                return
        await q.edit_message_text(
            "⚠️ No se pudo eliminar.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver", callback_data="sec_admins")
            ]]))
        return

    # ── DCC Review Panel (Fase 6) ──────────────────────
    if a == "dcc_menu":
        queue  = data.get("dcc_review_queue", [])
        stats  = data.get("dcc_training_stats", {})
        safe_p = len(data.get("dcc_learned_safe", []))
        dng_p  = len(data.get("dcc_learned_danger", []))
        kb = [
            [InlineKeyboardButton("📋 Ver Cola",          callback_data="dcc_list_0")],
            [InlineKeyboardButton("🧹 Vaciar Cola",       callback_data="dcc_clear")],
            [InlineKeyboardButton("📊 Estadísticas",      callback_data="dcc_stats")],
            [InlineKeyboardButton("⬅️ Volver",            callback_data="sec_menu")],
        ]
        await q.edit_message_text(
            f"🧠 *DCC Review — Discernimiento Contextual*\n\n"
            f"📋 En cola: *{len(queue)}* mensajes\n"
            f"🟢 Patrones seguros aprendidos: *{safe_p}*\n"
            f"🔴 Patrones peligrosos aprendidos: *{dng_p}*\n"
            f"✅ Aprobados: {stats.get('aprobados', 0)}\n"
            f"🚫 Bloqueados: {stats.get('bloqueados', 0)}\n"
            f"🔍 Revisados: {stats.get('revisados', 0)}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    if a.startswith("dcc_list_"):
        page  = int(a[len("dcc_list_"):])
        queue = data.get("dcc_review_queue", [])
        if not queue:
            await q.edit_message_text(
                "📋 *Cola DCC vacía.*\n\nNo hay mensajes pendientes de revisión.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="dcc_menu")
                ]]),
                parse_mode="Markdown")
            return
        PAGE = 5
        total = len(queue)
        start = page * PAGE
        end   = min(start + PAGE, total)
        kb = []
        for item in queue[start:end]:
            conf  = item.get("confianza", {})
            emoji = conf.get("emoji", "⚪") if isinstance(conf, dict) else "⚪"
            label = f"{emoji} {item.get('nombre','?')} | score:{item.get('score',0)}"
            kb.append([InlineKeyboardButton(label, callback_data=f"dcc_view_{item['id']}")])
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️", callback_data=f"dcc_list_{page-1}"))
        if end < total:
            nav.append(InlineKeyboardButton("▶️", callback_data=f"dcc_list_{page+1}"))
        if nav:
            kb.append(nav)
        kb.append([InlineKeyboardButton("⬅️ Volver", callback_data="dcc_menu")])
        await q.edit_message_text(
            f"📋 *Cola DCC* ({start+1}-{end} de {total}):",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    if a.startswith("dcc_view_"):
        rid   = a[len("dcc_view_"):]
        queue = data.get("dcc_review_queue", [])
        item  = next((x for x in queue if x.get("id") == rid), None)
        if not item:
            await q.edit_message_text("⚠️ Registro no encontrado.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="dcc_list_0")
                ]]))
            return
        conf     = item.get("confianza", {})
        pct      = conf.get("pct", 0) if isinstance(conf, dict) else 0
        emoji    = conf.get("emoji", "⚪") if isinstance(conf, dict) else "⚪"
        lbl      = conf.get("label", "?") if isinstance(conf, dict) else "?"
        context.user_data["dcc_reviewing"] = rid
        kb = [
            [InlineKeyboardButton("✅ Aprobar",         callback_data="dcc_approve"),
             InlineKeyboardButton("🚫 Marcar Peligroso", callback_data="dcc_danger")],
            [InlineKeyboardButton("🗑 Eliminar Registro", callback_data="dcc_delete")],
            [InlineKeyboardButton("⬅️ Volver",           callback_data="dcc_list_0")],
        ]
        msg_preview = item.get("mensaje", "")[:200]
        await q.edit_message_text(
            f"🔍 *Revisión DCC*\n\n"
            f"👤 {item.get('nombre','?')} (@{item.get('username','?')})\n"
            f"📅 {item.get('fecha','?')}\n"
            f"📊 Score: `{item.get('score',0)}` | {emoji} {lbl} ({pct}%)\n"
            f"🏷 Motivo: _{item.get('motivo','?')}_\n\n"
            f"💬 *Mensaje:*\n_{msg_preview}_",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    if a == "dcc_approve":
        rid   = context.user_data.pop("dcc_reviewing", None)
        queue = data.get("dcc_review_queue", [])
        item  = next((x for x in queue if x.get("id") == rid), None)
        if item:
            # Fase 7 — aprender patrón seguro
            dcc_learn_safe(item.get("mensaje", ""))
            # Fase 9 — estadística (ya incluida en dcc_learn_safe)
            # Remover de cola
            data["dcc_review_queue"] = [x for x in queue if x.get("id") != rid]
            save_data(data)
            await q.edit_message_text(
                "✅ *Mensaje aprobado.*\n\nPatrón seguro aprendido correctamente.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="dcc_list_0")
                ]]),
                parse_mode="Markdown")
        return

    if a == "dcc_danger":
        rid   = context.user_data.pop("dcc_reviewing", None)
        queue = data.get("dcc_review_queue", [])
        item  = next((x for x in queue if x.get("id") == rid), None)
        if item:
            # Fase 7 — aprender patrón peligroso
            dcc_learn_danger(item.get("mensaje", ""))
            # Fase 9 — estadística (ya incluida en dcc_learn_danger)
            data["dcc_review_queue"] = [x for x in queue if x.get("id") != rid]
            save_data(data)
            await q.edit_message_text(
                "🚫 *Mensaje marcado como peligroso.*\n\nPatrón peligroso aprendido.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="dcc_list_0")
                ]]),
                parse_mode="Markdown")
        return

    if a == "dcc_delete":
        rid   = context.user_data.pop("dcc_reviewing", None)
        queue = data.get("dcc_review_queue", [])
        data["dcc_review_queue"] = [x for x in queue if x.get("id") != rid]
        save_data(data)
        await q.edit_message_text(
            "🗑 *Registro eliminado.*",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver", callback_data="dcc_list_0")
            ]]),
            parse_mode="Markdown")
        return

    if a == "dcc_clear":
        data["dcc_review_queue"] = []
        save_data(data)
        await q.edit_message_text(
            "🧹 *Cola DCC vaciada correctamente.*",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver", callback_data="dcc_menu")
            ]]),
            parse_mode="Markdown")
        return

    if a == "dcc_stats":
        stats  = data.get("dcc_training_stats", {})
        safe_p = len(data.get("dcc_learned_safe", []))
        dng_p  = len(data.get("dcc_learned_danger", []))
        await q.edit_message_text(
            f"📊 *Estadísticas DCC V2*\n\n"
            f"✅ Mensajes aprobados: {stats.get('aprobados', 0)}\n"
            f"🚫 Mensajes bloqueados: {stats.get('bloqueados', 0)}\n"
            f"🔍 Mensajes revisados: {stats.get('revisados', 0)}\n"
            f"🧠 Patrones aprendidos: {stats.get('patrones_aprendidos', 0)}\n\n"
            f"🟢 Patrones seguros: {safe_p}\n"
            f"🔴 Patrones peligrosos: {dng_p}\n\n"
            f"Umbrales actuales:\n"
            f"ALLOW ≤ {DCC_ALLOW_SCORE} | BLOCK ≥ {DCC_BLOCK_SCORE}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver", callback_data="dcc_menu")
            ]]),
            parse_mode="Markdown")
        return

    # ── Módulo de horario ──────────────────────────────
    if a == "schedule_menu":
        text, kb = _schedule_menu_kb()
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if a == "auto_on":
        data["night_mode_auto"] = True
        save_data(data)
        text, kb = _schedule_menu_kb()
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if a == "auto_off":
        data["night_mode_auto"] = False
        save_data(data)
        text, kb = _schedule_menu_kb()
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if a == "set_night_hour":
        context.user_data["pending_action"] = "set_night_hour"
        await q.edit_message_text(
            "✏️ Escribe la *hora de cierre* (0-23):\n\nEjemplo: `22` (10:00 PM)",
            parse_mode="Markdown")
        return

    if a == "set_day_hour":
        context.user_data["pending_action"] = "set_day_hour"
        await q.edit_message_text(
            "✏️ Escribe la *hora de apertura* (0-23):\n\nEjemplo: `6` (6:00 AM)",
            parse_mode="Markdown")
        return

    # ── Panel principal ────────────────────────────────
    if a == "status":
        night  = "🌙 CERRADO" if data["night_mode_active"] else "☀️ ABIERTO"
        grupos = len(data.get("registered_chats", []))
        auto   = "✅ Activado" if data.get("night_mode_auto", True) else "❌ Desactivado"
        msgs   = len(data.get("custom_messages", []))
        wp_on  = "✅ Activo" if data.get("welcome_config", {}).get("enabled") else "❌ Inactivo"
        await q.edit_message_text(
            f"📊 *Estado del Bot*\n\n"
            f"🔘 Grupo: {night}\n"
            f"🌙 Horario automático: {auto}\n"
            f"⏰ Cierre: {data['night_hour']}:00 — Apertura: {data['day_hour']}:00\n"
            f"🌎 Zona: America/Bogota\n"
            f"🏠 Grupos registrados: {grupos}\n"
            f"🚫 Palabras prohibidas: {len(data['bad_words'])}\n"
            f"🔞 Dominios bloqueados: {len(data['adult_domains'])}\n"
            f"⚡ Anti-spam: +{SPAM_LIMIT} msgs en {SPAM_WINDOW}s\n"
            f"📨 Mensajes guardados: {msgs}\n"
            f"👋 Bienvenida Premium: {wp_on}",
            parse_mode="Markdown")

    # ── Bienvenida Premium ─────────────────────────────
    elif a == "wp_menu":
        await q.edit_message_text(
            _wp_status_text(),
            reply_markup=_wp_menu_kb(),
            parse_mode="Markdown")

    elif a == "wp_status":
        await q.edit_message_text(
            _wp_status_text(),
            reply_markup=_wp_menu_kb(),
            parse_mode="Markdown")

    elif a == "wp_set_image":
        context.user_data["pending_action"] = "wp_capture_image"
        await q.edit_message_text(
            "🖼 *Configurar Imagen de Bienvenida*\n\n"
            "📤 Envía la imagen que deseas utilizar como bienvenida premium.",
            parse_mode="Markdown")

    elif a == "wp_set_message":
        context.user_data["pending_action"] = "wp_capture_message"
        await q.edit_message_text(
            "📝 *Configurar Mensaje de Bienvenida*\n\n"
            "✍️ Envía el mensaje de bienvenida.\n\n"
            "Puedes utilizar `{nombre}` para insertar el nombre del nuevo miembro.\n\n"
            "_Ejemplo:_\n"
            "👋 _{nombre}_\n\n"
            "🙏 Es una alegría tenerte con nosotros.\n"
            "📖 Que encuentres aquí amistad, apoyo y crecimiento espiritual.\n"
            "✨ Que Dios bendiga tu vida. DTB ✝️",
            parse_mode="Markdown")

    elif a == "wp_toggle_rules":
        wc = data.setdefault("welcome_config", {})
        wc["show_rules"] = not wc.get("show_rules", True)
        save_data(data)
        await q.edit_message_text(
            _wp_status_text(),
            reply_markup=_wp_menu_kb(),
            parse_mode="Markdown")

    elif a == "wp_enable":
        wc = data.get("welcome_config", {})
        if not wc.get("image_file_id") or not wc.get("message_text"):
            await q.answer(
                "⚠️ Debes configurar una imagen y un mensaje antes de activar.",
                show_alert=True)
        else:
            wc["enabled"] = True
            save_data(data)
            await q.edit_message_text(
                _wp_status_text(),
                reply_markup=_wp_menu_kb(),
                parse_mode="Markdown")

    elif a == "wp_disable":
        data.setdefault("welcome_config", {})["enabled"] = False
        save_data(data)
        await q.edit_message_text(
            _wp_status_text(),
            reply_markup=_wp_menu_kb(),
            parse_mode="Markdown")

    elif a == "list_bad":
        words = "\n".join(f"• {w}" for w in sorted(data["bad_words"])) or "_Lista vacía_"
        await q.edit_message_text(
            f"🚫 *Palabras Prohibidas:*\n\n{words}", parse_mode="Markdown")

    elif a == "list_adult":
        doms = "\n".join(f"• {d}" for d in sorted(data["adult_domains"]))
        await q.edit_message_text(
            f"🔞 *Dominios Bloqueados:*\n\n{doms}", parse_mode="Markdown")

    elif a == "msg_center":
        await _show_msg_center(q)

    # ── Crear mensaje — Paso 1: nombre ─────────────────
    elif a == "msg_create":
        context.user_data["pending_action"] = "msg_nombre"
        context.user_data.pop("cm_captured", None)
        context.user_data.pop("cm_nombre", None)
        context.user_data.pop("cm_tipo", None)
        context.user_data.pop("cm_categoria", None)
        await q.edit_message_text(
            "📨 *Crear mensaje — Paso 1 de 5*\n\n"
            "📝 Escribe un *nombre* para identificar este mensaje:",
            parse_mode="Markdown")

    # ── Crear mensaje — Paso 2: tipo (botones) ─────────
    elif a == "msg_type_select":
        kb = [[InlineKeyboardButton(label, callback_data=f"msg_type_{t}")]
              for t, label in TYPE_LABELS.items()]
        kb.append([InlineKeyboardButton("⬅️ Volver", callback_data="msg_create")])
        await q.edit_message_text(
            "📨 *Crear mensaje — Paso 2 de 5*\n\n"
            "Selecciona el *tipo de contenido*:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")

    elif a.startswith("msg_type_"):
        tipo = a[len("msg_type_"):]
        if tipo not in VALID_TYPES:
            await q.answer("⚠️ Tipo no válido.", show_alert=True)
            return
        context.user_data["cm_tipo"] = tipo
        context.user_data["pending_action"] = "msg_capture"
        if tipo == "text":
            await q.edit_message_text(
                "📨 *Crear mensaje — Paso 3 de 5*\n\n"
                "📝 Escribe el *texto* del mensaje:",
                parse_mode="Markdown")
        else:
            label = TYPE_LABELS[tipo]
            await q.edit_message_text(
                f"📨 *Crear mensaje — Paso 3 de 5*\n\n"
                f"Envía el archivo de tipo *{label}* al chat:",
                parse_mode="Markdown")

    # ── Crear mensaje — Paso 4: categoría (botones) ────
    elif a == "msg_cat_select":
        kb = [[InlineKeyboardButton(label, callback_data=f"msg_cat_{c}")]
              for c, label in CAT_LABELS.items()]
        await q.edit_message_text(
            "📨 *Crear mensaje — Paso 4 de 5*\n\n"
            "Selecciona la *categoría*:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")

    elif a.startswith("msg_cat_"):
        cat = a[len("msg_cat_"):]
        if cat not in VALID_CATEGORIES:
            await q.answer("⚠️ Categoría no válida.", show_alert=True)
            return
        context.user_data["cm_categoria"] = cat
        # Paso 5: guardar
        await _save_new_message(q, context)

    # ── Ver mensajes paginado ───────────────────────────
    elif a.startswith("msg_list_"):
        page = int(a[len("msg_list_"):])
        msgs = data.get("custom_messages", [])
        if not msgs:
            await q.edit_message_text(
                "📋 No hay mensajes guardados.\n\nUsa ➕ Crear mensaje para agregar uno.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="msg_center")
                ]]))
        else:
            kb, total, pg = _paginated_msg_kb(page, "msg_info_", "msg_center")
            start = page * MSG_PAGE_SIZE + 1
            end   = min((page + 1) * MSG_PAGE_SIZE, total)
            await q.edit_message_text(
                f"📋 *Mensajes guardados* ({start}-{end} de {total}):",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown")

    elif a.startswith("msg_info_"):
        mid = a[len("msg_info_"):]
        m = next((x for x in data.get("custom_messages", []) if x["id"] == mid), None)
        if m:
            cat   = CAT_LABELS.get(m.get("categoria","general"), "📁 General")
            tipo  = TYPE_LABELS.get(m.get("tipo","text"), m.get("tipo",""))
            cap   = f"\n📝 _Caption:_ {m['caption']}" if m.get("caption") else ""
            tags  = ", ".join(m.get("tags", [])) or "—"
            await q.edit_message_text(
                f"📄 *{m['nombre']}*\n\n"
                f"🔖 Tipo: {tipo}\n"
                f"📂 Categoría: {cat}\n"
                f"🏷 Tags: {tags}{cap}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="msg_list_0")
                ]]),
                parse_mode="Markdown")

    # ── Editar mensaje ──────────────────────────────────
    elif a == "msg_edit_list":
        msgs = data.get("custom_messages", [])
        if not msgs:
            await q.edit_message_text(
                "✏️ No hay mensajes para editar.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="msg_center")
                ]]))
        else:
            kb, total, _ = _paginated_msg_kb(0, "msg_edit_", "msg_center")
            await q.edit_message_text(
                "✏️ *Selecciona el mensaje a editar:*",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown")

    elif a.startswith("msg_edit_") and not a.startswith("msg_edit_list"):
        mid = a[len("msg_edit_"):]
        m = next((x for x in data.get("custom_messages", []) if x["id"] == mid), None)
        if m:
            context.user_data["cm_edit_id"] = mid
            kb = [
                [InlineKeyboardButton("✏️ Cambiar nombre",    callback_data="msg_edit_field_nombre")],
                [InlineKeyboardButton("✏️ Cambiar categoría", callback_data="msg_edit_field_categoria")],
                [InlineKeyboardButton("✏️ Cambiar contenido", callback_data="msg_edit_field_contenido")],
                [InlineKeyboardButton("🏷 Editar tags",       callback_data="msg_edit_field_tags")],
                [InlineKeyboardButton("⬅️ Volver",            callback_data="msg_edit_list")],
            ]
            await q.edit_message_text(
                f"✏️ *Editando:* {m['nombre']}\n\n¿Qué deseas modificar?",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown")

    elif a.startswith("msg_edit_field_"):
        field = a[len("msg_edit_field_"):]
        context.user_data["cm_edit_field"] = field
        if field == "categoria":
            kb = [[InlineKeyboardButton(label, callback_data=f"msg_edit_cat_{c}")]
                  for c, label in CAT_LABELS.items()]
            await q.edit_message_text(
                "✏️ Selecciona la nueva *categoría*:",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown")
        else:
            prompts_edit = {
                "nombre":    "✏️ Escribe el *nuevo nombre* del mensaje:",
                "contenido": "✏️ Envía el *nuevo contenido*\n(texto, imagen, video, audio o documento):",
                "tags":      "🏷 Escribe los *tags* separados por coma:\nEjemplo: `lunes, mañana, jóvenes`",
            }
            context.user_data["pending_action"] = f"msg_edit_save_{field}"
            await q.edit_message_text(prompts_edit.get(field, "✏️ Escribe el nuevo valor:"),
                                      parse_mode="Markdown")

    elif a.startswith("msg_edit_cat_"):
        cat = a[len("msg_edit_cat_"):]
        mid = context.user_data.get("cm_edit_id")
        m = next((x for x in data.get("custom_messages", []) if x["id"] == mid), None)
        if m and cat in VALID_CATEGORIES:
            m["categoria"] = cat
            save_data(data)
            await q.edit_message_text(
                f"✅ Categoría actualizada a *{CAT_LABELS[cat]}*.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="msg_center")
                ]]),
                parse_mode="Markdown")

    # ── Eliminar mensaje con confirmación ───────────────
    elif a == "msg_del_list":
        msgs = data.get("custom_messages", [])
        if not msgs:
            await q.edit_message_text(
                "🗑 No hay mensajes para eliminar.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="msg_center")
                ]]))
        else:
            kb, _, _ = _paginated_msg_kb(0, "msg_del_confirm_", "msg_center")
            await q.edit_message_text(
                "🗑 *Selecciona el mensaje a eliminar:*",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown")

    elif a.startswith("msg_del_confirm_"):
        mid = a[len("msg_del_confirm_"):]
        m = next((x for x in data.get("custom_messages", []) if x["id"] == mid), None)
        if m:
            kb = [
                [InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"msg_del_{mid}")],
                [InlineKeyboardButton("❌ No, cancelar", callback_data="msg_center")],
            ]
            # Contar programaciones asociadas
            assoc = sum(1 for s in data.get("scheduled_messages", [])
                        if s.get("mensaje_id") == mid)
            warn = f"\n\n⚠️ _Esto también eliminará {assoc} programación(es) asociada(s)._" if assoc else ""
            await q.edit_message_text(
                f"⚠️ ¿Deseas eliminar el mensaje *{m['nombre']}*?{warn}",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown")

    elif a.startswith("msg_del_") and not a.startswith("msg_del_confirm_") and not a.startswith("msg_del_list"):
        mid = a[len("msg_del_"):]
        msgs = data.get("custom_messages", [])
        m = next((x for x in msgs if x["id"] == mid), None)
        if m:
            data["custom_messages"] = [x for x in msgs if x["id"] != mid]
            scheds_antes = len(data.get("scheduled_messages", []))
            data["scheduled_messages"] = [
                s for s in data.get("scheduled_messages", [])
                if s.get("mensaje_id") != mid
            ]
            scheds_eliminadas = scheds_antes - len(data["scheduled_messages"])
            save_data(data)
            extra = f"\n🗓 {scheds_eliminadas} programación(es) eliminada(s)." if scheds_eliminadas else ""
            await q.edit_message_text(
                f"✅ Mensaje *{m['nombre']}* eliminado.{extra}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="msg_center")
                ]]),
                parse_mode="Markdown")

    # ── Paginación genérica ─────────────────────────────
    elif a.startswith("msg_page_"):
        parts = a[len("msg_page_"):].rsplit("_", 1)
        if len(parts) == 2:
            prefix, page_str = parts[0] + "_", parts[1]
            try:
                page = int(page_str)
                kb, total, pg = _paginated_msg_kb(page, prefix, "msg_center")
                start = page * MSG_PAGE_SIZE + 1
                end   = min((page + 1) * MSG_PAGE_SIZE, total)
                await q.edit_message_text(
                    f"📋 *Mensajes* ({start}-{end} de {total}):",
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode="Markdown")
            except ValueError:
                pass

    # ── Enviar mensaje ──────────────────────────────────
    elif a == "msg_send_list":
        msgs = data.get("custom_messages", [])
        if not msgs:
            await q.edit_message_text(
                "📤 No hay mensajes para enviar.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver", callback_data="msg_center")
                ]]))
        else:
            kb, _, _ = _paginated_msg_kb(0, "msg_send_", "msg_center")
            await q.edit_message_text(
                "📤 *Selecciona un mensaje para enviar:*",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown")

    elif a.startswith("msg_send_") and not a == "msg_send_list":
        mid = a[len("msg_send_"):]
        m = next((x for x in data.get("custom_messages", []) if x["id"] == mid), None)
        if m:
            context.user_data["pending_action"] = "msg_send_group"
            context.user_data["msg_to_send"] = mid
            await q.edit_message_text(
                f"📤 Enviar *{m['nombre']}*\n\nEscribe el *ID del grupo* destino:\n"
                f"_(Usa /getid en el grupo para obtenerlo)_",
                parse_mode="Markdown")

    elif a == "sched_menu":
        total = len([s for s in data.get("scheduled_messages", []) if s.get("active", True)])
        kb = [
            [InlineKeyboardButton("➕ Crear programación",   callback_data="sched_create")],
            [InlineKeyboardButton("📋 Ver programaciones",   callback_data="sched_list")],
            [InlineKeyboardButton("🗑 Eliminar programación", callback_data="sched_del_list")],
            [InlineKeyboardButton("⬅️ Volver",               callback_data="back_panel")],
        ]
        await q.edit_message_text(
            f"⏰ *Mensajes Programados*\n\nProgramaciones activas: *{total}*\n\nSelecciona una opción:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")

    elif a == "sched_create":
        msgs = data.get("custom_messages", [])
        if not msgs:
            await q.edit_message_text(
                "⚠️ No hay mensajes en el Centro de Mensajes.\n\nPrimero crea un mensaje en 📨 Centro de Mensajes.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="sched_menu")]]))
        else:
            kb = [[InlineKeyboardButton(f"📄 {m['nombre']}", callback_data=f"sched_pick_{m['id']}")]
                  for m in msgs]
            kb.append([InlineKeyboardButton("⬅️ Volver", callback_data="sched_menu")])
            await q.edit_message_text(
                "⏰ *Crear Programación*\n\nPaso 1: Selecciona el mensaje a programar:",
                reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif a.startswith("sched_pick_"):
        context.user_data["sched_msg_id"] = a[len("sched_pick_"):]
        kb = [
            [InlineKeyboardButton("1️⃣ Una vez",         callback_data="sched_freq_una_vez")],
            [InlineKeyboardButton("📅 Diario",           callback_data="sched_freq_diario")],
            [InlineKeyboardButton("📆 Semanal",          callback_data="sched_freq_semanal")],
            [InlineKeyboardButton("💼 Días laborables",  callback_data="sched_freq_dias_laborables")],
            [InlineKeyboardButton("🌅 Fines de semana",  callback_data="sched_freq_fines_de_semana")],
            [InlineKeyboardButton("🎛 Personalizado",    callback_data="sched_freq_personalizado")],
            [InlineKeyboardButton("⬅️ Volver",           callback_data="sched_create")],
        ]
        await q.edit_message_text(
            "⏰ *Crear Programación*\n\nPaso 2: Selecciona la frecuencia:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif a.startswith("sched_freq_"):
        freq = a[len("sched_freq_"):]
        context.user_data["sched_freq"] = freq
        if freq in ("diario", "dias_laborables", "fines_de_semana"):
            context.user_data["pending_action"] = "sched_hora"
            await q.edit_message_text(
                "⏰ *Crear Programación*\n\nPaso 3: Escribe la hora de envío.\n\n"
                "Formato: `HH:MM` (hora Colombia)\nEjemplo: `08:00` o `20:30`",
                parse_mode="Markdown")
        elif freq == "una_vez":
            context.user_data["pending_action"] = "sched_fecha"
            await q.edit_message_text(
                "⏰ *Crear Programación*\n\nPaso 3: Escribe la fecha y hora.\n\n"
                "Formato: `YYYY-MM-DD HH:MM`\nEjemplo: `2026-06-10 08:00`",
                parse_mode="Markdown")
        elif freq in ("semanal", "personalizado"):
            context.user_data["sched_dias"] = []
            await _show_day_picker(q, context)

    elif a.startswith("sched_day_"):
        day = a[len("sched_day_"):]
        dias = context.user_data.setdefault("sched_dias", [])
        if day in dias:
            dias.remove(day)
        else:
            dias.append(day)
        await _show_day_picker(q, context)

    elif a == "sched_days_confirm":
        dias = context.user_data.get("sched_dias", [])
        if not dias:
            await q.answer("⚠️ Selecciona al menos un día.", show_alert=True)
            await _show_day_picker(q, context)
        else:
            context.user_data["pending_action"] = "sched_hora"
            await q.edit_message_text(
                "⏰ *Crear Programación*\n\nPaso 4: Escribe la hora de envío.\n\n"
                "Formato: `HH:MM` (hora Colombia)\nEjemplo: `08:00`",
                parse_mode="Markdown")

    elif a == "sched_list":
        scheds = data.get("scheduled_messages", [])
        if not scheds:
            await q.edit_message_text(
                "📋 No hay programaciones guardadas.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="sched_menu")]]))
        else:
            lines = []
            for s in scheds:
                estado = "✅" if s.get("active", True) else "⏸"
                m = next((x for x in data.get("custom_messages", []) if x["id"] == s.get("mensaje_id")), None)
                nombre_msg = m["nombre"] if m else "?"
                lines.append(f"{estado} *{s['nombre']}* — _{nombre_msg}_ — `{s['hora']}`")
            await q.edit_message_text(
                "📋 *Programaciones:*\n\n" + "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="sched_menu")]]),
                parse_mode="Markdown")

    elif a == "sched_del_list":
        scheds = data.get("scheduled_messages", [])
        if not scheds:
            await q.edit_message_text(
                "🗑 No hay programaciones para eliminar.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="sched_menu")]]))
        else:
            kb = [[InlineKeyboardButton(f"🗑 {s['nombre']}", callback_data=f"sched_del_{s['id']}")]
                  for s in scheds]
            kb.append([InlineKeyboardButton("⬅️ Volver", callback_data="sched_menu")])
            await q.edit_message_text(
                "🗑 *Selecciona la programación a eliminar:*",
                reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif a.startswith("sched_del_"):
        sid = a[len("sched_del_"):]
        scheds = data.get("scheduled_messages", [])
        s = next((x for x in scheds if x["id"] == sid), None)
        if s:
            data["scheduled_messages"] = [x for x in scheds if x["id"] != sid]
            save_data(data)
            await q.edit_message_text(
                f"✅ Programación *{s['nombre']}* eliminada.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="sched_menu")]]),
                parse_mode="Markdown")

    else:
        prompts = {
            "edit_welcome":  "✏️ Escribe el nuevo mensaje de *bienvenida*.\nUsa {nombre} donde va el nombre del miembro:",
            "edit_farewell": "✏️ Escribe el nuevo mensaje de *despedida*.\nUsa {nombre} donde va el nombre del miembro:",
            "add_bad":       "➕ Escribe la palabra a *agregar* a la lista prohibida:",
            "del_bad":       "🗑 Escribe la palabra a *eliminar* de la lista prohibida:",
            "add_adult":     "➕ Escribe el dominio adulto a *agregar*:",
            "del_adult":     "🗑 Escribe el dominio adulto a *eliminar*:",
        }
        if a in prompts:
            context.user_data["pending_action"] = a
            await q.edit_message_text(prompts[a], parse_mode="Markdown")

# ═══════════════════════════════════════════════════════
#  RESPUESTAS DEL ADMIN EN PRIVADO
# ═══════════════════════════════════════════════════════
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    owners = data.get("owner_security", {}).get("owners", [ADMIN_ID])
    if msg.from_user.id not in owners or msg.chat.type != "private":
        return
    action = context.user_data.get("pending_action")
    if not action:
        return

    # ── Paso 1: nombre del mensaje ─────────────────────
    if action == "msg_nombre":
        context.user_data.pop("pending_action", None)
        nombre = msg.text.strip() if msg.text else ""
        if not nombre:
            context.user_data["pending_action"] = "msg_nombre"
            await msg.reply_text("⚠️ El nombre no puede estar vacío. Escríbelo de nuevo:")
            return
        context.user_data["cm_nombre"] = nombre
        # Ir al paso 2: tipo
        kb = [[InlineKeyboardButton(label, callback_data=f"msg_type_{t}")]
              for t, label in TYPE_LABELS.items()]
        await msg.reply_text(
            f"📨 *Crear mensaje — Paso 2 de 5*\n\n"
            f"Nombre: *{nombre}*\n\n"
            f"Selecciona el *tipo de contenido*:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    # ── Paso 3: captura de contenido ───────────────────
    if action == "msg_capture":
        context.user_data.pop("pending_action", None)
        tipo_esperado = context.user_data.get("cm_tipo")
        captured = None

        if msg.text and tipo_esperado == "text":
            captured = {"tipo": "text", "contenido": msg.text, "caption": None}
        elif msg.photo and tipo_esperado == "photo":
            captured = {"tipo": "photo", "contenido": msg.photo[-1].file_id, "caption": msg.caption}
        elif msg.video and tipo_esperado == "video":
            captured = {"tipo": "video", "contenido": msg.video.file_id, "caption": msg.caption}
        elif msg.audio and tipo_esperado == "audio":
            captured = {"tipo": "audio", "contenido": msg.audio.file_id, "caption": msg.caption}
        elif msg.voice and tipo_esperado == "voice":
            captured = {"tipo": "voice", "contenido": msg.voice.file_id, "caption": None}
        elif msg.document and tipo_esperado == "document":
            captured = {"tipo": "document", "contenido": msg.document.file_id, "caption": msg.caption}
        else:
            context.user_data["pending_action"] = "msg_capture"
            label = TYPE_LABELS.get(tipo_esperado, tipo_esperado)
            await msg.reply_text(
                f"⚠️ Tipo incorrecto. Se esperaba *{label}*. Intenta de nuevo:",
                parse_mode="Markdown")
            return

        context.user_data["cm_captured"] = captured
        # Ir al paso 4: categoría
        kb = [[InlineKeyboardButton(label, callback_data=f"msg_cat_{c}")]
              for c, label in CAT_LABELS.items()]
        await msg.reply_text(
            "📨 *Crear mensaje — Paso 4 de 5*\n\n"
            "✅ Contenido capturado.\n\n"
            "Selecciona la *categoría*:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown")
        return

    # ── Edición de campos ───────────────────────────────
    if action.startswith("msg_edit_save_"):
        field = action[len("msg_edit_save_"):]
        context.user_data.pop("pending_action", None)
        mid = context.user_data.get("cm_edit_id")
        m = next((x for x in data.get("custom_messages", []) if x["id"] == mid), None)
        if not m:
            await msg.reply_text("⚠️ Mensaje no encontrado.")
            return
        if field == "nombre":
            val = msg.text.strip() if msg.text else ""
            if not val:
                await msg.reply_text("⚠️ El nombre no puede estar vacío.")
                return
            m["nombre"] = val
            save_data(data)
            await msg.reply_text(f"✅ Nombre actualizado a *{val}*.", parse_mode="Markdown")
        elif field == "contenido":
            # Capturar cualquier tipo de contenido
            if msg.text:
                m["contenido"] = msg.text
                m["tipo"] = "text"
            elif msg.photo:
                m["contenido"] = msg.photo[-1].file_id
                m["tipo"] = "photo"
                if msg.caption: m["caption"] = msg.caption
            elif msg.video:
                m["contenido"] = msg.video.file_id
                m["tipo"] = "video"
                if msg.caption: m["caption"] = msg.caption
            elif msg.audio:
                m["contenido"] = msg.audio.file_id
                m["tipo"] = "audio"
            elif msg.voice:
                m["contenido"] = msg.voice.file_id
                m["tipo"] = "voice"
            elif msg.document:
                m["contenido"] = msg.document.file_id
                m["tipo"] = "document"
                if msg.caption: m["caption"] = msg.caption
            else:
                await msg.reply_text("⚠️ Tipo no reconocido.")
                return
            if m["tipo"] not in VALID_TYPES:
                await msg.reply_text("⚠️ Tipo no válido.")
                return
            save_data(data)
            await msg.reply_text(f"✅ Contenido actualizado ({TYPE_LABELS.get(m['tipo'], m['tipo'])}).")
        elif field == "tags":
            raw = msg.text.strip() if msg.text else ""
            tags = [t.strip() for t in raw.split(",") if t.strip()]
            m["tags"] = tags
            save_data(data)
            await msg.reply_text(f"✅ Tags actualizados: {', '.join(tags) or '—'}.")
        return

    text = msg.text.strip() if msg.text else ""
    context.user_data.pop("pending_action", None)

    # ── Seguridad — agregar administrador ──────────────
    if action == "sec_add_admin_id":
        context.user_data.pop("pending_action", None)
        val = msg.text.strip() if msg.text else ""
        if not val.isdigit():
            context.user_data["pending_action"] = "sec_add_admin_id"
            await msg.reply_text("⚠️ El ID debe ser numérico. Intenta de nuevo:")
            return
        uid_int = int(val)
        owners  = data.setdefault("owner_security", {}).setdefault("owners", [ADMIN_ID])
        if uid_int in owners:
            await msg.reply_text(f"ℹ️ El ID `{uid_int}` ya está en la lista.",
                                 parse_mode="Markdown")
            return
        owners.append(uid_int)
        save_data(data)
        await msg.reply_text(f"✅ Administrador `{uid_int}` agregado correctamente.",
                             parse_mode="Markdown")
        return

    # ── Seguridad — cambiar palabra secreta ────────────
    if action == "sec_keyword":
        context.user_data.pop("pending_action", None)
        keyword = msg.text.strip() if msg.text else ""
        if len(keyword) < 3:
            context.user_data["pending_action"] = "sec_keyword"
            await msg.reply_text("⚠️ Mínimo 3 caracteres. Intenta de nuevo:")
            return
        if len(keyword) > 50:
            context.user_data["pending_action"] = "sec_keyword"
            await msg.reply_text("⚠️ Máximo 50 caracteres. Intenta de nuevo:")
            return
        data.setdefault("owner_security", {})["secret_keyword"] = keyword
        save_data(data)
        await msg.reply_text("✅ Palabra secreta actualizada correctamente.")
        return

    # ── Seguridad — cambiar tiempo de sesión ───────────
    # ── Bienvenida Premium — captura imagen ────────────
    if action == "wp_capture_image":
        context.user_data.pop("pending_action", None)
        if not msg.photo:
            context.user_data["pending_action"] = "wp_capture_image"
            await msg.reply_text(
                "⚠️ Debes enviar una *imagen*. Intenta de nuevo:",
                parse_mode="Markdown")
            return
        file_id = msg.photo[-1].file_id
        data.setdefault("welcome_config", {})["image_file_id"] = file_id
        save_data(data)
        await msg.reply_text("✅ Imagen guardada correctamente.")
        return

    # ── Bienvenida Premium — captura mensaje ───────────
    if action == "wp_capture_message":
        context.user_data.pop("pending_action", None)
        if not msg.text or not msg.text.strip():
            context.user_data["pending_action"] = "wp_capture_message"
            await msg.reply_text("⚠️ El mensaje no puede estar vacío. Intenta de nuevo:")
            return
        data.setdefault("welcome_config", {})["message_text"] = msg.text.strip()
        save_data(data)
        await msg.reply_text(
            "✅ Mensaje guardado correctamente.\n\n"
            "_Vista previa:_\n" +
            msg.text.strip().replace("{nombre}", "*(nombre)*"),
            parse_mode="Markdown")
        return

    if action == "edit_welcome":
        data["welcome"] = text
        save_data(data)
        await msg.reply_text("✅ Mensaje de bienvenida actualizado.")

    elif action == "edit_farewell":
        data["farewell"] = text
        save_data(data)
        await msg.reply_text("✅ Mensaje de despedida actualizado.")

    elif action == "add_bad":
        w = text.lower()
        if w not in data["bad_words"]:
            data["bad_words"].append(w)
            save_data(data)
            await msg.reply_text(f"✅ Palabra *{w}* agregada.", parse_mode="Markdown")
        else:
            await msg.reply_text(f"ℹ️ *{w}* ya estaba en la lista.", parse_mode="Markdown")

    elif action == "del_bad":
        w = text.lower()
        if w in data["bad_words"]:
            data["bad_words"].remove(w)
            save_data(data)
            await msg.reply_text(f"✅ Palabra *{w}* eliminada.", parse_mode="Markdown")
        else:
            await msg.reply_text(f"ℹ️ No encontré *{w}*.", parse_mode="Markdown")

    elif action == "add_adult":
        d2 = text.lower()
        if d2 not in data["adult_domains"]:
            data["adult_domains"].append(d2)
            save_data(data)
            await msg.reply_text(f"✅ Dominio *{d2}* agregado.", parse_mode="Markdown")
        else:
            await msg.reply_text(f"ℹ️ *{d2}* ya estaba en la lista.", parse_mode="Markdown")

    elif action == "del_adult":
        d2 = text.lower()
        if d2 in data["adult_domains"]:
            data["adult_domains"].remove(d2)
            save_data(data)
            await msg.reply_text(f"✅ Dominio *{d2}* eliminado.", parse_mode="Markdown")
        else:
            await msg.reply_text(f"ℹ️ No encontré *{d2}*.", parse_mode="Markdown")

    elif action == "set_night_hour":
        if not (text.isdigit() and 0 <= int(text) <= 23):
            await msg.reply_text("⚠️ Escribe un número entre 0 y 23. Ejemplo: `22`",
                                 parse_mode="Markdown")
        elif int(text) == data["day_hour"]:
            await msg.reply_text(
                f"⚠️ La hora de cierre debe ser diferente a la hora de apertura "
                f"(actualmente *{data['day_hour']}:00*).",
                parse_mode="Markdown")
        else:
            data["night_hour"] = int(text)
            save_data(data)
            await msg.reply_text(
                f"✅ Hora de cierre actualizada: *{data['night_hour']}:00*",
                parse_mode="Markdown")

    elif action == "set_day_hour":
        if not (text.isdigit() and 0 <= int(text) <= 23):
            await msg.reply_text("⚠️ Escribe un número entre 0 y 23. Ejemplo: `6`",
                                 parse_mode="Markdown")
        elif int(text) == data["night_hour"]:
            await msg.reply_text(
                f"⚠️ La hora de apertura debe ser diferente a la hora de cierre "
                f"(actualmente *{data['night_hour']}:00*).",
                parse_mode="Markdown")
        else:
            data["day_hour"] = int(text)
            save_data(data)
            await msg.reply_text(
                f"✅ Hora de apertura actualizada: *{data['day_hour']}:00*",
                parse_mode="Markdown")

    elif action == "sched_fecha":
        # Una vez: fecha + hora juntos
        try:
            dt = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
            context.user_data["sched_fecha_val"] = dt.strftime("%Y-%m-%d")
            context.user_data["sched_hora_val"]  = dt.strftime("%H:%M")
            context.user_data["pending_action"]  = "sched_nombre"
            await msg.reply_text(
                f"✅ Fecha y hora: *{text}*\n\nAhora escribe un *nombre* para esta programación:",
                parse_mode="Markdown")
        except ValueError:
            context.user_data["pending_action"] = "sched_fecha"
            await msg.reply_text(
                "⚠️ Formato incorrecto. Usa: `YYYY-MM-DD HH:MM`\nEjemplo: `2026-06-10 08:00`",
                parse_mode="Markdown")

    elif action == "sched_hora":
        # Validar HH:MM
        if not re.match(r"^\d{2}:\d{2}$", text):
            context.user_data["pending_action"] = "sched_hora"
            await msg.reply_text(
                "⚠️ Formato incorrecto. Usa: `HH:MM`\nEjemplo: `08:00`",
                parse_mode="Markdown")
            return
        try:
            h, m2 = int(text.split(":")[0]), int(text.split(":")[1])
            if not (0 <= h <= 23 and 0 <= m2 <= 59):
                raise ValueError
        except ValueError:
            context.user_data["pending_action"] = "sched_hora"
            await msg.reply_text("⚠️ Hora inválida. Ejemplo: `08:00`", parse_mode="Markdown")
            return
        context.user_data["sched_hora_val"] = text
        context.user_data["pending_action"] = "sched_nombre"
        await msg.reply_text(
            f"✅ Hora: *{text}*\n\nAhora escribe un *nombre* para esta programación:",
            parse_mode="Markdown")

    elif action == "sched_nombre":
        nombre = text
        freq      = context.user_data.pop("sched_freq", "diario")
        hora      = context.user_data.pop("sched_hora_val", "08:00")
        fecha     = context.user_data.pop("sched_fecha_val", None)
        dias      = context.user_data.pop("sched_dias", [])
        msg_id    = context.user_data.pop("sched_msg_id", None)
        new_id    = f"sched_{int(time.time())}"
        entry = {
            "id":         new_id,
            "nombre":     nombre,
            "mensaje_id": msg_id,
            "frecuencia": freq,
            "hora":       hora,
            "dias":       dias,
            "fecha":      fecha,
            "active":     True,
        }
        data.setdefault("scheduled_messages", []).append(entry)
        save_data(data)

        freq_labels = {
            "una_vez": "Una vez", "diario": "Diario",
            "semanal": "Semanal", "dias_laborables": "Días laborables",
            "fines_de_semana": "Fines de semana", "personalizado": "Personalizado"
        }
        dias_str = ", ".join(d.capitalize() for d in dias) if dias else "—"
        await msg.reply_text(
            f"✅ Programación *{nombre}* creada.\n\n"
            f"📅 Frecuencia: {freq_labels.get(freq, freq)}\n"
            f"⏰ Hora: {hora} (Colombia)\n"
            f"📆 Días: {dias_str}",
            parse_mode="Markdown")

    elif action == "msg_send_group":
        mid = context.user_data.pop("msg_to_send", None)
        m = next((x for x in data.get("custom_messages", []) if x["id"] == mid), None)
        if not m:
            await msg.reply_text("⚠️ Mensaje no encontrado.")
            return
        try:
            cid = int(text)
            tipo = m["tipo"]
            content = m["contenido"]
            caption = m.get("caption") or None
            if tipo == "text":
                await context.bot.send_message(cid, content, parse_mode="Markdown")
            elif tipo == "photo":
                await context.bot.send_photo(cid, content, caption=caption)
            elif tipo == "video":
                await context.bot.send_video(cid, content, caption=caption)
            elif tipo == "audio":
                await context.bot.send_audio(cid, content, caption=caption)
            elif tipo == "document":
                await context.bot.send_document(cid, content, caption=caption)
            elif tipo == "sticker":
                await context.bot.send_sticker(cid, content)
            elif tipo == "animation":
                await context.bot.send_animation(cid, content, caption=caption)
            await msg.reply_text(f"✅ Mensaje *{m['nombre']}* enviado.", parse_mode="Markdown")
        except Exception as e:
            await msg.reply_text(f"⚠️ Error al enviar: {e}")

# ═══════════════════════════════════════════════════════
#  DESPACHADOR DE MENSAJES PROGRAMADOS
# ═══════════════════════════════════════════════════════
async def dispatch_scheduled(context: ContextTypes.DEFAULT_TYPE):
    """Revisa cada minuto si hay mensajes programados que enviar."""
    now = datetime.datetime.now(BOGOTA_TZ)
    now_day  = now.strftime("%A").lower()
    now_time = now.strftime("%H:%M")
    now_date = now.strftime("%Y-%m-%d")

    DAY_MAP = {
        "monday":"lunes","tuesday":"martes","wednesday":"miércoles",
        "thursday":"jueves","friday":"viernes","saturday":"sábado","sunday":"domingo"
    }
    now_day_es = DAY_MAP.get(now_day, now_day)

    changed = False

    for sched in data.get("scheduled_messages", []):
        if not sched.get("active", True):
            continue
        if sched["hora"] != now_time:
            continue

        freq = sched["frecuencia"]
        dias = sched.get("dias", [])

        # ── Determinar período actual para anti-duplicados ──
        # Clave única que identifica el período de ejecución actual
        if freq == "una_vez":
            period_key = sched.get("fecha", now_date)
        elif freq in ("diario", "dias_laborables", "fines_de_semana"):
            period_key = now_date
        elif freq in ("semanal", "personalizado"):
            period_key = f"{now_date}_{now_day_es}"
        else:
            period_key = now_date

        # ── Verificar si ya fue ejecutado en este período ──
        if sched.get("last_run") == period_key:
            continue

        # ── Verificar si corresponde ejecutar hoy ──
        match = False
        if freq == "una_vez":
            match = sched.get("fecha") == now_date
        elif freq == "diario":
            match = True
        elif freq == "semanal":
            match = now_day_es in dias
        elif freq == "fines_de_semana":
            match = now_day_es in ("sábado", "domingo")
        elif freq == "dias_laborables":
            match = now_day_es in ("lunes","martes","miércoles","jueves","viernes")
        elif freq == "personalizado":
            match = now_day_es in dias

        if not match:
            continue

        # ── Verificar que el mensaje existe ──
        msg_id = sched.get("mensaje_id")
        m = next((x for x in data.get("custom_messages", []) if x["id"] == msg_id), None)
        if not m:
            continue

        # ── Enviar a todos los grupos registrados ──
        for cid in data.get("registered_chats", []):
            try:
                tipo    = m["tipo"]
                content = m["contenido"]
                caption = m.get("caption") or None
                if tipo == "text":
                    await context.bot.send_message(int(cid), content, parse_mode="Markdown")
                elif tipo == "photo":
                    await context.bot.send_photo(int(cid), content, caption=caption)
                elif tipo == "video":
                    await context.bot.send_video(int(cid), content, caption=caption)
                elif tipo == "audio":
                    await context.bot.send_audio(int(cid), content, caption=caption)
                elif tipo == "document":
                    await context.bot.send_document(int(cid), content, caption=caption)
                elif tipo == "sticker":
                    await context.bot.send_sticker(int(cid), content)
                elif tipo == "animation":
                    await context.bot.send_animation(int(cid), content, caption=caption)
                logger.info(f"✅ Programado '{sched['nombre']}' enviado a {cid}")
            except Exception as e:
                logger.warning(f"Programado {sched['id']} → {cid}: {e}")

        # ── Actualizar last_run y manejar una_vez ──
        sched["last_run"] = period_key
        if freq == "una_vez":
            sched["active"] = False
        changed = True

    if changed:
        save_data(data)

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(data["rules"], parse_mode="Markdown")

async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    cid = update.message.chat_id
    await update.message.reply_text(
        f"📋 Tienes *{get_warn(cid, uid)}* advertencia(s).",
        parse_mode="Markdown")

async def cmd_getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 ID de este chat: `{update.message.chat_id}`",
        parse_mode="Markdown")

@only_admin
async def cmd_resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Phase 9 — requiere sesión activa
    if not is_owner(update, context):
        await update.message.reply_text(
            "⛔ Este comando requiere sesión activa.\n"
            "Envía tu palabra secreta en chat privado.")
        return
    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
        reset_warn(update.message.chat_id, uid)
        await update.message.reply_text("✅ Advertencias reiniciadas.")
    else:
        await update.message.reply_text(
            "↩️ Responde al mensaje del usuario para resetear sus advertencias.")


# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    app.job_queue.run_repeating(auto_night_check,   interval=60,   first=10)
    app.job_queue.run_repeating(dispatch_scheduled, interval=60,   first=15)
    app.job_queue.run_repeating(cleanup_spam_tracker, interval=1800, first=1800)

    app.add_handler(ChatMemberHandler(on_my_chat_member,  ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_member_change,   ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CommandHandler("reglas",       cmd_rules))
    app.add_handler(CommandHandler("advertencias", cmd_warnings))
    app.add_handler(CommandHandler("getid",        cmd_getid))
    app.add_handler(CommandHandler("resetwarn",    cmd_resetwarn))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, moderate_text))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.VIDEO_NOTE, moderate_media))
    app.add_handler(MessageHandler(
        filters.Sticker.ALL, moderate_sticker))
    # Palabra secreta — prioridad alta en privado
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        handle_secret_keyword), group=0)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        handle_admin_reply), group=1)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (
            filters.PHOTO | filters.VIDEO | filters.AUDIO |
            filters.Document.ALL | filters.Sticker.ALL | filters.ANIMATION
        ),
        handle_admin_reply))

    logger.info("✝️  Bot Fuera del Templo — activo")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
