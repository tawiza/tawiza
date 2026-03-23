"""RSS Feed Configuration for Tawiza-V2 Intelligence Platform.

Organized by category with metadata for filtering, priority, and language.
Inspired by World Monitor's multi-variant feed architecture.
"""

from dataclasses import dataclass, field
from enum import Enum, StrEnum


class FeedCategory(StrEnum):
    """Feed categories for filtering and routing."""

    ECO_NATIONAL = "eco_national"  # National economic press
    ECO_REGIONAL = "eco_regional"  # Regional economic press (PACA focus)
    STARTUPS = "startups"  # Startup/innovation ecosystem
    INDUSTRY = "industry"  # Industry & manufacturing
    INSTITUTIONS = "institutions"  # Government, INSEE, Banque de France
    THINK_TANKS = "think_tanks"  # Economic research & analysis
    INTERNATIONAL = "international"  # World Monitor-style international
    TECH = "tech"  # Tech/AI/digital
    SECURITY = "security"  # Cybersecurity (ANSSI, CERT)
    ENVIRONMENT = "environment"  # Environment & energy


class FeedPriority(int, Enum):
    """Feed priority for processing order."""

    CRITICAL = 1  # Wire services, government
    HIGH = 2  # Major outlets
    MEDIUM = 3  # Specialty press
    LOW = 4  # Aggregators, blogs


@dataclass
class FeedConfig:
    """Configuration for a single RSS feed."""

    name: str
    url: str
    category: FeedCategory
    priority: FeedPriority = FeedPriority.MEDIUM
    language: str = "fr"
    region: str | None = None  # ISO region code or department
    refresh_interval: int = 300  # seconds (5min default)
    max_items: int = 20
    enabled: bool = True
    tags: list[str] = field(default_factory=list)


# =============================================================================
# FEED REGISTRY
# =============================================================================

FEEDS: list[FeedConfig] = [
    # =========================================================================
    # ECO_NATIONAL  -  Presse économique nationale
    # =========================================================================
    FeedConfig(
        "Les Échos",
        "https://www.lesechos.fr/rss/rss_une.xml",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.HIGH,
        enabled=False,
        tags=["macro", "finance"],
    ),
    FeedConfig(
        "Les Échos Entreprises",
        "https://www.lesechos.fr/rss/rss_entreprises.xml",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.HIGH,
        enabled=False,
        tags=["entreprises"],
    ),
    FeedConfig(
        "Les Échos PME",
        "https://entrepreneurs.lesechos.fr/",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.HIGH,
        enabled=False,
        tags=["pme", "eti"],
    ),
    FeedConfig(
        "Les Échos Start-up",
        "https://www.lesechos.fr/rss/rss_start-up.xml",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.HIGH,
        enabled=False,
        tags=["startups"],
    ),
    FeedConfig(
        "Le Figaro Économie",
        "https://www.lefigaro.fr/rss/figaro_economie.xml",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.HIGH,
        tags=["macro"],
    ),
    FeedConfig(
        "Le Figaro Conjoncture",
        "https://www.lefigaro.fr/rss/figaro_conjoncture.xml",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.MEDIUM,
        tags=["indicateurs"],
    ),
    FeedConfig(
        "Capital",
        "https://www.capital.fr/feed",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["finance", "patrimoine"],
    ),
    FeedConfig(
        "Challenges",
        "https://www.challenges.fr/feed",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["business"],
    ),
    FeedConfig(
        "BFM Business",
        "https://bfmbusiness.bfmtv.com/rss/info/flux-rss/flux-toutes-les-actualites.xml",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.MEDIUM,
        tags=["marchés"],
    ),
    FeedConfig(
        "L'Usine Nouvelle",
        "https://www.usinenouvelle.com/rss",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["industrie"],
    ),
    FeedConfig(
        "Le Journal des Entreprises",
        "https://www.lejournaldesentreprises.com/rss",
        FeedCategory.ECO_NATIONAL,
        FeedPriority.MEDIUM,
        tags=["entreprises", "régional"],
    ),
    # =========================================================================
    # ECO_REGIONAL  -  Presse régionale (priorité PACA / dept 13)
    # =========================================================================
    FeedConfig(
        "La Provence",
        "https://www.laprovence.com/feed",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.HIGH,
        region="13",
        enabled=False,
        tags=["marseille", "paca"],
    ),
    FeedConfig(
        "Marsactu",
        "https://marsactu.fr/feed/",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.HIGH,
        region="13",
        tags=["marseille", "métropole"],
    ),
    FeedConfig(
        "Made in Marseille",
        "https://madeinmarseille.net/feed/",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.HIGH,
        region="13",
        tags=["marseille", "eco"],
    ),
    FeedConfig(
        "GoMet",
        "https://gomet.net/feed/",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.HIGH,
        region="13",
        tags=["aix-marseille", "eco"],
    ),
    FeedConfig(
        "Destimed",
        "https://destimed.fr/feed/",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.MEDIUM,
        region="13",
        tags=["méditerranée"],
    ),
    FeedConfig(
        "France Bleu Provence",
        "https://www.francebleu.fr/rss/provence.xml",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.MEDIUM,
        region="13",
        enabled=False,
        tags=["info_locale"],
    ),
    FeedConfig(
        "JDE PACA",
        "https://www.lejournaldesentreprises.com/region/provence-alpes-cote-dazur/rss",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.HIGH,
        region="13",
        enabled=False,
        tags=["paca", "entreprises"],
    ),
    FeedConfig(
        "Var-Matin",
        "https://www.varmatin.com/feed",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.LOW,
        region="83",
        enabled=False,
        tags=["var"],
    ),
    FeedConfig(
        "Nice-Matin",
        "https://www.nicematin.com/feed",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.LOW,
        region="06",
        tags=["nice", "alpes-maritimes"],
    ),
    # Autres régions stratégiques
    FeedConfig(
        "Lyon Capitale",
        "https://www.lyoncapitale.fr/feed/",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.LOW,
        region="69",
        tags=["lyon", "aura"],
    ),
    FeedConfig(
        "Rue89 Lyon",
        "https://www.rue89lyon.fr/feed/",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.LOW,
        region="69",
        tags=["lyon"],
    ),
    FeedConfig(
        "Touleco",
        "https://www.touleco.fr/feed",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.LOW,
        region="31",
        enabled=False,
        tags=["toulouse", "occitanie"],
    ),
    FeedConfig(
        "Les Échos IDF",
        "https://www.lesechos.fr/pme-regions/ile-de-france/rss.xml",
        FeedCategory.ECO_REGIONAL,
        FeedPriority.LOW,
        region="75",
        enabled=False,
        tags=["paris", "idf"],
    ),
    # =========================================================================
    # STARTUPS  -  Écosystème startup/innovation
    # =========================================================================
    FeedConfig(
        "Maddyness",
        "https://www.maddyness.com/feed/",
        FeedCategory.STARTUPS,
        FeedPriority.HIGH,
        tags=["startups", "levées"],
    ),
    FeedConfig(
        "FrenchWeb",
        "https://www.frenchweb.fr/feed",
        FeedCategory.STARTUPS,
        FeedPriority.HIGH,
        tags=["startups", "tech"],
    ),
    FeedConfig(
        "Journal du Net",
        "https://www.journaldunet.com/rss/",
        FeedCategory.STARTUPS,
        FeedPriority.MEDIUM,
        tags=["digital", "business"],
    ),
    FeedConfig(
        "Frenchweb Decode",
        "https://decode.frenchweb.fr/feed",
        FeedCategory.STARTUPS,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["decode", "analyse"],
    ),
    FeedConfig(
        "Station F Blog",
        "https://stationf.co/blog/rss.xml",
        FeedCategory.STARTUPS,
        FeedPriority.LOW,
        enabled=False,
        tags=["incubateur", "paris"],
    ),
    # =========================================================================
    # INDUSTRY  -  Industrie & manufacturing
    # =========================================================================
    FeedConfig(
        "Usine Digitale",
        "https://www.usine-digitale.fr/rss",
        FeedCategory.INDUSTRY,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["digital", "industrie"],
    ),
    FeedConfig(
        "L'Usine Nouvelle Industrie",
        "https://www.usinenouvelle.com/rss",
        FeedCategory.INDUSTRY,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["industrie", "manufacturing"],
    ),
    FeedConfig(
        "Techniques de l'Ingénieur",
        "https://www.techniques-ingenieur.fr/feed/",
        FeedCategory.INDUSTRY,
        FeedPriority.LOW,
        enabled=False,
        tags=["ingénierie"],
    ),
    # =========================================================================
    # INSTITUTIONS  -  Gouvernement, INSEE, Banque de France
    # =========================================================================
    FeedConfig(
        "Ministère Économie",
        "https://www.economie.gouv.fr/rss",
        FeedCategory.INSTITUTIONS,
        FeedPriority.CRITICAL,
        tags=["gouv", "politique_eco"],
    ),
    FeedConfig(
        "INSEE Actualités",
        "https://www.insee.fr/fr/statistiques/flux-rss",
        FeedCategory.INSTITUTIONS,
        FeedPriority.CRITICAL,
        enabled=False,
        tags=["stats", "indicateurs"],
    ),
    FeedConfig(
        "Banque de France",
        "https://www.banque-france.fr/fr/rss.xml",
        FeedCategory.INSTITUTIONS,
        FeedPriority.CRITICAL,
        enabled=False,
        tags=["monétaire", "bdf"],
    ),
    FeedConfig(
        "DARES",
        "https://dares.travail-emploi.gouv.fr/rss.xml",
        FeedCategory.INSTITUTIONS,
        FeedPriority.HIGH,
        tags=["emploi", "travail"],
    ),
    FeedConfig(
        "Cour des Comptes",
        "https://www.ccomptes.fr/fr/rss.xml",
        FeedCategory.INSTITUTIONS,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["finances_publiques"],
    ),
    FeedConfig(
        "France Stratégie",
        "https://www.strategie.gouv.fr/feed",
        FeedCategory.INSTITUTIONS,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["prospective"],
    ),
    FeedConfig(
        "Vie Publique",
        "https://www.vie-publique.fr/rss.xml",
        FeedCategory.INSTITUTIONS,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["législation", "politique"],
    ),
    # =========================================================================
    # THINK_TANKS  -  Recherche économique
    # =========================================================================
    FeedConfig(
        "OFCE",
        "https://www.ofce.sciences-po.fr/feed/",
        FeedCategory.THINK_TANKS,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["conjoncture"],
    ),
    FeedConfig(
        "CEPII",
        "http://www.cepii.fr/rss/rss.xml",
        FeedCategory.THINK_TANKS,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["commerce_international"],
    ),
    FeedConfig(
        "Crédit Agricole Études",
        "https://etudes-economiques.credit-agricole.com/Flux-RSS",
        FeedCategory.THINK_TANKS,
        FeedPriority.LOW,
        enabled=False,
        tags=["analyses_eco"],
    ),
    FeedConfig(
        "BNP Paribas Research",
        "https://economic-research.bnpparibas.com/RSS/en-US",
        FeedCategory.THINK_TANKS,
        FeedPriority.LOW,
        language="en",
        tags=["recherche_eco"],
    ),
    FeedConfig(
        "Natixis Research",
        "https://www.research.natixis.com/feeds/rss",
        FeedCategory.THINK_TANKS,
        FeedPriority.LOW,
        enabled=False,
        tags=["recherche_eco"],
    ),
    # =========================================================================
    # INTERNATIONAL  -  Sources World Monitor style
    # =========================================================================
    FeedConfig(
        "France 24 FR",
        "https://www.france24.com/fr/rss",
        FeedCategory.INTERNATIONAL,
        FeedPriority.HIGH,
        tags=["monde", "géopolitique"],
    ),
    FeedConfig(
        "Le Monde",
        "https://www.lemonde.fr/rss/une.xml",
        FeedCategory.INTERNATIONAL,
        FeedPriority.HIGH,
        tags=["monde"],
    ),
    FeedConfig(
        "EuroNews FR",
        "https://fr.euronews.com/rss?format=xml",
        FeedCategory.INTERNATIONAL,
        FeedPriority.MEDIUM,
        tags=["europe"],
    ),
    FeedConfig(
        "Jeune Afrique",
        "https://www.jeuneafrique.com/feed/",
        FeedCategory.INTERNATIONAL,
        FeedPriority.MEDIUM,
        tags=["afrique"],
    ),
    FeedConfig(
        "BBC Afrique",
        "https://www.bbc.com/afrique/index.xml",
        FeedCategory.INTERNATIONAL,
        FeedPriority.MEDIUM,
        tags=["afrique"],
    ),
    FeedConfig(
        "L'Orient-Le Jour",
        "https://www.lorientlejour.com/rss",
        FeedCategory.INTERNATIONAL,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["moyen_orient", "liban"],
    ),
    FeedConfig(
        "Reuters World",
        "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best",
        FeedCategory.INTERNATIONAL,
        FeedPriority.HIGH,
        language="en",
        enabled=False,
        tags=["wire"],
    ),
    FeedConfig(
        "Al Jazeera",
        "https://www.aljazeera.com/xml/rss/all.xml",
        FeedCategory.INTERNATIONAL,
        FeedPriority.MEDIUM,
        language="en",
        tags=["monde"],
    ),
    # =========================================================================
    # TECH  -  Tech/AI/Digital
    # =========================================================================
    FeedConfig(
        "Le Monde Informatique",
        "https://www.lemondeinformatique.fr/flux-rss/thematique/toutes-les-actualites/rss.xml",
        FeedCategory.TECH,
        FeedPriority.MEDIUM,
        tags=["tech", "it"],
    ),
    FeedConfig(
        "01net",
        "https://www.01net.com/feed/",
        FeedCategory.TECH,
        FeedPriority.MEDIUM,
        tags=["tech", "consumer"],
    ),
    FeedConfig(
        "Siècle Digital",
        "https://siecledigital.fr/feed/",
        FeedCategory.TECH,
        FeedPriority.MEDIUM,
        tags=["digital", "marketing"],
    ),
    FeedConfig(
        "Hacker News",
        "https://hnrss.org/frontpage",
        FeedCategory.TECH,
        FeedPriority.MEDIUM,
        language="en",
        tags=["tech", "dev"],
    ),
    FeedConfig(
        "ArXiv CS.AI",
        "https://rss.arxiv.org/rss/cs.AI",
        FeedCategory.TECH,
        FeedPriority.LOW,
        language="en",
        tags=["ia", "recherche"],
    ),
    # =========================================================================
    # SECURITY  -  Cybersécurité
    # =========================================================================
    FeedConfig(
        "CERT-FR (ANSSI)",
        "https://www.cert.ssi.gouv.fr/feed/",
        FeedCategory.SECURITY,
        FeedPriority.CRITICAL,
        tags=["cyber", "alertes"],
    ),
    FeedConfig(
        "CERT-EU",
        "https://cert.europa.eu/publications/security-advisories/rss",
        FeedCategory.SECURITY,
        FeedPriority.HIGH,
        language="en",
        enabled=False,
        tags=["cyber", "europe"],
    ),
    FeedConfig(
        "Zataz",
        "https://www.zataz.com/feed/",
        FeedCategory.SECURITY,
        FeedPriority.MEDIUM,
        tags=["cyber", "france"],
    ),
    # =========================================================================
    # ENVIRONMENT  -  Environnement & énergie
    # =========================================================================
    FeedConfig(
        "Actu-Environnement",
        "https://www.actu-environnement.com/flux/rss/",
        FeedCategory.ENVIRONMENT,
        FeedPriority.MEDIUM,
        tags=["environnement"],
    ),
    FeedConfig(
        "Novethic",
        "https://www.novethic.fr/rss.xml",
        FeedCategory.ENVIRONMENT,
        FeedPriority.MEDIUM,
        enabled=False,
        tags=["rse", "climat"],
    ),
    FeedConfig(
        "Reporterre",
        "https://reporterre.net/spip.php?page=backend",
        FeedCategory.ENVIRONMENT,
        FeedPriority.LOW,
        tags=["écologie"],
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_feeds_by_category(category: FeedCategory) -> list[FeedConfig]:
    """Get all feeds for a given category."""
    return [f for f in FEEDS if f.category == category and f.enabled]


def get_feeds_by_region(region: str) -> list[FeedConfig]:
    """Get all feeds for a given region/department code."""
    return [f for f in FEEDS if f.region == region and f.enabled]


def get_feeds_by_priority(max_priority: FeedPriority) -> list[FeedConfig]:
    """Get feeds up to a given priority level."""
    return [f for f in FEEDS if f.priority.value <= max_priority.value and f.enabled]


def get_all_feed_urls() -> dict[str, str]:
    """Get all feeds as {name: url} dict (compatible with RssAdapter)."""
    return {f.name: f.url for f in FEEDS if f.enabled}


def get_feed_count() -> dict[str, int]:
    """Get feed count per category."""
    counts: dict[str, int] = {}
    for f in FEEDS:
        cat = f.category.value
        counts[cat] = counts.get(cat, 0) + 1
    return counts
