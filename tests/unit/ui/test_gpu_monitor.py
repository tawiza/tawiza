# tests/unit/ui/test_gpu_monitor.py
from unittest.mock import Mock, patch

import pytest

from src.cli.ui.gpu_monitor import GPULocation, GPUMonitor, GPUStatus, get_gpu_status


def test_gpu_status_creation():
    status = GPUStatus(
        available=True,
        location=GPULocation.VM,
        name="AMD RX 7900 XTX",
        memory_used=4096,
        memory_total=24576,
        utilization=45.5,
    )
    assert status.memory_percent == pytest.approx(16.67, rel=0.1)


def test_gpu_not_available():
    status = GPUStatus(available=False, location=GPULocation.NONE)
    assert status.available == False
    assert status.memory_percent == 0


def test_gpu_status_zero_memory():
    """Test memory_percent when total is 0."""
    status = GPUStatus(
        available=True,
        memory_used=0,
        memory_total=0,
    )
    assert status.memory_percent == 0.0


def test_gpu_monitor_initialization():
    """Test GPU monitor can be initialized with custom settings."""
    monitor = GPUMonitor(vm_host="localhost", vm_user="testuser")
    assert monitor.vm_host == "localhost"
    assert monitor.vm_user == "testuser"


def test_gpu_monitor_parse_rocm_output():
    """Test parsing ROCm output."""
    monitor = GPUMonitor()
    rocm_output = """
GPU[0]        : GPU use (%): 45%
GPU[0]        : Memory Used (MB): 4096 / 24576 MB
GPU[0]        : Temperature (c): 65.0c
"""
    status = monitor._parse_rocm_output(rocm_output)
    assert status is not None
    assert status.available == True
    assert status.memory_used == 4096
    assert status.memory_total == 24576
    assert status.temperature == 65
    assert status.utilization == 45.0


def test_gpu_monitor_parse_invalid_output():
    """Test parsing invalid ROCm output returns status with zeros."""
    monitor = GPUMonitor()
    status = monitor._parse_rocm_output("")
    # Parser returns a status but with zero values when parsing fails gracefully
    assert status is not None
    assert status.available == True  # Still marked as available
    assert status.memory_total == 0  # But no data parsed


@patch("subprocess.run")
def test_check_host_gpu_success(mock_run):
    """Test successful host GPU detection."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "GPU[0]: 2048 / 24576 MB"
    mock_run.return_value = mock_result

    monitor = GPUMonitor()
    status = monitor.check_host_gpu()

    assert status is not None
    assert status.available == True
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_check_host_gpu_not_found(mock_run):
    """Test when no GPU found on host."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = "No GPU found"
    mock_run.return_value = mock_result

    monitor = GPUMonitor()
    status = monitor.check_host_gpu()

    assert status is None


@patch("subprocess.run")
def test_get_status_host_priority(mock_run):
    """Test that host is checked before VM."""
    # Mock successful host GPU
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "GPU[0]: 2048 / 24576 MB"
    mock_run.return_value = mock_result

    monitor = GPUMonitor()
    status = monitor.get_status()

    assert status.available == True
    assert status.location == GPULocation.HOST


def test_get_gpu_status_helper():
    """Test the helper function."""
    status = get_gpu_status()
    assert isinstance(status, GPUStatus)
    assert isinstance(status.location, GPULocation)
