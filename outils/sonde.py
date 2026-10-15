"""Sonde ponctuelle : quelles entreprises françaises publient sur un logiciel de recrutement lisible,
et l'APEC ou Choisir le service public sont-ils lisibles proprement ?

Lancée par .github/workflows/sonde.yml, elle écrit outils/sonde_resultat.json.
Elle ne lit que des listes d'offres publiques, une requête à la fois par site.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
from engine import geo  # noqa: E402
from engine.filtres import titre_retenu  # noqa: E402

AGENT = {"User-Agent": "FlairBot/1.0 (veille d'offres personnelle; contact via GitHub)"}

SLUGS = """
qonto alan alanhealth doctolib backmarket payfit swile spendesk pennylane agicap malt vestiairecollective
manomano deezer photoroom lydia sumeria shifttechnology shift-technology exotec akeneo brevo sendinblue botify
didomi yousign voodoo getaround ornikar swan upflow ovhcloud believe dailymotion contentsquare mirakl criteo
algolia ledger sorare ankorstore younited libeo side ivalua dashlane withings owkin padoa jellysmack leboncoin
adevinta welcometothejungle jobteaser openclassrooms 360learning dilitrust hexa sezane hivebrite skello partoo
memobank shine luko leocare treezor zenchef staffme brigad stuart ynsect sundayapp heetch lemonway mooncard
meero jow deepki electra iziwork moniteur pigment alma lucca payplug cooltra vulog hiflow ector everoad
zenpark sunday nabla huggingface poolside h-company hcompany dust kyutai gladia lightonai lighton mistral
artefact siapartners sia-partners wavestone eleven elevenstrategy kea keaandpartners advancy estin mawenzi
circlestrategy bartle cva corporatevalueassociates indefi accuracy eightadvisory eight-advisory alixpartners
rolandberger roland-berger strategyand bearingpoint julhiet julhietsterwen colombusconsulting squaremanagement
magellanpartners headmind onepoint converteo fabernovel octo theodo talan devoteam sopra-steria dalberg
ardian eurazeo tikehau tikehaucapital partech bpifrance keensight astorg paigroup wendel isai elaia alven
kima frst serena idinvest raise raisegroup
""".split()

SMARTRECRUITERS = """
PublicisGroupe Publicis Sodexo Accor AccorHotels Decathlon Veolia Edenred Ipsos Capgemini SopraSteria
Wavestone SiaPartners Devoteam Keyrus Kering LOreal Danone PernodRicard Servier Valeo Forvia Atos Eviden
BureauVeritas Bic Lagardere LagardereTravelRetail Vivendi CanalPlus Havas Ayvens Arval BNPParibas
SocieteGenerale Natixis Amundi AXA Coface SchneiderElectric Legrand Nexans SaintGobain Alstom Safran
DassaultSystemes Orange Bouygues Vinci Eiffage Engie EDF TotalEnergies AirLiquide Carrefour Auchan FnacDarty
Renault RenaultGroup Stellantis Hermes Chanel LVMH Sephora Lacoste Clarins PierreFabre Ipsen Biomerieux
Getlink AirFranceKLM Transdev Keolis Elior Lactalis GroupeBel Roquette Tereos Avril Generali CNPAssurances
Groupama Worldline Teleperformance Vallourec Arkema Imerys Eramet Orano Framatome NavalGroup MBDA ArianeGroup
CMACGM Geodis GroupeRocher Equans Ubisoft2 Believe Criteo Contentsquare Mirakl Doctolib Qonto Alan
""".split()


def lieu_fr(lieu, iso=""):
    return (iso or "").upper() == "FR" or "FR" in geo.pays_detectes(lieu or "")


def resume(postes):
    """postes : liste de (titre, lieu, iso)."""
    cibles = [(t, l) for t, l, i in postes if titre_retenu(t)]
    cibles_fr = [(t, l) for t, l, i in postes if titre_retenu(t) and lieu_fr(l, i)]
    return {
        "total": len(postes),
        "en_france": sum(1 for t, l, i in postes if lieu_fr(l, i)),
        "cibles": len(cibles),
        "cibles_france": len(cibles_fr),
        "exemples": [f"{t} | {l}" for t, l in (cibles_fr + cibles)[:6]],
    }


def appel(url, **kw):
    time.sleep(0.3)
    return requests.get(url, headers=AGENT, timeout=20, **kw)


def greenhouse(slug):
    r = appel(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if r.status_code != 200:
        return None
    return [(j.get("title", ""), (j.get("location") or {}).get("name", ""), "") for j in r.json().get("jobs", [])]


def lever(slug):
    for base in ("https://api.lever.co/v0/postings/", "https://api.eu.lever.co/v0/postings/"):
        r = appel(base + slug, params={"mode": "json"})
        if r.status_code == 200:
            postes = []
            for j in r.json():
                cats = j.get("categories") or {}
                lieux = "; ".join(dict.fromkeys(x for x in [cats.get("location") or ""] + list(cats.get("allLocations") or []) if x))
                postes.append((j.get("text", ""), lieux, j.get("country") or ""))
            return postes
    return None


def ashby(slug):
    r = appel(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if r.status_code != 200:
        return None
    postes = []
    for j in r.json().get("jobs", []):
        lieux = [j.get("location") or ""] + [s.get("location") or "" for s in j.get("secondaryLocations") or []]
        pays = (((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or "")
        postes.append((j.get("title", ""), "; ".join(x for x in lieux + [pays] if x), ""))
    return postes


def workable(slug):
    r = appel(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    if r.status_code != 200:
        return None
    return [(j.get("title", ""), ", ".join(x for x in [j.get("city"), j.get("country")] if x), "")
            for j in r.json().get("jobs", [])]


def recruitee(slug):
    r = appel(f"https://{slug}.recruitee.com/api/offers/")
    if r.status_code != 200:
        return None
    try:
        offres = r.json().get("offers", [])
    except ValueError:
        return None
    return [(o.get("title", ""), o.get("location") or "", o.get("country_code") or "") for o in offres]


def smartrecruiters(cid):
    r = appel(f"https://api.smartrecruiters.com/v1/companies/{cid}/postings", params={"limit": 100})
    if r.status_code != 200:
        return None
    data = r.json()
    if not data.get("totalFound"):
        return None
    postes = []
    for it in data.get("content", []):
        loc = it.get("location") or {}
        postes.append((it.get("name", ""), ", ".join(x for x in [loc.get("city"), loc.get("country")] if x), loc.get("country") or ""))
    rfr = appel(f"https://api.smartrecruiters.com/v1/companies/{cid}/postings", params={"limit": 100, "country": "fr"})
    fr = []
    if rfr.status_code == 200:
        for it in rfr.json().get("content", []):
            loc = it.get("location") or {}
            fr.append((it.get("name", ""), ", ".join(x for x in [loc.get("city"), loc.get("country")] if x), loc.get("country") or ""))
    res = resume(postes + [p for p in fr if p not in postes])
    res["total_annonce"] = data.get("totalFound")
    res["total_france_annonce"] = (rfr.json() or {}).get("totalFound") if rfr.status_code == 200 else None
    return res


def sonder(nom, fn, slugs):
    trouves = {}
    for s in slugs:
        try:
            postes = fn(s)
        except Exception as err:  # noqa: BLE001
            trouves[s] = {"erreur": f"{type(err).__name__}: {str(err)[:120]}"}
            continue
        if postes is None:
            continue
        trouves[s] = postes if isinstance(postes, dict) else resume(postes)
    return nom, trouves


def apec():
    res = {}
    try:
        res["robots"] = appel("https://www.apec.fr/robots.txt").text[:3000]
    except Exception as err:  # noqa: BLE001
        res["robots"] = f"erreur {err}"
    corps = {
        "lieux": [], "fonctions": [], "statutPoste": [], "typesContrat": [], "typesConvention": [],
        "niveauxExperience": [], "idsEtablissement": [], "secteursActivite": [], "typesTeletravail": [],
        "idNomZonesDeplacement": [], "positionNumbersExcluded": [], "typeClient": "CADRE",
        "sorts": [{"type": "DATE", "direction": "DESCENDING"}],
        "pagination": {"range": 20, "startIndex": 0}, "activeFiltre": True,
        "pointGeolocDeReference": {"distance": 0}, "motsCles": "chief of staff",
    }
    try:
        time.sleep(0.5)
        r = requests.post("https://www.apec.fr/cms/webservices/rechercheOffre", json=corps,
                          headers={**AGENT, "Accept": "application/json"}, timeout=25)
        res["recherche_statut"] = r.status_code
        res["recherche_extrait"] = r.text[:4000]
        if r.status_code == 200:
            data = r.json()
            res["recherche_cles"] = list(data.keys())
            items = data.get("resultats") or []
            res["recherche_nb"] = len(items)
            res["recherche_total"] = data.get("totalCount")
            if items:
                res["premier"] = items[0]
                num = items[0].get("numeroOffre")
                time.sleep(0.5)
                d = requests.get("https://www.apec.fr/cms/webservices/offre/public", params={"numeroOffre": num},
                                 headers={**AGENT, "Accept": "application/json"}, timeout=25)
                res["detail_statut"] = d.status_code
                res["detail_extrait"] = d.text[:5000]
    except Exception as err:  # noqa: BLE001
        res["recherche_erreur"] = f"{type(err).__name__}: {err}"
    return res


def service_public():
    res = {}
    for nom, url in [("robots", "https://choisirleservicepublic.gouv.fr/robots.txt"),
                     ("liste", "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/mot-cles/strat%C3%A9gie/")]:
        try:
            r = appel(url)
            res[nom + "_statut"] = r.status_code
            texte = r.text
            if nom == "liste":
                i = texte.find("offre")
                res["liste_taille"] = len(texte)
                res["liste_liens_offre"] = texte.count("/offre-emploi/")
                j = texte.find("/offre-emploi/")
                res["liste_extrait"] = texte[max(0, j - 2500): j + 2500] if j >= 0 else texte[i: i + 3000]
            else:
                res[nom] = texte[:2000]
        except Exception as err:  # noqa: BLE001
            res[nom + "_erreur"] = f"{type(err).__name__}: {err}"
    return res


def main():
    taches = [("greenhouse", greenhouse, SLUGS), ("lever", lever, SLUGS), ("ashby", ashby, SLUGS),
              ("workable", workable, SLUGS), ("recruitee", recruitee, SLUGS),
              ("smartrecruiters", smartrecruiters, SMARTRECRUITERS)]
    resultat = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futurs = [pool.submit(sonder, n, f, s) for n, f, s in taches]
        f_apec = pool.submit(apec)
        f_csp = pool.submit(service_public)
        for f in futurs:
            nom, trouves = f.result()
            resultat[nom] = trouves
        resultat["apec"] = f_apec.result()
        resultat["choisir_service_public"] = f_csp.result()
    with open(os.path.join(RACINE, "outils", "sonde_resultat.json"), "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=1)
    for nom in ("greenhouse", "lever", "ashby", "workable", "recruitee", "smartrecruiters"):
        print(nom, len(resultat[nom]), "comptes trouvés")


if __name__ == "__main__":
    main()
