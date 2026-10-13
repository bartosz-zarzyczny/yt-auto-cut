import os
import re
import random
import numpy as np
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, CompositeAudioClip, AudioFileClip
import moviepy.audio.fx.all as afx
from moviepy.config import change_settings

# Ścieżka do ImageMagick (zostaw swoją, jeśli działała)
change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"})

# ===================================================================
# KONFIGURACJA ŚCIEŻEK
# ===================================================================
FOLDER_WEJSCIOWY = r"D:\Repo\yt-auto-cut\Surowe"      
FOLDER_WYJSCIOWY = r"D:\Repo\yt-auto-cut\Gotowe"      
FOLDER_MUZYKI = r"D:\Repo\yt-auto-cut\Muzyka"         
PLIK_Z_WYNIKAMI = r"D:\Repo\yt-auto-cut\wyniki.txt"   

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


def znajdz_czas_timera_od_tylu(video_clip, czas_z_tabeli):
    """
    Nowa logika: Szuka ostatniego strzału i na jego podstawie wylicza timer.
    """
    audio_clip = video_clip.audio
    # Pobieramy całe audio do analizy
    ramki_audio = list(audio_clip.iter_frames(fps=22050))
    audio_array = np.vstack(ramki_audio)
    
    if len(audio_array.shape) > 1:
        mono = audio_array.mean(axis=1)
    else:
        mono = audio_array
        
    okno = int(22050 * 0.1) # Badamy paczki po 100ms
    glosnosci = []
    
    # Skanowanie całego nagrania
    for i in range(0, len(mono), okno):
        fragment = mono[i:i+okno]
        rms = np.sqrt(np.mean(fragment**2))
        glosnosci.append((i / 22050.0, rms))
        
    # Znajdujemy głośność najgłośniejszego wystrzału na nagraniu
    max_glosnosc = max([g[1] for g in glosnosci])
    
    # Ustawiamy próg na 40% maksymalnej głośności (bezpieczny próg dla strzału)
    prog = max_glosnosc * 0.4 
    
    # Przeszukujemy listę OD KOŃCA, by znaleźć OSTATNI wystrzał
    ostatni_strzal_czas = 0
    for czas, rms in reversed(glosnosci):
        if rms >= prog:
            ostatni_strzal_czas = czas
            break
            
    # Obliczamy, gdzie musiał paść Timer! (Ostatni strzał MINUS czas przejazdu)
    kalkulowany_timer = ostatni_strzal_czas - czas_z_tabeli
    
    # Zabezpieczenie przed błędami
    return max(0.0, kalkulowany_timer)


# ===================================================================
# GŁÓWNA LOGIKA
# ===================================================================

def uruchom_automatyzacje():
    os.makedirs(FOLDER_WYJSCIOWY, exist_ok=True)
    
    dane_torow = czytaj_wyniki_z_pliku(PLIK_Z_WYNIKAMI)
    muzyka_pliki = [m for m in os.listdir(FOLDER_MUZYKI) if m.lower().endswith('.mp3')]
    
    wideo_pliki = [w for w in os.listdir(FOLDER_WEJSCIOWY) if w.lower().endswith(('.mp4', '.mov'))]
    wideo_pliki.sort() 
    
    for index, nazwa_pliku in enumerate(wideo_pliki):
        nr_toru = str(index + 1)
        print(f"\n>>> Przetwarzanie: {nazwa_pliku} jako TOR {nr_toru}")
        
        if nr_toru not in dane_torow:
            continue
            
        dane = dane_torow[nr_toru]
        czas_z_tabeli = dane['czas']
        
        sciezka_wej = os.path.join(FOLDER_WEJSCIOWY, nazwa_pliku)
        sciezka_wyj = os.path.join(FOLDER_WYJSCIOWY, f"Gotowe_Stage_{nr_toru}.mp4")
        
        try:
            video = VideoFileClip(sciezka_wej)
            
            # --- ZNALEZIENIE TIMERA METODĄ OSTATNIEGO STRZAŁU ---
            start_timera = znajdz_czas_timera_od_tylu(video, czas_z_tabeli)
            
            # Tniemy od 0.2s przed obliczonym timerem do 0.5s po ostatnim strzale
            start_ciecia = max(0, start_timera - 0.2)
            koniec_ciecia = min(video.duration, start_timera + czas_z_tabeli + 0.5)
            
            przyciete_video = video.subclip(start_ciecia, koniec_ciecia)
            nowy_czas_trwania = przyciete_video.duration
            print(f"Kalkulowany Timer: {start_timera:.2f}s | Wycięty czas wideo: {nowy_czas_trwania:.2f}s")
            
            # --- MUZYKA ---
            if muzyka_pliki:
                losowy_utwor = random.choice(muzyka_pliki)
                sciezka_muzyki = os.path.join(FOLDER_MUZYKI, losowy_utwor)
                
                audio_muzyka = AudioFileClip(sciezka_muzyki).subclip(0, nowy_czas_trwania)
                
                if hasattr(audio_muzyka, 'volx'):
                    audio_muzyka = audio_muzyka.volx(0.12)
                elif hasattr(audio_muzyka, 'multiply_volume'):
                    audio_muzyka = audio_muzyka.multiply_volume(0.12)
                else:
                    audio_muzyka = audio_muzyka.fl(lambda gf, t: 0.12 * gf(t), keep_duration=True)
                    
                audio_muzyka = audio_muzyka.fx(afx.audio_fadeout, 1.0)
                
                ziksowane_audio = CompositeAudioClip([przyciete_video.audio, audio_muzyka])
                przyciete_video = przyciete_video.set_audio(ziksowane_audio)
            
            # --- NAPISY ---
            tekst_wyswietlany = (f"STAGE {nr_toru} | Miejsce: {dane['miejsce']} ({dane['procent']})\n"
                                 f"Czas: {dane['czas']}s | HF: {dane['hf']} | Pkt: {dane['punkty']}")
            
            napis = TextClip(tekst_wyswietlany, fontsize=55, color='white', 
                             font='Arial-Bold', stroke_color='black', stroke_width=2.5, align='center')
            
            # Napis wyrównany do dołu
            napis = napis.set_position(('center', 0.85), relative=True).set_duration(nowy_czas_trwania)
            
                        # --- ZMIANA ROZDZIELCZOŚCI NA 1080x1920 (portrait) ---
                        # Dopasowujemy przycięte wideo do zadanej rozdzielczości (szer. x wys.)
                        przyciete_video = przyciete_video.resize(newsize=(1080, 1920))
                        # Tworzymy Composite z jawnie ustawionym rozmiarem wyjściowym, aby napisy i pozycjonowanie działały poprawnie
                        wideo_koncowe = CompositeVideoClip([przyciete_video, napis], size=(1080, 1920))
            
            # --- RENDEROWANIE Z ZACHOWANIEM KOLORÓW I BEZ OBROTÓW ---
            print(f"Rozpoczynam renderowanie (NVENC)...")
            wideo_koncowe.write_videofile(
                sciezka_wyj, 
                fps=30, 
                codec="h264_nvenc", 
                audio_codec="aac",
                bitrate="8000k",    
                preset="fast",
                ffmpeg_params=['-pix_fmt', 'yuv420p'],  # Gwarantuje poprawne kolory i odtwarzanie w Windows
                logger=None         
            )
            
            video.close()
            wideo_koncowe.close()
            print("Zakończono sukcesem!\n")
            
        except Exception as e:
            print(f"BŁĄD podczas przetwarzania: {str(e)}\n")

if __name__ == "__main__":
    uruchom_automatyzacje()