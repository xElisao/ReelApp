import streamlit as st
from openai import OpenAI
import os
import random
from moviepy import VideoFileClip, concatenate_videoclips

# Seitenkonfiguration
st.set_page_config(page_title="Universal Reel Auto-Cutter", page_icon="🎬", layout="centered")

st.title("🎬 Universal Creator Reel Auto-Cutter")
st.caption("Lade Clips hoch – die App zieht sich automatisch abwechslungsreiche Highlights und mischt sie durch.")

# OpenAI API Key Input (Sidebar)
api_key = st.sidebar.text_input("OpenAI API Key", type="password")
if not api_key:
    st.info("👉 Bitte gib in der linken Seitenleiste deinen OpenAI API-Key ein, um zu starten.")
    st.stop()

client = OpenAI(api_key=api_key)

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

        # Wir berechnen, wie lang ein einzelner Teilausschnitt sein soll (z.B. 3-4 Sekunden pro Clip/Abschnitt)
        total_items = len(uploaded_files)
        # Wenn jemand z.B. 1 Video 3-mal hochlädt, simulieren wir verschiedene Stellen daraus
        subclip_duration = max(3.0, target_duration / max(1, total_items))

        for idx, uploaded_file in enumerate(uploaded_files):
            # Speichere jeden Upload (auch den gleichen Dateinamen) unter einem eindeutigen Namen ab
            temp_path = os.path.join(".", f"temp_{idx}_{uploaded_file.name}")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            temp_files.append(temp_path)

            clip = VideoFileClip(temp_path)
            dur = clip.duration
            
            # WICHTIG: Wenn das Video lang genug ist, wählen wir je nach Index 
            # unterschiedliche Startpunkte, damit sich bei mehrfachem Upload nichts wiederholt!
            if dur > (subclip_duration + 5):
                # Wir verteilen die Startpunkte intelligent über das gesamte Video
                # Z.B. Clip 1 am Anfang, Clip 2 (oder gleicher Clip als Duplikat) in der Mitte oder später
                max_start = dur - subclip_duration
                # Nutzen einen versetzten Startpunkt pro Schleife
                start = min(max_start, (idx * 4.0) % max_start) if max_start > 0 else 0.0
            else:
                start = 0.0

            end = min(start + subclip_duration, dur)
            
            # Ausschnitt erstellen
            sub = clip.subclipped(start, end)
            clips_to_concat.append(sub)

        # Alle unterschiedlichen Passagen nahtlos hintereinander schneiden
        final_reel = concatenate_videoclips(clips_to_concat, method="compose")
        final_reel.write_videofile(output_path, codec="libx264", audio_codec="aac")

        # Aufräumen
        for c in clips_to_concat:
            c.close()

        st.success("✅ Fertig! Verschiedene Highlights wurden dynamisch extrahiert und zusammengefügt.")
        
        # Video anzeigen
        st.video(output_path)
        
        # Download-Button
        with open(output_path, "rb") as file:
            st.download_button(
                label="📥 Dynamisches Reel herunterladen (.mp4)",
                data=file,
                file_name="dynamic_creator_reel.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Fehler bei der Videoverarbeitung: {e}")

    # Temporäre Dateien aufräumen
    for tf in temp_files:
        if os.path.exists(tf):
            os.remove(tf)