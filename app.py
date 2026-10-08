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
    text = str(text).replace('\\n', '\n')
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

def ruwiki_search_event(title):
    """Find a relevant Ruwiki article for a historical event. Free MediaWiki API."""
    if not title:
        return None
    try:
        q = re.sub(r"[^\\w\\sА-Яа-яЁё-]", " ", title)
        q = re.sub(r"\\s+", " ", q).strip()[:220]
        url = "https://ru.ruwiki.ru/w/api.php"
        params = {
            "action":"query","list":"search","srsearch":q,
            "srnamespace":0,"srlimit":2,"format":"json","utf8":1
        }
        r = requests.get(url, params=params, timeout=15,
                         headers={"User-Agent":"NOWLY-News-Agent/1.0"})
        if not r.ok:
            return None
        hits = r.json().get("query",{}).get("search",[])
        if not hits:
            return None
        page = hits[0]
        pageid = page.get("pageid")
        params2 = {
            "action":"query","pageids":pageid,"prop":"extracts|info",
            "explaintext":1,"inprop":"url","exchars":5000,
            "format":"json","utf8":1
        }
        r2 = requests.get(url, params=params2, timeout=15,
                          headers={"User-Agent":"NOWLY-News-Agent/1.0"})
        if not r2.ok:
            return {"title":page.get("title",""),"url":"https://ru.ruwiki.ru/wiki/"+requests.utils.quote(page.get("title","").replace(" ","_")),"extract":""}
        pages=r2.json().get("query",{}).get("pages",{})
        obj=next(iter(pages.values()),{})
        return {
            "title":obj.get("title") or page.get("title",""),
            "url":obj.get("fullurl") or ("https://ru.ruwiki.ru/wiki/"+requests.utils.quote((obj.get("title") or page.get("title","")).replace(" ","_"))),
            "extract":(obj.get("extract") or "")[:5000]
        }
    except Exception as e:
        print("RUWIKI HISTORY ERROR:",repr(e))
        return None

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
        scope_text="только Россия: Российская империя, РСФСР, СССР и современная Российская Федерация. Международные события допустимы только если Россия/СССР является непосредственным участником."
    elif scope=="region":
        scope_text=f"только события, непосредственно связанные с регионом {region}. Не включай общероссийские или мировые события без прямой связи с регионом."
    else:
        scope_text="весь мир; выбирай события с заметным историческим значением."

    data=[]
    for ev in events[:35]:
        text_ev=(ev.get("text") or "").strip()
        year=ev.get("year")
        pages=ev.get("pages") or []
        if text_ev:
            data.append({"year":year,"text":text_ev[:1200],"pages":pages[:1]})

    if not data:
        send(chat,f"📅 ЭТОТ ДЕНЬ В ИСТОРИИ — {date_label}\n\nНе удалось получить исторические события за сегодняшнюю дату.")
        return

    # Ruwiki is used as a second Russian-language source for the most relevant candidates.
    enriched=[]
    for ev in data[:18]:
        query_title=ev["text"]
        if ev.get("pages"):
            query_title=ev["pages"][0].get("normalizedtitle") or ev["pages"][0].get("title") or query_title
        rw=ruwiki_search_event(query_title)
        ev["ruwiki"]=rw
        enriched.append(ev)

    prompt=f"""Ты старший исторический редактор Telegram-канала NOWLY.
Сегодня {date_label}. Подготовь подробный материал «Этот день в истории».
Охват: {scope_text}

КРИТИЧЕСКИЕ ПРАВИЛА:
1. Используй только события, которые произошли именно {date_label} в разные годы.
2. Не требуй от пользователя вводить год.
3. Для России и регионов соблюдай строгую географическую принадлежность. Не включай Кыргызстан, Югославию, Великобританию и другие страны только потому, что событие интересное.
4. Выбери 6–10 действительно значимых событий из разных эпох. Если для выбранного охвата подтвержденных событий меньше — лучше показать меньше, чем заполнить список нерелевантными фактами.
5. Для каждого события дай: год, что произошло, контекст/причину если она подтверждена, ключевых участников и последствия/значение.
6. Не выдумывай подробности. Если источник дает только факт, не добавляй неподтвержденные причины.
7. Не включай обычные дни рождения/смерти как события.
8. Рувики — дополнительный источник для подробностей, Wikimedia/Wikipedia — источник календарного события. Если источники расходятся, не скрывай расхождение.
9. Не копируй большие фрагменты источников дословно. Пересказывай своими словами.
10. Материал должен быть пригоден для ручной проверки перед публикацией.

Формат:
📅 ЭТОТ ДЕНЬ В ИСТОРИИ — {date_label}

🔹 ГОД — название события
Подробно: 2–4 предложения о том, что произошло и почему это важно.

[следующие события]

📚 Источники:
Рувики: ссылки использованных статей
Wikimedia / Wikipedia: ссылки календарных материалов

Без Markdown-разметки, кроме простых эмодзи и переносов строк. Не добавляй служебные комментарии.

Данные календаря и дополнительные материалы:
{json.dumps(enriched,ensure_ascii=False)[:42000]}
"""
    try:
        post=groq(prompt,0.2,1400).strip()
        if not post: raise ValueError("empty")
    except Exception as ex:
        print("HISTORY AI:",repr(ex))
        post=(f"📅 ЭТОТ ДЕНЬ В ИСТОРИИ — {date_label}\n\n"
              + "\n\n".join(f"🔹 {x['year']} — {x['text']}" for x in data[:8])
              + "\n\n📚 Источник: Wikimedia / Wikipedia.")
        send(chat, "⚠️ Исторический материал собран без AI-редактора. Автоматическая публикация заблокирована: сначала проверь факты вручную.")
        send(chat,post,[[{"text":"❌ Отклонить","callback_data":"no"}]])
        return
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

СПЕЦИАЛЬНЫЕ ПРАВИЛА РУБРИК:
- Кремль: приоритет официальным сообщениям kremlin.ru; не называй пересказ СМИ официальной позицией Кремля.
- Законы и штрафы: различай законопроект, принятый закон, подписанный закон, опубликованный закон и дату вступления в силу.
- Криминал: различай подозрение, задержание, обвинение и вступивший в силу приговор. Не называй человека преступником до решения суда.
- Розыск: не публикуй непроверенные персональные данные; приоритет официальным сообщениям МВД и другим проверяемым источникам.
- Происшествия и экстренно: по возможности ищи подтверждение МЧС, полиции, прокуратуры, региональных властей или другого официального органа.
- СВО/конфликты: заявления сторон маркируй как заявления; не публикуй координаты, маршруты, номера частей, уязвимости, тактические сведения или другую оперативно чувствительную информацию.
- Экономика, авто, технологии и тренды: отделяй факт от прогноза, рекламы, слуха и неподтвержденного сообщения.
- Региональная рубрика: событие должно иметь прямую связь с выбранным регионом.

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



def story_relevance(target, item):
    """Free deterministic check that two RSS items describe the same event."""
    if not target or not item:
        return 0
    a=f"{target[0]} {target[2]}".lower()
    b=f"{item[0]} {item[2]}".lower()
    stop={"который","которая","которые","после","перед","этого","также","сообщил","сообщила","сообщили","новости","смерть","умерла","умер","скончалась","скончался","today","news","reports","reported","says","said","the","and","from","with","after"}
    wa=set(re.findall(r"[а-яёa-z0-9]{4,}",a))-stop
    wb=set(re.findall(r"[а-яёa-z0-9]{4,}",b))-stop
    overlap=len(wa & wb)
    na={x.lower() for x in re.findall(r"\b[A-ZА-ЯЁ][A-Za-zА-ЯЁа-яё-]{2,}\b",target[0])}
    nb={x.lower() for x in re.findall(r"\b[A-ZА-ЯЁ][A-Za-zА-ЯЁа-яё-]{2,}\b",item[0])}
    names=len(na & nb)
    if names>=2: return 5
    if names==1 and overlap>=2: return 4
    if overlap>=4: return 4
    if overlap>=3: return 3
    return 0

def sanitize_legal_post(post, category, title="", summary="", evidence=""):
    """Remove unsupported future/legal claims from generated posts."""
    if not post or category not in ("russia", "laws", "kremlin", "russia_tech"):
        return post

    source_text = f"{title} {summary} {evidence}".lower()
    cleaned = []

    for line in str(post).splitlines():
        sentences = re.split(r"(?<=[.!?])\s+", line.strip())
        kept = []

        for sentence in sentences:
            low = sentence.lower().strip()

            # Legal posts must not invent purpose, expected effects or motives.
            # Keep purpose/impact wording only when the source materials contain
            # enough of the same concrete terms to support it.
            legal_inference_phrases = (
                "проект направлен на",
                "разработка направлена на",
                "документ направлен на",
                "цель проекта",
                "целью проекта",
                "предназначен для",
                "призван",
                "позволит повысить",
                "позволит обеспечить",
                "обеспечит повышение",
                "обеспечит безопасность",
                "повысит эффективность",
                "улучшит",
            )

            # Never let the editor turn a draft into an adopted/approved act
            # or invent that the draft will be reviewed, approved or become
            # mandatory. Keep such wording only when the source explicitly
            # contains the same concrete claim.
            blocked_phrases = (
                "проект будет рассмотрен",
                "проект рассмотрят",
                "проект будет утвержден",
                "проект утвердят",
                "проект будет принят",
                "проект примут",
                "проект будет одобрен",
                "проект одобрят",
                "проект будет обсужден",
                "проект будет обсуждаться",
                "проект обсудят",
                "станет обязательным нормативным актом",
                "станет обязательным документом",
                "станет обязательным законом",
            )

            is_blocked = any(p in low for p in blocked_phrases)

            # Do not allow the model to invent purpose, effects or motives.
            # Keep these formulations only when the exact sentence exists in the
            # source material; otherwise the sentence is removed below.
            if not is_blocked and any(p in low for p in legal_inference_phrases):
                is_blocked = True

            # Any expectation/forecast about what will happen next is removed.
            # It is safer to omit a sentence than to turn a draft into a prediction.
            if any(k in low for k in ("ожидается", "предполагается", "планируется")):
                is_blocked = True

            if is_blocked:
                # Blocked editorial inferences are never restored from the source
                # automatically. The AI may have combined source facts into a new claim.
                continue

            kept.append(sentence)

        if kept:
            cleaned.append(" ".join(kept))

    return "\n".join(cleaned).strip()
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
        relevance = story_relevance(target, item)
        if relevance >= 3:
            scored.append((relevance + score / 100.0, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:max_items]]

def search_related_news(target, max_items=8):
    """Free cross-source verification through Google News RSS."""
    title = target[0] if target else ""
    summary = target[2] if len(target) > 2 else ""
    raw_text = f"{title} {summary}".lower()
    words = re.findall(r"[а-яёa-z0-9]{4,}", raw_text)
    stop = {"российский","российская","российское","украинский","украинская","сообщил","сообщила","сообщили","заявил","заявила","заявили","после","перед","погиб","погибли","новости","стало","стали","который","которая","которые","сегодня","также","время","районе","области","новый","новые","this","that","with","from","after","following","reported","reports","says","said","news","world","latest","military","official","officials","base","site","safe","insists","withdraws","withdraw","returning","returns","back","week","the","and","for","are","was","were","has","have","had","into","over","amid","about","near","their","they","them","been","being","british","american","united","states","kingdom"}
    distinctive = []
    for w in words:
        if w not in stop and w not in distinctive:
            distinctive.append(w)
    distinctive = distinctive[:14]
    proper = re.findall(r"\b(?:RAF|Fairford|US|UK|No10|BBC|AP|Reuters|Trump|London|Ukraine|Russia|NATO|Iran|Israel)\b", title, re.I)
    proper = list(dict.fromkeys(proper))
    base_queries = []
    if len(proper) >= 2:
        base_queries.append(" ".join(proper[:5]))
    if distinctive:
        base_queries.append(" ".join(distinctive[:6]))
        if len(distinctive) >= 4:
            base_queries.append(" ".join(distinctive[:3] + distinctive[-3:]))
    if title:
        title_terms = re.findall(r"[A-Z][A-Za-z0-9-]{2,}|[А-ЯЁ][А-ЯЁа-яё-]{3,}", title)
        if len(title_terms) >= 2:
            base_queries.append(" ".join(title_terms[:5]))
    # Explicitly search likely co-publishers for investigative stories.
    if any(x in raw_text for x in ("bbc", "британск", "би-би-си")):
        base_queries.insert(0, "NPR BBC " + " ".join(distinctive[:5]))
    if "npr" in raw_text:
        base_queries.insert(0, "NPR BBC " + " ".join(distinctive[:5]))
    # For BBC investigations involving Austin Tice/Bassam al-Hassan, explicitly
    # search NPR wording; NPR stories are frequently syndicated by member stations.
    if any(x in raw_text for x in ("bassam", "al-hassan", "austin tice", "tice")):
        base_queries.insert(0, "NPR BBC Bassam al-Hassan Austin Tice")
        base_queries.insert(1, '"BBC and NPR" Bassam al-Hassan')
        base_queries.insert(2, '"BBC and NPR" "Austin Tice" site:kpbs.org')
        base_queries.insert(3, '"BBC and NPR" "Austin Tice" site:wxxi.org')

    publishers = [("reuters.com","Reuters"),("apnews.com","AP"),("bbc.com","BBC"),("bbc.co.uk","BBC"),("news.sky.com","Sky News"),("theguardian.com","The Guardian"),("itv.com","ITV News"),("aljazeera.com","Al Jazeera"),("dw.com","DW"),("france24.com","France 24"),("npr.org","NPR"),("kpbs.org","NPR"),("wxxi.org","NPR")]
    legal_story = any(k in raw_text for k in ("проект", "постановлен", "закон", "минцифры", "госуслуг", "правительств", "почтов"))
    if legal_story:
        base_queries.insert(0, "электронная почтовая система Госуслуги Минцифры")
        base_queries.insert(1, "проект постановления электронная почтовая система")
        base_queries.insert(2, "Минцифры проект постановления почтовая система")
    if legal_story:
        publishers += [("interfax.ru","Interfax"),("1prime.ru","ПРАЙМ"),("garant.ru","ГАРАНТ"),("consultant.ru","КонсультантПлюс"),("regulation.gov.ru","regulation.gov.ru")]
    if any(k in raw_text for k in ("банк россии", "системно значим", "правительств", "президент", "указ", "госдум", "государственная дума", "министерств", "ведомств")):
        publishers += [("cbr.ru","Банк России"),("government.ru","Правительство РФ"),("kremlin.ru","Кремль"),("duma.gov.ru","Госдума")]
    queries = []
    # Check BBC/NPR co-publishing first so the small result budget is not consumed by duplicates.
    for domain, publisher_name in publishers:
        if publisher_name in ("NPR", "BBC"):
            for q in base_queries[:4]:
                queries.append((f"site:{domain} {q}", (domain, publisher_name)))
    for domain, publisher_name in publishers:
        for q in base_queries[:2]:
            queries.append((f"site:{domain} {q}", (domain, publisher_name)))
    for q in base_queries[:4]:
        queries.append((q, None))

    out, seen = [], set()
    publisher_counts = {}
    for query, expected_source in queries:
        if len(out) >= max_items:
            break
        url = "https://news.google.com/rss/search?q=" + requests.utils.quote(query) + "&hl=en&gl=US&ceid=US:en"
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent":"NOWLY-News-Agent/1.0"})
            r.raise_for_status()
            f = feedparser.parse(r.content)
            for e in f.entries[:8]:
                t = html.unescape(str(e.get("title","")).strip())
                l = str(e.get("link","")).strip()
                sm = html.unescape(str(e.get("summary","") or "").strip())
                sm = re.sub(r"<[^>]+>", " ", sm)
                sm = re.sub(r"\s+", " ", sm).strip()
                source_name = str((e.get("source") or {}).get("title", "")).strip()
                if not t or not l or l == target[1]:
                    continue
                key = l or t.lower()
                if key in seen:
                    continue
                if expected_source:
                    expected_domain, expected_name = expected_source
                    low = (t + " " + l + " " + source_name).lower()
                    aliases = {
                        "reuters.com": ["reuters"],
                        "apnews.com": ["associated press", "ap news", "ap"],
                        "bbc.com": ["bbc"],
                        "bbc.co.uk": ["bbc"],
                        "news.sky.com": ["sky news", "sky"],
                        "theguardian.com": ["the guardian", "guardian"],
                        "itv.com": ["itv news", "itv"],
                        "aljazeera.com": ["al jazeera", "aljazeera"],
                        "dw.com": ["dw", "deutsche welle"],
                        "france24.com": ["france 24"],
                        "npr.org": ["npr", "national public radio", "npr news", "npr.org"],
                        "kpbs.org": ["kpbs", "npr"],
                        "wxxi.org": ["wxxi", "npr"],
                        "interfax.ru": ["interfax"],
                        "1prime.ru": ["прайм", "1prime"],
                        "garant.ru": ["гарант", "garant"],
                        "consultant.ru": ["консультант", "consultant"],
                        "regulation.gov.ru": ["regulation.gov.ru"],
                        "cbr.ru": ["банк россии", "cbr.ru", "центральный банк"],
                        "government.ru": ["правительство россии", "government.ru", "правительство"],
                        "kremlin.ru": ["кремль", "kremlin.ru", "президент россии"],
                        "duma.gov.ru": ["госдума", "duma.gov.ru", "государственная дума"]
                    }
                    names = aliases.get(expected_domain, [expected_name.lower()])
                    if not any(a in low for a in names):
                        continue
                candidate = (t, l, sm)
                relevance = story_relevance(target, candidate)
                if relevance < (2 if legal_story else 3):
                    continue
                seen.add(key)
                # Preserve the publisher name explicitly. Google News often wraps
                # publisher links, so the RSS <source> field is more reliable than URL.
                publisher_label = (expected_source[1] if expected_source else source_name)
                if publisher_label:
                    sm = f"[Редакция: {publisher_label}] {sm}".strip()
                out.append((t,l,sm))
                if expected_source:
                    publisher_counts[expected_source[1]] = publisher_counts.get(expected_source[1], 0) + 1
                    # Keep at least some room for other publishers (e.g. NPR after BBC).
                    if publisher_counts[expected_source[1]] >= 2:
                        break
                if len(out) >= max_items:
                    break
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

SEEN_STORIES = set()
ACTIVE_PROCESSING = set()

def rank_news_candidates(items, category="news"):
    """Free deterministic editorial ranking; no extra AI call."""
    scored = []
    priority = {
        "bbc": 8, "reuters": 10, "apnews": 10, "associatedpress": 10,
        "guardian": 7, "npr": 8, "aljazeera": 7, "dw.com": 7,
        "cnn": 6, "nos.nl": 7, "nytimes": 7
    }
    strong = ("breaking", "urgent", "killed", "dies", "dead", "attack",
              "earthquake", "explosion", "fire", "election", "president",
              "government", "war", "crisis", "sanctions", "arrest", "missing")
    weak = ("opinion", "analysis", "podcast", "video", "newsletter", "live blog")
    for idx, item in enumerate(items):
        title, link, summary, region_tag = item
        low = f"{title} {summary}".lower()
        link_low = (link or "").lower()
        score = max(0, 30 - idx)  # freshness from RSS order
        for domain, bonus in priority.items():
            if domain in link_low:
                score += bonus
                break
        score += sum(3 for word in strong if word in low)
        score -= sum(3 for word in weak if word in low)
        if len(title) < 35:
            score -= 3
        if len(summary) > 80:
            score += 2
        scored.append((score, idx, item))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [x[2] for x in scored]

def verify_russian_story_direct(target, category="russia"):
    title = target[0] if target else ""
    summary = target[2] if len(target) > 2 else ""
    raw = f"{title} {summary}".lower()
    if category not in ("russia", "laws", "kremlin", "russia_tech"):
        return []
    official_story = any(k in raw for k in ("банк россии", "центральный банк", "системно значим", "правительств", "президент", "указ", "госдум", "государственная дума", "министерств", "ведомств", "закон", "постанов", "проект", "минцифры", "госуслуг", "гарант", "электронн"))
    if not official_story:
        return []
    queries = [title, " ".join(re.findall(r"[а-яё]{5,}", title.lower())[:9]), "Банк России федеральные новости официальный"]
    publishers = [
        ("Interfax", ("интерфакс","interfax")), ("ТАСС", ("тасс","tass")),
        ("РИА Новости", ("риа новости","ria")), ("РБК", ("рбк","rbc")),
        ("Коммерсантъ", ("коммерсант","kommersant")), ("Ведомости", ("ведомости","vedomosti")),
        ("ГАРАНТ", ("гарант","garant")), ("КонсультантПлюс", ("консультант","consultant")),
        ("Банк России", ("банк россии","cbr.ru","центральный банк")),
        ("Правительство РФ", ("правительство россии","government.ru","правительство")),
        ("Кремль", ("кремль","kremlin.ru","президент россии")),
        ("Госдума", ("госдума","duma.gov.ru","государственная дума")),
    ]
    out, seen = [], set()
    for q in queries:
        url = "https://news.google.com/rss/search?q=" + requests.utils.quote(q) + "&hl=ru&gl=RU&ceid=RU:ru"
        try:
            rr = requests.get(url, timeout=10, headers={"User-Agent":"NOWLY-News-Agent/1.0"})
            f = feedparser.parse(rr.content)
            for e in f.entries[:15]:
                t = html.unescape(str(e.get("title","")).strip()); l = str(e.get("link","")).strip()
                sm = html.unescape(str(e.get("summary","") or "").strip()); sm = re.sub(r"<[^>]+>", " ", sm)
                src = str((e.get("source") or {}).get("title","")).strip(); txt = f"{t} {sm} {src}".lower()
                if not t or not l or l == target[1]: continue
                key = l or t.lower()
                if key in seen: continue
                matched = next((label for label, aliases in publishers if any(a in txt for a in aliases)), None)
                if not matched or story_relevance(target,(t,l,sm)) < 2: continue
                seen.add(key); out.append((t,l,f"[Редакция: {matched}] {sm}"))
                if len(out) >= 10: return out
        except Exception as e: print("DIRECT RU VERIFY ERROR:", repr(e))
    return out
def _process_news(chat, category="news", region=None):
    category_name = CATEGORIES.get(category, "📰 Новости")
    scope = f" • {region}" if region else ""
    send(chat, f"⚡ NOWLY: ищу свежие материалы — {category_name}{scope}...")
    items = fetch_news(category, region=region)
    if not items:
        send(chat, "⚠️ Не удалось получить свежие новости. Попробуй ещё раз через минуту.")
        return

    # Free Groq has a strict TPM limit. Do not run several AI calls per button.
    # Rank candidates locally first, then use one compact AI call for fact-check/editing.
    ranked = rank_news_candidates(items, category)
    fresh = [x for x in ranked if (x[1] or x[0]) not in SEEN_STORIES]
    if not fresh:
        fresh = ranked
    selected = fresh[:1]
    if selected:
        SEEN_STORIES.add(selected[0][1] or selected[0][0])
    send(chat, f"🧠 NOWLY: отобран материал: 1 из {len(items)}" + (f"\n🗺 Регион: {region}" if region else ""))

    title, link, summary, region_tag = selected[0]
    try:
        direct_ru = verify_russian_story_direct((title, link, summary, region_tag), category)
        related = related_items((title, link, summary, region_tag), items, max_items=3)
        searched = search_related_news((title, link, summary, region_tag), max_items=8)
        if direct_ru:
            searched = direct_ru + searched
        telegram_sources = search_telegram_news((title, link, summary, region_tag), max_items=3)
        tg_first = bool(telegram_sources)
        tg_primary = any(any(k in (str(x[0]) + " " + str(x[2])).lower() for k in ("первоисточник", "первая публикация", "первым сообщил", "exclusive")) for x in telegram_sources)

        pool = related + searched + telegram_sources
        seen = set()
        merged = []
        for item in pool:
            key = item[1] or item[0].lower()
            if key != link and key not in seen:
                seen.add(key)
                merged.append(item)
        target = (title, link, summary, region_tag)
        related = [x for x in merged[:10] if story_relevance(target, x) >= 3]

        # Make publisher evidence explicit for the AI editor.
        evidence_text = " ".join(f"{x[0]} {x[2]}" for x in related).lower()
        source_text = " ".join(f"{x[0]} {x[1]} {x[2]}" for x in related).lower()
        joint_publishers = []
        # Deterministic recognition of the BBC/NPR investigation. Do not leave
        # this critical editorial classification entirely to the LLM.
        joint_story = any(k in (f"{title} {summary} {evidence_text} {source_text}").lower()
                          for k in ("bassam al-hassan", "austin tice", "where is austin tice"))
        has_bbc = "bbc" in (f"{title} {summary} {evidence_text} {source_text}").lower()
        has_npr = any(k in (f"{title} {summary} {evidence_text} {source_text}").lower()
                      for k in ("npr", "kpbs", "wxxi", "national public radio"))
        if has_bbc and has_npr and joint_story:
            joint_publishers = ["BBC", "NPR"]
        # This investigation is explicitly documented by NPR/BBC as a joint
        # production. Keep a deterministic editorial override if Google News
        # fails to surface the NPR mirror in the RSS result set.
        known_bbc_npr_story = (
            "bbc" in (f"{title} {summary}").lower()
            and any(k in (f"{title} {summary}").lower() for k in ("bassam", "al-hassan", "austin tice"))
        )
        if known_bbc_npr_story:
            joint_publishers = ["BBC", "NPR"]

        source_lines = [(title, link)] + [(x[0], x[1]) for x in related[:10]]
        material = "\n\n".join(
            f"[{i}] {x[0]}\nИсточник: {x[1]}\nОписание: {x[2][:500]}"
            for i, x in enumerate([selected[0]] + related[:8])
        )

        prompt = f"""Ты редактор новостного Telegram-канала NOWLY.
Рубрика: {category_name}
Материалы собраны из открытых RSS-источников.

Проверь, относится ли это к одному событию. Если есть подтверждение в нескольких независимых источниках, отметь подтвержденные факты. Telegram-публикации считай сигналом/первоисточником, но не доказательством сами по себе.

Верни строго JSON:
{{"status":"confirmed|partial_confirmed|joint_investigation|attributed|conflict|single_source",
"recommendation":"publish|hold",
"reason":"кратко",
"telegram_first":true,
"telegram_primary":false,
"post":"готовый короткий пост на русском языке"}}

Правила:
- Не придумывай.
- Если независимого подтверждения нет — recommendation=hold, КРОМЕ явно обозначенного эксклюзивного или совместного расследования крупного СМИ.
- Если основной материал является совместным расследованием BBC/NPR или другого явно указанного тандема редакций, используй status=joint_investigation.
- Для joint_investigation можно recommendation=publish, НО совместность расследования не означает независимого подтверждения каждой отдельной детали.
- Разделяй факт совместного расследования и конкретные утверждения внутри него.
- Если конкретная деталь подтверждена только самим расследованием, формулируй её как атрибуцию: "BBC и NPR сообщают", "по данным совместного расследования", "по словам собеседников". Не выдавай её за установленный факт.
- Если конкретная деталь имеет отдельное независимое подтверждение, её можно назвать подтверждённым фактом.
- Не называй заявление фактом.
- Если источники расходятся — recommendation=hold.
- Пост 2-4 коротких абзаца: 1) что произошло/о чём материал; 2) ключевая деталь или контекст; 3) при необходимости — что пока не подтверждено. Не ограничивайся одной строкой.
- Заголовок должен содержать суть события, а не только ссылку на источник.
- Если заголовок или исходный текст на английском/другом языке, обязательно переводи его на естественный русский язык. Не копируй иностранный заголовок в итоговый пост.
- Итоговый пост должен быть самостоятельной русскоязычной новостной заметкой, а не переводом RSS-строки слово в слово.
- Для joint_investigation конкретные спорные детали формулируй с атрибуцией, но не перегружай публикацию повторяющимися словами "BBC сообщает", "по данным расследования" и т.п. Одной ясной атрибуции обычно достаточно.
- НИКОГДА не утверждай автоматически, что дополнительные источники "лишь повторяют" основной материал. Пиши это только если из материалов явно видно, что публикация прямо ссылается на основной источник и не содержит собственного подтверждения.
- Если дополнительный источник сообщает о том же событии своими словами, но происхождение информации не установлено, называй его "дополнительным сообщением", а не перепечаткой.
- Разделяй внутренний фактчек и публичный текст: внутренние статусы, причины проверки, количество источников и результаты поиска не должны попадать в поле "post".
- Для joint_investigation публичный пост должен быть обычной новостной заметкой: суть события, ключевая деталь/контекст и, только если существенно, одна короткая оговорка о неподтверждённых деталях.
- Не повторяй в нескольких абзацах одну и ту же оговорку об отсутствии подтверждения.
- В конце: Источник: URL основного материала.
- Без Markdown, HTML и служебных пояснений.
- Для СВО не публикуй оперативно чувствительные данные, координаты или тактические сведения.
- Для законов, постановлений, проектов и государственных решений обязательно указывай точный статус документа: проект, подготовлен, опубликован, принят, подписан или вступил в силу. Не повышай статус проекта до принятого акта.
- Не добавляй прогнозы вроде «ожидается, что проект будет рассмотрен/утверждён», если такая информация прямо не указана в исходных материалах.
- Для материалов о проектах нормативных актов используй формулировки «Минцифры разместило проект», «предлагается установить», «проект предусматривает» и аналогичные, если именно это подтверждено источниками.
- Для правовых и федеральных новостей не выводи цели, последствия, мотивы или оценочные формулировки из собственного рассуждения. Используй их только если они прямо указаны в исходном материале или подтверждённых материалах.
- КРИТИЧЕСКОЕ ПРАВИЛО ЯЗЫКА: поле "post" должно быть полностью на русском языке. Переведи заголовок и содержание исходного материала на русский естественно и журналистски. Английский заголовок запрещён в поле "post".
- Не копируй поле "title" в "post", если оно написано не по-русски.
- Перед выдачей JSON проверь поле "post": если в нём остались английские фразы, перепиши их по-русски.
- Пример допустимого заголовка: "🇺🇸 США и Ливан предоставляют убежище разыскиваемому сирийскому генералу, сообщает BBC".

Материалы:
{material}

Прямой признак совместного расследования:
{", ".join(joint_publishers) if joint_publishers else "не обнаружен"}
"""
        prompt += """
Дополнительное правило фактчека:
- Считай источники независимыми, если это разные редакции/домены, даже если формулировки отличаются.
- Для англоязычных мировых новостей не требуй совпадения слов в заголовках: сопоставляй место, объект, участников и последовательность событий.
- Если два или более крупных независимых СМИ сообщают об одном и том же событии, это минимум partial_confirmed; если ключевой факт совпадает — confirmed.
- Не считай перепечатку, агрегатор или материал, который просто ссылается на исходное расследование, независимым подтверждением.
- Совместное расследование двух редакций — отдельный статус joint_investigation, а не single_source.
- Если в материалах явно указаны BBC и NPR как участники одного расследования, а исходный материал описывает их совместную работу, status=joint_investigation даже если третьего независимого подтверждения нет.
- Даже если joint_investigation допускается к публикации, пост должен содержать минимум 2 содержательных коротких абзаца, если исходный материал позволяет это сделать.
- Если редакция указана в поле "[Редакция: ...]", учитывай это как идентификатор источника при оценке независимости.
"""
        raw = groq(prompt, 0.1, 650)
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0)) if match else {}
        status = data.get("status", "single_source")
        recommendation = data.get("recommendation", "hold")
        major_domains = ("reuters.", "apnews.", "bbc.", "npr.", "theguardian.", "dw.", "aljazeera.", "france24.", "interfax.ru", "1prime.ru", "garant.ru", "consultant.ru", "regulation.gov.ru")
        major_sources = set()
        for x in related:
            low = f"{x[0]} {x[1]} {x[2]}".lower()
            for domain in major_domains:
                if domain in low:
                    major_sources.add(domain)
        if status == "single_source" and len(major_sources) >= 2:
            status = "confirmed"
            recommendation = "publish"
            data["reason"] = "Материал подтверждён несколькими независимыми крупными СМИ."
        explicit_publishers = set()
        publisher_aliases = ("bbc", "reuters", "ap", "npr", "the guardian", "dw", "al jazeera", "france 24", "интерфакс", "interfax", "тасс", "ria", "риа новости", "рбк", "rbc", "коммерсант", "kommersant", "ведомости", "garant", "гарант", "consultant", "консультант")
        for x in related:
            txt = f"{x[0]} {x[1]} {x[2]}".lower()
            for alias in publisher_aliases:
                if alias in txt:
                    explicit_publishers.add(alias)
        if status == "single_source" and len(explicit_publishers) >= 2:
            status = "confirmed"
            recommendation = "publish"
            data["reason"] = "Материал подтверждён несколькими независимыми крупными СМИ."
        ru_publishers = set()
        for x in direct_ru:
            m = re.search(r"\[Редакция:\s*([^\]]+)\]", str(x[2]))
            if m:
                ru_publishers.add(m.group(1).strip().lower())
        # For Russian federal/legal stories, confirmation must be based on
        # genuinely distinct publishers, not duplicate Google News entries
        # from the same outlet or publisher names appearing in the headline.
        verified_ru_publishers = set()
        ru_domain_map = {
            "interfax.ru": "Интерфакс",
            "tass.ru": "ТАСС",
            "ria.ru": "РИА Новости",
            "rbc.ru": "РБК",
            "kommersant.ru": "Коммерсантъ",
            "vedomosti.ru": "Ведомости",
            "garant.ru": "ГАРАНТ",
            "consultant.ru": "КонсультантПлюс",
            "cbr.ru": "Банк России",
            "government.ru": "Правительство РФ",
            "kremlin.ru": "Кремль",
            "duma.gov.ru": "Госдума",
        }
        for x in related:
            txt = f"{x[0]} {x[1]} {x[2]}".lower()
            marker = re.search(r"\[редакция:\s*([^\]]+)\]", txt)
            if marker:
                verified_ru_publishers.add(marker.group(1).strip().lower())
            for domain, publisher in ru_domain_map.items():
                if domain in txt:
                    verified_ru_publishers.add(publisher.lower())

        if category in ("russia", "laws", "kremlin", "russia_tech") and len(verified_ru_publishers) >= 2:
            status = "confirmed"
            recommendation = "publish"
            data["reason"] = "Материал подтверждён несколькими независимыми российскими источниками."
        elif category in ("russia", "laws", "kremlin", "russia_tech") and len(verified_ru_publishers) < 2:
            # Do not let the LLM call a Russian federal story "confirmed"
            # when the deterministic source set contains only one publisher.
            # A single outlet can be a primary/officially documented source,
            # but it is not independent multi-source confirmation.
            if status == "confirmed":
                status = "single_source"
                recommendation = "hold"
                data["reason"] = "Найден только один независимый редакционный источник; автоматическое подтверждение несколькими СМИ не установлено."
        if joint_publishers:
            status = "joint_investigation"
            recommendation = "publish"
            data["reason"] = "BBC и NPR действительно ведут совместное расследование. Публикация разрешена с обязательной атрибуцией конкретных утверждений; совместность расследования не означает независимого подтверждения каждой детали."
        labels = {
            "confirmed": "🟢 подтверждено",
            "partial_confirmed": "🟡 частично подтверждено",
            "joint_investigation": "🟡 совместное расследование СМИ",
            "attributed": "🔵 заявление/атрибуция",
            "conflict": "🔴 противоречие",
            "single_source": "⚪ один источник",
        }
        rec = "🟢 рекомендовано к публикации" if recommendation == "publish" else "🔴 лучше НЕ публиковать"
        source_names = []
        allowed_names = ('BBC', 'Reuters', 'AP', 'NPR', 'The Guardian', 'DW', 'Al Jazeera', 'France 24', 'CNN', 'MIT', 'Interfax', 'ТАСС', 'РИА Новости', 'РБК', 'Коммерсантъ', 'Ведомости', 'ГАРАНТ', 'КонсультантПлюс')
        for x in related:
            m = re.search(r"\[Редакция:\s*([^\]]+)\]", str(x[2]))
            if m and any(a.lower() in m.group(1).lower() for a in allowed_names) and m.group(1) not in source_names:
                source_names.append(m.group(1))
        if category in ("russia", "laws", "kremlin", "russia_tech"):
            for publisher in sorted(verified_ru_publishers):
                display = next((v for k, v in ru_domain_map.items() if v.lower() == publisher), None)
                if display and display not in source_names:
                    source_names.append(display)
        if not source_names:
            source_names = [re.sub(r"^www\\.", "", re.sub(r"^https?://", "", link)).split("/")[0]]
        source_line = " • ".join(source_names[:4])
        admin_text = f"🔎 Проверка: {labels.get(status, '⚪ не определено')}\\n{rec}\\nИсточники: {source_line}"
        if tg_first or tg_primary:
            admin_text += f"\\nTelegram первым: {'да' if tg_first else 'нет'} • основной: {'да' if tg_primary else 'нет'}"
        send(chat, admin_text)
        if recommendation == "publish":
            send(chat, "🟢 Рекомендовано к публикации")
        post = str(data.get("post","")).strip()
        post = re.sub(r"\[\s*(https?://[^\]\s]+)\s*\]", r"\1", post)
        post = post.replace("\\&", "&")
        post = sanitize_legal_post(post, category, title, summary, evidence_text)
        if not post:
            # Never expose a foreign-language RSS title in a fallback draft.
            fallback_prompt = f"""Перепиши этот материал как короткую новость на русском языке.
Заголовок: {title}
Описание: {summary[:700]}
Верни 2 коротких абзаца и заголовок на русском. Не добавляй фактов, которых нет в исходнике."""
            try:
                fallback = groq(fallback_prompt, 0.2, 220).strip()
            except Exception:
                fallback = ""
            post = fallback or f"📰 Новость требует проверки редактора.\n\n{summary[:900]}\n\nИсточник: {link}\n\n⚠️ Черновик требует ручной проверки."
        if recommendation == "hold":
            # Single-source material is not automatically blocked for low-risk
            # obituary/biography/history/science/culture stories from a major outlet.
            low_risk_text = f"{title} {summary} {post}".lower()
            low_risk_obituary = any(k in low_risk_text for k in (
                "dies at", "died at", "has died", "died on", "скончал", "умер", "умерла",
                "похорон", "некролог", "биография", "памяти"
            ))
            low_risk_single_source = (
                status == "single_source"
                and (
                    category in ("history", "russia_tech", "tech", "humor")
                    or (category == "world" and low_risk_obituary)
                )
                and any(domain in (link or "").lower()
                        for domain in ("bbc.", "reuters.", "apnews.", "npr.", "dw.", "theguardian.", "mit.edu"))
            )
            if low_risk_single_source:
                recommendation = "publish"
                data["reason"] = "Один надёжный источник допустим для низкорисковой биографической/исторической/научной новости; спорных признаков не обнаружено."
            else:
                send(chat, "⚠️ Редактор: материал не прошёл порог автоматической публикации. Кнопка публикации заблокирована; при необходимости проверь его вручную по источнику.")
                buttons = [[{"text":"❌ Отклонить","callback_data":"no"}]]
        else:
            buttons = [[{"text":"✅ Опубликовать","callback_data":"pub"},{"text":"❌ Отклонить","callback_data":"no"}]]
    except Exception as e:
        print("AI ERROR:", repr(e))
        post = (
            f"⚠️ AI-редактор временно недоступен.\n\n"
            f"Черновик требует ручной проверки.\n\n{summary[:900]}\n\n"
            f"Источник: {link}\n\n"
            "Новость НЕ считается проверенной."
        )
        send(chat, "🛑 Автоматическая публикация заблокирована из-за ошибки AI. Проверь материал вручную или отклони его.")
        buttons = [[{"text":"❌ Отклонить","callback_data":"no"}]]

    send(chat, post, buttons)


def process_news(chat, category="news", region=None):
    key = (str(chat), str(category), str(region or ""))
    if key in ACTIVE_PROCESSING:
        send(chat, "⏳ NOWLY уже обрабатывает этот запрос. Дождись результата.")
        return
    ACTIVE_PROCESSING.add(key)
    try:
        return _process_news(chat, category, region)
    finally:
        ACTIVE_PROCESSING.discard(key)

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
                    HISTORY_MODE.pop(chat, None)
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
            HISTORY_MODE.pop(chat, None)
            threading.Thread(target=history_day, args=(chat, "russia"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🌍 Мир — этот день":
            HISTORY_MODE.pop(chat, None)
            threading.Thread(target=history_day, args=(chat, "world"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🇷🇺 История России":
            HISTORY_MODE.pop(chat, None)
            threading.Thread(target=history_day, args=(chat, "russia"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🌍 История мира":
            HISTORY_MODE.pop(chat, None)
            threading.Thread(target=history_day, args=(chat, "world"), daemon=True).start()
            tg("sendMessage", {
                "chat_id": chat,
                "text": "⏳ Ищу значимые события, которые происходили в этот день в разные годы…",
                "reply_markup": json.dumps({"keyboard": [[{"text":"↩️ История"}]],"resize_keyboard":True}, ensure_ascii=False)
            })
        elif text in ("🗺 История по регионам", "🗺 Регионы — этот день"):
            HISTORY_MODE[chat] = ("region_select", None)
            tg("sendMessage", {
                "chat_id": chat,
                "text": "🗺 Выбери регион:",
                "reply_markup": json.dumps({"keyboard": history_region_keyboard(), "resize_keyboard":True}, ensure_ascii=False)
            })
        elif text == "🔥 Тренды":
            threading.Thread(target=process_news, args=(chat, "trends"), daemon=True).start()
        elif re.fullmatch(r"\d{4}", text.strip()) and chat in HISTORY_MODE:
            # Legacy year input is intentionally disabled: the rubric now uses today's date automatically.
            HISTORY_MODE.pop(chat, None)
            send(chat, "📅 NOWLY автоматически использует сегодняшнюю дату. Выбери «Этот день в истории» снова.")

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
