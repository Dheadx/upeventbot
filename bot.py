import asyncio
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# AYARLAR
# =========================================================

TOKEN = "8953491566:AAF7d-i31x09g52ZUyOLy1hEKABofwfpcHk"

# Türkiye saati
TZ = ZoneInfo("Europe/Istanbul")

DB = "aff_posts.db"


# =========================================================
# VERİTABANI
# =========================================================

def init_db():
    conn = sqlite3.connect(DB)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            send_time TEXT NOT NULL,
            sent INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# /start
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 AFF Post Manager aktif!\n\n"
        "Komutlar:\n"
        "/setup - Bu grubu tanıt\n"
        "/link URL - Affiliate linkini kaydet\n"
        "/post - Post planla\n"
        "/posts - Planlanan postları göster\n"
        "/cancel ID - Postu iptal et\n"
        "/id - Telegram ID'ni göster"
    )


# =========================================================
# TELEGRAM ID
# =========================================================

async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        f"Telegram ID'n:\n\n{update.effective_user.id}"
    )


# =========================================================
# GRUP KAYDET
# =========================================================

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "❌ /setup komutunu bir Telegram grubunda kullan."
        )
        return

    conn = sqlite3.connect(DB)

    conn.execute(
        "INSERT OR REPLACE INTO groups (chat_id, title) VALUES (?, ?)",
        (chat.id, chat.title)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Grup kaydedildi!\n\n"
        f"Grup: {chat.title}\n"
        f"ID: {chat.id}\n\n"
        f"Artık bu gruba post planlayabilirsin."
    )


# =========================================================
# AFFILIATE LINK KAYDET
# Kullanım:
# /link https://ornek.com/partner-link
# =========================================================

async def set_link(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "❌ /link komutunu Telegram grubunda kullan."
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Kullanım:\n/link https://partner-link.com/xxxxx"
        )
        return

    link = context.args[0].strip()

    if not link.startswith(("http://", "https://")):
        await update.message.reply_text(
            "❌ Geçerli bir link gir."
        )
        return

    conn = sqlite3.connect(DB)

    conn.execute(
        "UPDATE groups SET affiliate_link = ? WHERE chat_id = ?",
        (link, chat.id)
    )

    conn.commit()

    row = conn.execute(
        "SELECT title FROM groups WHERE chat_id = ?",
        (chat.id,)
    ).fetchone()

    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ Bu grup henüz kayıtlı değil. Önce /setup kullan."
        )
        return

    await update.message.reply_text(
        f"✅ Affiliate link kaydedildi!\n\n"
        f"Grup: {row[0]}\n"
        f"Link: {link}"
    )


# =========================================================
# POST PLANLA
#
# Kullanım:
# /post 04.09.2026 18:30 Mesaj burada
# =========================================================

async def add_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "❌ Şimdilik /post komutunu grup içerisinde kullan."
        )
        return

    if len(context.args) < 4:
        await update.message.reply_text(
            "❌ Kullanım:\n\n"
            "/post 04.09.2026 18:30 Mesajınız burada"
        )
        return

    date_str = context.args[0]
    time_str = context.args[1]
    text = " ".join(context.args[2:])

    try:
        send_time = datetime.strptime(
            f"{date_str} {time_str}",
            "%d.%m.%Y %H:%M"
        ).replace(tzinfo=TZ)

    except ValueError:
        await update.message.reply_text(
            "❌ Tarih formatı yanlış.\n\n"
            "Örnek:\n"
            "/post 04.09.2026 18:30 Merhaba arkadaşlar!"
        )
        return

    if send_time <= datetime.now(TZ):
        await update.message.reply_text(
            "❌ Bu saat geçmişte kalmış."
        )
        return

    conn = sqlite3.connect(DB)

    cursor = conn.execute(
        """
        INSERT INTO posts (chat_id, text, send_time)
        VALUES (?, ?, ?)
        """,
        (
            chat.id,
            text,
            send_time.isoformat()
        )
    )

    post_id = cursor.lastrowid

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ POST PLANLANDI\n\n"
        f"ID: {post_id}\n"
        f"📅 {send_time.strftime('%d.%m.%Y')}\n"
        f"⏰ {send_time.strftime('%H:%M')}\n\n"
        f"📝 {text}"
    )


# =========================================================
# PLANLANAN POSTLAR
# =========================================================

async def posts(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn = sqlite3.connect(DB)

    rows = conn.execute(
        """
        SELECT id, chat_id, text, send_time
        FROM posts
        WHERE sent = 0
        ORDER BY send_time
        """
    ).fetchall()

    conn.close()

    if not rows:
        await update.message.reply_text(
            "📭 Planlanmış post bulunmuyor."
        )
        return

    message = "📅 PLANLANAN POSTLAR\n\n"

    for post_id, chat_id, text, send_time in rows:

        dt = datetime.fromisoformat(send_time)

        message += (
            f"🆔 ID: {post_id}\n"
            f"📅 {dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"📝 {text[:100]}\n\n"
        )

    await update.message.reply_text(message)


# =========================================================
# POST İPTAL
# =========================================================

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if len(context.args) != 1:
        await update.message.reply_text(
            "Kullanım:\n/cancel POST_ID"
        )
        return

    try:
        post_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Post ID sayı olmalı."
        )
        return

    conn = sqlite3.connect(DB)

    cursor = conn.execute(
        """
        DELETE FROM posts
        WHERE id = ? AND sent = 0
        """,
        (post_id,)
    )

    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted:
        await update.message.reply_text(
            f"🗑 Post {post_id} iptal edildi."
        )
    else:
        await update.message.reply_text(
            "❌ Bu ID'ye ait planlanmış post bulunamadı."
        )


# =========================================================
# ZAMANLAYICI
# =========================================================

async def scheduler(bot):

    while True:

        try:

            now = datetime.now(TZ)

            conn = sqlite3.connect(DB)

            rows = conn.execute(
                """
                SELECT id, chat_id, text
                FROM posts
                WHERE sent = 0
                AND send_time <= ?
                ORDER BY send_time
                """,
                (now.isoformat(),)
            ).fetchall()

            for post_id, chat_id, text in rows:

                try:

                    group = conn.execute(
                        "SELECT affiliate_link FROM groups WHERE chat_id = ?",
                        (chat_id,)
                    ).fetchone()

                    affiliate_link = group[0] if group and group[0] else ""

                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                    text = text.replace("{LINK}", "").strip()

                    reply_markup = None

                    if affiliate_link:
                        reply_markup = InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                "🔥 BONUSU AL",
                                url=affiliate_link
                            )]
                        ])

                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=reply_markup
                    )

                    conn.execute(
                        "UPDATE posts SET sent = 1 WHERE id = ?",
                        (post_id,)
                    )

                    conn.commit()

                    print(
                        f"POST GÖNDERİLDİ: {post_id}"
                    )

                except Exception as e:

                    print(
                        f"Post gönderilemedi {post_id}: {e}"
                    )

            conn.close()

        except Exception as e:

            print("Scheduler hatası:", e)

        await asyncio.sleep(10)


# =========================================================
# BOTU BAŞLAT
# =========================================================

async def main():

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("id", my_id)
    )

    app.add_handler(
        CommandHandler("setup", setup)
    )

    app.add_handler(
        CommandHandler("link", set_link)
    )

    app.add_handler(
        CommandHandler("post", add_post)
    )

    app.add_handler(
        CommandHandler("posts", posts)
    )

    app.add_handler(
        CommandHandler("cancel", cancel_post)
    )

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    print("🤖 AFF POST BOT ÇALIŞIYOR")

    asyncio.create_task(
        scheduler(app.bot)
    )

    try:
        await asyncio.Event().wait()

    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())