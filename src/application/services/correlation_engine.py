"""Correlation Engine - Trouve les corrélations cachées entre indicateurs.

Ce que l'humain ne voit pas:
- Corrélations décalées dans le temps (lag correlations)
- Patterns multi-territoires
- Signaux précurseurs de crises
- Causalité de Granger (prédictibilité statistique)
- Relations non-linéaires (information mutuelle)
- Effets de confounders (corrélation partielle)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import numpy as np
from loguru import logger
from scipy import stats

from src.infrastructure.persistence.models.territorial_timeseries import (
    IndicatorType,
)


class CausalityStrength(StrEnum):
    """Force de la relation causale détectée."""

    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class CorrelationResult:
    """Résultat d'une analyse de corrélation."""

    source_indicator: IndicatorType
    target_indicator: IndicatorType
    correlation: float
    lag_months: int
    p_value: float
    n_observations: int
    confidence: float
    territory_code: str | None = None

    @property
    def is_significant(self) -> bool:
        """Corrélation statistiquement significative ?"""
        return self.p_value < 0.05 and abs(self.correlation) > 0.3

    @property
    def direction(self) -> str:
        """Direction de la corrélation."""
        if self.correlation > 0.1:
            return "positive"
        elif self.correlation < -0.1:
            return "negative"
        return "neutral"

    def to_dict(self) -> dict:
        return {
            "source": self.source_indicator.value,
            "target": self.target_indicator.value,
            "correlation": round(self.correlation, 3),
            "lag_months": self.lag_months,
            "p_value": round(self.p_value, 4),
            "n_observations": self.n_observations,
            "confidence": round(self.confidence, 2),
            "territory": self.territory_code,
            "significant": self.is_significant,
            "direction": self.direction,
        }


@dataclass
class AnomalyResult:
    """Anomalie détectée."""

    indicator: IndicatorType
    territory_code: str
    anomaly_type: str  # spike, drop, trend_break
    severity: float
    expected_value: float
    actual_value: float
    deviation_sigma: float
    period: datetime

    def to_dict(self) -> dict:
        return {
            "indicator": self.indicator.value,
            "territory": self.territory_code,
            "type": self.anomaly_type,
            "severity": round(self.severity, 2),
            "expected": round(self.expected_value, 2),
            "actual": round(self.actual_value, 2),
            "deviation_sigma": round(self.deviation_sigma, 2),
            "period": self.period.isoformat(),
        }


@dataclass
class CausalResult:
    """Résultat d'analyse causale enrichie.

    Combine plusieurs méthodes de détection:
    - Corrélation lag (Pearson avec décalage temporel)
    - Causalité de Granger (F-test sur prédictibilité)
    - Information mutuelle (dépendances non-linéaires)
    - Corrélation partielle (contrôle des confounders)
    """

    source_indicator: IndicatorType
    target_indicator: IndicatorType
    territory_code: str | None

    # Corrélation classique
    correlation: float
    lag_months: int
    p_value: float
    n_observations: int

    # Granger causality
    granger_f_stat: float = 0.0
    granger_p_value: float = 1.0
    granger_significant: bool = False

    # Information mutuelle
    mutual_info: float = 0.0
    mutual_info_normalized: float = 0.0  # 0-1, comparable entre paires

    # Corrélation partielle (contrôlant confounders)
    partial_correlation: float = 0.0
    confounders_controlled: list[str] = field(default_factory=list)

    # Score combiné
    causal_score: float = 0.0
    strength: CausalityStrength = CausalityStrength.NONE

    @property
    def is_causal(self) -> bool:
        """Relation causale statistiquement significative ?"""
        return self.granger_significant and self.lag_months > 0 and abs(self.correlation) > 0.3

    @property
    def is_nonlinear(self) -> bool:
        """Relation non-linéaire détectée ?"""
        # MI élevée mais corrélation faible → relation non-linéaire
        return self.mutual_info_normalized > 0.3 and abs(self.correlation) < 0.3

    def to_dict(self) -> dict:
        return {
            "source": self.source_indicator.value,
            "target": self.target_indicator.value,
            "territory": self.territory_code,
            "correlation": round(self.correlation, 3),
            "lag_months": self.lag_months,
            "p_value": round(self.p_value, 4),
            "n_observations": self.n_observations,
            "granger": {
                "f_stat": round(self.granger_f_stat, 2),
                "p_value": round(self.granger_p_value, 4),
                "significant": self.granger_significant,
            },
            "mutual_info": {
                "raw": round(self.mutual_info, 4),
                "normalized": round(self.mutual_info_normalized, 3),
            },
            "partial_correlation": round(self.partial_correlation, 3),
            "confounders_controlled": self.confounders_controlled,
            "causal_score": round(self.causal_score, 3),
            "strength": self.strength.value,
            "is_causal": self.is_causal,
            "is_nonlinear": self.is_nonlinear,
        }


class CorrelationEngine:
    """Moteur de découverte de corrélations.

    Analyse les séries temporelles pour trouver:
    1. Corrélations lag (indicateur A prédit B avec N mois de décalage)
    2. Anomalies statistiques
    3. Patterns récurrents
    """

    # Paires d'indicateurs à tester pour corrélations
    INDICATOR_PAIRS = [
        # Immobilier → Entreprises
        (IndicatorType.DVF_TRANSACTIONS, IndicatorType.SIRENE_CREATIONS),
        (IndicatorType.DVF_VOLUME, IndicatorType.BODACC_PROCEDURES),
        (IndicatorType.DVF_PRICE_M2_APT, IndicatorType.SIRENE_NET_CREATIONS),
        # Immobilier → Emploi
        (IndicatorType.DVF_TRANSACTIONS, IndicatorType.FT_OFFRES),
        (IndicatorType.DVF_VOLUME, IndicatorType.FT_DEMANDEURS),
        # Entreprises → Procédures
        (IndicatorType.SIRENE_RADIATIONS, IndicatorType.BODACC_PROCEDURES),
        (IndicatorType.SIRENE_NET_CREATIONS, IndicatorType.BODACC_LIQUIDATIONS),
        # Emploi → Entreprises
        (IndicatorType.FT_TENSION, IndicatorType.SIRENE_CREATIONS),
        (IndicatorType.FT_DEMANDEURS, IndicatorType.BODACC_PROCEDURES),
        # Subventions → Croissance
        (IndicatorType.SUB_ACCORDEES, IndicatorType.SIRENE_CREATIONS),
        # Démographie → Immobilier
        (IndicatorType.INSEE_POPULATION, IndicatorType.DVF_TRANSACTIONS),
        (IndicatorType.INSEE_REVENU_MEDIAN, IndicatorType.DVF_PRICE_M2_APT),
    ]

    # Lags à tester (en mois)
    LAGS_TO_TEST = [0, 1, 2, 3, 6, 9, 12, 18, 24]

    def __init__(self):
        self._correlations: list[CorrelationResult] = []
        self._anomalies: list[AnomalyResult] = []

    def compute_lag_correlation(
        self,
        source_series: np.ndarray,
        target_series: np.ndarray,
        max_lag: int = 24,
    ) -> tuple[float, int, float]:
        """Calcule la corrélation optimale avec décalage.

        Args:
            source_series: Série source (cause potentielle)
            target_series: Série cible (effet potentiel)
            max_lag: Lag maximum à tester (en périodes)

        Returns:
            (correlation, optimal_lag, p_value)
        """
        if len(source_series) < 10 or len(target_series) < 10:
            return 0.0, 0, 1.0

        best_corr = 0.0
        best_lag = 0
        best_pval = 1.0

        for lag in range(0, min(max_lag + 1, len(source_series) // 3)):
            if lag == 0:
                s1 = source_series
                s2 = target_series
            else:
                # Source précède Target de `lag` périodes
                s1 = source_series[:-lag]
                s2 = target_series[lag:]

            # Aligner les longueurs
            min_len = min(len(s1), len(s2))
            if min_len < 5:
                continue

            s1 = s1[-min_len:]
            s2 = s2[-min_len:]

            # Calculer corrélation de Pearson
            try:
                corr, pval = stats.pearsonr(s1, s2)

                if abs(corr) > abs(best_corr) and pval < 0.1:
                    best_corr = corr
                    best_lag = lag
                    best_pval = pval
            except Exception:
                continue

        return best_corr, best_lag, best_pval

    def granger_causality_test(
        self,
        cause_series: np.ndarray,
        effect_series: np.ndarray,
        max_lag: int = 4,
    ) -> tuple[float, float, bool]:
        """Test de causalité de Granger.

        Teste si la série 'cause' aide à prédire la série 'effect'
        au-delà de ce que 'effect' peut prédire d'elle-même.

        H0: cause ne Granger-cause pas effect
        H1: cause Granger-cause effect

        Args:
            cause_series: Série potentiellement causale
            effect_series: Série potentiellement causée
            max_lag: Nombre de lags à inclure dans le modèle

        Returns:
            (f_statistic, p_value, is_significant)
        """
        n = len(effect_series)
        if n < max_lag * 3 + 5:  # Besoin de suffisamment de données
            return 0.0, 1.0, False

        try:
            # Modèle restreint: effect ~ lags(effect)
            # Modèle complet: effect ~ lags(effect) + lags(cause)

            # Créer les matrices de design
            y = effect_series[max_lag:]
            n_obs = len(y)

            # Lags de effect (modèle restreint)
            X_restricted = np.column_stack(
                [effect_series[max_lag - i - 1 : n - i - 1] for i in range(max_lag)]
            )
            X_restricted = np.column_stack([np.ones(n_obs), X_restricted])

            # Lags de effect + lags de cause (modèle complet)
            X_full = np.column_stack(
                [X_restricted, *[cause_series[max_lag - i - 1 : n - i - 1] for i in range(max_lag)]]
            )

            # Régression OLS pour chaque modèle
            # Modèle restreint
            beta_r = np.linalg.lstsq(X_restricted, y, rcond=None)[0]
            resid_r = y - X_restricted @ beta_r
            rss_r = np.sum(resid_r**2)

            # Modèle complet
            beta_f = np.linalg.lstsq(X_full, y, rcond=None)[0]
            resid_f = y - X_full @ beta_f
            rss_f = np.sum(resid_f**2)

            # F-test
            df1 = max_lag  # Degrés de liberté numérateur
            df2 = n_obs - 2 * max_lag - 1  # Degrés de liberté dénominateur

            if df2 <= 0 or rss_f <= 0:
                return 0.0, 1.0, False

            f_stat = ((rss_r - rss_f) / df1) / (rss_f / df2)
            p_value = 1 - stats.f.cdf(f_stat, df1, df2)

            is_significant = p_value < 0.05 and f_stat > 0

            return float(f_stat), float(p_value), is_significant

        except (np.linalg.LinAlgError, ValueError) as e:
            logger.debug(f"Granger test failed: {e}")
            return 0.0, 1.0, False

    def mutual_information(
        self,
        x: np.ndarray,
        y: np.ndarray,
        n_bins: int = 10,
    ) -> tuple[float, float]:
        """Calcule l'information mutuelle entre deux séries.

        Détecte les dépendances non-linéaires que la corrélation manque.

        Args:
            x: Première série
            y: Deuxième série
            n_bins: Nombre de bins pour l'histogramme

        Returns:
            (mutual_info_raw, mutual_info_normalized)
        """
        if len(x) != len(y) or len(x) < 10:
            return 0.0, 0.0

        try:
            # Discrétiser les variables
            x_binned = np.digitize(x, np.linspace(x.min(), x.max(), n_bins))
            y_binned = np.digitize(y, np.linspace(y.min(), y.max(), n_bins))

            # Distribution jointe
            joint_hist, _, _ = np.histogram2d(x_binned, y_binned, bins=n_bins)
            joint_prob = joint_hist / joint_hist.sum()

            # Distributions marginales
            p_x = joint_prob.sum(axis=1)
            p_y = joint_prob.sum(axis=0)

            # Calculer MI
            mi = 0.0
            for i in range(n_bins):
                for j in range(n_bins):
                    if joint_prob[i, j] > 0 and p_x[i] > 0 and p_y[j] > 0:
                        mi += joint_prob[i, j] * np.log(joint_prob[i, j] / (p_x[i] * p_y[j]))

            # Normaliser par min des entropies (0-1)
            h_x = -np.sum(p_x[p_x > 0] * np.log(p_x[p_x > 0]))
            h_y = -np.sum(p_y[p_y > 0] * np.log(p_y[p_y > 0]))

            if min(h_x, h_y) > 0:
                mi_normalized = mi / min(h_x, h_y)
            else:
                mi_normalized = 0.0

            return float(mi), float(min(1.0, mi_normalized))

        except Exception as e:
            logger.debug(f"Mutual information failed: {e}")
            return 0.0, 0.0

    def partial_correlation(
        self,
        x: np.ndarray,
        y: np.ndarray,
        confounders: list[np.ndarray],
    ) -> float:
        """Calcule la corrélation partielle contrôlant les confounders.

        Répond à: X et Y sont-ils corrélés APRÈS avoir enlevé
        l'effet des variables confondantes ?

        Args:
            x: Première série
            y: Deuxième série
            confounders: Liste de séries confondantes à contrôler

        Returns:
            Corrélation partielle (-1 à 1)
        """
        if len(x) != len(y) or len(x) < 10:
            return 0.0

        if not confounders:
            # Pas de confounders → corrélation simple
            corr, _ = stats.pearsonr(x, y)
            return float(corr)

        try:
            # Aligner toutes les séries
            min_len = min(len(x), len(y), *[len(c) for c in confounders])
            x = x[:min_len]
            y = y[:min_len]
            confounders = [c[:min_len] for c in confounders]

            # Matrice des confounders
            Z = np.column_stack(confounders)
            Z = np.column_stack([np.ones(min_len), Z])  # Ajouter intercept

            # Résidus de x sur Z
            beta_x = np.linalg.lstsq(Z, x, rcond=None)[0]
            resid_x = x - Z @ beta_x

            # Résidus de y sur Z
            beta_y = np.linalg.lstsq(Z, y, rcond=None)[0]
            resid_y = y - Z @ beta_y

            # Corrélation des résidus
            corr, _ = stats.pearsonr(resid_x, resid_y)
            return float(corr)

        except (np.linalg.LinAlgError, ValueError) as e:
            logger.debug(f"Partial correlation failed: {e}")
            return 0.0

    def compute_causal_score(
        self,
        correlation: float,
        granger_p: float,
        granger_significant: bool,
        mutual_info_norm: float,
        lag: int,
    ) -> tuple[float, CausalityStrength]:
        """Calcule un score causal combiné.

        Combine les différentes métriques en un score unique
        et détermine la force de la relation.

        Args:
            correlation: Corrélation de Pearson
            granger_p: P-value du test de Granger
            granger_significant: Granger significatif ?
            mutual_info_norm: Information mutuelle normalisée
            lag: Décalage temporel

        Returns:
            (score, strength)
        """
        score = 0.0

        # Contribution de la corrélation (max 0.3)
        score += min(0.3, abs(correlation) * 0.3)

        # Contribution de Granger (max 0.4)
        if granger_significant:
            granger_contrib = (1 - granger_p) * 0.4
            score += granger_contrib

        # Contribution de l'information mutuelle (max 0.2)
        score += mutual_info_norm * 0.2

        # Bonus pour lag positif (cause précède effet)
        if lag > 0:
            score += 0.1

        # Déterminer la force
        if score < 0.2:
            strength = CausalityStrength.NONE
        elif score < 0.35:
            strength = CausalityStrength.WEAK
        elif score < 0.5:
            strength = CausalityStrength.MODERATE
        elif score < 0.7:
            strength = CausalityStrength.STRONG
        else:
            strength = CausalityStrength.VERY_STRONG

        return min(1.0, score), strength

    def analyze_causal_relationship(
        self,
        source_series: np.ndarray,
        target_series: np.ndarray,
        source_indicator: IndicatorType,
        target_indicator: IndicatorType,
        territory_code: str | None = None,
        confounders: dict[str, np.ndarray] | None = None,
    ) -> CausalResult:
        """Analyse causale complète entre deux séries.

        Combine toutes les méthodes de détection pour une analyse exhaustive.

        Args:
            source_series: Série source (cause potentielle)
            target_series: Série cible (effet potentiel)
            source_indicator: Type d'indicateur source
            target_indicator: Type d'indicateur cible
            territory_code: Code territoire
            confounders: Dict {nom: série} des confounders potentiels

        Returns:
            Résultat d'analyse causale enrichi
        """
        # 1. Corrélation lag classique
        corr, lag, p_val = self.compute_lag_correlation(source_series, target_series)

        # 2. Test de Granger
        f_stat, granger_p, granger_sig = self.granger_causality_test(source_series, target_series)

        # 3. Information mutuelle
        mi_raw, mi_norm = self.mutual_information(source_series, target_series)

        # 4. Corrélation partielle
        confounder_list = list(confounders.values()) if confounders else []
        confounder_names = list(confounders.keys()) if confounders else []
        partial_corr = self.partial_correlation(source_series, target_series, confounder_list)

        # 5. Score combiné
        causal_score, strength = self.compute_causal_score(
            corr, granger_p, granger_sig, mi_norm, lag
        )

        return CausalResult(
            source_indicator=source_indicator,
            target_indicator=target_indicator,
            territory_code=territory_code,
            correlation=corr,
            lag_months=lag,
            p_value=p_val,
            n_observations=min(len(source_series), len(target_series)),
            granger_f_stat=f_stat,
            granger_p_value=granger_p,
            granger_significant=granger_sig,
            mutual_info=mi_raw,
            mutual_info_normalized=mi_norm,
            partial_correlation=partial_corr,
            confounders_controlled=confounder_names,
            causal_score=causal_score,
            strength=strength,
        )

    def find_all_causal_relationships(
        self,
        timeseries_data: dict[tuple[IndicatorType, str], tuple[np.ndarray, list[datetime]]],
    ) -> list[CausalResult]:
        """Trouve toutes les relations causales significatives.

        Version enrichie de find_all_correlations utilisant l'analyse causale complète.

        Args:
            timeseries_data: Dict {(indicator, territory): (values, dates)}

        Returns:
            Liste des relations causales trouvées
        """
        results = []

        # Grouper par territoire
        territories = {key[1] for key in timeseries_data}

        for territory in territories:
            territory_data = {k[0]: v for k, v in timeseries_data.items() if k[1] == territory}

            # Tester chaque paire
            for source_ind, target_ind in self.INDICATOR_PAIRS:
                if source_ind not in territory_data or target_ind not in territory_data:
                    continue

                source_values, _ = territory_data[source_ind]
                target_values, _ = territory_data[target_ind]

                # Construire les confounders potentiels (autres indicateurs)
                confounders = {}
                for ind, (values, _) in territory_data.items():
                    if ind not in (source_ind, target_ind):
                        confounders[ind.value] = values

                # Analyse causale complète
                result = self.analyze_causal_relationship(
                    source_values,
                    target_values,
                    source_ind,
                    target_ind,
                    territory,
                    confounders if len(confounders) <= 3 else None,  # Limiter les confounders
                )

                # Filtrer les résultats non significatifs
                if result.strength != CausalityStrength.NONE:
                    results.append(result)

        # Trier par score causal
        results.sort(key=lambda x: x.causal_score, reverse=True)

        logger.info(f"Found {len(results)} causal relationships")
        return results

    def detect_anomalies(
        self,
        series: np.ndarray,
        indicator: IndicatorType,
        territory_code: str,
        periods: list[datetime],
        window: int = 12,
        threshold_sigma: float = 2.5,
    ) -> list[AnomalyResult]:
        """Détecte les anomalies dans une série temporelle.

        Utilise z-score sur fenêtre glissante.

        Args:
            series: Valeurs de la série
            indicator: Type d'indicateur
            territory_code: Code territoire
            periods: Dates correspondantes
            window: Taille de fenêtre (périodes)
            threshold_sigma: Seuil en écarts-types

        Returns:
            Liste d'anomalies détectées
        """
        anomalies = []

        if len(series) < window + 1:
            return anomalies

        for i in range(window, len(series)):
            # Fenêtre précédente (sans la valeur actuelle)
            window_data = series[i - window : i]
            current_value = series[i]

            mean = np.mean(window_data)
            std = np.std(window_data)

            if std < 1e-10:
                continue

            z_score = (current_value - mean) / std

            if abs(z_score) > threshold_sigma:
                anomaly_type = "spike" if z_score > 0 else "drop"
                severity = min(1.0, abs(z_score) / 5.0)

                anomalies.append(
                    AnomalyResult(
                        indicator=indicator,
                        territory_code=territory_code,
                        anomaly_type=anomaly_type,
                        severity=severity,
                        expected_value=mean,
                        actual_value=current_value,
                        deviation_sigma=abs(z_score),
                        period=periods[i] if i < len(periods) else datetime.now(),
                    )
                )

        return anomalies

    def detect_trend_break(
        self,
        series: np.ndarray,
        indicator: IndicatorType,
        territory_code: str,
        periods: list[datetime],
        min_segment: int = 6,
    ) -> list[AnomalyResult]:
        """Détecte les ruptures de tendance.

        Compare les tendances avant/après chaque point.
        """
        anomalies = []

        if len(series) < min_segment * 2:
            return anomalies

        for i in range(min_segment, len(series) - min_segment):
            # Tendance avant
            x_before = np.arange(min_segment)
            y_before = series[i - min_segment : i]
            slope_before, _, _, _, _ = stats.linregress(x_before, y_before)

            # Tendance après
            x_after = np.arange(min_segment)
            y_after = series[i : i + min_segment]
            slope_after, _, _, _, _ = stats.linregress(x_after, y_after)

            # Changement de signe ou magnitude
            if slope_before * slope_after < 0:  # Changement de signe
                severity = min(1.0, abs(slope_before - slope_after) / (abs(slope_before) + 1e-10))

                if severity > 0.3:
                    anomalies.append(
                        AnomalyResult(
                            indicator=indicator,
                            territory_code=territory_code,
                            anomaly_type="trend_break",
                            severity=severity,
                            expected_value=slope_before,
                            actual_value=slope_after,
                            deviation_sigma=severity * 3,
                            period=periods[i] if i < len(periods) else datetime.now(),
                        )
                    )

        return anomalies

    def find_all_correlations(
        self,
        timeseries_data: dict[tuple[IndicatorType, str], tuple[np.ndarray, list[datetime]]],
    ) -> list[CorrelationResult]:
        """Trouve toutes les corrélations significatives.

        Args:
            timeseries_data: Dict {(indicator, territory): (values, dates)}

        Returns:
            Liste des corrélations trouvées
        """
        results = []

        # Grouper par territoire
        territories = {key[1] for key in timeseries_data}

        for territory in territories:
            territory_data = {k[0]: v for k, v in timeseries_data.items() if k[1] == territory}

            # Tester chaque paire
            for source_ind, target_ind in self.INDICATOR_PAIRS:
                if source_ind not in territory_data or target_ind not in territory_data:
                    continue

                source_values, _ = territory_data[source_ind]
                target_values, _ = territory_data[target_ind]

                corr, lag, pval = self.compute_lag_correlation(source_values, target_values)

                if abs(corr) > 0.2 and pval < 0.1:
                    confidence = (1 - pval) * min(1.0, len(source_values) / 24)

                    results.append(
                        CorrelationResult(
                            source_indicator=source_ind,
                            target_indicator=target_ind,
                            correlation=corr,
                            lag_months=lag,
                            p_value=pval,
                            n_observations=min(len(source_values), len(target_values)),
                            confidence=confidence,
                            territory_code=territory,
                        )
                    )

        # Trier par corrélation absolue
        results.sort(key=lambda x: abs(x.correlation), reverse=True)

        logger.info(f"Found {len(results)} significant correlations")
        return results

    def generate_insights(
        self,
        correlations: list[CorrelationResult],
        anomalies: list[AnomalyResult],
    ) -> list[dict[str, Any]]:
        """Génère des insights exploitables.

        Combine corrélations et anomalies pour produire des alertes.
        """
        insights = []

        # Insight 1: Corrélations prédictives fortes
        for corr in correlations:
            if corr.lag_months >= 3 and abs(corr.correlation) > 0.5:
                insights.append(
                    {
                        "type": "predictive_correlation",
                        "severity": abs(corr.correlation),
                        "message": (
                            f"{corr.source_indicator.value} prédit "
                            f"{corr.target_indicator.value} avec {corr.lag_months} mois d'avance "
                            f"(r={corr.correlation:.2f}, p={corr.p_value:.3f})"
                        ),
                        "territory": corr.territory_code,
                        "actionable": True,
                    }
                )

        # Insight 2: Anomalies sur indicateurs corrélés
        corr_sources = {c.source_indicator for c in correlations if c.is_significant}

        for anomaly in anomalies:
            if anomaly.indicator in corr_sources:
                # Trouver les indicateurs impactés
                impacted = [
                    c.target_indicator.value
                    for c in correlations
                    if c.source_indicator == anomaly.indicator and c.is_significant
                ]

                if impacted:
                    insights.append(
                        {
                            "type": "cascade_risk",
                            "severity": anomaly.severity,
                            "message": (
                                f"Anomalie {anomaly.anomaly_type} sur {anomaly.indicator.value} "
                                f"({anomaly.deviation_sigma:.1f}σ) - "
                                f"Impact probable sur: {', '.join(impacted)}"
                            ),
                            "territory": anomaly.territory_code,
                            "actionable": True,
                        }
                    )

        # Insight 3: Clusters d'anomalies
        territory_anomalies: dict[str, list] = {}
        for a in anomalies:
            territory_anomalies.setdefault(a.territory_code, []).append(a)

        for territory, anoms in territory_anomalies.items():
            if len(anoms) >= 3:
                indicators = [a.indicator.value for a in anoms]
                avg_severity = sum(a.severity for a in anoms) / len(anoms)

                insights.append(
                    {
                        "type": "anomaly_cluster",
                        "severity": avg_severity,
                        "message": (
                            f"Cluster de {len(anoms)} anomalies sur {territory}: "
                            f"{', '.join(set(indicators))}"
                        ),
                        "territory": territory,
                        "actionable": True,
                    }
                )

        # Trier par sévérité
        insights.sort(key=lambda x: x["severity"], reverse=True)

        return insights


# Singleton
_engine: CorrelationEngine | None = None


def get_correlation_engine() -> CorrelationEngine:
    """Get singleton instance."""
    global _engine
    if _engine is None:
        _engine = CorrelationEngine()
    return _engine
