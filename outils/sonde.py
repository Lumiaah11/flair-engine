"""Sonde ponctuelle (6e passage) : paramètres de recherche de Choisir le service public
(bloc ParamsDataSearch, filtre date de publication, filtres acceptés par /wp-json/api/offer-list).

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


def resume_liste(r):
    try:
        d = r.json()
        return {"statut": r.status_code, "titre": d.get("title"), "n": len(d.get("items") or []),
                "premiers": [(i.get("title"), i.get("publication_date")) for i in (d.get("items") or [])[:3]],
                "cles": [k for k in d.keys() if k != "items"]}
    except ValueError:
        return {"statut": r.status_code, "extrait": r.text[:300]}


def main():
    res = {}
    page = requests.get(CSP + "/nos-offres/filtres/mot-cles/strat%C3%A9gie/", headers=AGENT, timeout=30).text
    m = re.search(r"id='ParamsDataSearch' data-json='(.*?)'>", page, re.S)
    res["params_data_search"] = m.group(1)[:4000] if m else None
    res["date_publication"] = [page[max(0, x.start() - 400): x.end() + 600] for x in re.finditer(r"date-de-publication|date_de_publication", page)][:6]
    res["checkbox_dates"] = re.findall(r'data-slug="date[^"]*"[^>]*', page)[:10]
    essais = []
    corps_liste = [{"page": 2}, {"paged": 2}, {"mot-cles": "stratégie"}, {"mots-cles": "stratégie"}, {"keyword": "stratégie"},
                   {"q": "stratégie"}, {"query": "stratégie"}, {"s": "stratégie"}, {"filters": {"mot-cles": ["stratégie"]}},
                   {"motCles": "stratégie"}, {"keywords": ["stratégie"]}]
    for corps in corps_liste:
        time.sleep(0.5)
        r = requests.post(CSP + "/wp-json/api/offer-list", json=corps, headers={**AGENT, "Accept": "application/json"}, timeout=30)
        essais.append({"corps": corps, **resume_liste(r)})
    for qs in ("mot-cles=strat%C3%A9gie", "keywords=strat%C3%A9gie", "s=strat%C3%A9gie", "page=2"):
        time.sleep(0.5)
        r = requests.post(CSP + "/wp-json/api/offer-list?" + qs, json={}, headers={**AGENT, "Accept": "application/json"}, timeout=30)
        essais.append({"qs": qs, **resume_liste(r)})
    res["offer_list"] = essais
    with open(os.path.join(RACINE, "outils", "sonde_resultat.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
