import os
import re
import logging
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes, ChatMemberHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")

# ─── PALABRAS PROHIBIDAS ───────────────────────────────────────────────────────
PALABRAS_PROHIBIDAS = [
    # Groserías en español
    "mierda", "puta", "puto", "coño", "joder", "hostia", "cabrón", "cabron",
    "pendejo", "güey", "guey", "chinga", "chingada", "verga", "culero",
    "marica", "maricon", "maricón", "hijueputa", "gonorrea", "hijodeputa",
    "malparido", "hdp", "ptm", "stfu", "wtf",
    # Términos explícitos / adultos
    "porno", "porn", "xxx", "sexo", "sex", "desnudo", "nude", "nudes",
    "onlyfans", "only fans", "webcam", "escort", "prostituta", "prostituto",
    "fornica", "lujuria",
    # Insultos
    "idiota", "imbecil", "imbécil", "estupido", "estúpido", "animal",
    "basura", "inutil", "inútil", "maldito", "maldita",
]

# ─── ESTADO: advertencias por usuario ─────────────────────────────────────────
advertencias: dict[int, int] = {}

MAX_WARNS = 3  # Al llegar a este número → ban

# ─── REGLAS DEL GRUPO ─────────────────────────────────────────────────────────
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

⚠️ El incumplimiento resultará en advertencias y posible expulsión.
"""

BIENVENIDA = """
👋 ¡Bienvenido/a *{nombre}*!

Aquí no hay apariencias ni religión de escaparate — hay relación real, dudas reales y gente imperfecta buscando a Dios de verdad.

La puerta está abierta. Solo pedimos respeto y que lo que compartas construya.

📜 Lee las reglas con /reglas — son pocas pero van en serio.
"""

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def contiene_palabra_prohibida(texto: str) -> bool:
    texto_lower = texto.lower()
    for palabra in PALABRAS_PROHIBIDAS:
        patron = r'\b' + re.escape(palabra) + r'\b'
        if re.search(patron, texto_lower):
            return True
    return False

async def es_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    admins = await update.effective_chat.get_administrators()
    ids_admins = [a.user.id for a in admins]
    return update.effective_user.id in ids_admins

async def aplicar_advertencia(update: Update, context: ContextTypes.DEFAULT_TYPE, razon: str):
    user = update.effective_user
    chat = update.effective_chat
    uid = user.id

    advertencias[uid] = advertencias.get(uid, 0) + 1
    warns = advertencias[uid]

    try:
        await update.message.delete()
    except Exception:
        pass

    if warns >= MAX_WARNS:
        try:
            await context.bot.ban_chat_member(chat.id, uid)
            advertencias.pop(uid, None)
            await context.bot.send_message(
                chat.id,
                f"🚫 *{user.first_name}* ha sido expulsado del grupo por acumular {MAX_WARNS} advertencias.\n\n_{razon}_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error al banear: {e}")
    else:
        restantes = MAX_WARNS - warns
        emoji = "⚠️" if warns == 1 else "🔴"
        await context.bot.send_message(
            chat.id,
            f"{emoji} *Advertencia {warns}/{MAX_WARNS}* para {user.mention_markdown()}\n"
            f"Razón: _{razon}_\n\n"
            f"{'⚠️ Próxima advertencia = expulsión.' if restantes == 1 else f'Te quedan {restantes} advertencias.'}",
            parse_mode="Markdown"
        )

# ─── HANDLERS ─────────────────────────────────────────────────────────────────

async def handle_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    # Ignorar admins
    if await es_admin(update, context):
        return

    msg = update.message

    # 1. Revisar contenido multimedia (fotos, videos, stickers, documentos)
    if msg.photo or msg.video or msg.animation or msg.video_note:
        await aplicar_advertencia(update, context, "Contenido multimedia no permitido en el grupo.")
        return

    if msg.document:
        mime = msg.document.mime_type or ""
        if mime.startswith("image/") or mime.startswith("video/"):
            await aplicar_advertencia(update, context, "Archivo multimedia no permitido.")
            return

    # 2. Revisar texto
    texto = msg.text or msg.caption or ""
    if texto and contiene_palabra_prohibida(texto):
        await aplicar_advertencia(update, context, "Lenguaje inapropiado o contenido no apto.")
        return

    # 3. Revisar links sospechosos
    if msg.entities:
        for entity in msg.entities:
            if entity.type in ["url", "text_link"]:
                url = entity.url or texto[entity.offset:entity.offset + entity.length]
                url_lower = url.lower()
                if any(x in url_lower for x in ["porn", "xxx", "adult", "onlyfans", "nude"]):
                    await aplicar_advertencia(update, context, "Enlace con contenido adulto no permitido.")
                    return

async def bienvenida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.chat_member.new_chat_members if hasattr(update, 'chat_member') else []:
        if not member.is_bot:
            nombre = member.first_name
            await context.bot.send_message(
                update.effective_chat.id,
                BIENVENIDA.format(nombre=nombre),
                parse_mode="Markdown"
            )

async def nuevo_miembro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if not member.is_bot:
                await context.bot.send_message(
                    update.effective_chat.id,
                    BIENVENIDA.format(nombre=member.first_name),
                    parse_mode="Markdown"
                )

# ─── COMANDOS ─────────────────────────────────────────────────────────────────

async def cmd_reglas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(REGLAS, parse_mode="Markdown")

async def cmd_advertencias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Solo admins — ver advertencias de un usuario (responder a su mensaje)"""
    if not await es_admin(update, context):
        return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        warns = advertencias.get(user.id, 0)
        await update.message.reply_text(
            f"⚠️ {user.first_name} tiene *{warns}/{MAX_WARNS}* advertencias.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Responde al mensaje del usuario para ver sus advertencias.")

async def cmd_resetear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Solo admins — resetear advertencias de un usuario"""
    if not await es_admin(update, context):
        return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        advertencias.pop(user.id, None)
        await update.message.reply_text(
            f"✅ Advertencias de *{user.first_name}* han sido reseteadas.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Responde al mensaje del usuario para resetear sus advertencias.")

async def cmd_expulsar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Solo admins — expulsar usuario"""
    if not await es_admin(update, context):
        return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        advertencias.pop(user.id, None)
        await update.message.reply_text(
            f"🚫 *{user.first_name}* ha sido expulsado del grupo.",
            parse_mode="Markdown"
        )

async def cmd_silenciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Solo admins — silenciar usuario por 1 hora"""
    if not await es_admin(update, context):
        return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        from datetime import datetime, timedelta
        hasta = datetime.now() + timedelta(hours=1)
        await context.bot.restrict_chat_member(
            update.effective_chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=hasta
        )
        await update.message.reply_text(
            f"🔇 *{user.first_name}* ha sido silenciado por 1 hora.",
            parse_mode="Markdown"
        )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola, soy el bot moderador de este grupo.\n\n"
        "Estoy aquí para cuidar el espacio — sin apariencias, sin spam, sin faltarle el respeto a nadie.\n\n"
        "Usa /reglas para ver las reglas del grupo."
    )

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        raise ValueError("❌ No se encontró BOT_TOKEN en las variables de entorno.")

    app = Application.builder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reglas", cmd_reglas))
    app.add_handler(CommandHandler("advertencias", cmd_advertencias))
    app.add_handler(CommandHandler("resetear", cmd_resetear))
    app.add_handler(CommandHandler("expulsar", cmd_expulsar))
    app.add_handler(CommandHandler("silenciar", cmd_silenciar))

    # Mensajes
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_mensaje))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, nuevo_miembro))

    logger.info("🤖 Bot iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()
