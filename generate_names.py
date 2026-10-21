import argparse
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple, Union

PROJECT_DIR = Path(__file__).resolve().parent
DESCRIPTION_FILE = PROJECT_DIR / "opis_zawodow.txt"
MAX_TITLE_LENGTH = 100

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4,
    "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9,
    "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}


@dataclass(frozen=True)
class MatchData:
    name: str
    match_date: date
    location: str
    match_type: str
    level: str


def _parse_date(text: str) -> Optional[date]:
    for pattern, order in (
        (r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", "ymd"),
        (r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", "dmy"),
    ):
        match = re.search(pattern, text)
        if match:
            values = [int(value) for value in match.groups()]
            year, month, day = (
                values if order == "ymd" else (values[2], values[1], values[0])
            )
            try:
                return date(year, month, day)
            except ValueError as error:
                raise ValueError(f"Nieprawidłowa data zawodów: {match.group(0)}") from error

    month_pattern = "|".join(sorted(_MONTHS, key=len, reverse=True))
    match = re.search(
        rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})\b",
        text,
        re.IGNORECASE,
    )
    if match:
        month = _MONTHS[match.group(1).lower()]
        return date(int(match.group(3)), month, int(match.group(2)))

    match = re.search(
        rf"\b(\d{{1,2}})\s+({month_pattern})\s+(\d{{4}})\b", text, re.IGNORECASE
    )
    if match:
        month = _MONTHS[match.group(2).lower()]
        return date(int(match.group(3)), month, int(match.group(1)))
    return None


def _field_value(lines: List[str], pattern: str) -> str:
    for line in lines:
        match = re.match(pattern + r"\s*:\s*(.+?)\s*$", line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def read_match_data(description_path: Path = DESCRIPTION_FILE) -> MatchData:
    if not description_path.is_file():
        raise FileNotFoundError(f"Brak pliku z opisem zawodów: {description_path}")

    text = description_path.read_text(encoding="utf-8-sig")
    lines = [line.strip() for line in text.splitlines()]
    name = _field_value(lines, r"(?:Nazwa zawodów|Competition name|Match name)")
    if not name:
        name = next((line for line in lines if line), "")
    if not name:
        raise ValueError(f"Plik z opisem zawodów jest pusty: {description_path}")

    match_date = None
    for line in lines:
        if re.search(r"\b(?:Match starts|Main Match|Data zawodów|Data|Termin)\b", line, re.I):
            match_date = _parse_date(line)
            if match_date:
                break
    if match_date is None:
        raise ValueError(
            f"Nie znaleziono daty zawodów w {description_path}; "
            "podaj ją w polu Data zawodów lub Match starts."
        )

    location = _field_value(lines, r"(?:Miejsce|Location)")
    if not location:
        for index, line in enumerate(lines):
            if re.match(r"Location\s*:\s*$", line, re.IGNORECASE):
                location = next((value for value in lines[index + 1:] if value), "")
                break
    match_type = _field_value(lines, r"(?:Typ zawodów(?:/Match type)?|Match type)")
    level = _field_value(lines, r"(?:Poziom(?:/Match level)?|Match level)")
    return MatchData(name, match_date, location, match_type, level)


def generate_title(
    file_name: Union[str, Path], description_path: Path = DESCRIPTION_FILE
) -> str:
    match_data = read_match_data(description_path)
    match = re.search(r"(?:stage|tor)[\s_-]*(\d+)", Path(file_name).stem, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"Nie można odczytać numeru toru z nazwy pliku {Path(file_name).name}; "
            "oczekiwano np. Gotowe_Stage_3.mp4."
        )

    fixed_part = f"{match_data.match_date.isoformat()} -  - Tor {match.group(1)} #bodycam"
    name_limit = MAX_TITLE_LENGTH - len(fixed_part)
    if name_limit < 1:
        raise ValueError("Data i numer toru nie mieszczą się w limicie długości tytułu YouTube.")
    name = match_data.name[:name_limit].rstrip()
    return f"{match_data.match_date.isoformat()} - {name} - Tor {match.group(1)} #bodycam"


def _hashtag_slug(text: str) -> str:
    text = text.replace("Ł", "L").replace("ł", "l")
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", ascii_text)
    return "".join(words)


def generate_description_and_hashtags(
    description_path: Path = DESCRIPTION_FILE,
) -> Tuple[str, List[str]]:
    match_data = read_match_data(description_path)
    hashtags = ["#IPSC"]
    for phrase in (match_data.match_type, match_data.location, match_data.name):
        for word in re.findall(r"[^\W\d_]+", phrase, re.UNICODE):
            hashtag = _hashtag_slug(word)
            if len(hashtag) >= 3 and hashtag.casefold() not in {
                tag[1:].casefold() for tag in hashtags
            }:
                hashtags.append(f"#{hashtag}")
            if len(hashtags) >= 8:
                break
        if len(hashtags) >= 8:
            break

    description_lines = [match_data.name, f"Data zawodów: {match_data.match_date.isoformat()}"]
    if match_data.location:
        description_lines.append(f"Miejsce: {match_data.location}")
    if match_data.match_type:
        description_lines.append(f"Typ zawodów: {match_data.match_type}")
    if match_data.level:
        description_lines.append(f"Poziom: {match_data.level}")
    return "\n".join(description_lines + ["", " ".join(hashtags)]), hashtags


def safe_file_name(title: str, extension: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return f"{name}{extension.lower()}"


def rename_file(path: Path, title: str) -> Path:
    target = path.with_name(safe_file_name(title, path.suffix))
    if target == path:
        return path
    if target.exists():
        raise FileExistsError(f"Plik docelowy już istnieje: {target}")
    return path.rename(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nadaje filmowi nazwę według danych zawodów.")
    parser.add_argument("plik", type=Path, help="Plik MP4 zawierający numer toru w nazwie.")
    parser.add_argument("--opis", type=Path, default=DESCRIPTION_FILE, help="Plik z opisem zawodów.")
    args = parser.parse_args()

    title = generate_title(args.plik, args.opis)
    new_path = rename_file(args.plik, title)
    print(f"Tytuł: {title}")
    print(f"Plik: {new_path}")


if __name__ == "__main__":
    main()
