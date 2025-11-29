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
LOGO_FILE = "logo.png"
IMAGES_DIR = "therapist_images"

if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)

# --- המוח הרפואי (Medical Knowledge Base) ---
# זהו מנוע שמכיל ידע רפואי וממיין אותו לקטגוריות
MEDICAL_KNOWLEDGE = {
    "hpc": [
        "נפלתי", "תאונה", "חבלה", "מכה", "סיבוב", "תנועה לא טובה", "התחיל", "לפני", 
        "חריף", "כרוני", "פתאומי", "הדרגתי", "מתמשך", "החמרה", "התקף", "טראומה",
        "תאונת דרכים", "צליפצ", "וויפלש", "הרמתי", "סחבתי", "אימון", "חדר כושר"
    ],
    "gh": [
        "סוכרת", "לחץ דם", "יתר לחץ דם", "שומנים", "כולסטרול", "לב", "אסטמה", "עישון",
        "סרטן", "ניתוח", "שבר", "פריקה", "אוסטיאופורוזיס", "דלקת פרקים", "הריון",
        "ניתוח קיסרי", "אפנדציט", "בלוטת התריס", "משקל", "גובה", "BMI", "pacemaker"
    ],
    "med": [
        "כדור", "תרופה", "אקמול", "אופטלגין", "נורופן", "אדוויל", "ארקוקסיה", "אתופן",
        "טרמדקס", "רוקסט", "פרקוסט", "זריקה", "סטרואידים", "חומצה היאלורונית",
        "ct", "mri", "us", "רנטגן", "צילום", "מיפוי עצמות", "emg", "בדיקת דם"
    ],
    "anatomy_front": [
        "חזה", "בטן", "סטרנום", "צלעות", "מפשעה", "ארבע ראשי", "קוואד", "שוק", "פנים", "עיניים", "לסת"
    ],
    "anatomy_back": [
        "גב", "עמוד שדרה", "שכמה", "סקפולה", "עכוז", "ישבן", "המסטרינג", "תאומים", "אחורי", "עורף"
    ],
    "anatomy_joints": [
        "כתף", "ברך", "קרסול", "ירך", "מרפק", "שורש כף יד", "אצבעות", "בוהן"
    ],
    "pain_desc": [
        "שורף", "דוקר", "לוחץ", "עמום", "חד", "מקרין", "זרמים", "נימול", "רדימות", "פעימות"
    ],
    "agg": [
        "הליכה", "עמידה", "ישיבה", "שכיבה", "כיפוף", "יישור", "רוטציה", "נהיגה", 
        "מדרגות", "עליה", "ירידה", "ריצה", "קפיצה", "שיעול", "עיטוש", "מאמץ"
    ],
    "ease": [
        "מנוחה", "שינוי תנוחה", "חימום", "קירור", "קרח", "מקלחת", "מסאז", "מתיחה", "כרית"
    ],
    "night": [
        "לילה", "שינה", "מתעורר", "נרדם", "כאב לילי", "צד", "גב", "בטן"
    ],
    "soc": [
        "עובד", "פנסיה", "סטודנט", "משרד", "הייטק", "פיזי", "נהג", "נשוי", "רווק", "ילדים",
        "לבד", "קומה", "מעלית", "מדרגות בבית", "ספורטאי", "תחביב"
    ]
}

# --- פונקציות תשתית ---
def load_data():
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], "כתף שמאל - קדמי": [205, 120],
        "חזה": [150, 150], "בטן": [150, 240], "אגן - קדמי": [150, 290],
        "ברך ימין - קדמי": [115, 460], "ברך שמאל - קדמי": [185, 460],
        "גב עליון": [450, 160], "גב תחתון": [450, 240]
    }
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    # טעינת DB - אם אין קובץ, מחזירים מילון ריק!
    db = {} 
    if os.path.exists(DB_FILE):
        try: db = json.load(open(DB_FILE, "r", encoding="utf-8"))
        except: pass
    return coords, db

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    return None

# --- עיצוב UI/UX מקצועי (Medical Clean) ---
def add_custom_design():
    st.markdown("""
        <style>
        /* ייבוא פונט נקי (Heebo/Roboto) */
        @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Heebo', sans-serif;
            direction: rtl;
        }
        
        /* רקע כללי נקי */
        .stApp {
            background-color: #F4F6F7; 
        }
        
        /* סרגל צד מקצועי */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-left: 1px solid #E0E0E0;
            box-shadow: -2px 0 5px rgba(0,0,0,0.05);
        }
        
        /* כותרות */
        h1, h2, h3 {
            color: #2C3E50 !important;
            font-weight: 700;
        }
        
        /* כרטיסיות מידע (Cards) */
        .css-1r6slb0, .stTextArea, .stTextInput {
            background-color: #FFFFFF;
            border-radius: 8px;
            
        }
        
        /* שדות קלט */
        .stTextArea textarea, .stTextInput input {
            background-color: #FFFFFF !important;
            border: 1px solid #CFD8DC;
            border-radius: 6px;
            color: #37474F !important;
        }
        .stTextArea textarea:focus, .stTextInput input:focus {
            border-color: #009688;
            box-shadow: 0 0 0 1px #009688;
        }

        /* כפתורים - עיצוב מודרני */
        .stButton button {
            background-color: #00897B !important; /* Teal */
            color: white !important;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            transition: all 0.3s;
        }
        .stButton button:hover {
            background-color: #00796B !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        
        /* כפתור מחיקה - אדום עדין */
        .delete-btn button {
            background-color: #FFEBEE !important;
            color: #D32F2F !important;
            border: 1px solid #FFCDD2 !important;
        }
        
        /* כותרות סקשנים בטופס */
        .form-header {
            background: linear-gradient(90deg, #00695c 0%, #00897B 100%);
            color: white;
            padding: 8px 15px;
            border-radius: 6px;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 1.1em;
            display: flex;
            align-items: center;
        }
        
        /* תגיות (Labels) */
        label {
            color: #546E7A !important;
            font-weight: 600;
            font-size: 0.9rem;
        }
        
        </style>
    """, unsafe_allow_html=True)

# --- מנוע הבינה המלאכותית (Medical Engine) ---
def analyze_medical_text(text):
    res = {"body_parts": [], "pain": 0, "fields": {}}
    t = text.replace(",", " ").replace(".", " ")
    
    # 1. זיהוי צד וכיוון
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in MEDICAL_KNOWLEDGE["anatomy_back"]) else "קדמי"
    
    # 2. זיהוי אנטומיה חכם
    for organ in MEDICAL_KNOWLEDGE["anatomy_joints"]:
        if organ in t:
            res["body_parts"].append(f"{organ} {side} - {view}")
    
    for organ in MEDICAL_KNOWLEDGE["anatomy_front"]:
        if organ in t: res["body_parts"].append(organ) # מיקומים מרכזיים
        
    for organ in MEDICAL_KNOWLEDGE["anatomy_back"]:
        if organ in t and "גב" in organ: # טיפול מיוחד לגב
            if "תחתון" in t: res["body_parts"].append("גב תחתון")
            elif "עליון" in t: res["body_parts"].append("גב עליון")
            else: res["body_parts"].append("גב תחתון") # ברירת מחדל

    # 3. זיהוי כאב
    for w in t.split():
        if w.isdigit() and int(w) <= 10: res["pain"] = int(w)

    # 4. סיווג לקטגוריות
    # סורק את כל המילון הרפואי ומחפש התאמות
    for category, keywords in MEDICAL_KNOWLEDGE.items():
        found_terms = []
        for term in keywords:
            if term in t:
                # טריק: מוצא את המילה ולוקח קצת הקשר (3 מילים קדימה ואחורה)
                words = t.split()
                try:
                    idx = words.index(term)
                    start = max(0, idx - 2)
                    end = min(len(words), idx + 4)
                    context = " ".join(words[start:end])
                    found_terms.append(context)
                except:
                    found_terms.append(term)
        
        if found_terms:
            # מיפוי שמות קטגוריות לשמות שדות ב-DB
            field_map = {
                "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", 
                "ease": "ease", "night": "night", "soc": "soc"
            }
            if category in field_map:
                res["fields"][field_map[category]] = " | ".join(list(set(found_terms)))
    
    # תמיד שומר את הטקסט המלא ב-Perspective
    if "pp" not in res["fields"]:
        res["fields"]["pp"] = t
        
    return res

def draw_map(gender, parts, intensity, coords):
    try:
        path = "body_male.png" if gender == "Male" else "body_female.png"
        if not os.path.exists(path): return None
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        color = (231, 76, 60, 180) # אדום רפואי יפה
        
        for part in parts:
            found = False
            # חיפוש מדויק
            if part in coords:
                x, y = coords[part][:2]
                draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
                found = True
            # חיפוש חכם (Fuzzy)
            else:
                base = part.split(" - ")[0]
                for k, v in coords.items():
                    if base in k:
                        x, y = v[:2]
                        draw.ellipse((x-25, y-25, x+25, y+25), fill=color)
                        found = True
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

# --- Main App ---
st.set_page_config(layout="wide", page_title="Medical Intake AI")
add_custom_design()

coords, clinic_db = load_data()
if 'clinic_db' not in st.session_state: st.session_state.clinic_db = clinic_db
if 'coords' not in st.session_state: st.session_state.coords = coords

# --- Sidebar ---
with st.sidebar:
    # לוגו
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, use_container_width=True)
    else:
        st.markdown("## 🏥 Medical AI")
    
    st.markdown("---")
    
    # 1. בחירת מטפל (אם הרשימה ריקה - מציג רק הוספה)
    therapists = list(st.session_state.clinic_db.keys())
    
    if not therapists:
        st.warning("המערכת ריקה. אנא הוסף מטפל ראשון.")
        with st.expander("➕ הוספת מטפל", expanded=True):
            new_t = st.text_input("שם המטפל:")
            new_g = st.radio("מגדר:", ["Male", "Female"], horizontal=True)
            up_file = st.file_uploader("תמונה (אופציונלי)", type=['png', 'jpg'])
            if st.button("צור פרופיל"):
                if new_t:
                    path = None
                    if up_file:
                        path = os.path.join(IMAGES_DIR, f"{new_t}.png")
                        with open(path, "wb") as f: f.write(up_file.getbuffer())
                    st.session_state.clinic_db[new_t] = {"profile": {"gender": new_g, "image_path": path}, "patients": {}}
                    save_db(st.session_state.clinic_db)
                    st.rerun()
        st.stop() # עוצר כאן עד שיווצר מטפל
        
    else:
        selected_t = st.selectbox("מטפל מחובר:", therapists)
        t_data = st.session_state.clinic_db[selected_t]
        
        # תמונת מטפל
        img_path = t_data["profile"].get("image_path")
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{b64}" style="width:100px;height:100px;border-radius:50%;border:3px solid #009688;"></div>', unsafe_allow_html=True)
        else:
            emoji = "👨‍⚕️" if t_data["profile"]["gender"]=="Male" else "👩‍⚕️"
            st.markdown(f"<div style='text-align:center;font-size:60px;'>{emoji}</div>", unsafe_allow_html=True)
            
        patients = t_data["patients"]
        
        st.markdown("---")
        
        # ניהול מטופלים
        with st.expander("➕ מטופל חדש"):
            p_name = st.text_input("שם מלא:")
            p_gen = st.radio("מין:", ["Male", "Female"], horizontal=True, key="p_gen")
            if st.button("פתח תיק"):
                if p_name and p_name not in patients:
                    patients[p_name] = {"gender": p_gen, "age": "", "text": "", "analysis": {}}
                    save_db(st.session_state.clinic_db)
                    st.rerun()
        
        if patients:
            curr_p = st.selectbox("בחר מטופל:", list(patients.keys()))
            # כפתור מחיקה
            st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
            if st.button("🗑️ מחק תיק"):
                del patients[curr_p]
                save_db(st.session_state.clinic_db)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("אין תיקים פתוחים.")
            st.stop()

# --- Main Content ---
data = patients[curr_p]
if 'analysis' not in data: data['analysis'] = {}
anl = data['analysis']
p_gen = data.get('gender', 'Male')

# כותרת ראשית
st.markdown(f"## תיק רפואי: {curr_p}")
st.caption(f"תאריך: {datetime.date.today().strftime('%d/%m/%Y')} | מין: {'זכר' if p_gen=='Male' else 'נקבה'}")

# הקלטה
audio = mic_recorder(start_prompt="🎤 התחל הקלטה", stop_prompt="⏹️ סיים ונתח", key='rec')

if audio:
    st.toast("מנתח שמע...")
    text = process_audio(audio['bytes'])
    if text:
        data['text'] += "\n" + text
        # המנוע הרפואי בפעולה
        res = analyze_medical_text(text)
        
        # עדכון גרפי
        if res['body_parts']: anl['body_parts'] = res['body_parts']
        if res['pain'] > 0: anl['pain_intensity'] = res['pain']
        
        # עדכון שדות טקסט (הוספה חכמה)
        mapping = {"pp": "pp", "hpc": "hpc", "gh": "gh", "med": "med", "agg": "agg", "ease": "ease", "night": "night", "soc": "soc"}
        for k, v in mapping.items():
            if k in res['fields']:
                curr = st.session_state.get(v, "")
                # משרשר רק אם המידע חדש
                if res['fields'][k] not in curr:
                    st.session_state[v] = f"{curr}\n• {res['fields'][k]}".strip()
        
        save_db(st.session_state.clinic_db)
        st.rerun()

st.markdown("---")

col_form, col_map = st.columns([1.5, 1])

with col_form:
    # אתחול שדות
    fields = ["pp", "hpc", "gh", "med", "agg", "ease", "night", "soc", "exp", "plan"]
    for f in fields: 
        if f not in st.session_state: st.session_state[f] = ""

    st.markdown("<div class='form-header'>Subjective Assessment</div>", unsafe_allow_html=True)
    st.text_area("Patient's Perspective", key="pp", height=70)
    st.text_area("HPC (History of Present Condition)", key="hpc", height=90)
    
    c1, c2 = st.columns(2)
    with c1: st.text_area("Social History", key="soc", height=60)
    with c2: st.text_input("Expectations", key="exp")

    st.markdown("<div class='form-header'>Medical Background</div>", unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    with c3: st.text_area("General Health / FH", key="gh", height=60)
    with c4: st.text_area("Medications / Imaging", key="med", height=60)
    
    st.markdown("<div class='form-header'>Symptoms & Behavior</div>", unsafe_allow_html=True)
    pain_val = anl.get('pain_intensity', 0)
    st.slider("Pain Intensity (VAS)", 0, 10, int(pain_val))
    
    c5, c6 = st.columns(2)
    with c5: st.text_area("Aggravating Factors", key="agg", height=60)
    with c6: st.text_area("Easing Factors", key="ease", height=60)
    
    st.text_input("24h / Night Pain", key="night")

    st.markdown("<div class='form-header'>Plan</div>", unsafe_allow_html=True)
    st.text_area("Physical Examination Plan", key="plan", height=80)

with col_map:
    st.markdown("### Body Chart")
    parts = anl.get('body_parts', [])
    pain = anl.get('pain_intensity', 0)
    final_img = draw_map(p_gen, parts, pain, st.session_state.coords)
    
    if final_img: 
        st.image(final_img, use_container_width=True)
        if parts: st.info(f"זוהה: {', '.join(parts)}")
    else: 
        st.error("Missing Image File")

with st.expander("📝 תמלול מלא (לביקורת)"):
    st.text(data['text'])