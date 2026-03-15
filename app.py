# ============================================================
# UV Skincare Advisor — app.py
# Class 12 Capstone Project
# ============================================================
# HOW TO RUN:  streamlit run app.py
# ============================================================

import streamlit as st
from core.uv_fetcher import fetch_uv_data, classify_uv_risk
from core.skin_advisor import calculate_burn_time, get_spf_recommendation
from core.ml_scanner.predict import (
    analyze_ingredients_ml as analyze_ingredients,
    rating_color, rating_label,
    protection_color, concern_color
)
from core.charts import uv_gauge, hourly_uv_chart, burn_time_chart

# ── PAGE CONFIG ───────────────────────────────────────────────

st.set_page_config(
    page_title="UV Skincare Advisor",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }

    /* ── Dark base ── */
    .main { background-color: #0f1117 !important; }
    .block-container { background-color: #0f1117 !important; padding-top: 2rem !important; }
    [data-testid="stAppViewContainer"] { background-color: #0f1117 !important; }
    [data-testid="stHeader"] { background-color: #0f1117 !important; }

    /* ── Global text ── */
    .main p, .main span, .main div, .main label,
    .main h1, .main h2, .main h3, .main h4 { color: #e2e8f0; }

    #MainMenu, footer, header { visibility: hidden; }

    /* ── Metrics ── */
    [data-testid="stMetricLabel"] p,
    [data-testid="stMetricLabel"] span { color: #94a3b8 !important; font-size: 0.82rem !important; }
    [data-testid="stMetricValue"]       { color: #f1f5f9 !important; font-weight: 700 !important; }
    [data-testid="stMetricDelta"] span  { color: #94a3b8 !important; }

    /* ── Alerts ── */
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span,
    [data-testid="stAlert"] div { color: #e2e8f0 !important; }

    /* ── Captions ── */
    [data-testid="stCaptionContainer"] p { color: #64748b !important; font-size: 0.8rem !important; }

    /* ── Expander ── */
    [data-testid="stExpander"] { background: #1e2130 !important; border: 1px solid #2d3348 !important; border-radius: 10px !important; }
    [data-testid="stExpander"] p,
    [data-testid="stExpander"] span { color: #e2e8f0 !important; }

    /* ── Input fields ── */
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] div,
    [data-baseweb="select"] { background: #1e2130 !important; color: #e2e8f0 !important; border-color: #2d3348 !important; }
    [data-baseweb="select"] * { color: #e2e8f0 !important; }
    [data-testid="stSlider"] { color: #e2e8f0 !important; }

    /* ── Tabs ── */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 4px;
        background: #1e2130;
        padding: 4px;
        border-radius: 12px;
        border: none !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 20px !important;
        font-weight: 500 !important;
        color: #64748b !important;
        background: transparent !important;
        border: none !important;
    }
    [data-testid="stTabs"] [aria-selected="true"] {
        background: #2d3348 !important;
        color: #f97316 !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 6px rgba(249,115,22,0.2) !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"],
    [data-testid="stTabs"] [data-baseweb="tab-border"] { display: none !important; }

    /* ── Primary button ── */
    [data-testid="stButton"] button[kind="primary"],
    .stButton button {
        background: linear-gradient(135deg, #f97316, #ea580c) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 12px rgba(249,115,22,0.35) !important;
    }
    .stButton button:hover {
        box-shadow: 0 4px 20px rgba(249,115,22,0.5) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Cards ── */
    .card {
        background: #1e2130;
        border: 1px solid #2d3348;
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    .card-accent {
        background: #1e2130;
        border: 1px solid #2d3348;
        border-radius: 14px;
        padding: 16px 20px;
        border-left: 4px solid #f97316;
        margin-bottom: 10px;
    }

    /* ── UV card ── */
    .uv-card {
        border-radius: 18px;
        padding: 32px 28px;
        color: #ffffff !important;
        text-align: center;
        box-shadow: 0 8px 40px rgba(0,0,0,0.4);
    }
    .uv-card div, .uv-card span { color: #ffffff !important; }

    /* ── Section headers ── */
    .section-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 14px;
    }

    /* ── Pills ── */
    .pill {
        display: inline-block;
        background: #1e2130;
        border: 1px solid #2d3348;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.82rem;
        color: #94a3b8 !important;
        margin: 3px 2px;
    }
    .pill-orange { background: #2d1f0e; border-color: #7c3c10; color: #fb923c !important; }
    .pill-blue   { background: #0f1f33; border-color: #1e3a5c; color: #60a5fa !important; }

    /* ── Science box ── */
    .science-box {
        background: #131c2e;
        border-left: 4px solid #3b82f6;
        border-radius: 10px;
        padding: 16px 20px;
        font-size: 0.91rem;
        color: #93c5fd !important;
        line-height: 1.7;
    }
    .science-box b { color: #bfdbfe !important; }

    /* ── Controls bar ── */
    .controls-bar {
        background: #1e2130;
        border: 1px solid #2d3348;
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 24px;
    }

    /* ── App title ── */
    .app-title {
        font-size: 2.4rem;
        font-weight: 800;
        color: #f1f5f9;
        letter-spacing: -0.5px;
        line-height: 1.1;
    }
    .app-title span { color: #f97316; }
    .app-subtitle {
        font-size: 0.9rem;
        color: #475569;
        margin-top: 6px;
        margin-bottom: 28px;
    }

    /* ── Divider ── */
    hr { border: none; border-top: 1px solid #2d3348; margin: 20px 0; }

    /* ── Selectbox dropdown ── */
    [data-baseweb="popover"] { background: #1e2130 !important; border: 1px solid #2d3348 !important; }
    [data-baseweb="menu"] { background: #1e2130 !important; }
    [data-baseweb="menu"] li { color: #e2e8f0 !important; }
    [data-baseweb="menu"] li:hover { background: #2d3348 !important; }

</style>
""", unsafe_allow_html=True)

# ── FITZPATRICK DATA ──────────────────────────────────────────

FITZPATRICK_TYPES = {
    "Type I — Very Fair (Always burns, never tans)":         {"id": 1, "description": "Very fair, often freckles. Red/blonde hair. Blue eyes.",  "color_hex": "#FDDBB4"},
    "Type II — Fair (Usually burns, tans minimally)":        {"id": 2, "description": "Fair skin. Light hair. Blue, green, or hazel eyes.",       "color_hex": "#F5C8A0"},
    "Type III — Medium (Sometimes burns, gradually tans)":   {"id": 3, "description": "Medium skin. Any hair or eye colour.",                     "color_hex": "#E8A87C"},
    "Type IV — Olive (Rarely burns, tans easily)":           {"id": 4, "description": "Olive or light brown skin. Dark hair and eyes.",           "color_hex": "#C68642"},
    "Type V — Brown (Very rarely burns, tans very easily)":  {"id": 5, "description": "Brown skin. Dark hair and eyes.",                          "color_hex": "#8D5524"},
    "Type VI — Dark Brown/Black (Never burns)":              {"id": 6, "description": "Dark brown to black skin. Dark hair and eyes.",            "color_hex": "#4A2912"},
}

# ══════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="app-title">☀️ UVision</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Real-time UV intelligence · Personalised by Fitzpatrick skin type ·</div>',
    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  INLINE CONTROLS (replaces sidebar)
# ══════════════════════════════════════════════════════════════
with st.container():
    st.markdown("""
    <div style='background:#1e2130;border:1px solid #2d3348;border-radius:14px;
    padding:4px 24px 0px 24px;margin-bottom:4px;'>
    </div>""", unsafe_allow_html=True)

    ctrl1, ctrl2, ctrl3, ctrl4, ctrl5 = st.columns([1.2, 1.5, 1, 1, 0.8])

    with ctrl1:
        st.markdown("**📍 City**")
        city_name = st.text_input("City", value="Mumbai",
            placeholder="e.g. Delhi, London",
            label_visibility="collapsed")

    with ctrl2:
        st.markdown("**🎨 Skin Type**")
        selected_skin_label = st.selectbox("Skin type",
            options=list(FITZPATRICK_TYPES.keys()), index=2,
            label_visibility="collapsed")
        selected_skin = FITZPATRICK_TYPES[selected_skin_label]

    with ctrl3:
        st.markdown("**🏃 Activity**")
        activity = st.selectbox("Activity",
            ["Casual walk / commute", "Sports / exercise",
             "Beach / swimming", "Gardening", "Just checking"],
            label_visibility="collapsed")

    with ctrl4:
        st.markdown("**⏱ Hours outdoors**")
        duration_hours = st.slider("Hours",
            min_value=0.5, max_value=8.0, value=1.0,
            step=0.5, format="%.1f hrs",
            label_visibility="collapsed")

    with ctrl5:
        st.markdown("** **")
        analyze_button = st.button("🔍 Analyze", use_container_width=True, type="primary")

    # Skin swatch
    text_color = "#ffffff" if selected_skin["id"] >= 5 else "#1a1a1a"
    st.markdown(
        f"""<div style='background:{selected_skin["color_hex"]};border-radius:8px;
        padding:8px 14px;font-size:0.83rem;color:{text_color};
        border:1px solid rgba(0,0,0,0.1);display:inline-block;margin-top:4px;'>
        <b>Fitzpatrick Type {selected_skin["id"]}</b> —
        {selected_skin["description"]}
        </div>""", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
if "uv_result"   not in st.session_state: st.session_state.uv_result   = None
if "scan_result" not in st.session_state: st.session_state.scan_result = None
if "scan_ran"    not in st.session_state: st.session_state.scan_ran    = False

@st.cache_data(ttl=3600, show_spinner=False)
def cached_fetch(city: str):
    return fetch_uv_data(city)

if analyze_button:
    if not city_name.strip():
        st.warning("⚠️ Please enter a city name.")
    else:
        with st.spinner(f"Fetching live UV data for **{city_name}**..."):
            st.session_state.uv_result = cached_fetch(city_name.strip().title())

result = st.session_state.uv_result

# ══════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════
tab_dashboard, tab_charts, tab_ai, tab_science = st.tabs([
    "🏠 Dashboard", "📊 Charts", "🤖 AI Scanner", "🔬 Science Corner"
])

# ══════════════════════════════════════════════════════════════
#  TAB 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════
with tab_dashboard:
    col1, col2, col3 = st.columns([1.2, 1, 1], gap="medium")

    with col1:
        st.markdown('<div class="section-header">📡 Live UV Index</div>', unsafe_allow_html=True)

        if result is None:
            st.markdown("""
            <div class="uv-card" style="background:linear-gradient(135deg,#94a3b8,#64748b);">
                <div style="font-size:0.9rem;opacity:0.8;">UV Index</div>
                <div style="font-size:1.2rem;font-weight:700;margin:4px 0;">📍 Awaiting location...</div>
                <div style="font-size:5rem;font-weight:900;line-height:1;">—</div>
                <div style="font-size:0.9rem;opacity:0.8;">Enter city & click Analyze</div>
            </div>""", unsafe_allow_html=True)
        elif not result.get("success"):
            st.error(f"❌ {result.get('message','Unknown error')}")
            if result.get("detail"):
                st.caption(f"Debug: {result.get('detail')}")
        else:
            uv   = result["uv_index"]
            risk = classify_uv_risk(uv)
            st.markdown(f"""
            <div class="uv-card" style="background:linear-gradient(135deg,{risk['color']},{risk['color']}cc);">
                <div style="font-size:0.88rem;opacity:0.85;">UV Index for</div>
                <div style="font-size:1.2rem;font-weight:700;margin:2px 0;">
                    📍 {result['city']}, {result['country']}
                </div>
                <div style="font-size:5.5rem;font-weight:900;line-height:1.05;">{uv}</div>
                <div style="font-size:1.15rem;font-weight:600;">{risk['emoji']} {risk['level']} Risk</div>
            </div>""", unsafe_allow_html=True)

            st.markdown(f"""<br>
            <span class="pill pill-orange">🌤 {result['weather_description']}</span>
            <span class="pill pill-orange">🌡 {result['temperature_c']}°C</span>
            <span class="pill pill-orange">☁️ {result['cloud_cover_pct']}% cloud</span>
            <span class="pill pill-blue">🌅 {result['sunrise']}</span>
            <span class="pill pill-blue">🌇 {result['sunset']}</span>
            <span class="pill pill-blue">⛰ {result['elevation_m']}m</span>
            """, unsafe_allow_html=True)

            if result['elevation_m'] and result['elevation_m'] > 1000:
                st.info(f"⚠️ At {result['elevation_m']}m altitude, UV is ~{int(result['elevation_m']/1000*10)}% stronger than at sea level.")

    with col2:
        st.markdown('<div class="section-header">⏱️ Burn Time</div>', unsafe_allow_html=True)
        if result and result.get("success"):
            uv   = result["uv_index"]
            burn = calculate_burn_time(uv, selected_skin["id"], activity)
            if burn["no_risk"]:
                st.success("✅ UV Index is 0 — no burn risk right now. 🌙")
            else:
                st.metric("Unprotected burn time", f"{burn['burn_time_min']} min")
                st.caption(f"Fitzpatrick Type {selected_skin['id']} · {activity}")
                st.metric("Today's peak UV", str(result["uv_index_max_today"]))

        else:
            st.markdown('<div class="card" style="color:#94a3b8;text-align:center;padding:40px;">⏱️<br>Enter city & analyze</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="section-header">🧴 SPF Advice</div>', unsafe_allow_html=True)
        if result and result.get("success"):
            uv  = result["uv_index"]
            spf = get_spf_recommendation(uv, selected_skin["id"], activity, duration_hours)
            spf_val = spf["recommended_spf"]
            if spf_val == 15:   st.success(f"✅ **SPF {spf_val}** recommended")
            elif spf_val == 30: st.warning(f"⚠️ **SPF {spf_val}** recommended")
            else:               st.error(f"🔴 **SPF {spf_val}+** recommended")
            reapply_min = int(spf["reapply_hrs"] * 60)
            st.metric("🔁 Reapply every", f"{reapply_min} min",
                      delta=f"{spf['reapplications']} reapplication(s) for {duration_hours}h",
                      delta_color="off")
            st.caption(f"📊 {spf['reasoning']}")
            if spf["activity_note"]:
                st.info(f"🏃 **{activity}:** {spf['activity_note']}")
        else:
            st.markdown('<div class="card" style="color:#94a3b8;text-align:center;padding:40px;">🧴<br>Enter city & analyze</div>', unsafe_allow_html=True)

    if result and result.get("success") and result["uv_index"] > 0:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">🛡️ Your Personalised Protection Plan</div>',
                    unsafe_allow_html=True)
        spf_data = get_spf_recommendation(result["uv_index"], selected_skin["id"], activity, duration_hours)
        tip_cols = st.columns(2)
        for i, tip in enumerate(spf_data["tips"]):
            with tip_cols[i % 2]:
                st.markdown(
                    f"""<div class="card-accent">
                    <span style="font-size:1.3rem;">{tip['emoji']}</span>
                    <b style="color:#f1f5f9;font-size:0.93rem;"> {tip['title']}</b><br>
                    <span style="color:#94a3b8;font-size:0.84rem;">{tip['detail']}</span>
                    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  TAB 2 — CHARTS
# ══════════════════════════════════════════════════════════════
with tab_charts:
    if not (result and result.get("success")):
        st.markdown("""
        <div style='text-align:center;padding:60px;color:#94a3b8;'>
            <div style='font-size:3rem;'>📊</div>
            <div style='font-size:1.05rem;margin-top:12px;'>
                Charts will appear here after you analyze a city.<br>
                Enter a city in the sidebar and click <b>Analyze My UV Risk</b>.
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        uv = result["uv_index"]
        c1, c2 = st.columns([1, 1.7], gap="medium")

        with c1:
            st.markdown('<div class="section-header">🎯 UV Index Gauge</div>', unsafe_allow_html=True)
            st.plotly_chart(uv_gauge(uv, result["city"]), use_container_width=True)
            risk = classify_uv_risk(uv)
            burn_note = f"Type I skin can start to burn in ~{round(200/(uv*1.5))} min." if uv > 0 else "UV Index is 0 — no burn risk. 🌙"
            st.markdown(
                f"""<div style='background:#1e2130;border-radius:10px;
                border-left:3px solid {risk["color"]};padding:12px 16px;
                font-size:0.85rem;color:#e2e8f0;'>
                <b>{risk["emoji"]} {risk["level"]} Risk</b><br>{burn_note}
                </div>""", unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="section-header">📈 Hourly UV Forecast</div>', unsafe_allow_html=True)
            st.plotly_chart(
                hourly_uv_chart(result["hourly_labels"], result["hourly_uv"],
                                result["hourly_cloud"], result["current_hour_idx"], result["city"]),
                use_container_width=True)
            st.caption("Bars = UV Index by WHO risk band · Blue dotted = cloud cover · Orange dashed = now")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">🔥 Burn Time — All Skin Types</div>', unsafe_allow_html=True)
        st.plotly_chart(burn_time_chart(uv, activity), use_container_width=True)
        st.caption(f"⚠️ Without sunscreen · UV Index {uv} · {activity}")

# ══════════════════════════════════════════════════════════════
#  TAB 3 — AI SCANNER
# ══════════════════════════════════════════════════════════════
with tab_ai:
    st.markdown('<div class="section-header">🤖 AI Sunscreen Ingredient Scanner</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div style='background:#13261a;border-left:4px solid #22c55e;border-radius:10px;
    padding:12px 18px;font-size:0.9rem;color:#86efac;margin-bottom:20px;'>
    <b>How to use:</b> Copy the ingredient list from the back of any sunscreen bottle
    and paste it below. Our trained ML model will analyse every ingredient, flag concerns,
    and give personalised advice based on your Fitzpatrick skin type.
    </div>""", unsafe_allow_html=True)

    SAMPLE = """Active Ingredients: Avobenzone 3%, Homosalate 10%, Octisalate 5%, Octocrylene 2.7%, Oxybenzone 4%
Inactive Ingredients: Water, Glycerin, Dimethicone, Cetyl Alcohol, Phenoxyethanol, Aloe Barbadensis Leaf Extract, Tocopheryl Acetate"""

    # ── Initialise all scanner session state ─────────────────
    if "selected_skin_type"  not in st.session_state:
        st.session_state.selected_skin_type  = "✨ Normal"
    if "scanner_ingredients" not in st.session_state:
        st.session_state.scanner_ingredients = ""

    ai_col1, ai_col2 = st.columns([1.6, 1], gap="medium")
    with ai_col1:
        st.markdown("**📋 Paste ingredient list**")

        use_sample = st.checkbox("Use sample ingredients for testing",
                                  key="use_sample_checkbox")

        # When sample is checked, pre-fill session state once
        if use_sample:
            st.session_state.scanner_ingredients = SAMPLE

        st.text_area(
            "Ingredients",
            height=180,
            key="scanner_ingredients",
            label_visibility="collapsed",
            placeholder="e.g. Active Ingredients: Zinc Oxide 20%...")

        # Skin type selector
        st.markdown("**🧴 Your Skin Type**")
        skin_type_options = ["Oily", "Dry", "Combination", "Sensitive", "Normal"]
        skin_type_emojis  = ["💧 Oily", "🌵 Dry", "⚖️ Combination", "🌸 Sensitive", "✨ Normal"]

        selected_skin_type_label = st.selectbox(
            "Skin type", options=skin_type_emojis,
            index=skin_type_emojis.index(st.session_state.selected_skin_type),
            key="skin_type_selectbox",
            label_visibility="collapsed")
        st.session_state.selected_skin_type = selected_skin_type_label
        selected_skin_type = skin_type_options[skin_type_emojis.index(selected_skin_type_label)]

        scan_button = st.button("🔬 Scan with ML Model", use_container_width=True, type="primary")

    with ai_col2:
        st.markdown("**🧪 What the AI checks**")
        st.markdown("""
        <div style='font-size:0.87rem;color:#64748b;line-height:1.9;'>
        ✅ UV-A and UV-B filter coverage<br>
        ✅ Photostability of each filter<br>
        ✅ Broad spectrum protection<br>
        ✅ Ingredients of concern<br>
        ✅ Skin type compatibility<br>
        ✅ Reapplication guidance<br>
        ✅ Chemistry science fact<br><br>
        <b style='color:#94a3b8;'>Powered by:</b> Our trained ML model<br>
        <b style='color:#94a3b8;'>Dataset:</b> 500 ingredients · FDA, EWG, EU
        </div>""", unsafe_allow_html=True)
        if result and result.get("success"):
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"""<div style='background:#1e2130;border:1px solid #2d3348;
                border-radius:10px;padding:12px 16px;font-size:0.85rem;color:#94a3b8;'>
                <b style='color:#e2e8f0;'>Current context</b><br>
                UV Index: <b style='color:#f97316;'>{result['uv_index']}</b> · {result['city']}<br>
                Skin: <b style='color:#e2e8f0;'>Fitzpatrick {selected_skin['id']}</b>
                </div>""", unsafe_allow_html=True)

    if scan_button:
        active_ingredients = st.session_state.scanner_ingredients
        if not active_ingredients.strip():
            st.warning("⚠️ Please paste an ingredient list first.")
        else:
            current_uv = result["uv_index"] if (result and result.get("success")) else None
            with st.spinner("🔬 Analysing ingredients with ML model..."):
                st.session_state.scan_result = analyze_ingredients(
                    active_ingredients, selected_skin["id"], current_uv,
                    skin_type=selected_skin_type)
                st.session_state.scan_ran = True

    scan = st.session_state.scan_result
    if not st.session_state.scan_ran:
        st.markdown("""
        <div style='text-align:center;padding:40px;color:#475569;'>
            <div style='font-size:2.5rem;'>🔬</div>
            <div style='font-size:0.95rem;margin-top:10px;'>
                Paste an ingredient list above and click <b>Scan with ML Model</b>
            </div>
        </div>""", unsafe_allow_html=True)
    elif scan:
        if not scan.get("success"):
            st.error(f"❌ {scan.get('message','Unknown error')}")
            if scan.get("error") == "no_model":
                st.info("💡 Run `python core/ml_scanner/train_model.py` to train the model first.")
        else:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">📊 Analysis Results</div>', unsafe_allow_html=True)

            rating  = scan.get("overall_rating", 0)
            r_color = rating_color(rating)
            r_label = rating_label(rating)

            sc1, sc2, sc3, sc4, sc5 = st.columns(5)
            with sc1:
                st.markdown(
                    f"""<div style='text-align:center;background:{r_color}18;
                    border:2px solid {r_color};border-radius:12px;padding:18px 8px;'>
                    <div style='font-size:2.4rem;font-weight:900;color:{r_color};'>{rating}/10</div>
                    <div style='font-size:0.85rem;font-weight:600;color:{r_color};'>{r_label}</div>
                    <div style='font-size:0.75rem;color:#94a3b8;margin-top:4px;'>Overall</div>
                    </div>""", unsafe_allow_html=True)

            for col, (label, val) in zip([sc2, sc3, sc4, sc5], [
                ("UV-A",  scan.get("uva_protection","—")),
                ("UV-B",  scan.get("uvb_protection","—")),
                ("Photo", scan.get("photostability","—")),
                ("Skin",  scan.get("skin_type_compatibility","—")),
            ]):
                pc = protection_color(val)
                with col:
                    st.markdown(
                        f"""<div style='text-align:center;background:{pc}18;
                        border:2px solid {pc};border-radius:12px;padding:18px 8px;'>
                        <div style='font-size:1.2rem;font-weight:800;color:{pc};'>{val}</div>
                        <div style='font-size:0.75rem;color:#94a3b8;margin-top:6px;'>{label}</div>
                        </div>""", unsafe_allow_html=True)

            st.markdown(
                f"""<div style='background:#1e2130;border-radius:10px;
                border-left:3px solid {r_color};padding:14px 18px;
                margin:16px 0;font-size:0.92rem;color:#e2e8f0;'>
                <b>AI Verdict:</b> {scan.get("overall_verdict","")}
                </div>""", unsafe_allow_html=True)

            # ── Skin Type Score Cards ─────────────────────────
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">🧴 Score by Skin Type</div>',
                        unsafe_allow_html=True)

            skin_scores = scan.get("skin_type_scores", {})
            selected_st = scan.get("selected_skin_type", "Normal")

            if skin_scores:
                st_cols = st.columns(len(skin_scores))
                for col, (st_name, st_data) in zip(st_cols, skin_scores.items()):
                    is_selected = (st_name == selected_st)
                    border = "3px solid " + st_data['color'] if is_selected else "1px solid #2d3348"
                    bg     = st_data['color'] + "22" if is_selected else "#1e2130"
                    badge  = "<div style='position:absolute;top:6px;right:8px;font-size:0.6rem;color:" + st_data['color'] + ";font-weight:700;'>YOUR TYPE</div>" if is_selected else ""
                    score  = str(st_data['score'])
                    label  = st_data['label']
                    color  = st_data['color']
                    emoji  = st_data['emoji']
                    html = (
                        "<div style='text-align:center;background:" + bg + ";"
                        "border:" + border + ";border-radius:14px;"
                        "padding:16px 8px;position:relative;'>"
                        + badge +
                        "<div style='font-size:1.5rem;'>" + emoji + "</div>"
                        "<div style='font-size:0.78rem;color:#64748b;margin:4px 0;'>" + st_name + "</div>"
                        "<div style='font-size:2rem;font-weight:900;color:" + color + ";line-height:1;'>" + score + "</div>"
                        "<div style='font-size:0.65rem;color:" + color + ";font-weight:600;'>/10 · " + label + "</div>"
                        "</div>"
                    )
                    with col:
                        st.markdown(html, unsafe_allow_html=True)

            filters = scan.get("uv_filters_found", [])
            if filters:
                broad = "✅ Broad Spectrum" if scan.get("broad_spectrum") else "⚠️ Not Broad Spectrum"
                st.markdown(
                    f"""<div style='background:#1e2130;border:1px solid #2d3348;
                    border-radius:10px;padding:10px 16px;margin-bottom:12px;
                    font-size:0.88rem;color:#94a3b8;'>
                    {broad} · <b style='color:#e2e8f0;'>{scan.get('filter_type','Unknown')}</b> ·
                    Photostability: <b style='color:#e2e8f0;'>{scan.get('photostability','N/A')}</b>
                    </div>""", unsafe_allow_html=True)

            # ── Ingredients of Concern — full width ──────────
            st.markdown('<div class="section-header">⚠️ Ingredients of Concern</div>',
                        unsafe_allow_html=True)
            concerning = scan.get("concerning_ingredients", [])
            if concerning:
                concern_cols = st.columns(2)
                for i, c in enumerate(concerning):
                    sc_color = concern_color(c.get("severity","Low"))
                    with concern_cols[i % 2]:
                        st.markdown(
                            f"""<div style='background:#1e1510;border-radius:10px;
                            border-left:3px solid {sc_color};padding:10px 14px;
                            margin-bottom:8px;font-size:0.87rem;color:#fcd34d;'>
                            <b style='color:#fde68a;'>{c.get("name","")}</b>
                            <span style='float:right;color:{sc_color};font-weight:700;font-size:0.8rem;'>
                            {c.get("severity","")} risk</span><br>
                            {c.get("concern","")}
                            </div>""", unsafe_allow_html=True)
            else:
                st.success("✅ No concerning ingredients detected!")

            st.markdown("<hr>", unsafe_allow_html=True)
            n1, n2 = st.columns(2, gap="medium")
            with n1:
                st.markdown(
                    f"""<div style='background:#131c2e;border-left:4px solid #3b82f6;
                    border-radius:10px;padding:16px 18px;font-size:0.9rem;color:#93c5fd;'>
                    <b style='color:#bfdbfe;'>🎨 Fitzpatrick Type {selected_skin["id"]} Notes</b><br><br>
                    {scan.get("skin_type_notes","")}
                    </div>""", unsafe_allow_html=True)
            with n2:
                st.markdown(
                    f"""<div style='background:#2d1f0e;border-left:4px solid #f97316;
                    border-radius:10px;padding:16px 18px;font-size:0.9rem;color:#fdba74;'>
                    <b style='color:#fed7aa;'>🔁 Reapplication Note</b><br><br>
                    {scan.get("reapplication_note","")}
                    </div>""", unsafe_allow_html=True)

            if scan.get("science_fact"):
                st.markdown(
                    f"""<div style='background:#1a1228;border-left:4px solid #a855f7;
                    border-radius:10px;padding:14px 18px;margin-top:12px;
                    font-size:0.9rem;color:#d8b4fe;'>
                    <b style='color:#e9d5ff;'>⚛️ Science Fact:</b> {scan.get("science_fact","")}
                    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  TAB 4 — SCIENCE CORNER
# ══════════════════════════════════════════════════════════════
with tab_science:
    st.markdown('<div class="section-header">🔬 Science Corner</div>', unsafe_allow_html=True)
    sc_tab1, sc_tab2, sc_tab3 = st.tabs([
        "⚛️ The Physics of UV", "🧬 The Biology of Skin", "📡 How Open-Meteo Works"
    ])

    with sc_tab1:
        st.markdown("""
        <div class="science-box">
        <b>What is UV Radiation?</b><br>
        Ultraviolet (UV) radiation is electromagnetic radiation with wavelengths between
        100–400 nm — shorter than visible light, longer than X-rays.<br><br>
        <b>UV-A (315–400 nm)</b> — penetrates into the dermis; causes photoageing and long-term DNA damage.<br>
        <b>UV-B (280–315 nm)</b> — absorbed by the epidermis; the primary cause of sunburn and skin cancer.<br>
        <b>UV-C (100–280 nm)</b> — entirely absorbed by the ozone layer; never reaches Earth's surface.<br><br>
        The <b>UV Index</b> is a WHO-standardised scale measuring erythemally-weighted solar irradiance —
        UV energy weighted by how biologically damaging each wavelength is to skin.
        Each UV Index unit ≈ 0.025 W/m².
        </div>""", unsafe_allow_html=True)

    with sc_tab2:
        st.markdown("""
        <div class="science-box">
        <b>Why Does Skin Type Matter?</b><br>
        The key variable is <b>melanin</b> — a biopolymer pigment produced by melanocytes in the epidermis.
        Melanin acts as a natural broadband UV absorber, converting photon energy into harmless heat
        through ultrafast internal conversion.<br><br>
        People with more <b>eumelanin</b> (Fitzpatrick Types IV–VI) have a higher
        <b>Minimal Erythemal Dose (MED)</b> — they need significantly more UV exposure before sunburn occurs.<br><br>
        People with <b>less melanin</b> (Types I–II) have a much lower MED and are at higher risk of
        UV-induced DNA damage — specifically <b>pyrimidine dimer formation</b> in DNA strands,
        the primary molecular trigger of skin cancer.
        </div>""", unsafe_allow_html=True)

    with sc_tab3:
        st.markdown("""
        <div class="science-box">
        <b>How Open-Meteo Provides UV Data:</b><br><br>
        <b>Step 1 — Geocoding:</b> We call the Open-Meteo Geocoding API with your city name.
        It returns precise latitude, longitude, timezone, and elevation.<br><br>
        <b>Step 2 — Forecast:</b> We call the Forecast API with those coordinates.
        Open-Meteo calculates UV Index from the <b>NOAA GFS model</b>, which uses satellite
        observations and atmospheric ozone data, updated every 6 hours.<br><br>
        <b>Why elevation matters — Beer-Lambert Law:</b> UV intensity increases ~10% per 1000m
        of altitude because there is less atmosphere and ozone to absorb UV photons.
        This is the same principle used in spectroscopy to measure light absorption through a medium.
        </div>""", unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
st.caption(
    "🎓 Class 12 Capstone Project · Built with Streamlit · "
    "UV data via Open-Meteo · AI via self made ML model · "
    "Science: WHO & Fitzpatrick (1975)"
)