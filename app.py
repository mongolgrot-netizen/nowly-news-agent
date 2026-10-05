import os, html, threading
from flask import Flask, request, jsonify
import requests, feedparser

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_CHAT_ID", "")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@NOWLY")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")

RSS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews",
]

def tg(method, data):
    if not TOKEN:
        return None
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data, timeout=30)
    return r.json()

def setup_webhook():
    if not TOKEN or not WEBHOOK_URL:
        return
    try:
        result = tg("setWebhook", {"url": WEBHOOK_URL + "/telegram/webhook"})
        print("Telegram webhook:", result)
    except Exception as e:
        print("Webhook setup error:", e)

def send(chat, text, buttons=None):
    data = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "false"}
    if buttons:
        import json
        data["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    return tg("sendMessage", data)

def fetch_news(limit=8):
    items = []
    for url in RSS:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:6]:
                title = html.unescape(e.get("title", ""))
                link = e.get("link", "")
                if title and link:
                    items.append((title, link))
        except Exception:
            pass
    seen = set()
    out = []
    for x in items:
        k = x[0].lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out[:limit]

def ai_post(title, link):
    prompt = f'''Ты редактор Telegram-канала NOWLY. Сделай короткий новостной пост на русском по материалу.
Заголовок: {title}
Источник: {link}
Не выдумывай факты. 2-4 коротких абзаца, заголовок с эмодзи, нейтральный тон. В конце: Источник: <ссылка>.'''
    if not GROQ_KEY:
        return f"📰 <b>{html.escape(title)}</b>\n\nПодробнее: {link}"
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
        timeout=45
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def process_news(chat):
    items = fetch_news()
    if not items:
        send(chat, "⚠️ Не удалось получить новости. Попробуй ещё раз через минуту.")
        return
    send(chat, "⚡ <b>NOWLY: собираю свежие новости...</b>")
    for title, link in items[:5]:
        try:
            post = ai_post(title, link)
        except Exception:
            post = f"📰 <b>{html.escape(title)}</b>\n\n{link}\n\n⚠️ AI пока не обработал материал."
        buttons = [[
            {"text": "✅ Опубликовать", "callback_data": "pub:" + link[:180]},
            {"text": "❌ Отклонить", "callback_data": "no"}
        ]]
        send(chat, post, buttons)

def handle_update(u):
    if "message" in u:
        m = u["message"]
        chat = m["chat"]["id"]
        text = m.get("text", "")
        if ADMIN_ID and str(chat) != str(ADMIN_ID):
            return
        if text.startswith("/start"):
            send(chat, "⚡ <b>NOWLY AI EDITOR</b>\n\n/news — собрать свежие новости\n/status — проверить работу бота")
        elif text.startswith("/news"):
            threading.Thread(target=process_news, args=(chat,), daemon=True).start()
        elif text.startswith("/status"):
            send(chat, "🟢 NOWLY AI Editor работает.")
    elif "callback_query" in u:
        q = u["callback_query"]
        chat = q["message"]["chat"]["id"]
        if ADMIN_ID and str(chat) != str(ADMIN_ID):
            return
        if q["data"].startswith("pub:"):
            text = q["message"]["text"]
            result = tg("sendMessage", {
                "chat_id": CHANNEL,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "false"
            })
            if result and result.get("ok"):
                tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Опубликовано в NOWLY"})
            else:
                tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Ошибка публикации"})
        else:
            tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Отклонено"})
            try:
                tg("editMessageReplyMarkup", {
                    "chat_id": chat,
                    "message_id": q["message"]["message_id"],
                    "reply_markup": '{"inline_keyboard":[]}'
                })
            except Exception:
                pass

@app.get("/")
def health():
    return jsonify({"status": "online", "service": "NOWLY AI Editor"})

@app.post("/telegram/webhook")
def webhook():
    handle_update(request.get_json(force=True))
    return "ok"

if __name__ == "__main__":
    setup_webhook()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
