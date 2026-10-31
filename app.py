import streamlit as st
from openai import OpenAI
import os
import stripe
import cv2

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
    st.caption("Lade Clips hoch – die App bereitet sie blitzschnell für deine Social-Media-Kanäle auf.")
    
    st.success(f"🎉 Eingeloggt als: {st.session_state['user_email']} | Pro-Zugang aktiv!")
    
    if st.sidebar.button("Abmelden"):
        st.session_state["user_email"] = None
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("💎 VeloCut Pro")
    st.sidebar.success("Aktiviert ✅")

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

    # Hier ist die Prompt-Eingabe wieder zurück!
    user_instruction = st.text_area(
        "Schnitt-Anweisungen (optional)",
        placeholder="z. B. Dynamischer Mix aus schnellen Passagen...",
        height=70
    )

    if st.button("🚀 Intelligentes Multi-Clip-Reel generieren", type="primary"):
        if not uploaded_files:
            st.warning("Bitte lade mindestens eine Videodatei hoch.")
            st.stop()
        
        output_path = os.path.join(".", "final_dynamic_reel.mp4")
        temp_files = []

        try:
            with st.status("📁 Verarbeite hochgeladene Clips...", expanded=True) as status:
                uploaded_file = uploaded_files[0]
                raw_path = os.path.join(".", f"raw_{uploaded_file.name}")
                
                with open(raw_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                temp_files.append(raw_path)

                cap = cv2.VideoCapture(raw_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0 or fps > 120:
                    fps = 30.0
                
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                max_frames = int(target_duration * fps)
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

                frame_count = 0
                while cap.isOpened() and frame_count < max_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    out.write(frame)
                    frame_count += 1
                
                cap.release()
                out.release()
                status.update(label="✅ Fertig! Das Reel wurde erfolgreich generiert.", state="complete", expanded=False)
            
            st.success("🎉 Dein Reel ist bereit!")
            st.video(output_path)
            
            with open(output_path, "rb") as file:
                st.download_button(
                    label="📥 Dynamisches Reel herunterladen (.mp4)",
                    data=file,
                    file_name="dynamic_creator_reel.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            st.error(f"Ein Fehler ist aufgetreten: {e}")

        for tf in temp_files:
            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except:
                    pass
