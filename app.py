import streamlit as st
from openai import OpenAI
import os
import stripe
import json
import uuid

# Datenbank-Funktionen importieren
from database import init_db, check_user_is_pro

# DB beim Start initialisieren
init_db()

# WICHTIG: Pillow-Patch für MoviePy-Kompatibilität (behebt den ANTIALIAS-Fehler)
from PIL import Image
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip, ColorClip

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
        st.write("Automatischer KI-Schnitt in Sekunden.")
    with col2:
        st.markdown("🎯 **Intelligent**")
        st.write("Erkennt die besten Passagen & Timestamps.")
    with col3:
        st.markdown("🚀 **Ready to Post**")
        st.write("Perfekt für Reels, Shorts & TikToks mit Sound.")
        
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
            
            # Blitzschneller Admin- oder Datenbank-Check (Keine langsamen Stripe-API-Loops mehr!)
            if clean_input in [e.lower() for e in admin_emails] or check_user_is_pro(clean_input):
                st.session_state["user_email"] = email_input
                st.success("Erfolgreich eingeloggt! Pro-Zugang verifiziert.")
                st.rerun()
            else:
                st.error("Kein aktiver Kauf für diese E-Mail-Adresse gefunden. (Falls du gerade erst bezahlt hast, warte 1-2 Minuten, bis der Webhook verarbeitet wurde).")

    st.sidebar.markdown("---")
    st.sidebar.subheader("💎 VeloCut Pro")
    st.sidebar.write("Schalte unbegrenzte KI-Reels frei!")
    st.sidebar.link_button("🚀 Pro-Zugang kaufen (14,99 €)", stripe_test_link)

# ==========================================
# 2. BEREICH: DAS ECHTE PROGRAMM (NUR wenn eingeloggt!)
# ==========================================
else:
    st.title("🎬 VeloCut - AI Reel Auto-Cutter")
    st.caption("Lade Clips hoch – die KI analysiert und schneidet das perfekte Highlight-Reel inkl. Audio.")
    
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
        placeholder="z. B. Konzentriere dich auf die schnellen Passagen und Vollgas-Momente...",
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
            with st.status("📁 Analysiere Videos mit KI und extrahiere Highlights...", expanded=True) as status:
                
                video_metadata = []
                for idx, uploaded_file in enumerate(uploaded_files):
                    # UUID-Absicherung, damit sich gleichnamige Dateien nicht überschreiben
                    unique_id = uuid.uuid4().hex
                    video_path = os.path.join(".", f"raw_{idx}_{unique_id}_{uploaded_file.name}")
                    
                    with open(video_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    temp_files.append(video_path)
                    
                    temp_clip = VideoFileClip(video_path)
                    duration = temp_clip.duration
                    temp_clip.close()
                    
                    video_metadata.append({
                        "index": idx,
                        "name": uploaded_file.name,
                        "duration": duration,
                        "path": video_path
                    })

                highlight_plan = []
                if client:
                    try:
                        st.write("🤖 KI-Regie analysiert Videolängen und Nische...")
                        prompt_content = f"""
                        Du bist ein professioneller Video-Editor. Gegeben sind {len(video_metadata)} Videos mit folgenden Gesamtlängen in Sekunden:
                        {[f"Video {v['index']}: {v['name']} ({v['duration']:.1f}s)" for v in video_metadata]}
                        
                        Ziel-Gesamtlänge des finalen Reels: {target_duration} Sekunden.
                        Content-Nische: {content_niche}
                        Zusätzlicher Regie-Wunsch: {user_instruction if user_instruction else 'Keiner'}
                        
                        Erstelle einen Schnittplan als reines JSON-Array. Wähle für jedes Video sinnvolle Start- und End-Zeitstempel (in Sekunden), sodass die Summe aller Clips exakt ca. {target_duration} Sekunden ergibt.
                        Format (striktes JSON, kein Markdown drumherum):
                        [
                          {{"video_index": 0, "start": 2.0, "end": 7.0}},
                          {{"video_index": 1, "start": 5.5, "end": 12.0}}
                        ]
                        """
                        ai_response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "Du gibst ausschließlich valides JSON zurück."},
                                {"role": "user", "content": prompt_content}
                            ]
                        )
                        raw_json = ai_response.choices[0].message.content.strip()
                        if raw_json.startswith("```json"):
                            raw_json = raw_json[7:-3].strip()
                        highlight_plan = json.loads(raw_json)
                    except Exception as e:
                        st.warning(f"KI-Analyse-Fallback aktiv (Fehler: {e})")
                        highlight_plan = []

                if not highlight_plan:
                    duration_per_video = target_duration / len(video_metadata)
                    for v in video_metadata:
                        start = max(0.0, (v["duration"] - duration_per_video) / 2)
                        end = min(v["duration"], start + duration_per_video)
                        highlight_plan.append({
                            "video_index": v["index"],
                            "start": start,
                            "end": end
                        })

                target_w, target_h = 720, 1280
                
                for item in highlight_plan:
                    v_idx = item["video_index"]
                    start_t = max(0.0, item["start"])
                    end_t = min(video_metadata[v_idx]["duration"], item["end"])
                    
                    if start_t >= end_t:
                        end_t = min(video_metadata[v_idx]["duration"], start_t + 3.0)

                    clip_path = video_metadata[v_idx]["path"]
                    subclip = VideoFileClip(clip_path).subclip(start_t, end_t)
                    
                    w, h = subclip.size
                    scale = min(target_w / w, target_h / h)
                    subclip_resized = subclip.resize(scale)
                    
                    bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).set_duration(subclip.duration)
                    final_sub = CompositeVideoClip([bg, subclip_resized.set_position("center")])
                    
                    clips_to_concat.append(final_sub)
                    st.write(f"✨ Highlight aus Video {v_idx+1} ({start_t:.1f}s bis {end_t:.1f}s) extrahiert.")

                final_reel = concatenate_videoclips(clips_to_concat, method="compose")
                final_reel.write_videofile(
                    output_path, 
                    fps=30, 
                    codec="libx264", 
                    audio_codec="aac", 
                    preset="medium",
                    threads=4
                )
                
                final_reel.close()
                for c in clips_to_concat:
                    c.close()

                status.update(label="✅ Fertig! Das Highlight-Reel mit Sound wurde erfolgreich erstellt.", state="complete", expanded=False)
            
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

        finally:
            for tf in temp_files:
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except:
                        pass
