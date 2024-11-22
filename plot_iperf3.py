import json
from pathlib import Path

import pandas as pd

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches

from utils import get_logs_by_timestamp, pipe_or_save, parse_timestamp_arg

matplotlib.style.use("seaborn-v0_8")
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Libertinus Serif"]

CONG_NAMES = {
    "bbr": "BBR",
    "cubic": "CUBIC",
    "dctcp": "DCTCP",
    "lgc": "LGC",
    "lgcc": "LGCC",
    "reno": "Reno",
}


def main():
    timestamp = parse_timestamp_arg()
    logs = get_logs_by_timestamp(target_timestamp=timestamp)
    logs = logs[max(logs)]

    json_files = []
    for full_path, metadata in logs:
        with open(full_path, "r") as file:
            try:
                data = json.load(file)
            except json.decoder.JSONDecodeError as e:
                print(e)
                print(f"Malformed JSON. Skipping '{file}'.")
                continue
            data.update(
                {
                    "path": full_path,
                    "basename": Path(full_path).stem,
                    "program": metadata[1],
                    "cong": metadata[2],
                    "host": metadata[-1],
                }
            )
        json_files.append(data)

    data_frames = []
    for log in json_files:
        start_date = log["start"]["timestamp"]["timesecs"]
        df = pd.DataFrame([i["streams"][0] for i in log["intervals"]])
        df["datetime"] = pd.to_datetime(start_date + df["start"], unit="s")
        df["program"] = log["program"]
        df["congestion_control"] = log["cong"]
        df["host"] = log["host"]
        df["time"] = df["datetime"].dt.floor("1s")
        data_frames.append(df)

    df = pd.concat(data_frames)

    df["relative_time"] = df.groupby("congestion_control")["time"].transform(
        lambda x: (x - x.min()).dt.total_seconds()
    )

    # PLOTTING
    hosts = sorted(df["host"].unique())
    congestion_controls = sorted(df["congestion_control"].unique())
    sender_or_receiver = df["sender"].unique()

    fig, axes = plt.subplots(
        nrows=len(congestion_controls),
        ncols=len(sender_or_receiver),
        figsize=(8, len(congestion_controls) * 2),
        sharey=True,
        sharex=True,
        squeeze=False,
    )

    # Create consistent colors
    n = max(2, len(hosts))
    colors = dict(zip(hosts, [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)]))

    # Plot data
    for i, cong in enumerate(congestion_controls):
        for j, sender in enumerate(sender_or_receiver):
            ax = axes[i, j]
            data = df[(df["sender"] == sender) & (df["congestion_control"] == cong)]
            if data.empty:
                ax.set_visible(False)
                continue

            for host in hosts:
                data_host = data[data["host"] == host]
                if data_host.empty:
                    continue

                grouped = (
                    data_host.groupby("relative_time")["bits_per_second"]
                    .agg(["mean", "min", "max"])
                    .reset_index()
                )

                ax.plot(
                    grouped["relative_time"],
                    grouped["mean"],
                    color=colors[host],
                )
                ax.fill_between(
                    grouped["relative_time"],
                    grouped["min"],
                    grouped["max"],
                    color=colors[host],
                    alpha=0.2,
                )

            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda x, _: f"{x / 1e6:.0f}")
            )

            ax.autoscale()

            if j == 0:
                ax.set_ylabel(CONG_NAMES[cong], fontstyle="italic")
            if i == 0:
                ax.set_title(
                    f"{'Sender' if sender else 'Receiver'}", fontstyle="italic"
                )

    # Create legend elements
    legend_elements = []

    # Add both line and patch for each host
    for host in hosts:
        # Add mean line
        legend_elements.append(
            plt.Line2D([], [], color=colors[host], label=f"{host} mean (1s)")
        )
        # Add range patch
        legend_elements.append(
            mpatches.Patch(
                color=colors[host], alpha=0.2, label=f"{host} min/max range (1s)"
            )
        )

    # Place legend at top with good spacing
    fig.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.15),
        ncol=len(hosts),  # Two entries per host
        fontsize="small",
    )

    # Adjust labels and title
    fig.supxlabel("Time (s)", fontstyle="italic")
    fig.supylabel("Mbit per second", fontstyle="italic")

    # Adjust layout with proper spacing
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)

    pipe_or_save("iperf3")


if __name__ == "__main__":
    main()
