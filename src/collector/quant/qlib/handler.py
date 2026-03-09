"""
Territorial DataHandler adapted from Microsoft QLib.

This is the main orchestrator that loads data from PostgreSQL,
applies processing chains, generates alpha features, and creates
datasets ready for machine learning.

Adapted from: https://github.com/microsoft/qlib/blob/main/qlib/data/dataset/handler.py
License: MIT
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Union, Any, Tuple
from datetime import datetime, date
import warnings
from dataclasses import dataclass

from .ops import evaluate_expression
from .processor import ProcessorChain, Processor
from .dataset import TerritorialDataset
from .expressions import ALPHA_EXPRESSIONS, get_compatible_expressions, validate_expression_metrics


@dataclass
class DataHandlerConfig:
    """Configuration for TerritorialDataHandler."""
    db_url: str
    territories: Optional[List[str]] = None
    start_date: Optional[Union[str, date]] = None
    end_date: Optional[Union[str, date]] = None
    raw_features: Optional[List[str]] = None
    alpha_expressions: Optional[List[str]] = None
    infer_processors: Optional[ProcessorChain] = None
    learn_processors: Optional[ProcessorChain] = None
    population_data: Optional[Dict[str, float]] = None


class TerritorialDataHandler:
    """
    Territorial data handler for loading, processing and feature generation.
    
    This is the main interface for working with territorial time series data.
    It handles:
    1. Loading raw data from PostgreSQL
    2. Applying processing pipelines (normalization, etc.)
    3. Generating alpha features from expressions
    4. Creating datasets for ML workflows
    
    Args:
        config: DataHandler configuration
    """
    
    def __init__(self, config: DataHandlerConfig):
        self.config = config
        self._raw_data = None
        self._processed_data = {}  # Cache for processed data
        self._population_data = config.population_data or {}
        
        # Default territories (main French departments if none specified)
        if self.config.territories is None:
            self.config.territories = [
                "06", "13", "31", "33", "34", "35", "44", "54", "59", "62", "67", "69", "75", "76", "93", "94"
            ]
        
        # Default time range
        if self.config.start_date is None:
            self.config.start_date = "2024-01-01"
        if self.config.end_date is None:
            self.config.end_date = datetime.now().strftime("%Y-%m-%d")
    
    async def _load_population_data(self) -> Dict[str, float]:
        """Load population data from our population module."""
        if not self._population_data:
            try:
                # Try to load from existing population module
                from ..population import get_population_data
                self._population_data = await get_population_data()
            except ImportError:
                warnings.warn("Population module not available. Population normalization will be skipped.")
                self._population_data = {}
        return self._population_data
    
    async def load_raw_data(self, 
                           territories: Optional[List[str]] = None,
                           start_date: Optional[Union[str, date]] = None,
                           end_date: Optional[Union[str, date]] = None,
                           metrics: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Load raw data from PostgreSQL signals table.
        
        Args:
            territories: Territory codes to load (default: config territories)
            start_date: Start date (default: config start_date)
            end_date: End date (default: config end_date)
            metrics: Specific metrics to load (default: all available)
            
        Returns:
            DataFrame with MultiIndex (event_date, code_dept) and metric columns
        """
        territories = territories or self.config.territories
        start_date = start_date or self.config.start_date
        end_date = end_date or self.config.end_date
        
        # Convert dates to strings if needed
        if isinstance(start_date, date):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, date):
            end_date = end_date.strftime("%Y-%m-%d")
        
        # Build query
        territory_list = "', '".join(territories)
        query = f"""
        SELECT 
            event_date,
            code_dept,
            source,
            metric_name,
            metric_value,
            confidence
        FROM signals 
        WHERE 
            event_date >= $1
            AND event_date <= $2
            AND code_dept IN ('{territory_list}')
            AND metric_value IS NOT NULL
        """
        
        if metrics:
            metric_list = "', '".join(metrics)
            query += f" AND metric_name IN ('{metric_list}')"
        
        query += " ORDER BY event_date, code_dept, source, metric_name"
        
        # Execute query
        try:
            conn = await asyncpg.connect(self.config.db_url)
            records = await conn.fetch(query, start_date, end_date)
            await conn.close()
        except Exception as e:
            raise ValueError(f"Failed to load data from database: {e}")
        
        if not records:
            warnings.warn("No data found for specified criteria")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Pivot to get metrics as columns
        # Combine source and metric_name for unique column names
        df['metric_key'] = df['source'] + '_' + df['metric_name']
        
        # Create pivot table
        pivot_df = df.pivot_table(
            index=['event_date', 'code_dept'],
            columns='metric_key',
            values='metric_value',
            aggfunc='mean'  # Average if multiple values per day
        )
        
        # Clean column names (remove prefix if consistent)
        pivot_df.columns.name = None
        
        # Forward fill within each territory to handle missing days
        pivot_df = pivot_df.groupby(level=1).fillna(method='ffill')
        
        # Cache the raw data
        self._raw_data = pivot_df
        
        return pivot_df
    
    def _group_by_month(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Group daily data by month for temporal analysis.
        
        Args:
            df: DataFrame with daily data
            
        Returns:
            DataFrame grouped by month
        """
        if not isinstance(df.index, pd.MultiIndex):
            return df
        
        # Extract date and territory levels
        df_reset = df.reset_index()
        df_reset['year_month'] = pd.to_datetime(df_reset['event_date']).dt.to_period('M')
        
        # Group by month and territory, aggregate with mean
        monthly_df = df_reset.groupby(['year_month', 'code_dept']).mean(numeric_only=True)
        
        # Convert period back to datetime for consistency
        monthly_df = monthly_df.reset_index()
        monthly_df['year_month'] = monthly_df['year_month'].dt.start_time
        monthly_df = monthly_df.set_index(['year_month', 'code_dept'])
        
        return monthly_df
    
    def generate_alpha_features(self, 
                               data: pd.DataFrame,
                               expressions: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Generate alpha features from raw data using expressions.
        
        Args:
            data: Input DataFrame with raw metrics
            expressions: List of expression names to compute
            
        Returns:
            DataFrame with computed alpha features
        """
        if expressions is None:
            # Use compatible expressions based on available data
            available_metrics = [col.split('_', 1)[-1] for col in data.columns]
            expressions = get_compatible_expressions(available_metrics)
        
        if not expressions:
            warnings.warn("No compatible expressions found for available data")
            return pd.DataFrame(index=data.index)
        
        # Prepare data for expression evaluation
        # Normalize column names for expression matching
        eval_data = data.copy()
        
        # Map column names to expression variables (remove source prefix)
        column_mapping = {}
        for col in data.columns:
            if '_' in col:
                source, metric = col.split('_', 1)
                column_mapping[metric] = col
        
        # Create evaluation DataFrame with standardized column names
        for metric, original_col in column_mapping.items():
            eval_data[metric] = data[original_col]
        
        # Evaluate expressions
        alpha_features = pd.DataFrame(index=data.index)
        
        for expr_name in expressions:
            if expr_name in ALPHA_EXPRESSIONS:
                try:
                    expression = ALPHA_EXPRESSIONS[expr_name]
                    result = evaluate_expression(expression, eval_data)
                    alpha_features[expr_name] = result
                except Exception as e:
                    warnings.warn(f"Failed to evaluate expression '{expr_name}': {e}")
            else:
                warnings.warn(f"Unknown expression: {expr_name}")
        
        return alpha_features
    
    async def prepare_dataset(self, 
                             data_key: str = "infer",
                             features: Optional[List[str]] = None,
                             alpha_expressions: Optional[List[str]] = None,
                             labels: Optional[pd.DataFrame] = None) -> TerritorialDataset:
        """
        Prepare a complete dataset with features and optional labels.
        
        Args:
            data_key: Type of data preparation ("raw", "infer", "learn")
            features: Specific raw features to include
            alpha_expressions: Alpha expressions to compute
            labels: Optional labels DataFrame
            
        Returns:
            TerritorialDataset ready for ML
        """
        # Load raw data if not cached
        if self._raw_data is None:
            await self.load_raw_data()
        
        if self._raw_data.empty:
            raise ValueError("No raw data available")
        
        # Group by month for temporal analysis
        monthly_data = self._group_by_month(self._raw_data)
        
        # Select raw features
        if features:
            available_features = [f for f in features if f in monthly_data.columns]
            if not available_features:
                raise ValueError("None of the specified features are available")
            feature_data = monthly_data[available_features]
        else:
            feature_data = monthly_data
        
        # Generate alpha features
        if alpha_expressions or self.config.alpha_expressions:
            expressions = alpha_expressions or self.config.alpha_expressions
            alpha_features = self.generate_alpha_features(monthly_data, expressions)
            
            # Combine raw features and alpha features
            if not feature_data.empty and not alpha_features.empty:
                combined_features = pd.concat([feature_data, alpha_features], axis=1)
            elif not alpha_features.empty:
                combined_features = alpha_features
            else:
                combined_features = feature_data
        else:
            combined_features = feature_data
        
        # Apply processing pipeline based on data_key
        if data_key == "raw":
            processed_data = combined_features
        elif data_key == "infer":
            if self.config.infer_processors is not None:
                processed_data = self.config.infer_processors.transform(combined_features)
            else:
                # Default inference processing
                from .processor import create_inference_chain
                population = await self._load_population_data()
                processor = create_inference_chain(population)
                processed_data = processor.fit_transform(combined_features)
        elif data_key == "learn":
            if self.config.learn_processors is not None:
                processed_data = self.config.learn_processors.transform(combined_features)
            else:
                # Default learning processing
                from .processor import create_standard_chain
                population = await self._load_population_data()
                processor = create_standard_chain(population, robust=True)
                processed_data = processor.fit_transform(combined_features)
        else:
            raise ValueError(f"Unknown data_key: {data_key}")
        
        # Create dataset
        metadata = {
            'data_key': data_key,
            'territories': self.config.territories,
            'date_range': (self.config.start_date, self.config.end_date),
            'raw_features': list(feature_data.columns) if not feature_data.empty else [],
            'alpha_expressions': alpha_expressions or [],
            'processing': str(type(self.config.infer_processors if data_key == "infer" else self.config.learn_processors))
        }
        
        return TerritorialDataset(processed_data, labels, metadata)
    
    async def get_latest_signals(self, n_periods: int = 3) -> TerritorialDataset:
        """
        Get the latest n periods of processed signals.
        
        Args:
            n_periods: Number of latest periods to return
            
        Returns:
            TerritorialDataset with latest signals
        """
        dataset = await self.prepare_dataset(data_key="infer")
        return dataset.get_latest_data(n_periods)
    
    def create_labels(self, 
                     target_metric: str,
                     prediction_horizon: int = 6,
                     threshold_method: str = "quantile",
                     threshold_value: float = 0.8) -> pd.DataFrame:
        """
        Create labels for supervised learning.
        
        Args:
            target_metric: Metric to predict
            prediction_horizon: Months ahead to predict
            threshold_method: Method for creating binary labels ("quantile", "zscore", "absolute")
            threshold_value: Threshold value for the method
            
        Returns:
            DataFrame with binary labels
        """
        if self._raw_data is None or self._raw_data.empty:
            raise ValueError("No raw data available for label creation")
        
        monthly_data = self._group_by_month(self._raw_data)
        
        if target_metric not in monthly_data.columns:
            available_metrics = list(monthly_data.columns)
            raise ValueError(f"Target metric '{target_metric}' not found. Available: {available_metrics}")
        
        target_series = monthly_data[target_metric]
        
        # Create future values (shift backward to get future values)
        if isinstance(target_series.index, pd.MultiIndex):
            future_values = target_series.groupby(level=1).shift(-prediction_horizon)
        else:
            future_values = target_series.shift(-prediction_horizon)
        
        # Calculate change
        change = (future_values - target_series) / (target_series.abs() + 1e-6)
        
        # Create binary labels based on threshold method
        if threshold_method == "quantile":
            threshold = change.quantile(threshold_value)
            labels = (change >= threshold).astype(int)
        elif threshold_method == "zscore":
            zscore = (change - change.mean()) / change.std()
            labels = (zscore >= threshold_value).astype(int)
        elif threshold_method == "absolute":
            labels = (change >= threshold_value).astype(int)
        else:
            raise ValueError(f"Unknown threshold method: {threshold_method}")
        
        # Create DataFrame
        label_df = pd.DataFrame({
            f"{target_metric}_future_{prediction_horizon}m": labels
        })
        
        # Remove rows with NaN (at the end due to shift)
        label_df = label_df.dropna()
        
        return label_df
    
    async def detect_anomalies(self, 
                              method: str = "isolation_forest",
                              contamination: float = 0.1) -> pd.DataFrame:
        """
        Detect anomalies in the latest data.
        
        Args:
            method: Anomaly detection method
            contamination: Expected proportion of outliers
            
        Returns:
            DataFrame with anomaly scores and binary flags
        """
        dataset = await self.prepare_dataset(data_key="infer")
        latest_dataset = dataset.get_latest_data(1)
        
        X, _ = latest_dataset.to_numpy()
        
        if method == "isolation_forest":
            from sklearn.ensemble import IsolationForest
            detector = IsolationForest(contamination=contamination, random_state=42)
            anomaly_labels = detector.fit_predict(X)
            anomaly_scores = detector.score_samples(X)
        elif method == "local_outlier_factor":
            from sklearn.neighbors import LocalOutlierFactor
            detector = LocalOutlierFactor(contamination=contamination)
            anomaly_labels = detector.fit_predict(X)
            anomaly_scores = detector.negative_outlier_factor_
        else:
            raise ValueError(f"Unknown anomaly detection method: {method}")
        
        # Create results DataFrame
        results = pd.DataFrame({
            'anomaly_score': anomaly_scores,
            'is_anomaly': (anomaly_labels == -1).astype(int),
            'territory': latest_dataset.territories * len(latest_dataset.dates) if latest_dataset.dates else latest_dataset.territories
        }, index=latest_dataset.features.index)
        
        return results
    
    def get_feature_importance(self, 
                              target_metric: str,
                              prediction_horizon: int = 6,
                              method: str = "random_forest") -> pd.DataFrame:
        """
        Calculate feature importance for predicting a target metric.
        
        Args:
            target_metric: Target metric name
            prediction_horizon: Prediction horizon in months
            method: Method for feature importance calculation
            
        Returns:
            DataFrame with feature importances
        """
        # This would require implementing a full ML pipeline
        # For now, return a placeholder
        warnings.warn("Feature importance calculation not yet implemented")
        return pd.DataFrame()
    
    async def export_data(self, 
                         filepath: str,
                         data_key: str = "infer",
                         format: str = "csv",
                         **kwargs) -> None:
        """
        Export processed data to file.
        
        Args:
            filepath: Output file path
            data_key: Type of data to export
            format: Output format ("csv", "parquet")
            **kwargs: Additional arguments for export
        """
        dataset = await self.prepare_dataset(data_key=data_key)
        
        if format == "csv":
            dataset.export_to_csv(filepath, **kwargs)
        elif format == "parquet":
            dataset.export_to_parquet(filepath, **kwargs)
        else:
            raise ValueError(f"Unknown export format: {format}")
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the data handler configuration.
        
        Returns:
            Dictionary with handler information
        """
        return {
            'db_url': '***',  # Hide connection string
            'territories': self.config.territories,
            'date_range': (self.config.start_date, self.config.end_date),
            'raw_features': self.config.raw_features,
            'alpha_expressions': self.config.alpha_expressions,
            'has_raw_data': self._raw_data is not None,
            'raw_data_shape': self._raw_data.shape if self._raw_data is not None else None,
            'population_data_available': len(self._population_data) > 0
        }
    
    def __repr__(self) -> str:
        info = self.get_info()
        return (
            f"TerritorialDataHandler(\n"
            f"  territories: {len(info['territories'])} departments\n"
            f"  date_range: {info['date_range']}\n"
            f"  raw_data: {info['raw_data_shape']}\n"
            f"  expressions: {len(info['alpha_expressions'] or [])}\n"
            f")"
        )