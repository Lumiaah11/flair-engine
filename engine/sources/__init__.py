"""Connecteurs de collecte. Chaque connecteur renvoie (offres, nombre_d_offres_lues)."""
from ..texte import identifiant


def offre(source, source_id, entreprise, titre, lieu, url, publiee="", description="",
          pays_iso="", vie=False, contrat="", teletravail=False):
    return {
        "id": identifiant(source, source_id or url),
        "source": source,
        "entreprise": (entreprise or "").strip(),
        "titre": (titre or "").strip(),
        "lieu": (lieu or "").strip(),
        "url": url or "",
        "publiee": (publiee or "")[:10] if publiee and str(publiee)[:4].isdigit() else (publiee or ""),
        "description": description or "",
        "pays_iso": (pays_iso or "").upper()[:2],
        "vie": bool(vie),
        "contrat": contrat or "",
        "teletravail": bool(teletravail),
    }
