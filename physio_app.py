import streamlit as st
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import base64

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"
IMAGES_DIR = "therapist_images"

if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)

# --- פונקציות תמונה (נשאר זהה כי זה עבד מצוין) ---
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

# --- פונקציות נתונים ---
def load_data():
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], "ברך ימין - קדמי": [115, 460],
        "גב תחתון": [450, 240], "גב עליון": [450, 160], "אגן - אחורי": [450, 300]
    }
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    db = {"דניאל": {"profile": {"gender": "Male"}, "patients": {"מטופל בדיקה": {"gender": "Male", "age": "30", "text": ""}}}}
    if os.path.exists(DB_FILE):
        try: db = json.load(open(DB_FILE, "r", encoding="utf-8"))
        except: pass
    return coords, db

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db, f, indent=4, ensure_ascii=False)

# --- עיצוב ---
def add_custom_design():
    st.markdown("""
        <style>
        .stApp { background-color: #e0f7fa; }
        h1, h2, h3, h4, p, label, div, span, input, textarea { color: black !important; }
        [data-testid="stSidebar"] { background-color: #b0bec5; border-right: 2px solid #546e7a; }
        section[data-testid="stSidebar"] .stButton button {
            background-color: #ffcc80 !important; border: 1px solid #ef6c00 !important; color: black !important; font-weight: bold;
        }
        .stButton button { background-color: #b9f6ca; border: 1px solid black !important; border-radius: 10px; }
        .stTextArea textarea, .stTextInput input { background-color: white !important; border: 1px solid #ccc; }
        .section-header { background-color: #00695c; color: white !important; padding: 5px 10px; border-radius: 5px; margin-top: 15px; font-weight: bold; }
        .patient-header { font-size: 22px; font-weight: bold; color: #00695c !important; margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)

# --- המוח המורחב (NLP Logic) ---
def analyze_text_deep(text):
    res = {"body_parts": [], "pain": 0, "fields": {}}
    t = text.replace(",", " ").replace(".", " ")
    
    # 1. זיהוי גוף וכאב (כמו קודם)
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["גב", "אחור", "עורף", "ישבן", "שכמה"]) else "קדמי"
    
    parts_keywords = {
        "כתף": f"כתף {side} - {view}", "ברך": f"ברך {side} - {view}", "ראש": f"ראש - {view}",
        "צוואר": f"צוואר - {view}", "גב תחתון": "גב תחתון", "מותנית": "גב תחתון",
        "גב עליון": "גב עליון", "שכמה": "גב עליון", "קרסול": f"קרסול {side} - {view}"
    }
    for word, mapped in parts_keywords.items():
        if word in t: res["body_parts"].append(mapped)
    
    for w in t.split():
        if w.isdigit() and int(w) <= 10: res["pain"] = int(w)

    # 2. מילון קטגוריות מורחב (הלב של העדכון)
    CATEGORIES = {
        "hpc": ["נפלתי", "תאונה", "מכה", "התחיל", "לפני", "כואב לי", "החלקתי", "סובבתי", "מתלונן", "רקע"],
        "gh": ["סוכרת", "לחץ דם", "מחלה", "בריא", "ניתוח", "שבר", "אשפוז", "כולסטרול", "משקל", "גובה"],
        "med": ["כדור", "אקמול", "תרופה", "מרשם", "אופטלגין", "ארקוקסיה", "זריקה", "סי טי", "MRI", "רנטגן", "צילום"],
        "agg": ["הליכה", "עמידה", "ישיבה", "כיפוף", "הרמה", "מאמץ", "ריצה", "עליה", "ירידה", "נהיגה"],
        "ease": ["מנוחה", "שכיבה", "חימום", "קרח", "מקלחת", "עיסוי", "תנועה"],
        "night": ["לילה", "ישן", "מתעורר", "שינה", "כרית"],
        "wake": ["בוקר", "קם", "נוקשות", "תפוס"],
        "soc": ["עובד", "פנסיה", "נשוי", "רווק", "ילדים", "קומה", "מעלית", "ספורט", "חדר כושר"],
        "exp": ["לחזור", "לרוץ", "ללכת", "בלי כאב", "לטפל", "להבין"]
    }
    
    # אלגוריתם זיהוי: אם מילה מהרשימה מופיעה, קח את המשפט שסביבה
    for cat, keywords in CATEGORIES.items():
        detected = []
        for k in keywords:
            if k in t:
                # טריק: לוקח את המילה ואת ה-5 מילים שאחריה כדי לתת הקשר
                words = t.split()
                try:
                    idx = words.index(k)
                    snippet = " ".join(words[max(0, idx-1) : min(len(words), idx+6)])
                    detected.append(snippet)
                except: 
                    detected.append(k)
        
        if detected:
            # מנקה כפילויות ומחבר
            res["fields"][cat] = " | ".join(list(set(detected)))

    return res

def draw_map(gender, parts, intensity, coords):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        if not os.path.exists(path): return None
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        alpha = int(80 + (intensity * 15)) if intensity > 0 else 150
        color = (255, 0, 0, alpha)
        for part in parts:
            if part in coords:
                x, y = coords[part] if len(coords[part])==2 else coords[part][:2]
                draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
            else:
                base = part.split(" - ")[0]
                for k, v in coords.items():
                    if base in k:
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

# --- Main ---
st.set_page_config(layout="wide", page_title="Sunrise Mobile")
add_custom_design()
coords, clinic_db = load_data()
if 'clinic_db' not in st.session_state: st.session_state.clinic_db = clinic_db
if 'coords' not in st.session_state: st.session_state.coords = coords

with st.sidebar:
    st.title("👨‍⚕️ ניהול")
    therapist_list = list(st.session_state.clinic_db.keys())
    selected_therapist = st.selectbox("מטפל:", therapist_list)
    therapist_data = st.session_state.clinic_db[selected_therapist]
    
    # תמיכה בפורמט ישן
    if "profile" not in therapist_data:
        therapist_data = {"profile": {"gender": "Male"}, "patients": therapist_data}
        st.session_state.clinic_db[selected_therapist] = therapist_data
    
    # הצגת תמונה
    t_profile = therapist_data.get("profile", {})
    t_img = t_profile.get("image_path")
    if t_img: st.markdown(circular_avatar_html(t_img), unsafe_allow_html=True)
    
    patients_dict = therapist_data.get("patients", {})
    
    with st.expander("➕ הוספת מטפל (עם תמונה)"):
        new_t = st.text_input("שם:")
        new_gen = st.radio("מין:", ["Male", "Female"], horizontal=True)
        up_file = st.file_uploader("תמונה", type=['png', 'jpg'])
        if st.button("צור מטפל"):
            if new_t:
                path = None
                if up_file:
                    path = os.path.join(IMAGES_DIR, f"{new_t}.png")
                    with open(path, "wb") as f: f.write(up_file.getbuffer())
                st.session_state.clinic_db[new_t] = {"profile": {"gender": new_gen, "image_path": path}, "patients": {}}
                save_db(st.session_state.clinic_db)
                st.rerun()

    st.markdown("---")
    with st.expander("➕ מטופל חדש", expanded=True):
        nn = st.text_input("שם מטופל:")
        ng = st.radio("מין מטופל:", ["Male", "Female"], horizontal=True)
        if st.button("פתח תיק"):
            if nn:
                patients_dict[nn] = {"gender": ng, "age": "", "text": "", "analysis": {}}
                save_db(st.session_state.clinic_db)
                st.rerun()

    if len(patients_dict) > 0:
        curr_p = st.radio("תיק:", list(patients_dict.keys()))
        if st.button("🗑️ מחק"):
            del patients_dict[curr_p]
            save_db(st.session_state.clinic_db)
            st.rerun()
    else:
        st.info("אין תיקים"); st.stop()

# --- תוכן ---
data = patients_dict.get(curr_p, {})
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
p_gender = data.get('gender', 'Male')

c1, c2 = st.columns([1, 6])
with c1: st.write("## 🌅")
with c2: st.markdown(f"<div class='patient-header'>מטופל: {curr_p}</div>", unsafe_allow_html=True)

# הקלטה
audio = mic_recorder(start_prompt="🎤 התחל הקלטה", stop_prompt="⏹️ סיים ושמור", key='rec')

if audio:
    st.toast("מפענח...")
    text = process_audio(audio['bytes'])
    if text:
        data['text'] += "\n" + text
        # המוח המורחב בפעולה
        res = analyze_text_deep(text)
        
        # שמירת נתונים ויזואליים
        if res['body_parts']: anl['body_parts'] = res['body_parts']
        if res['pain'] > 0: anl['pain_intensity'] = res['pain']
        
        # עדכון שדות הטופס (הוספה חכמה)
        mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease", "night": "night", "wake": "wake", "soc": "soc", "exp": "exp"}
        for k, v in mapping.items():
            if k in res['fields']:
                curr = st.session_state.get(v, "")
                # מוסיף שורה חדשה אם יש מידע חדש
                st.session_state[v] = f"{curr}\n• {res['fields'][k]}".strip()
        
        save_db(st.session_state.clinic_db)
        st.rerun()

st.markdown("---")

col_form, col_map = st.columns([1.5, 1])

with col_form:
    for f in ["pp", "hpc", "gh", "med", "agg", "ease", "night", "wake", "plan", "soc", "exp"]:
        if f not in st.session_state: st.session_state[f] = ""

    st.markdown("<div class='section-header'>History</div>", unsafe_allow_html=True)
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
    curr_pain = anl.get('pain_intensity', 0)
    st.slider("VAS (0-10)", 0, 10, int(curr_pain))
    
    c5, c6 = st.columns(2)
    with c5: st.text_area("Aggravating", key="agg", height=60)
    with c6: st.text_area("Easing", key="ease", height=60)
    
    c7, c8 = st.columns(2)
    with c7: st.text_input("Night Pain", key="night")
    with c8: st.text_input("On Waking", key="wake")

with col_map:
    st.markdown("### Body Chart")
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    final_img = draw_map(p_gender, parts, pain, st.session_state.coords)
    if final_img: 
        st.image(final_img, use_container_width=True)
        if parts: st.success(f"זוהה: {', '.join(parts)}")
    else: st.warning("No Image")

with st.expander("📝 תמלול"):
    st.text(data['text'])