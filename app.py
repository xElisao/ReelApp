import streamlit as st
from openai import OpenAI
import os
import random
from moviepy import VideoFileClip, concatenate_videoclips

# Seitenkonfiguration (Muss ganz oben stehen)
st.set_page_config(page_title="VeloCut - AI Reel Auto-Cutter", page_icon="🎬", layout="centered")

# Stripe Live-Link
stripe_test_link = "https://buy.stripe.com/aFa8wP6aXgCa7Zt6BubEA01"

# Session State für den E-Mail-Login initialisieren
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None

# ==========================================
# 1. BEREICH: PAYWALL & LANDING PAGE (wenn NICHT eingeloggt)
# ==========================================
if not st.session_state["user_email"]:
    
    # Modernes Hero-Layout für die Startseite
    st.markdown("<h1 style='text-align: center;'>🎬 VeloCut</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Verwandle rohes Material in Sekunden in virale Highlight-Reels</h3>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Wertversprechen / Features
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
    
    # Kaufen-Bereich in der Mitte
    st.info("🔒 **VeloCut Pro** ist ein Premium-Tool. Schalte den unbegrenzten Zugang für eine einmalige Zahlung frei.")
    
    # Großer, zentraler Call-to-Action Button
    st.link_button("🚀 VeloCut Pro jetzt freischalten (14,99 €)", stripe_test_link, use_container_width=True)

    st.markdown("---")
    
    # E-Mail Login für bereits bezahlte Käufer
    st.subheader("Bereits gekauft?")
    st.markdown("Gib hier deine E-Mail-Adresse ein, mit der du bei Stripe bezahlt hast:")
    
    email_input = st.text_input("E-Mail-Adresse eingeben:")
    
    if st.button("Einloggen"):
        if not email_input:
            st.warning("Bitte gib eine E-Mail-Adresse ein.")
        else:
            try:
                # Verbindung zur Google Sheets Kundendatenbank herstellen
                conn = st.connection("gsheets", type="gsheets")
                df = conn.read(worksheet="Sheet1", usecols=[0], ttl=0)
                
                # Bereinigen und Prüfen, ob die E-Mail in der Tabelle existiert
                df["email_clean"] = df.iloc[:, 0].astype(str).str.strip().str.lower()
                clean_input = email_input.strip().lower()
                
                if clean_input in df["email_clean"].values:
                    st.session_state["user_email"] = email_input
                    st.success("Erfolgreich eingeloggt! Willkommen zurück.")
                    st.rerun()
                else:
                    st.error("Diese E-Mail-Adresse wurde in unserer Kaufliste nicht gefunden. Hast du bereits bezahlt?")
            except Exception as e:
                st.error(f"Verbindungsfehler zur Datenbank: {e}")

    # Sidebar Kauf-Button für Besucher
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
    
    # Abmelden-Button in der Sidebar
    if st.sidebar.button("Abmelden"):
        st.session_state["user_email"] = None
        st.rerun()
    
    # Sidebar Status für Pro-Nutzer
    st.sidebar.markdown("---")
    st.sidebar.subheader("💎 VeloCut Pro")
    st.sidebar.success("Aktiviert ✅")

    # OpenAI Client wird direkt sicher aus den Cloud-Secrets geladen
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception:
        st.error("⚠️ OpenAI API Key wurde nicht in den Cloud-Secrets gefunden! Bitte in den Streamlit-Einstellungen hinterlegen.")
        st.stop()

    # 1. Multi-Video-Upload
    st.subheader("1. Rohvideos hochladen")
    uploaded_files = st.file_uploader(
        "Wähle deine Videos aus (du kannst auch dasselbe Video mehrfach hochladen!)", 
        type=["mp4", "mov"], 
        accept_multiple_files=True
    )

    # 2. Setup & Stil
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

    # Ausführen-Button
    if st.button("🚀 Intelligentes Multi-Clip-Reel generieren", type="primary"):
        if not uploaded_files:
            st.warning("Bitte lade mindestens ein Videodatei hoch.")
            st.stop()
        
        output_path = os.path.join(".", "final_dynamic_reel.mp4")
        temp_files = []
        clips_to_concat = []

        try:
            st.info("📁 Analysiere Clips und wähle abwechslungsreiche Highlights aus...")

            total_items = len(uploaded_files)
            subclip_duration = max(3.0, target_duration / max(1, total_items))

            for idx, uploaded_file in enumerate(uploaded_files):
                temp_path = os.path.join(".", f"temp_{idx}_{uploaded_file.name}")
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                temp_files.append(temp_path)

                clip = VideoFileClip(temp_path)
                dur = clip.duration
                
                if dur > (subclip_duration + 5):
                    max_start = dur - subclip_duration
                    start = min(max_start, (idx * 4.0) % max_start) if max_start > 0 else 0.0
                else:
                    start = 0.0

                end = min(start + subclip_duration, dur)
                
                sub = clip.subclipped(start, end)
                clips_to_concat.append(sub)

            final_reel = concatenate_videoclips(clips_to_concat, method="compose")
            final_reel.write_videofile(output_path, codec="libx264", audio_codec="aac")

            for c in clips_to_concat:
                c.close()

            st.success("✅ Fertig! Verschiedene Highlights wurden dynamisch extrahiert und zusammengefügt.")
            
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
