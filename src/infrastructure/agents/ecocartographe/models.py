"""
Modèles de domaine pour EcoCartographe
Architecture DDD - Entités, Value Objects et Agrégats
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any
from uuid import uuid4


class ActeurType(StrEnum):
    """Types d'acteurs dans l'écosystème territorial"""
    ENTREPRISE = "entreprise"
    STARTUP = "startup"
    LABORATOIRE = "laboratoire"
    UNIVERSITE = "universite"
    CLUSTER = "cluster"
    POLE_COMPETITIVITE = "pole_competitivite"
    INCUBATEUR = "incubateur"
    ACCELERATEUR = "accelerateur"
    FINANCEUR = "financeur"
    COLLECTIVITE = "collectivite"
    ASSOCIATION = "association"
    AUTRE = "autre"


class RelationType(StrEnum):
    """Types de relations entre acteurs"""
    COLLABORATION = "collaboration"
    FINANCEMENT = "financement"
    INCUBATION = "incubation"
    PARTENARIAT = "partenariat"
    COTRAITANCE = "cotraitance"
    PROXIMITE_THEMATIQUE = "proximite_thematique"
    PROXIMITE_GEOGRAPHIQUE = "proximite_geographique"
    MEMBRE = "membre"
    PROJET_COMMUN = "projet_commun"
    SPIN_OFF = "spin_off"


class StatutProjet(StrEnum):
    """Statut du projet de cartographie"""
    BROUILLON = "brouillon"
    EN_COURS = "en_cours"
    EXTRACTION = "extraction"
    ANALYSE = "analyse"
    VISUALISATION = "visualisation"
    TERMINE = "termine"
    ERREUR = "erreur"


@dataclass
class Coordonnees:
    """Value Object - Coordonnées géographiques"""
    latitude: float
    longitude: float

    def distance_to(self, other: "Coordonnees") -> float:
        """Calcule la distance en km (formule de Haversine)"""
        from math import asin, cos, radians, sin, sqrt

        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(other.latitude), radians(other.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Rayon de la Terre en km

        return c * r

    def to_tuple(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)


@dataclass
class Adresse:
    """Value Object - Adresse postale"""
    rue: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    region: str | None = None
    pays: str = "France"
    coordonnees: Coordonnees | None = None


@dataclass
class MetriquesReseau:
    """Value Object - Métriques de centralité d'un acteur"""
    degre: float = 0.0
    centralite_intermediation: float = 0.0
    centralite_proximite: float = 0.0
    centralite_vecteur_propre: float = 0.0
    coefficient_clustering: float = 0.0

    @property
    def score_influence(self) -> float:
        """Score composite d'influence"""
        return (
            self.degre * 0.2 +
            self.centralite_intermediation * 0.3 +
            self.centralite_proximite * 0.2 +
            self.centralite_vecteur_propre * 0.3
        )


@dataclass
class Acteur:
    """Entité - Acteur de l'écosystème d'innovation"""
    id: str = field(default_factory=lambda: str(uuid4()))
    nom: str = ""
    type: ActeurType = ActeurType.AUTRE
    description: str | None = None
    adresse: Adresse | None = None
    site_web: str | None = None
    secteurs: list[str] = field(default_factory=list)
    mots_cles: list[str] = field(default_factory=list)
    metriques: MetriquesReseau = field(default_factory=MetriquesReseau)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    date_extraction: datetime = field(default_factory=datetime.utcnow)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Acteur):
            return self.id == other.id
        return False


@dataclass
class Relation:
    """Entité - Relation entre deux acteurs"""
    id: str = field(default_factory=lambda: str(uuid4()))
    source_id: str = ""
    cible_id: str = ""
    type: RelationType = RelationType.COLLABORATION
    force: float = 1.0  # Poids de la relation (0-1)
    bidirectionnelle: bool = True
    description: str | None = None
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    evidence: list[str] = field(default_factory=list)  # Preuves de la relation
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)


@dataclass
class Communaute:
    """Entité - Communauté détectée par algorithme de clustering"""
    id: str = field(default_factory=lambda: str(uuid4()))
    nom: str | None = None
    acteurs_ids: list[str] = field(default_factory=list)
    thematiques: list[str] = field(default_factory=list)
    centroide: Coordonnees | None = None
    metriques: dict[str, float] = field(default_factory=dict)

    @property
    def taille(self) -> int:
        return len(self.acteurs_ids)


@dataclass
class AnalyseReseau:
    """Value Object - Résultats d'analyse NetworkX"""
    nb_noeuds: int = 0
    nb_aretes: int = 0
    densite: float = 0.0
    diametre: int | None = None
    rayon: int | None = None
    coefficient_clustering_moyen: float = 0.0
    nb_composantes_connexes: int = 0
    modularite: float = 0.0
    acteurs_centraux: list[str] = field(default_factory=list)
    ponts: list[tuple[str, str]] = field(default_factory=list)
    communautes: list[Communaute] = field(default_factory=list)


@dataclass
class ConfigurationExtraction:
    """Value Object - Configuration pour l'extraction"""
    modele_spacy: str = "fr_core_news_lg"
    modele_ollama: str = "mistral:latest"
    seuil_proximite_km: float = 50.0
    seuil_similarite_thematique: float = 0.7
    types_entites: list[str] = field(default_factory=lambda: ["ORG", "LOC", "PERSON"])
    max_iterations: int = 15
    timeout_seconds: int = 300


@dataclass
class SourceDonnees:
    """Value Object - Source de données à ingérer"""
    id: str = field(default_factory=lambda: str(uuid4()))
    type: str = "csv"  # csv, excel, json, web, api
    chemin: str = ""
    url: str | None = None
    configuration: dict[str, Any] = field(default_factory=dict)
    date_ingestion: datetime | None = None
    nb_enregistrements: int = 0
    statut: str = "pending"  # pending, processing, completed, error
    erreur: str | None = None


@dataclass
class ResultatCartographie:
    """Agrégat racine - Résultat complet d'une cartographie"""
    acteurs: list[Acteur] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    analyse: AnalyseReseau = field(default_factory=AnalyseReseau)
    fichier_carte: str | None = None
    fichier_graphe: str | None = None
    fichier_rapport: str | None = None
    date_generation: datetime = field(default_factory=datetime.utcnow)

    @property
    def nb_acteurs(self) -> int:
        return len(self.acteurs)

    @property
    def nb_relations(self) -> int:
        return len(self.relations)


@dataclass
class ProjetCartographie:
    """Agrégat racine - Projet de cartographie d'écosystème"""
    id: str = field(default_factory=lambda: str(uuid4()))
    nom: str = ""
    description: str | None = None
    territoire: str | None = None  # ex: "Nouvelle-Aquitaine", "France"
    thematique: str | None = None  # ex: "AgriTech", "HealthTech"
    statut: StatutProjet = StatutProjet.BROUILLON
    configuration: ConfigurationExtraction = field(default_factory=ConfigurationExtraction)
    sources: list[SourceDonnees] = field(default_factory=list)
    resultat: ResultatCartographie | None = None
    progression: int = 0
    etape_courante: str = "Initialisation"
    logs: list[dict[str, Any]] = field(default_factory=list)
    date_creation: datetime = field(default_factory=datetime.utcnow)
    date_modification: datetime = field(default_factory=datetime.utcnow)
    date_completion: datetime | None = None
    erreur: str | None = None

    def ajouter_source(self, source: SourceDonnees) -> None:
        """Ajoute une source de données au projet"""
        self.sources.append(source)
        self.date_modification = datetime.utcnow()
        self._ajouter_log("info", f"Source ajoutée: {source.type} - {source.chemin or source.url}")

    def demarrer(self) -> None:
        """Démarre le projet de cartographie"""
        self.statut = StatutProjet.EN_COURS
        self.date_modification = datetime.utcnow()
        self._ajouter_log("info", "Projet démarré")

    def terminer(self, resultat: ResultatCartographie) -> None:
        """Termine le projet avec succès"""
        self.resultat = resultat
        self.statut = StatutProjet.TERMINE
        self.progression = 100
        self.date_completion = datetime.utcnow()
        self.date_modification = datetime.utcnow()
        self._ajouter_log("info", f"Projet terminé: {resultat.nb_acteurs} acteurs, {resultat.nb_relations} relations")

    def marquer_erreur(self, erreur: str) -> None:
        """Marque le projet en erreur"""
        self.statut = StatutProjet.ERREUR
        self.erreur = erreur
        self.date_modification = datetime.utcnow()
        self._ajouter_log("error", f"Erreur: {erreur}")

    def mettre_a_jour_progression(self, progression: int, etape: str) -> None:
        """Met à jour la progression du projet"""
        self.progression = min(100, max(0, progression))
        self.etape_courante = etape
        self.date_modification = datetime.utcnow()
        self._ajouter_log("info", f"[{progression}%] {etape}")

    def _ajouter_log(self, niveau: str, message: str) -> None:
        """Ajoute une entrée de log"""
        self.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "niveau": niveau,
            "message": message
        })

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le projet en dictionnaire"""
        return {
            "id": self.id,
            "nom": self.nom,
            "description": self.description,
            "territoire": self.territoire,
            "thematique": self.thematique,
            "statut": self.statut.value,
            "progression": self.progression,
            "etape_courante": self.etape_courante,
            "nb_sources": len(self.sources),
            "nb_acteurs": self.resultat.nb_acteurs if self.resultat else 0,
            "nb_relations": self.resultat.nb_relations if self.resultat else 0,
            "date_creation": self.date_creation.isoformat(),
            "date_modification": self.date_modification.isoformat(),
            "date_completion": self.date_completion.isoformat() if self.date_completion else None,
            "erreur": self.erreur
        }
