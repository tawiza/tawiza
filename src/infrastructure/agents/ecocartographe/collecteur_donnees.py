"""
Collecteur de Données Web pour EcoCartographe
Recherche et collecte automatiquement des données sur les acteurs d'innovation

Sources:
- Web scraping (annuaires, sites institutionnels)
- APIs publiques (data.gouv.fr, SIRENE, OpenStreetMap)
- Recherche web via Ollama pour analyse intelligente
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .models import Acteur, ActeurType, Adresse, ConfigurationExtraction, Coordonnees


@dataclass
class SourceWeb:
    """Configuration d'une source web à scraper"""
    nom: str
    url: str
    type_source: str  # annuaire, institutionnel, cluster, api
    selecteurs: dict[str, str] = field(default_factory=dict)
    pagination: str | None = None
    max_pages: int = 10


@dataclass
class ResultatRecherche:
    """Résultat d'une recherche de données"""
    acteurs: list[Acteur] = field(default_factory=list)
    sources_utilisees: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# Sources web connues par région/thématique
SOURCES_FRANCE = {
    "annuaires_nationaux": [
        SourceWeb(
            nom="French Tech",
            url="https://lafrenchtech.com/fr/la-france-est-une-tech/les-startups/",
            type_source="annuaire",
            selecteurs={"liste": ".startup-card", "nom": ".startup-name", "ville": ".startup-location"}
        ),
        SourceWeb(
            nom="BPI France",
            url="https://www.bpifrance.fr/",
            type_source="institutionnel"
        ),
    ],
    "clusters": [
        SourceWeb(
            nom="France Clusters",
            url="https://franceclusters.fr/annuaire/",
            type_source="cluster"
        ),
    ],
    "poles_competitivite": [
        SourceWeb(
            nom="Pôles de compétitivité",
            url="https://competitivite.gouv.fr/",
            type_source="institutionnel"
        ),
    ]
}

# APIs publiques françaises
APIS_PUBLIQUES = {
    "sirene": {
        "nom": "API SIRENE (via recherche-entreprises)",
        "url": "https://recherche-entreprises.api.gouv.fr/search",
        "description": "Base SIRENE des entreprises françaises",
        "auth_required": False  # Free API
    },
    "data_gouv": {
        "nom": "data.gouv.fr",
        "url": "https://www.data.gouv.fr/api/1",
        "description": "Données ouvertes du gouvernement français",
        "auth_required": False
    },
    "annuaire_entreprises": {
        "nom": "Annuaire des Entreprises",
        "url": "https://recherche-entreprises.api.gouv.fr",
        "description": "API de recherche d'entreprises (gratuite)",
        "auth_required": False
    },
    "nominatim": {
        "nom": "OpenStreetMap Nominatim",
        "url": "https://nominatim.openstreetmap.org",
        "description": "Géocodage gratuit",
        "auth_required": False
    }
}


class CollecteurDonnees:
    """
    Service de collecte automatique de données sur les acteurs d'innovation.

    Capacités:
    - Recherche d'entreprises par territoire et secteur
    - Scraping d'annuaires et sites institutionnels
    - Enrichissement des données (géocodage, secteurs, descriptions)
    - Génération de datasets structurés
    """

    def __init__(self, config: ConfigurationExtraction, output_dir: str = "./workspace/datasets"):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._http_client = None
        self._ollama_client = None
        self._rate_limit_delay = 1.0  # Délai entre requêtes (respect des sites)

        # Cache pour éviter les doublons
        self._acteurs_vus: set[str] = set()

    async def initialiser(self) -> None:
        """Initialise les clients HTTP et Ollama"""
        try:
            import httpx
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "EcoCartographe/1.0 (Research Bot; contact@example.com)",
                    "Accept": "text/html,application/json",
                    "Accept-Language": "fr-FR,fr;q=0.9"
                },
                follow_redirects=True
            )
            logger.info("Client HTTP initialisé")
        except ImportError:
            logger.warning("httpx non installé")

        try:
            import httpx
            self._ollama_client = httpx.AsyncClient(
                base_url="http://localhost:11434",
                timeout=60.0
            )
            logger.info("Client Ollama initialisé")
        except Exception as e:
            logger.warning(f"Ollama non disponible: {e}")

    async def fermer(self) -> None:
        """Ferme les connexions"""
        if self._http_client:
            await self._http_client.aclose()
        if self._ollama_client:
            await self._ollama_client.aclose()

    async def rechercher_acteurs(
        self,
        territoire: str,
        thematique: str | None = None,
        types_acteurs: list[ActeurType] | None = None,
        limite: int = 100
    ) -> ResultatRecherche:
        """
        Recherche automatique d'acteurs pour un territoire et une thématique.

        Args:
            territoire: Région, département ou ville cible
            thematique: Secteur d'activité (AgriTech, HealthTech, etc.)
            types_acteurs: Types d'acteurs à rechercher
            limite: Nombre maximum d'acteurs à collecter

        Returns:
            ResultatRecherche avec les acteurs trouvés
        """
        await self.initialiser()
        resultat = ResultatRecherche()

        logger.info(f"Recherche d'acteurs: {territoire}, thématique={thematique}")

        try:
            # 1. Recherche via l'API Annuaire des Entreprises (gratuite)
            acteurs_api = await self._rechercher_api_entreprises(
                territoire, thematique, limite // 2
            )
            resultat.acteurs.extend(acteurs_api)
            if acteurs_api:
                resultat.sources_utilisees.append("API Annuaire des Entreprises")

            # 2. Recherche via scraping de sources connues
            if len(resultat.acteurs) < limite:
                acteurs_web = await self._scraper_sources_web(
                    territoire, thematique, limite - len(resultat.acteurs)
                )
                resultat.acteurs.extend(acteurs_web)
                if acteurs_web:
                    resultat.sources_utilisees.append("Sources web (scraping)")

            # 3. Recherche intelligente via Ollama si disponible
            if len(resultat.acteurs) < limite and self._ollama_client:
                acteurs_llm = await self._rechercher_via_ollama(
                    territoire, thematique, limite - len(resultat.acteurs)
                )
                resultat.acteurs.extend(acteurs_llm)
                if acteurs_llm:
                    resultat.sources_utilisees.append("Recherche LLM (Ollama)")

            # 4. Dédupliquer et enrichir
            resultat.acteurs = self._dedupliquer_acteurs(resultat.acteurs)
            await self._enrichir_acteurs(resultat.acteurs)

            resultat.metadata = {
                "territoire": territoire,
                "thematique": thematique,
                "nb_acteurs": len(resultat.acteurs),
                "date_collecte": datetime.utcnow().isoformat()
            }

            logger.info(f"Collecte terminée: {len(resultat.acteurs)} acteurs")

        except Exception as e:
            logger.exception("Erreur lors de la recherche")
            resultat.erreurs.append(str(e))

        finally:
            await self.fermer()

        return resultat

    async def _rechercher_api_entreprises(
        self,
        territoire: str,
        thematique: str | None,
        limite: int
    ) -> list[Acteur]:
        """Recherche via l'API Annuaire des Entreprises (recherche-entreprises.api.gouv.fr)"""
        acteurs = []

        if not self._http_client:
            return acteurs

        try:
            # Construire la requête
            params = {
                "q": f"{thematique or 'innovation'} {territoire}",
                "per_page": min(limite, 25),
                "page": 1
            }

            # Ajouter le code région si possible
            code_region = self._territoire_vers_code_region(territoire)
            if code_region:
                params["code_region"] = code_region

            url = f"{APIS_PUBLIQUES['annuaire_entreprises']['url']}/search"

            pages_restantes = (limite // 25) + 1

            for page in range(1, pages_restantes + 1):
                params["page"] = page

                response = await self._http_client.get(url, params=params)

                if response.status_code != 200:
                    logger.warning(f"API Entreprises: {response.status_code}")
                    break

                data = response.json()
                results = data.get("results", [])

                if not results:
                    break

                for entreprise in results:
                    acteur = self._entreprise_api_vers_acteur(entreprise)
                    if acteur and acteur.nom.lower() not in self._acteurs_vus:
                        acteurs.append(acteur)
                        self._acteurs_vus.add(acteur.nom.lower())

                if len(acteurs) >= limite:
                    break

                await asyncio.sleep(self._rate_limit_delay)

            logger.info(f"API Entreprises: {len(acteurs)} acteurs trouvés")

        except Exception as e:
            logger.warning(f"Erreur API Entreprises: {e}")

        return acteurs[:limite]

    def _entreprise_api_vers_acteur(self, data: dict[str, Any]) -> Acteur | None:
        """Convertit une entreprise de l'API en Acteur"""
        try:
            nom = data.get("nom_complet") or data.get("nom_raison_sociale", "")
            if not nom or len(nom) < 2:
                return None

            # Déterminer le type
            nature = data.get("nature_juridique", "")
            categorie = data.get("categorie_entreprise", "")
            activite = data.get("activite_principale", "")

            type_acteur = self._determiner_type_depuis_api(nature, categorie, activite, nom)

            # Adresse
            siege = data.get("siege", {})
            adresse = None
            if siege:
                adresse = Adresse(
                    rue=siege.get("adresse"),
                    code_postal=siege.get("code_postal"),
                    ville=siege.get("libelle_commune"),
                    region=siege.get("libelle_region")
                )

                # Coordonnées si disponibles
                if siege.get("latitude") and siege.get("longitude"):
                    adresse.coordonnees = Coordonnees(
                        latitude=float(siege["latitude"]),
                        longitude=float(siege["longitude"])
                    )

            acteur = Acteur(
                nom=nom,
                type=type_acteur,
                adresse=adresse,
                site_web=data.get("site_web"),
                secteurs=[data.get("libelle_activite_principale", "")] if data.get("libelle_activite_principale") else [],
                source="API Annuaire des Entreprises",
                metadata={
                    "siren": data.get("siren"),
                    "siret": data.get("siege", {}).get("siret"),
                    "date_creation": data.get("date_creation"),
                    "tranche_effectif": data.get("tranche_effectif_salarie")
                }
            )

            return acteur

        except Exception as e:
            logger.warning(f"Erreur conversion entreprise: {e}")
            return None

    def _determiner_type_depuis_api(
        self,
        nature_juridique: str,
        categorie: str,
        activite: str,
        nom: str
    ) -> ActeurType:
        """Détermine le type d'acteur depuis les données API"""
        nom_lower = nom.lower()
        activite_lower = activite.lower() if activite else ""

        # Patterns de détection
        if any(kw in nom_lower for kw in ['université', 'univ ', 'ufr', 'iut', 'école', 'institut']):
            return ActeurType.UNIVERSITE
        elif any(kw in nom_lower for kw in ['laboratoire', 'lab ', 'cnrs', 'inria', 'cea', 'inserm', 'inrae']):
            return ActeurType.LABORATOIRE
        elif any(kw in nom_lower for kw in ['cluster', 'pôle', 'pole competitivite', 'technopole']):
            return ActeurType.POLE_COMPETITIVITE
        elif any(kw in nom_lower for kw in ['incubateur', 'pépinière', 'pepiniere']):
            return ActeurType.INCUBATEUR
        elif any(kw in nom_lower for kw in ['accelerateur', 'accélérateur']):
            return ActeurType.ACCELERATEUR
        elif any(kw in nom_lower for kw in ['startup', 'start-up', 'start up']):
            return ActeurType.STARTUP
        elif any(kw in nom_lower for kw in ['region', 'département', 'mairie', 'métropole', 'communauté']):
            return ActeurType.COLLECTIVITE
        elif any(kw in nom_lower for kw in ['banque', 'bpi', 'capital', 'invest', 'ventures']):
            return ActeurType.FINANCEUR
        elif any(kw in nom_lower for kw in ['association', 'asso ', 'fédération']):
            return ActeurType.ASSOCIATION
        elif '72' in activite_lower or 'recherche' in activite_lower:
            return ActeurType.LABORATOIRE
        elif categorie == "PME" or categorie == "TPE":
            return ActeurType.STARTUP
        else:
            return ActeurType.ENTREPRISE

    async def _scraper_sources_web(
        self,
        territoire: str,
        thematique: str | None,
        limite: int
    ) -> list[Acteur]:
        """Scrape des sources web connues"""
        acteurs = []

        if not self._http_client:
            return acteurs

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("BeautifulSoup non installé, scraping désactivé")
            return acteurs

        # Recherche Google/DuckDuckGo pour trouver des listes d'acteurs
        queries = [
            f"startups {thematique or 'innovation'} {territoire}",
            f"entreprises innovantes {territoire}",
            f"écosystème innovation {territoire}",
            f"incubateurs accelerateurs {territoire}"
        ]

        for query in queries[:2]:  # Limiter le nombre de recherches
            try:
                # Utiliser DuckDuckGo HTML (pas d'API key nécessaire)
                url = f"https://html.duckduckgo.com/html/?q={query}"
                response = await self._http_client.get(url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Extraire les résultats
                    for result in soup.select('.result__body')[:10]:
                        title_elem = result.select_one('.result__title')
                        snippet_elem = result.select_one('.result__snippet')
                        link_elem = result.select_one('.result__url')

                        if title_elem:
                            titre = title_elem.get_text(strip=True)
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            url_result = link_elem.get_text(strip=True) if link_elem else ""

                            # Extraire les noms d'entreprises du titre/snippet
                            noms_extraits = await self._extraire_noms_entreprises(
                                f"{titre} {snippet}",
                                territoire
                            )

                            for nom in noms_extraits:
                                if nom.lower() not in self._acteurs_vus:
                                    acteur = Acteur(
                                        nom=nom,
                                        type=ActeurType.ENTREPRISE,
                                        description=snippet[:200] if snippet else None,
                                        source=f"Web search: {query}",
                                        metadata={"query": query, "url_source": url_result}
                                    )
                                    acteurs.append(acteur)
                                    self._acteurs_vus.add(nom.lower())

                await asyncio.sleep(self._rate_limit_delay * 2)  # Plus prudent pour le scraping

                if len(acteurs) >= limite:
                    break

            except Exception as e:
                logger.debug(f"Scraping failed for query '{query}': {e}")

        logger.info(f"Scraping web: {len(acteurs)} acteurs trouvés")
        return acteurs[:limite]

    async def _extraire_noms_entreprises(self, texte: str, territoire: str) -> list[str]:
        """Utilise des heuristiques pour extraire les noms d'entreprises"""
        noms = []

        # Patterns courants pour les noms d'entreprises
        patterns = [
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s+(?:SAS|SARL|SA|SNC|EURL|SASU)',
            r'\b([A-Z][a-zA-Z]+(?:Tech|Lab|AI|Data|Cloud|Bio|Med|Agri|Green|Smart))\b',
            r'(?:startup|entreprise|société)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, texte)
            for match in matches:
                nom = match.strip()
                if len(nom) >= 3 and nom.lower() not in ['sas', 'sarl', 'france', territoire.lower()]:
                    noms.append(nom)

        return list(set(noms))[:5]  # Limiter à 5 noms par texte

    async def _rechercher_via_ollama(
        self,
        territoire: str,
        thematique: str | None,
        limite: int
    ) -> list[Acteur]:
        """Utilise Ollama pour générer/rechercher des acteurs connus"""
        acteurs = []

        if not self._ollama_client:
            return acteurs

        try:
            prompt = f"""Tu es un expert de l'écosystème d'innovation français.

Liste les acteurs de l'innovation (startups, entreprises, labs, incubateurs, clusters)
dans la région {territoire}{f" dans le secteur {thematique}" if thematique else ""}.

Pour chaque acteur, donne:
- Nom exact
- Type (startup/entreprise/laboratoire/incubateur/cluster/université/financeur)
- Ville
- Secteur d'activité
- Description courte (1 phrase)

Format JSON:
[
  {{"nom": "...", "type": "...", "ville": "...", "secteur": "...", "description": "..."}}
]

Liste {min(limite, 20)} acteurs réels et vérifiables."""

            response = await self._ollama_client.post(
                "/api/generate",
                json={
                    "model": self.config.modele_ollama,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
            )

            if response.status_code == 200:
                result = response.json()
                texte = result.get("response", "")

                # Extraire le JSON
                json_match = re.search(r'\[.*\]', texte, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        for item in data:
                            if item.get("nom") and item["nom"].lower() not in self._acteurs_vus:
                                acteur = Acteur(
                                    nom=item["nom"],
                                    type=self._str_vers_type(item.get("type", "entreprise")),
                                    description=item.get("description"),
                                    adresse=Adresse(ville=item.get("ville")) if item.get("ville") else None,
                                    secteurs=[item.get("secteur")] if item.get("secteur") else [],
                                    source="Ollama LLM",
                                    metadata={"generated": True, "needs_verification": True}
                                )
                                acteurs.append(acteur)
                                self._acteurs_vus.add(acteur.nom.lower())
                    except json.JSONDecodeError:
                        logger.warning("Impossible de parser la réponse Ollama")

            logger.info(f"Ollama: {len(acteurs)} acteurs générés")

        except Exception as e:
            logger.warning(f"Erreur Ollama: {e}")

        return acteurs[:limite]

    def _str_vers_type(self, s: str) -> ActeurType:
        """Convertit une chaîne en ActeurType"""
        mapping = {
            "startup": ActeurType.STARTUP,
            "entreprise": ActeurType.ENTREPRISE,
            "laboratoire": ActeurType.LABORATOIRE,
            "lab": ActeurType.LABORATOIRE,
            "université": ActeurType.UNIVERSITE,
            "universite": ActeurType.UNIVERSITE,
            "incubateur": ActeurType.INCUBATEUR,
            "accélérateur": ActeurType.ACCELERATEUR,
            "accelerateur": ActeurType.ACCELERATEUR,
            "cluster": ActeurType.CLUSTER,
            "pôle": ActeurType.POLE_COMPETITIVITE,
            "pole": ActeurType.POLE_COMPETITIVITE,
            "financeur": ActeurType.FINANCEUR,
            "investisseur": ActeurType.FINANCEUR,
            "collectivité": ActeurType.COLLECTIVITE,
            "collectivite": ActeurType.COLLECTIVITE,
            "association": ActeurType.ASSOCIATION
        }
        return mapping.get(s.lower(), ActeurType.ENTREPRISE)

    def _territoire_vers_code_region(self, territoire: str) -> str | None:
        """Convertit un nom de territoire en code région INSEE"""
        regions = {
            "ile-de-france": "11", "idf": "11", "paris": "11",
            "nouvelle-aquitaine": "75", "bordeaux": "75", "aquitaine": "75",
            "occitanie": "76", "toulouse": "76", "montpellier": "76",
            "auvergne-rhone-alpes": "84", "lyon": "84", "auvergne": "84",
            "provence-alpes-cote-d-azur": "93", "paca": "93", "marseille": "93",
            "bretagne": "53", "rennes": "53",
            "pays-de-la-loire": "52", "nantes": "52",
            "hauts-de-france": "32", "lille": "32",
            "grand-est": "44", "strasbourg": "44",
            "normandie": "28", "rouen": "28",
            "centre-val-de-loire": "24", "tours": "24", "orleans": "24",
            "bourgogne-franche-comte": "27", "dijon": "27",
            "corse": "94", "ajaccio": "94"
        }

        territoire_lower = territoire.lower().replace(" ", "-").replace("'", "-")

        for key, code in regions.items():
            if key in territoire_lower or territoire_lower in key:
                return code

        return None

    async def _enrichir_acteurs(self, acteurs: list[Acteur]) -> None:
        """Enrichit les acteurs avec des données supplémentaires (géocodage, etc.)"""
        if not self._http_client:
            return

        for acteur in acteurs:
            # Géocodage si adresse sans coordonnées
            if acteur.adresse and not acteur.adresse.coordonnees:
                if acteur.adresse.ville or acteur.adresse.rue:
                    coords = await self._geocoder_adresse(acteur.adresse)
                    if coords:
                        acteur.adresse.coordonnees = coords
                    await asyncio.sleep(self._rate_limit_delay)

    async def _geocoder_adresse(self, adresse: Adresse) -> Coordonnees | None:
        """Géocode une adresse via Nominatim"""
        try:
            adresse_str = " ".join(filter(None, [
                adresse.rue,
                adresse.code_postal,
                adresse.ville,
                "France"
            ]))

            response = await self._http_client.get(
                f"{APIS_PUBLIQUES['nominatim']['url']}/search",
                params={"q": adresse_str, "format": "json", "limit": 1}
            )

            if response.status_code == 200:
                results = response.json()
                if results:
                    return Coordonnees(
                        latitude=float(results[0]["lat"]),
                        longitude=float(results[0]["lon"])
                    )
        except Exception as e:
            logger.debug(f"Erreur géocodage: {e}")

        return None

    def _dedupliquer_acteurs(self, acteurs: list[Acteur]) -> list[Acteur]:
        """Déduplique les acteurs par nom normalisé"""
        vus: dict[str, Acteur] = {}

        for acteur in acteurs:
            nom_normalise = acteur.nom.lower().strip()
            # Nettoyer les suffixes juridiques
            for suffixe in [' sas', ' sarl', ' sa', ' sasu', ' eurl', ' snc']:
                nom_normalise = nom_normalise.replace(suffixe, '')

            if nom_normalise not in vus:
                vus[nom_normalise] = acteur
            else:
                # Fusionner les données
                existant = vus[nom_normalise]
                if not existant.description and acteur.description:
                    existant.description = acteur.description
                if not existant.adresse and acteur.adresse:
                    existant.adresse = acteur.adresse
                if acteur.secteurs:
                    existant.secteurs = list(set(existant.secteurs + acteur.secteurs))

        return list(vus.values())

    async def sauvegarder_dataset(
        self,
        resultat: ResultatRecherche,
        nom_fichier: str,
        format: str = "json"
    ) -> str:
        """Sauvegarde le résultat de recherche en dataset"""
        chemin = self.output_dir / nom_fichier

        if format == "json":
            data = {
                "metadata": resultat.metadata,
                "sources": resultat.sources_utilisees,
                "acteurs": [
                    {
                        "nom": a.nom,
                        "type": a.type.value,
                        "description": a.description,
                        "adresse": {
                            "rue": a.adresse.rue if a.adresse else None,
                            "code_postal": a.adresse.code_postal if a.adresse else None,
                            "ville": a.adresse.ville if a.adresse else None,
                            "region": a.adresse.region if a.adresse else None,
                        } if a.adresse else None,
                        "coordonnees": {
                            "latitude": a.adresse.coordonnees.latitude,
                            "longitude": a.adresse.coordonnees.longitude
                        } if a.adresse and a.adresse.coordonnees else None,
                        "site_web": a.site_web,
                        "secteurs": a.secteurs,
                        "source": a.source,
                        "metadata": a.metadata
                    }
                    for a in resultat.acteurs
                ]
            }

            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        elif format == "csv":
            import csv
            chemin = chemin.with_suffix('.csv')

            with open(chemin, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'nom', 'type', 'description', 'ville', 'code_postal',
                    'region', 'latitude', 'longitude', 'site_web', 'secteurs'
                ])
                writer.writeheader()

                for a in resultat.acteurs:
                    writer.writerow({
                        'nom': a.nom,
                        'type': a.type.value,
                        'description': a.description or '',
                        'ville': a.adresse.ville if a.adresse else '',
                        'code_postal': a.adresse.code_postal if a.adresse else '',
                        'region': a.adresse.region if a.adresse else '',
                        'latitude': a.adresse.coordonnees.latitude if a.adresse and a.adresse.coordonnees else '',
                        'longitude': a.adresse.coordonnees.longitude if a.adresse and a.adresse.coordonnees else '',
                        'site_web': a.site_web or '',
                        'secteurs': ', '.join(a.secteurs)
                    })

        logger.info(f"Dataset sauvegardé: {chemin}")
        return str(chemin)


class EnrichisseurDonnees:
    """
    Service d'enrichissement des données existantes.
    Complète les informations manquantes sur les acteurs.
    """

    def __init__(self, config: ConfigurationExtraction):
        self.config = config
        self._http_client = None
        self._ollama_client = None

    async def initialiser(self) -> None:
        """Initialise les clients"""
        import httpx
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._ollama_client = httpx.AsyncClient(base_url="http://localhost:11434", timeout=60.0)

    async def enrichir_acteur(self, acteur: Acteur) -> Acteur:
        """Enrichit un acteur avec des données complémentaires"""

        # 1. Géocodage si manquant
        if acteur.adresse and not acteur.adresse.coordonnees:
            await self._geocoder_acteur(acteur)

        # 2. Recherche site web si manquant
        if not acteur.site_web:
            acteur.site_web = await self._rechercher_site_web(acteur.nom)

        # 3. Enrichissement description via LLM si manquante
        if not acteur.description and self._ollama_client:
            acteur.description = await self._generer_description(acteur)

        # 4. Classification secteurs si manquants
        if not acteur.secteurs:
            acteur.secteurs = await self._classifier_secteurs(acteur)

        return acteur

    async def _geocoder_acteur(self, acteur: Acteur) -> None:
        """Géocode l'adresse d'un acteur"""
        if not acteur.adresse:
            return

        try:
            adresse_str = " ".join(filter(None, [
                acteur.adresse.rue,
                acteur.adresse.code_postal,
                acteur.adresse.ville,
                "France"
            ]))

            response = await self._http_client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": adresse_str, "format": "json", "limit": 1},
                headers={"User-Agent": "EcoCartographe/1.0"}
            )

            if response.status_code == 200:
                results = response.json()
                if results:
                    acteur.adresse.coordonnees = Coordonnees(
                        latitude=float(results[0]["lat"]),
                        longitude=float(results[0]["lon"])
                    )
        except Exception as e:
            logger.debug(f"Erreur géocodage: {e}")

    async def _rechercher_site_web(self, nom: str) -> str | None:
        """Recherche le site web d'un acteur"""
        try:
            # Recherche simple via DuckDuckGo
            response = await self._http_client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"{nom} site officiel"},
                headers={"User-Agent": "EcoCartographe/1.0"}
            )

            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                for result in soup.select('.result__url')[:3]:
                    url = result.get_text(strip=True)
                    if url and nom.lower().split()[0] in url.lower():
                        return f"https://{url}" if not url.startswith('http') else url
        except Exception as e:
            logger.debug(f"Website search failed for {nom}: {e}")

        return None

    async def _generer_description(self, acteur: Acteur) -> str | None:
        """Génère une description via Ollama"""
        try:
            response = await self._ollama_client.post(
                "/api/generate",
                json={
                    "model": self.config.modele_ollama,
                    "prompt": f"Décris brièvement (1-2 phrases) l'activité de {acteur.nom}, une {acteur.type.value} française. Réponds directement avec la description.",
                    "stream": False,
                    "options": {"temperature": 0.3, "max_tokens": 100}
                }
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()[:200]
        except Exception as e:
            logger.debug(f"Failed to generate description for {acteur.nom}: {e}")

        return None

    async def _classifier_secteurs(self, acteur: Acteur) -> list[str]:
        """Classifie les secteurs d'activité via LLM"""
        if not self._ollama_client:
            return []

        try:
            response = await self._ollama_client.post(
                "/api/generate",
                json={
                    "model": self.config.modele_ollama,
                    "prompt": f"Quels sont les secteurs d'activité de {acteur.nom} ({acteur.type.value})? Liste 1 à 3 secteurs, séparés par des virgules. Réponds uniquement avec les secteurs.",
                    "stream": False,
                    "options": {"temperature": 0.2, "max_tokens": 50}
                }
            )

            if response.status_code == 200:
                result = response.json()
                secteurs_str = result.get("response", "")
                return [s.strip() for s in secteurs_str.split(',') if s.strip()][:3]
        except Exception as e:
            logger.debug(f"Failed to classify sectors for {acteur.nom}: {e}")

        return []
