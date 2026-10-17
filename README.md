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

## 🍎 Konfiguracja pod macOS

Projekt działa na macOS (kodek `h264_videotoolbox` lub `libx264`; NVIDIA nie jest potrzebna). Poniższe komendy wykonaj w Terminalu.

1. **Homebrew** (jeśli go nie masz) — instrukcja na [brew.sh](https://brew.sh/).
2. **Python, ImageMagick i FFmpeg:**
   ```bash
   brew install python imagemagick ffmpeg
   ```
3. **Środowisko wirtualne i biblioteki** (w folderze projektu):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```
   Przy kolejnych uruchomieniach najpierw wykonaj `source .venv/bin/activate`.
4. **Uruchomienie:**
   ```bash
   python ipsc_automato.py            # montaż + nazwy plików
   python ipsc_automato.py --yt       # dodatkowo podgląd YouTube
   ```
   Opcja `/yt` działa tak samo, ale w zsh/bash lepiej używać `--yt` (ukośnik na początku bywa traktowany jak ścieżka).
5. **YouTube:** konfiguracja OAuth jest identyczna jak na Windows (sekcja „Publikowanie Shorts na YouTube”). Plik `youtube_client_secret.json` zapisz w folderze projektu; logowanie otworzy się w domyślnej przeglądarce.

Uwagi: napisy z wynikami używają systemowego Arial Bold lub Helvetica; jeśli ImageMagick nie jest wykrywany, sprawdź `which magick` (na Apple Silicon Homebrew instaluje w `/opt/homebrew/bin`). Brak uprawnień do folderów rozwiąż w **Ustawienia systemowe → Prywatność i ochrona**.

## 📦 Instalacja bibliotek Pythona

Otwórz wiersz poleceń (CMD) w folderze, w którym znajduje się plik `ipsc_automato.py` oraz `requirements.txt`, a następnie uruchom komendę:

```bash
pip install -r requirements.txt
```

*Uwaga: Wymagane są specyficzne, starsze wersje bibliotek (`moviepy<2.0.0` oraz `decorator==4.4.2`), aby zapobiec błędom z importem modułu editor oraz błędowi `must be real number, not NoneType` przy renderowaniu.*

`requirements.txt` zawiera też biblioteki Google (`google-auth`, `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`) potrzebne do opcji `--yt`. Instaluj je tym samym interpreterem, którym uruchamiasz skrypt: `python -m pip install -r requirements.txt`.

## ⚙️ Konfiguracja Skryptu

Przed pierwszym uruchomieniem otwórz plik `ipsc_automato.py` w notatniku lub dowolnym edytorze kodu i dostosuj następujące ustawienia na samej górze pliku:

1. **ImageMagick:**
   Skrypt sam szuka `magick`/`convert` w `PATH` (Windows: dodatkowo w `C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\`). Jeśli masz inną wersję, zmień ścieżkę domyślną w wywołaniu `znajdz_imagemagick(...)` na górze `ipsc_automato.py`.

2. **Ścieżki do folderów roboczych:**
   Domyślnie są **względne** – liczone od folderu ze skryptem (`KATALOG_PROJEKTU`), więc projekt działa na Windows, macOS i Linuksie po skopiowaniu w dowolne miejsce:
   ```python
   FOLDER_WEJSCIOWY = os.path.join(KATALOG_PROJEKTU, "Surowe")      # Tu wrzucasz oryginalne nagrania (mp4/mov)
   FOLDER_WYJSCIOWY = os.path.join(KATALOG_PROJEKTU, "Gotowe")      # Tu pojawią się gotowe rolki
   FOLDER_MUZYKI = os.path.join(KATALOG_PROJEKTU, "Muzyka")         # Podkłady muzyczne (mp3)
   PLIK_Z_WYNIKAMI = os.path.join(KATALOG_PROJEKTU, "wyniki.txt")   # Wyniki zawodów
   PLIK_Z_TEKSTAMI = os.path.join(KATALOG_PROJEKTU, "dodatkowe_teksty.txt")   # Teksty u góry wideo
   PLIK_Z_TORAMI = os.path.join(KATALOG_PROJEKTU, "tory.txt")       # Kolejność torów
   ```
   Możesz je podmienić na dowolne własne ścieżki.

   **Czcionka i kodek (automatycznie, `ustawienia_systemu.py`):** Napisy z wynikami używają czcionki systemowej (Windows: `Arial-Bold`; pozostałe systemy: Arial Bold/Helvetica lub Liberation Sans/DejaVu Sans Bold, z czcionkami z folderu `Fonts` jako zapasowymi). Dodatkowe teksty u góry używają Mister Brush z `Fonts/mister-brush/MisterBrush.ttf`. Kodek: `h264_nvenc` (NVIDIA), na macOS `h264_videotoolbox`, w innym razie `libx264` (wolniejszy, ale działa wszędzie). Na macOS/Linuksie zainstaluj ImageMagick (`brew install imagemagick` / `sudo apt install imagemagick`).

3a. **Kolejność torów (`tory.txt`):**
   Obsługuje to moduł `mapowanie_torow.py`. Pliki z `FOLDER_WEJSCIOWY` są sortowane alfabetycznie, a **N-ta linia** pliku `tory.txt` to numer toru dla **N-tego pliku**. Przykład: jeśli plik jest drugi w sortowaniu, a druga linia w `tory.txt` to `1`, to jest to Tor 1 (i do niego zostaną dopasowane wyniki ze `wyniki.txt`).
   ```text
   2
   1
   3
   ```
   Jeśli pliku `tory.txt` brakuje lub ma za mało linii, numer toru wynika z pozycji w sortowaniu (1, 2, 3...).

3. **Dodatkowe teksty u góry wideo (`dodatkowe_teksty.txt`):**
   Każdy tekst wpisz w nawiasach kwadratowych, np. `[Klub ZSD]`. Plik może zawierać zero lub kilka wpisów, ale **maksymalnie 5** (kolejne są ignorowane).
   * Teksty pojawiają się po kolei, neonowym cyjanem (czcionka Oxanium Bold z folderu `Fonts\Oxanium\static`), w górnej części wideo.
   * Każdy tekst wyświetla się min. 5 s (max 8 s), a przerwa między tekstami wynosi min. 2 s. Teksty są rozłożone równomiernie na całym filmie (bez długiej pustki na końcu). Jeśli film jest za krótki, dodawane jest tyle tekstów, ile się zmieści.
   * Jeśli film jest za krótki, kolejne teksty z pliku nie są dodawane.

## 🚀 Jak używać skryptu?

1. **Przygotuj pliki wideo:** Po zawodach zrzuć nagrania z telefonu do `FOLDER_WEJSCIOWY`. 
   * *Skrypt sortuje pliki alfabetycznie po nazwie, a numer toru każdego z nich bierze z odpowiedniej linii w `tory.txt` (patrz punkt 3a). Bez `tory.txt` kolejne pliki to Tor 1, 2, 3, itd.*
2. **Przygotuj podkłady:** Upewnij się, że w `FOLDER_MUZYKI` masz chociaż jeden plik `.mp3`. Skrypt losuje muzykę dla każdego toru.
3. **Wklej wyniki:** Skopiuj swoje wyniki z PractiScore (tabelę zawierającą np. `%`, `Czas`, `HF`, `Punkty`) i wklej je bez formatowania do pliku `wyniki.txt`.
4. **Uruchom skrypt:**
   Otwórz terminal w folderze ze skryptem i wpisz:
   ```bash
   python ipsc_automato.py
   ```
   Po każdym udanym renderze plik w `Gotowe` jest automatycznie przemianowywany przez `generuj_nazwy.py` na `YYYY-MM-DD - Nazwa zawodów - Tor X #bodycam.mp4`. Wymaga to poprawnie uzupełnionego `opis_zawodow.txt`.
5. Poczekaj na wygenerowanie i przemianowanie plików wideo w `FOLDER_WYJSCIOWY`.

## 📺 Publikowanie Shorts na YouTube

### Konfiguracja OAuth (jednorazowo)

Skrypt używa **OAuth 2.0, a nie klucza API** — sam klucz API nie pozwala przesyłać filmów ani czytać prywatnej kolejki kanału.

1. W [Google Cloud Console](https://console.cloud.google.com/) utwórz lub wybierz projekt.
2. W **Interfejsy API i usługi → Biblioteka** włącz **YouTube Data API v3**.
3. Skonfiguruj ekran zgody OAuth (typ użytkowników **External**).
4. W [Audience](https://console.cloud.google.com/auth/audience), w sekcji **Test users**, dodaj konto Google, którym będziesz się logować (najlepiej zarządzające docelowym kanałem).
5. W **Dane logowania** utwórz **Identyfikator klienta OAuth** typu **Aplikacja komputerowa**, pobierz JSON i zapisz go w katalogu projektu jako `youtube_client_secret.json`.
6. Uruchom `python ipsc_automato.py --yt` i zaloguj się w przeglądarce. Powstanie lokalny `youtube_token.json`.

Nie używaj konta usługi — upload odbywa się w imieniu zalogowanego kanału. Pliki `youtube_client_secret.json`, `youtube_token.json` i `youtube_upload_state.json` (rejestr wysłanych filmów) są poufne i ignorowane przez Git — nie udostępniaj ich.

> Projekt w trybie **Testing** pozwala logować się tylko dodanym testerom, a autoryzacja wygasa po 7 dniach — wtedy usuń `youtube_token.json` i zaloguj się ponownie.

### Nazwy plików i publikacja

Uzupełnij `opis_zawodow.txt` nazwą i datą zawodów. Generator `generuj_nazwy.py` odczytuje nazwę z pola `Nazwa zawodów:` lub pierwszej niepustej linii, datę z `Match starts: August 09, 2026` albo `Data zawodów: 09.08.2026`, a numer toru z nazwy takiej jak `Gotowe_Stage_3.mp4`. Tytuł ma format `YYYY-MM-DD - Nazwa zawodów - Tor X #bodycam`, jest ograniczany do 100 znaków i służy również jako nazwa pliku MP4. Jest uruchamiany automatycznie po standardowym montażu; można go też wywołać ręcznie:

```bash
python generuj_nazwy.py Gotowe_Stage_1.mp4
```

Uploader `youtube_upload.py` jest uruchamiany z głównego skryptu wyłącznie po podaniu opcji `/yt` lub `--yt`. Odczytuje playlistę przesłanych filmów kanału, sprawdza zaplanowane publikacje i wybiera najbliższy wolny dzień: poniedziałek–piątek o 7:30, sobota–niedziela o 10:00 czasu `Europe/Warsaw`. Uwzględnia terminy filmów zaplanowanych oraz dni publikacji filmów publicznych i niepublicznych. Opis YouTube zawiera tylko nazwę, datę, lokalizację, typ i poziom zawodów oraz hashtagi tworzone z tych pól — nie kopiuje całego pliku z opisem zawodów.

Standardowe uruchomienie montuje filmy i zmienia ich nazwy, ale nie uruchamia połączenia z YouTube. Opcja `/yt` lub `--yt` po zakończeniu montażu uruchamia **tylko podgląd** kolejki — nic nie jest przesyłane:

```bash
python ipsc_automato.py --yt
```

Po sprawdzeniu podglądu rzeczywisty upload wymaga obu opcji:

```bash
python ipsc_automato.py --yt --publish
```

### Podsumowanie komend

| Komenda | Działanie |
|---|---|
| `python ipsc_automato.py` | Montaż + nadanie nazw plikom; bez YouTube |
| `python ipsc_automato.py --yt` (lub `/yt`) | Jak wyżej + podgląd tytułów i terminów; nic nie jest wysyłane |
| `python ipsc_automato.py --yt --publish` | Jak wyżej + rzeczywisty upload zaplanowany na wolne terminy |
| `python generuj_nazwy.py Gotowe_Stage_1.mp4` | Ręczna zmiana nazwy jednego pliku |
| `python youtube_upload.py [plik\|folder] [--publish]` | Bezpośrednie wywołanie uploadera (domyślnie folder `Gotowe`) |

`--publish` bez `/yt` lub `--yt` jest odrzucane. Każdy film musi być pionowy lub kwadratowy i trwać maksymalnie 3 minuty. Przy wielu plikach uploader planuje najwyżej jedną publikację dziennie na wybranym kanale. Jeśli OAuth zwróci więcej niż jeden kanał, ustaw zmienną środowiskową `YOUTUBE_CHANNEL_ID` na ID właściwego kanału. Google może wymagać weryfikacji projektu OAuth, zanim filmy przesyłane przez API będą mogły być publiczne.

## ⚠️ Najczęstsze problemy

*   **`ModuleNotFoundError: No module named 'google'`:** Brakuje bibliotek Google. Uruchom `python -m pip install -r requirements.txt` tym samym Pythonem, którym odpalasz skrypt.
*   **`Błąd 403: access_denied` przy logowaniu Google:** Projekt OAuth jest w trybie Testing, a Twoje konto nie jest testerem. Dodaj je w Google Cloud Console → Audience → Test users i spróbuj ponownie.
*   **`Brak pliku OAuth ... youtube_client_secret.json`:** Pobierz dane klienta OAuth typu „Aplikacja komputerowa” i zapisz je w katalogu projektu pod tą nazwą.
*   **`Nie można jednoznacznie wybrać kanału`:** Konto ma kilka kanałów — ustaw zmienną środowiskową `YOUTUBE_CHANNEL_ID`.
*   **Błąd daty/nazwy zawodów:** Uzupełnij `opis_zawodow.txt` (nazwa + `Match starts:`/`Data zawodów:`); numer toru musi występować w nazwie pliku (`Gotowe_Stage_3.mp4`).
*   **Błąd `[WinError 2] Nie można odnaleźć określonego pliku` lub problem z `None`:** MoviePy nie może znaleźć programu ImageMagick. Upewnij się, że ścieżka do `magick.exe` (lub `convert.exe`) w `change_settings` w kodzie jest w 100% poprawna dla Twojego komputera.
*   **Błąd `ModuleNotFoundError: No module named 'moviepy.editor'`:** Masz zainstalowaną nową wersję MoviePy (2.0+). Wpisz w konsoli `pip uninstall moviepy` a następnie `pip install "moviepy<2.0.0"`.
*   **Błąd `must be real number, not NoneType` przy zapisie wideo:** Masz zbyt nową bibliotekę `decorator`. Użyj `pip install "decorator==4.4.2"`.
*   **Błąd `Accessing time t=... with clip duration=...` dla muzyki:** Skrypt zapętla muzykę, więc krótki utwór nie powinien go wywołać; sprawdź, czy plik `.mp3` nie jest uszkodzony.
*   **Pliki `*TEMP_MPY_*`:** Resztki nieudanych renderów. Skrypt je pomija, możesz je bezpiecznie usunąć.