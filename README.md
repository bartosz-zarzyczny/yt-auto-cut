# Automatyzacja Montażu Wideo IPSC 🔫🎬

Ten skrypt w Pythonie automatyzuje proces montażu nagrań wideo z zawodów IPSC. Przetwarza pliki wideo w całej ich długości (bez przycinania), zapętla i podkłada muzykę z efektem fade-out, zmienia format na pionowy 1080x1920 i dodaje planszę z Twoimi wynikami (czas, miejsce, punkty, Hit Factor).

Dzięki wykorzystaniu sprzętowego kodera karty graficznej NVIDIA (NVENC) renderowanie gotowych filmów jest błyskawiczne.

## 🛠️ Wymagania wstępne (Oprogramowanie)

Aby skrypt działał poprawnie, musisz zainstalować w systemie Windows następujące elementy:

1. **Python (3.8 lub nowszy):** Pamiętaj, aby podczas instalacji zaznaczyć pole *„Add Python to PATH”*.
2. **ImageMagick (Niezbędny do napisów!):**
   * Pobierz wersję dla Windows ze strony: [imagemagick.org](https://imagemagick.org/script/download.php#windows) (najlepiej pierwszą pozycję `.exe`, np. `ImageMagick-7.1.x-Q16-HDRI-x64-dll.exe`).
   * **BARDZO WAŻNE:** Podczas instalacji musisz zaznaczyć pole **"Install legacy utilities (e.g. convert)"**.
3. Karta graficzna **NVIDIA** (np. RTX 4060) w celu obsługi szybkiego renderowania `h264_nvenc`.

## 📦 Instalacja bibliotek Pythona

Otwórz wiersz poleceń (CMD) w folderze, w którym znajduje się plik `ipsc_automato.py` oraz `requirements.txt`, a następnie uruchom komendę:

```bash
pip install -r requirements.txt
```

*Uwaga: Wymagane są specyficzne, starsze wersje bibliotek (`moviepy<2.0.0` oraz `decorator==4.4.2`), aby zapobiec błędom z importem modułu editor oraz błędowi `must be real number, not NoneType` przy renderowaniu.*

## ⚙️ Konfiguracja Skryptu

Przed pierwszym uruchomieniem otwórz plik `ipsc_automato.py` w notatniku lub dowolnym edytorze kodu i dostosuj następujące ustawienia na samej górze pliku:

1. **Ścieżka do ImageMagick:**
   Sprawdź w swoim systemie (zazwyczaj w `C:\Program Files\`), jak dokładnie nazywa się folder ImageMagick i podmień ścieżkę w poniższej linijce:
   ```python
   change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"})
   ```

2. **Ścieżki do folderów roboczych:**
   Możesz stworzyć własną strukturę folderów, np. na dysku C:
   ```python
   FOLDER_WEJSCIOWY = r"C:\IPSC\Surowe"      # Tu wrzucasz oryginalne nagrania (mp4/mov)
   FOLDER_WYJSCIOWY = r"C:\IPSC\Gotowe"      # Tu pojawią się gotowe rolki
   FOLDER_MUZYKI = r"C:\IPSC\Muzyka"         # Tu wrzuć swoje ulubione podkłady muzyczne (mp3)
   PLIK_Z_WYNIKAMI = r"C:\IPSC\wyniki.txt"   # Plik tekstowy ze skopiowanymi wynikami zawodów
   PLIK_Z_TEKSTAMI = r"C:\IPSC\dodatkowe_teksty.txt"   # Teksty wyświetlane u góry wideo
   ```

3. **Dodatkowe teksty u góry wideo (`dodatkowe_teksty.txt`):**
   Każdy tekst wpisz w nawiasach kwadratowych, np. `[Klub ZSD]`. Plik może zawierać zero lub kilka wpisów, ale **maksymalnie 5** (kolejne są ignorowane).
   * Teksty pojawiają się po kolei, neonowym cyjanem (czcionka Oxanium Bold z folderu `Fonts\Oxanium\static`), w górnej części wideo.
   * Każdy tekst wyświetla się min. 5 s (max 8 s), a przerwa między tekstami wynosi min. 2 s. Teksty są rozłożone równomiernie na całym filmie (bez długiej pustki na końcu). Jeśli film jest za krótki, dodawane jest tyle tekstów, ile się zmieści.
   * Jeśli film jest za krótki, kolejne teksty z pliku nie są dodawane.

## 🚀 Jak używać skryptu?

1. **Przygotuj pliki wideo:** Po zawodach zrzuć nagrania z telefonu do `FOLDER_WEJSCIOWY`. 
   * *Skrypt posortuje je chronologicznie po nazwie (dacie modyfikacji/utworzenia), przypisując najstarszy plik jako Tor 1, kolejny jako Tor 2, itd.*
2. **Przygotuj podkłady:** Upewnij się, że w `FOLDER_MUZYKI` masz chociaż jeden plik `.mp3`. Skrypt losuje muzykę dla każdego toru.
3. **Wklej wyniki:** Skopiuj swoje wyniki z PractiScore (tabelę zawierającą np. `%`, `Czas`, `HF`, `Punkty`) i wklej je bez formatowania do pliku `wyniki.txt`.
4. **Uruchom skrypt:**
   Otwórz terminal w folderze ze skryptem i wpisz:
   ```bash
   python ipsc_automato.py
   ```
5. Poczekaj na wygenerowanie plików wideo w `FOLDER_WYJSCIOWY`.

## ⚠️ Najczęstsze problemy

*   **Błąd `[WinError 2] Nie można odnaleźć określonego pliku` lub problem z `None`:** MoviePy nie może znaleźć programu ImageMagick. Upewnij się, że ścieżka do `magick.exe` (lub `convert.exe`) w `change_settings` w kodzie jest w 100% poprawna dla Twojego komputera.
*   **Błąd `ModuleNotFoundError: No module named 'moviepy.editor'`:** Masz zainstalowaną nową wersję MoviePy (2.0+). Wpisz w konsoli `pip uninstall moviepy` a następnie `pip install "moviepy<2.0.0"`.
*   **Błąd `must be real number, not NoneType` przy zapisie wideo:** Masz zbyt nową bibliotekę `decorator`. Użyj `pip install "decorator==4.4.2"`.
*   **Błąd `Accessing time t=... with clip duration=...` dla muzyki:** Skrypt zapętla muzykę, więc krótki utwór nie powinien go wywołać; sprawdź, czy plik `.mp3` nie jest uszkodzony.
*   **Pliki `*TEMP_MPY_*`:** Resztki nieudanych renderów. Skrypt je pomija, możesz je bezpiecznie usunąć.