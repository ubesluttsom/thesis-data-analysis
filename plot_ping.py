import re
from pathlib import Path

import pandas as pd
import numpy as np

import matplotlib as mpl
import matplotlib.pyplot as plt

from utils import get_logs_by_timestamp, pipe_or_save

# Set the style and fonts to match your existing script
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


def process_ping_logs(logs):
    data_frames = []
    for full_path, metadata in logs:
        basename = Path(full_path).stem
        if len(metadata) >= 4:
            # Assuming filename is 'YYYYMMDDHHMMSS_ping_congestion_control_host.log'
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

        # Read and parse the ping log file
        with open(full_path, "r") as f:
            lines = f.readlines()

        # Initialize lists to collect data
        seq_list = []
        time_list = []
        rtt_list = []
        for line in lines:
            line = line.strip()
            if "bytes from" in line:
                # Use regex to extract seq and time
                match = re.search(r"seq=(\d+).*time=([\d.]+) ms", line)
                if match:
                    seq = int(match.group(1))
                    rtt = float(match.group(2))
                    seq_list.append(seq)
                    # Calculate the time for this packet
                    time_offset = pd.Timedelta(seconds=seq * 0.1)  # Interval is 0.1s
                    packet_time = pd.to_datetime(0) + time_offset
                    time_list.append(packet_time)
                    rtt_list.append(rtt)

        # Create DataFrame
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

    # Concatenate all data frames
    if data_frames:
        df = pd.concat(data_frames, ignore_index=True)
        # You can now work with 'df' as needed
        return df
    else:
        print("No data frames to process.")
        exit(1)


def main():
    logs = get_logs_by_timestamp(ext=".log", log_dir="logs")
    logs = logs[max(logs)]
    df = process_ping_logs(logs)

    # Convert 'time' to datetime if not already
    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"])

    # Sort by time
    df.sort_values("time", inplace=True)

    # Calculate relative time for each congestion control group
    df["relative_time"] = df.groupby("congestion_control")["time"].transform(
        lambda x: (x - x.min()).dt.total_seconds()
    )

    # Map congestion control names
    df["cong_name"] = (
        df["congestion_control"].map(CONG_NAMES).fillna(df["congestion_control"])
    )

    # Exclude 'vm1' from the DataFrame if needed
    df = df[df["host"] != "vm1"]

    # PLOTTING

    # Get unique hosts and congestion_controls
    host_groups = df["host"].unique()
    congestion_controls = df["congestion_control"].unique()

    # Adjust figure rows, columns, size, and aspect ratio
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

    # Create consistent colors for each host
    unique_hosts = df["host"].unique()
    n = max(2, len(unique_hosts))
    colors = dict(
        zip(unique_hosts, [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)])
    )

    # Loop through each subplot
    for i, host in enumerate(host_groups):
        for j, congestion_control in enumerate(congestion_controls):
            ax = axes[i, j]
            data = df[
                (df["host"] == host) & (df["congestion_control"] == congestion_control)
            ]
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

            # Plot mean RTT as a solid line
            ax.plot(
                resampled["relative_time"],
                resampled["mean"],
                color=colors[host],
                alpha=0.9,
                label=HOSTNAMES.get(host, host),
            )

            # Fill between min and max RTT to show variability
            ax.fill_between(
                resampled["relative_time"],
                resampled["min"],
                resampled["max"],
                color=colors[host],
                alpha=0.3,
            )

            # Set axis limits and labels
            ax.autoscale()

            if i == 0:
                ax.set_title(
                    CONG_NAMES.get(congestion_control, congestion_control),
                    fontstyle="italic",
                )
            if j == len(congestion_controls) - 1:
                ax.annotate(
                    f"{HOSTNAMES.get(host, host)}",
                    xy=(1.01, 0.5),
                    xycoords="axes fraction",
                    rotation=270,
                    ha="left",
                    va="center",
                    fontstyle="italic",
                )

    # Add legend
    handles = [plt.Line2D([0], [0], color=colors[host], lw=2) for host in unique_hosts]
    labels = [HOSTNAMES.get(host, host) for host in unique_hosts]
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=len(labels),
        bbox_to_anchor=(0.5, 1),
    )

    fig.supxlabel("Time (s)", fontstyle="italic")
    fig.supylabel("RTT (ms)", x=0, fontstyle="italic")
    fig.suptitle("Ping RTT over Time", y=1.05, fontweight="bold")

    plt.tight_layout()
    pipe_or_save("ping")


if __name__ == "__main__":
    main()
