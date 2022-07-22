import functools
import logging
import os
import plistlib
import subprocess
from subprocess import PIPE

import psutil

from .parsers import (parse_cpu_metrics, parse_gpu_metrics,
                      parse_thermal_pressure)

logger = logging.getLogger(__name__)


def parse_powermetrics(process):
    """
    Fetch entry from process
    """
    data = b''
    write = False
    try:
        for line in process.stdout:
            if b'<?xml' in line:
                if write:  # we have hit a new batch
                    break
                data += line.replace(b'\x00', b'')
                write = True
                continue
            if write:
                data += line
        powermetrics_parse = plistlib.loads(data)
        thermal_pressure = parse_thermal_pressure(powermetrics_parse)
        cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
        cpu_metrics_dict["usage"] = psutil.cpu_percent()
        gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
        timestamp = powermetrics_parse["timestamp"]
        return (cpu_metrics_dict, gpu_metrics_dict, thermal_pressure,
                timestamp)
    except Exception as err:
        logger.error(err)
        process.stdout.close()
        raise


def clear_console():
    command = 'clear'
    os.system(command)


def convert_to_GB(value):
    return round(value / 1024 / 1024 / 1024, 1)


def run_powermetrics_process(nice=10, interval=1000):
    command = " ".join([
        "sudo nice -n",
        str(nice), "powermetrics", "--samplers cpu_power,gpu_power,thermal",
        "-f plist", "-i",
        str(interval)
    ])
    process = subprocess.Popen(command.split(" "), stdin=PIPE, stdout=PIPE)
    return process


def get_ram_metrics_dict():
    ram_metrics = psutil.virtual_memory()
    swap_metrics = psutil.swap_memory()
    total_GB = convert_to_GB(ram_metrics.total)
    free_GB = convert_to_GB(ram_metrics.available)
    used_GB = convert_to_GB(ram_metrics.total - ram_metrics.available)
    swap_total_GB = convert_to_GB(swap_metrics.total)
    swap_used_GB = convert_to_GB(swap_metrics.used)
    swap_free_GB = convert_to_GB(swap_metrics.total - swap_metrics.used)
    if swap_total_GB > 0:
        swap_free_percent = int(100 - (swap_free_GB / swap_total_GB * 100))
    else:
        swap_free_percent = None
    ram_metrics_dict = {
        "total_GB":
        round(total_GB, 1),
        "free_GB":
        round(free_GB, 1),
        "used_GB":
        round(used_GB, 1),
        "free_percent":
        int(100 - (ram_metrics.available / ram_metrics.total * 100)),
        "swap_total_GB":
        swap_total_GB,
        "swap_used_GB":
        swap_used_GB,
        "swap_free_GB":
        swap_free_GB,
        "swap_free_percent":
        swap_free_percent,
    }
    return ram_metrics_dict


@functools.lru_cache()
def _get_cpu_info():
    cmd = 'command sysctl -a | command grep -E "^machdep.cpu|^hw"'
    cpu_info_lines = os.popen(cmd).read().splitlines()
    return dict(
        map(
            lambda l: next(
                (k, v.strip()) for k, v in [l.split(":", maxsplit=1)]),
            cpu_info_lines))


def get_soc_info():
    cpu_info = _get_cpu_info()
    performance_core_count = int(cpu_info.get("hw.perflevel0.logicalcpu", 0))
    soc_info = {
        "name": cpu_info["machdep.cpu.brand_string"],
        "core_count": int(cpu_info["machdep.cpu.core_count"]),
        "cpu_max_power": 20,
        "gpu_max_power": 20,
        "cpu_count": performance_core_count,
        "gpu_core_count": 1,
    }
    return soc_info
