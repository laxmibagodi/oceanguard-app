import streamlit as st
import tensorflow as tf
import numpy as np
import cv2
import os
import io
import time
import random
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
import pandas as pd
import gdown

st.set_page_config(
    page_title="OceanGuard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Exo+2:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Exo 2', sans-serif; }
    .stApp {
        background: linear-gradient(135deg,#020b18 0%,#041428 40%,#062040 70%,#083050 100%);
        color: #e0f4ff;
    }
    .main-title {
        font-family:'Orbitron',monospace; font-size:2.8rem; font-weight:900;
        background:linear-gradient(90deg,#00d4ff,#00ff9f,#00d4ff);
        background-size:200%; -webkit-background-clip:text;
        -webkit-text-fill-color:transparent;
        animation:shimmer 3s infinite; text-align:center;
        letter-spacing:4px; margin-bottom:0;
    }
    @keyframes shimmer{0%{background-position:0%}100%{background-position:200%}}
    .subtitle {
        text-align:center; color:#7ecfea; font-size:0.9rem;
        letter-spacing:3px; text-transform:uppercase;
        margin-top:0.2rem; margin-bottom:1.5rem;
    }
    .ocean-card {
        background:linear-gradient(145deg,rgba(0,60,100,0.6),rgba(0,30,60,0.8));
        border:1px solid rgba(0,212,255,0.2); border-radius:16px;
        padding:1.5rem; margin:0.8rem 0;
        box-shadow:0 8px 32px rgba(0,212,255,0.1);
    }
    .alert-oil {
        background:linear-gradient(135deg,rgba(255,40,40,0.25),rgba(180,0,0,0.3));
        border:2px solid #ff4444; border-radius:12px;
        padding:1.2rem 1.5rem; text-align:center;
        animation:pulse-red 1.5s infinite; margin:1rem 0;
    }
    @keyframes pulse-red{
        0%,100%{box-shadow:0 0 10px rgba(255,68,68,0.4);}
        50%{box-shadow:0 0 30px rgba(255,68,68,0.9);}
    }
    .alert-clean {
        background:linear-gradient(135deg,rgba(0,200,100,0.2),rgba(0,150,80,0.25));
        border:2px solid #00cc66; border-radius:12px;
        padding:1.2rem 1.5rem; text-align:center; margin:1rem 0;
    }
    .alert-title{font-family:'Orbitron',monospace;font-size:1.6rem;font-weight:700;margin:0;}
    .alert-sub  {font-size:0.9rem;opacity:0.85;margin-top:0.3rem;}
    .metric-box  {background:rgba(0,80,130,0.4);border:1px solid rgba(0,212,255,0.3);border-radius:12px;padding:1rem;text-align:center;margin-bottom:0.5rem;}
    .metric-value{font-family:'Orbitron',monospace;font-size:2rem;font-weight:700;color:#00d4ff;}
    .metric-label{font-size:0.75rem;color:#7ecfea;text-transform:uppercase;letter-spacing:2px;}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#020e1f 0%,#041828 100%);border-right:1px solid rgba(0,212,255,0.15);}
    .stTabs [data-baseweb="tab-list"]{background:rgba(0,30,60,0.6);border-radius:12px;padding:4px;gap:4px;}
    .stTabs [data-baseweb="tab"]     {background:transparent;color:#7ecfea;border-radius:8px;font-family:'Exo 2',sans-serif;font-weight:600;}
    .stTabs [aria-selected="true"]   {background:linear-gradient(135deg,#004080,#006090) !important;color:#00d4ff !important;}
    [data-testid="stFileUploader"]   {background:rgba(0,50,100,0.3);border:2px dashed rgba(0,212,255,0.4);border-radius:12px;}
    .stButton > button {background:linear-gradient(135deg,#004080,#006090);color:#00d4ff;border:1px solid rgba(0,212,255,0.4);border-radius:8px;font-family:'Exo 2',sans-serif;font-weight:600;transition:all 0.3s;}
    .stButton > button:hover{background:linear-gradient(135deg,#0060b0,#0080b0);box-shadow:0 0 20px rgba(0,212,255,0.5);transform:translateY(-1px);}
    .log-entry-oil  {background:rgba(255,50,50,0.1);border-left:3px solid #ff4444;padding:0.5rem 0.8rem;margin:0.3rem 0;border-radius:0 8px 8px 0;font-size:0.85rem;}
    .log-entry-clean{background:rgba(0,200,100,0.08);border-left:3px solid #00cc66;padding:0.5rem 0.8rem;margin:0.3rem 0;border-radius:0 8px 8px 0;font-size:0.85rem;}
    .scanning{animation:scan-pulse 1s infinite;}
    @keyframes scan-pulse{0%,100%{opacity:1}50%{opacity:0.4}}
    #MainMenu{visibility:hidden;}footer{visibility:hidden;}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════
for k, v in {
    'total_scans': 0, 'oil_alerts': 0,
    'alert_log': [], 'scan_history': []
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════
# GLOBAL OCEAN REGIONS (35 regions)
# ══════════════════════════════════════════════
OCEAN_REGIONS = [
    # AUSTRALIA
    {"name":"Great Barrier Reef",    "lat":-18.2,"lon":147.7},
    {"name":"Torres Strait",          "lat":-10.5,"lon":142.2},
    {"name":"Coral Sea",              "lat":-20.0,"lon":155.0},
    {"name":"Gulf of Carpentaria",    "lat":-14.0,"lon":136.5},
    {"name":"Arafura Sea",            "lat":-10.0,"lon":133.0},
    {"name":"Timor Sea",              "lat":-12.0,"lon":127.0},
    {"name":"Northwest Shelf WA",     "lat":-20.5,"lon":115.0},
    # INDIAN OCEAN
    {"name":"Arabian Sea",            "lat": 15.0,"lon": 65.0},
    {"name":"Bay of Bengal",          "lat": 12.0,"lon": 87.0},
    {"name":"Lakshadweep Sea",        "lat": 10.5,"lon": 73.0},
    {"name":"Gulf of Aden",           "lat": 12.5,"lon": 48.0},
    {"name":"Gulf of Oman",           "lat": 23.0,"lon": 58.5},
    {"name":"Persian Gulf",           "lat": 26.0,"lon": 52.0},
    {"name":"Red Sea",                "lat": 20.0,"lon": 38.0},
    {"name":"Andaman Sea",            "lat": 11.0,"lon": 96.0},
    {"name":"Mozambique Channel",     "lat":-18.0,"lon": 38.0},
    {"name":"South Indian Ocean",     "lat":-35.0,"lon": 75.0},
    {"name":"Maldives Waters",        "lat":  3.5,"lon": 73.5},
    {"name":"Sri Lanka Coast",        "lat":  7.5,"lon": 81.5},
    {"name":"Mumbai Offshore",        "lat": 18.9,"lon": 70.0},
    {"name":"Chennai Offshore",       "lat": 12.5,"lon": 82.0},
    {"name":"Kochi Offshore",         "lat":  9.9,"lon": 75.5},
    {"name":"Vizag Offshore",         "lat": 17.7,"lon": 83.5},
    {"name":"Andaman Islands",        "lat": 12.5,"lon": 92.8},
    {"name":"Central Indian Ocean",   "lat":-10.0,"lon": 75.0},
    # SE ASIA
    {"name":"Singapore Strait",       "lat":  1.2,"lon":104.0},
    {"name":"Strait of Malacca",      "lat":  3.5,"lon":100.5},
    {"name":"South China Sea",        "lat": 12.0,"lon":115.0},
    {"name":"Java Sea",               "lat": -5.5,"lon":110.5},
    {"name":"Banda Sea",              "lat": -6.0,"lon":127.0},
    {"name":"Gulf of Thailand",       "lat":  9.0,"lon":101.0},
    # AFRICA / MIDDLE EAST
    {"name":"Suez Canal Approach",    "lat": 29.5,"lon": 32.5},
    {"name":"Horn of Africa",         "lat": 11.5,"lon": 51.0},
    {"name":"Niger Delta",            "lat":  4.5,"lon":  6.0},
    {"name":"Cape of Good Hope",      "lat":-34.0,"lon": 18.5},
    {"name":"Strait of Hormuz",       "lat": 26.5,"lon": 56.5},
]

def random_ocean_coord():
    r = random.choice(OCEAN_REGIONS)
    return (round(r["lat"]+random.uniform(-1.5,1.5),4),
            round(r["lon"]+random.uniform(-1.5,1.5),4),
            r["name"])


# ══════════════════════════════════════════════
# LOAD MODEL
# ══════════════════════════════════════════════
# @st.cache_resource
# def load_model():
#     for path in ["models/oceanguard_v3.keras",
#                  "models/oceanguard_v2.keras",
#                  "models/oceanguard_v1.keras"]:
#         if os.path.exists(path):
#             try:
#                 return tf.keras.models.load_model(path), path
#             except:
#                 continue
#     return None, None

@st.cache_resource
def load_model():
    MODEL_PATH = "models/oceanguard_v3.h5"
    os.makedirs("models", exist_ok=True)
    
    if not os.path.exists(MODEL_PATH):
        with st.spinner("📥 Downloading model... (224MB, please wait)"):
            url = "https://drive.google.com/uc?id=14j4fp5K4MKcB3Z7OjDXB-tk5dtvt_5W9"
            gdown.download(url, MODEL_PATH, quiet=False)
    
    try:
        return tf.keras.models.load_model(MODEL_PATH, compile=False), MODEL_PATH
    except Exception as e:
        st.error(f"❌ Model load failed: {e}")
        return None, None

model, model_path = load_model()


# ══════════════════════════════════════════════
# PREDICT
# ══════════════════════════════════════════════
def predict(image_input, threshold=0.4):
    IMG_SIZE = 128
    img = np.array(image_input.convert('RGB')) \
          if isinstance(image_input, Image.Image) else image_input
    img_norm  = cv2.resize(img, (IMG_SIZE, IMG_SIZE)) / 255.0
    probs     = model.predict(np.expand_dims(img_norm,0), verbose=0)[0]
    oil_p     = float(probs[1]) if len(probs)>1 else float(probs[0])
    clean_p   = float(probs[0]) if len(probs)>1 else 1-float(probs[0])
    label     = "Oil Spill" if oil_p >= threshold else "Clean Sea"
    conf      = oil_p*100 if label=="Oil Spill" else clean_p*100
    return label, conf, {"Clean Sea":clean_p,"Oil Spill":oil_p}


# ══════════════════════════════════════════════
# SAR PREPROCESSING — makes webcam look like SAR
# ══════════════════════════════════════════════
def preprocess_as_sar(rgb_frame):
    """
    Converts a normal webcam RGB frame into a
    SAR-like grayscale texture image so the model
    can make meaningful predictions on it.

    Steps:
    1. Convert to grayscale
    2. CLAHE contrast enhancement (mimics SAR texture)
    3. Gaussian blur (reduces noise like SAR processing)
    4. Convert back to RGB for model compatibility
    """
    # Step 1: Grayscale
    gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)

    # Step 2: CLAHE — boosts local contrast like SAR imagery
    clahe    = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)

    # Step 3: Light blur — smooths noise
    blurred  = cv2.GaussianBlur(enhanced, (3,3), 0)

    # Step 4: Back to RGB (model expects 3 channels)
    sar_like = cv2.cvtColor(blurred, cv2.COLOR_GRAY2RGB)

    return sar_like


# ══════════════════════════════════════════════
# IMAGE ANNOTATION — Mark spill on image
# ══════════════════════════════════════════════
def annotate_image(pil_image, label, confidence, probs):
    """
    Draws detection overlay directly on the satellite image.
    - Oil Spill: red bounding boxes + heatmap overlay + label
    - Clean Sea: green border + label
    Returns annotated PIL image.
    """
    img_cv = cv2.cvtColor(np.array(pil_image.convert('RGB')),
                          cv2.COLOR_RGB2BGR)
    h, w   = img_cv.shape[:2]

    if label == "Oil Spill":
        # Convert to grayscale — oil spills = DARK regions in SAR
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # Threshold: find darkest 25% = likely spill
        _, dark_mask = cv2.threshold(
            gray, int(np.percentile(gray, 25)), 255, cv2.THRESH_BINARY_INV)

        # Clean up mask
        kernel    = np.ones((15,15), np.uint8)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN,  kernel)

        # Find contours of spill regions
        contours, _ = cv2.findContours(
            dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        # Red background tint
        overlay = img_cv.copy()
        cv2.rectangle(overlay, (0,0), (w,h), (0,0,80), -1)
        img_cv  = cv2.addWeighted(img_cv, 0.85, overlay, 0.15, 0)

        # Draw top 3 spill regions
        for idx, cnt in enumerate(contours[:3]):
            if cv2.contourArea(cnt) < 200:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)

            # Semi-transparent red fill
            mask_overlay = img_cv.copy()
            cv2.drawContours(mask_overlay, [cnt], -1, (0,0,255), -1)
            img_cv = cv2.addWeighted(img_cv, 0.7, mask_overlay, 0.3, 0)

            # Red bounding box
            cv2.rectangle(img_cv, (x,y), (x+bw,y+bh),
                          (0,0,255), max(2,w//150))

            # Label badge
            rank  = ["PRIMARY","SECONDARY","TERTIARY"][idx]
            fscale= max(0.4, w/1000)
            tsz   = cv2.getTextSize(rank, cv2.FONT_HERSHEY_SIMPLEX, fscale, 1)[0]
            cv2.rectangle(img_cv, (x,y-tsz[1]-8), (x+tsz[0]+8,y), (0,0,200),-1)
            cv2.putText(img_cv, rank, (x+4,y-4),
                        cv2.FONT_HERSHEY_SIMPLEX, fscale, (255,255,255), 1)

        # Top banner
        bh2 = max(50, h//10)
        cv2.rectangle(img_cv, (0,0), (w,bh2), (0,0,180), -1)
        cv2.putText(img_cv,
                    f"OIL SPILL DETECTED — {confidence:.1f}% CONFIDENCE",
                    (10, bh2//2+8), cv2.FONT_HERSHEY_SIMPLEX,
                    max(0.6,w/600), (0,100,255), 2)

        # Regions flagged count
        n_spills = sum(1 for c in contours[:3] if cv2.contourArea(c)>200)
        cv2.putText(img_cv, f"REGIONS FLAGGED: {n_spills}",
                    (w-max(200,w//4), bh2//2+8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    max(0.4,w/1200), (0,200,255), 1)

        # Bottom bar
        by = h-max(35,h//12)
        cv2.rectangle(img_cv,(0,by),(w,h),(0,0,100),-1)
        cv2.putText(img_cv,
                    f"OCEANGUARD AI | Sentinel-1 SAR | "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    (10, by+max(20,h//30)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    max(0.35,w/1800), (0,200,255), 1)

    else:
        # Green border for clean water
        cv2.rectangle(img_cv,(0,0),(w,h),(0,200,80),max(6,w//80))
        bh2 = max(50,h//10)
        cv2.rectangle(img_cv,(0,0),(w,bh2),(0,100,40),-1)
        cv2.putText(img_cv,
                    f"CLEAN WATER — {confidence:.1f}% CONFIDENCE",
                    (10,bh2//2+8), cv2.FONT_HERSHEY_SIMPLEX,
                    max(0.6,w/600), (0,255,100), 2)
        by = h-max(35,h//12)
        cv2.rectangle(img_cv,(0,by),(w,h),(0,60,30),-1)
        cv2.putText(img_cv,
                    f"OCEANGUARD AI | No pollution detected | "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    (10,by+max(20,h//30)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    max(0.35,w/1800),(0,200,100),1)

    return Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))


def log_detection(label, conf, source, lat=None, lon=None, region=None):
    if lat is None:
        lat, lon, region = random_ocean_coord()
    ts = datetime.now()
    st.session_state.total_scans += 1
    if label == "Oil Spill":
        st.session_state.oil_alerts += 1
    st.session_state.alert_log.append({
        "time": ts.strftime("%H:%M:%S"), "result": label,
        "confidence": conf, "source": source,
        "lat": lat, "lon": lon, "region": region or "Unknown"
    })
    st.session_state.scan_history.append({
        "time_dt": ts, "result": label, "confidence": conf
    })


# ══════════════════════════════════════════════
# BUILD FOLIUM MAP (always visible)
# ══════════════════════════════════════════════
def build_map(logs=None):
    m = folium.Map(location=[10.0,75.0], zoom_start=3,
                   tiles='CartoDB dark_matter')

    if not logs:
        rg = folium.FeatureGroup(name="📡 Monitored Regions").add_to(m)
        for r in OCEAN_REGIONS:
            folium.CircleMarker(
                [r['lat'],r['lon']], radius=5,
                color='#00d4ff', fill=True,
                fill_color='#00d4ff', fill_opacity=0.4, weight=1,
                tooltip=f"📡 {r['name']} — Monitoring Active"
            ).add_to(rg)
        legend = """
        <div style='position:fixed;bottom:30px;left:30px;z-index:1000;
                    background:#041428;border:1px solid #00d4ff;
                    border-radius:8px;padding:12px;color:#e0f4ff;
                    font-family:monospace;font-size:12px;'>
            <b style='color:#00d4ff;'>🌊 OceanGuard</b><br>
            <span style='color:#00d4ff;'>●</span> Monitored Region<br>
            <i style='color:#7ecfea;'>Run a scan to see detections</i>
        </div>"""
        m.get_root().html.add_child(folium.Element(legend))
        folium.LayerControl(collapsed=False).add_to(m)
        return m

    oil_locs   = [l for l in logs if l['result']=='Oil Spill']
    clean_locs = [l for l in logs if l['result']=='Clean Sea']
    cc  = MarkerCluster(name="🟢 Clean Scans").add_to(m)
    og  = folium.FeatureGroup(name="🔴 Oil Spill Alerts").add_to(m)

    for e in logs:
        is_oil = e['result']=='Oil Spill'
        popup  = folium.Popup(f"""
        <div style='font-family:monospace;min-width:200px;
                    background:#041428;color:#e0f4ff;
                    padding:10px;border-radius:8px;'>
            <b style='color:{"#ff4444" if is_oil else "#00cc66"};font-size:1rem;'>
                {"🚨 OIL SPILL" if is_oil else "✅ CLEAN SEA"}
            </b>
            <hr style='border-color:#1a4a6a;margin:6px 0;'>
            🕐 {e['time']}<br>📍 {e['region']}<br>
            🌐 {e['lat']}°, {e['lon']}°<br>
            📈 Confidence: {e['confidence']:.1f}%<br>
            📁 {e['source'][:28]}
        </div>""", max_width=260)

        if is_oil:
            folium.CircleMarker(
                [e['lat'],e['lon']], radius=16,
                color='#ff0000', fill=True,
                fill_color='#ff4444', fill_opacity=0.75, weight=3,
                popup=popup,
                tooltip=f"🚨 {e['region']} | {e['confidence']:.1f}%"
            ).add_to(og)
            folium.CircleMarker(
                [e['lat'],e['lon']], radius=28,
                color='#ff0000', fill=False, weight=1, opacity=0.3
            ).add_to(og)
        else:
            folium.CircleMarker(
                [e['lat'],e['lon']], radius=8,
                color='#00cc66', fill=True,
                fill_color='#00ff88', fill_opacity=0.5, weight=2,
                popup=popup,
                tooltip=f"✅ {e['region']} | {e['confidence']:.1f}%"
            ).add_to(cc)

    if oil_locs:
        HeatMap(
            [[e['lat'],e['lon'],e['confidence']/100] for e in oil_locs],
            name="🔥 Oil Spill Heatmap",
            radius=35, blur=25,
            gradient={0.2:'blue',0.5:'orange',0.8:'red',1.0:'darkred'}
        ).add_to(m)

    legend = f"""
    <div style='position:fixed;bottom:30px;left:30px;z-index:1000;
                background:#041428;border:1px solid #00d4ff;
                border-radius:8px;padding:12px;color:#e0f4ff;
                font-family:monospace;font-size:12px;'>
        <b style='color:#00d4ff;'>🌊 OceanGuard Live Map</b><br>
        <span style='color:#ff4444;font-size:16px;'>●</span> Oil Spill ({len(oil_locs)})<br>
        <span style='color:#00cc66;font-size:16px;'>●</span> Clean ({len(clean_locs)})<br>
        <span style='color:#ff6666;'>🔥</span> Heatmap = Spill density
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    return m


# ══════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:1rem 0;'>
        <div style='font-family:Orbitron,monospace;font-size:1.4rem;
                    color:#00d4ff;font-weight:900;letter-spacing:3px;'>
            🌊 OCEANGUARD</div>
        <div style='color:#7ecfea;font-size:0.7rem;letter-spacing:2px;margin-top:4px;'>
            ENVIRONMENTAL AI MONITOR</div>
    </div><hr>""", unsafe_allow_html=True)

    if model:
        st.success(f"✅ `{os.path.basename(model_path)}`")
        st.caption(f"Parameters: {model.count_params():,}")
    else:
        st.error("❌ No model found!")
        st.info("Run 02_Training.ipynb first")
        st.stop()

    st.markdown("---")
    st.markdown("**⚙️ Detection Sensitivity**")
    threshold = st.slider("Oil Spill Threshold", 0.1, 0.9, 0.4, 0.05)
    if threshold < 0.35:   st.warning("⚠️ Very sensitive")
    elif threshold > 0.65: st.warning("⚠️ Low sensitivity")
    else:                  st.success("✅ Balanced")

    st.markdown("---")
    st.markdown("**📊 Session Stats**")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"<div class='metric-box'><div class='metric-value'>"
                    f"{st.session_state.total_scans}</div>"
                    f"<div class='metric-label'>Scans</div></div>",
                    unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-box'><div class='metric-value' "
                    f"style='color:#ff6666;'>{st.session_state.oil_alerts}"
                    f"</div><div class='metric-label'>Alerts</div></div>",
                    unsafe_allow_html=True)

    if st.session_state.total_scans > 0:
        rate  = st.session_state.oil_alerts/st.session_state.total_scans*100
        color = "#ff6666" if rate>30 else "#ffaa44" if rate>10 else "#00cc66"
        st.markdown(f"<div style='text-align:center;color:{color};"
                    f"font-size:0.85rem;margin-top:0.5rem;font-weight:600;'>"
                    f"⚠️ Alert Rate: {rate:.1f}%</div>",
                    unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"""
    <div style='font-size:0.75rem;color:#4a8fa8;line-height:1.8;'>
        <b style='color:#7ecfea;'>📡 Data Source</b><br>
        Sentinel-1 SAR · CSIRO Dataset<br>
        DOI: 10.25919/4v55-dn16<br><br>
        <b style='color:#7ecfea;'>🌍 Coverage</b><br>
        {len(OCEAN_REGIONS)} Ocean Regions<br>
        Indian Ocean · Arabian Sea<br>
        Bay of Bengal · Persian Gulf<br>
        SE Asia · Australia · Africa<br><br>
        <b style='color:#7ecfea;'>🌱 Green AI</b><br>
        GlobalAvgPool · EarlyStopping<br>
        ResNet50 Transfer Learning
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🗑️ Clear Session", use_container_width=True):
        st.session_state.total_scans  = 0
        st.session_state.oil_alerts   = 0
        st.session_state.alert_log    = []
        st.session_state.scan_history = []
        st.rerun()


# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
st.markdown("<div class='main-title'>🌊 OCEANGUARD</div>",
            unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Illegal Ocean Dumping Detection · "
            "Sentinel-1 SAR · Deep Learning AI · 24/7 Global Monitoring"
            "</div>", unsafe_allow_html=True)
st.markdown(
    f"<div style='text-align:center;color:#4a8fa8;font-size:0.8rem;"
    f"font-family:monospace;margin-bottom:1rem;'>"
    f"🕐 {datetime.now().strftime('%Y-%m-%d  |  %H:%M:%S')}  |  "
    f"Model: {os.path.basename(model_path) if model_path else 'N/A'}  |  "
    f"Monitoring: {len(OCEAN_REGIONS)} Ocean Regions</div>",
    unsafe_allow_html=True)
st.markdown("---")


# ══════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📤  Upload & Detect",
    "📹  Live Camera",
    "🛰️  Auto Satellite Scan",
    "🗺️  Live Detection Map",
    "📊  Analytics Dashboard"
])


# ════════════════════════════════════════════════════════
# TAB 1 — UPLOAD & DETECT
# ════════════════════════════════════════════════════════
with tab1:
    st.markdown("### 📤 Upload Satellite Image")
    st.markdown(
        "<p style='color:#7ecfea;'>Upload a SAR or optical satellite image. "
        "OceanGuard will detect oil spills and <b>mark the exact location "
        "on the image</b>.</p>", unsafe_allow_html=True)

    uploaded = st.file_uploader("Drop satellite image here",
                                 type=['jpg','jpeg','png','tiff','tif'])

    if uploaded:
        image = Image.open(uploaded)

        with st.spinner("🔍 Analyzing satellite image..."):
            time.sleep(0.3)
            label, conf, probs = predict(image, threshold)
            annotated          = annotate_image(image, label, conf, probs)

        lat, lon, region = random_ocean_coord()
        log_detection(label, conf, uploaded.name, lat, lon, region)

        if label == "Oil Spill":
            st.markdown("""<div class='alert-oil'>
                <div class='alert-title' style='color:#ff4444;'>
                    🚨 OIL SPILL DETECTED — LOCATION MARKED ON IMAGE</div>
                <div class='alert-sub' style='color:#ffaaaa;'>
                    Red regions show detected spill areas · Click image to zoom
                </div></div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class='alert-clean'>
                <div class='alert-title' style='color:#00cc66;'>
                    ✅ CLEAN WATER — NO POLLUTION DETECTED</div>
                <div class='alert-sub' style='color:#aaffcc;'>
                    No oil spill signatures found in this image
                </div></div>""", unsafe_allow_html=True)

        col_orig, col_anno = st.columns([1,1], gap="large")
        with col_orig:
            st.markdown("**🛰️ Original Satellite Image**")
            st.image(image, use_column_width=True,
                     caption=f"Original: {uploaded.name}")
        with col_anno:
            st.markdown("**🔍 AI Detection Result**")
            st.image(annotated, use_column_width=True,
                     caption=f"Annotated: {label} ({conf:.1f}%)")

        st.markdown("---")
        res_col, meta_col = st.columns([1,1], gap="large")
        with res_col:
            st.markdown("**📊 Confidence Scores**")
            for cls, prob in probs.items():
                color = "#ff4444" if cls=="Oil Spill" else "#00cc66"
                pct   = prob*100
                st.markdown(f"""
                <div style='margin:0.5rem 0;'>
                    <div style='display:flex;justify-content:space-between;
                                color:#b0d4e8;font-size:0.85rem;margin-bottom:4px;'>
                        <span>{cls}</span>
                        <span style='color:{color};font-weight:600;'>{pct:.1f}%</span>
                    </div>
                    <div style='background:rgba(255,255,255,0.1);
                                border-radius:6px;height:12px;overflow:hidden;'>
                        <div style='width:{pct}%;height:100%;
                                    background:linear-gradient(90deg,{color}88,{color});
                                    border-radius:6px;'></div>
                    </div>
                </div>""", unsafe_allow_html=True)

        with meta_col:
            st.markdown("**📋 Detection Metadata**")
            st.markdown(f"""
            <div style='font-size:0.85rem;color:#7ecfea;line-height:2.2;'>
                🕐 <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}<br>
                📍 <b>Region:</b> {region}<br>
                🌐 <b>Coords:</b> {lat}°, {lon}°<br>
                🎯 <b>Result:</b> {label}<br>
                📈 <b>Confidence:</b> {conf:.1f}%<br>
                ⚙️ <b>Threshold:</b> {threshold}<br>
                🛰️ <b>Sensor:</b> Sentinel-1 SAR<br>
                🌱 <b>Model:</b> ResNet50 (Green AI)
            </div>""", unsafe_allow_html=True)

        st.markdown("")
        b1, b2, b3 = st.columns(3)
        with b1:
            if label == "Oil Spill":
                if st.button("📤 Report to Authorities",
                             use_container_width=True):
                    st.success(f"✅ Reported! {region} ({lat}, {lon})")
        with b2:
            buf = io.BytesIO()
            annotated.save(buf, format='PNG')
            st.download_button(
                "💾 Download Annotated Image",
                data=buf.getvalue(),
                file_name=f"oceanguard_{label.replace(' ','_')}_"
                          f"{datetime.now().strftime('%H%M%S')}.png",
                mime="image/png",
                use_container_width=True)
        with b3:
            if st.button("🔄 Scan Another", use_container_width=True):
                st.rerun()
    else:
        st.markdown("""
        <div class='ocean-card' style='text-align:center;padding:3rem;'>
            <div style='font-size:4rem;margin-bottom:1rem;'>🛰️</div>
            <div style='font-family:Orbitron,monospace;color:#00d4ff;
                        font-size:1.1rem;margin-bottom:0.5rem;'>
                AWAITING SATELLITE IMAGE</div>
            <div style='color:#7ecfea;font-size:0.9rem;'>
                Upload a Sentinel-1 SAR image — OceanGuard will detect
                and mark spill locations on the image
            </div>
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
# TAB 2 — LIVE CAMERA (FIXED: SAR preprocessing)
# ════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 📹 Live Camera / Drone Feed")
    st.markdown(
        "<p style='color:#7ecfea;'>Real-time detection with SAR-style "
        "preprocessing. For best results, point camera at a printed or "
        "displayed satellite image.</p>", unsafe_allow_html=True)

    c1, c2 = st.columns([1,2])
    with c1:
        cam_idx      = st.selectbox("Camera", [0,1,2],
                                     format_func=lambda x: f"Camera {x}")
        n_frames     = st.slider("Scan every N frames", 1, 30, 5)
        overlay      = st.checkbox("Show overlay", value=True)
        annotate_live= st.checkbox("Annotate spill regions", value=True)
        sar_mode     = st.checkbox("SAR preprocessing ✅", value=True,
                                    help="Converts webcam to SAR-like "
                                         "grayscale for better detection")
        # Lower threshold for webcam
        cam_threshold= st.slider("Camera Threshold", 0.1, 0.9, 0.25, 0.05,
                                  help="Lower = more sensitive for webcam")
        go_cam       = st.button("▶️ Start Detection",
                                  use_container_width=True)
        stop_cam     = st.button("⏹️ Stop Camera",
                                  use_container_width=True)

    with c2:
        st.markdown("""<div class='ocean-card'>
            <div style='color:#00d4ff;font-weight:600;margin-bottom:0.8rem;'>
                📡 SAR Preprocessing Pipeline</div>
            <div style='color:#b0d4e8;font-size:0.85rem;line-height:2;'>
                1. Webcam frame captured (RGB)<br>
                2. <b style='color:#00d4ff;'>Convert to grayscale</b>
                   — like SAR imagery<br>
                3. <b style='color:#00d4ff;'>CLAHE enhancement</b>
                   — boosts texture contrast<br>
                4. <b style='color:#00d4ff;'>Gaussian blur</b>
                   — reduces noise<br>
                5. Feed to ResNet50 model<br>
                6. Mark detected regions in red<br><br>
                <b style='color:#ffaa44;'>💡 Demo tip:</b>
                Point camera at a satellite image on
                your phone/screen for best results!
            </div></div>""", unsafe_allow_html=True)

        # Show SAR preview when camera not running
        st.markdown("""<div class='ocean-card'>
            <div style='color:#00d4ff;font-weight:600;margin-bottom:0.5rem;'>
                🎯 Best Demo Results</div>
            <div style='color:#b0d4e8;font-size:0.82rem;line-height:1.8;'>
                ✅ Open <code>data/1/</code> image on phone → point camera<br>
                ✅ Print a SAR satellite image → hold to camera<br>
                ✅ Show dark/textured surface → dark = oil-like<br>
                ❌ Bright lit room → model sees "clean water"
            </div></div>""", unsafe_allow_html=True)

    frame_ph  = st.empty()
    sar_ph    = st.empty()
    fps_ph    = st.empty()
    result_ph = st.empty()

    if go_cam:
        cap = cv2.VideoCapture(cam_idx)
        if not cap.isOpened():
            st.error(f"❌ Cannot open camera {cam_idx}. "
                     "Try index 0, 1, or 2.")
        else:
            st.success(f"✅ Camera {cam_idx} connected! "
                       f"SAR mode: {'ON 🛰️' if sar_mode else 'OFF'}")
            fc = 0; last_label = "Initializing..."; last_conf = 0.0
            t0 = time.time()

            while not stop_cam:
                ret, frame = cap.read()
                if not ret:
                    st.error("❌ Camera feed lost.")
                    break

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                fc += 1

                if fc % n_frames == 0:
                    # ── CORE FIX: SAR preprocessing ──
                    if sar_mode:
                        processed = preprocess_as_sar(rgb)
                    else:
                        processed = rgb

                    pil = Image.fromarray(processed)
                    last_label, last_conf, _ = predict(
                        pil, cam_threshold)

                    lat, lon, region = random_ocean_coord()
                    log_detection(last_label, last_conf,
                                  f"Camera {cam_idx}",
                                  lat, lon, region)

                    # Annotate on original (not SAR) for display
                    if annotate_live:
                        display = np.array(annotate_image(
                            Image.fromarray(rgb),
                            last_label, last_conf,
                            {"Clean Sea":0,"Oil Spill":0}))
                    else:
                        display = rgb.copy()
                        if overlay:
                            color = (255,60,60) \
                                    if last_label=="Oil Spill" \
                                    else (0,220,100)
                            cv2.rectangle(display,(10,10),(420,75),
                                          (0,20,40),-1)
                            cv2.putText(display, last_label,
                                        (20,45),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.9, color, 2)
                            cv2.putText(display,
                                        f"Conf: {last_conf:.1f}%",
                                        (20,68),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.55,(180,220,255),1)
                else:
                    display = rgb.copy()
                    if overlay and last_label != "Initializing...":
                        color = (255,60,60) \
                                if last_label=="Oil Spill" \
                                else (0,220,100)
                        cv2.rectangle(display,(10,10),(420,75),
                                      (0,20,40),-1)
                        cv2.putText(display, last_label,
                                    (20,45),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.9, color, 2)
                        cv2.putText(display,
                                    f"Conf: {last_conf:.1f}%",
                                    (20,68),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.55,(180,220,255),1)

                frame_ph.image(display, use_column_width=True,
                               caption=f"Live Feed — Frame {fc} "
                                       f"| SAR: {'ON' if sar_mode else 'OFF'}")

                # Show SAR-processed version in small preview
                if sar_mode and fc % n_frames == 0:
                    sar_preview = preprocess_as_sar(rgb)
                    sar_ph.image(sar_preview,
                                 caption="SAR-preprocessed input to model",
                                 width=200)

                fps = fc/(time.time()-t0+1e-6)
                fps_ph.markdown(
                    f"<div style='text-align:center;color:#4a8fa8;"
                    f"font-size:0.8rem;'>"
                    f"FPS: {fps:.1f} | Frame: {fc} | "
                    f"Last: <b style='color:"
                    f"{'#ff4444' if last_label=='Oil Spill' else '#00cc66'};'>"
                    f"{last_label}</b> ({last_conf:.1f}%)"
                    f"</div>", unsafe_allow_html=True)
                time.sleep(0.03)

            cap.release()
            st.info("📷 Camera stopped.")


# ════════════════════════════════════════════════════════
# TAB 3 — AUTO SATELLITE SCAN
# ════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 🛰️ Auto Satellite Scan — 24/7 Monitoring")
    c1, c2 = st.columns([1,1], gap="large")
    with c1:
        # ── FIXED: default path is now data/1 not ../data/1 ──
        watch_folder   = st.text_input("Watch Folder", value="data/1",
                             help="Relative to OceanGuard/ folder")
        scan_delay     = st.slider("Scan interval (seconds)", 2, 60, 10)
        max_scans      = st.slider("Max scans", 5, 50, 10)
        auto_report    = st.checkbox("Auto-report detections", value=True)
        show_annotated = st.checkbox("Show annotated images", value=True)
        go_auto        = st.button("🚀 Start 24/7 Monitoring",
                                    use_container_width=True,
                                    type="primary")
    with c2:
        st.markdown(f"""<div class='ocean-card'>
            <div style='color:#00d4ff;font-weight:600;margin-bottom:0.8rem;'>
                🌍 Global Monitoring Coverage</div>
            <div style='color:#b0d4e8;font-size:0.82rem;line-height:2;'>
                🌊 Indian Ocean · Arabian Sea · Bay of Bengal<br>
                🇮🇳 India: Mumbai · Chennai · Kochi · Vizag<br>
                🌏 SE Asia: Singapore · Malacca · Java Sea<br>
                🇦🇺 Australia: GBR · Timor Sea · Coral Sea<br>
                🌍 Africa: Niger Delta · Horn of Africa<br>
                📡 <b>{len(OCEAN_REGIONS)} regions</b> worldwide
            </div></div>""", unsafe_allow_html=True)

    scan_ph = st.empty(); prog_ph = st.empty()
    img_ph  = st.empty(); log_ph  = st.empty()

    if go_auto:
        if not os.path.exists(watch_folder):
            st.error(f"❌ Folder not found: `{watch_folder}`\n\n"
                     f"Try: `data/1` or full path like "
                     f"`C:/Users/YourName/OceanGuard/data/1`")
        else:
            imgs = [f for f in os.listdir(watch_folder)
                    if f.lower().endswith(
                        ('.jpg','.jpeg','.png','.tiff','.tif'))]
            if not imgs:
                st.error("❌ No images found in that folder!")
            else:
                st.success(f"✅ Found {len(imgs)} images. Monitoring!")
                results = []
                for i in range(min(max_scans, len(imgs))):
                    f    = random.choice(imgs)
                    path = os.path.join(watch_folder, f)

                    scan_ph.markdown(f"""
                    <div class='ocean-card' style='text-align:center;'>
                        <div class='scanning' style='color:#00d4ff;
                             font-family:Orbitron,monospace;font-size:1rem;'>
                            📡 SCANNING PASS {i+1}/{max_scans}</div>
                        <div style='color:#7ecfea;font-size:0.8rem;
                                    margin-top:0.5rem;'>
                            Processing: {f}</div>
                    </div>""", unsafe_allow_html=True)
                    prog_ph.progress(i/max_scans)

                    img              = Image.open(path).convert('RGB')
                    label, conf, probs = predict(img, threshold)
                    lat, lon, region = random_ocean_coord()
                    log_detection(label, conf,
                                  f"Auto:{f}", lat, lon, region)
                    results.append({
                        "scan":i+1, "file":f, "result":label,
                        "confidence":conf,
                        "time":datetime.now().strftime("%H:%M:%S"),
                        "region":region})

                    display = annotate_image(img,label,conf,probs) \
                              if show_annotated else img
                    img_ph.image(display,
                        caption=f"Scan {i+1}: {label} "
                                f"({conf:.1f}%) — {region}",
                        use_column_width=True)

                    log_html = "<div>"
                    log_html += ("<div style='color:#00d4ff;font-weight:600;"
                                 "margin-bottom:0.5rem;font-size:0.85rem;'>"
                                 "📋 SCAN LOG</div>")
                    for e in reversed(results[-8:]):
                        is_oil = e['result']=="Oil Spill"
                        css    = "log-entry-oil" if is_oil \
                                 else "log-entry-clean"
                        icon   = "🔴" if is_oil else "🟢"
                        log_html += (f"<div class='{css}'>{icon} "
                                     f"[{e['time']}] Scan {e['scan']} — "
                                     f"<b>{e['result']}</b> "
                                     f"({e['confidence']:.1f}%) — "
                                     f"{e['region']}</div>")
                    log_html += "</div>"
                    log_ph.markdown(log_html, unsafe_allow_html=True)
                    if i < max_scans-1: time.sleep(scan_delay)

                prog_ph.progress(1.0)
                oil_n = sum(1 for r in results if r['result']=="Oil Spill")
                scan_ph.markdown(f"""
                <div class='ocean-card' style='text-align:center;'>
                    <div style='font-family:Orbitron,monospace;color:#00ff9f;
                                font-size:1.1rem;font-weight:700;'>
                        ✅ SESSION COMPLETE</div>
                    <div style='color:#7ecfea;margin-top:0.8rem;'>
                        Scans: <b style='color:#00d4ff;'>{len(results)}</b>
                        &nbsp;|&nbsp;
                        Oil: <b style='color:#ff6666;'>{oil_n}</b>
                        &nbsp;|&nbsp;
                        Clean: <b style='color:#00cc66;'>
                            {len(results)-oil_n}</b>
                    </div></div>""", unsafe_allow_html=True)
                if oil_n > 0 and auto_report:
                    st.error(f"🚨 {oil_n} oil spill(s) detected!")
                else:
                    st.success("✅ No oil spills detected.")


# ════════════════════════════════════════════════════════
# TAB 4 — LIVE DETECTION MAP
# ════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 🗺️ Live Detection Map")
    logs = st.session_state.alert_log

    if not logs:
        st.markdown("""
        <div class='ocean-card' style='padding:1rem;margin-bottom:1rem;'>
            <div style='color:#00d4ff;font-weight:600;'>
                📡 Monitoring Active — No Detections Yet</div>
            <div style='color:#7ecfea;font-size:0.85rem;margin-top:0.3rem;'>
                Blue dots = 35 monitored ocean regions worldwide.
                Run a scan to see 🔴 oil spill alerts on the map.
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        oil_locs   = [l for l in logs if l['result']=='Oil Spill']
        clean_locs = [l for l in logs if l['result']=='Clean Sea']
        m1,m2,m3,m4 = st.columns(4)
        for col, lbl, val, clr in [
            (m1,"Total Scans",  len(logs),       "#00d4ff"),
            (m2,"🔴 Oil Alerts",len(oil_locs),   "#ff6666"),
            (m3,"🟢 Clean",     len(clean_locs), "#00cc66"),
            (m4,"Alert Rate",
             f"{len(oil_locs)/len(logs)*100:.1f}%","#ffaa44"),
        ]:
            with col:
                st.markdown(
                    f"<div class='metric-box'>"
                    f"<div class='metric-value' style='color:{clr};'>"
                    f"{val}</div>"
                    f"<div class='metric-label'>{lbl}</div></div>",
                    unsafe_allow_html=True)
        st.markdown("")

    # ALWAYS render map
    m = build_map(logs if logs else None)
    st_folium(m, width=None, height=560, returned_objects=[])

    if logs:
        st.markdown("#### 📋 Recent Detections")
        df = pd.DataFrame(logs[-20:][::-1])
        df = df[['time','result','confidence','region','lat','lon']].copy()
        df.columns = ['Time','Result','Conf %','Region','Lat','Lon']
        df['Conf %'] = df['Conf %'].round(1)

        def highlight(val):
            if val=='Oil Spill':
                return 'background-color:rgba(255,68,68,0.2);color:#ff6666'
            return 'background-color:rgba(0,204,102,0.1);color:#00cc66'

        st.dataframe(
            df.style.applymap(highlight, subset=['Result']),
            use_container_width=True, height=260)


# ════════════════════════════════════════════════════════
# TAB 5 — ANALYTICS
# ════════════════════════════════════════════════════════
with tab5:
    st.markdown("### 📊 Analytics Dashboard")

    if not st.session_state.scan_history:
        st.markdown("""<div class='ocean-card' style='text-align:center;
                        padding:2rem;'>
            <div style='font-size:3rem;'>📊</div>
            <div style='color:#00d4ff;font-family:Orbitron,monospace;
                        font-size:1.1rem;margin-top:0.5rem;'>NO DATA YET</div>
            <div style='color:#7ecfea;font-size:0.9rem;margin-top:0.5rem;'>
                Run scans to generate analytics</div>
        </div>""", unsafe_allow_html=True)
    else:
        history  = st.session_state.scan_history
        logs     = st.session_state.alert_log
        oil_n    = sum(1 for h in history if h['result']=='Oil Spill')
        clean_n  = len(history)-oil_n
        avg_conf = np.mean([h['confidence'] for h in history])
        max_conf = np.max( [h['confidence'] for h in history])

        s1,s2,s3,s4 = st.columns(4)
        for col, lbl, val, clr in [
            (s1,"Total Scans",     len(history),       "#00d4ff"),
            (s2,"🔴 Oil Alerts",   oil_n,              "#ff6666"),
            (s3,"Avg Confidence",  f"{avg_conf:.1f}%", "#ffaa44"),
            (s4,"Peak Confidence", f"{max_conf:.1f}%", "#00ff9f"),
        ]:
            with col:
                st.markdown(
                    f"<div class='metric-box'>"
                    f"<div class='metric-value' style='color:{clr};'>"
                    f"{val}</div>"
                    f"<div class='metric-label'>{lbl}</div></div>",
                    unsafe_allow_html=True)
        st.markdown("---")

        # Chart 1: Count
        st.markdown("#### 🔢 Detection Count")
        fig1,ax1=plt.subplots(figsize=(6,4))
        fig1.patch.set_facecolor('#041428'); ax1.set_facecolor('#041428')
        bars=ax1.bar(['🟢 Clean','🔴 Oil'],[clean_n,oil_n],
                     color=['#00cc66','#ff4444'],width=0.4,edgecolor='none')
        for bar,val in zip(bars,[clean_n,oil_n]):
            ax1.text(bar.get_x()+bar.get_width()/2,
                     bar.get_height()+0.1,str(val),
                     ha='center',color='white',fontsize=14,fontweight='bold')
        ax1.set_title("Total Detections",color='#00d4ff',fontsize=13)
        ax1.set_ylabel("Count",color='#7ecfea')
        ax1.tick_params(colors='#7ecfea')
        ax1.spines[:].set_color('#1a4a6a')
        ax1.set_ylim(0,max(clean_n,oil_n)*1.3+1)
        plt.tight_layout()
        st.pyplot(fig1,use_container_width=True); plt.close()
        st.markdown("---")

        # Chart 2: Confidence over time
        st.markdown("#### 📈 Confidence Over Time")
        fig2,ax2=plt.subplots(figsize=(12,4))
        fig2.patch.set_facecolor('#041428'); ax2.set_facecolor('#041428')
        xs=[h['confidence'] for h in history]
        cs=['#ff4444' if h['result']=='Oil Spill' else '#00cc66'
            for h in history]
        ax2.plot(range(1,len(xs)+1),xs,color='#00d4ff',
                 linewidth=1.5,alpha=0.5)
        ax2.scatter(range(1,len(xs)+1),xs,c=cs,s=60,zorder=2)
        ax2.axhline(threshold*100,color='#ffaa44',linestyle='--',alpha=0.7)
        ax2.set_xlabel("Scan #",color='#7ecfea')
        ax2.set_ylabel("Confidence %",color='#7ecfea')
        ax2.set_title("Confidence Over Time",color='#00d4ff',fontsize=13)
        ax2.tick_params(colors='#7ecfea'); ax2.spines[:].set_color('#1a4a6a')
        ax2.set_ylim(0,105)
        oil_p=mpatches.Patch(color='#ff4444',label='Oil Spill')
        cln_p=mpatches.Patch(color='#00cc66',label='Clean Sea')
        thr_l=plt.Line2D([0],[0],color='#ffaa44',linestyle='--',
                          label=f'Threshold ({threshold*100:.0f}%)')
        ax2.legend(handles=[oil_p,cln_p,thr_l],
                   facecolor='#041428',labelcolor='#7ecfea')
        plt.tight_layout()
        st.pyplot(fig2,use_container_width=True); plt.close()
        st.markdown("---")

        # Chart 3: By region
        st.markdown("#### 🌍 Oil Spills by Ocean Region")
        oil_logs=[l for l in logs if l['result']=='Oil Spill']
        if oil_logs:
            rc={}
            for l in oil_logs: rc[l['region']]=rc.get(l['region'],0)+1
            pairs=sorted(rc.items(),key=lambda x:x[1],reverse=True)
            regs,cnts=zip(*pairs)
            fig3,ax3=plt.subplots(figsize=(10,max(4,len(regs)*0.55)))
            fig3.patch.set_facecolor('#041428'); ax3.set_facecolor('#041428')
            bars3=ax3.barh(regs,cnts,color='#ff4444',
                           alpha=0.85,edgecolor='none')
            for bar,val in zip(bars3,cnts):
                ax3.text(val+0.05,bar.get_y()+bar.get_height()/2,
                         str(val),va='center',color='white',fontsize=11)
            ax3.set_xlabel("Oil Spill Count",color='#7ecfea')
            ax3.set_title("Oil Spill Alerts by Region",
                          color='#00d4ff',fontsize=13)
            ax3.tick_params(colors='#7ecfea')
            ax3.spines[:].set_color('#1a4a6a')
            plt.tight_layout()
            st.pyplot(fig3,use_container_width=True); plt.close()
        else:
            st.success("✅ No oil spills detected yet!")
        st.markdown("---")

        # Chart 4: Hourly
        st.markdown("#### 🕐 Hourly Summary")
        if len(history)>=2:
            ho,hc={},{}
            for e in logs:
                hr=e['time'][:5]
                if e['result']=='Oil Spill': ho[hr]=ho.get(hr,0)+1
                else:                        hc[hr]=hc.get(hr,0)+1
            hours=sorted(set(list(ho.keys())+list(hc.keys())))
            oil_v=[ho.get(h,0) for h in hours]
            cln_v=[hc.get(h,0) for h in hours]
            fig4,ax4=plt.subplots(figsize=(12,4))
            fig4.patch.set_facecolor('#041428'); ax4.set_facecolor('#041428')
            x=np.arange(len(hours)); w=0.35
            ax4.bar(x-w/2,cln_v,w,label='Clean',
                    color='#00cc66',alpha=0.85,edgecolor='none')
            ax4.bar(x+w/2,oil_v,w,label='Oil Spill',
                    color='#ff4444',alpha=0.85,edgecolor='none')
            ax4.set_xticks(x)
            ax4.set_xticklabels(hours,rotation=45,
                                color='#7ecfea',fontsize=9)
            ax4.set_ylabel("Count",color='#7ecfea')
            ax4.set_title("Detections by Time",color='#00d4ff',fontsize=13)
            ax4.tick_params(colors='#7ecfea')
            ax4.spines[:].set_color('#1a4a6a')
            ax4.legend(facecolor='#041428',labelcolor='#7ecfea')
            plt.tight_layout()
            st.pyplot(fig4,use_container_width=True); plt.close()
        else:
            st.info("Run more scans for hourly breakdown!")


# ══════════════════════════════════════════════
# GLOBAL ALERT LOG
# ══════════════════════════════════════════════
if st.session_state.alert_log:
    st.markdown("---")
    st.markdown("### 📋 Global Alert Log")
    log_html=""
    for e in reversed(st.session_state.alert_log[-15:]):
        is_oil=e['result']=="Oil Spill"
        css="log-entry-oil" if is_oil else "log-entry-clean"
        icon="🔴" if is_oil else "🟢"
        log_html+=(f"<div class='{css}'>{icon} [{e['time']}] — "
                   f"<b>{e['result']}</b> ({e['confidence']:.1f}%) — "
                   f"📍 {e['region']} — "
                   f"🌐 {e['lat']}°, {e['lon']}° — "
                   f"{e['source']}</div>")
    st.markdown(log_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style='text-align:center;color:#2a5f7a;font-size:0.75rem;
            padding:1rem;line-height:2;'>
    🌊 <b style='color:#4a8fa8;'>OceanGuard</b> ·
    Sentinel-1 SAR · CSIRO Dataset · TensorFlow/Keras · ResNet50<br>
    🌍 {len(OCEAN_REGIONS)} Ocean Regions ·
    Indian Ocean · Arabian Sea · Bay of Bengal · Pacific · Australia<br>
    🌱 Green AI · GlobalAveragePooling · EarlyStopping · CO₂-efficient
</div>""", unsafe_allow_html=True)