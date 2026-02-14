"""Parser for .po and .ts translation files."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto


class EntryState(Enum):
    TRANSLATED = auto()
    UNTRANSLATED = auto()
    FUZZY = auto()


@dataclass
class TranslationEntry:
    msgid: str
    msgstr: str
    state: EntryState
    context: str = ""
    comment: str = ""
    reference: str = ""
    # UI hint from comment or context
    ui_hint: str = ""  # "button", "menu", "dialog", "label", "tooltip"

    @property
    def is_truncated(self) -> bool:
        """Heuristic: translation significantly longer than source may truncate."""
        if not self.msgstr or not self.msgid:
            return False
        ratio = len(self.msgstr) / max(len(self.msgid), 1)
        if self.ui_hint == "button" and len(self.msgstr) > 20:
            return True
        if self.ui_hint == "menu" and len(self.msgstr) > 30:
            return True
        if ratio > 1.8 and len(self.msgstr) > 25:
            return True
        return False


def _guess_ui_hint(comment: str, context: str, msgid: str) -> str:
    """Guess what UI element a string belongs to."""
    text = (comment + " " + context).lower()
    if any(w in text for w in ("button", "btn", "_btn")):
        return "button"
    if any(w in text for w in ("menu", "menuitem", "action")):
        return "menu"
    if any(w in text for w in ("dialog", "message", "description")):
        return "dialog"
    if any(w in text for w in ("tooltip", "tip")):
        return "tooltip"
    if any(w in text for w in ("title", "header", "label")):
        return "label"
    # Guess from content
    if len(msgid) < 15 and not " " in msgid:
        return "button"
    if msgid.endswith("...") or msgid.endswith("…"):
        return "menu"
    if len(msgid) > 80:
        return "dialog"
    return "label"


def parse_po(path: str) -> list[TranslationEntry]:
    """Parse a .po file and return translation entries."""
    entries = []
    content = Path(path).read_text(encoding="utf-8", errors="replace")

    # Split into blocks separated by blank lines
    blocks = re.split(r"\n\n+", content)

    for block in blocks:
        if not block.strip():
            continue

        lines = block.strip().split("\n")
        msgid_parts = []
        msgstr_parts = []
        comments = []
        references = []
        msgctxt_parts = []
        is_fuzzy = False
        current = None

        for line in lines:
            if line.startswith("#,") and "fuzzy" in line:
                is_fuzzy = True
            elif line.startswith("#:"):
                references.append(line[2:].strip())
            elif line.startswith("#."):
                comments.append(line[2:].strip())
            elif line.startswith("#"):
                comments.append(line[1:].strip())
            elif line.startswith("msgctxt "):
                current = "msgctxt"
                msgctxt_parts.append(_unquote(line[8:]))
            elif line.startswith("msgid "):
                current = "msgid"
                msgid_parts.append(_unquote(line[6:]))
            elif line.startswith("msgstr "):
                current = "msgstr"
                msgstr_parts.append(_unquote(line[7:]))
            elif line.startswith('"') and current:
                val = _unquote(line)
                if current == "msgid":
                    msgid_parts.append(val)
                elif current == "msgstr":
                    msgstr_parts.append(val)
                elif current == "msgctxt":
                    msgctxt_parts.append(val)

        msgid = "".join(msgid_parts)
        msgstr = "".join(msgstr_parts)
        msgctxt = "".join(msgctxt_parts)
        comment = " ".join(comments)
        reference = ", ".join(references)

        if not msgid:  # Skip header
            continue

        if is_fuzzy:
            state = EntryState.FUZZY
        elif msgstr:
            state = EntryState.TRANSLATED
        else:
            state = EntryState.UNTRANSLATED

        hint = _guess_ui_hint(comment, msgctxt, msgid)

        entries.append(TranslationEntry(
            msgid=msgid,
            msgstr=msgstr,
            state=state,
            context=msgctxt,
            comment=comment,
            reference=reference,
            ui_hint=hint,
        ))

    return entries


def _unquote(s: str) -> str:
    """Remove quotes from a PO string value."""
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    s = s.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
    return s


def parse_ts(path: str) -> list[TranslationEntry]:
    """Parse a Qt .ts file and return translation entries."""
    entries = []
    tree = ET.parse(path)
    root = tree.getroot()

    for context_elem in root.iter("context"):
        ctx_name = ""
        name_elem = context_elem.find("name")
        if name_elem is not None and name_elem.text:
            ctx_name = name_elem.text

        for msg in context_elem.iter("message"):
            source_elem = msg.find("source")
            trans_elem = msg.find("translation")
            comment_elem = msg.find("comment")

            source = source_elem.text if source_elem is not None and source_elem.text else ""
            translation = ""
            is_unfinished = False

            if trans_elem is not None:
                is_unfinished = trans_elem.get("type") == "unfinished"
                translation = trans_elem.text or ""

            comment = comment_elem.text if comment_elem is not None and comment_elem.text else ""
            location = ""
            loc_elem = msg.find("location")
            if loc_elem is not None:
                filename = loc_elem.get("filename", "")
                line = loc_elem.get("line", "")
                location = f"{filename}:{line}" if filename else ""

            if is_unfinished and not translation:
                state = EntryState.UNTRANSLATED
            elif is_unfinished:
                state = EntryState.FUZZY
            elif translation:
                state = EntryState.TRANSLATED
            else:
                state = EntryState.UNTRANSLATED

            hint = _guess_ui_hint(comment, ctx_name, source)

            entries.append(TranslationEntry(
                msgid=source,
                msgstr=translation,
                state=state,
                context=ctx_name,
                comment=comment,
                reference=location,
                ui_hint=hint,
            ))

    return entries


def parse_file(path: str) -> list[TranslationEntry]:
    """Parse a .po or .ts file."""
    p = path.lower()
    if p.endswith(".po") or p.endswith(".pot"):
        return parse_po(path)
    elif p.endswith(".ts"):
        return parse_ts(path)
    else:
        raise ValueError(f"Unsupported file format: {path}")
