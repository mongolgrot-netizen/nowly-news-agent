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
HISTORY_MODE = {}  # chat_id -> ("world"|"russia"|"region_select"|"region", region)

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
        "https://news.google.com/rss/search?q=site%3At.me+СВО+Россия+фронт+военкор&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=site%3At.me+военкор+Россия+Украина&hl=ru&gl=RU&ceid=RU:ru",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
    "russia_tech": [
        "https://news.google.com/rss/search?q=Россия+технологии+наука+разработки+ученые&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=российская+наука+технологии+исследования+РАН&hl=ru&gl=RU&ceid=RU:ru",
    ],
    "laws": [
        "https://news.google.com/rss/search?q=Россия+новые+законы+законопроект+вступает+в+силу&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=Россия+новые+штрафы+изменение+штрафа+КоАП&hl=ru&gl=RU&ceid=RU:ru",
        "https://news.google.com/rss/search?q=site%3Apravo.gov.ru+закон+постановление+Россия&hl=ru&gl=RU&ceid=RU:ru",
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
    "russia_tech": "🔬 Технологии и наука России",
    "laws": "⚖️ Законы и штрафы",
    "tech": "🤖 ИИ / технологии",
    "economy": "💰 Экономика",
    "auto": "🚗 Авто",
    "humor": "😂 Юмор",
    "history": "🏛 История",
    "trends": "🔥 Тренды",
}

REGION_NAMES = list(REGION_QUERIES.keys())

# Automatic region tagging without an additional AI/API call.
# Covers the major Russian regions and common short forms used by news media.
REGION_ALIASES = {
    "Москва": ["москва", "москве", "москвы", "москвой"],
    "Московская область": ["московская область", "подмосковье", "московской области", "мо"],
    "Санкт-Петербург": ["санкт-петербург", "санкт петербург", "петербург", "спб", "петербурге"],
    "Ленинградская область": ["ленинградская область", "ленобласть", "ленинградской области"],
    "Республика Татарстан": ["татарстан", "казань", "республике татарстан", "татарстана"],
    "Республика Башкортостан": ["башкортостан", "башкирия", "уфа", "республике башкортостан"],
    "Свердловская область": ["свердловская область", "екатеринбург", "свердловской области"],
    "Челябинская область": ["челябинская область", "челябинск", "челябинской области"],
    "Тюменская область": ["тюменская область", "тюмень", "тюменской области"],
    "Ханты-Мансийский АО — Югра": ["ханты-мансийский", "ханты мансийский", "югра", "хмао", "сургут", "нижневартовск"],
    "Ямало-Ненецкий АО": ["ямало-ненецкий", "янао", "салехард", "новый уренгой"],
    "Краснодарский край": ["краснодарский край", "краснодар", "сочи", "кубань"],
    "Ростовская область": ["ростовская область", "ростов-на-дону", "ростов на дону", "донской регион"],
    "Республика Крым": ["республика крым", "крым", "симферополь", "севастополь"],
    "Севастополь": ["севастополь"],
    "Воронежская область": ["воронежская область", "воронеж"],
    "Белгородская область": ["белгородская область", "белгород"],
    "Курская область": ["курская область", "курск"],
    "Брянская область": ["брянская область", "брянск"],
    "Тульская область": ["тульская область", "тула"],
    "Калужская область": ["калужская область", "калуга"],
    "Рязанская область": ["рязанская область", "рязань"],
    "Ярославская область": ["ярославская область", "ярославль"],
    "Владимирская область": ["владимирская область", "владимир"],
    "Тверская область": ["тверская область", "тверь"],
    "Калининградская область": ["калининградская область", "калининград"],
    "Нижегородская область": ["нижегородская область", "нижний новгород", "нижнем новгороде"],
    "Самарская область": ["самарская область", "самара"],
    "Саратовская область": ["саратовская область", "саратов"],
    "Пензенская область": ["пензенская область", "пенза"],
    "Ульяновская область": ["ульяновская область", "ульяновск"],
    "Оренбургская область": ["оренбургская область", "оренбург"],
    "Пермский край": ["пермский край", "пермь"],
    "Удмуртская Республика": ["удмуртия", "удмуртская республика", "ижевск"],
    "Чувашская Республика": ["чувашия", "чувашская республика", "чебоксары"],
    "Республика Марий Эл": ["марий эл", "йошкар-ола", "йошкар ола"],
    "Республика Мордовия": ["мордовия", "саранск"],
    "Удмуртская Республика": ["удмуртия", "удмуртская республика", "ижевск"],
    "Кировская область": ["кировская область", "киров"],
    "Архангельская область": ["архангельская область", "архангельск"],
    "Мурманская область": ["мурманская область", "мурманск"],
    "Вологодская область": ["вологодская область", "вологда"],
    "Новгородская область": ["новгородская область", "великий новгород"],
    "Псковская область": ["псковская область", "псков"],
    "Республика Карелия": ["карелия", "петрозаводск"],
    "Республика Коми": ["коми", "сыктывкар"],
    "Красноярский край": ["красноярский край", "красноярск"],
    "Иркутская область": ["иркутская область", "иркутск"],
    "Новосибирская область": ["новосибирская область", "новосибирск"],
    "Омская область": ["омская область", "омск"],
    "Томская область": ["томская область", "томск"],
    "Кемеровская область — Кузбасс": ["кемеровская область", "кузбасс", "кемерово", "новокузнецк"],
    "Алтайский край": ["алтайский край", "барнаул"],
    "Республика Алтай": ["республика алтай", "горно-алтайск"],
    "Приморский край": ["приморский край", "владивосток", "приморье"],
    "Хабаровский край": ["хабаровский край", "хабаровск"],
    "Амурская область": ["амурская область", "благовещенск"],
    "Сахалинская область": ["сахалинская область", "сахалин", "южно-сахалинск"],
    "Камчатский край": ["камчатский край", "камчатка", "петропавловск-камчатский"],
    "Магаданская область": ["магаданская область", "магадан"],
    "Чукотский АО": ["чукотский автономный округ", "чукотка", "анадырь"],
    "Забайкальский край": ["забайкальский край", "забайкалье", "чита"],
    "Республика Бурятия": ["бурятия", "улан-удэ"],
    "Республика Тыва": ["тыва", "тува", "кызыл"],
    "Республика Хакасия": ["хакасия", "абакан"],
    "Республика Дагестан": ["дагестан", "махачкала"],
    "Чеченская Республика": ["чечня", "чеченская республика", "грозный"],
    "Кабардино-Балкарская Республика": ["кабардино-балкария", "нальчик"],
    "Республика Северная Осетия — Алания": ["северная осетия", "осетия", "владикавказ"],
    "Ставропольский край": ["ставропольский край", "ставрополь"],
    "Республика Калмыкия": ["калмыкия", "элиста"],
    "Астраханская область": ["астраханская область", "астрахань"],
    "Волгоградская область": ["волгоградская область", "волгоград"],
    "Республика Адыгея": ["адыгея", "майкоп"],
    "Карачаево-Черкесская Республика": ["карачаево-черкесия", "черкесск"],
    "Республика Ингушетия": ["ингушетия", "магас"],
    "Республика Саха (Якутия)": ["якутия", "республика саха", "якутск"],
}

def detect_region(title, summary="", source=""):
    text = f"{title} {summary}".lower()
    found = []
    for region, aliases in REGION_ALIASES.items():
        for alias in aliases:
            # Avoid treating tiny abbreviations such as "мо" as standalone words.
            if len(alias) <= 3:
                hit = re.search(r"(?<![а-яёa-z])" + re.escape(alias) + r"(?![а-яёa-z])", text)
            else:
                hit = alias in text
            if hit:
                found.append(region)
                break

    # Prefer the explicit region name over a city alias when both occur.
    unique = list(dict.fromkeys(found))
    if len(unique) == 1:
        return unique[0]
    if unique:
        # Moscow/МО and St Petersburg/LO are intentionally kept distinct.
        priority = ["Москва", "Московская область", "Санкт-Петербург", "Ленинградская область"]
        for p in priority:
            if p in unique:
                return p
        return unique[0]
    return "Россия — регион не определён"



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
                    region = detect_region(title, summary, link)
                    items.append((title, link, summary, region))
        except Exception as e:
            print("RSS ERROR:", url, repr(e))

    seen = set()
    out = []
    for item in items:
        title, link, summary, region = item
        key = re.sub(r"\W+", " ", title.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            out.append((title, link, summary, region))
    return out[:limit]

def menu_keyboard():
    return [
        [{"text": "🌍 Мировые новости"}],
        [{"text": "🇷🇺 Россия — федеральные новости"}],
        [{"text": "🗺 Россия по регионам"}],
        [{"text": "📡 События"}, {"text": "🚨 Происшествия"}],
        [{"text": "⚡ Экстренно"}, {"text": "🕵️ Криминал"}],
        [{"text": "🔎 Внимание: розыск"}, {"text": "🏛 Новости Кремля"}],
        [{"text": "⚔️ СВО"}],
        [{"text": "🤖 ИИ / технологии"}, {"text": "🔬 Наука и технологии России"}],
        [{"text": "⚖️ Законы и штрафы"}, {"text": "💰 Экономика"}],
        [{"text": "🚗 Авто"}, {"text": "🔥 Тренды"}],
        [{"text": "😂 Юмор"}, {"text": "🏛 История"}],
        [{"text": "ℹ️ Статус"}]
    ]

def history_keyboard():
    return [
        [{"text": "📅 Этот день в истории"}],
        [{"text": "🇷🇺 История России"}, {"text": "🌍 История мира"}],
        [{"text": "🗺 История по регионам"}],
        [{"text": "↩️ Главное меню"}]
    ]

def history_scope_keyboard():
    return [
        [{"text": "🇷🇺 Россия — этот день"}],
        [{"text": "🌍 Мир — этот день"}],
        [{"text": "🗺 Регионы — этот день"}],
        [{"text": "↩️ История"}]
    ]

def history_region_keyboard():
    return [
        [{"text": "📍 Москва и МО"}, {"text": "📍 Санкт-Петербург и ЛО"}],
        [{"text": "📍 ЦФО"}, {"text": "📍 СЗФО"}, {"text": "📍 ЮФО"}],
        [{"text": "📍 СКФО"}, {"text": "📍 ПФО"}, {"text": "📍 УФО"}],
        [{"text": "📍 СФО"}, {"text": "📍 ДФО"}],
        [{"text": "↩️ История"}]
    ]

def history_day(chat, scope="world", region=None):
    from datetime import datetime
    now=datetime.now()
    day,month=now.day,now.month
    date_label=now.strftime("%-d.%m")
    lang="ru" if scope!="world" else "en"
    urls=[
        f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/events/{month:02d}/{day:02d}",
        f"https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/events/{month:02d}/{day:02d}"
    ]
    events=[]
    for url in urls:
        try:
            rr=requests.get(url,timeout=20,headers={"User-Agent":"NOWLY/1.0"})
            if rr.ok:
                events=rr.json().get("events",[])
                if events: break
        except Exception as ex:
            print("HISTORY API:",repr(ex))

    if scope=="russia":
        scope_text="Россия: Российская империя, СССР и современная Россия."
    elif scope=="region":
        scope_text=f"только {region}"
    else:
        scope_text="весь мир"

    data=[]
    for ev in events[:50]:
        text_ev=(ev.get("text") or "").strip()
        year=ev.get("year")
        pages=ev.get("pages") or []
        if text_ev:
            data.append({"year":year,"text":text_ev[:900],"pages":pages[:1]})

    if not data:
        send(chat,f"📅 ЭТОТ ДЕНЬ В ИСТОРИИ — {date_label}\n\nНе удалось получить исторические события за сегодняшнюю дату.")
        return

    prompt=f"""Ты исторический редактор NOWLY.
Сегодня {date_label}. Подготовь рубрику «Этот день в истории» для охвата: {scope_text}.

ВАЖНО: год НЕ задается пользователем. Выбирай значимые события, произошедшие именно в этот календарный день в РАЗНЫЕ годы.
Выбери 5–8 самых интересных событий из разных эпох. Приоритет: войны и переломные события, государственные решения, революции, открытия, наука, технологии, катастрофы, культура и другие события с заметным историческим значением.
Не включай обычные дни рождения и смерти, если они не являются самостоятельным значимым событием.
Для России и региона отбрасывай события, не относящиеся к выбранному охвату.
Не выдумывай годы или факты.

Формат:
📅 ЭТОТ ДЕНЬ В ИСТОРИИ — {date_label}

ГОД — событие
ГОД — событие
...

Источник: Wikimedia / Wikipedia.

Без Markdown, HTML и служебных пояснений.

Данные Wikimedia:
{json.dumps(data,ensure_ascii=False)}
"""
    try:
        post=groq(prompt,0.2,800).strip()
        if not post: raise ValueError("empty")
    except Exception as ex:
        print("HISTORY AI:",repr(ex))
        post=f"📅 ЭТОТ ДЕНЬ В ИСТОРИИ — {date_label}\n\n" + "\n".join(
            f"{x['year']} — {x['text']}" for x in data[:8]
        ) + "\n\nИсточник: Wikimedia / Wikipedia."
    send(chat,post,[[{"text":"✅ Опубликовать","callback_data":"pub"},{"text":"❌ Отклонить","callback_data":"no"}]])


def world_keyboard():
    return [
        [{"text": "🌍 Мировые новости"}],
        [{"text": "⚔️ Международные конфликты"}],
        [{"text": "📡 Мировые события"}, {"text": "🚨 Мировые происшествия"}],
        [{"text": "⚡ Мировые экстренные новости"}],
        [{"text": "🤖 ИИ / технологии"}, {"text": "💰 Экономика"}],
        [{"text": "🚗 Авто"}, {"text": "🔥 Тренды"}],
        [{"text": "😂 Юмор"}, {"text": "🏛 История"}],
        [{"text": "↩️ Главное меню"}]
    ]

def russia_keyboard():
    return [
        [{"text": "🇷🇺 Федеральные новости"}],
        [{"text": "🗺 Новости по регионам"}],
        [{"text": "📡 События"}, {"text": "🚨 Происшествия"}],
        [{"text": "⚡ Экстренно"}, {"text": "🕵️ Криминал"}],
        [{"text": "🔎 Внимание: розыск"}, {"text": "🏛 Новости Кремля"}],
        [{"text": "⚔️ СВО"}],
        [{"text": "📡 Анализ Telegram-каналов по СВО"}],
        [{"text": "🤖 ИИ / технологии"}, {"text": "🔬 Наука и технологии России"}],
        [{"text": "⚖️ Законы и штрафы"}, {"text": "💰 Экономика"}],
        [{"text": "🚗 Авто"}, {"text": "🔥 Тренды"}],
        [{"text": "😂 Юмор"}, {"text": "🏛 История"}],
        [{"text": "↩️ Главное меню"}]
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
        [{"text": f"📰 Новости — {region}"}, {"text": f"📡 События — {region}"}],
        [{"text": f"🚨 Происшествия — {region}"}, {"text": f"⚡ Экстренно — {region}"}],
        [{"text": f"🕵️ Криминал — {region}"}, {"text": f"🔎 Розыск — {region}"}],
        [{"text": f"🏛 Кремль — {region}"}, {"text": f"↩️ Регионы"}]
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
    for attempt in range(4):
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens},
            timeout=45)
        if r.ok:
            return r.json()["choices"][0]["message"]["content"].strip()
        if r.status_code == 429 and attempt < 3:
            wait = 6
            try:
                msg = r.json().get("error", {}).get("message", "")
                m = re.search(r"(?:in|after) ([0-9.]+)s", msg)
                if m: wait = min(max(float(m.group(1)) + 1, 6), 30)
            except Exception: pass
            time.sleep(wait)
            continue
        try: detail = r.json().get("error", {}).get("message", r.text)
        except Exception: detail = r.text
        raise RuntimeError(f"Groq HTTP {r.status_code}: {detail[:500]}")
    raise RuntimeError("Groq: превышен лимит запросов")
def select_news(items, category="news", region=None):
    candidates = []
    for i, item in enumerate(items):
        title, link, summary, region_tag = item
        candidates.append(
            f"[{i}] {title}\nРегион: {region_tag}\nОписание: {summary[:350]}\nИсточник: {link}"
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
        return items[:1]

    return [items[i] for i in selected[:1]]


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
    # Search by the key facts, not the whole headline, to catch independent reports.
    title = target[0]
    summary = target[2] if len(target) > 2 else ""
    words = re.findall(r"[а-яёa-z0-9]{5,}", f"{title} {summary}".lower())
    stop = {
        "российский","российская","российское","украинский","украинская",
        "сообщил","сообщила","сообщили","заявил","заявила","после","погиб",
        "погибли","новости","стало","стали","который","которая","которые",
        "сегодня","также","время","районе","области"
    }
    words = [w for w in words if w not in stop][:9]
    if not words:
        return []
    queries = ["+".join(words[:6]), "+".join(words[:4] + words[-3:])]
    out, seen = [], set()
    for query in queries:
        url = "https://news.google.com/rss/search?q=" + query + "&hl=ru&gl=RU&ceid=RU:ru"
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent":"NOWLY-News-Agent/1.0"})
            r.raise_for_status()
            f = feedparser.parse(r.content)
            for e in f.entries[:max_items]:
                t = html.unescape(str(e.get("title","")).strip())
                l = str(e.get("link","")).strip()
                sm = html.unescape(str(e.get("summary","") or "").strip())
                sm = re.sub(r"<[^>]+>", " ", sm)
                sm = re.sub(r"\s+", " ", sm).strip()
                key = l or t.lower()
                if t and l and l != target[1] and key not in seen:
                    seen.add(key)
                    out.append((t,l,sm))
        except Exception as e:
            print("RELATED SEARCH ERROR:", repr(e))
    return out[:max_items]

def search_telegram_news(target, max_items=6):
    """Find public Russian Telegram reports via Google News RSS.
    Telegram posts are treated as leads, not automatic confirmation."""
    title = target[0]
    summary = target[2] if len(target) > 2 else ""
    words = re.findall(r"[а-яёa-z0-9]{5,}", f"{title} {summary}".lower())
    stop = {
        "российский","российская","российское","украинский","украинская",
        "сообщил","сообщила","сообщили","заявил","заявила","после","новости",
        "сегодня","также","который","которая","которые","стало","стали"
    }
    words = [w for w in words if w not in stop][:7]
    if not words:
        return []
    queries = [
        "site:t.me " + " ".join(words[:5]),
        "site:telegram.me " + " ".join(words[:5])
    ]
    out, seen = [], set()
    for q in queries:
        url = "https://news.google.com/rss/search?q=" + requests.utils.quote(q) + "&hl=ru&gl=RU&ceid=RU:ru"
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent":"NOWLY-News-Agent/1.0"})
            r.raise_for_status()
            f = feedparser.parse(r.content)
            for e in f.entries[:max_items]:
                t = html.unescape(str(e.get("title","")).strip())
                l = str(e.get("link","")).strip()
                sm = html.unescape(str(e.get("summary","") or "").strip())
                sm = re.sub(r"<[^>]+>", " ", sm)
                sm = re.sub(r"\s+", " ", sm).strip()
                key = l or t.lower()
                if t and l and ("t.me/" in l or "telegram.me/" in l) and key not in seen:
                    seen.add(key)
                    out.append((t,l,sm))
        except Exception as e:
            print("TELEGRAM SEARCH ERROR:", repr(e))
    return out[:max_items]

def fact_check(target, related, telegram_sources=None):
    telegram_sources = telegram_sources or []
    if not related and not telegram_sources:
        return {"status":"single_source","reason":"Других независимых материалов об этом событии не найдено.","safe_facts":[],"disputed_facts":[],"source_indexes":[0],"telegram_first":False,"telegram_primary":False,"recommendation":"hold"}
    sources = [target] + related[:4] + telegram_sources[:3]
    material = []
    for i, item in enumerate(sources):
        title, link, summary, *rest = item
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
- Отдельно анализируй Telegram-источники: если публичный российский Telegram-канал опубликовал информацию раньше других найденных источников, это можно отметить как "первым сообщил", но это НЕ означает подтверждение.
- Если Telegram является единственным источником существенного факта, статус не должен становиться confirmed.
- Если Telegram содержит только слух/анонимное утверждение без подтверждения, рекомендация = hold.
- Если независимые источники подтверждают событие, а Telegram лишь сообщил первым, recommendation = publish и telegram_first = true.
- Если источники существенно расходятся или нет достаточной проверки, recommendation = hold.
- Никогда не считай копии одного Telegram-сообщения независимыми источниками.
- Верни дополнительные поля: "telegram_first":true|false, "telegram_primary":true|false, "recommendation":"publish|hold".

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
        "source_indexes": [0],
        "telegram_first": False,
        "telegram_primary": False,
        "recommendation": "hold"
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
    telegram_rule = ""
    if category == "conflicts":
        telegram_rule = """
Для материалов по СВО дополнительно анализируй найденные публичные российские Telegram-источники.
Не считай публикацию одного военкора доказательством. Сопоставляй сообщения разных каналов и открытых СМИ.
Отдельно отмечай, где информация является сообщением/заявлением Telegram-канала, а где подтверждена независимыми источниками.
Не раскрывай закрытые данные, не публикуй непроверенные координаты или оперативно чувствительную информацию.
"""
    prompt = f"""Ты главный редактор Telegram-канала NOWLY.
Напиши готовый короткий пост для рубрики {category_name} на русском языке.
{telegram_rule}

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

    # Free Groq has a strict TPM limit. Do not run several AI calls per button.
    # Pick the freshest candidate deterministically, then use one compact AI call
    # to edit it and assess whether it is safe enough for manual publication.
    selected = items[:1]
    send(chat, f"🧠 NOWLY: отобран материал: 1 из {len(items)}" + (f"\n🗺 Регион: {region}" if region else ""))

    title, link, summary, region_tag = selected[0]
    try:
        related = related_items((title, link, summary, region_tag), items, max_items=3)
        searched = search_related_news((title, link, summary, region_tag), max_items=3)
        telegram_sources = search_telegram_news((title, link, summary, region_tag), max_items=3)

        pool = related + searched + telegram_sources
        seen = set()
        merged = []
        for item in pool:
            key = item[1] or item[0].lower()
            if key != link and key not in seen:
                seen.add(key)
                merged.append(item)
        related = merged[:4]

        source_lines = [(title, link)] + [(x[0], x[1]) for x in related[:4]]
        material = "\n\n".join(
            f"[{i}] {x[0]}\nИсточник: {x[1]}\nОписание: {x[2][:500]}"
            for i, x in enumerate([selected[0]] + related[:4])
        )

        prompt = f"""Ты редактор новостного Telegram-канала NOWLY.
Рубрика: {category_name}
Материалы собраны из открытых RSS-источников.

Проверь, относится ли это к одному событию. Если есть подтверждение в нескольких независимых источниках, отметь подтвержденные факты. Telegram-публикации считай сигналом/первоисточником, но не доказательством сами по себе.

Верни строго JSON:
{{"status":"confirmed|partial_confirmed|attributed|conflict|single_source",
"recommendation":"publish|hold",
"reason":"кратко",
"telegram_first":true,
"telegram_primary":false,
"post":"готовый короткий пост на русском языке"}}

Правила:
- Не придумывай.
- Если независимого подтверждения нет — recommendation=hold.
- Не называй заявление фактом.
- Если источники расходятся — recommendation=hold.
- Пост 2-3 коротких абзаца, нейтральный заголовок с одним эмодзи.
- В конце: Источник: URL основного материала.
- Без Markdown, HTML и служебных пояснений.
- Для СВО не публикуй оперативно чувствительные данные, координаты или тактические сведения.

Материалы:
{material}
"""
        raw = groq(prompt, 0.1, 650)
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0)) if match else {}
        status = data.get("status", "single_source")
        recommendation = data.get("recommendation", "hold")
        labels = {
            "confirmed":"🟢 подтверждено",
            "partial_confirmed":"🟠 частично подтверждено",
            "attributed":"🟡 заявление / атрибуция",
            "conflict":"🔴 источники расходятся",
            "single_source":"⚪ один источник"
        }
        tg_first = "да" if data.get("telegram_first") else "нет"
        tg_primary = "да" if data.get("telegram_primary") else "нет"
        rec = "🟢 рекомендовано к публикации" if recommendation == "publish" else "🔴 лучше НЕ публиковать"
        send(chat, f"🔎 Проверка: {labels.get(status, '⚪ не определено')}\n{rec}\nTelegram первым: {tg_first} • Telegram — основной источник: {tg_primary}\n{str(data.get('reason',''))[:700]}")
        post = str(data.get("post","")).strip()
        if not post:
            post = f"📰 {title}\n\n{summary[:900]}\n\nИсточник: {link}\n\n⚠️ Черновик требует ручной проверки."
        if recommendation == "hold":
            send(chat, "⚠️ Редактор: публикация рекомендуется только после дополнительной проверки. Решение о публикации остаётся за администратором.")
    except Exception as e:
        print("AI ERROR:", repr(e))
        post = (
            f"⚠️ AI-редактор временно недоступен.\n\n"
            f"Черновик: {title}\n\n{summary[:900]}\n\n"
            f"Источник: {link}\n\n"
            "Новость НЕ считается проверенной."
        )

    buttons = [[
        {"text":"✅ Опубликовать","callback_data":"pub"},
        {"text":"❌ Отклонить","callback_data":"no"}
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
        elif text == "🗺 Новости по регионам":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🗺 РОССИЯ ПО РЕГИОНАМ\\n\\nВыбери федеральный округ или региональный блок:",
                "reply_markup": json.dumps({"keyboard": region_keyboard(), "resize_keyboard": True, "is_persistent": True}, ensure_ascii=False)
            })
        elif text == "🗺 Россия по регионам":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🗺 РОССИЯ ПО РЕГИОНАМ\n\nВыбери федеральный уровень или региональный блок:",
                "reply_markup": json.dumps({"keyboard": region_keyboard(), "resize_keyboard": True}, ensure_ascii=False)
            })
        elif text == "🇷🇺 Россия":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🇷🇺 РОССИЯ\n\nВыбери направление:",
                "reply_markup": json.dumps({"keyboard": russia_keyboard(), "resize_keyboard": True, "is_persistent": True}, ensure_ascii=False)
            })
        elif text == "🇷🇺 Россия — федеральные новости":
            threading.Thread(target=process_news, args=(chat, "russia"), daemon=True).start()
        elif text == "🇷🇺 Федеральные новости":
            threading.Thread(target=process_news, args=(chat, "russia"), daemon=True).start()
        elif text == "↩️ Главное меню":
            send_menu(chat)
        elif text == "↩️ История":
            HISTORY_MODE.pop(chat, None)
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🏛 ИСТОРИЯ\n\nВыбери формат:",
                "reply_markup": json.dumps({"keyboard": history_keyboard(), "resize_keyboard": True, "is_persistent": True}, ensure_ascii=False)
            })
        elif text == "↩️ Регионы":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🗺 Выбери регион:",
                "reply_markup": json.dumps({"keyboard": region_keyboard(), "resize_keyboard": True}, ensure_ascii=False)
            })
        elif text.startswith("📍 "):
            region = text[3:].strip()
            if region in REGION_QUERIES:
                if HISTORY_MODE.get(chat) == ("region_select", None):
                    HISTORY_MODE[chat] = ("region", region)
                    threading.Thread(target=history_day, args=(chat, "region", region), daemon=True).start()
                    tg("sendMessage", {
                        "chat_id": chat,
                        "text": f"⏳ Ищу значимые события {region}, произошедшие в этот день в разные годы…",
                        "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
                    })
                else:
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
        elif text.startswith("🏛 Кремль — "):
            region = text[len("🏛 Кремль — "):]
            threading.Thread(target=process_news, args=(chat, "kremlin", region), daemon=True).start()
        elif text.startswith("📡 События — "):
            region = text[len("📡 События — "):]
            threading.Thread(target=process_news, args=(chat, "events", region), daemon=True).start()
        elif text.startswith("/news") or text == "📰 Новости":
            threading.Thread(target=process_news, args=(chat, "news"), daemon=True).start()
        elif text == "🌍 Мир":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🌍 МИР\n\nВыбери направление:",
                "reply_markup": json.dumps({"keyboard": world_keyboard(), "resize_keyboard": True, "is_persistent": True}, ensure_ascii=False)
            })
        elif text == "🌍 Мировые новости":
            threading.Thread(target=process_news, args=(chat, "world"), daemon=True).start()
        elif text == "📡 Мировые события":
            threading.Thread(target=process_news, args=(chat, "events"), daemon=True).start()
        elif text == "🚨 Мировые происшествия":
            threading.Thread(target=process_news, args=(chat, "incidents"), daemon=True).start()
        elif text == "⚡ Мировые экстренные новости":
            threading.Thread(target=process_news, args=(chat, "emergency"), daemon=True).start()
        elif text == "⚔️ Международные конфликты":
            threading.Thread(target=process_news, args=(chat, "conflicts"), daemon=True).start()
        elif text == "📡 События":
            threading.Thread(target=process_news, args=(chat, "events"), daemon=True).start()
        elif text == "🚨 Происшествия":
            threading.Thread(target=process_news, args=(chat, "incidents"), daemon=True).start()
        elif text == "⚡ Экстренно":
            threading.Thread(target=process_news, args=(chat, "emergency"), daemon=True).start()
        elif text == "🕵️ Криминал":
            threading.Thread(target=process_news, args=(chat, "crime"), daemon=True).start()
        elif text in ("🔎 Розыск", "🔎 Внимание: розыск"):
            threading.Thread(target=process_news, args=(chat, "wanted"), daemon=True).start()
        elif text in ("🏛 Кремль", "🏛 Новости Кремля"):
            threading.Thread(target=process_news, args=(chat, "kremlin"), daemon=True).start()
        elif text in ("⚔️ СВО", "⚔️ СВО / конфликты"):
            threading.Thread(target=process_news, args=(chat, "conflicts"), daemon=True).start()
        elif text == "📡 Анализ Telegram-каналов по СВО":
            threading.Thread(target=process_news, args=(chat, "conflicts"), daemon=True).start()
        elif text in ("🔬 Наука и технологии России",):
            threading.Thread(target=process_news, args=(chat, "russia_tech"), daemon=True).start()
        elif text == "⚖️ Законы и штрафы":
            threading.Thread(target=process_news, args=(chat, "laws"), daemon=True).start()
        elif text == "🤖 ИИ / технологии":
            threading.Thread(target=process_news, args=(chat, "tech"), daemon=True).start()
        elif text == "💰 Экономика":
            threading.Thread(target=process_news, args=(chat, "economy"), daemon=True).start()
        elif text == "🚗 Авто":
            threading.Thread(target=process_news, args=(chat, "auto"), daemon=True).start()
        elif text == "😂 Юмор":
            threading.Thread(target=process_news, args=(chat, "humor"), daemon=True).start()
        elif text == "🏛 История":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🏛 ИСТОРИЯ\n\nВыбери формат:",
                "reply_markup": json.dumps({"keyboard": history_keyboard(), "resize_keyboard": True, "is_persistent": True}, ensure_ascii=False)
            })
        elif text == "📅 Этот день в истории":
            tg("sendMessage", {
                "chat_id": chat,
                "text": "📅 ЭТОТ ДЕНЬ В ИСТОРИИ\n\nВыбери охват:",
                "reply_markup": json.dumps({"keyboard": history_scope_keyboard(), "resize_keyboard": True}, ensure_ascii=False)
            })
        elif text == "🇷🇺 Россия — этот день":
            HISTORY_MODE[chat] = ("russia", None)
            threading.Thread(target=history_day, args=(chat, "russia"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🌍 Мир — этот день":
            HISTORY_MODE[chat] = ("world", None)
            threading.Thread(target=history_day, args=(chat, "world"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🇷🇺 История России":
            HISTORY_MODE[chat] = ("russia", None)
            threading.Thread(target=history_day, args=(chat, "russia"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🌍 История мира":
            HISTORY_MODE[chat] = ("world", None)
            threading.Thread(target=history_day, args=(chat, "world"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🗺 История по регионам":
            HISTORY_MODE[chat] = ("region_select", None)
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🗺 Выбери регион:",
                "reply_markup": json.dumps({"keyboard": history_region_keyboard(), "resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🔥 Тренды":
            threading.Thread(target=process_news, args=(chat, "trends"), daemon=True).start()
        elif re.fullmatch(r"\d{4}", text.strip()) and chat in HISTORY_MODE:
            mode = HISTORY_MODE.pop(chat)
            year = int(text.strip())
            if 1 <= year <= 2100:
                scope = mode[0]
                region = mode[1] if len(mode) > 1 else None
                threading.Thread(target=history_day, args=(chat, year, scope, region), daemon=True).start()
            else:
                send(chat, "⚠️ Введи корректный год, например: 1753.")
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
