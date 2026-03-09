"""Query parser for territorial market analysis.

Transforms user queries into structured search strategies compatible with the Sirene API.
Uses a hybrid approach: static dictionary for common terms + LLM fallback for unknown terms.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ParsedQuery:
    """Structured representation of a parsed search query."""

    original: str
    keywords: list[str] = field(default_factory=list)
    naf_codes: list[str] = field(default_factory=list)
    region: str | None = None
    commune: str | None = None
    effectif_min: str | None = None
    search_strategies: list[dict[str, Any]] = field(default_factory=list)
    used_llm: bool = False


# =============================================================================
# DICTIONNAIRE TECH/IT
# =============================================================================
TECH_MAPPINGS = {
    # Intelligence Artificielle
    "ia": {
        "keywords": ["intelligence artificielle", "machine learning", "deep learning"],
        "naf_codes": ["62.01Z", "62.02A", "72.19Z"],
    },
    "intelligence artificielle": {
        "keywords": ["intelligence artificielle", "IA", "machine learning"],
        "naf_codes": ["62.01Z", "62.02A", "72.19Z"],
    },
    "machine learning": {
        "keywords": ["machine learning", "intelligence artificielle", "data science"],
        "naf_codes": ["62.01Z", "62.02A", "72.19Z"],
    },
    "deep learning": {
        "keywords": ["deep learning", "intelligence artificielle", "neural network"],
        "naf_codes": ["62.01Z", "72.19Z"],
    },

    # Data
    "data": {
        "keywords": ["data", "données", "analytics", "big data"],
        "naf_codes": ["62.01Z", "62.02A", "63.11Z"],
    },
    "data science": {
        "keywords": ["data science", "data analyst", "machine learning"],
        "naf_codes": ["62.01Z", "62.02A", "72.19Z"],
    },
    "big data": {
        "keywords": ["big data", "données massives", "analytics"],
        "naf_codes": ["62.01Z", "63.11Z"],
    },

    # Développement
    "dev": {
        "keywords": ["développement", "logiciel", "programmation"],
        "naf_codes": ["62.01Z"],
    },
    "développement": {
        "keywords": ["développement", "logiciel", "programmation", "software"],
        "naf_codes": ["62.01Z"],
    },
    "logiciel": {
        "keywords": ["logiciel", "software", "éditeur"],
        "naf_codes": ["62.01Z", "58.29A"],
    },
    "saas": {
        "keywords": ["saas", "logiciel", "cloud", "abonnement"],
        "naf_codes": ["62.01Z", "63.11Z", "58.29A"],
    },
    "web": {
        "keywords": ["web", "internet", "site", "application"],
        "naf_codes": ["62.01Z", "63.12Z"],
    },
    "mobile": {
        "keywords": ["mobile", "application", "smartphone", "android", "ios"],
        "naf_codes": ["62.01Z"],
    },

    # Cloud & Infra
    "cloud": {
        "keywords": ["cloud", "hébergement", "infrastructure", "aws", "azure"],
        "naf_codes": ["62.01Z", "62.03Z", "63.11Z"],
    },
    "hébergement": {
        "keywords": ["hébergement", "hosting", "serveur", "datacenter"],
        "naf_codes": ["63.11Z", "62.03Z"],
    },
    "infrastructure": {
        "keywords": ["infrastructure", "système", "réseau", "devops"],
        "naf_codes": ["62.03Z", "62.02A"],
    },

    # Cybersécurité
    "cybersécurité": {
        "keywords": ["cybersécurité", "sécurité informatique", "protection"],
        "naf_codes": ["62.01Z", "62.02A"],
    },
    "sécurité informatique": {
        "keywords": ["sécurité informatique", "cybersécurité", "protection données"],
        "naf_codes": ["62.01Z", "62.02A"],
    },

    # Startup/Innovation
    "startup": {
        "keywords": ["startup", "innovation", "tech", "numérique"],
        "naf_codes": ["62.01Z", "62.02A", "71.12B", "72.19Z"],
    },
    "innovation": {
        "keywords": ["innovation", "R&D", "recherche", "tech"],
        "naf_codes": ["72.19Z", "71.12B", "62.01Z"],
    },
    "tech": {
        "keywords": ["technologie", "numérique", "digital", "IT"],
        "naf_codes": ["62.01Z", "62.02A", "63.11Z"],
    },
    "numérique": {
        "keywords": ["numérique", "digital", "informatique"],
        "naf_codes": ["62.01Z", "62.02A", "63.12Z"],
    },
    "fintech": {
        "keywords": ["fintech", "finance", "technologie", "paiement"],
        "naf_codes": ["62.01Z", "64.19Z", "66.19B"],
    },
    "healthtech": {
        "keywords": ["healthtech", "santé", "médical", "e-santé"],
        "naf_codes": ["62.01Z", "72.11Z", "86.90D"],
    },
    "edtech": {
        "keywords": ["edtech", "éducation", "formation", "e-learning"],
        "naf_codes": ["62.01Z", "85.59A", "85.59B"],
    },
    "greentech": {
        "keywords": ["greentech", "environnement", "énergie", "durable"],
        "naf_codes": ["62.01Z", "71.12B", "72.19Z"],
    },

    # IoT & Hardware
    "iot": {
        "keywords": ["iot", "objets connectés", "capteurs", "embarqué"],
        "naf_codes": ["62.01Z", "26.11Z", "26.20Z"],
    },
    "robotique": {
        "keywords": ["robotique", "robot", "automatisation", "industrie 4.0"],
        "naf_codes": ["28.99B", "62.01Z", "72.19Z"],
    },
    "embarqué": {
        "keywords": ["embarqué", "systèmes embarqués", "firmware", "hardware"],
        "naf_codes": ["62.01Z", "26.11Z"],
    },

    # Blockchain
    "blockchain": {
        "keywords": ["blockchain", "crypto", "décentralisé", "web3"],
        "naf_codes": ["62.01Z", "63.11Z"],
    },
}


# =============================================================================
# DICTIONNAIRE SERVICES
# =============================================================================
SERVICES_MAPPINGS = {
    # Conseil - keywords plus spécifiques, pas de termes trop génériques
    "conseil": {
        "keywords": ["conseil", "consulting", "cabinet conseil"],
        "naf_codes": ["62.02A", "70.22Z"],
    },
    "consulting": {
        "keywords": ["consulting", "consultant", "cabinet"],
        "naf_codes": ["70.22Z", "62.02A"],
    },
    "stratégie": {
        "keywords": ["stratégie", "strategy", "management"],
        "naf_codes": ["70.22Z"],
    },
    "accompagnement": {
        "keywords": ["coaching", "mentoring"],
        "naf_codes": ["70.22Z", "85.59A"],
    },

    # IT Services
    "informatique": {
        "keywords": ["informatique", "IT", "système d'information"],
        "naf_codes": ["62.01Z", "62.02A", "62.09Z"],
    },
    "ssii": {
        "keywords": ["SSII", "ESN", "services numériques", "prestation"],
        "naf_codes": ["62.02A", "62.01Z"],
    },
    "esn": {
        "keywords": ["ESN", "SSII", "services numériques", "digital"],
        "naf_codes": ["62.02A", "62.01Z"],
    },
    "intégrateur": {
        "keywords": ["intégrateur", "intégration", "système", "ERP"],
        "naf_codes": ["62.02A", "62.09Z"],
    },
    "maintenance": {
        "keywords": ["maintenance", "support", "TMA", "infogérance"],
        "naf_codes": ["62.02B", "62.03Z"],
    },

    # Formation
    "formation": {
        "keywords": ["formation", "enseignement", "apprentissage", "cours"],
        "naf_codes": ["85.59A", "85.59B", "85.42Z"],
    },
    "e-learning": {
        "keywords": ["e-learning", "formation en ligne", "MOOC", "digital learning"],
        "naf_codes": ["85.59A", "62.01Z"],
    },

    # Audit
    "audit": {
        "keywords": ["audit", "contrôle", "conformité", "certification"],
        "naf_codes": ["69.20Z", "70.22Z", "71.20B"],
    },

    # RH
    "rh": {
        "keywords": ["ressources humaines", "RH", "recrutement", "emploi"],
        "naf_codes": ["78.10Z", "70.22Z"],
    },
    "recrutement": {
        "keywords": ["recrutement", "chasseur de têtes", "emploi", "talent"],
        "naf_codes": ["78.10Z"],
    },

    # Marketing & Communication
    "marketing": {
        "keywords": ["marketing", "communication", "publicité", "digital"],
        "naf_codes": ["73.11Z", "70.21Z", "73.12Z"],
    },
    "communication": {
        "keywords": ["communication", "agence", "média", "relations publiques"],
        "naf_codes": ["70.21Z", "73.11Z"],
    },
    "digital marketing": {
        "keywords": ["digital marketing", "SEO", "SEA", "social media"],
        "naf_codes": ["73.11Z", "73.12Z", "63.12Z"],
    },
    "agence web": {
        "keywords": ["agence web", "création site", "webdesign"],
        "naf_codes": ["62.01Z", "73.11Z", "74.10Z"],
    },

    # Design
    "design": {
        "keywords": ["design", "UX", "UI", "graphisme", "créatif"],
        "naf_codes": ["74.10Z", "73.11Z"],
    },
    "ux": {
        "keywords": ["UX", "expérience utilisateur", "design", "ergonomie"],
        "naf_codes": ["74.10Z", "62.01Z"],
    },
}


# =============================================================================
# DICTIONNAIRE INDUSTRIE
# =============================================================================
INDUSTRIE_MAPPINGS = {
    # Ingénierie
    "ingénierie": {
        "keywords": ["ingénierie", "bureau d'études", "conception", "R&D"],
        "naf_codes": ["71.12B", "71.12A"],
    },
    "bureau d'études": {
        "keywords": ["bureau d'études", "ingénierie", "conception", "calcul"],
        "naf_codes": ["71.12B"],
    },
    "r&d": {
        "keywords": ["R&D", "recherche", "développement", "innovation"],
        "naf_codes": ["72.19Z", "72.11Z", "71.12B"],
    },
    "recherche": {
        "keywords": ["recherche", "laboratoire", "scientifique", "R&D"],
        "naf_codes": ["72.19Z", "72.11Z", "72.20Z"],
    },

    # Énergie
    "énergie": {
        "keywords": ["énergie", "électricité", "renouvelable", "transition"],
        "naf_codes": ["35.11Z", "35.14Z", "71.12B"],
    },
    "renouvelable": {
        "keywords": ["renouvelable", "solaire", "éolien", "énergie verte"],
        "naf_codes": ["35.11Z", "71.12B", "43.21A"],
    },
    "hydrogène": {
        "keywords": ["hydrogène", "pile à combustible", "H2", "décarbonation"],
        "naf_codes": ["72.19Z", "71.12B", "20.11Z"],
    },
    "nucléaire": {
        "keywords": ["nucléaire", "atome", "réacteur", "énergie"],
        "naf_codes": ["71.12B", "72.19Z", "35.11Z"],
    },

    # BTP
    "btp": {
        "keywords": ["BTP", "bâtiment", "construction", "travaux publics"],
        "naf_codes": ["41.20A", "41.20B", "42.11Z"],
    },
    "construction": {
        "keywords": ["construction", "bâtiment", "immobilier", "promoteur"],
        "naf_codes": ["41.20A", "41.20B", "41.10A"],
    },
    "architecture": {
        "keywords": ["architecture", "architecte", "urbanisme", "maîtrise d'œuvre"],
        "naf_codes": ["71.11Z"],
    },

    # Manufacturing
    "industrie": {
        "keywords": ["industrie", "fabrication", "production", "usine"],
        "naf_codes": ["25.62A", "28.99B", "29.10Z"],
    },
    "manufacturing": {
        "keywords": ["manufacturing", "fabrication", "usinage", "production"],
        "naf_codes": ["25.62A", "28.41Z"],
    },
    "mécanique": {
        "keywords": ["mécanique", "usinage", "métallurgie", "pièces"],
        "naf_codes": ["25.62A", "25.61Z", "28.41Z"],
    },
    "électronique": {
        "keywords": ["électronique", "composants", "circuits", "cartes"],
        "naf_codes": ["26.11Z", "26.12Z", "26.20Z"],
    },
    "automobile": {
        "keywords": ["automobile", "véhicule", "voiture", "mobilité"],
        "naf_codes": ["29.10Z", "29.32Z", "45.11Z"],
    },
    "aéronautique": {
        "keywords": ["aéronautique", "aviation", "spatial", "aérospatial"],
        "naf_codes": ["30.30Z", "33.16Z", "71.12B"],
    },
    "ferroviaire": {
        "keywords": ["ferroviaire", "train", "rail", "transport"],
        "naf_codes": ["30.20Z", "42.12Z", "71.12B"],
    },

    # Logistique
    "logistique": {
        "keywords": ["logistique", "supply chain", "transport", "entreposage"],
        "naf_codes": ["52.10B", "52.29A", "49.41A"],
    },
    "transport": {
        "keywords": ["transport", "livraison", "fret", "messagerie"],
        "naf_codes": ["49.41A", "49.41B", "52.29A"],
    },

    # Environnement
    "environnement": {
        "keywords": ["environnement", "écologie", "développement durable", "RSE"],
        "naf_codes": ["71.12B", "74.90B", "38.21Z"],
    },
    "recyclage": {
        "keywords": ["recyclage", "déchets", "économie circulaire", "valorisation"],
        "naf_codes": ["38.21Z", "38.32Z", "46.77Z"],
    },

    # Biotech/Pharma
    "biotech": {
        "keywords": ["biotechnologie", "biotech", "sciences du vivant"],
        "naf_codes": ["72.11Z", "21.20Z"],
    },
    "pharma": {
        "keywords": ["pharmaceutique", "médicament", "santé", "laboratoire"],
        "naf_codes": ["21.20Z", "21.10Z", "72.11Z"],
    },
    "medtech": {
        "keywords": ["medtech", "dispositif médical", "santé", "diagnostic"],
        "naf_codes": ["26.60Z", "32.50A", "72.11Z"],
    },

    # Agroalimentaire
    "agroalimentaire": {
        "keywords": ["agroalimentaire", "alimentaire", "food", "agri"],
        "naf_codes": ["10.11Z", "10.51A", "10.89Z"],
    },
    "agriculture": {
        "keywords": ["agriculture", "agri", "ferme", "exploitation"],
        "naf_codes": ["01.11Z", "01.13Z", "01.50Z"],
    },
    "foodtech": {
        "keywords": ["foodtech", "alimentation", "innovation alimentaire"],
        "naf_codes": ["10.89Z", "62.01Z", "72.19Z"],
    },
}


# =============================================================================
# DICTIONNAIRE RÉGIONS
# =============================================================================
REGION_MAPPINGS = {
    # Hauts-de-France
    "hauts-de-france": "32",
    "hdf": "32",
    "nord": "32",
    "nord-pas-de-calais": "32",
    "picardie": "32",
    "lille": "32",
    "amiens": "32",
    "dunkerque": "32",
    "roubaix": "32",
    "tourcoing": "32",
    "valenciennes": "32",
    "lens": "32",
    "calais": "32",
    "arras": "32",
    "beauvais": "32",
    "compiègne": "32",

    # Île-de-France
    "ile-de-france": "11",
    "idf": "11",
    "paris": "11",
    "la défense": "11",
    "boulogne": "11",
    "nanterre": "11",
    "versailles": "11",
    "saint-denis": "11",

    # Auvergne-Rhône-Alpes
    "auvergne-rhone-alpes": "84",
    "ara": "84",
    "lyon": "84",
    "grenoble": "84",
    "saint-etienne": "84",
    "clermont-ferrand": "84",
    "annecy": "84",
    "chambéry": "84",

    # Nouvelle-Aquitaine
    "nouvelle-aquitaine": "75",
    "bordeaux": "75",
    "limoges": "75",
    "poitiers": "75",
    "la rochelle": "75",
    "pau": "75",
    "bayonne": "75",

    # Occitanie
    "occitanie": "76",
    "toulouse": "76",
    "montpellier": "76",
    "nîmes": "76",
    "perpignan": "76",
    "béziers": "76",

    # Bretagne
    "bretagne": "53",
    "rennes": "53",
    "brest": "53",
    "lorient": "53",
    "vannes": "53",
    "saint-brieuc": "53",
    "quimper": "53",

    # Pays de la Loire
    "pays-de-la-loire": "52",
    "pdl": "52",
    "nantes": "52",
    "angers": "52",
    "le mans": "52",
    "saint-nazaire": "52",

    # Grand Est
    "grand-est": "44",
    "strasbourg": "44",
    "metz": "44",
    "nancy": "44",
    "reims": "44",
    "mulhouse": "44",
    "colmar": "44",

    # Normandie
    "normandie": "28",
    "rouen": "28",
    "le havre": "28",
    "caen": "28",
    "cherbourg": "28",

    # Provence-Alpes-Côte d'Azur
    "provence-alpes-cote-d-azur": "93",
    "paca": "93",
    "marseille": "93",
    "nice": "93",
    "toulon": "93",
    "aix-en-provence": "93",
    "cannes": "93",
    "sophia antipolis": "93",

    # Centre-Val de Loire
    "centre-val-de-loire": "24",
    "orléans": "24",
    "tours": "24",
    "bourges": "24",
    "chartres": "24",

    # Bourgogne-Franche-Comté
    "bourgogne-franche-comte": "27",
    "dijon": "27",
    "besançon": "27",

    # Corse
    "corse": "94",
    "ajaccio": "94",
    "bastia": "94",
}


# Merge all term mappings
ALL_TERM_MAPPINGS = {**TECH_MAPPINGS, **SERVICES_MAPPINGS, **INDUSTRIE_MAPPINGS}


class QueryParser:
    """Parser for transforming user queries into Sirene API search strategies."""

    def __init__(self, use_llm_fallback: bool = True, ollama_model: str = "qwen3.5:27b"):
        """Initialize the query parser.

        Args:
            use_llm_fallback: Whether to use LLM for unknown terms
            ollama_model: Ollama model to use for fallback
        """
        self.use_llm_fallback = use_llm_fallback
        self.ollama_model = ollama_model

    async def parse(self, query: str) -> ParsedQuery:
        """Parse a user query into structured search parameters.

        Args:
            query: User's search query (e.g., "startups IA Hauts-de-France")

        Returns:
            ParsedQuery with keywords, NAF codes, region, and search strategies
        """
        result = ParsedQuery(original=query)
        query_lower = query.lower().strip()

        # Step 1: Extract region
        result.region, query_without_region = self._extract_region(query_lower)

        # Step 2: Match terms from dictionary
        matched_keywords: set[str] = set()
        matched_naf: set[str] = set()
        terms_found = []

        # Sort terms by length (longest first) to match specific terms before generic ones
        sorted_terms = sorted(ALL_TERM_MAPPINGS.keys(), key=len, reverse=True)

        for term in sorted_terms:
            # Use word boundary matching to avoid partial matches (e.g., "tech" in "biotech")
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, query_without_region, re.IGNORECASE):
                mapping = ALL_TERM_MAPPINGS[term]
                terms_found.append(term)
                matched_keywords.update(mapping["keywords"])
                matched_naf.update(mapping["naf_codes"])

        result.keywords = list(matched_keywords)
        result.naf_codes = list(matched_naf)

        # Step 3: LLM fallback if no matches found
        if not terms_found and self.use_llm_fallback:
            logger.info(f"No dictionary matches for '{query}', trying LLM fallback")
            llm_result = await self._llm_parse(query)
            if llm_result:
                result.keywords = llm_result.get("keywords", [])
                result.naf_codes = llm_result.get("naf_codes", [])
                result.used_llm = True

        # Step 4: Generate search strategies
        result.search_strategies = self._generate_strategies(result)

        logger.info(
            f"Parsed '{query}' -> {len(result.keywords)} keywords, "
            f"{len(result.naf_codes)} NAF codes, region={result.region}"
        )

        return result

    def _extract_region(self, query: str) -> tuple[str | None, str]:
        """Extract region from query and return (region_code, query_without_region)."""
        query_clean = query
        region_code = None

        # Sort by length descending to match longer terms first
        sorted_regions = sorted(REGION_MAPPINGS.keys(), key=len, reverse=True)

        for region_name in sorted_regions:
            if region_name in query:
                region_code = REGION_MAPPINGS[region_name]
                # Remove region from query for further processing
                query_clean = query.replace(region_name, " ").strip()
                query_clean = re.sub(r'\s+', ' ', query_clean)
                break

        return region_code, query_clean

    def _generate_strategies(self, parsed: ParsedQuery) -> list[dict[str, Any]]:
        """Generate search strategies based on parsed query.

        Priority order:
        1. NAF codes (most precise)
        2. Original query terms (user intent)
        3. Keywords from dictionary (fallback)
        """
        strategies = []

        if not parsed.keywords and not parsed.naf_codes:
            # Fallback: use original query
            strategies.append({
                "query": parsed.original,
                "naf": None,
            })
            return strategies

        # Strategy 1: Search with NAF codes (most precise)
        # NAF codes give exact activity matches
        if parsed.naf_codes:
            for naf in parsed.naf_codes[:3]:  # Top 3 NAF codes
                strategies.append({
                    "query": "",
                    "naf": naf,
                })

        # Strategy 2: Use original query words (minus region)
        # This captures user intent directly
        original_words = parsed.original.lower()
        # Remove region from original
        for region in REGION_MAPPINGS:
            original_words = original_words.replace(region, "").strip()

        if original_words and len(original_words) > 2:
            strategies.append({
                "query": original_words,
                "naf": None,
            })

        # Strategy 3: Top keyword only as fallback
        if parsed.keywords and len(strategies) < 4:
            # Only add first keyword if different from original
            first_keyword = parsed.keywords[0]
            if first_keyword.lower() not in original_words:
                strategies.append({
                    "query": first_keyword,
                    "naf": None,
                })

        # Deduplicate
        seen = set()
        unique_strategies = []
        for s in strategies:
            key = (s["query"], s.get("naf"))
            if key not in seen:
                seen.add(key)
                unique_strategies.append(s)

        return unique_strategies[:5]  # Max 5 strategies

    async def _llm_parse(self, query: str) -> dict[str, Any] | None:
        """Use LLM to parse unknown query terms."""
        try:
            from src.infrastructure.llm.ollama_client import OllamaClient

            ollama = OllamaClient(model=self.ollama_model)

            prompt = f"""Analyse cette requête de recherche d'entreprises françaises:
"{query}"

Réponds UNIQUEMENT en JSON valide avec ce format exact:
{{
  "keywords": ["mot-clé 1", "mot-clé 2", "mot-clé 3"],
  "sector": "secteur d'activité principal",
  "naf_codes": ["62.01Z", "62.02A"]
}}

Les keywords doivent être des termes que l'on peut trouver dans des noms d'entreprises.
Les codes NAF doivent être des codes réels (ex: 62.01Z = programmation informatique).
/no_think"""

            response = await ollama.generate(prompt)

            # Extract JSON from response
            import json

            # Try to find JSON in response
            text = response.get("response", "")
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)

            if json_match:
                return json.loads(json_match.group())

            return None

        except Exception as e:
            logger.warning(f"LLM parse failed: {e}")
            return None


async def parse_query(query: str, use_llm: bool = True) -> ParsedQuery:
    """Convenience function to parse a query.

    Args:
        query: User's search query
        use_llm: Whether to use LLM fallback

    Returns:
        ParsedQuery instance
    """
    parser = QueryParser(use_llm_fallback=use_llm)
    return await parser.parse(query)
