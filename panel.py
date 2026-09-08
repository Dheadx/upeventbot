from flask import Flask, request, redirect, url_for, render_template_string, session
import sqlite3
import os
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
DB = "aff_posts.db"
TZ = ZoneInfo("Europe/Istanbul")

# Kalıcı güvenli session anahtarı
SECRET_FILE = ".panel_secret"

if os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, "r") as f:
        app.secret_key = f.read().strip()
else:
    secret = secrets.token_hex(32)
    with open(SECRET_FILE, "w") as f:
        f.write(secret)
    app.secret_key = secret


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def init_db():
    conn = db()

    # Mevcut groups tablosunu koru
    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT
        )
    """)

    # Mevcut posts tablosunu koru
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            send_time TEXT NOT NULL,
            sent INTEGER DEFAULT 0,
            status TEXT DEFAULT 'planned'
        )
    """)

    # Eksik kolonları güvenli şekilde ekle
    if not column_exists(conn, "groups", "affiliate_link"):
        conn.execute("ALTER TABLE groups ADD COLUMN affiliate_link TEXT")

    if not column_exists(conn, "posts", "sent_at"):
        conn.execute("ALTER TABLE posts ADD COLUMN sent_at TEXT")

    if not column_exists(conn, "posts", "status"):
        conn.execute("ALTER TABLE posts ADD COLUMN status TEXT DEFAULT 'planned'")

    # Kullanıcılar
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # İşlem geçmişi
    conn.execute("""
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            post_id INTEGER,
            chat_id INTEGER,
            details TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def format_time(value):
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return str(value).replace("T", " ")[:19]


def now_text():
    return datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")


def log_action(username, action, post_id=None, chat_id=None, details=None):
    conn = db()
    conn.execute("""
        INSERT INTO action_log
        (username, action, post_id, chat_id, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        username,
        action,
        post_id,
        chat_id,
        details,
        now_text()
    ))
    conn.commit()
    conn.close()


def logged_in():
    return "user" in session


BASE = """
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UltraPari AFF Panel</title>
<style>
*{box-sizing:border-box}
body{
    margin:0;
    background:#080d17;
    color:#e5e7eb;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
}
.sidebar{
    position:fixed;
    left:0;
    top:0;
    bottom:0;
    width:245px;
    background:#0b1220;
    border-right:1px solid #1e293b;
    padding:28px 18px;
}
.logo{
    font-size:22px;
    font-weight:800;
    padding:0 12px 30px;
}
.logo span{color:#3b82f6}
.nav-title{
    color:#64748b;
    font-size:11px;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:1px;
    padding:14px 12px 8px;
}
.sidebar a{
    display:block;
    color:#94a3b8;
    text-decoration:none;
    padding:12px;
    margin:3px 0;
    border-radius:9px;
    transition:.15s;
}
.sidebar a:hover{
    background:#172033;
    color:#fff;
}
.logout{
    position:absolute;
    bottom:25px;
    left:18px;
    right:18px;
}
.main{
    margin-left:245px;
    padding:35px 42px;
    max-width:1500px;
}
.topbar{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:30px;
}
h1{
    margin:0 0 8px;
    font-size:28px;
}
.subtitle{
    color:#64748b;
    margin-bottom:28px;
}
.cards{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:18px;
    margin-bottom:30px;
}
.card{
    background:#101827;
    border:1px solid #1e293b;
    padding:22px;
    border-radius:14px;
}
.card-label{
    color:#94a3b8;
    font-size:13px;
}
.number{
    font-size:31px;
    font-weight:800;
    margin-top:8px;
}
.box{
    background:#101827;
    border:1px solid #1e293b;
    padding:25px;
    border-radius:14px;
    margin-bottom:22px;
}
.box h2{
    margin-top:0;
}
input,textarea,select{
    width:100%;
    background:#0b1220;
    color:#fff;
    border:1px solid #334155;
    border-radius:8px;
    padding:12px;
    margin:7px 0 18px;
    font-size:14px;
}
textarea{
    min-height:190px;
    resize:vertical;
}
label{
    color:#cbd5e1;
    font-size:13px;
    font-weight:600;
}
button,.btn{
    display:inline-block;
    background:#2563eb;
    color:#fff;
    border:0;
    border-radius:8px;
    padding:11px 18px;
    cursor:pointer;
    text-decoration:none;
    font-size:14px;
    font-weight:600;
}
button:hover,.btn:hover{background:#1d4ed8}
.btn-danger{background:#991b1b}
.btn-danger:hover{background:#b91c1c}
.btn-secondary{
    background:#334155;
}
.btn-secondary:hover{
    background:#475569;
}
.ok{
    background:#052e1b;
    border:1px solid #166534;
    color:#bbf7d0;
    padding:13px 16px;
    border-radius:9px;
    margin-bottom:20px;
}
.err{
    background:#3b0a0a;
    border:1px solid #991b1b;
    color:#fecaca;
    padding:13px 16px;
    border-radius:9px;
    margin-bottom:20px;
}
table{
    width:100%;
    border-collapse:collapse;
}
th{
    color:#64748b;
    font-size:12px;
    text-transform:uppercase;
    text-align:left;
    padding:13px;
    border-bottom:1px solid #334155;
}
td{
    padding:15px 13px;
    border-bottom:1px solid #1e293b;
    vertical-align:top;
}
.badge{
    display:inline-block;
    padding:5px 9px;
    border-radius:20px;
    font-size:12px;
    font-weight:700;
}
.badge-planned{
    background:#172554;
    color:#93c5fd;
}
.badge-sent{
    background:#052e1b;
    color:#86efac;
}
.badge-cancelled{
    background:#3f1d1d;
    color:#fca5a5;
}
.badge-failed{
    background:#451a03;
    color:#fdba74;
}
.muted{
    color:#64748b;
}
.small{
    font-size:12px;
}
.post-text{
    max-width:450px;
    white-space:pre-wrap;
    word-break:break-word;
}
.group-card{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:20px;
    padding:18px;
    border:1px solid #1e293b;
    border-radius:10px;
    margin-bottom:10px;
    background:#0b1220;
}
.link-ok{color:#86efac}
.link-none{color:#64748b}
.checkbox-list{
    display:grid;
    gap:10px;
    margin:10px 0 20px;
}
.checkbox-item{
    background:#0b1220;
    border:1px solid #334155;
    padding:12px;
    border-radius:8px;
}
.checkbox-item input{
    width:auto;
    margin:0 8px 0 0;
}
.login-page{
    min-height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    padding:20px;
}
.login-box{
    width:100%;
    max-width:410px;
    background:#101827;
    border:1px solid #1e293b;
    border-radius:16px;
    padding:35px;
}
.login-logo{
    font-size:25px;
    font-weight:800;
    margin-bottom:8px;
}
.login-logo span{color:#3b82f6}
.login-sub{
    color:#64748b;
    margin-bottom:28px;
}
.user-info{
    color:#64748b;
    font-size:13px;
}
@media(max-width:900px){
    .sidebar{width:190px}
    .main{margin-left:190px;padding:25px}
    .cards{grid-template-columns:repeat(2,1fr)}
}
</style>
</head>
<body>

{% if session.get('user') %}
<div class="sidebar">
    <div class="logo">⚡ Ultra<span>Pari</span></div>

    <div class="nav-title">Yönetim</div>
    <a href="/">📊 Dashboard</a>
    <a href="/new">➕ Yeni Post</a>
    <a href="/planned">📅 Bekleyenler</a>
    <a href="/sent">📤 Gönderilenler</a>

    <div class="nav-title">Sistem</div>
    <a href="/groups">👥 Gruplar & Linkler</a>
    <a href="/history">📜 İşlem Geçmişi</a>
    <a href="/settings">⚙️ Ayarlar</a>

    <div class="logout">
        <div class="user-info">👤 {{session.get('user')}}</div>
        <a href="/logout">🚪 Çıkış Yap</a>
    </div>
</div>
{% endif %}

<div class="{% if session.get('user') %}main{% endif %}">
{{content|safe}}
</div>

</body>
</html>
"""


def page(content, **kwargs):
    return render_template_string(BASE, content=content, **kwargs)


@app.route("/login", methods=["GET", "POST"])
def login():
    conn = db()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if user_count == 0 and request.form.get("first_setup") == "1":
            if len(username) < 3:
                error = "Kullanıcı adı en az 3 karakter olmalı."
            elif len(password) < 6:
                error = "Şifre en az 6 karakter olmalı."
            else:
                conn.execute("""
                    INSERT INTO users(username,password_hash,created_at)
                    VALUES(?,?,?)
                """, (
                    username,
                    generate_password_hash(password),
                    now_text()
                ))
                conn.commit()
                conn.close()

                session["user"] = username
                log_action(username, "İlk yönetici hesabı oluşturuldu")
                return redirect(url_for("home"))

        else:
            user = conn.execute(
                "SELECT * FROM users WHERE username=?",
                (username,)
            ).fetchone()

            if user and check_password_hash(user["password_hash"], password):
                conn.close()
                session["user"] = username
                log_action(username, "Giriş yapıldı")
                return redirect(url_for("home"))

            error = "Kullanıcı adı veya şifre hatalı."

    conn.close()

    setup_text = ""
    if user_count == 0:
        setup_text = """
        <input type="hidden" name="first_setup" value="1">
        <div class="ok">İlk kullanım. Yönetici hesabını şimdi oluştur.</div>
        """

    content = f"""
    <div class="login-page">
        <div class="login-box">
            <div class="login-logo">⚡ Ultra<span>Pari</span></div>
            <div class="login-sub">AFF Yönetim Paneli</div>

            {f'<div class="err">{error}</div>' if error else ''}

            <form method="post">
                {setup_text}

                <label>Kullanıcı adı</label>
                <input type="text" name="username" required autocomplete="username">

                <label>Şifre</label>
                <input type="password" name="password" required autocomplete="current-password">

                <button style="width:100%">🔐 {'Hesap Oluştur' if user_count == 0 else 'Giriş Yap'}</button>
            </form>
        </div>
    </div>
    """

    return render_template_string(BASE, content=content)


@app.route("/logout")
def logout():
    username = session.get("user")
    if username:
        log_action(username, "Çıkış yapıldı")
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def require_login():
    allowed = ["/login", "/static"]
    if request.path not in allowed and not logged_in():
        return redirect(url_for("login"))


@app.route("/")
def home():
    conn = db()

    groups = conn.execute(
        "SELECT COUNT(*) FROM groups"
    ).fetchone()[0]

    planned = conn.execute("""
        SELECT COUNT(*) FROM posts
        WHERE status='planned' AND sent=0
    """).fetchone()[0]

    sent = conn.execute("""
        SELECT COUNT(*) FROM posts
        WHERE status='sent' OR sent=1
    """).fetchone()[0]

    failed = conn.execute("""
        SELECT COUNT(*) FROM posts
        WHERE status='failed'
    """).fetchone()[0]

    recent = conn.execute("""
        SELECT posts.*, groups.title
        FROM posts
        LEFT JOIN groups ON groups.chat_id=posts.chat_id
        ORDER BY posts.id DESC
        LIMIT 8
    """).fetchall()

    conn.close()

    rows = ""
    for p in recent:
        status = p["status"] or "planned"
        badge = {
            "planned": '<span class="badge badge-planned">BEKLEYEN</span>',
            "sent": '<span class="badge badge-sent">GÖNDERİLDİ</span>',
            "cancelled": '<span class="badge badge-cancelled">İPTAL</span>',
            "failed": '<span class="badge badge-failed">HATA</span>'
        }.get(status, status)

        rows += f"""
        <tr>
            <td>{p["title"] or "Bilinmeyen grup"}</td>
            <td class="post-text">{p["text"][:100]}</td>
            <td><strong>{format_time(p["send_time"])}</strong></td>
            <td>{format_time(p["sent_at"])}</td>
            <td>{badge}</td>
        </tr>
        """

    content = f"""
    <div class="topbar">
        <div>
            <h1>Dashboard</h1>
            <div class="subtitle">Telegram AFF paylaşım sisteminin genel görünümü</div>
        </div>
    </div>

    <div class="cards">
        <div class="card">
            <div class="card-label">Telegram Grupları</div>
            <div class="number">{groups}</div>
        </div>
        <div class="card">
            <div class="card-label">Bekleyen Postlar</div>
            <div class="number">{planned}</div>
        </div>
        <div class="card">
            <div class="card-label">Gönderilenler</div>
            <div class="number">{sent}</div>
        </div>
        <div class="card">
            <div class="card-label">Hatalı İşlemler</div>
            <div class="number">{failed}</div>
        </div>
    </div>

    <div class="box">
        <h2>Son İşlemler</h2>
        <table>
            <tr>
                <th>Grup</th>
                <th>Post</th>
                <th>Planlanan Saat</th>
                <th>Gönderim Saati</th>
                <th>Durum</th>
            </tr>
            {rows if rows else '<tr><td colspan="5" class="muted">Henüz işlem yok.</td></tr>'}
        </table>
    </div>

    <a class="btn" href="/new">➕ Yeni Post Oluştur</a>
    """

    return page(content)


@app.route("/groups")
def groups_page():
    conn = db()
    groups = conn.execute("""
        SELECT chat_id,title,affiliate_link
        FROM groups
        ORDER BY title
    """).fetchall()
    conn.close()

    cards = ""

    for g in groups:
        link = g["affiliate_link"]

        if link:
            try:
                from urllib.parse import urlparse
                host = urlparse(link).netloc
                link_info = f'<span class="link-ok">● Affiliate link kayıtlı ({host})</span>'
            except:
                link_info = '<span class="link-ok">● Affiliate link kayıtlı</span>'
        else:
            link_info = '<span class="link-none">● Affiliate link tanımlanmamış</span>'

        cards += f"""
        <div class="group-card">
            <div>
                <strong>{g["title"] or "İsimsiz Grup"}</strong><br>
                <span class="muted small">Chat ID: {g["chat_id"]}</span>
            </div>
            <div>{link_info}</div>
        </div>
        """

    content = f"""
    <h1>👥 Gruplar & Affiliate Linkler</h1>
    <div class="subtitle">
        Her Telegram grubunun affiliate linki bot üzerinden otomatik kullanılır.
    </div>

    <div class="box">
        <h2>Kayıtlı Gruplar</h2>
        {cards if cards else '<p class="muted">Henüz kayıtlı grup yok.</p>'}

        <p class="muted small">
            Affiliate linki panelden değiştirmene gerek yok.
            Telegram grubunda <b>/link</b> komutuyla tanımlanan link otomatik kullanılır.
        </p>
    </div>
    """

    return page(content)


@app.route("/new", methods=["GET", "POST"])
def new_post():
    conn = db()
    groups = conn.execute("""
        SELECT chat_id,title,affiliate_link
        FROM groups
        ORDER BY title
    """).fetchall()
    conn.close()

    message = None
    error = None

    if request.method == "POST":
        chat_ids = request.form.getlist("chat_ids")
        text = request.form.get("text", "").strip()
        send_at = request.form.get("send_at", "").strip()

        if not chat_ids:
            error = "En az bir Telegram grubu seçmelisin."
        elif not text:
            error = "Post metni boş bırakılamaz."
        elif not send_at:
            error = "Gönderim zamanı seçmelisin."
        else:
            try:
                dt = datetime.strptime(send_at, "%Y-%m-%dT%H:%M")
                send_at = dt.strftime("%Y-%m-%dT%H:%M:%S")

                conn = db()
                created_posts = []

                for chat_id in chat_ids:
                    cur = conn.execute("""
                        INSERT INTO posts
                        (chat_id,text,send_time,sent,status)
                        VALUES(?,?,?,0,'planned')
                    """, (
                        int(chat_id),
                        text,
                        send_at
                    ))
                    created_posts.append((cur.lastrowid, int(chat_id)))

                conn.commit()
                conn.close()

                for post_id, chat_id in created_posts:
                    log_action(
                        session["user"],
                        "Post planlandı",
                        post_id,
                        chat_id,
                        f"Gönderim: {send_at}"
                    )

                message = f"✅ Post {len(chat_ids)} grup için planlandı."

            except Exception as e:
                error = f"Post planlanırken hata oluştu: {e}"

    group_options = ""

    for g in groups:
        link_state = "🔗 Link hazır" if g["affiliate_link"] else "⚠️ Link yok"

        group_options += f"""
        <label class="checkbox-item">
            <input type="checkbox" name="chat_ids" value="{g["chat_id"]}">
            <strong>{g["title"] or "İsimsiz Grup"}</strong>
            <span class="muted small"> — {link_state}</span>
        </label>
        """

    content = f"""
    <h1>➕ Yeni Post</h1>
    <div class="subtitle">
        Tek postu birden fazla Telegram grubuna aynı anda planlayabilirsin.
    </div>

    {f'<div class="ok">{message}</div>' if message else ''}
    {f'<div class="err">{error}</div>' if error else ''}

    <div class="box">
        <form method="post">

            <label>Telegram Grupları</label>
            <div class="checkbox-list">
                {group_options if group_options else '<p class="muted">Önce Telegram grubunda /setup kullanmalısın.</p>'}
            </div>

            <label>Post Metni</label>
            <textarea
                name="text"
                placeholder="Gönderilecek postu buraya yaz..."
                required></textarea>

            <p class="muted small">
                💡 Affiliate linkini buraya yazmana gerek yok.
                Bot, seçilen her grubun kayıtlı affiliate linkini otomatik olarak
                <b>🔥 BONUSU AL</b> butonuna bağlar.
            </p>

            <label>Gönderim Zamanı</label>
            <input
                type="datetime-local"
                name="send_at"
                required>

            <button>📅 Postu Planla</button>
        </form>
    </div>
    """

    return page(content)


@app.route("/planned")
def planned():
    conn = db()
    posts = conn.execute("""
        SELECT posts.*, groups.title
        FROM posts
        LEFT JOIN groups ON groups.chat_id=posts.chat_id
        WHERE posts.status='planned' AND posts.sent=0
        ORDER BY posts.send_time ASC
    """).fetchall()
    conn.close()

    rows = ""

    for p in posts:
        rows += f"""
        <tr>
            <td><strong>{p["title"] or "Bilinmeyen grup"}</strong><br>
                <span class="muted small">{p["chat_id"]}</span>
            </td>
            <td class="post-text">{p["text"]}</td>
            <td><strong>{p["send_time"]}</strong></td>
            <td>
                <span class="badge badge-planned">BEKLEYEN</span>
            </td>
            <td>
                <a class="btn btn-danger" href="/cancel/{p["id"]}"
                   onclick="return confirm('Bu post iptal edilsin mi?')">
                   İptal
                </a>
            </td>
        </tr>
        """

    content = f"""
    <h1>📅 Bekleyen Postlar</h1>
    <div class="subtitle">Gönderilmesi beklenen tüm planlı paylaşımlar</div>

    <div class="box">
        <table>
            <tr>
                <th>Grup</th>
                <th>Post</th>
                <th>Planlanan Saat</th>
                <th>Durum</th>
                <th>İşlem</th>
            </tr>
            {rows if rows else '<tr><td colspan="5" class="muted">Bekleyen post yok.</td></tr>'}
        </table>
    </div>
    """

    return page(content)


@app.route("/cancel/<int:post_id>")
def cancel(post_id):
    conn = db()

    post = conn.execute(
        "SELECT * FROM posts WHERE id=?",
        (post_id,)
    ).fetchone()

    if post:
        conn.execute("""
            UPDATE posts
            SET status='cancelled', sent=1
            WHERE id=?
        """, (post_id,))
        conn.commit()

        log_action(
            session["user"],
            "Post iptal edildi",
            post_id,
            post["chat_id"],
            None
        )

    conn.close()
    return redirect(url_for("planned"))


@app.route("/sent")
def sent():
    conn = db()
    posts = conn.execute("""
        SELECT posts.*, groups.title
        FROM posts
        LEFT JOIN groups ON groups.chat_id=posts.chat_id
        WHERE posts.status='sent' OR posts.sent=1
        ORDER BY posts.sent_at DESC, posts.id DESC
    """).fetchall()
    conn.close()

    rows = ""

    for p in posts:
        if p["status"] == "cancelled":
            badge = '<span class="badge badge-cancelled">İPTAL</span>'
        elif p["status"] == "failed":
            badge = '<span class="badge badge-failed">HATA</span>'
        else:
            badge = '<span class="badge badge-sent">GÖNDERİLDİ</span>'

        rows += f"""
        <tr>
            <td><strong>{p["title"] or "Bilinmeyen grup"}</strong></td>
            <td class="post-text">{p["text"]}</td>
            <td><strong>{format_time(p["send_time"])}</strong></td>
            <td>{format_time(p["sent_at"])}</td>
            <td>{badge}</td>
        </tr>
        """

    content = f"""
    <h1>📤 Gönderilenler</h1>
    <div class="subtitle">Tam gönderim zamanı ile birlikte geçmiş paylaşımlar</div>

    <div class="box">
        <table>
            <tr>
                <th>Grup</th>
                <th>Post</th>
                <th>Planlanan</th>
                <th>Gönderilen</th>
                <th>Durum</th>
            </tr>
            {rows if rows else '<tr><td colspan="5" class="muted">Henüz gönderilmiş post yok.</td></tr>'}
        </table>
    </div>
    """

    return page(content)


@app.route("/history")
def history():
    conn = db()
    logs = conn.execute("""
        SELECT *
        FROM action_log
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()
    conn.close()

    rows = ""

    for l in logs:
        rows += f"""
        <tr>
            <td>{l["created_at"]}</td>
            <td>{l["username"] or "BOT"}</td>
            <td>{l["action"]}</td>
            <td>{l["post_id"] or "-"}</td>
            <td>{l["details"] or "-"}</td>
        </tr>
        """

    content = f"""
    <h1>📜 İşlem Geçmişi</h1>
    <div class="subtitle">Panel üzerindeki işlemlerin kayıtları</div>

    <div class="box">
        <table>
            <tr>
                <th>Tarih / Saat</th>
                <th>Kullanıcı</th>
                <th>İşlem</th>
                <th>Post ID</th>
                <th>Detay</th>
            </tr>
            {rows if rows else '<tr><td colspan="5" class="muted">Henüz işlem geçmişi yok.</td></tr>'}
        </table>
    </div>
    """

    return page(content)


@app.route("/settings")
def settings():
    token = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))

    content = f"""
    <h1>⚙️ Ayarlar</h1>
    <div class="subtitle">Sistem ve bağlantı durumu</div>

    <div class="box">
        <h2>Telegram Bot</h2>

        <div class="{'ok' if token else 'err'}">
            {'✅ Telegram bot bağlantı değişkeni mevcut.'
             if token
             else '❌ TELEGRAM_BOT_TOKEN bulunamadı.'}
        </div>

        <p><b>Saat dilimi:</b> Europe/Istanbul</p>
        <p><b>Panel adresi:</b> http://127.0.0.1:5001</p>
        <p><b>Affiliate link yönetimi:</b> Telegram <code>/link</code> komutu</p>
    </div>

    <div class="box">
        <h2>Affiliate Link Sistemi</h2>
        <p class="muted">
            Linkler panelden elle girilmez. Her Telegram grubu kendi affiliate
            linkini bot üzerinden saklar. Yeni post gönderildiğinde sistem
            doğru grubun linkini otomatik olarak <b>🔥 BONUSU AL</b> butonuna bağlar.
        </p>
    </div>
    """

    return page(content)


init_db()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5001,
        debug=True
    )
