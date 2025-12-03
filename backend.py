# backend.py - המוח והלוגיקה
import speech_recognition as sr
from PIL import Image, ImageDraw
import json
import os
import io
import base64
import datetime

# נסיון לייבא את המילון הרפואי
try:
    import medical_knowledge as mk
    HAS_MK = True
except ImportError:
    HAS_MK = False

# --- הגדרות ---
COORDS_FILE = "body_coords.json"
DB_FILE = "clinic_data.json"
IMAGES_DIR = "therapist_images"

if not os.path.exists(IMAGES_DIR): os.makedirs(IMAGES_DIR)

# --- ניהול נתונים ---
def load_data():
    coords = {
        "ראש - קדמי": [150, 40], "כתף ימין - קדמי": [95, 120], "כתף שמאל - קדמי": [205, 120],
        "ברך ימין - קדמי": [115, 460], "ברך שמאל - קדמי": [185, 460], "גב תחתון": [450, 240]
    }
    # אם יש מוח חיצוני, קח משם ברירות מחדל
    if HAS_MK: coords.update(mk.DEFAULT_BODY_COORDS)
    
    if os.path.exists(COORDS_FILE):
        try: coords.update(json.load(open(COORDS_FILE, "r")))
        except: pass
    
    db = {"דניאל": {"profile": {"gender": "Male"}, "patients": {}}}
    if os.path.exists(DB_FILE):
        try: db = json.load(open(DB_FILE, "r", encoding="utf-8"))
        except: pass
    return coords, db

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def save_coords(coords):
    with open(COORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(coords, f)

# --- עיבוד תמונה ואווטאר ---
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
    return None

def circular_avatar(image_path):
    b64 = get_image_base64(image_path)
    if not b64: return ""
    return f"<div style='text-align:center'><img src='data:image/png;base64,{b64}' style='width:80px;height:80px;border-radius:50%;border:2px solid #009688;'></div>"

# --- ניתוח טקסט (משתמש במוח החיצוני אם קיים) ---
def analyze_text(text, coords_db):
    res = {"parts": [], "pain": 0, "fields": {}}
    t = text.replace(",", "").replace(".", "")
    words = t.split()
    
    # 1. מיפוי גוף
    for saved_part in coords_db.keys():
        if saved_part in t: res["parts"].append(saved_part)
            
    # 2. זיהוי כאב
    for w in words:
        if w.isdigit():
            val = int(w)
            if 0 <= val <= 10: res["pain"] = val

    # 3. מילוי שדות (אם יש מוח חיצוני - משתמש בו, אחרת בסיסי)
    if HAS_MK:
        for category, keywords in mk.MEDICAL_BRAIN.items():
            found = []
            for key in keywords:
                if key in t:
                    try: # מנסה לקחת הקשר
                        idx = words.index(key)
                        snippet = " ".join(words[max(0, idx-1):min(len(words), idx+5)])
                        found.append(snippet)
                    except: found.append(key)
            if found: res["fields"][category] = " | ".join(list(set(found)))
    
    # ברירת מחדל אם לא זוהה כלום
    if not res["fields"] and t:
        res["fields"]["hpc"] = t
        
    return res

# --- ציור מפה ---
def draw_map(gender, parts, intensity, coords_db, highlight_point=None):
    path = "body_male.png" if gender == "Male" else "body_female.png"
    if not os.path.exists(path): return None
    
    try:
        img = Image.open(path).convert("RGBA")
        overlay = Image.new('RGBA', img.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)
        
        if not highlight_point: # מצב רגיל
            color = (255, 0, 0, 180)
            for part in parts:
                if part in coords_db:
                    x, y = coords_db[part][:2]
                    draw.ellipse((x-15, y-15, x+15, y+15), fill=color)
        else: # מצב כיול
            x, y = highlight_point
            draw.ellipse((x-5, y-5, x+5, y+5), fill=(0,0,255,255))
            draw.ellipse((x-10, y-10, x+10, y+10), outline="blue", width=2)
            
        return Image.alpha_composite(img, overlay)
    except: return None

# --- עיבוד אודיו ---
def process_audio(audio_bytes):
    r = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            return r.recognize_google(r.record(source), language="he-IL")
    except: return None