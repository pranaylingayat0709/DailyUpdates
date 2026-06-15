import streamlit as st
import json
from openai import OpenAI
from datetime import datetime
from gtts import gTTS
import io
import base64

# ---------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------
st.set_page_config(
    page_title="Huxe Daily Cast",
    page_icon="🎙️",
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
# FULL PREMIUM CSS + ANIMATIONS
# ---------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@300;400;500;600&display=swap');

/* ── BASE RESET ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: #080C14 !important;
    color: #E2E8F0 !important;
}
.stApp { background: #080C14 !important; }
.main .block-container {
    max-width: 700px;
    padding-top: 0 !important;
    padding-bottom: 6rem;
}
#MainMenu, footer, header { visibility: hidden; }
* { box-sizing: border-box; }

/* ── HERO WAVEFORM HEADER ── */
.huxe-masthead {
    position: relative;
    width: 100%;
    padding: 4rem 0 2.5rem;
    text-align: center;
    overflow: hidden;
    margin-bottom: 1rem;
}
.huxe-masthead::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(109,40,217,0.18) 0%, transparent 70%);
    pointer-events: none;
}
.huxe-wordmark {
    font-family: 'Syne', sans-serif;
    font-size: 4.5rem;
    font-weight: 800;
    letter-spacing: -3px;
    line-height: 1;
    background: linear-gradient(135deg, #818CF8 0%, #C084FC 45%, #F472B6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.4rem;
    animation: fadeSlideDown 0.8s ease both;
}
.huxe-tagline {
    font-size: 0.85rem;
    font-weight: 500;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: #64748B;
    animation: fadeSlideDown 0.9s 0.1s ease both;
}

/* ── LIVE WAVEFORM BARS ── */
.waveform-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 40px;
    margin: 1.5rem auto 0;
    animation: fadeSlideDown 1s 0.2s ease both;
}
.waveform-wrap.idle .bar { animation-play-state: paused !important; }
.bar {
    width: 3px;
    border-radius: 99px;
    background: linear-gradient(to top, #6366F1, #C084FC);
    animation: wave 1.2s ease-in-out infinite;
    transform-origin: bottom;
}
.bar:nth-child(1)  { height:12px; animation-delay:0.0s; }
.bar:nth-child(2)  { height:22px; animation-delay:0.1s; }
.bar:nth-child(3)  { height:32px; animation-delay:0.2s; }
.bar:nth-child(4)  { height:28px; animation-delay:0.3s; }
.bar:nth-child(5)  { height:38px; animation-delay:0.15s; }
.bar:nth-child(6)  { height:30px; animation-delay:0.25s; }
.bar:nth-child(7)  { height:40px; animation-delay:0.05s; }
.bar:nth-child(8)  { height:34px; animation-delay:0.35s; }
.bar:nth-child(9)  { height:28px; animation-delay:0.1s; }
.bar:nth-child(10) { height:20px; animation-delay:0.2s; }
.bar:nth-child(11) { height:14px; animation-delay:0.3s; }
.bar:nth-child(12) { height:26px; animation-delay:0.0s; }
.bar:nth-child(13) { height:36px; animation-delay:0.15s; }
.bar:nth-child(14) { height:30px; animation-delay:0.25s; }
.bar:nth-child(15) { height:18px; animation-delay:0.05s; }
.bar:nth-child(16) { height:10px; animation-delay:0.35s; }

@keyframes wave {
    0%, 100% { transform: scaleY(0.4); opacity:0.5; }
    50%       { transform: scaleY(1.0); opacity:1; }
}

/* ── GLASS BUTTON ── */
.stButton > button {
    display: block !important;
    margin: 0 auto !important;
    background: linear-gradient(135deg, rgba(99,102,241,0.25) 0%, rgba(167,139,250,0.2) 100%) !important;
    border: 1px solid rgba(139,92,246,0.5) !important;
    backdrop-filter: blur(10px) !important;
    color: #E0E7FF !important;
    border-radius: 999px !important;
    padding: 0.75rem 3rem !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 0 24px rgba(99,102,241,0.2), inset 0 1px 0 rgba(255,255,255,0.08) !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, rgba(99,102,241,0.45) 0%, rgba(167,139,250,0.4) 100%) !important;
    box-shadow: 0 0 40px rgba(139,92,246,0.4), inset 0 1px 0 rgba(255,255,255,0.12) !important;
    transform: translateY(-2px) scale(1.02) !important;
}
.stButton > button:active { transform: scale(0.98) !important; }

/* ── AUDIO PLAYER CARD ── */
.audio-shell {
    background: linear-gradient(135deg, rgba(17,24,39,0.8) 0%, rgba(30,27,75,0.7) 100%);
    border: 1px solid rgba(139,92,246,0.25);
    border-radius: 20px;
    padding: 1.75rem 2rem;
    margin: 2rem 0 2.5rem;
    position: relative;
    overflow: hidden;
    animation: cardReveal 0.6s ease both;
    backdrop-filter: blur(12px);
}
.audio-shell::before {
    content: '';
    position: absolute;
    top: -60px; left: -60px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(109,40,217,0.15), transparent 70%);
    pointer-events: none;
}
.audio-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #A78BFA;
    margin-bottom: 0.35rem;
}
.audio-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.2rem;
    font-weight: 700;
    color: #F1F5F9;
    margin-bottom: 1.25rem;
}
.stAudio { margin-top: 0 !important; }
.stAudio audio {
    width: 100% !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.04) !important;
    filter: none !important;
}

/* ── SECTION MODULES ── */
.huxe-section {
    margin-bottom: 3rem;
    animation: cardReveal 0.6s ease both;
}
.section-eyebrow {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1rem;
}
.section-icon {
    width: 32px; height: 32px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
}
.icon-india   { background: rgba(251,191,36,0.12); }
.icon-global  { background: rgba(96,165,250,0.12); }
.icon-tech    { background: rgba(52,211,153,0.12); }
.icon-focus   { background: rgba(167,139,250,0.12); }
.icon-word    { background: rgba(248,113,113,0.12); }
.icon-weather { background: rgba(125,211,252,0.12); }
.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    color: #F1F5F9;
    letter-spacing: -0.5px;
    margin: 0;
}

/* ── GREETING CARD ── */
.greeting-card {
    background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(167,139,250,0.06));
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 2rem;
    color: #CBD5E1;
    font-size: 1.05rem;
    line-height: 1.7;
    animation: cardReveal 0.5s ease both;
}
.greeting-card strong { color: #A5B4FC; }

/* ── WEATHER PILL ── */
.weather-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(125,211,252,0.08);
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 999px;
    padding: 0.4rem 1rem;
    font-size: 0.85rem;
    color: #7DD3FC;
    margin-bottom: 2rem;
    font-weight: 500;
    animation: cardReveal 0.55s ease both;
}

/* ── NEWS ITEMS ── */
.news-item {
    display: flex;
    gap: 14px;
    padding: 1rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    transition: background 0.2s;
}
.news-item:last-child { border-bottom: none; }
.news-index {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 800;
    min-width: 28px;
    padding-top: 2px;
    line-height: 1;
}
.idx-india  { color: rgba(251,191,36,0.4); }
.idx-global { color: rgba(96,165,250,0.4); }
.idx-tech   { color: rgba(52,211,153,0.4); }
.news-content { flex: 1; }
.news-headline {
    font-weight: 600;
    font-size: 0.95rem;
    color: #F1F5F9;
    line-height: 1.4;
    margin-bottom: 0.25rem;
}
.news-detail {
    font-size: 0.875rem;
    color: #64748B;
    line-height: 1.6;
}

/* ── NEWS GROUP CARD ── */
.news-group {
    background: rgba(15,23,42,0.6);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 0.5rem 1.25rem 0.25rem;
    backdrop-filter: blur(8px);
}

/* ── QUOTE BLOCK ── */
.focus-card {
    background: linear-gradient(135deg, rgba(109,40,217,0.1), rgba(192,132,252,0.06));
    border: 1px solid rgba(139,92,246,0.2);
    border-left: 3px solid #8B5CF6;
    border-radius: 0 16px 16px 0;
    padding: 1.5rem 1.5rem 1.5rem 1.75rem;
}
.focus-quote {
    font-family: 'Syne', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: #DDD6FE;
    line-height: 1.5;
    margin-bottom: 0.75rem;
    font-style: italic;
}
.focus-expl {
    font-size: 0.9rem;
    color: #94A3B8;
    line-height: 1.7;
}

/* ── WORD OF THE DAY ── */
.word-card {
    background: rgba(15,23,42,0.6);
    border: 1px solid rgba(248,113,113,0.15);
    border-radius: 16px;
    padding: 1.5rem;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.75rem 1.25rem;
    align-items: start;
}
.word-main {
    font-family: 'Syne', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    color: #FCA5A5;
    grid-column: 1 / -1;
    border-bottom: 1px solid rgba(248,113,113,0.1);
    padding-bottom: 0.75rem;
    margin-bottom: 0.25rem;
}
.word-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #475569;
    padding-top: 2px;
}
.word-val {
    font-size: 0.9rem;
    color: #94A3B8;
    line-height: 1.6;
}
.word-val em { color: #CBD5E1; font-style: italic; }

/* ── DIVIDER ── */
.huxe-sep {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 2.5rem 0;
    opacity: 0.3;
}
.huxe-sep::before, .huxe-sep::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(to right, transparent, rgba(148,163,184,0.5), transparent);
}
.huxe-sep-dot {
    width: 4px; height: 4px;
    border-radius: 50%;
    background: #475569;
}

/* ── SPINNER OVERRIDE ── */
.stSpinner > div {
    border-top-color: #8B5CF6 !important;
}

/* ── ANIMATIONS ── */
@keyframes fadeSlideDown {
    from { opacity:0; transform: translateY(-16px); }
    to   { opacity:1; transform: translateY(0); }
}
@keyframes cardReveal {
    from { opacity:0; transform: translateY(20px); }
    to   { opacity:1; transform: translateY(0); }
}

/* ── STAGGERED SECTION DELAYS ── */
.delay-1 { animation-delay: 0.05s; }
.delay-2 { animation-delay: 0.12s; }
.delay-3 { animation-delay: 0.19s; }
.delay-4 { animation-delay: 0.26s; }
.delay-5 { animation-delay: 0.33s; }
.delay-6 { animation-delay: 0.40s; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------
SYSTEM_INSTRUCTIONS = """
You are the voice of Huxe, a sophisticated, premium AI radio host. Your task is to generate a daily briefing script structured as valid JSON.
The script must sound completely seamless and natural when read aloud via Text-to-Speech (TTS), avoiding awkward text elements or abbreviations.

STRICT WRITING RULES:
- The `spoken_script` must be written entirely in continuous, natural paragraphs without symbols, bullet characters, or hashtags.
- Use explicit transitions between segments (e.g., "Turning our attention to the global stage...", "Now for your architectural tech update...").
- For the `visual_data` blocks, isolate the main news items into scannable headlines and 1-sentence descriptions for screen presentation.

You MUST return a valid JSON object with the exact keys:
{
  "greeting": "A short, warm welcoming sentence addressing Pranay personally.",
  "weather": "Conversational forecast summary for Mumbai and Nagpur in one sentence.",
  "india_news": [{"headline": "Bold Key Phase", "detail": "One clear explanation sentence."}],
  "global_news": [{"headline": "Bold Key Phase", "detail": "One clear explanation sentence."}],
  "tech_news": [{"headline": "Bold Key Phase", "detail": "One clear explanation sentence."}],
  "moment_of_focus": {"quote": "Quote text", "explanation": "Application mapping sentence."},
  "word_of_day": {"word": "The word", "definition": "Meaning", "example": "Context sentence"},
  "spoken_script": "The complete narrative containing all elements smoothly integrated to be read continuously by an audio engine."
}
"""

# ---------------------------------------------------
# HELPER: SEPARATOR
# ---------------------------------------------------
def sep():
    st.markdown('<div class="huxe-sep"><div class="huxe-sep-dot"></div><div class="huxe-sep-dot"></div><div class="huxe-sep-dot"></div></div>', unsafe_allow_html=True)

# ---------------------------------------------------
# MASTHEAD
# ---------------------------------------------------
st.markdown("""
<div class="huxe-masthead">
    <div class="huxe-wordmark">HUXE</div>
    <div class="huxe-tagline">Daily Cast &nbsp;·&nbsp; Your personalized audio briefing</div>
    <div class="waveform-wrap idle" id="waveform">
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
# TRIGGER BUTTON
# ---------------------------------------------------
trigger_brief = st.button("☀️ Generate Morning Brief")

if trigger_brief:
    # Activate waveform
    st.markdown("""
    <script>
    document.getElementById('waveform') && document.getElementById('waveform').classList.remove('idle');
    </script>
    """, unsafe_allow_html=True)

    with st.spinner("Curating your morning dispatch…"):
        try:
            current_date = datetime.now().strftime("%A, %B %d, %Y")

            prompt_payload = f"""
            Generate today's complete customized daily briefing for Pranay.
            Date: {current_date}
            Locations: Mumbai (Goregaon) and Nagpur.
            Tech focus: Backend systems, Java/Spring Boot, PostgreSQL, Quantum Computing.
            Provide exactly 5 highly critical items each for national, international, and tech updates.
            """

            completion = client.chat.completions.create(
                model="nvidia/llama-3.3-nemotron-super-49b-v1",
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": prompt_payload}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            payload = json.loads(completion.choices[0].message.content)

            # ── TTS GENERATION ──
            tts_text = payload.get("spoken_script", "")
            tts = gTTS(text=tts_text, lang='en', tld='co.in', slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)

            # ── AUDIO PLAYER ──
            st.markdown("""
            <div class="audio-shell">
                <div class="audio-label">▶ Now Playing</div>
                <div class="audio-title">Your Personalized Morning Brief &nbsp;·&nbsp; {date}</div>
            </div>
            """.replace("{date}", datetime.now().strftime("%b %d")), unsafe_allow_html=True)
            st.audio(fp, format="audio/mp3", autoplay=True)

            sep()

            # ── GREETING ──
            greeting = payload.get("greeting", "Good morning, Pranay!")
            weather  = payload.get("weather", "")
            st.markdown(f"""
            <div class="huxe-section delay-1">
                <div class="greeting-card">{greeting}</div>
                <div class="weather-pill">🌤 {weather}</div>
            </div>
            """, unsafe_allow_html=True)

            sep()

            # ── NATIONAL ──
            st.markdown("""
            <div class="huxe-section delay-2">
                <div class="section-eyebrow">
                    <div class="section-icon icon-india">🇮🇳</div>
                    <h2 class="section-title">National Intel</h2>
                </div>
                <div class="news-group">
            """, unsafe_allow_html=True)
            for i, item in enumerate(payload.get("india_news", []), 1):
                st.markdown(f"""
                <div class="news-item">
                    <div class="news-index idx-india">0{i}</div>
                    <div class="news-content">
                        <div class="news-headline">{item['headline']}</div>
                        <div class="news-detail">{item['detail']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)

            sep()

            # ── GLOBAL ──
            st.markdown("""
            <div class="huxe-section delay-3">
                <div class="section-eyebrow">
                    <div class="section-icon icon-global">🌐</div>
                    <h2 class="section-title">Global Overview</h2>
                </div>
                <div class="news-group">
            """, unsafe_allow_html=True)
            for i, item in enumerate(payload.get("global_news", []), 1):
                st.markdown(f"""
                <div class="news-item">
                    <div class="news-index idx-global">0{i}</div>
                    <div class="news-content">
                        <div class="news-headline">{item['headline']}</div>
                        <div class="news-detail">{item['detail']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)

            sep()

            # ── TECH ──
            st.markdown("""
            <div class="huxe-section delay-4">
                <div class="section-eyebrow">
                    <div class="section-icon icon-tech">⚡</div>
                    <h2 class="section-title">Tech & Architecture</h2>
                </div>
                <div class="news-group">
            """, unsafe_allow_html=True)
            for i, item in enumerate(payload.get("tech_news", []), 1):
                st.markdown(f"""
                <div class="news-item">
                    <div class="news-index idx-tech">0{i}</div>
                    <div class="news-content">
                        <div class="news-headline">{item['headline']}</div>
                        <div class="news-detail">{item['detail']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)

            sep()

            # ── MOMENT OF FOCUS ──
            focus = payload.get("moment_of_focus", {})
            st.markdown(f"""
            <div class="huxe-section delay-5">
                <div class="section-eyebrow">
                    <div class="section-icon icon-focus">🧘</div>
                    <h2 class="section-title">Moment of Focus</h2>
                </div>
                <div class="focus-card">
                    <div class="focus-quote">"{focus.get('quote', '')}"</div>
                    <div class="focus-expl">{focus.get('explanation', '')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            sep()

            # ── WORD OF THE DAY ──
            w = payload.get("word_of_day", {})
            st.markdown(f"""
            <div class="huxe-section delay-6">
                <div class="section-eyebrow">
                    <div class="section-icon icon-word">📝</div>
                    <h2 class="section-title">Daily Lexicon</h2>
                </div>
                <div class="word-card">
                    <div class="word-main">{w.get('word', '')}</div>
                    <div class="word-label">Meaning</div>
                    <div class="word-val">{w.get('definition', '')}</div>
                    <div class="word-label">In context</div>
                    <div class="word-val"><em>"{w.get('example', '')}"</em></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── FOOTER ──
            st.markdown(f"""
            <div style="text-align:center; margin-top:4rem; padding-bottom:2rem;">
                <p style="font-size:0.75rem; color:#1E293B; letter-spacing:0.1em; text-transform:uppercase;">
                    Huxe Cast &nbsp;·&nbsp; {datetime.now().strftime("%A, %B %d %Y")} &nbsp;·&nbsp; Powered by NVIDIA NIM
                </p>
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Failed to generate morning brief: {e}")
