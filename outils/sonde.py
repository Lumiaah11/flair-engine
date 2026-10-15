"""Sonde ponctuelle (3e passage) : plan du site de Choisir le service public (sitemaps, API WordPress)
et structure des flux RSS Teamtailor (Converteo, Indefi).

Lancée par .github/workflows/sonde.yml, elle écrit outils/sonde_resultat.json.
"""
import json
import os
import re
import time

import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = {"User-Agent": "FlairBot/1.0 (veille d'offres personnelle; contact via GitHub)"}
CSP = "https://choisirleservicepublic.gouv.fr"


def appel(url, **kw):
    time.sleep(0.4)
    return requests.get(url, headers=AGENT, timeout=30, **kw)


def main():
    res = {}
    r = appel(CSP + "/sitemapindex.xml")
    res["index_statut"] = r.status_code
    res["index"] = r.text[:4000]
    plans = re.findall(r"<loc>(.*?)</loc>", r.text)
    res["plans"] = plans[:60]
    offres = [p for p in plans if "offre" in p.lower()]
    res["plans_offres"] = offres[:20]
    for p in offres[:2]:
        d = appel(p)
        res.setdefault("plans_offres_detail", []).append({
            "url": p, "statut": d.status_code, "taille": len(d.text), "nb_url": d.text.count("<url>"),
            "debut": d.text[:1500], "fin": d.text[-800:]})
    for chemin in ("/wp-json/wp/v2/types", "/wp-json/"):
        try:
            w = appel(CSP + chemin)
            res["wp" + chemin.replace("/", "_")] = {"statut": w.status_code, "extrait": w.text[:2500]}
        except Exception as err:  # noqa: BLE001
            res["wp" + chemin.replace("/", "_")] = f"erreur {err}"
    for slug in ("converteo", "indefi"):
        t = appel(f"https://{slug}.teamtailor.com/jobs.rss")
        items = re.findall(r"<item>(.*?)</item>", t.text, re.S)
        res["teamtailor_" + slug] = {"statut": t.status_code, "entete": t.text[:1200], "items": len(items),
                                     "premier": items[0][:3000] if items else ""}
    with open(os.path.join(RACINE, "outils", "sonde_resultat.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
