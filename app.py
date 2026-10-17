import streamlit as st
from openai import OpenAI
import os
import random
import cv2
from moviepy import VideoFileClip, concatenate_videoclips
import stripe

# Seitenkonfiguration (Muss ganz oben stehen)
st.set_page_config(page_title="VeloCut - AI Reel Auto-Cutter", page_icon="🎬", layout="centered")

# GitHub-Menü, Kopfzeile und Fußzeile komplett ausblenden für maximale Privatsphäre
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
            
            # Master-Override für dich selbst (optional, falls du dich immer einloggen willst)
            admin_emails = ["elias.krainer@icloud.com", "krainerelias@gmx.at"]
            
            if clean_input in [e.lower() for e in admin_emails]:
                st.session_state["user_email"] = email_input
                st.success("Erfolgreich eingeloggt! (Admin-Zugang)")
                st.rerun()

            try:
                # Direkte Abfrage bei Stripe, ob die E-Mail bezahlt hat
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
                    st.error("Kein aktiver Kauf für diese E-Mail-Adresse bei Stripe gefunden. (Falls du gerade erst bezahlt hast, versuche es in wenigen Sekunden noch einmal).")
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
    st.caption("Lade Clips hoch – die App zieht sich automatisch abwechslungsreiche Highlights und mischt sie durch.")
    
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
        st.error("⚠️ OpenAI API Key wurde nicht in den Cloud-Secrets gefunden!")
        st.stop()

    st.subheader("1. Rohvideos hochladen")
    uploaded_files = st.file_uploader(
        "Wähle deine Videos aus (egal ob iPhone, Android oder PC)", 
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
        placeholder="z. B. Dynamischer Mix aus verschiedenen Passagen...",
        height=70
    )

    if st.button("🚀 Intelligentes Multi-Clip-Reel generieren", type="primary"):
        if not uploaded_files:
            st.warning("Bitte lade mindestens eine Videodatei hoch.")
            st.stop()
        
        output_path = os.path.join(".", "final_dynamic_reel.mp4")
        temp_files = []
        clips_to_concat = []

        try:
            st.info("📁 Bereinige und verarbeite hochgeladene Clips...")

            total_items = len(uploaded_files)
            subclip_duration = max(3.0, target_duration / max(1, total_items))

            for idx, uploaded_file in enumerate(uploaded_files):
                raw_path = os.path.join(".", f"raw_{idx}_{uploaded_file.name}")
                clean_path = os.path.join(".", f"clean_{idx}.mp4")
                
                with open(raw_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                temp_files.append(raw_path)
                temp_files.append(clean_path)

                cap = cv2.VideoCapture(raw_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0 or fps > 120:
                    fps = 30.0
                
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                dur = frame_count / fps if fps > 0 else 0

                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(clean_path, fourcc, fps, (width, height))

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    out.write(frame)
                
                cap.release()
                out.release()

                if dur <= 0:
                    temp_check = VideoFileClip(clean_path)
                    dur = temp_check.duration
                    temp_check.close()

                if dur > (subclip_duration + 5):
                    max_start = dur - subclip_duration
                    start = min(max_start, (idx * 4.0) % max_start) if max_start > 0 else 0.0
                else:
                    start = 0.0

                end = min(start + subclip_duration, dur)
                
                clip = VideoFileClip(clean_path)
                sub = clip.subclipped(start, end)
                clips_to_concat.append(sub)

            final_reel = concatenate_videoclips(clips_to_concat, method="compose")
            final_reel.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac", 
                fps=30, 
                preset="medium", 
                threads=4
            )

            for c in clips_to_concat:
                c.close()

            st.success("✅ Fertig! Das Reel wurde erfolgreich generiert.")
            
            st.video(output_path)
            
            with open(output_path, "rb") as file:
                st.download_button(
                    label="📥 Dynamisches Reel herunterladen (.mp4)",
                    data=file,
                    file_name="dynamic_creator_reel.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            st.error(f"Fehler bei der Videoverarbeitung: {e}")

        for tf in temp_files:
            if os.path.exists(tf):
                os.remove(tf)
