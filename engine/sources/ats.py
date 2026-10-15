"""Connecteurs des logiciels de recrutement (pages carrières des entreprises)."""
from datetime import datetime, timezone

import requests

from ..http import get_json, post_json
from ..texte import html_vers_texte
from . import offre


def greenhouse(e, retenir):
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{e['id']}/jobs", params={"content": "true"})
    jobs = data.get("jobs", []) or []
    res = []
    for j in jobs:
        titre = j.get("title", "")
        if not retenir(titre):
            continue
        lieu = (j.get("location") or {}).get("name", "") or ""
        bureaux = "; ".join(o.get("location") or o.get("name") or "" for o in (j.get("offices") or []))
        if bureaux and bureaux not in lieu:
            lieu = f"{lieu}; {bureaux}" if lieu else bureaux
        res.append(offre("greenhouse", j.get("id"), e["nom"], titre, lieu, j.get("absolute_url"),
                         (j.get("updated_at") or "")[:10], html_vers_texte(j.get("content", ""))))
    return res, len(jobs)


def lever(e, retenir):
    data = None
    for base in ("https://api.lever.co/v0/postings/", "https://api.eu.lever.co/v0/postings/"):
        try:
            data = get_json(base + e["id"], params={"mode": "json"})
            break
        except requests.HTTPError as err:
            if err.response is not None and err.response.status_code == 404:
                continue
            raise
    if data is None:
        raise RuntimeError("introuvable sur Lever (US et UE)")
    res = []
    for j in data:
        titre = j.get("text", "")
        if not retenir(titre):
            continue
        cats = j.get("categories") or {}
        lieux = [cats.get("location") or ""] + list(cats.get("allLocations") or [])
        lieu = "; ".join(dict.fromkeys(l for l in lieux if l))
        blocs = [j.get("descriptionPlain") or ""]
        for liste in j.get("lists") or []:
            blocs.append((liste.get("text") or "") + "\n" + html_vers_texte(liste.get("content") or ""))
        blocs.append(j.get("additionalPlain") or "")
        cree = j.get("createdAt")
        publiee = datetime.fromtimestamp(cree / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if cree else ""
        res.append(offre("lever", j.get("id"), e["nom"], titre, lieu, j.get("hostedUrl"), publiee,
                         "\n".join(b for b in blocs if b), pays_iso=j.get("country") or "",
                         contrat=cats.get("commitment") or "", teletravail=j.get("workplaceType") == "remote"))
    return res, len(data)


def ashby(e, retenir):
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{e['id']}", params={"includeCompensation": "true"})
    jobs = data.get("jobs", []) or []
    res = []
    for j in jobs:
        if j.get("isListed") is False:
            continue
        titre = j.get("title", "")
        if not retenir(titre):
            continue
        lieux = [j.get("location") or ""]
        for s in j.get("secondaryLocations") or []:
            lieux.append(s.get("location") or "")
        adresse = ((j.get("address") or {}).get("postalAddress") or {})
        if adresse.get("addressCountry"):
            lieux.append(adresse.get("addressCountry"))
        lieu = "; ".join(dict.fromkeys(l for l in lieux if l))
        desc = j.get("descriptionPlain") or html_vers_texte(j.get("descriptionHtml") or "")
        res.append(offre("ashby", j.get("id"), e["nom"], titre, lieu, j.get("jobUrl") or j.get("applyUrl"),
                         (j.get("publishedAt") or "")[:10], desc, teletravail=bool(j.get("isRemote"))))
    return res, len(jobs)


def smartrecruiters(e, retenir):
    cid = e["id"]
    vus, res, total = set(), [], 0
    for q in e.get("recherches") or ["strategy", "chief of staff", "market intelligence", "business operations", "corporate development"]:
        decalage = 0
        while decalage < 300:
            data = get_json(f"https://api.smartrecruiters.com/v1/companies/{cid}/postings",
                            params={"limit": 100, "offset": decalage, "q": q})
            items = data.get("content", []) or []
            total += len(items)
            for it in items:
                if it.get("id") in vus:
                    continue
                vus.add(it.get("id"))
                titre = it.get("name", "")
                if not retenir(titre):
                    continue
                loc = it.get("location") or {}
                lieu = ", ".join(x for x in [loc.get("city"), loc.get("region"), loc.get("country", "").upper()] if x)
                desc = ""
                if it.get("ref"):
                    try:
                        det = get_json(it["ref"])
                        sections = ((det.get("jobAd") or {}).get("sections") or {})
                        desc = "\n".join(html_vers_texte((sections.get(k) or {}).get("text", ""))
                                         for k in ("jobDescription", "qualifications", "additionalInformation"))
                    except Exception:
                        desc = ""
                res.append(offre("smartrecruiters", it.get("id"), (it.get("company") or {}).get("name") or e["nom"],
                                 titre, lieu, f"https://jobs.smartrecruiters.com/{cid}/{it.get('id')}",
                                 (it.get("releasedDate") or "")[:10], desc, pays_iso=loc.get("country") or "",
                                 teletravail=bool(loc.get("remote"))))
            if len(items) < 100:
                break
            decalage += 100
    return res, total


def workable(e, retenir):
    data = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{e['id']}", params={"details": "true"})
    jobs = data.get("jobs", []) or []
    res = []
    for j in jobs:
        titre = j.get("title", "")
        if not retenir(titre):
            continue
        lieux = [", ".join(x for x in [j.get("city"), j.get("state"), j.get("country")] if x)]
        for l in j.get("locations") or []:
            lieux.append(", ".join(x for x in [l.get("city"), l.get("region"), l.get("country")] if x))
        lieu = "; ".join(dict.fromkeys(l for l in lieux if l))
        res.append(offre("workable", j.get("shortcode") or j.get("id"), e["nom"], titre, lieu,
                         j.get("url") or j.get("shortlink") or j.get("application_url"),
                         j.get("published_on") or (j.get("created_at") or "")[:10],
                         html_vers_texte(j.get("description") or ""), teletravail=bool(j.get("telecommuting"))))
    return res, len(jobs)


def workday(e, retenir):
    hote, tenant, site = e["host"], e["tenant"], e["site"]
    base = f"https://{hote}/wday/cxs/{tenant}/{site}"
    vus, res, total = set(), [], 0
    for q in e.get("recherches") or ["strategy", "chief of staff", "market intelligence", "corporate development"]:
        for page in range(3):
            data = post_json(base + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": page * 20, "searchText": q},
                             headers={"Accept": "application/json"})
            posts = data.get("jobPostings", []) or []
            total += len(posts)
            for p in posts:
                chemin = p.get("externalPath") or ""
                if not chemin or chemin in vus:
                    continue
                vus.add(chemin)
                titre = p.get("title", "")
                if not retenir(titre):
                    continue
                desc, lieu, publiee, url = "", p.get("locationsText") or "", p.get("postedOn") or "", f"https://{hote}/{site}{chemin}"
                try:
                    det = get_json(base + chemin, headers={"Accept": "application/json"})
                    info = det.get("jobPostingInfo") or {}
                    desc = html_vers_texte(info.get("jobDescription") or "")
                    autres = info.get("additionalLocations") or []
                    lieu = "; ".join(x for x in [info.get("location") or lieu] + list(autres) if x)
                    pays = (info.get("country") or {}).get("descriptor") or ""
                    if pays and pays not in lieu:
                        lieu = f"{lieu}; {pays}" if lieu else pays
                    publiee = info.get("startDate") or publiee
                    url = info.get("externalUrl") or url
                except Exception:
                    pass
                res.append(offre("workday", chemin, e["nom"], titre, lieu, url, publiee, desc))
            if len(posts) < 20:
                break
    return res, total


CONNECTEURS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "smartrecruiters": smartrecruiters,
    "workable": workable,
    "workday": workday,
}
