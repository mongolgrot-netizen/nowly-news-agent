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
        [{"text": "🌍 Мир"}],
        [{"text": "🇷🇺 Россия"}],
        [{"text": "🗺 Россия по регионам"}],
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
        [{"text": "🇷🇺 Россия"}],
        [{"text": "🌍 Мир"}],
        [{"text": "🗺 По регионам России"}],
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

def history_day(chat, year, scope="world", region=None):
    # Бесплатные открытые источники Wikimedia. Сначала берем страницу
    # конкретной даты, затем при необходимости страницу года.
    from datetime import datetime
    now = datetime.now()
    day = f"{now.day} {['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'][now.month-1]}"
    send(chat, f"📅 Ищу события {day} {year} года...")
    try:
        date_title = f"{now.day}_{['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'][now.month-1]}"
        url = "https://ru.wikipedia.org/w/api.php"
        params = {"action":"query","prop":"extracts","explaintext":"1","titles":date_title,"format":"json","formatversion":"2"}
        rr = requests.get(url, params=params, timeout=20, headers={"User-Agent":"NOWLY-News-Agent/1.0"})
        rr.raise_for_status()
        pages = rr.json().get("query",{}).get("pages",[])
        text_ru = pages[0].get("extract","") if pages else ""
        if not text_ru:
            raise RuntimeError("Не удалось получить исторические материалы")
        # Ограничиваем объем, чтобы не расходовать бесплатный Groq TPM.
        text_ru = text_ru[:14000]
        scope_text = {
            "russia":"Россия",
            "world":"мир",
            "region": f"регион {region}" if region else "регионы России"
        }.get(scope, "мир")
        prompt = f"""Ты исторический редактор Telegram-канала NOWLY.
Сегодняшняя дата: {day}. Нужны события именно {day} {year} года.
Охват: {scope_text}.
Ниже текст открытой энциклопедической страницы.

Строго:
- выбери только события, относящиеся к {year} году и именно к этой календарной дате;
- для России учитывай Российскую империю, СССР и современную Россию, если это исторически уместно;
- для региона {region or 'не указан'} бери только события, реально связанные с ним;
- не путай дату события с датой рождения/смерти, если это не указано как событие;
- если точных событий нет, честно напиши, что надежных данных не найдено;
- не выдумывай;
- 2-4 наиболее интересных пункта;
- русский язык;
- каждый пункт: год/дата — событие;
- в конце: Источник: Википедия.

Текст:
{text_ru}
"""
        post = groq(prompt, 0.2, 450)
        buttons = [[{"text":"✅ Опубликовать","callback_data":"pub"},{"text":"❌ Отклонить","callback_data":"no"}]]
        send(chat, post, buttons)
    except Exception as e:
        print("HISTORY ERROR:", repr(e))
        send(chat, f"⚠️ Не удалось подготовить историческую публикацию.\n\n{str(e)[:400]}")

def world_keyboard():
    return [
        [{"text": "🌍 Мировые новости"}],
        [{"text": "⚔️ Международные конфликты"}],
        [{"text": "🤖 ИИ / технологии"}, {"text": "💰 Экономика"}],
        [{"text": "🚗 Авто"}, {"text": "🔥 Тренды"}],
        [{"text": "😂 Юмор"}, {"text": "🏛 История"}],
        [{"text": "↩️ Главное меню"}]
    ]

def russia_keyboard():
    return [
        [{"text": "🇷🇺 Федеральные новости"}],
        [{"text": "📡 События"}, {"text": "🚨 Происшествия"}],
        [{"text": "⚡ Экстренно"}, {"text": "🕵️ Криминал"}],
        [{"text": "🔎 Розыск"}, {"text": "🏛 Кремль"}],
        [{"text": "⚔️ СВО / конфликты"}],
        [{"text": "🤖 ИИ / технологии"}, {"text": "💰 Экономика"}],
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

    for item in selected:
        title, link, summary, region = item
        try:
            related = related_items((title, link, summary, region), items)
            searched = search_related_news((title, link, summary, region))
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

            fact = fact_check((title, link, summary, region), related)
            labels = {
                "confirmed": "🟢 подтверждено",
                "partial_confirmed": "🟠 частично подтверждено",
                "attributed": "🟡 заявление / атрибуция",
                "conflict": "🔴 источники расходятся",
                "single_source": "⚪ один источник"
            }
            send(chat, f"🔎 Проверка: {labels.get(fact.get('status'), '⚪ не определено')}\n{fact.get('reason','')[:700]}")

            source_list = [(title, link)] + [(x[0], x[1]) for x in related[:5]]
            post = ai_post(
                title, link, summary + f"\nРегион: {region}", category, fact,
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
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🇷🇺 РОССИЯ\n\nВыбери направление:",
                "reply_markup": json.dumps({"keyboard": russia_keyboard(), "resize_keyboard": True, "is_persistent": True}, ensure_ascii=False)
            })
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
                    tg("sendMessage", {
                        "chat_id": chat,
                        "text": f"🗺 ИСТОРИЯ — {region}\n\nВведи год, например: 1753",
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
        elif text == "🇷🇺 История России":
            HISTORY_MODE[chat] = ("russia", None)
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🇷🇺 Введи год, например: 1753",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🌍 История мира":
            HISTORY_MODE[chat] = ("world", None)
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🌍 Введи год, например: 1753",
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
