import streamlit as st
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import base64
import datetime

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"
IMAGES_DIR = "therapist_images"

if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)

# --- פונקציות תמונה ---
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    return None

def circular_avatar_html(image_path):
    img_b64 = get_image_base64(image_path)
    if not img_b64: return ""
    return f"""<div style="display: flex; justify-content: center; margin-bottom: 15px;">
            <img src="data:image/png;base64,{img_b64}" 
            style="border-radius: 50%; width: 100px; height: 100px; object-fit: cover; border: 3px solid #ffcc80;"></div>"""

# --- ניהול נתונים ---
def load_data():
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], "ברך ימין - קדמי": [115, 460],
        "גב תחתון": [450, 240], "גב עליון": [450, 160], "אגן - אחורי": [450, 300]
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

# --- פונקציה קריטית: איפוס מסך למטופל חדש ---
def reset_screen_fields():
    """מנקה את כל השדות במסך כדי שלא יעבור מידע בין מטופלים"""
    fields = ["pp", "hpc", "gh", "med", "agg", "ease", "night", "wake", "plan", "soc", "exp", "pain_slider"]
    for f in fields:
        st.session_state[f] = "" if f != "pain_slider" else 0

def load_patient_to_screen(patient_data):
    """טוען נתונים של מטופל קיים למסך"""
    analysis = patient_data.get('analysis', {})
    
    # מיפוי שדות הדאטה לשדות המסך
    mapping = {
        "pp": "patient_perspective",
        "hpc": "hpc",
        "gh": "gh",
        "med": "med",
        "agg": "agg",
        "ease": "ease",
        "night": "night",
        "wake": "wake",
        "soc": "soc",
        "exp": "exp"
    }
    
    for screen_key, data_key in mapping.items():
        st.session_state[screen_key] = analysis.get(data_key, "")
        
    # טעינת כאב בנפרד (כי זה מספר)
    try:
        st.session_state['pain_slider'] = int(analysis.get('pain_intensity', 0))
    except:
        st.session_state['pain_slider'] = 0

# --- המוח המנתח (חוקים) ---
def analyze_text_deep(text):
    res = {"body_parts": [], "pain": 0, "fields": {}}
    t = text.replace(",", " ").replace(".", " ")
    
    # 1. גוף
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["גב", "אחור", "עורף", "ישבן"]) else "קדמי"
    
    parts_map = {
        "כתף": f"כתף {side} - {view}", "ברך": f"ברך {side} - {view}",
        "גב תחתון": "גב תחתון", "גב": "גב עליון", "ראש": f"ראש - {view}"
    }
    for k, v in parts_map.items():
        if k in t: res["body_parts"].append(v)
    
    # 2. כאב
    for w in t.split():
        if w.isdigit() and int(w) <= 10: res["pain"] = int(w)

    # 3. מילוי טבלה (לפי מילות מפתח)
    CATEGORIES = {
        "hpc": ["נפלתי", "תאונה", "מכה", "התחיל", "כואב לי", "לפני"],
        "gh": ["סוכרת", "לחץ דם", "בריא", "ניתוח", "שוקל"],
        "med": ["כדור", "אקמול", "תרופה"],
        "agg": ["הליכה", "עמידה", "כיפוף", "מאמץ"],
        "ease": ["מנוחה", "שכיבה", "חימום"],
        "night": ["לילה", "שינה"],
        "soc": ["עובד", "נשוי", "ספורט"],
        "pp": [] # תמיד מקבל הכל
    }
    
    for cat, keywords in CATEGORIES.items():
        found = [word for word in keywords if word in t]
        if found or cat == "pp":
            # אם מצא מילה, הוא מעתיק את המשפט הרלוונטי (פשוט את כל הטקסט במקרה הזה כדי לא לאבד מידע)
            # בגרסה מתקדמת אפשר לחתוך משפטים
            res["fields"][cat] = t 

    return res

def draw_map(gender, parts, intensity, coords):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        if not os.path.exists(path): return None
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        color = (255, 0, 0, 150)
        for part in parts:
            if part in coords:
                x, y = coords[part] if len(coords[part])==2 else coords[part][:2]
                draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
            else: # חיפוש חלקי
                for k, v in coords.items():
                    if part.split(" - ")[0] in k:
                         x, y = v if len(v)==2 else v[:2]
                         draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
                         break
        return Image.alpha_composite(img, overlay)
    except: return None

def process_audio(audio_bytes):
    r = sr.Recognizer()
    try:
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            return r.recognize_google(r.record(source), language="he-IL")
    except: return None

# --- עיצוב ---
def add_custom_design():
    st.markdown("""
        <style>
        .stApp { background-color: #e0f7fa; }
        h1, h2, h3, h4, p, label, div, span, input, textarea { color: black !important; }
        [data-testid="stSidebar"] { background-color: #b0bec5; border-right: 2px solid #546e7a; }
        .stButton button { background-color: #b9f6ca; border: 1px solid black !important; border-radius: 10px; }
        .stTextArea textarea, .stTextInput input { background-color: white !important; border: 1px solid #ccc; }
        .section-header { background-color: #00695c; color: white !important; padding: 5px 10px; border-radius: 5px; margin-top: 15px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

# --- App ---
st.set_page_config(layout="wide", page_title="Sunrise Mobile")
add_custom_design()
coords, clinic_db = load_data()
if 'clinic_db' not in st.session_state: st.session_state.clinic_db = clinic_db
if 'coords' not in st.session_state: st.session_state.coords = coords

# משתנה לשמירת המטופל הפעיל בזיכרון (כדי לא לאבד במעבר)
if 'active_patient_id' not in st.session_state: st.session_state.active_patient_id = None

with st.sidebar:
    st.title("👨‍⚕️ ניהול")
    therapist_list = list(st.session_state.clinic_db.keys())
    selected_therapist = st.selectbox("מטפל:", therapist_list)
    therapist_data = st.session_state.clinic_db[selected_therapist]
    
    # תמיכה לאחור
    if "profile" not in therapist_data:
        therapist_data = {"profile": {"gender": "Male"}, "patients": therapist_data}
    
    # תמונה
    img = therapist_data["profile"].get("image_path")
    if img: st.markdown(circular_avatar_html(img), unsafe_allow_html=True)
    
    patients_dict = therapist_data.get("patients", {})
    
    st.markdown("---")
    # יצירת מטופל חדש - עם איפוס מסך!
    with st.expander("➕ מטופל חדש"):
        new_p = st.text_input("שם:")
        new_g = st.radio("מין:", ["Male", "Female"], horizontal=True)
        if st.button("צור תיק נקי"):
            if new_p and new_p not in patients_dict:
                # יצירת התיק
                patients_dict[new_p] = {"gender": new_g, "age": "", "text": "", "analysis": {}}
                save_db(st.session_state.clinic_db)
                
                # מעבר למטופל החדש וניקוי מסך
                st.session_state.active_patient_id = new_p
                reset_screen_fields() # ניקוי קריטי!
                st.rerun()

    # בחירת מטופל קיים
    if len(patients_dict) > 0:
        # אם אין מטופל פעיל, בחר את הראשון
        if not st.session_state.active_patient_id or st.session_state.active_patient_id not in patients_dict:
            st.session_state.active_patient_id = list(patients_dict.keys())[0]
            
        selected_p = st.radio("בחר תיק:", list(patients_dict.keys()), index=list(patients_dict.keys()).index(st.session_state.active_patient_id))
        
        # אם המשתמש החליף מטופל ידנית ברדיו
        if selected_p != st.session_state.active_patient_id:
            st.session_state.active_patient_id = selected_p
            # טעינת הנתונים של המטופל החדש למסך
            load_patient_to_screen(patients_dict[selected_p])
            st.rerun()
    else:
        st.warning("אין תיקים. צור חדש.")
        st.stop()

# --- עבודה על המטופל הפעיל ---
curr_p = st.session_state.active_patient_id
data = patients_dict[curr_p]
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
p_gender = data.get('gender', 'Male')

c1, c2 = st.columns([1, 6])
with c1: st.write("## 🌅")
with c2: st.markdown(f"### תיק רפואי: {curr_p}")

# --- הקלטה ---
audio = mic_recorder(start_prompt="🎤 התחל הקלטה", stop_prompt="⏹️ סיים ושמור", key='rec')

if audio:
    st.toast("מעבד...")
    text = process_audio(audio['bytes'])
    if text:
        # שמירת הטקסט הגולמי
        data['text'] += "\n" + text
        
        # ניתוח
        res = analyze_text_deep(text)
        
        # עדכון מבנה הנתונים ב-DB
        if res['body_parts']: anl['body_parts'] = res['body_parts']
        if res['pain'] > 0: anl['pain_intensity'] = res['pain']
        
        for k, v in res['fields'].items():
            # הוספת המידע החדש למידע הקיים ב-DB
            old_val = anl.get(k, "")
            anl[k] = f"{old_val}\n{v}".strip()
            
        # עדכון המסך (כדי שנראה את השינוי מיד)
        load_patient_to_screen(data)
        
        save_db(st.session_state.clinic_db)
        st.rerun()

st.markdown("---")

col_form, col_map = st.columns([1.5, 1])

with col_form:
    # אתחול שדות אם לא קיימים (למניעת שגיאות)
    if "pp" not in st.session_state: reset_screen_fields()

    st.markdown("<div class='section-header'>History</div>", unsafe_allow_html=True)
    # שימוש ב-key מיוחד שמקושר ל-session_state
    st.text_area("Patient Perspective", key="pp", height=70)
    st.text_area("HPC", key="hpc", height=70)
    
    c1, c2 = st.columns(2)
    with c1: st.text_area("Social History", key="soc", height=60)
    with c2: st.text_input("Expectations", key="exp")

    st.markdown("<div class='section-header'>Medical</div>", unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    with c3: st.text_input("General Health", key="gh")
    with c4: st.text_input("Medications", key="med")
    
    st.markdown("<div class='section-header'>Pain & Behavior</div>", unsafe_allow_html=True)
    st.slider("VAS (0-10)", 0, 10, key="pain_slider")
    
    c5, c6 = st.columns(2)
    with c5: st.text_area("Aggravating", key="agg", height=60)
    with c6: st.text_area("Easing", key="ease", height=60)
    
    c7, c8 = st.columns(2)
    with c7: st.text_input("Night Pain", key="night")
    with c8: st.text_input("On Waking", key="wake")

    # שמירה ידנית של שינויים בטופס (למקרה שהמשתמש מקליד)
    if st.button("💾 שמור שינויים ידניים"):
        # מעתיק מהמסך ל-DB
        mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease", "night": "night", "wake": "wake", "soc": "soc", "exp": "exp"}
        for db_key, screen_key in mapping.items():
            anl[db_key] = st.session_state[screen_key]
        anl['pain_intensity'] = st.session_state['pain_slider']
        
        save_db(st.session_state.clinic_db)
        st.success("נשמר!")

with col_map:
    st.markdown("### Body Chart")
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    final_img = draw_map(p_gender, parts, pain, st.session_state.coords)
    if final_img: 
        st.image(final_img, use_container_width=True)
        if parts: st.success(f"זוהה: {', '.join(parts)}")
    else: st.warning("No Image")

with st.expander("📝 תמלול מלא"):
    st.text(data['text'])