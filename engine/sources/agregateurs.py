"""Agrégateurs (Adzuna, Jooble, The Muse), VIE Business France et listes HTML (iAgora, BNP Paribas)."""
import html
import json
import os
import re
from datetime import date

from .. import geo
from ..http import get_json, get_text, post_json
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


def _jobposting(page_html):
    """Extrait le bloc JSON-LD JobPosting d'une page d'offre (format utilisé pour Google Jobs)."""
    for bloc in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page_html, re.S | re.I):
        try:
            data = json.loads(bloc.strip())
        except ValueError:
            continue
        candidats = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for c in candidats:
            if isinstance(c, dict) and "JobPosting" in str(c.get("@type", "")):
                return c
    return None


def _lieu_jsonld(jp):
    lieux = jp.get("jobLocation") or []
    if isinstance(lieux, dict):
        lieux = [lieux]
    morceaux = []
    for l in lieux:
        adr = (l or {}).get("address") or {}
        if isinstance(adr, str):
            morceaux.append(adr)
            continue
        pays = adr.get("addressCountry")
        if isinstance(pays, dict):
            pays = pays.get("name")
        morceaux.append(", ".join(x for x in [adr.get("addressLocality"), adr.get("addressRegion"), pays] if x))
    return "; ".join(m for m in morceaux if m)


def _pays_slug(slug):
    s = (slug or "").replace("-", " ")
    for alias, iso in sorted(((a, i) for i, (_, al) in geo.PAYS.items() for a in al), key=lambda x: -len(x[0])):
        if re.search(r"(^|\s)" + re.escape(alias) + r"(\s|$)", s):
            return iso
    return ""


def listes_html(cfg, retenir):
    """Pages de listes d'offres en HTML (iAgora pour les VIE, page VIE de BNP Paribas)."""
    res, total, debug = [], 0, {}
    for src in cfg.get("sources", []):
        if src.get("actif") is False:
            continue
        motif = re.compile(src["motif"], re.S | re.I)
        vus, details, avec_entreprise = set(), 0, 0
        a_lire = list(src.get("pages", []))[:1]
        restantes = list(src.get("pages", []))[1:]
        lues_pages = 0
        while a_lire and lues_pages < src.get("max_pages", 8):
            url_page = a_lire.pop(0)
            lues_pages += 1
            try:
                page = get_text(url_page)
            except Exception as err:
                debug.setdefault(src["nom"], []).append(f"{url_page} : {type(err).__name__}")
                break
            suivante = re.search(r'<(?:a|link)[^>]*rel="next"[^>]*href="([^"]+)"|<(?:a|link)[^>]*href="([^"]+)"[^>]*rel="next"', page, re.I)
            if suivante:
                lien = html.unescape(suivante.group(1) or suivante.group(2))
                a_lire.append(lien if lien.startswith("http") else src.get("base", "") + lien)
            elif restantes:
                a_lire.append(restantes.pop(0))
            trouves = list(motif.finditer(page))
            if not trouves:
                i = page.lower().find(src.get("indice", "offer"))
                debug.setdefault(src["nom"], []).append(f"{url_page} : 0 lien, extrait {page[max(0, i - 150):i + 350]!r}")
                break
            nouveaux = 0
            for m in trouves:
                oid = m.group("id")
                if oid in vus:
                    continue
                vus.add(oid)
                nouveaux += 1
                total += 1
                url = m.group("url")
                if url.startswith("/"):
                    url = src.get("base", "") + url
                titre = html_vers_texte(m.group("titre") or "")
                if titre and not (retenir(titre) or retenir("VIE " + titre)):
                    continue
                entreprise, lieu, desc, publiee = "", "", "", ""
                pays_iso = _pays_slug(m.groupdict().get("slug")) if src.get("pays_depuis_slug") else ""
                if src.get("detail") and details < src.get("max_details", 60):
                    details += 1
                    try:
                        page_offre = get_text(url)
                        jp = _jobposting(page_offre) or {}
                        titre = titre or jp.get("title", "")
                        org = jp.get("hiringOrganization") or {}
                        entreprise = org.get("name", "") if isinstance(org, dict) else str(org)
                        if not entreprise:
                            m_org = re.search(r'"(?:companyName|company_name|employer)"\s*:\s*"([^"]{2,80})"', page_offre)
                            entreprise = m_org.group(1) if m_org else ""
                        if entreprise:
                            avec_entreprise += 1
                        elif details == 1:
                            i = page_offre.lower().find("company")
                            debug.setdefault(src["nom"], []).append(f"fiche sans entreprise, extrait {page_offre[max(0, i - 200):i + 300]!r}")
                        lieu = _lieu_jsonld(jp)
                        desc = html_vers_texte(jp.get("description", ""))
                        publiee = (jp.get("datePosted") or "")[:10]
                        if jp.get("validThrough") and jp["validThrough"][:10] < date.today().isoformat():
                            continue
                    except Exception:
                        pass
                if not titre or not (retenir(titre) or retenir("VIE " + titre)):
                    continue
                res.append(offre(src["nom"], oid, entreprise, titre, lieu or geo.nom_pays(pays_iso), url, publiee, desc,
                                 pays_iso=pays_iso, vie=src.get("vie", False), contrat="VIE" if src.get("vie") else ""))
            if not nouveaux:
                break
        debug.setdefault(src["nom"], []).append(f"pages lues : {lues_pages}, fiches ouvertes : {details}, avec entreprise : {avec_entreprise}")
    cfg["_debug"] = debug
    return res, total


AGREGATEURS = {
    "adzuna": adzuna,
    "jooble": jooble,
    "themuse": themuse,
    "vie_bf": vie_business_france,
    "listes_html": listes_html,
}
