"""Prépare l'import des offres du moteur dans la page Flair.

Usage :
  python3 outils/vers_flair.py --offres data/nouvelles.json --existantes DOSSIER --sortie DOSSIER [--seuil 55] [--max 150]
                               [--seuil-france 50] [--max-france 40]

- --offres : data/offres.json ou data/nouvelles.json du moteur (local ou téléchargé depuis GitHub).
- --existantes : dossier où ArtifactData a enregistré la collection « offers » de la page (out_dir), pour éviter les doublons.
- --sortie : dossier où écrire un fichier JSON par document, plus lots.json (lots de 50 identifiants).
- Les offres en France passent en premier, avec un seuil un peu plus bas, pour qu'elles ne soient jamais
  évincées par le plafond --max.
"""
import argparse
import glob
import json
import os
import re
import unicodedata

SOURCES = {
    "greenhouse": "Page carrière (Greenhouse)", "lever": "Page carrière (Lever)", "ashby": "Page carrière (Ashby)",
    "smartrecruiters": "Page carrière (SmartRecruiters)", "workable": "Page carrière (Workable)",
    "workday": "Page carrière (Workday)", "themuse": "The Muse", "adzuna": "Adzuna", "jooble": "Jooble",
    "iagora": "Liste VIE iAgora", "bnp_vie": "Page VIE BNP Paribas", "vie_bf": "Site VIE Business France",
    "france_travail": "France Travail", "recruitee": "Page carrière (Recruitee)",
    "teamtailor": "Page carrière (Teamtailor)", "service_public": "Choisir le service public",
}


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def norm_url(u):
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"[?#].*$", "", u) if "gh_jid=" not in u else u
    return u.rstrip("/")


def tronque(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    if len(s) <= n:
        return s
    coupe = s[:n]
    return coupe[:coupe.rfind(" ")] + "…" if " " in coupe else coupe + "…"


def charger_existantes(dossier):
    urls, couples, ids = set(), set(), set()
    if not dossier:
        return urls, couples, ids
    for f in glob.glob(os.path.join(dossier, "**", "*.json"), recursive=True):
        try:
            obj = json.load(open(f, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        doc = obj.get("data", obj) if isinstance(obj, dict) else {}
        ids.add(os.path.splitext(os.path.basename(f))[0])
        if doc.get("url"):
            urls.add(norm_url(doc["url"]))
        couples.add(norm(doc.get("entreprise")) + "|" + norm(doc.get("titre")))
    return urls, couples, ids


def vers_document(o):
    annees = o.get("annees_exp")
    lieu = (o.get("lieu") or "").split(";")[0].strip()
    return {
        "titre": o.get("titre", ""),
        "entreprise": o.get("entreprise", "") or "Entreprise sur la fiche",
        "ville": tronque(lieu, 60),
        "pays": o.get("pays", ""),
        "zone": o.get("zone", ""),
        "code": o.get("code", ""),
        "contrat": o.get("contrat", "") or "CDI",
        "famille": o.get("famille", ""),
        "url": o.get("url", ""),
        "source": SOURCES.get(o.get("source"), o.get("source", "")),
        "publiee": o.get("publiee", ""),
        "trouvee": o.get("premiere_vue", ""),
        "etat": "ouverte",
        "score": int(o.get("score_auto", 0)),
        "pourquoi": "",
        "extrait": tronque(o.get("extrait", ""), 1200),
        "drapeaux": (o.get("drapeaux") or [])[:4],
        "autorisation": o.get("autorisation", ""),
        "acces": "Contact ou alumni d'abord : en France, le tri sur l'école est fréquent." if o.get("zone") == "France" else "",
        "experience": (f"{annees} an demandé" if annees == 1 else f"{annees} ans demandés") if annees else "",
        "salaire": "",
        "statut": "nouveau",
        "notes": "",
        "revue": False,
        "moteur_id": o.get("id", ""),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--offres", required=True)
    p.add_argument("--existantes", default="")
    p.add_argument("--sortie", required=True)
    p.add_argument("--seuil", type=int, default=55)
    p.add_argument("--max", type=int, default=150)
    p.add_argument("--seuil-france", type=int, default=None, help="par défaut : seuil - 5")
    p.add_argument("--max-france", type=int, default=40)
    a = p.parse_args()
    seuil_fr = a.seuil_france if a.seuil_france is not None else a.seuil - 5

    offres = sorted(json.load(open(a.offres, encoding="utf-8")).get("offres", []), key=lambda x: -x.get("score_auto", 0))
    urls, couples, ids = charger_existantes(a.existantes)
    os.makedirs(os.path.join(a.sortie, "docs"), exist_ok=True)
    retenus, compte = [], {"doublons": 0, "sous_seuil": 0, "france": 0}

    def essayer(o, seuil):
        if o.get("score_auto", 0) < seuil:
            compte["sous_seuil"] += 1
            return False
        doc_id = "e-" + o.get("id", "")
        cle = norm(o.get("entreprise")) + "|" + norm(o.get("titre"))
        if doc_id in ids or norm_url(o.get("url")) in urls or cle in couples:
            compte["doublons"] += 1
            return False
        couples.add(cle)
        urls.add(norm_url(o.get("url")))
        with open(os.path.join(a.sortie, "docs", doc_id + ".json"), "w", encoding="utf-8") as f:
            json.dump(vers_document(o), f, ensure_ascii=False)
        retenus.append((o.get("score_auto", 0), doc_id))
        return True

    for o in (x for x in offres if x.get("zone") == "France"):
        if compte["france"] >= a.max_france:
            break
        if essayer(o, seuil_fr):
            compte["france"] += 1
    for o in (x for x in offres if x.get("zone") != "France"):
        if len(retenus) >= a.max:
            break
        essayer(o, a.seuil)
    ordre = [d for _, d in sorted(retenus, key=lambda x: -x[0])]
    lots = [ordre[i:i + 50] for i in range(0, len(ordre), 50)]
    json.dump({"lots": lots, "total": len(ordre), "france": compte["france"]}, open(os.path.join(a.sortie, "lots.json"), "w"))
    print(f"À importer : {len(ordre)} (dont France : {compte['france']}) · doublons ignorés : {compte['doublons']} · "
          f"sous le seuil : {compte['sous_seuil']} · lots : {len(lots)}")


if __name__ == "__main__":
    main()
