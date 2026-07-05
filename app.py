import streamlit as st
import json
import io
import time
import base64
import requests
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
# PAGE CONFIG
# ═══════════════════════════════════════════════════
st.set_page_config(
    page_title="SatiCast",
    page_icon="🪷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════
def init_state():
    defaults = {
        "dark_mode":   False,
        "history":     [],
        "last_result": None,   # generated brief lives here — survives theme toggles & reruns
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

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
    "hi": (
        "Write the spoken_script ENTIRELY in fluent Hindi (Devanagari). "
        "All visual fields must also be in Hindi/Devanagari."
    ),
    "mr": (
        "Write the spoken_script ENTIRELY in fluent Marathi (Devanagari). "
        "All visual fields must also be in Marathi/Devanagari."
    ),
}

# Learning Byte topics — rotates by day-of-year so it changes EVERY day
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
    """Fetch real headlines from NewsAPI — supports india / global / tech / sports."""
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
        else:  # india
            url = f"{base}?country=in&pageSize={page_size}&apiKey={NEWS_API_KEY}"
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            articles = r.json().get("articles", [])
            # Sports in-country can be sparse — fall back to global sports
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
def fetch_markets() -> dict:
    if not YFINANCE_OK:
        return {}
    result = {}
    for name, ticker in MARKET_TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                curr = hist["Close"].iloc[-1]
                chg  = ((curr - prev) / prev) * 100
                result[name] = {"price": round(curr, 2), "chg": round(chg, 2), "up": chg >= 0}
        except Exception:
            pass
    return result


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
    idx = datetime.now().timetuple().tm_yday % len(pool)
    e = pool[idx]
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
    day_idx = datetime.now().timetuple().tm_yday % len(daily_words)
    word    = daily_words[day_idx]
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
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════
def build_system_prompt(lang_code, topics, weather_ctx, news_ctx, learning_topic):
    lang_note = LANG_INSTRUCTION.get(lang_code, LANG_INSTRUCTION["en"])
    section_keys = {}
    if "National" in topics:
        section_keys['"india_news"'] = '[{"headline":"…","detail":"…","source":"…"}]'
    if "Global" in topics:
        section_keys['"global_news"'] = '[{"headline":"…","detail":"…","source":"…"}]'
    if "Tech" in topics:
        section_keys['"tech_news"'] = '[{"headline":"…","detail":"…","source":"…"}]'
    if "Sports" in topics:
        section_keys['"sports_flash"'] = '[{"headline":"…","detail":"…","source":"…"}]'
    if "Learning" in topics:
        section_keys['"learning_byte"'] = '{"topic":"…","insight":"…","tip":"…"}'
    sections_json = ",\n  ".join(f'{k}: {v}' for k, v in section_keys.items())

    weather_block  = f"\nLIVE WEATHER DATA (use this, do not invent):\n{weather_ctx}" if weather_ctx else ""
    news_block     = f"\nLIVE NEWS HEADLINES (use these as basis; keep the source names):\n{news_ctx}" if news_ctx else ""
    learning_block = (
        f'\nTODAY\'S LEARNING TOPIC (mandatory — the learning_byte MUST be about exactly this topic): "{learning_topic}"'
        if "Learning" in topics else ""
    )

    return f"""
You are the voice of SatiCast — a mindful, premium AI radio host.
Generate a complete daily briefing as a valid JSON object.

LANGUAGE RULE: {lang_note}
{weather_block}
{news_block}
{learning_block}

STRICT RULES:
- spoken_script must be continuous natural prose — no bullets, no symbols.
- Keep the spoken_script concise: under 350 words.
- If live weather/news data is provided above, USE IT — including the source names. Do not fabricate.
- Return ONLY valid JSON — no markdown fences, no preamble.
- Provide exactly 5 items for every news array requested.
- Do NOT address the listener by any personal name.

Return a JSON object with EXACTLY these keys:
{{
  "greeting": "Warm generic welcome — no personal name.",
  "weather_summary": "One vivid sentence describing today's weather.",
  {sections_json},
  "spoken_script": "Complete TTS-ready narrative in the chosen language. Do NOT include a quote or word-of-the-day segment — those are handled separately."
}}
"""


# ═══════════════════════════════════════════════════
# LOADER
# ═══════════════════════════════════════════════════
LOADER_STAGES = [
    ("🌸", "Waking up your morning brief…",   "Initialising SatiCast"),
    ("📡", "Fetching live data…",             "Weather · News · Markets"),
    ("🧠", "Crafting personalised insights…", "Calling AI engine"),
    ("🎵", "Generating voice audio…",         "Rendering speech"),
    ("✨", "Polishing your digest…",          "Final quality pass"),
]

def render_loader(stage_idx: int, dark: bool) -> str:
    total = len(LOADER_STAGES)
    emoji, title, sub = LOADER_STAGES[stage_idx]
    pct = int((stage_idx + 1) / total * 100)
    bg = "rgba(15,10,30,0.92)" if dark else "rgba(255,255,255,0.95)"
    tc = "#DDD6FE" if dark else "#1e1b4b"
    sc = "#A78BFA" if dark else "#6d28d9"
    dots = "".join([
        f'<div class="ld {"ldone" if i < stage_idx else ("lactive" if i == stage_idx else "")}"></div>'
        for i in range(total)
    ])
    return (
        f'<div class="loader-wrap" style="background:{bg};">'
        f'<div class="loader-emoji">{emoji}</div>'
        f'<div class="loader-title" style="color:{tc};">{title}</div>'
        f'<div class="loader-sub" style="color:{sc};">{sub} &nbsp;·&nbsp; {stage_idx+1}/{total}</div>'
        f'<div class="loader-dots">{dots}</div>'
        f'<div class="loader-bar-bg"><div class="loader-bar-fg" style="width:{pct}%"></div></div>'
        f'<div class="loader-pct" style="color:{sc};">{pct}%</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════
# CSS — static block + dynamic :root (no f-string brace pain)
# ═══════════════════════════════════════════════════
STATIC_CSS = """
h1,h2,h3,h4,h5,h6,[data-testid] h1,[data-testid] h2,[data-testid] h3 {
    color: var(--text-main) !important;
    -webkit-text-fill-color: var(--text-main) !important;
}
html,body,[class*="css"] {
    font-family:'Inter',sans-serif !important;
    background-color: var(--bg-base) !important;
    color: var(--text-main) !important;
}
.stApp { background: var(--bg-grad) !important; min-height:100vh; }
.main .block-container { max-width:740px; padding-top:0 !important; padding-bottom:6rem; }
#MainMenu,footer,header { visibility:hidden; }
* { box-sizing:border-box; }

.sati-bg { position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden; }
.orb { position:absolute;border-radius:50%;filter:blur(72px);opacity:0.28;animation:drift 14s ease-in-out infinite alternate; }
.orb1 { width:420px;height:420px;background:#C4B5FD;top:-100px;left:-120px; }
.orb2 { width:360px;height:360px;background:#FBCFE8;top:220px;right:-100px;animation-delay:4s; }
.orb3 { width:300px;height:300px;background:#BAE6FD;bottom:120px;left:50px;animation-delay:7s; }
.orb4 { width:240px;height:240px;background:#BBF7D0;bottom:-50px;right:70px;animation-delay:2s; }
@keyframes drift { 0%{transform:translate(0,0) scale(1)} 100%{transform:translate(28px,18px) scale(1.07)} }

.sati-masthead { position:relative;z-index:1;padding:3rem 0 1.5rem;text-align:center; }
.sati-lotus { font-size:2.6rem;display:block;margin-bottom:0.5rem;animation:floatLotus 3.2s ease-in-out infinite; }
@keyframes floatLotus { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)} }
.sati-wordmark {
    font-family:'Syne',sans-serif;font-size:4rem;font-weight:800;
    letter-spacing:-3px;line-height:1;
    background:linear-gradient(135deg,#6D28D9 0%,#BE185D 55%,#0369A1 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
    margin:0 0 0.3rem;animation:fadeSlideDown 0.8s ease both;
}
.sati-tagline { font-size:0.76rem;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#6D28D9;opacity:0.75;animation:fadeSlideDown 0.9s 0.1s ease both; }
.sati-meaning { margin-top:0.5rem;font-size:0.84rem;color:#5B21B6;font-style:italic;font-weight:500;animation:fadeSlideDown 0.95s 0.15s ease both; }

.waveform-wrap { display:flex;align-items:center;justify-content:center;gap:4px;height:40px;margin:1.2rem auto 0;animation:fadeSlideDown 1s 0.2s ease both; }
.bar { width:3px;border-radius:99px;background:linear-gradient(to top,#6D28D9,#DB2777,#0EA5E9);animation:wave 1.3s ease-in-out infinite;transform-origin:center; }
.bar:nth-child(1){height:10px;animation-delay:0.00s}
.bar:nth-child(2){height:20px;animation-delay:0.08s}
.bar:nth-child(3){height:32px;animation-delay:0.16s}
.bar:nth-child(4){height:26px;animation-delay:0.24s}
.bar:nth-child(5){height:40px;animation-delay:0.12s}
.bar:nth-child(6){height:34px;animation-delay:0.20s}
.bar:nth-child(7){height:40px;animation-delay:0.04s}
.bar:nth-child(8){height:36px;animation-delay:0.28s}
.bar:nth-child(9){height:28px;animation-delay:0.08s}
.bar:nth-child(10){height:18px;animation-delay:0.16s}
.bar:nth-child(11){height:12px;animation-delay:0.24s}
.bar:nth-child(12){height:24px;animation-delay:0.00s}
.bar:nth-child(13){height:38px;animation-delay:0.12s}
.bar:nth-child(14){height:30px;animation-delay:0.20s}
.bar:nth-child(15){height:16px;animation-delay:0.04s}
.bar:nth-child(16){height:8px;animation-delay:0.28s}
@keyframes wave { 0%,100%{transform:scaleY(0.35);opacity:0.45} 50%{transform:scaleY(1.0);opacity:1.0} }

div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stMultiSelect"] label {
    color:#5B21B6 !important;font-size:0.74rem !important;
    font-weight:700 !important;letter-spacing:0.08em !important;text-transform:uppercase !important;
}
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stMultiSelect"] > div > div {
    background:var(--input-bg) !important;border:1.5px solid var(--input-bdr) !important;
    border-radius:12px !important;color:var(--input-txt) !important;font-weight:500 !important;
    backdrop-filter:blur(8px) !important;
}
div[data-testid="stTextInput"] input {
    background:var(--input-bg) !important;border:1.5px solid var(--input-bdr) !important;
    border-radius:12px !important;color:var(--input-txt) !important;font-weight:500 !important;
    backdrop-filter:blur(8px) !important;padding:0.55rem 0.9rem !important;
}
div[data-testid="stTextInput"] input::placeholder { color:#9CA3AF !important; }
div[data-testid="stTextInput"] input:focus {
    border-color:rgba(109,40,217,0.6) !important;
    box-shadow:0 0 0 3px rgba(109,40,217,0.1) !important;outline:none !important;
}
span[data-baseweb="tag"] { background:linear-gradient(135deg,#6D28D9,#BE185D) !important;color:#fff !important;border-radius:8px !important; }

div[data-testid="stToggle"] label p, .stCheckbox label p { color: var(--text-main) !important; font-weight:600 !important; }

.stButton > button {
    display:block !important;margin:1.5rem auto 0 !important;
    background:linear-gradient(135deg,#6D28D9 0%,#BE185D 100%) !important;
    border:none !important;color:#FFFFFF !important;
    border-radius:999px !important;padding:0.85rem 3.5rem !important;
    font-size:0.95rem !important;font-weight:700 !important;
    letter-spacing:0.08em !important;text-transform:uppercase !important;
    transition:all 0.25s ease !important;
    box-shadow:0 8px 28px rgba(109,40,217,0.32) !important;
    position:relative;z-index:2;
}
.stButton > button:hover { box-shadow:0 12px 38px rgba(109,40,217,0.48) !important;transform:translateY(-3px) scale(1.03) !important; }
.stButton > button:active { transform:scale(0.97) !important; }

details summary { color:var(--text-main) !important;font-weight:600 !important; }
details { background:var(--card-bg) !important;border-radius:16px !important;border:1.5px solid var(--card-bdr) !important;padding:0.5rem 1rem !important;margin-bottom:1rem !important; }

@keyframes loaderBounce { 0%,100%{transform:translateY(0) scale(1)} 40%{transform:translateY(-12px) scale(1.12)} 65%{transform:translateY(-6px) scale(1.06)} }
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
@keyframes dotPop { from{transform:scale(0.3);opacity:0} to{transform:scale(1);opacity:1} }
@keyframes loaderFadeIn { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
.loader-wrap { border-radius:24px;padding:3rem 2.5rem;text-align:center;max-width:520px;margin:2rem auto;box-shadow:0 24px 60px rgba(0,0,0,0.2);animation:loaderFadeIn 0.4s ease both;border:1.5px solid rgba(139,92,246,0.2); }
.loader-emoji { font-size:3rem;display:block;margin-bottom:0.85rem;animation:loaderBounce 1.3s ease-in-out infinite; }
.loader-title { font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:800;margin-bottom:0.3rem; }
.loader-sub { font-size:0.82rem;font-weight:600;margin-bottom:1.5rem; }
.loader-dots { display:flex;justify-content:center;gap:9px;margin-bottom:1.4rem; }
.ld { width:10px;height:10px;border-radius:50%;background:#E5E7EB;transition:background 0.3s; }
.lactive { background:linear-gradient(135deg,#6D28D9,#BE185D);animation:dotPop 0.4s ease both;box-shadow:0 0 8px rgba(109,40,217,0.4); }
.ldone { background:#6D28D9; }
.loader-bar-bg { height:6px;border-radius:99px;background:rgba(109,40,217,0.12);overflow:hidden;margin-bottom:0.5rem; }
.loader-bar-fg { height:100%;border-radius:99px;background:linear-gradient(90deg,#6D28D9,#BE185D,#0EA5E9,#6D28D9);background-size:200% 100%;animation:shimmer 1.8s linear infinite;transition:width 0.5s ease; }
.loader-pct { font-size:0.78rem;font-weight:800;letter-spacing:0.06em; }

.weather-widget {
    background:var(--weather-bg);border:1.5px solid rgba(14,165,233,0.25);
    border-radius:20px;padding:1.25rem 1.5rem;margin-bottom:1.5rem;
    position:relative;z-index:2;box-shadow:0 4px 20px rgba(14,165,233,0.1);
    display:grid;grid-template-columns:auto 1fr auto;gap:0.5rem 1.2rem;align-items:center;
}
.weather-icon { font-size:2.8rem;line-height:1; }
.weather-temp { font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;color:var(--weather-tc); }
.weather-desc { font-size:0.88rem;font-weight:600;color:var(--weather-tc);opacity:0.85; }
.weather-meta { font-size:0.78rem;color:var(--weather-tc);opacity:0.7;margin-top:0.2rem; }
.weather-feels { font-size:0.85rem;font-weight:600;color:var(--weather-tc);text-align:right; }

.market-strip { display:flex;gap:10px;flex-wrap:wrap;margin-bottom:2rem;position:relative;z-index:2; }
.market-chip { background:var(--card-bg);border:1.5px solid var(--card-bdr);border-radius:12px;padding:0.5rem 0.9rem;backdrop-filter:blur(8px);min-width:110px; }
.market-name { font-size:0.65rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-muted); }
.market-price { font-family:'Syne',sans-serif;font-size:0.95rem;font-weight:800;color:var(--text-main); }
.market-chg-up { font-size:0.75rem;font-weight:700;color:#10B981; }
.market-chg-down { font-size:0.75rem;font-weight:700;color:#EF4444; }

.audio-shell {
    position:relative;z-index:2;
    background:linear-gradient(135deg,rgba(109,40,217,0.09),rgba(190,24,93,0.06));
    border:1.5px solid rgba(109,40,217,0.2);border-radius:20px;
    padding:1.5rem 1.75rem 1.2rem;margin:2rem 0 0.5rem;
    backdrop-filter:blur(14px);box-shadow:0 8px 32px rgba(109,40,217,0.09);
    animation:cardReveal 0.6s ease both;
}
.audio-pill { display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#6D28D9,#BE185D);color:#FFFFFF;font-size:0.62rem;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;padding:0.25rem 0.85rem;border-radius:999px;margin-bottom:0.6rem; }
.audio-title { font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:800;color:var(--text-main);margin-bottom:0.4rem; }
.audio-meta { font-size:0.76rem;color:#6D28D9;font-weight:600; }
.listen-badge { display:inline-flex;align-items:center;gap:5px;background:rgba(109,40,217,0.1);border:1px solid rgba(109,40,217,0.2);border-radius:999px;padding:0.25rem 0.75rem;font-size:0.75rem;font-weight:700;color:#6D28D9;margin-top:0.5rem; }

.dl-wrap { margin:0.75rem 0 1rem;position:relative;z-index:2; }
.dl-wrap a { display:inline-flex;align-items:center;gap:6px;background:rgba(109,40,217,0.08);border:1.5px solid rgba(109,40,217,0.2);border-radius:999px;padding:0.4rem 1.1rem;font-size:0.78rem;font-weight:700;color:#6D28D9;text-decoration:none;transition:all 0.2s; }
.dl-wrap a:hover { background:rgba(109,40,217,0.15); }

.sati-section { position:relative;z-index:2;margin-bottom:2.5rem;animation:cardReveal 0.6s ease both; }
.section-header { display:flex;align-items:center;gap:10px;margin-bottom:1rem; }
.section-badge { width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0; }
.badge-india { background:linear-gradient(135deg,#FEF3C7,#FDE68A); }
.badge-global { background:linear-gradient(135deg,#DBEAFE,#BFDBFE); }
.badge-tech { background:linear-gradient(135deg,#D1FAE5,#A7F3D0); }
.badge-focus { background:linear-gradient(135deg,#EDE9FE,#DDD6FE); }
.badge-word { background:linear-gradient(135deg,#FFE4E6,#FECDD3); }
.badge-sports { background:linear-gradient(135deg,#FEF9C3,#FDE047); }
.badge-learn { background:linear-gradient(135deg,#ECFDF5,#A7F3D0); }

.section-title { font-family:'Syne',sans-serif !important;font-size:1.35rem !important;font-weight:800 !important;color:var(--text-main) !important;letter-spacing:-0.4px !important;margin:0 !important;-webkit-text-fill-color:var(--text-main) !important; }

.greeting-card { background:var(--greet-bg);border:1.5px solid rgba(109,40,217,0.18);border-radius:16px;padding:1.2rem 1.5rem;margin-bottom:1.25rem;color:var(--text-sub);font-size:1.02rem;line-height:1.7;position:relative;z-index:2;animation:cardReveal 0.5s ease both;box-shadow:0 4px 20px rgba(109,40,217,0.07); }
.weather-pill { display:inline-flex;align-items:center;gap:6px;background:var(--weather-bg);border:1.5px solid rgba(3,105,161,0.25);border-radius:999px;padding:0.4rem 1.1rem;font-size:0.85rem;color:var(--weather-tc);margin-bottom:1.5rem;font-weight:600;position:relative;z-index:2; }

.news-group { background:var(--news-bg);border:1.5px solid var(--news-bdr);border-radius:18px;padding:0.5rem 1.25rem 0.25rem;backdrop-filter:blur(12px);box-shadow:0 4px 24px rgba(0,0,0,0.05); }
.news-item { display:flex;gap:14px;padding:1rem 0;border-bottom:1px solid var(--news-bdr); }
.news-item:last-child { border-bottom:none; }
.news-index { font-family:'Syne',sans-serif;font-size:1rem;font-weight:800;min-width:26px;padding-top:2px;line-height:1; }
.idx-india { color:#B45309; }
.idx-global { color:#1D4ED8; }
.idx-tech { color:#047857; }
.idx-sports { color:#D97706; }
.news-headline { font-weight:700;font-size:0.93rem;color:var(--news-hl);line-height:1.4;margin-bottom:0.2rem; }
.news-detail { font-size:0.84rem;color:var(--news-dt);line-height:1.6; }
.news-source { display:inline-block;font-size:0.68rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#7C3AED;margin-top:0.25rem;background:rgba(124,58,237,0.08);border-radius:4px;padding:0.1rem 0.4rem; }

.focus-card { background:var(--focus-bg);border:1.5px solid rgba(109,40,217,0.2);border-left:4px solid #6D28D9;border-radius:0 16px 16px 0;padding:1.5rem 1.5rem 1.5rem 1.75rem;box-shadow:0 4px 20px rgba(109,40,217,0.07); }
.focus-quote { font-family:'Syne',sans-serif;font-size:1.08rem;font-weight:700;color:var(--text-main);line-height:1.6;margin-bottom:0.5rem;font-style:italic; }
.focus-author { font-size:0.78rem;font-weight:700;color:#7C3AED;margin-bottom:0.5rem; }

.word-card { background:var(--word-bg);border:1.5px solid rgba(190,24,93,0.15);border-radius:16px;padding:1.5rem;box-shadow:0 4px 20px rgba(190,24,93,0.05);backdrop-filter:blur(8px); }
.word-main { font-family:'Syne',sans-serif;font-size:1.5rem;font-weight:800;background:linear-gradient(135deg,#BE185D,#6D28D9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;border-bottom:1px solid rgba(190,24,93,0.12);padding-bottom:0.75rem;margin-bottom:0.9rem; }
.word-pos { display:inline-block;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#7C3AED;background:rgba(124,58,237,0.08);border-radius:6px;padding:0.1rem 0.5rem;margin-left:0.5rem;-webkit-text-fill-color:#7C3AED; }
.word-label { font-size:0.68rem;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#BE185D;margin-top:0.7rem; }
.word-val { font-size:0.88rem;color:var(--word-val);line-height:1.6;margin-top:0.2rem; }
.word-val em { color:#5B21B6;font-style:italic; }

.learn-card { background:var(--card-bg);border:1.5px solid rgba(16,185,129,0.2);border-left:4px solid #10B981;border-radius:0 16px 16px 0;padding:1.4rem 1.5rem 1.4rem 1.75rem;box-shadow:0 4px 20px rgba(16,185,129,0.07); }
.learn-topic { font-family:'Syne',sans-serif;font-size:1rem;font-weight:800;color:#047857;margin-bottom:0.5rem; }
.learn-insight { font-size:0.92rem;color:var(--text-sub);line-height:1.7;margin-bottom:0.5rem; }
.learn-tip { font-size:0.82rem;font-weight:600;color:#065F46;background:rgba(16,185,129,0.08);border-radius:8px;padding:0.5rem 0.75rem;border-left:3px solid #10B981; }
.learn-daily-note { font-size:0.72rem;font-weight:600;color:#059669;opacity:0.75;margin-top:0.6rem;font-style:italic; }

.hist-item { background:var(--card-bg);border:1.5px solid var(--card-bdr);border-radius:14px;padding:1rem 1.25rem;margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center;backdrop-filter:blur(8px); }
.hist-date { font-family:'Syne',sans-serif;font-size:0.9rem;font-weight:800;color:var(--text-main); }
.hist-meta { font-size:0.75rem;color:var(--text-muted);margin-top:0.2rem; }

.live-source-badge { display:inline-flex;align-items:center;gap:4px;background:rgba(109,40,217,0.08);border:1px solid rgba(109,40,217,0.2);border-radius:999px;padding:0.2rem 0.7rem;font-size:0.68rem;font-weight:700;color:#6D28D9;text-decoration:none;letter-spacing:0.04em;margin-left:auto;transition:background 0.2s; }
.live-source-badge:hover { background:rgba(109,40,217,0.15); }
.focus-live-note { font-size:0.72rem;font-weight:600;color:#7C3AED;opacity:0.7;margin-top:0.75rem;display:block;font-style:italic; }

.sati-sep { display:flex;align-items:center;gap:12px;margin:2rem 0;opacity:0.2;position:relative;z-index:2; }
.sati-sep::before,.sati-sep::after { content:'';flex:1;height:1px;background:linear-gradient(to right,transparent,var(--sep-color),transparent); }
.sati-sep-dot { width:5px;height:5px;border-radius:50%;background:var(--sep-color); }

.sati-footer { text-align:center;margin-top:4rem;padding-bottom:2rem;position:relative;z-index:2; }
.sati-footer p { font-size:0.7rem;color:var(--footer-c);letter-spacing:0.12em;text-transform:uppercase;font-weight:600; }

.d1{animation-delay:0.05s}.d2{animation-delay:0.12s}.d3{animation-delay:0.19s}
.d4{animation-delay:0.26s}.d5{animation-delay:0.33s}.d6{animation-delay:0.40s}

@keyframes fadeSlideDown { from{opacity:0;transform:translateY(-16px)} to{opacity:1;transform:translateY(0)} }
@keyframes cardReveal { from{opacity:0;transform:translateY(22px)} to{opacity:1;transform:translateY(0)} }
"""

def inject_css(dark: bool):
    if dark:
        root = """
        --bg-base:#080C14; --bg-grad:linear-gradient(160deg,#0F0A2A 0%,#0A1628 40%,#150A20 70%,#0A1A14 100%);
        --text-main:#E2E8F0; --text-sub:#94A3B8; --text-muted:#475569;
        --card-bg:rgba(15,23,42,0.8); --card-bdr:rgba(139,92,246,0.2);
        --input-bg:rgba(15,23,42,0.9); --input-bdr:rgba(139,92,246,0.35); --input-txt:#DDD6FE;
        --sep-color:#6D28D9; --news-bg:rgba(15,23,42,0.7); --news-bdr:rgba(255,255,255,0.06);
        --news-hl:#E2E8F0; --news-dt:#64748B; --focus-bg:rgba(109,40,217,0.12);
        --word-bg:rgba(15,23,42,0.7); --word-val:#CBD5E1;
        --greet-bg:linear-gradient(135deg,rgba(79,50,180,0.3),rgba(168,85,247,0.15));
        --weather-bg:linear-gradient(135deg,rgba(14,116,144,0.25),rgba(8,145,178,0.15));
        --weather-tc:#7DD3FC; --footer-c:#8B5CF6;
        """
    else:
        root = """
        --bg-base:#F5F0FF; --bg-grad:linear-gradient(160deg,#EDE8FF 0%,#E8F4FF 38%,#FFE8F5 68%,#E8FFF2 100%);
        --text-main:#1E1535; --text-sub:#374151; --text-muted:#6B7280;
        --card-bg:rgba(255,255,255,0.75); --card-bdr:rgba(109,40,217,0.15);
        --input-bg:rgba(255,255,255,0.8); --input-bdr:rgba(109,40,217,0.28); --input-txt:#2E1065;
        --sep-color:#6D28D9; --news-bg:rgba(255,255,255,0.7); --news-bdr:rgba(0,0,0,0.07);
        --news-hl:#1E1535; --news-dt:#4B5563;
        --focus-bg:linear-gradient(135deg,rgba(237,233,254,0.75),rgba(245,208,254,0.55));
        --word-bg:rgba(255,255,255,0.75); --word-val:#1F2937;
        --greet-bg:linear-gradient(135deg,rgba(237,233,254,0.85),rgba(252,231,243,0.65));
        --weather-bg:linear-gradient(135deg,#E0F2FE,#BAE6FD);
        --weather-tc:#0C4A6E; --footer-c:#6D28D9;
        """
    css = (
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@300;400;500;600;700&display=swap');"
        ":root{" + root + "}"
        + STATIC_CSS +
        "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)


def sep():
    st.markdown(
        '<div class="sati-sep"><div class="sati-sep-dot"></div>'
        '<div class="sati-sep-dot"></div><div class="sati-sep-dot"></div></div>',
        unsafe_allow_html=True
    )


def news_section(title, badge_cls, idx_cls, icon, items, delay_cls):
    """Render one news section — HTML is single-line to avoid markdown code-block parsing."""
    st.markdown(
        f'<div class="sati-section {delay_cls}">'
        f'<div class="section-header">'
        f'<div class="section-badge {badge_cls}">{icon}</div>'
        f'<h2 class="section-title">{title}</h2>'
        f'</div>',
        unsafe_allow_html=True
    )
    rows = ""
    for i, item in enumerate(items, 1):
        src = item.get("source", "")
        src_html = f'<span class="news-source">{src}</span>' if src else ""
        url = item.get("url", "")
        hl_text = item.get("headline", "")
        hl = (f'<a href="{url}" target="_blank" style="color:inherit;text-decoration:none;">{hl_text}</a>'
              if url else hl_text)
        rows += (
            f'<div class="news-item">'
            f'<div class="news-index {idx_cls}">0{i}</div>'
            f'<div><div class="news-headline">{hl}</div>'
            f'<div class="news-detail">{item.get("detail","")}</div>'
            f'{src_html}</div></div>'
        )
    st.markdown(f'<div class="news-group">{rows}</div></div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════
# RENDER — draws entirely from a stored result dict.
# Runs on EVERY rerun, so theme toggles never lose the brief.
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

    # ── AUDIO PLAYER (only if audio was generated) ──
    if audio_b64:
        st.markdown(
            f'<div class="audio-shell">'
            f'<div class="audio-pill">▶ Now Playing</div>'
            f'<div class="audio-title">Your Mindful Morning Brief &nbsp;·&nbsp; {gen_date}</div>'
            f'<div class="audio-meta">{voice_choice} &nbsp;·&nbsp; {lang_display} &nbsp;·&nbsp; 🌆 {city}</div>'
            f'<div class="listen-badge">🎧 {listen_time}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        audio_bytes = base64.b64decode(audio_b64)
        st.audio(audio_bytes, format="audio/mp3", autoplay=res.get("fresh", False))
        st.markdown(
            f'<div class="dl-wrap"><a href="data:audio/mp3;base64,{audio_b64}" '
            f'download="saticast_{datetime.now().strftime("%Y%m%d")}.mp3">⬇️ Download MP3</a></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="audio-shell">'
            f'<div class="audio-pill">📄 Text Brief</div>'
            f'<div class="audio-title">Your Mindful Morning Brief &nbsp;·&nbsp; {gen_date}</div>'
            f'<div class="audio-meta">{lang_display} &nbsp;·&nbsp; 🌆 {city} &nbsp;·&nbsp; Audio skipped for faster generation</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    sep()

    # ── GREETING ──
    greeting = payload.get("greeting", "Good morning! Welcome to SatiCast.")
    st.markdown(
        f'<div class="sati-section d1"><div class="greeting-card">{greeting}</div></div>',
        unsafe_allow_html=True
    )

    # ── WEATHER ──
    if weather_data:
        wicon = weather_emoji(weather_data.get("icon", ""))
        st.markdown(
            f'<div class="weather-widget">'
            f'<div class="weather-icon">{wicon}</div>'
            f'<div><div class="weather-temp">{weather_data["temp"]}°C</div>'
            f'<div class="weather-desc">{weather_data["desc"]}</div>'
            f'<div class="weather-meta">💧 {weather_data["humidity"]}% humidity &nbsp;·&nbsp; 💨 {weather_data["wind"]} km/h</div></div>'
            f'<div><div class="weather-feels">Feels like</div>'
            f'<div class="weather-temp" style="font-size:1.4rem">{weather_data["feels"]}°C</div></div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        ws = payload.get("weather_summary", "")
        if ws:
            st.markdown(
                f'<div class="sati-section d1"><div class="weather-pill">🌤 {ws}</div></div>',
                unsafe_allow_html=True
            )

    # ── MARKET PULSE ──
    if "Market" in topics and markets_data:
        sep()
        st.markdown(
            '<div class="sati-section d2"><div class="section-header">'
            '<div class="section-badge badge-sports">📈</div>'
            '<h2 class="section-title">Market Pulse</h2></div></div>',
            unsafe_allow_html=True
        )
        chips = ""
        for name, md in markets_data.items():
            cls = "market-chg-up" if md["up"] else "market-chg-down"
            arrow = "▲" if md["up"] else "▼"
            chips += (
                f'<div class="market-chip"><div class="market-name">{name}</div>'
                f'<div class="market-price">{md["price"]:,.1f}</div>'
                f'<div class="{cls}">{arrow} {abs(md["chg"])}%</div></div>'
            )
        st.markdown(f'<div class="market-strip">{chips}</div>', unsafe_allow_html=True)

    # ── NEWS SECTIONS ──
    if "National" in topics:
        sep()
        news_section("National Intel", "badge-india", "idx-india", "🇮🇳",
                     payload.get("india_news", res.get("india_live") or []), "d2")
    if "Global" in topics:
        sep()
        news_section("Global Overview", "badge-global", "idx-global", "🌐",
                     payload.get("global_news", res.get("global_live") or []), "d3")
    if "Tech" in topics:
        sep()
        news_section("Tech & Architecture", "badge-tech", "idx-tech", "⚡",
                     payload.get("tech_news", res.get("tech_live") or []), "d4")

    # ── SPORTS FLASH — now with sources (Issue 6) ──
    if "Sports" in topics:
        sports_items = payload.get("sports_flash") or res.get("sports_live") or []
        # Merge sources from live data if the LLM dropped them
        sports_live = res.get("sports_live") or []
        for i, item in enumerate(sports_items):
            if not item.get("source") and i < len(sports_live):
                item["source"] = sports_live[i].get("source", "")
                item["url"]    = sports_live[i].get("url", "")
        if sports_items:
            sep()
            news_section("Sports Flash", "badge-sports", "idx-sports", "🏏",
                         sports_items, "d4")

    # ── LEARNING BYTE — daily topic badge (Issue 3) ──
    if "Learning" in topics and payload.get("learning_byte"):
        sep()
        lb = payload["learning_byte"]
        st.markdown(
            f'<div class="sati-section d5">'
            f'<div class="section-header">'
            f'<div class="section-badge badge-learn">💡</div>'
            f'<h2 class="section-title">Learning Byte</h2>'
            f'<span class="live-source-badge">📅 Topic #{datetime.now().timetuple().tm_yday % len(LEARNING_TOPICS) + 1} of {len(LEARNING_TOPICS)}</span>'
            f'</div>'
            f'<div class="learn-card">'
            f'<div class="learn-topic">{lb.get("topic","")}</div>'
            f'<div class="learn-insight">{lb.get("insight","")}</div>'
            f'<div class="learn-tip">💡 {lb.get("tip","")}</div>'
            f'<div class="learn-daily-note">✦ A new engineering topic every day</div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    # ── MOMENT OF FOCUS ──
    sep()
    if live_quote.get("source_url"):
        q_badge = (f'<a href="{live_quote["source_url"]}" target="_blank" class="live-source-badge">'
                   f'🔗 {live_quote["source"]}</a>')
    else:
        q_badge = f'<span class="live-source-badge">{live_quote.get("source","")}</span>'
    st.markdown(
        f'<div class="sati-section d5">'
        f'<div class="section-header">'
        f'<div class="section-badge badge-focus">🧘</div>'
        f'<h2 class="section-title">Moment of Focus</h2>'
        f'{q_badge}</div>'
        f'<div class="focus-card">'
        f'<div class="focus-quote">"{live_quote.get("quote","")}"</div>'
        f'<div class="focus-author">— {live_quote.get("author","")}</div>'
        f'<span class="focus-live-note">✦ Refreshes daily with a new quote</span>'
        f'</div></div>',
        unsafe_allow_html=True
    )

    # ── DAILY LEXICON — single-line HTML fixes code-block bug (Issue 4) ──
    sep()
    if live_word.get("source_url"):
        w_badge = (f'<a href="{live_word["source_url"]}" target="_blank" class="live-source-badge">'
                   f'🔗 {live_word["source"]}</a>')
    else:
        w_badge = f'<span class="live-source-badge">{live_word.get("source","")}</span>'
    pos_html = f'<span class="word-pos">{live_word.get("pos","")}</span>' if live_word.get("pos") else ""
    example_html = (
        f'<div class="word-label">In Context</div>'
        f'<div class="word-val"><em>"{live_word["example"]}"</em></div>'
    ) if live_word.get("example") else ""
    st.markdown(
        f'<div class="sati-section d6">'
        f'<div class="section-header">'
        f'<div class="section-badge badge-word">📝</div>'
        f'<h2 class="section-title">Daily Lexicon</h2>'
        f'{w_badge}</div>'
        f'<div class="word-card">'
        f'<div class="word-main">{live_word.get("word","")} {pos_html}</div>'
        f'<div class="word-label">Meaning</div>'
        f'<div class="word-val">{live_word.get("definition","")}</div>'
        f'{example_html}'
        f'<span class="focus-live-note">✦ Changes every day</span>'
        f'</div></div>',
        unsafe_allow_html=True
    )

    # ── FOOTER ──
    time_str = f' &nbsp;·&nbsp; {listen_time}' if listen_time else ''
    st.markdown(
        f'<div class="sati-footer"><p>🪷 SatiCast &nbsp;·&nbsp; {datetime.now().strftime("%A, %B %d %Y")}'
        f' &nbsp;·&nbsp; 🌆 {city} &nbsp;·&nbsp; {voice_choice}{time_str}</p></div>',
        unsafe_allow_html=True
    )


# ═══════════════════════════════════════════════════
# PAGE RENDER STARTS
# ═══════════════════════════════════════════════════
dark = st.session_state.dark_mode
inject_css(dark)

st.markdown(
    '<div class="sati-bg"><div class="orb orb1"></div><div class="orb orb2"></div>'
    '<div class="orb orb3"></div><div class="orb orb4"></div></div>',
    unsafe_allow_html=True
)

# Dark mode toggle — only flips CSS; the brief is re-rendered from session state (Issue 1)
dm_col1, dm_col2 = st.columns([8, 1])
with dm_col2:
    if st.button("☀️" if dark else "🌙", key="dm_toggle"):
        st.session_state.dark_mode = not dark
        st.rerun()

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

# ═══════════════════════════════════════════════════
# CONTROLS
# ═══════════════════════════════════════════════════
c1, c2 = st.columns(2)
with c1:
    voice_choice = st.selectbox("🎙 Voice & Accent", options=list(VOICE_OPTIONS.keys()), index=0)
with c2:
    city_input = st.text_input("🌆 City for Weather", value="Mumbai",
                               placeholder="e.g. Nagpur, Delhi, Pune…")

voice_cfg    = VOICE_OPTIONS[voice_choice]
lang_code    = voice_cfg["lang"]
tld_code     = voice_cfg["tld"]
lang_display = LANG_LABEL.get(lang_code, "English")

c3, c4 = st.columns(2)
with c3:
    chosen_topics = st.multiselect(
        "📌 Topics to include",
        options=list(TOPIC_ICONS.keys()),
        default=["National", "Global", "Tech"],
    )
with c4:
    tts_engines = ["gTTS (Free)"]
    if ELEVENLABS_KEY:
        tts_engines += list(ELEVENLABS_VOICES.keys())
    tts_choice = st.selectbox("🔊 TTS Engine", options=tts_engines, index=0)

# Audio toggle (Issue 2) + read-only script language
c5, c6 = st.columns(2)
with c5:
    generate_audio = st.toggle(
        "🎧 Generate Audio",
        value=True,
        help="Turn off to skip voice generation — the brief appears much faster as text only."
    )
with c6:
    st.selectbox("📢 Script Language", options=[lang_display], disabled=True,
                 help="Auto-follows your voice selection")

# ═══════════════════════════════════════════════════
# GENERATE — stores result in session_state, then renders below
# ═══════════════════════════════════════════════════
trigger = st.button("🪷 Generate Morning Brief")

if trigger:
    if not chosen_topics:
        st.warning("⚠️ Please select at least one topic.")
        st.stop()

    city = city_input.strip() or "Mumbai"
    slot = st.empty()

    slot.markdown(render_loader(0, dark), unsafe_allow_html=True)

    # ── PARALLEL FETCH of all live data (Issue 5: much faster) ──
    slot.markdown(render_loader(1, dark), unsafe_allow_html=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {
            "quote":   ex.submit(fetch_quote_of_day),
            "word":    ex.submit(fetch_word_of_day),
            "weather": ex.submit(fetch_weather, city),
        }
        if "Market"   in chosen_topics: futs["markets"] = ex.submit(fetch_markets)
        if "National" in chosen_topics: futs["india"]   = ex.submit(fetch_news, "india")
        if "Global"   in chosen_topics: futs["global"]  = ex.submit(fetch_news, "global")
        if "Tech"     in chosen_topics: futs["tech"]    = ex.submit(fetch_news, "tech")
        if "Sports"   in chosen_topics: futs["sports"]  = ex.submit(fetch_news, "sports")

        def safe(key, default):
            try:
                return futs[key].result(timeout=15) if key in futs else default
            except Exception:
                return default

        live_quote   = safe("quote",   {"quote": "", "author": "", "source": "", "source_url": ""})
        live_word    = safe("word",    {"word": "", "pos": "", "definition": "", "example": "", "source": "", "source_url": ""})
        weather_data = safe("weather", {})
        markets_data = safe("markets", {})
        india_live   = safe("india",   [])
        global_live  = safe("global",  [])
        tech_live    = safe("tech",    [])
        sports_live  = safe("sports",  [])

    def news_ctx(items):
        return "\n".join(
            f"- {i['headline']} (SOURCE: {i.get('source','')}) — {i.get('detail','')}"
            for i in items
        ) if items else ""

    weather_ctx = ""
    if weather_data:
        weather_ctx = (f"{city}: {weather_data['temp']}°C, feels {weather_data['feels']}°C, "
                       f"{weather_data['desc']}, humidity {weather_data['humidity']}%, "
                       f"wind {weather_data['wind']} km/h")

    news_context = ""
    if india_live:  news_context += f"\nINDIA:\n{news_ctx(india_live)}"
    if global_live: news_context += f"\nGLOBAL:\n{news_ctx(global_live)}"
    if tech_live:   news_context += f"\nTECH:\n{news_ctx(tech_live)}"
    if sports_live: news_context += f"\nSPORTS:\n{news_ctx(sports_live)}"

    learning_topic = todays_learning_topic()

    slot.markdown(render_loader(2, dark), unsafe_allow_html=True)

    try:
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        prompt = f"""
Generate today's complete daily briefing for a general listener.
Date: {current_date}
Weather city: {city}
Topics requested: {', '.join(chosen_topics)}
Tech focus: Backend systems, Java/Spring Boot, PostgreSQL, Quantum Computing, AI/LLMs.
Provide exactly 5 items per news section requested, and KEEP the source name for each item in its "source" field.
Do NOT use any personal name in greeting.
Voice: {voice_choice}

TODAY'S QUOTE (weave naturally into the spoken_script):
"{live_quote.get('quote','')}" — {live_quote.get('author','')}

TODAY'S WORD (mention in spoken_script as a vocabulary moment):
Word: {live_word.get('word','')} ({live_word.get('pos','')})
Meaning: {live_word.get('definition','')}
"""
        completion = nim_client.chat.completions.create(
            model="nvidia/llama-3.3-nemotron-super-49b-v1",
            messages=[
                {"role": "system", "content": build_system_prompt(
                    lang_code, chosen_topics, weather_ctx, news_context, learning_topic)},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2500,   # capped for speed (Issue 5)
            response_format={"type": "json_object"}
        )
        payload = json.loads(completion.choices[0].message.content)

        # ── OPTIONAL TTS (Issue 2) ──
        audio_b64   = None
        listen_time = ""
        tts_text    = payload.get("spoken_script", "")

        if generate_audio and tts_text:
            slot.markdown(render_loader(3, dark), unsafe_allow_html=True)
            audio_bytes = None
            if tts_choice != "gTTS (Free)" and ELEVENLABS_KEY:
                audio_bytes = elevenlabs_tts(tts_text, ELEVENLABS_VOICES.get(tts_choice))
            if audio_bytes is None:
                tts_obj = gTTS(text=tts_text, lang=lang_code, tld=tld_code, slow=False)
                fp = io.BytesIO()
                tts_obj.write_to_fp(fp)
                fp.seek(0)
                audio_bytes = fp.read()
            audio_b64   = base64.b64encode(audio_bytes).decode()
            listen_time = word_count_to_minutes(tts_text)

        slot.markdown(render_loader(4, dark), unsafe_allow_html=True)

        # ── STORE RESULT in session state (Issue 1) ──
        result = {
            "payload":     payload,
            "topics":      chosen_topics,
            "city":        city,
            "voice":       voice_choice,
            "lang":        lang_display,
            "quote":       live_quote,
            "word":        live_word,
            "weather":     weather_data,
            "markets":     markets_data,
            "india_live":  india_live,
            "global_live": global_live,
            "tech_live":   tech_live,
            "sports_live": sports_live,
            "audio_b64":   audio_b64,
            "listen_time": listen_time,
            "gen_date":    datetime.now().strftime("%b %d, %Y"),
            "fresh":       True,
        }
        st.session_state.last_result = result

        # History
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

    except Exception as e:
        slot.empty()
        st.error(f"⚠️ Something went wrong — please try again. Detail: {e}")

# ═══════════════════════════════════════════════════
# RENDER THE STORED RESULT — survives theme toggles & reruns
# ═══════════════════════════════════════════════════
if st.session_state.last_result:
    render_result(st.session_state.last_result)
    # After first render, disable autoplay on subsequent reruns
    st.session_state.last_result["fresh"] = False

# ═══════════════════════════════════════════════════
# HISTORY PANEL
# ═══════════════════════════════════════════════════
if st.session_state.history:
    sep()
    with st.expander("🕘 Past Briefs — click to replay", expanded=False):
        for idx, entry in enumerate(st.session_state.history):
            topics_str = " · ".join(f"{TOPIC_ICONS.get(t,'')} {t}" for t in entry.get("topics", []))
            st.markdown(
                f'<div class="hist-item"><div>'
                f'<div class="hist-date">{entry["date"]}</div>'
                f'<div class="hist-meta">🌆 {entry["city"]} &nbsp;·&nbsp; {entry["voice"]} &nbsp;·&nbsp; {topics_str}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
            if entry.get("audio_b64"):
                st.audio(base64.b64decode(entry["audio_b64"]), format="audio/mp3")
                st.markdown(
                    f'<div class="dl-wrap"><a href="data:audio/mp3;base64,{entry["audio_b64"]}" '
                    f'download="saticast_replay_{idx}.mp3">⬇️ Download</a></div>',
                    unsafe_allow_html=True
                )
            else:
                st.caption("📄 Text-only brief (audio was skipped)")