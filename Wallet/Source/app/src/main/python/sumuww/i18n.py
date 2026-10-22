"""UI catalogs and language preferences with bounded wallet-overwrite checks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .wallet_paths import reject_wallet_overwrite


LANGUAGES = (
    ("en", "English"), ("fr", "Français"), ("es", "Español"),
    ("ar", "العربية"), ("zh", "中文（普通话）"), ("pt", "Português"),
    ("ru", "Русский"), ("de", "Deutsch"), ("sw", "Kiswahili"),
    ("hi", "हिन्दी"), ("ko", "한국어"),
    ("ja", "日本語"),
    ("id", "Bahasa Indonesia"),
    ("vi", "Tiếng Việt"),
    ("tr", "Türkçe"),
    ("th", "ไทย"),
    ("it", "Italiano"),
    ("bn", "বাংলা"),
    ("ur", "اردو"),
    ("pl", "Polski"),
    ("nl", "Nederlands"),
    ("fil", "Filipino"),
    ("ta", "தமிழ்"),
    ("zh-TW", "繁體中文（台灣）"),
    ("zh-HK", "繁體中文（香港）"),
    ("cs", "Čeština"),
    ("da", "Dansk"),
    ("fi", "Suomi"),
    ("el", "Ελληνικά"),
    ("no", "Norsk (bokmål)"),
    ("sv", "Svenska"),
    ("sr", "Српски"),
    ("mn", "Монгол (Кирилл)"),
    ("mn-Mong", "ᠮᠣᠩᠭᠣᠯ"),
)
LANGUAGE_CODES = tuple(code for code, _ in LANGUAGES)
CATALOG_DIRECTORY = Path(__file__).resolve().parent.parent / "assets" / "locales"


def preference_path():
    local = os.environ.get("LOCALAPPDATA")
    current = ((Path(local) / "SUMUWW") if local else Path.home() / ".sumuww") / "ui-language.json"
    legacy = ((Path(local) / "DORA") if local else Path.home() / ".dora") / "ui-language.json"
    return current if current.exists() or not legacy.exists() else legacy


def load_language(path=None):
    """Absent or invalid preferences always select English."""
    path = preference_path() if path is None else Path(path)
    try:
        if path.stat().st_size > 4096:
            return "en"
        document = json.loads(path.read_text(encoding="utf-8"))
        if (isinstance(document, dict) and set(document) == {"schema_version", "language"}
                and type(document["schema_version"]) is int and document["schema_version"] == 1
                and document["language"] in LANGUAGE_CODES):
            return document["language"]
    except (OSError, ValueError, TypeError):
        pass
    return "en"


def save_language(language, path=None):
    """Publish one complete preference file atomically."""
    if language not in LANGUAGE_CODES:
        raise ValueError("Unknown UI language")
    path = preference_path() if path is None else Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    def guard_destination():
        try:
            reject_wallet_overwrite(path)
        except ValueError as error:
            # Language persistence failures use the GUI's existing OSError API.
            raise OSError(str(error)) from None
    guard_destination()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump({"schema_version": 1, "language": language}, output, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        guard_destination()
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


class LocalizedText(str):
    """A string retaining its message and arguments for an in-place refresh."""

    def __new__(cls, translator, key=None, arguments=(), parts=None):
        instance = str.__new__(cls, cls._render(translator, key, arguments, parts))
        instance.translator = translator
        instance.key, instance.arguments, instance.parts = key, arguments, parts
        return instance

    @staticmethod
    def _render(translator, key, arguments, parts):
        if parts is not None:
            return "".join(part.render() if isinstance(part, LocalizedText) else str(part) for part in parts)
        arguments = tuple(value.render() if isinstance(value, LocalizedText) else value for value in arguments)
        return translator.render(key, *arguments)

    def render(self):
        return self._render(self.translator, self.key, self.arguments, self.parts)

    def __add__(self, other):
        if isinstance(other, str):
            return LocalizedText(self.translator, parts=(self, other))
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, str):
            return LocalizedText(self.translator, parts=(other, self))
        return NotImplemented


class Translator:
    def __init__(self, language="en", catalog_directory=None):
        self.catalog_directory = CATALOG_DIRECTORY if catalog_directory is None else Path(catalog_directory)
        self._catalogs = {}
        self.set_language(language)

    def set_language(self, language):
        if language not in LANGUAGE_CODES:
            raise ValueError("Unknown UI language")
        self.language = language

    def catalog(self, language):
        if language not in self._catalogs:
            try:
                path = self.catalog_directory / f"{language}.json"
                if path.stat().st_size > 1_048_576:
                    raise ValueError("UI catalog too large")
                document = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(document, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in document.items()):
                    raise ValueError("Invalid UI catalog")
                self._catalogs[language] = document
            except (OSError, ValueError, TypeError):
                self._catalogs[language] = {}
        return self._catalogs[language]

    def render(self, key, *arguments):
        value = self.catalog(self.language).get(key, self.catalog("en").get(key, key))
        if not arguments:
            return value
        try:
            return value.format(*arguments)
        except (IndexError, KeyError, ValueError):
            return key.format(*arguments)

    def text(self, key, *arguments):
        return LocalizedText(self, key, arguments)


_active = Translator()


def set_translator(translator):
    global _active
    _active = translator


def get_translator():
    return _active


def tr(key, *arguments):
    return _active.text(key, *arguments)
