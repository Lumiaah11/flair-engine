"""Agrégateurs (Adzuna, Jooble, The Muse) et VIE Business France."""
import os

from ..http import get_json, post_json
from ..texte import html_vers_texte
from . import offre


def adzuna(cfg, retenir):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError("clés Adzuna absentes (ADZUNA_APP_ID, ADZUNA_APP_KEY)")
    res, total = [], 0
    for pays in cfg.get("pays", []):
        for q in cfg.get("requetes", []):
            data = get_json(f"https://api.adzuna.com/v1/api/jobs/{pays}/search/1", params={
                "app_id": app_id, "app_key": app_key, "results_per_page": 50, "title_only": q,
                "max_days_old": cfg.get("max_days_old", 3), "content-type": "application/json"})
            items = data.get("results", []) or []
            total += len(items)
            for it in items:
                titre = html_vers_texte(it.get("title", ""))
                if not retenir(titre):
                    continue
                loc = it.get("location") or {}
                lieu = ", ".join(reversed(loc.get("area") or [])) or loc.get("display_name", "")
                res.append(offre("adzuna", it.get("id"), (it.get("company") or {}).get("display_name", ""), titre, lieu,
                                 it.get("redirect_url"), (it.get("created") or "")[:10],
                                 html_vers_texte(it.get("description", "")), pays_iso=pays.upper().replace("GB", "GB"),
                                 contrat=it.get("contract_type") or ""))
    return res, total


def jooble(cfg, retenir):
    cle = os.environ.get("JOOBLE_KEY")
    if not cle:
        raise RuntimeError("clé Jooble absente (JOOBLE_KEY)")
    res, total = [], 0
    for lieu_q in cfg.get("lieux", []):
        for q in cfg.get("requetes", []):
            data = post_json(f"https://jooble.org/api/{cle}", {"keywords": q, "location": lieu_q, "page": "1"})
            items = data.get("jobs", []) or []
            total += len(items)
            for it in items:
                titre = html_vers_texte(it.get("title", ""))
                if not retenir(titre):
                    continue
                res.append(offre("jooble", it.get("id"), it.get("company", ""), titre, it.get("location") or lieu_q,
                                 it.get("link"), (it.get("updated") or "")[:10], html_vers_texte(it.get("snippet", ""))))
    return res, total


def themuse(cfg, retenir):
    res, total = [], 0
    for categorie in cfg.get("categories", []):
        for page in range(cfg.get("pages", 5)):
            params = [("page", page), ("descending", "true"), ("category", categorie)]
            params += [("level", n) for n in cfg.get("niveaux", ["Entry Level", "Mid Level"])]
            data = get_json("https://www.themuse.com/api/public/jobs", params=params)
            items = data.get("results", []) or []
            total += len(items)
            for it in items:
                titre = it.get("name", "")
                if not retenir(titre):
                    continue
                lieu = "; ".join(l.get("name", "") for l in it.get("locations") or [])
                res.append(offre("themuse", it.get("id"), (it.get("company") or {}).get("name", ""), titre, lieu,
                                 (it.get("refs") or {}).get("landing_page"), (it.get("publication_date") or "")[:10],
                                 html_vers_texte(it.get("contents", ""))))
            if page + 1 >= (data.get("page_count") or 0):
                break
    return res, total


def _premier(d, *cles):
    for c in cles:
        v = d.get(c)
        if v:
            return v
    return ""


def vie_business_france(cfg, retenir):
    """Offres VIE du site officiel (API interne du site Mon Volontariat International)."""
    url = cfg.get("url", "https://civiweb-api-prd.azurewebsites.net/api/Offers/search")
    res, total, saut = [], 0, 0
    maximum = cfg.get("maximum", 3000)
    while saut < maximum:
        corps = {"limit": 100, "skip": saut, "query": None, "activitySectorId": [], "missionsTypesIds": [],
                 "missionsDurations": [], "gerographicZones": [], "countriesIds": [], "studiesLevelId": [],
                 "companiesSizes": [], "specializationsIds": [], "entreprisesIds": [0], "missionStartDate": None}
        data = post_json(url, corps, headers={"Origin": "https://mon-vie-via.businessfrance.fr",
                                              "Referer": "https://mon-vie-via.businessfrance.fr/"})
        items = data.get("result") or data.get("results") or data.get("offers") or []
        if not items:
            break
        total += len(items)
        for it in items:
            titre = _premier(it, "missionTitle", "missionTitleEn", "title")
            ok_titre = retenir(titre) or retenir("VIE " + titre)
            if not ok_titre:
                continue
            ville = _premier(it, "cityNameEn", "cityName", "city")
            pays = _premier(it, "countryNameEn", "countryName", "country")
            debut = _premier(it, "missionStartDate", "startDate")
            duree = _premier(it, "missionDuration", "duration")
            desc = html_vers_texte(_premier(it, "missionDescription", "description", "missionProfile"))
            if debut:
                desc = f"Start date: {debut}. Duration: {duree} months.\n" + desc
            oid = it.get("id")
            res.append(offre("vie_bf", oid, _premier(it, "organizationName", "companyName"), titre,
                             ", ".join(x for x in [ville, pays] if x),
                             f"https://mon-vie-via.businessfrance.fr/offres/{oid}",
                             (_premier(it, "creationDate", "publicationDate") or "")[:10], desc, vie=True, contrat="VIE"))
        saut += 100
        compte = data.get("count") or data.get("total")
        if compte and saut >= int(compte):
            break
    return res, total


AGREGATEURS = {
    "adzuna": adzuna,
    "jooble": jooble,
    "themuse": themuse,
    "vie_bf": vie_business_france,
}
