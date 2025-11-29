import streamlit as st
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import base64
import shutil # ספרייה לשמירת קבצי תמונה

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"
IMAGES_DIR = "therapist_images" # תיקייה לשמירת תמונות מטפלים

# יצירת תיקיית תמונות אם אינה קיימת
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

# --- פונקציות עזר לתמונות (עיגול) ---
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    return None

def circular_avatar_html(image_path):
    """יוצר אלמנט HTML של תמונה עגולה מתמונה קיימת"""
    img_b64 = get_image_base64(image_path)
    if not img_b64: return "" # לא מציג כלום אם אין תמונה
    
    return f"""
        <div style="display: flex; justify-content: center; margin-bottom: 15px;">
            <img src="data:image/png;base64,{img_b64}" 
            style="border-radius: 50%; width: 100px; height: 100px; object-fit: cover; border: 3px solid #ffcc80; box-shadow: 0px 4px 8px rgba(0,0,0,0.2);">
        </div>
    """

# --- פונקציות טעינה ושמירה ---
def load_data():
    # קואורדינטות ברירת מחדל
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], "כתף שמאל - קדמי": [205, 120],
        "ברך ימין - קדמי": [115, 460], "ברך שמאל - קדמי": [185, 460],
        "גב עליון": [450, 160], "גב תחתון": [450, 240], "אגן - אחורי": [450, 300]
    }
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    # בסיס נתונים - מבנה התחלתי
    db = {
        "דניאל (הדגמה)": {
            "profile": {"gender": "Male", "image_path": None},
            "patients": {
                "מטופל בדיקה": {"gender": "Male", "age": "30", "text": "", "analysis": {}}
            }
        }
    }
    
    if os.path.exists(DB_FILE):
        try: 
            loaded_db = json.load(open(DB_FILE, "r", encoding="utf-8"))
            if loaded_db:
                # מיגרציה קלה למקרה של מבנה ישן
                first_key = next(iter(loaded_db))
                if "profile" not in loaded_db[first_key]:
                     new_db = {}
                     for t, p in loaded_db.items():
                         new_db[t] = {"profile": {"gender": "Male", "image_path": None}, "patients": p}
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
        
        /* סרגל צד */
        [data-testid="stSidebar"] { background-color: #b0bec5; border-right: 2px solid #546e7a; }
        section[data-testid="stSidebar"] .stButton button {
            background-color: #ffcc80 !important; border: 1px solid #ef6c00 !important; color: black !important; font-weight: bold;
        }
        
        /* כפתור הקלטה נייד */
        .stButton button { background-color: #b9f6ca; border: 1px solid black !important; border-radius: 10px; }
        
        /* שדות וטפסים */
        .stTextArea textarea, .stTextInput input { background-color: white !important; border: 1px solid #ccc; }
        .section-header { background-color: #00695c; color: white !important; padding: 5px 10px; border-radius: 5px; margin-top: 15px; font-weight: bold; }
        
        /* כותרת שם מטופל */
        .patient-header { font-size: 22px; font-weight: bold; color: #00695c !important; margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)

# --- המוח (Local Logic) - תוקן ושופר ---
def analyze_text_rules(text):
    res = {"body_parts": [], "pain": 0, "fields": {}}
    t = text.replace(",", "").replace(".", "") # ניקוי סימני פיסוק
    
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["גב", "אחור", "עורף", "ישבן", "שכמה"]) else "קדמי"
    
    # זיהוי איברים מורחב
    if "כתף" in t: res["body_parts"].append(f"כתף {side} - {view}")
    if "ברך" in t: res["body_parts"].append(f"ברך {side} - {view}")
    if "ראש" in t or "כאב ראש" in t: res["body_parts"].append(f"ראש - {view}")
    if "צוואר" in t: res["body_parts"].append(f"צוואר - {view}")
    if "גב תחתון" in t or "מותנית" in t: res["body_parts"].append("גב תחתון")
    if "גב" in t and "תחתון" not in t: res["body_parts"].append("גב עליון")
    if "אגן" in t or "ירך" in t: res["body_parts"].append(f"אגן - {view}")

    # הסרת כפילויות
    res["body_parts"] = list(set(res["body_parts"]))

    for w in t.split():
        if w.isdigit() and int(w) <= 10: res["pain"] = int(w)

    KEYWORDS = {
        "hpc": ["נפלתי", "תאונה", "מכה", "התחיל", "כואב לי"], 
        "gh": ["סוכרת", "לחץ דם", "מחלה", "בריא"], 
        "med": ["כדור", "אקמול", "תרופה", "מרשם"],
        "agg": ["הליכה", "עמידה", "ישיבה", "כיפוף"],
        "ease": ["מנוחה", "שכיבה", "חימום"],
        "night": ["לילה", "ישן", "מתעורר"],
        "pp": []
    }
    for cat, keys in KEYWORDS.items():
        if any(k in t for k in keys) or cat == "pp": res["fields"][cat] = t 
    return res

# --- ציור מפה (תוקן) ---
def draw_map(gender, parts, intensity, coords):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        if not os.path.exists(path): return None
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        
        # צבע אדום עם שקיפות שתלויה בכאב
        alpha = int(80 + (intensity * 15)) if intensity > 0 else 150
        color = (255, 0, 0, alpha)
        
        drawn = False
        for part in parts:
            # 1. ניסיון התאמה מדויקת
            if part in coords:
                x, y = coords[part] if len(coords[part])==2 else coords[part][:2]
                draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
                drawn = True
            # 2. ניסיון התאמה חלקית חכמה (למשל 'כתף ימין' תופס 'כתף ימין - קדמי')
            else:
                base_part = part.split(" - ")[0] # למשל "כתף ימין"
                required_view = part.split(" - ")[1] if " - " in part else "" # למשל "קדמי"
                
                for k, v in coords.items():
                    # בודק אם שם האיבר הבסיסי קיים, ואם יש דרישת כיוון - שגם היא תואמת
                    if base_part in k and (not required_view or required_view in k):
                         x, y = v if len(v)==2 else v[:2]
                         draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
                         drawn = True
                         break # עובר לאיבר הבא
                         
        return Image.alpha_composite(img, overlay)
    except Exception as e: 
        print(f"Error drawing: {e}")
        return None

# --- עיבוד שמע ---
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

coords, clinic_db = load_data()
if 'clinic_db' not in st.session_state: st.session_state.clinic_db = clinic_db
if 'coords' not in st.session_state: st.session_state.coords = coords

# --- סרגל צד: ניהול מטפלים ---
with st.sidebar:
    st.title("👨‍⚕️ ניהול קליניקה")
    
    therapist_list = list(st.session_state.clinic_db.keys())
    selected_therapist = st.selectbox("בחר מטפל:", therapist_list)
    
    therapist_data = st.session_state.clinic_db[selected_therapist]
    t_profile = therapist_data.get("profile", {"gender": "Male", "image_path": None})
    patients_dict = therapist_data.get("patients", {})
    
    # --- הצגת תמונת המטפל הנבחר ---
    final_img_path = None
    # אם יש תמונה אישית שהועלתה - השתמש בה
    if t_profile.get("image_path") and os.path.exists(t_profile["image_path"]):
        final_img_path = t_profile["image_path"]
    # אחרת, השתמש בברירת מחדל לפי מגדר (אם הקבצים קיימים)
    else:
        default_img = "therapist_male.png" if t_profile["gender"] == "Male" else "therapist_female.png"
        if os.path.exists(default_img):
             final_img_path = default_img
             
    if final_img_path:
         st.markdown(circular_avatar_html(final_img_path), unsafe_allow_html=True)

    st.markdown(f"<div style='text-align:center; font-weight:bold; margin-bottom:20px; font-size: 18px;'>{selected_therapist}</div>", unsafe_allow_html=True)

    # --- הוספת מטפל חדש (עם העלאת תמונה) ---
    with st.expander("➕ מטפל חדש (עם תמונה)"):
        new_t_name = st.text_input("שם:")
        new_t_gender = st.radio("מגדר:", ["Male", "Female"], horizontal=True, key="ntg")
        # כפתור העלאת קובץ
        uploaded_file = st.file_uploader("בחר תמונת פרופיל", type=['png', 'jpg', 'jpeg'])
        
        if st.button("צור מטפל"):
            if new_t_name and new_t_name not in st.session_state.clinic_db:
                
                saved_img_path = None
                # שמירת התמונה שהועלתה
                if uploaded_file is not None:
                    file_ext = uploaded_file.name.split('.')[-1]
                    # יצירת שם קובץ ייחודי על בסיס שם המטפל
                    safe_name = "".join([c for c in new_t_name if c.isalpha() or c.isdigit()]).rstrip()
                    saved_img_path = os.path.join(IMAGES_DIR, f"img_{safe_name}.{file_ext}")
                    with open(saved_img_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                # יצירת הרשומה החדשה ב-DB
                st.session_state.clinic_db[new_t_name] = {
                    "profile": {"gender": new_t_gender, "image_path": saved_img_path},
                    "patients": {}
                }
                save_db(st.session_state.clinic_db)
                st.success("מטפל נוסף בהצלחה!")
                st.rerun()

    st.markdown("---")

    # --- ניהול מטופלים ---
    with st.expander("👤 מטופלים", expanded=True):
        nn = st.text_input("שם מטופל חדש:")
        ng = st.radio("מין:", ["Male", "Female"], horizontal=True, key="npg")
        if st.button("פתח תיק"):
            if nn and nn not in patients_dict:
                patients_dict[nn] = {"gender": ng, "age": "", "text": "", "analysis": {}}
                save_db(st.session_state.clinic_db)
                st.rerun()

    if len(patients_dict) > 0:
        curr_p = st.radio("תיק פעיל:", list(patients_dict.keys()))
    else:
        st.info("אין מטופלים.")
        st.stop()

# --- תוכן ראשי ---
data = patients_dict.get(curr_p, {})
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
p_gender = data.get('gender', 'Male')

c1, c2 = st.columns([1, 6])
with c1: st.markdown("## 🌅")
with c2: st.title("Sunrise Physio")

# --- כותרת שם המטופל החדשה ---
st.markdown(f"<h3 class='patient-header'>מטופל: {curr_p}</h3>", unsafe_allow_html=True)

# כפתור הקלטה
audio = mic_recorder(start_prompt="🎤 התחל הקלטה", stop_prompt="⏹️ סיים ושמור", key='rec')

if audio:
    st.toast("מעבד...")
    text = process_audio(audio['bytes'])
    if text:
        data['text'] += "\n" + text
        res = analyze_text_rules(text)
        
        # עדכון ישיר של נתוני הניתוח לבסיס הנתונים
        anl['body_parts'] = res['body_parts']
        anl['pain_intensity'] = res['pain']
        
        mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease", "night":"night"}
        for k, v in mapping.items():
            if k in res['fields']:
                curr = st.session_state.get(v, "")
                st.session_state[v] = f"{curr} {res['fields'][k]}".strip()
        
        save_db(st.session_state.clinic_db)
        st.rerun() # ריענון קריטי כדי שהציור יתעדכן

st.markdown("---")

col_form, col_map = st.columns([1.5, 1])

with col_form:
    for f in ["pp", "hpc", "gh", "med", "agg", "ease", "night", "wake", "plan"]:
        if f not in st.session_state: st.session_state[f] = ""

    st.markdown("<div class='section-header'>History & Subjective</div>", unsafe_allow_html=True)
    st.text_area("Patient Perspective", key="pp", height=70)
    st.text_area("HPC", key="hpc", height=70)
    
    c_h1, c_h2 = st.columns(2)
    with c_h1: st.text_input("General Health", key="gh")
    with c_h2: st.text_input("Medications/Investigations", key="med")
    
    st.markdown("<div class='section-header'>Pain & 24h Behavior</div>", unsafe_allow_html=True)
    curr_pain = anl.get('pain_intensity', 0)
    st.slider("VAS (0-10) - זוהה אוטומטית", 0, 10, int(curr_pain), disabled=True) # סליידר לקריאה בלבד להצגת הזיהוי
    
    c_p1, c_p2 = st.columns(2)
    with c_p1: st.text_area("Aggravating", key="agg", height=60)
    with c_p2: st.text_area("Easing", key="ease", height=60)

    c_n1, c_n2 = st.columns(2)
    with c_n1: st.text_input("Night", key="night")
    with c_n2: st.text_input("Morning/Wake", key="wake")

with col_map:
    st.markdown("### Body Chart")
    # שליפה ישירה של האיברים מה-DB המעודכן
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    
    final_img = draw_map(p_gender, parts, pain, st.session_state.coords)
    
    if final_img: 
        st.image(final_img, use_container_width=True)
        if parts: 
            st.success(f"סומן: {', '.join(parts)}")
    else: 
        st.info("אמור מילה כמו 'כתף', 'ברך' או 'גב' כדי לסמן על המפה.")

with st.expander("📝 תמלול מלא"):
    st.text(data['text'])