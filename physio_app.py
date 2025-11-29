import streamlit as st
from streamlit_mic_recorder import mic_recorder
import speech_recognition as sr
from PIL import Image, ImageDraw
import io
import os

# --- הגדרות ---
# אין צורך ב-OpenAI לגרסה זו (המוח מקומי)

# --- עיצוב ---
st.set_page_config(layout="wide", page_title="Sunrise Mobile")
st.markdown("""
    <style>
    .stApp { background-color: #e0f7fa; }
    h1, h2, h3, p, label { color: black !important; }
    
    /* כפתור הקלטה גדול ונוח לנייד */
    .stButton button { 
        background-color: #ffcc80 !important; 
        color: black !important; 
        border: 2px solid black !important;
        font-weight: bold;
        width: 100%;
        height: 60px;
        font-size: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- לוגיקה מקומית (זיהוי מילים) ---
def analyze_text(text):
    res = {"parts": [], "pain": 0}
    t = text
    
    # זיהוי צד
    side = "שמאל" if "שמאל" in t else "ימין"
    view = "אחורי" if any(w in t for w in ["גב", "אחור", "עורף"]) else "קדמי"
    
    # מיפוי איברים
    if "כתף" in t: res["parts"].append(f"כתף {side} - {view}")
    elif "ברך" in t: res["parts"].append(f"ברך {side} - {view}")
    elif "ראש" in t: res["parts"].append(f"ראש - {view}")
    elif "גב תחתון" in t: res["parts"] = ["גב תחתון"]
    elif "גב" in t: res["parts"] = ["גב עליון"]
    
    # זיהוי כאב (מספרים)
    for w in t.split():
        if w.isdigit(): res["pain"] = int(w)
        
    return res

# --- ציור מפה ---
def draw_body_map(parts):
    # נסיון טעינת תמונה
    img_path = "body_male.png" 
    if not os.path.exists(img_path): return None
    
    img = Image.open(img_path).convert("RGBA")
    overlay = Image.new('RGBA', img.size, (255,255,255,0))
    draw = ImageDraw.Draw(overlay)
    
    # קואורדינטות בסיסיות (ניתן להרחיב)
    coords = {
        "כתף ימין - קדמי": (95, 120), "כתף שמאל - קדמי": (205, 120),
        "ברך ימין - קדמי": (115, 460), "ברך שמאל - קדמי": (185, 460),
        "ראש - קדמי": (150, 40), "גב תחתון": (450, 240)
    }
    
    for part in parts:
        if part in coords:
            x, y = coords[part]
            # עיגול אדום גדול
            draw.ellipse((x-25, y-25, x+25, y+25), fill=(255, 0, 0, 150))
    
    return Image.alpha_composite(img, overlay)

# --- ממשק האפליקציה ---
c1, c2 = st.columns([1, 5])
with c1: st.write("## 🌅")
with c2: st.title("Sunrise Mobile")

if 'transcription' not in st.session_state: st.session_state.transcription = ""

# --- כפתור ההקלטה החדש (שעובד בטלפון) ---
st.info("👇 לחץ להקלטה (פעם אחת להתחלה, פעם אחת לסיום)")

# הרכיב הזה מחליף את sr.Microphone() הבעייתי
audio = mic_recorder(
    start_prompt="🎤 התחל הקלטה",
    stop_prompt="⏹️ סיים ושמור",
    key='recorder',
    format="wav"
)

if audio:
    # עיבוד ההקלטה רק לאחר שהסתיימה
    st.toast("מעבד שמע...")
    r = sr.Recognizer()
    try:
        audio_data = io.BytesIO(audio['bytes'])
        with sr.AudioFile(audio_data) as source:
            audio_content = r.record(source)
            text = r.recognize_google(audio_content, language="he-IL")
            st.session_state.transcription = text
    except Exception as e:
        st.error("לא הצלחתי להבין את הדיבור")

# --- תצוגת תוצאות ---
st.markdown("---")

# ניתוח הטקסט
analysis = analyze_text(st.session_state.transcription)

col_form, col_map = st.columns(2)

with col_form:
    st.subheader("פרטים")
    st.text_area("תמלול", value=st.session_state.transcription, height=100)
    st.slider("עוצמת כאב", 0, 10, value=analysis['pain'])

with col_map:
    st.subheader("מפה")
    if analysis['parts']:
        st.success(f"זוהה: {', '.join(analysis['parts'])}")
        
    final_img = draw_body_map(analysis['parts'])
    if final_img:
        st.image(final_img, use_container_width=True)
    else:
        st.warning("לא נמצאה תמונת גוף (body_male.png)")