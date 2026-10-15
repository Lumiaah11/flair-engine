"""Tri des offres : intitulé, lieu, séniorité, langues, nationalité, puis score automatique.

Le score suit la grille de Pierre (sur 100) :
poste 35, séniorité 20, autorisation de travail 15, langues 10, démarrage 10, employeur 10.
Claude affine ensuite la note le matin.
"""
import re

from . import geo
from .texte import sans_accents

# --- Intitulés --------------------------------------------------------------

FAMILLES = [
    ("Chief of Staff et bras droit", 30, re.compile(r"chief of staff|founder'?s associate|founders associate|office of the ceo|ceo office|bras droit|executive associate to the ceo", re.I)),
    ("Corp dev junior", 22, re.compile(r"corporate development|corp\.? ?dev|m&a analyst|strategy (?:&|and) m&a|mergers (?:&|and) acquisitions analyst", re.I)),
    ("Market analyst", 28, re.compile(r"market (?:intelligence|analyst|insights?|research analyst)|competitive intelligence|insights (?:&|and) strategy|business insights", re.I)),
    ("Strategy & Operations", 24, re.compile(r"strategy ?(?:&|and|/) ?operations|biz ?ops|business operations|strategic operations|\bs&o\b", re.I)),
    ("Conseil en stratégie", 32, re.compile(r"(?:strategy|strategic|management) consult|junior consultant|associate consultant|consultant.{0,25}strat|strategy consultant", re.I)),
    ("Stratégie corporate", 32, re.compile(r"strateg|stratég|transformation (?:analyst|associate|officer)|strategic planning|growth strategy", re.I)),
]

# Intitulés généralistes acceptés seulement chez les cabinets de conseil en stratégie.
CONSEIL_GENERIQUE = re.compile(r"\b(consultant|business analyst|associate|analyst|research analyst)\b", re.I)

TITRE_EXCLU = re.compile(
    r"\b(senior|sr\.?|lead|principal|director|directeur|directrice|head|vp|vice[- ]president|svp|evp|partner|"
    r"intern|internship|interns|stagiaire|alternan\w*|apprenti\w*|working student|werkstudent|phd|ph\.d|"
    r"postdoc|fellow|fellowship|manager|managing|responsable|summer|event|webinar|competition|challenge|"
    r"crack the case|hackathon|talent pool|talent community|talent pipeline|spontaneous|spontanée)\b"
    r"|\bchief\b(?! of staff)"
    r"|(?:^|\(|\s)stage(?:\s*[-–:)]|\s+(?:de|en|d')\b)",
    re.I,
)
# Fonctions qui contiennent « strategy » sans être de la strat (vente, marketing, tech, risque...).
NON_STRAT = re.compile(
    r"\b(account executive|account manager|sales|customer success|engineer\w*|developer|designer|recruit\w*|"
    r"talent acquisition|legal|counsel|attorney|paralegal|content|social media|seo|brand|creative|media|"
    r"communications|copywrit\w*|tax|audit\w*|accountant|accounting|software|ux|it strategy|cloud|security|"
    r"cyber\w*|infrastructure|devops|network|clinical|medical|nurse|pharmac\w*|investment strateg\w*|trading|"
    r"trader|quant\w*|credit|fraud|risk|collections|underwriting|merchandis\w*|buyer|procurement|marketing|"
    r"teacher|instructor|editor|journalist|writer)\b",
    re.I,
)
SENIOR_ASSOCIATE = re.compile(r"senior associate", re.I)
NATIONAUX_TITRE = re.compile(r"\((?:national|emirati national|saudi national)\)|emirati talent|saudi talent|nationals? only", re.I)

VIE_TITRE = re.compile(r"\bV\.?I\.?E\.?\b|(?i:volontariat international|international volunteer)")
VIE_UTILE = re.compile(r"strat|analyst|business|market|transformation|chief of staff|development|performance|project", re.I)


def famille(titre, est_conseil=False):
    """Renvoie (label, points) ou (None, 0)."""
    for label, pts, motif in FAMILLES:
        if motif.search(titre):
            if label != "Chief of Staff et bras droit" and NON_STRAT.search(titre):
                return None, 0
            return label, pts
    if est_conseil and CONSEIL_GENERIQUE.search(titre) and not NON_STRAT.search(titre):
        return "Conseil en stratégie", 30
    return None, 0


def titre_exclu(titre):
    t = SENIOR_ASSOCIATE.sub("associate", titre or "")
    m = TITRE_EXCLU.search(t)
    if m:
        return "intitulé : " + m.group(0).strip().lower()
    if NATIONAUX_TITRE.search(titre or ""):
        return "réservé aux nationaux"
    return None


def titre_retenu(titre, est_conseil=False):
    """Filtre rapide avant tout appel de détail."""
    if not titre or titre_exclu(titre):
        return False
    if famille(titre, est_conseil)[0] is not None:
        return True
    return bool(VIE_TITRE.search(titre) and VIE_UTILE.search(titre) and not NON_STRAT.search(titre))


# --- Description --------------------------------------------------------------

_ANNEES = re.compile(
    r"(?<![\d.])(\d{1,2})\s*\+?\s*(?:(?:-|–|to|à|a)\s*(\d{1,2})\s*\+?\s*)?(?:years?|yrs?|ans|années)",
    re.I,
)
_EXPERIENCE = re.compile(r"experience|expérience|experiencia|track record|background", re.I)


def annees_experience(texte):
    """Plus petite durée d'expérience exigée trouvée près du mot experience."""
    if not texte:
        return None
    valeurs = []
    for m in _ANNEES.finditer(texte):
        debut, fin = max(0, m.start() - 60), min(len(texte), m.end() + 70)
        if not _EXPERIENCE.search(texte[debut:fin]):
            continue
        n = int(m.group(1))
        if 0 <= n <= 15:
            valeurs.append(n)
    return min(valeurs) if valeurs else None


LANGUES = {
    "german": "Allemand", "deutsch": "Allemand", "dutch": "Néerlandais", "flemish": "Néerlandais",
    "arabic": "Arabe", "mandarin": "Mandarin", "chinese": "Chinois", "cantonese": "Cantonais",
    "japanese": "Japonais", "korean": "Coréen", "portuguese": "Portugais", "italian": "Italien",
    "polish": "Polonais", "czech": "Tchèque", "swedish": "Suédois", "danish": "Danois",
    "norwegian": "Norvégien", "finnish": "Finnois", "hebrew": "Hébreu", "turkish": "Turc",
    "russian": "Russe", "greek": "Grec", "hungarian": "Hongrois", "romanian": "Roumain",
    "thai": "Thaï", "vietnamese": "Vietnamien", "bahasa": "Bahasa", "luxembourgish": "Luxembourgeois",
    "spanish": "Espagnol", "french": "Français",
}
_PLUS = re.compile(r"\b(plus|advantage\w*|nice to have|bonus|preferred|asset|desirable|beneficial|ideally|appreciated|would be|atout|apprécié|souhaité)\b", re.I)
_EXIGE = re.compile(r"\b(fluent|fluency|native|proficien\w*|business[- ]level|required|essential|mandatory|must|c1|c2|excellent command|full professional|courant|exigé|obligatoire|indispensable)\b", re.I)
_PHRASES = re.compile(r"(?<=[.!?;\n•])\s+|\n")


def langues(texte):
    """Renvoie (langues_exigees, langues_appreciees) en libellés français."""
    exigees, appreciees = [], []
    if not texte:
        return exigees, appreciees
    for phrase in _PHRASES.split(texte):
        p = phrase.lower()
        for cle, label in LANGUES.items():
            if not re.search(r"\b" + cle + r"\b", p):
                continue
            if _PLUS.search(p):
                if label not in appreciees:
                    appreciees.append(label)
            elif _EXIGE.search(p):
                if label not in exigees:
                    exigees.append(label)
    return exigees, appreciees


NATIONALITE = re.compile(
    r"\b(emirati nationals?|uae nationals?|saudi nationals?|saudi talent|qatari nationals?|kuwaiti nationals?|"
    r"omani nationals?|bahraini nationals?|gcc nationals?|nationals only|local nationals only|emiratisation|saudization)\b",
    re.I,
)
HABILITATION = re.compile(r"security clearance|clearance required|ts/sci|secret clearance", re.I)
SANS_SPONSOR = re.compile(
    r"(?:will not|won't|unable to|cannot|can't|do not|does not|not able to|not)\s+(?:\w+\s+){0,4}sponsor|without (?:visa )?sponsorship|no (?:visa )?sponsorship",
    re.I,
)
DEMARRAGE_TOP = re.compile(r"(?:january|janvier|jan\.?)\s+2027|as soon as possible|\basap\b|dès que possible|immediate start|start immediately", re.I)
DEMARRAGE_PRINTEMPS = re.compile(r"(?:march|mars|april|avril|may|mai|spring|printemps)\s+2027", re.I)
DEMARRAGE_TARDIF = re.compile(r"(?:september|septembre|fall|autumn|automne|august|août)\s+2027|2027 (?:graduate|grad) (?:program|programme|intake)|class of 2027", re.I)

AUTORISATION = {  # zone -> (points, libellé)
    "États-Unis": (15, "OK · citoyen US"),
    "Europe": (15, "OK · UE"),
    "Suisse": (15, "OK · UE"),
    "Royaume-Uni": (3, "Sponsor requis"),
    "Canada": (8, "À vérifier"),
    "Golfe": (8, "Visa employeur"),
    "Asie": (8, "Visa employeur"),
    "Océanie": (8, "À vérifier"),
    "Afrique": (8, "Visa employeur"),
    "Amérique latine": (8, "Visa employeur"),
    "Moyen-Orient": (8, "Visa employeur"),
    "Autre": (5, "À vérifier"),
}


def analyse(offre, entreprise_info=None):
    """Complète l'offre (pays, zone, score, drapeaux) ou renvoie la raison du rejet."""
    info = entreprise_info or {}
    titre = offre.get("titre", "")
    texte = offre.get("description", "") or ""
    est_conseil = info.get("type") == "conseil"

    raison = titre_exclu(titre)
    if raison:
        return None, raison

    est_vie = bool(offre.get("vie")) or bool(VIE_TITRE.search(titre))
    label, pts_poste = famille(titre, est_conseil)
    if not label:
        if est_vie and VIE_UTILE.search(titre) and not NON_STRAT.search(titre):
            label, pts_poste = "Stratégie corporate", 20
        else:
            return None, "intitulé hors cible"
    if re.search(r"\b(analyst|associate|junior|graduate|entry|new grad|jeune diplômé)\b", titre, re.I):
        pts_poste = min(35, pts_poste + 2)

    lieux = geo.pays_detectes(offre.get("lieu", ""))
    if not lieux and offre.get("pays_iso"):
        lieux = [offre["pays_iso"]]
    hors_france = [p for p in lieux if p != "FR"]
    if lieux and not hors_france:
        return None, "basé en France"
    iso = hors_france[0] if hors_france else (offre.get("pays_iso") or "")
    z = geo.zone(iso) if iso else "Autre"

    if NATIONALITE.search(texte):
        return None, "réservé aux nationaux"

    annees = annees_experience(texte)
    if annees is not None and annees >= 4:
        return None, f"{annees} ans d'expérience demandés"

    exigees, appreciees = langues(texte)
    bloquantes = [l for l in exigees if l not in ("Français", "Espagnol")]
    if bloquantes:
        return None, "langue exigée : " + ", ".join(bloquantes)

    drapeaux = []
    # Séniorité
    if re.search(r"\b(junior|graduate|entry[- ]level|new grad|jeune diplômé|early career)\b", titre + " " + texte[:600], re.I) and (annees is None or annees <= 1):
        pts_senior = 20
    elif annees is None:
        pts_senior = 15
    elif annees <= 1:
        pts_senior = 20
    elif annees == 2:
        pts_senior = 15
    else:
        pts_senior = 8
    if annees:
        drapeaux.append(f"{annees} ans demandés" if annees > 1 else f"{annees} an demandé")

    # Autorisation de travail
    if est_vie:
        pts_auth, autorisation = 15, "OK · VIE"
        if iso == "US":
            drapeaux.append("Éligibilité VIE binational à vérifier")
    else:
        pts_auth, autorisation = AUTORISATION.get(z, (5, "À vérifier"))
    if SANS_SPONSOR.search(texte):
        if iso == "US":
            drapeaux.append("Pas de sponsor : ton passeport US passe")
        elif z not in ("Europe", "Suisse"):
            pts_auth = min(pts_auth, 3)
            autorisation = "Sponsor requis"
    if HABILITATION.search(texte):
        drapeaux.append("Habilitation sécurité")

    # Langues
    pts_langues = 10
    if "Espagnol" in exigees:
        pts_langues = 5
        drapeaux.append("Espagnol courant demandé")
    if "Français" in exigees or "Français" in appreciees:
        drapeaux.append("Français apprécié")
    for l in appreciees:
        if l not in ("Français",) and len(drapeaux) < 6:
            drapeaux.append(f"{l} apprécié")

    # Démarrage
    if DEMARRAGE_TOP.search(texte):
        pts_demarrage = 10
    elif DEMARRAGE_TARDIF.search(texte):
        pts_demarrage = 2
        drapeaux.append("Démarrage tardif")
    elif DEMARRAGE_PRINTEMPS.search(texte):
        pts_demarrage = 6
    else:
        pts_demarrage = 7

    pts_employeur = int(info.get("niveau", 5))
    score = pts_poste + pts_senior + pts_auth + pts_langues + pts_demarrage + pts_employeur

    offre.update({
        "famille": label,
        "pays_iso": iso,
        "pays": geo.nom_pays(iso) if iso else "",
        "zone": "VIE" if est_vie and not iso else z,
        "code": geo.code_ville(offre.get("lieu", ""), iso),
        "contrat": "VIE" if est_vie else (offre.get("contrat") or "CDI"),
        "autorisation": autorisation,
        "annees_exp": annees,
        "langues_exigees": exigees,
        "drapeaux": drapeaux[:4],
        "score_auto": int(score),
        "detail_score": {"poste": pts_poste, "seniorite": pts_senior, "autorisation": pts_auth,
                         "langues": pts_langues, "demarrage": pts_demarrage, "employeur": pts_employeur},
    })
    return offre, None


def cle_doublon(offre):
    def n(s):
        s = sans_accents(s or "").lower()
        return re.sub(r"[^a-z0-9]+", " ", s).strip()
    return f"{n(offre.get('entreprise'))}|{n(offre.get('titre'))}|{n(offre.get('pays_iso'))}"
