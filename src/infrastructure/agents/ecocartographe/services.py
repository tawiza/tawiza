"""
Services métier pour EcoCartographe
Extraction d'entités, analyse de relations, analyse réseau et visualisation
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .models import (
    Acteur,
    ActeurType,
    Adresse,
    AnalyseReseau,
    Communaute,
    ConfigurationExtraction,
    Coordonnees,
    MetriquesReseau,
    Relation,
    RelationType,
)


class ExtracteurEntites:
    """Service d'extraction d'entités avec spaCy"""

    def __init__(self, config: ConfigurationExtraction):
        self.config = config
        self._nlp = None
        self._geocoder = None

    async def initialiser(self) -> None:
        """Initialise spaCy et le géocodeur"""
        try:
            import spacy
            self._nlp = spacy.load(self.config.modele_spacy)
            logger.info(f"Modèle spaCy chargé: {self.config.modele_spacy}")
        except OSError:
            logger.warning(f"Modèle {self.config.modele_spacy} non trouvé, tentative de téléchargement...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", self.config.modele_spacy])
            import spacy
            self._nlp = spacy.load(self.config.modele_spacy)

        try:
            from geopy.geocoders import Nominatim
            self._geocoder = Nominatim(user_agent="ecocartographe")
            logger.info("Géocodeur Nominatim initialisé")
        except ImportError:
            logger.warning("geopy non installé, géocodage désactivé")

    async def extraire_depuis_texte(self, texte: str, source: str = "texte") -> list[Acteur]:
        """Extrait les acteurs depuis un texte libre"""
        if not self._nlp:
            await self.initialiser()

        doc = self._nlp(texte)
        acteurs = []
        entites_vues: set[str] = set()

        for ent in doc.ents:
            if ent.label_ not in self.config.types_entites:
                continue

            nom_normalise = ent.text.strip()
            if nom_normalise in entites_vues or len(nom_normalise) < 2:
                continue

            entites_vues.add(nom_normalise)

            acteur = Acteur(
                nom=nom_normalise,
                type=self._determiner_type_acteur(ent.label_, nom_normalise),
                source=source,
                metadata={"label_spacy": ent.label_}
            )

            # Extraire les mots-clés du contexte
            acteur.mots_cles = self._extraire_mots_cles_contexte(doc, ent)

            acteurs.append(acteur)

        logger.info(f"Extrait {len(acteurs)} acteurs depuis le texte")
        return acteurs

    async def extraire_depuis_csv(self, chemin: str, mapping: dict[str, str] = None) -> list[Acteur]:
        """Extrait les acteurs depuis un fichier CSV"""
        import pandas as pd

        df = pd.read_csv(chemin)
        mapping = mapping or self._detecter_mapping_colonnes(df.columns.tolist())

        acteurs = []
        for _, row in df.iterrows():
            acteur = self._row_vers_acteur(row, mapping)
            if acteur:
                acteurs.append(acteur)

        # Géocoder les adresses si possible
        if self._geocoder:
            await self._geocoder_acteurs(acteurs)

        logger.info(f"Extrait {len(acteurs)} acteurs depuis CSV: {chemin}")
        return acteurs

    async def extraire_depuis_excel(self, chemin: str, feuille: str = None) -> list[Acteur]:
        """Extrait les acteurs depuis un fichier Excel"""
        import pandas as pd

        df = pd.read_excel(chemin, sheet_name=feuille)
        mapping = self._detecter_mapping_colonnes(df.columns.tolist())

        acteurs = []
        for _, row in df.iterrows():
            acteur = self._row_vers_acteur(row, mapping)
            if acteur:
                acteurs.append(acteur)

        if self._geocoder:
            await self._geocoder_acteurs(acteurs)

        logger.info(f"Extrait {len(acteurs)} acteurs depuis Excel: {chemin}")
        return acteurs

    async def extraire_depuis_json(self, chemin: str) -> list[Acteur]:
        """Extrait les acteurs depuis un fichier JSON"""
        with open(chemin, encoding='utf-8') as f:
            data = json.load(f)

        acteurs = []
        if isinstance(data, list):
            for item in data:
                acteur = self._dict_vers_acteur(item)
                if acteur:
                    acteurs.append(acteur)
        elif isinstance(data, dict):
            # Peut être un dict avec une clé contenant la liste
            for key in ['acteurs', 'actors', 'data', 'items', 'organisations']:
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        acteur = self._dict_vers_acteur(item)
                        if acteur:
                            acteurs.append(acteur)
                    break

        if self._geocoder:
            await self._geocoder_acteurs(acteurs)

        logger.info(f"Extrait {len(acteurs)} acteurs depuis JSON: {chemin}")
        return acteurs

    def _determiner_type_acteur(self, label: str, nom: str) -> ActeurType:
        """Détermine le type d'acteur basé sur le label spaCy et le nom"""
        nom_lower = nom.lower()

        # Patterns de détection
        if any(kw in nom_lower for kw in ['université', 'university', 'univ', 'ufr', 'iut']):
            return ActeurType.UNIVERSITE
        elif any(kw in nom_lower for kw in ['laboratoire', 'lab', 'cnrs', 'inria', 'cea', 'inserm']):
            return ActeurType.LABORATOIRE
        elif any(kw in nom_lower for kw in ['cluster', 'pôle', 'pole', 'competitivite']):
            return ActeurType.POLE_COMPETITIVITE
        elif any(kw in nom_lower for kw in ['incubateur', 'incubator', 'pépinière']):
            return ActeurType.INCUBATEUR
        elif any(kw in nom_lower for kw in ['startup', 'start-up']):
            return ActeurType.STARTUP
        elif any(kw in nom_lower for kw in ['accelerateur', 'accelerator']):
            return ActeurType.ACCELERATEUR
        elif any(kw in nom_lower for kw in ['region', 'département', 'mairie', 'métropole', 'communauté']):
            return ActeurType.COLLECTIVITE
        elif any(kw in nom_lower for kw in ['banque', 'bpi', 'investissement', 'capital', 'fund']):
            return ActeurType.FINANCEUR
        elif any(kw in nom_lower for kw in ['association', 'asso', 'federation']):
            return ActeurType.ASSOCIATION
        elif label == "ORG":
            return ActeurType.ENTREPRISE
        else:
            return ActeurType.AUTRE

    def _extraire_mots_cles_contexte(self, doc, entite, fenetre: int = 50) -> list[str]:
        """Extrait les mots-clés autour d'une entité"""
        mots_cles = []
        start = max(0, entite.start - fenetre)
        end = min(len(doc), entite.end + fenetre)

        for token in doc[start:end]:
            if token.pos_ in ['NOUN', 'PROPN'] and token.text.lower() not in ['le', 'la', 'les', 'un', 'une', 'des']:
                if len(token.text) > 2 and token.text not in mots_cles:
                    mots_cles.append(token.text.lower())

        return mots_cles[:10]  # Limiter à 10 mots-clés

    def _detecter_mapping_colonnes(self, colonnes: list[str]) -> dict[str, str]:
        """Détecte automatiquement le mapping des colonnes"""
        mapping = {}
        colonnes_lower = {c.lower(): c for c in colonnes}

        # Mapping nom
        for key in ['nom', 'name', 'organisation', 'organization', 'raison_sociale', 'societe']:
            if key in colonnes_lower:
                mapping['nom'] = colonnes_lower[key]
                break

        # Mapping type
        for key in ['type', 'categorie', 'category', 'type_acteur']:
            if key in colonnes_lower:
                mapping['type'] = colonnes_lower[key]
                break

        # Mapping adresse
        for key in ['adresse', 'address', 'rue']:
            if key in colonnes_lower:
                mapping['adresse'] = colonnes_lower[key]
                break

        # Mapping ville
        for key in ['ville', 'city', 'commune']:
            if key in colonnes_lower:
                mapping['ville'] = colonnes_lower[key]
                break

        # Mapping code postal
        for key in ['code_postal', 'cp', 'postal_code', 'zipcode']:
            if key in colonnes_lower:
                mapping['code_postal'] = colonnes_lower[key]
                break

        # Mapping description
        for key in ['description', 'desc', 'activite', 'activity']:
            if key in colonnes_lower:
                mapping['description'] = colonnes_lower[key]
                break

        # Mapping site web
        for key in ['site_web', 'website', 'url', 'site']:
            if key in colonnes_lower:
                mapping['site_web'] = colonnes_lower[key]
                break

        # Mapping secteurs
        for key in ['secteur', 'secteurs', 'sector', 'sectors', 'domaine']:
            if key in colonnes_lower:
                mapping['secteurs'] = colonnes_lower[key]
                break

        return mapping

    def _row_vers_acteur(self, row, mapping: dict[str, str]) -> Acteur | None:
        """Convertit une ligne de DataFrame en Acteur"""
        nom = row.get(mapping.get('nom', ''), '')
        if not nom or str(nom) == 'nan':
            return None

        acteur = Acteur(nom=str(nom).strip())

        # Type
        type_str = row.get(mapping.get('type', ''), '')
        if type_str and str(type_str) != 'nan':
            acteur.type = self._str_vers_type_acteur(str(type_str))

        # Description
        desc = row.get(mapping.get('description', ''), '')
        if desc and str(desc) != 'nan':
            acteur.description = str(desc)

        # Site web
        site = row.get(mapping.get('site_web', ''), '')
        if site and str(site) != 'nan':
            acteur.site_web = str(site)

        # Adresse
        adresse = Adresse()
        rue = row.get(mapping.get('adresse', ''), '')
        if rue and str(rue) != 'nan':
            adresse.rue = str(rue)

        ville = row.get(mapping.get('ville', ''), '')
        if ville and str(ville) != 'nan':
            adresse.ville = str(ville)

        cp = row.get(mapping.get('code_postal', ''), '')
        if cp and str(cp) != 'nan':
            adresse.code_postal = str(cp)

        if adresse.rue or adresse.ville:
            acteur.adresse = adresse

        # Secteurs
        secteurs = row.get(mapping.get('secteurs', ''), '')
        if secteurs and str(secteurs) != 'nan':
            acteur.secteurs = [s.strip() for s in str(secteurs).split(',')]

        return acteur

    def _dict_vers_acteur(self, data: dict[str, Any]) -> Acteur | None:
        """Convertit un dictionnaire en Acteur"""
        nom = data.get('nom') or data.get('name') or data.get('organisation')
        if not nom:
            return None

        acteur = Acteur(nom=str(nom).strip())

        if 'type' in data:
            acteur.type = self._str_vers_type_acteur(data['type'])

        acteur.description = data.get('description')
        acteur.site_web = data.get('site_web') or data.get('website')

        if 'secteurs' in data:
            acteur.secteurs = data['secteurs'] if isinstance(data['secteurs'], list) else [data['secteurs']]

        if 'mots_cles' in data:
            acteur.mots_cles = data['mots_cles'] if isinstance(data['mots_cles'], list) else [data['mots_cles']]

        # Adresse
        if any(k in data for k in ['adresse', 'ville', 'code_postal', 'rue']):
            acteur.adresse = Adresse(
                rue=data.get('rue') or data.get('adresse'),
                ville=data.get('ville'),
                code_postal=data.get('code_postal'),
                region=data.get('region')
            )

        # Coordonnées
        if 'latitude' in data and 'longitude' in data:
            if not acteur.adresse:
                acteur.adresse = Adresse()
            acteur.adresse.coordonnees = Coordonnees(
                latitude=float(data['latitude']),
                longitude=float(data['longitude'])
            )

        return acteur

    def _str_vers_type_acteur(self, s: str) -> ActeurType:
        """Convertit une chaîne en ActeurType"""
        s_lower = s.lower()
        for t in ActeurType:
            if t.value in s_lower or s_lower in t.value:
                return t
        return ActeurType.AUTRE

    async def _geocoder_acteurs(self, acteurs: list[Acteur], delay: float = 1.0) -> None:
        """Géocode les adresses des acteurs"""
        if not self._geocoder:
            return

        for acteur in acteurs:
            if not acteur.adresse:
                continue
            if acteur.adresse.coordonnees:
                continue  # Déjà géocodé

            try:
                adresse_str = f"{acteur.adresse.rue or ''} {acteur.adresse.code_postal or ''} {acteur.adresse.ville or ''} France"
                location = self._geocoder.geocode(adresse_str.strip(), timeout=10)
                if location:
                    acteur.adresse.coordonnees = Coordonnees(
                        latitude=location.latitude,
                        longitude=location.longitude
                    )
                await asyncio.sleep(delay)  # Rate limiting
            except Exception as e:
                logger.warning(f"Échec géocodage pour {acteur.nom}: {e}")


class AnalyseurRelations:
    """Service d'analyse et détection des relations entre acteurs"""

    def __init__(self, config: ConfigurationExtraction):
        self.config = config
        self._ollama_client = None

    async def initialiser(self) -> None:
        """Initialise le client Ollama pour l'analyse sémantique"""
        try:
            import httpx
            self._ollama_client = httpx.AsyncClient(base_url="http://localhost:11434", timeout=60.0)
            logger.info("Client Ollama initialisé")
        except ImportError:
            logger.warning("httpx non installé, analyse LLM désactivée")

    async def detecter_relations(self, acteurs: list[Acteur], textes: list[str] = None) -> list[Relation]:
        """Détecte toutes les relations entre acteurs"""
        relations = []

        # Relations par proximité géographique
        relations.extend(await self._relations_proximite_geographique(acteurs))

        # Relations par similarité thématique
        relations.extend(await self._relations_proximite_thematique(acteurs))

        # Relations par co-occurrence dans les textes
        if textes:
            relations.extend(await self._relations_cooccurrence(acteurs, textes))

        # Déduplication
        relations = self._dedupliquer_relations(relations)

        logger.info(f"Détecté {len(relations)} relations")
        return relations

    async def _relations_proximite_geographique(self, acteurs: list[Acteur]) -> list[Relation]:
        """Détecte les relations par proximité géographique"""
        relations = []
        acteurs_geo = [a for a in acteurs if a.adresse and a.adresse.coordonnees]

        for i, a1 in enumerate(acteurs_geo):
            for a2 in acteurs_geo[i+1:]:
                distance = a1.adresse.coordonnees.distance_to(a2.adresse.coordonnees)
                if distance <= self.config.seuil_proximite_km:
                    force = 1.0 - (distance / self.config.seuil_proximite_km)
                    relations.append(Relation(
                        source_id=a1.id,
                        cible_id=a2.id,
                        type=RelationType.PROXIMITE_GEOGRAPHIQUE,
                        force=force,
                        description=f"Distance: {distance:.1f} km",
                        evidence=[f"Proximité géographique < {self.config.seuil_proximite_km} km"]
                    ))

        return relations

    async def _relations_proximite_thematique(self, acteurs: list[Acteur]) -> list[Relation]:
        """Détecte les relations par similarité thématique (mots-clés/secteurs)"""
        relations = []

        for i, a1 in enumerate(acteurs):
            for a2 in acteurs[i+1:]:
                similarite = self._calculer_similarite_jaccard(
                    set(a1.mots_cles + a1.secteurs),
                    set(a2.mots_cles + a2.secteurs)
                )
                if similarite >= self.config.seuil_similarite_thematique:
                    relations.append(Relation(
                        source_id=a1.id,
                        cible_id=a2.id,
                        type=RelationType.PROXIMITE_THEMATIQUE,
                        force=similarite,
                        description=f"Similarité: {similarite:.2f}",
                        evidence=[
                            f"Mots-clés communs: {set(a1.mots_cles) & set(a2.mots_cles)}",
                            f"Secteurs communs: {set(a1.secteurs) & set(a2.secteurs)}"
                        ]
                    ))

        return relations

    async def _relations_cooccurrence(self, acteurs: list[Acteur], textes: list[str]) -> list[Relation]:
        """Détecte les relations par co-occurrence dans les textes"""
        relations = []
        cooccurrences: dict[tuple[str, str], int] = {}

        for texte in textes:
            texte_lower = texte.lower()
            acteurs_presents = [a for a in acteurs if a.nom.lower() in texte_lower]

            for i, a1 in enumerate(acteurs_presents):
                for a2 in acteurs_presents[i+1:]:
                    key = tuple(sorted([a1.id, a2.id]))
                    cooccurrences[key] = cooccurrences.get(key, 0) + 1

        # Créer les relations
        max_coocc = max(cooccurrences.values()) if cooccurrences else 1
        for (id1, id2), count in cooccurrences.items():
            if count >= 2:  # Au moins 2 co-occurrences
                relations.append(Relation(
                    source_id=id1,
                    cible_id=id2,
                    type=RelationType.COLLABORATION,
                    force=count / max_coocc,
                    description=f"Co-occurrences: {count}",
                    evidence=[f"Apparaissent ensemble dans {count} documents"]
                ))

        return relations

    def _calculer_similarite_jaccard(self, set1: set[str], set2: set[str]) -> float:
        """Calcule l'indice de similarité de Jaccard"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _dedupliquer_relations(self, relations: list[Relation]) -> list[Relation]:
        """Déduplique les relations en gardant la plus forte"""
        meilleures: dict[tuple[str, str], Relation] = {}

        for rel in relations:
            key = tuple(sorted([rel.source_id, rel.cible_id]))
            if key not in meilleures or rel.force > meilleures[key].force:
                meilleures[key] = rel

        return list(meilleures.values())


class AnalyseurReseau:
    """Service d'analyse de réseau avec NetworkX"""

    def __init__(self):
        self._graph = None

    def construire_graphe(self, acteurs: list[Acteur], relations: list[Relation]):
        """Construit le graphe NetworkX"""
        import networkx as nx

        self._graph = nx.Graph()

        # Ajouter les noeuds
        for acteur in acteurs:
            self._graph.add_node(
                acteur.id,
                nom=acteur.nom,
                type=acteur.type.value,
                label=acteur.nom[:20]
            )

        # Ajouter les arêtes
        for rel in relations:
            if rel.source_id in self._graph and rel.cible_id in self._graph:
                self._graph.add_edge(
                    rel.source_id,
                    rel.cible_id,
                    weight=rel.force,
                    type=rel.type.value
                )

        logger.info(f"Graphe construit: {self._graph.number_of_nodes()} noeuds, {self._graph.number_of_edges()} arêtes")

    def analyser(self, acteurs: list[Acteur]) -> AnalyseReseau:
        """Effectue l'analyse complète du réseau"""
        import networkx as nx
        from networkx.algorithms import community

        if not self._graph or self._graph.number_of_nodes() == 0:
            return AnalyseReseau()

        analyse = AnalyseReseau(
            nb_noeuds=self._graph.number_of_nodes(),
            nb_aretes=self._graph.number_of_edges(),
            densite=nx.density(self._graph)
        )

        # Composantes connexes
        analyse.nb_composantes_connexes = nx.number_connected_components(self._graph)

        # Diamètre et rayon (sur la plus grande composante)
        if nx.is_connected(self._graph):
            analyse.diametre = nx.diameter(self._graph)
            analyse.rayon = nx.radius(self._graph)
        else:
            largest_cc = max(nx.connected_components(self._graph), key=len)
            subgraph = self._graph.subgraph(largest_cc)
            if len(largest_cc) > 1:
                analyse.diametre = nx.diameter(subgraph)
                analyse.rayon = nx.radius(subgraph)

        # Coefficient de clustering moyen
        analyse.coefficient_clustering_moyen = nx.average_clustering(self._graph)

        # Centralités
        self._calculer_centralites(acteurs)

        # Acteurs centraux (top 10 par centralité d'intermédiation)
        betweenness = nx.betweenness_centrality(self._graph)
        sorted_actors = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
        analyse.acteurs_centraux = [aid for aid, _ in sorted_actors[:10]]

        # Ponts (arêtes dont la suppression augmente les composantes)
        try:
            bridges = list(nx.bridges(self._graph))
            analyse.ponts = bridges[:20]  # Top 20 ponts
        except nx.NetworkXError as e:
            logger.debug(f"Could not calculate bridges for graph: {e}")

        # Détection de communautés
        analyse.communautes = self._detecter_communautes(acteurs)

        # Modularité
        if analyse.communautes:
            partition = {}
            for i, comm in enumerate(analyse.communautes):
                for aid in comm.acteurs_ids:
                    partition[aid] = i
            try:
                analyse.modularite = community.modularity(
                    self._graph,
                    [{aid for aid in comm.acteurs_ids if aid in self._graph} for comm in analyse.communautes]
                )
            except Exception as e:
                logger.debug(f"Could not calculate modularity: {e}")

        return analyse

    def _calculer_centralites(self, acteurs: list[Acteur]) -> None:
        """Calcule et assigne les métriques de centralité aux acteurs"""
        import networkx as nx

        if not self._graph:
            return

        degre = dict(self._graph.degree())
        max_deg = max(degre.values()) if degre else 1

        betweenness = nx.betweenness_centrality(self._graph)
        closeness = nx.closeness_centrality(self._graph)
        eigenvector = {}
        try:
            eigenvector = nx.eigenvector_centrality(self._graph, max_iter=1000)
        except nx.PowerIterationFailedConvergence as e:
            logger.debug(f"Eigenvector centrality did not converge: {e}")

        clustering = nx.clustering(self._graph)

        acteurs_dict = {a.id: a for a in acteurs}

        for node_id in self._graph.nodes():
            if node_id in acteurs_dict:
                acteur = acteurs_dict[node_id]
                acteur.metriques = MetriquesReseau(
                    degre=degre.get(node_id, 0) / max_deg,
                    centralite_intermediation=betweenness.get(node_id, 0),
                    centralite_proximite=closeness.get(node_id, 0),
                    centralite_vecteur_propre=eigenvector.get(node_id, 0),
                    coefficient_clustering=clustering.get(node_id, 0)
                )

    def _detecter_communautes(self, acteurs: list[Acteur]) -> list[Communaute]:
        """Détecte les communautés avec l'algorithme de Louvain"""
        from networkx.algorithms import community

        if not self._graph or self._graph.number_of_nodes() < 3:
            return []

        try:
            communities = community.louvain_communities(self._graph, resolution=1.0)
        except Exception:
            try:
                communities = list(community.greedy_modularity_communities(self._graph))
            except Exception:
                return []

        acteurs_dict = {a.id: a for a in acteurs}
        result = []

        for i, comm_nodes in enumerate(communities):
            comm = Communaute(
                nom=f"Communauté {i+1}",
                acteurs_ids=list(comm_nodes)
            )

            # Extraire thématiques
            thematiques: dict[str, int] = {}
            for aid in comm_nodes:
                if aid in acteurs_dict:
                    for kw in acteurs_dict[aid].mots_cles + acteurs_dict[aid].secteurs:
                        thematiques[kw] = thematiques.get(kw, 0) + 1

            comm.thematiques = [k for k, _ in sorted(thematiques.items(), key=lambda x: x[1], reverse=True)[:5]]

            # Calculer centroïde géographique
            coords = []
            for aid in comm_nodes:
                if aid in acteurs_dict:
                    a = acteurs_dict[aid]
                    if a.adresse and a.adresse.coordonnees:
                        coords.append(a.adresse.coordonnees)

            if coords:
                avg_lat = sum(c.latitude for c in coords) / len(coords)
                avg_lon = sum(c.longitude for c in coords) / len(coords)
                comm.centroide = Coordonnees(avg_lat, avg_lon)

            result.append(comm)

        return result

    def exporter_gexf(self, chemin: str) -> None:
        """Exporte le graphe au format GEXF (pour Gephi)"""
        import networkx as nx
        if self._graph:
            nx.write_gexf(self._graph, chemin)
            logger.info(f"Graphe exporté: {chemin}")

    def exporter_json(self) -> dict[str, Any]:
        """Exporte le graphe au format JSON (pour D3.js/vis.js)"""
        if not self._graph:
            return {"nodes": [], "links": []}

        return {
            "nodes": [
                {"id": n, **self._graph.nodes[n]}
                for n in self._graph.nodes()
            ],
            "links": [
                {"source": u, "target": v, **self._graph.edges[u, v]}
                for u, v in self._graph.edges()
            ]
        }


class GenerateurVisualisations:
    """Service de génération de visualisations (cartes et graphes)"""

    def __init__(self, output_dir: str = "./workspace/outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generer_carte(
        self,
        acteurs: list[Acteur],
        relations: list[Relation],
        nom_fichier: str = "carte.html"
    ) -> str:
        """Génère une carte interactive avec Folium"""
        import folium
        from folium.plugins import MarkerCluster

        # Trouver le centre
        coords = [a.adresse.coordonnees for a in acteurs if a.adresse and a.adresse.coordonnees]
        if not coords:
            center = [46.603354, 1.888334]  # Centre de la France
            zoom = 6
        else:
            center = [
                sum(c.latitude for c in coords) / len(coords),
                sum(c.longitude for c in coords) / len(coords)
            ]
            zoom = 8

        carte = folium.Map(location=center, zoom_start=zoom, tiles='cartodbpositron')

        # Cluster de marqueurs
        cluster = MarkerCluster()

        # Couleurs par type
        couleurs = {
            ActeurType.ENTREPRISE: 'blue',
            ActeurType.STARTUP: 'green',
            ActeurType.LABORATOIRE: 'red',
            ActeurType.UNIVERSITE: 'purple',
            ActeurType.CLUSTER: 'orange',
            ActeurType.POLE_COMPETITIVITE: 'darkred',
            ActeurType.INCUBATEUR: 'cadetblue',
            ActeurType.ACCELERATEUR: 'lightgreen',
            ActeurType.FINANCEUR: 'black',
            ActeurType.COLLECTIVITE: 'lightblue',
            ActeurType.ASSOCIATION: 'pink',
            ActeurType.AUTRE: 'gray'
        }

        # Ajouter les acteurs
        acteurs_avec_coords = {a.id: a for a in acteurs if a.adresse and a.adresse.coordonnees}
        for acteur in acteurs_avec_coords.values():
            popup_html = f"""
            <b>{acteur.nom}</b><br>
            Type: {acteur.type.value}<br>
            {acteur.description or ''}<br>
            Secteurs: {', '.join(acteur.secteurs[:3])}<br>
            Score d'influence: {acteur.metriques.score_influence:.2f}
            """
            folium.Marker(
                location=acteur.adresse.coordonnees.to_tuple(),
                popup=popup_html,
                tooltip=acteur.nom,
                icon=folium.Icon(color=couleurs.get(acteur.type, 'gray'), icon='info-sign')
            ).add_to(cluster)

        cluster.add_to(carte)

        # Ajouter les relations géographiques comme lignes
        for rel in relations:
            if rel.source_id in acteurs_avec_coords and rel.cible_id in acteurs_avec_coords:
                a1 = acteurs_avec_coords[rel.source_id]
                a2 = acteurs_avec_coords[rel.cible_id]
                folium.PolyLine(
                    locations=[
                        a1.adresse.coordonnees.to_tuple(),
                        a2.adresse.coordonnees.to_tuple()
                    ],
                    color='gray',
                    weight=rel.force * 3,
                    opacity=0.5,
                    popup=f"{rel.type.value}: {a1.nom} - {a2.nom}"
                ).add_to(carte)

        # Légende
        legend_html = """
        <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,0,0,0.3);">
        <b>Légende</b><br>
        """
        for type_acteur, couleur in list(couleurs.items())[:6]:
            legend_html += f'<i style="background:{couleur};width:10px;height:10px;display:inline-block;margin-right:5px;border-radius:50%;"></i>{type_acteur.value}<br>'
        legend_html += "</div>"
        carte.get_root().html.add_child(folium.Element(legend_html))

        # Sauvegarder
        chemin = self.output_dir / nom_fichier
        carte.save(str(chemin))
        logger.info(f"Carte générée: {chemin}")

        return str(chemin)

    async def generer_graphe(
        self,
        acteurs: list[Acteur],
        relations: list[Relation],
        nom_fichier: str = "graphe.html"
    ) -> str:
        """Génère un graphe interactif avec PyVis"""
        from pyvis.network import Network

        net = Network(
            height="800px",
            width="100%",
            bgcolor="#ffffff",
            font_color="black",
            directed=False
        )

        # Configuration physique
        net.set_options("""
        {
            "physics": {
                "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "centralGravity": 0.01,
                    "springLength": 100,
                    "springConstant": 0.08
                },
                "maxVelocity": 50,
                "solver": "forceAtlas2Based",
                "stabilization": {"iterations": 150}
            },
            "nodes": {
                "font": {"size": 12}
            },
            "edges": {
                "smooth": {"type": "continuous"}
            }
        }
        """)

        # Couleurs par type
        couleurs = {
            ActeurType.ENTREPRISE: '#3498db',
            ActeurType.STARTUP: '#2ecc71',
            ActeurType.LABORATOIRE: '#e74c3c',
            ActeurType.UNIVERSITE: '#9b59b6',
            ActeurType.CLUSTER: '#f39c12',
            ActeurType.POLE_COMPETITIVITE: '#c0392b',
            ActeurType.INCUBATEUR: '#1abc9c',
            ActeurType.ACCELERATEUR: '#27ae60',
            ActeurType.FINANCEUR: '#2c3e50',
            ActeurType.COLLECTIVITE: '#3498db',
            ActeurType.ASSOCIATION: '#e91e63',
            ActeurType.AUTRE: '#95a5a6'
        }

        # Ajouter les noeuds
        acteurs_dict = {a.id: a for a in acteurs}
        for acteur in acteurs:
            taille = 10 + acteur.metriques.score_influence * 30
            net.add_node(
                acteur.id,
                label=acteur.nom[:25],
                title=f"{acteur.nom}\nType: {acteur.type.value}\nInfluence: {acteur.metriques.score_influence:.2f}",
                color=couleurs.get(acteur.type, '#95a5a6'),
                size=taille,
                font={'size': 10}
            )

        # Ajouter les arêtes
        for rel in relations:
            if rel.source_id in acteurs_dict and rel.cible_id in acteurs_dict:
                net.add_edge(
                    rel.source_id,
                    rel.cible_id,
                    value=rel.force * 5,
                    title=f"{rel.type.value}\nForce: {rel.force:.2f}"
                )

        # Sauvegarder
        chemin = self.output_dir / nom_fichier
        net.save_graph(str(chemin))
        logger.info(f"Graphe généré: {chemin}")

        return str(chemin)

    async def generer_rapport(
        self,
        projet_nom: str,
        acteurs: list[Acteur],
        relations: list[Relation],
        analyse: AnalyseReseau,
        nom_fichier: str = "rapport.md"
    ) -> str:
        """Génère un rapport Markdown"""

        rapport = f"""# Rapport de Cartographie: {projet_nom}

*Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')}*

## Résumé

| Métrique | Valeur |
|----------|--------|
| Nombre d'acteurs | {len(acteurs)} |
| Nombre de relations | {len(relations)} |
| Densité du réseau | {analyse.densite:.3f} |
| Coefficient de clustering | {analyse.coefficient_clustering_moyen:.3f} |
| Nombre de communautés | {len(analyse.communautes)} |
| Modularité | {analyse.modularite:.3f} |

## Distribution des Types d'Acteurs

"""
        # Dictionnaire pour accéder aux acteurs par ID
        acteurs_dict = {a.id: a for a in acteurs}

        # Comptage par type
        par_type: dict[ActeurType, int] = {}
        for a in acteurs:
            par_type[a.type] = par_type.get(a.type, 0) + 1

        for t, count in sorted(par_type.items(), key=lambda x: x[1], reverse=True):
            rapport += f"- **{t.value}**: {count} ({count*100/len(acteurs):.1f}%)\n"

        rapport += "\n## Acteurs les Plus Influents\n\n"
        rapport += "| Rang | Acteur | Type | Score d'influence |\n"
        rapport += "|------|--------|------|-------------------|\n"

        acteurs_tries = sorted(acteurs, key=lambda a: a.metriques.score_influence, reverse=True)
        for i, a in enumerate(acteurs_tries[:15], 1):
            rapport += f"| {i} | {a.nom} | {a.type.value} | {a.metriques.score_influence:.3f} |\n"

        rapport += "\n## Communautés Détectées\n\n"
        for i, comm in enumerate(analyse.communautes, 1):
            rapport += f"### Communauté {i}: {comm.nom}\n\n"
            rapport += f"- **Taille**: {comm.taille} acteurs\n"
            rapport += f"- **Thématiques**: {', '.join(comm.thematiques)}\n"
            rapport += f"- **Acteurs**: {', '.join([acteurs_dict.get(aid, Acteur()).nom for aid in comm.acteurs_ids[:5]])}...\n\n"

        rapport += "\n## Distribution des Relations\n\n"
        par_type_rel: dict[RelationType, int] = {}
        for r in relations:
            par_type_rel[r.type] = par_type_rel.get(r.type, 0) + 1

        for t, count in sorted(par_type_rel.items(), key=lambda x: x[1], reverse=True):
            rapport += f"- **{t.value}**: {count}\n"

        rapport += "\n## Ponts Stratégiques\n\n"
        rapport += "Relations dont la suppression fragmenterait le réseau:\n\n"
        for src, tgt in analyse.ponts[:10]:
            nom_src = acteurs_dict.get(src, Acteur(nom="?")).nom
            nom_tgt = acteurs_dict.get(tgt, Acteur(nom="?")).nom
            rapport += f"- {nom_src} ↔ {nom_tgt}\n"

        rapport += "\n---\n*Rapport généré par EcoCartographe*\n"

        chemin = self.output_dir / nom_fichier
        with open(chemin, 'w', encoding='utf-8') as f:
            f.write(rapport)

        logger.info(f"Rapport généré: {chemin}")
        return str(chemin)
