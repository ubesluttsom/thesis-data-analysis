from pathlib import Path

import pandas as pd
import numpy as np

import matplotlib as mpl
import matplotlib.pyplot as plt

from utils import get_logs_by_timestamp, pipe_or_save

mpl.style.use("seaborn-v0_8")
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Libertinus Serif"]

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
    "lgc": "LGC",
    "lgcc": "LGCC",
    "dctcp": "DCTCP",
    "bbr": "BBR",
}


def process_ss_logs(logs):
    data_frames = []
    for full_path, metadata in logs:
        basename = Path(full_path).stem
        if len(metadata) >= 4:
            # Assuming filename is 'YYYYMMDDHHMMSS_program_congestion_control_host.log'
            program = metadata[1]
            congestion_control = metadata[2]
            host = metadata[3]
        elif len(metadata) == 3:
            program = metadata[1]
            congestion_control = metadata[2]
            host = "unknown"
        else:
            program = "ss"
            congestion_control = "unknown"
            host = "unknown"

        # Read and parse the ss log file
        try:
            data = pd.read_csv(full_path)
            data["path"] = full_path
            data["basename"] = basename
            data["program"] = program
            data["congestion_control"] = congestion_control
            data["host"] = host
            data_frames.append(data)
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            continue

    # Concatenate all data frames
    if data_frames:
        df = pd.concat(data_frames, ignore_index=True)
        return df
    else:
        print("No data frames to process.")
        exit(1)


def main():
    logs = get_logs_by_timestamp(ext=".log")
    logs = logs[max(logs)]
    df = process_ss_logs(logs)

    # Exclude 'vm1' from the DataFrame
    df = df[df["host"] != "vm1"]

    # Convert to datetime and sort by it
    df["datetime"] = pd.to_datetime(df["time"])
    df["time"] = df["datetime"]  # .dt.floor("1s")   # disable 1s bin for now
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

    # Create a unique identifier for each flow
    df["flow_id"] = (
        df["src_hostname"]
        + ":"
        + df["src_port"].astype(str)
        + "->"
        + df["dst_hostname"]
        + ":"
        + df["dst_port"].astype(str)
    )

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
        squeeze=False,
    )

    # Ensure axes is 2D
    axes = np.atleast_2d(axes)

    # Create consistent colors for each src_dest pair
    unique_src_dest = df["src_dest"].dropna().unique()
    n = max(2, len(unique_src_dest))
    colors = dict(
        zip(unique_src_dest, [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)])
    )

    # Loop through each subplot
    for i, host_group in enumerate(host_groups):
        for j, congestion_control in enumerate(congestion_controls):
            ax = axes[i, j]
            data = df[
                (df["host_group"] == host_group)
                & (df["congestion_control"] == congestion_control)
            ]
            unique_src_dest = data["src_dest"].dropna().unique()

            if data.empty:
                ax.set_visible(False)
                continue

            # Group and plot data
            for src_dest in unique_src_dest:
                data_src_dest = data[data["src_dest"] == src_dest]
                flows = data_src_dest["flow_id"].unique()
                for flow_id in flows:
                    data_flow = data_src_dest[data_src_dest["flow_id"] == flow_id]
                    ax.plot(
                        data_flow["relative_time"],
                        data_flow["cwnd"],
                        color=colors[src_dest],
                        alpha=0.5,  # Use transparency to differentiate flows
                        # Optionally add labels to individual flows
                    )

            # Set axis limits and labels
            ax.autoscale()

            if i == 0:
                ax.set_title(CONG_NAMES[congestion_control], fontstyle="italic")
            if j == len(congestion_controls) - 1:
                ax.annotate(
                    f"{host_group}",
                    xy=(1.01, 0.5),
                    xycoords="axes fraction",
                    rotation=270,
                    ha="left",
                    va="center",
                    fontstyle="italic",
                )

            # Add a factorized legend
            if i == 0 and j == 0:
                # Legend entries for src_dest colors
                src_dest_handles = [
                    plt.Line2D([0], [0], color=colors[src_dest], lw=2)
                    for src_dest in unique_src_dest
                ]
                src_dest_labels = unique_src_dest.tolist()
                # Generic handle for individual flows
                # flow_handle = plt.Line2D([0], [0], color='k', lw=2, alpha=0.5)
                # flow_label = 'Individual flows'
                # Combine handles and labels
                handles = src_dest_handles  # + [flow_handle]
                labels = src_dest_labels  # + [flow_label]
                fig.legend(
                    handles,
                    labels,
                    loc="upper center",
                    ncol=len(labels),
                    bbox_to_anchor=(0.5, 1),
                )

    fig.supxlabel("Time (s)", fontstyle="italic")
    fig.supylabel("cwnd", x=0, fontstyle="italic")
    fig.suptitle("Congestion window (cwnd)", y=1.05, fontweight="bold")

    plt.tight_layout()

    pipe_or_save("ss")

    return df


if __name__ == "__main__":
    main()
