"""Sonde ponctuelle (4e passage) : routes de l'API « api » de Choisir le service public
et balises de lieu des flux RSS Teamtailor.

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
    r = appel(CSP + "/wp-json/api")
    res["api_statut"] = r.status_code
    try:
        routes = r.json().get("routes", {})
        res["api_routes"] = {k: [e.get("methods") for e in v.get("endpoints", [])] for k, v in routes.items()}
        res["api_args"] = {k: [list((e.get("args") or {}).keys()) for e in v.get("endpoints", [])] for k, v in routes.items()}
    except ValueError:
        res["api_extrait"] = r.text[:3000]
    page = appel(CSP + "/nos-offres/filtres/mot-cles/strat%C3%A9gie/").text
    res["scripts"] = re.findall(r'<script[^>]+src="([^"]+)"', page)[:40]
    res["ajax"] = [page[max(0, m.start() - 200): m.end() + 300] for m in re.finditer(r"ajax|wp-json|data-url|data-endpoint", page)][:12]
    for slug in ("converteo", "indefi"):
        t = appel(f"https://{slug}.teamtailor.com/jobs.rss").text
        items = re.findall(r"<item>(.*?)</item>", t, re.S)
        res["tt_" + slug] = [re.sub(r"<description>.*?</description>", "<description/>", i, flags=re.S)[:1500] for i in items[:3]]
    with open(os.path.join(RACINE, "outils", "sonde_resultat.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
