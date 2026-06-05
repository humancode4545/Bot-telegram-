import logging
import re
import json
import os
import random
import datetime
import time
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
    "bad_words": [
        "puta","puto","mierda","coño","pendejo","pendeja","cabron","cabrón",
        "joder","hostia","gilipollas","imbécil","imbecil","idiota","estupido",
        "estúpido","marica","maricon","maricón","hdp","verga","polla","culo",
        "cojones","chingar","chingada","chingado","culero","mamada","carajo",
        "malparido","malparida","gonorrea","hijueputa","hijuemadre","maldicion"
    ],
    "adult_domains": [
        "pornhub","xvideos","xnxx","redtube","youporn","xhamster","brazzers",
        "onlyfans","chaturbate","livejasmin","stripchat","cam4","myfreecams",
        "bongacams","porn","xxx","sex","adult","nudist","nude","erotic",
        "hentai","fetish","sexo","porno","nakedgirl","nsfw","rule34"
    ],
    "adult_keywords": [
        "desnudo","desnuda","sin ropa","foto caliente","video hot",
        "contenido adulto","pack","manda pack","envia pack","fotos intimas",
        "video intimo","sexting","nudes","nude","porno","pornografia",
        "masturbacion","orgasmo","relacion sexual","acto sexual"
    ],
    "devotionals": [
        "📖 *Devocional del día*\n\n_\"Esfuérzate y sé valiente. No temas ni desmayes, porque Jehová tu Dios estará contigo.\"_\n— Josué 1:9 🙏",
        "📖 *Devocional del día*\n\n_\"Todo lo puedo en Cristo que me fortalece.\"_\n— Filipenses 4:13 💪✝️",
        "📖 *Devocional del día*\n\n_\"El Señor es mi pastor; nada me faltará.\"_\n— Salmo 23:1 🙏",
        "📖 *Devocional del día*\n\n_\"Encomienda al Señor tu camino, y confía en él; él actuará.\"_\n— Salmo 37:5 🌟",
        "📖 *Devocional del día*\n\n_\"Busquen primeramente el reino de Dios y su justicia.\"_\n— Mateo 6:33 🙏",
        "📖 *Devocional del día*\n\n_\"Porque yo sé los planes que tengo para ustedes, planes de bienestar.\"_\n— Jeremías 29:11 ✝️",
        "📖 *Devocional del día*\n\n_\"Transformaos por medio de la renovación de vuestro entendimiento.\"_\n— Romanos 12:2 💡",
        "📖 *Devocional del día*\n\n_\"Ámense los unos a los otros como yo los he amado.\"_\n— Juan 13:34 ❤️",
        "📖 *Devocional del día*\n\n_\"Confía en el Señor de todo corazón, y no en tu propia inteligencia.\"_\n— Proverbios 3:5 🙏",
        "📖 *Devocional del día*\n\n_\"Sean fuertes y valientes. El Señor su Dios va con ustedes.\"_\n— Deuteronomio 31:6 🔥",
    ],
    "verses": [
        "✝️ *Versículo del día*\n\n_\"Porque de tal manera amó Dios al mundo, que ha dado a su Hijo unigénito.\"_ — Juan 3:16",
        "✝️ *Versículo del día*\n\n_\"El Señor es mi luz y mi salvación; ¿a quién temeré?\"_ — Salmo 27:1",
        "✝️ *Versículo del día*\n\n_\"Clama a mí, y yo te responderé, y te enseñaré cosas grandes.\"_ — Jeremías 33:3",
        "✝️ *Versículo del día*\n\n_\"El que comenzó en ustedes la buena obra, la perfeccionará.\"_ — Filipenses 1:6",
        "✝️ *Versículo del día*\n\n_\"Dios es nuestro amparo y fortaleza, nuestro pronto auxilio.\"_ — Salmo 46:1",
        "✝️ *Versículo del día*\n\n_\"Jehová peleará por vosotros, y vosotros estaréis tranquilos.\"_ — Éxodo 14:14",
        "✝️ *Versículo del día*\n\n_\"Yo soy el camino, la verdad y la vida.\"_ — Juan 14:6",
        "✝️ *Versículo del día*\n\n_\"La gracia del Señor Jesucristo esté con todos ustedes.\"_ — Apocalipsis 22:21",
    ],
    "rules": "📖 *REGLAMENTO OFICIAL — FUERA DEL TEMPLO*\n\n*1. Cristo es el centro*\nToda participación alineada con los valores de Jesucristo. Se promoverá el amor, la verdad, la gracia y el respeto.\n\n*2. Respeto mutuo*\nNo insultos, burlas, humillaciones ni lenguaje ofensivo. Prohibido el acoso o agresión verbal.\n\n*3. Contenido apropiado*\n✅ Reflexiones bíblicas, devocionales, testimonios, música cristiana, mensajes de ánimo.\n❌ Contenido sexual, blasfemo, violento o contrario a la fe cristiana.\n\n*4. Debates doctrinales*\nCon respeto. Sin ataques a iglesias o denominaciones.\n\n*5. Sin spam ni enlaces*\nNo links sin autorización. No publicidad ni contenido repetitivo.\n\n*6. Privacidad*\nNo compartir datos personales de otros miembros sin autorización.\n\n*7. Ambiente edificante*\nEmpatía y apoyo mutuo. Sin chismes ni rumores destructivos.\n\n*8. Uso responsable*\nEvitar mensajes excesivos. Respetar momentos de reflexión y oración.\n\n*9. Sanciones*\n1️⃣ Llamado de atención → 2️⃣ Advertencia formal → 3️⃣ Restricción 24h → 4️⃣ Expulsión\n\n*10. Principios*\nAmor • Respeto • Humildad • Honestidad • Servicio • Fe\n\n✨ _Este grupo existe para glorificar a Dios._ 🙏📖✝️"
}

# ═══════════════════════════════════════════════════════
#  PERSISTENCIA
# ═══════════════════════════════════════════════════════
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        d = DEFAULT_DATA.copy()
        d.update(saved)
        return d
    return DEFAULT_DATA.copy()

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

data = load_data()

# ═══════════════════════════════════════════════════════
#  ANTI-SPAM
# ═══════════════════════════════════════════════════════
SPAM_WINDOW = 10
SPAM_LIMIT  = 3
spam_tracker = defaultdict(deque)

def is_spamming(chat_id, user_id):
    key = (chat_id, user_id)
    now = time.time()
    q = spam_tracker[key]
    while q and now - q[0] > SPAM_WINDOW:
        q.popleft()
    q.append(now)
    return len(q) > SPAM_LIMIT

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
#  ADVERTENCIAS
# ═══════════════════════════════════════════════════════
def get_warn(chat_id, user_id):
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
    name    = user.first_name or user.username or "Hermano/a"

    if old_s in ("left", "kicked") and new_s == "member":
        for key in ("last_welcome_id", "last_rules_id"):
            mid = data[key].get(str(chat_id))
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

    # Detección de contenido prohibido
    reason = None
    if is_adult(text):       reason = "contenido para adultos 🔞"
    elif has_link(text):     reason = "enlace no autorizado 🔗"
    elif has_bad_word(text): reason = "lenguaje inapropiado 🚫"

    if reason:
        try: await msg.delete()
        except Exception: pass
        count = add_warn(chat_id, user_id)
        await sanction(msg, context, name, user_id, chat_id, count, reason)

# ═══════════════════════════════════════════════════════
#  MODERACIÓN FOTOS Y VIDEOS
# ═══════════════════════════════════════════════════════
async def moderate_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
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
    now_h = datetime.datetime.now().hour

    if now_h == data["night_hour"] and not data["night_mode_active"]:
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

    elif now_h == data["day_hour"] and data["night_mode_active"]:
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
#  PANEL DE CONTROL
# ═══════════════════════════════════════════════════════
@only_admin
async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("✏️ Bienvenida",      callback_data="edit_welcome"),
         InlineKeyboardButton("✏️ Despedida",        callback_data="edit_farewell")],
        [InlineKeyboardButton("➕ Agregar Palabra",   callback_data="add_bad"),
         InlineKeyboardButton("🗑 Quitar Palabra",    callback_data="del_bad")],
        [InlineKeyboardButton("📋 Ver Palabras",      callback_data="list_bad"),
         InlineKeyboardButton("🔞 Ver Dominios",      callback_data="list_adult")],
        [InlineKeyboardButton("➕ Agregar Dominio",   callback_data="add_adult"),
         InlineKeyboardButton("🗑 Quitar Dominio",    callback_data="del_adult")],
        [InlineKeyboardButton("🌙 Activar Noche",     callback_data="night_on"),
         InlineKeyboardButton("☀️ Activar Día",       callback_data="day_on")],
        [InlineKeyboardButton("⚙️ Cambiar Horario",   callback_data="config_hours"),
         InlineKeyboardButton("📊 Estado del Bot",    callback_data="status")],
        [InlineKeyboardButton("📖 Enviar Devocional", callback_data="send_devo"),
         InlineKeyboardButton("✝️ Enviar Versículo",  callback_data="send_verse")],
    ]
    await update.message.reply_text(
        "🎛 *Panel de Control — Fuera del Templo*\n\nSelecciona una opción:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("⛔ Sin acceso.")
        return
    a = q.data

    if a == "status":
        night  = "🌙 CERRADO" if data["night_mode_active"] else "☀️ ABIERTO"
        grupos = len(data.get("registered_chats", []))
        await q.edit_message_text(
            f"📊 *Estado del Bot*\n\n"
            f"🔘 Grupo: {night}\n"
            f"⏰ Horario: {data['night_hour']}:00 cierre — {data['day_hour']}:00 apertura\n"
            f"🏠 Grupos registrados: {grupos}\n"
            f"🚫 Palabras prohibidas: {len(data['bad_words'])}\n"
            f"🔞 Dominios bloqueados: {len(data['adult_domains'])}\n"
            f"⚡ Anti-spam: +{SPAM_LIMIT} msgs en {SPAM_WINDOW}s\n"
            f"📖 Devocionales: {len(data['devotionals'])}\n"
            f"✝️ Versículos: {len(data['verses'])}",
            parse_mode="Markdown")

    elif a == "list_bad":
        words = "\n".join(f"• {w}" for w in sorted(data["bad_words"]))
        await q.edit_message_text(
            f"🚫 *Palabras Prohibidas:*\n\n{words}", parse_mode="Markdown")

    elif a == "list_adult":
        doms = "\n".join(f"• {d}" for d in sorted(data["adult_domains"]))
        await q.edit_message_text(
            f"🔞 *Dominios Bloqueados:*\n\n{doms}", parse_mode="Markdown")

    elif a == "night_on":
        data["night_mode_active"] = True
        save_data(data)
        for cid in data.get("registered_chats", []):
            try:
                await context.bot.send_message(
                    int(cid),
                    f"🌙 *El grupo entra en Modo Noche.*\n\nEs hora de descansar. 😴\n"
                    f"El grupo estará cerrado hasta las *{data['day_hour']}:00 AM*.\n\n"
                    f"_Que el Señor les dé un buen descanso._ 🙏✝️",
                    parse_mode="Markdown")
            except Exception: pass
        await q.edit_message_text(
            "🌙 *Modo Noche activado. Grupo cerrado.*", parse_mode="Markdown")

    elif a == "day_on":
        data["night_mode_active"] = False
        save_data(data)
        for cid in data.get("registered_chats", []):
            try:
                await context.bot.send_message(
                    int(cid),
                    f"☀️ *¡Buenos días! El grupo está abierto nuevamente.*\n\n"
                    f"_Que este nuevo día esté lleno de la presencia de Dios._ 🙏📖✝️",
                    parse_mode="Markdown")
            except Exception: pass
        await q.edit_message_text(
            "☀️ *Modo Día activado. Grupo abierto.*", parse_mode="Markdown")

    else:
        prompts = {
            "edit_welcome":  "✏️ Escribe el nuevo mensaje de *bienvenida*.\nUsa {nombre} donde va el nombre del miembro:",
            "edit_farewell": "✏️ Escribe el nuevo mensaje de *despedida*.\nUsa {nombre} donde va el nombre del miembro:",
            "add_bad":       "➕ Escribe la palabra a *agregar* a la lista prohibida:",
            "del_bad":       "🗑 Escribe la palabra a *eliminar* de la lista prohibida:",
            "add_adult":     "➕ Escribe el dominio adulto a *agregar* (ej: sexo, porn2):",
            "del_adult":     "🗑 Escribe el dominio adulto a *eliminar*:",
            "config_hours":  "⚙️ Escribe el horario así:\n`HORA_CIERRE HORA_APERTURA`\n\nEjemplo: `22 6` (cierra 10pm, abre 6am)",
            "send_devo":     "📖 Escribe el *ID del grupo* donde enviar el devocional:\n_(Usa /getid en el grupo para obtenerlo)_",
            "send_verse":    "✝️ Escribe el *ID del grupo* donde enviar el versículo:",
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
    if msg.from_user.id != ADMIN_ID or msg.chat.type != "private":
        return
    action = context.user_data.get("pending_action")
    if not action:
        return
    text = msg.text.strip()
    context.user_data.pop("pending_action", None)

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

    elif action == "config_hours":
        parts = text.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            data["night_hour"] = int(parts[0])
            data["day_hour"]   = int(parts[1])
            save_data(data)
            await msg.reply_text(
                f"✅ Horario actualizado:\n"
                f"🌙 Cierre: {data['night_hour']}:00\n"
                f"☀️ Apertura: {data['day_hour']}:00")
        else:
            await msg.reply_text("⚠️ Formato incorrecto. Ejemplo: `22 6`",
                                 parse_mode="Markdown")

    elif action == "send_devo":
        try:
            await context.bot.send_message(
                int(text), random.choice(data["devotionals"]),
                parse_mode="Markdown")
            await msg.reply_text("✅ Devocional enviado.")
        except Exception as e:
            await msg.reply_text(f"⚠️ Error: {e}")

    elif action == "send_verse":
        try:
            await context.bot.send_message(
                int(text), random.choice(data["verses"]),
                parse_mode="Markdown")
            await msg.reply_text("✅ Versículo enviado.")
        except Exception as e:
            await msg.reply_text(f"⚠️ Error: {e}")

# ═══════════════════════════════════════════════════════
#  COMANDOS GENERALES
# ═══════════════════════════════════════════════════════
async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(data["rules"], parse_mode="Markdown")

async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    cid = update.message.chat_id
    await update.message.reply_text(
        f"📋 Tienes *{get_warn(cid, uid)}* advertencia(s).",
        parse_mode="Markdown")

async def cmd_verse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        random.choice(data["verses"]), parse_mode="Markdown")

async def cmd_devo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        random.choice(data["devotionals"]), parse_mode="Markdown")

async def cmd_getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 ID de este chat: `{update.message.chat_id}`",
        parse_mode="Markdown")

@only_admin
async def cmd_resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
        reset_warn(update.message.chat_id, uid)
        await update.message.reply_text("✅ Advertencias reiniciadas.")
    else:
        await update.message.reply_text(
            "↩️ Responde al mensaje del usuario para resetear sus advertencias.")

@only_admin
async def cmd_night(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["night_mode_active"] = True
    save_data(data)
    for cid in data.get("registered_chats", []):
        try:
            await context.bot.send_message(
                int(cid),
                f"🌙 *El grupo entra en Modo Noche.*\n\nEs hora de descansar. 😴\n"
                f"El grupo estará cerrado hasta las *{data['day_hour']}:00 AM*.\n\n"
                f"_Que el Señor les dé un buen descanso._ 🙏✝️",
                parse_mode="Markdown")
        except Exception: pass
    await update.message.reply_text(
        "🌙 *Modo Noche activado. Grupo cerrado.*", parse_mode="Markdown")

@only_admin
async def cmd_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["night_mode_active"] = False
    save_data(data)
    for cid in data.get("registered_chats", []):
        try:
            await context.bot.send_message(
                int(cid),
                f"☀️ *¡Buenos días! El grupo está abierto nuevamente.*\n\n"
                f"_Que este nuevo día esté lleno de la presencia de Dios._ 🙏📖✝️",
                parse_mode="Markdown")
        except Exception: pass
    await update.message.reply_text(
        "☀️ *Modo Día activado. Grupo abierto.*", parse_mode="Markdown")

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

    app.job_queue.run_repeating(auto_night_check, interval=60, first=10)

    app.add_handler(ChatMemberHandler(on_my_chat_member,  ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_member_change,   ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CommandHandler("panel",        cmd_panel))
    app.add_handler(CommandHandler("reglas",       cmd_rules))
    app.add_handler(CommandHandler("advertencias", cmd_warnings))
    app.add_handler(CommandHandler("versiculo",    cmd_verse))
    app.add_handler(CommandHandler("devocional",   cmd_devo))
    app.add_handler(CommandHandler("getid",        cmd_getid))
    app.add_handler(CommandHandler("resetwarn",    cmd_resetwarn))
    app.add_handler(CommandHandler("noche",        cmd_night))
    app.add_handler(CommandHandler("dia",          cmd_day))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, moderate_text))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.VIDEO_NOTE, moderate_media))
    app.add_handler(MessageHandler(
        filters.Sticker.ALL, moderate_sticker))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        handle_admin_reply))

    logger.info("✝️  Bot Fuera del Templo — activo")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
