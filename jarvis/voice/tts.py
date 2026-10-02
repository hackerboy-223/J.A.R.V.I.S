from __future__ import annotations

import html
import re
import threading
import time
import unicodedata

import pyttsx3


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:https?://)?[^)]+\)")
_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_WINDOWS_PATH_RE = re.compile(
    r"(?<!\w)(?:[A-Za-z]:\\[^\s]+|(?:\.\\|\.\.\\)[^\s]+)"
)
_MARKDOWN_PREFIX_RE = re.compile(r"^\s{0,3}(?:#{1,6}|>|[-+*]|\d+[.)])\s+")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _decode_language(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").replace("\x05", "")
    return str(value or "")


def _looks_like_code_or_table(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if stripped.startswith(("PS ", ">>>", "$ ", "C:\\", ".\\", "../", "./")):
        return True

    if stripped.count("|") >= 2:
        return True

    technical_tokens = ("{", "}", "=>", "::", "&&", "||", "</", "/>", "===", "!==")
    if any(token in stripped for token in technical_tokens):
        punctuation = sum(1 for ch in stripped if not ch.isalnum() and not ch.isspace())
        return punctuation / max(1, len(stripped)) > 0.14

    return False


def _strip_symbol_noise(text: str) -> str:
    chars: list[str] = []
    for ch in text:
        category = unicodedata.category(ch)

        # Remove emoji/symbol glyphs that TTS engines may announce strangely.
        if category in {"So", "Sk"}:
            continue

        if ch in {"*", "#", "_", "~", "^", "\\", "|", "<", ">", "{", "}", "[", "]"}:
            chars.append(" ")
            continue

        # Slash and repeated technical separators are visual, not useful in speech.
        if ch in {"/", "=", "•", "▪", "◦", "→", "←", "↓", "↑"}:
            chars.append(" ")
            continue

        # Keep ordinary sentence punctuation for natural pauses.
        chars.append(ch)

    return "".join(chars)


def prepare_for_speech(text: str) -> str:
    """Convert rich Markdown/technical output into natural speech.

    The visual answer stays untouched. Only the string sent to the TTS engine
    is simplified.
    """
    clean = html.unescape(str(text or ""))
    clean = clean.replace("\r\n", "\n").replace("\r", "\n")

    # Code should remain visible in the UI, but never be read character by character.
    clean = _FENCED_CODE_RE.sub("\n", clean)

    # Markdown link -> human label; raw URL -> remove.
    clean = _MD_LINK_RE.sub(r"\1", clean)
    clean = _URL_RE.sub(" ", clean)

    # Windows/shell paths are useful visually but awful when spoken.
    clean = _WINDOWS_PATH_RE.sub(" ", clean)

    # Inline code: keep simple words, drop strongly technical fragments.
    def inline_replacement(match: re.Match[str]) -> str:
        value = match.group(1).strip()
        if not value:
            return " "
        if _looks_like_code_or_table(value):
            return " "
        if any(ch in value for ch in ("\\", "/", "{", "}", "=", ";")):
            return " "
        return f" {value} "

    clean = _INLINE_CODE_RE.sub(inline_replacement, clean)

    spoken_lines: list[str] = []
    for raw_line in clean.splitlines():
        line = raw_line.strip()
        if not line:
            spoken_lines.append("")
            continue

        if _looks_like_code_or_table(line):
            continue

        line = _MARKDOWN_PREFIX_RE.sub("", line)

        # Markdown emphasis and formatting punctuation.
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"__([^_]+)__", r"\1", line)
        line = re.sub(r"~~([^~]+)~~", r"\1", line)

        # Make a few common symbols sound natural.
        line = line.replace("&", " et ")
        line = re.sub(r"(?<=\d)%(?!\w)", " pour cent", line)
        line = re.sub(r"\s+\+\s+", " plus ", line)

        line = _strip_symbol_noise(line)

        # Hyphens used as separators should not be announced.
        line = re.sub(r"\s+-\s+", ", ", line)
        line = re.sub(r"-{2,}", " ", line)

        line = _MULTI_SPACE_RE.sub(" ", line).strip(" ,;:-")
        if line:
            spoken_lines.append(line)

    clean = "\n".join(spoken_lines)
    clean = _MULTI_NEWLINE_RE.sub("\n\n", clean)
    clean = _MULTI_SPACE_RE.sub(" ", clean)

    # Avoid awkward punctuation runs left by removed technical fragments.
    clean = re.sub(r"\s+([,.!?;:])", r"\1", clean)
    clean = re.sub(r"([,.!?;:]){2,}", r"\1", clean)
    clean = clean.strip()

    return clean


class Speaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._speaking = threading.Event()

    def _pick_voice(self, engine) -> str | None:
        voices = engine.getProperty("voices") or []
        scored: list[tuple[int, str]] = []

        for voice in voices:
            voice_id = str(getattr(voice, "id", "") or "")
            name = str(getattr(voice, "name", "") or "")
            languages = " ".join(
                _decode_language(item)
                for item in (getattr(voice, "languages", None) or [])
            ).lower()
            haystack = f"{name} {voice_id} {languages}".lower()

            score = 0
            if "fr-fr" in haystack or "fr_fr" in haystack:
                score += 8
            if "français" in haystack or "french" in haystack:
                score += 6
            if any(
                token in haystack
                for token in ("hortense", "paul", "denise", "henri", "julie")
            ):
                score += 4
            if score:
                scored.append((score, voice_id))

        if not scored:
            return None
        scored.sort(reverse=True)
        return scored[0][1]

    @staticmethod
    def _avoid_wake_word(text: str) -> str:
        # Prevent J.A.R.V.I.S. from waking itself through speaker echo.
        text = re.sub(
            r"(?i)\\bJ\\.?A\\.?R\\.?V\\.?I\\.?S\\.?\\b[:,]?",
            "",
            text,
        )
        text = re.sub(r"(?i)\\bjarvis\\b[:,]?", "", text)
        return re.sub(r"[ \\t]{2,}", " ", text).strip()

    def speak(self, text: str, *, avoid_wake_word: bool = True) -> None:
        clean = prepare_for_speech(text)
        if avoid_wake_word:
            clean = self._avoid_wake_word(clean)
        if not clean:
            return

        with self._lock:
            self._stop_event.clear()
            self._speaking.set()
            engine = pyttsx3.init()
            loop_started = False

            try:
                voice_id = self._pick_voice(engine)
                if voice_id:
                    engine.setProperty("voice", voice_id)

                engine.setProperty("rate", 170)
                engine.setProperty("volume", 1.0)
                engine.say(clean)

                # External loop lets stop() interrupt from another thread.
                engine.startLoop(False)
                loop_started = True

                while engine.isBusy():
                    if self._stop_event.is_set():
                        engine.stop()
                        break
                    engine.iterate()
                    time.sleep(0.012)
            finally:
                try:
                    engine.stop()
                except Exception:
                    pass

                if loop_started:
                    try:
                        engine.endLoop()
                    except Exception:
                        pass

                self._speaking.clear()
                self._stop_event.clear()

    def test(self) -> None:
        self.speak(
            "Systèmes vocaux opérationnels. "
            "Je lirai désormais uniquement le contenu utile, H@CKERBOY.",
            avoid_wake_word=False,
        )

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def is_speaking(self) -> bool:
        return self._speaking.is_set()
