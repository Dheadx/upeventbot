import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TZ = ZoneInfo("Europe/Istanbul")


def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL eksik")
    return psycopg.connect(DATABASE_URL)


def init_db():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id BIGINT PRIMARY KEY,
                    title TEXT NOT NULL,
                    affiliate_link TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id BIGSERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    text TEXT NOT NULL,
                    send_time TEXT NOT NULL,
                    sent INTEGER DEFAULT 0,
                    sent_at TEXT,
                    status TEXT DEFAULT 'planned'
                )
            """)

            cur.execute("""
                ALTER TABLE groups
                ADD COLUMN IF NOT EXISTS affiliate_link TEXT
            """)

            cur.execute("""
                ALTER TABLE posts
                ADD COLUMN IF NOT EXISTS sent_at TEXT
            """)

            cur.execute("""
                ALTER TABLE posts
                ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'planned'
            """)


async def start(update, context):
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


async def my_id(update, context):
    await update.message.reply_text(
        f"Telegram ID'n:\n\n{update.effective_user.id}"
    )


async def setup(update, context):
    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "❌ /setup komutunu bir Telegram grubunda kullan."
        )
        return

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO groups (chat_id, title)
                VALUES (%s, %s)
                ON CONFLICT (chat_id)
                DO UPDATE SET title = EXCLUDED.title
            """, (chat.id, chat.title))

    await update.message.reply_text(
        f"✅ Grup kaydedildi!\n\n"
        f"Grup: {chat.title}\n"
        f"ID: {chat.id}\n\n"
        f"Artık bu gruba post planlayabilirsin."
    )


async def set_link(update, context):
    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "❌ /link komutunu Telegram grubunda kullan."
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Kullanım:\n"
            "/link https://partner-link.com/xxxxx"
        )
        return

    link = context.args[0].strip()

    if not link.startswith(("http://", "https://")):
        await update.message.reply_text(
            "❌ Geçerli bir link gir."
        )
        return

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title FROM groups WHERE chat_id = %s",
                (chat.id,)
            )
            row = cur.fetchone()

            if not row:
                await update.message.reply_text(
                    "❌ Bu grup henüz kayıtlı değil. "
                    "Önce /setup kullan."
                )
                return

            cur.execute(
                """
                UPDATE groups
                SET affiliate_link = %s
                WHERE chat_id = %s
                """,
                (link, chat.id)
            )

    await update.message.reply_text(
        f"✅ Affiliate link kaydedildi!\n\n"
        f"Grup: {row[0]}\n"
        f"Link: {link}"
    )


async def add_post(update, context):
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

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO posts
                    (chat_id, text, send_time, sent, status)
                VALUES
                    (%s, %s, %s, 0, 'planned')
                RETURNING id
                """,
                (
                    chat.id,
                    text,
                    send_time.isoformat()
                )
            )

            post_id = cur.fetchone()[0]

    await update.message.reply_text(
        f"✅ POST PLANLANDI\n\n"
        f"ID: {post_id}\n"
        f"📅 {send_time.strftime('%d.%m.%Y')}\n"
        f"⏰ {send_time.strftime('%H:%M')}\n\n"
        f"📝 {text}"
    )


async def posts(update, context):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, chat_id, text, send_time
                FROM posts
                WHERE sent = 0
                  AND status = 'planned'
                ORDER BY send_time, id
            """)

            rows = cur.fetchall()

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


async def cancel_post(update, context):
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

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM posts
                WHERE id = %s
                  AND sent = 0
                """,
                (post_id,)
            )

            deleted = cur.rowcount

    if deleted:
        await update.message.reply_text(
            f"🗑 Post {post_id} iptal edildi."
        )
    else:
        await update.message.reply_text(
            "❌ Bu ID'ye ait planlanmış post bulunamadı."
        )


def claim_post():
    """
    Aynı postun iki ayrı scheduler tarafından
    aynı anda gönderilmesini engeller.
    """

    now = datetime.now(TZ).isoformat()

    with db() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    p.id,
                    p.chat_id,
                    p.text,
                    g.affiliate_link
                FROM posts p
                LEFT JOIN groups g
                    ON g.chat_id = p.chat_id
                WHERE p.sent = 0
                  AND p.status = 'planned'
                  AND p.send_time <= %s
                ORDER BY p.send_time, p.id
                LIMIT 1
                FOR UPDATE OF p SKIP LOCKED
            """, (now,))

            row = cur.fetchone()

            if not row:
                return None

            post_id, chat_id, text, affiliate_link = row

            cur.execute("""
                UPDATE posts
                SET sent = 2,
                    status = 'sending'
                WHERE id = %s
            """, (post_id,))

            return post_id, chat_id, text, affiliate_link


def mark_sent(post_id):
    sent_at = datetime.now(TZ).isoformat()

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE posts
                SET sent = 1,
                    status = 'sent',
                    sent_at = %s
                WHERE id = %s
            """, (sent_at, post_id))


def mark_failed(post_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE posts
                SET sent = 0,
                    status = 'planned'
                WHERE id = %s
            """, (post_id,))


async def scheduler(bot):
    while True:
        try:
            while True:
                claimed = claim_post()

                if not claimed:
                    break

                post_id, chat_id, text, affiliate_link = claimed

                try:
                    text = text.replace("{LINK}", "").strip()

                    reply_markup = None

                    if affiliate_link:
                        reply_markup = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    "🔥 BONUSU AL",
                                    url=affiliate_link
                                )
                            ]
                        ])

                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=reply_markup
                    )

                    mark_sent(post_id)

                    print(
                        f"POST GÖNDERİLDİ: {post_id}"
                    )

                except Exception as e:
                    mark_failed(post_id)

                    print(
                        f"Post gönderilemedi "
                        f"{post_id}: {e}"
                    )

        except Exception as e:
            print(
                "Scheduler hatası:",
                e
            )

        await asyncio.sleep(10)


async def main():
    init_db()

    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN bulunamadı"
        )

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL bulunamadı"
        )

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

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
