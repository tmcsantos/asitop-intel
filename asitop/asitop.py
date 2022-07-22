import argparse
import time
from collections import deque

from dashing import HChart, HGauge, HSplit, VGauge, VSplit

from .utils import (clear_console, get_ram_metrics_dict, get_soc_info,
                    parse_powermetrics, run_powermetrics_process)

parser = argparse.ArgumentParser(
    description='asitop: Performance monitoring CLI tool for Intel Macs')
parser.add_argument(
    '--interval',
    type=int,
    default=1,
    help='Display interval and sampling interval for powermetrics (seconds)')
parser.add_argument('--color',
                    type=int,
                    default=2,
                    help='Choose display color (0~8)')
parser.add_argument('--avg',
                    type=int,
                    default=30,
                    help='Interval for averaged values (seconds)')
args = parser.parse_args()


def main():
    print("\nASITOP - Performance monitoring CLI tool for Intel Macs")
    print("You can update ASITOP by running `pip install asitop --upgrade`")
    # print("Get help at `https://github.com/tlkh/asitop`")
    print("P.S. You are recommended to run ASITOP with `sudo asitop`\n")
    print("\n[1/3] Loading ASITOP\n")
    print("\033[?25l")

    cpu_gauge = HGauge(title="CPU Usage", val=0, color=args.color)
    gpu_gauge = HGauge(title="GPU Usage", val=0, color=args.color)

    soc_info_dict = get_soc_info()
    core_count = soc_info_dict["core_count"]

    core_gauges = [
        VGauge(val=0, color=args.color, border_color=args.color)
        for _ in range(min(core_count, 8))
    ]
    core_split = [HSplit(*core_gauges, )]
    if core_count > 8:
        core_gauges_ext = [
            VGauge(val=0, color=args.color, border_color=args.color)
            for _ in range(core_count - 8)
        ]
        core_split.append(HSplit(*core_gauges_ext, ))
    processor_gauges = [HSplit(cpu_gauge), HSplit(gpu_gauge)]
    processor_split = VSplit(
        *processor_gauges,
        title="Processor Utilization",
        border_color=args.color,
    )

    ram_gauge = HGauge(title="RAM Usage", val=0, color=args.color)
    memory_gauges = VSplit(ram_gauge, border_color=args.color, title="Memory")

    cpu_power_chart = HChart(title="CPU Power", color=args.color)
    power_charts = HSplit(
        cpu_power_chart,
        title="Power Chart",
        border_color=args.color,
    )

    ui = VSplit(
        processor_split,
        memory_gauges,
        power_charts,
    )

    usage_gauges = ui.items[0]

    cpu_title = "".join([
        soc_info_dict["name"], " (cores: ",
        str(soc_info_dict["core_count"]), "+",
        str(soc_info_dict["gpu_core_count"]), "GPU)"
    ])
    usage_gauges.title = cpu_title
    cpu_max_power = soc_info_dict["cpu_max_power"]

    cpu_peak_power = 0
    package_peak_power = 0

    print("\n[2/3] Starting powermetrics process\n")

    powermetrics_process = run_powermetrics_process(interval=args.interval *
                                                    1000)

    print("\n[3/3] Waiting for first reading...\n")

    ready = parse_powermetrics(powermetrics_process)
    last_timestamp = ready[-1]

    def get_avg(inlist):
        avg = sum(inlist) / len(inlist)
        return avg

    avg_package_power_list = deque([], maxlen=int(args.avg / args.interval))
    avg_cpu_power_list = deque([], maxlen=int(args.avg / args.interval))

    clear_console()

    try:
        while True:
            (cpu_metrics_dict, gpu_metrics_dict, thermal_pressure,
             timestamp) = parse_powermetrics(powermetrics_process)

            if timestamp > last_timestamp:
                last_timestamp = timestamp

                if thermal_pressure == "Nominal":
                    thermal_throttle = "no"
                else:
                    thermal_throttle = "yes"

                cpu_gauge.title = "".join([
                    "CPU Usage: ",
                    str(cpu_metrics_dict["usage"]), "% @ ",
                    str(cpu_metrics_dict["freq_hz"]), " MHz"
                ])
                cpu_gauge.value = cpu_metrics_dict["usage"]

                gpu_gauge.title = "".join([
                    "GPU Usage: ",
                    str(gpu_metrics_dict["active"]), "% @ ",
                    str(gpu_metrics_dict["freq_MHz"]), " MHz"
                ])
                gpu_gauge.value = gpu_metrics_dict["active"]

                ram_metrics_dict = get_ram_metrics_dict()

                if ram_metrics_dict["swap_total_GB"] < 0.1:
                    ram_gauge.title = "".join([
                        "RAM Usage: ",
                        str(ram_metrics_dict["used_GB"]), "/",
                        str(ram_metrics_dict["total_GB"]), "GB - swap inactive"
                    ])
                else:
                    ram_gauge.title = "".join([
                        "RAM Usage: ",
                        str(ram_metrics_dict["used_GB"]), "/",
                        str(ram_metrics_dict["total_GB"]), "GB", " - swap:",
                        str(ram_metrics_dict["swap_used_GB"]), "/",
                        str(ram_metrics_dict["swap_total_GB"]), "GB"
                    ])
                ram_gauge.value = ram_metrics_dict["free_percent"]

                package_power_W = cpu_metrics_dict["package_W"] / args.interval
                if package_power_W > package_peak_power:
                    package_peak_power = package_power_W
                avg_package_power_list.append(package_power_W)
                avg_package_power = get_avg(avg_package_power_list)
                power_charts.title = "".join([
                    "Package Power: ",
                    '{0:.2f}'.format(package_power_W),
                    "W (avg: ",
                    '{0:.2f}'.format(avg_package_power),
                    "W peak: ",
                    '{0:.2f}'.format(package_peak_power),
                    "W) throttle: ",
                    thermal_throttle,
                ])

                cpu_power_percent = int(cpu_metrics_dict["package_W"] /
                                        args.interval / cpu_max_power * 100)
                cpu_power_W = cpu_metrics_dict["package_W"] / args.interval
                if cpu_power_W > cpu_peak_power:
                    cpu_peak_power = cpu_power_W
                avg_cpu_power_list.append(cpu_power_W)
                avg_cpu_power = get_avg(avg_cpu_power_list)
                cpu_power_chart.title = "".join([
                    "CPU: ", '{0:.2f}'.format(cpu_power_W), "W (avg: ",
                    '{0:.2f}'.format(avg_cpu_power), "W peak: ",
                    '{0:.2f}'.format(cpu_peak_power), "W)"
                ])
                cpu_power_chart.append(cpu_power_percent)

                ui.display()

            time.sleep(args.interval)

    except KeyboardInterrupt:
        powermetrics_process.stdout.close()

    return powermetrics_process


if __name__ == "__main__":
    powermetrics_process = main()
    try:
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
    except Exception as e:
        print(e)
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
