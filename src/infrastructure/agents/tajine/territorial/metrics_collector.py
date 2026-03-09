"""
Territorial Metrics Collector - Collecte et calcule les métriques territoriales.

Ce module fait le lien entre les datasources brutes (SIRENE, BODACC, France Travail, etc.)
et le SignalDetector en calculant les métriques agrégées et variations.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TerritorialMetrics:
    """Métriques calculées pour un territoire."""
    territory_code: str
    territory_name: str
    period_start: datetime
    period_end: datetime
    
    # SIRENE - Entreprises
    creations_count: int = 0
    creations_previous_period: int = 0
    closures_count: int = 0
    closures_previous_period: int = 0
    total_establishments: int = 0
    
    # BODACC - Annonces légales
    collective_procedures_count: int = 0
    collective_procedures_previous: int = 0
    modifications_count: int = 0
    sales_count: int = 0
    
    # France Travail - Emploi
    job_offers_count: int = 0
    job_offers_previous: int = 0
    job_seekers_count: int = 0  # Demandeurs d'emploi (si dispo)
    
    # INSEE - Démographie & Emploi
    population: int = 0
    unemployment_rate: float = 0.0  # Taux de chômage en %
    
    # DVF - Immobilier
    real_estate_transactions: int = 0
    avg_price_sqm: float = 0.0  # Prix moyen au m²
    
    # Indicateurs enrichis
    establishments_per_1000: float = 0.0  # Densité économique
    job_offers_sample: bool = True  # True si job_offers est un sample (max API)
    data_quality_score: float = 0.0  # 0-1, qualité des données collectées
    
    # Calculs dérivés
    @property
    def creation_rate(self) -> float:
        """Taux de création (créations / stock)."""
        if self.total_establishments == 0:
            return 0.0
        return self.creations_count / self.total_establishments
    
    @property
    def closure_rate(self) -> float:
        """Taux de fermeture (fermetures / stock)."""
        if self.total_establishments == 0:
            return 0.0
        return self.closures_count / self.total_establishments
    
    @property
    def creation_variation(self) -> float:
        """Variation des créations vs période précédente."""
        if self.creations_previous_period == 0:
            return 0.0 if self.creations_count == 0 else 1.0
        return (self.creations_count - self.creations_previous_period) / self.creations_previous_period
    
    @property
    def procedures_variation(self) -> float:
        """Variation des procédures collectives."""
        if self.collective_procedures_previous == 0:
            return 0.0 if self.collective_procedures_count == 0 else 1.0
        return (self.collective_procedures_count - self.collective_procedures_previous) / self.collective_procedures_previous
    
    @property
    def job_offers_variation(self) -> float:
        """Variation des offres d'emploi vs période précédente."""
        if self.job_offers_previous == 0:
            return 0.0 if self.job_offers_count == 0 else 1.0
        return (self.job_offers_count - self.job_offers_previous) / self.job_offers_previous
    
    @property
    def tension_ratio(self) -> float:
        """Ratio offres/demandeurs (tension du marché). >1 = pénurie de main d'œuvre."""
        if self.job_seekers_count == 0:
            return 1.0  # Neutre si pas de données
        return self.job_offers_count / self.job_seekers_count
    
    @property
    def net_creation(self) -> int:
        """Solde net (créations - fermetures)."""
        return self.creations_count - self.closures_count
    
    @property
    def vitality_index(self) -> float:
        """
        Indice de vitalité économique (0-100).
        Utilise vitality_breakdown pour le calcul.
        """
        breakdown = self.vitality_breakdown
        return breakdown["total"]
    
    @property
    def vitality_breakdown(self) -> dict[str, Any]:
        """
        Décomposition détaillée de l'indice de vitalité.
        
        Formule (5 composantes) :
        - Base : 50
        - Créations nettes : +/- 15 pts (SIRENE/BODACC)
        - Procédures : -10 pts max (BODACC)
        - Offres emploi : +10 pts max (France Travail)
        - Chômage : -10 pts max (INSEE)
        - Immobilier : +5 pts max (DVF)
        
        Returns:
            {
                "total": 65.0,
                "base": 50.0,
                "components": [
                    {"source": "BODACC", "name": "Créations nettes", "impact": +12.0, "detail": "+24 créations"},
                    ...
                ]
            }
        """
        components = []
        score = 50.0
        
        # 1. Créations nettes (poids: 30%)
        creations_impact = 0.0
        if self.total_establishments > 0:
            net_rate = self.net_creation / self.total_establishments
            creations_impact = min(15, max(-15, net_rate * 750))
        score += creations_impact
        components.append({
            "source": "BODACC/SIRENE",
            "name": "Créations nettes",
            "impact": round(creations_impact, 1),
            "detail": f"{self.net_creation:+d} (créations - fermetures)",
            "weight": "30%",
        })
        
        # 2. Procédures collectives (poids: 20%)
        proc_impact = 0.0
        if self.total_establishments > 0:
            proc_rate = self.collective_procedures_count / self.total_establishments
            proc_impact = -min(10, proc_rate * 1000)
        score += proc_impact
        if self.collective_procedures_count > 0:
            components.append({
                "source": "BODACC",
                "name": "Procédures collectives",
                "impact": round(proc_impact, 1),
                "detail": f"{self.collective_procedures_count} procédures",
                "weight": "20%",
            })
        
        # 3. Offres d'emploi (poids: 20%)
        offers_impact = 0.0
        if self.job_offers_count > 0:
            if self.total_establishments > 0:
                offers_rate = self.job_offers_count / self.total_establishments
                offers_impact = min(10, offers_rate * 100)
            else:
                offers_impact = min(8, self.job_offers_count / 15)
        score += offers_impact
        if self.job_offers_count > 0:
            components.append({
                "source": "France Travail",
                "name": "Offres d'emploi",
                "impact": round(offers_impact, 1),
                "detail": f"{self.job_offers_count} offres actives",
                "weight": "20%",
            })
        
        # 4. Taux de chômage (poids: 20%)
        chom_impact = 0.0
        if self.unemployment_rate > 0:
            chom_impact = min(10, max(-10, (7.0 - self.unemployment_rate) * 1.5))
        score += chom_impact
        if self.unemployment_rate > 0:
            components.append({
                "source": "INSEE",
                "name": "Taux de chômage",
                "impact": round(chom_impact, 1),
                "detail": f"{self.unemployment_rate:.1f}% (réf: 7%)",
                "weight": "20%",
            })
        
        # 5. Transactions immobilières (poids: 10%)
        immo_impact = 0.0
        if self.real_estate_transactions > 0 and self.population > 0:
            tx_rate = (self.real_estate_transactions / self.population) * 1000
            immo_impact = min(5, tx_rate * 0.5)
        score += immo_impact
        if self.real_estate_transactions > 0:
            components.append({
                "source": "DVF",
                "name": "Transactions immobilières",
                "impact": round(immo_impact, 1),
                "detail": f"{self.real_estate_transactions} transactions",
                "weight": "10%",
            })
        
        total = max(0, min(100, score))
        
        return {
            "total": round(total, 1),
            "base": 50.0,
            "components": components,
            "formula": "Base 50 + Créations(±15) + Procédures(-10) + Emploi(+10) + Chômage(±10) + Immo(+5)",
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "raw": {
                "creations": self.creations_count,
                "creations_previous": self.creations_previous_period,
                "closures": self.closures_count,
                "total_establishments": self.total_establishments,
                "collective_procedures": self.collective_procedures_count,
                "modifications": self.modifications_count,
                "sales": self.sales_count,
                "job_offers": self.job_offers_count,
                "job_offers_previous": self.job_offers_previous,
                "job_seekers": self.job_seekers_count,
                "population": self.population,
                "unemployment_rate": self.unemployment_rate,
                "real_estate_transactions": self.real_estate_transactions,
                "avg_price_sqm": self.avg_price_sqm,
            },
            "computed": {
                "creation_rate": round(self.creation_rate, 4),
                "closure_rate": round(self.closure_rate, 4),
                "creation_variation": round(self.creation_variation, 4),
                "procedures_variation": round(self.procedures_variation, 4),
                "job_offers_variation": round(self.job_offers_variation, 4),
                "tension_ratio": round(self.tension_ratio, 2),
                "net_creation": self.net_creation,
                "vitality_index": round(self.vitality_index, 2),
                "establishments_per_1000": self.establishments_per_1000,
            },
            "data_quality": {
                "score": self.data_quality_score,
                "job_offers_is_sample": self.job_offers_sample,
                "sources_status": {
                    "bodacc": self.creations_count > 0 or self.closures_count > 0,
                    "insee_population": self.population > 0,
                    "insee_unemployment": self.unemployment_rate > 0,
                    "france_travail": self.job_offers_count > 0,
                    "dvf": self.real_estate_transactions > 0,
                },
            },
        }


class TerritorialMetricsCollector:
    """
    Collecteur de métriques territoriales.
    
    Agrège les données des différentes sources pour calculer des métriques
    exploitables par le SignalDetector.
    """
    
    def __init__(
        self,
        sirene_adapter: Any = None,
        bodacc_adapter: Any = None,
        france_travail_adapter: Any = None,
        dvf_adapter: Any = None,
        insee_adapter: Any = None,
    ) -> None:
        """
        Initialise le collecteur avec les adaptateurs de données.
        """
        self.sirene = sirene_adapter
        self.bodacc = bodacc_adapter
        self.france_travail = france_travail_adapter
        self.dvf = dvf_adapter
        self.insee = insee_adapter
        self._cache: dict[str, tuple[datetime, TerritorialMetrics]] = {}
        self._cache_ttl = timedelta(hours=1)
    
    async def collect_metrics(
        self,
        territory_code: str,
        territory_name: str,
        period_months: int = 1,
    ) -> TerritorialMetrics:
        """
        Collecte les métriques pour un territoire.
        
        Args:
            territory_code: Code INSEE du territoire (commune ou département)
            territory_name: Nom du territoire
            period_months: Période d'analyse en mois
            
        Returns:
            TerritorialMetrics avec toutes les métriques calculées
        """
        # Vérifier le cache
        cache_key = f"{territory_code}:{period_months}"
        if cache_key in self._cache:
            cached_time, cached_metrics = self._cache[cache_key]
            if datetime.utcnow() - cached_time < self._cache_ttl:
                logger.debug(f"Cache hit for {territory_code}")
                return cached_metrics
        
        # Définir les périodes
        now = datetime.utcnow()
        period_end = now
        period_start = now - timedelta(days=period_months * 30)
        previous_start = period_start - timedelta(days=period_months * 30)
        
        # Collecter en parallèle
        tasks = []
        
        # BODACC (index 0, 1)
        if self.bodacc:
            tasks.append(self._collect_bodacc(territory_code, period_start, period_end))
            tasks.append(self._collect_bodacc(territory_code, previous_start, period_start))
        else:
            tasks.extend([self._empty_bodacc(), self._empty_bodacc()])
        
        # SIRENE (index 2)
        if self.sirene:
            tasks.append(self._collect_sirene(territory_code, period_start, period_end))
        else:
            tasks.append(self._empty_sirene())
        
        # France Travail (index 3, 4)
        if self.france_travail:
            tasks.append(self._collect_france_travail(territory_code))
            tasks.append(self._collect_france_travail_previous(territory_code))
        else:
            tasks.extend([self._empty_france_travail(), self._empty_france_travail()])
        
        # INSEE (index 5)
        if self.insee:
            tasks.append(self._collect_insee(territory_code))
        else:
            tasks.append(self._empty_insee())
        
        # DVF (index 6)
        if self.dvf:
            tasks.append(self._collect_dvf(territory_code))
        else:
            tasks.append(self._empty_dvf())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Parser les résultats
        bodacc_current = results[0] if not isinstance(results[0], Exception) else {}
        bodacc_previous = results[1] if not isinstance(results[1], Exception) else {}
        sirene_data = results[2] if not isinstance(results[2], Exception) else {}
        france_travail_current = results[3] if not isinstance(results[3], Exception) else {}
        france_travail_previous = results[4] if not isinstance(results[4], Exception) else {}
        insee_data = results[5] if not isinstance(results[5], Exception) else {}
        dvf_data = results[6] if not isinstance(results[6], Exception) else {}
        
        # Construire les métriques
        # Créations : préférer BODACC (temps réel) si disponible, sinon SIRENE
        creations = bodacc_current.get("creations", 0) or sirene_data.get("creations", 0)
        creations_prev = bodacc_previous.get("creations", 0)
        
        metrics = TerritorialMetrics(
            territory_code=territory_code,
            territory_name=territory_name,
            period_start=period_start,
            period_end=period_end,
            # Créations (BODACC prioritaire)
            creations_count=creations,
            total_establishments=sirene_data.get("total", 0) or 1000,  # Estimation si pas dispo
            # BODACC courant
            collective_procedures_count=bodacc_current.get("procedures", 0),
            modifications_count=bodacc_current.get("modifications", 0),
            sales_count=bodacc_current.get("sales", 0),
            closures_count=bodacc_current.get("radiations", 0),
            # BODACC précédent
            collective_procedures_previous=bodacc_previous.get("procedures", 0),
            creations_previous_period=creations_prev,
            closures_previous_period=bodacc_previous.get("radiations", 0),
            # France Travail
            job_offers_count=france_travail_current.get("offers", 0),
            job_offers_previous=france_travail_previous.get("offers", 0),
            job_seekers_count=france_travail_current.get("seekers", 0),
            # INSEE
            population=insee_data.get("population", 0),
            unemployment_rate=insee_data.get("unemployment_rate", 0.0),
            # DVF
            real_estate_transactions=dvf_data.get("transactions", 0),
            avg_price_sqm=dvf_data.get("avg_price_sqm", 0.0),
        )
        
        # Calculer les indicateurs enrichis
        population = insee_data.get("population", 0)
        total_est = sirene_data.get("total", 0) or 1000
        job_offers = france_travail_current.get("offers", 0)
        
        # Densité économique (établissements pour 1000 habitants)
        if population > 0:
            metrics.establishments_per_1000 = round((total_est / population) * 1000, 1)
        
        # Flag si job_offers est un sample (max API = 150)
        metrics.job_offers_sample = (job_offers >= 150)
        
        # Score qualité des données (0-1)
        quality_factors = []
        if bodacc_current.get("total", 0) > 0:
            quality_factors.append(1.0)  # BODACC ok
        if population > 0:
            quality_factors.append(1.0)  # INSEE population ok
        if insee_data.get("unemployment_rate", 0) > 0:
            quality_factors.append(1.0)  # INSEE chômage ok
        if job_offers > 0:
            quality_factors.append(0.7 if job_offers >= 150 else 1.0)  # France Travail (partial if max)
        if dvf_data.get("transactions", 0) > 0:
            quality_factors.append(1.0)  # DVF ok
        
        metrics.data_quality_score = round(sum(quality_factors) / max(5, len(quality_factors)), 2) if quality_factors else 0.0
        
        # Mettre en cache
        self._cache[cache_key] = (now, metrics)
        
        logger.info(
            f"Collected metrics for {territory_name}: "
            f"creations={metrics.creations_count}, "
            f"vitality={metrics.vitality_index:.1f}"
        )
        
        return metrics
    
    async def _collect_bodacc(
        self,
        territory_code: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, int]:
        """Collecte les données BODACC pour une période."""
        try:
            # Déterminer si c'est un département ou une commune
            is_department = len(territory_code) == 2 or (len(territory_code) == 3 and territory_code.startswith("97"))
            
            # Utiliser les paramètres supportés par l'adaptateur BODACC
            query = {"limit": 100}
            
            if is_department:
                query["departement"] = territory_code
            else:
                # Pour une commune, utiliser le département des 2 premiers chiffres
                query["departement"] = territory_code[:2]
            
            results = await self.bodacc.search(query)
            
            # Compter par type
            # Types BODACC: creation, modification, radiation, vente, procedure, other
            counts = {
                "creations": 0,
                "procedures": 0,
                "modifications": 0,
                "sales": 0,
                "radiations": 0,
                "total": len(results),
            }
            
            for r in results:
                type_val = r.get("type", "").lower()
                type_label = r.get("type_label", "").lower()
                
                # Match exact sur le type principal
                if type_val == "creation":
                    counts["creations"] += 1
                elif type_val == "radiation":
                    counts["radiations"] += 1
                elif type_val == "modification":
                    counts["modifications"] += 1
                elif type_val == "vente":
                    counts["sales"] += 1
                elif type_val == "procedure":
                    counts["procedures"] += 1
                # Fallback sur type_label pour "other"
                elif "liquidation" in type_label or "redressement" in type_label or "sauvegarde" in type_label:
                    counts["procedures"] += 1
                elif "cession" in type_label or "vente" in type_label:
                    counts["sales"] += 1
            
            return counts
            
        except Exception as e:
            logger.error(f"BODACC collection failed: {e}")
            return {"creations": 0, "procedures": 0, "modifications": 0, "sales": 0, "radiations": 0, "total": 0}
    
    async def _collect_sirene(
        self,
        territory_code: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, int]:
        """Collecte les données SIRENE."""
        try:
            # Pour SIRENE, on utilise une recherche par département/commune
            is_department = len(territory_code) == 2 or (len(territory_code) == 3 and territory_code.startswith("97"))
            
            # Construire la requête selon le format attendu par l'API
            if is_department:
                query = {"departement": territory_code, "limit": 25}
            else:
                # Pour une commune, chercher par code postal approximatif
                query = {"code_postal": territory_code[:5], "limit": 25}
            
            results = await self.sirene.search(query)
            
            if not isinstance(results, list):
                results = []
            
            # Compter les créations récentes
            creations = 0
            for r in results:
                if isinstance(r, dict) and self._is_recent_creation(r, start):
                    creations += 1
            
            return {
                "total": max(len(results) * 40, 1000),  # Estimation du stock total
                "creations": creations,
            }
            
        except Exception as e:
            logger.error(f"SIRENE collection failed: {e}")
            return {"total": 1000, "creations": 0}  # Valeurs par défaut
    
    def _is_recent_creation(self, record: dict, since: datetime) -> bool:
        """Vérifie si un établissement est une création récente."""
        date_str = record.get("date_creation") or record.get("date_debut_activite")
        if not date_str:
            return False
        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return date >= since
        except Exception:
            return False
    
    async def _empty_bodacc(self) -> dict[str, int]:
        """Retourne des données BODACC vides."""
        return {"creations": 0, "procedures": 0, "modifications": 0, "sales": 0, "radiations": 0, "total": 0}
    
    async def _empty_sirene(self) -> dict[str, int]:
        """Retourne des données SIRENE vides."""
        return {"total": 0, "creations": 0}
    
    async def _collect_france_travail(
        self,
        territory_code: str,
    ) -> dict[str, int]:
        """Collecte les offres d'emploi France Travail."""
        try:
            is_department = len(territory_code) == 2 or (len(territory_code) == 3 and territory_code.startswith("97"))
            
            # Récupérer les offres d'emploi
            # Note: l'API retourne max 150 offres par requête
            # Pour le nombre réel, il faudrait paginer ou utiliser une API stats
            offers = await self.france_travail.search_offres(
                departement=territory_code if is_department else territory_code[:2],
                limit=150,
            )
            
            offers_count = len(offers) if isinstance(offers, list) else 0
            
            # Essayer de récupérer les stats du marché du travail
            seekers_count = 0
            try:
                if hasattr(self.france_travail, "get_marche_travail_stats"):
                    stats = await self.france_travail.get_marche_travail_stats(
                        code_departement=territory_code if is_department else territory_code[:2]
                    )
                    if isinstance(stats, dict) and "data" in stats:
                        data = stats["data"]
                        # Extraire les demandeurs si disponible
                        if isinstance(data, dict):
                            seekers_count = data.get("nbDemandeurs", 0) or data.get("demandeurs", 0)
            except Exception as e:
                logger.debug(f"Could not get job market stats: {e}")
            
            return {
                "offers": offers_count,
                "seekers": seekers_count,
            }
            
        except Exception as e:
            logger.error(f"France Travail collection failed: {e}")
            return {"offers": 0, "seekers": 0}
    
    async def _collect_france_travail_previous(
        self,
        territory_code: str,
    ) -> dict[str, int]:
        """
        Collecte les offres France Travail période précédente.
        
        Note: L'API France Travail ne permet pas de filtrer par date facilement,
        on retourne donc 0 (pas de comparaison historique disponible).
        """
        # L'API France Travail retourne les offres actives, pas d'historique
        # Pour une vraie comparaison, il faudrait stocker les données régulièrement
        return {"offers": 0, "seekers": 0}
    
    async def _empty_france_travail(self) -> dict[str, int]:
        """Retourne des données France Travail vides."""
        return {"offers": 0, "seekers": 0}
    
    async def _collect_insee(
        self,
        territory_code: str,
    ) -> dict[str, Any]:
        """Collecte les données INSEE (population, chômage)."""
        try:
            is_department = len(territory_code) == 2 or (len(territory_code) == 3 and territory_code.startswith("97"))
            
            data = {"population": 0, "unemployment_rate": 0.0}
            
            # Population
            if hasattr(self.insee, "get_population"):
                pop_data = await self.insee.get_population(territory_code)
                if isinstance(pop_data, dict):
                    data["population"] = pop_data.get("population", 0) or pop_data.get("total", 0)
            
            # Taux de chômage
            if is_department and hasattr(self.insee, "get_unemployment_rate"):
                rate = await self.insee.get_unemployment_rate(territory_code)
                if rate is not None:
                    data["unemployment_rate"] = rate
            
            return data
            
        except Exception as e:
            logger.error(f"INSEE collection failed: {e}")
            return {"population": 0, "unemployment_rate": 0.0}
    
    async def _empty_insee(self) -> dict[str, Any]:
        """Retourne des données INSEE vides."""
        return {"population": 0, "unemployment_rate": 0.0}
    
    async def _collect_dvf(
        self,
        territory_code: str,
    ) -> dict[str, Any]:
        """Collecte les données DVF (transactions immobilières)."""
        try:
            is_department = len(territory_code) == 2 or (len(territory_code) == 3 and territory_code.startswith("97"))
            
            # Rechercher les transactions récentes
            query = {"limit": 100}
            if is_department:
                query["code_departement"] = territory_code
            else:
                query["code_insee"] = territory_code
            
            # Année courante - 1 (DVF a du retard)
            from datetime import datetime
            query["annee_min"] = datetime.now().year - 1
            
            transactions = await self.dvf.search(query)
            
            if not isinstance(transactions, list):
                transactions = []
            
            # Calculer stats
            tx_count = len(transactions)
            avg_price = 0.0
            
            if tx_count > 0:
                prices = []
                for tx in transactions:
                    # DVF adapter returns "valeur" and "surface_reelle"
                    price = tx.get("valeur") or tx.get("valeur_fonciere") or tx.get("prix")
                    surface = tx.get("surface_reelle") or tx.get("surface_reelle_bati") or tx.get("surface") or 1
                    if price and surface and surface > 0:
                        prices.append(price / surface)
                if prices:
                    avg_price = sum(prices) / len(prices)
            
            return {
                "transactions": tx_count,
                "avg_price_sqm": round(avg_price, 2),
            }
            
        except Exception as e:
            logger.error(f"DVF collection failed: {e}")
            return {"transactions": 0, "avg_price_sqm": 0.0}
    
    async def _empty_dvf(self) -> dict[str, Any]:
        """Retourne des données DVF vides."""
        return {"transactions": 0, "avg_price_sqm": 0.0}


async def demo_metrics(department: str = "69", name: str = "Rhône"):
    """Démonstration du collecteur de métriques."""
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter
    
    collector = TerritorialMetricsCollector(
        sirene_adapter=SireneAdapter(),
        bodacc_adapter=BodaccAdapter(),
    )
    
    metrics = await collector.collect_metrics(
        territory_code=department,
        territory_name=name,
        period_months=1,
    )
    
    print(f"\n{'='*50}")
    print(f"MÉTRIQUES TERRITORIALES: {metrics.territory_name}")
    print(f"{'='*50}")
    print(f"Période: {metrics.period_start.date()} → {metrics.period_end.date()}")
    print(f"\n📊 Données brutes:")
    print(f"  - Créations: {metrics.creations_count}")
    print(f"  - Fermetures: {metrics.closures_count}")
    print(f"  - Procédures collectives: {metrics.collective_procedures_count}")
    print(f"  - Modifications: {metrics.modifications_count}")
    print(f"  - Ventes/Cessions: {metrics.sales_count}")
    print(f"\n📈 Indicateurs calculés:")
    print(f"  - Taux de création: {metrics.creation_rate*100:.2f}%")
    print(f"  - Variation créations: {metrics.creation_variation*100:+.1f}%")
    print(f"  - Solde net: {metrics.net_creation:+d}")
    print(f"  - Indice de vitalité: {metrics.vitality_index:.1f}/100")
    
    return metrics


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_metrics())
