"""Territorial time series models - Séries temporelles pour analyse.

Stocke les indicateurs agrégés par territoire et période.
Permet les corrélations décalées dans le temps.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.infrastructure.persistence.database import Base


class IndicatorType(StrEnum):
    """Types d'indicateurs territoriaux."""

    # Immobilier (DVF)
    DVF_TRANSACTIONS = "dvf_transactions"
    DVF_VOLUME = "dvf_volume"
    DVF_PRICE_M2_APT = "dvf_price_m2_apt"
    DVF_PRICE_M2_HOUSE = "dvf_price_m2_house"

    # Entreprises (SIRENE)
    SIRENE_CREATIONS = "sirene_creations"
    SIRENE_RADIATIONS = "sirene_radiations"
    SIRENE_NET_CREATIONS = "sirene_net_creations"
    SIRENE_STOCK = "sirene_stock"

    # Procédures (BODACC)
    BODACC_PROCEDURES = "bodacc_procedures"
    BODACC_LIQUIDATIONS = "bodacc_liquidations"
    BODACC_REDRESSEMENTS = "bodacc_redressements"
    BODACC_PRIVILEGES = "bodacc_privileges"

    # Emploi (France Travail)
    FT_OFFRES = "ft_offres"
    FT_DEMANDEURS = "ft_demandeurs"
    FT_TENSION = "ft_tension"

    # Démographie (INSEE)
    INSEE_POPULATION = "insee_population"
    INSEE_REVENU_MEDIAN = "insee_revenu_median"
    INSEE_CHOMAGE = "insee_chomage"

    # Subventions
    SUB_DEMANDES = "sub_demandes"
    SUB_ACCORDEES = "sub_accordees"


class GranularityType(StrEnum):
    """Granularité temporelle."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TerritorialTimeSeries(Base):
    """Série temporelle pour un territoire et un indicateur."""

    __tablename__ = "territorial_timeseries"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Territoire
    territory_type = Column(String(20), nullable=False)  # commune, departement, region
    territory_code = Column(String(10), nullable=False)  # Code INSEE
    territory_name = Column(String(100))

    # Indicateur
    indicator = Column(Enum(IndicatorType), nullable=False)
    granularity = Column(Enum(GranularityType), default=GranularityType.MONTHLY)

    # Période
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Valeurs
    value = Column(Float, nullable=False)
    count = Column(Integer)  # Nombre d'observations (pour moyennes)

    # Métadonnées
    source = Column(String(50))  # dvf, sirene, bodacc, etc.
    extra_data = Column(JSONB, default={})  # Détails supplémentaires

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "territory_type",
            "territory_code",
            "indicator",
            "granularity",
            "period_start",
            name="uq_timeseries_unique",
        ),
        Index("idx_timeseries_territory", "territory_type", "territory_code"),
        Index("idx_timeseries_indicator", "indicator"),
        Index("idx_timeseries_period", "period_start", "period_end"),
        Index("idx_timeseries_lookup", "territory_code", "indicator", "period_start"),
    )


class CausalCorrelation(Base):
    """Corrélation causale découverte entre indicateurs."""

    __tablename__ = "causal_correlations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Indicateurs liés
    source_indicator = Column(Enum(IndicatorType), nullable=False)
    target_indicator = Column(Enum(IndicatorType), nullable=False)

    # Territoire (peut être global si NULL)
    territory_type = Column(String(20))
    territory_code = Column(String(10))

    # Corrélation
    correlation = Column(Float, nullable=False)  # -1 à 1
    lag_months = Column(Integer, default=0)  # Décalage temporel

    # Statistiques
    p_value = Column(Float)
    n_observations = Column(Integer)
    confidence = Column(Float)  # 0 à 1

    # Métadonnées
    method = Column(String(50))  # pearson, spearman, granger
    discovered_at = Column(DateTime, default=datetime.utcnow)
    validated = Column(Integer, default=0)  # 0=auto, 1=confirmed, -1=rejected
    notes = Column(Text)

    __table_args__ = (
        Index("idx_corr_source", "source_indicator"),
        Index("idx_corr_target", "target_indicator"),
        Index("idx_corr_territory", "territory_code"),
    )


class TerritorialAnomaly(Base):
    """Anomalie détectée sur un territoire."""

    __tablename__ = "territorial_anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Territoire
    territory_type = Column(String(20), nullable=False)
    territory_code = Column(String(10), nullable=False)

    # Indicateur concerné
    indicator = Column(Enum(IndicatorType), nullable=False)

    # Anomalie
    anomaly_type = Column(String(50))  # spike, drop, trend_break, outlier
    severity = Column(Float)  # 0 à 1

    # Valeurs
    expected_value = Column(Float)
    actual_value = Column(Float)
    deviation_sigma = Column(Float)  # Nombre d'écarts-types

    # Période
    detected_at = Column(DateTime, nullable=False)
    period_start = Column(DateTime)
    period_end = Column(DateTime)

    # Contexte
    context = Column(JSONB, default={})
    related_anomalies = Column(JSONB, default=[])  # IDs d'anomalies liées

    # Statut
    status = Column(String(20), default="new")  # new, confirmed, dismissed
    impact_score = Column(Float)  # Impact potentiel calculé

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_anomaly_territory", "territory_code"),
        Index("idx_anomaly_indicator", "indicator"),
        Index("idx_anomaly_detected", "detected_at"),
        Index("idx_anomaly_severity", "severity"),
    )


class PredictionRecord(Base):
    """Prédiction faite par TAJINE pour validation ultérieure."""

    __tablename__ = "prediction_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Territoire
    territory_type = Column(String(20), nullable=False)
    territory_code = Column(String(10), nullable=False)

    # Prédiction
    prediction_type = Column(String(50))  # defaillance, growth, crisis
    target_indicator = Column(Enum(IndicatorType))

    # Valeurs prédites
    predicted_value = Column(Float)
    confidence = Column(Float)
    horizon_months = Column(Integer)  # Horizon de prédiction

    # Facteurs
    factors = Column(JSONB, default=[])  # Facteurs ayant contribué

    # Dates
    predicted_at = Column(DateTime, default=datetime.utcnow)
    target_date = Column(DateTime)  # Date de réalisation prévue

    # Validation (rempli après)
    actual_value = Column(Float)
    validated_at = Column(DateTime)
    accuracy_score = Column(Float)  # 0 à 1

    __table_args__ = (
        Index("idx_pred_territory", "territory_code"),
        Index("idx_pred_type", "prediction_type"),
        Index("idx_pred_target_date", "target_date"),
    )
