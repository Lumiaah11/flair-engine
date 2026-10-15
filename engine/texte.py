"""Petits utilitaires de texte."""
import hashlib
import html
import re
import unicodedata

_BALISES = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"[ \t\r\f\v]+")
_LIGNES = re.compile(r"\n\s*\n+")


def html_vers_texte(contenu):
    if not contenu:
        return ""
    t = html.unescape(str(contenu))
    t = re.sub(r"(?i)<\s*(br|/p|/li|/div|/h\d)\s*/?>", "\n", t)
    t = re.sub(r"(?i)<\s*li[^>]*>", "\n- ", t)
    t = _BALISES.sub(" ", t)
    t = html.unescape(t)
    t = _ESPACES.sub(" ", t)
    t = _LIGNES.sub("\n", t)
    return t.strip()


def sans_accents(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def normalise(s):
    s = sans_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def tronque(s, n=1200):
    s = s or ""
    if len(s) <= n:
        return s
    coupe = s[:n]
    espace = coupe.rfind(" ")
    return (coupe[:espace] if espace > n * 0.8 else coupe) + "…"


def identifiant(*morceaux):
    brut = "|".join(str(m or "") for m in morceaux)
    return hashlib.sha1(brut.encode("utf-8")).hexdigest()[:16]
