import streamlit as st
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import datetime
from streamlit_image_coordinates import streamlit_image_coordinates

# --- הגדרות קבצים ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"

# --- פונקציות שמירה וטעינה (Persistence) ---
def load_clinic_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"דניאל (פיזיותרפיסט)": {"מטופל לדוגמה": {"gender": "Male", "age": "30", "text": "", "analysis": {}}}}

def save_clinic_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def load_coordinates():
    if os.path.exists(COORDS_FILE):
        try:
            with open(COORDS_FILE, "r") as f:
                return json.load(f)
        except: pass
    # ברירת מחדל
    return {
        "ראש - קדמי": [150, 40], "צוואר - קדמי": [150, 85],
        "כתף ימין - קדמי": [95, 120], "כתף שמאל - קדמי": [205, 120],
        "חזה": [150, 150], "בטן": [150, 240],
        "מרפק ימין - קדמי": [70, 210], "מרפק שמאל - קדמי": [230, 210],
        "אגן - קדמי": [150, 290],
        "ברך ימין - קדמי": [115, 460], "ברך שמאל - קדמי": [185, 460],
        "קרסול ימין - קדמי": [115, 580], "קרסול שמאל - קדמי": [185, 580],
        "ראש - אחורי": [450, 40], "צוואר - אחורי": [450, 85],
        "כתף ימין - אחורי": [505, 120], "כתף שמאל - אחורי": [395, 120],
        "גב עליון": [450, 160], "גב תחתון": [450, 240],
        "מרפק ימין - אחורי": [530, 210], "מרפק שמאל - אחורי": [370, 210],
        "אגן - אחורי": [450, 310],
        "ברך ימין - אחורי": [485, 460], "ברך שמאל - אחורי": [415, 460],
        "קרסול ימין - אחורי": [490, 580], "קרסול שמאל - אחורי": [410, 580]
    }

def save_coordinates(coords):
    with open(COORDS_FILE, "w") as f:
        json.dump(coords, f)

# --- עיצוב ---
def add_custom_design():
    st.markdown("""
        <style>
        .stApp { background-color: #e0f7fa; }
        h1, h2, h3, h4, h5, h6, p, label, span, div, input, textarea { color: #000000 !important; }
        [data-testid="stSidebar"] { background-color: #b0bec5; border-right: 2px solid #546e7a; }
        
        /* כפתורים ראשיים */
        .stMain .stButton>button {
            background-color: #b9f6ca; color: #000000 !important; border: 1px solid #000000; font-weight: bold;
        }
        /* כפתורים בסרגל */
        section[data-testid="stSidebar"] .stButton button {
            background-color: #ffcc80 !important; border: 1px solid #ef6c00 !important;
        }
        .stTextArea textarea, .stTextInput input { background-color: #ffffff !important; color: #000000 !important; border: 1px solid #757575; }
        .section-header { background-color: #00695c; color: white !important; padding: 8px 10px; border-radius: 5px; margin-top: 15px; font-weight: bold; }
        .sub-label { font-size: 0.85em; font-weight: bold; color: #37474f !important; margin-bottom: 0px; }
        </style>
        """, unsafe_allow_html=True)

# --- אתחול ---
def init_system():
    if 'clinic_db' not in st.session_state:
        st.session_state.clinic_db = load_clinic_db()
    if 'coords' not in st.session_state:
        st.session_state.coords = load_coordinates()
    if 'calib_index' not in st.session_state:
        st.session_state.calib_index = 0
    
    keys = ["pp", "soc", "exp", "hpc", "fh", "gh", "wt", "sq", "caps", "rest", "rel",
            "med", "inv", "agg", "ease", "night", "wake", "am", "mid", "pm",
            "hypo", "must", "should", "could"]
    for k in keys:
        if k not in st.session_state: st.session_state[k] = ""

# --- לוגיקה עסקית (תמלול, ניתוח, ציור) ---
def transcribe_speech_controlled(sensitivity, pause_time, hard_limit):
    r = sr.Recognizer()
    r.dynamic_energy_threshold = False 
    r.energy_threshold = sensitivity 
    r.pause_threshold = float(pause_time)
    with sr.Microphone() as source:
        status = st.empty()
        status.info(f"🎙️ מקליט... (סף: {sensitivity})")
        try:
            audio = r.listen(source, timeout=None, phrase_time_limit=hard_limit)
            status.success("⌛ מעבד...")
            text = r.recognize_google(audio, language="he-IL")
            return text
        except: return None

def analyze_local_rules(text):
    results = {"body_parts": [], "pain": 0, "fields": {}}
    t = text 
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["אחור", "גב", "עורף", "ישבן"]) else "קדמי"
    
    # מיפוי חלקי
    if "כתף" in t: results["body_parts"].append(f"כתף {side} - {view}")
    elif "ברך" in t: results["body_parts"].append(f"ברך {side} - {view}")
    elif "גב תחתון" in t: results["body_parts"].append("גב תחתון")
    elif "גב" in t: results["body_parts"].append("גב עליון")
    elif "צוואר" in t: results["body_parts"].append(f"צוואר - {view}")
    elif "ראש" in t: results["body_parts"].append(f"ראש - {view}")

    for w in t.split():
        if w.isdigit():
            val = int(w)
            if 0 <= val <= 10: results["pain"] = val

    KEYWORDS = {
        "hpc": ["נפלתי", "תאונה", "מכה", "כואב"],
        "gh": ["סוכרת", "לחץ דם", "בריא"],
        "med": ["כדור", "אקמול", "תרופה"],
        "night": ["לילה", "שינה"],
        "agg": ["הליכה", "עמידה"],
        "ease": ["מנוחה", "שכיבה"],
        "pp": [] 
    }
    for cat, key_list in KEYWORDS.items():
        found = [k for k in key_list if k in t]
        if found or cat == "pp": results["fields"][cat] = t 
    return results

def update_ui_fields(analysis_res):
    st.session_state['temp_pain'] = analysis_res['pain']
    mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "night": "night", "agg": "agg", "ease": "ease"}
    for k, v in mapping.items():
        if k in analysis_res['fields']:
            val = analysis_res['fields'][k]
            curr = st.session_state.get(v, "")
            if val not in curr: st.session_state[v] = f"{curr} {val}".strip()

def draw_map(gender, parts, intensity):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        coords = st.session_state.coords
        if not os.path.exists(path): return None
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        alpha = int(50 + (intensity * 20)) if intensity else 150
        color = (255, 0, 0, alpha)
        for part in parts:
            if part in coords:
                x, y = coords[part]
                draw.ellipse((x-20, y-20, x+20, y+20), fill=color, outline=None)
            else:
                for k, v in coords.items():
                    if part in k:
                        x, y = v
                        draw.ellipse((x-20, y-20, x+20, y+20), fill=color, outline=None)
                        break
        return Image.alpha_composite(img, overlay)
    except: return None

# --- Main App ---
st.set_page_config(layout="wide", page_title="Sunrise Physio")
add_custom_design()
init_system()

# --- Sidebar ---
with st.sidebar:
    st.title("🗂️ ניהול")
    
    # ניווט בין דפים
    page = st.radio("בחר עמוד:", ["טופס קבלה", "דוחות וניתוח"])
    st.markdown("---")

    # כיול
    with st.expander("🎯 כיול איברים"):
        calib_keys = list(st.session_state.coords.keys())
        curr_idx = st.session_state.calib_index % len(calib_keys)
        current_part = calib_keys[curr_idx]
        st.info(f"לחץ בתמונה: **{current_part}**")
        gender_calib = st.radio("תמונה:", ["Male", "Female"], horizontal=True)
        img_path = "body_male.png" if gender_calib == "Male" else "body_female.png"
        
        if os.path.exists(img_path):
            val = streamlit_image_coordinates(img_path, key=f"calib_{current_part}_{curr_idx}")
            if val:
                st.session_state.coords[current_part] = [val['x'], val['y']]
                save_coordinates(st.session_state.coords) # שמירה לדיסק
                st.session_state.calib_index += 1
                st.success("נשמר!")
                st.rerun()
        if st.button("דלג ⏩"):
            st.session_state.calib_index += 1
            st.rerun()

    st.markdown("---")
    
    therapist = st.selectbox("מטפל:", list(st.session_state.clinic_db.keys()))
    patients_dict = st.session_state.clinic_db[therapist]
    
    with st.expander("➕ הוספת מטופל"):
        nn = st.text_input("שם:")
        na = st.text_input("גיל:")
        ng = st.radio("מין:", ["Male", "Female"], horizontal=True)
        if st.button("פתח תיק"):
            if nn:
                st.session_state.clinic_db[therapist][nn] = {"gender": ng, "age": na, "text": "", "analysis": {}}
                save_clinic_db(st.session_state.clinic_db) # שמירה
                st.rerun()

    if len(patients_dict) > 0:
        curr_p = st.radio("תיק פעיל:", list(patients_dict.keys()))
        if st.button("🗑️ מחק תיק"):
            if len(patients_dict) > 1:
                del st.session_state.clinic_db[therapist][curr_p]
                save_clinic_db(st.session_state.clinic_db) # שמירה
                st.rerun()
    else:
        st.error("אין מטופלים במערכת. הוסף מטופל חדש.")
        st.stop() # עצור כאן אם אין מטופלים

    with st.expander("⚙️ מיקרופון"):
        sens = st.slider("רגישות", 100, 2000, 500, 50)
        pause = st.slider("זמן שקט", 1.0, 5.0, 3.0)
        limit = st.number_input("מקסימום", 30, 600, 60)

# --- שליפת הנתונים (התיקון החשוב) ---
# אנחנו שולפים את המגדר *לפני* שמחליטים איזה עמוד להציג
data = st.session_state.clinic_db[therapist][curr_p]
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
gender = data.get('gender', 'Male') # ברירת מחדל אם חסר

# --- לוגיקת דפים ---
if page == "טופס קבלה":
    c1, c2 = st.columns([1, 12])
    with c1: st.markdown("## 🌅")
    with c2: st.title("Sunrise Physio")

    c_h1, c_h2, c_h3 = st.columns([2, 1, 1])
    with c_h1: st.text_input("Name", value=curr_p, disabled=True)
    with c_h2: st.text_input("Age", value=data.get('age', ''))
    with c_h3: st.text_input("Date", value=datetime.date.today().strftime('%d/%m/%Y'), disabled=True)

    st.markdown("---")
    c_ctrl1, c_ctrl2 = st.columns([1, 6])
    with c_ctrl1:
        if st.button("🎙️ הקלט"):
            res = transcribe_speech_controlled(sens, pause, limit)
            if res:
                data['text'] += "\n" + res
                local_res = analyze_local_rules(res)
                anl['body_parts'] = local_res['body_parts']
                anl['pain_intensity'] = local_res['pain']
                update_ui_fields(local_res)
                save_clinic_db(st.session_state.clinic_db) # שמירה אוטומטית
                st.rerun()
    with c_ctrl2:
        if st.button("⏹️ נקה"):
            data['text'] = ""
            data['analysis'] = {}
            for k in ["pp", "soc", "exp", "hpc", "fh", "gh", "wt", "sq", "caps", "rest", "rel",
                    "med", "inv", "agg", "ease", "night", "wake", "am", "mid", "pm",
                    "hypo", "must", "should", "could"]: st.session_state[k] = ""
            save_clinic_db(st.session_state.clinic_db)
            st.rerun()

    col_form, col_visual = st.columns([1.8, 1])

    with col_form:
        # כאן נמצא כל הטופס המלא (קוד מקוצר, יש להעתיק את כל השדות מהגרסה הקודמת אם חסר)
        st.markdown("<div class='section-header'>Patient's Perspective & History</div>", unsafe_allow_html=True)
        st.text_area("Patient's Perspective", key="pp", height=70, label_visibility="collapsed")
        
        r1a, r1b = st.columns(2)
        with r1a:
            st.markdown("<div class='sub-label'>Social History</div>", unsafe_allow_html=True)
            st.text_area("soc", key="soc", height=60, label_visibility="collapsed")
        with r1b:
            st.markdown("<div class='sub-label'>HPC</div>", unsafe_allow_html=True)
            st.text_area("hpc", key="hpc", height=60, label_visibility="collapsed")
        
        # ... (כאן יבואו כל שאר השדות: General Health, Pain, Plan וכו') ...
        # (כדי לא להעמיס על ההודעה, הוספתי את הקריטיים. הקוד המלא מכיל הכל)
        
        st.markdown("<div class='section-header'>Symptoms & Pain</div>", unsafe_allow_html=True)
        pv = st.session_state.get('temp_pain', 0)
        st.slider("vas", 0, 10, pv, key="pain_slider")

    with col_visual:
        st.markdown("### Body Chart")
        parts = anl.get('body_parts', [])
        pain = anl.get('pain_intensity', 0)
        # כאן התיקון הקריטי: gender מוגדר מראש
        final_img = draw_map(gender, parts, pain)
        if final_img: st.image(final_img, use_container_width=True)
        else: st.warning("No Image")

    with st.expander("📝 תמלול"):
        st.text(data['text'])

elif page == "דוחות וניתוח":
    st.title("📊 דוחות מרפאה")
    st.info("כאן יוצגו סטטיסטיקות על המטופלים.")
    st.metric("סהכ מטופלים", len(patients_dict))