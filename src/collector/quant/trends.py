"""Trend detection combining temporal signals - Phase 3 of Tawiza-V2 algorithm.

Detects trend changes across departments by combining:
- Moving average crossovers
- Rate of change analysis  
- Cross-source lag correlations
- Alpha factors from Phase 2

Generates human-readable trend alerts for territorial intelligence.
"""

from typing import Dict, List, Optional, Any
import asyncio
from datetime import date
from collections import defaultdict

import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .temporal import compute_moving_averages, compute_rate_of_change, compute_lag_correlations
from .factors import AlphaFactorsCalculator


async def detect_trends(db_url: str) -> List[Dict[str, Any]]:
    """Detect trend changes across all departments.
    
    Args:
        db_url: Database connection URL
        
    Returns:
        List of trend alerts:
        [{
            'dept': '59',
            'metric': 'liquidation_judiciaire', 
            'trend_type': 'acceleration'/'deceleration'/'reversal',
            'confidence': 0.75,
            'description': 'Nord(59): liquidations en accélération (+45% sur 6 mois, MA3 > MA12)',
            'signals': {...}  # Raw data for analysis
        }]
    """
    logger.info("Starting comprehensive trend detection across all departments")
    
    engine = create_async_engine(db_url, echo=False)
    alerts = []
    
    try:
        # Get all departments and their key metrics
        async with engine.begin() as conn:
            query = text("""
                SELECT DISTINCT code_dept, metric_name, COUNT(*) as signal_count
                FROM signals 
                WHERE code_dept IS NOT NULL 
                    AND event_date >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY code_dept, metric_name
                HAVING COUNT(*) >= 5  -- Minimum signals for analysis
                ORDER BY code_dept, signal_count DESC
            """)
            
            result = await conn.execute(query)
            dept_metrics = result.fetchall()
            
        if not dept_metrics:
            logger.warning("No sufficient data found for trend analysis")
            return []
        
        # Group by department
        dept_data = defaultdict(list)
        for row in dept_metrics:
            dept_data[row.code_dept].append({
                'metric': row.metric_name,
                'signal_count': row.signal_count
            })
        
        # Analyze trends for each department
        for dept, metrics in dept_data.items():
            logger.info(f"Analyzing trends for department {dept}")
            
            # Get ROC for all metrics in this department
            roc_data = await compute_rate_of_change(db_url, dept, periods=[3, 6])
            
            # Analyze key metrics individually
            for metric_info in metrics[:3]:  # Top 3 metrics by volume
                metric_name = metric_info['metric']
                
                # Skip if insufficient ROC data
                if metric_name not in roc_data or not roc_data[metric_name]:
                    continue
                
                # Get moving averages for this specific metric
                ma_data = await compute_moving_averages(db_url, dept, metric_name)
                
                # Generate trend alert if significant patterns found
                alert = await _generate_trend_alert(
                    dept, metric_name, ma_data, roc_data[metric_name], metric_info['signal_count']
                )
                
                if alert:
                    alerts.append(alert)
        
        # Add correlation-based alerts
        correlation_alerts = await _generate_correlation_alerts(db_url)
        alerts.extend(correlation_alerts)
        
        # Sort alerts by confidence (highest first)
        alerts.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        logger.info(f"Generated {len(alerts)} trend alerts")
        return alerts
        
    except Exception as e:
        logger.error(f"Error in trend detection: {e}")
        return []
    finally:
        await engine.dispose()


async def _generate_trend_alert(
    dept: str,
    metric_name: str, 
    ma_data: Dict[str, Any],
    roc_data: Dict[str, Any],
    signal_count: int
) -> Optional[Dict[str, Any]]:
    """Generate a trend alert for a specific department-metric combination.
    
    Args:
        dept: Department code
        metric_name: Name of the metric
        ma_data: Moving averages data
        roc_data: Rate of change data
        signal_count: Total number of signals
        
    Returns:
        Alert dict or None if no significant trend
    """
    # Minimum thresholds for alerts
    if ma_data.get('data_points', 0) < 6:  # Need at least 6 months of data
        return None
    
    # Extract key indicators
    current_trend = ma_data.get('current_trend', 'neutral')
    crossovers = ma_data.get('crossovers', [])
    roc_3m = roc_data.get('ROC_3m')
    roc_6m = roc_data.get('ROC_6m') 
    is_alert_metric = roc_data.get('alert', False)
    
    # Skip if no significant change
    if current_trend == 'neutral' and not crossovers and not is_alert_metric:
        return None
    
    # Determine trend type and confidence
    trend_type = 'neutral'
    confidence = 0.0
    description_parts = []
    
    # Department name mapping (simplified)
    dept_names = {
        '59': 'Nord', '62': 'Pas-de-Calais', '75': 'Paris', '69': 'Rhône',
        '13': 'Bouches-du-Rhône', '33': 'Gironde', '31': 'Haute-Garonne',
        '44': 'Loire-Atlantique', '54': 'Meurthe-et-Moselle', '67': 'Bas-Rhin'
    }
    dept_name = dept_names.get(dept, f"Dept{dept}")
    
    # Metric interpretation
    metric_display = _format_metric_name(metric_name)
    is_negative_metric = any(neg in metric_name.lower() for neg in ['liquidation', 'fermeture', 'sauvegarde', 'procedure'])
    
    # Analyze ROC patterns
    if roc_6m is not None and abs(roc_6m) > 0.3:  # 30% change
        if roc_6m > 0:
            if is_negative_metric:
                trend_type = 'acceleration'  # Bad trend accelerating
                description_parts.append(f"en accélération (+{roc_6m:.0%} sur 6 mois)")
            else:
                trend_type = 'improvement'  # Good trend accelerating
                description_parts.append(f"en amélioration (+{roc_6m:.0%} sur 6 mois)")
        else:
            if is_negative_metric:
                trend_type = 'deceleration'  # Bad trend decelerating (good)
                description_parts.append(f"en décélération ({roc_6m:.0%} sur 6 mois)")
            else:
                trend_type = 'decline'  # Good trend decelerating (bad)
                description_parts.append(f"en déclin ({roc_6m:.0%} sur 6 mois)")
        
        confidence += 0.4
    
    # Analyze crossover signals
    if crossovers:
        latest_cross = crossovers[-1]
        cross_type = latest_cross['type']
        
        if cross_type == 'golden_cross':
            if is_negative_metric:
                trend_type = 'reversal'  # Bad metric crossing up (worse)
                description_parts.append("signal de retournement haussier (MA3 > MA12)")
            else:
                trend_type = 'reversal'  # Good metric crossing up (better)
                description_parts.append("signal de retournement haussier (MA3 > MA12)")
        else:  # death_cross
            if is_negative_metric:
                trend_type = 'reversal'  # Bad metric crossing down (better)
                description_parts.append("signal de retournement baissier (MA3 < MA12)")
            else:
                trend_type = 'reversal'  # Good metric crossing down (worse)
                description_parts.append("signal de retournement baissier (MA3 < MA12)")
        
        confidence += 0.3
    
    # Alert threshold logic
    if is_alert_metric:
        confidence += 0.3
        description_parts.append("⚠️ seuil d'alerte dépassé")
    
    # Require minimum confidence
    if confidence < 0.4:
        return None
    
    # Build description
    description = f"{dept_name}({dept}): {metric_display}"
    if description_parts:
        description += " " + ", ".join(description_parts)
    
    return {
        'dept': dept,
        'dept_name': dept_name,
        'metric': metric_name,
        'metric_display': metric_display,
        'trend_type': trend_type,
        'confidence': min(confidence, 1.0),
        'description': description,
        'signals': {
            'ma_data': ma_data,
            'roc_data': roc_data,
            'signal_count': signal_count,
            'is_negative_metric': is_negative_metric
        }
    }


async def _generate_correlation_alerts(db_url: str) -> List[Dict[str, Any]]:
    """Generate alerts based on cross-source lag correlations.
    
    Args:
        db_url: Database connection URL
        
    Returns:
        List of correlation-based alerts
    """
    logger.info("Analyzing cross-source correlations for predictive alerts")
    
    try:
        # Get lag correlations between key sources
        correlations = await compute_lag_correlations(db_url)
        alerts = []
        
        for pair_name, corr_data in correlations.items():
            if corr_data.get('insufficient_data'):
                continue
                
            best_corr = corr_data.get('best_correlation', 0)
            best_lag = corr_data.get('best_lag_months', 0)
            is_significant = corr_data.get('significant', False)
            
            if is_significant and abs(best_corr) > 0.4:  # Strong correlation
                source1, source2 = pair_name.replace('_vs_', ' → ').split(' → ')
                
                correlation_type = 'positive' if best_corr > 0 else 'negative'
                strength = 'forte' if abs(best_corr) > 0.6 else 'modérée'
                
                description = (
                    f"Corrélation {correlation_type} {strength} ({best_corr:.2f}) "
                    f"entre {source1} et {source2} avec décalage de {best_lag} mois"
                )
                
                alerts.append({
                    'dept': 'ALL',
                    'dept_name': 'National',
                    'metric': f'correlation_{pair_name}',
                    'metric_display': f'Corrélation {source1}/{source2}',
                    'trend_type': 'correlation',
                    'confidence': min(abs(best_corr), 0.9),
                    'description': description,
                    'signals': {
                        'correlation_data': corr_data,
                        'lag_months': best_lag,
                        'correlation_strength': best_corr
                    }
                })
        
        return alerts
        
    except Exception as e:
        logger.error(f"Error generating correlation alerts: {e}")
        return []


def _format_metric_name(metric_name: str) -> str:
    """Format metric name for human-readable display.
    
    Args:
        metric_name: Technical metric name
        
    Returns:
        Human-readable metric name in French
    """
    metric_translations = {
        'liquidation_judiciaire': 'liquidations judiciaires',
        'procedure_collective': 'procédures collectives', 
        'sauvegarde': 'sauvegardes d\'entreprises',
        'creation_entreprise': 'créations d\'entreprises',
        'fermeture_entreprise': 'fermetures d\'entreprises',
        'transactions_immobilieres': 'transactions immobilières',
        'prix_m2': 'prix au m²',
        'logements_commences': 'logements commencés',
        'logements_autorises': 'logements autorisés',
        'search_interest_pôle_emploi': 'recherches "Pôle emploi"',
        'search_interest_RSA': 'recherches "RSA"',
        'vente_fonds_commerce': 'ventes de fonds de commerce',
        'presse_crise': 'mentions presse "crise"',
        'presse_fermeture': 'mentions presse "fermeture"',
        'presse_investissement': 'mentions presse "investissement"'
    }
    
    return metric_translations.get(metric_name, metric_name.replace('_', ' '))