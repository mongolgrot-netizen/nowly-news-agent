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

RSS_BY_CATEGORY = {
    "news": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "https://news.google.com/rss/search?q=срочно+новости+мир+происшествия&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=последние+новости+события&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "world": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://news.google.com/rss/search?q=мир+международные+новости&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "incidents": [
        "https://news.google.com/rss/search?q=происшествия+катастрофа+пожар+авария&hl=ru&gl=RU&ceid=RU:ru",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
    "conflicts": [
        "https://news.google.com/rss/search?q=Россия+Украина+СВО+конфликт+война&hl=ru&gl=RU&ceid=RU:ru",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
    "tech": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://news.google.com/rss/search?q=ИИ+искусственный+интеллект+технологии&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "economy": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://news.google.com/rss/search?q=экономика+бизнес+финансы&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "auto": [
        "https://news.google.com/rss/search?q=авто+автомобили+машины&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "humor": [
        "https://news.google.com/rss/search?q=юмор+смешные+новости+курьез&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "history": [
        "https://news.google.com/rss/search?q=история+исторические+события+археология&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "trends": [
        "https://news.google.com/rss/search?q=тренды+вирусное+необычное+соцсети&hl=ru&gl=RU&ceid=RU:ru",
    ],
}

CATEGORIES = {
    "news": "📰 Новости",
    "world": "🌍 Мир",
    "incidents": "🚨 Происшествия",
    "conflicts": "⚔️ СВО / конфликты",
    "tech": "🤖 ИИ / технологии",
    "economy": "💰 Экономика",
    "auto": "🚗 Авто",
    "humor": "😂 Юмор",
    "history": "🏛 История",
    "trends": "🔥 Тренды",
}

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

def fetch_news(category="news", limit=30):
    items = []
    urls = RSS_BY_CATEGORY.get(category, RSS_BY_CATEGORY["news"])
    for url in urls:
        try:
            r = requests.get(
                url,
                timeout=12,
                headers={"User-Agent": "NOWLY-News-Agent/1.0"}
            )
            r.raise_for_status()
            f = feedparser.parse(r.content)
            for e in f.entries[:12]:
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

def menu_keyboard():
    return [
        [{"text": "📰 Новости"}, {"text": "🌍 Мир"}, {"text": "🚨 Происшествия"}],
        [{"text": "⚔️ СВО / конфликты"}, {"text": "🤖 ИИ / технологии"}],
        [{"text": "💰 Экономика"}, {"text": "🚗 Авто"}, {"text": "🔥 Тренды"}],
        [{"text": "😂 Юмор"}, {"text": "🏛 История"}],
        [{"text": "ℹ️ Статус"}]
    ]

def send_menu(chat):
    tg("sendMessage", {
        "chat_id": chat,
        "text": "⚡ NOWLY AI EDITOR\n\nВыбери направление. Я найду свежие материалы именно по этой теме, отберу лучшие и подготовлю посты на проверку.\n\nКанал один — темы разделены на уровне редактора, поэтому позже не придётся плодить десятки каналов.",
        "reply_markup": json.dumps({
            "keyboard": menu_keyboard(),
            "resize_keyboard": True,
            "is_persistent": True
        }, ensure_ascii=False)
    })

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

def select_news(items, category="news"):
    candidates = []
    for i, (title, link, summary) in enumerate(items):
        candidates.append(
            f"[{i}] {title}\nОписание: {summary[:700]}\nИсточник: {link}"
        )

    category_name = CATEGORIES.get(category, "📰 Новости")
    fact = fact or {}
    fact_status = fact.get("status", "single_source")
    fact_reason = fact.get("reason", "")
    prompt = f"""Ты главный редактор Telegram-канала NOWLY.
Выбери самые интересные материалы именно для рубрики {category_name}.

Приоритет этой рубрики: релевантность теме, свежесть, общественный интерес и понятность массовой аудитории.
Для СВО/конфликтов особенно важно отделять подтвержденные факты от заявлений сторон и не выдавать утверждения одной стороны за установленный факт.
Для юмора и трендов выбирай действительно интересные и массовые истории, а не случайный мусор.
Для истории выбирай факты, события и находки с понятной исторической ценностью.

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


def related_items(target, items, max_items=5):
    title_words = set(re.findall(r"[а-яёa-z0-9]{4,}", target[0].lower()))
    scored = []
    for item in items:
        if item[1] == target[1]:
            continue
        words = set(re.findall(r"[а-яёa-z0-9]{4,}", item[0].lower()))
        score = len(title_words & words)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:max_items]]

def fact_check(target, related):
    sources = [target] + related
    material = []
    for i, (title, link, summary) in enumerate(sources):
        material.append(
            f"[{i}] {title}\nИсточник: {link}\nОписание: {summary[:600]}"
        )

    prompt = """Ты фактчекер новостного редактора NOWLY.
Проверь выбранную новость только по предоставленным материалам разных источников.

Верни строго JSON:
{"status":"confirmed|attributed|conflict|single_source","reason":"кратко","safe_facts":["..."],"source_indexes":[0,1]}

Правила:
- confirmed — ключевой факт подтверждается несколькими независимыми материалами;
- attributed — есть только заявление конкретной стороны/лица;
- conflict — источники расходятся по важным фактам;
- single_source — подтверждения нет;
- Не придумывай факты.
- Для военных конфликтов и СВО особенно строго отделяй заявления сторон от подтвержденных событий.

Материалы:
""" + "\n\n".join(material)

    try:
        raw = groq(prompt, 0.0)
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            data = json.loads(match.group(0))
            if data.get("status") in {"confirmed","attributed","conflict","single_source"}:
                return data
    except Exception as e:
        print("FACT CHECK ERROR:", repr(e))

    return {
        "status": "single_source",
        "reason": "Не удалось автоматически получить подтверждение из других материалов.",
        "safe_facts": [],
        "source_indexes": [0]
    }

def ai_post(title, link, summary="", category="news", fact=None):
    category_name = CATEGORIES.get(category, "📰 Новости")
    prompt = f"""Ты главный редактор Telegram-канала NOWLY.
Напиши готовый короткий пост для рубрики {category_name} на русском языке.

Заголовок: {title}
Источник: {link}
Описание: {summary}

Правила:
- Только русский язык.
- Заголовок яркий, но нейтральный, с одним подходящим эмодзи.
- 2-4 коротких абзаца.
- Только факты из предоставленной информации.
- Не додумывай и не усиливай события.
- Для конфликтов и военных событий обязательно указывай, кому принадлежит заявление, если факт не подтвержден независимым источником.
- Статус проверки: {fact_status}. Комментарий фактчекера: {fact_reason}
- Если статус attributed или single_source, используй осторожную атрибуцию.
- Если статус conflict, укажи, что источники расходятся, и не выбирай одну версию без основания.
- Не используй Markdown, HTML и служебные пояснения.
- В конце отдельной строкой: Источник: {link}
"""
    return groq(prompt, 0.3)

def process_news(chat, category="news"):
    category_name = CATEGORIES.get(category, "📰 Новости")
    send(chat, f"⚡ NOWLY: ищу свежие материалы — {category_name}...")
    items = fetch_news(category)
    if not items:
        send(chat, "⚠️ Не удалось получить свежие новости. Попробуй ещё раз через минуту.")
        return

    try:
        selected = select_news(items, category)
    except Exception as e:
        print("SELECT ERROR:", repr(e))
        selected = items[:3]

    send(chat, f"🧠 NOWLY: отобрано материалов: {len(selected)} из {len(items)}")

    for title, link, summary in selected:
        try:
            related = related_items((title, link, summary), items)
            fact = fact_check((title, link, summary), related)
            labels = {
                "confirmed": "✅ подтверждено",
                "attributed": "🟡 заявление / атрибуция",
                "conflict": "🔴 источники расходятся",
                "single_source": "⚪ один источник"
            }
            send(chat, f"🔎 Проверка: {labels.get(fact.get('status'), '⚪ не определено')}\n{fact.get('reason','')[:500]}")
            post = ai_post(title, link, summary, category, fact)
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

        if text.startswith("/start") or text == "ℹ️ Статус":
            send_menu(chat)
        elif text.startswith("/news") or text == "📰 Новости":
            threading.Thread(target=process_news, args=(chat, "news"), daemon=True).start()
        elif text == "🌍 Мир":
            threading.Thread(target=process_news, args=(chat, "world"), daemon=True).start()
        elif text == "🚨 Происшествия":
            threading.Thread(target=process_news, args=(chat, "incidents"), daemon=True).start()
        elif text == "⚔️ СВО / конфликты":
            threading.Thread(target=process_news, args=(chat, "conflicts"), daemon=True).start()
        elif text == "🤖 ИИ / технологии":
            threading.Thread(target=process_news, args=(chat, "tech"), daemon=True).start()
        elif text == "💰 Экономика":
            threading.Thread(target=process_news, args=(chat, "economy"), daemon=True).start()
        elif text == "🚗 Авто":
            threading.Thread(target=process_news, args=(chat, "auto"), daemon=True).start()
        elif text == "😂 Юмор":
            threading.Thread(target=process_news, args=(chat, "humor"), daemon=True).start()
        elif text == "🏛 История":
            threading.Thread(target=process_news, args=(chat, "history"), daemon=True).start()
        elif text == "🔥 Тренды":
            threading.Thread(target=process_news, args=(chat, "trends"), daemon=True).start()
        elif text.startswith("/status"):
            send(chat, "🟢 NOWLY AI Editor работает.", menu_keyboard())

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
