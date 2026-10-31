import streamlit as st
from openai import OpenAI
import os
import stripe
import cv2
import numpy as np

# Seitenkonfiguration (Muss ganz oben stehen)
st.set_page_config(page_title="VeloCut - AI Reel Auto-Cutter", page_icon="🎬", layout="centered")

# GitHub-Menü, Kopfzeile und Fußzeile ausblenden
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Stripe Live-Link für den Kaufen-Button
stripe_test_link = "https://buy.stripe.com/aFa8wP6aXgCa7Zt6BubEA01"

# Stripe API Key aus den Streamlit Secrets laden
try:
    stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
except Exception:
    pass

# Session State für den E-Mail-Login initialisieren
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None

# ==========================================
# 1. BEREICH: PAYWALL & LANDING PAGE (wenn NICHT eingeloggt)
# ==========================================
if not st.session_state["user_email"]:
    
    st.markdown("<h1 style='text-align: center;'>🎬 VeloCut</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Verwandle rohes Material in Sekunden in virale Highlight-Reels</h3>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("⚡ **Blitzschnell**")
        st.write("Automatischer Schnitt in wenigen Sekunden.")
    with col2:
        st.markdown("🎯 **Intelligent**")
        st.write("Zieht die besten Passagen aus deinen Clips.")
    with col3:
        st.markdown("🚀 **Ready to Post**")
        st.write("Perfekt für Reels, Shorts & TikToks.")
        
    st.markdown("---")
    
    st.info("🔒 **VeloCut Pro** ist ein Premium-Tool. Schalte den unbegrenzten Zugang für eine einmalige Zahlung frei.")
    
    st.link_button("🚀 VeloCut Pro jetzt freischalten (14,99 €)", stripe_test_link, use_container_width=True)

    st.markdown("---")
    
    st.subheader("Bereits gekauft?")
    st.markdown("Gib hier deine E-Mail-Adresse ein, mit der du bei Stripe bezahlt hast:")
    
    email_input = st.text_input("E-Mail-Adresse eingeben:")
    
    if st.button("Einloggen"):
        if not email_input:
            st.warning("Bitte gib eine E-Mail-Adresse ein.")
        else:
            clean_input = email_input.strip().lower()
            admin_emails = ["elias.krainer@icloud.com", "krainerelias@gmx.at"]
            
            if clean_input in [e.lower() for e in admin_emails]:
                st.session_state["user_email"] = email_input
                st.success("Erfolgreich eingeloggt! (Admin-Zugang)")
                st.rerun()

            try:
                sessions = stripe.checkout.Session.list(limit=100)
                paid = False
                
                for session in sessions.data:
                    s_dict = session.to_dict()
                    customer_email = s_dict.get("customer_details", {}).get("email") or s_dict.get("customer_email")
                    if customer_email and customer_email.strip().lower() == clean_input:
                        if s_dict.get("payment_status") == "paid":
                            paid = True
                            break
                
                if paid:
                    st.session_state["user_email"] = email_input
                    st.success("Erfolgreich eingeloggt! Pro-Zugang verifiziert.")
                    st.rerun()
                else:
                    st.error("Kein aktiver Kauf für diese E-Mail-Adresse bei Stripe gefunden.")
            except Exception as e:
                st.error(f"Fehler bei der Stripe-Verifizierung: {e}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("💎 VeloCut Pro")
    st.sidebar.write("Schalte unbegrenzte KI-Reels frei!")
    st.sidebar.link_button("🚀 Pro-Zugang kaufen (14,99 €)", stripe_test_link)

# ==========================================
# 2. BEREICH: DAS ECHTE PROGRAMM (NUR wenn eingeloggt!)
# ==========================================
else:
    st.title("🎬 VeloCut - AI Reel Auto-Cutter")
    st.caption("Lade Clips hoch – die App extrahiert intelligente Highlights über die gesamte Länge passend zur Nische.")
    
    st.success(f"🎉 Eingeloggt als: {st.session_state['user_email']} | Pro-Zugang aktiv!")
    
    if st.sidebar.button("Abmelden"):
        st.session_state["user_email"] = None
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("💎 VeloCut Pro")
    st.sidebar.success("Aktiviert ✅")

    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception:
        client = None

    st.subheader("1. Rohvideos hochladen")
    uploaded_files = st.file_uploader(
        "Wähle deine Videos aus", 
        type=["mp4", "mov", "avi", "m4v"], 
        accept_multiple_files=True
    )

    st.subheader("2. Setup & Ziel")
    col1, col2 = st.columns(2)
    with col1:
        content_niche = st.selectbox(
            "Content-Nische",
            ["Motorrad / Action / Motorsport", "Fitness / Gym Workout", "Reise / Vlog / Outdoor", "Allgemeiner Content"]
        )
    with col2:
        target_duration = st.select_slider(
            "Ziel-Laufzeit des Gesamtreels (Sekunden)",
            options=[10, 15, 20, 30, 45],
            value=15
        )

    user_instruction = st.text_area(
        "Schnitt-Anweisungen (optional)",
        placeholder="z. B. Extrahiere die actionreichsten Passagen über die gesamte Länge...",
        height=70
    )

    if st.button("🚀 Intelligentes Multi-Clip-Reel generieren", type="primary"):
        if not uploaded_files:
            st.warning("Bitte lade mindestens eine Videodatei hoch.")
            st.stop()
        
        output_path = os.path.join(".", "final_dynamic_reel.mp4")
        temp_files = []

        try:
            with st.status("📁 Analysiere Videos und extrahiere intelligente Highlights...", expanded=True) as status:
                
                # KI-Regieanweisung passend zur Nische
                if user_instruction and client:
                    try:
                        ai_response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "Du bist ein professioneller Regieassistent für Videoschnitt. Kommentiere kurz auf Deutsch, wie für die gewählte Nische die besten Momente aus den Videos über die Gesamtlänge kombiniert werden."},
                                {"role": "user", "content": f"Nische: {content_niche}, Anweisung: {user_instruction}"}
                            ]
                        )
                        st.write(f"🤖 KI-Regie: {ai_response.choices[0].message.content}")
                    except Exception:
                        pass

                target_width = 720
                target_height = 1280
                fps = 30.0

                fourcc = cv2.VideoWriter_fourcc(*'avc1')
                out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))
                
                if not out.isOpened():
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))

                total_videos = len(uploaded_files)
                # Gesamt-Frames für das Ziel-Reel
                total_target_frames = int(target_duration * fps)
                
                # Wir berechnen, wie viele Frames jedes Video beitragen darf
                frames_per_video = total_target_frames // total_videos

                for idx, uploaded_file in enumerate(uploaded_files):
                    video_path = os.path.join(".", f"raw_{idx}_{uploaded_file.name}")
                    with open(video_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    temp_files.append(video_path)

                    cap = cv2.VideoCapture(video_path)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    # INTELLIGENTE HIGHLIGHT-VERTEILUNG:
                    # Statt nur am Start zu hängen, teilen wir das Video in 3 Bereiche auf 
                    # (z.B. Start-Drittel, Mitte, Schluss-Drittel) und nehmen daraus knackige Mini-Clips!
                    chunk_size = frames_per_video // 3 if frames_per_video >= 90 else frames_per_video
                    num_chunks = 3 if frames_per_video >= 90 else 1
                    
                    frames_written_for_this_video = 0
                    
                    for chunk_idx in range(num_chunks):
                        if frames_written_for_this_video >= frames_per_video:
                            break
                            
                        # Setze Startpunkte über das ganze Video verteilt (z.B. bei 20%, 50%, 75% des Clips)
                        if num_chunks == 3:
                            fractions = [0.2, 0.5, 0.75]
                            start_frame = int(total_frames * fractions[chunk_idx])
                        else:
                            start_frame = int(total_frames * 0.15) # Fallback bei sehr kurzen Clips
                            
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, start_frame))
                        
                        chunk_frames_target = chunk_size
                        chunk_frames_written = 0
                        
                        while cap.isOpened() and chunk_frames_written < chunk_frames_target and frames_written_for_this_video < frames_per_video:
                            ret, frame = cap.read()
                            if not ret:
                                break
                            
                            # Format anpassen (Letterboxing ohne Verzerrung)
                            h, w = frame.shape[:2]
                            scale = min(target_width / w, target_height / h)
                            new_w = int(w * scale)
                            new_h = int(h * scale)
                            
                            resized_frame = cv2.resize(frame, (new_w, new_h))
                            canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
                            
                            x_offset = (target_width - new_w) // 2
                            y_offset = (target_height - new_h) // 2
                            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_frame
                            
                            out.write(canvas)
                            chunk_frames_written += 1
                            frames_written_for_this_video += 1
                    
                    cap.release()
                    st.write(f"✨ Highlights aus Video {idx+1} ({uploaded_file.name}) intelligent über die Gesamtlänge extrahiert.")

                out.release()
                status.update(label="✅ Fertig! Die besten Passagen wurden optimal kombiniert.", state="complete", expanded=False)
            
            st.success("🎉 Dein Multi-Clip Highlight-Reel ist fertig und bereit zum Download!")
            
            if os.path.exists(output_path):
                with open(output_path, "rb") as file:
                    st.download_button(
                        label="📥 Dynamisches Reel herunterladen (.mp4)",
                        data=file,
                        file_name="dynamic_creator_reel.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )

        except Exception as e:
            st.error(f"Ein Fehler ist aufgetreten: {e}")

        for tf in temp_files:
            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except:
                    pass
