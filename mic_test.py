import speech_recognition as sr

def check_mic():
    r = sr.Recognizer()
    
    # הגדרות רגישות
    r.energy_threshold = 300  
    r.dynamic_energy_threshold = True
    
    # בחירת המיקרופון
    with sr.Microphone() as source:
        print("---------------------------------")
        print("🎙️  מכייל רעשים... (נא לשמור על שקט)")
        r.adjust_for_ambient_noise(source, duration=1)
        print("🟢  דבר עכשיו! (תגיד משפט בעברית)")
        print("---------------------------------")
        
        try:
            # הקלטה
            audio = r.listen(source, timeout=10) # יקליט עד שתשתוק
            print("⏳  מעבד...")
            
            # שליחה לגוגל
            text = r.recognize_google(audio, language="he-IL")
            print(f"\n✅  הצלחה! זיהיתי: {text}")
            
        except sr.UnknownValueError:
            print("\n❌  לא הצלחתי להבין מילים.")
        except sr.RequestError:
            print("\n❌  אין חיבור לאינטרנט.")
        except Exception as e:
            print(f"\n❌  שגיאה: {e}")

if __name__ == "__main__":
    check_mic()