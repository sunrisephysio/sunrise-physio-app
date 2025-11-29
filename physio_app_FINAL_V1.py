import streamlit as st
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import datetime
import io
from streamlit_image_coordinates import streamlit_image_coordinates
# הרכיב החדש להקלטה מהטלפון
from streamlit_mic_recorder import mic_recorder

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
openai.api_key = "YOUR_OPENAI_API_KEY" # לא בשימוש כרגע, המוח מקומי

# --- פונקציות שמירה וטעינה ---
def load_coordinates():
    if os.path.exists(COORDS_FILE):
        try: return json.load(open(COORDS_FILE, "r"))
        except: pass
    # ברירת מחדל (ניתן להוסיף עוד)
    return {
        "ראש - קדמי": [150, 40], "צוואר - קדמי": [150, 85],
        "כתף ימין - קדמי": [95, 120], "כתף שמאל - קדמי": [205, 120],
        "חזה": [150, 150], "בטן": [150, 240],
        "גב עליון": [450, 160], "גב תחתון": [450, 240],
        "ברך ימין - קדמי": [115, 460], "ברך שמאל - קדמי": [185, 460],
        "כתף ימין - אחורי": [505, 120], "כתף שמאל - אחורי": [395, 120]
    }

def save_coordinates(coords):
    with open(COORDS_FILE, "w") as f: json.dump(coords, f)

def load_db():
    # כאן טוענים את הנתונים (בגרסה המלאה יש כאן טעינה מקובץ)
    if 'clinic_db' not in st.session_state:
        st.session_state.clinic_db = {"דניאל": {"מטופל בדיקה": {"gender": "Male", "text": "", "analysis": {}}}}

# --- עיצוב ---
def add_custom_design():
    st.markdown("""
        <style>
        .stApp { background-color: #e0f7fa; }
        h1, h2, h3, h4, p, div, label, span { color: black !important; }
        /* כפתורי הקלטה */
        .stButton button { background-color: #b9f6ca; border: 1px solid black; color: black; }
        </style>
    """, unsafe_allow_html=True)

# --- המוח הויזואלי החדש (לוגיקה משופרת) ---
def analyze_local_visuals(text):
    results = {"body_parts": [], "pain": 0, "fields": {}}
    t = text 
    
    # 1. זיהוי צד
    is_left = "שמאל" in t
    side_str = "שמאל" if is_left else "ימין"
    
    # 2. זיהוי כיוון (קדמי/אחורי) - לוגיקה חכמה יותר
    is_back = any(w in t for w in ["גב", "אחור", "עורף", "ישבן", "שכמה"])
    view_str = "אחורי" if is_back else "קדמי"
    
    # 3. מיפוי איברים (חוקים)
    if "כתף" in t: results["body_parts"].append(f"כתף {side_str} - {view_str}")
    elif "ברך" in t: results["body_parts"].append(f"ברך {side_str} - {view_str}")
    elif "מרפק" in t: results["body_parts"].append(f"מרפק {side_str} - {view_str}")
    elif "ראש" in t: results["body_parts"].append(f"ראש - {view_str}")
    elif "צוואר" in t: results["body_parts"].append(f"צוואר - {view_str}")
    
    # מקרים מיוחדים
    if "גב תחתון" in t: results["body_parts"] = ["גב תחתון"]
    elif "גב" in t and "עליון" in t: results["body_parts"] = ["גב עליון"]
    elif "חזה" in t: results["body_parts"] = ["חזה"]
    elif "בטן" in t: results["body_parts"] = ["בטן"]

    # 4. זיהוי כאב
    for w in t.split():
        if w.isdigit() and int(w) <= 10: results["pain"] = int(w)

    # 5. מילוי שדות (אותו מילון כמו קודם)
    KEYWORDS = {
        "hpc": ["נפלתי", "תאונה", "מכה", "כואב"],
        "gh": ["סוכרת", "לחץ דם", "בריא"],
        "med": ["כדור", "אקמול"],
        "agg": ["הליכה", "עמידה"],
        "ease": ["מנוחה", "שכיבה"],
        "pp": [] # תמיד
    }
    for cat, keys in KEYWORDS.items():
        if any(k in t for k in keys) or cat == "pp": results["fields"][cat] = t
        
    return results

def update_ui(res):
    st.session_state['temp_pain'] = res['pain']
    mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease"}
    for k, v in mapping.items():
        if k in res['fields']:
            curr = st.session_state.get(v, "")
            if res['fields'][k] not in curr: st.session_state[v] = f"{curr} {res['fields'][k]}".strip()

# --- עיבוד הקלטה (מהרכיב החדש) ---
def process_audio(audio_bytes):
    r = sr.Recognizer()
    try:
        # המרת ה-Bytes לקובץ שמע שהמנוע מבין
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio = r.record(source)
            text = r.recognize_google(audio, language="he-IL")
            return text
    except Exception as e:
        return None

# --- ציור ---
def draw_map(gender, parts, intensity):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        coords = st.session_state.coords
        if not os.path.exists(path): return None
        
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        
        color = (255, 0, 0, int(50 + (intensity * 20)))
        
        for part in parts:
            if part in coords:
                x, y = coords[part]
                draw.ellipse((x-20, y-20, x+20, y+20), fill=color)
            else:
                # חיפוש חכם (Fallback)
                for k, v in coords.items():
                    # אם המילה קיימת חלקית (למשל 'כתף ימין' בתוך 'כתף ימין - קדמי')
                    # אבל גם בודקים שהכיוון תואם
                    if part.split(" - ")[0] in k:
                        if len(part.split(" - ")) > 1 and part.split(" - ")[1] in k:
                             x, y = v
                             draw.ellipse((x-20, y-20, x+20, y+20), fill=color)
                             break
        return Image.alpha_composite(img, overlay)
    except: return None

# --- אפליקציה ---
st.set_page_config(layout="wide", page_title="Sunrise Mobile")
add_custom_design()
init_system()
load_db()

if 'coords' not in st.session_state: st.session_state.coords = load_coordinates()
if 'calib_index' not in st.session_state: st.session_state.calib_index = 0

# אתחול שדות
keys = ["pp", "hpc", "gh", "med", "agg", "ease"]
for k in keys: 
    if k not in st.session_state: st.session_state[k] = ""

# --- ממשק ---
c1, c2 = st.columns([1, 10])
with c1: st.markdown("## 🌅")
with c2: st.title("Sunrise Physio (Mobile)")

# ניהול בסיסי
therapist = "דניאל"
curr_p = "מטופל בדיקה"
data = st.session_state.clinic_db[therapist][curr_p]
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']

# --- הקלטה בטלפון ---
st.info("🎙️ הקלטה מהנייד: לחץ פעם אחת להתחלה, ופעם שנייה לסיום.")
audio = mic_recorder(
    start_prompt="התחל הקלטה",
    stop_prompt="סיים הקלטה", 
    key='recorder',
    format="wav" # חשוב!
)

if audio:
    st.success("הקלטה התקבלה! מעבד...")
    text = process_audio(audio['bytes'])
    if text:
        data['text'] += "\n" + text
        
        # המוח הויזואלי
        local_res = analyze_local_visuals(text)
        
        # עדכון נתונים
        anl['body_parts'] = local_res['body_parts']
        anl['pain_intensity'] = local_res['pain']
        update_ui(local_res)
        st.rerun()
    else:
        st.error("לא זוהה דיבור")

st.markdown("---")

col_form, col_visual = st.columns([1.5, 1])

with col_form:
    st.text_area("Patient's Perspective", key="pp")
    st.text_area("HPC", key="hpc")
    st.text_input("General Health", key="gh")
    st.text_input("Medications", key="med")
    
    pv = st.session_state.get('temp_pain', 0)
    st.slider("Pain (0-10)", 0, 10, pv)

with col_visual:
    st.markdown("### Body Chart")
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    final = draw_map("Male", parts, pain)
    if final: st.image(final, use_container_width=True)
    
    # הצגת טקסט הכיול כדי שתדע מה המערכת זיהתה
    if parts:
        st.caption(f"זיהוי מערכת: {', '.join(parts)}")

with st.sidebar:
    st.title("כיול")
    # (קוד הכיול הקיים יכול להיכנס כאן, קיצרתי לטובת המיקוד במיקרופון)
    if st.checkbox("הצג נקודות כיול"):
        st.json(st.session_state.coords)