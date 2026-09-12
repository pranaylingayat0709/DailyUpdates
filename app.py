import streamlit as st
import streamlit.components.v1 as components
import json
import io
import re
import time
import base64
import requests
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from gtts import gTTS

try:
    import yfinance as yf
    YFINANCE_OK = True
except ImportError:
    YFINANCE_OK = False

# ═══════════════════════════════════════════════════
# PAGE CONFIG — WIDE
# ═══════════════════════════════════════════════════
st.set_page_config(
    page_title="SatiCast",
    page_icon="🪷",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ═══════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════
if "NVIDIA_API_KEY" not in st.secrets:
    st.error("🔑 NVIDIA_API_KEY not found in Streamlit secrets.")
    st.stop()

nim_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=st.secrets["NVIDIA_API_KEY"]
)

OPENWEATHER_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")
NEWS_API_KEY    = st.secrets.get("NEWS_API_KEY", "")
ELEVENLABS_KEY  = st.secrets.get("ELEVENLABS_API_KEY", "")

# ═══════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════
VOICE_OPTIONS = {
    "🇮🇳 English – Indian":  {"lang": "en", "tld": "co.in"},
    "🌐 English – Global":   {"lang": "en", "tld": "com"},
    "🇬🇧 English – UK":      {"lang": "en", "tld": "co.uk"},
    "🇨🇦 English – Canada":  {"lang": "en", "tld": "ca"},
    "🇮🇳 हिन्दी – Hindi":    {"lang": "hi", "tld": "co.in"},
    "🇮🇳 मराठी – Marathi":   {"lang": "mr", "tld": "co.in"},
}
LANG_LABEL = {"en": "English", "hi": "हिन्दी (Hindi)", "mr": "मराठी (Marathi)"}

TOPIC_ICONS = {
    "National": "🇮🇳", "Global": "🌐", "Tech": "⚡",
    "Market": "📈", "Sports": "🏏", "Learning": "💡"
}

ELEVENLABS_VOICES = {
    "Rachel – Calm Female": "21m00Tcm4TlvDq8ikWAM",
    "Adam – Neutral Male":  "pNInz6obpgDQGcFmaJgB",
    "Elli – Bright Female": "MF3mGyEYCl7XYWbV9V6O",
}

MARKET_TICKERS = {
    "Nifty 50": "^NSEI", "Sensex": "^BSESN",
    "USD/INR": "INR=X", "Gold": "GC=F",
}

LANG_INSTRUCTION = {
    "en": "Write the spoken_script in clear, natural English.",
    "hi": "Write the spoken_script ENTIRELY in fluent Hindi (Devanagari). Greeting and weather_summary must also be Hindi.",
    "mr": "Write the spoken_script ENTIRELY in fluent Marathi (Devanagari). Greeting and weather_summary must also be Marathi.",
}

LEARNING_TOPICS = [
    "PostgreSQL index-only scans and covering indexes",
    "Java virtual threads (Project Loom) in production",
    "The Saga pattern for distributed transactions",
    "HikariCP connection pool tuning",
    "Idempotency keys in payment APIs",
    "CQRS — when it helps and when it hurts",
    "PostgreSQL EXPLAIN ANALYZE — reading query plans",
    "Circuit breakers with Resilience4j",
    "Kafka consumer group rebalancing",
    "Database connection leaks — detection and prevention",
    "The Outbox pattern for reliable event publishing",
    "Spring Boot startup time optimisation",
    "JWT vs opaque tokens — security trade-offs",
    "PostgreSQL VACUUM and table bloat",
    "gRPC vs REST — choosing for internal services",
    "Optimistic vs pessimistic locking in JPA",
    "Rate limiting algorithms: token bucket vs sliding window",
    "Blue-green vs canary deployments",
    "N+1 query problem in ORMs and fixes",
    "Redis as a cache: eviction policies explained",
    "Structured logging and correlation IDs",
    "PostgreSQL partial indexes for hot subsets",
    "Backpressure in reactive systems",
    "Database migrations with zero downtime",
    "The Strangler Fig pattern for legacy migration",
    "Consistent hashing in distributed caches",
    "Thread dumps — reading them like a pro",
    "API versioning strategies compared",
    "Event sourcing basics and pitfalls",
    "PostgreSQL DISTINCT ON vs window functions",
    "Garbage collection tuning: G1 vs ZGC",
]

NEWS_TOPIC_MAP = {"National": "india", "Global": "global", "Tech": "tech", "Sports": "sports"}

# Maps a source NAME (as the LLM writes it, case-insensitive) to that outlet's
# real homepage — so clicking the source badge opens the actual outlet's site
# instead of a generic search, even for AI-generated items with no article URL.
SOURCE_HOMEPAGES = {
    "reuters": "https://www.reuters.com", "the hindu": "https://www.thehindu.com",
    "bbc": "https://www.bbc.com/news", "pti": "https://www.ptinews.com",
    "ndtv": "https://www.ndtv.com", "hindustan times": "https://www.hindustantimes.com",
    "times of india": "https://timesofindia.indiatimes.com", "the guardian": "https://www.theguardian.com",
    "cnn": "https://www.cnn.com", "al jazeera": "https://www.aljazeera.com",
    "bloomberg": "https://www.bloomberg.com", "cnbc": "https://www.cnbc.com",
    "techcrunch": "https://techcrunch.com", "the verge": "https://www.theverge.com",
    "wired": "https://www.wired.com", "ars technica": "https://arstechnica.com",
    "espn": "https://www.espn.com", "sky sports": "https://www.skysports.com",
    "cricinfo": "https://www.espncricinfo.com", "espncricinfo": "https://www.espncricinfo.com",
    "indian express": "https://indianexpress.com", "livemint": "https://www.livemint.com",
    "economic times": "https://economictimes.indiatimes.com", "moneycontrol": "https://www.moneycontrol.com",
    "ap": "https://apnews.com", "associated press": "https://apnews.com",
    "afp": "https://www.afp.com", "the wire": "https://thewire.in",
    "scroll.in": "https://scroll.in", "the print": "https://theprint.in",
}


def resolve_source_url(source: str, fallback_headline: str = "") -> str:
    """Real outlet homepage if we recognise the source name, else a search
    fallback for the headline — never a fabricated specific-article URL."""
    key = source.strip().lower()
    if key in SOURCE_HOMEPAGES:
        return SOURCE_HOMEPAGES[key]
    if fallback_headline:
        q = urllib.parse.quote(f"{fallback_headline} {source}".strip())
        return f"https://www.google.com/search?q={q}&tbm=nws"
    return ""


_CROSS_REF_STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "with", "by", "is", "are", "new", "after", "amid", "over", "its",
    "this", "that", "from", "as", "into", "amid", "will", "has", "have",
}


def _extract_keywords(text: str) -> set:
    words = re.findall(r"[A-Za-z']+", text or "")
    return {w.lower() for w in words if len(w) > 3 and w.lower() not in _CROSS_REF_STOPWORDS}


def find_cross_references(items_by_topic: dict, min_shared: int = 2) -> dict:
    """
    Pure-Python, zero-API-call heuristic: flags pairs of headlines from
    DIFFERENT topics that share several significant keywords, suggesting
    they cover the same underlying story (e.g. a policy story appearing
    in both National and Global). This is a best-effort keyword-overlap
    heuristic, not real semantic understanding — it will miss some genuine
    overlaps and could occasionally flag a coincidental one, so it's shown
    only as a soft "possibly related" hint, never a confident claim.
    Returns {(topic, idx): [(other_topic, other_idx, other_headline), ...]}.
    """
    flat = []
    for topic, items in items_by_topic.items():
        for idx, item in enumerate(items):
            flat.append((topic, idx, _extract_keywords(item.get("headline", "")), item.get("headline", "")))

    refs = {}
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            t1, i1, kw1, h1 = flat[i]
            t2, i2, kw2, h2 = flat[j]
            if t1 == t2 or not kw1 or not kw2:
                continue
            if len(kw1 & kw2) >= min_shared:
                refs.setdefault((t1, i1), []).append((t2, i2, h2))
                refs.setdefault((t2, i2), []).append((t1, i1, h1))
    return refs

# ═══════════════════════════════════════════════════
# LIVE DATA HELPERS
# ═══════════════════════════════════════════════════
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_weather(city: str) -> dict:
    if not OPENWEATHER_KEY:
        return {}
    try:
        url = (f"https://api.openweathermap.org/data/2.5/weather"
               f"?q={city}&appid={OPENWEATHER_KEY}&units=metric")
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            d = r.json()
            return {
                "temp":     round(d["main"]["temp"]),
                "feels":    round(d["main"]["feels_like"]),
                "humidity": d["main"]["humidity"],
                "desc":     d["weather"][0]["description"].capitalize(),
                "wind":     round(d["wind"]["speed"] * 3.6, 1),
                "icon":     d["weather"][0]["main"],
            }
    except Exception:
        pass
    return {}


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_news(topic: str, page_size: int = 5) -> list:
    if not NEWS_API_KEY:
        return []
    try:
        base = "https://newsapi.org/v2/top-headlines"
        if topic == "tech":
            url = f"{base}?category=technology&language=en&pageSize={page_size}&apiKey={NEWS_API_KEY}"
        elif topic == "sports":
            url = f"{base}?category=sports&country=in&pageSize={page_size}&apiKey={NEWS_API_KEY}"
        elif topic == "global":
            url = f"{base}?language=en&pageSize={page_size}&apiKey={NEWS_API_KEY}"
        else:
            url = f"{base}?country=in&pageSize={page_size}&apiKey={NEWS_API_KEY}"
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            articles = r.json().get("articles", [])
            if topic == "sports" and not articles:
                url = f"{base}?category=sports&language=en&pageSize={page_size}&apiKey={NEWS_API_KEY}"
                r2 = requests.get(url, timeout=6)
                if r2.status_code == 200:
                    articles = r2.json().get("articles", [])
            return [
                {
                    "headline": a.get("title", "").split(" - ")[0][:90],
                    "detail":   a.get("description", "") or "",
                    "source":   a.get("source", {}).get("name", ""),
                    "url":      a.get("url", ""),
                }
                for a in articles
                if a.get("title") and "[Removed]" not in a.get("title", "")
            ][:page_size]
    except Exception:
        pass
    return []


@st.cache_data(ttl=300, show_spinner=False)
def make_sparkline_svg(values: list, up: bool) -> str:
    """Tiny inline SVG line chart from a list of prices — pure Python/SVG,
    no JS, no external chart library needed."""
    if len(values) < 2:
        return ""
    w, h, pad = 70, 24, 3
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = (w - 2 * pad) / (len(values) - 1)
    points = []
    for i, v in enumerate(values):
        x = pad + i * step
        y = pad + (1 - (v - lo) / span) * (h - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")
    color = "#10B981" if up else "#EF4444"
    poly = " ".join(points)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_markets() -> dict:
    if not YFINANCE_OK:
        return {}
    result = {}
    for name, ticker in MARKET_TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="7d")
            if len(hist) >= 2:
                closes = hist["Close"].tolist()
                prev = closes[-2]
                curr = closes[-1]
                chg  = ((curr - prev) / prev) * 100
                up   = chg >= 0
                result[name] = {
                    "price": round(curr, 2), "chg": round(chg, 2), "up": up,
                    "sparkline": make_sparkline_svg(closes[-6:], up),
                }
        except Exception:
            pass
    return result


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_on_this_day() -> dict:
    """Free Wikipedia 'On this day' fact — no API key required."""
    try:
        today = datetime.now()
        url = f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/selected/{today.month:02d}/{today.day:02d}"
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            events = r.json().get("selected", [])
            if events:
                e = events[0]
                return {"year": e.get("year", ""), "text": e.get("text", "")}
    except Exception:
        pass
    return {}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_quote_of_day() -> dict:
    try:
        r = requests.get("https://zenquotes.io/api/today", timeout=6)
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list):
                q = data[0]
                return {"quote": q.get("q", ""), "author": q.get("a", "Unknown"),
                        "source": "ZenQuotes", "source_url": "https://zenquotes.io"}
    except Exception:
        pass
    try:
        r = requests.get("https://api.quotable.io/random?minLength=60&maxLength=180", timeout=6)
        if r.status_code == 200:
            d = r.json()
            return {"quote": d.get("content", ""), "author": d.get("author", "Unknown"),
                    "source": "Quotable.io", "source_url": "https://quotable.io"}
    except Exception:
        pass
    pool = [
        {"quote": "The present moment is the only moment available to us, and it is the door to all moments.", "author": "Thich Nhat Hanh"},
        {"quote": "Wherever you are, be all there.", "author": "Jim Elliot"},
        {"quote": "Do not dwell in the past, do not dream of the future, concentrate the mind on the present moment.", "author": "Buddha"},
        {"quote": "Almost everything will work again if you unplug it for a few minutes — including you.", "author": "Anne Lamott"},
        {"quote": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucius"},
        {"quote": "Simplicity is the ultimate sophistication.", "author": "Leonardo da Vinci"},
        {"quote": "The secret of getting ahead is getting started.", "author": "Mark Twain"},
        {"quote": "Focus on being productive instead of busy.", "author": "Tim Ferriss"},
        {"quote": "Your mind is for having ideas, not holding them.", "author": "David Allen"},
        {"quote": "First, solve the problem. Then, write the code.", "author": "John Johnson"},
    ]
    e = pool[datetime.now().timetuple().tm_yday % len(pool)]
    return {"quote": e["quote"], "author": e["author"], "source": "SatiCast Daily Collection", "source_url": ""}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_word_of_day() -> dict:
    WORDNIK_KEY = st.secrets.get("WORDNIK_API_KEY", "")
    if WORDNIK_KEY:
        try:
            url = f"https://api.wordnik.com/v4/words.json/wordOfTheDay?api_key={WORDNIK_KEY}"
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                d    = r.json()
                word = d.get("word", "")
                defs = d.get("definitions", [])
                exas = d.get("examples", [])
                pos  = defs[0].get("partOfSpeech", "") if defs else ""
                defn = defs[0].get("text", "")          if defs else ""
                exam = exas[0].get("text", "")          if exas else ""
                if word and defn:
                    return {"word": word.capitalize(), "pos": pos, "definition": defn,
                            "example": exam, "source": "Wordnik",
                            "source_url": f"https://www.wordnik.com/words/{word}"}
        except Exception:
            pass
    daily_words = [
        "sonder","ephemeral","petrichor","hiraeth","wanderlust","serendipity",
        "mellifluous","eloquent","perspicacious","resilience","equanimity",
        "cogent","luminous","taciturn","loquacious","sagacious","tenacious",
        "effervescent","mercurial","pragmatic","esoteric","juxtapose","ubiquitous",
        "paradox","catalyst","paradigm","empirical","synthesis","metamorphosis",
        "momentum","velocity","integrity","perseverance","discernment","confluence",
        "acumen","gravitas","penchant","nuance","ardent","fervid","celerity",
        "alacrity","aplomb","candor","efficacy","fastidious","incisive","lucid",
        "meticulous","poise","quandary","rigor","sagacity","veracity","zeal",
        "adroit","astute","brevity","clarity","deft","erudite","forthright",
        "heuristic","immutable","judicious","kinetic","latent","myriad",
    ]
    word = daily_words[datetime.now().timetuple().tm_yday % len(daily_words)]
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=6)
        if r.status_code == 200:
            entries  = r.json()
            meanings = entries[0].get("meanings", []) if entries else []
            if meanings:
                m    = meanings[0]
                defs = m.get("definitions", [])
                pos  = m.get("partOfSpeech", "")
                defn = defs[0].get("definition", "") if defs else ""
                exam = defs[0].get("example", "")    if defs else ""
                if defn:
                    return {"word": word.capitalize(), "pos": pos, "definition": defn,
                            "example": exam, "source": "Free Dictionary",
                            "source_url": f"https://www.merriam-webster.com/dictionary/{word}"}
    except Exception:
        pass
    fallback = [
        {"word":"Sonder","pos":"noun","definition":"The realization that each passerby has a life as vivid and complex as your own.","example":"A quiet sonder washed over her as she watched the busy street."},
        {"word":"Ephemeral","pos":"adjective","definition":"Lasting for a very short time; transitory.","example":"The morning dew is ephemeral, vanishing with the first rays of sunlight."},
        {"word":"Equanimity","pos":"noun","definition":"Mental calmness, composure, especially in difficult situations.","example":"She faced the challenge with remarkable equanimity."},
        {"word":"Cogent","pos":"adjective","definition":"Clear, logical, and convincing.","example":"She made a cogent argument that changed everyone's perspective."},
        {"word":"Alacrity","pos":"noun","definition":"Brisk and cheerful readiness to do something.","example":"The team accepted the new challenge with alacrity."},
    ]
    fb = fallback[datetime.now().timetuple().tm_yday % len(fallback)]
    return {"word": fb["word"], "pos": fb["pos"], "definition": fb["definition"],
            "example": fb["example"], "source": "SatiCast Daily Collection", "source_url": ""}


def repair_truncated_json(raw: str) -> dict:
    """
    Best-effort repair for a JSON object that got cut off mid-string
    (usually because max_tokens was hit). Closes the open string and
    braces so json.loads can still recover whatever fields completed.
    """
    s = raw.rstrip()
    # If it ends mid-string (odd number of unescaped quotes), close the string.
    quote_count = len(re.findall(r'(?<!\\)"', s))
    if quote_count % 2 == 1:
        s += '"'
    # Close any open arrays/objects in the right order.
    opens = re.findall(r'[\{\[]', s)
    closes = re.findall(r'[\}\]]', s)
    # Walk the string tracking a stack to close things properly.
    stack = []
    in_str = False
    esc = False
    for ch in s:
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in '{[':
            stack.append(ch)
        elif ch in '}]':
            if stack:
                stack.pop()
    while stack:
        opener = stack.pop()
        s += '}' if opener == '{' else ']'
    try:
        return json.loads(s)
    except Exception:
        return {}


def _strip_reasoning_wrapper(raw: str) -> str:
    """
    Nemotron 3.5 Lightning (and other hybrid reasoning models) can prepend
    a <think>...</think> block before the actual JSON, or wrap the JSON in
    markdown code fences. Strip both before any JSON parsing is attempted.
    """
    s = raw.strip()
    s = re.sub(r'<think>.*?</think>', '', s, flags=re.DOTALL)
    s = re.sub(r'^.*?</think>', '', s, count=1, flags=re.DOTALL)  # unterminated opening tag
    s = re.sub(r'^```(?:json)?\s*', '', s.strip())
    s = re.sub(r'```\s*$', '', s.strip())
    return s.strip()


def safe_parse_llm_json(raw: str) -> dict:
    """Parse LLM JSON output, stripping any reasoning wrapper and repairing truncation if needed."""
    s = _strip_reasoning_wrapper(raw)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        repaired = repair_truncated_json(s)
        if repaired:
            return repaired
        raise


def nim_chat_json(system_prompt: str, user_message: str, temperature: float, max_tokens: int):
    """
    Calls the NVIDIA NIM chat endpoint and returns the raw completion object.
    Nemotron 3.5 Lightning is a hybrid reasoning model that can otherwise
    prepend a <think>...</think> block before the JSON — this tries to
    disable that via extra_body first, falling back cleanly if the server
    rejects the parameter. safe_parse_llm_json() strips any leftover
    <think> block regardless, as a safety net either way.
    """
    kwargs = dict(
        model="nvidia/nemotron-3.5-lightning-30b-a3b",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_message}],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    try:
        return nim_client.chat.completions.create(
            **kwargs, extra_body={"chat_template_kwargs": {"thinking": False}}
        )
    except Exception:
        return nim_client.chat.completions.create(**kwargs)


def cached_llm_call(cache_key: tuple, compute_fn, ttl: int = 1800):
    """
    Session-scoped cache for LLM text-generation results, keyed by whatever
    inputs actually determine the output. Deliberately implemented as a
    thin wrapper around each call site's EXISTING body (see call_script /
    call_news_topic / call_misc) rather than restructuring the surrounding
    parallel-call orchestration — that orchestration took several rounds to
    get right, so this only touches what's inside each function, not how
    or when they're invoked. If the exact same city/topics/language/quote/
    word/weather combination is requested again within `ttl` seconds, the
    cached text is returned instantly with no new API call.
    """
    if "llm_content_cache" not in st.session_state:
        st.session_state.llm_content_cache = {}
    cache = st.session_state.llm_content_cache
    entry = cache.get(cache_key)
    if entry and (time.time() - entry[0] < ttl):
        return entry[1]
    result = compute_fn()
    cache[cache_key] = (time.time(), result)
    if len(cache) > 200:  # simple bound so a long session doesn't grow unbounded
        oldest_key = min(cache, key=lambda k: cache[k][0])
        del cache[oldest_key]
    return result


def elevenlabs_tts(text: str, voice_id: str):
    if not ELEVENLABS_KEY:
        return None
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"}
        body = {"text": text, "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


def word_count_to_minutes(text: str) -> str:
    mins = max(1, round(len(text.split()) / 130))
    return f"~{mins} min listen"


def weather_emoji(icon: str) -> str:
    return {"Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "🌦️",
            "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️", "Haze": "🌫️",
            "Fog": "🌫️"}.get(icon, "🌤️")


def todays_learning_topic() -> str:
    return LEARNING_TOPICS[datetime.now().timetuple().tm_yday % len(LEARNING_TOPICS)]


# ═══════════════════════════════════════════════════
# SYSTEM PROMPT — LLM only generates what live APIs can't.
# When live news exists for a topic, the LLM does NOT regenerate it.
# ═══════════════════════════════════════════════════
def build_script_prompt(lang_code, news_ctx, quote_line, word_line, weather_line, user_name: str = ""):
    """
    Minimal, fast prompt — produces ONLY greeting + spoken_script.
    This is the only call the audio pipeline depends on, so it's kept
    as small as possible and run in parallel with the visual-data call.
    """
    lang_note = LANG_INSTRUCTION.get(lang_code, LANG_INSTRUCTION["en"])
    news_block = f"\nTODAY'S HEADLINES (mention the most important ones in spoken_script):\n{news_ctx}" if news_ctx else ""
    name_rule = (
        f'- Address the listener warmly by name ("{user_name}") once near the start of the greeting.'
        if user_name.strip() else
        "- Do NOT address the listener by any personal name."
    )
    greeting_hint = f'Warm welcome addressing "{user_name}" by name.' if user_name.strip() else "Warm generic welcome — no personal name."

    return f"""
You are the voice of SatiCast — a mindful, premium AI radio host.
Generate ONLY greeting and spoken_script as a valid JSON object. Be fast.

LANGUAGE RULE: {lang_note}
{weather_line}
{news_block}
{quote_line}
{word_line}

STRICT RULES:
- spoken_script: continuous natural prose, NO bullets/symbols — full-length radio script, not a summary.
- Return ONLY valid JSON — no markdown fences, no preamble.
{name_rule}
- Do NOT include any reasoning, chain-of-thought, or <think> tags — output ONLY the raw JSON object, starting with {{ and ending with }}.

Return a JSON object with EXACTLY these keys:
{{
  "greeting": "{greeting_hint}",
  "spoken_script": "Complete TTS-ready narrative covering greeting, weather, today's top headlines, the quote, and the word of the day — natural full-length radio script."
}}
"""


NEWS_KEY_MAP = {
    "National": "india_news",
    "Global":   "global_news",
    "Tech":     "tech_news",
    "Sports":   "sports_flash",
}

def build_news_topic_prompt(topic_name: str) -> str:
    """
    Dedicated prompt for exactly ONE news topic. Splitting these into
    separate calls (instead of one shared call for all topics) means
    each one gets a full token budget for all 5 items — no more risk
    of the array getting truncated to 1 item because a shared budget
    ran out partway through.
    """
    key = NEWS_KEY_MAP[topic_name]
    return f"""
You generate realistic current news headlines for a daily briefing app.
Generate EXACTLY 5 plausible, distinct current news items for the "{topic_name}" category,
each with a realistic and varied source name (e.g. Reuters, BBC, The Hindu, TechCrunch, ESPN — pick ones fitting the category).

Return ONLY valid JSON — no markdown fences, no preamble, no reasoning or <think> tags. Return EXACTLY this key:
{{
  "{key}": [
    {{"headline":"…","detail":"…","source":"…"}},
    {{"headline":"…","detail":"…","source":"…"}},
    {{"headline":"…","detail":"…","source":"…"}},
    {{"headline":"…","detail":"…","source":"…"}},
    {{"headline":"…","detail":"…","source":"…"}}
  ]
}}
"""


def build_misc_prompt(need_weather_summary: bool, need_learning: bool, learning_topic: str) -> str:
    """Small prompt for the two lightweight on-screen fields that aren't news arrays."""
    keys = []
    if need_weather_summary:
        keys.append('"weather_summary": "One vivid sentence describing today\'s weather."')
    if need_learning:
        keys.append('"learning_byte": {"topic":"…","insight":"…","tip":"…"}')
    keys_json = ",\n  ".join(keys)
    learning_block = f'\nThe learning_byte MUST be about exactly this topic: "{learning_topic}"' if need_learning else ""

    return f"""
You generate small on-screen supplementary fields for SatiCast, a daily briefing app.
Generate ONLY the requested fields as a valid JSON object. Be fast and concise.
{learning_block}

Return ONLY valid JSON — no markdown fences, no preamble, no reasoning or <think> tags.

Return a JSON object with EXACTLY these keys:
{{
  {keys_json}
}}
"""


def build_relevance_prompt(keyed_headlines: dict) -> str:
    """
    Optional add-on prompt: one short "why this matters" sentence per
    live-fetched headline, keyed by a stable "Topic-index" string so the
    result can be matched back to the exact card it came from regardless
    of response ordering.
    """
    items_block = "\n".join(f'- [{key}] {headline}' for key, headline in keyed_headlines.items())
    keys_example = ",\n  ".join(f'"{key}": "…"' for key in keyed_headlines.keys())
    return f"""
You explain why news headlines matter to an everyday reader, in ONE short
sentence each (under 20 words). Be concrete — connect it to a real-world
effect, not a vague generality like "this is important."

HEADLINES:
{items_block}

Return ONLY valid JSON — no markdown fences, no preamble, no reasoning or <think> tags.
Return a JSON object with EXACTLY these keys (use the bracketed keys exactly as given):
{{
  {keys_example}
}}
"""


# ═══════════════════════════════════════════════════
# LOADER — colors via CSS vars (theme-independent)
# ═══════════════════════════════════════════════════
LOADER_STAGES = [
    ("🌸", "Waking up your morning brief…",   "Initialising SatiCast"),
    ("📡", "Fetching live data in parallel…", "Weather · News · Markets · Quote · Word"),
    ("🧠", "Writing script, news &amp; visuals in parallel…", "Multiple AI calls running concurrently"),
    ("🎵", "Generating voice audio…",         "Overlapped with any remaining calls"),
    ("✨", "Polishing your digest…",          "Final quality pass"),
]

def render_loader(stage_idx: int) -> str:
    total = len(LOADER_STAGES)
    emoji, title, sub = LOADER_STAGES[stage_idx]
    pct = int((stage_idx + 1) / total * 100)
    dots = "".join([
        f'<div class="ld {"ldone" if i < stage_idx else ("lactive" if i == stage_idx else "")}"></div>'
        for i in range(total)
    ])
    return (
        f'<div class="loader-wrap">'
        f'<div class="loader-emoji">{emoji}</div>'
        f'<div class="loader-title">{title}</div>'
        f'<div class="loader-sub">{sub} &nbsp;·&nbsp; {stage_idx+1}/{total}</div>'
        f'<div class="loader-dots">{dots}</div>'
        f'<div class="loader-bar-bg"><div class="loader-bar-fg" style="width:{pct}%"></div></div>'
        f'<div class="loader-pct">{pct}%</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════
# CSS — pure-CSS dark toggle via :has(), NO rerun needed.
# Light vars on :root; dark vars override under body:has(#dmchk:checked).
# ═══════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg-grad: linear-gradient(160deg,#FAF9F5 0%,#F5F0E8 38%,#FBEEE5 68%,#F3F0E4 100%);
    --text-main:#1F1E1D; --text-sub:#374151; --text-muted:#6B7280;
    --card-bg:rgba(255,255,255,0.78); --card-bdr:rgba(217,119,87,0.15);
    --input-bg:rgba(255,255,255,0.85); --input-bdr:rgba(217,119,87,0.28); --input-txt:#3D2817;
    --sep-color:#D97757; --news-bg:rgba(255,255,255,0.78); --news-bdr:rgba(0,0,0,0.07);
    --news-hl:#1E1535; --news-dt:#4B5563;
    --focus-bg:linear-gradient(135deg,rgba(237,233,254,0.8),rgba(245,208,254,0.6));
    --word-bg:rgba(255,255,255,0.8); --word-val:#1F2937;
    --greet-bg:linear-gradient(135deg,rgba(237,233,254,0.9),rgba(252,231,243,0.7));
    --weather-bg:linear-gradient(135deg,#E0F2FE,#BAE6FD);
    --weather-tc:#0C4A6E; --footer-c:#D97757;
    --loader-bg:rgba(255,255,255,0.96); --loader-title:#1e1b4b; --loader-sub:#6d28d9;
}
body:has(#dmchk:checked) {
    --bg-grad: linear-gradient(160deg,#1F1E1D 0%,#211E1A 40%,#241C18 70%,#1D1B17 100%);
    --text-main:#E2E8F0; --text-sub:#94A3B8; --text-muted:#64748B;
    --card-bg:rgba(15,23,42,0.82); --card-bdr:rgba(232,146,124,0.22);
    --input-bg:rgba(15,23,42,0.9); --input-bdr:rgba(232,146,124,0.35); --input-txt:#F5E6D8;
    --sep-color:#E8927C; --news-bg:rgba(15,23,42,0.75); --news-bdr:rgba(255,255,255,0.07);
    --news-hl:#E2E8F0; --news-dt:#94A3B8;
    --focus-bg:rgba(217,119,87,0.15);
    --word-bg:rgba(15,23,42,0.75); --word-val:#CBD5E1;
    --greet-bg:linear-gradient(135deg,rgba(79,50,180,0.35),rgba(168,85,247,0.18));
    --weather-bg:linear-gradient(135deg,rgba(14,116,144,0.3),rgba(8,145,178,0.18));
    --weather-tc:#7DD3FC; --footer-c:#E8A87C;
    --loader-bg:rgba(15,10,30,0.94); --loader-title:#F5E6D8; --loader-sub:#E8A87C;
}

h1,h2,h3,h4,h5,h6 { color:var(--text-main) !important; -webkit-text-fill-color:var(--text-main) !important; }
html,body,[class*="css"] { font-family:'Inter',sans-serif !important; color:var(--text-main) !important; }
.stApp { background:var(--bg-grad) !important; min-height:100vh; transition:background 0.5s ease; }
.main .block-container { max-width:1200px; padding-top:0 !important; padding-bottom:6rem; padding-left:2rem; padding-right:2rem; }
#MainMenu,footer,header { visibility:hidden; }
* { box-sizing:border-box; }

/* ── PURE-CSS DARK TOGGLE — no Streamlit rerun, generation never interrupted ── */
#dmchk { display:none; }
.dm-label {
    position:fixed; top:1.1rem; right:1.4rem; z-index:99999;
    width:58px; height:30px; border-radius:999px; cursor:pointer;
    background:linear-gradient(135deg,#D97757,#B45532);
    display:flex; align-items:center; padding:3px;
    box-shadow:0 4px 14px rgba(217,119,87,0.35);
    transition:all 0.3s ease;
}
.dm-label::after {
    content:'🌙'; width:24px; height:24px; border-radius:50%;
    background:#fff; display:flex; align-items:center; justify-content:center;
    font-size:0.8rem; transition:transform 0.35s cubic-bezier(0.34,1.56,0.64,1);
}
body:has(#dmchk:checked) .dm-label::after { content:'☀️'; transform:translateX(28px); }

/* ── FONT-SIZE ACCESSIBILITY CONTROL ── */
html { font-size:16px; transition:font-size 0.2s ease; }
html:has(#fsSmall:checked) { font-size:14px; }
html:has(#fsLarge:checked) { font-size:18px; }
#fsSmall, #fsNormal, #fsLarge { display:none; }
.fs-toggle {
    position:fixed; top:1.1rem; right:5.2rem; z-index:99999;
    display:flex; gap:2px; background:var(--card-bg);
    border:1.5px solid var(--card-bdr); border-radius:999px; padding:3px;
    backdrop-filter:blur(10px); box-shadow:0 4px 14px rgba(0,0,0,0.1);
}
.fs-btn {
    width:26px; height:24px; display:flex; align-items:center; justify-content:center;
    border-radius:999px; font-size:0.7rem; font-weight:800; cursor:pointer;
    color:var(--text-muted); transition:all 0.2s ease;
}
#fsSmall:checked ~ label[for="fsSmall"],
#fsNormal:checked ~ label[for="fsNormal"],
#fsLarge:checked ~ label[for="fsLarge"] {
    background:#D97757; color:#fff;
}

/* ── ORBS ── */
.sati-bg { position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden;animation:ambientHue 60s linear infinite; }
@keyframes ambientHue { 0%{filter:hue-rotate(0deg)} 50%{filter:hue-rotate(8deg)} 100%{filter:hue-rotate(0deg)} }
.orb { position:absolute;border-radius:50%;filter:blur(80px);opacity:0.3;animation:drift 16s ease-in-out infinite alternate; }
.orb1 { width:520px;height:520px;background:#F0C4A8;top:-140px;left:-140px; }
.orb2 { width:440px;height:440px;background:#FBCFE8;top:240px;right:-140px;animation-delay:4s; }
.orb3 { width:380px;height:380px;background:#BAE6FD;bottom:140px;left:60px;animation-delay:7s; }
.orb4 { width:300px;height:300px;background:#BBF7D0;bottom:-60px;right:100px;animation-delay:2s; }
@keyframes drift { 0%{transform:translate(0,0) scale(1) rotate(0deg)} 100%{transform:translate(40px,25px) scale(1.1) rotate(8deg)} }

/* ── MASTHEAD ── */
.sati-masthead { position:relative;z-index:1;padding:3.5rem 0 1.5rem;text-align:center; }
.sati-lotus { font-size:3rem;display:block;margin-bottom:0.5rem;animation:floatLotus 3.2s ease-in-out infinite; }
@keyframes floatLotus { 0%,100%{transform:translateY(0) rotate(-2deg)} 50%{transform:translateY(-9px) rotate(2deg)} }
.sati-wordmark {
    font-family:'Syne',sans-serif;font-size:5rem;font-weight:800;
    letter-spacing:-4px;line-height:1;
    background:linear-gradient(120deg,#D97757,#B45532,#0369A1,#D97757);
    background-size:280% auto;
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
    margin:0 0 0.4rem;animation:fadeSlideDown 0.8s ease both, gradShift 7s linear infinite;
}
@keyframes gradShift { to { background-position:280% center; } }
.sati-tagline { font-size:0.82rem;font-weight:700;letter-spacing:0.3em;text-transform:uppercase;color:#D97757;opacity:0.8;animation:fadeSlideDown 0.9s 0.1s ease both; }
body:has(#dmchk:checked) .sati-tagline { color:#E8A87C; }
.sati-meaning { margin-top:0.55rem;font-size:0.9rem;color:#8B3A1F;font-style:italic;font-weight:500;animation:fadeSlideDown 0.95s 0.15s ease both; }
body:has(#dmchk:checked) .sati-meaning { color:#F0C4A8; }

.waveform-wrap { display:flex;align-items:center;justify-content:center;gap:5px;height:46px;margin:1.4rem auto 0;animation:fadeSlideDown 1s 0.2s ease both; }
.bar { width:4px;border-radius:99px;background:linear-gradient(to top,#D97757,#C26847,#0EA5E9);animation:wave 1.3s ease-in-out infinite;transform-origin:center; }
.bar:nth-child(1){height:12px;animation-delay:0.00s}
.bar:nth-child(2){height:22px;animation-delay:0.08s}
.bar:nth-child(3){height:34px;animation-delay:0.16s}
.bar:nth-child(4){height:28px;animation-delay:0.24s}
.bar:nth-child(5){height:44px;animation-delay:0.12s}
.bar:nth-child(6){height:36px;animation-delay:0.20s}
.bar:nth-child(7){height:46px;animation-delay:0.04s}
.bar:nth-child(8){height:38px;animation-delay:0.28s}
.bar:nth-child(9){height:30px;animation-delay:0.08s}
.bar:nth-child(10){height:20px;animation-delay:0.16s}
.bar:nth-child(11){height:14px;animation-delay:0.24s}
.bar:nth-child(12){height:26px;animation-delay:0.00s}
.bar:nth-child(13){height:40px;animation-delay:0.12s}
.bar:nth-child(14){height:32px;animation-delay:0.20s}
.bar:nth-child(15){height:18px;animation-delay:0.04s}
.bar:nth-child(16){height:10px;animation-delay:0.28s}
@keyframes wave { 0%,100%{transform:scaleY(0.35);opacity:0.45} 50%{transform:scaleY(1.0);opacity:1.0} }

/* ── CONTROLS ── */
div[data-testid="stMultiSelect"] label, div[data-testid="stTextInput"] label {
    color:#8B3A1F !important;font-size:0.74rem !important;
    font-weight:700 !important;letter-spacing:0.08em !important;text-transform:uppercase !important;
}
body:has(#dmchk:checked) div[data-testid="stMultiSelect"] label,
body:has(#dmchk:checked) div[data-testid="stTextInput"] label { color:#F0C4A8 !important; }

/* Multiselect box (used for Voice & Accent, TTS Engine, and Topics to include) —
   chip text has been reliably readable in both themes throughout, so this is
   the widget of choice instead of st.selectbox. */
div[data-testid="stMultiSelect"] > div > div {
    background:var(--input-bg) !important;border:1.5px solid var(--input-bdr) !important;
    border-radius:14px !important;font-weight:500 !important;
}
div[data-testid="stTextInput"] input {
    background:var(--input-bg) !important;border:1.5px solid var(--input-bdr) !important;
    border-radius:14px !important;color:var(--input-txt) !important;font-weight:500 !important;
    padding:0.55rem 0.9rem !important;
}
span[data-baseweb="tag"] { background:linear-gradient(135deg,#D97757,#B45532) !important;color:#fff !important;border-radius:8px !important; }
div[data-testid="stToggle"] label p, .stCheckbox label p { color:var(--text-main) !important;font-weight:600 !important; }

/* ── PILLS WRAP SAFEGUARD — never let pill options overflow their
   container; always wrap into additional rows instead. ── */
div[data-testid="stPills"] > div,
div[data-testid="stPills"] div[role="radiogroup"],
div[data-testid="stPills"] div[role="group"] {
    flex-wrap: wrap !important;
    row-gap: 8px !important;
}

/* ── FALLBACK PILL GRID (only used if st.pills isn't available in this
   Streamlit version — see _pill_grid_fallback). Uses the same proven
   marker-sibling technique: a hidden marker placed right before the
   selected button, highlighted via a plain adjacent-sibling selector. ── */
.pill-label {
    color:#8B3A1F !important;font-size:0.74rem;font-weight:700;
    letter-spacing:0.08em;text-transform:uppercase;margin:0.4rem 0 0.5rem;
}
body:has(#dmchk:checked) .pill-label { color:#F0C4A8 !important; }
.pill-scope-fallback, .pill-selected-marker { height:0; margin:0; padding:0; }
.pill-scope-fallback ~ div[data-testid="stHorizontalBlock"] button {
    border-radius:12px !important;padding:0.4rem 0.5rem !important;font-size:0.74rem !important;
    font-weight:600 !important;white-space:normal !important;line-height:1.25 !important;
    min-height:2.4rem !important;box-shadow:none !important;transform:none !important;
    margin:0.2rem 0 !important;background:var(--input-bg) !important;color:var(--text-main) !important;
    border:1.5px solid var(--input-bdr) !important;
}
.pill-selected-marker + div[data-testid="stButton"] button {
    background:linear-gradient(135deg,#D97757,#B45532) !important;
    color:#FFFFFF !important;border:none !important;font-weight:800 !important;
}

/* ── SCRIPT LANGUAGE BADGE (replaces the disabled, unreadable selectbox) ── */
.script-lang-badge {
    display:inline-block;
    background:var(--card-bg);
    border:1.5px solid var(--card-bdr);
    border-radius:999px;
    padding:0.55rem 1.2rem;
    font-size:0.85rem;
    color:var(--text-sub);
    margin:0.3rem 0 1.2rem;
}
.script-lang-badge strong { color:var(--text-main); }

.stButton > button {
    display:block !important;margin:1.8rem auto 0 !important;
    background:linear-gradient(135deg,#D97757 0%,#B45532 100%) !important;
    border:none !important;color:#FFFFFF !important;
    border-radius:999px !important;padding:0.95rem 4rem !important;
    font-size:1rem !important;font-weight:700 !important;
    letter-spacing:0.08em !important;text-transform:uppercase !important;
    transition:all 0.25s ease !important;
    box-shadow:0 8px 30px rgba(217,119,87,0.35) !important;
    position:relative;z-index:2;
}
.stButton > button:hover { box-shadow:0 14px 44px rgba(217,119,87,0.5) !important;transform:translateY(-3px) scale(1.03) !important; }
.stButton > button:active { transform:scale(0.97) !important; }

details summary { color:var(--text-main) !important;font-weight:600 !important; }
details { background:var(--card-bg) !important;border-radius:16px !important;border:1.5px solid var(--card-bdr) !important;padding:0.5rem 1rem !important;margin-bottom:1rem !important; }

/* ── LOADER ── */
@keyframes loaderBounce { 0%,100%{transform:translateY(0) scale(1)} 40%{transform:translateY(-12px) scale(1.12)} 65%{transform:translateY(-6px) scale(1.06)} }
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
@keyframes dotPop { from{transform:scale(0.3);opacity:0} to{transform:scale(1);opacity:1} }
@keyframes loaderFadeIn { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
.loader-wrap { border-radius:26px;padding:3rem 2.5rem;text-align:center;max-width:540px;margin:2rem auto;box-shadow:0 24px 60px rgba(0,0,0,0.22);animation:loaderFadeIn 0.4s ease both;border:1.5px solid rgba(232,146,124,0.2);background:var(--loader-bg);position:relative;overflow:hidden; }
.loader-wrap::after {
    content:''; position:absolute; top:0; left:-150%; width:100%; height:100%;
    background:linear-gradient(100deg, transparent, rgba(217,119,87,0.08), transparent);
    animation:loaderSweep 2.2s ease-in-out infinite;
}
@keyframes loaderSweep { to { left:150%; } }
.loader-emoji { font-size:3.2rem;display:block;margin-bottom:0.9rem;animation:loaderBounce 1.3s ease-in-out infinite; }
.loader-title { font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;margin-bottom:0.3rem;color:var(--loader-title); }
.loader-sub { font-size:0.83rem;font-weight:600;margin-bottom:1.5rem;color:var(--loader-sub); }
.loader-dots { display:flex;justify-content:center;gap:9px;margin-bottom:1.4rem; }
.ld { width:10px;height:10px;border-radius:50%;background:#E5E7EB;transition:background 0.3s; }
.lactive { background:linear-gradient(135deg,#D97757,#B45532);animation:dotPop 0.4s ease both;box-shadow:0 0 8px rgba(217,119,87,0.4); }
.ldone { background:#D97757; }
.loader-bar-bg { height:6px;border-radius:99px;background:rgba(217,119,87,0.12);overflow:hidden;margin-bottom:0.5rem; }
.loader-bar-fg { height:100%;border-radius:99px;background:linear-gradient(90deg,#D97757,#B45532,#0EA5E9,#D97757);background-size:200% 100%;animation:shimmer 1.8s linear infinite;transition:width 0.5s ease; }
.loader-pct { font-size:0.78rem;font-weight:800;letter-spacing:0.06em;color:var(--loader-sub); }

/* ── HERO ROW: audio + weather side by side ── */
.hero-row { display:grid;grid-template-columns:1.4fr 1fr;gap:1.25rem;margin:2rem 0 0.5rem;position:relative;z-index:2; }
@media (max-width:900px) { .hero-row { grid-template-columns:1fr; } }

.audio-shell {
    background:linear-gradient(135deg,rgba(217,119,87,0.1),rgba(180,85,50,0.07));
    border:1.5px solid rgba(217,119,87,0.22);border-radius:22px;
    padding:1.6rem 1.8rem;backdrop-filter:blur(14px);
    box-shadow:0 8px 32px rgba(217,119,87,0.1);
    animation:cardReveal 0.6s ease both;
    transition:transform 0.3s ease, box-shadow 0.3s ease;
}
.audio-shell:hover { transform:translateY(-3px); box-shadow:0 14px 44px rgba(217,119,87,0.18); }
.audio-pill { display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#D97757,#B45532);color:#FFFFFF;font-size:0.62rem;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;padding:0.28rem 0.9rem;border-radius:999px;margin-bottom:0.7rem;animation:pulse 2.4s ease-in-out infinite; }
@keyframes pulse { 0%,100%{box-shadow:0 0 0 0 rgba(180,85,50,0.35)} 50%{box-shadow:0 0 0 8px rgba(180,85,50,0)} }
.audio-title { font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:800;color:var(--text-main);margin-bottom:0.4rem; }
.audio-meta { font-size:0.78rem;color:#D97757;font-weight:600; }
body:has(#dmchk:checked) .audio-meta { color:#E8A87C; }
.listen-badge { display:inline-flex;align-items:center;gap:5px;background:rgba(217,119,87,0.1);border:1px solid rgba(217,119,87,0.2);border-radius:999px;padding:0.28rem 0.8rem;font-size:0.75rem;font-weight:700;color:#D97757;margin-top:0.6rem; }
body:has(#dmchk:checked) .listen-badge { color:#F0C4A8; }

.weather-widget {
    background:var(--weather-bg);border:1.5px solid rgba(14,165,233,0.28);
    border-radius:22px;padding:1.5rem 1.7rem;
    box-shadow:0 8px 28px rgba(14,165,233,0.12);
    display:grid;grid-template-columns:auto 1fr auto;gap:0.5rem 1.3rem;align-items:center;
    animation:cardReveal 0.6s 0.08s ease both;
    transition:transform 0.3s ease;
}
.weather-widget:hover { transform:translateY(-3px); }

/* ── WEATHER PARTICLE ANIMATIONS ── */
.wx-particles { position:absolute; inset:0; pointer-events:none; overflow:hidden; z-index:0; }
.wx-rain span {
    position:absolute; top:-10%; width:2px; height:14px;
    background:linear-gradient(to bottom, transparent, rgba(56,189,248,0.6));
    animation:wxFall 1s linear infinite;
}
.wx-rain span:nth-child(1){left:5%;animation-delay:0s;animation-duration:0.9s}
.wx-rain span:nth-child(2){left:15%;animation-delay:0.2s;animation-duration:1.1s}
.wx-rain span:nth-child(3){left:25%;animation-delay:0.4s;animation-duration:0.8s}
.wx-rain span:nth-child(4){left:35%;animation-delay:0.1s;animation-duration:1.0s}
.wx-rain span:nth-child(5){left:45%;animation-delay:0.3s;animation-duration:0.95s}
.wx-rain span:nth-child(6){left:55%;animation-delay:0.5s;animation-duration:1.05s}
.wx-rain span:nth-child(7){left:65%;animation-delay:0.15s;animation-duration:0.85s}
.wx-rain span:nth-child(8){left:75%;animation-delay:0.35s;animation-duration:1.0s}
.wx-rain span:nth-child(9){left:85%;animation-delay:0.25s;animation-duration:0.9s}
.wx-rain span:nth-child(10){left:95%;animation-delay:0.45s;animation-duration:1.1s}
.wx-rain span:nth-child(11){left:10%;animation-delay:0.6s;animation-duration:0.8s}
.wx-rain span:nth-child(12){left:60%;animation-delay:0.05s;animation-duration:1.0s}
@keyframes wxFall { 0%{transform:translateY(0);opacity:0.8} 100%{transform:translateY(140px);opacity:0} }

.wx-sun .wx-ray {
    position:absolute; top:-30%; right:-10%; width:160px; height:160px; border-radius:50%;
    background:radial-gradient(circle, rgba(253,224,71,0.35), transparent 70%);
    animation:wxPulse 3s ease-in-out infinite;
}
@keyframes wxPulse { 0%,100%{transform:scale(1);opacity:0.6} 50%{transform:scale(1.15);opacity:0.9} }

.wx-clouds span {
    position:absolute; top:20%; width:60px; height:20px; border-radius:20px;
    background:rgba(255,255,255,0.35); animation:wxDrift 12s linear infinite;
}
.wx-clouds span:nth-child(1){top:15%;animation-delay:0s}
.wx-clouds span:nth-child(2){top:55%;animation-delay:6s}
@keyframes wxDrift { 0%{transform:translateX(-80px)} 100%{transform:translateX(340px)} }
.weather-icon { font-size:3.4rem;line-height:1;animation:floatLotus 4s ease-in-out infinite; }
.weather-temp { font-family:'Syne',sans-serif;font-size:2.4rem;font-weight:800;color:var(--weather-tc); }
.weather-desc { font-size:0.9rem;font-weight:600;color:var(--weather-tc);opacity:0.85; }
.weather-meta { font-size:0.78rem;color:var(--weather-tc);opacity:0.7;margin-top:0.2rem; }
.weather-feels { font-size:0.85rem;font-weight:600;color:var(--weather-tc);text-align:right; }

.dl-wrap { margin:0.75rem 0 1rem;position:relative;z-index:2; }
.dl-wrap a { display:inline-flex;align-items:center;gap:6px;background:rgba(217,119,87,0.08);border:1.5px solid rgba(217,119,87,0.22);border-radius:999px;padding:0.45rem 1.2rem;font-size:0.8rem;font-weight:700;color:#D97757;text-decoration:none;transition:all 0.2s; }
.dl-wrap a:hover { background:rgba(217,119,87,0.16);transform:translateY(-1px); }
body:has(#dmchk:checked) .dl-wrap a { color:#F0C4A8; }

/* ── GREETING BANNER ── */
.greeting-card {
    background:var(--greet-bg);border:1.5px solid rgba(217,119,87,0.18);
    border-radius:20px;padding:1.4rem 1.8rem;margin:1.5rem 0;
    color:var(--text-sub);font-size:1.12rem;line-height:1.75;
    position:relative;z-index:2;animation:cardReveal 0.5s ease both;
    box-shadow:0 4px 22px rgba(217,119,87,0.08);
    border-left:5px solid #D97757;
}

/* ── SECTIONS ── */
.sati-section { position:relative;z-index:2;margin-bottom:3rem;animation:cardReveal 0.6s ease both; }
.section-header { display:flex;align-items:center;gap:12px;margin-bottom:1.3rem; }
.section-badge { width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.25rem;flex-shrink:0;transition:transform 0.3s ease; }
.sati-section:hover .section-badge { transform:rotate(-8deg) scale(1.1); }
.badge-india { background:linear-gradient(135deg,#FEF3C7,#FDE68A); }
.badge-global { background:linear-gradient(135deg,#DBEAFE,#BFDBFE); }
.badge-tech { background:linear-gradient(135deg,#D1FAE5,#A7F3D0); }
.badge-focus { background:linear-gradient(135deg,#EDE9FE,#F5E6D8); }
.badge-word { background:linear-gradient(135deg,#FFE4E6,#FECDD3); }
.badge-sports { background:linear-gradient(135deg,#FEF9C3,#FDE047); }
.badge-learn { background:linear-gradient(135deg,#ECFDF5,#A7F3D0); }
.section-title {
    font-family:'Syne',sans-serif !important;font-size:1.7rem !important;font-weight:800 !important;
    color:var(--text-main) !important;letter-spacing:-0.5px !important;margin:0 !important;
    -webkit-text-fill-color:var(--text-main) !important;
    position:relative;
}

/* ── MARKET STRIP ── */
.market-strip { display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;position:relative;z-index:2; }
.market-chip {
    background:var(--card-bg);border:1.5px solid var(--card-bdr);border-radius:16px;
    padding:1rem 1.2rem;backdrop-filter:blur(8px);
    transition:transform 0.25s ease, box-shadow 0.25s ease;
}
.market-chip:hover { transform:translateY(-4px);box-shadow:0 12px 28px rgba(217,119,87,0.15); }
.market-spark { margin-top:0.4rem; opacity:0.85; }
.market-name { font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--text-muted); }
.market-price { font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:var(--text-main);margin:0.15rem 0; }
.market-chg-up { font-size:0.82rem;font-weight:700;color:#10B981; }
.market-chg-down { font-size:0.82rem;font-weight:700;color:#EF4444; }

/* ── NEWS GRID: 2 columns wide-screen, animated cards ── */
.news-grid { display:grid;grid-template-columns:1fr 1fr;gap:14px; }
@media (max-width:900px) { .news-grid { grid-template-columns:1fr; } }
.news-card {
    background:var(--news-bg);border:1.5px solid var(--news-bdr);border-radius:18px;
    padding:1.2rem 1.4rem;backdrop-filter:blur(12px);
    box-shadow:0 4px 18px rgba(0,0,0,0.05);
    display:flex;gap:14px;
    transition:transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    animation:cardReveal 0.5s ease both;
}
.news-card:hover { transform:translateY(-4px);box-shadow:0 14px 32px rgba(217,119,87,0.14);border-color:rgba(217,119,87,0.3); }
.news-card:nth-child(1){animation-delay:0.03s}
.news-card:nth-child(2){animation-delay:0.08s}
.news-card:nth-child(3){animation-delay:0.13s}
.news-card:nth-child(4){animation-delay:0.18s}
.news-card:nth-child(5){animation-delay:0.23s}
.news-index { font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;min-width:32px;line-height:1;opacity:0.85; }
.idx-india { color:#B45309; } .idx-global { color:#1D4ED8; }
.idx-tech { color:#047857; } .idx-sports { color:#D97706; }
.news-headline { font-weight:700;font-size:0.96rem;color:var(--news-hl);line-height:1.45;margin-bottom:0.3rem; }
.news-detail { font-size:0.85rem;color:var(--news-dt);line-height:1.65; }
.news-source { display:inline-block;font-size:0.66rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#C26847;margin-top:0.4rem;background:rgba(194,104,71,0.09);border-radius:5px;padding:0.15rem 0.5rem;text-decoration:none;cursor:pointer;transition:background 0.15s ease; }
.news-source:hover { background:rgba(194,104,71,0.2); }
body:has(#dmchk:checked) .news-source { color:#F0C4A8;background:rgba(232,146,124,0.15); }
body:has(#dmchk:checked) .news-source:hover { background:rgba(232,146,124,0.28); }

/* ── DUAL ROW: quote + word side by side ── */
.dual-row { display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;position:relative;z-index:2;margin-bottom:3rem; }
@media (max-width:900px) { .dual-row { grid-template-columns:1fr; } }

.focus-card {
    background:var(--focus-bg);border:1.5px solid rgba(217,119,87,0.2);
    border-left:5px solid #D97757;border-radius:0 20px 20px 0;
    padding:1.7rem 1.7rem 1.7rem 1.9rem;box-shadow:0 4px 22px rgba(217,119,87,0.08);
    transition:transform 0.25s ease;height:100%;
}
.focus-card:hover { transform:translateY(-4px); }
.focus-quote { font-family:'Syne',sans-serif;font-size:1.15rem;font-weight:700;color:var(--text-main);line-height:1.65;margin-bottom:0.6rem;font-style:italic; }
.focus-author { font-size:0.8rem;font-weight:700;color:#C26847;margin-bottom:0.5rem; }
body:has(#dmchk:checked) .focus-author { color:#F0C4A8; }

.word-card {
    background:var(--word-bg);border:1.5px solid rgba(180,85,50,0.16);
    border-radius:20px;padding:1.7rem;box-shadow:0 4px 22px rgba(180,85,50,0.06);
    backdrop-filter:blur(8px);transition:transform 0.25s ease;height:100%;
}
.word-card:hover { transform:translateY(-4px); }
.word-main { font-family:'Syne',sans-serif;font-size:1.7rem;font-weight:800;background:linear-gradient(135deg,#B45532,#D97757);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;border-bottom:1px solid rgba(180,85,50,0.14);padding-bottom:0.75rem;margin-bottom:0.9rem; }
.word-pos { display:inline-block;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#C26847;background:rgba(194,104,71,0.09);border-radius:6px;padding:0.12rem 0.55rem;margin-left:0.5rem;-webkit-text-fill-color:#C26847;vertical-align:middle; }
.word-label { font-size:0.68rem;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#B45532;margin-top:0.8rem; }
.word-val { font-size:0.9rem;color:var(--word-val);line-height:1.65;margin-top:0.25rem; }
.word-val em { color:#8B3A1F;font-style:italic; }
body:has(#dmchk:checked) .word-val em { color:#F0C4A8; }

/* ── LEARNING ── */
.learn-card {
    background:var(--card-bg);border:1.5px solid rgba(16,185,129,0.22);
    border-left:5px solid #10B981;border-radius:0 20px 20px 0;
    padding:1.6rem 1.7rem 1.6rem 1.9rem;box-shadow:0 4px 22px rgba(16,185,129,0.08);
    transition:transform 0.25s ease;
}
.learn-card:hover { transform:translateY(-4px); }
.learn-topic { font-family:'Syne',sans-serif;font-size:1.15rem;font-weight:800;color:#047857;margin-bottom:0.6rem; }
body:has(#dmchk:checked) .learn-topic { color:#6EE7B7; }
.learn-insight { font-size:0.95rem;color:var(--text-sub);line-height:1.75;margin-bottom:0.6rem; }
.learn-tip { font-size:0.84rem;font-weight:600;color:#065F46;background:rgba(16,185,129,0.09);border-radius:10px;padding:0.6rem 0.9rem;border-left:3px solid #10B981; }
body:has(#dmchk:checked) .learn-tip { color:#A7F3D0; }
.learn-daily-note { font-size:0.72rem;font-weight:600;color:#059669;opacity:0.75;margin-top:0.7rem;font-style:italic; }

/* ── MISC ── */
.live-source-badge { display:inline-flex;align-items:center;gap:4px;background:rgba(217,119,87,0.08);border:1px solid rgba(217,119,87,0.2);border-radius:999px;padding:0.22rem 0.75rem;font-size:0.68rem;font-weight:700;color:#D97757;text-decoration:none;letter-spacing:0.04em;margin-left:auto;transition:background 0.2s; }
.live-source-badge:hover { background:rgba(217,119,87,0.16); }
body:has(#dmchk:checked) .live-source-badge { color:#F0C4A8; }
.focus-live-note { font-size:0.72rem;font-weight:600;color:#C26847;opacity:0.7;margin-top:0.75rem;display:block;font-style:italic; }
body:has(#dmchk:checked) .focus-live-note { color:#E8A87C; }

.hist-item { background:var(--card-bg);border:1.5px solid var(--card-bdr);border-radius:14px;padding:1rem 1.25rem;margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center; }
.hist-date { font-family:'Syne',sans-serif;font-size:0.9rem;font-weight:800;color:var(--text-main); }
.hist-meta { font-size:0.75rem;color:var(--text-muted);margin-top:0.2rem; }

.sati-sep { display:flex;align-items:center;gap:12px;margin:2.4rem 0;opacity:0.22;position:relative;z-index:2; }
.sati-sep::before,.sati-sep::after { content:'';flex:1;height:1px;background:linear-gradient(to right,transparent,var(--sep-color),transparent); }
.sati-sep-dot { width:5px;height:5px;border-radius:50%;background:var(--sep-color); }

.sati-footer { text-align:center;margin-top:4rem;padding-bottom:2rem;position:relative;z-index:2; }
.sati-footer p { font-size:0.72rem;color:var(--footer-c);letter-spacing:0.12em;text-transform:uppercase;font-weight:600; }

@keyframes fadeSlideDown { from{opacity:0;transform:translateY(-16px)} to{opacity:1;transform:translateY(0)} }
@keyframes cardReveal { from{opacity:0;transform:translateY(24px)} to{opacity:1;transform:translateY(0)} }

/* ── CUSTOM SCROLLBAR ── */
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(217,119,87,0.35); border-radius:99px; }
::-webkit-scrollbar-thumb:hover { background:rgba(217,119,87,0.55); }

/* ── PRINT-FRIENDLY ── */
@media print {
    .sati-bg, .dm-label, .stButton, #dmchk { display:none !important; }
    .stApp { background:#fff !important; }
    .sati-section, .news-card, .focus-card, .word-card, .learn-card { box-shadow:none !important; }
}

/* ── CARD HOVER ACCENT SWEEP — matching claude.com/blog's card hover style ── */
.news-card, .focus-card, .word-card, .learn-card, .weather-widget, .audio-shell {
    position:relative;
}
.news-card::before, .focus-card::before, .word-card::before, .learn-card::before {
    content:'';
    position:absolute; top:0; left:0; height:3px; width:0;
    background:linear-gradient(90deg,#D97757,#B45532);
    transition:width 0.35s ease;
    border-radius:3px 3px 0 0;
}
.news-card:hover::before, .focus-card:hover::before,
.word-card:hover::before, .learn-card:hover::before { width:100%; }

/* ── NEWSPAPER-STYLE PAGE TURNING for news sections ── */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,800;1,600&display=swap');

.news-book-wrap {
    max-width:600px; margin:0 auto; position:relative; padding:6px 0 14px;
}
/* Stacked-pages illusion behind the top sheet */
.news-book-wrap::before, .news-book-wrap::after {
    content:''; position:absolute; left:50%;
    background:#F3EAD8; border:1px solid rgba(139,58,31,0.18);
}
.news-book-wrap::before { width:95%; height:100%; top:7px; transform:translateX(-50%) rotate(-0.6deg); z-index:0; opacity:0.7; }
.news-book-wrap::after  { width:90%; height:100%; top:13px; transform:translateX(-50%) rotate(0.9deg); z-index:-1; opacity:0.4; }

.news-book-page {
    animation: paperTurn 0.45s cubic-bezier(0.34,1.56,0.64,1) both;
    min-height:150px; position:relative; z-index:1;
    background:
        repeating-linear-gradient(#F9F4E8 0 27px, rgba(139,58,31,0.05) 27px 28px)
        !important;
    border:1px solid rgba(139,58,31,0.25) !important;
    border-radius:2px !important;
    box-shadow:0 12px 30px rgba(60,30,10,0.14), inset 0 0 40px rgba(139,58,31,0.04) !important;
    padding:1.6rem 1.8rem 1.4rem !important;
}
@keyframes paperTurn {
    from { opacity:0; transform:perspective(900px) rotateY(-14deg) translateX(-18px); }
    to   { opacity:1; transform:perspective(900px) rotateY(0deg) translateX(0); }
}
/* Masthead-style rule above/below the headline */
.news-book-page .news-headline {
    font-family:'Playfair Display',Georgia,serif !important;
    font-size:1.15rem !important; font-weight:800 !important;
    border-bottom:2px double rgba(139,58,31,0.3);
    padding-bottom:0.5rem; margin-bottom:0.5rem !important;
}
.news-book-page .news-detail {
    font-family:Georgia,'Times New Roman',serif !important;
    font-size:0.9rem !important; line-height:1.65 !important;
    column-count:1;
}
.news-book-page .news-index {
    font-family:'Playfair Display',Georgia,serif !important;
    font-style:italic; font-size:1.4rem !important;
    color:#8B3A1F !important; opacity:0.55;
}
.news-book-page .news-source {
    font-family:Georgia,serif !important; font-style:italic;
    text-transform:none !important; letter-spacing:0.02em !important;
    border:1px solid rgba(139,58,31,0.3) !important; background:transparent !important;
}

.book-dots { display:flex; justify-content:center; align-items:center; gap:8px; margin:0.9rem 0 0.6rem; }
.cross-ref-hint {
    max-width:600px; margin:-0.4rem auto 0.8rem; text-align:center;
    font-size:0.76rem; color:var(--text-muted); font-style:italic;
    background:rgba(217,119,87,0.06); border-radius:8px; padding:0.4rem 0.8rem;
}
.cross-ref-hint strong { color:#C26847; font-style:normal; }
.relevance-hint {
    max-width:600px; margin:-0.4rem auto 0.8rem; text-align:left;
    font-size:0.8rem; color:var(--text-sub); line-height:1.5;
    background:rgba(16,185,129,0.07); border-left:3px solid #10B981;
    border-radius:6px; padding:0.5rem 0.9rem;
}
.relevance-hint strong { color:#047857; }

/* ── ONBOARDING BANNER — pure CSS dismiss, same pattern as dark mode toggle ── */
#onboardDismiss { display:none; }
.onboarding-banner {
    max-width:700px; margin:0 auto 1.5rem; display:flex; align-items:center;
    gap:14px; background:rgba(217,119,87,0.08); border:1.5px solid rgba(217,119,87,0.25);
    border-radius:14px; padding:0.9rem 1.3rem; animation:fadeSlideDown 0.6s ease both;
}
.onboarding-text { font-size:0.85rem; color:var(--text-sub); line-height:1.5; flex:1; }
.onboarding-dismiss {
    flex-shrink:0; cursor:pointer; font-size:0.75rem; font-weight:700;
    color:#D97757; border:1.5px solid rgba(217,119,87,0.4); border-radius:999px;
    padding:0.35rem 0.9rem; white-space:nowrap; transition:all 0.2s ease;
}
.onboarding-dismiss:hover { background:#D97757; color:#fff; }
#onboardDismiss:checked ~ .onboarding-banner { display:none; }
.book-dot { width:5px; height:5px; border-radius:50%; background:rgba(139,58,31,0.3); transition:all 0.25s ease; }
.book-dot-active { background:#8B3A1F; width:5px; transform:scale(1.8); }

/* ── NEWSPAPER "TURN THE PAGE" BUTTONS ──
   Rather than fighting Streamlit's built-in button padding (which kept
   winning the CSS specificity fight regardless of approach), these use
   FULL TEXT labels ("‹ Previous Page" / "Next Page ›") styled at whatever
   natural size Streamlit renders — guaranteed to show real, readable
   words instead of a lone glyph that could vanish in some fonts. ── */
.book-nav-scope { height:0; margin:0; padding:0; }
.book-nav-scope ~ div[data-testid="stHorizontalBlock"] button {
    font-family:'Playfair Display',Georgia,serif !important;
    font-style:italic !important; font-weight:700 !important;
    font-size:0.85rem !important; letter-spacing:0.01em !important;
    text-transform:none !important;
    background:#F9F4E8 !important; color:#8B3A1F !important;
    border:1.5px solid rgba(139,58,31,0.4) !important;
    border-radius:3px !important;
    box-shadow:2px 2px 0 rgba(139,58,31,0.15) !important;
}
.book-nav-scope ~ div[data-testid="stHorizontalBlock"] button:hover:not(:disabled) {
    background:#8B3A1F !important; color:#F9F4E8 !important;
    transform:translate(-1px,-1px) !important;
    box-shadow:3px 3px 0 rgba(139,58,31,0.25) !important;
}
.book-nav-scope ~ div[data-testid="stHorizontalBlock"] button:disabled { opacity:0.25 !important; }

/* ── ACCESSIBILITY: visible focus rings for keyboard navigation ── */
button:focus-visible, input:focus-visible, a:focus-visible,
.dm-label:has(input:focus-visible) {
    outline: 3px solid #D97757 !important;
    outline-offset: 2px !important;
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# Pure-CSS dark toggle — clicking it triggers NO Streamlit rerun.
st.markdown('<input type="checkbox" id="dmchk"><label for="dmchk" class="dm-label"></label>', unsafe_allow_html=True)

# Pure-CSS font-size control (A⁻/A/A⁺) — same no-rerun technique as dark
# mode. Scales the ROOT font-size, which every existing "rem" measurement
# in the app is relative to, so it cascades everywhere with zero need to
# touch individual font-size declarations.
st.markdown(
    '<div class="fs-toggle">'
    '<input type="radio" name="fontsize" id="fsSmall">'
    '<input type="radio" name="fontsize" id="fsNormal" checked>'
    '<input type="radio" name="fontsize" id="fsLarge">'
    '<label for="fsSmall" class="fs-btn">A⁻</label>'
    '<label for="fsNormal" class="fs-btn">A</label>'
    '<label for="fsLarge" class="fs-btn">A⁺</label>'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sati-bg"><div class="orb orb1"></div><div class="orb orb2"></div>'
    '<div class="orb orb3"></div><div class="orb orb4"></div></div>',
    unsafe_allow_html=True
)


def sep():
    st.markdown(
        '<div class="sati-sep"><div class="sati-sep-dot"></div>'
        '<div class="sati-sep-dot"></div><div class="sati-sep-dot"></div></div>',
        unsafe_allow_html=True
    )


def news_section(title, badge_cls, idx_cls, icon, items, live_badge="", section_key="", cross_refs=None, relevance_map=None):
    st.markdown(
        f'<div class="sati-section">'
        f'<div class="section-header">'
        f'<div class="section-badge {badge_cls}">{icon}</div>'
        f'<h2 class="section-title">{title}</h2>{live_badge}</div>',
        unsafe_allow_html=True
    )

    if not items:
        st.markdown('</div>', unsafe_allow_html=True)
        return

    page_key = f"news_page_{section_key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    st.session_state[page_key] = max(0, min(st.session_state[page_key], len(items) - 1))
    idx = st.session_state[page_key]
    item = items[idx]

    src = item.get("source", "")
    url = item.get("url", "")
    hl_text = item.get("headline", "")
    has_real_url = bool(url)
    if has_real_url:
        # Live-fetched item — we have the exact article URL.
        final_url = url
    else:
        # AI-generated item — no specific article exists. Prefer the real
        # outlet's homepage if we recognise the source name; only fall back
        # to a headline search when the source is unrecognised.
        final_url = resolve_source_url(src, hl_text)

    hl = (f'<a href="{final_url}" target="_blank" style="color:inherit;text-decoration:none;">{hl_text}</a>'
          if final_url else hl_text)
    src_html = (
        f'<a href="{final_url}" target="_blank" class="news-source">{src} ↗</a>'
        if src and final_url else
        (f'<span class="news-source">{src}</span>' if src else "")
    )

    st.markdown(
        f'<div class="news-book-wrap">'
        f'<div class="news-card news-book-page">'
        f'<div class="news-index {idx_cls}">0{idx+1}</div>'
        f'<div><div class="news-headline">{hl}</div>'
        f'<div class="news-detail">{item.get("detail","")}</div>'
        f'{src_html}</div></div></div>',
        unsafe_allow_html=True
    )

    # Cross-reference hint — a soft, best-effort "possibly related" note,
    # pure keyword-overlap heuristic, never claiming certainty.
    if cross_refs:
        related = cross_refs.get((section_key, idx))
        if related:
            other_topic, _, other_headline = related[0]
            st.markdown(
                f'<div class="cross-ref-hint">🔗 Possibly related — '
                f'<strong>{other_topic}</strong>: {other_headline}</div>',
                unsafe_allow_html=True
            )

    # "Why this matters" — only present when the user opted in and this
    # specific item was a live-fetched headline covered by that call.
    if relevance_map:
        explanation = relevance_map.get(f"{section_key}-{idx}")
        if explanation:
            st.markdown(
                f'<div class="relevance-hint">💡 <strong>Why it matters:</strong> {explanation}</div>',
                unsafe_allow_html=True
            )

    # Page-turn controls — newspaper-style "turn the page" links with full
    # text labels (guaranteed to render, unlike a lone glyph that could
    # vanish depending on the font actually applied to the button).
    dots = "".join(
        '<span class="book-dot book-dot-active"></span>' if i == idx else '<span class="book-dot"></span>'
        for i in range(len(items))
    )
    st.markdown(f'<div class="book-dots">{dots}</div>', unsafe_allow_html=True)

    st.markdown('<div class="book-nav-scope"></div>', unsafe_allow_html=True)
    bcol1, bcol2, bcol3, bcol4, bcol5 = st.columns([1, 2.4, 1.6, 2.4, 1])
    with bcol2:
        if st.button("‹ Previous Page", key=f"{page_key}_prev", disabled=(idx == 0), use_container_width=True):
            st.session_state[page_key] -= 1
            st.rerun()
    with bcol3:
        st.markdown(
            f'<div style="text-align:center;font-family:Georgia,serif;font-style:italic;'
            f'font-size:0.78rem;font-weight:700;color:#8B3A1F;padding-top:0.6rem;'
            f'letter-spacing:0.03em;">— {idx+1} of {len(items)} —</div>',
            unsafe_allow_html=True
        )
    with bcol4:
        if st.button("Next Page ›", key=f"{page_key}_next", disabled=(idx == len(items) - 1), use_container_width=True):
            st.session_state[page_key] += 1
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
# RENDER — draws from stored session result on every rerun
# ═══════════════════════════════════════════════════
def render_result(res: dict):
    payload      = res["payload"]
    topics       = res["topics"]
    city         = res["city"]
    voice_choice = res["voice"]
    lang_display = res["lang"]
    live_quote   = res["quote"]
    live_word    = res["word"]
    weather_data = res["weather"]
    markets_data = res["markets"]
    audio_b64    = res.get("audio_b64")
    listen_time  = res.get("listen_time", "")
    gen_date     = res.get("gen_date", "")

    # ── HERO ROW: audio card + weather side by side ──
    if audio_b64:
        audio_html = (
            f'<div class="audio-shell">'
            f'<div class="audio-pill">▶ Now Playing</div>'
            f'<div class="audio-title">Your Mindful Morning Brief · {gen_date}</div>'
            f'<div class="audio-meta">{voice_choice} · {lang_display} · 🌆 {city}</div>'
            f'<div class="listen-badge">🎧 {listen_time}</div>'
            f'</div>'
        )
    else:
        audio_html = (
            f'<div class="audio-shell">'
            f'<div class="audio-pill">📄 Text Brief</div>'
            f'<div class="audio-title">Your Mindful Morning Brief · {gen_date}</div>'
            f'<div class="audio-meta">{lang_display} · 🌆 {city} · Audio skipped for speed</div>'
            f'</div>'
        )

    if weather_data:
        wicon = weather_emoji(weather_data.get("icon", ""))
        cond = weather_data.get("icon", "")
        particle_html = ""
        if cond in ("Rain", "Drizzle", "Thunderstorm"):
            particle_html = '<div class="wx-particles wx-rain">' + '<span></span>' * 12 + '</div>'
        elif cond == "Clear":
            particle_html = '<div class="wx-particles wx-sun"><span class="wx-ray"></span></div>'
        elif cond == "Clouds":
            particle_html = '<div class="wx-particles wx-clouds"><span></span><span></span></div>'
        weather_html = (
            f'<div class="weather-widget" style="position:relative;overflow:hidden;">'
            f'{particle_html}'
            f'<div class="weather-icon" style="position:relative;z-index:1;">{wicon}</div>'
            f'<div style="position:relative;z-index:1;"><div class="weather-temp">{weather_data["temp"]}°C</div>'
            f'<div class="weather-desc">{weather_data["desc"]} · {city}</div>'
            f'<div class="weather-meta">💧 {weather_data["humidity"]}% · 💨 {weather_data["wind"]} km/h</div></div>'
            f'<div style="position:relative;z-index:1;"><div class="weather-feels">Feels like</div>'
            f'<div class="weather-temp" style="font-size:1.5rem">{weather_data["feels"]}°C</div></div>'
            f'</div>'
        )
    else:
        ws = payload.get("weather_summary", "")
        weather_html = (
            f'<div class="weather-widget" style="grid-template-columns:auto 1fr;">'
            f'<div class="weather-icon">🌤</div>'
            f'<div><div class="weather-desc" style="font-size:1rem;">{ws}</div></div>'
            f'</div>'
        )

    st.markdown(f'<div class="hero-row">{audio_html}{weather_html}</div>', unsafe_allow_html=True)

    if audio_b64:
        autoplay_attr = "autoplay" if res.get("fresh", False) else ""
        components.html(f"""
        <div style="font-family:'Inter',sans-serif;overflow:visible;padding-bottom:6px;">
            <audio id="satiAudioPlayer" controls {autoplay_attr} style="width:100%;border-radius:12px;"
                   src="data:audio/mp3;base64,{audio_b64}"></audio>
            <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap;align-items:center;">
                <span style="font-size:0.75rem;color:#94A3B8;align-self:center;margin-right:4px;">Speed:</span>
                <button onclick="document.getElementById('satiAudioPlayer').playbackRate=0.75"
                    style="padding:4px 10px;border-radius:999px;border:1px solid #D97757;background:transparent;color:#E8A87C;cursor:pointer;font-size:0.72rem;">0.75x</button>
                <button onclick="document.getElementById('satiAudioPlayer').playbackRate=1.0"
                    style="padding:4px 10px;border-radius:999px;border:1px solid #D97757;background:#D97757;color:#fff;cursor:pointer;font-size:0.72rem;">1x</button>
                <button onclick="document.getElementById('satiAudioPlayer').playbackRate=1.25"
                    style="padding:4px 10px;border-radius:999px;border:1px solid #D97757;background:transparent;color:#E8A87C;cursor:pointer;font-size:0.72rem;">1.25x</button>
                <button onclick="document.getElementById('satiAudioPlayer').playbackRate=1.5"
                    style="padding:4px 10px;border-radius:999px;border:1px solid #D97757;background:transparent;color:#E8A87C;cursor:pointer;font-size:0.72rem;">1.5x</button>
            </div>
        </div>
        """, height=140)
        st.markdown(
            f'<div class="dl-wrap"><a href="data:audio/mp3;base64,{audio_b64}" '
            f'download="saticast_{datetime.now().strftime("%Y%m%d")}.mp3">⬇️ Download MP3</a></div>',
            unsafe_allow_html=True
        )

    # ── GREETING ──
    greeting = payload.get("greeting", "Good morning! Welcome to SatiCast.")
    st.markdown(f'<div class="greeting-card">👋 {greeting}</div>', unsafe_allow_html=True)

    live_tag = '<span class="live-source-badge">🔴 Live headlines</span>'

    def items_for(topic_name, payload_key):
        live = res.get(f"{NEWS_TOPIC_MAP[topic_name]}_live") or []
        if live:
            return live, live_tag
        return payload.get(payload_key, []), ""

    # Compute cross-topic story relationships ONCE, across every topic the
    # user selected — pure Python, no extra API call. news_section() looks
    # up (topic, idx) in this dict to show a "possibly related" hint.
    _all_items_by_topic = {}
    for _topic_name, _payload_key in [("National", "india_news"), ("Global", "global_news"), ("Tech", "tech_news")]:
        if _topic_name in topics:
            _items, _ = items_for(_topic_name, _payload_key)
            if _items:
                _all_items_by_topic[_topic_name] = _items
    cross_refs = find_cross_references(_all_items_by_topic)
    relevance_map = res.get("relevance_map") or {}

    def render_market():
        if not markets_data:
            return
        sep()
        st.markdown(
            '<div class="sati-section"><div class="section-header">'
            '<div class="section-badge badge-sports">📈</div>'
            '<h2 class="section-title">Market Pulse</h2></div></div>',
            unsafe_allow_html=True
        )
        chips = ""
        for name, md in markets_data.items():
            cls = "market-chg-up" if md["up"] else "market-chg-down"
            arrow = "▲" if md["up"] else "▼"
            spark = md.get("sparkline", "")
            chips += (
                f'<div class="market-chip"><div class="market-name">{name}</div>'
                f'<div class="market-price">{md["price"]:,.1f}</div>'
                f'<div class="{cls}">{arrow} {abs(md["chg"])}%</div>'
                f'<div class="market-spark">{spark}</div></div>'
            )
        st.markdown(f'<div class="market-strip">{chips}</div>', unsafe_allow_html=True)

    def render_national():
        sep()
        items, badge = items_for("National", "india_news")
        news_section("National Intel", "badge-india", "idx-india", "🇮🇳", items, badge, "National", cross_refs, relevance_map)

    def render_global():
        sep()
        items, badge = items_for("Global", "global_news")
        news_section("Global Overview", "badge-global", "idx-global", "🌐", items, badge, "Global", cross_refs, relevance_map)

    def render_tech():
        sep()
        items, badge = items_for("Tech", "tech_news")
        news_section("Tech & Architecture", "badge-tech", "idx-tech", "⚡", items, badge, "Tech", cross_refs, relevance_map)

    def render_sports():
        items, badge = items_for("Sports", "sports_flash")
        if items:
            sep()
            news_section("Sports Flash", "badge-sports", "idx-sports", "🏏", items, badge, "Sports", cross_refs, relevance_map)

    def render_learning():
        if not payload.get("learning_byte"):
            return
        sep()
        lb = payload["learning_byte"]
        topic_num = datetime.now().timetuple().tm_yday % len(LEARNING_TOPICS) + 1
        st.markdown(
            f'<div class="sati-section">'
            f'<div class="section-header">'
            f'<div class="section-badge badge-learn">💡</div>'
            f'<h2 class="section-title">Learning Byte</h2>'
            f'<span class="live-source-badge">📅 Topic #{topic_num} of {len(LEARNING_TOPICS)}</span>'
            f'</div>'
            f'<div class="learn-card">'
            f'<div class="learn-topic">{lb.get("topic","")}</div>'
            f'<div class="learn-insight">{lb.get("insight","")}</div>'
            f'<div class="learn-tip">💡 {lb.get("tip","")}</div>'
            f'<div class="learn-daily-note">✦ A new engineering topic every day</div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    # Sections render in the SAME ORDER the user selected them in the
    # "Topics to include" multiselect, instead of a fixed hardcoded order.
    section_renderers = {
        "Market":   render_market,
        "National": render_national,
        "Global":   render_global,
        "Tech":     render_tech,
        "Sports":   render_sports,
        "Learning": render_learning,
    }
    for topic_name in topics:
        renderer = section_renderers.get(topic_name)
        if renderer:
            renderer()

    # ── QUOTE + WORD side by side ──
    sep()
    if live_quote.get("source_url"):
        q_badge = f'<a href="{live_quote["source_url"]}" target="_blank" class="live-source-badge">🔗 {live_quote["source"]}</a>'
    else:
        q_badge = f'<span class="live-source-badge">{live_quote.get("source","")}</span>'
    if live_word.get("source_url"):
        w_badge = f'<a href="{live_word["source_url"]}" target="_blank" class="live-source-badge">🔗 {live_word["source"]}</a>'
    else:
        w_badge = f'<span class="live-source-badge">{live_word.get("source","")}</span>'
    pos_html = f'<span class="word-pos">{live_word.get("pos","")}</span>' if live_word.get("pos") else ""
    example_html = (
        f'<div class="word-label">In Context</div>'
        f'<div class="word-val"><em>"{live_word["example"]}"</em></div>'
    ) if live_word.get("example") else ""

    quote_block = (
        f'<div>'
        f'<div class="section-header">'
        f'<div class="section-badge badge-focus">🧘</div>'
        f'<h2 class="section-title">Moment of Focus</h2>{q_badge}</div>'
        f'<div class="focus-card">'
        f'<div class="focus-quote">"{live_quote.get("quote","")}"</div>'
        f'<div class="focus-author">— {live_quote.get("author","")}</div>'
        f'<span class="focus-live-note">✦ Refreshes daily with a new quote</span>'
        f'</div></div>'
    )
    word_block = (
        f'<div>'
        f'<div class="section-header">'
        f'<div class="section-badge badge-word">📝</div>'
        f'<h2 class="section-title">Daily Lexicon</h2>{w_badge}</div>'
        f'<div class="word-card">'
        f'<div class="word-main">{live_word.get("word","")} {pos_html}</div>'
        f'<div class="word-label">Meaning</div>'
        f'<div class="word-val">{live_word.get("definition","")}</div>'
        f'{example_html}'
        f'<span class="focus-live-note">✦ Changes every day</span>'
        f'</div></div>'
    )
    st.markdown(f'<div class="dual-row">{quote_block}{word_block}</div>', unsafe_allow_html=True)

    # ── ON THIS DAY ──
    otd = res.get("on_this_day") or {}
    if otd.get("text"):
        sep()
        st.markdown(
            f'<div class="sati-section">'
            f'<div class="section-header">'
            f'<div class="section-badge badge-focus">📜</div>'
            f'<h2 class="section-title">On This Day</h2>'
            f'<span class="live-source-badge">🔗 Wikipedia</span></div>'
            f'<div class="focus-card">'
            f'<div class="focus-quote">{otd.get("year","")}</div>'
            f'<div class="focus-expl" style="margin-top:0.4rem;">{otd["text"]}</div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    # ── DOWNLOAD TEXT BRIEF ──
    brief_txt = build_text_export(res)
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "⬇️ Download as Text", data=brief_txt,
            file_name=f"saticast_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain", key="dl_brief_txt", use_container_width=True
        )
    with dl_col2:
        pdf_bytes, pdf_err = build_pdf_export(res)
        if pdf_bytes:
            st.download_button(
                "📰 Download as PDF", data=pdf_bytes,
                file_name=f"saticast_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf", key="dl_brief_pdf", use_container_width=True
            )
        elif pdf_err:
            st.caption(f"📄 PDF export unavailable: {pdf_err}")

    # ── FOOTER ──
    time_str = f' · {listen_time}' if listen_time else ''
    st.markdown(
        f'<div class="sati-footer"><p>🪷 SatiCast · {datetime.now().strftime("%A, %B %d %Y")}'
        f' · 🌆 {city} · {voice_choice}{time_str}</p></div>',
        unsafe_allow_html=True
    )


def build_text_export(res: dict) -> str:
    """Plain-text version of the brief for the download button."""
    p = res["payload"]
    lines = [
        f"SATICAST — {res.get('gen_date','')}",
        f"City: {res['city']} · Voice: {res['voice']} · Language: {res['lang']}",
        "",
        p.get("greeting", ""),
        "",
    ]
    for key, title in [("india_news", "NATIONAL"), ("global_news", "GLOBAL"), ("tech_news", "TECH")]:
        items = p.get(key) or res.get(f"{key.split('_')[0]}_live") or []
        if items:
            lines.append(f"— {title} —")
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. {item.get('headline','')} — {item.get('detail','')}")
            lines.append("")
    q = res.get("quote", {})
    if q.get("quote"):
        lines.append(f'"{q["quote"]}" — {q.get("author","")}')
        lines.append("")
    w = res.get("word", {})
    if w.get("word"):
        lines.append(f"Word of the Day: {w['word']} — {w.get('definition','')}")
    return "\n".join(lines)


def build_pdf_export(res: dict):
    """
    Newspaper-style PDF of the brief, using fpdf2 — pure Python, no system
    dependencies (unlike weasyprint), so it's safe to add to a Streamlit
    Cloud deployment. Returns (pdf_bytes, None) on success, or
    (None, error_message) if fpdf2 isn't installed.
    """
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except ImportError:
        return None, "fpdf2 isn't installed — add 'fpdf2' to requirements.txt to enable PDF export."

    p = res["payload"]

    def clean(s: str) -> str:
        # fpdf2's built-in fonts are latin-1 only; keep this safe by
        # stripping anything outside that range (emoji, exotic punctuation).
        return (s or "").encode("latin-1", "ignore").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Times", "B", 26)
    pdf.cell(0, 12, "SATICAST", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Times", "I", 10)
    pdf.cell(0, 6, clean(f"{res.get('gen_date','')} - {res['city']} - {res['lang']}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(4)
    pdf.set_draw_color(139, 58, 31)
    pdf.set_line_width(0.6)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Times", "", 12)
    pdf.multi_cell(0, 7, clean(p.get("greeting", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    for key, title in [("india_news", "NATIONAL INTEL"), ("global_news", "GLOBAL OVERVIEW"), ("tech_news", "TECH & ARCHITECTURE")]:
        items = p.get(key) or res.get(f"{key.split('_')[0]}_live") or []
        if not items:
            continue
        pdf.set_font("Times", "B", 14)
        pdf.cell(0, 8, clean(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for i, item in enumerate(items, 1):
            pdf.set_font("Times", "B", 11)
            pdf.multi_cell(0, 6, clean(f"{i}. {item.get('headline','')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Times", "", 10)
            pdf.multi_cell(0, 5.5, clean(item.get("detail", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            src = item.get("source", "")
            if src:
                pdf.set_font("Times", "I", 9)
                pdf.cell(0, 5, clean(f"-- {src}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        pdf.ln(2)

    q = res.get("quote", {})
    if q.get("quote"):
        pdf.set_font("Times", "BI", 12)
        pdf.multi_cell(0, 7, clean(f'"{q["quote"]}"'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Times", "", 10)
        pdf.cell(0, 6, clean(f"-- {q.get('author','')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

    w = res.get("word", {})
    if w.get("word"):
        pdf.set_font("Times", "BI", 13)
        pdf.cell(0, 7, clean(f"Word of the Day: {w['word']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Times", "", 10)
        pdf.multi_cell(0, 5.5, clean(w.get("definition", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output()), None


# ═══════════════════════════════════════════════════
# MASTHEAD
# ═══════════════════════════════════════════════════
st.markdown(
    '<div class="sati-masthead">'
    '<span class="sati-lotus">🪷</span>'
    '<div class="sati-wordmark">SATICAST</div>'
    '<div class="sati-tagline">Daily Cast &nbsp;·&nbsp; Your mindful morning briefing</div>'
    '<div class="sati-meaning">✦ Sati — the Pali word for mindfulness &amp; awareness ✦</div>'
    '<div class="waveform-wrap">'
    + '<div class="bar"></div>' * 16 +
    '</div></div>',
    unsafe_allow_html=True
)

# First-time onboarding banner — pure CSS dismiss (same zero-rerun checkbox
# technique as the dark-mode toggle), so there's no button-sizing fight and
# no extra script rerun just to hide a hint. Resets on a fresh page load,
# which is a reasonable scope for a lightweight "new here?" hint.
st.markdown(
    '<input type="checkbox" id="onboardDismiss">'
    '<div class="onboarding-banner">'
    '<div class="onboarding-text">👋 <strong>New here?</strong> Pick your voice, city, and topics '
    'below, then hit <strong>Generate Morning Brief</strong>. Use 🌙/☀️ (top-right) for dark mode, '
    'and A⁻ / A / A⁺ for text size.</div>'
    '<label for="onboardDismiss" class="onboarding-dismiss">Got it ✕</label>'
    '</div>',
    unsafe_allow_html=True
)

# ═══════════════════════════════════════════════════
# CONTROLS — keyed widgets so preferences persist across reruns
#
# NOTE: Voice & Accent / TTS Engine use st.pills — Streamlit's own
# purpose-built single-select pill widget — which lets you switch freely
# between options in one click (unlike st.multiselect + max_selections=1,
# which blocks adding a new pick until the old one is manually removed).
# If this Streamlit version predates st.pills, falls back to a custom
# button-grid single-select that was already confirmed to render
# correctly (checkmark + gradient highlight on the selected option).
# ═══════════════════════════════════════════════════
def pick_one_pill(label: str, options: list, state_key: str, default: str):
    if state_key not in st.session_state or st.session_state[state_key] not in options:
        st.session_state[state_key] = default
    # NOTE: st.pills' own internal styling (label color, unselected pill
    # background) is controlled by Streamlit's built-in theme and cannot be
    # reliably overridden by our CSS — it rendered with poor contrast against
    # our custom cream/terracotta theme. The button-grid fallback below is
    # fully ours to style, so it's used unconditionally for consistent theming.
    return _pill_grid_fallback(label, options, state_key, default)


def _pill_grid_fallback(label: str, options: list, state_key: str, default: str, per_row: int = 3):
    st.markdown(f'<div class="pill-label">{label}</div>', unsafe_allow_html=True)
    st.markdown('<div class="pill-scope-fallback"></div>', unsafe_allow_html=True)
    for row_start in range(0, len(options), per_row):
        row_opts = options[row_start:row_start + per_row]
        cols = st.columns(per_row)
        for i, opt in enumerate(row_opts):
            with cols[i]:
                is_sel = st.session_state[state_key] == opt
                btn_label = f"✓ {opt}" if is_sel else opt
                if is_sel:
                    st.markdown('<div class="pill-selected-marker"></div>', unsafe_allow_html=True)
                if st.button(btn_label, key=f"{state_key}_btn_{row_start + i}", use_container_width=True):
                    st.session_state[state_key] = opt
                    st.rerun()
    return st.session_state[state_key]


voice_keys = list(VOICE_OPTIONS.keys())

voice_choice = pick_one_pill("🎙 Voice & Accent", voice_keys, "voice_pill", voice_keys[0])

c2, c3 = st.columns(2)
with c2:
    city_input = st.text_input("🌆 City for Weather", value="Mumbai",
                               placeholder="e.g. Nagpur, Delhi, Pune…", key="pref_city")
with c3:
    tts_engines = ["gTTS (Free)"]
    if ELEVENLABS_KEY:
        tts_engines += list(ELEVENLABS_VOICES.keys())
    tts_choice = pick_one_pill("🔊 TTS Engine", tts_engines, "tts_pill", tts_engines[0])

voice_cfg    = VOICE_OPTIONS[voice_choice]
lang_code    = voice_cfg["lang"]
tld_code     = voice_cfg["tld"]
lang_display = LANG_LABEL.get(lang_code, "English")

c4, c5 = st.columns([2, 1])
with c4:
    chosen_topics = st.multiselect("📌 Topics to include", options=list(TOPIC_ICONS.keys()),
                                   default=["National", "Global", "Tech"], key="pref_topics")
with c5:
    generate_audio = st.toggle("🎧 Generate Audio", value=True, key="pref_audio",
                               help="Turn off to skip voice generation — text brief appears much faster.")

explain_relevance = st.toggle(
    "💡 Explain why each live headline matters", value=False, key="pref_relevance",
    help="Adds one extra AI-generated sentence per LIVE headline (requires NEWS_API_KEY) — off by default since it adds one more parallel call."
)

your_name = st.text_input("👤 Your Name (optional — personalizes the greeting)",
                          placeholder="e.g. Pranay", key="pref_name")

st.markdown(
    f'<div class="script-lang-badge">📢 Script Language auto-follows your voice: '
    f'<strong>{lang_display}</strong></div>',
    unsafe_allow_html=True
)

# ═══════════════════════════════════════════════════
# GENERATE
# ═══════════════════════════════════════════════════
if "last_gen_time" not in st.session_state:
    st.session_state.last_gen_time = 0.0

RATE_LIMIT_SECS = 15
now_ts = time.time()
cooldown_left = RATE_LIMIT_SECS - (now_ts - st.session_state.last_gen_time)
in_cooldown = cooldown_left > 0

if in_cooldown:
    st.markdown(
        f'<div style="text-align:center;background:rgba(217,119,87,0.08);'
        f'border:1.5px solid rgba(217,119,87,0.2);border-radius:14px;'
        f'padding:0.6rem 1rem;margin-bottom:1rem;color:#D97757;font-weight:700;font-size:0.85rem;">'
        f'⏳ Please wait {int(cooldown_left)+1}s before generating again</div>',
        unsafe_allow_html=True
    )

trigger = st.button("🪷 Generate Morning Brief", disabled=in_cooldown)

if trigger:
    st.session_state.last_gen_time = time.time()

    if not chosen_topics:
        st.warning("⚠️ Please select at least one topic.")
        st.stop()

    city = city_input.strip() or "Mumbai"
    slot = st.empty()
    slot.markdown(render_loader(0), unsafe_allow_html=True)

    # ── PARALLEL FETCH ──
    slot.markdown(render_loader(1), unsafe_allow_html=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {
            "quote":   ex.submit(fetch_quote_of_day),
            "word":    ex.submit(fetch_word_of_day),
            "weather": ex.submit(fetch_weather, city),
            "otd":     ex.submit(fetch_on_this_day),
        }
        if "Market" in chosen_topics:
            futs["markets"] = ex.submit(fetch_markets)
        for topic_name, api_key_name in NEWS_TOPIC_MAP.items():
            if topic_name in chosen_topics:
                futs[api_key_name] = ex.submit(fetch_news, api_key_name)

        def safe(key, default):
            try:
                return futs[key].result(timeout=15) if key in futs else default
            except Exception:
                return default

        live_quote   = safe("quote",   {"quote": "", "author": "", "source": "", "source_url": ""})
        live_word    = safe("word",    {"word": "", "pos": "", "definition": "", "example": "", "source": "", "source_url": ""})
        weather_data = safe("weather", {})
        markets_data = safe("markets", {})
        on_this_day  = safe("otd", {})
        live_news    = {k: safe(k, []) for k in ("india", "global", "tech", "sports")}

    # Which news topics still need the LLM (no live data)?
    llm_news_topics = [t for t in chosen_topics
                       if t in NEWS_TOPIC_MAP and not live_news[NEWS_TOPIC_MAP[t]]]
    need_weather_summary = not bool(weather_data)
    need_learning        = "Learning" in chosen_topics
    learning_topic       = todays_learning_topic()

    # Compact headline context for the spoken script (top 3 per topic to keep prompt light)
    news_ctx_parts = []
    for t in chosen_topics:
        if t in NEWS_TOPIC_MAP and live_news[NEWS_TOPIC_MAP[t]]:
            tops = live_news[NEWS_TOPIC_MAP[t]][:3]
            news_ctx_parts.append(f"{t}: " + " | ".join(i["headline"] for i in tops))
    news_ctx = "\n".join(news_ctx_parts)

    weather_line = ""
    if weather_data:
        weather_line = (f"Weather in {city}: {weather_data['temp']}°C, {weather_data['desc']}, "
                        f"feels {weather_data['feels']}°C.")

    slot.markdown(render_loader(2), unsafe_allow_html=True)

    try:
        current_date = datetime.now().strftime("%A, %B %d, %Y")

        quote_line = f'QUOTE to weave into spoken_script: "{live_quote.get("quote","")}" — {live_quote.get("author","")}'
        word_line  = f'WORD to mention in spoken_script: {live_word.get("word","")} — {live_word.get("definition","")}'
        user_ctx   = f"Date: {current_date}\nCity: {city}\nTopics: {', '.join(chosen_topics)}"

        needs_misc_call = need_weather_summary or need_learning

        def call_script(user_message: str, max_words_hint: str = ""):
            cache_key = ("script", lang_code, news_ctx, quote_line, word_line,
                        weather_line, your_name, user_message, max_words_hint)

            def _compute():
                sys_prompt = build_script_prompt(lang_code, news_ctx, quote_line, word_line, weather_line, your_name)
                msg = user_message + (f"\n\nIMPORTANT: {max_words_hint}" if max_words_hint else "")
                c = nim_chat_json(sys_prompt, msg, temperature=0.3, max_tokens=1800)
                return safe_parse_llm_json(c.choices[0].message.content)

            return cached_llm_call(cache_key, _compute)

        def call_news_topic(topic_name: str) -> dict:
            """
            Dedicated call for ONE news topic — full token budget for 5 items,
            so it can never get truncated to 1 item by a shared budget.
            Retries once (smaller ask) if the first attempt is malformed.
            """
            cache_key = ("news_topic", topic_name, user_ctx)

            def _compute():
                sys_prompt = build_news_topic_prompt(topic_name)
                msg = f"{user_ctx}\nGenerate the 5 {topic_name} news items now."
                c = nim_chat_json(sys_prompt, msg, temperature=0.4, max_tokens=1200)
                try:
                    return safe_parse_llm_json(c.choices[0].message.content)
                except Exception:
                    # Retry once, even more tightly scoped
                    c2 = nim_chat_json(
                        sys_prompt, msg + " Keep each 'detail' under 15 words.",
                        temperature=0.3, max_tokens=1200
                    )
                    return safe_parse_llm_json(c2.choices[0].message.content)

            return cached_llm_call(cache_key, _compute)

        def call_misc(user_message: str) -> dict:
            cache_key = ("misc", need_weather_summary, need_learning, learning_topic, user_message)

            def _compute():
                sys_prompt = build_misc_prompt(need_weather_summary, need_learning, learning_topic)
                c = nim_chat_json(sys_prompt, user_message, temperature=0.3, max_tokens=900)
                return safe_parse_llm_json(c.choices[0].message.content)

            return cached_llm_call(cache_key, _compute)

        # Build the keyed-headline set for the OPTIONAL relevance call, using
        # only live-fetched items (the AI-generated ones aren't known until
        # after this same parallel batch completes, so they're out of scope
        # for this pass — see build_relevance_prompt's docstring).
        relevance_keyed_headlines = {}
        if explain_relevance:
            for _disp_name, _api_key in NEWS_TOPIC_MAP.items():
                for _i, _item in enumerate(live_news.get(_api_key, [])):
                    if _item.get("headline"):
                        relevance_keyed_headlines[f"{_disp_name}-{_i}"] = _item["headline"]

        def call_relevance(keyed_headlines: dict) -> dict:
            cache_key = ("relevance", tuple(sorted(keyed_headlines.items())))

            def _compute():
                sys_prompt = build_relevance_prompt(keyed_headlines)
                c = nim_chat_json(sys_prompt, "Explain each headline now.", temperature=0.4, max_tokens=900)
                return safe_parse_llm_json(c.choices[0].message.content)

            return cached_llm_call(cache_key, _compute)

        slot.markdown(render_loader(2), unsafe_allow_html=True)

        # ── LAUNCH SCRIPT + ONE CALL PER MISSING NEWS TOPIC + MISC + OPTIONAL RELEVANCE — ALL IN PARALLEL ──
        with ThreadPoolExecutor(max_workers=max(4, len(llm_news_topics) + 3)) as ex:
            fut_script = ex.submit(call_script, user_ctx)
            fut_news   = {t: ex.submit(call_news_topic, t) for t in llm_news_topics}
            fut_misc   = ex.submit(call_misc, user_ctx) if needs_misc_call else None
            fut_relevance = (
                ex.submit(call_relevance, relevance_keyed_headlines)
                if relevance_keyed_headlines else None
            )

            # Script result feeds TTS — grab it first, with a repair-retry inline.
            try:
                script_payload = fut_script.result(timeout=45)
            except Exception:
                script_payload = call_script(
                    user_ctx, "Keep spoken_script concise (under 180 words) to guarantee the JSON completes."
                )

            tts_text = script_payload.get("spoken_script", "")

            # ── TTS starts the instant the script is ready — overlapping
            #    with the news/misc calls if they're still in flight. ──
            tts_future = None
            if generate_audio and tts_text:
                slot.markdown(render_loader(3), unsafe_allow_html=True)

                def run_tts():
                    audio_bytes = None
                    if tts_choice != "gTTS (Free)" and ELEVENLABS_KEY:
                        audio_bytes = elevenlabs_tts(tts_text, ELEVENLABS_VOICES.get(tts_choice))
                    if audio_bytes is None:
                        tts_obj = gTTS(text=tts_text, lang=lang_code, tld=tld_code, slow=False)
                        fp = io.BytesIO()
                        tts_obj.write_to_fp(fp)
                        fp.seek(0)
                        audio_bytes = fp.read()
                    return audio_bytes

                tts_future = ex.submit(run_tts)

            # Collect each topic's news result — these have likely already
            # finished by now since they ran concurrently with the script call.
            visual_payload = {}
            for topic_name, fut in fut_news.items():
                try:
                    visual_payload.update(fut.result(timeout=45))
                except Exception:
                    pass  # that topic simply won't render — others are unaffected

            if fut_misc is not None:
                try:
                    visual_payload.update(fut_misc.result(timeout=45))
                except Exception:
                    pass

            relevance_map = {}
            if fut_relevance is not None:
                try:
                    relevance_map = fut_relevance.result(timeout=45)
                except Exception:
                    pass  # relevance is a nice-to-have — silently skip on failure

            audio_bytes = tts_future.result() if tts_future is not None else None

        payload = {**visual_payload, **script_payload}

        audio_b64   = None
        listen_time = ""
        if audio_bytes:
            audio_b64   = base64.b64encode(audio_bytes).decode()
            listen_time = word_count_to_minutes(tts_text)

        slot.markdown(render_loader(4), unsafe_allow_html=True)

        st.session_state.last_result = {
            "payload":     payload,
            "topics":      chosen_topics,
            "city":        city,
            "voice":       voice_choice,
            "lang":        lang_display,
            "quote":       live_quote,
            "word":        live_word,
            "weather":     weather_data,
            "markets":     markets_data,
            "on_this_day": on_this_day,
            "relevance_map": relevance_map,
            "india_live":  live_news["india"],
            "global_live": live_news["global"],
            "tech_live":   live_news["tech"],
            "sports_live": live_news["sports"],
            "audio_b64":   audio_b64,
            "listen_time": listen_time,
            "gen_date":    datetime.now().strftime("%b %d, %Y"),
            "fresh":       True,
        }

        st.session_state.history.insert(0, {
            "date":      datetime.now().strftime("%b %d, %Y · %I:%M %p"),
            "city":      city,
            "lang":      lang_display,
            "voice":     voice_choice,
            "topics":    chosen_topics,
            "audio_b64": audio_b64,
        })
        st.session_state.history = st.session_state.history[:7]

        slot.empty()
        st.balloons()

    except Exception as e:
        slot.empty()
        st.error(f"⚠️ Something went wrong — please try again. Detail: {e}")

# ═══════════════════════════════════════════════════
# RENDER STORED RESULT — survives every rerun
# ═══════════════════════════════════════════════════
if st.session_state.last_result:
    render_result(st.session_state.last_result)
    st.session_state.last_result["fresh"] = False

# ═══════════════════════════════════════════════════
# HISTORY
# ═══════════════════════════════════════════════════
if st.session_state.history:
    sep()
    with st.expander("🕘 Past Briefs — click to replay", expanded=False):
        for idx, entry in enumerate(st.session_state.history):
            topics_str = " · ".join(f"{TOPIC_ICONS.get(t,'')} {t}" for t in entry.get("topics", []))
            st.markdown(
                f'<div class="hist-item"><div>'
                f'<div class="hist-date">{entry["date"]}</div>'
                f'<div class="hist-meta">🌆 {entry["city"]} · {entry["voice"]} · {topics_str}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
            if entry.get("audio_b64"):
                st.audio(base64.b64decode(entry["audio_b64"]), format="audio/mp3")
            else:
                st.caption("📄 Text-only brief (audio was skipped)")