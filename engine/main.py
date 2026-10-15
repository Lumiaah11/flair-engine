"""Collecte nocturne de Flair.

Lit les sources, garde les offres strat hors France qui passent la grille,
et écrit data/offres.json, data/nouvelles.json, data/stats.json et data/rejets.json.
"""
import json
import os
import sys
import traceback
from collections import Counter
from datetime import date, datetime, timezone

from . import filtres
from .filtres import analyse, cle_doublon, titre_retenu
from .sources.agregateurs import AGREGATEURS
from .sources.ats import CONNECTEURS
from .texte import tronque

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RACINE, "data")
CONFIG = os.path.join(RACINE, "config")


def lire_json(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def ecrire_json(chemin, contenu):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False, indent=1)


def collecter(entreprises, agregateurs, seule=None):
    brutes, stats = [], {}
    for e in entreprises:
        if seule and e["nom"] != seule:
            continue
        if e.get("actif") is False:
            continue
        fn = CONNECTEURS.get(e.get("ats"))
        nom = f"{e['nom']} ({e.get('ats')})"
        if not fn:
            stats[nom] = {"statut": "erreur", "message": "connecteur inconnu"}
            continue
        doit = (e.get("titre_doit_contenir") or "").lower()
        retenir = (lambda t, c=(e.get("type") == "conseil"), d=doit: (not d or d in (t or "").lower()) and titre_retenu(t, c))
        try:
            offres, lues = fn(e, retenir)
            for o in offres:
                o["_info"] = e
            brutes.extend(offres)
            stats[nom] = {"statut": "ok", "lues": lues, "titres_retenus": len(offres)}
        except Exception as err:  # une source en échec ne bloque pas les autres
            stats[nom] = {"statut": "erreur", "message": f"{type(err).__name__}: {str(err)[:180]}"}
    for cle, cfg in (agregateurs or {}).items():
        if seule:
            break
        if not cfg.get("actif", True):
            stats[cle] = {"statut": "désactivé"}
            continue
        fn = AGREGATEURS.get(cle)
        try:
            offres, lues = fn(cfg, titre_retenu)
            info = {"nom": cle, "niveau": cfg.get("niveau_employeur", 5), "type": "agregateur"}
            for o in offres:
                o["_info"] = info
            brutes.extend(offres)
            stats[cle] = {"statut": "ok", "lues": lues, "titres_retenus": len(offres)}
            if cfg.get("_debug"):
                stats[cle]["debug"] = cfg.pop("_debug")
        except Exception as err:
            stats[cle] = {"statut": "erreur", "message": f"{type(err).__name__}: {str(err)[:180]}"}
    return brutes, stats


def main(argv=None):
    argv = argv or sys.argv[1:]
    seule = argv[argv.index("--seule") + 1] if "--seule" in argv else None
    aujourd_hui = date.today().isoformat()
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")

    entreprises = lire_json(os.path.join(CONFIG, "entreprises.json"), [])
    agregateurs = lire_json(os.path.join(CONFIG, "agregateurs.json"), {})
    reglages = lire_json(os.path.join(CONFIG, "reglages.json"), {})
    seuil = reglages.get("seuil_score", 45)
    filtres.INCLURE_FRANCE = reglages.get("inclure_france", True)

    brutes, stats = collecter(entreprises, agregateurs, seule)

    gardees, rejets, raisons = {}, [], Counter()
    for o in brutes:
        info = o.pop("_info", {})
        resultat, raison = analyse(o, info)
        if not resultat:
            raisons[raison] += 1
            if len(rejets) < 400:
                rejets.append({"titre": o.get("titre"), "entreprise": o.get("entreprise"), "lieu": o.get("lieu"),
                               "raison": raison, "url": o.get("url"), "source": o.get("source")})
            continue
        if resultat["score_auto"] < seuil:
            raisons[f"score < {seuil}"] += 1
            continue
        resultat["extrait"] = tronque(resultat.pop("description", ""), 1200)
        cle = cle_doublon(resultat)
        precedent = gardees.get(cle)
        if precedent is None or resultat["score_auto"] > precedent["score_auto"] or (
                precedent["source"] in AGREGATEURS and resultat["source"] not in AGREGATEURS):
            gardees[cle] = resultat

    # Fusion avec la collecte précédente : date de première vue, retrait des offres fermées.
    ancien = lire_json(os.path.join(DATA, "offres.json"), {}).get("offres", [])
    anciens_par_id = {o["id"]: o for o in ancien}
    sources_en_erreur = {k.split(" (")[0] for k, v in stats.items() if v.get("statut") == "erreur"}
    jours_max = reglages.get("jours_agregateurs", 14)
    finales = {}
    for o in gardees.values():
        a = anciens_par_id.get(o["id"])
        o["premiere_vue"] = a["premiere_vue"] if a else aujourd_hui
        o["derniere_vue"] = aujourd_hui
        finales[o["id"]] = o
    for a in ancien:
        if a["id"] in finales:
            continue
        age = (date.fromisoformat(aujourd_hui) - date.fromisoformat(a.get("premiere_vue", aujourd_hui))).days
        if a.get("source") in AGREGATEURS and age <= jours_max:
            finales[a["id"]] = a
        elif a.get("entreprise") in sources_en_erreur or a.get("source") in sources_en_erreur:
            finales[a["id"]] = a

    liste = sorted(finales.values(), key=lambda o: o.get("premiere_vue", ""), reverse=True)
    liste.sort(key=lambda o: -o["score_auto"])
    nouvelles = [o for o in liste if o.get("premiere_vue") == aujourd_hui]

    ecrire_json(os.path.join(DATA, "offres.json"), {"maj": maintenant, "total": len(liste), "offres": liste})
    ecrire_json(os.path.join(DATA, "nouvelles.json"), {"maj": maintenant, "date": aujourd_hui, "total": len(nouvelles), "offres": nouvelles})
    ok = sum(1 for v in stats.values() if v.get("statut") == "ok")
    ecrire_json(os.path.join(DATA, "stats.json"), {
        "maj": maintenant,
        "compteurs": {"sources_ok": ok, "sources_en_erreur": len(sources_en_erreur), "titres_retenus": len(brutes),
                      "offres_gardees": len(liste), "nouvelles": len(nouvelles),
                      "offres_lues": sum(v.get("lues", 0) for v in stats.values())},
        "rejets_par_raison": dict(raisons.most_common()),
        "sources": stats,
    })
    ecrire_json(os.path.join(DATA, "rejets.json"), {"maj": maintenant, "rejets": rejets})
    print(f"Sources OK : {ok}/{len(stats)} · lues : {sum(v.get('lues', 0) for v in stats.values())} · "
          f"titres retenus : {len(brutes)} · gardées : {len(liste)} · nouvelles : {len(nouvelles)}")
    for k, v in stats.items():
        if v.get("statut") == "erreur":
            print(f"  ERREUR {k} : {v.get('message')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
