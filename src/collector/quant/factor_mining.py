"""
Factor Mining avec LLM pour Tawiza-V2
Phase 4: Génération et test d'hypothèses de facteurs via Ollama
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import statistics

import numpy as np
import pandas as pd
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  
from sqlalchemy import text
from scipy.stats import pearsonr, spearmanr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FactorMining:
    """
    Factor Mining avec LLM pour découvrir de nouveaux facteurs économiques
    
    Utilise Ollama (qwen3.5:27b) pour générer des hypothèses de facteurs,
    puis calcule l'Information Coefficient (IC) sur les données réelles.
    """
    
    def __init__(self, 
                 db_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5433/tawiza_signals"),
                 ollama_url: str = "http://localhost:11434"):
        self.db_url = db_url
        self.ollama_url = ollama_url
        self.engine = create_async_engine(db_url)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        
    async def get_top_bottom_departments(self, limit: int = 10) -> Dict[str, List[str]]:
        """
        Récupérer les départements top/bottom du scoring Phase 2
        
        Args:
            limit: Nombre de départements à récupérer dans chaque catégorie
            
        Returns:
            Dict avec listes 'top' et 'bottom' des codes département
        """
        logger.info(f"Récupération des top/bottom {limit} départements...")
        
        # Query pour récupérer les dernières anomalies avec scores
        query = """
        SELECT 
            code_commune,
            score,
            description,
            detected_at
        FROM anomalies 
        WHERE score IS NOT NULL
            AND detected_at >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY detected_at DESC
        LIMIT 100;
        """
        
        async with self.session_factory() as session:
            result = await session.execute(text(query))
            anomaly_rows = result.fetchall()
        
        if not anomaly_rows:
            logger.warning("Aucune anomalie avec score trouvée, utilisation de métriques alternatives")
            return await self._get_departments_by_signal_metrics(limit)
        
        # Convertir en DataFrame et extraire les départements
        df = pd.DataFrame(anomaly_rows, columns=['code_commune', 'score', 'description', 'detected_at'])
        
        # Extraire code_dept depuis code_commune (2 premiers caractères)
        df['code_dept'] = df['code_commune'].str[:2]
        
        # Agréger par département (moyenne des scores)
        dept_scores = df.groupby('code_dept')['score'].agg(['mean', 'count']).reset_index()
        dept_scores = dept_scores[dept_scores['count'] >= 2]  # Au moins 2 signaux
        
        # Trier par score moyen
        dept_scores = dept_scores.sort_values('mean', ascending=False)
        
        top_depts = dept_scores.head(limit)['code_dept'].tolist()
        bottom_depts = dept_scores.tail(limit)['code_dept'].tolist()
        
        logger.info(f"Top départements (scores élevés): {top_depts}")
        logger.info(f"Bottom départements (scores faibles): {bottom_depts}")
        
        return {
            "top": top_depts,
            "bottom": bottom_depts
        }
    
    async def _get_departments_by_signal_metrics(self, limit: int) -> Dict[str, List[str]]:
        """Fallback: utiliser les métriques de signaux pour classer les départements"""
        
        query = """
        SELECT 
            code_dept,
            COUNT(*) as signal_count,
            AVG(metric_value) as avg_metric_value,
            COUNT(DISTINCT metric_name) as metric_diversity
        FROM signals 
        WHERE code_dept IS NOT NULL 
            AND metric_value IS NOT NULL
            AND event_date >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY code_dept
        HAVING COUNT(*) >= 10
        ORDER BY signal_count DESC, metric_diversity DESC;
        """
        
        async with self.session_factory() as session:
            result = await session.execute(text(query))
            rows = result.fetchall()
        
        if not rows:
            logger.error("Aucune donnée trouvée pour classer les départements")
            return {"top": [], "bottom": []}
        
        df = pd.DataFrame(rows, columns=['code_dept', 'signal_count', 'avg_metric_value', 'metric_diversity'])
        
        # Score composite simple
        df['composite_score'] = (
            df['signal_count'].rank(pct=True) * 0.4 +
            df['metric_diversity'].rank(pct=True) * 0.6
        )
        
        df = df.sort_values('composite_score', ascending=False)
        
        top_depts = df.head(limit)['code_dept'].tolist()
        bottom_depts = df.tail(limit)['code_dept'].tolist()
        
        return {"top": top_depts, "bottom": bottom_depts}

    async def generate_factor_hypotheses(self, top_bottom_depts: Dict[str, List[str]]) -> List[Dict[str, str]]:
        """
        Générer des hypothèses de facteurs via Ollama
        
        Args:
            top_bottom_depts: Dict avec départements top/bottom
            
        Returns:
            Liste d'hypothèses avec description et méthode de calcul
        """
        logger.info("Génération d'hypothèses de facteurs via LLM...")
        
        top_depts = top_bottom_depts["top"][:5]  # Limiter pour le prompt
        bottom_depts = top_bottom_depts["bottom"][:5]
        
        # Récupérer quelques caractéristiques des départements pour le contexte
        context = await self._get_department_context(top_depts + bottom_depts)
        
        prompt = f"""Tu es un expert en économie territoriale et data science. 

CONTEXTE:
- Départements performants: {top_depts}
- Départements en difficulté: {bottom_depts}

DONNÉES DISPONIBLES dans notre base:
{context}

MISSION: Propose 8-10 nouveaux facteurs économiques innovants qui pourraient expliquer les différences entre départements performants et en difficulté. 

Pour chaque facteur, fournis:
1. Nom du facteur (court)
2. Description (1-2 phrases)  
3. Méthode de calcul précise avec les métriques disponibles
4. Justification économique

Format de réponse (JSON strict):
```json
[
  {{
    "name": "densité_entrepreneuriale",
    "description": "Ratio entre créations et fermetures d'entreprises pondéré par la population active",
    "calculation_method": "(création_entreprise / fermeture_entreprise) * (offres_emploi / 1000)",
    "economic_rationale": "Mesure la dynamique entrepreneuriale locale ajustée par l'activité économique"
  }}
]
```

Sois créatif mais réaliste avec les données disponibles."""

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "qwen3.5:27b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get("response", "")
                    
                    # Extraire le JSON de la réponse
                    hypotheses = self._extract_json_from_response(llm_response)
                    
                    logger.info(f"LLM a généré {len(hypotheses)} hypothèses de facteurs")
                    return hypotheses
                    
                else:
                    logger.error(f"Erreur Ollama: {response.status_code} - {response.text}")
                    return self._get_fallback_hypotheses()
                    
        except Exception as e:
            logger.error(f"Erreur connexion Ollama: {e}")
            return self._get_fallback_hypotheses()

    async def _get_department_context(self, dept_codes: List[str]) -> str:
        """Récupérer le contexte des départements pour le prompt"""
        
        context_query = """
        SELECT 
            code_dept,
            metric_name,
            AVG(metric_value) as avg_value,
            COUNT(*) as count
        FROM signals 
        WHERE code_dept = ANY($1)
            AND metric_value IS NOT NULL
            AND event_date >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY code_dept, metric_name
        ORDER BY code_dept, count DESC;
        """
        
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            result = await raw.driver_connection.fetch(context_query, dept_codes)
        
        # Construire le contexte par département
        context_lines = []
        current_dept = None
        dept_metrics = []
        
        for row in result:
            if current_dept != row['code_dept']:
                if current_dept:
                    context_lines.append(f"- Dept {current_dept}: {', '.join(dept_metrics[:5])}")
                current_dept = row['code_dept']
                dept_metrics = []
            
            dept_metrics.append(f"{row['metric_name']} ({row['avg_value']:.1f})")
        
        if current_dept:
            context_lines.append(f"- Dept {current_dept}: {', '.join(dept_metrics[:5])}")
        
        return "\n".join(context_lines[:10])  # Limiter la taille

    def _extract_json_from_response(self, response: str) -> List[Dict[str, str]]:
        """Extraire le JSON de la réponse LLM"""
        try:
            # Chercher le JSON entre ```json et ```
            start_idx = response.find("```json")
            if start_idx != -1:
                start_idx += 7
                end_idx = response.find("```", start_idx)
                if end_idx != -1:
                    json_str = response[start_idx:end_idx].strip()
                    return json.loads(json_str)
            
            # Fallback: chercher un JSON direct
            import re
            json_pattern = r'\[\s*\{.*?\}\s*\]'
            matches = re.findall(json_pattern, response, re.DOTALL)
            if matches:
                return json.loads(matches[0])
                
        except Exception as e:
            logger.error(f"Erreur extraction JSON: {e}")
        
        return self._get_fallback_hypotheses()

    def _get_fallback_hypotheses(self) -> List[Dict[str, str]]:
        """Hypothèses de fallback si LLM échoue"""
        return [
            {
                "name": "ratio_dynamisme_economique",
                "description": "Ratio entre créations d'entreprises et liquidations judiciaires",
                "calculation_method": "creation_entreprise / (liquidation_judiciaire + 1)",
                "economic_rationale": "Mesure la santé entrepreneuriale locale"
            },
            {
                "name": "indicateur_emploi_immobilier",
                "description": "Corrélation entre offres d'emploi et prix immobilier",
                "calculation_method": "offres_emploi / (prix_m2_moyen / 1000)",
                "economic_rationale": "Attractivité économique vs coût de la vie"
            },
            {
                "name": "densite_transactionnelle",
                "description": "Volume de transactions immobilières par habitant équivalent",
                "calculation_method": "transactions_immobilieres / (offres_emploi / 100)",
                "economic_rationale": "Fluidité du marché immobilier local"
            },
            {
                "name": "score_resilience_entreprises",
                "description": "Capacité de résistance aux difficultés économiques",
                "calculation_method": "vente_fonds_commerce / (liquidation_judiciaire + redressement_judiciaire + 1)",
                "economic_rationale": "Mesure la résilience du tissu économique"
            }
        ]

    async def calculate_information_coefficient(self, factor_def: Dict[str, str]) -> Dict[str, Any]:
        """
        Calculer l'Information Coefficient (IC) pour une hypothèse de facteur
        
        Args:
            factor_def: Définition du facteur avec méthode de calcul
            
        Returns:
            Dict avec IC, p-value, et métadonnées
        """
        logger.info(f"Calcul IC pour facteur: {factor_def['name']}")
        
        try:
            # Récupérer les données nécessaires
            factor_data = await self._compute_factor_values(factor_def)
            
            if factor_data.empty:
                logger.warning(f"Pas de données pour calculer {factor_def['name']}")
                return {
                    "factor_name": factor_def["name"],
                    "ic_pearson": None,
                    "ic_spearman": None,
                    "p_value_pearson": None,
                    "p_value_spearman": None,
                    "sample_size": 0,
                    "error": "Données insuffisantes"
                }
            
            # Récupérer les scores de référence (ou proxy)
            reference_scores = await self._get_reference_scores(factor_data.index.tolist())
            
            if reference_scores.empty:
                logger.warning(f"Pas de scores de référence disponibles")
                return {
                    "factor_name": factor_def["name"],
                    "ic_pearson": None,
                    "ic_spearman": None,
                    "error": "Scores de référence manquants"
                }
            
            # Aligner les données
            common_depts = factor_data.index.intersection(reference_scores.index)
            if len(common_depts) < 5:
                return {
                    "factor_name": factor_def["name"],
                    "ic_pearson": None,
                    "ic_spearman": None,
                    "error": f"Pas assez de départements communs ({len(common_depts)})"
                }
            
            factor_values = factor_data.loc[common_depts, 'factor_value']
            ref_values = reference_scores.loc[common_depts, 'score']
            
            # Supprimer les NaN
            mask = ~(pd.isna(factor_values) | pd.isna(ref_values))
            factor_clean = factor_values[mask]
            ref_clean = ref_values[mask]
            
            if len(factor_clean) < 5:
                return {
                    "factor_name": factor_def["name"],
                    "ic_pearson": None,
                    "ic_spearman": None,
                    "error": "Pas assez de valeurs valides après nettoyage"
                }
            
            # Calculer les corrélations (Information Coefficient)
            ic_pearson, p_val_pearson = pearsonr(factor_clean, ref_clean)
            ic_spearman, p_val_spearman = spearmanr(factor_clean, ref_clean)
            
            result = {
                "factor_name": factor_def["name"],
                "description": factor_def["description"],
                "calculation_method": factor_def["calculation_method"],
                "economic_rationale": factor_def["economic_rationale"],
                "ic_pearson": float(ic_pearson),
                "ic_spearman": float(ic_spearman),
                "p_value_pearson": float(p_val_pearson),
                "p_value_spearman": float(p_val_spearman),
                "sample_size": len(factor_clean),
                "factor_mean": float(factor_clean.mean()),
                "factor_std": float(factor_clean.std()),
                "significant_pearson": p_val_pearson < 0.05,
                "significant_spearman": p_val_spearman < 0.05
            }
            
            logger.info(f"IC calculé pour {factor_def['name']}: Pearson={ic_pearson:.3f} (p={p_val_pearson:.3f})")
            return result
            
        except Exception as e:
            logger.error(f"Erreur calcul IC pour {factor_def['name']}: {e}")
            return {
                "factor_name": factor_def["name"],
                "ic_pearson": None,
                "ic_spearman": None,
                "error": str(e)
            }

    async def _compute_factor_values(self, factor_def: Dict[str, str]) -> pd.DataFrame:
        """Calculer les valeurs du facteur pour chaque département"""
        
        # Parser la méthode de calcul pour identifier les métriques nécessaires
        calc_method = factor_def["calculation_method"]
        
        # Identifier les métriques mentionnées
        known_metrics = [
            'offres_emploi', 'transactions_immobilieres', 'prix_m2_moyen',
            'liquidation_judiciaire', 'vente_fonds_commerce', 
            'creation_entreprise', 'fermeture_entreprise',
            'redressement_judiciaire', 'procedure_collective'
        ]
        
        needed_metrics = [metric for metric in known_metrics if metric in calc_method]
        
        if not needed_metrics:
            logger.warning(f"Aucune métrique reconnue dans: {calc_method}")
            return pd.DataFrame()
        
        # Query pour récupérer les métriques nécessaires
        metrics_query = """
        SELECT 
            code_dept,
            metric_name,
            AVG(metric_value) as avg_value,
            COUNT(*) as signal_count
        FROM signals 
        WHERE code_dept IS NOT NULL 
            AND metric_name = ANY($1)
            AND metric_value IS NOT NULL
            AND event_date >= CURRENT_DATE - INTERVAL '365 days'
        GROUP BY code_dept, metric_name
        HAVING COUNT(*) >= 3
        ORDER BY code_dept;
        """
        
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            result = await raw.driver_connection.fetch(metrics_query, needed_metrics)
        
        if not result:
            return pd.DataFrame()
        
        # Pivoter en DataFrame
        df = pd.DataFrame(result, columns=['code_dept', 'metric_name', 'avg_value', 'signal_count'])
        pivot_df = df.pivot(index='code_dept', columns='metric_name', values='avg_value')
        
        # Remplir les NaN avec 0 ou médiane selon le contexte
        pivot_df = pivot_df.fillna(0)
        
        # Calculer le facteur selon la méthode définie
        try:
            factor_values = self._evaluate_factor_formula(calc_method, pivot_df)
            
            # Filtrer les valeurs aberrantes
            if len(factor_values) > 0:
                q99 = factor_values.quantile(0.99)
                q01 = factor_values.quantile(0.01) 
                factor_values = factor_values.clip(lower=q01, upper=q99)
            
            return pd.DataFrame({'factor_value': factor_values})
            
        except Exception as e:
            logger.error(f"Erreur calcul facteur: {e}")
            return pd.DataFrame()

    def _evaluate_factor_formula(self, formula: str, data: pd.DataFrame) -> pd.Series:
        """Évaluer la formule du facteur de manière sécurisée"""
        
        # Remplacer les noms de métriques par les colonnes de données
        # Sort by length descending to avoid partial replacements
        safe_formula = formula
        for col in sorted(data.columns, key=len, reverse=True):
            safe_formula = safe_formula.replace(col, f"data['{col}']")
        
        # Use np.maximum for safe division instead of string manipulation
        import re
        safe_formula = re.sub(r'/ \(([^)]+)\)', r'/ np.maximum(\1, 0.001)', safe_formula)
        
        # Évaluer la formule
        try:
            # Contexte sécurisé pour eval
            safe_dict = {
                'data': data,
                'np': np,
                'abs': abs,
                'max': max,
                'min': min
            }
            
            result = eval(safe_formula, {"__builtins__": {}}, safe_dict)
            
            if isinstance(result, pd.Series):
                return result
            else:
                return pd.Series(result, index=data.index)
                
        except Exception as e:
            logger.error(f"Erreur évaluation formule '{formula}': {e}")
            # Fallback: retourner une série simple
            if len(data.columns) > 0:
                return data.iloc[:, 0]  # Première colonne
            return pd.Series(dtype=float)

    async def _get_reference_scores(self, dept_codes: List[str]) -> pd.DataFrame:
        """Récupérer les scores de référence pour les départements"""
        
        # D'abord essayer les anomalies avec scores
        anomaly_query = """
        SELECT 
            SUBSTRING(code_commune, 1, 2) as code_dept,
            AVG(score) as score
        FROM anomalies 
        WHERE score IS NOT NULL
            AND SUBSTRING(code_commune, 1, 2) = ANY($1)
            AND detected_at >= CURRENT_DATE - INTERVAL '60 days'
        GROUP BY SUBSTRING(code_commune, 1, 2);
        """
        
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            result = await raw.driver_connection.fetch(anomaly_query, dept_codes)
        
        if result:
            df = pd.DataFrame(result, columns=['code_dept', 'score'])
            return df.set_index('code_dept')
        
        # Fallback: créer un score composite simple
        logger.info("Aucun score d'anomalie disponible, utilisation d'un score composite")
        
        composite_query = """
        SELECT 
            code_dept,
            AVG(CASE WHEN metric_name = 'offres_emploi' THEN metric_value ELSE 0 END) as emploi,
            AVG(CASE WHEN metric_name = 'liquidation_judiciaire' THEN metric_value ELSE 0 END) as liquidations,
            COUNT(DISTINCT metric_name) as diversity
        FROM signals 
        WHERE code_dept = ANY($1)
            AND metric_value IS NOT NULL
            AND event_date >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY code_dept;
        """
        
        result = await connection.fetch(composite_query, dept_codes)
        
        if not result:
            return pd.DataFrame()
        
        df = pd.DataFrame(result, columns=['code_dept', 'emploi', 'liquidations', 'diversity'])
        
        # Score composite simple: emploi positif, liquidations négatif
        df['score'] = (
            df['emploi'].rank(pct=True) * 0.4 +
            (1 - df['liquidations'].rank(pct=True)) * 0.4 +
            df['diversity'].rank(pct=True) * 0.2
        )
        
        return df.set_index('code_dept')[['score']]

    async def run_factor_mining(self) -> Dict[str, Any]:
        """
        Exécuter le processus complet de Factor Mining
        
        Returns:
            Dict avec hypothèses générées et leurs IC
        """
        logger.info("Démarrage du Factor Mining...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "top_bottom_departments": {},
            "factor_hypotheses": [],
            "information_coefficients": []
        }
        
        try:
            # Étape 1: Identifier les départements top/bottom
            top_bottom_depts = await self.get_top_bottom_departments()
            results["top_bottom_departments"] = top_bottom_depts
            
            if not top_bottom_depts["top"] and not top_bottom_depts["bottom"]:
                logger.warning("Aucun département trouvé pour l'analyse")
                return results
            
            # Étape 2: Générer des hypothèses via LLM
            hypotheses = await self.generate_factor_hypotheses(top_bottom_depts)
            results["factor_hypotheses"] = hypotheses
            
            # Étape 3: Calculer l'IC pour chaque hypothèse
            ic_results = []
            for hypothesis in hypotheses:
                ic_result = await self.calculate_information_coefficient(hypothesis)
                ic_results.append(ic_result)
            
            results["information_coefficients"] = ic_results
            
            # Trier par IC absolu (Spearman de préférence)
            valid_ics = [r for r in ic_results if r.get("ic_spearman") is not None]
            valid_ics.sort(key=lambda x: abs(x["ic_spearman"]), reverse=True)
            
            results["best_factors"] = valid_ics[:5]  # Top 5
            
            logger.info(f"Factor Mining terminé: {len(hypotheses)} hypothèses, {len(valid_ics)} ICs valides")
            
        except Exception as e:
            logger.error(f"Erreur Factor Mining: {e}")
            results["error"] = str(e)
        
        return results


# Fonction principale pour tests
async def main():
    """Fonction de test du Factor Mining"""
    factor_miner = FactorMining()
    
    try:
        # Test départements top/bottom
        top_bottom = await factor_miner.get_top_bottom_departments(limit=5)
        print(f"Top/Bottom départements: {top_bottom}")
        
        # Test génération d'hypothèses (avec fallback)
        hypotheses = factor_miner._get_fallback_hypotheses()
        print(f"\nHypothèses de test: {len(hypotheses)}")
        
        # Test calcul IC sur une hypothèse
        if hypotheses:
            ic_result = await factor_miner.calculate_information_coefficient(hypotheses[0])
            print(f"\nIC test: {ic_result}")
        
        # Test complet
        full_results = await factor_miner.run_factor_mining()
        print(f"\nFactor Mining complet: {full_results.get('timestamp')}")
        print(f"Meilleurs facteurs: {len(full_results.get('best_factors', []))}")
        
    except Exception as e:
        logger.error(f"Erreur main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())