import os, html, threading, json, re
from flask import Flask, request, jsonify
import requests, feedparser

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_CHAT_ID", "")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@Paramitaplus")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")

RSS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
]

def tg(method, data):
    if not TOKEN:
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/{method}",
            data=data,
            timeout=30
        )
        return r.json()
    except Exception as e:
        print("TELEGRAM ERROR:", repr(e))
        return None

def setup_webhook():
    if not TOKEN or not WEBHOOK_URL:
        return
    try:
        result = tg("setWebhook", {"url": WEBHOOK_URL + "/telegram/webhook"})
        print("Telegram webhook:", result)
    except Exception as e:
        print("Webhook setup error:", repr(e))

def send(chat, text, buttons=None):
    data = {
        "chat_id": chat,
        "text": text,
        "disable_web_page_preview": "false"
    }
    if buttons:
        data["reply_markup"] = json.dumps({"inline_keyboard": buttons}, ensure_ascii=False)
    return tg("sendMessage", data)

def fetch_news(limit=12):
    items = []
    for url in RSS:
        try:
            r = requests.get(
                url,
                timeout=12,
                headers={"User-Agent": "NOWLY-News-Agent/1.0"}
            )
            r.raise_for_status()
            f = feedparser.parse(r.content)
            for e in f.entries[:8]:
                title = html.unescape(str(e.get("title", "")).strip())
                link = str(e.get("link", "")).strip()
                summary = html.unescape(str(
                    e.get("summary", "") or e.get("description", "")
                ).strip())
                summary = re.sub(r"<[^>]+>", " ", summary)
                summary = re.sub(r"\s+", " ", summary).strip()
                if title and link:
                    items.append((title, link, summary))
        except Exception as e:
            print("RSS ERROR:", url, repr(e))

    seen = set()
    out = []
    for title, link, summary in items:
        key = re.sub(r"\W+", " ", title.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            out.append((title, link, summary))
    return out[:limit]

def groq(prompt, temperature=0.2):
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY не задан в Render Environment Variables")

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        },
        timeout=45
    )

    if not r.ok:
        try:
            detail = r.json().get("error", {}).get("message", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Groq HTTP {r.status_code}: {detail[:500]}")

    data = r.json()
    return data["choices"][0]["message"]["content"].strip()

def select_news(items):
    candidates = []
    for i, (title, link, summary) in enumerate(items):
        candidates.append(
            f"[{i}] {title}\nОписание: {summary[:700]}\nИсточник: {link}"
        )

    prompt = """Ты главный редактор Telegram-канала NOWLY.
Выбери самые интересные и общественно значимые новости для массовой русскоязычной аудитории.

Приоритет:
1. важные события и происшествия;
2. международные события;
3. технологии и ИИ;
4. экономика и бизнес;
5. необычные и вирусные события.

Не выбирай несколько материалов об одном событии.
Не выбирай скучные второстепенные сообщения.
Не придумывай факты.

Верни ТОЛЬКО номера выбранных материалов через запятую, максимум 3 номера.
Пример: 4,1,7

Материалы:
""" + "\n\n".join(candidates)

    raw = groq(prompt, 0.1)
    nums = re.findall(r"\d+", raw)
    selected = []
    for n in nums:
        i = int(n)
        if 0 <= i < len(items) and i not in selected:
            selected.append(i)
        if len(selected) >= 3:
            break

    if not selected:
        return items[:3]

    return [items[i] for i in selected]

def ai_post(title, link, summary=""):
    prompt = f"""Ты главный редактор Telegram-канала NOWLY.
Напиши готовый короткий новостной пост на русском языке.

Заголовок: {title}
Источник: {link}
Описание: {summary}

Правила:
- Только русский язык.
- Заголовок яркий, но нейтральный, с одним подходящим эмодзи.
- 2-4 коротких абзаца.
- Только факты из предоставленной информации.
- Не додумывай и не усиливай события.
- Не используй Markdown, HTML и служебные пояснения.
- В конце отдельной строкой: Источник: {link}
"""
    return groq(prompt, 0.3)

def process_news(chat):
    send(chat, "⚡ NOWLY: ищу свежие новости и отбираю самые интересные...")
    items = fetch_news()
    if not items:
        send(chat, "⚠️ Не удалось получить свежие новости. Попробуй ещё раз через минуту.")
        return

    try:
        selected = select_news(items)
    except Exception as e:
        print("SELECT ERROR:", repr(e))
        selected = items[:3]

    send(chat, f"🧠 NOWLY: отобрано материалов: {len(selected)}")

    for title, link, summary in selected:
        try:
            post = ai_post(title, link, summary)
        except Exception as e:
            print("AI ERROR:", repr(e))
            post = (
                "⚠️ Не удалось обработать новость\n\n"
                "AI-перевод временно недоступен. Новость не публикуется.\n\n"
                f"Техническая причина: {str(e)[:500]}\n\n"
                f"Источник: {link}"
            )

        buttons = [[
            {"text": "✅ Опубликовать", "callback_data": "pub"},
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
            send(
                chat,
                "⚡ NOWLY AI EDITOR\n\n"
                "/news — найти и подготовить лучшие свежие новости\n"
                "/status — проверить работу бота"
            )
        elif text.startswith("/news"):
            threading.Thread(
                target=process_news,
                args=(chat,),
                daemon=True
            ).start()
        elif text.startswith("/status"):
            send(chat, "🟢 NOWLY AI Editor работает.")

    elif "callback_query" in u:
        q = u["callback_query"]
        chat = q["message"]["chat"]["id"]

        if ADMIN_ID and str(chat) != str(ADMIN_ID):
            return

        if q["data"] == "pub":
            text = q["message"]["text"]
            result = tg("sendMessage", {
                "chat_id": CHANNEL,
                "text": text,
                "disable_web_page_preview": "false"
            })

            if result and result.get("ok"):
                tg("answerCallbackQuery", {
                    "callback_query_id": q["id"],
                    "text": "Опубликовано в NOWLY"
                })
                try:
                    tg("editMessageReplyMarkup", {
                        "chat_id": chat,
                        "message_id": q["message"]["message_id"],
                        "reply_markup": json.dumps({"inline_keyboard": []})
                    })
                except Exception:
                    pass
            else:
                error_text = "Неизвестная ошибка Telegram"
                if result:
                    error_text = result.get("description", str(result))
                tg("answerCallbackQuery", {
                    "callback_query_id": q["id"],
                    "text": "Ошибка публикации",
                    "show_alert": True
                })
                send(
                    chat,
                    f"❌ Не удалось опубликовать в канал {CHANNEL}.\n\n"
                    f"Причина Telegram: {error_text}"
                )

        else:
            tg("answerCallbackQuery", {
                "callback_query_id": q["id"],
                "text": "Отклонено"
            })
            try:
                tg("editMessageReplyMarkup", {
                    "chat_id": chat,
                    "message_id": q["message"]["message_id"],
                    "reply_markup": json.dumps({"inline_keyboard": []})
                })
            except Exception:
                pass

@app.get("/")
def health():
    return jsonify({
        "status": "online",
        "service": "NOWLY AI Editor",
        "channel": CHANNEL
    })

@app.post("/telegram/webhook")
def webhook():
    handle_update(request.get_json(force=True))
    return "ok"

if __name__ == "__main__":
    setup_webhook()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
