"""Agrégateurs (France Travail, Adzuna, Jooble, The Muse), Choisir le service public, VIE Business France
et listes HTML (iAgora, BNP Paribas)."""
import html
import json
import os
import re
from datetime import date, timedelta
from urllib.parse import quote

import requests

from .. import geo
from ..http import SESSION, get_json, get_text, post_form, post_json
from ..texte import html_vers_texte
from . import offre


def adzuna(cfg, retenir):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError("clés Adzuna absentes (ADZUNA_APP_ID, ADZUNA_APP_KEY)")
    res, total = [], 0
    mode_titre = True
    for pays in cfg.get("pays", []):
        for q in (cfg.get("requetes_par_pays") or {}).get(pays, cfg.get("requetes", [])):
            params = {"app_id": app_id, "app_key": app_key, "results_per_page": 50,
                      "max_days_old": cfg.get("max_days_old", 3), "content-type": "application/json"}
            params["title_only" if mode_titre else "what"] = q
            try:
                data = get_json(f"https://api.adzuna.com/v1/api/jobs/{pays}/search/1", params=params)
            except requests.HTTPError as err:
                if mode_titre and err.response is not None and err.response.status_code == 400:
                    mode_titre = False  # paramètre refusé : recherche plein texte, le tri des intitulés fait le reste
                    params.pop("title_only", None)
                    params["what"] = q
                    data = get_json(f"https://api.adzuna.com/v1/api/jobs/{pays}/search/1", params=params)
                else:
                    raise
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


# Cabinets de recrutement, plateformes de missions et annonces anonymes : du bruit pour Pierre.
INTERMEDIAIRES = re.compile(r"staffing|recruit\w*|executive search|search group|\bsearch\b|jobleads|hire\b|hiring|"
                            r"talent\w*|career launch|mercor|crossing hurdles|teema|confidential|interim|intérim|"
                            r"randstad|adecco|manpower", re.I)


def jooble(cfg, retenir):
    """API Jooble (clé gratuite). Chaque recherche a son lieu (« Paris, France »), son pays attendu
    et ses mots-clés : en français pour la France, en anglais ailleurs."""
    cle = os.environ.get("JOOBLE_KEY")
    if not cle:
        raise RuntimeError("clé Jooble absente (JOOBLE_KEY)")
    recherches = cfg.get("recherches") or [{"lieu": l, "requetes": cfg.get("requetes", [])} for l in cfg.get("lieux", [])]
    extras = {"datecreatedfrom": (date.today() - timedelta(days=cfg.get("jours", 7))).isoformat(),
              "ResultOnPage": cfg.get("par_page", 50)}
    res, total, vus, debug, erreurs = [], 0, set(), [], 0
    for r in recherches:
        url = f"https://{r.get('hote', 'jooble.org')}/api/{cle}"
        for q in r.get("requetes", []):
            for page in range(1, r.get("pages", 1) + 1):
                corps = {"keywords": q, "location": r["lieu"], "page": str(page)}
                try:
                    try:
                        data = post_json(url, {**corps, **extras})
                    except requests.HTTPError as err:
                        if not extras or err.response is None or err.response.status_code != 400:
                            raise
                        extras = {}  # paramètres facultatifs refusés : recherche simple
                        data = post_json(url, corps)
                except Exception as err:  # une recherche en échec ne bloque pas les autres
                    erreurs += 1
                    debug.append(f"{r.get('hote', 'jooble.org')} {r['lieu']} / {q} : {type(err).__name__} {str(err)[:80]}")
                    break
                items = data.get("jobs", []) or []
                total += len(items)
                if page == 1:
                    debug.append(f"{r.get('hote', 'jooble.org')} {r['lieu']} / {q} : {len(items)} offres, ex. "
                                 + " ; ".join((it.get("location") or "?") for it in items[:3]))
                if r.get("diagnostic"):
                    break
                for it in items:
                    cle_vue = it.get("id") or it.get("link") or f"{it.get('title')}|{it.get('company')}|{it.get('location')}"
                    if cle_vue in vus:
                        continue
                    vus.add(cle_vue)
                    titre = html_vers_texte(it.get("title", ""))
                    lieu = it.get("location") or r["lieu"]
                    if geo.pays_detectes(lieu) and lieu.strip().lower() in {n.lower() for n in geo.noms_pays()}:
                        lieu = r["lieu"]  # Jooble ne donne que le pays : on garde la ville cherchée
                    detectes = geo.pays_detectes(lieu)
                    if r.get("pays") and detectes and (r["pays"] not in detectes or (r["pays"] != "US" and "US" in detectes)):
                        continue  # homonyme américain (Paris, TX) ou offre hors du pays visé
                    if not retenir(titre) or INTERMEDIAIRES.search(it.get("company") or "confidential"):
                        continue
                    res.append(offre("jooble", it.get("id"), it.get("company", ""), titre, lieu,
                                     it.get("link"), (it.get("updated") or "")[:10], html_vers_texte(it.get("snippet", "")),
                                     pays_iso=r.get("pays", ""), contrat=it.get("type") or ""))
                if len(items) < extras.get("ResultOnPage", 20):
                    break
    cfg["_debug"] = debug
    if erreurs and not total:
        raise RuntimeError("toutes les recherches Jooble ont échoué : " + " | ".join(debug[:3]))
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


def france_travail(cfg, retenir):
    """API officielle Offres d'emploi v2 de France Travail (clés gratuites sur francetravail.io)."""
    cid, secret = os.environ.get("FT_CLIENT_ID"), os.environ.get("FT_CLIENT_SECRET")
    if not (cid and secret):
        raise RuntimeError("clés France Travail absentes (FT_CLIENT_ID, FT_CLIENT_SECRET)")
    jeton = post_form("https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire",
                      {"grant_type": "client_credentials", "client_id": cid, "client_secret": secret,
                       "scope": "api_offresdemploiv2 o2dsoffre"}).get("access_token")
    entetes = {"Authorization": f"Bearer {jeton}", "Accept": "application/json"}
    res, total, vus = [], 0, set()
    for q in cfg.get("requetes", []):
        r = SESSION.get("https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
                        params={"motsCles": q, "range": "0-149", "publieeDepuis": cfg.get("publiee_depuis", 3)},
                        headers=entetes, timeout=25)
        if r.status_code == 204:
            continue
        r.raise_for_status()
        items = (r.json() or {}).get("resultats", []) or []
        total += len(items)
        for it in items:
            if it.get("id") in vus:
                continue
            vus.add(it.get("id"))
            titre = it.get("intitule", "")
            if not retenir(titre) or it.get("typeContrat") in ("MIS", "SAI"):
                continue
            permis = "; ".join(f"Permis {p.get('libelle', '')} {'exigé' if p.get('exigence') == 'E' else 'souhaité'}"
                               for p in it.get("permis") or [])
            desc = "\n".join(x for x in [it.get("description", ""), it.get("experienceLibelle", ""), permis] if x)
            url = ((it.get("origineOffre") or {}).get("urlOrigine")
                   or f"https://candidat.francetravail.fr/offres/recherche/detail/{it.get('id')}")
            res.append(offre("france_travail", it.get("id"), (it.get("entreprise") or {}).get("nom", ""), titre,
                             ((it.get("lieuTravail") or {}).get("libelle", "") + ", France"), url,
                             (it.get("dateCreation") or "")[:10], desc, pays_iso="FR",
                             contrat=it.get("typeContrat") or ""))
    return res, total


CSP = "https://choisirleservicepublic.gouv.fr"
MOIS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
        "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
_CARTE_TITRE = re.compile(r'href="(?P<url>https://choisirleservicepublic\.gouv\.fr/offre-emploi/[^"]+?-reference-(?P<ref>[^/"]+)/)"'
                          r'[^>]*>(?P<titre>.*?)</a>', re.S)


def _champ_carte(bloc, libelle):
    m = re.search(libelle + r"\s*:\s*</span>(.*?)</li>", bloc, re.S)
    return html_vers_texte(m.group(1)) if m else ""


def _date_fr(texte):
    m = re.search(r"(\d{1,2})\s+([a-zéûè]+)\s+(\d{4})", texte or "", re.I)
    if not m or m.group(2).lower() not in MOIS:
        return ""
    return date(int(m.group(3)), MOIS[m.group(2).lower()], int(m.group(1))).isoformat()


def service_public(cfg, retenir):
    """Choisir le service public (site officiel de l'emploi public) : pages de recherche par mot-clé,
    limitées aux offres récentes, puis fiche détaillée des intitulés retenus."""
    res, total, vus, fiches = [], 0, set(), 0
    periode = cfg.get("periode", "7_derniers_jours")
    for mot in cfg.get("recherches", ["stratégie"]):
        base = f"{CSP}/nos-offres/filtres/mot-cles/{quote(mot)}/date-de-publication/{periode}/"
        for n in range(1, cfg.get("pages_par_recherche", 2) + 1):
            try:
                page = get_text(base if n == 1 else f"{base}page/{n}/")
            except requests.HTTPError as err:
                if n == 1 and err.response is not None and err.response.status_code == 404:
                    base = f"{CSP}/nos-offres/filtres/mot-cles/{quote(mot)}/"  # filtre de date refusé : liste simple
                    page = get_text(base)
                else:
                    break
            cartes = page.split('fr-card--offer')[1:]
            if not cartes:
                break
            for bloc in cartes:
                m = _CARTE_TITRE.search(bloc)
                if not m or m.group("ref") in vus:
                    continue
                vus.add(m.group("ref"))
                total += 1
                titre = html_vers_texte(m.group("titre"))
                if not retenir(titre):
                    continue
                lieu = _champ_carte(bloc, "Localisation")
                employeur = _champ_carte(bloc, "Employeur")
                versant = _champ_carte(bloc, "Fonction publique")
                logo = re.search(r'alt="([^"]+?)(?: - (?i:libert)[ée].*?)?"', bloc)
                ministere = html.unescape(logo.group(1)) if logo else ""
                publiee = _date_fr((re.search(r"En ligne depuis le ([^<]+)", bloc) or [None, ""])[1])
                desc, nature = "", ""
                if fiches < cfg.get("max_fiches", 15):
                    fiches += 1
                    try:
                        fiche = get_text(m.group("url"))
                        jp = _jobposting(fiche) or {}
                        corps = html_vers_texte(fiche[max(0, fiche.find("<main")):])
                        nature = (re.search(r"Nature de l.emploi\s*(.{0,90}?)(?:\s+Expérience|\n)", corps, re.S) or [None, ""])[1]
                        if re.search(r"ouvert(?:e)? (?:uniquement |exclusivement )?aux (?:seuls )?(?:fonctionnaires|titulaires)(?! et)", nature, re.I):
                            continue  # réservé aux fonctionnaires
                        categorie = re.search(r"Catégorie\s+Catégorie\s+([ABC])", corps)
                        if categorie and categorie.group(1) in "BC":
                            continue  # postes de catégorie B ou C : hors cible cadre
                        desc = "\n".join(x for x in [f"Employeur : {employeur}" if employeur else "",
                                                     html_vers_texte(jp.get("Description") or jp.get("description") or ""),
                                                     nature, (re.search(r"Expérience souhaitée\s*([^\n]{0,60})", corps) or [None, ""])[1]] if x)
                    except Exception:
                        desc = ""
                res.append(offre("service_public", m.group("ref"), ministere or employeur or versant, titre, f"{lieu}, France", m.group("url"),
                                 publiee, desc, pays_iso="FR", contrat="CDD" if "contractuel" in nature.lower() else ""))
            if len(cartes) < 20:
                break
    return res, total


AGREGATEURS = {
    "france_travail": france_travail,
    "adzuna": adzuna,
    "jooble": jooble,
    "themuse": themuse,
    "vie_bf": vie_business_france,
    "listes_html": listes_html,
    "service_public": service_public,
}
