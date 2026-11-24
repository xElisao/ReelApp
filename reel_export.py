"""Erster lokaler MP4-Reel-Export aus bereits geprüften Vorschauclips.

Die Clips bleiben temporär und in der aktuellen Streamlit-Sitzung.
Hochkantformat (540x960), standardmäßig mit weichgezeichnetem Bildhintergrund.
Das vollständige Quellbild bleibt in der Mitte sichtbar; optionale schwarze Balken.
Diese Laborversion exportiert standardmäßig OHNE Ton; vorhandener Originalton
kann beim Export ausdrücklich aktiviert werden. Keine Sprachanalyse/Musikmischung.
Es wird weder das Originalvideo noch die OpenAI-API erneut benötigt.
"""

from __future__ import annotations

import math
import io
import re
import shutil
import subprocess
import tempfile
import textwrap
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, UnidentifiedImageError


MAX_SEGMENTS = 3
MAX_SEGMENT_SECONDS = 10.0
MAX_REEL_SECONDS = 30.0
MAX_SEGMENT_BYTES = 10 * 1024 * 1024
MAX_REEL_BYTES = 40 * 1024 * 1024
BACKGROUND_MODES = frozenset({"blur", "black"})
AUDIO_MODES = frozenset({"mute", "original"})
TRANSITION_MODES = frozenset({"cut", "fade"})
DESIGN_TEMPLATES = frozenset({"classic", "modern"})
FADE_SECONDS = 0.5  # Alter Standard, auch für bestehende Aufrufer.
FADE_DURATIONS = frozenset({0.25, 0.5, 1.0})
MAX_OVERLAY_CHARACTERS = 56
OVERLAY_FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
OVERLAY_DURATION_SECONDS = 2.0
MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_IMAGE_DIMENSION = 2048
LOGO_RENDER_WIDTH = 144
LOGO_RENDER_HEIGHT = 88
LOGO_MARGIN_RIGHT = 32
LOGO_MARGIN_TOP = 48


class ReelExportError(RuntimeError):
    """Ungültige Reel-Auswahl oder lokaler FFmpeg-Fehler."""


def normalize_overlay_text(value: str) -> str:
    """Prüft optionalen Bildschirmtext vor jeglichem FFmpeg-Aufruf.

    Benutzereingaben gelangen nur in eine temporäre UTF-8-Textdatei,
    niemals in Kommandoargumente oder den FFmpeg-Filterausdruck.
    """
    if not isinstance(value, str):
        raise ReelExportError("Texteinblendungen müssen normale Texte sein.")
    text = unicodedata.normalize("NFC", value.strip())
    if len(text) > MAX_OVERLAY_CHARACTERS:
        raise ReelExportError(
            f"Eine Texteinblendung darf höchstens {MAX_OVERLAY_CHARACTERS} "
            "Zeichen enthalten."
        )
    if any(unicodedata.category(char).startswith("C") for char in text):
        raise ReelExportError(
            "Texteinblendungen dürfen keine Steuer- oder Zeilenumbruchzeichen enthalten."
        )
    return text


def normalize_brand_color(value: str | None) -> str | None:
    """Prüft eine Firmenfarbe streng, bevor FFmpeg aufgerufen wird."""
    if value is None:
        return None
    if not isinstance(value, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is None:
        raise ReelExportError(
            "Bitte eine Markenfarbe als sechsstelligen HEX-Wert (#RRGGBB) wählen."
        )
    return value.upper()


def _brand_text_style(brand_color: str | None) -> tuple[str, str]:
    """Volltonfarbe mit gut lesbarer schwarzer oder weißer Schrift.

    Bei deckender Farbfläche und Wahl des größeren Kontrastes
    erreichen Schwarz/Weiß >= 4,5:1 nach WCAG-Berechnung
    (vor der H.264-Komprimierung).
    """
    if brand_color is None:
        return "black@0.65", "white"
    rgb = tuple(int(brand_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def linear(channel: float) -> float:
        return (
            channel / 12.92 if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )

    luminance = sum(
        linear(channel) * weight
        for channel, weight in zip(rgb, (0.2126, 0.7152, 0.0722))
    )
    black_contrast = (luminance + 0.05) / 0.05
    white_contrast = 1.05 / (luminance + 0.05)
    font_color = "black" if black_contrast >= white_contrast else "white"
    return f"0x{brand_color[1:]}", font_color


def _append_reel_text_overlays(
    graph: list[str],
    target: Path,
    total_seconds: float,
    title_text: str,
    cta_text: str,
    brand_color: str | None = None,
    design_template: str = "classic",
) -> str:
    """Blendet optionale Texte in sicheren Bereichen ein, ohne KI-Aufruf.

    Separate Textdateien + expansion=none verhindern, dass Eingaben
    als Filter-Syntax bzw. drawtext-Expressions interpretiert werden.
    Die Schrift wird auf dem Testserver über das Debian-Paket
    fonts-dejavu-core bereitgestellt (nicht mit dem MP4 ausgeliefert).
    """
    if not (title_text or cta_text):
        return "video"
    if not OVERLAY_FONT_PATH.is_file():
        raise ReelExportError(
            "Die Schriftart für Texteinblendungen fehlt auf dem Testserver."
        )
    output_label = "video"
    box_color, font_color = _brand_text_style(brand_color)
    visible_seconds = min(OVERLAY_DURATION_SECONDS, total_seconds / 2.0)
    # Klassisch bleibt pixelgenau wie bisher: mittig, bei y=150.
    # Modern ist bewusst linksbündig und tiefer positioniert,
    # mit kleinerer Schrift und kürzeren Zeilen, damit der Text
    # auch bei breiten Zeichen innerhalb der Hochkantfläche bleibt.
    if design_template == "classic":
        wrap_width, font_size, border_width, line_spacing = 16, 30, 16, 6
        x_position = "(w-text_w)/2"
        title_y, cta_y = "150", "h-185-text_h"
    else:
        wrap_width, font_size, border_width, line_spacing = 14, 28, 12, 7
        x_position = "44"
        title_y, cta_y = "210", "h-235-text_h"
    for kind, text in (("title", title_text), ("cta", cta_text)):
        if not text:
            continue
        text_path = target / f"overlay_{kind}.txt"
        lines = textwrap.wrap(
            text, width=wrap_width, break_long_words=True, break_on_hyphens=False,
        )
        text_path.write_text("\n".join(lines), encoding="utf-8")
        # Diese Pfade stammen nur aus unserem temporären Serververzeichnis.
        # Der Nutzer kann weder Pfad noch Filtergraph bestimmen.
        if kind == "title":
            enable = f"lt(t,{visible_seconds:.6f})"
            y = title_y
        else:
            enable = f"gte(t,{total_seconds - visible_seconds:.6f})"
            y = cta_y
        next_label = f"reel_{kind}"
        graph.append(
            f"[{output_label}]drawtext="
            f"fontfile='{OVERLAY_FONT_PATH.as_posix()}':"
            f"textfile='{text_path.as_posix()}':"
            f"expansion=none:fontsize={font_size}:fontcolor={font_color}:"
            f"box=1:boxcolor={box_color}:boxborderw={border_width}:"
            f"line_spacing={line_spacing}:"
            f"x={x_position}:"
            f"y={y}:enable='{enable}'"
            f"[{next_label}]"
        )
        output_label = next_label
    return output_label


def normalize_logo_png(logo_png_bytes: bytes | None) -> bytes | None:
    """Validiert einen Logo-Upload und entfernt Metadaten, bevor FFmpeg ihn sieht.

    Nur statische PNGs, mit Grenzen für Dateigröße und Bildpixel. Die
    transparente Fläche wird auf sichtbare Pixel zugeschnitten; das Logo
    wird proportional auf maximal 144×88 Pixel skaliert. Als völlig
    neu kodiertes RGBA-PNG verlassen weder eingebettete Metadaten noch
    fremde Dateinamen den lokalen temporären Verarbeitungsbereich.
    """
    if logo_png_bytes is None:
        return None
    if not isinstance(logo_png_bytes, bytes):
        raise ReelExportError("Das Logo muss als PNG-Datei hochgeladen werden.")
    if not 8 <= len(logo_png_bytes) <= MAX_LOGO_BYTES:
        raise ReelExportError("Die Logo-PNG darf höchstens 2 MB groß sein.")
    if not logo_png_bytes.startswith(bytes((137, 80, 78, 71, 13, 10, 26, 10))):
        raise ReelExportError("Bitte eine echte PNG-Datei für das Logo verwenden.")
    try:
        with Image.open(io.BytesIO(logo_png_bytes)) as image:
            if image.format != "PNG":
                raise ReelExportError("Das Logo muss eine PNG-Datei sein.")
            width, height = image.size
            if (
                not 1 <= width <= MAX_LOGO_IMAGE_DIMENSION
                or not 1 <= height <= MAX_LOGO_IMAGE_DIMENSION
                or getattr(image, "n_frames", 1) != 1
            ):
                raise ReelExportError(
                    "Das Logo muss ein einzelnes PNG-Bild mit höchstens "
                    "2048 × 2048 Pixel sein."
                )
            image.load()
            canvas = image.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ReelExportError("Die hochgeladene Logo-Datei ist kein lesbares PNG.") from exc
    alpha_bounds = canvas.getchannel("A").getbbox()
    if alpha_bounds is None:
        raise ReelExportError("Das Logo ist vollständig transparent und daher unsichtbar.")
    canvas = canvas.crop(alpha_bounds)
    canvas.thumbnail(
        (LOGO_RENDER_WIDTH, LOGO_RENDER_HEIGHT), Image.Resampling.LANCZOS,
    )
    destination = io.BytesIO()
    canvas.save(destination, format="PNG", optimize=False)
    return destination.getvalue()


def _append_reel_logo_overlay(
    graph: list[str], output_video_label: str,
    logo_input_index: int,
) -> str:
    """Legt das geprüfte PNG in die rechte obere Ecke des fertigen Reels."""
    graph.append(
        f"[{output_video_label}][{logo_input_index}:v:0]"
        f"overlay=x=W-w-{LOGO_MARGIN_RIGHT}:y={LOGO_MARGIN_TOP}:"
        "shortest=0:format=auto,"
        "format=yuv420p,settb=AVTB,fps=24"
        "[video_logo]"
    )
    return "video_logo"


@dataclass(frozen=True)
class ReelSegment:
    source_id: str
    start_seconds: float
    end_seconds: float
    mp4_bytes: bytes

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


def validate_reel_segments(segments: Sequence[ReelSegment]) -> float:
    """Prüft Zeitlimits, echte MP4-Dateien und doppelte/überlappende Auswahl."""
    if not 2 <= len(segments) <= MAX_SEGMENTS:
        raise ReelExportError("Bitte 2 bis 3 Vorschauclips für das Test-Reel auswählen.")

    total = 0.0
    intervals: dict[str, list[tuple[float, float]]] = {}
    for segment in segments:
        if not isinstance(segment, ReelSegment):
            raise ReelExportError("Ungültige Vorschau-Auswahl.")
        if not isinstance(segment.source_id, str) or not segment.source_id.strip():
            raise ReelExportError("Dem Clip fehlt die Video-Quelle.")
        start, end = segment.start_seconds, segment.end_seconds
        if (
            not isinstance(start, (int, float)) or isinstance(start, bool)
            or not isinstance(end, (int, float)) or isinstance(end, bool)
            or not math.isfinite(start) or not math.isfinite(end)
            or start < 0 or end <= start
        ):
            raise ReelExportError("Ungültige Clip-Zeitangaben.")
        duration = end - start
        if duration > MAX_SEGMENT_SECONDS + 1e-6:
            raise ReelExportError("Ein Clip ist länger als 10 Sekunden.")
        if (
            not isinstance(segment.mp4_bytes, bytes)
            or not 8 <= len(segment.mp4_bytes) <= MAX_SEGMENT_BYTES
            or segment.mp4_bytes[4:8] != b"ftyp"
        ):
            raise ReelExportError("Ein Vorschauclip ist kein gültiger MP4-Container.")
        total += duration
        intervals.setdefault(segment.source_id, []).append((start, end))

    if total > MAX_REEL_SECONDS + 1e-6:
        raise ReelExportError("Das Test-Reel darf maximal 30 Sekunden lang sein.")
    for spans in intervals.values():
        ordered = sorted(spans)
        for earlier, later in zip(ordered, ordered[1:]):
            if later[0] < earlier[1] - 1e-6:
                raise ReelExportError(
                    "Zwei Clips überlappen im Originalvideo. "
                    "Bitte einen davon abwählen."
                )
    return total


def expected_reel_duration(
    segments: Sequence[ReelSegment], *,
    transition_mode: str = "cut",
    fade_duration_seconds: float = FADE_SECONDS,
) -> float:
    """Reellaufzeit bei 0,25/0,5/1,0 s Übergängen oder direktem Schnitt.

    Weiche Übergänge überlagern die Clips und fügen keine Zeit ein.
    Alle Clips müssen mindestens doppelt so lang wie die gewählte Blende
    sein; auch bei drei Szenen bleibt so genügend Material für BEIDE
    Übergänge der mittleren Szene.
    """
    total = validate_reel_segments(segments)
    if transition_mode not in TRANSITION_MODES:
        raise ReelExportError("Unbekannter Übergangsmodus.")
    if (
        not isinstance(fade_duration_seconds, (int, float))
        or isinstance(fade_duration_seconds, bool)
        or not math.isfinite(fade_duration_seconds)
        or fade_duration_seconds not in FADE_DURATIONS
    ):
        raise ReelExportError(
            "Ungültige Überblendungsdauer. Erlaubt sind 0,25, 0,5 oder 1 Sekunde."
        )
    if transition_mode == "fade":
        min_seconds = 2 * fade_duration_seconds
        if any(
            segment.duration_seconds < min_seconds - 1e-6
            for segment in segments
        ):
            fade_label = f"{fade_duration_seconds:.2f}".replace(".", ",")
            minimum_label = f"{min_seconds:.2f}".replace(".", ",")
            raise ReelExportError(
                "Für eine weiche Überblendung mit "
                f"{fade_label} Sekunden muss jede Szene "
                f"mindestens {minimum_label} Sekunden lang sein. "
                "Bitte die Szene verlängern oder direkten Schnitt wählen."
            )
        total -= fade_duration_seconds * (len(segments) - 1)
    return total


def _clip_has_audio(path: Path, *, timeout_seconds: int = 12) -> bool:
    """Prüfe die lokale Vorschau auf Audio, ohne Mediendaten nach außen zu senden."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise ReelExportError("FFprobe fehlt auf dem Testserver.")
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=index", "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True, timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReelExportError("Die Tonspur konnte nicht geprüft werden.") from exc
    if result.returncode != 0:
        raise ReelExportError("Die Tonspur konnte nicht geprüft werden.")
    return bool(result.stdout.strip())


def render_test_reel(
    segments: Sequence[ReelSegment],
    *,
    background_mode: str = "blur",
    audio_mode: str = "mute",
    transition_mode: str = "cut",
    fade_duration_seconds: float = FADE_SECONDS,
    title_text: str = "",
    cta_text: str = "",
    logo_png_bytes: bytes | None = None,
    brand_color: str | None = None,
    design_template: str = "classic",
    timeout_seconds: int = 100,
) -> bytes:
    """Fügt bis zu drei kurze Clips mit normalisierter Hochkant-Leinwand zusammen.

    Jedes Segment wird auf 540x960 / 24fps / SAR=1 normalisiert; unterschiedliche
    Originalauflösungen und Seitenverhältnisse sind damit zulässig.
    Audio: standardmäßig stumm. Bei "original" wird die schon in der
    Vorschau vorhandene Tonspur übernommen; stumme Clips erhalten an
    gleicher Position lokal erzeugte Stille für einen stabilen Export.
    Es erfolgen weder Sprachanalyse noch zusätzliche OpenAI-Aufrufe.
    "blur" erhält das Originalmotiv mittig und füllt freie Flächen mit
    weichgezeichnetem Bildmaterial, "black" bietet den alten Letterbox-Modus.
    "cut" verbindet direkt; "fade" überblendet mit wählbarer Dauer
    (0,25, 0,5 oder 1,0 s) per xfade und synchronem acrossfade.
    Optionale Titel und Schlusszeilen und ein PNG-Logo werden erst NACH
    den Szenenübergängen rein lokal ins MP4 gerendert; sie ändern
    die Laufzeit nicht und erfordern keine weiteren KI-Aufrufe.
    Eine optionale Markenfarbe färbt die Titel- und CTA-Textflächen
    deckend ein; schwarze/weiße Schrift hat den höheren Kontrast.
    Ohne Farbwahl bleibt die bisherige halbtransparente schwarze Box.
    Der Logo-Export bleibt unverändert.
    Designvorlagen: "classic" belässt das bisherige mittige Layout.
    "modern" platziert kürzer umbrochene Texte linksbündig, etwas
    tiefer und mit schmalerer Textfläche; die Clipdauer bleibt gleich.
    """
    total_seconds = expected_reel_duration(
        segments, transition_mode=transition_mode,
        fade_duration_seconds=fade_duration_seconds,
    )
    title_text = normalize_overlay_text(title_text)
    cta_text = normalize_overlay_text(cta_text)
    brand_color = normalize_brand_color(brand_color)
    if (
        not isinstance(design_template, str)
        or design_template not in DESIGN_TEMPLATES
    ):
        raise ReelExportError("Unbekannte Designvorlage. Bitte Klassisch oder Modern wählen.")
    # Wichtig: Bilddatei schon vor dem FFmpeg-Start validieren und
    # vollständig neu als PNG kodieren; nur die sichere Version nutzen.
    logo_png_bytes = normalize_logo_png(logo_png_bytes)
    if background_mode not in BACKGROUND_MODES:
        raise ReelExportError("Unbekannter Hintergrundmodus.")
    if audio_mode not in AUDIO_MODES:
        raise ReelExportError("Unbekannter Tonmodus.")
    if timeout_seconds <= 0:
        raise ReelExportError("Ungültiges Render-Zeitlimit.")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ReelExportError("FFmpeg fehlt auf dem Testserver.")

    with tempfile.TemporaryDirectory(prefix="velocut_reel_") as directory:
        target = Path(directory)
        cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
        graph = []
        for index, segment in enumerate(segments):
            clip_path = target / f"clip_{index:02d}.mp4"
            clip_path.write_bytes(segment.mp4_bytes)
            cmd.extend(["-i", str(clip_path)])
            if audio_mode == "original":
                segment_duration = f"{segment.duration_seconds:.6f}"
                if _clip_has_audio(clip_path):
                    # Einheitliches Format für die FFmpeg-Verkettung.
                    # apad/atrim hält Audio exakt auf der Videolänge;
                    # sehr kurze Tonspuren bleiben sonst nicht synchron.
                    graph.append(
                        f"[{index}:a:0]"
                        "aresample=48000,"
                        "aformat=sample_fmts=fltp:sample_rates=48000:"
                        "channel_layouts=stereo,"
                        "asetpts=PTS-STARTPTS,apad,"
                        f"atrim=duration={segment_duration}"
                        f"[a{index}]"
                    )
                else:
                    # Gemischte Auswahl aus Clips mit und ohne Ton:
                    # die stummen Teile dürfen nicht verschoben werden.
                    graph.append(
                        "anullsrc=r=48000:cl=stereo,"
                        f"atrim=duration={segment_duration},"
                        "aformat=sample_fmts=fltp:sample_rates=48000:"
                        "channel_layouts=stereo,"
                        f"asetpts=PTS-STARTPTS[a{index}]"
                    )
            if background_mode == "blur":
                # Eine einzige Videoquelle wird in Hintergrund und Vordergrund
                # geteilt. Das Hintergrundbild füllt 9:16 aus (Crop nur HINTER
                # dem Motiv); das scharfe Motiv selbst bleibt vollständig.
                graph.extend([
                    f"[{index}:v:0]fps=24,setsar=1,split=2[bg{index}][fg{index}]",
                    f"[bg{index}]"
                    "scale=540:960:force_original_aspect_ratio=increase,"
                    "crop=540:960,"
                    "boxblur=luma_radius=18:luma_power=2:"
                    "chroma_radius=9:chroma_power=2,"
                    "eq=brightness=-0.055:saturation=0.9"
                    f"[blur{index}]",
                    f"[fg{index}]"
                    "scale=540:960:force_original_aspect_ratio=decrease:"
                    "force_divisible_by=2,setsar=1"
                    f"[sharp{index}]",
                    f"[blur{index}][sharp{index}]"
                    "overlay=(W-w)/2:(H-h)/2:shortest=1,"
                    "setsar=1,format=yuv420p,setpts=PTS-STARTPTS,"
                    f"trim=duration={segment.duration_seconds:.6f},settb=AVTB,fps=24"
                    f"[v{index}]",
                ])
            else:
                graph.append(
                    f"[{index}:v:0]"
                    "fps=24,"
                    "scale=540:960:force_original_aspect_ratio=decrease:"
                    "force_divisible_by=2,"
                    "pad=540:960:(ow-iw)/2:(oh-ih)/2:color=black,"
                    "setsar=1,format=yuv420p,setpts=PTS-STARTPTS,"
                    f"trim=duration={segment.duration_seconds:.6f},settb=AVTB,fps=24"
                    f"[v{index}]"
                )
        if transition_mode == "fade":
            # Video- und Tonspuren überlappen jeweils fade_duration_seconds.
            # Alle Videos haben dieselbe Canvas, 24 fps und AVTB.
            # Die zweite xfade-Position bezieht sich auf die bereits
            # um vorherige Blenden verkürzte Ergebnis-Zeitleiste.
            current_video = "v0"
            prefix_duration = segments[0].duration_seconds
            for index in range(1, len(segments)):
                offset = (
                    prefix_duration - fade_duration_seconds * index
                )
                next_video = (
                    "video" if index == len(segments) - 1
                    else f"vf{index}"
                )
                graph.append(
                    f"[{current_video}][v{index}]"
                    f"xfade=transition=fade:duration={fade_duration_seconds:.6f}:"
                    f"offset={offset:.6f}[{next_video}]"
                )
                current_video = next_video
                prefix_duration += segments[index].duration_seconds

            if audio_mode == "original":
                current_audio = "a0"
                for index in range(1, len(segments)):
                    next_audio = (
                        "audio" if index == len(segments) - 1
                        else f"af{index}"
                    )
                    graph.append(
                        f"[{current_audio}][a{index}]"
                        f"acrossfade=d={fade_duration_seconds:.6f}:"
                        f"c1=tri:c2=tri[{next_audio}]"
                    )
                    current_audio = next_audio
        elif audio_mode == "original":
            graph.append(
                "".join(
                    f"[v{i}][a{i}]" for i in range(len(segments))
                ) + f"concat=n={len(segments)}:v=1:a=1[video][audio]"
            )
        else:
            graph.append(
                "".join(f"[v{i}]" for i in range(len(segments)))
                + f"concat=n={len(segments)}:v=1:a=0[video]"
            )
        output_video_label = _append_reel_text_overlays(
            graph, target, total_seconds, title_text, cta_text,
            brand_color, design_template,
        )
        if logo_png_bytes is not None:
            logo_path = target / "brand_logo.png"
            logo_path.write_bytes(logo_png_bytes)
            logo_input_index = len(segments)
            cmd.extend([
                "-loop", "1", "-framerate", "24", "-i", str(logo_path),
            ])
            output_video_label = _append_reel_logo_overlay(
                graph, output_video_label, logo_input_index,
            )
        destination = target / "velocut_test_reel.mp4"
        cmd.extend([
            "-filter_complex", ";".join(graph),
            "-map", f"[{output_video_label}]",
        ])
        if logo_png_bytes is not None:
            # Das ge-loopte PNG ist unendlich lang. shortest=1 in overlay
            # würde bei FFmpeg das LETZTE Videoframe verlieren (131 statt
            # 132 bei einem 5,5-s-Reel mit 24 fps). Durch shortest=0
            # plus feste Gesamtdauer bleibt das letzte Frame erhalten,
            # ohne einen unendlich langen Export zu erzeugen.
            cmd.extend(["-t", f"{total_seconds:.6f}"])
        if audio_mode == "original":
            cmd.extend([
                "-map", "[audio]", "-c:a", "aac", "-b:a", "128k",
                "-ar", "48000",
            ])
        else:
            cmd.append("-an")
        cmd.extend([
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-threads", "2",
            "-movflags", "+faststart", str(destination),
        ])
        try:
            result = subprocess.run(
                cmd, capture_output=True, check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReelExportError("Zeitlimit beim Zusammenfügen überschritten.") from exc
        except OSError as exc:
            raise ReelExportError("FFmpeg konnte das Reel nicht erstellen.") from exc

        if result.returncode != 0 or not destination.is_file():
            # Potenziell sensible Dateipfade/Metadaten nicht in die UI übernehmen.
            raise ReelExportError(
                "Die Vorschauclips konnten nicht zu einem MP4-Reel kombiniert werden."
            )
        size = destination.stat().st_size
        if not 8 <= size <= MAX_REEL_BYTES:
            raise ReelExportError("Das erstellte Reel überschreitet das Größenlimit.")
        output = destination.read_bytes()
        if output[4:8] != b"ftyp":
            raise ReelExportError("FFmpeg hat keinen gültigen MP4-Container ausgegeben.")
        return output
