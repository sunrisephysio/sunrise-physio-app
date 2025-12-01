import streamlit as st
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import base64
try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    HAS_CALIB = True
except ImportError:
    HAS_CALIB = False

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"

# --- עיצוב מתוקן (טקסט שחור חזק) ---
def add_custom_design():
    st.markdown("""
        <style>
        /* כיוון ימין שמאל ורקע */
        .stApp { background-color: #f0f2f6; direction: rtl; }
        
        /* כל הטקסטים באפליקציה - שחור מוחלט */
        h1, h2, h3, h4, h5, h6, p, div, span, label, li, .stMarkdown {
            color: #000000 !important;
        }
        
        /* תפריטים וסרגל צד */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-left: 1px solid #ccc;
        }
        
        /* תיקון צבע טקסט בתוך Selectbox ו-Input */
        .stSelectbox div, .stTextInput input, .stTextArea textarea {
            color: #000000 !important;
            background-color: #ffffff !important;
            border-color: #999 !important;
        }
        
        /* כפתורים - עיצוב ברור */
        .stButton button {
            color: #ffffff !important;
            font-weight: bold;
            border-radius: 8px;
            border: none;
        }
        /* כפתור הקלטה - כתום */
        .rec-btn button { background-color: #ff9800 !important; }
        
        /* כפתורי ניווט - כחול */
        .nav-btn button { background-color: #2196f3 !important; }
        
        /* כותרות סקשנים */
        .section-header {
            background-color: #37474f;
            color: #ffffff !important;
            padding: 8px 12px;
            border-radius: 6px;
            margin-top: 15px;
            font-weight: bold;
            font-size: 1.1em;
        }
        </style>
    """, unsafe_allow_html=True)

# --- מוח רפואי (לוגיקה) ---
MEDICAL_BRAIN = {
    "hpc": ["נפלתי", "תאונה", "מכה", "חבלה", "כואב לי", "התחיל", "פתאום"],
    "gh": ["סוכרת", "לחץ דם", "לב", "ניתוח", "שבר", "בריא", "מחלות"],
    "med": ["תרופה", "כדור", "אקמול", "אופטלגין", "זריקה", "טיפול"],
    "agg": ["הליכה", "עמידה", "ישיבה", "כיפוף", "מאמץ", "מדרגות"],
    "ease": ["מנוחה", "שכיבה", "חימום", "קרח", "מקלחת"],
    "night": ["לילה", "שינה", "מתעורר"],
    "soc": ["עובד", "נשוי", "ילדים", "קומה", "ספורט"]
}

def analyze_text_smart(text, coords_db):
    res = {"parts": [], "pain": 0, "fields": {}}
    t = text.replace(",", "").replace(".", "")
    words = t.split()
    
    # 1. מיפוי גוף
    for saved_part in coords_db.keys():
        if saved_part in t: res["parts"].append(saved_part)
            
    # 2. כאב
    for w in words:
        if w.isdigit():
            val = int(w)
            if 0 <= val <= 10: res["pain"] = val

    # 3. שדות
    for category, keywords in MEDICAL_BRAIN.items():
        found = []
        for key in keywords:
            if key in t:
                try:
                    idx = words.index(key)
                    snippet = " ".join(words[max(0, idx-1) : min(len(words), idx+5)])
                    found.append(snippet)
                except: found.append(key)
        
        if found: res["fields"][category] = " | ".join(list(set(found)))
            
    if not res["fields"] and t: res["fields"]["hpc"] = t
    return res

# --- טעינה ושמירה ---
def load_data():
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], "גב תחתון": [450, 240]
    }
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    db = {"דניאל": {"profile": {"gender": "Male"}, "patients": {}}}
    if os.path.exists(DB_FILE):
        try: db = json.load(open(DB_FILE, "r", encoding="utf-8"))
        except: pass
    return coords, db

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db, f, indent=4, ensure_ascii=False)

def save_coords(coords):
    with open(COORDS_FILE, "w", encoding="utf-8") as f: json.dump(coords, f)

# --- הקלטה ---
def record_speech(sensitivity, time_limit):
    r = sr.Recognizer()
    r.dynamic_energy_threshold = False
    r.energy_threshold = sensitivity
    with sr.Microphone() as source:
        placeholder = st.empty()
        placeholder.info(f"🎙️ מקליט ({time_limit} שניות)...")
        try:
            audio = r.listen(source, timeout=None, phrase_time_limit=time_limit)
            placeholder.success("⌛ מעבד...")
            return r.recognize_google(audio, language="he-IL")
        except: return None

# --- ציור (שם הפונקציה תוקן!) ---
def draw_map(gender, parts, coords_db):
    img_path = "body_male.png" if gender == "Male" else "body_female.png"
    if not os.path.exists(img_path): return None
    
    img = Image.open(img_path).convert("RGBA")
    overlay = Image.new('RGBA', img.size, (255,255,255,0))
    draw = ImageDraw.Draw(overlay)
    
    for part in parts:
        if part in coords_db:
            x, y = coords_db[part]
            draw.ellipse((x-10, y-10, x+10, y+10), fill=(255, 0, 0, 180))
            
    return Image.alpha_composite(img, overlay)

# --- ניהול האפליקציה ---
if 'page' not in st.session_state: st.session_state.page = "clinic"
if 'coords' not in st.session_state: st.session_state.coords = {}
if 'db' not in st.session_state: st.session_state.db = {}

st.set_page_config(layout="wide", page_title="Sunrise Physio")
add_custom_design()

coords, db = load_data()
st.session_state.coords = coords
st.session_state.db = db

# --- דף חדר בקרה ---
if st.session_state.page == "admin":
    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    if st.button("🔙 חזרה לקליניקה"):
        st.session_state.page = "clinic"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.title("⚙️ חדר בקרה")
    
    tab1, tab2 = st.tabs(["🎯 כיול גוף", "🎙️ מיקרופון"])
    
    with tab1:
        if HAS_CALIB:
            c1, c2 = st.columns([1, 2])
            with c1:
                new_p = st.text_input("שם איבר:", placeholder="לדוגמה: ברך ימין")
                st.write("רשימת איברים:")
                st.json(list(coords.keys()))
            with c2:
                if os.path.exists("body_male.png"):
                    st.info("לחץ על התמונה כדי לשמור מיקום")
                    val = streamlit_image_coordinates("body_male.png", key="calib")
                    if val and new_p:
                        coords[new_p] = [val['x'], val['y']]
                        save_coords(coords)
                        st.success(f"נשמר: {new_p}")
                        st.rerun()
                else: st.error("חסרה תמונה")
        else: st.error("חסר הרכיב streamlit-image-coordinates")

    with tab2:
        st.session_state.sens = st.slider("רגישות", 100, 2000, 300, 50)
        st.session_state.time = st.slider("זמן הקלטה", 3, 15, 5)

# --- דף קליניקה ---
else:
    with st.sidebar:
        st.title("🗂️ ניהול")
        therapist = st.selectbox("מטפל:", list(db.keys()))
        patients = db[therapist]["patients"]
        
        with st.expander("➕ הוספת מטופל"):
            np = st.text_input("שם:")
            if st.button("צור") and np:
                patients[np] = {"text": "", "fields": {}}
                save_db(db)
                st.rerun()
        
        if patients:
            curr_p = st.selectbox("תיק פעיל:", list(patients.keys()))
        else:
            st.stop()
            
        st.markdown("---")
        st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
        if st.button("⚙️ חדר בקרה"):
            st.session_state.page = "admin"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    p_data = patients[curr_p]
    if "fields" not in p_data: p_data["fields"] = {}
    
    st.header(f"תיק: {curr_p}")
    
    st.markdown('<div class="rec-btn">', unsafe_allow_html=True)
    if st.button("🎙️ הקלט דיווח"):
        sens = st.session_state.get('sens', 300)
        tm = st.session_state.get('time', 5)
        text = record_speech(sens, tm)
        if text:
            p_data["text"] = text
            res = analyze_text_smart(text, st.session_state.coords)
            for k, v in res['fields'].items():
                old = p_data["fields"].get(k, "")
                p_data["fields"][k] = f"{old} {v}".strip()
            p_data["parts"] = res["parts"]
            if res["pain"] > 0: p_data["fields"]["pain"] = res["pain"]
            save_db(db)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    c_form, c_vis = st.columns([1.5, 1])
    
    with c_form:
        f = p_data["fields"]
        st.markdown("<div class='section-header'>History</div>", unsafe_allow_html=True)
        st.text_area("HPC", value=f.get("hpc", ""))
        
        c1, c2 = st.columns(2)
        with c1: st.text_input("Medical History", value=f.get("gh", ""))
        with c2: st.text_input("Medications", value=f.get("med", ""))
        
        c3, c4 = st.columns(2)
        with c3: st.text_area("Aggravating", value=f.get("agg", ""), height=60)
        with c4: st.text_area("Easing", value=f.get("ease", ""), height=60)

    with c_vis:
        st.markdown("#### Body Chart")
        parts = p_data.get("parts", [])
        # כאן היה הבאג - תוקן לקרוא לפונקציה הנכונה
        final_img = draw_map("Male", parts, st.session_state.coords)
        if final_img: 
            st.image(final_img, use_container_width=True)
        else: st.warning("חסרה תמונה")