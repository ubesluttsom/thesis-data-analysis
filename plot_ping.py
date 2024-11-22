import re
from pathlib import Path

import pandas as pd
import numpy as np

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from utils import get_logs_by_timestamp, pipe_or_save, parse_timestamp_arg

mpl.style.use("seaborn-v0_8")
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Libertinus Serif"]

HOSTNAMES = {
    "10.0.1.101": "vm1",
    "10.0.2.101": "vm2",
    "10.0.3.101": "vm3",
    "10.0.4.101": "vm4",
}

CONG_NAMES = {
    "bbr": "BBR",
    "cubic": "CUBIC",
    "dctcp": "DCTCP",
    "lgc": "LGC",
    "lgcc": "LGCC",
    "reno": "Reno",
}


def process_ping_logs(logs):
    data_frames = []
    for full_path, metadata in logs:
        basename = Path(full_path).stem
        if len(metadata) >= 4:
            program = metadata[1]
            congestion_control = metadata[2]
            host = metadata[3]
        elif len(metadata) == 3:
            program = metadata[1]
            congestion_control = metadata[2]
            host = "unknown"
        else:
            program = "ping"
            congestion_control = "unknown"
            host = "unknown"

        with open(full_path, "r") as f:
            lines = f.readlines()

        seq_list = []
        time_list = []
        rtt_list = []
        for line in lines:
            line = line.strip()
            if "bytes from" in line:
                match = re.search(r"seq=(\d+).*time=([\d.]+) ms", line)
                if match:
                    seq = int(match.group(1))
                    rtt = float(match.group(2))
                    seq_list.append(seq)
                    time_offset = pd.Timedelta(seconds=seq * 0.1)
                    packet_time = pd.to_datetime(0) + time_offset
                    time_list.append(packet_time)
                    rtt_list.append(rtt)

        data = pd.DataFrame(
            {
                "seq": seq_list,
                "time": time_list,
                "rtt": rtt_list,
            }
        )
        data["path"] = full_path
        data["basename"] = basename
        data["program"] = program
        data["congestion_control"] = congestion_control
        data["host"] = host
        data_frames.append(data)

    if data_frames:
        return pd.concat(data_frames, ignore_index=True)
    else:
        print("No data frames to process.")
        exit(1)


def main():
    timestamp = parse_timestamp_arg()
    logs = get_logs_by_timestamp(ext=".log", target_timestamp=timestamp)
    logs = logs[max(logs)]
    df = process_ping_logs(logs)

    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"])

    df.sort_values("time", inplace=True)

    df["relative_time"] = df.groupby("congestion_control")["time"].transform(
        lambda x: (x - x.min()).dt.total_seconds()
    )

    df["cong_name"] = (
        df["congestion_control"].map(CONG_NAMES).fillna(df["congestion_control"])
    )

    # Exclude 'vm1' from the DataFrame
    df = df[df["host"] != "vm1"]

    # PLOTTING
    hosts = sorted(df["host"].unique())
    congestion_controls = sorted(df["congestion_control"].unique())

    fig, axes = plt.subplots(
        nrows=len(congestion_controls),
        ncols=len(hosts),
        figsize=(8, len(congestion_controls) * 2),
        sharey="row",
        sharex=True,
        squeeze=False,
    )

    # Create consistent colors
    n = max(2, len(hosts))
    colors = dict(zip(hosts, [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)]))

    # Plot data with sorted congestion controls
    for i, cong in enumerate(congestion_controls):
        for j, host in enumerate(hosts):
            ax = axes[i, j]
            data = df[(df["host"] == host) & (df["congestion_control"] == cong)]
            if data.empty:
                ax.set_visible(False)
                continue

            # Resample data into 1-second bins
            data.set_index("relative_time", inplace=True)
            resampled = (
                data["rtt"].groupby(np.floor(data.index)).agg(["mean", "min", "max"])
            )
            resampled.reset_index(inplace=True)
            resampled.rename(columns={"index": "relative_time"}, inplace=True)

            # Plot mean RTT
            ax.plot(
                resampled["relative_time"],
                resampled["mean"],
                color=colors[host],
            )

            # Fill between min and max RTT
            ax.fill_between(
                resampled["relative_time"],
                resampled["min"],
                resampled["max"],
                color=colors[host],
                alpha=0.2,
            )

            ax.autoscale()

            if j == 0:
                ax.set_ylabel(CONG_NAMES[cong], fontstyle="italic")
            if i == 0:
                ax.set_title(HOSTNAMES.get(host, host), fontstyle="italic")

    legend_elements = []

    for host in hosts:
        # Add mean line
        legend_elements.append(
            plt.Line2D(
                [],
                [],
                color=colors[host],
                label=f"{HOSTNAMES.get(host, host)} mean (1s)",
            )
        )
        # Add range patch
        legend_elements.append(
            mpatches.Patch(
                color=colors[host],
                alpha=0.2,
                label=f"{HOSTNAMES.get(host, host)} min/max range (1s)",
            )
        )

    # Place legend at top
    fig.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=len(hosts),
        fontsize="small",
    )

    # Adjust labels and title
    fig.supxlabel("Time (s)", fontstyle="italic")
    fig.supylabel("RTT (ms)", fontstyle="italic")

    # Adjust layout with matching spacing
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)

    pipe_or_save("ping")


if __name__ == "__main__":
    main()
