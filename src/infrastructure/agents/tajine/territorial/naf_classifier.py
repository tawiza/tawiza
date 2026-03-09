"""
NAF Classifier - Classifie les activités BODACC en sections NAF.

Les 21 sections NAF:
A - Agriculture, sylviculture et pêche
B - Industries extractives
C - Industrie manufacturière
D - Production et distribution d'électricité, gaz, vapeur
E - Eau, assainissement, gestion des déchets
F - Construction
G - Commerce, réparation d'automobiles
H - Transports et entreposage
I - Hébergement et restauration
J - Information et communication
K - Activités financières et d'assurance
L - Activités immobilières
M - Activités scientifiques et techniques
N - Services administratifs et de soutien
O - Administration publique
P - Enseignement
Q - Santé humaine et action sociale
R - Arts, spectacles et activités récréatives
S - Autres activités de services
T - Ménages employeurs
U - Organisations extraterritoriales
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class NAFSection:
    """Section NAF avec métadonnées."""
    code: str
    name: str
    short_name: str
    keywords: list[str]


# Définition des sections NAF avec mots-clés de classification
NAF_SECTIONS = [
    NAFSection("A", "Agriculture, sylviculture et pêche", "Agriculture", [
        "agricole", "agriculture", "ferme", "élevage", "pêche", "sylviculture",
        "viticulture", "maraîchage", "horticulture", "apiculture", "aquaculture"
    ]),
    NAFSection("B", "Industries extractives", "Extraction", [
        "extraction", "mine", "carrière", "pétrole", "gaz naturel"
    ]),
    NAFSection("C", "Industrie manufacturière", "Industrie", [
        "fabrication", "manufacture", "usine", "production industrielle",
        "agroalimentaire", "textile", "métallurgie", "chimie", "pharmaceutique",
        "électronique", "mécanique", "automobile", "aéronautique"
    ]),
    NAFSection("D", "Production d'électricité, gaz", "Énergie", [
        "électricité", "énergie", "gaz", "centrale", "solaire", "éolien"
    ]),
    NAFSection("E", "Eau, assainissement, déchets", "Environnement", [
        "eau", "assainissement", "déchet", "recyclage", "épuration", "collecte"
    ]),
    NAFSection("F", "Construction", "Construction", [
        "construction", "bâtiment", "btp", "maçonnerie", "plomberie", "électricité bâtiment",
        "menuiserie", "charpente", "couverture", "peinture bâtiment", "travaux",
        "rénovation", "gros œuvre", "second œuvre", "terrassement"
    ]),
    NAFSection("G", "Commerce, réparation auto", "Commerce", [
        "commerce", "vente", "détail", "gros", "magasin", "boutique", "négoce",
        "distribution", "supermarché", "épicerie", "automobile", "véhicule",
        "réparation auto", "garage", "e-commerce", "en ligne"
    ]),
    NAFSection("H", "Transports et entreposage", "Transport", [
        "transport", "livraison", "logistique", "entreposage", "stockage",
        "routier", "maritime", "aérien", "ferroviaire", "déménagement", "taxi", "vtc"
    ]),
    NAFSection("I", "Hébergement et restauration", "Hôtellerie-Resto", [
        "restaurant", "hôtel", "café", "bar", "traiteur", "restauration",
        "hébergement", "chambre d'hôte", "camping", "snack", "pizzeria",
        "brasserie", "fast-food", "food truck"
    ]),
    NAFSection("J", "Information et communication", "Tech & Média", [
        "informatique", "logiciel", "développement", "web", "numérique", "digital",
        "édition", "audiovisuel", "télécommunication", "presse", "radio", "télévision",
        "programmation", "data", "cloud", "saas", "application"
    ]),
    NAFSection("K", "Activités financières, assurance", "Finance", [
        "banque", "finance", "assurance", "crédit", "investissement", "gestion actifs",
        "courtage", "bourse", "fonds", "capital", "holding"
    ]),
    NAFSection("L", "Activités immobilières", "Immobilier", [
        "immobilier", "agence immobilière", "location", "gestion locative",
        "promotion immobilière", "sci", "foncier", "syndic", "copropriété"
    ]),
    NAFSection("M", "Activités scientifiques, techniques", "Conseil & Tech", [
        "conseil", "consulting", "ingénierie", "architecture", "expertise",
        "comptable", "juridique", "avocat", "notaire", "audit", "études",
        "recherche", "design", "publicité", "marketing", "communication"
    ]),
    NAFSection("N", "Services administratifs, soutien", "Services B2B", [
        "nettoyage", "sécurité", "gardiennage", "intérim", "travail temporaire",
        "secrétariat", "centre d'appel", "location véhicule", "voyage", "tourisme"
    ]),
    NAFSection("O", "Administration publique", "Admin publique", [
        "administration", "public", "gouvernement", "collectivité"
    ]),
    NAFSection("P", "Enseignement", "Éducation", [
        "enseignement", "formation", "école", "cours", "coaching", "soutien scolaire",
        "auto-école", "université", "éducation"
    ]),
    NAFSection("Q", "Santé et action sociale", "Santé & Social", [
        "santé", "médical", "infirmier", "aide à domicile", "ehpad",
        "crèche", "social", "handicap", "paramédical", "kinésithérapie",
        "ostéopathie", "psychologie", "bien-être"
    ]),
    NAFSection("R", "Arts, spectacles, loisirs", "Culture & Loisirs", [
        "art", "spectacle", "musique", "théâtre", "cinéma", "sport", "fitness",
        "loisir", "jeux", "événementiel", "photographe", "artiste"
    ]),
    NAFSection("S", "Autres activités de services", "Services divers", [
        "coiffure", "esthétique", "beauté", "réparation", "service à la personne",
        "pressing", "blanchisserie", "funéraire", "association"
    ]),
    NAFSection("T", "Ménages employeurs", "Particuliers", [
        "employeur particulier", "personnel de maison"
    ]),
]


class NAFClassifier:
    """Classifie les descriptions d'activités en sections NAF."""
    
    def __init__(self):
        self._sections = {s.code: s for s in NAF_SECTIONS}
        self._keyword_map = self._build_keyword_map()
    
    def _build_keyword_map(self) -> dict[str, str]:
        """Construit un mapping mot-clé → code section."""
        mapping = {}
        for section in NAF_SECTIONS:
            for kw in section.keywords:
                mapping[kw.lower()] = section.code
        return mapping
    
    def classify(self, activity_text: str) -> tuple[str, float]:
        """
        Classifie une description d'activité.
        
        Returns:
            (code_section, confidence) - ex: ("G", 0.8)
        """
        if not activity_text:
            return ("?", 0.0)
        
        text = activity_text.lower()
        
        # Compter les matches par section
        scores: dict[str, int] = {}
        
        for keyword, code in self._keyword_map.items():
            if keyword in text:
                scores[code] = scores.get(code, 0) + 1
        
        if not scores:
            return ("?", 0.0)
        
        # Prendre la section avec le plus de matches
        best_code = max(scores, key=lambda k: scores[k])
        confidence = min(1.0, scores[best_code] / 3)  # 3+ matches = 100%
        
        return (best_code, confidence)
    
    def classify_with_details(self, activity_text: str) -> dict[str, Any]:
        """
        Classifie avec détails complets.
        """
        code, confidence = self.classify(activity_text)
        section = self._sections.get(code)
        
        return {
            "code": code,
            "name": section.name if section else "Non classifié",
            "short_name": section.short_name if section else "Autre",
            "confidence": round(confidence, 2),
            "activity_text": activity_text[:100] if activity_text else None,
        }
    
    def get_section(self, code: str) -> NAFSection | None:
        """Retourne la section NAF par code."""
        return self._sections.get(code)
    
    @property
    def all_sections(self) -> list[NAFSection]:
        """Retourne toutes les sections."""
        return NAF_SECTIONS


# Singleton
_classifier: NAFClassifier | None = None


def get_naf_classifier() -> NAFClassifier:
    """Retourne le classifieur singleton."""
    global _classifier
    if _classifier is None:
        _classifier = NAFClassifier()
    return _classifier


def classify_bodacc_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Classifie un enregistrement BODACC.
    
    Extrait l'activité du champ listeetablissements et la classifie.
    """
    import json
    
    classifier = get_naf_classifier()
    
    # Extraire l'activité
    activity = None
    raw = record.get("raw", {})
    etab_str = raw.get("listeetablissements", "")
    
    if etab_str:
        try:
            etab = json.loads(etab_str) if isinstance(etab_str, str) else etab_str
            if isinstance(etab, dict) and "etablissement" in etab:
                activity = etab["etablissement"].get("activite", "")
        except (json.JSONDecodeError, TypeError):
            pass
    
    return classifier.classify_with_details(activity)
