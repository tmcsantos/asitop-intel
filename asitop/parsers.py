def parse_thermal_pressure(powermetrics_parse):
    return powermetrics_parse["thermal_pressure"]


def parse_cpu_metrics(powermetrics_parse):
    cpu_metrics = powermetrics_parse.get("processor")
    cpu_metrics_dict = {}
    cpu_metrics_dict["package_W"] = cpu_metrics.get("package_watts")
    cpu_metrics_dict["freq_hz"] = int(cpu_metrics.get("freq_hz") / 1e6)
    cpu_metrics_dict["freq_ratio"] = int(
        cpu_metrics.get("freq_ratio", .0) * 100)

    for package in cpu_metrics.get("packages"):
        for core in package.get("cores"):
            for cpu in core.get("cpus"):
                name = f"C{cpu.get('cpu')}"
                cpu_metrics_dict[name + "_freq_Mhz"] = int(
                    cpu.get("freq_hz") / 1e6)
    return cpu_metrics_dict


def parse_gpu_metrics(powermetrics_parse):
    gpu_metrics = powermetrics_parse.get("GPU")
    for gpu in gpu_metrics:
        return {
            "freq_MHz": int(gpu["freq_hz"] / 1e6),
            "active": int(gpu["freq_ratio"] * 100),
        }
    return {}
