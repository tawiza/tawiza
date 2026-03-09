"""
Machine Learning Detection for Tawiza-V2
Phase 4: Unsupervised anomaly detection and clustering
"""
import os

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import hdbscan
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLDetection:
    """
    Machine Learning Detection for Tawiza-V2 
    
    Provides unsupervised anomaly detection with Isolation Forest
    and clustering with HDBSCAN/DBSCAN for département analysis.
    """
    
    def __init__(self, db_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5433/tawiza")):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        
    async def create_ml_anomalies_table(self) -> None:
        """Créer la table ml_anomalies si elle n'existe pas"""
        sql_commands = [
            """
            CREATE TABLE IF NOT EXISTS ml_anomalies (
                id BIGSERIAL PRIMARY KEY,
                code_dept VARCHAR(3) NOT NULL,
                detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                anomaly_score DOUBLE PRECISION,
                is_anomaly BOOLEAN NOT NULL,
                method VARCHAR(50) NOT NULL,
                features_used TEXT[] NOT NULL,
                feature_values JSONB NOT NULL,
                description TEXT,
                cluster_id INTEGER,
                cluster_size INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_ml_anomalies_dept ON ml_anomalies(code_dept)",
            "CREATE INDEX IF NOT EXISTS idx_ml_anomalies_method ON ml_anomalies(method)",
            "CREATE INDEX IF NOT EXISTS idx_ml_anomalies_detected_at ON ml_anomalies(detected_at)"
        ]
        
        async with self.session_factory() as session:
            try:
                for sql_cmd in sql_commands:
                    await session.execute(text(sql_cmd))
                await session.commit()
                logger.info("Table ml_anomalies créée ou vérifiée")
            except Exception as e:
                logger.error(f"Erreur création table ml_anomalies: {e}")
                await session.rollback()
                raise

    async def build_department_features_matrix(self) -> pd.DataFrame:
        """
        Construire une matrice de features par département depuis la DB
        
        Returns:
            DataFrame avec code_dept en index et features en colonnes
        """
        logger.info("Construction de la matrice de features par département...")
        
        # Query pour agréger les métriques par département
        features_query = """
        WITH dept_metrics AS (
            SELECT 
                code_dept,
                metric_name,
                AVG(metric_value) as avg_value,
                COUNT(*) as signal_count,
                MAX(metric_value) as max_value,
                MIN(metric_value) as min_value,
                STDDEV(metric_value) as std_value
            FROM signals 
            WHERE code_dept IS NOT NULL 
                AND metric_value IS NOT NULL
                AND event_date >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY code_dept, metric_name
        ),
        dept_summary AS (
            SELECT 
                code_dept,
                COUNT(DISTINCT metric_name) as unique_metrics,
                COUNT(DISTINCT source) as unique_sources,
                COUNT(*) as total_signals,
                AVG(confidence) as avg_confidence,
                MIN(event_date) as first_signal_date,
                MAX(event_date) as last_signal_date
            FROM signals 
            WHERE code_dept IS NOT NULL
                AND event_date >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY code_dept
        )
        SELECT 
            dm.code_dept,
            dm.metric_name,
            dm.avg_value,
            dm.signal_count,
            dm.max_value,
            dm.min_value,
            dm.std_value,
            ds.unique_metrics,
            ds.unique_sources, 
            ds.total_signals,
            ds.avg_confidence
        FROM dept_metrics dm
        JOIN dept_summary ds ON dm.code_dept = ds.code_dept
        ORDER BY dm.code_dept, dm.metric_name;
        """
        
        async with self.session_factory() as session:
            result = await session.execute(text(features_query))
            rows = result.fetchall()
            
        if not rows:
            logger.warning("Aucune donnée trouvée pour construire la matrice")
            return pd.DataFrame()
            
        # Convertir en DataFrame et pivoter
        df = pd.DataFrame(rows, columns=[
            'code_dept', 'metric_name', 'avg_value', 'signal_count',
            'max_value', 'min_value', 'std_value', 'unique_metrics',
            'unique_sources', 'total_signals', 'avg_confidence'
        ])
        
        logger.info(f"Données brutes: {len(df)} lignes pour {df['code_dept'].nunique()} départements")
        
        # Features de base par département
        dept_base_features = df.groupby('code_dept').agg({
            'unique_metrics': 'first',
            'unique_sources': 'first', 
            'total_signals': 'first',
            'avg_confidence': 'first'
        })
        
        # Pivoter les métriques principales
        key_metrics = [
            'prix_m2_moyen', 'offres_emploi', 'transactions_immobilieres',
            'liquidation_judiciaire', 'vente_fonds_commerce', 
            'creation_entreprise', 'fermeture_entreprise'
        ]
        
        features_matrix = dept_base_features.copy()
        
        for metric in key_metrics:
            metric_data = df[df['metric_name'] == metric].set_index('code_dept')
            if not metric_data.empty:
                features_matrix[f'{metric}_avg'] = metric_data['avg_value']
                features_matrix[f'{metric}_count'] = metric_data['signal_count']
                features_matrix[f'{metric}_std'] = metric_data['std_value']
        
        # Ratios calculés
        liq_avg = features_matrix.get('liquidation_judiciaire_avg', 0)
        creation_avg = features_matrix.get('creation_entreprise_avg', 0)
        
        # Ratio liquidations/créations (avec gestion division par zéro)
        features_matrix['ratio_liquidation_creation'] = np.where(
            creation_avg > 0, 
            liq_avg / creation_avg, 
            liq_avg
        )
        
        # Densité de signaux par mille habitants (approximation simple)
        features_matrix['signal_density'] = features_matrix['total_signals'] / 1000
        
        # Remplir les NaN avec des médiannes
        numeric_cols = features_matrix.select_dtypes(include=[np.number]).columns
        features_matrix[numeric_cols] = features_matrix[numeric_cols].fillna(
            features_matrix[numeric_cols].median()
        )
        
        logger.info(f"Matrice construite: {len(features_matrix)} départements x {len(features_matrix.columns)} features")
        logger.info(f"Features: {list(features_matrix.columns)}")
        
        return features_matrix

    async def isolation_forest_detection(self, contamination: float = 0.1) -> Dict[str, Any]:
        """
        Détecter les départements outliers avec Isolation Forest
        
        Args:
            contamination: Proportion d'anomalies attendues (0.1 = 10%)
            
        Returns:
            Dict avec résultats de détection
        """
        logger.info(f"Isolation Forest détection (contamination={contamination})...")
        
        # Construire la matrice de features
        features_df = await self.build_department_features_matrix()
        
        if features_df.empty:
            logger.warning("Pas de données pour Isolation Forest")
            return {"anomalies": [], "total_departments": 0}
            
        # Standardiser les features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(features_df)
        
        # Appliquer Isolation Forest
        iso_forest = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=200
        )
        
        outliers = iso_forest.fit_predict(X_scaled)
        anomaly_scores = iso_forest.score_samples(X_scaled)
        
        # Préparer les résultats
        results = []
        for idx, (dept_code, _) in enumerate(features_df.iterrows()):
            is_anomaly = outliers[idx] == -1
            score = float(anomaly_scores[idx])
            
            if is_anomaly:
                feature_values = features_df.loc[dept_code].to_dict()
                # Convertir les valeurs numpy en types Python natifs
                feature_values = {k: (float(v) if not pd.isna(v) else None) 
                                for k, v in feature_values.items()}
                
                results.append({
                    "code_dept": dept_code,
                    "anomaly_score": score,
                    "is_anomaly": True,
                    "method": "isolation_forest",
                    "features_used": list(features_df.columns),
                    "feature_values": feature_values,
                    "description": f"Département détecté comme outlier (score: {score:.3f})"
                })
        
        logger.info(f"Isolation Forest: {len(results)} anomalies détectées sur {len(features_df)} départements")
        
        # Sauvegarder en DB
        await self._save_anomalies_to_db(results)
        
        return {
            "anomalies": results,
            "total_departments": len(features_df),
            "contamination_used": contamination
        }

    async def cluster_departments(self, use_hdbscan: bool = True, min_cluster_size: int = 3) -> Dict[str, Any]:
        """
        Grouper les départements par clustering HDBSCAN/DBSCAN
        
        Args:
            use_hdbscan: Utiliser HDBSCAN (True) ou DBSCAN (False)
            min_cluster_size: Taille minimum des clusters
            
        Returns:
            Dict avec résultats de clustering
        """
        logger.info(f"Clustering départements ({'HDBSCAN' if use_hdbscan else 'DBSCAN'})...")
        
        # Construire la matrice de features
        features_df = await self.build_department_features_matrix()
        
        if features_df.empty:
            logger.warning("Pas de données pour clustering")
            return {"clusters": {}, "anomalies": []}
            
        # Standardiser les features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(features_df)
        
        # Appliquer le clustering
        if use_hdbscan:
            try:
                clusterer = hdbscan.HDBSCAN(
                    min_cluster_size=min_cluster_size,
                    metric='euclidean',
                    cluster_selection_method='eom'
                )
                cluster_labels = clusterer.fit_predict(X_scaled)
                method = "hdbscan"
            except Exception as e:
                logger.warning(f"HDBSCAN failed, falling back to DBSCAN: {e}")
                use_hdbscan = False
        
        if not use_hdbscan:
            clusterer = DBSCAN(eps=0.5, min_samples=min_cluster_size)
            cluster_labels = clusterer.fit_predict(X_scaled)
            method = "dbscan"
        
        # Analyser les résultats
        clusters = {}
        for idx, (dept_code, _) in enumerate(features_df.iterrows()):
            cluster_id = int(cluster_labels[idx])
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(dept_code)
        
        # Calculer les tailles
        cluster_sizes = {cid: len(depts) for cid, depts in clusters.items()}
        
        # Construire les enregistrements pour TOUS les depts (pas seulement noise)
        all_records = []
        noise_depts = []
        for idx, (dept_code, _) in enumerate(features_df.iterrows()):
            cluster_id = int(cluster_labels[idx])
            is_noise = cluster_id == -1
            
            feature_values = features_df.loc[dept_code].to_dict()
            feature_values = {k: (float(v) if not pd.isna(v) else None) 
                            for k, v in feature_values.items()}
            
            all_records.append({
                "code_dept": dept_code,
                "anomaly_score": None,
                "is_anomaly": is_noise,
                "method": method,
                "features_used": list(features_df.columns),
                "feature_values": feature_values,
                "cluster_id": cluster_id if not is_noise else None,
                "cluster_size": cluster_sizes.get(cluster_id, 0) if not is_noise else None,
                "description": f"Cluster {cluster_id} ({cluster_sizes.get(cluster_id, 0)} depts)" if not is_noise else "Département isolé (noise)"
            })
            
            if is_noise:
                noise_depts.append(dept_code)
        
        # Sauvegarder TOUS les résultats de clustering
        await self._save_anomalies_to_db(all_records)
        
        # Stats
        cluster_stats = {}
        for cluster_id, depts in clusters.items():
            if cluster_id != -1:
                cluster_stats[f"cluster_{cluster_id}"] = {
                    "size": len(depts),
                    "departments": depts
                }
        
        logger.info(f"Clustering: {len(cluster_stats)} clusters, {len(noise_depts)} départements isolés")
        
        return {
            "method": method,
            "clusters": cluster_stats,
            "noise_departments": noise_depts,
            "total_departments": len(features_df)
        }

    async def _save_anomalies_to_db(self, anomalies: List[Dict[str, Any]]) -> None:
        """Sauvegarder les anomalies dans la table ml_anomalies"""
        if not anomalies:
            return
            
        logger.info(f"Sauvegarde de {len(anomalies)} anomalies en DB...")
        
        # S'assurer que la table existe
        await self.create_ml_anomalies_table()
        
        insert_sql = """
        INSERT INTO ml_anomalies 
        (code_dept, anomaly_score, is_anomaly, method, features_used, 
         feature_values, description, cluster_id, cluster_size)
        VALUES (:code_dept, :anomaly_score, :is_anomaly, :method, :features_used, 
                :feature_values, :description, :cluster_id, :cluster_size)
        """
        
        async with self.session_factory() as session:
            try:
                for anomaly in anomalies:
                    await session.execute(
                        text(insert_sql),
                        {
                            "code_dept": anomaly["code_dept"],
                            "anomaly_score": anomaly["anomaly_score"],
                            "is_anomaly": anomaly["is_anomaly"],
                            "method": anomaly["method"],
                            "features_used": anomaly["features_used"],
                            "feature_values": json.dumps(anomaly["feature_values"]), 
                            "description": anomaly["description"],
                            "cluster_id": anomaly.get("cluster_id"),
                            "cluster_size": anomaly.get("cluster_size")
                        }
                    )
                
                await session.commit()
                logger.info(f"Anomalies sauvegardées avec succès")
                
            except Exception as e:
                logger.error(f"Erreur sauvegarde anomalies: {e}")
                await session.rollback()
                raise

    async def run_full_detection(self) -> Dict[str, Any]:
        """
        Exécuter la détection complète: Isolation Forest + Clustering
        Nettoie les anciens résultats avant de relancer.
        
        Returns:
            Dict avec tous les résultats
        """
        logger.info("Démarrage de la détection ML complète...")
        
        # Nettoyer les anciens résultats
        await self.create_ml_anomalies_table()
        async with self.session_factory() as session:
            await session.execute(text("TRUNCATE ml_anomalies"))
            await session.commit()
        logger.info("Table ml_anomalies nettoyée")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "isolation_forest": {},
            "clustering": {}
        }
        
        try:
            # Étape 1: Isolation Forest
            isolation_results = await self.isolation_forest_detection(contamination=0.1)
            results["isolation_forest"] = isolation_results
            
            # Étape 2: Clustering — min_cluster_size=2 pour mieux grouper
            clustering_results = await self.cluster_departments(use_hdbscan=True, min_cluster_size=2)
            results["clustering"] = clustering_results
            
            # Étape 3: Feature importance
            features_df = await self.build_department_features_matrix()
            if not features_df.empty:
                results["feature_importance"] = self._compute_feature_importance(features_df)
            
            logger.info("Détection ML complète terminée avec succès")
            
        except Exception as e:
            logger.error(f"Erreur pendant la détection ML: {e}")
            results["error"] = str(e)
            raise
            
        return results
    
    def _compute_feature_importance(self, features_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Calculer l'importance des features via variance et corrélation avec anomaly score"""
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(features_df)
        
        iso = IsolationForest(contamination=0.1, random_state=42, n_estimators=200)
        iso.fit(X_scaled)
        scores = iso.score_samples(X_scaled)
        
        importances = []
        for i, col in enumerate(features_df.columns):
            # Corrélation entre la feature et le score d'anomalie
            corr = float(np.corrcoef(X_scaled[:, i], scores)[0, 1])
            variance = float(np.var(X_scaled[:, i]))
            importances.append({
                "feature": col,
                "correlation_with_anomaly": round(abs(corr), 4),
                "variance": round(variance, 4)
            })
        
        importances.sort(key=lambda x: x["correlation_with_anomaly"], reverse=True)
        return importances


# Fonction principale pour tests
async def main():
    """Fonction de test"""
    ml_detector = MLDetection()
    
    try:
        # Test de la création de table
        await ml_detector.create_ml_anomalies_table()
        
        # Test construction matrice
        features_df = await ml_detector.build_department_features_matrix()
        print(f"Features matrix: {features_df.shape}")
        print(f"Columns: {list(features_df.columns)}")
        print(f"Departments: {list(features_df.index[:10])}")
        
        # Test Isolation Forest
        iso_results = await ml_detector.isolation_forest_detection()
        print(f"\nIsolation Forest: {len(iso_results['anomalies'])} anomalies")
        
        # Test Clustering
        cluster_results = await ml_detector.cluster_departments()
        print(f"\nClustering: {len(cluster_results['clusters'])} clusters")
        
        # Test complet
        full_results = await ml_detector.run_full_detection()
        print(f"\nDétection complète terminée: {full_results['timestamp']}")
        
    except Exception as e:
        logger.error(f"Erreur main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())