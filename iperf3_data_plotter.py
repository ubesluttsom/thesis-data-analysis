import os
import json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches

matplotlib.style.use("seaborn-v0_8")
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Libertinus Serif"]

LOG_DIR = "logs"
CONG_NAMES = {
    "reno": "Reno",
    "cubic": "CUBIC",
    "lgcc": "LGCC",
}

if __name__ == "__main__":
    # Get a list of all JSON files in LOG_DIR
    json_files = []
    for entry in os.listdir(LOG_DIR):
        if os.path.isfile(full_path := os.path.join(LOG_DIR, entry)):
            split_path = os.path.splitext(entry)
            if split_path[1].lower() == ".json":
                basename = Path(split_path[0]).with_suffix("").name
                metadata = basename.split("_")
                with open(full_path, "r") as file:
                    data = json.load(file)
                    data.update(
                        {
                            "path": full_path,
                            "basename": basename,
                            "program": metadata[0],
                            "cong": metadata[1],
                            "host": metadata[-1],
                        }
                    )
                json_files.append(data)

    # Create DataFrames for all iperf3 files
    data_frames = []
    for log in json_files:
        start_date = log["start"]["timestamp"]["timesecs"]
        df = pd.DataFrame(
            [i["streams"][0] for i in log["intervals"]]
        )  # Assuming 1 stream!
        df["datetime"] = pd.to_datetime(start_date + df["start"], unit="s")
        df["program"] = log["program"]
        df["congestion_control"] = log["cong"]
        df["host"] = log["host"]
        df["time"] = df["datetime"].dt.floor("1s")
        data_frames.append(df)

    # Make giant DataFrame
    df = pd.concat(data_frames)

    # Calculate relative time, starting from 0 for each congestion control
    # group. Assuming each congestion control group is tested concurently.
    df["relative_time"] = df.groupby("congestion_control")["time"].transform(
        lambda x: (x - x.min()).dt.total_seconds()
    )

    # PLOTTING

    # Unique hosts and congestion controls
    hosts = df["host"].unique()
    congestion_controls = df["congestion_control"].unique()
    sender_or_reciever = df["sender"].unique()

    # Adjust figure rows, columns, size, and aspect ratio
    fig, axes = plt.subplots(
        nrows=len(sender_or_reciever),
        ncols=len(congestion_controls),
        figsize=(len(congestion_controls) * 4, len(sender_or_reciever) * 2),
        sharey="row",
        sharex="col",
    )

    # Ensure axes is 2D
    axes = np.atleast_2d(axes)

    # Create consistent colors
    unique_hosts = df["host"].unique()
    n = max(2, len(unique_hosts))
    colors = dict(
        zip(unique_hosts, [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)])
    )

    # Plot data
    for i, sender in enumerate(sender_or_reciever):
        for j, cong in enumerate(congestion_controls):
            ax = axes[i, j]
            data = df[(df["sender"] == sender) & (df["congestion_control"] == cong)]
            if data.empty:
                ax.set_visible(False)
                continue

            for host in data["host"].unique():
                data_host = data[data["host"] == host]
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

            # Convert y-axis to Mbps
            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda x, _: f"{x / 1e6:.0f}")
            )

            # ax.relim()
            ax.autoscale()
            # ax.autoscale_view()

            if i == 0:
                ax.set_title(CONG_NAMES[cong], fontstyle='italic')
            if j == len(congestion_controls) - 1:
                ax.annotate(
                    f"{'Sender' if sender else 'Reciever'}",
                    xy=(1.01, 0.5),
                    xycoords="axes fraction",
                    rotation=270,
                    ha="left",
                    va="center",
                    fontstyle='italic',
                )

            # Add a single legend
            if i == 0 and j == 0:
                handles = [
                    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=colors[host], markersize=10)
                    for host in data["host"].unique()
                ]
                labels = data["host"].unique().tolist()
                handles.append(plt.Line2D([0], [0], color="black"))
                labels.append("1 second mean")
                handles.append(mpatches.Patch(color="black", alpha=0.2))
                labels.append("Min/max range")
                fig.legend(
                    handles,
                    labels,
                    loc="upper center",
                    ncol=len(labels),
                    bbox_to_anchor=(0.5, 1),
                )

    fig.supxlabel("Time (s)", fontstyle='italic')
    fig.supylabel("Mbit per second", x=0.0, fontstyle='italic')
    fig.suptitle("Network rate, sender and reciever", y=1.05, fontweight='bold')

    plt.tight_layout()
    plt.savefig("matplotlib_iperf3.pdf", bbox_inches="tight")
