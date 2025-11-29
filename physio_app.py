import streamlit as st
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import datetime
# ספריית עיבוד תמונה בסיסית של פייתון (לעיגול תמונות)
import base64

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"

# --- פונקציות עזר לתמונות ---
def get_image_base64(image_path):
    """ממיר תמונה לקוד כדי להציג אותה בעיגול ב-HTML"""
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    return None

def circular_avatar_html(image_path, gender):
    """יוצר אלמנט HTML של תמונה עגולה"""
    img_b64 = get_image_base64(image_path)
    
    # אם אין תמונה, נשתמש באייקון
    if not img_b64:
        emoji = "👨‍⚕️" if gender == "Male" else "👩‍⚕️"
        return f"""<div style='font-size: 50px; text-align: center; 
                    background-color: #ffffff; border-radius: 50%; 
                    width: 80px; height: 80px; line-height: 80px; 
                    border: 2px solid #00695c; margin: auto;'>{emoji}</div>"""
    
    return f"""
        <div style="display: flex; justify-content: center;">
            <img src="data:image/png;base64,{img_b64}" 
            style="border-radius: 50%; width: 80px; height: 80px; object-fit: cover; border: 3px solid #00695c;">
        </div>
    """

# --- פונקציות טעינה ושמירה ---
def load_data():
    # קואורדינטות
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], 
        "ברך ימין - קדמי": [115, 460], "גב תחתון": [450, 240] 
        # (רשימה חלקית לברירת מחדל, הקובץ המלא נטען אם קיים)
    }
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    # בסיס נתונים (מבנה משודרג עם פרופיל)
    # מבנה: { "שם המטפל": { "profile": {"gender": "Male"}, "patients": { ... } } }
    db = {
        "דניאל": {
            "profile": {"gender": "Male"},
            "patients": {
                "מטופל בדיקה": {"gender": "Male", "age": "30", "text": "", "analysis": {}}
            }
        }
    }
    
    if os.path.exists(DB_FILE):
        try: 
            loaded_db = json.load(open(DB_FILE, "r", encoding="utf-8"))
            # בדיקת תאימות למבנה החדש (מיגרציה קטנה)
            if loaded_db and "profile" not in list(loaded_db.values())[0]:
                # המרה ממבנה ישן לחדש אם צריך
                new_db = {}
                for therapist, patients in loaded_db.items():
                    new_db[therapist] = {"profile": {"gender": "Male"}, "patients": patients}
                return coords, new_db
            return coords, loaded_db
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
        h1, h2, h3, h4, p, label, div, span, input, textarea { color: black !important; }
        
        [data-testid="stSidebar"] { background-color: #b0bec5; border-right: 2px solid #546e7a; }

        /* כפתורים כתומים בסרגל צד */
        section[data-testid="stSidebar"] .stButton button {
            background-color: #ffcc80 !important;
            border: 1px solid #ef6c00 !important;
            color: black !important;
            font-weight: bold;
        }
        
        /* כפתור הקלטה לנייד */
        .stButton button { 
            background-color: #b9f6ca; 
            color: black !important; 
            border: 1px solid black !important; 
            border-radius: 10px;
        }
        
        .stTextArea textarea, .stTextInput input { background-color: white !important; border: 1px solid #ccc; }
        .section-header { background-color: #00695c; color: white !important; padding: 5px 10px; border-radius: 5px; margin-top: 15px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

# --- לוגיקה עסקית (אותה לוגיקה שעבדה מצוין) ---
def analyze_text_rules(text):
    res = {"body_parts": [], "pain": 0, "fields": {}}
    t = text 
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["גב", "אחור", "עורף"]) else "קדמי"
    
    if "כתף" in t: res["body_parts"].append(f"כתף {side} - {view}")
    elif "ברך" in t: res["body_parts"].append(f"ברך {side} - {view}")
    elif "ראש" in t: res["body_parts"].append(f"ראש - {view}")
    elif "גב תחתון" in t: res["body_parts"].append("גב תחתון")
    elif "גב" in t: res["body_parts"].append("גב עליון")

    for w in t.split():
        if w.isdigit() and int(w) <= 10: res["pain"] = int(w)

    KEYWORDS = {"hpc": ["נפלתי", "תאונה", "כואב"], "gh": ["סוכרת", "לחץ"], "med": ["כדור", "אקמול"], "pp": []}
    for cat, keys in KEYWORDS.items():
        if any(k in t for k in keys) or cat == "pp": res["fields"][cat] = t 
    return res

def draw_map(gender, parts, intensity, coords):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        if not os.path.exists(path): return None
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        color = (255, 0, 0, int(50 + (intensity * 20)) if intensity else 150)
        for part in parts:
            if part in coords:
                x, y = coords[part] if len(coords[part])==2 else coords[part][:2]
                draw.ellipse((x-20, y-20, x+20, y+20), fill=color)
            else: # Fallback
                for k, v in coords.items():
                    if part.split(" - ")[0] in k:
                         x, y = v if len(v)==2 else v[:2]
                         draw.ellipse((x-20, y-20, x+20, y+20), fill=color)
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

# --- אפליקציה ראשית ---
st.set_page_config(layout="wide", page_title="Sunrise Mobile")
add_custom_design()

# טעינה
coords, clinic_db = load_data()
if 'clinic_db' not in st.session_state: st.session_state.clinic_db = clinic_db
if 'coords' not in st.session_state: st.session_state.coords = coords

# --- סרגל צד ---
with st.sidebar:
    st.title("🗂️ ניהול קליניקה")
    
    # 1. בחירת מטפל והצגת תמונה
    therapist_list = list(st.session_state.clinic_db.keys())
    selected_therapist = st.selectbox("בחר מטפל:", therapist_list)
    
    # שליפת נתוני המטפל הנבחר
    therapist_data = st.session_state.clinic_db[selected_therapist]
    # (תמיכה לאחור בגרסאות ישנות של ה-DB)
    if "profile" not in therapist_data:
        therapist_data = {"profile": {"gender": "Male"}, "patients": therapist_data}
        st.session_state.clinic_db[selected_therapist] = therapist_data
        
    therapist_profile = therapist_data.get("profile", {"gender": "Male"})
    patients_dict = therapist_data.get("patients", {})
    
    # הצגת תמונת המטפל (עיגול)
    t_gender = therapist_profile.get("gender", "Male")
    t_img_path = "therapist_male.png" if t_gender == "Male" else "therapist_female.png"
    st.markdown(circular_avatar_html(t_img_path, t_gender), unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:center; font-weight:bold; margin-bottom:20px;'>{selected_therapist}</div>", unsafe_allow_html=True)

    # 2. הוספת מטפל חדש
    with st.expander("👨‍⚕️ הוספת מטפל חדש"):
        new_t_name = st.text_input("שם המטפל:")
        new_t_gender = st.radio("מגדר:", ["Male", "Female"], horizontal=True, key="new_t_gen")
        if st.button("הוסף לצוות"):
            if new_t_name and new_t_name not in st.session_state.clinic_db:
                st.session_state.clinic_db[new_t_name] = {
                    "profile": {"gender": new_t_gender},
                    "patients": {}
                }
                save_db(st.session_state.clinic_db)
                st.success("נוסף בהצלחה!")
                st.rerun()

    st.markdown("---")

    # 3. ניהול מטופלים של המטפל הזה
    with st.expander("➕ הוספת מטופל", expanded=True):
        nn = st.text_input("שם מטופל:")
        ng = st.radio("מין מטופל:", ["Male", "Female"], horizontal=True, key="new_p_gen")
        if st.button("פתח תיק חדש"):
            if nn:
                patients_dict[nn] = {"gender": ng, "age": "", "text": "", "analysis": {}}
                save_db(st.session_state.clinic_db)
                st.rerun()

    if len(patients_dict) > 0:
        curr_p = st.radio("תיק פעיל:", list(patients_dict.keys()))
        if st.button("🗑️ מחק תיק"):
            del patients_dict[curr_p]
            save_db(st.session_state.clinic_db)
            st.rerun()
    else:
        st.info("אין מטופלים למטפל זה.")
        st.stop()

# --- תוכן ראשי ---
data = patients_dict.get(curr_p, {})
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
p_gender = data.get('gender', 'Male')

c1, c2 = st.columns([1, 6])
with c1: st.markdown("## 🌅")
with c2: st.title("Sunrise Physio")

st.info(f"תיק רפואי: **{curr_p}**")

# כפתור הקלטה לנייד
audio = mic_recorder(start_prompt="🎤 התחל הקלטה", stop_prompt="⏹️ סיים ושמור", key='rec')

if audio:
    st.toast("מעבד...")
    text = process_audio(audio['bytes'])
    if text:
        data['text'] += "\n" + text
        res = analyze_text_rules(text)
        anl['body_parts'] = res['body_parts']
        anl['pain_intensity'] = res['pain']
        
        mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease"}
        for k, v in mapping.items():
            if k in res['fields']:
                curr = st.session_state.get(v, "")
                st.session_state[v] = f"{curr} {res['fields'][k]}".strip()
        
        save_db(st.session_state.clinic_db)
        st.rerun()

st.markdown("---")

col_form, col_map = st.columns([1.5, 1])

with col_form:
    # אתחול שדות
    for f in ["pp", "hpc", "gh", "med", "agg", "ease", "night", "wake", "plan"]:
        if f not in st.session_state: st.session_state[f] = ""

    st.markdown("<div class='section-header'>History</div>", unsafe_allow_html=True)
    st.text_area("Patient Perspective", key="pp", height=70)
    st.text_area("HPC", key="hpc", height=70)
    
    c_h1, c_h2 = st.columns(2)
    with c_h1: st.text_input("General Health", key="gh")
    with c_h2: st.text_input("Medications", key="med")
    
    st.markdown("<div class='section-header'>Pain</div>", unsafe_allow_html=True)
    curr_pain = anl.get('pain_intensity', 0)
    st.slider("VAS (0-10)", 0, 10, int(curr_pain))
    
    c_p1, c_p2 = st.columns(2)
    with c_p1: st.text_area("Aggravating", key="agg", height=60)
    with c_p2: st.text_area("Easing", key="ease", height=60)

with col_map:
    st.markdown("### Body Chart")
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    final_img = draw_map(p_gender, parts, pain, st.session_state.coords)
    
    if final_img: 
        st.image(final_img, use_container_width=True)
        if parts: st.success(f"זוהה: {', '.join(parts)}")
    else: 
        st.warning("No Image")

with st.expander("📝 היסטוריית תמלול"):
    st.text(data['text'])