"""Tests hors ligne : géographie, filtres, connecteurs (réponses simulées) et passage complet."""
import json
import os
import tempfile
import unittest
from unittest import mock

from engine import geo, main
from engine.filtres import analyse, annees_experience, langues, titre_exclu, titre_retenu
from engine.sources import ats, agregateurs, offre


class Geo(unittest.TestCase):
    def test_pays(self):
        self.assertEqual(geo.pays_detectes("New York, NY"), ["US"])
        self.assertEqual(geo.pays_detectes("San Francisco, CA"), ["US"])
        self.assertEqual(geo.pays_detectes("Toronto, ON, Canada"), ["CA"])
        self.assertEqual(geo.pays_detectes("Paris, France"), ["FR"])
        self.assertEqual(geo.pays_detectes("Dubai, United Arab Emirates"), ["AE"])
        self.assertEqual(geo.pays_detectes("Remote - US"), ["US"])
        self.assertIn("GB", geo.pays_detectes("London; Paris"))
        self.assertEqual(geo.pays_detectes("Woman's health, Oman"), ["OM"])
        self.assertEqual(geo.pays_detectes("Gerlingen, BW, DE"), ["DE"])
        self.assertEqual(geo.pays_detectes("Wilmington, DE"), ["US"])
        self.assertEqual(geo.zone("LU"), "Europe")
        self.assertEqual(geo.zone("CH"), "Suisse")
        self.assertEqual(geo.code_ville("Lisbon, Portugal", "PT"), "LIS")


class Filtres(unittest.TestCase):
    def test_titres(self):
        for t in ["Strategy Analyst", "Associate, Strategy & Operations", "Chief of Staff to the CEO",
                  "Founder's Associate", "Market Intelligence Analyst", "Corporate Development Analyst",
                  "Senior Associate, Corporate Strategy", "VIE - Business Analyst Strategy"]:
            self.assertTrue(titre_retenu(t), t)
        for t in ["Senior Strategy Manager", "Strategy Intern", "Account Executive, Strategics",
                  "Head of Strategy", "Software Engineer", "Brand Strategy Lead", "Content Strategist",
                  "Stage - Strategy Analyst", "Chief Strategy Officer", "Summer Analyst 2027",
                  "Credit Strategy Analyst", "Marketing Strategy Analyst"]:
            self.assertFalse(titre_retenu(t), t)
        for t in ["Deployment Strategist", "Talent Strategist", "Financial Crimes Compliance Strategist",
                  "SAP Group Reporting Junior Consultant", "Oliver Wyman – P&C Practice – Actuarial Consultant",
                  "Associate Strategic Client Executive, Rx Solutions"]:
            self.assertFalse(titre_retenu(t, est_conseil=True), t)
        self.assertTrue(titre_retenu("Business Strategist"))
        self.assertTrue(titre_retenu("Consultant", est_conseil=True))
        self.assertFalse(titre_retenu("Consultant"))
        self.assertEqual(titre_exclu("Strategy Analyst (National)"), "réservé aux nationaux")

    def test_annees(self):
        self.assertEqual(annees_experience("You have 1-3+ years of experience in consulting"), 1)
        self.assertEqual(annees_experience("Minimum of 6+ years of relevant experience"), 6)
        self.assertEqual(annees_experience("At least 2 years of consulting or investment banking experience"), 2)
        self.assertIsNone(annees_experience("We are a 20 years old company with offices worldwide"))

    def test_langues(self):
        exigees, appreciees = langues("Fluent English and German are required. French is a plus.")
        self.assertIn("Allemand", exigees)
        self.assertIn("Français", appreciees)
        exigees, appreciees = langues("Mandarin would be a plus.")
        self.assertEqual(exigees, [])
        self.assertIn("Mandarin", appreciees)

    def _offre(self, titre, lieu, desc, **kw):
        o = offre("test", titre + lieu, "Acme", titre, lieu, "https://exemple.com/" + titre, "2026-10-14", desc, **kw)
        return analyse(o, {"niveau": 8})

    def test_analyse(self):
        o, r = self._offre("Strategy Analyst", "New York, NY", "1-2 years of experience in consulting. We will not sponsor visas.")
        self.assertIsNone(r)
        self.assertEqual(o["zone"], "États-Unis")
        self.assertEqual(o["autorisation"], "OK · citoyen US")
        self.assertIn("Pas de sponsor : ton passeport US passe", o["drapeaux"])
        self.assertGreaterEqual(o["score_auto"], 80)

        self.assertEqual(self._offre("Strategy Analyst", "Paris, France", "")[1], "basé en France")
        self.assertTrue(self._offre("Strategy Analyst", "Zurich, Switzerland", "Fluent German is essential.")[1].startswith("langue exigée"))
        self.assertEqual(self._offre("Strategy Analyst", "Abu Dhabi, UAE", "Open to UAE Nationals only.")[1], "réservé aux nationaux")
        self.assertEqual(self._offre("Strategy Associate", "Berlin, Germany", "6+ years of experience")[1], "6 ans d'expérience demandés")

        o, r = self._offre("VIE Analyst Strategy, Development & Data", "Lisbon, Portugal", "Start date: January 2027.", vie=True)
        self.assertIsNone(r)
        self.assertEqual(o["contrat"], "VIE")
        self.assertEqual(o["autorisation"], "OK · VIE")
        self.assertEqual(o["detail_score"]["demarrage"], 10)

        o, r = self._offre("Strategy Analyst", "London, United Kingdom", "")
        self.assertEqual(o["autorisation"], "Sponsor requis")

        allemand = ("Wir suchen für unser Team in Stuttgart eine engagierte Person, die mit uns die Strategie "
                    "weiterentwickelt. Du bist kommunikativ und hast Freude an der Arbeit mit den Kollegen und "
                    "verfügst über erste Erfahrungen im Bereich der Beratung oder in einem Unternehmen.")
        self.assertEqual(self._offre("Junior Strategy Consultant", "Stuttgart, Germany", allemand)[1], "annonce rédigée en allemand")

        o, r = self._offre("Strategic Finance Analyst", "New York, NY", "")
        self.assertEqual(o["famille"], "Finance stratégique")


class Connecteurs(unittest.TestCase):
    def test_greenhouse(self):
        faux = {"jobs": [
            {"id": 1, "title": "Strategy & Operations Associate", "absolute_url": "https://x/1",
             "location": {"name": "New York, NY"}, "updated_at": "2026-10-10T00:00:00Z", "content": "&lt;p&gt;2+ years of experience&lt;/p&gt;"},
            {"id": 2, "title": "Software Engineer", "absolute_url": "https://x/2", "location": {"name": "NYC"}, "content": ""},
        ]}
        with mock.patch.object(ats, "get_json", return_value=faux):
            res, lues = ats.greenhouse({"nom": "Acme", "id": "acme"}, titre_retenu)
        self.assertEqual(lues, 2)
        self.assertEqual(len(res), 1)
        self.assertIn("2+ years", res[0]["description"])

    def test_lever(self):
        faux = [{"id": "a", "text": "Strategy Analyst", "hostedUrl": "https://jobs.lever.co/x/a", "createdAt": 1760000000000,
                 "categories": {"location": "Shanghai, China"}, "descriptionPlain": "Market research.", "lists": [], "country": "CN"}]
        with mock.patch.object(ats, "get_json", return_value=faux):
            res, _ = ats.lever({"nom": "Coins", "id": "coins"}, titre_retenu)
        self.assertEqual(res[0]["pays_iso"], "CN")
        self.assertTrue(res[0]["publiee"].startswith("2025"))

    def test_ashby(self):
        faux = {"jobs": [{"id": "z", "title": "Chief of Staff", "location": "Remote - US", "jobUrl": "https://jobs.ashbyhq.com/x/z",
                          "publishedAt": "2026-10-01T00:00:00Z", "descriptionPlain": "0-2 years", "isListed": True}]}
        with mock.patch.object(ats, "get_json", return_value=faux):
            res, _ = ats.ashby({"nom": "Ramp", "id": "ramp"}, titre_retenu)
        self.assertEqual(res[0]["titre"], "Chief of Staff")

    def test_workday(self):
        liste = {"total": 1, "jobPostings": [{"title": "VIE - Strategy Analyst", "externalPath": "/job/Singapore/VIE_R1", "locationsText": "Singapore"}]}
        detail = {"jobPostingInfo": {"jobDescription": "<p>Start date: January 2027</p>", "location": "Singapore", "country": {"descriptor": "Singapore"}}}
        with mock.patch.object(ats, "post_json", return_value=liste), mock.patch.object(ats, "get_json", return_value=detail):
            res, _ = ats.workday({"nom": "Airbus", "host": "ag.wd3.myworkdayjobs.com", "tenant": "ag", "site": "Airbus", "recherches": ["VIE"]}, titre_retenu)
        self.assertEqual(len(res), 1)
        self.assertIn("January 2027", res[0]["description"])

    def test_vie_bf(self):
        page = {"result": [{"id": 42, "missionTitle": "Business Strategy Analyst", "organizationName": "TotalEnergies",
                            "cityNameEn": "Kuala Lumpur", "countryNameEn": "Malaysia", "missionStartDate": "2027-01-01",
                            "missionDuration": 24, "missionDescription": "Strategy support", "creationDate": "2026-10-01"}], "count": 1}
        with mock.patch.object(agregateurs, "post_json", return_value=page):
            res, _ = agregateurs.vie_business_france({}, titre_retenu)
        self.assertEqual(res[0]["contrat"], "VIE")
        self.assertTrue(res[0]["url"].endswith("/offres/42"))


class PassageComplet(unittest.TestCase):
    def test_main(self):
        def faux_connecteur(e, retenir):
            o1 = offre("greenhouse", 1, e["nom"], "Strategy Analyst", "Brussels, Belgium", "https://x/1", "2026-10-14",
                       "Junior role, 0-2 years of experience.")
            o2 = offre("greenhouse", 2, e["nom"], "Strategy Analyst", "Paris, France", "https://x/2", "2026-10-14", "")
            return [o for o in (o1, o2) if retenir(o["titre"])], 2

        with tempfile.TemporaryDirectory() as tmp:
            cfg, data = os.path.join(tmp, "config"), os.path.join(tmp, "data")
            os.makedirs(cfg)
            with open(os.path.join(cfg, "entreprises.json"), "w") as f:
                json.dump([{"nom": "Acme", "ats": "greenhouse", "id": "acme", "niveau": 8}], f)
            with open(os.path.join(cfg, "agregateurs.json"), "w") as f:
                json.dump({}, f)
            with mock.patch.object(main, "CONFIG", cfg), mock.patch.object(main, "DATA", data), \
                    mock.patch.dict(main.CONNECTEURS, {"greenhouse": faux_connecteur}):
                main.main([])
                with open(os.path.join(data, "offres.json")) as f:
                    sortie = json.load(f)
                with open(os.path.join(data, "stats.json")) as f:
                    stats = json.load(f)
        self.assertEqual(sortie["total"], 1)
        self.assertEqual(sortie["offres"][0]["pays"], "Belgique")
        self.assertEqual(stats["rejets_par_raison"].get("basé en France"), 1)


if __name__ == "__main__":
    unittest.main()


class ListesHtml(unittest.TestCase):
    def test_iagora(self):
        page1 = ('<a href="/work/en/offer/VIE-netherlands-finance/111">VIE - Market Intelligence Analyst</a>'
                 '<a href="/work/en/offer/VIE-belgium-finance/112">Financial Controller VIE</a>'
                 '<a rel="next" href="/work/en/VIE?page=2">Next</a>')
        page2 = '<a href="/work/en/offer/VIE-united-arab-emirates-management/113">VIE Strategy Analyst</a>'
        fiche = ('<script type="application/ld+json">{"@type": "JobPosting", "title": "VIE - Market Intelligence Analyst",'
                 '"hiringOrganization": {"name": "Schneider Electric"}, "jobLocation": {"address": {"addressLocality": "Hoofddorp",'
                 '"addressCountry": "NL"}}, "description": "<p>Master and first experience</p>", "datePosted": "2026-10-13"}</script>')
        pages = {"https://www.iagora.com/work/en/VIE": page1, "https://www.iagora.com/work/en/VIE?page=2": page2}

        def faux_get_text(url, **kw):
            return pages.get(url, fiche)

        cfg = {"sources": [{"nom": "iagora", "base": "https://www.iagora.com", "vie": True, "detail": True,
                            "pays_depuis_slug": True, "pages": ["https://www.iagora.com/work/en/VIE"],
                            "motif": r'href="(?P<url>(?:https://www\.iagora\.com)?/work/en/offer/VIE-(?P<slug>[a-z0-9-]+)/(?P<id>\d+))"[^>]*>(?P<titre>.*?)</a>'}]}
        with mock.patch.object(agregateurs, "get_text", side_effect=faux_get_text):
            res, lues = agregateurs.listes_html(cfg, titre_retenu)
        self.assertEqual(lues, 3)
        titres = {o["titre"] for o in res}
        self.assertIn("VIE - Market Intelligence Analyst", titres)
        self.assertNotIn("Financial Controller VIE", titres)
        mi = [o for o in res if "Market" in o["titre"]][0]
        self.assertEqual(mi["entreprise"], "Schneider Electric")
        self.assertEqual(mi["pays_iso"], "NL")
