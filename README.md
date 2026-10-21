# Automatyzacja Montażu Wideo IPSC 🔫🎬

Ten skrypt w Pythonie automatyzuje proces montażu nagrań wideo z zawodów IPSC. Przetwarza pliki wideo w całej ich długości (bez przycinania), zapętla i podkłada muzykę z efektem fade-out, zmienia format na pionowy 1080x1920 i dodaje planszę z Twoimi wynikami (czas, miejsce, punkty, Hit Factor).

Jeśli komputer ma obsługiwaną kartę graficzną (NVIDIA, AMD lub Intel), renderowanie korzysta ze sprzętowego kodera i jest bardzo szybkie. Bez niej montaż nadal działa, ale na procesorze (wolniej).

## 🛠️ Wymagania wstępne (Oprogramowanie)

Aby skrypt działał poprawnie, musisz zainstalować w systemie Windows następujące elementy:

1. **Python (3.8 lub nowszy):** Pamiętaj, aby podczas instalacji zaznaczyć pole *„Add Python to PATH”*.
2. **ImageMagick (Niezbędny do napisów!):**
   * Pobierz wersję dla Windows ze strony: [imagemagick.org](https://imagemagick.org/script/download.php#windows) (najlepiej pierwszą pozycję `.exe`, np. `ImageMagick-7.1.x-Q16-HDRI-x64-dll.exe`).
   * **BARDZO WAŻNE:** Podczas instalacji musisz zaznaczyć pole **"Install legacy utilities (e.g. convert)"**.
3. *(Opcjonalnie)* **Karta graficzna z kodowaniem sprzętowym H.264** dla szybszego renderowania — **NVIDIA** (`h264_nvenc`, np. RTX 4060), **AMD** (`h264_amf`) lub grafika **Intel** (`h264_qsv`). Karta nie jest wymagana: bez niej aplikacja automatycznie użyje `libx264` (procesor), co jest wolniejsze, ale działa na każdym komputerze. Do kodowania sprzętowego potrzebne są aktualne sterowniki oraz pełna wersja FFmpeg (np. z [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)).

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

## 🖥️ Aplikacja desktopowa (Windows i macOS)

Po zainstalowaniu zależności uruchom aplikację poleceniem:

```bash
python desktop_app.py
```

Interfejs w ciemnym motywie jest podzielony na pięć zakładek (w tej kolejności):

| Zakładka | Zawartość |
|---|---|
| **Główna** | Checkbox **Czy dodać napisy** (domyślnie odznaczony), wybór folderów **Nagrania źródłowe** i **Gotowe filmy**, przyciski **Rozpocznij montaż** / **Przerwij generowanie**, pasek postępu i dziennik pracy |
| **Zawody** | Wybór **Wideo Pionowe / Poziome** oraz edytory plików **Mapowanie torów** (`mapowanie_torow.txt`) i **Wyniki zawodów** (`wyniki.txt`) |
| **Konfiguracja** | Folder z muzyką, ścieżka do programu **ImageMagick** (zapis w `settings.json`) oraz edytory plików **Teksty wideo** (`teksty_wideo.txt`) i **Opis zawodów** (`opis_zawodow.txt`) |
| **YouTube** | Sekcja **PUBLIKACJA** (własne dni tygodnia i godziny albo „Publikuj wszystkie od razu”), wybór folderu z filmami, przyciski **Wyślij do YT** / **Przerwij wysyłanie**, opcja „Tylko podgląd” i dziennik wysyłania |
| **Pomoc** | Przycisk **Test Systemu** oraz ten plik README z formatowaniem |

**Zapamiętywanie ścieżek.** Wszystkie wybrane foldery i pliki są zapisywane lokalnie dla bieżącego użytkownika (`QSettings`) i przywracane po ponownym uruchomieniu aplikacji.

**Edytory plików TXT.** Pod każdym edytorem jest pole ze ścieżką, przycisk **Przeglądaj…** oraz **Wczytaj z pliku** i **Zapisz do pliku** (kodowanie UTF-8). Zawartość plików wczytuje się automatycznie przy starcie, a po wskazaniu innego pliku od razu. Aplikacja ostrzega przed utratą niezapisanych zmian, a przy starcie montażu sama zapisuje zmienione edytory.

Montaż działa w tle; postęp i komunikaty są widoczne w oknie. Podczas montażu można użyć przycisku **Przerwij generowanie** — bieżący etap zostanie bezpiecznie zatrzymany, niedokończony plik tymczasowy usunięty, a wcześniej gotowe filmy pozostaną bez zmian. **Wysyłanie na YouTube z aplikacji.** Zakładka **YouTube** domyślnie używa folderu **Gotowe filmy** (pole jest wtedy wyszarzone i podąża za zakładką Główna). Odznacz „Taki sam jak Gotowe filmy”, aby wskazać inny folder z plikami MP4 — wybór jest zapamiętywany. **Wyślij do YT** prosi o potwierdzenie i wysyła filmy jako prywatne z zaplanowaną publikacją (lub od razu publiczne, jeśli wybierzesz „Publikuj wszystkie od razu” w sekcji **PUBLIKACJA**) (wymaga skonfigurowanego klucza — patrz sekcja o YouTube API); „Tylko podgląd” pokazuje wyłącznie tytuły i terminy. **Przerwij wysyłanie** zatrzymuje wysyłkę po bieżącym fragmencie pliku (nie da się przerwać okna logowania Google w przeglądarce). Już wysłane filmy są pomijane. To samo można zrobić z konsoli (`python youtube_upload.py`).

### 🩺 Test Systemu

Przy każdym uruchomieniu aplikacja w tle sprawdza środowisko (moduł `system_check.py`). Gdy wszystko jest w porządku, zostajesz na zakładce **Główna**. Gdy czegoś brakuje, aplikacja przechodzi do zakładki **Pomoc** i pokazuje raport. To samo możesz wywołać w każdej chwili przyciskiem **Test Systemu**.

Raport pokazuje wersje i status (✔ / ✘) dla:

* **Python** (wymagany 3.8+),
* **bibliotek:** `moviepy<2.0.0`, `decorator==4.4.2`, `numpy`, `librosa`, `scipy`, `Pillow`, `PySide6>=6.5,<7`, bibliotek Google i `tzdata` — nie tylko ich obecność, ale też możliwość zaimportowania,
* **FFmpeg** (wersja i ścieżka), kodeku **libx264** oraz opcjonalnych kodeków sprzętowych (`h264_nvenc`, `h264_amf`, `h264_qsv` / `h264_videotoolbox`) — każdy jest sprawdzany próbnym kodowaniem, więc raport pokazuje tylko te, które naprawdę działają,
* **ImageMagick** (wersja i ścieżka).

Pod listą pojawia się sekcja **Do doinstalowania / naprawy** z gotowym poleceniem (np. `python -m pip install "moviepy<2.0.0"`) lub instrukcją instalacji programu dla Twojego systemu. Brak kodeku sprzętowego nie jest błędem — montaż użyje wtedy wolniejszego `libx264`.

Aplikacja uruchomi się nawet wtedy, gdy brakuje moviepy, FFmpeg lub ImageMagick, żeby pokazać, co trzeba doinstalować (przycisk montażu jest wtedy zablokowany do czasu naprawy). Jeśli brakuje samego PySide6, nie da się otworzyć okna głównego — raport pojawi się wtedy w prostym oknie awaryjnym (lub w konsoli) z poleceniem instalacji.

Aplikacja korzysta z tych samych wymagań systemowych co montaż konsolowy: FFmpeg oraz ImageMagick. Na macOS zainstaluj je poleceniem `brew install imagemagick ffmpeg`. Do dystrybucji potrzebne będą osobne buildy Windows i macOS.

## ⚙️ Konfiguracja Skryptu

Przed pierwszym uruchomieniem otwórz plik `ipsc_automato.py` w notatniku lub dowolnym edytorze kodu i dostosuj następujące ustawienia na samej górze pliku:

1. **ImageMagick:**
   Ścieżka do `magick.exe` jest zapisana w pliku **`settings.json`** (klucz `imagemagick_path`) w katalogu projektu — plik powstaje automatycznie przy pierwszym uruchomieniu (na Windows z dotychczasową ścieżką domyślną `C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe`) i jest lokalny dla komputera (ignorowany przez Git). Jeśli masz inną wersję lub folder, zmień wartość w pliku albo w aplikacji desktopowej: zakładka **Konfiguracja → ImageMagick (napisy) → Przeglądaj…**. Gdy ścieżka jest pusta lub wskazuje nieistniejący plik, skrypt szuka `magick`/`convert` w `PATH`. Zmiana działa od następnego montażu.
   ```json
   {
     "imagemagick_path": "C:\\Program Files\\ImageMagick-7.1.2-Q16-HDRI\\magick.exe"
   }
   ```

2. **Ścieżki do folderów roboczych:**
   Domyślnie są **względne** – liczone od folderu ze skryptem (`PROJECT_DIR`), więc projekt działa na Windows, macOS i Linuksie po skopiowaniu w dowolne miejsce:
   ```python
   FOLDER_WEJSCIOWY = os.path.join(PROJECT_DIR, "Surowe")      # Tu wrzucasz oryginalne nagrania (mp4/mov)
   FOLDER_WYJSCIOWY = os.path.join(PROJECT_DIR, "Gotowe")      # Tu pojawią się gotowe rolki
   FOLDER_MUZYKI = os.path.join(PROJECT_DIR, "Muzyka")         # Podkłady muzyczne (mp3)
   PLIK_Z_WYNIKAMI = os.path.join(PROJECT_DIR, "wyniki.txt")   # Wyniki zawodów
   PLIK_Z_TEKSTAMI = os.path.join(PROJECT_DIR, "teksty_wideo.txt")   # Teksty u góry wideo
   PLIK_Z_TORAMI = os.path.join(PROJECT_DIR, "mapowanie_torow.txt")       # Kolejność torów
   ```
   Możesz je podmienić na dowolne własne ścieżki.

   **Czcionka i kodek (automatycznie, `system_settings.py`):** Napisy z wynikami używają czcionki systemowej (Windows: `Arial-Bold`; pozostałe systemy: Arial Bold/Helvetica lub Liberation Sans/DejaVu Sans Bold, z czcionkami z folderu `Fonts` jako zapasowymi). Dodatkowe teksty u góry używają Mister Brush z `Fonts/mister-brush/MisterBrush.ttf`. Kodek wybierany jest automatycznie, na podstawie próbnego kodowania, w tej kolejności: `h264_nvenc` (NVIDIA), `h264_amf` (AMD), `h264_qsv` (Intel Quick Sync), na macOS `h264_videotoolbox`, a w ostateczności `libx264` (procesor; wolniejszy, ale działa wszędzie). Preset jest dobierany do kodeka (`fast`; dla AMD `speed`). Kodeki AMD (`h264_amf`) i Intel (`h264_qsv`) nie zostały jeszcze sprawdzone na prawdziwym sprzęcie (autor testował NVENC). Jeśli montaż z którymś z nich zawiedzie, uruchom **Test Systemu** w zakładce Pomoc i zgłoś problem; kodek sprzętowy nie jest wymagany, a aplikacja w razie potrzeby użyje `libx264`. Na macOS/Linuksie zainstaluj ImageMagick (`brew install imagemagick` / `sudo apt install imagemagick`).

3a. **Kolejność torów i orientacja filmu (`mapowanie_torow.txt`):**
   Obsługują to moduły `track_mapping.py` i `track_order.py`. Pliki z `FOLDER_WEJSCIOWY` są sortowane alfabetycznie, a **N-ta linia** pliku `mapowanie_torow.txt` opisuje **N-ty plik**. Przykład: jeśli plik jest drugi w sortowaniu, a druga linia w `mapowanie_torow.txt` to `1`, to jest to Tor 1 (i do niego zostaną dopasowane wyniki ze `wyniki.txt`).

   **Orientacja wszystkich filmów:** w aplikacji, w zakładce **Zawody** nad edytorem mapowania, wybierz **Wideo Pionowe** (1080×1920) lub **Wideo Poziome** (1920×1080). Wybór jest zapamiętywany i dotyczy każdego pliku, któremu nie przypisano orientacji w `mapowanie_torow.txt`. Przycisk **?** obok pokazuje podpowiedź (po najechaniu), a po kliknięciu przenosi do tej Pomocy. Jeśli chcesz, by pliki były różnego rodzaju, dopisz orientację w pliku:

   Format linii: `numer` albo `numer;orientacja`, gdzie orientacja to:
   * `V` — film **pionowy** 1080×1920,
   * `H` — film **poziomy** 1920×1080 (wielkość liter nie ma znaczenia, więc `h` i `H` działają tak samo),
   * brak litery — obowiązuje wybór **Wideo Pionowe / Poziome** z aplikacji (domyślnie pionowe; w skrypcie bez aplikacji zawsze pionowe).

   ```text
   2;V
   1;H
   3
   ```
   Powyższy przykład: pierwszy plik to Tor 2 (pionowy), drugi to Tor 1 (poziomy), trzeci to Tor 3 (orientacja z wyboru w aplikacji). Puste linie są pomijane. Jeśli pliku `mapowanie_torow.txt` brakuje lub ma za mało linii, numer toru wynika z pozycji w sortowaniu (1, 2, 3...), a film ma orientację z wyboru w aplikacji. Wybrana orientacja określa rozdzielczość całego montażu — napisy z wynikami i teksty u góry są układane na tym samym kadrze.

   > Uploader YouTube przyjmuje wyłącznie filmy pionowe lub kwadratowe (patrz niżej), więc filmy z orientacją `H` nie zostaną wysłane jako Shorts.

3b. **Wyniki zawodów (`wyniki.txt`):**
   Plik zawiera **skopiowaną stronę z wynikami zawodnika z PractiScore** (wyniki jednej osoby ze wszystkich stage'y danych zawodów). Parser (`czytaj_wyniki_z_pliku`) odczytuje dla każdego wiersza `Stage N`: miejsce, procent, punkty, Hit Factor i czas. Wartości są nakładane na film dla toru o numerze `N`.

   **Jak zdobyć te dane (PractiScore):**
   1. Wejdź na [practiscore.com](https://practiscore.com) i otwórz wyniki zawodów: z menu **Matches** / **Scores** wybierz swoje zawody (lub użyj linku do wyników od organizatora). Zawody muszą mieć opublikowane wyniki.
   2. Na stronie wyników zawodów znajdź swoje nazwisko (lista wyników ogólnych albo wyszukiwarka **Search**) i kliknij je. Otworzy się strona z wynikami zawodnika, z tabelą stage'ów (kolumny `Stage`, `#`, `%`, `Stg Pts`, `Pts`, `HF`, `Time`, `Div`, ...) oraz nazwą zawodów, datą i Twoim nazwiskiem u góry. Adres takiej strony ma postać:
      `https://practiscore.com/results/all/<id-zawodów>?q_individual=mmShooter_<id-zawodnika>`
      np. [https://practiscore.com/results/all/cd7e5150-2fb6-41fb-b7dd-4f08574509cc?q_individual=mmShooter_10148199](https://practiscore.com/results/all/cd7e5150-2fb6-41fb-b7dd-4f08574509cc?q_individual=mmShooter_10148199). Taki link możesz też zapisać lub wysłać dalej — otwiera od razu wyniki wybranego zawodnika.
   3. Zaznacz całą stronę (**Ctrl+A**), skopiuj (**Ctrl+C**) i wklej do pliku `wyniki.txt` lub do edytora w zakładce **Zawody** (**Ctrl+V**), po czym zapisz. Nie trzeba niczego przycinać — program sam znajduje wiersze `Stage N` i pomija menu, stopkę i resztę strony.
   4. Przy kolejnym zawodniku lub zawodach podmień całą zawartość pliku na nowo skopiowaną stronę.

   > Układ strony PractiScore może się zmienić; ważne, by w skopiowanym tekście były wiersze w formacie `Stage 1 Nazwa  miejsce  %  Stg Pts  Pts  HF  Time ...`. Nazwy stage'y mogą być dowolne (np. `Stage 3 Tor 3`), liczy się numer po słowie `Stage`.

   * Numer toru z `mapowanie_torow.txt` musi mieć odpowiadający wiersz `Stage N` w wynikach. Jeśli go brakuje, nagranie jest **pomijane** z komunikatem „brak wyników dla toru N”, a w aplikacji desktopowej ma status „pominięto”.
   * Jeśli pominięto wszystkie nagrania, aplikacja informuje, że wyniki nie zawierają przypisanych torów — sprawdź wtedy `mapowanie_torow.txt` i `wyniki.txt` w zakładce **Zawody**.
   * Plik wczytywany jest w UTF-8; w aplikacji desktopowej możesz go wkleić i zapisać bezpośrednio w zakładce **Zawody**.

3. **Dodatkowe teksty u góry wideo (`teksty_wideo.txt`):**
   Teksty i napisy z wynikami są dodawane tylko wtedy, gdy na zakładce **Główna** zaznaczono **Czy dodać napisy**. Gdy checkbox jest odznaczony, pliki `wyniki.txt` i `teksty_wideo.txt` mogą być puste lub nie wybrane — nie są brane pod uwagę przy napisach, a czas przebiegu z `wyniki.txt` (jeśli jest dostępny) nadal służy do przycięcia filmu.
   Każdy tekst wpisz w nawiasach kwadratowych, np. `[Klub ZSD]`. Plik może zawierać zero lub kilka wpisów, ale **maksymalnie 5** (kolejne są ignorowane). Nadmiarowe białe znaki w tekście są normalizowane, a puste nawiasy pomijane. Brak pliku nie przerywa montażu — filmy powstaną bez tekstów.
   * Teksty pojawiają się po kolei, neonowym cyjanem z ciemnym obrysem (czcionka Mister Brush z `Fonts/mister-brush/MisterBrush.ttf`), w górnej części wideo, z płynnym pojawianiem i znikaniem (0,4 s).
   * Każdy tekst wyświetla się min. 5 s (max 8 s), a przerwa między tekstami wynosi min. 2 s. Pierwszy tekst startuje po 1 s, a na końcu zostaje 1 s marginesu. Teksty są rozłożone równomiernie na całym filmie (bez długiej pustki na końcu).
   * Jeśli film jest za krótki, dodawane jest tyle tekstów, ile się zmieści; kolejne teksty z pliku nie są dodawane, a w logu pojawia się informacja ile użyto.
   * Podgląd planu (czas startu i końca każdego tekstu) trafia do dziennika w aplikacji desktopowej.

## 🚀 Jak używać skryptu?

1. **Przygotuj pliki wideo:** Po zawodach zrzuć nagrania z telefonu do `FOLDER_WEJSCIOWY`. 
   * *Skrypt sortuje pliki alfabetycznie po nazwie, a numer toru każdego z nich bierze z odpowiedniej linii w `mapowanie_torow.txt` (patrz punkt 3a). Bez `mapowanie_torow.txt` kolejne pliki to Tor 1, 2, 3, itd.*
2. **Przygotuj podkłady:** Upewnij się, że w `FOLDER_MUZYKI` masz chociaż jeden plik `.mp3`. Skrypt losuje muzykę dla każdego toru.
3. **Wklej wyniki:** Skopiuj stronę z wynikami zawodnika z PractiScore (jak to zrobić — patrz punkt 3b) i wklej do `wyniki.txt` lub w zakładce **Zawody**. Nie trzeba niczego przycinać.
4. **Uruchom skrypt:**
   Otwórz terminal w folderze ze skryptem i wpisz:
   ```bash
   python ipsc_automato.py
   ```
   Po każdym udanym renderze plik w `Gotowe` jest automatycznie przemianowywany przez `generate_names.py` na `YYYY-MM-DD - Nazwa zawodów - Tor X #bodycam.mp4`. Wymaga to poprawnie uzupełnionego `opis_zawodow.txt`.
5. Poczekaj na wygenerowanie i przemianowanie plików wideo w `FOLDER_WYJSCIOWY`.

## 📺 Publikowanie Shorts na YouTube

### Jak uzyskać klucz (dane dostępowe) do YouTube API

Skrypt używa **OAuth 2.0, a nie zwykłego klucza API** (tzw. *API key*). Sam klucz API pozwala tylko na odczyt publicznych danych — nie umożliwia przesyłania filmów ani czytania prywatnej kolejki kanału. Zamiast niego potrzebujesz pliku z danymi klienta OAuth (`youtube_client_secret.json`). Konfiguracja jest jednorazowa i bezpłatna:

1. Zaloguj się w [Google Cloud Console](https://console.cloud.google.com/) kontem Google, które zarządza docelowym kanałem YouTube.
2. Utwórz projekt: lista projektów u góry strony → **Nowy projekt** → nadaj nazwę (np. `yt-auto-cut`) → **Utwórz** i wybierz go.
3. Włącz API: **Interfejsy API i usługi → Biblioteka** → wyszukaj **YouTube Data API v3** → **Włącz**.
4. Skonfiguruj ekran zgody OAuth (**Interfejsy API i usługi → Ekran zgody OAuth**, w nowszym interfejsie: **Google Auth Platform → Branding / Audience**):
   * wpisz nazwę aplikacji i swój adres e-mail pomocy oraz kontaktowy,
   * typ użytkowników: **External** (zewnętrzni),
   * w [Audience](https://console.cloud.google.com/auth/audience), w sekcji **Test users**, dodaj konto Google, którym będziesz się logować.
5. Utwórz dane logowania: **Dane logowania → Utwórz dane logowania → Identyfikator klienta OAuth** → typ aplikacji **Aplikacja komputerowa** (*Desktop app*) → **Utwórz**.
6. W oknie z identyfikatorem kliknij **Pobierz JSON** i zapisz plik w katalogu projektu pod nazwą `youtube_client_secret.json`. Nie wpisuj tego pliku do repozytorium ani nikomu go nie przesyłaj.
7. Zaloguj się w przeglądarce: w aplikacji desktopowej kliknij **Wyślij do YT** w zakładce **YouTube** (najlepiej z opcją „Tylko podgląd”) albo uruchom `python ipsc_automato.py --yt`. Zatwierdź dwa uprawnienia: przesyłanie filmów (`youtube.upload`) i odczyt kanału (`youtube.readonly`). Przy ostrzeżeniu „Google nie zweryfikowało tej aplikacji” wybierz **Zaawansowane → Przejdź do… (niebezpieczne)** — to Twoja własna aplikacja. Po zalogowaniu powstanie lokalny `youtube_token.json`, dzięki czemu kolejne uruchomienia nie wymagają logowania.

Jeśli zobaczysz błąd **`Błąd 403: access_denied`**, sprawdź, czy konto jest dodane jako **Test user** (krok 4).

Nie używaj konta usługi — upload odbywa się w imieniu zalogowanego kanału. Pliki `youtube_client_secret.json`, `youtube_token.json` i `youtube_upload_state.json` (rejestr wysłanych filmów) są poufne i ignorowane przez Git — nie udostępniaj ich.

> Projekt w trybie **Testing** pozwala logować się tylko dodanym testerom, a autoryzacja wygasa po 7 dniach — wtedy usuń `youtube_token.json` i zaloguj się ponownie.

### Wysyłanie z aplikacji desktopowej (zakładka YouTube)

1. Wybierz folder z filmami: domyślnie jest to folder **Gotowe filmy** z zakładki Główna. Odznacz „Taki sam jak Gotowe filmy”, aby wskazać dowolny inny folder (np. gdy filmy przeniosłeś lub chcesz wysłać tylko część); wybór jest zapamiętywany.
2. Na górze zakładki, w sekcji **PUBLIKACJA**, wybierz sposób publikacji (ustawienia są zapamiętywane):
   - **Zaplanuj publikację** (domyślnie) — filmy trafiają na YouTube jako prywatne z terminem publikacji. Bez dodatkowych opcji obowiązuje harmonogram domyślny: pon–pt 7:30, sob–nd 10:00.
   - **Własne dni i godziny publikacji** — po zaznaczeniu tego checkboxa aktywują się kolumny Pon–Nd. Zaznacz dni, w których chcesz publikować, i ustaw dla każdego własną godzinę (`HH:mm`). Każdy film dostaje najbliższy wolny termin w jednym z zaznaczonych dni (jeden film na dzień). Trzeba zaznaczyć co najmniej jeden dzień.
   - **Publikuj wszystkie od razu** — filmy są wysyłane jako publiczne, bez terminu; opcje planowania są wtedy wyszarzone.
3. Zostaw zaznaczone **Tylko podgląd**, aby zobaczyć w dzienniku tytuły i terminy publikacji bez wysyłania. Gdy wszystko się zgadza, odznacz tę opcję.
4. Kliknij **Wyślij do YT** i potwierdź (okno wskazuje, czy filmy będą zaplanowane, czy opublikowane natychmiast). Postęp widać w dzienniku wysyłania.
5. **Przerwij wysyłanie** zatrzymuje wysyłkę po bieżącym fragmencie pliku; film przerwany w trakcie nie zostaje zapisany w rejestrze, więc kolejna próba wyśle go od nowa. Już wysłane filmy są pomijane (rejestr `youtube_upload_state.json`). Okna logowania Google w przeglądarce nie da się przerwać z aplikacji — zamknij je ręcznie.
6. Aplikacja nie zamknie się w trakcie wysyłania; najpierw ją przerwij.

Opcje sekcji **PUBLIKACJA** dotyczą tylko aplikacji desktopowej; uploader uruchamiany z konsoli zawsze używa harmonogramu domyślnego.

Przy braku `youtube_client_secret.json` lub bibliotek Google aplikacja pokaże komunikat błędu w dzienniku — patrz instrukcja uzyskania klucza powyżej oraz zakładka **Pomoc → Test Systemu**.

### Nazwy plików i publikacja

Uzupełnij `opis_zawodow.txt` nazwą i datą zawodów. Generator `generate_names.py` odczytuje nazwę z pola `Nazwa zawodów:` lub pierwszej niepustej linii, datę z `Match starts: August 09, 2026` albo `Data zawodów: 09.08.2026`, a numer toru z nazwy takiej jak `Gotowe_Stage_3.mp4`. Tytuł ma format `YYYY-MM-DD - Nazwa zawodów - Tor X #bodycam`, jest ograniczany do 100 znaków i służy również jako nazwa pliku MP4. Jest uruchamiany automatycznie po standardowym montażu; można go też wywołać ręcznie:

```bash
python generate_names.py Gotowe_Stage_1.mp4
```

Uploader `youtube_upload.py` jest uruchamiany z głównego skryptu wyłącznie po podaniu opcji `/yt` lub `--yt` (lub przyciskiem **Wyślij do YT** w aplikacji desktopowej). Odczytuje playlistę przesłanych filmów kanału, sprawdza zaplanowane publikacje i wybiera najbliższy wolny dzień: domyślnie poniedziałek–piątek o 7:30, sobota–niedziela o 10:00 czasu `Europe/Warsaw` (w aplikacji desktopowej można to zmienić w sekcji **PUBLIKACJA** albo publikować od razu). Uwzględnia terminy filmów zaplanowanych oraz dni publikacji filmów publicznych i niepublicznych. Opis YouTube zawiera tylko nazwę, datę, lokalizację, typ i poziom zawodów oraz hashtagi tworzone z tych pól — nie kopiuje całego pliku z opisem zawodów.

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
| `python generate_names.py Gotowe_Stage_1.mp4` | Ręczna zmiana nazwy jednego pliku |
| `python youtube_upload.py [plik\|folder] [--publish]` | Bezpośrednie wywołanie uploadera (domyślnie folder `Gotowe`); to samo robi zakładka **YouTube** w aplikacji |

`--publish` bez `/yt` lub `--yt` jest odrzucane. Każdy film musi być pionowy lub kwadratowy i trwać maksymalnie 3 minuty. Przy wielu plikach uploader planuje najwyżej jedną publikację dziennie na wybranym kanale. Jeśli OAuth zwróci więcej niż jeden kanał, ustaw zmienną środowiskową `YOUTUBE_CHANNEL_ID` na ID właściwego kanału. Google może wymagać weryfikacji projektu OAuth, zanim filmy przesyłane przez API będą mogły być publiczne.

## ⚠️ Najczęstsze problemy

*   **`ModuleNotFoundError: No module named 'google'`:** Brakuje bibliotek Google. Uruchom `python -m pip install -r requirements.txt` tym samym Pythonem, którym odpalasz skrypt.
*   **`Błąd 403: access_denied` przy logowaniu Google:** Projekt OAuth jest w trybie Testing, a Twoje konto nie jest testerem. Dodaj je w Google Cloud Console → Audience → Test users i spróbuj ponownie.
*   **`Brak pliku OAuth ... youtube_client_secret.json`:** Pobierz dane klienta OAuth typu „Aplikacja komputerowa” i zapisz je w katalogu projektu pod tą nazwą.
*   **`Nie można jednoznacznie wybrać kanału`:** Konto ma kilka kanałów — ustaw zmienną środowiskową `YOUTUBE_CHANNEL_ID`.
*   **Błąd daty/nazwy zawodów:** Uzupełnij `opis_zawodow.txt` (nazwa + `Match starts:`/`Data zawodów:`); numer toru musi występować w nazwie pliku (`Gotowe_Stage_3.mp4`).
*   **Film z toru został pominięty („brak wyników dla toru N”):** Pojawia się tylko przy zaznaczonym **Czy dodać napisy**. W `wyniki.txt` nie ma wiersza `Stage N` dla numeru toru przypisanego w `mapowanie_torow.txt`. Sprawdź oba pliki w zakładce **Zawody** lub odznacz checkbox na zakładce **Główna**.
*   **Film wyszedł w złej orientacji:** W zakładce **Zawody** wybierz **Wideo Pionowe** lub **Wideo Poziome** (dotyczy wszystkich plików bez litery w `mapowanie_torow.txt`) albo dopisz w `mapowanie_torow.txt` po numerze toru `;H` (poziomy 1920×1080) lub `;V` (pionowy 1080×1920), np. `3;H` — ta litera ma pierwszeństwo.
*   **Zakładka YouTube: „Brak pliku OAuth” lub „Brak bibliotek Google API”:** Zapisz `youtube_client_secret.json` w katalogu projektu (instrukcja wyżej) i zainstaluj zależności `python -m pip install -r requirements.txt`.
*   **Zakładka YouTube: „Short musi mieć format pionowy lub kwadratowy”:** Film wybrany do wysyłki jest poziomy lub dłuższy niż 3 minuty — wygeneruj go ponownie jako **Wideo Pionowe**.
*   **Aplikacja po starcie otwiera zakładkę Pomoc:** Test systemu wykrył braki — wykonaj polecenia z sekcji **Do doinstalowania / naprawy** i uruchom aplikację ponownie.
*   **Błąd `[WinError 2] Nie można odnaleźć określonego pliku` lub problem z `None`:** MoviePy nie może znaleźć programu ImageMagick. Upewnij się, że ścieżka do `magick.exe` (lub `convert.exe`) w `settings.json` (lub w zakładce **Konfiguracja** aplikacji) jest w 100% poprawna dla Twojego komputera.
*   **Błąd `ModuleNotFoundError: No module named 'moviepy.editor'`:** Masz zainstalowaną nową wersję MoviePy (2.0+). Wpisz w konsoli `pip uninstall moviepy` a następnie `pip install "moviepy<2.0.0"`.
*   **Błąd `must be real number, not NoneType` przy zapisie wideo:** Masz zbyt nową bibliotekę `decorator`. Użyj `pip install "decorator==4.4.2"`.
*   **Błąd `Accessing time t=... with clip duration=...` dla muzyki:** Skrypt zapętla muzykę, więc krótki utwór nie powinien go wywołać; sprawdź, czy plik `.mp3` nie jest uszkodzony.
*   **Pliki `*TEMP_MPY_*`:** Resztki nieudanych renderów. Skrypt je pomija, możesz je bezpiecznie usunąć.