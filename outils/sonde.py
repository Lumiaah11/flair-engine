"""Sonde ponctuelle (2e passage) : structure de Choisir le service public, flux RSS de la PEP,
et cabinets de conseil français sur Personio, Breezy, Teamtailor et Recruitee.

Lancée par .github/workflows/sonde.yml, elle écrit outils/sonde_resultat.json.
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
from engine import geo  # noqa: E402
from engine.filtres import titre_retenu  # noqa: E402

AGENT = {"User-Agent": "FlairBot/1.0 (veille d'offres personnelle; contact via GitHub)"}
CSP = "https://choisirleservicepublic.gouv.fr"

CABINETS = """
kea kea-partners keapartners kea-and-partners eleven eleven-strategy elevenstrategy estin estin-co estinco
mawenzi mawenzi-partners circle-strategy circlestrategy bartle cva cvagroup corporate-value-associates indefi
accuracy eight-advisory eightadvisory advancy ares-co aresandco a2-consulting opeo argon argon-co onepoint
converteo vertone equancy colombus colombus-consulting square-management squaremanagement magellan-consulting
headmind-partners oresys bluestone citwell alcimed advention nextep partners-and-co cylad ylios c-level clevel
greenflex carbone4 eurogroup eurogroup-consulting wavestone sia-partners siapartners la-javaness quantmetry
emerton bain-paris roland-berger simon-kucher kurt-salmon ac-and-partners mckinsey bcg kearney lek
strategy-and monitor-deloitte ey-parthenon alvarez-marsal finexsi ledger qonto alan swile pennylane
""".split()


def appel(url, **kw):
    time.sleep(0.3)
    return requests.get(url, headers=AGENT, timeout=20, **kw)


def resume(postes):
    cibles = [(t, l) for t, l in postes if titre_retenu(t, True)]
    fr = [p for p in postes if "FR" in geo.pays_detectes(p[1] or "")]
    return {"total": len(postes), "en_france": len(fr), "cibles": len(cibles),
            "exemples": [f"{t} | {l}" for t, l in cibles[:5]] or [f"{t} | {l}" for t, l in postes[:3]]}


def personio(slug):
    for dom in ("jobs.personio.de", "jobs.personio.com"):
        r = appel(f"https://{slug}.{dom}/xml", params={"language": "fr"})
        if r.status_code == 200 and "<position" in r.text:
            postes = [(re.search(r"<name>(.*?)</name>", p, re.S).group(1) if "<name>" in p else "",
                       (re.search(r"<office>(.*?)</office>", p, re.S) or re.search(r"()", "")).group(1))
                      for p in re.findall(r"<position>(.*?)</position>", r.text, re.S)]
            return resume(postes)
    return None


def breezy(slug):
    r = appel(f"https://{slug}.breezy.hr/json")
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    return resume([(p.get("name", ""), ((p.get("location") or {}).get("name") or "")) for p in data])


def teamtailor(slug):
    r = appel(f"https://{slug}.teamtailor.com/jobs.rss")
    if r.status_code != 200 or "<item" not in r.text:
        return None
    titres = re.findall(r"<item>.*?<title>(.*?)</title>", r.text, re.S)
    return resume([(re.sub(r"<!\[CDATA\[|\]\]>", "", t), "") for t in titres])


def recruitee(slug):
    r = appel(f"https://{slug}.recruitee.com/api/offers/")
    if r.status_code != 200:
        return None
    try:
        return resume([(o.get("title", ""), o.get("location") or "") for o in r.json().get("offers", [])])
    except ValueError:
        return None


def sonder(nom, fn):
    trouves = {}
    for s in CABINETS:
        try:
            v = fn(s)
        except Exception as err:  # noqa: BLE001
            v = {"erreur": f"{type(err).__name__}: {str(err)[:100]}"}
        if v is not None:
            trouves[s] = v
    return nom, trouves


def autour(texte, motif, n=8, avant=150, apres=350):
    sorties = []
    for m in re.finditer(motif, texte, re.I):
        sorties.append(texte[max(0, m.start() - avant): m.end() + apres])
        if len(sorties) >= n:
            break
    return sorties


def service_public():
    res = {}
    r = appel(CSP + "/nos-offres/filtres/mot-cles/strat%C3%A9gie/")
    page = r.text
    res["p1_statut"] = r.status_code
    res["p1_titres"] = [re.sub(r"\s+", " ", t).strip() for t in re.findall(r'href="https://choisirleservicepublic\.gouv\.fr/offre-emploi/[^"]+"[^>]*>(.*?)</a>', page, re.S)][:20]
    res["p1_tri"] = autour(page, r"trier|orderby|order_by|tri-|sort", 6)
    res["p1_contractuels"] = autour(page, r"contractu", 6)
    res["p1_categorie"] = autour(page, r"cat[ée]gorie A", 4)
    res["p1_pagination"] = autour(page, r'rel="next"|/page/2|paged=2|pagination', 6)
    res["p1_formulaire"] = autour(page, r"<form", 3, 50, 1200)
    for nom, url in [("p2_chemin", CSP + "/nos-offres/filtres/mot-cles/strat%C3%A9gie/page/2/"),
                     ("p2_param", CSP + "/nos-offres/filtres/mot-cles/strat%C3%A9gie/?paged=2")]:
        try:
            r2 = appel(url)
            res[nom] = {"statut": r2.status_code, "titres": [re.sub(r"\s+", " ", t).strip() for t in re.findall(
                r'href="https://choisirleservicepublic\.gouv\.fr/offre-emploi/[^"]+"[^>]*>(.*?)</a>', r2.text, re.S)][:5]}
        except Exception as err:  # noqa: BLE001
            res[nom] = f"erreur {err}"
    lien = re.search(r'href="(https://choisirleservicepublic\.gouv\.fr/offre-emploi/[^"]+)"', page)
    if lien:
        d = appel(lien.group(1))
        fiche = d.text
        res["fiche_url"] = lien.group(1)
        res["fiche_statut"] = d.status_code
        res["fiche_jsonld"] = re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', fiche, re.S)[:2]
        i = fiche.find("<main")
        corps = re.sub(r"<[^>]+>", " ", fiche[i:i + 60000])
        res["fiche_texte"] = re.sub(r"\s+", " ", corps)[:6000]
    try:
        rss = appel("https://place-ep-recrute.talent-soft.com//offre-de-emploi/tous-les-flux-rss.aspx")
        res["pep_rss_statut"] = rss.status_code
        res["pep_rss_liens"] = re.findall(r'href="([^"]*rss[^"]*)"', rss.text, re.I)[:30]
    except Exception as err:  # noqa: BLE001
        res["pep_rss"] = f"erreur {err}"
    return res


def main():
    resultat = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futurs = [pool.submit(sonder, n, f) for n, f in
                  [("personio", personio), ("breezy", breezy), ("teamtailor", teamtailor), ("recruitee", recruitee)]]
        f_csp = pool.submit(service_public)
        for f in futurs:
            nom, trouves = f.result()
            resultat[nom] = trouves
        resultat["choisir_service_public"] = f_csp.result()
    with open(os.path.join(RACINE, "outils", "sonde_resultat.json"), "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
