import streamlit as st
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import datetime

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"

# --- קואורדינטות ברירת מחדל (למקרה שאין כיול) ---
DEFAULT_COORDS = {
    "ראש - קדמי": [150, 40], "צוואר - קדמי": [150, 85],
    "כתף ימין - קדמי": [95, 120], "כתף שמאל - קדמי": [205, 120],
    "חזה": [150, 150], "בטן": [150, 240],
    "מרפק ימין - קדמי": [70, 210], "מרפק שמאל - קדמי": [230, 210],
    "אגן - קדמי": [150, 290],
    "ברך ימין - קדמי": [115, 460], "ברך שמאל - קדמי": [185, 460],
    "קרסול ימין - קדמי": [115, 580], "קרסול שמאל - קדמי": [185, 580],
    "גב עליון": [450, 160], "גב תחתון": [450, 240],
    "כתף ימין - אחורי": [505, 120], "כתף שמאל - אחורי": [395, 120]
}

# --- פונקציות טעינה ושמירה ---
def load_data():
    # טעינת קואורדינטות
    coords = DEFAULT_COORDS.copy()
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    # טעינת מטופלים
    db = {"דניאל": {"מטופל בדיקה": {"gender": "Male", "age": "30", "text": "", "analysis": {}}}}
    if os.path.exists(DB_FILE):
        try: db = json.load(open(DB_FILE, "r", encoding="utf-8"))
        except: pass
        
    return coords, db

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

# --- עיצוב ---
def add_custom_design():
    st.markdown("""
        <style>
        .stApp { background-color: #e0f7fa; }
        h1, h2, h3, h4, p, label, div, span { color: black !important; }
        
        /* כפתור הקלטה לנייד - כתום */
        .stButton button { 
            background-color: #ffcc80 !important; 
            color: black !important; 
            border: 2px solid black !important;
            font-weight: bold;
            border-radius: 10px;
        }
        
        /* כותרות סקשנים בטופס */
        .section-header {
            background-color: #00695c;
            color: white !important;
            padding: 5px 10px;
            border-radius: 5px;
            margin-top: 15px;
            font-weight: bold;
        }
        
        /* שדות קלט */
        .stTextArea textarea, .stTextInput input {
            background-color: white !important;
            border: 1px solid #ccc;
        }
        </style>
    """, unsafe_allow_html=True)

# --- לוגיקת המוח (Local Logic) ---
def analyze_text_rules(text):
    res = {"body_parts": [], "pain": 0, "fields": {}}
    t = text 
    
    # 1. מיפוי גוף
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["גב", "אחור", "עורף"]) else "קדמי"
    
    if "כתף" in t: res["body_parts"].append(f"כתף {side} - {view}")
    elif "ברך" in t: res["body_parts"].append(f"ברך {side} - {view}")
    elif "ראש" in t: res["body_parts"].append(f"ראש - {view}")
    elif "גב תחתון" in t: res["body_parts"].append("גב תחתון")
    elif "גב" in t: res["body_parts"].append("גב עליון")
    elif "קרסול" in t: res["body_parts"].append(f"קרסול {side} - {view}")

    # 2. כאב
    for w in t.split():
        if w.isdigit(): 
            val = int(w)
            if val <= 10: res["pain"] = val

    # 3. מילוי שדות
    KEYWORDS = {
        "hpc": ["נפלתי", "תאונה", "מכה", "כואב", "התחיל", "לפני"],
        "gh": ["סוכרת", "לחץ", "בריא", "ניתוח", "מחלה"],
        "med": ["כדור", "אקמול", "תרופה", "זריקה"],
        "night": ["לילה", "שינה", "מתעורר"],
        "wake": ["בוקר", "קם", "נוקשות"],
        "agg": ["הליכה", "עמידה", "כיפוף"],
        "ease": ["מנוחה", "שכיבה", "חימום"],
        "pp": [] 
    }
    
    for cat, keys in KEYWORDS.items():
        found = [k for k in keys if k in t]
        if found or cat == "pp":
            res["fields"][cat] = t 
            
    return res

# --- ציור מפה ---
def draw_map(gender, parts, intensity, coords):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        if not os.path.exists(path): return None
        
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        
        alpha = int(50 + (intensity * 20)) if intensity else 150
        color = (255, 0, 0, alpha)
        
        for part in parts:
            # חיפוש חכם בקואורדינטות
            if part in coords:
                x, y = coords[part] if len(coords[part]) == 2 else coords[part][:2]
                draw.ellipse((x-20, y-20, x+20, y+20), fill=color)
            else:
                # חיפוש חלקי
                for k, v in coords.items():
                    if part.split(" - ")[0] in k: # למשל "כתף ימין"
                         x, y = v if len(v) == 2 else v[:2]
                         draw.ellipse((x-20, y-20, x+20, y+20), fill=color)
                         break
                         
        return Image.alpha_composite(img, overlay)
    except: return None

# --- עיבוד שמע ---
def process_audio(audio_bytes):
    r = sr.Recognizer()
    try:
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio = r.record(source)
            return r.recognize_google(audio, language="he-IL")
    except: return None

# --- אפליקציה ראשית ---
st.set_page_config(layout="wide", page_title="Sunrise Mobile")
add_custom_design()

# טעינת נתונים
coords, clinic_db = load_data()
if 'clinic_db' not in st.session_state: st.session_state.clinic_db = clinic_db
if 'coords' not in st.session_state: st.session_state.coords = coords

# סרגל צד
with st.sidebar:
    st.header("🗂️ ניהול")
    therapist = st.selectbox("מטפל:", list(st.session_state.clinic_db.keys()))
    patients = st.session_state.clinic_db[therapist]
    
    with st.expander("➕ מטופל חדש"):
        nn = st.text_input("שם:")
        ng = st.radio("מין:", ["Male", "Female"], horizontal=True)
        if st.button("צור"):
            st.session_state.clinic_db[therapist][nn] = {"gender": ng, "age": "", "text": "", "analysis": {}}
            save_db(st.session_state.clinic_db)
            st.rerun()
            
    if len(patients) > 0:
        curr_p = st.radio("תיק:", list(patients.keys()))
        if st.button("🗑️ מחק"):
            del st.session_state.clinic_db[therapist][curr_p]
            save_db(st.session_state.clinic_db)
            st.rerun()

# נתונים נוכחיים
data = st.session_state.clinic_db[therapist].get(curr_p, {})
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
gender = data.get('gender', 'Male')

# --- גוף האפליקציה ---
c1, c2 = st.columns([1, 6])
with c1: st.markdown("## 🌅")
with c2: st.title("Sunrise Physio")

st.info(f"תיק רפואי: **{curr_p}** ({'זכר' if gender=='Male' else 'נקבה'})")

# --- כפתור ההקלטה הנייד ---
audio = mic_recorder(start_prompt="🎤 התחל הקלטה", stop_prompt="⏹️ סיים", key='rec')

if audio:
    st.toast("מעבד...")
    text = process_audio(audio['bytes'])
    if text:
        # שמירת הטקסט
        data['text'] += "\n" + text
        
        # המוח מנתח
        res = analyze_text_rules(text)
        
        # שמירת מיקום גוף וכאב
        anl['body_parts'] = res['body_parts']
        anl['pain_intensity'] = res['pain']
        
        # עדכון שדות הטופס (אם מצאנו משהו רלוונטי)
        mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease", "night": "night", "wake": "wake"}
        for k, v in mapping.items():
            if k in res['fields']:
                curr_val = st.session_state.get(v, "")
                # משרשר את הטקסט החדש לשדה
                st.session_state[v] = f"{curr_val} {res['fields'][k]}".strip()
        
        save_db(st.session_state.clinic_db)
        st.rerun()

st.markdown("---")

# --- גריד הטופס והתמונה ---
col_form, col_map = st.columns([1.5, 1])

with col_form:
    # אתחול Session State לשדות כדי שלא יתאפסו
    fields = ["pp", "hpc", "gh", "med", "agg", "ease", "night", "wake", "plan"]
    for f in fields:
        if f not in st.session_state: st.session_state[f] = ""

    st.markdown("<div class='section-header'>History</div>", unsafe_allow_html=True)
    st.text_area("Patient Perspective", key="pp", height=70)
    st.text_area("HPC", key="hpc", height=70)
    
    c_h1, c_h2 = st.columns(2)
    with c_h1: st.text_input("General Health", key="gh")
    with c_h2: st.text_input("Medications", key="med")
    
    st.markdown("<div class='section-header'>Pain & Behavior</div>", unsafe_allow_html=True)
    
    # סליידר כאב (מחובר לניתוח)
    curr_pain = anl.get('pain_intensity', 0)
    st.slider("Pain (0-10)", 0, 10, int(curr_pain))
    
    c_p1, c_p2 = st.columns(2)
    with c_p1: st.text_area("Aggravating", key="agg", height=60)
    with c_p2: st.text_area("Easing", key="ease", height=60)
    
    c_t1, c_t2 = st.columns(2)
    with c_t1: st.text_input("Night Pain", key="night")
    with c_t2: st.text_input("On Waking", key="wake")
    
    st.markdown("<div class='section-header'>Plan</div>", unsafe_allow_html=True)
    st.text_area("Physical Exam Plan", key="plan")

with col_map:
    st.markdown("### Body Chart")
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    
    final_img = draw_map(gender, parts, pain, st.session_state.coords)
    
    if final_img: 
        st.image(final_img, use_container_width=True)
        if parts: st.success(f"זוהה: {', '.join(parts)}")
    else: 
        st.warning("No Image")

with st.expander("📝 היסטוריית תמלול מלאה"):
    st.text(data['text'])