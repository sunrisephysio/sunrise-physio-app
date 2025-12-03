import streamlit as st
# ייבוא רכיבי UI
from streamlit_mic_recorder import mic_recorder
try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    HAS_CALIB = True
except ImportError: HAS_CALIB = False

import os
import datetime
# === החיבור לפועל החדש שלנו ===
import backend as bp 

# --- הגדרות עמוד ועיצוב ---
st.set_page_config(layout="wide", page_title="Sunrise Physio")

def apply_css():
    st.markdown("""
        <style>
        .stApp { background-color: #f4f6f9; direction: rtl; }
        h1, h2, h3, p, label, div, span, input, textarea { color: #111 !important; }
        [data-testid="stSidebar"] { background-color: #ffffff; border-left: 1px solid #ccc; }
        .rec-btn button { 
            background-color: #ff9800 !important; color: black !important; 
            border: 1px solid black; height: 60px; font-size: 20px; font-weight: bold; width: 100%; border-radius: 10px;
        }
        .admin-btn button { background-color: #607d8b !important; color: white !important; width: 100%; margin-top: 20px; }
        .stTextArea textarea, .stTextInput input { background-color: white !important; border: 1px solid #bbb; }
        .section-header { background-color: #00695c; color: white !important; padding: 8px; border-radius: 5px; margin-top: 15px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

apply_css()

# --- ניהול זיכרון (Session State) ---
if 'page' not in st.session_state: st.session_state.page = "clinic"
coords, db = bp.load_data()
st.session_state.coords = coords
st.session_state.clinic_db = db

# ===========================
# דף 1: חדר בקרה (כיול)
# ===========================
if st.session_state.page == "admin":
    if st.sidebar.button("🔙 חזרה לקליניקה"):
        st.session_state.page = "clinic"
        st.rerun()
    
    st.title("⚙️ חדר בקרה")
    c1, c2 = st.columns([1, 2])
    with c1:
        new_p = st.text_input("שם נקודה לכיול:", placeholder="למשל: מרפק שמאל")
        st.write("נקודות קיימות:"); st.json(list(st.session_state.coords.keys()))
    with c2:
        if HAS_CALIB and os.path.exists("body_male.png"):
            val = streamlit_image_coordinates("body_male.png", key="calib")
            if val and new_p:
                st.session_state.coords[new_p] = [val['x'], val['y']]
                bp.save_coords(st.session_state.coords)
                st.success(f"נשמר: {new_p}"); st.rerun()
        else: st.warning("אין תמונה או רכיב כיול")

# ===========================
# דף 2: הקליניקה (ראשי)
# ===========================
else:
    with st.sidebar:
        st.title("🗂️ ניהול")
        therapist = st.selectbox("מטפל:", list(st.session_state.clinic_db.keys()))
        t_data = st.session_state.clinic_db[therapist]
        
        if "profile" in t_data and t_data["profile"].get("image_path"):
            st.markdown(bp.circular_avatar(t_data["profile"]["image_path"]), unsafe_allow_html=True)
            
        patients = t_data.get("patients", {})
        with st.expander("➕ מטופל חדש"):
            nn = st.text_input("שם:"); ng = st.radio("מין:", ["Male", "Female"], horizontal=True)
            if st.button("צור") and nn:
                patients[nn] = {"gender": ng, "text": "", "fields": {}}
                bp.save_db(st.session_state.clinic_db); st.rerun()
        
        if patients: curr_p = st.selectbox("תיק פעיל:", list(patients.keys()))
        else: st.warning("צור מטופל"); st.stop()
        
        st.markdown("---")
        st.markdown('<div class="admin-btn">', unsafe_allow_html=True)
        if st.button("⚙️ חדר בקרה"): st.session_state.page = "admin"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- תוכן התיק ---
    p_data = patients[curr_p]
    if "fields" not in p_data: p_data["fields"] = {}
    anl = p_data["fields"]
    
    c1, c2 = st.columns([5, 1])
    with c1: st.header(f"תיק: {curr_p}")
    with c2: st.caption(datetime.date.today().strftime("%d/%m/%Y"))

    # הקלטה
    st.markdown('<div class="rec-btn">', unsafe_allow_html=True)
    audio = mic_recorder(start_prompt="🎤 התחל הקלטה", stop_prompt="⏹️ סיים ונתח", key='rec')
    st.markdown('</div>', unsafe_allow_html=True)
    
    if audio:
        st.toast("מעבד...")
        text = bp.process_audio(audio['bytes'])
        if text:
            p_data["text"] += "\n" + text
            # קריאה ללוגיקה ב-backend
            res = bp.analyze_text(text, st.session_state.coords)
            
            for k, v in res['fields'].items():
                old = anl.get(k, "")
                if v not in old: anl[k] = f"{old} {v}".strip()
            
            if res['body_parts']: p_data["parts"] = res['body_parts']
            if res['pain'] > 0: anl["pain"] = res['pain']
            
            bp.save_db(st.session_state.clinic_db)
            st.rerun()

    st.markdown("---")
    c_form, c_vis = st.columns([1.5, 1])
    
    with c_form:
        st.markdown("<div class='section-header'>History</div>", unsafe_allow_html=True)
        st.text_area("Patient Perspective", value=anl.get("pp", ""), height=70)
        st.text_area("HPC", value=anl.get("hpc", ""), height=80)
        c1, c2 = st.columns(2)
        with c1: st.text_input("General Health", value=anl.get("gh", ""))
        with c2: st.text_input("Medications", value=anl.get("med", ""))
        
        st.markdown("<div class='section-header'>Symptoms</div>", unsafe_allow_html=True)
        st.slider("Pain", 0, 10, int(anl.get("pain", 0)))
        c3, c4 = st.columns(2)
        with c3: st.text_area("Aggravating", value=anl.get("agg", ""), height=60)
        with c4: st.text_area("Easing", value=anl.get("ease", ""), height=60)
        
        if st.button("💾 שמור"):
            bp.save_db(st.session_state.clinic_db); st.success("נשמר!")

    with c_vis:
        st.markdown("#### Body Chart")
        parts = p_data.get("parts", [])
        pain = anl.get("pain", 0)
        final_img = bp.draw_map(p_data["gender"], parts, pain, st.session_state.coords)
        if final_img: st.image(final_img, use_container_width=True)
        else: st.warning("חסרה תמונה")
        
    with st.expander("📝 תמלול מלא"): st.text(p_data.get("text", ""))