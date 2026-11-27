# Automatyzacja Montażu Wideo IPSC 🔫🎬

Ten program w Pythonie automatyzuje montaż nagrań wideo z zawodów IPSC — w aplikacji okienkowej (Windows i macOS) albo z terminala. Sam znajduje w dźwięku sygnał timera i przycina każde nagranie do przebiegu (start timera i czas z wyników), podkłada zapętloną muzykę z efektem fade-out, zmienia format na pionowy 1080×1920 lub poziomy 1920×1080 i dodaje planszę z Twoimi wynikami (czas, a gdy są w wynikach — miejsce, punkty i Hit Factor), teksty wideo i logo. Tryb **Tylko przycięcie** szybko przycina nagrania bez żadnych dodatków. Gotowe filmy możesz najpierw obejrzeć, a potem opublikować na YouTube lub przez Buffer — montaż nigdy nie publikuje niczego sam.

Jeśli komputer ma obsługiwaną kartę graficzną (NVIDIA, AMD lub Intel), renderowanie korzysta ze sprzętowego kodera i jest bardzo szybkie. Bez niej montaż nadal działa, ale na procesorze (wolniej).

## 🛠️ Wymagania wstępne (Oprogramowanie)

Aby skrypt działał poprawnie, musisz zainstalować w systemie Windows następujące elementy:

1. **Python (3.8 lub nowszy):** Pamiętaj, aby podczas instalacji zaznaczyć pole _„Add Python to PATH”_.
2. **Napisy nie wymagają dodatkowych programów** — wyniki i teksty wideo rysuje biblioteka Pillow (instalowana z `requirements.txt`). ImageMagick nie jest już potrzebny.
3. _(Opcjonalnie)_ **Karta graficzna z kodowaniem sprzętowym H.264** dla szybszego renderowania — **NVIDIA** (`h264_nvenc`, np. RTX 4060), **AMD** (`h264_amf`) lub grafika **Intel** (`h264_qsv`). Karta nie jest wymagana: bez niej aplikacja automatycznie użyje `libx264` (procesor), co jest wolniejsze, ale działa na każdym komputerze. Do kodowania sprzętowego potrzebne są aktualne sterowniki oraz pełna wersja FFmpeg (np. z [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)).

## 🍎 Konfiguracja pod macOS

Projekt działa na macOS (kodek `h264_videotoolbox` lub `libx264`; NVIDIA nie jest potrzebna). Poniższe komendy wykonaj w Terminalu.

1. **Homebrew** (jeśli go nie masz) — instrukcja na [brew.sh](https://brew.sh/).
2. **Python i FFmpeg:**
   ```bash
   brew install python ffmpeg
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

Uwagi: plansza wyników używa systemowej czcionki Arial Bold (jest w macOS), a gdy jej brak — czcionki dołączonej do projektu. Brak uprawnień do folderów rozwiąż w **Ustawienia systemowe → Prywatność i ochrona**.

## 📦 Instalacja bibliotek Pythona

Otwórz wiersz poleceń (CMD) w folderze, w którym znajduje się plik `ipsc_automato.py` oraz `requirements.txt`, a następnie uruchom komendę:

```bash
pip install -r requirements.txt
```

_Uwaga: Wymagane są specyficzne, starsze wersje bibliotek (`moviepy<2.0.0` oraz `decorator==4.4.2`), aby zapobiec błędom z importem modułu editor oraz błędowi `must be real number, not NoneType` przy renderowaniu._

`requirements.txt` zawiera też biblioteki Google (`google-auth`, `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`) potrzebne do opcji `--yt`. Instaluj je tym samym interpreterem, którym uruchamiasz skrypt: `python -m pip install -r requirements.txt`.

## 🖥️ Aplikacja desktopowa (Windows i macOS)

Po zainstalowaniu zależności uruchom aplikację poleceniem:

```bash
python desktop_app.py
```

Interfejs ma motyw **jasny**, **ciemny** albo **jak w systemie** (domyślnie; przełącza się razem z Windows/macOS — wybór w **Ustawienia → Wygląd**). Używa czcionek systemu i własnych ikon, więc wygląda tak samo na Windows i macOS. Po lewej jest pasek z krokami pracy; przy każdym kroku pojawia się ✓ (gotowe) albo ⚠ (coś do poprawy — opis po najechaniu myszką):

| Krok | Zawartość |
| ---- | --------- |
| **1. Zawody** | Foldery **Nagrania źródłowe** i **Gotowe filmy** oraz formularz **Opis zawodów**: nazwa, data (kalendarz), miejsce, typ i poziom, z podglądem tytułu i nazwy pliku. Pola formularza są zapisywane na początku `opis_zawodow.txt`, a reszta tekstu (np. wklejony opis z Practiscore) zostaje bez zmian. **Pokaż pełny tekst opisu** odsłania cały plik do ręcznej edycji |
| **2. Wyniki** | Edytor wyników (`wyniki.txt`) z wyborem formatu **Practiscore / ECM / Trening** i tabelą **Odczytane wyniki** aktualizowaną na bieżąco. Jeśli wklejony tekst pasuje do innego formatu niż wybrany, format przełącza się sam |
| **3. Montaż** | **Rodzaj montażu** (pełny / tylko przycięcie, wyniki, muzyka, nadpisywanie, domyślna orientacja), tabela **Plan montażu**: plik → tor → H/V → czas → start timera → co się stanie (montaż, brak wyniku, film już istnieje). Numer toru zmienisz dwukrotnym kliknięciem albo przyciskami **W górę / W dół**, orientację listą w wierszu — zmiany zapisują się do `mapowanie_torow.txt`. **Wykryj start timera** analizuje dźwięk nagrań i pokazuje, od której sekundy zacznie się film (albo że timera nie wykryto). Dalej przycisk **Rozpocznij montaż (N)**, postęp z czasem do końca i dziennik |
| **4. Publikacja** | Dwie karty. **YouTube:** Sekcja **PUBLIKACJA** (własne dni tygodnia i godziny albo „Publikuj wszystkie od razu”), wybór folderu z filmami, przyciski **Wyślij do YT** / **Przerwij wysyłanie**, opcja „Tylko podgląd” i dziennik wysyłania **Buffer i Cloudflare:** Checkboxy platform **Facebook**, **Instagram**, **X/Twitter** (dla Facebooka i Instagrama lista typu posta: **reel**, **post**, **story**, domyślnie **reel**), osobne pola **Opis na Facebook**, **Opis na Instagram** (licznik hashtagów, limit 5) i **Opis na X/Twitter** (licznik znaków, limit 280), edytor **Lista filmów Buffer** (`buffer.txt`) z przyciskami **Wczytaj z pliku** / **Zapisz do pliku** oraz wyborem pliku (ścieżka jest zapamiętywana), sekcja **PLANOWANIE SZKICÓW** (własne dni i godziny) i przycisk **Utwórz szkice w Buffer** — tworzy wyłącznie szkice (bez publikacji) w pierwszych wolnych terminach. Każdy adres z listy (np. publiczny link Cloudflare R2) jest dołączany do posta jako plik wideo (Buffer pobiera go z tego adresu), a treść posta to sam opis, bez linku. Wysłane pary platforma + film są pomijane (rejestr `buffer_upload_state.json`). Przycisk **Wyślij do CloudFlare** pod edytorem: wysyła pliki MP4 z wybranego folderu (domyślnie **Gotowe**, zmiana przyciskiem **Przeglądaj…**) do bucketa Cloudflare R2 i na bieżąco dopisuje ich publiczne linki do `buffer.txt` (pliki o już istniejącej nazwie w buckecie nie są wysyłane ponownie) |
| **Ustawienia** | Folder z muzyką, opcjonalne **Logo** (plik PNG/JPG/BMP/GIF/WEBP — pojawia się w prawym górnym rogu filmu, automatycznie zmniejszane do maks. 200×200 px z zachowaniem proporcji; puste pole = bez logo; moduł `logo_overlay.py`), checkbox **Czy dodać teksty wideo** oraz edytor pliku **Teksty wideo** (`teksty_wideo.txt`), edytor **Mapowanie torów (zaawansowane)** (`mapowanie_torow.txt`, zmienia się sam przy edycji tabeli planu), sekcja **Klucze usług** (Buffer API i Cloudflare R2 — zapis w `settings.json`) oraz **Wygląd** (motyw) |
| **Pomoc** | Przycisk **Test systemu**, ten plik README z formatowaniem i linki do profili autora |

**Zapamiętywanie ścieżek.** Wszystkie wybrane foldery i pliki są zapisywane lokalnie dla bieżącego użytkownika (`QSettings`) i przywracane po ponownym uruchomieniu aplikacji.

Strony kroków przewijają się pionowo, gdy ich zawartość nie mieści się w oknie.

**Edytory plików TXT.** Pod każdym edytorem jest pole ze ścieżką, przycisk **Przeglądaj…** i **Wczytaj ponownie** (kodowanie UTF-8). Zmiany zapisują się same chwilę po zakończeniu pisania (status pod edytorem pokazuje godzinę zapisu), więc nie ma pytań o niezapisane zmiany. Zawartość plików wczytuje się automatycznie przy starcie, a po wskazaniu innego pliku od razu.

**Błędy i powiadomienia.** Nieprawidłowa ścieżka jest podświetlana na czerwono z opisem pod polem (aplikacja sama przechodzi do właściwej zakładki), zamiast wyskakującego okienka. Po zakończeniu montażu, gdy okno nie jest na wierzchu, pojawia się powiadomienie systemowe. Gdy coś pójdzie nie tak, dziennik rozwija się sam.

**Skróty klawiszowe.** **Ctrl+Enter** (na Macu **⌘+Enter**) — rozpocznij montaż; **Ctrl+S** (**⌘+S**) — zapisz od razu wszystkie edytory. Autor i linki do jego profili są na dole kroku **Pomoc**.

Montaż działa w tle; postęp i komunikaty są widoczne w oknie. Podczas montażu można użyć przycisku **Przerwij** — bieżący etap zostanie bezpiecznie zatrzymany, niedokończony plik tymczasowy usunięty, a wcześniej gotowe filmy pozostaną bez zmian. **Wysyłanie na YouTube z aplikacji.** Zakładka **YouTube** domyślnie używa folderu **Gotowe filmy** (pole jest wtedy wyszarzone i podąża za zakładką Główna). Odznacz „Taki sam jak Gotowe filmy”, aby wskazać inny folder z plikami MP4 — wybór jest zapamiętywany. **Wyślij do YT** prosi o potwierdzenie i wysyła filmy jako prywatne z zaplanowaną publikacją (lub od razu publiczne, jeśli wybierzesz „Publikuj wszystkie od razu” w sekcji **PUBLIKACJA**) (wymaga skonfigurowanego klucza — patrz sekcja o YouTube API); „Tylko podgląd” pokazuje wyłącznie tytuły i terminy. **Przerwij wysyłanie** zatrzymuje wysyłkę po bieżącym fragmencie pliku (nie da się przerwać okna logowania Google w przeglądarce). Już wysłane filmy są pomijane. To samo można zrobić z konsoli (`python youtube_upload.py`).

### 🩺 Test Systemu

Przy każdym uruchomieniu aplikacja w tle sprawdza środowisko (moduł `system_check.py`). Gdy wszystko jest w porządku, zostajesz na kroku **1. Zawody**. Gdy czegoś brakuje, aplikacja przechodzi do kroku **Pomoc** i pokazuje raport. To samo możesz wywołać w każdej chwili przyciskiem **Test Systemu**.

Raport pokazuje wersje i status (✔ / ✘) dla:

- **Python** (wymagany 3.8+),
- **bibliotek:** `moviepy<2.0.0`, `decorator==4.4.2`, `numpy`, `scipy`, `Pillow`, `PySide6>=6.5,<7`, bibliotek Google, `tzdata` i `boto3` — nie tylko ich obecność, ale też możliwość zaimportowania,
- **FFmpeg** (wersja i ścieżka), kodeku **libx264** oraz opcjonalnych kodeków sprzętowych (`h264_nvenc`, `h264_amf`, `h264_qsv` / `h264_videotoolbox`) — każdy jest sprawdzany próbnym kodowaniem, więc raport pokazuje tylko te, które naprawdę działają.

Pod listą pojawia się sekcja **Do doinstalowania / naprawy** z gotowym poleceniem (np. `python -m pip install "moviepy<2.0.0"`) lub instrukcją instalacji programu dla Twojego systemu. Brak kodeku sprzętowego nie jest błędem — montaż użyje wtedy wolniejszego `libx264`.

Aplikacja uruchomi się nawet wtedy, gdy brakuje moviepy lub FFmpeg, żeby pokazać, co trzeba doinstalować (przycisk montażu jest wtedy zablokowany do czasu naprawy). Jeśli brakuje samego PySide6, nie da się otworzyć okna głównego — raport pojawi się wtedy w prostym oknie awaryjnym (lub w konsoli) z poleceniem instalacji.

Aplikacja korzysta z tych samych wymagań systemowych co montaż konsolowy: wystarczy FFmpeg (na macOS `brew install ffmpeg`). Do dystrybucji potrzebne będą osobne buildy Windows i macOS.

## ⚙️ Konfiguracja Skryptu

Przed pierwszym uruchomieniem otwórz plik `ipsc_automato.py` w notatniku lub dowolnym edytorze kodu i dostosuj następujące ustawienia na samej górze pliku:

1. **Plik `settings.json`:** powstaje automatycznie przy pierwszym uruchomieniu w katalogu projektu, z pustymi kluczami Buffer i Cloudflare do uzupełnienia. Jest lokalny dla komputera (ignorowany przez Git). Dawny klucz `imagemagick_path` nie jest już używany i można go usunąć.

2. **Klucz Buffer API (zakładka Buffer):**
   Token do Buffer API wpisz w pliku **`settings.json`** w katalogu projektu, pod kluczem `BUFFER_API`. Plik jest lokalny dla komputera (ignorowany przez Git). Token możesz wpisać w aplikacji (**Konfiguracja → Klucze usług**) albo w notatniku. Informacje o uzyskaniu tokenu znajdziesz w dokumentacji Buffer API: https://developers.buffer.com/. Bez tego wpisu Buffer nie utworzy szkiców.

   ```json
   {
     "BUFFER_API": "TWOJ_TOKEN_BUFFER"
   }
   ```

2a. **Cloudflare R2 (wysyłka filmów z zakładki Buffer):**
   W pliku **`settings.json`** uzupełnij klucze: `CLOUDFLARE_API` (endpoint S3 z nazwą bucketa, np. `https://<ID_KONTA>.r2.cloudflarestorage.com/buffer-api`), `CLOUDFLARE_ACCESS_KEY_ID` i `CLOUDFLARE_SECRET_ACCESS_KEY` (klucze R2 API Token) oraz `CLOUDFLARE_PUBLIC_URL` — publiczny adres bucketa, np. `https://pub-xxxx.r2.dev`. Publiczny adres włączysz w Cloudflare: **R2 → buffer-api → Settings → Public access** (albo podepnij własną domenę). Endpoint S3 **nie** nadaje się jako `CLOUDFLARE_PUBLIC_URL`, bo nie udostępnia plików publicznie.

   ```json
   {
     "CLOUDFLARE_API": "https://<ID_KONTA>.r2.cloudflarestorage.com/buffer-api",
     "CLOUDFLARE_ACCESS_KEY_ID": "TWOJ_ACCESS_KEY_ID",
     "CLOUDFLARE_SECRET_ACCESS_KEY": "TWOJ_SECRET_ACCESS_KEY",
     "CLOUDFLARE_PUBLIC_URL": "https://pub-xxxx.r2.dev"
   }
   ```

3. **Ścieżki do folderów roboczych:**
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

   **Czcionka i kodek (automatycznie, `system_settings.py`):** Napisy rysuje Pillow (`text_render.py`), więc wyglądają tak samo na Windows i macOS. Plansza wyników używa systemowej czcionki Arial Bold (Windows i macOS; na Linuksie Liberation Sans/DejaVu Sans Bold), a gdy jej brak — Chakra Petch z folderu `Fonts`. Dodatkowe teksty u góry używają Mister Brush z `Fonts/mister-brush/MisterBrush.ttf`. Kodek wybierany jest automatycznie, na podstawie próbnego kodowania, w tej kolejności: `h264_nvenc` (NVIDIA), `h264_amf` (AMD), `h264_qsv` (Intel Quick Sync), na macOS `h264_videotoolbox`, a w ostateczności `libx264` (procesor; wolniejszy, ale działa wszędzie). Preset jest dobierany do kodeka (`fast`; dla AMD `speed`). Kodeki AMD (`h264_amf`) i Intel (`h264_qsv`) nie zostały jeszcze sprawdzone na prawdziwym sprzęcie (autor testował NVENC). Jeśli montaż z którymś z nich zawiedzie, uruchom **Test Systemu** w zakładce Pomoc i zgłoś problem; kodek sprzętowy nie jest wymagany, a aplikacja w razie potrzeby użyje `libx264`.

3a. **Kolejność torów i orientacja filmu (`mapowanie_torow.txt`):**
Obsługują to moduły `track_mapping.py` i `track_order.py`. Pliki z `FOLDER_WEJSCIOWY` są sortowane alfabetycznie, a **N-ta linia** pliku `mapowanie_torow.txt` opisuje **N-ty plik**. Przykład: jeśli plik jest drugi w sortowaniu, a druga linia w `mapowanie_torow.txt` to `1`, to jest to Tor 1 (i do niego zostaną dopasowane wyniki ze `wyniki.txt`).

**Orientacja wszystkich filmów:** w aplikacji, w kroku **Montaż** (sekcja **Rodzaj montażu**) wybierz **Wideo Pionowe** (1080×1920) lub **Wideo Poziome** (1920×1080). Wybór jest zapamiętywany i dotyczy każdego pliku, któremu nie przypisano orientacji w `mapowanie_torow.txt`. Przycisk **?** obok pokazuje podpowiedź (po najechaniu), a po kliknięciu przenosi do tej Pomocy. Jeśli chcesz, by pliki były różnego rodzaju, dopisz orientację w pliku:

Format linii: `numer` albo `numer;orientacja`, gdzie orientacja to:

- `V` — film **pionowy** 1080×1920,
- `H` — film **poziomy** 1920×1080 (wielkość liter nie ma znaczenia, więc `h` i `H` działają tak samo),
- brak litery — obowiązuje wybór **Wideo Pionowe / Poziome** z aplikacji (domyślnie pionowe; w skrypcie bez aplikacji zawsze pionowe).

```text
2;V
1;H
3
```

Powyższy przykład: pierwszy plik to Tor 2 (pionowy), drugi to Tor 1 (poziomy), trzeci to Tor 3 (orientacja z wyboru w aplikacji). Puste linie są pomijane. Jeśli pliku `mapowanie_torow.txt` brakuje lub ma za mało linii, numer toru wynika z pozycji w sortowaniu (1, 2, 3...), a film ma orientację z wyboru w aplikacji. Wybrana orientacja określa rozdzielczość całego montażu — napisy z wynikami i teksty u góry są układane na tym samym kadrze.

> Filmy z orientacją `H` (1920x1080) są wysyłane na YouTube jako zwykłe wideo (nie Shorts); filmy pionowe są traktowane jako Shorts.

3b. **Wyniki zawodów (`wyniki.txt`):**
Plik zawiera **skopiowaną stronę z wynikami zawodnika z PractiScore** (wyniki jednej osoby ze wszystkich stage'y danych zawodów). Parser (`czytaj_wyniki_z_pliku`) odczytuje dla każdego wiersza `Stage N`: miejsce, procent, punkty, Hit Factor i czas. Wartości są nakładane na film dla toru o numerze `N`.

**Jak zdobyć te dane (PractiScore):**

1.  Wejdź na [practiscore.com](https://practiscore.com) i otwórz wyniki zawodów: z menu **Matches** / **Scores** wybierz swoje zawody (lub użyj linku do wyników od organizatora). Zawody muszą mieć opublikowane wyniki.
2.  Na stronie wyników zawodów znajdź swoje nazwisko (lista wyników ogólnych albo wyszukiwarka **Search**) i kliknij je. Otworzy się strona z wynikami zawodnika, z tabelą stage'ów (kolumny `Stage`, `#`, `%`, `Stg Pts`, `Pts`, `HF`, `Time`, `Div`, ...) oraz nazwą zawodów, datą i Twoim nazwiskiem u góry. Adres takiej strony ma postać:
    `https://practiscore.com/results/all/<id-zawodów>?q_individual=mmShooter_<id-zawodnika>`
    np. [https://practiscore.com/results/all/cd7e5150-2fb6-41fb-b7dd-4f08574509cc?q_individual=mmShooter_10148199](https://practiscore.com/results/all/cd7e5150-2fb6-41fb-b7dd-4f08574509cc?q_individual=mmShooter_10148199). Taki link możesz też zapisać lub wysłać dalej — otwiera od razu wyniki wybranego zawodnika.
3.  Zaznacz całą stronę (**Ctrl+A**), skopiuj (**Ctrl+C**) i wklej do pliku `wyniki.txt` lub do edytora w kroku **Wyniki** (**Ctrl+V**), po czym zapisz. Nie trzeba niczego przycinać — program sam znajduje wiersze `Stage N` i pomija menu, stopkę i resztę strony.
4.  Przy kolejnym zawodniku lub zawodach podmień całą zawartość pliku na nowo skopiowaną stronę.

> Układ strony PractiScore może się zmienić; ważne, by w skopiowanym tekście były wiersze w formacie `Stage 1 Nazwa  miejsce  %  Stg Pts  Pts  HF  Time ...`. Nazwy stage'y mogą być dowolne (np. `Stage 3 Tor 3`), liczy się numer po słowie `Stage`.

- Numer toru z `mapowanie_torow.txt` musi mieć odpowiadający wiersz `Stage N` w wynikach. Jeśli go brakuje, nagranie jest **pomijane** z komunikatem „brak wyników dla toru N”, a w aplikacji desktopowej ma status „pominięto”.
- Jeśli pominięto wszystkie nagrania, aplikacja informuje, że wyniki nie zawierają przypisanych torów — sprawdź wtedy tabelę planu w kroku **Montaż** i odczytane wyniki w kroku **Wyniki**.
- Plik wczytywany jest w UTF-8; w aplikacji desktopowej możesz go wkleić i zapisać bezpośrednio w kroku **Wyniki** — tabela pod edytorem od razu pokaże odczytane tory.
- **Format wyników (krok Wyniki):** nad wyborem pliku wybierz jedną z opcji — **Practiscore** (domyślnie, wyniki wklejone ze strony PractiScore), **ECM** (wiersze `Stage 01  4.3290  40  8 0 0 0 0 0  9.24`, czas z ostatniej kolumny) lub **Trening** (ręcznie wpisane wiersze `numer toru; czas`, np. `1; 23` lub `3;20,81`). Wybór jest zapamiętywany. Plansza na filmie pokazuje tylko pola, które są w wynikach: przy Treningu jedną linię `STAGE 3 | Czas: 20.81s`, przy ECM czas, HF i punkty (bez miejsca), a przy Practiscore komplet.

3. **Dodatkowe teksty u góry wideo (`teksty_wideo.txt`):**
   Checkbox **Czy dodać wyniki** steruje wyłącznie planszą z wynikami na dole filmu. Osobny checkbox **Czy dodać teksty wideo** w **Ustawieniach** (domyślnie zaznaczony, wybór jest zapamiętywany) steruje tekstami z `teksty_wideo.txt`, niezależnie od wyników. Pusty plik (lub plik bez wpisów w nawiasach kwadratowych) nie dodaje tekstów. Czas przebiegu z `wyniki.txt` nadal służy do przycięcia filmu, jeśli jest dostępny.
   Każdy tekst wpisz w nawiasach kwadratowych, np. `[Klub ZSD]`. Plik może zawierać zero lub kilka wpisów, ale **maksymalnie 5** (kolejne są ignorowane). Nadmiarowe białe znaki w tekście są normalizowane, a puste nawiasy pomijane. W aplikacji zaznaczenie tekstów wymaga istniejącego pliku; po odznaczeniu plik nie jest wymagany.
   - Teksty pojawiają się po kolei, neonowym cyjanem z ciemnym obrysem (czcionka Mister Brush z `Fonts/mister-brush/MisterBrush.ttf`), w górnej części wideo, z płynnym pojawianiem i znikaniem (0,4 s).
   - Każdy tekst wyświetla się min. 5 s (max 8 s), a przerwa między tekstami wynosi min. 2 s. Pierwszy tekst startuje po 1 s, a na końcu zostaje 1 s marginesu. Teksty są rozłożone równomiernie na całym filmie (bez długiej pustki na końcu).
   - Jeśli film jest za krótki, dodawane jest tyle tekstów, ile się zmieści; kolejne teksty z pliku nie są dodawane, a w logu pojawia się informacja ile użyto.
   - Podgląd planu (czas startu i końca każdego tekstu) trafia do dziennika w aplikacji desktopowej.

## 🚀 Jak używać skryptu?

1. **Przygotuj pliki wideo:** Po zawodach zrzuć nagrania z telefonu do `FOLDER_WEJSCIOWY`.
   - _Skrypt sortuje pliki alfabetycznie po nazwie, a numer toru każdego z nich bierze z odpowiedniej linii w `mapowanie_torow.txt` (patrz punkt 3a). Bez `mapowanie_torow.txt` kolejne pliki to Tor 1, 2, 3, itd._
2. **Przygotuj podkłady:** Upewnij się, że w `FOLDER_MUZYKI` masz chociaż jeden plik `.mp3`. Skrypt losuje muzykę dla każdego toru.
3. **Wklej wyniki:** Skopiuj stronę z wynikami zawodnika z PractiScore (jak to zrobić — patrz punkt 3b) i wklej do `wyniki.txt` lub w kroku **Wyniki**. Nie trzeba niczego przycinać.
4. **Uruchom skrypt:**
   Otwórz terminal w folderze ze skryptem i wpisz:
   ```bash
   python ipsc_automato.py
   ```
   Gotowy film od razu dostaje nazwę `YYYY-MM-DD - Nazwa zawodów - Tor X #bodycam.mp4` (`generate_names.py`). Opis zawodów jest sprawdzany przed montażem: jeśli `opis_zawodow.txt` nie ma nazwy lub daty, montaż i tak się wykona, a filmy zachowają nazwy techniczne `Gotowe_Stage_X.mp4` (w dzienniku pojawi się ostrzeżenie).
5. Poczekaj na wygenerowanie plików wideo w `FOLDER_WYJSCIOWY`.

### ✂️ Montaż bez publikacji i tryb „Tylko przycięcie”

Montaż nigdy niczego nie publikuje — najpierw możesz obejrzeć gotowe filmy, a wysłać je później (krok **Publikacja** albo komenda `automato.py publish`).

- **Tylko przycięcie** — film jest przycinany do przebiegu (start timera i czas z wyników), bez muzyki, napisów, logo i zmiany rozdzielczości. Obraz jest kopiowany bez ponownego kodowania, więc trwa to kilka sekund zamiast minut. Start może wypaść ułamek sekundy wcześniej (na najbliższej klatce kluczowej). W tym trybie nagrania bez wyniku nie są pomijane — zostają w całości.
- **Dodaj muzykę** — można wyłączyć podkład muzyczny także w pełnym montażu.
- **Nadpisuj gotowe filmy** — domyślnie wyłączone: nagranie, którego gotowy film jest już w folderze wyjściowym, jest pomijane (ponowne uruchomienie montuje tylko brakujące filmy). Zaznacz, aby zmontować wszystko od nowa.

### 💻 Praca z terminala (`automato.py`)

Wszystko, co robi aplikacja, można zrobić z terminala na Windows i macOS. Montaż i publikacja to osobne komendy:

```bash
python automato.py check                       # test systemu (biblioteki, FFmpeg, kodeki)
python automato.py plan                        # co zostanie zmontowane: tor, czas, decyzja, nazwa pliku
python automato.py plan --detect-timer --json  # z analizą timera, wynik dla skryptów
python automato.py render                      # pełny montaż (bez publikacji)
python automato.py render --trim-only          # tylko przycięcie
python automato.py render --no-music --no-texts --overwrite
python automato.py publish youtube             # podgląd kolejki YouTube (nic nie wysyła)
python automato.py publish youtube --publish --schedule "pon=07:30,sob=10:00"
python automato.py publish cloudflare
python automato.py publish buffer --platforms facebook,instagram
```

Ścieżki i ustawienia projektu podajesz flagami (`--input`, `--output`, `--music`, `--results`, `--results-mode practiscore|ecm|trening`, `--tracks`, `--texts`, `--description`, `--orientation V|H`, `--logo`, `--no-results`); bez nich używane są domyślne pliki z folderu projektu. `python automato.py KOMENDA --help` pokazuje wszystkie opcje. Ctrl+C przerywa montaż bezpiecznie po bieżącym etapie (drugie Ctrl+C kończy natychmiast). Kody wyjścia: `0` sukces, `1` błędy, `2` złe argumenty, `130` przerwano. Dotychczasowe `python ipsc_automato.py [--yt] [--publish] …` działa bez zmian.

## 📺 Publikowanie Shorts na YouTube

### Jak uzyskać klucz (dane dostępowe) do YouTube API

Skrypt używa **OAuth 2.0, a nie zwykłego klucza API** (tzw. _API key_). Sam klucz API pozwala tylko na odczyt publicznych danych — nie umożliwia przesyłania filmów ani czytania prywatnej kolejki kanału. Zamiast niego potrzebujesz pliku z danymi klienta OAuth (`youtube_client_secret.json`). Konfiguracja jest jednorazowa i bezpłatna:

1. Zaloguj się w [Google Cloud Console](https://console.cloud.google.com/) kontem Google, które zarządza docelowym kanałem YouTube.
2. Utwórz projekt: lista projektów u góry strony → **Nowy projekt** → nadaj nazwę (np. `yt-auto-cut`) → **Utwórz** i wybierz go.
3. Włącz API: **Interfejsy API i usługi → Biblioteka** → wyszukaj **YouTube Data API v3** → **Włącz**.
4. Skonfiguruj ekran zgody OAuth (**Interfejsy API i usługi → Ekran zgody OAuth**, w nowszym interfejsie: **Google Auth Platform → Branding / Audience**):
   - wpisz nazwę aplikacji i swój adres e-mail pomocy oraz kontaktowy,
   - typ użytkowników: **External** (zewnętrzni),
   - w [Audience](https://console.cloud.google.com/auth/audience), w sekcji **Test users**, dodaj konto Google, którym będziesz się logować.
5. Utwórz dane logowania: **Dane logowania → Utwórz dane logowania → Identyfikator klienta OAuth** → typ aplikacji **Aplikacja komputerowa** (_Desktop app_) → **Utwórz**.
6. W oknie z identyfikatorem kliknij **Pobierz JSON** i zapisz plik w katalogu projektu pod nazwą `youtube_client_secret.json`. Nie wpisuj tego pliku do repozytorium ani nikomu go nie przesyłaj.
7. Zaloguj się w przeglądarce: w aplikacji desktopowej kliknij **Wyślij do YT** w kroku **Publikacja → YouTube** (najlepiej z opcją „Tylko podgląd”) albo uruchom `python ipsc_automato.py --yt`. Zatwierdź dwa uprawnienia: przesyłanie filmów (`youtube.upload`) i odczyt kanału (`youtube.readonly`). Przy ostrzeżeniu „Google nie zweryfikowało tej aplikacji” wybierz **Zaawansowane → Przejdź do… (niebezpieczne)** — to Twoja własna aplikacja. Po zalogowaniu powstanie lokalny `youtube_token.json`, dzięki czemu kolejne uruchomienia nie wymagają logowania.

Jeśli zobaczysz błąd **`Błąd 403: access_denied`**, sprawdź, czy konto jest dodane jako **Test user** (krok 4).

Nie używaj konta usługi — upload odbywa się w imieniu zalogowanego kanału. Pliki `youtube_client_secret.json`, `youtube_token.json` i `youtube_upload_state.json` (rejestr wysłanych filmów) są poufne i ignorowane przez Git — nie udostępniaj ich.

> Projekt w trybie **Testing** pozwala logować się tylko dodanym testerom, a autoryzacja wygasa po 7 dniach — wtedy usuń `youtube_token.json` i zaloguj się ponownie.

### Wysyłanie z aplikacji desktopowej (zakładka YouTube)

1. Wybierz folder z filmami: domyślnie jest to folder **Gotowe filmy** z zakładki Główna. Odznacz „Taki sam jak Gotowe filmy”, aby wskazać dowolny inny folder (np. gdy filmy przeniosłeś lub chcesz wysłać tylko część); wybór jest zapamiętywany.
2. Na górze zakładki, w sekcji **PUBLIKACJA**, wybierz sposób publikacji (ustawienia są zapamiętywane):
   - **Zaplanuj publikację** (domyślnie) — filmy trafiają na YouTube jako prywatne z terminem publikacji. Bez dodatkowych opcji obowiązuje harmonogram domyślny: pon–pt 7:30, sob–nd 10:00.
   - **Własne dni i godziny publikacji** — po zaznaczeniu tego checkboxa aktywują się kolumny Pon–Nd. Zaznacz dni, w których chcesz publikować, i ustaw dla każdego własną godzinę (`HH:mm`). Każdy film dostaje najbliższy wolny termin w jednym z zaznaczonych dni (jeden film na dzień). Trzeba zaznaczyć co najmniej jeden dzień.
   - **Publikuj wszystkie od razu** — filmy są wysyłane jako publiczne, bez terminu; opcje planowania są wtedy wyszarzone.
   - **Dodatkowo opublikuj prywatnie** — ten sam film jest wysyłany drugi raz jako niepubliczny (dostępny tylko z linkiem), z natychmiastową publikacją, niezależnie od wybranego trybu. Powstają dwa osobne filmy i dwa linki; na końcu wysyłki dziennik pokazuje listę prywatnych linków wraz z tytułami. Jeśli film jest już opublikowany lub w kolejce (rejestr albo istniejący tytuł), a nie ma jeszcze wersji prywatnej, wysyłana jest tylko wersja prywatna.
3. Zostaw zaznaczone **Tylko podgląd**, aby zobaczyć w dzienniku tytuły i terminy publikacji bez wysyłania. Gdy wszystko się zgadza, odznacz tę opcję.
4. Kliknij **Wyślij do YT** i potwierdź (okno wskazuje, czy filmy będą zaplanowane, czy opublikowane natychmiast). Postęp widać w dzienniku wysyłania.
5. **Przerwij wysyłanie** zatrzymuje wysyłkę po bieżącym fragmencie pliku; film przerwany w trakcie nie zostaje zapisany w rejestrze, więc kolejna próba wyśle go od nowa. Już wysłane filmy są pomijane (rejestr `youtube_upload_state.json`). Okna logowania Google w przeglądarce nie da się przerwać z aplikacji — zamknij je ręcznie.
6. Aplikacja nie zamknie się w trakcie wysyłania; najpierw ją przerwij.

Opcje sekcji **PUBLIKACJA** w aplikacji desktopowej mają odpowiedniki w terminalu (`--schedule`, `--publish-now`, `--unlisted`, opisane w sekcji „Opcje publikacji w terminalu”). Bez tych flag obowiązuje harmonogram domyślny.

Przy braku `youtube_client_secret.json` lub bibliotek Google aplikacja pokaże komunikat błędu w dzienniku — patrz instrukcja uzyskania klucza powyżej oraz zakładka **Pomoc → Test Systemu**.

### Nazwy plików i publikacja

Uzupełnij `opis_zawodow.txt` nazwą i datą zawodów. Generator `generate_names.py` odczytuje nazwę z pola `Nazwa zawodów:` lub pierwszej niepustej linii, datę z `Match starts: August 09, 2026` albo `Data zawodów: 09.08.2026`, a numer toru z nazwy takiej jak `Gotowe_Stage_3.mp4`. Tytuł ma format `YYYY-MM-DD - Nazwa zawodów - Tor X #bodycam`, jest ograniczany do 100 znaków i służy również jako nazwa pliku MP4. Jest uruchamiany automatycznie po standardowym montażu; można go też wywołać ręcznie:

```bash
python generate_names.py Gotowe_Stage_1.mp4
```

Uploader `youtube_upload.py` jest uruchamiany z głównego skryptu wyłącznie po podaniu opcji `/yt` lub `--yt` (lub przyciskiem **Wyślij do YT** w aplikacji desktopowej). Odczytuje playlistę przesłanych filmów kanału, sprawdza zaplanowane publikacje i wybiera najbliższy wolny dzień: domyślnie poniedziałek–piątek o 7:30, sobota–niedziela o 10:00 czasu `Europe/Warsaw` (można to zmienić w sekcji **PUBLIKACJA** aplikacji desktopowej albo flagami `--schedule` / `--publish-now`). Uwzględnia terminy filmów zaplanowanych oraz dni publikacji filmów publicznych i niepublicznych. Opis YouTube zawiera tylko nazwę, datę, lokalizację, typ i poziom zawodów oraz hashtagi tworzone z tych pól — nie kopiuje całego pliku z opisem zawodów.

Standardowe uruchomienie montuje filmy i zmienia ich nazwy, ale nie uruchamia połączenia z YouTube. Opcja `/yt` lub `--yt` po zakończeniu montażu uruchamia **tylko podgląd** kolejki — nic nie jest przesyłane:

```bash
python ipsc_automato.py --yt
```

Po sprawdzeniu podglądu rzeczywisty upload wymaga obu opcji:

```bash
python ipsc_automato.py --yt --publish
```

### Podsumowanie komend

| Komenda                                               | Działanie                                                                                                   |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `python ipsc_automato.py`                             | Montaż + nadanie nazw plikom; bez YouTube                                                                   |
| `python ipsc_automato.py --yt` (lub `/yt`)            | Jak wyżej + podgląd tytułów i terminów; nic nie jest wysyłane                                               |
| `python ipsc_automato.py --yt --publish`              | Jak wyżej + rzeczywisty upload zaplanowany na wolne terminy                                                 |
| `python generate_names.py Gotowe_Stage_1.mp4`         | Ręczna zmiana nazwy jednego pliku                                                                           |
| `python youtube_upload.py [plik\|folder] [--publish]` | Bezpośrednie wywołanie uploadera (domyślnie folder `Gotowe`); to samo robi zakładka **YouTube** w aplikacji |

`--publish` bez `/yt` lub `--yt` jest odrzucane. Film pionowy lub kwadratowy (Short) może trwać maksymalnie 3 minuty; filmy poziome nie mają tego limitu. Przy wielu plikach uploader planuje najwyżej jedną publikację dziennie na wybranym kanale. Jeśli OAuth zwróci więcej niż jeden kanał, ustaw zmienną środowiskową `YOUTUBE_CHANNEL_ID` na ID właściwego kanału. Google może wymagać weryfikacji projektu OAuth, zanim filmy przesyłane przez API będą mogły być publiczne.

### Opcje publikacji w terminalu

Wszystkie poniższe opcje działają po montażu, w tej kolejności: Cloudflare R2 → Buffer → YouTube. Są też dostępne w aplikacji desktopowej. Kod wyjścia to `0` przy sukcesie i `1`, gdy wystąpił błąd.

| Flaga                              | Działanie                                                                                                         | Wymaga                     |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `--schedule "pon=07:30,sob=10:00"` | Harmonogram publikacji YouTube w tygodniu (dni: `pon`, `wt`, `sr`, `czw`, `pt`, `sob`, `nd`)                      | `--yt --publish`           |
| `--publish-now`                    | Publikuje na YouTube od razu, bez harmonogramu (wyklucza się z `--schedule`)                                      | `--yt --publish`           |
| `--unlisted`                       | Dodatkowo wysyła na YouTube wersję **unlisted** i wypisuje link `youtu.be`                                        | `--yt --publish`           |
| `--cloudflare`                     | Wysyła MP4 z folderu `Gotowe` na bucket Cloudflare R2 i dopisuje linki do `buffer.txt`                             | konfiguracja R2 w `settings.json` |
| `--buffer`                         | Tworzy szkice w Buffer z linków z `buffer.txt`                                                                     | `--buffer-platforms`       |
| `--buffer-platforms facebook,instagram,x` | Platformy Buffer (`x` można zapisać jako `twitter`)                                                        | `--buffer`                 |
| `--buffer-post-type reel\|post\|story` | Typ posta dla Facebooka i Instagrama (domyślnie `reel`)                                                       | `--buffer`                 |
| `--buffer-schedule "pon=07:30,sob=10:00"` | Harmonogram szkiców Buffer; bez tej opcji szkice trafiają w pierwsze wolne terminy domyślne                 | `--buffer`                 |

Opisy dla Buffer pochodzą z pliku `opis_zawodow.txt` (ten sam plik, którego używa aplikacja desktopowa). Dla Instagrama użyte są maksymalnie 5 hashtagów, a dla X obowiązuje limit 280 znaków.

Przykłady:

```bash
# Montaż, upload na R2, szkice Buffer na Facebooku i Instagramie
python ipsc_automato.py --cloudflare --buffer --buffer-platforms facebook,instagram --buffer-post-type reel

# Montaż i publikacja na YouTube w wybrane dni, z wersją unlisted
python ipsc_automato.py --yt --publish --schedule "pon=07:30,sob=10:00" --unlisted

# Montaż i natychmiastowa publikacja na YouTube
python ipsc_automato.py --yt --publish --publish-now
```

Flagi `--publish`, `--schedule`, `--publish-now` i `--unlisted` wymagają `--yt`. Flagi `--buffer-platforms`, `--buffer-post-type` i `--buffer-schedule` wymagają `--buffer`. Opcja `--buffer` wymaga `--buffer-platforms`. Buffer i Cloudflare działają tylko po montażu, bo są uruchamiane po nim w tym samym przebiegu.

## 📣 Publikacja na Facebooku, Instagramie i X przez Buffer

Zakładka **Buffer** tworzy w Buffer **szkice** postów z filmami (bez publikacji) — publikację zatwierdzasz już w panelu Buffer. Działa na podstawie listy adresów plików wideo z pliku `buffer.txt`, zwykle linków publicznych z Cloudflare R2.

### Zakładka Buffer w aplikacji

- **Platformy:** checkboxy **Facebook**, **Instagram** i **X/Twitter**. Dla Facebooka i Instagrama wybierasz typ posta: **reel**, **post** lub **story** (domyślnie **reel**). Instagram zawsze jest wysyłany z opcją udostępnienia w feedzie.
- **Opisy:** osobne pola dla każdej platformy. Aplikacja liczy hashtagi w opisie Instagrama (limit 5) i znaki w opisie X/Twitter (limit 280, każdy adres URL liczy się jako 23 znaki). Przekroczenie limitu blokuje utworzenie szkiców.
- **Lista filmów (`buffer.txt`):** edytor z przyciskami **Wczytaj z pliku** i **Zapisz do pliku** oraz wyborem pliku. Ścieżka jest zapamiętywana. Z listy brane są wszystkie adresy `http(s)://`, bez duplikatów.
- **PLANOWANIE SZKICÓW:** te same dni tygodnia i godziny co w sekcji **PUBLIKACJA** zakładki YouTube.
- **Utwórz szkice w Buffer:** tworzy szkice w pierwszych wolnych terminach. Każdy film dostaje jeden termin, który jest wspólny dla wszystkich wybranych platform. Przycisk **Przerwij** zatrzymuje pracę po bieżącym kroku.
- **Wyślij do CloudFlare:** wysyła pliki MP4 do bucketa R2 (patrz niżej).

### Integracja z API Buffer

**Gdzie znaleźć klucz API:**

1. Zaloguj się na konto Buffer (jeśli go nie masz, załóż je na https://buffer.com/signup).
2. Otwórz stronę ustawień API: https://publish.buffer.com/settings/api.
3. Utwórz nowy klucz API i skopiuj go. Klucz daje dostęp do Twojego konta Buffer, więc nie udostępniaj go i nie wrzucaj do repozytorium Git.
4. Wklej klucz do pliku `settings.json` w katalogu projektu pod kluczem `BUFFER_API`:

```json
{
  "BUFFER_API": "tu_wklej_klucz_api"
}
```

Aplikacja korzysta z GraphQL API Buffer (`https://api.buffer.com`) przez moduł `buffer_api.py`, bez dodatkowych bibliotek. Token zapisany pod kluczem `BUFFER_API` w `settings.json` jest wysyłany jako nagłówek autoryzacji. Przebieg tworzenia szkiców:

1. Pobranie pierwszej organizacji konta (`account.organizations`).
2. Pobranie kanałów i dopasowanie ich po usłudze: `facebook`, `instagram`, `twitter` (X). Jeśli na koncie jest kilka kanałów tej samej usługi, używany jest pierwszy z nich, a w dzienniku pojawia się ostrzeżenie.
3. Pobranie terminów istniejących postów i szkiców wybranych kanałów, aby nie planować dwóch filmów w tym samym dniu.
4. Dla każdego filmu wybór najbliższego wolnego terminu i utworzenie szkicu mutacją `createPost` (`saveToDraft: true`, tryb `customScheduled`, wideo jako `assets.video.url`).

Buffer pobiera plik wideo z podanego adresu dopiero w chwili publikacji, dlatego link musi być trwały i publiczny. Treść posta to sam opis, bez linku do filmu.

Postęp zapisuje się w pliku **`buffer_upload_state.json`** (kluczem jest para `platforma|link` z identyfikatorem posta i terminem). Dzięki temu ponowne uruchomienie pomija już wysłane pary, a film dla kolejnej platformy dostaje ten sam termin co wcześniej. Usunięcie tego pliku spowoduje utworzenie szkiców od nowa, więc rób to tylko świadomie.

Błędy API (np. odrzucony token, brak kanału danej usługi, brak połączenia) są pokazywane w dzienniku jako `[Buffer] BŁĄD: …`.

### Integracja z Cloudflare R2

Cloudflare R2 pełni rolę publicznego hostingu plików wideo, z którego Buffer je pobiera. Moduł `cloudflare_upload.py` korzysta z interfejsu S3 (biblioteka `boto3`). Wymagane klucze w `settings.json` opisuje sekcja „Konfiguracja Skryptu” (`CLOUDFLARE_API`, `CLOUDFLARE_ACCESS_KEY_ID`, `CLOUDFLARE_SECRET_ACCESS_KEY`, `CLOUDFLARE_PUBLIC_URL`). Przed wysyłką aplikacja sprawdza, czy `CLOUDFLARE_PUBLIC_URL` nie wskazuje na endpoint S3.

**Gdzie znaleźć dane do konfiguracji R2:**

1. **Bucket:** w panelu Cloudflare otwórz **R2 object storage → Overview** i wybierz **Create bucket**. Nazwa bucketa (np. `buffer-api`) musi być taka sama jak na końcu `CLOUDFLARE_API`.
2. **Account ID:** widoczny na stronie **R2 object storage → Overview** w sekcji **Account Details**. Wstaw go w adresie endpointu w miejscu `<ID_KONTA>`.
3. **Klucze API (`CLOUDFLARE_ACCESS_KEY_ID` i `CLOUDFLARE_SECRET_ACCESS_KEY`):** na stronie **R2 object storage → Overview**, w sekcji **Account Details**, wybierz **Manage** przy **API Tokens**, a następnie **Create Account API token** (lub **Create User API token**). W uprawnieniach wybierz **Object Read & Write** i (opcjonalnie) ogranicz token do bucketa `buffer-api`. Po utworzeniu zobaczysz **Access Key ID** i **Secret Access Key** — skopiuj oba od razu, bo sekretu nie da się odczytać ponownie.
4. **Endpoint (`CLOUDFLARE_API`):** `https://<ID_KONTA>.r2.cloudflarestorage.com/<nazwa_bucketa>`. Jeśli bucket założono w jurysdykcji UE, endpoint ma postać `https://<ID_KONTA>.eu.r2.cloudflarestorage.com/<nazwa_bucketa>`.
5. **Publiczny adres (`CLOUDFLARE_PUBLIC_URL`):** otwórz bucket, przejdź do **Settings → Public access** i włącz dostęp. Cloudflare pokaże adres `https://pub-….r2.dev` (albo możesz podpiąć własną domenę). To ten adres wpisz w `CLOUDFLARE_PUBLIC_URL`.

Przykład uzupełnionych kluczy w `settings.json`:

```json
{
  "CLOUDFLARE_API": "https://<ID_KONTA>.r2.cloudflarestorage.com/buffer-api",
  "CLOUDFLARE_ACCESS_KEY_ID": "twoj_access_key_id",
  "CLOUDFLARE_SECRET_ACCESS_KEY": "twoj_secret_access_key",
  "CLOUDFLARE_PUBLIC_URL": "https://pub-xxxx.r2.dev"
}
```

Przycisk **Wyślij do CloudFlare** działa tak:

1. Zbiera wszystkie pliki `.mp4` z wybranego folderu (domyślnie **Gotowe**), posortowane po nazwie.
2. Dla każdego pliku sprawdza, czy obiekt o tej samej nazwie już istnieje w buckecie. Jeśli tak, nie wysyła go ponownie.
3. Wysyła brakujące pliki z typem `video/mp4`.
4. Buduje publiczny link (`CLOUDFLARE_PUBLIC_URL` + nazwa pliku, z zakodowanymi znakami specjalnymi) i dopisuje go na końcu `buffer.txt`, jeśli go tam jeszcze nie ma. Dotyczy to także plików, które były już w buckecie.

Link jest dopisywany po każdym pliku, więc przerwana wysyłka nie gubi już wysłanych filmów. Błąd jednego pliku (np. chwilowy problem sieci) jest zapisywany w dzienniku jako `[Cloudflare] BŁĄD przy …`, a wysyłka przechodzi do kolejnych plików.

## ⚠️ Najczęstsze problemy

- **`ModuleNotFoundError: No module named 'google'`:** Brakuje bibliotek Google. Uruchom `python -m pip install -r requirements.txt` tym samym Pythonem, którym odpalasz skrypt.
- **`Błąd 403: access_denied` przy logowaniu Google:** Projekt OAuth jest w trybie Testing, a Twoje konto nie jest testerem. Dodaj je w Google Cloud Console → Audience → Test users i spróbuj ponownie.
- **`Brak pliku OAuth ... youtube_client_secret.json`:** Pobierz dane klienta OAuth typu „Aplikacja komputerowa” i zapisz je w katalogu projektu pod tą nazwą.
- **`Nie można jednoznacznie wybrać kanału`:** Konto ma kilka kanałów — ustaw zmienną środowiskową `YOUTUBE_CHANNEL_ID`.
- **Błąd daty/nazwy zawodów:** Uzupełnij `opis_zawodow.txt` (nazwa + `Match starts:`/`Data zawodów:`); numer toru musi występować w nazwie pliku (`Gotowe_Stage_3.mp4`).
- **Film z toru został pominięty („brak wyników dla toru N”):** Pojawia się tylko przy zaznaczonym **Czy dodać wyniki**. W `wyniki.txt` nie ma wiersza `Stage N` dla numeru toru przypisanego w `mapowanie_torow.txt`. Sprawdź oba pliki w kroku **Wyniki** lub odznacz checkbox w kroku **Montaż**.
- **Film wyszedł w złej orientacji:** W kroku **Montaż** wybierz **Wideo Pionowe** lub **Wideo Poziome** (dotyczy wszystkich plików bez litery w `mapowanie_torow.txt`) albo dopisz w `mapowanie_torow.txt` po numerze toru `;H` (poziomy 1920×1080) lub `;V` (pionowy 1080×1920), np. `3;H` — ta litera ma pierwszeństwo.
- **Zakładka YouTube: „Brak pliku OAuth” lub „Brak bibliotek Google API”:** Zapisz `youtube_client_secret.json` w katalogu projektu (instrukcja wyżej) i zainstaluj zależności `python -m pip install -r requirements.txt`.
- **Zakładka YouTube: „Shorts muszą mieć maksymalnie 180 sekund”:** Film pionowy jest dłuższy niż 3 minuty — skróć go lub zmień orientację toru na `H` w pliku z torami.
- **Aplikacja po starcie otwiera zakładkę Pomoc:** Test systemu wykrył braki — wykonaj polecenia z sekcji **Do doinstalowania / naprawy** i uruchom aplikację ponownie.
- **Błąd `ModuleNotFoundError: No module named 'moviepy.editor'`:** Masz zainstalowaną nową wersję MoviePy (2.0+). Wpisz w konsoli `pip uninstall moviepy` a następnie `pip install "moviepy<2.0.0"`.
- **Błąd `must be real number, not NoneType` przy zapisie wideo:** Masz zbyt nową bibliotekę `decorator`. Użyj `pip install "decorator==4.4.2"`.
- **Błąd `Accessing time t=... with clip duration=...` dla muzyki:** Skrypt zapętla muzykę, więc krótki utwór nie powinien go wywołać; sprawdź, czy plik `.mp3` nie jest uszkodzony.
- **Pliki `*TEMP_MPY_*`:** Resztki nieudanych renderów. Skrypt je pomija, możesz je bezpiecznie usunąć.
- **Buffer: „Buffer odrzucił zapytanie (HTTP 401/403)”:** Nieprawidłowy lub wygasły token. Wpisz aktualny klucz w `settings.json` pod `BUFFER_API`.
- **Buffer: „W Buffer nie znaleziono kanału …”:** Na koncie Buffer nie ma kanału wybranej platformy. Podłącz go w panelu Buffer albo odznacz tę platformę.
- **Buffer: „Pominięto już wysłany film”:** Ta para platforma + film jest już w `buffer_upload_state.json`. Aby utworzyć szkic ponownie, usuń odpowiedni wpis z pliku (świadomie — może to dać duplikat w Buffer).
- **Buffer: „Opis na Instagram ma … hashtagów” / „Opis na X/Twitter ma … znaków”:** Skróć opis do limitu, zanim utworzysz szkice.
- **Cloudflare: „Uzupełnij w settings.json: …”:** Brakuje jednego z kluczy `CLOUDFLARE_*`. Uzupełnij wszystkie cztery.
- **Cloudflare: „CLOUDFLARE_PUBLIC_URL wskazuje na endpoint S3”:** W `CLOUDFLARE_PUBLIC_URL` wpisałeś adres `*.r2.cloudflarestorage.com`. Włącz **Public access** dla bucketa i wpisz adres `https://pub-….r2.dev` lub własnej domeny.
- **Cloudflare: „Nieprawidłowy adres CLOUDFLARE_API”:** Adres musi kończyć się nazwą bucketa, np. `https://<ID_KONTA>.r2.cloudflarestorage.com/buffer-api`.
- **Cloudflare: „W folderze nie ma plików MP4”:** Wybrany folder nie zawiera plików `.mp4`. Wskaż właściwy folder przyciskiem **Przeglądaj…**.
- **Buffer: film nie pojawia się w Buffer po publikacji:** Sprawdź, czy link z `buffer.txt` otwiera się w przeglądarce bez logowania. Jeśli nie, włącz Public access dla bucketa w Cloudflare R2.

## 🌐 Znajdź mnie w sieci

Ikony prowadzą do profili autora na GitHubie i w mediach społecznościowych:

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/bartosz-zarzyczny)
[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@Mr_BartekZ)
[![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/mr_bartekz/)
[![Facebook](https://img.shields.io/badge/Facebook-0866FF?style=for-the-badge&logo=facebook&logoColor=white)](https://www.facebook.com/profile.php?id=61587533125970)
[![X](https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/Mr_BartekZ)
