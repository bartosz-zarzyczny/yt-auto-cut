# DIFF: `desktop_app.py` vs `ipsc_automato.py`

Porównanie funkcjonalności aplikacji desktopowej i wersji konsolowej.
Stan na commit `057492e` (2026-10-26). Ten plik jest jedyną zmianą — kod aplikacji nie był modyfikowany.

## 1. Wniosek w skrócie

| Obszar | Zgodność |
| ------ | -------- |
| Rdzeń montażu (przycinanie, muzyka, napisy, logo, render, nazwy plików) | **Pełna** — desktop wywołuje dokładnie tę samą funkcję `uruchom_automatyzacje` (`desktop_app.py:130`), nie ma własnej kopii pipeline'u |
| Konfiguracja montażu (`KonfiguracjaSciezek`) | **Pełna** — wszystkie 11 pól ma odpowiednik w UI |
| YouTube — samo wysyłanie / podgląd | **Jest**, ale w osobnym kroku (zakładka), bez uruchamiania po montażu |
| YouTube — automatyczne `--yt` / `--publish` po montażu | **Brak w desktopie** |
| YouTube — własny plik OAuth (`--client-secrets`) | **Brak w desktopie** |
| Tryb wsadowy / headless (harmonogram, brak GUI) | **Brak w desktopie** |
| Buffer, Cloudflare, harmonogramy publikacji, „publikuj od razu”, wersja unlisted | **Tylko desktop** (konsola tego nie ma) |
| Wynik formatów (Practiscore/ECM/Trening), orientacja H/V, logo, własne ścieżki | **Tylko desktop** — CLI nie ma do tego flag |

Podsumowując: **desktop jest funkcjonalnie nadzbiorem konsoli**, z trzema wyjątkami opisanymi w sekcji 3 (automatyczne YT po montażu, wybór pliku OAuth, praca bez GUI).

## 2. Jak to sprawdzono

- `desktop_app.py` importuje `uruchom_automatyzacje` i `KonfiguracjaSciezek` z `ipsc_automato` (`desktop_app.py:62-75`) i wywołuje je w `AssemblyWorker.run` (`desktop_app.py:128-135`).
- W `desktop_app.py` nie ma żadnego własnego kodu montażu: brak `VideoFileClip`, `write_videofile`, `TextClip`, `CompositeVideoClip` (jedyne `resize` to `QMainWindow.resize`).
- Przejrzane: `ipsc_automato.py` (CLI + `uruchom_automatyzacje`), `desktop_app.py` (całość), `youtube_upload.py`, `buffer_upload.py`, `cloudflare_upload.py`, `system_settings.py`, `app_settings.py`, `file_migration.py`, `timer_detect.py`, `timer_trim.py`, `additional_texts.py`, `logo_overlay.py`, `video_cancellation.py`.

## 3. Luki: konsola ma, desktop nie

### 3.5 Ścieżka kodu YouTube (desktop ma więcej opcji niż konsola przez `--yt`)

- Konsola (`ipsc_automato.py --yt`) wywołuje `youtube_upload.main(["Gotowe"])` (`ipsc_automato.py:353-358`). `main()` obsługuje pojedynczy plik lub folder, ma flagę `--client-secrets` (inny plik OAuth), ale **nie ma** harmonogramu godzinowego, opcji „publikuj wszystkie od razu” ani wersji unlisted (`youtube_upload.py:388-426`).
- Desktop wywołuje `youtube_upload.upload_videos(...)` bezpośrednio (`desktop_app.py:203-212`) – ma harmonogram godzinowy (`hours`), `immediate` (publikuj od razu), `also_unlisted` (dodatkowa wersja prywatna), ale **tylko folder** (brak pojedynczego pliku) i **brak** wyboru pliku OAuth.
- Skutek: przez `ipsc_automato --yt --publish` nie da się ustawić własnych godzin publikacji ani wysłać wersji unlisted; przez desktop nie da się wskazać innego pliku OAuth ani wysłać pojedynczego pliku.

### 3.6 Interpretacja wyniku montażu

- Konsola: `main()` wywołuje `uruchom_automatyzacje(...)` i **ignoruje zwracany bool** (`ipsc_automato.py:382`). Skrypt zawsze kończy się kodem 0, nawet gdy montaż się nie powiódł.
- Desktop: `AssemblyWorker` analizuje `success`, `error_count`, `skipped_count`, `completed_count` i pokazuje różne komunikaty („Wszystkie nagrania pominięto…”, „Montaż zakończony z błędami…”, „Montaż zakończony.”) (`desktop_app.py:141-156`).

### 3.7 Brak przerwania z klawiatury w konsoli

- `uruchom_automatyzacje` akceptuje `cancel_event`, ale `main()` konsoli nie ma sposobu, by go ustawić (brak obsługi Ctrl+C). Anulowanie działa tylko w desktopie (`desktop_app.py:1648-1654`).

### 3.8 Zależności

- Desktop wymaga dodatkowo `PySide6` (brak go → aplikacja się nie otwiera, tylko raport awaryjny w konsoli lub oknie). Konsola go nie potrzebuje.

### 3.9 Sposób uruchomienia

- `start.bat` uruchamia `desktop_app.py`, nie `ipsc_automato.py`. Konsolę trzeba uruchamiać ręcznie: `python ipsc_automato.py [--yt] [--publish]`.

### 3.1 Automatyczne YouTube po montażu (`--yt`, `--yt --publish`)

- Konsola: `python ipsc_automato.py --yt` po montażu uruchamia podgląd kolejki; `--yt --publish` wykonuje realny upload (`ipsc_automato.py:352-358`, `362-382`).
- Desktop: `AssemblyWorker` woła `uruchom_automatyzacje(...)` **bez** argumentów `yt` i `publikuj`, więc zawsze dostaje `False` (`desktop_app.py:130-135`). Wysyłkę trzeba uruchomić ręcznie w zakładce **YouTube**.
- Skutek: ta sama funkcja jest osiągalna, ale nie jednym przebiegiem; nie da się „montaż + publikacja” z jednego kliknięcia i nie da się tego zautomatyzować.
- Obejście: montaż na zakładce **Główna**, potem **YouTube → Wyślij do YT**.

### 3.2 Własny plik OAuth (`--client-secrets` / `YOUTUBE_CLIENT_SECRETS`)

- Konsola (`youtube_upload.py:408-413`) pozwala wskazać inny plik `client_secret*.json`.
- Desktop zawsze używa `youtube_client_secret.json`: `YouTubeWorker` nie przekazuje `client_secrets` do `upload_videos` (`desktop_app.py:203-212`), a UI nie ma takiego pola.
- Skutek: nie da się w GUI przełączyć projektu OAuth ani użyć innego konta bez podmiany pliku w katalogu projektu.

### 3.3 Tryb wsadowy / headless

- Konsola działa bez Qt, z Task Scheduler / crona, z dowolnego katalogu i bez otwartego okna. Obsługuje `/yt` jako alias `--yt` (`ipsc_automato.py:366-378`) oraz `--help`.
- Desktop wymaga PySide6 i kliknięcia **Rozpocznij montaż**; nie ma trybu CLI ani harmonogramu montażu.

### 3.4 Domyślne wartości różnią się (nie luka, ale zmiana zachowania)

| Ustawienie | `ipsc_automato.py` | `desktop_app.py` |
| ---------- | ------------------ | ---------------- |
| `dodaj_napisy` | `True` (`KonfiguracjaSciezek`, `ipsc_automato.py:80`) | `False` przy pierwszym uruchomieniu (`QSettings("dodaj_napisy", "false")`, `desktop_app.py:467-469`) |
| Tryb wyników | zawsze `practiscore` | wybór w UI, domyślnie `practiscore` |
| Orientacja | zawsze `V` | wybór w UI, domyślnie `V` |
| Logo | zawsze brak (`plik_logo=""`) | wybór pliku w UI |
| YouTube | domyślnie **podgląd** (bez `--publish`) | domyślnie **publikacja** („Tylko podgląd” odznaczone) |

Najważniejsza konsekwencja: `python ipsc_automato.py` bez argumentów **pomija filmy bez wyników** (bo `dodaj_napisy=True` → `dane is None` → `skipped`, `ipsc_automato.py:230-234`), a desktop przy odznaczonych napisach przetwarza wszystkie nagrania (bez planszy wyników).

### 3.5 Walidacja wejścia

- Desktop przed startem sprawdza istnienie folderów/plików, obecność MP4/MOV i poprawność ścieżek (`desktop_app.py:1601-1622`).
- Konsola nie waliduje: brakujący folder kończy się wyjątkiem z `os.listdir`, brak pliku wyników tylko komunikatem i pustym słownikiem (`ipsc_automato.py:153-156`).
- Uwaga: walidacja w desktopie pomija `plik_logo` (typ `"image"` nie jest sprawdzany w pętli) — nieistniejące logo jest po prostu ignorowane przez `resolve_logo_path`.

### 3.6 Upload pojedynczego pliku

- `python youtube_upload.py plik.mp4` obsługuje pojedynczy plik (`youtube_upload.py:416-422`).
- Zakładka **YouTube** przyjmuje tylko folder (bierze wszystkie `*.mp4` z katalogu, `desktop_app.py:195-198`).

### 3.7 Edytor wyników przy wyłączonych napisach

- Desktop nie zapisuje niezapisanych zmian w edytorze „Wyniki zawodów”, gdy checkbox napisów jest odznaczony (`desktop_app.py:1566-1573`).
- Sam montaż i tak czyta plik z dysku, jeśli istnieje (`ipsc_automato.py:198-199`), więc zmiany w edytorze mogą zostać po cichu pominięte.

## 4. Funkcje desktopu, których konsola nie ma

| Funkcja | Gdzie w desktopie |
| ------- | ----------------- |
| Zakładka **Buffer** — szkice postów FB/IG/X, typy postów, limity znaków/hashtagów, rejestr `buffer_upload_state.json` | `desktop_app.py:622-696`, `952-1064` |
| **Cloudflare R2** — wysyłka MP4 i dopisywanie linków do `buffer.txt` | `desktop_app.py:1066-1184` |
| Harmonogram publikacji YT: własne dni/godziny, „publikuj wszystkie od razu”, „także prywatnie (unlisted)” | `desktop_app.py:823-867`, `881-925` |
| Edycja plików projektu w GUI (teksty, opis, tory, wyniki, lista Buffer) + zapis/wczytanie | `desktop_app.py:1409-1557` |
| Wybór formatu wyników (Practiscore/ECM/Trening) i orientacji H/V | `desktop_app.py:1330-1391` |
| Wybór logo, folderów i wszystkich ścieżek z zapamiętywaniem | `desktop_app.py:1393-1407`, `1451-1499` |
| Ścieżka do ImageMagick w UI (`settings.json`) | `desktop_app.py:1186-1237` |
| Test systemu w GUI + automatyczny test przy starcie, przejście do zakładki Pomoc | `desktop_app.py:1239-1311` |
| Pasek postępu, przycisk **Przerwij** dla montażu i każdej wysyłki | `desktop_app.py:474-495`, `1648-1654` |
| Odporność na brak bibliotek montażu (okno i Pomoc działają, montaż zablokowany) | `desktop_app.py:77-104`, `1588-1597` |
| Zapamiętywanie ustawień między uruchomieniami (QSettings) | `desktop_app.py:339`, `1451-1499` |

Uwaga: konsola ma `cancel_event` w API, ale nie ma sposobu, by go ustawić z terminala (brak obsługi Ctrl+C) — więc anulowanie jest realnie tylko w desktopie.

## 5. Zgodność rdzenia montażu (szczegóły)

| Krok | `ipsc_automato.py` | Desktop |
| ---- | ------------------ | ------- |
| Sprawdzenie środowiska i wybór kodeka | `check_environment` (`191`) | to samo (przez import) |
| Odczyt wyników (3 formaty) | `czytaj_wyniki_z_pliku` (`153-165`) | to samo, tryb z UI |
| Lista nagrań MP4/MOV + sortowanie | `204-208` | to samo |
| Przypisanie torów i rozdzielczości | `assign_tracks` (`209-213`) | to samo |
| Detekcja timera + przycięcie | `zglos_wykrycie_timera`, `trim_video` (`253-257`) | to samo |
| Muzyka: losowy utwór, loop, głośność 0.12, fade-out 1 s | `262-280` | to samo |
| Plansza wyników (STAGE, miejsce, czas, HF, pkt) | `282-293` | to samo |
| Teksty wideo, logo, skala H/V | `295-305` | to samo |
| Render: fps 30, aac, 8000k, `yuv420p`, preset, plik tymczasowy | `308-320` | to samo |
| Nazwa pliku (`generate_title` / `rename_file`) | `324-326` | to samo |
| Sprzątanie plików tymczasowych, zamykanie klipów | `342-350` | to samo |
| `move_old_files` / `ensure_settings_file` | `39`, `62` | `58-59` + przez import |

## 6. Znalezione przy okazji (nie naprawiane)

1. **Błąd w `desktop_app.py:1679-1682`** — gałąź `elif not success:` wykonuje `self.log_view.append(message)`. `QPlainTextEdit` nie ma metody `append` (jest `appendPlainText`), więc anulowanie montażu przez użytkownika kończy się `AttributeError` w slocie `_finish` zamiast wpisu w dzienniku.
2. **`main()` konsoli nie zwraca kodu wyjścia** (`ipsc_automato.py:382`) — `uruchom_automatyzacje` zwraca `bool`, ale wynik jest ignorowany, więc skrypt zawsze kończy się kodem 0. Automatyzacja nie odróżni sukcesu od błędu.
3. **Dokumentacja vs kod** — `logo_overlay.py:1` mówi „maks. 100x100”, stała `LOGO_MAX_SIZE = 200`, a podpowiedź w GUI (`desktop_app.py:523`) i README mówią „250×250”.
4. **README (`294`)** twierdzi, że plan Buffer to „te same dni tygodnia i godziny co w sekcji PUBLIKACJA”, a w kodzie to dwie niezależne siatki ustawień (`buffer_*` i `yt_*`) — mają tylko te same wartości domyślne i nie synchronizują się po zmianie.

## 7. Rekomendacje

1. Dodać w zakładce **Główna** checkbox „Po montażu wyślij do YouTube” (+ wybór podgląd/publikacja), który po sukcesie uruchomi istniejący `YouTubeWorker` z folderem `folder_wyjsciowy` — to domknie parite z `--yt` / `--publish`.
2. Dodać opcjonalne pole „Plik OAuth (client secret)” w zakładce **YouTube** i przekazywać je do `upload_videos(client_secrets=...)`.
3. Ujednolicić domyślne `dodaj_napisy` (albo świadomie udokumentować różnicę `True` vs `False`) — obecnie ten sam projekt daje różne wyniki w zależności od trybu uruchomienia.
4. Naprawić `append` → `appendPlainText` w `_finish`.
5. Jeśli ma być jedno źródło prawdy o różnicach: trzymać ten plik aktualizowanym przy zmianach w `uruchom_automatyzacje` / argumentach CLI.

Poza powyższym desktop realizuje cały zakres `ipsc_automato.py` (i więcej), więc nie ma ryzyka, że któraś operacja montażu „wypadła” z wersji graficznej.
