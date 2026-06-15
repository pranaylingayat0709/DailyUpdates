import streamlit as st
import json
from openai import OpenAI
from datetime import datetime
from gtts import gTTS
import io

# ---------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------
st.set_page_config(
    page_title="SatiCast",
    page_icon="🪷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------
# CREDENTIALS VALIDATION
# ---------------------------------------------------
if "NVIDIA_API_KEY" not in st.secrets:
    st.error("🔑 NVIDIA_API_KEY not found in Streamlit secrets.")
    st.stop()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=st.secrets["NVIDIA_API_KEY"]
)

# ---------------------------------------------------
# VOICE / LANGUAGE CONFIG
# ---------------------------------------------------
VOICE_OPTIONS = {
    "🇮🇳 English – Indian accent":     {"lang": "en", "tld": "co.in"},
    "🇺🇸 English – American accent":   {"lang": "en", "tld": "us"},
    "🇦🇺 English – Australian accent": {"lang": "en", "tld": "com.au"},
    "🇮🇳 हिन्दी – Hindi":              {"lang": "hi", "tld": "co.in"},
    "🇮🇳 मराठी – Marathi":             {"lang": "mr", "tld": "co.in"},
}

LANG_INSTRUCTION = {
    "en": "Write the spoken_script in clear, natural English.",
    "hi": "Write the spoken_script entirely in Hindi (Devanagari script). All visual fields (headline, detail, greeting, weather, quote, word, definition, example) should remain in English for on-screen readability, but the spoken_script must be fluent Hindi.",
    "mr": "Write the spoken_script entirely in Marathi (Devanagari script). All visual fields (headline, detail, greeting, weather, quote, word, definition, example) should remain in English for on-screen readability, but the spoken_script must be fluent Marathi.",
}

# ---------------------------------------------------
# FULL PREMIUM CSS — VIBRANT LIGHT THEME
# ---------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@300;400;500;600&display=swap');

/* ── BASE ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: #F5F0FF !important;
    color: #1E1535 !important;
}
.stApp {
    background: linear-gradient(160deg, #F0EAFF 0%, #EBF4FF 40%, #FFF0F8 70%, #F0FFF4 100%) !important;
    min-height: 100vh;
}
.main .block-container {
    max-width: 720px;
    padding-top: 0 !important;
    padding-bottom: 6rem;
}
#MainMenu, footer, header { visibility: hidden; }
* { box-sizing: border-box; }

/* ── ANIMATED GRADIENT BG ORBS ── */
.sati-bg {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
}
.orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(70px);
    opacity: 0.35;
    animation: drift 12s ease-in-out infinite alternate;
}
.orb1 { width:420px; height:420px; background:#C4B5FD; top:-100px; left:-120px; animation-delay:0s; }
.orb2 { width:360px; height:360px; background:#FBCFE8; top:200px; right:-100px; animation-delay:3s; }
.orb3 { width:300px; height:300px; background:#BAE6FD; bottom:100px; left:60px; animation-delay:6s; }
.orb4 { width:250px; height:250px; background:#BBF7D0; bottom:-60px; right:80px; animation-delay:2s; }
@keyframes drift {
    0%   { transform: translate(0,0) scale(1); }
    100% { transform: translate(30px, 20px) scale(1.08); }
}

/* ── MASTHEAD ── */
.sati-masthead {
    position: relative;
    z-index: 1;
    padding: 3.5rem 0 2rem;
    text-align: center;
}
.sati-lotus {
    font-size: 2.5rem;
    display: block;
    margin-bottom: 0.5rem;
    animation: floatLotus 3s ease-in-out infinite;
}
@keyframes floatLotus {
    0%, 100% { transform: translateY(0); }
    50%       { transform: translateY(-6px); }
}
.sati-wordmark {
    font-family: 'Syne', sans-serif;
    font-size: 4.2rem;
    font-weight: 800;
    letter-spacing: -3px;
    line-height: 1;
    background: linear-gradient(135deg, #7C3AED 0%, #DB2777 50%, #0EA5E9 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.3rem;
    animation: fadeSlideDown 0.8s ease both;
}
.sati-tagline {
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: #7C3AED;
    opacity: 0.7;
    animation: fadeSlideDown 0.9s 0.1s ease both;
}
.sati-meaning {
    margin-top: 0.6rem;
    font-size: 0.85rem;
    color: #6D28D9;
    font-style: italic;
    font-weight: 400;
    opacity: 0.85;
    animation: fadeSlideDown 0.95s 0.15s ease both;
}

/* ── WAVEFORM ── */
.waveform-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 44px;
    margin: 1.4rem auto 0;
    animation: fadeSlideDown 1s 0.2s ease both;
}
.bar {
    width: 3px;
    border-radius: 99px;
    background: linear-gradient(to top, #7C3AED, #EC4899, #38BDF8);
    animation: wave 1.3s ease-in-out infinite;
    transform-origin: center;
}
.bar:nth-child(1)  { height:10px; animation-delay:0.00s; }
.bar:nth-child(2)  { height:20px; animation-delay:0.08s; }
.bar:nth-child(3)  { height:32px; animation-delay:0.16s; }
.bar:nth-child(4)  { height:26px; animation-delay:0.24s; }
.bar:nth-child(5)  { height:40px; animation-delay:0.12s; }
.bar:nth-child(6)  { height:34px; animation-delay:0.20s; }
.bar:nth-child(7)  { height:44px; animation-delay:0.04s; }
.bar:nth-child(8)  { height:36px; animation-delay:0.28s; }
.bar:nth-child(9)  { height:28px; animation-delay:0.08s; }
.bar:nth-child(10) { height:18px; animation-delay:0.16s; }
.bar:nth-child(11) { height:12px; animation-delay:0.24s; }
.bar:nth-child(12) { height:24px; animation-delay:0.00s; }
.bar:nth-child(13) { height:38px; animation-delay:0.12s; }
.bar:nth-child(14) { height:30px; animation-delay:0.20s; }
.bar:nth-child(15) { height:16px; animation-delay:0.04s; }
.bar:nth-child(16) { height:8px;  animation-delay:0.28s; }
@keyframes wave {
    0%, 100% { transform: scaleY(0.35); opacity: 0.4; }
    50%       { transform: scaleY(1.0);  opacity: 1.0; }
}

/* ── CONTROLS ROW ── */
.controls-row {
    position: relative;
    z-index: 2;
    display: flex;
    gap: 12px;
    margin: 1.5rem 0 0.5rem;
    flex-wrap: wrap;
}

/* ── SELECT BOXES ── */
div[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.75) !important;
    border: 1.5px solid rgba(124,58,237,0.3) !important;
    border-radius: 12px !important;
    color: #3B0764 !important;
    font-weight: 500 !important;
    backdrop-filter: blur(8px) !important;
}
div[data-testid="stSelectbox"] label {
    color: #6D28D9 !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}

/* ── MAIN BUTTON ── */
.stButton > button {
    display: block !important;
    margin: 1.5rem auto 0 !important;
    background: linear-gradient(135deg, #7C3AED 0%, #DB2777 100%) !important;
    border: none !important;
    color: #FFFFFF !important;
    border-radius: 999px !important;
    padding: 0.85rem 3.5rem !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 8px 30px rgba(124,58,237,0.35), 0 2px 8px rgba(219,39,119,0.2) !important;
    position: relative; z-index: 2;
}
.stButton > button:hover {
    box-shadow: 0 12px 40px rgba(124,58,237,0.5), 0 4px 12px rgba(219,39,119,0.3) !important;
    transform: translateY(-3px) scale(1.03) !important;
}
.stButton > button:active { transform: scale(0.97) !important; }

/* ── AUDIO CARD ── */
.audio-shell {
    position: relative; z-index: 2;
    background: linear-gradient(135deg, rgba(124,58,237,0.1) 0%, rgba(219,39,119,0.07) 100%);
    border: 1.5px solid rgba(124,58,237,0.2);
    border-radius: 20px;
    padding: 1.6rem 1.75rem 1.2rem;
    margin: 2rem 0 1.5rem;
    animation: cardReveal 0.6s ease both;
    backdrop-filter: blur(14px);
    box-shadow: 0 8px 32px rgba(124,58,237,0.1);
}
.audio-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: linear-gradient(135deg, #7C3AED, #DB2777);
    color: #fff;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    padding: 0.25rem 0.8rem;
    border-radius: 999px;
    margin-bottom: 0.65rem;
}
.audio-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    color: #3B0764;
    margin-bottom: 1rem;
}
.audio-accent {
    font-size: 0.78rem;
    color: #7C3AED;
    font-weight: 500;
    margin-bottom: 0.75rem;
}

/* ── SECTION CARDS ── */
.sati-section {
    position: relative; z-index: 2;
    margin-bottom: 2.5rem;
    animation: cardReveal 0.6s ease both;
}
.section-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 1rem;
}
.section-badge {
    width: 34px; height: 34px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; flex-shrink: 0;
}
.badge-india   { background: linear-gradient(135deg, #FEF3C7, #FDE68A); }
.badge-global  { background: linear-gradient(135deg, #DBEAFE, #BFDBFE); }
.badge-tech    { background: linear-gradient(135deg, #D1FAE5, #A7F3D0); }
.badge-focus   { background: linear-gradient(135deg, #EDE9FE, #DDD6FE); }
.badge-word    { background: linear-gradient(135deg, #FFE4E6, #FECDD3); }

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.4rem;
    font-weight: 800;
    color: #1E1535;
    letter-spacing: -0.4px;
    margin: 0;
}

/* ── GREETING CARD ── */
.greeting-card {
    background: linear-gradient(135deg, rgba(237,233,254,0.8), rgba(252,231,243,0.6));
    border: 1.5px solid rgba(124,58,237,0.18);
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.25rem;
    color: #3B0764;
    font-size: 1.05rem;
    line-height: 1.7;
    position: relative; z-index: 2;
    animation: cardReveal 0.5s ease both;
    box-shadow: 0 4px 20px rgba(124,58,237,0.08);
}
.weather-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: linear-gradient(135deg, #E0F2FE, #BAE6FD);
    border: 1.5px solid rgba(14,165,233,0.3);
    border-radius: 999px;
    padding: 0.4rem 1.1rem;
    font-size: 0.85rem;
    color: #0369A1;
    margin-bottom: 2rem;
    font-weight: 600;
    position: relative; z-index: 2;
    box-shadow: 0 2px 8px rgba(14,165,233,0.12);
}

/* ── NEWS CARD GROUP ── */
.news-group {
    background: rgba(255,255,255,0.65);
    border: 1.5px solid rgba(0,0,0,0.06);
    border-radius: 18px;
    padding: 0.5rem 1.25rem 0.25rem;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.06);
}
.news-item {
    display: flex; gap: 14px;
    padding: 1rem 0;
    border-bottom: 1px solid rgba(0,0,0,0.05);
    transition: background 0.2s;
}
.news-item:last-child { border-bottom: none; }
.news-index {
    font-family: 'Syne', sans-serif;
    font-size: 1rem; font-weight: 800;
    min-width: 26px; padding-top: 2px; line-height: 1;
}
.idx-india  { color: #D97706; }
.idx-global { color: #2563EB; }
.idx-tech   { color: #059669; }
.news-headline { font-weight: 600; font-size: 0.95rem; color: #1E1535; line-height: 1.4; margin-bottom: 0.2rem; }
.news-detail   { font-size: 0.86rem; color: #64748B; line-height: 1.6; }

/* ── QUOTE BLOCK ── */
.focus-card {
    background: linear-gradient(135deg, rgba(237,233,254,0.7), rgba(245,208,254,0.5));
    border: 1.5px solid rgba(124,58,237,0.2);
    border-left: 4px solid #7C3AED;
    border-radius: 0 16px 16px 0;
    padding: 1.5rem 1.5rem 1.5rem 1.75rem;
    box-shadow: 0 4px 20px rgba(124,58,237,0.08);
}
.focus-quote {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem; font-weight: 700;
    color: #4C1D95;
    line-height: 1.6; margin-bottom: 0.75rem; font-style: italic;
}
.focus-expl { font-size: 0.9rem; color: #6D28D9; line-height: 1.7; }

/* ── WORD CARD ── */
.word-card {
    background: rgba(255,255,255,0.7);
    border: 1.5px solid rgba(244,63,94,0.15);
    border-radius: 16px;
    padding: 1.5rem;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.6rem 1.2rem;
    align-items: start;
    box-shadow: 0 4px 20px rgba(244,63,94,0.06);
    backdrop-filter: blur(8px);
}
.word-main {
    font-family: 'Syne', sans-serif;
    font-size: 1.6rem; font-weight: 800;
    background: linear-gradient(135deg, #DB2777, #7C3AED);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    grid-column: 1 / -1;
    border-bottom: 1px solid rgba(219,39,119,0.12);
    padding-bottom: 0.75rem; margin-bottom: 0.2rem;
}
.word-label { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: #DB2777; padding-top: 2px; }
.word-val   { font-size: 0.9rem; color: #374151; line-height: 1.6; }
.word-val em { color: #6D28D9; font-style: italic; }

/* ── SEPARATOR ── */
.sati-sep {
    display: flex; align-items: center; gap: 12px;
    margin: 2rem 0; opacity: 0.25; position: relative; z-index: 2;
}
.sati-sep::before, .sati-sep::after {
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(to right, transparent, #7C3AED, transparent);
}
.sati-sep-dot { width: 5px; height: 5px; border-radius: 50%; background: #7C3AED; }

/* ── FOOTER ── */
.sati-footer {
    text-align: center; margin-top: 4rem; padding-bottom: 2rem;
    position: relative; z-index: 2;
}
.sati-footer p {
    font-size: 0.72rem; color: #A78BFA;
    letter-spacing: 0.12em; text-transform: uppercase;
}

/* ── SPINNER ── */
.stSpinner > div { border-top-color: #7C3AED !important; }

/* ── ANIMATIONS ── */
@keyframes fadeSlideDown {
    from { opacity:0; transform: translateY(-16px); }
    to   { opacity:1; transform: translateY(0); }
}
@keyframes cardReveal {
    from { opacity:0; transform: translateY(22px); }
    to   { opacity:1; transform: translateY(0); }
}
.d1 { animation-delay:0.05s; }
.d2 { animation-delay:0.12s; }
.d3 { animation-delay:0.19s; }
.d4 { animation-delay:0.26s; }
.d5 { animation-delay:0.33s; }
.d6 { animation-delay:0.40s; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# SYSTEM PROMPT BUILDER
# ---------------------------------------------------
def build_system_prompt(lang_code):
    lang_note = LANG_INSTRUCTION.get(lang_code, LANG_INSTRUCTION["en"])
    return f"""
You are the voice of SatiCast — a mindful, premium AI radio host. Generate a daily briefing as valid JSON.
{lang_note}

STRICT RULES:
- spoken_script must be continuous natural prose with no symbols, bullets, or hashtags.
- Use smooth transitions between segments.
- Visual fields (headline, detail, greeting, weather, quote, word, definition, example) must always be in English.

Return ONLY a valid JSON object with these exact keys:
{{
  "greeting": "Warm welcoming sentence addressing Pranay personally.",
  "weather": "One-sentence forecast for Mumbai and Nagpur.",
  "india_news": [{{"headline": "Bold Key Phrase", "detail": "One clear sentence."}}],
  "global_news": [{{"headline": "Bold Key Phrase", "detail": "One clear sentence."}}],
  "tech_news": [{{"headline": "Bold Key Phrase", "detail": "One clear sentence."}}],
  "moment_of_focus": {{"quote": "Quote text", "explanation": "Application sentence."}},
  "word_of_day": {{"word": "The word", "definition": "Meaning", "example": "Context sentence"}},
  "spoken_script": "Complete narrative for TTS — all in the chosen language."
}}
"""

# ---------------------------------------------------
# HELPER
# ---------------------------------------------------
def sep():
    st.markdown('<div class="sati-sep"><div class="sati-sep-dot"></div><div class="sati-sep-dot"></div><div class="sati-sep-dot"></div></div>', unsafe_allow_html=True)

# ---------------------------------------------------
# AMBIENT ORBS (behind everything)
# ---------------------------------------------------
st.markdown("""
<div class="sati-bg">
    <div class="orb orb1"></div>
    <div class="orb orb2"></div>
    <div class="orb orb3"></div>
    <div class="orb orb4"></div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# MASTHEAD
# ---------------------------------------------------
st.markdown("""
<div class="sati-masthead">
    <span class="sati-lotus">🪷</span>
    <div class="sati-wordmark">SATICAST</div>
    <div class="sati-tagline">Daily Cast &nbsp;·&nbsp; Your mindful morning briefing</div>
    <div class="sati-meaning">✦ Sati — the Pali word for mindfulness &amp; awareness ✦</div>
    <div class="waveform-wrap">
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# CONTROLS: VOICE & LANGUAGE
# ---------------------------------------------------
col1, col2 = st.columns([1, 1])
with col1:
    voice_choice = st.selectbox(
        "🎙 Voice & Accent",
        options=list(VOICE_OPTIONS.keys()),
        index=0
    )
with col2:
    # Derived from voice choice — just informational label
    voice_cfg = VOICE_OPTIONS[voice_choice]
    lang_code = voice_cfg["lang"]
    tld_code  = voice_cfg["tld"]
    lang_display = {
        "en": "English",
        "hi": "हिन्दी (Hindi)",
        "mr": "मराठी (Marathi)"
    }.get(lang_code, "English")
    st.selectbox("📢 Script Language", options=[lang_display], index=0, disabled=True)

# ---------------------------------------------------
# TRIGGER BUTTON
# ---------------------------------------------------
trigger_brief = st.button("🪷 Generate Morning Brief")

if trigger_brief:
    with st.spinner("Curating your mindful morning dispatch…"):
        try:
            current_date = datetime.now().strftime("%A, %B %d, %Y")

            prompt_payload = f"""
Generate today's complete customised daily briefing for Pranay.
Date: {current_date}
Locations: Mumbai (Goregaon) and Nagpur.
Tech focus: Backend systems, Java/Spring Boot, PostgreSQL, Quantum Computing.
Provide exactly 5 highly critical items each for national, international, and tech updates.
Voice/accent selected by the user: {voice_choice}
"""
            completion = client.chat.completions.create(
                model="nvidia/llama-3.3-nemotron-super-49b-v1",
                messages=[
                    {"role": "system", "content": build_system_prompt(lang_code)},
                    {"role": "user",   "content": prompt_payload}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            payload = json.loads(completion.choices[0].message.content)

            # ── TTS ──
            tts_text = payload.get("spoken_script", "")
            tts = gTTS(text=tts_text, lang=lang_code, tld=tld_code, slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)

            # ── AUDIO PLAYER ──
            st.markdown(f"""
            <div class="audio-shell">
                <div class="audio-pill">▶ Now Playing</div>
                <div class="audio-title">Your Mindful Morning Brief &nbsp;·&nbsp; {datetime.now().strftime("%b %d, %Y")}</div>
                <div class="audio-accent">{voice_choice} &nbsp;·&nbsp; {lang_display}</div>
            </div>
            """, unsafe_allow_html=True)
            st.audio(fp, format="audio/mp3", autoplay=True)

            sep()

            # ── GREETING & WEATHER ──
            greeting = payload.get("greeting", "Good morning, Pranay!")
            weather  = payload.get("weather", "")
            st.markdown(f"""
            <div class="sati-section d1">
                <div class="greeting-card">{greeting}</div>
                <div class="weather-pill">🌤 {weather}</div>
            </div>
            """, unsafe_allow_html=True)

            sep()

            # ── NATIONAL ──
            st.markdown("""
            <div class="sati-section d2">
                <div class="section-header">
                    <div class="section-badge badge-india">🇮🇳</div>
                    <h2 class="section-title">National Intel</h2>
                </div>
                <div class="news-group">
            """, unsafe_allow_html=True)
            for i, item in enumerate(payload.get("india_news", []), 1):
                st.markdown(f"""
                <div class="news-item">
                    <div class="news-index idx-india">0{i}</div>
                    <div>
                        <div class="news-headline">{item.get('headline','')}</div>
                        <div class="news-detail">{item.get('detail','')}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)

            sep()

            # ── GLOBAL ──
            st.markdown("""
            <div class="sati-section d3">
                <div class="section-header">
                    <div class="section-badge badge-global">🌐</div>
                    <h2 class="section-title">Global Overview</h2>
                </div>
                <div class="news-group">
            """, unsafe_allow_html=True)
            for i, item in enumerate(payload.get("global_news", []), 1):
                st.markdown(f"""
                <div class="news-item">
                    <div class="news-index idx-global">0{i}</div>
                    <div>
                        <div class="news-headline">{item.get('headline','')}</div>
                        <div class="news-detail">{item.get('detail','')}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)

            sep()

            # ── TECH ──
            st.markdown("""
            <div class="sati-section d4">
                <div class="section-header">
                    <div class="section-badge badge-tech">⚡</div>
                    <h2 class="section-title">Tech & Architecture</h2>
                </div>
                <div class="news-group">
            """, unsafe_allow_html=True)
            for i, item in enumerate(payload.get("tech_news", []), 1):
                st.markdown(f"""
                <div class="news-item">
                    <div class="news-index idx-tech">0{i}</div>
                    <div>
                        <div class="news-headline">{item.get('headline','')}</div>
                        <div class="news-detail">{item.get('detail','')}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)

            sep()

            # ── MOMENT OF FOCUS ──
            focus = payload.get("moment_of_focus", {})
            st.markdown(f"""
            <div class="sati-section d5">
                <div class="section-header">
                    <div class="section-badge badge-focus">🧘</div>
                    <h2 class="section-title">Moment of Focus</h2>
                </div>
                <div class="focus-card">
                    <div class="focus-quote">"{focus.get('quote','')}"</div>
                    <div class="focus-expl">{focus.get('explanation','')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            sep()

            # ── WORD OF THE DAY ──
            w = payload.get("word_of_day", {})
            st.markdown(f"""
            <div class="sati-section d6">
                <div class="section-header">
                    <div class="section-badge badge-word">📝</div>
                    <h2 class="section-title">Daily Lexicon</h2>
                </div>
                <div class="word-card">
                    <div class="word-main">{w.get('word','')}</div>
                    <div class="word-label">Meaning</div>
                    <div class="word-val">{w.get('definition','')}</div>
                    <div class="word-label">In Context</div>
                    <div class="word-val"><em>"{w.get('example','')}"</em></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── FOOTER ──
            st.markdown(f"""
            <div class="sati-footer">
                <p>🪷 SatiCast &nbsp;·&nbsp; {datetime.now().strftime("%A, %B %d %Y")} &nbsp;·&nbsp; Powered by NVIDIA NIM &nbsp;·&nbsp; {voice_choice}</p>
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Failed to generate SatiCast brief: {e}")