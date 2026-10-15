"""Détection du pays et de la zone à partir d'un texte de localisation."""
import re
import unicodedata


def _norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


# ISO2 -> (nom français, alias en minuscules sans accents)
PAYS = {
    "US": ("États-Unis", ["united states", "united states of america", "usa", "u.s.", "etats-unis", "us remote", "remote us", "remote - us", "anywhere in the us"]),
    "CA": ("Canada", ["canada"]),
    "GB": ("Royaume-Uni", ["united kingdom", "uk", "england", "scotland", "royaume-uni", "great britain"]),
    "IE": ("Irlande", ["ireland", "irlande"]),
    "CH": ("Suisse", ["switzerland", "suisse", "schweiz"]),
    "DE": ("Allemagne", ["germany", "allemagne", "deutschland"]),
    "AT": ("Autriche", ["austria", "autriche", "osterreich"]),
    "NL": ("Pays-Bas", ["netherlands", "pays-bas", "nederland", "the netherlands"]),
    "BE": ("Belgique", ["belgium", "belgique", "belgie"]),
    "LU": ("Luxembourg", ["luxembourg", "grand duchy of luxembourg"]),
    "ES": ("Espagne", ["spain", "espagne", "espana"]),
    "PT": ("Portugal", ["portugal"]),
    "IT": ("Italie", ["italy", "italie", "italia"]),
    "DK": ("Danemark", ["denmark", "danemark"]),
    "SE": ("Suède", ["sweden", "suede", "sverige"]),
    "NO": ("Norvège", ["norway", "norvege"]),
    "FI": ("Finlande", ["finland", "finlande"]),
    "PL": ("Pologne", ["poland", "pologne", "polska"]),
    "CZ": ("Tchéquie", ["czech republic", "czechia", "tchequie", "republique tcheque"]),
    "HU": ("Hongrie", ["hungary", "hongrie"]),
    "RO": ("Roumanie", ["romania", "roumanie"]),
    "BG": ("Bulgarie", ["bulgaria", "bulgarie"]),
    "GR": ("Grèce", ["greece", "grece"]),
    "HR": ("Croatie", ["croatia", "croatie"]),
    "SK": ("Slovaquie", ["slovakia", "slovaquie"]),
    "SI": ("Slovénie", ["slovenia", "slovenie"]),
    "EE": ("Estonie", ["estonia", "estonie"]),
    "LV": ("Lettonie", ["latvia", "lettonie"]),
    "LT": ("Lituanie", ["lithuania", "lituanie"]),
    "MT": ("Malte", ["malta", "malte"]),
    "CY": ("Chypre", ["cyprus", "chypre"]),
    "IS": ("Islande", ["iceland", "islande"]),
    "AE": ("Émirats arabes unis", ["united arab emirates", "uae", "emirats arabes unis", "u.a.e."]),
    "SA": ("Arabie saoudite", ["saudi arabia", "arabie saoudite", "ksa", "kingdom of saudi arabia"]),
    "QA": ("Qatar", ["qatar"]),
    "KW": ("Koweït", ["kuwait", "koweit"]),
    "BH": ("Bahreïn", ["bahrain", "bahrein"]),
    "OM": ("Oman", ["oman"]),
    "SG": ("Singapour", ["singapore", "singapour"]),
    "HK": ("Hong Kong", ["hong kong", "hong kong sar", "hongkong"]),
    "CN": ("Chine", ["china", "chine", "mainland china"]),
    "JP": ("Japon", ["japan", "japon"]),
    "KR": ("Corée du Sud", ["south korea", "korea", "coree du sud"]),
    "IN": ("Inde", ["india", "inde"]),
    "MY": ("Malaisie", ["malaysia", "malaisie"]),
    "TH": ("Thaïlande", ["thailand", "thailande"]),
    "ID": ("Indonésie", ["indonesia", "indonesie"]),
    "VN": ("Vietnam", ["vietnam", "viet nam"]),
    "PH": ("Philippines", ["philippines"]),
    "TW": ("Taïwan", ["taiwan"]),
    "AU": ("Australie", ["australia", "australie"]),
    "NZ": ("Nouvelle-Zélande", ["new zealand", "nouvelle-zelande"]),
    "MA": ("Maroc", ["morocco", "maroc"]),
    "ZA": ("Afrique du Sud", ["south africa", "afrique du sud"]),
    "NG": ("Nigeria", ["nigeria"]),
    "KE": ("Kenya", ["kenya"]),
    "EG": ("Égypte", ["egypt", "egypte"]),
    "CI": ("Côte d'Ivoire", ["ivory coast", "cote d'ivoire", "cote divoire"]),
    "SN": ("Sénégal", ["senegal"]),
    "TN": ("Tunisie", ["tunisia", "tunisie"]),
    "MG": ("Madagascar", ["madagascar"]),
    "MX": ("Mexique", ["mexico", "mexique"]),
    "BR": ("Brésil", ["brazil", "bresil", "brasil"]),
    "AR": ("Argentine", ["argentina", "argentine"]),
    "CL": ("Chili", ["chile", "chili"]),
    "CO": ("Colombie", ["colombia", "colombie"]),
    "PE": ("Pérou", ["peru", "perou"]),
    "IL": ("Israël", ["israel"]),
    "TR": ("Turquie", ["turkey", "turquie", "turkiye"]),
    "FR": ("France", ["france"]),
}

VILLES = {
    # États-Unis
    "new york": "US", "nyc": "US", "brooklyn": "US", "manhattan": "US", "san francisco": "US", "los angeles": "US",
    "chicago": "US", "boston": "US", "seattle": "US", "austin": "US", "washington": "US", "mclean": "US",
    "atlanta": "US", "miami": "US", "denver": "US", "dallas": "US", "houston": "US", "philadelphia": "US",
    "palo alto": "US", "menlo park": "US", "mountain view": "US", "redwood city": "US", "san jose": "US",
    "sunnyvale": "US", "armonk": "US", "stamford": "US", "greenwich": "US", "charlotte": "US", "san diego": "US",
    "foster city": "US", "jersey city": "US", "minneapolis": "US", "detroit": "US", "pittsburgh": "US",
    # Canada
    "toronto": "CA", "montreal": "CA", "vancouver": "CA", "calgary": "CA", "ottawa": "CA",
    # Europe
    "london": "GB", "londres": "GB", "manchester": "GB", "edinburgh": "GB", "dublin": "IE",
    "zurich": "CH", "geneva": "CH", "geneve": "CH", "lausanne": "CH", "basel": "CH", "bale": "CH", "bern": "CH", "zug": "CH",
    "berlin": "DE", "munich": "DE", "munchen": "DE", "hamburg": "DE", "frankfurt": "DE", "francfort": "DE",
    "cologne": "DE", "koln": "DE", "dusseldorf": "DE", "stuttgart": "DE", "vienna": "AT", "wien": "AT", "vienne": "AT",
    "amsterdam": "NL", "rotterdam": "NL", "the hague": "NL", "hoofddorp": "NL", "utrecht": "NL", "eindhoven": "NL",
    "brussels": "BE", "bruxelles": "BE", "antwerp": "BE", "anvers": "BE", "ghent": "BE", "diegem": "BE",
    "madrid": "ES", "barcelona": "ES", "barcelone": "ES", "valencia": "ES", "lisbon": "PT", "lisboa": "PT",
    "lisbonne": "PT", "porto": "PT", "milan": "IT", "milano": "IT", "rome": "IT", "roma": "IT", "turin": "IT",
    "copenhagen": "DK", "copenhague": "DK", "stockholm": "SE", "oslo": "NO", "helsinki": "FI", "warsaw": "PL",
    "varsovie": "PL", "krakow": "PL", "prague": "CZ", "budapest": "HU", "bucharest": "RO", "bucarest": "RO",
    "sofia": "BG", "athens": "GR", "athenes": "GR", "tallinn": "EE", "riga": "LV", "vilnius": "LT",
    # Golfe et Moyen-Orient
    "dubai": "AE", "dubaï": "AE", "abu dhabi": "AE", "riyadh": "SA", "riyad": "SA", "jeddah": "SA",
    "doha": "QA", "kuwait city": "KW", "manama": "BH", "muscat": "OM", "tel aviv": "IL", "istanbul": "TR",
    # Asie et Océanie
    "singapore": "SG", "hong kong": "HK", "shanghai": "CN", "beijing": "CN", "shenzhen": "CN", "tokyo": "JP",
    "seoul": "KR", "mumbai": "IN", "bangalore": "IN", "bengaluru": "IN", "new delhi": "IN", "delhi": "IN",
    "gurgaon": "IN", "gurugram": "IN", "pune": "IN", "hyderabad": "IN", "chennai": "IN", "kuala lumpur": "MY",
    "bangkok": "TH", "jakarta": "ID", "ho chi minh": "VN", "hanoi": "VN", "manila": "PH", "taipei": "TW",
    "sydney": "AU", "melbourne": "AU", "brisbane": "AU", "auckland": "NZ",
    # Afrique et Amérique latine
    "casablanca": "MA", "rabat": "MA", "johannesburg": "ZA", "cape town": "ZA", "lagos": "NG", "nairobi": "KE",
    "cairo": "EG", "abidjan": "CI", "dakar": "SN", "tunis": "TN", "antananarivo": "MG", "mexico city": "MX",
    "sao paulo": "BR", "rio de janeiro": "BR", "buenos aires": "AR", "santiago": "CL", "bogota": "CO", "lima": "PE",
    # France (pour l'exclusion)
    "paris": "FR", "lyon": "FR", "marseille": "FR", "toulouse": "FR", "bordeaux": "FR", "lille": "FR",
    "nantes": "FR", "nice": "FR", "grenoble": "FR", "montpellier": "FR", "strasbourg": "FR", "rennes": "FR",
    "la defense": "FR", "boulogne-billancourt": "FR", "issy-les-moulineaux": "FR", "levallois-perret": "FR",
    "neuilly-sur-seine": "FR", "courbevoie": "FR", "puteaux": "FR", "massy": "FR", "clermont-ferrand": "FR",
    "sophia antipolis": "FR", "ile-de-france": "FR", "rueil-malmaison": "FR", "saint-denis": "FR", "nanterre": "FR",
}

ETATS_US = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
NOMS_ETATS_US = ["california", "texas", "new jersey", "massachusetts", "virginia", "illinois", "florida", "georgia", "colorado", "north carolina", "pennsylvania", "washington state", "connecticut", "maryland", "minnesota", "michigan", "ohio", "arizona", "utah", "oregon"]
PROVINCES_CA = {"ON", "QC", "BC", "AB", "MB", "NS"}

ZONES = {
    "US": "États-Unis", "CA": "Canada", "GB": "Royaume-Uni", "CH": "Suisse",
    "AE": "Golfe", "SA": "Golfe", "QA": "Golfe", "KW": "Golfe", "BH": "Golfe", "OM": "Golfe",
    "SG": "Asie", "HK": "Asie", "CN": "Asie", "JP": "Asie", "KR": "Asie", "IN": "Asie", "MY": "Asie",
    "TH": "Asie", "ID": "Asie", "VN": "Asie", "PH": "Asie", "TW": "Asie",
    "AU": "Océanie", "NZ": "Océanie",
    "MA": "Afrique", "ZA": "Afrique", "NG": "Afrique", "KE": "Afrique", "EG": "Afrique", "CI": "Afrique",
    "SN": "Afrique", "TN": "Afrique", "MG": "Afrique",
    "MX": "Amérique latine", "BR": "Amérique latine", "AR": "Amérique latine", "CL": "Amérique latine",
    "CO": "Amérique latine", "PE": "Amérique latine",
    "IL": "Moyen-Orient", "TR": "Europe", "FR": "France",
}
EUROPE_UE = set("IE DE AT NL BE LU ES PT IT DK SE NO FI PL CZ HU RO BG GR HR SK SI EE LV LT MT CY IS".split())

CODES_VILLES = {
    "new york": "NYC", "san francisco": "SFO", "boston": "BOS", "chicago": "CHI", "los angeles": "LAX",
    "seattle": "SEA", "washington": "WAS", "mclean": "WAS", "atlanta": "ATL", "austin": "AUS", "miami": "MIA",
    "toronto": "YTO", "montreal": "YMQ", "london": "LON", "dublin": "DUB", "zurich": "ZRH", "geneva": "GVA",
    "geneve": "GVA", "lausanne": "QLS", "basel": "BSL", "berlin": "BER", "munich": "MUC", "hamburg": "HAM",
    "frankfurt": "FRA", "vienna": "VIE", "amsterdam": "AMS", "hoofddorp": "AMS", "rotterdam": "RTM",
    "brussels": "BRU", "bruxelles": "BRU", "luxembourg": "LUX", "madrid": "MAD", "barcelona": "BCN",
    "lisbon": "LIS", "lisboa": "LIS", "lisbonne": "LIS", "milan": "MIL", "copenhagen": "CPH", "stockholm": "STO",
    "oslo": "OSL", "warsaw": "WAW", "prague": "PRG", "budapest": "BUD", "sofia": "SOF", "dubai": "DXB",
    "abu dhabi": "AUH", "riyadh": "RUH", "jeddah": "JED", "doha": "DOH", "singapore": "SIN", "hong kong": "HKG",
    "shanghai": "SHA", "beijing": "BJS", "tokyo": "TYO", "seoul": "SEL", "mumbai": "BOM", "bangalore": "BLR",
    "bengaluru": "BLR", "delhi": "DEL", "kuala lumpur": "KUL", "bangkok": "BKK", "jakarta": "JKT",
    "sydney": "SYD", "melbourne": "MEL", "casablanca": "CAS", "mexico city": "MEX", "sao paulo": "SAO",
}

_PAYS_ALIASES = sorted(((alias, iso) for iso, (_, aliases) in PAYS.items() for alias in aliases), key=lambda x: -len(x[0]))
_VILLES_TRIEES = sorted(VILLES.items(), key=lambda x: -len(x[0]))


def _cherche(mot, texte):
    return re.search(r"(?<![a-z])" + re.escape(mot) + r"(?![a-z])", texte)


def pays_detectes(lieu):
    """Liste ordonnée des codes pays présents dans un texte de localisation."""
    if not lieu:
        return []
    brut = lieu
    t = _norm(lieu)
    trouves = []

    def ajoute(pos, iso):
        trouves.append((pos, iso))

    for alias, iso in _PAYS_ALIASES:
        m = _cherche(alias, t)
        if m:
            ajoute(m.start(), iso)
    for ville, iso in _VILLES_TRIEES:
        m = _cherche(ville, t)
        if m:
            ajoute(m.start(), iso)
    # « Gerlingen, BW, DE » : le dernier code est un pays, pas l'État américain du Delaware.
    paire = re.search(r",\s*([A-Z]{2}),\s*([A-Z]{2})\s*$", brut)
    if paire and paire.group(2) in PAYS and paire.group(1) not in ETATS_US:
        ajoute(paire.start(2), paire.group(2))
    else:
        for m in re.finditer(r",\s*([A-Z]{2})\b", brut):
            code = m.group(1)
            if code in ETATS_US:
                ajoute(m.start(), "US")
            elif code in PROVINCES_CA:
                ajoute(m.start(), "CA")
    for nom in NOMS_ETATS_US:
        m = _cherche(nom, t)
        if m:
            ajoute(m.start(), "US")
    if re.search(r"\bremote\b", t) and re.search(r"\b(us|usa|united states)\b", t):
        ajoute(0, "US")
    vus, ordre = set(), []
    for _, iso in sorted(trouves):
        if iso not in vus:
            vus.add(iso)
            ordre.append(iso)
    return ordre


def nom_pays(iso):
    return PAYS.get(iso, (iso or "", []))[0]


def zone(iso):
    if not iso:
        return "Autre"
    if iso in EUROPE_UE:
        return "Europe"
    return ZONES.get(iso, "Autre")


def ville_principale(lieu):
    t = _norm(lieu)
    for ville, _ in _VILLES_TRIEES:
        if _cherche(ville, t):
            return ville
    return ""


def code_ville(lieu, iso):
    v = ville_principale(lieu)
    if v in CODES_VILLES:
        return CODES_VILLES[v]
    return (iso or "").upper()[:3] or "···"
