import os
import re
import logging
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes, CallbackQueryHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
MAX_WARNS        = 3
HORA_NOCHE       = 22
HORA_DIA         = 6
ZONA_OFFSET      = -5   # Colombia/Perú/Ecuador = -5. Cambia si es otra zona.

# ─── FUNCIONES ACTIVABLES/DESACTIVABLES ───────────────────────────────────────
funciones = {
    "bienvenida":       True,   # Mensaje de bienvenida
    "despedida":        True,   # Mensaje de despedida
    "modo_horario":     True,   # Modo noche/día automático
    "anti_multimedia":  True,   # Bloquear fotos/videos/stickers/GIFs
    "anti_spam":        True,   # Detectar spam
    "anti_reenvios":    True,   # Bloquear mensajes reenviados
    "anti_links":       True,   # Bloquear links bloqueados
    "filtro_palabras":  True,   # Filtro de palabras prohibidas
    "versiculo_diario": False,  # Versículo del día (activar manualmente)
    "cita_reflexion":   False,  # Reflexión al entrar nuevo miembro
}

# ─── PALABRAS PROHIBIDAS ──────────────────────────────────────────────────────
PALABRAS_PROHIBIDAS = [
    "mierda","mrd","puta","put@","puto","put0","coño","joder","hostia",
    "cabrón","cabron","cabr0n","pendejo","pendej@","güey","guey","wey",
    "chinga","chingada","chingad@","verga","verg@","culero","culo","cul0",
    "marica","maricon","maricón","hijueputa","hijodeputa","hp","hdp","h.d.p",
    "gonorrea","malparido","malparid@","ptm","carajo","zorra","zorr@",
    "gilipollas","capullo","boludo","pelotudo","gil","forro",
    "porno","porn","p0rn","xxx","sexo","sex0","s3xo","sexual","sexting",
    "desnudo","desnud@","nude","nudes","n00des","onlyfans","only fans",
    "webcam","cam girl","escort","prostituta","prostituto","fornica",
    "fornicacion","fornicación","lujuria","masturbacion","masturbación",
    "pornhub","xvideos","xnxx","redtube","stripper","burdel",
    "me cago en dios","dios maldito","cristo maldito","maldito dios",
    "cocaina","cocaína","crack","heroina","heroína","marihuana","weed",
    "mota","cannabis","droga","dealer",
    "te voy a matar","muérete","muerate","suicídate","suicidate",
    "idiota","imbecil","imbécil","estupido","estúpido","inutil","inútil",
    "animal","basura","desgraciado","maldito","maldita","tarado","retrasado",
    "gana dinero facil","bitcoin gratis","crypto gratis","te hago rico",
]

DOMINIOS_BLOQUEADOS = [
    "porn","xxx","adult","onlyfans","nude","sex","xvideos","pornhub",
    "xnxx","redtube","youporn","brazzers","cam4","chaturbate",
]

VERSICULOS = [
    "\"Porque yo sé los planes que tengo para ustedes, planes de bienestar y no de calamidad, para darles un futuro y una esperanza.\" — Jer 29:11",
    "\"Todo lo puedo en Cristo que me fortalece.\" — Fil 4:13",
    "\"El Señor es mi pastor, nada me falta.\" — Sal 23:1",
    "\"Confía en el Señor con todo tu corazón, y no te apoyes en tu propia prudencia.\" — Prov 3:5",
    "\"Porque tanto amó Dios al mundo que dio a su Hijo único.\" — Juan 3:16",
    "\"Busquen primero el reino de Dios y su justicia, y todas estas cosas les serán añadidas.\" — Mat 6:33",
    "\"Sean fuertes y valientes. No teman ni se asusten, porque el Señor su Dios estará con ustedes dondequiera que vayan.\" — Jos 1:9",
    "\"El amor es paciente, es bondadoso... todo lo soporta.\" — 1 Cor 13:4-7",
    "\"Vengan a mí todos ustedes que están cansados y agobiados, y yo les daré descanso.\" — Mat 11:28",
    "\"No se amolden al mundo actual, sino sean transformados mediante la renovación de su mente.\" — Rom 12:2",
]

REFLEXIONES_BIENVENIDA = [
    "Recuerda: no vine a juzgarte, vine a caminar contigo. 🙏",
    "Aquí todos estamos en proceso. Nadie llegó terminado. 💪",
    "La fe no es tener todas las respuestas, es confiar igual. 🔥",
    "Eres bienvenido/a tal como eres. Dios te acepta, nosotros también. ❤️",
    "Aquí se habla sin filtros de religión, pero con mucho amor. 🕊️",
]

# ─── ESTADO ───────────────────────────────────────────────────────────────────
advertencias: dict[int, int] = {}
modo_noche_activo = False
spam_tracker: dict[int, list] = {}
grupo_chat_id: int | None = None

# ─── TEXTOS ───────────────────────────────────────────────────────────────────
REGLAS = """
📜 *REGLAS DEL GRUPO*

1️⃣ *Aquí no hay religión, hay relación.*
Nada de rituales vacíos ni apariencias. Si vienes a aparentar santidad, estás en el lugar equivocado.

2️⃣ *La puerta está abierta para todos.*
Dudas, caídas, preguntas incómodas, crisis de fe — todo cabe. No juzgamos el punto de partida de nadie.

3️⃣ *La Palabra manda, no las opiniones.*
Los debates son bienvenidos, pero la Biblia es la autoridad. No imponemos doctrinas humanas.

4️⃣ *Respeto absoluto.*
Puedes no estar de acuerdo. No puedes faltar el respeto. Diferencia enorme.

5️⃣ *Nada de spam, ventas ni cadenas.*
Fuera del templo no significa fuera del orden. Cero publicidad, cero mensajes reenviados sin sentido.

6️⃣ *Comparte lo que edifica.*
Testimonios, reflexiones, preguntas reales. Si no construye, no va aquí.

7️⃣ *La hipocresía no tiene lugar.*
Somos imperfectos y lo sabemos. Pero la doble vida y la falsedad no se toleran.

8️⃣ *Los admins tienen la última palabra.*
No como autoridad religiosa — sino como guardianes del espacio.

⚠️ 3 advertencias = expulsión automática.
"""

def mensaje_bienvenida(nombre: str, username: str | None) -> str:
    import random
    reflexion = random.choice(REFLEXIONES_BIENVENIDA)
    user_str = f"@{username}" if username else nombre
    return (
        f"🔥 ¡Ey, ey, ey! Bienvenido/a *{nombre}* ({user_str}) 👋\n\n"
        f"Este no es un grupo de perfectos — es un grupo de reales.\n"
        f"Gente que tropieza, se levanta y sigue creyendo. Eso somos.\n\n"
        f"_{reflexion}_\n\n"
        f"📜 Antes de arrancar, dale una leída a las reglas:\n\n"
        + REGLAS +
        f"\n¡Que Dios te bendiga y bienvenido/a a la familia! 🙌"
    )

def mensaje_despedida(nombre: str, username: str | None) -> str:
    user_str = f"@{username}" if username else nombre
    return (
        f"👋 *{nombre}* ({user_str}) ha salido del grupo.\n\n"
        f"_\"El Señor te bendiga y te guarde; el Señor haga resplandecer su rostro sobre ti.\"_ — Núm 6:24-25\n\n"
        f"Que Dios te lleve bien, hermano/a. Las puertas siguen abiertas. 🕊️"
    )

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def hora_local() -> int:
    return (datetime.utcnow() + timedelta(hours=ZONA_OFFSET)).hour

def normalizar(texto: str) -> str:
    return texto.lower().replace("@","a").replace("0","o").replace("3","e").replace("1","i").replace("+","")

def contiene_palabra_prohibida(texto: str) -> bool:
    t = normalizar(texto)
    for p in PALABRAS_PROHIBIDAS:
        if re.search(r'\b' + re.escape(p) + r'\b', t):
            return True
    return False

def contiene_link_bloqueado(texto: str) -> bool:
    return any(d in texto.lower() for d in DOMINIOS_BLOQUEADOS)

def es_spam(uid: int) -> bool:
    ahora = datetime.utcnow()
    spam_tracker.setdefault(uid, [])
    spam_tracker[uid] = [t for t in spam_tracker[uid] if (ahora-t).seconds < 10]
    spam_tracker[uid].append(ahora)
    return len(spam_tracker[uid]) >= 6

async def es_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        admins = await update.effective_chat.get_administrators()
        return update.effective_user.id in [a.user.id for a in admins]
    except:
        return False

async def aplicar_advertencia(update: Update, context: ContextTypes.DEFAULT_TYPE, razon: str):
    user = update.effective_user
    chat = update.effective_chat
    uid  = user.id

    advertencias[uid] = advertencias.get(uid, 0) + 1
    warns = advertencias[uid]

    try:
        await update.message.delete()
    except:
        pass

    if warns >= MAX_WARNS:
        try:
            await context.bot.ban_chat_member(chat.id, uid)
            advertencias.pop(uid, None)
            await context.bot.send_message(
                chat.id,
                f"🚫 *{user.first_name}* fue expulsado por acumular {MAX_WARNS} advertencias.\n_Motivo: {razon}_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ban error: {e}")
    else:
        restantes = MAX_WARNS - warns
        await context.bot.send_message(
            chat.id,
            f"{'⚠️' if warns==1 else '🔴'} *Advertencia {warns}/{MAX_WARNS}* — {user.mention_markdown()}\n"
            f"Motivo: _{razon}_\n\n"
            f"{'🚨 *Una más y serás expulsado.*' if restantes==1 else f'Te quedan {restantes} advertencias.'}",
            parse_mode="Markdown"
        )

async def silenciar_grupo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    global modo_noche_activo
    try:
        await context.bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
        await context.bot.send_message(
            chat_id,
            "🌙 *Modo noche activado* — El grupo descansa hasta las 6:00 AM.\n"
            "_\"En paz me acostaré y así también dormiré.\"_ — Sal 4:8 🙏",
            parse_mode="Markdown"
        )
        modo_noche_activo = True
    except Exception as e:
        logger.error(f"Error silenciando: {e}")

async def activar_grupo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    global modo_noche_activo
    try:
        await context.bot.set_chat_permissions(
            chat_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=False,
                can_send_polls=True,
                can_send_other_messages=False,
                can_add_web_page_previews=True,
            )
        )
        import random
        versiculo = random.choice(VERSICULOS)
        await context.bot.send_message(
            chat_id,
            f"☀️ *Buenos días, familia* — El grupo está activo.\n\n"
            f"📖 _{versiculo}_",
            parse_mode="Markdown"
        )
        modo_noche_activo = False
    except Exception as e:
        logger.error(f"Error activando: {e}")

# ─── TAREA HORARIA ────────────────────────────────────────────────────────────

async def revisar_horario(context: ContextTypes.DEFAULT_TYPE):
    if not funciones["modo_horario"] or not grupo_chat_id:
        return
    hora = hora_local()
    if (hora >= HORA_NOCHE or hora < HORA_DIA) and not modo_noche_activo:
        await silenciar_grupo(context, grupo_chat_id)
    elif HORA_DIA <= hora < HORA_NOCHE and modo_noche_activo:
        await activar_grupo(context, grupo_chat_id)

# ─── HANDLERS ─────────────────────────────────────────────────────────────────

async def nuevo_miembro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global grupo_chat_id
    grupo_chat_id = update.effective_chat.id
    if not update.message or not update.message.new_chat_members:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        if funciones["bienvenida"]:
            await context.bot.send_message(
                update.effective_chat.id,
                mensaje_bienvenida(member.first_name, member.username),
                parse_mode="Markdown"
            )

async def miembro_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return
    member = update.message.left_chat_member
    if member.is_bot:
        return
    if funciones["despedida"]:
        await context.bot.send_message(
            update.effective_chat.id,
            mensaje_despedida(member.first_name, member.username),
            parse_mode="Markdown"
        )

async def handle_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global grupo_chat_id
    if not update.message or not update.effective_user:
        return
    grupo_chat_id = update.effective_chat.id
    if await es_admin(update, context):
        return

    msg = update.message

    if funciones["anti_multimedia"]:
        if msg.photo or msg.video or msg.animation or msg.video_note or msg.sticker:
            await aplicar_advertencia(update, context, "Imágenes, videos, GIFs y stickers no están permitidos.")
            return
        if msg.document:
            mime = msg.document.mime_type or ""
            if mime.startswith("image/") or mime.startswith("video/"):
                await aplicar_advertencia(update, context, "Archivos multimedia no permitidos.")
                return

    if funciones["anti_spam"] and es_spam(update.effective_user.id):
        await aplicar_advertencia(update, context, "Spam — demasiados mensajes seguidos.")
        return

    if funciones["anti_reenvios"]:
        if msg.forward_date or msg.forward_from or msg.forward_from_chat:
            await aplicar_advertencia(update, context, "No se permiten mensajes reenviados ni cadenas.")
            return

    texto = msg.text or msg.caption or ""
    if texto:
        if funciones["filtro_palabras"] and contiene_palabra_prohibida(texto):
            await aplicar_advertencia(update, context, "Lenguaje inapropiado detectado.")
            return
        if funciones["anti_links"] and contiene_link_bloqueado(texto):
            await aplicar_advertencia(update, context, "Enlace con contenido no permitido.")
            return

    if funciones["anti_links"] and msg.entities:
        for entity in msg.entities:
            if entity.type in ["url", "text_link"]:
                url = (entity.url or texto[entity.offset:entity.offset+entity.length] or "").lower()
                if contiene_link_bloqueado(url):
                    await aplicar_advertencia(update, context, "Enlace bloqueado detectado.")
                    return

# ─── PANEL DE CONTROL ─────────────────────────────────────────────────────────

NOMBRES_FUNCIONES = {
    "bienvenida":       "👋 Bienvenida",
    "despedida":        "🕊️ Despedida",
    "modo_horario":     "🌙 Modo noche/día",
    "anti_multimedia":  "🖼️ Anti-multimedia",
    "anti_spam":        "⚡ Anti-spam",
    "anti_reenvios":    "🔁 Anti-reenvíos",
    "anti_links":       "🔗 Anti-links",
    "filtro_palabras":  "🤬 Filtro palabras",
    "versiculo_diario": "📖 Versículo diario",
    "cita_reflexion":   "✨ Reflexión entrada",
}

def teclado_panel():
    botones = []
    for key, nombre in NOMBRES_FUNCIONES.items():
        estado = "✅" if funciones[key] else "❌"
        botones.append([InlineKeyboardButton(f"{estado} {nombre}", callback_data=f"toggle_{key}")])
    botones.append([InlineKeyboardButton("🔄 Actualizar", callback_data="refresh_panel")])
    return InlineKeyboardMarkup(botones)

async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        await update.message.reply_text("⛔ Solo los admins pueden usar el panel.")
        return
    await update.message.reply_text(
        "⚙️ *Panel de Control del Bot*\n\nToca una función para activarla o desactivarla:",
        reply_markup=teclado_panel(),
        parse_mode="Markdown"
    )

async def handle_boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "refresh_panel":
        await query.edit_message_reply_markup(reply_markup=teclado_panel())
        return

    if query.data.startswith("toggle_"):
        key = query.data.replace("toggle_", "")
        if key in funciones:
            funciones[key] = not funciones[key]
            estado = "activada ✅" if funciones[key] else "desactivada ❌"
            nombre = NOMBRES_FUNCIONES.get(key, key)
            await query.edit_message_text(
                f"⚙️ *Panel de Control del Bot*\n\n"
                f"_{nombre}_ fue *{estado}*\n\n"
                f"Toca una función para activarla o desactivarla:",
                reply_markup=teclado_panel(),
                parse_mode="Markdown"
            )

# ─── COMANDOS ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global grupo_chat_id
    grupo_chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name("horario")
    if not jobs:
        context.job_queue.run_repeating(revisar_horario, interval=60, first=10, name="horario")
    await update.message.reply_text(
        "🤖 *Bot moderador activo y listo.*\n\n"
        "Estoy vigilando el espacio — sin spam, sin contenido inapropiado, con amor pero con orden.\n\n"
        "⚙️ Usa /panel para ver y controlar todas las funciones.\n"
        "📜 Usa /reglas para ver las reglas del grupo.",
        parse_mode="Markdown"
    )

async def cmd_reglas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(REGLAS, parse_mode="Markdown")

async def cmd_versiculo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import random
    await update.message.reply_text(
        f"📖 *Versículo del día*\n\n_{random.choice(VERSICULOS)}_",
        parse_mode="Markdown"
    )

async def cmd_noche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    await silenciar_grupo(context, update.effective_chat.id)

async def cmd_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    await activar_grupo(context, update.effective_chat.id)

async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    hora = hora_local()
    estado = "🌙 Modo noche" if modo_noche_activo else "☀️ Modo día"
    activas = sum(1 for v in funciones.values() if v)
    await update.message.reply_text(
        f"📊 *Estado del bot*\n\n"
        f"Hora local: {hora}:00\n"
        f"Grupo: {estado}\n"
        f"Funciones activas: {activas}/{len(funciones)}\n\n"
        f"Usa /panel para gestionar las funciones.",
        parse_mode="Markdown"
    )

async def cmd_advertencias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        warns = advertencias.get(user.id, 0)
        await update.message.reply_text(
            f"⚠️ *{user.first_name}* tiene *{warns}/{MAX_WARNS}* advertencias.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Responde al mensaje del usuario para ver sus advertencias.")

async def cmd_resetear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        advertencias.pop(user.id, None)
        await update.message.reply_text(f"✅ Advertencias de *{user.first_name}* reseteadas.", parse_mode="Markdown")

async def cmd_expulsar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        advertencias.pop(user.id, None)
        await update.message.reply_text(f"🚫 *{user.first_name}* expulsado.", parse_mode="Markdown")

async def cmd_silenciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        hasta = datetime.utcnow() + timedelta(hours=1)
        await context.bot.restrict_chat_member(
            update.effective_chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=hasta
        )
        await update.message.reply_text(f"🔇 *{user.first_name}* silenciado por 1 hora.", parse_mode="Markdown")

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Comandos disponibles*\n\n"
        "Para todos:\n"
        "/reglas — Ver las reglas del grupo\n"
        "/versiculo — Versículo del día\n\n"
        "Solo admins:\n"
        "/panel — Panel de control del bot\n"
        "/estado — Ver estado del bot\n"
        "/noche — Activar modo noche manualmente\n"
        "/dia — Activar modo día manualmente\n"
        "/advertencias — Ver advertencias de un usuario\n"
        "/resetear — Resetear advertencias de un usuario\n"
        "/silenciar — Silenciar usuario 1 hora\n"
        "/expulsar — Expulsar usuario",
        parse_mode="Markdown"
    )

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        raise ValueError("❌ No se encontró BOT_TOKEN en las variables de entorno.")

    app = Application.builder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start",         cmd_start))
    app.add_handler(CommandHandler("reglas",        cmd_reglas))
    app.add_handler(CommandHandler("panel",         cmd_panel))
    app.add_handler(CommandHandler("estado",        cmd_estado))
    app.add_handler(CommandHandler("ayuda",         cmd_ayuda))
    app.add_handler(CommandHandler("versiculo",     cmd_versiculo))
    app.add_handler(CommandHandler("noche",         cmd_noche))
    app.add_handler(CommandHandler("dia",           cmd_dia))
    app.add_handler(CommandHandler("advertencias",  cmd_advertencias))
    app.add_handler(CommandHandler("resetear",      cmd_resetear))
    app.add_handler(CommandHandler("expulsar",      cmd_expulsar))
    app.add_handler(CommandHandler("silenciar",     cmd_silenciar))

    # Botones del panel
    app.add_handler(CallbackQueryHandler(handle_boton))

    # Eventos de miembros
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, nuevo_miembro))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, miembro_sale))

    # Mensajes
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_mensaje))

    logger.info("🤖 Bot iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()
