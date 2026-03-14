"""GPU commands for Tawiza CLI v2 pro."""

import re
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli.v2.ui.components import MessageBox, StatusBar
from src.cli.v2.ui.spinners import ProgressBar, create_spinner
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()


def _run_cmd(cmd: list, timeout: int = 10) -> tuple:
    """Run command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def _get_gpu_info() -> dict:
    """Get comprehensive GPU information."""
    info = {
        "detected": False,
        "driver": None,
        "passthrough": False,
        "gpus": [],
    }

    # Check if amdgpu module is loaded
    ok, out, _ = _run_cmd(["lsmod"])
    if ok:
        if "amdgpu" in out:
            info["driver"] = "amdgpu"
            info["detected"] = True
        elif "vfio_pci" in out:
            info["driver"] = "vfio-pci"
            info["passthrough"] = True

    # Get GPU list from lspci
    ok, out, _ = _run_cmd(["lspci", "-nn"])
    if ok:
        for line in out.split("\n"):
            if "VGA" in line or "3D controller" in line or "Display" in line:
                # Parse: 03:00.0 VGA compatible controller [0300]: AMD... [1002:744c]
                match = re.match(r"(\S+)\s+(.+?)\s+\[(\w+)\]:\s+(.+)\s+\[(\w+):(\w+)\]", line)
                if match:
                    info["gpus"].append(
                        {
                            "pci_addr": match.group(1),
                            "type": match.group(2),
                            "class": match.group(3),
                            "name": match.group(4),
                            "vendor_id": match.group(5),
                            "device_id": match.group(6),
                        }
                    )

    return info


def _get_rocm_stats() -> dict:
    """Get ROCm GPU statistics."""
    stats = {
        "available": False,
        "gpu_use": 0,
        "memory_use": 0,
        "memory_total": 0,
        "memory_used": 0,
        "temperature": 0,
        "power": 0,
        "fan": 0,
    }

    # Check GPU utilization
    ok, out, _ = _run_cmd(["rocm-smi", "--showuse", "--csv"])
    if ok and "GPU" in out:
        stats["available"] = True
        lines = out.strip().split("\n")
        if len(lines) > 1:
            # Parse CSV: device,GPU use (%),GFX Activity,Memory Activity
            try:
                values = lines[1].split(",")
                stats["gpu_use"] = int(float(values[1].replace("%", "").strip()))
            except (IndexError, ValueError):
                pass

    # Check memory
    ok, out, _ = _run_cmd(["rocm-smi", "--showmeminfo", "vram", "--csv"])
    if ok:
        lines = out.strip().split("\n")
        if len(lines) > 1:
            try:
                # Parse memory info
                for line in lines[1:]:
                    if "VRAM Total" in line:
                        stats["memory_total"] = int(line.split(",")[-1].strip()) // (1024**2)
                    elif "VRAM Used" in line:
                        stats["memory_used"] = int(line.split(",")[-1].strip()) // (1024**2)
            except (IndexError, ValueError):
                pass

    if stats["memory_total"] > 0:
        stats["memory_use"] = int((stats["memory_used"] / stats["memory_total"]) * 100)

    # Check temperature
    ok, out, _ = _run_cmd(["rocm-smi", "--showtemp", "--csv"])
    if ok:
        lines = out.strip().split("\n")
        if len(lines) > 1:
            try:
                # Get edge temperature
                for line in lines[1:]:
                    if "edge" in line.lower() or "Temperature" in line:
                        temp_val = re.search(r"(\d+\.?\d*)", line.split(",")[-1])
                        if temp_val:
                            stats["temperature"] = int(float(temp_val.group(1)))
                            break
            except (IndexError, ValueError):
                pass

    # Check power
    ok, out, _ = _run_cmd(["rocm-smi", "--showpower", "--csv"])
    if ok:
        lines = out.strip().split("\n")
        if len(lines) > 1:
            try:
                power_val = re.search(r"(\d+\.?\d*)", lines[1])
                if power_val:
                    stats["power"] = int(float(power_val.group(1)))
            except (IndexError, ValueError):
                pass

    # Check fan
    ok, out, _ = _run_cmd(["rocm-smi", "--showfan", "--csv"])
    if ok:
        lines = out.strip().split("\n")
        if len(lines) > 1:
            try:
                fan_val = re.search(r"(\d+)", lines[1].split(",")[-1])
                if fan_val:
                    stats["fan"] = int(fan_val.group(1))
            except (IndexError, ValueError):
                pass

    return stats


def _get_iommu_groups() -> dict:
    """Get IOMMU groups for passthrough."""
    groups = {}
    iommu_path = Path("/sys/kernel/iommu_groups")

    if not iommu_path.exists():
        return groups

    for group_dir in sorted(iommu_path.iterdir(), key=lambda x: int(x.name)):
        group_id = int(group_dir.name)
        devices = []

        devices_path = group_dir / "devices"
        if devices_path.exists():
            for device in devices_path.iterdir():
                # Get device info from lspci
                pci_addr = device.name
                ok, out, _ = _run_cmd(["lspci", "-nns", pci_addr])
                if ok:
                    devices.append(
                        {
                            "pci_addr": pci_addr,
                            "info": out.strip(),
                        }
                    )

        if devices:
            groups[group_id] = devices

    return groups


def _check_vfio_config() -> dict:
    """Check VFIO passthrough configuration."""
    config = {
        "iommu_enabled": False,
        "vfio_loaded": False,
        "cmdline_ok": False,
        "modprobe_ok": False,
    }

    # Check kernel cmdline for IOMMU
    try:
        cmdline = Path("/proc/cmdline").read_text()
        if "iommu=on" in cmdline or "amd_iommu=on" in cmdline or "intel_iommu=on" in cmdline:
            config["iommu_enabled"] = True
            config["cmdline_ok"] = True
    except Exception:
        pass

    # Check if vfio modules are loaded
    ok, out, _ = _run_cmd(["lsmod"])
    if ok and "vfio" in out:
        config["vfio_loaded"] = True

    # Check modprobe config
    vfio_conf = Path("/etc/modprobe.d/vfio.conf")
    if vfio_conf.exists():
        config["modprobe_ok"] = True

    return config


def register(app: typer.Typer) -> None:
    """Register GPU commands."""

    @app.command("gpu-info")
    def gpu_info(
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info"),
    ):
        """Show comprehensive GPU information."""
        console.print(header("gpu info", 40))

        info = _get_gpu_info()
        stats = _get_rocm_stats()

        if not info["gpus"]:
            msg = MessageBox()
            console.print(msg.warning("No GPU detected"))
            console.print(footer(40))
            return

        # GPU list
        for i, gpu in enumerate(info["gpus"]):
            console.print(f"  [bold]GPU {i}:[/] {gpu['name']}")
            console.print(f"    PCI: {gpu['pci_addr']}")
            console.print(f"    ID:  {gpu['vendor_id']}:{gpu['device_id']}")

        console.print()

        # Driver status
        bar = StatusBar()
        if info["passthrough"]:
            bar.add("Driver", "vfio-pci (passthrough)", "warn")
        elif info["driver"]:
            bar.add("Driver", info["driver"], "ok")
        else:
            bar.add("Driver", "not loaded", "err")

        # ROCm stats if available
        if stats["available"]:
            bar.add("ROCm", "available", "ok")
            console.print(bar.render())
            console.print()

            # Progress bars for metrics
            progress = ProgressBar(width=20)

            console.print("  [bold]Utilization:[/]")
            console.print(
                f"    GPU:  {progress.render(stats['gpu_use'] / 100)} {stats['gpu_use']}%"
            )
            console.print(
                f"    VRAM: {progress.render(stats['memory_use'] / 100)} {stats['memory_used']}MB / {stats['memory_total']}MB"
            )
            console.print()

            console.print("  [bold]Thermals:[/]")
            temp_color = (
                "green"
                if stats["temperature"] < 70
                else "yellow"
                if stats["temperature"] < 85
                else "red"
            )
            console.print(f"    Temp:  [{temp_color}]{stats['temperature']}°C[/]")
            console.print(f"    Power: {stats['power']}W")
            console.print(f"    Fan:   {stats['fan']}%")
        else:
            if info["passthrough"]:
                bar.add("ROCm", "GPU in passthrough mode", "warn")
            else:
                bar.add("ROCm", "not available", "err")
            console.print(bar.render())

        if verbose:
            console.print()
            console.print("  [bold]IOMMU Groups:[/]")
            groups = _get_iommu_groups()
            gpu_groups = []
            for gid, devices in groups.items():
                for dev in devices:
                    if "VGA" in dev["info"] or "3D" in dev["info"]:
                        gpu_groups.append((gid, dev))

            for gid, dev in gpu_groups:
                console.print(f"    Group {gid}: {dev['pci_addr']}")

        console.print(footer(40))

    @app.command("gpu-benchmark")
    def gpu_benchmark(
        quick: bool = typer.Option(False, "--quick", "-q", help="Quick benchmark"),
        iterations: int = typer.Option(100, "--iterations", "-n", help="Number of iterations"),
    ):
        """Run GPU benchmark."""
        console.print(header("gpu benchmark", 40))

        info = _get_gpu_info()
        if info["passthrough"]:
            msg = MessageBox()
            console.print(
                msg.warning("GPU in passthrough mode", "Run benchmark inside the VM with the GPU")
            )
            console.print(footer(40))
            return

        stats = _get_rocm_stats()
        if not stats["available"]:
            msg = MessageBox()
            console.print(
                msg.error(
                    "ROCm not available",
                    ["Ensure AMD GPU driver is loaded", "Check with: rocm-smi"],
                )
            )
            console.print(footer(40))
            return

        console.print("  [bold]GPU Benchmark[/]")
        console.print()

        if quick:
            pass

        results = {}

        # Memory bandwidth test using rocm-bandwidth-test if available
        with create_spinner("Testing memory bandwidth...", "dots"):
            ok, out, _ = _run_cmd(["rocm-bandwidth-test", "-t", "1"], timeout=30)
            if ok:
                # Parse bandwidth results
                for line in out.split("\n"):
                    if "Bandwidth" in line:
                        match = re.search(r"(\d+\.?\d*)\s*(GB/s|MB/s)", line)
                        if match:
                            results["memory_bandwidth"] = f"{match.group(1)} {match.group(2)}"
                            break

        if "memory_bandwidth" not in results:
            results["memory_bandwidth"] = "N/A (rocm-bandwidth-test not available)"

        # Simple compute test using rocminfo
        with create_spinner("Getting compute info...", "dots"):
            ok, out, _ = _run_cmd(["rocminfo"])
            if ok:
                for line in out.split("\n"):
                    if "Compute Unit" in line:
                        match = re.search(r"(\d+)", line)
                        if match:
                            results["compute_units"] = match.group(1)
                            break
                    if "Max Clock" in line:
                        match = re.search(r"(\d+)", line)
                        if match:
                            results["max_clock"] = f"{match.group(1)} MHz"

        # PyTorch benchmark if available
        with create_spinner("Testing PyTorch (if available)...", "dots"):
            pytorch_test = """
import torch
import time
if torch.cuda.is_available() or hasattr(torch, 'hip'):
    device = 'cuda' if torch.cuda.is_available() else 'hip'
    # Matrix multiplication benchmark
    size = 4096
    a = torch.randn(size, size, device=device)
    b = torch.randn(size, size, device=device)

    # Warmup
    for _ in range(3):
        c = torch.matmul(a, b)
    torch.cuda.synchronize() if torch.cuda.is_available() else None

    # Benchmark
    start = time.time()
    for _ in range(10):
        c = torch.matmul(a, b)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    elapsed = time.time() - start

    tflops = (2 * size**3 * 10) / (elapsed * 1e12)
    print(f"TFLOPS:{tflops:.2f}")
else:
    print("NO_GPU")
"""
            ok, out, _ = _run_cmd(["python3", "-c", pytorch_test], timeout=60)
            if ok and "TFLOPS:" in out:
                tflops = out.split("TFLOPS:")[1].strip()
                results["pytorch_tflops"] = f"{tflops} TFLOPS"
            elif "NO_GPU" in out:
                results["pytorch_tflops"] = "N/A (no GPU in PyTorch)"
            else:
                results["pytorch_tflops"] = "N/A (PyTorch not available)"

        # Display results
        console.print("  [bold]Results:[/]")
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="bold")
        table.add_column("Value")

        table.add_row("Memory Bandwidth", results.get("memory_bandwidth", "N/A"))
        table.add_row("Compute Units", results.get("compute_units", "N/A"))
        table.add_row("Max Clock", results.get("max_clock", "N/A"))
        table.add_row("PyTorch Perf", results.get("pytorch_tflops", "N/A"))

        console.print(table)

        console.print()
        msg = MessageBox()
        console.print(msg.success("Benchmark complete"))
        console.print(footer(40))

    @app.command("gpu-passthrough-status")
    def gpu_passthrough_status():
        """Show GPU passthrough configuration status."""
        console.print(header("gpu passthrough", 40))

        config = _check_vfio_config()
        info = _get_gpu_info()

        bar = StatusBar()

        # IOMMU status
        if config["iommu_enabled"]:
            bar.add("IOMMU", "enabled", "ok")
        else:
            bar.add("IOMMU", "disabled", "err")

        # VFIO modules
        if config["vfio_loaded"]:
            bar.add("VFIO", "loaded", "ok")
        else:
            bar.add("VFIO", "not loaded", "warn")

        # Modprobe config
        if config["modprobe_ok"]:
            bar.add("Modprobe", "configured", "ok")
        else:
            bar.add("Modprobe", "not configured", "warn")

        console.print(bar.render())
        console.print()

        # GPU status
        console.print("  [bold]GPU Status:[/]")
        for gpu in info["gpus"]:
            driver = "vfio-pci" if info["passthrough"] else info["driver"] or "none"
            status = "passthrough" if info["passthrough"] else "host"
            color = "yellow" if info["passthrough"] else "green"
            console.print(f"    {gpu['pci_addr']}: [{color}]{status}[/] ({driver})")

        console.print()

        # IOMMU Groups with GPUs
        console.print("  [bold]IOMMU Groups (GPUs only):[/]")
        groups = _get_iommu_groups()

        for gid, devices in sorted(groups.items()):
            gpu_devices = [
                d
                for d in devices
                if "VGA" in d["info"] or "3D" in d["info"] or "Audio" in d["info"]
            ]
            if gpu_devices:
                console.print(f"    [cyan]Group {gid}:[/]")
                for dev in gpu_devices:
                    console.print(f"      {dev['info'][:60]}...")

        console.print(footer(40))

    @app.command("gpu-passthrough-enable")
    def gpu_passthrough_enable(
        pci_addr: str = typer.Argument(..., help="PCI address (e.g., 03:00.0)"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    ):
        """Enable GPU passthrough (bind to vfio-pci)."""
        console.print(header("enable passthrough", 40))

        # Verify GPU exists
        info = _get_gpu_info()
        gpu = None
        for g in info["gpus"]:
            if g["pci_addr"] == pci_addr or pci_addr in g["pci_addr"]:
                gpu = g
                break

        if not gpu:
            msg = MessageBox()
            console.print(
                msg.error(f"GPU not found: {pci_addr}", ["Check with: tawiza pro gpu-info"])
            )
            console.print(footer(40))
            return

        console.print(f"  [bold]GPU:[/] {gpu['name']}")
        console.print(f"  [bold]PCI:[/] {gpu['pci_addr']}")
        console.print(f"  [bold]IDs:[/] {gpu['vendor_id']}:{gpu['device_id']}")
        console.print()

        if not force:
            from rich.prompt import Confirm

            if not Confirm.ask("  Enable passthrough for this GPU?"):
                console.print("  [dim]Cancelled.[/]")
                console.print(footer(40))
                return

        # Create vfio.conf
        vfio_conf = Path("/etc/modprobe.d/vfio.conf")
        device_ids = f"{gpu['vendor_id']}:{gpu['device_id']}"

        # Also get audio device if in same IOMMU group
        groups = _get_iommu_groups()
        for _gid, devices in groups.items():
            for dev in devices:
                if gpu["pci_addr"] in dev["info"]:
                    for other_dev in devices:
                        if "Audio" in other_dev["info"]:
                            # Extract audio device ID
                            match = re.search(r"\[(\w+):(\w+)\]", other_dev["info"])
                            if match:
                                device_ids += f",{match.group(1)}:{match.group(2)}"

        config_content = f"""# GPU Passthrough configuration
# Generated by tawiza
options vfio-pci ids={device_ids}
softdep amdgpu pre: vfio-pci
"""

        console.print("  [bold]Configuration:[/]")
        console.print(f"    File: {vfio_conf}")
        console.print(f"    IDs: {device_ids}")
        console.print()

        try:
            vfio_conf.write_text(config_content)

            # Update initramfs
            with create_spinner("Updating initramfs...", "dots"):
                ok, _, err = _run_cmd(["update-initramfs", "-u"], timeout=120)

            if ok:
                msg = MessageBox()
                console.print(msg.success("Passthrough enabled!", "Reboot to apply changes"))
            else:
                msg = MessageBox()
                console.print(
                    msg.warning(
                        "Config saved, initramfs update failed", "Run manually: update-initramfs -u"
                    )
                )

        except PermissionError:
            msg = MessageBox()
            console.print(msg.error("Permission denied", ["Run with sudo or as root"]))
        except Exception as e:
            msg = MessageBox()
            console.print(msg.error(str(e)))

        console.print(footer(40))

    @app.command("gpu-passthrough-disable")
    def gpu_passthrough_disable(
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    ):
        """Disable GPU passthrough (use host driver)."""
        console.print(header("disable passthrough", 40))

        vfio_conf = Path("/etc/modprobe.d/vfio.conf")

        if not vfio_conf.exists():
            msg = MessageBox()
            console.print(msg.info("Passthrough not configured"))
            console.print(footer(40))
            return

        console.print(f"  [bold]Config file:[/] {vfio_conf}")
        console.print()

        if not force:
            from rich.prompt import Confirm

            if not Confirm.ask("  Disable GPU passthrough?"):
                console.print("  [dim]Cancelled.[/]")
                console.print(footer(40))
                return

        try:
            # Backup and remove config
            backup = vfio_conf.with_suffix(".conf.bak")
            vfio_conf.rename(backup)
            console.print(f"  [dim]Backup: {backup}[/]")

            # Update initramfs
            with create_spinner("Updating initramfs...", "dots"):
                ok, _, _ = _run_cmd(["update-initramfs", "-u"], timeout=120)

            if ok:
                msg = MessageBox()
                console.print(msg.success("Passthrough disabled!", "Reboot to use GPU on host"))
            else:
                msg = MessageBox()
                console.print(
                    msg.warning(
                        "Config removed, initramfs update failed",
                        "Run manually: update-initramfs -u",
                    )
                )

        except PermissionError:
            msg = MessageBox()
            console.print(msg.error("Permission denied", ["Run with sudo or as root"]))
        except Exception as e:
            msg = MessageBox()
            console.print(msg.error(str(e)))

        console.print(footer(40))

    @app.command("gpu-vm-list")
    def gpu_vm_list():
        """List VMs with GPU passthrough configured."""
        console.print(header("gpu vms", 40))

        # Check if we're on Proxmox
        if not Path("/etc/pve").exists():
            msg = MessageBox()
            console.print(msg.warning("Not a Proxmox host"))
            console.print(footer(40))
            return

        # Get VM configs
        vms_with_gpu = []
        qemu_configs = Path("/etc/pve/qemu-server")

        if qemu_configs.exists():
            for conf_file in qemu_configs.glob("*.conf"):
                vmid = conf_file.stem
                try:
                    content = conf_file.read_text()
                    # Look for hostpci entries
                    for line in content.split("\n"):
                        if line.startswith("hostpci"):
                            # Get VM name
                            name = "unknown"
                            for l in content.split("\n"):
                                if l.startswith("name:"):
                                    name = l.split(":")[1].strip()
                                    break

                            vms_with_gpu.append(
                                {
                                    "vmid": vmid,
                                    "name": name,
                                    "hostpci": line,
                                }
                            )
                except Exception:
                    pass

        if not vms_with_gpu:
            console.print("  [dim]No VMs with GPU passthrough found.[/]")
        else:
            table = Table(show_header=True, header_style=f"bold {THEME['accent']}")
            table.add_column("VMID")
            table.add_column("Name")
            table.add_column("GPU Config")

            for vm in vms_with_gpu:
                # Parse hostpci line
                pci_info = (
                    vm["hostpci"].split(":")[1].strip() if ":" in vm["hostpci"] else vm["hostpci"]
                )
                table.add_row(vm["vmid"], vm["name"], pci_info[:30])

            console.print(table)

        console.print(footer(40))
