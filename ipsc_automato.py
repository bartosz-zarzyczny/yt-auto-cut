import argparse
import os
import re
import random
from pathlib import Path
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, CompositeAudioClip, AudioFileClip
import moviepy.audio.fx.all as afx
from moviepy.config import change_settings
from timer_detect import zglos_wykrycie_timera
from timer_trim import przytnij_wideo
from dodatkowe_teksty import utworz_klipy_tekstowe
from mapowanie_torow import przypisz_tory
from ustawienia_systemu import KATALOG_PROJEKTU, znajdz_imagemagick, wybierz_czcionke, sprawdz_srodowisko
from generuj_nazwy import generuj_tytul, przemianuj_plik

# Pillow compatibility: some Pillow versions removed Image.ANTIALIAS constant.
# MoviePy / TextClip expects Image.ANTIALIAS; provide a fallback mapping to Resampling.LANCZOS.
try:
    from PIL import Image as _PILImage
except Exception:
    _PILImage = None

if _PILImage is not None and not hasattr(_PILImage, 'ANTIALIAS'):
    if hasattr(_PILImage, 'Resampling') and hasattr(_PILImage.Resampling, 'LANCZOS'):
        _PILImage.ANTIALIAS = _PILImage.Resampling.LANCZOS
    elif hasattr(_PILImage, 'LANCZOS'):
        _PILImage.ANTIALIAS = _PILImage.LANCZOS

# Ścieżka do ImageMagick (zostaw swoją, jeśli działała)
_magick = znajdz_imagemagick(r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe")
if _magick:
    change_settings({"IMAGEMAGICK_BINARY": _magick})

# ===================================================================
# KONFIGURACJA ŚCIEŻEK
# ===================================================================
FOLDER_WEJSCIOWY = os.path.join(KATALOG_PROJEKTU, "Surowe")
FOLDER_WYJSCIOWY = os.path.join(KATALOG_PROJEKTU, "Gotowe")
FOLDER_MUZYKI = os.path.join(KATALOG_PROJEKTU, "Muzyka")
PLIK_Z_WYNIKAMI = os.path.join(KATALOG_PROJEKTU, "wyniki.txt")
PLIK_Z_TEKSTAMI = os.path.join(KATALOG_PROJEKTU, "dodatkowe_teksty.txt")
PLIK_Z_TORAMI = os.path.join(KATALOG_PROJEKTU, "tory.txt")

# ===================================================================
# FUNKCJE POMOCNICZE
# ===================================================================

def czytaj_wyniki_z_pliku(sciezka_do_pliku):
    if not os.path.exists(sciezka_do_pliku):
        print(f"Brak pliku z wynikami: {sciezka_do_pliku}")
        return {}

    with open(sciezka_do_pliku, 'r', encoding='utf-8') as f:
        tekst = f.read()

    wyniki = {}
    wzorzec = re.finditer(r"Stage\s+(\d+).*?(\d+)\s+([\d.]+%)\s+[\d.]+\s+(\d+)\s+([\d.]+)\s+([\d.]+)", tekst, re.IGNORECASE)
    
    for dopasowanie in wzorzec:
        nr_toru = dopasowanie.group(1)
        wyniki[nr_toru] = {
            "miejsce": dopasowanie.group(2),
            "procent": dopasowanie.group(3),
            "punkty": dopasowanie.group(4),
            "hf": dopasowanie.group(5),
            "czas": float(dopasowanie.group(6)) # CZAS Z PRACTISCORE
        }
    return wyniki


# ===================================================================
# GŁÓWNA LOGIKA
# ===================================================================

def uruchom_automatyzacje(yt=False, publikuj=False):
    srodowisko_ok, kodek = sprawdz_srodowisko(_magick)
    if not srodowisko_ok:
        return

    os.makedirs(FOLDER_WYJSCIOWY, exist_ok=True)
    
    dane_torow = czytaj_wyniki_z_pliku(PLIK_Z_WYNIKAMI)
    muzyka_pliki = [m for m in os.listdir(FOLDER_MUZYKI) if m.lower().endswith('.mp3')]
    
    wideo_pliki = [
        w for w in os.listdir(FOLDER_WEJSCIOWY)
        if w.lower().endswith(('.mp4', '.mov')) and "TEMP_MPY_" not in w.upper()
    ]
    wideo_pliki.sort() 
    
    for nazwa_pliku, nr_toru, rozdzielczosc in przypisz_tory(wideo_pliki, PLIK_Z_TORAMI):
        print(f"\n>>> Przetwarzanie: {nazwa_pliku} jako TOR {nr_toru}")
        
        if nr_toru not in dane_torow:
            continue
            
        dane = dane_torow[nr_toru]
        
        sciezka_wej = os.path.join(FOLDER_WEJSCIOWY, nazwa_pliku)
        sciezka_wyj = os.path.join(FOLDER_WYJSCIOWY, f"Gotowe_Stage_{nr_toru}.mp4")
        
        try:
            sygnaly = zglos_wykrycie_timera(sciezka_wej)
            video = VideoFileClip(sciezka_wej)
            video = przytnij_wideo(video, sygnaly, dane["czas"])

            nowy_czas_trwania = video.duration
            print(f"Czas wideo: {nowy_czas_trwania:.2f}s")
            
            # --- MUZYKA ---
            if muzyka_pliki:
                losowy_utwor = random.choice(muzyka_pliki)
                sciezka_muzyki = os.path.join(FOLDER_MUZYKI, losowy_utwor)
                
                audio_muzyka = AudioFileClip(sciezka_muzyki)
                audio_muzyka = afx.audio_loop(audio_muzyka, duration=nowy_czas_trwania)
                
                if hasattr(audio_muzyka, 'volx'):
                    audio_muzyka = audio_muzyka.volx(0.12)
                elif hasattr(audio_muzyka, 'multiply_volume'):
                    audio_muzyka = audio_muzyka.multiply_volume(0.12)
                else:
                    audio_muzyka = audio_muzyka.fl(lambda gf, t: 0.12 * gf(t), keep_duration=True)
                    
                audio_muzyka = audio_muzyka.fx(afx.audio_fadeout, 1.0)
                
                ziksowane_audio = CompositeAudioClip([video.audio, audio_muzyka]).set_fps(44100)
                video = video.set_audio(ziksowane_audio)
            
            # --- NAPISY ---
            tekst_wyswietlany = (f"STAGE {nr_toru} | Miejsce: {dane['miejsce']} ({dane['procent']})\n"
                                 f"Czas: {dane['czas']}s | HF: {dane['hf']} | Pkt: {dane['punkty']}")
            
            napis = TextClip(tekst_wyswietlany, fontsize=55, color='white', 
                             font=wybierz_czcionke(), stroke_color='black', stroke_width=2.5, align='center')
            
            # Napis wyrównany do dołu
            napis = napis.set_position(('center', 0.85), relative=True).set_duration(nowy_czas_trwania)
            
            # --- ZMIANA ROZDZIELCZOŚCI (H = 1920x1080, V/domyślnie = 1080x1920) ---
            video = video.resize(newsize=rozdzielczosc)
            # Tworzymy Composite z jawnie ustawionym rozmiarem wyjściowym, aby napisy i pozycjonowanie działały poprawnie
            teksty_gorne = utworz_klipy_tekstowe(PLIK_Z_TEKSTAMI, nowy_czas_trwania)
            wideo_koncowe = CompositeVideoClip([video, napis] + teksty_gorne, size=rozdzielczosc).set_fps(30)
            
            # --- RENDEROWANIE Z ZACHOWANIEM KOLORÓW I BEZ OBROTÓW ---
            print(f"Rozpoczynam renderowanie ({kodek})...")
            wideo_koncowe.write_videofile(
                sciezka_wyj, 
                fps=30, 
                codec=kodek, 
                audio_codec="aac",
                bitrate="8000k",    
                preset="fast",
                ffmpeg_params=['-pix_fmt', 'yuv420p'],  # Gwarantuje poprawne kolory i odtwarzanie w Windows
                logger=None         
            )
            
            video.close()
            wideo_koncowe.close()
            sciezka_wyj = Path(sciezka_wyj)
            tytul = generuj_tytul(sciezka_wyj)
            sciezka_wyj = przemianuj_plik(sciezka_wyj, tytul)
            print(f"Nadano nazwę: {sciezka_wyj.name}")
            print("Zakończono sukcesem!\n")
            
        except Exception as e:
            print(f"BŁĄD podczas przetwarzania: {str(e)}\n")

    if yt:
        from youtube_upload import main as uruchom_youtube

        argumenty_youtube = [FOLDER_WYJSCIOWY]
        if publikuj:
            argumenty_youtube.append("--publish")
        uruchom_youtube(argumenty_youtube)


def main():
    parser = argparse.ArgumentParser(
        description="Montuje nagrania IPSC, a opcjonalnie przygotowuje publikację YouTube.",
        prefix_chars="-/",
    )
    parser.add_argument(
        "--yt",
        "/yt",
        dest="yt",
        action="store_true",
        help="Po montażu uruchamia podgląd kolejki YouTube (bez wysyłania).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Wysyła filmy do YouTube; wymaga jednocześnie opcji --yt lub /yt.",
    )
    args = parser.parse_args()
    if args.publish and not args.yt:
        parser.error("--publish wymaga również opcji --yt lub /yt.")
    uruchom_automatyzacje(yt=args.yt, publikuj=args.publish)


if __name__ == "__main__":
    main()