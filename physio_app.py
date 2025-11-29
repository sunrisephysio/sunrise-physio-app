import streamlit as st
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import base64
import datetime

# --- הגדרות מערכת ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"
IMAGES_DIR = "therapist_images"
if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)

# --- עיצוב UI/UX מקצועי (RTL + צבעים) ---
def apply_design():
    st.markdown("""
        <style>
        /* כיוון ימין-שמאל גלובלי */
        .stApp {
            direction: rtl;
            background-color: #f8f9fa; /* אפור-לבן נקי */
        }
        
        /* סרגל צד */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-left: 1px solid #ddd;
            box-shadow: -2px 0 5px rgba(0,0,0,0.05);
        }
        
        /* כותרות */
        h1, h2, h3, p, div, span, label {
            color: #333333 !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        /* כפתור הקלטה (בולט) */
        .stButton button {
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
            transition: 0.3s;
        }
        
        /* צביעת כפתורים ספציפיים לפי הקשר ייעשה בקוד עצמו בעזרת types */
        
        /* שדות קלט */
        .stTextInput input, .stTextArea textarea {
            background-color: white !important;
            border: 1px solid #ced4da;
            border-radius: 5px;
        }
        
        /* תמונת פרופיל עגולה */
        .avatar {
            border-radius: 50%;
            border: 3px solid #ff9800; /* כתום */
            object-fit: cover;
        }
        </style>
    """, unsafe_allow_html=True)

# --- פונקציות טעינת נתונים בטוחה ---
def load_data():
    # קואורדינטות (בסיס)
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], "כתף שמאל - קדמי": [205, 120],
        "ברך ימין - קדמי": [115, 460], "ברך שמאל - קדמי": [185, 460], "גב תחתון": [450, 240]
    }
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    # בסיס נתונים
    db = {}
    if os.path.exists(DB_FILE):
        try: db = json.load(open(DB_FILE, "r", encoding="utf-8"))
        except: pass
    
    # אתחול אם ריק
    if not db:
        db = {"Admin": {"profile": {"gender": "Male"}, "patients": {}}}
        
    return coords, db

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

# --- מנוע תמלול (הלב של המערכת) ---
def process_audio_data(audio_bytes):
    r = sr.Recognizer()
    try:
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language="he-IL")
            return text
    except sr.UnknownValueError:
        return None # לא זוהה דיבור
    except Exception as e:
        return f"Error: {str(e)}"

# --- מנוע ניתוח טקסט (מקומי) ---
def analyze_text(text):
    res = {"body_parts": [], "pain": 0, "fields": {}}
    t = text.replace(".", "").replace(",", "")
    
    # 1. מיפוי גוף
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["גב", "אחור", "עורף"]) else "קדמי"
    
    mapping = {
        "כתף": f"כתף {side} - {view}", "ברך": f"ברך {side} - {view}",
        "ראש": f"ראש - {view}", "גב תחתון": "גב תחתון", "צוואר": f"צוואר - {view}"
    }
    for k, v in mapping.items():
        if k in t: res["body_parts"].append(v)

    # 2. זיהוי כאב
    for w in t.split():
        if w.isdigit() and int(w) <= 10: res["pain"] = int(w)

    # 3. שיוך לשדות
    KEYWORDS = {
        "hpc": ["נפלתי", "מכה", "תאונה", "כואב", "התחיל"],
        "gh": ["סוכרת", "לחץ", "בריא", "ניתוח"],
        "med": ["כדור", "תרופה", "אקמול"],
        "agg": ["הליכה", "עמידה"],
        "ease": ["מנוחה", "שכיבה"],
        "pp": []
    }
    for cat, keys in KEYWORDS.items():
        if any(k in t for k in keys) or cat == "pp":
            res["fields"][cat] = t
            
    return res

# --- ציור מפה בטוח ---
def draw_body_map(gender, parts, intensity, coords):
    # נסיון לטעון תמונה - אם אין, מחזיר כלום בלי לקרוס
    filename = "body_male.png" if gender == "Male" else "body_female.png"
    if not os.path.exists(filename):
        return None, f"הקובץ {filename} חסר בשרת"
    
    try:
        img = Image.open(filename).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        
        # צבע אדום שקוף
        color = (255, 0, 0, 180)
        
        for part in parts:
            if part in coords:
                x, y = coords[part][:2]
                draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
            else:
                # חיפוש חלקי (Fallback)
                base = part.split(" - ")[0]
                for k, v in coords.items():
                    if base in k:
                        x, y = v[:2]
                        draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
                        break
                        
        return Image.alpha_composite(img, overlay), "OK"
    except Exception as e:
        return None, str(e)

# --- האפליקציה ---
st.set_page_config(layout="wide", page_title="Medical AI")
apply_design()

coords, clinic_db = load_data()
if 'clinic_db' not in st.session_state: st.session_state.clinic_db = clinic_db

# --- סרגל צד (Sidebar) ---
with st.sidebar:
    # לוגו
    if os.path.exists("logo.png"):
        st.image("logo.png", width=100)
    else:
        st.markdown("## 🏥 MedicalApp")
    
    st.markdown("---")
    st.header("ניהול")
    
    # בחירת מטפל
    therapists = list(st.session_state.clinic_db.keys())
    selected_t = st.selectbox("מטפל:", therapists)
    
    # תמונת מטפל (עם מנגנון הגנה)
    t_data = st.session_state.clinic_db[selected_t]
    if "profile" not in t_data: t_data = {"profile": {"gender": "Male"}, "patients": {}} # תיקון מבנה ישן
    
    img_path = t_data["profile"].get("image_path")
    gender_icon = "👨‍⚕️" if t_data["profile"].get("gender") == "Male" else "👩‍⚕️"
    
    if img_path and os.path.exists(img_path):
        st.image(img_path, width=80)
    else:
        st.markdown(f"<div style='font-size:50px;text-align:center;'>{gender_icon}</div>", unsafe_allow_html=True)
    
    # הוספת מטפל (כפתור כתום ב-CSS)
    with st.expander("➕ הוסף איש צוות"):
        new_name = st.text_input("שם:")
        new_gen = st.radio("מין:", ["Male", "Female"], horizontal=True)
        if st.button("שמור מטפל"):
            if new_name:
                st.session_state.clinic_db[new_name] = {"profile": {"gender": new_gen}, "patients": {}}
                save_db(st.session_state.clinic_db)
                st.rerun()

    st.markdown("---")
    
    # ניהול מטופלים
    patients = t_data.get("patients", {})
    
    # הוספת מטופל (איפוס מסך מובנה)
    with st.expander("➕ מטופל חדש", expanded=True):
        p_name = st.text_input("שם המטופל:")
        p_gen = st.radio("מין המטופל:", ["Male", "Female"], horizontal=True)
        if st.button("פתח תיק"):
            if p_name:
                patients[p_name] = {"gender": p_gen, "text": "", "analysis": {}}
                save_db(st.session_state.clinic_db)
                st.rerun()
    
    if patients:
        curr_p = st.selectbox("תיק פעיל:", list(patients.keys()))
    else:
        st.info("אין מטופלים.")
        st.stop()

# --- תוכן ראשי ---
data = patients[curr_p]
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
p_gender = data.get('gender', 'Male')

# כותרת
c1, c2 = st.columns([5, 1])
with c1: st.title(f"תיק: {curr_p}")
with c2: st.caption(datetime.date.today().strftime("%d/%m/%Y"))

# --- אזור הקלטה (הלב) ---
st.info("👇 לחץ להקלטה מהנייד (לחץ להתחלה -> דבר -> לחץ לסיום)")
audio = mic_recorder(
    start_prompt="🎤 התחל הקלטה",
    stop_prompt="⏹️ סיים ונתח",
    key='recorder'
)

if audio:
    st.toast("⏳ מעבד שמע...", icon="🔄")
    text = process_audio_data(audio['bytes'])
    
    if text and "Error" not in text:
        st.success("נקלט בהצלחה!")
        data['text'] += "\n" + text
        
        # ניתוח
        res = analyze_text(text)
        
        # עדכון DB
        if res['body_parts']: anl['body_parts'] = res['body_parts']
        if res['pain'] > 0: anl['pain_intensity'] = res['pain']
        
        mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease"}
        for k, v in mapping.items():
            if k in res['fields']:
                curr_val = st.session_state.get(v, "")
                # משרשר רק אם זה טקסט חדש
                st.session_state[v] = f"{curr_val} {res['fields'][k]}".strip()
        
        save_db(st.session_state.clinic_db)
        st.rerun()
    elif not text:
        st.warning("לא שמעתי כלום. נסה שוב.")
    else:
        st.error("שגיאה בתמלול. נסה שוב.")

st.markdown("---")

# --- גריד (Grid) ---
col_form, col_visual = st.columns([1.5, 1])

with col_form:
    # אתחול שדות (מונע קריסה)
    for f in ["pp", "hpc", "gh", "med", "agg", "ease"]:
        if f not in st.session_state: st.session_state[f] = ""

    st.markdown("### 📝 אנמנזה")
    st.text_area("תלונת המטופל", key="pp", height=70)
    st.text_area("HPC (סיפור המקרה)", key="hpc", height=90)
    
    c_sub1, c_sub2 = st.columns(2)
    with c_sub1: st.text_input("רקע רפואי", key="gh")
    with c_sub2: st.text_input("תרופות", key="med")
    
    st.markdown("### 📊 כאב והתנהגות")
    curr_pain = anl.get('pain_intensity', 0)
    st.slider("רמת כאב (VAS)", 0, 10, int(curr_pain))
    
    c_p1, c_p2 = st.columns(2)
    with c_p1: st.text_area("גורמים מחמירים", key="agg", height=60)
    with c_p2: st.text_area("גורמים מקלים", key="ease", height=60)

with col_visual:
    st.markdown("### 📍 מפת גוף")
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    
    final_img, status = draw_body_map(p_gender, parts, pain, coords)
    
    if final_img:
        st.image(final_img, use_container_width=True)
        if parts: st.info(f"זוהה: {', '.join(parts)}")
    else:
        # הודעת שגיאה ברורה אם התמונה חסרה בשרת
        st.error(f"חסרה תמונה בשרת ({status}). וודא שהעלית את body_male.png ל-GitHub.")

# --- היסטוריה ---
with st.expander("היסטוריית הקלטות מלאה"):
    st.text(data.get('text', ''))