"""Sonde ponctuelle (5e passage) : comment la page de recherche de Choisir le service public
récupère ses résultats (script du thème), et réponse de la route /wp-json/api/offer-list.

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


def main():
    res = {}
    js = requests.get(CSP + "/wp-content/themes/biep/assets/js/app.js", headers=AGENT, timeout=30).text
    res["js_taille"] = len(js)
    extraits = []
    for m in re.finditer(r"offer-list|admin-ajax|wp_ajax_url|action\s*[:=]\s*['\"][a-z_]+|wp-json|fetch\(|\.post\(|ajax\(", js):
        extraits.append(js[max(0, m.start() - 300): m.end() + 500])
        if len(extraits) >= 25:
            break
    res["js_extraits"] = extraits
    res["js_actions"] = sorted(set(re.findall(r"action['\"]?\s*[:=,]\s*['\"]([a-zA-Z_]+)['\"]", js)))[:60]
    essais = []
    for corps in ({}, {"keywords": "stratégie"}, {"motsCles": "stratégie", "page": 1}, {"search": "stratégie"}):
        time.sleep(0.5)
        try:
            r = requests.post(CSP + "/wp-json/api/offer-list", json=corps, headers={**AGENT, "Accept": "application/json"}, timeout=30)
            essais.append({"corps": corps, "statut": r.status_code, "extrait": r.text[:1500]})
        except Exception as err:  # noqa: BLE001
            essais.append({"corps": corps, "erreur": str(err)})
    res["offer_list"] = essais
    with open(os.path.join(RACINE, "outils", "sonde_resultat.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
