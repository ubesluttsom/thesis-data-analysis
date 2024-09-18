import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib as mpl

# mpl.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

mpl.style.use('seaborn-v0_8')
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Libertinus Serif']

LOG_DIR = "logs"
HOSTNAMES = {
    "10.0.1.101": "vm1",
    "10.0.2.101": "vm2",
    "10.0.3.101": "vm3",
    "10.0.4.101": "vm4",
}
CONG_NAMES = {
    "reno": "Reno",
    "cubic": "CUBIC",
    "lgcc": "LGCC",
}

if __name__ == "__main__":
    # Get a list of all `ss` CSV files in LOG_DIR
    data_frames = []
    for entry in os.listdir(LOG_DIR):
        if os.path.isfile(full_path := os.path.join(LOG_DIR, entry)):
            split_path = os.path.splitext(entry)
            if split_path[1].lower() == ".log":
                basename = Path(split_path[0]).with_suffix("").name
                metadata = basename.split("_")
                with open(full_path, "r") as file:
                    data = pd.read_csv(file)
                    data["path"] = full_path
                    data["basename"] = basename
                    data["program"] = metadata[0]
                    data["congestion_control"] = metadata[1]
                    data["host"] = metadata[-1]
                data_frames.append(data)

    # Make giant DataFrame
    df = pd.concat(data_frames)

    # Exclude 'vm1' from the DataFrame
    df = df[df["host"] != "vm1"]

    # Convert to datetime and sort by it
    df["datetime"] = pd.to_datetime(df["time"])
    df["time"] = df["datetime"].dt.floor("1s")
    df.sort_values("time", inplace=True)

    # Split IPs and ports, strip whitespace, coerce to ints
    df[["src_ip", "src_port"]] = df["source"].str.strip().str.split(":", expand=True)
    df[["dst_ip", "dst_port"]] = (
        df["destination"].str.strip().str.split(":", expand=True)
    )
    df[["src_port", "dst_port"]] = df[["src_port", "dst_port"]].apply(
        pd.to_numeric, errors="coerce"
    )

    # Remove port 22 data
    df = df[(df["src_port"] != 22) & (df["dst_port"] != 22)]

    # Replace IPs with hostnames
    df["src_hostname"] = df["src_ip"].map(HOSTNAMES)
    df["dst_hostname"] = df["dst_ip"].map(HOSTNAMES)

    # Exclude rows where 'vm1' is the src
    df = df[df["src_hostname"] != "vm1"]

    # Create a new column 'src_dest_pair'
    df["src_dest"] = df["src_hostname"] + "–" + df["dst_hostname"]

    # Calculate relative time, starting from 0 for each congestion control
    # group. Assuming each congestion control group is tested concurently.
    df["relative_time"] = df.groupby("congestion_control")["time"].transform(
        lambda x: (x - x.min()).dt.total_seconds()
    )

    # PLOTTING

    # Create the 'host_group' column
    df["host_group"] = df["host"].map(
        {
            "vm2": "VM2, VM3, VM4",
            "vm3": "VM2, VM3, VM4",
            "vm4": "VM2, VM3, VM4",
            "router1": "Router",
        }
    )

    # Drop rows where 'host_group' is NaN
    df = df.dropna(subset=["host_group"])

    # Get unique host_groups and congestion_controls
    host_groups = df["host_group"].unique()
    congestion_controls = df["congestion_control"].unique()

    # Adjust figure rows, columns, size and aspect ratio
    fig, axes = plt.subplots(
        nrows=len(host_groups),
        ncols=len(congestion_controls),
        figsize=(len(congestion_controls) * 4, len(host_groups) * 2),
        sharey="row",
        sharex="col",
    )

    # Ensure axes is 2D
    axes = np.atleast_2d(axes)

    # Create consistent colors
    unique_src_dest = df["src_dest"].unique()
    n = max(2, len(unique_src_dest))
    colors = dict(zip(unique_src_dest, [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)]))

    # Loop through each subplot
    for i, host_group in enumerate(host_groups):
        for j, congestion_control in enumerate(congestion_controls):
            ax = axes[i, j]
            data = df[
                (df["host_group"] == host_group)
                & (df["congestion_control"] == congestion_control)
            ]
            unique_src_dest = data["src_dest"].unique()
            if data.empty:
                ax.set_visible(False)
                continue

            # Group and plot data
            for src_dest in unique_src_dest:
                data_src = data[data["src_dest"] == src_dest]
                grouped = (
                    data_src.groupby("relative_time")["cwnd"]
                    .agg(["mean", "min", "max"])
                    .reset_index()
                )
                ax.plot(
                    grouped["relative_time"],
                    grouped["mean"],
                    color=colors[src_dest],
                )
                ax.fill_between(
                    grouped["relative_time"],
                    grouped["min"],
                    grouped["max"],
                    color=colors[src_dest],
                    alpha=0.2,
                )

            # Set axis limits and labels
            # ax.set_ylim(bottom=0)
            # ax.relim()
            ax.autoscale()
            # ax.autoscale_view()

            if i == 0:
                ax.set_title(CONG_NAMES[congestion_control], fontstyle='italic')
            if j == len(congestion_controls) - 1:
                ax.annotate(
                    f"{host_group}",
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
                    for host in unique_src_dest
                ]
                labels = unique_src_dest.tolist()
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
    fig.supylabel("cwnd", x=0, fontstyle='italic')
    fig.suptitle("Congestion window (cwnd)", y=1.05, fontweight='bold')

    plt.tight_layout()
    plt.savefig("matplotlib_ss.pdf", bbox_inches="tight")
