"""Evidently AI adapter for data drift detection.

This adapter implements IDataDriftDetector using Evidently AI library
for comprehensive data drift analysis and reporting.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from loguru import logger

from src.application.ports.ml_ports import IDataDriftDetector

if TYPE_CHECKING:
    from evidently import ColumnMapping

try:
    from evidently import ColumnMapping
    from evidently.metric_preset import DataDriftPreset, DataQualityPreset
    from evidently.metrics import (
        ColumnDriftMetric,
        DataDriftTable,
        DatasetDriftMetric,
    )
    from evidently.report import Report
    from evidently.test_preset import DataDriftTestPreset
    from evidently.test_suite import TestSuite

    EVIDENTLY_AVAILABLE = True
except ImportError:
    EVIDENTLY_AVAILABLE = False
    ColumnMapping = type("ColumnMapping", (), {})  # Dummy type stub when not installed
    logger.warning(
        "Evidently not installed. Install with: pip install evidently"
    )


class EvidentlyAdapter(IDataDriftDetector):
    """Adapter for Evidently AI data drift detection.

    Provides data drift detection, quality checks, and report generation
    using the Evidently library.

    Attributes:
        column_mapping: Optional column mapping for feature types
        drift_share_threshold: Threshold for dataset-level drift detection
    """

    def __init__(
        self,
        column_mapping: dict[str, Any] | None = None,
        drift_share_threshold: float = 0.5,
    ):
        """Initialize the Evidently adapter.

        Args:
            column_mapping: Optional mapping of column types
                (numerical, categorical, target, prediction, etc.)
            drift_share_threshold: Threshold for drift share (0-1)
                If more than this fraction of features drift, dataset is drifted
        """
        if not EVIDENTLY_AVAILABLE:
            raise ImportError(
                "Evidently is not installed. "
                "Install with: pip install evidently"
            )

        self._column_mapping = self._create_column_mapping(column_mapping)
        self.drift_share_threshold = drift_share_threshold

        logger.info(
            f"EvidentlyAdapter initialized with drift_share_threshold={drift_share_threshold}"
        )

    def _create_column_mapping(
        self, mapping: dict[str, Any] | None
    ) -> ColumnMapping | None:
        """Create Evidently ColumnMapping from dict."""
        if mapping is None:
            return None

        return ColumnMapping(
            target=mapping.get("target"),
            prediction=mapping.get("prediction"),
            numerical_features=mapping.get("numerical_features"),
            categorical_features=mapping.get("categorical_features"),
            datetime_features=mapping.get("datetime_features"),
            text_features=mapping.get("text_features"),
            embeddings=mapping.get("embeddings"),
        )

    async def check_drift(
        self,
        reference_data_path: str,
        current_data_path: str,
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Check for data drift between reference and current datasets.

        Uses statistical tests (PSI, K-S, Chi-squared) to detect drift
        in individual features and the overall dataset.

        Args:
            reference_data_path: Path to reference (training) dataset
            current_data_path: Path to current (production) dataset
            threshold: Drift detection threshold (0-1)

        Returns:
            Dict containing:
                - is_drifted: Boolean indicating overall drift
                - drift_share: Fraction of features that drifted
                - drifted_features: List of feature names that drifted
                - feature_drift_scores: Dict of feature -> drift score
                - timestamp: Analysis timestamp
                - dataset_info: Info about analyzed datasets
        """
        logger.info(
            f"Checking drift: reference={reference_data_path}, "
            f"current={current_data_path}, threshold={threshold}"
        )

        # Load datasets
        reference_df = self._load_data(reference_data_path)
        current_df = self._load_data(current_data_path)

        logger.debug(
            f"Loaded reference: {len(reference_df)} rows, "
            f"current: {len(current_df)} rows"
        )

        # Create drift report
        report = Report(metrics=[
            DatasetDriftMetric(),
            DataDriftTable(),
        ])

        report.run(
            reference_data=reference_df,
            current_data=current_df,
            column_mapping=self._column_mapping,
        )

        # Extract results
        result = report.as_dict()
        metrics = result.get("metrics", [])

        # Parse dataset drift metric
        dataset_drift = {}
        feature_drift = {}

        for metric in metrics:
            metric_id = metric.get("metric", "")

            if "DatasetDriftMetric" in metric_id:
                dataset_drift = metric.get("result", {})
            elif "DataDriftTable" in metric_id:
                drift_by_columns = metric.get("result", {}).get(
                    "drift_by_columns", {}
                )
                for col_name, col_data in drift_by_columns.items():
                    feature_drift[col_name] = {
                        "drift_detected": col_data.get("drift_detected", False),
                        "drift_score": col_data.get("drift_score", 0.0),
                        "stattest_name": col_data.get("stattest_name", ""),
                        "stattest_threshold": col_data.get(
                            "stattest_threshold", 0.0
                        ),
                    }

        # Determine drifted features
        drifted_features = [
            name for name, data in feature_drift.items()
            if data.get("drift_detected", False)
        ]

        drift_share = dataset_drift.get("share_of_drifted_columns", 0.0)
        is_drifted = drift_share >= threshold

        response = {
            "is_drifted": is_drifted,
            "drift_share": drift_share,
            "number_of_drifted_columns": dataset_drift.get(
                "number_of_drifted_columns", 0
            ),
            "number_of_columns": dataset_drift.get("number_of_columns", 0),
            "drifted_features": drifted_features,
            "feature_drift_scores": {
                name: data.get("drift_score", 0.0)
                for name, data in feature_drift.items()
            },
            "feature_details": feature_drift,
            "threshold": threshold,
            "timestamp": datetime.utcnow().isoformat(),
            "dataset_info": {
                "reference_rows": len(reference_df),
                "current_rows": len(current_df),
                "reference_path": reference_data_path,
                "current_path": current_data_path,
            },
        }

        logger.info(
            f"Drift check complete: is_drifted={is_drifted}, "
            f"drift_share={drift_share:.2%}, "
            f"drifted_features={len(drifted_features)}"
        )

        return response

    async def generate_report(
        self,
        reference_data_path: str,
        current_data_path: str,
        output_path: str,
    ) -> str:
        """Generate a comprehensive drift report.

        Creates an HTML report with visualizations for data drift,
        data quality, and feature distributions.

        Args:
            reference_data_path: Path to reference dataset
            current_data_path: Path to current dataset
            output_path: Path to save the HTML report

        Returns:
            Path to the generated report
        """
        logger.info(
            f"Generating drift report: reference={reference_data_path}, "
            f"current={current_data_path}"
        )

        # Load datasets
        reference_df = self._load_data(reference_data_path)
        current_df = self._load_data(current_data_path)

        # Create comprehensive report
        report = Report(metrics=[
            DataDriftPreset(),
            DataQualityPreset(),
        ])

        report.run(
            reference_data=reference_df,
            current_data=current_df,
            column_mapping=self._column_mapping,
        )

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save HTML report
        report.save_html(str(output_file))

        logger.info(f"Drift report saved to: {output_path}")

        return str(output_file)

    async def run_drift_tests(
        self,
        reference_data_path: str,
        current_data_path: str,
    ) -> dict[str, Any]:
        """Run drift tests and return pass/fail results.

        Uses Evidently's test suite for automated drift testing
        with configurable thresholds.

        Args:
            reference_data_path: Path to reference dataset
            current_data_path: Path to current dataset

        Returns:
            Dict containing:
                - passed: Boolean indicating if all tests passed
                - test_results: List of individual test results
                - summary: Summary statistics
        """
        logger.info("Running drift tests")

        reference_df = self._load_data(reference_data_path)
        current_df = self._load_data(current_data_path)

        # Create test suite
        test_suite = TestSuite(tests=[
            DataDriftTestPreset(),
        ])

        test_suite.run(
            reference_data=reference_df,
            current_data=current_df,
            column_mapping=self._column_mapping,
        )

        result = test_suite.as_dict()
        tests = result.get("tests", [])

        test_results = []
        passed_count = 0
        failed_count = 0

        for test in tests:
            test_name = test.get("name", "")
            test_status = test.get("status", "")
            is_passed = test_status == "SUCCESS"

            if is_passed:
                passed_count += 1
            else:
                failed_count += 1

            test_results.append({
                "name": test_name,
                "status": test_status,
                "passed": is_passed,
                "description": test.get("description", ""),
                "parameters": test.get("parameters", {}),
            })

        all_passed = failed_count == 0

        response = {
            "passed": all_passed,
            "test_results": test_results,
            "summary": {
                "total_tests": len(tests),
                "passed": passed_count,
                "failed": failed_count,
                "pass_rate": (
                    passed_count / len(tests) * 100 if tests else 0
                ),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Drift tests complete: passed={all_passed}, "
            f"{passed_count}/{len(tests)} tests passed"
        )

        return response

    async def check_feature_drift(
        self,
        reference_data_path: str,
        current_data_path: str,
        feature_name: str,
    ) -> dict[str, Any]:
        """Check drift for a specific feature.

        Args:
            reference_data_path: Path to reference dataset
            current_data_path: Path to current dataset
            feature_name: Name of the feature to check

        Returns:
            Dict with feature-specific drift information
        """
        logger.info(f"Checking drift for feature: {feature_name}")

        reference_df = self._load_data(reference_data_path)
        current_df = self._load_data(current_data_path)

        if feature_name not in reference_df.columns:
            raise ValueError(
                f"Feature '{feature_name}' not found in reference data"
            )
        if feature_name not in current_df.columns:
            raise ValueError(
                f"Feature '{feature_name}' not found in current data"
            )

        report = Report(metrics=[
            ColumnDriftMetric(column_name=feature_name),
        ])

        report.run(
            reference_data=reference_df,
            current_data=current_df,
            column_mapping=self._column_mapping,
        )

        result = report.as_dict()
        metrics = result.get("metrics", [])

        if not metrics:
            return {
                "feature_name": feature_name,
                "error": "No metrics generated",
            }

        metric_result = metrics[0].get("result", {})

        return {
            "feature_name": feature_name,
            "drift_detected": metric_result.get("drift_detected", False),
            "drift_score": metric_result.get("drift_score", 0.0),
            "stattest_name": metric_result.get("stattest_name", ""),
            "stattest_threshold": metric_result.get("stattest_threshold", 0.0),
            "current_distribution": metric_result.get(
                "current_distribution", {}
            ),
            "reference_distribution": metric_result.get(
                "reference_distribution", {}
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _load_data(self, path: str) -> pd.DataFrame:
        """Load data from file path.

        Supports CSV, Parquet, and JSON formats.

        Args:
            path: Path to data file

        Returns:
            Loaded DataFrame

        Raises:
            ValueError: If file format is not supported
        """
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        suffix = file_path.suffix.lower()

        if suffix == ".csv":
            return pd.read_csv(path)
        elif suffix == ".parquet":
            return pd.read_parquet(path)
        elif suffix == ".json":
            return pd.read_json(path)
        elif suffix in (".jsonl", ".ndjson"):
            return pd.read_json(path, lines=True)
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                f"Supported: .csv, .parquet, .json, .jsonl"
            )

    async def health_check(self) -> bool:
        """Check if Evidently is properly configured.

        Returns:
            True if healthy
        """
        return EVIDENTLY_AVAILABLE

    def get_supported_tests(self) -> list[str]:
        """Get list of supported drift tests.

        Returns:
            List of test names
        """
        return [
            "DataDriftTest",
            "DataQualityTest",
            "ColumnDriftTest",
            "ShareOfDriftedColumnsTest",
        ]
