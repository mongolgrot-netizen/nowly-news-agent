import os, html, threading, json, re, time
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
    "russia": [
        "https://news.google.com/rss/search?q=Россия+федеральные+новости&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=Россия+правительство+госдума+федеральные+новости&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "events": [
        "https://news.google.com/rss/search?q=события+Россия+сегодня&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=события+мир+сегодня&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "incidents": [
        "https://news.google.com/rss/search?q=происшествия+катастрофа+пожар+авария&hl=ru&gl=RU&ceid=RU:ru",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
    "emergency": [
        "https://news.google.com/rss/search?q=экстренно+срочно+ЧП+происшествие&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=МЧС+экстренные+новости+Россия&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "crime": [
        "https://news.google.com/rss/search?q=криминал+преступление+полиция+СК+прокуратура&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=задержан+арест+уголовное+дело+Россия&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "wanted": [
        "https://news.google.com/rss/search?q=розыск+пропал+без+вести+помогите+найти+человека&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=разыскивается+пропавший+человек+МВД&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "kremlin": [
        "https://news.google.com/rss/search?q=site%3Akremlin.ru+Президент+Россия+Путин&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=site%3Akremlin.ru+Кремль+сегодня&hl=ru&gl=RU&ceid=RU:ru",
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

# Region search phrases. They are used with Google News RSS, so the same
# editorial engine can work for federal, district and individual regions.
REGION_QUERIES = {
    "Москва и МО": "Москва Московская область",
    "Санкт-Петербург и ЛО": "Санкт-Петербург Ленинградская область",
    "ЦФО": "Центральный федеральный округ Россия",
    "СЗФО": "Северо-Западный федеральный округ Россия",
    "ЮФО": "Южный федеральный округ Россия",
    "СКФО": "Северо-Кавказский федеральный округ Россия",
    "ПФО": "Приволжский федеральный округ Россия",
    "УФО": "Уральский федеральный округ Россия",
    "СФО": "Сибирский федеральный округ Россия",
    "ДФО": "Дальневосточный федеральный округ Россия",
}


CATEGORIES = {
    "news": "📰 Новости",
    "world": "🌍 Мир",
    "russia": "🇷🇺 Россия — федеральные",
    "events": "📡 События",
    "incidents": "🚨 Происшествия",
    "emergency": "⚡ Экстренно",
    "crime": "🕵️ Криминал",
    "wanted": "🔎 Внимание: розыск",
    "kremlin": "🏛 Кремль",
    "conflicts": "⚔️ СВО / конфликты",
    "tech": "🤖 ИИ / технологии",
    "economy": "💰 Экономика",
    "auto": "🚗 Авто",
    "humor": "😂 Юмор",
    "history": "🏛 История",
    "trends": "🔥 Тренды",
}

REGION_NAMES = list(REGION_QUERIES.keys())


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

def fetch_news(category="news", limit=30, region=None):
    items = []
    urls = list(RSS_BY_CATEGORY.get(category, RSS_BY_CATEGORY["news"]))

    # Regional mode: add several free Google News RSS searches for the
    # requested region. We keep the base category feeds too, so a regional
    # editor can compare local stories with federal/world coverage.
    if region and region in REGION_QUERIES:
        rq = REGION_QUERIES[region]
        base_terms = {
            "news": "новости",
            "russia": "Россия",
            "events": "события",
            "incidents": "происшествия ЧП авария пожар",
            "emergency": "экстренно срочно ЧП",
            "crime": "криминал преступление полиция",
            "wanted": "розыск пропал человек",
            "conflicts": "конфликт СВО",
        }
        terms = base_terms.get(category, "новости")
        q = "+".join((rq + " " + terms).split())
        urls.insert(0, "https://news.google.com/rss/search?q=" + q + "&hl=ru&gl=RU&ceid=RU:ru")
        q2 = "+".join((rq + " " + terms + " сегодня").split())
        urls.insert(1, "https://news.google.com/rss/search?q=" + q2 + "&hl=ru&gl=RU&ceid=RU:ru")

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
        [{"text": "📰 Новости"}, {"text": "🌍 Мир"}, {"text": "🇷🇺 Россия"}],
        [{"text": "📡 События"}, {"text": "🚨 Происшествия"}, {"text": "⚡ Экстренно"}],
        [{"text": "🕵️ Криминал"}, {"text": "🔎 Розыск"}, {"text": "🏛 Кремль"}],
        [{"text": "⚔️ СВО / конфликты"}, {"text": "🤖 ИИ / технологии"}],
        [{"text": "💰 Экономика"}, {"text": "🚗 Авто"}, {"text": "🔥 Тренды"}],
        [{"text": "😂 Юмор"}, {"text": "🏛 История"}],
        [{"text": "🗺 Россия по регионам"}, {"text": "ℹ️ Статус"}]
    ]

def region_keyboard():
    return [
        [{"text": "🇷🇺 Федеральные новости"}],
        [{"text": "📍 Москва и МО"}, {"text": "📍 Санкт-Петербург и ЛО"}],
        [{"text": "📍 ЦФО"}, {"text": "📍 СЗФО"}, {"text": "📍 ЮФО"}],
        [{"text": "📍 СКФО"}, {"text": "📍 ПФО"}, {"text": "📍 УФО"}],
        [{"text": "📍 СФО"}, {"text": "📍 ДФО"}],
        [{"text": "↩️ Главное меню"}]
    ]

def region_category_keyboard(region):
    return [
        [{"text": f"📰 Новости — {region}"}, {"text": f"🚨 Происшествия — {region}"}],
        [{"text": f"⚡ Экстренно — {region}"}, {"text": f"🕵️ Криминал — {region}"}],
        [{"text": f"🔎 Розыск — {region}"}, {"text": f"📡 События — {region}"}],
        [{"text": f"↩️ Регионы"}]
    ]

def send_menu(chat):
    tg("sendMessage", {
        "chat_id": chat,
        "text": "⚡ NOWLY AI EDITOR\n\nВыбери направление. Теперь можно отдельно искать и готовить публикации по миру, России, федеральным новостям, регионам, событиям, происшествиям, экстренным сообщениям, криминалу, розыску и официальным новостям Кремля.\n\nВсе материалы проходят редакторскую проверку перед публикацией.",
        "reply_markup": json.dumps({
            "keyboard": menu_keyboard(),
            "resize_keyboard": True,
            "is_persistent": True
        }, ensure_ascii=False)
    })

def groq(prompt, temperature=0.2, max_tokens=500):
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY не задан в Render Environment Variables")
    for attempt in range(3):
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens},
            timeout=45)
        if r.ok:
            return r.json()["choices"][0]["message"]["content"].strip()
        if r.status_code == 429 and attempt < 2:
            wait = 3
            try:
                msg = r.json().get("error", {}).get("message", "")
                m = re.search(r"(?:in|after) ([0-9.]+)s", msg)
                if m: wait = min(max(float(m.group(1)) + 1, 2), 15)
            except Exception: pass
            time.sleep(wait)
            continue
        try: detail = r.json().get("error", {}).get("message", r.text)
        except Exception: detail = r.text
        raise RuntimeError(f"Groq HTTP {r.status_code}: {detail[:500]}")
    raise RuntimeError("Groq: превышен лимит запросов")
def select_news(items, category="news", region=None):
    candidates = []
    for i, (title, link, summary) in enumerate(items):
        candidates.append(
            f"[{i}] {title}\nОписание: {summary[:350]}\nИсточник: {link}"
        )

    category_name = CATEGORIES.get(category, "📰 Новости")
    region_line = f"Региональная привязка: {region}. Отбирай прежде всего материалы, относящиеся к этому региону." if region else "Региональная привязка отсутствует: отбирай материалы федерального или международного масштаба в рамках рубрики."
    prompt = f"""Ты главный редактор Telegram-канала NOWLY.
Выбери самые интересные материалы именно для рубрики {category_name}.

Приоритет этой рубрики: релевантность теме, свежесть, общественный интерес и понятность массовой аудитории.
{region_line}
Для рубрик «розыск» и «помогите найти человека» не придумывай персональные данные и не меняй факты из источника.
Для СВО/конфликтов особенно важно отделять подтвержденные факты от заявлений сторон и не выдавать утверждения одной стороны за установленный факт.
Для юмора и трендов выбирай действительно интересные и массовые истории, а не случайный мусор.
Для истории выбирай факты, события и находки с понятной исторической ценностью.

Не выбирай несколько материалов об одном событии.
Не выбирай скучные второстепенные сообщения.
Не придумывай факты.

Верни ТОЛЬКО номера выбранных материалов через запятую, максимум 2 номера.
Пример: 4,1,7

Материалы:
""" + "\n\n".join(candidates)

    raw = groq(prompt, 0.1, 250)
    nums = re.findall(r"\d+", raw)
    selected = []
    for n in nums:
        i = int(n)
        if 0 <= i < len(items) and i not in selected:
            selected.append(i)
        if len(selected) >= 2:
            break

    if not selected:
        return items[:3]

    return [items[i] for i in selected]


def related_items(target, items, max_items=5):
    # Compare title + summary, not title only.
    text_a = f"{target[0]} {target[2]}".lower()
    words_a = set(re.findall(r"[а-яёa-z0-9]{4,}", text_a))
    stop = {
        "который","которая","которые","после","перед","этого","также",
        "сообщил","сообщила","сообщили","стало","стали","новости",
        "российский","российская","украинский","украинская","черном",
        "black","sea","news"
    }
    words_a -= stop
    scored = []
    for item in items:
        if item[1] == target[1]:
            continue
        text_b = f"{item[0]} {item[2]}".lower()
        words_b = set(re.findall(r"[а-яёa-z0-9]{4,}", text_b)) - stop
        score = len(words_a & words_b)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:max_items]]

def search_related_news(target, max_items=8):
    # Free cross-source lookup through Google News RSS.
    title = target[0]
    words = re.findall(r"[а-яёa-z0-9]{5,}", title.lower())
    stop = {
        "российский","российская","украинский","украинская","сообщил",
        "сообщила","заявил","заявила","ужасный","черном","черного",
        "после","погиб","погибли","новости"
    }
    words = [w for w in words if w not in stop][:7]
    if not words:
        return []
    query = "+".join(words)
    url = (
        "https://news.google.com/rss/search?q=" + query +
        "&hl=ru&gl=RU&ceid=RU:ru"
    )
    out = []
    try:
        r = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": "NOWLY-News-Agent/1.0"}
        )
        r.raise_for_status()
        f = feedparser.parse(r.content)
        for e in f.entries[:max_items]:
            t = html.unescape(str(e.get("title", "")).strip())
            l = str(e.get("link", "")).strip()
            sm = html.unescape(str(e.get("summary", "") or "").strip())
            sm = re.sub(r"<[^>]+>", " ", sm)
            sm = re.sub(r"\s+", " ", sm).strip()
            if t and l and l != target[1]:
                out.append((t, l, sm))
    except Exception as e:
        print("RELATED SEARCH ERROR:", repr(e))
    return out

def fact_check(target, related):
    if not related:
        return {"status":"single_source","reason":"Других материалов об этом событии не найдено.","safe_facts":[],"disputed_facts":[],"source_indexes":[0]}
    sources = [target] + related[:4]
    material = []
    for i, (title, link, summary) in enumerate(sources):
        material.append(
            f"[{i}] {title}\nИсточник: {link}\nОписание: {summary[:900]}"
        )

    prompt = """Ты старший фактчекер новостного редактора NOWLY.
Сравни все предоставленные материалы об ОДНОМ событии.

Верни строго JSON:
{"status":"confirmed|partial_confirmed|attributed|conflict|single_source",
"reason":"краткое объяснение",
"safe_facts":["только подтвержденные несколькими источниками факты"],
"disputed_facts":["детали, которые подтверждены только одной стороной или расходятся"],
"source_indexes":[0,1]}

Правила:
- confirmed: ключевые факты совпадают минимум в двух независимых источниках.
- partial_confirmed: само событие подтверждается несколькими источниками, но отдельные детали (причина, виновник, число погибших, обстоятельства) подтверждены не всеми.
- attributed: существенный факт существует только как заявление конкретного лица/стороны.
- conflict: независимые источники прямо расходятся по существенной детали.
- single_source: по существу есть только один источник.
- Отдельно сравнивай ЧИСЛА: погибшие, спасенные, раненые.
- Отдельно сравнивай ПРИЧИНУ события и АВТОРСТВО.
- Не считай одинаковую перепечатку одного сообщения независимым подтверждением.
- Если официальный орган подтверждает само происшествие, но не подтверждает его причину, это partial_confirmed, а причина должна быть disputed_facts.
- Не придумывай факты.
- Для военных конфликтов особенно строго отделяй заявления сторон от подтвержденных сведений.

Материалы:
""" + "\n\n".join(material)

    try:
        raw = groq(prompt, 0.0, 350)
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            data = json.loads(match.group(0))
            allowed = {
                "confirmed","partial_confirmed","attributed",
                "conflict","single_source"
            }
            if data.get("status") in allowed:
                return data
    except Exception as e:
        print("FACT CHECK ERROR:", repr(e))

    return {
        "status": "single_source",
        "reason": "Не удалось автоматически получить независимые подтверждения.",
        "safe_facts": [],
        "disputed_facts": [],
        "source_indexes": [0]
    }

def ai_post(title, link, summary="", category="news", fact=None, sources=None):
    category_name = CATEGORIES.get(category, "📰 Новости")
    fact = fact or {}
    fact_status = fact.get("status", "single_source")
    fact_reason = fact.get("reason", "")
    safe_facts = fact.get("safe_facts", [])
    disputed = fact.get("disputed_facts", [])
    source_lines = []
    for src in (sources or [])[:3]:
        if len(src) >= 2:
            source_lines.append(f"- {src[0]} — {src[1]}")
    prompt = f"""Ты главный редактор Telegram-канала NOWLY.
Напиши готовый короткий пост для рубрики {category_name} на русском языке.

Основной материал:
Заголовок: {title}
Источник: {link}
Описание: {summary[:500]}

Результат фактчека:
Статус: {fact_status}
Причина: {fact_reason}
Подтвержденные факты: {json.dumps(safe_facts, ensure_ascii=False)}
Спорные/неподтвержденные детали: {json.dumps(disputed, ensure_ascii=False)}

Правила:
- Только русский язык.
- Не называй утверждение фактом, если оно не подтверждено.
- Если событие подтверждено, но причина/виновник/детали спорны, четко раздели эти части.
- Если есть разные цифры, используй только цифру, подтвержденную независимыми источниками; если источники расходятся, прямо укажи расхождение.
- Для заявлений Зеленского, российских властей или других сторон обязательно используй "заявил", "сообщила сторона", "по данным..." вместо выдачи заявления за установленный факт.
- Не придумывай.
- Заголовок яркий, но нейтральный, с одним эмодзи.
- 2-4 коротких абзаца.
- В конце отдельной строкой: Источник: {link}
- Не используй Markdown, HTML и служебные пояснения.

Дополнительные материалы:
{chr(10).join(source_lines)}
"""
    return groq(prompt, 0.3, 450)

def process_news(chat, category="news", region=None):
    category_name = CATEGORIES.get(category, "📰 Новости")
    scope = f" • {region}" if region else ""
    send(chat, f"⚡ NOWLY: ищу свежие материалы — {category_name}{scope}...")
    items = fetch_news(category, region=region)
    if not items:
        send(chat, "⚠️ Не удалось получить свежие новости. Попробуй ещё раз через минуту.")
        return

    try:
        selected = select_news(items, category, region)
    except Exception as e:
        print("SELECT ERROR:", repr(e))
        selected = items[:3]

    send(chat, f"🧠 NOWLY: отобрано материалов: {len(selected)} из {len(items)}" + (f"\n🗺 Регион: {region}" if region else ""))

    for title, link, summary in selected:
        try:
            related = related_items((title, link, summary), items)
            searched = search_related_news((title, link, summary))
            # Merge and deduplicate by URL/title.
            pool = related + searched
            seen = set()
            merged = []
            for item in pool:
                key = item[1] or item[0].lower()
                if key not in seen and item[1] != link:
                    seen.add(key)
                    merged.append(item)
            related = merged[:8]

            fact = fact_check((title, link, summary), related)
            labels = {
                "confirmed": "🟢 подтверждено",
                "partial_confirmed": "🟠 частично подтверждено",
                "attributed": "🟡 заявление / атрибуция",
                "conflict": "🔴 источники расходятся",
                "single_source": "⚪ один источник"
            }
            send(chat, f"🔎 Проверка: {labels.get(fact.get('status'), '⚪ не определено')}\n{fact.get('reason','')[:700]}")

            source_list = [(title, link)] + [
                (x[0], x[1]) for x in related[:5]
            ]
            post = ai_post(
                title, link, summary, category, fact,
                source_list
            )
        except Exception as e:
            print("AI ERROR:", repr(e))
            post = (
                "⚠️ Не удалось обработать новость\n\n"
                "AI-редактор временно недоступен. Новость не публикуется.\n\n"
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
        elif text == "🗺 Россия по регионам":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🗺 РОССИЯ ПО РЕГИОНАМ\n\nВыбери федеральный уровень или региональный блок:",
                "reply_markup": json.dumps({"keyboard": region_keyboard(), "resize_keyboard": True}, ensure_ascii=False)
            })
        elif text == "🇷🇺 Россия":
            threading.Thread(target=process_news, args=(chat, "russia"), daemon=True).start()
        elif text == "🇷🇺 Федеральные новости":
            threading.Thread(target=process_news, args=(chat, "russia"), daemon=True).start()
        elif text == "↩️ Главное меню":
            send_menu(chat)
        elif text == "↩️ Регионы":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🗺 Выбери регион:",
                "reply_markup": json.dumps({"keyboard": region_keyboard(), "resize_keyboard": True}, ensure_ascii=False)
            })
        elif text.startswith("📍 "):
            region = text[3:].strip()
            if region in REGION_QUERIES:
                tg("sendMessage", {
                    "chat_id": chat,
                    "text": f"🗺 {region}\n\nВыбери тип материалов:",
                    "reply_markup": json.dumps({"keyboard": region_category_keyboard(region), "resize_keyboard": True}, ensure_ascii=False)
                })
        elif text.startswith("📰 Новости — "):
            region = text[len("📰 Новости — "):]
            threading.Thread(target=process_news, args=(chat, "news", region), daemon=True).start()
        elif text.startswith("🚨 Происшествия — "):
            region = text[len("🚨 Происшествия — "):]
            threading.Thread(target=process_news, args=(chat, "incidents", region), daemon=True).start()
        elif text.startswith("⚡ Экстренно — "):
            region = text[len("⚡ Экстренно — "):]
            threading.Thread(target=process_news, args=(chat, "emergency", region), daemon=True).start()
        elif text.startswith("🕵️ Криминал — "):
            region = text[len("🕵️ Криминал — "):]
            threading.Thread(target=process_news, args=(chat, "crime", region), daemon=True).start()
        elif text.startswith("🔎 Розыск — "):
            region = text[len("🔎 Розыск — "):]
            threading.Thread(target=process_news, args=(chat, "wanted", region), daemon=True).start()
        elif text.startswith("📡 События — "):
            region = text[len("📡 События — "):]
            threading.Thread(target=process_news, args=(chat, "events", region), daemon=True).start()
        elif text.startswith("/news") or text == "📰 Новости":
            threading.Thread(target=process_news, args=(chat, "news"), daemon=True).start()
        elif text == "🌍 Мир":
            threading.Thread(target=process_news, args=(chat, "world"), daemon=True).start()
        elif text == "📡 События":
            threading.Thread(target=process_news, args=(chat, "events"), daemon=True).start()
        elif text == "🚨 Происшествия":
            threading.Thread(target=process_news, args=(chat, "incidents"), daemon=True).start()
        elif text == "⚡ Экстренно":
            threading.Thread(target=process_news, args=(chat, "emergency"), daemon=True).start()
        elif text == "🕵️ Криминал":
            threading.Thread(target=process_news, args=(chat, "crime"), daemon=True).start()
        elif text == "🔎 Розыск":
            threading.Thread(target=process_news, args=(chat, "wanted"), daemon=True).start()
        elif text == "🏛 Кремль":
            threading.Thread(target=process_news, args=(chat, "kremlin"), daemon=True).start()
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
