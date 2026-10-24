import argparse
import os
import re
import random
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Optional
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, CompositeAudioClip, AudioFileClip
import moviepy.audio.fx.all as afx
from moviepy.config import change_settings
from timer_detect import zglos_wykrycie_timera
from timer_trim import trim_video
from additional_texts import create_text_clips
from logo_overlay import create_logo_clip
from track_order import RESOLUTIONS, DEFAULT_RESOLUTION
from track_mapping import assign_tracks
from file_migration import move_old_files
from app_settings import ensure_settings_file, find_imagemagick
from system_settings import PROJECT_DIR, choose_font, check_environment, preset_for_codec
from generate_names import generate_title, rename_file
from video_cancellation import CancellableProgressLogger, GenerationCancelled

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

# Ścieżka do ImageMagick pochodzi z settings.json (klucz imagemagick_path); gdy jej tam nie ma, szukamy w PATH.
ensure_settings_file()


def zastosuj_imagemagick():
    """Odczytuje ścieżkę z settings.json i przekazuje ją MoviePy. Zwraca ścieżkę lub None."""
    sciezka = find_imagemagick()
    if sciezka:
        change_settings({"IMAGEMAGICK_BINARY": sciezka})
    return sciezka


_magick = zastosuj_imagemagick()

# ===================================================================
# KONFIGURACJA ŚCIEŻEK
# ===================================================================
FOLDER_WEJSCIOWY = os.path.join(PROJECT_DIR, "Surowe")
FOLDER_WYJSCIOWY = os.path.join(PROJECT_DIR, "Gotowe")
FOLDER_MUZYKI = os.path.join(PROJECT_DIR, "Muzyka")
PLIK_Z_WYNIKAMI = os.path.join(PROJECT_DIR, "wyniki.txt")
PLIK_Z_TEKSTAMI = os.path.join(PROJECT_DIR, "teksty_wideo.txt")
PLIK_Z_TORAMI = os.path.join(PROJECT_DIR, "mapowanie_torow.txt")
PLIK_OPISU_ZAWODOW = os.path.join(PROJECT_DIR, "opis_zawodow.txt")
move_old_files(PROJECT_DIR)


TRYB_WYNIKOW_PRACTISCORE = "practiscore"
TRYB_WYNIKOW_ECM = "ecm"
TRYB_WYNIKOW_TRENING = "trening"


@dataclass(frozen=True)
class KonfiguracjaSciezek:
    folder_wejsciowy: Path = Path(FOLDER_WEJSCIOWY)
    folder_wyjsciowy: Path = Path(FOLDER_WYJSCIOWY)
    folder_muzyki: Path = Path(FOLDER_MUZYKI)
    plik_z_wynikami: Path = Path(PLIK_Z_WYNIKAMI)
    plik_z_tekstami: Path = Path(PLIK_Z_TEKSTAMI)
    plik_z_torami: Path = Path(PLIK_Z_TORAMI)
    plik_opisu_zawodow: Path = Path(PLIK_OPISU_ZAWODOW)
    domyslna_orientacja: str = "V"
    dodaj_napisy: bool = True
    plik_logo: str = ""
    tryb_wynikow: str = TRYB_WYNIKOW_PRACTISCORE

# ===================================================================
# FUNKCJE POMOCNICZE
# ===================================================================

WZORZEC_PRACTISCORE = re.compile(
    r"Stage\s+(\d+).*?(\d+)\s+([\d.]+%)\s+[\d.]+\s+(\d+)\s+([\d.]+)\s+([\d.]+)",
    re.IGNORECASE,
)
# Wiersz ECM: STG, FACTOR, PTS, A, C, D, MI, NS, PE, pusta kolumna, TIME
WZORZEC_ECM = re.compile(
    r"^[ \t]*Stage[ \t]+(\d+)[ \t]+([\d.]+)[ \t]+(\d+)(?:[ \t]+\d+){6}[ \t]+([\d.]+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# Wiersz ręcznie wpisany w formacie: numer toru; czas
WZORZEC_TRENING = re.compile(
    r"^[ \t]*(\d+)[ \t]*;[ \t]*(\d+(?:[.,]\d+)?)[ \t]*$",
    re.MULTILINE,
)


def _czytaj_wyniki_practiscore(tekst):
    wyniki = {}
    for dopasowanie in WZORZEC_PRACTISCORE.finditer(tekst):
        nr_toru = dopasowanie.group(1)
        wyniki[nr_toru] = {
            "miejsce": dopasowanie.group(2),
            "procent": dopasowanie.group(3),
            "punkty": dopasowanie.group(4),
            "hf": dopasowanie.group(5),
            "czas": float(dopasowanie.group(6)) # CZAS Z PRACTISCORE
        }
    return wyniki


def _czytaj_wyniki_ecm(tekst):
    wyniki = {}
    for dopasowanie in WZORZEC_ECM.finditer(tekst):
        nr_toru = str(int(dopasowanie.group(1)))
        wyniki[nr_toru] = {
            "miejsce": "",
            "procent": "",
            "punkty": dopasowanie.group(3),
            "hf": dopasowanie.group(2),
            "czas": float(dopasowanie.group(4)) # CZAS Z ECM
        }
    return wyniki


def _czytaj_wyniki_trening(tekst):
    wyniki = {}
    for dopasowanie in WZORZEC_TRENING.finditer(tekst):
        nr_toru = str(int(dopasowanie.group(1)))
        wyniki[nr_toru] = {
            "miejsce": "",
            "procent": "",
            "punkty": "",
            "hf": "",
            "czas": float(dopasowanie.group(2).replace(",", "."))
        }
    return wyniki


CZYTNIKI_WYNIKOW = {
    TRYB_WYNIKOW_PRACTISCORE: _czytaj_wyniki_practiscore,
    TRYB_WYNIKOW_ECM: _czytaj_wyniki_ecm,
    TRYB_WYNIKOW_TRENING: _czytaj_wyniki_trening,
}


def czytaj_wyniki_z_pliku(sciezka_do_pliku, tryb=TRYB_WYNIKOW_PRACTISCORE):
    if not os.path.exists(sciezka_do_pliku):
        print(f"Brak pliku z wynikami: {sciezka_do_pliku}")
        return {}

    czytnik = CZYTNIKI_WYNIKOW.get(tryb)
    if czytnik is None:
        raise ValueError(f"Nieznany tryb wyników: {tryb}")

    with open(sciezka_do_pliku, 'r', encoding='utf-8') as f:
        tekst = f.read()

    return czytnik(tekst)


# ===================================================================
# GŁÓWNA LOGIKA
# ===================================================================

def uruchom_automatyzacje(
    yt=False,
    publikuj=False,
    konfiguracja: Optional[KonfiguracjaSciezek] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    cancel_event: Optional[Event] = None,
):
    konfiguracja = konfiguracja or KonfiguracjaSciezek()

    def raportuj(tekst):
        print(tekst)
        if log_callback:
            log_callback(tekst)

    def sprawdz_przerwanie():
        if cancel_event and cancel_event.is_set():
            raise GenerationCancelled("Generowanie przerwano przez użytkownika.")

    srodowisko_ok, kodek = check_environment(zastosuj_imagemagick(), raportuj)
    if not srodowisko_ok:
        raportuj("Nie można rozpocząć montażu: sprawdź wymagane narzędzia systemowe.")
        return False

    os.makedirs(konfiguracja.folder_wyjsciowy, exist_ok=True)
    
    if konfiguracja.dodaj_napisy or konfiguracja.plik_z_wynikami.is_file():
        dane_torow = czytaj_wyniki_z_pliku(str(konfiguracja.plik_z_wynikami), konfiguracja.tryb_wynikow)
    else:
        dane_torow = {}
    muzyka_pliki = [m for m in os.listdir(konfiguracja.folder_muzyki) if m.lower().endswith('.mp3')]
    
    wideo_pliki = [
        w for w in os.listdir(konfiguracja.folder_wejsciowy)
        if w.lower().endswith(('.mp4', '.mov')) and "TEMP_MPY_" not in w.upper()
    ]
    wideo_pliki.sort() 
    przypisane_tory = assign_tracks(
        wideo_pliki,
        str(konfiguracja.plik_z_torami),
        RESOLUTIONS.get(konfiguracja.domyslna_orientacja, DEFAULT_RESOLUTION),
    )
    if not przypisane_tory:
        raportuj(f"Nie znaleziono filmów MP4/MOV w folderze: {konfiguracja.folder_wejsciowy}")
    
    liczba_bledow = 0
    przerwano = False
    for indeks, (nazwa_pliku, nr_toru, rozdzielczosc) in enumerate(przypisane_tory, start=1):
        if cancel_event and cancel_event.is_set():
            przerwano = True
            raportuj("Generowanie przerwano przez użytkownika.")
            if progress_callback:
                progress_callback(indeks, len(przypisane_tory), nazwa_pliku, "cancelled")
            break

        raportuj(f"\n>>> Przetwarzanie: {nazwa_pliku} jako TOR {nr_toru}")
        
        dane = dane_torow.get(nr_toru)
        if dane is None and konfiguracja.dodaj_napisy:
            raportuj(f"Pominięto {nazwa_pliku}: brak wyników dla toru {nr_toru}.")
            if progress_callback:
                progress_callback(indeks, len(przypisane_tory), nazwa_pliku, "skipped")
            continue
            
        czas_przebiegu = dane["czas"] if dane else None
        
        sciezka_wej = os.path.join(konfiguracja.folder_wejsciowy, nazwa_pliku)
        sciezka_wyj = os.path.join(konfiguracja.folder_wyjsciowy, f"Gotowe_Stage_{nr_toru}.mp4")
        sciezka_wyj = Path(sciezka_wyj)
        sciezka_tymczasowa = sciezka_wyj.with_name(
            f"{sciezka_wyj.stem}_TEMP_MPY_{uuid.uuid4().hex}.mp4"
        )
        sciezka_audio_tymczasowego = sciezka_tymczasowa.with_name(
            f"{sciezka_tymczasowa.stem}_TEMP_AUDIO.m4a"
        )
        video = None
        wideo_koncowe = None
        audio_muzyka = None
        
        try:
            sprawdz_przerwanie()
            sygnaly = zglos_wykrycie_timera(sciezka_wej, raportuj, cancel_event)
            sprawdz_przerwanie()
            video = VideoFileClip(sciezka_wej)
            sprawdz_przerwanie()
            video = trim_video(video, sygnaly, czas_przebiegu, raportuj)

            nowy_czas_trwania = video.duration
            raportuj(f"Czas wideo: {nowy_czas_trwania:.2f}s")
            
            # --- MUZYKA ---
            if muzyka_pliki:
                losowy_utwor = random.choice(muzyka_pliki)
                sciezka_muzyki = os.path.join(konfiguracja.folder_muzyki, losowy_utwor)
                
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
            warstwy_napisow = []
            if konfiguracja.dodaj_napisy:
                tekst_wyswietlany = (f"STAGE {nr_toru} | Miejsce: {dane['miejsce']} ({dane['procent']})\n"
                                     f"Czas: {dane['czas']}s | HF: {dane['hf']} | Pkt: {dane['punkty']}")
            
                napis = TextClip(tekst_wyswietlany, fontsize=55, color='white', 
                                 font=choose_font(), stroke_color='black', stroke_width=2.5, align='center')
            
                # Napis wyrównany do dołu
                napis = napis.set_position(('center', 0.85), relative=True).set_duration(nowy_czas_trwania)
                warstwy_napisow = [napis]
            
            # --- ZMIANA ROZDZIELCZOŚCI (H = 1920x1080, V/domyślnie = 1080x1920) ---
            video = video.resize(newsize=rozdzielczosc)
            # Tworzymy Composite z jawnie ustawionym rozmiarem wyjściowym, aby napisy i pozycjonowanie działały poprawnie
            if konfiguracja.dodaj_napisy:
                warstwy_napisow += create_text_clips(
                    str(konfiguracja.plik_z_tekstami), nowy_czas_trwania, raportuj
                )
            klip_logo = create_logo_clip(konfiguracja.plik_logo, nowy_czas_trwania, rozdzielczosc[0], raportuj)
            if klip_logo is not None:
                warstwy_napisow.append(klip_logo)
            wideo_koncowe = CompositeVideoClip([video, *warstwy_napisow], size=rozdzielczosc).set_fps(30)
            sprawdz_przerwanie()
            
            # --- RENDEROWANIE Z ZACHOWANIEM KOLORÓW I BEZ OBROTÓW ---
            raportuj(f"Rozpoczynam renderowanie ({kodek})...")
            wideo_koncowe.write_videofile(
                str(sciezka_tymczasowa),
                fps=30, 
                codec=kodek, 
                audio_codec="aac",
                bitrate="8000k",    
                preset=preset_for_codec(kodek),
                ffmpeg_params=['-pix_fmt', 'yuv420p'],  # Gwarantuje poprawne kolory i odtwarzanie w Windows
                temp_audiofile=str(sciezka_audio_tymczasowego),
                logger=CancellableProgressLogger(cancel_event or Event()),
            )
            
            sprawdz_przerwanie()
            os.replace(sciezka_tymczasowa, sciezka_wyj)
            tytul = generate_title(sciezka_wyj, konfiguracja.plik_opisu_zawodow)
            sciezka_wyj = rename_file(sciezka_wyj, tytul)
            raportuj(f"Nadano nazwę: {sciezka_wyj.name}")
            raportuj("Zakończono sukcesem!\n")
            if progress_callback:
                progress_callback(indeks, len(przypisane_tory), nazwa_pliku, "done")
            
        except GenerationCancelled:
            przerwano = True
            raportuj("Generowanie przerwano przez użytkownika.")
            if progress_callback:
                progress_callback(indeks, len(przypisane_tory), nazwa_pliku, "cancelled")
            break
        except Exception as e:
            liczba_bledow += 1
            raportuj(f"BŁĄD podczas przetwarzania: {str(e)}\n")
            if progress_callback:
                progress_callback(indeks, len(przypisane_tory), nazwa_pliku, "error")
        finally:
            for klip in (wideo_koncowe, video, audio_muzyka):
                if klip is not None:
                    klip.close()
            for plik_tymczasowy in (sciezka_tymczasowa, sciezka_audio_tymczasowego):
                try:
                    plik_tymczasowy.unlink()
                except FileNotFoundError:
                    pass

    if yt and not przerwano:
        from youtube_upload import main as uruchom_youtube

        argumenty_youtube = [str(konfiguracja.folder_wyjsciowy)]
        if publikuj:
            argumenty_youtube.append("--publish")
        uruchom_youtube(argumenty_youtube)
    return bool(przypisane_tory) and liczba_bledow == 0 and not przerwano


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