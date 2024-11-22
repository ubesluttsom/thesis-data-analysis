from pathlib import Path
import sys

import pandas as pd

import matplotlib as mpl
import matplotlib.pyplot as plt

from utils import (
    get_logs_by_timestamp,
    pipe_or_save,
    parse_timestamp_arg,
    get_interval_stats,
)


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


def process_ss_logs(logs):
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
            program = "ss"
            congestion_control = "unknown"
            host = "unknown"

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

    if data_frames:
        return pd.concat(data_frames, ignore_index=True)
    else:
        print("No data frames to process.")
        exit(1)


def main():
    timestamp = parse_timestamp_arg()
    logs = get_logs_by_timestamp(ext=".log", target_timestamp=timestamp)
    logs = logs[max(logs)]
    df = process_ss_logs(logs)
    df = df[df["program"] == "ss"]

    # Data preprocessing
    df = df[df["host"] != "vm1"]
    df["datetime"] = pd.to_datetime(df["time"])
    df["time"] = df["datetime"]
    df.sort_values("time", inplace=True)

    # Process source and destination
    df[["src_ip", "src_port"]] = df["source"].str.strip().str.split(":", expand=True)
    df[["dst_ip", "dst_port"]] = (
        df["destination"].str.strip().str.split(":", expand=True)
    )
    df[["src_port", "dst_port"]] = df[["src_port", "dst_port"]].apply(
        pd.to_numeric, errors="coerce"
    )
    df = df[(df["src_port"] != 22) & (df["dst_port"] != 22)]

    # Replace IPs with hostnames
    df["src_hostname"] = df["src_ip"].map(HOSTNAMES)
    df["dst_hostname"] = df["dst_ip"].map(HOSTNAMES)
    df = df[df["src_hostname"] != "vm1"]

    # Create identifiers
    df["src_dest"] = df["src_hostname"] + "-" + df["dst_hostname"]
    df["flow_id"] = (
        df["src_hostname"]
        + ":"
        + df["src_port"].astype(str)
        + "->"
        + df["dst_hostname"]
        + ":"
        + df["dst_port"].astype(str)
    )

    # Calculate relative time
    df["relative_time"] = df.groupby("congestion_control")["time"].transform(
        lambda x: (x - x.min()).dt.total_seconds()
    )

    # Try to filter out iperf3's control flows
    df = filter_control_flows(df)

    # Create host groups
    df["host_group"] = df["host"].map(
        {
            "vm2": "Senders",
            "vm3": "Senders",
            "vm4": "Senders",
            "router1": "Router",
        }
    )
    df = df.dropna(subset=["host_group"])

    # PLOTTING
    host_groups = ["Senders", "Router"]  # Keep explicit order
    congestion_controls = sorted(df["congestion_control"].unique())

    metrics = [
        "cwnd",
        # 'snd_wnd',
    ]

    # Create figure with congestion controls * metrics as rows
    fig, axes = plt.subplots(
        nrows=len(congestion_controls) * len(metrics),
        ncols=len(host_groups),
        figsize=(8, len(congestion_controls) * len(metrics) * 2),
        sharex=True,
        # sharey=True,
        squeeze=False,
    )

    # Create consistent colors for source hosts
    source_hosts = sorted(df["src_hostname"].unique())
    n = max(2, len(source_hosts))
    colors = dict(
        zip(source_hosts, [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)])
    )

    # Plot data
    for i, cong in enumerate(congestion_controls):
        for m, metric in enumerate(metrics):
            row = i * len(metrics) + m  # Calculate the actual row in the figure
            for j, host_group in enumerate(host_groups):
                ax = axes[row, j]
                data = df[
                    (df["host_group"] == host_group)
                    & (df["congestion_control"] == cong)
                ]

                if data.empty:
                    ax.cla()
                else:
                    # Plot each flow, colored by source host
                    for src_host in source_hosts:
                        data_src = data[data["src_hostname"] == src_host]
                        if data_src.empty:
                            continue

                        for flow_id in data_src["flow_id"].unique():
                            flow_data = data_src[data_src["flow_id"] == flow_id]
                            ax.plot(
                                flow_data["relative_time"],
                                flow_data[metric],
                                color=colors[src_host],
                                alpha=0.7,
                            )

                    ax.autoscale()

                # Set labels
                if j == 0:
                    if m == 0:  # First metric (cwnd)
                        ax.set_ylabel(
                            f"{CONG_NAMES[cong]}\n{metric}", fontstyle="italic"
                        )
                    else:  # snd_wnd
                        ax.set_ylabel(f"{metric}", fontstyle="italic")
                if row == 0:  # Only set title on top row
                    ax.set_title(host_group, fontstyle="italic")

    # Create legend elements
    legend_elements = [
        plt.Line2D([], [], color=colors[src_host], label=f"Flows from {src_host}")
        for src_host in source_hosts
    ]

    # Place legend at top
    fig.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=len(source_hosts),
        fontsize="small",
    )

    # Adjust labels and title
    fig.supxlabel("Time (s)", fontstyle="italic")

    # Adjust layout
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)

    pipe_or_save("ss")

    # Print descriptive statistics
    if sys.stdout.isatty():
        time_by_src = df.groupby("src_ip")["relative_time"]
        interval = [time_by_src.min().max(), time_by_src.max().min()]
        print(format_stats_table(df, interval))

    return df


def filter_control_flows(df: pd.DataFrame, cwnd_threshold: int = 20) -> pd.DataFrame:
    """
    Filter out iperf3 control flows by identifying the lower-port flow
    between each IP pair for each congestion control test.
    """
    # Group by source IP, destination IP, and congestion control
    groups = df.groupby(["src_ip", "dst_ip", "congestion_control"])

    # Collect control flows
    control_flows = set()

    for _, group in groups:
        # For each unique connection+CC combo, find flow with lowest port
        flow_with_min_port = group.loc[group["src_port"].idxmin()]

        # If it looks like a control flow (small cwnd), mark it
        if flow_with_min_port["cwnd"] < cwnd_threshold:
            control_flows.add(flow_with_min_port["flow_id"])

    # Keep all non-control flows
    return df[~df["flow_id"].isin(control_flows)]


def format_stats_table(df: pd.DataFrame, time_interval: list) -> str:
    """
    Format statistics table with enhanced LaTeX styling and per-flow statistics.
    Dynamically handles groups based on available data.
    """
    # Get stats
    base_stats = get_interval_stats(
        df,
        "cwnd",
        f"{time_interval[0]} <= relative_time <= {time_interval[1]}",
        ["congestion_control", "host_group"],
    )

    # Get per-source stats
    detailed_stats = get_interval_stats(
        df,
        "cwnd",
        f"{time_interval[0]} <= relative_time <= {time_interval[1]}",
        ["congestion_control", "host_group", "src_hostname"],
    )

    # Create formatted mean values with source summaries
    mean_values = []
    for cc, hg in base_stats.index:
        source_means = []
        try:
            sources_data = detailed_stats.loc[(cc, hg)]
            # Just collect the means without VM labels
            means = sorted([f"{mean:.1f}" for mean in sources_data["mean"]])
            source_means.extend(means)
        except KeyError:
            pass

        base_mean = base_stats.loc[(cc, hg), "mean"]
        summary = f"({', '.join(source_means)})" if source_means else ""
        mean_values.append(f"{base_mean:.2f} {summary}")

    # Create a copy of base_stats with the formatted mean column
    formatted_stats = base_stats.copy()
    formatted_stats["mean"] = mean_values

    # Create the LaTeX table
    latex_rows = []

    # Add header
    latex_rows.extend(
        [
            "\\begin{tabular}{lrrrrr}",
            "\\toprule",
            "& \\textit{Samples} & \\textit{Mean} & \\textit{SD} & \\textit{Min} & \\textit{Max} \\\\",
            "\\midrule",
        ]
    )

    # Group the stats by protocol to check for multiple groups
    grouped_stats = formatted_stats.groupby(level=0)

    # Add data rows
    prev_protocol = None
    for protocol, group in grouped_stats:
        # Check if we need to show group labels
        show_groups = len(group) > 1

        for _, host_group in group.index:
            row = group.loc[(protocol, host_group)]

            # Format the protocol name, adding group label only if needed
            if show_groups:
                protocol_str = f"\\textsc{{{protocol}}} \\textit{{({host_group})}}"
            else:
                protocol_str = f"\\textsc{{{protocol}}}"

            # Format the row data
            row_str = (
                f"{protocol_str} & "
                f"{int(row['count'])} & "
                f"{row['mean']} & "
                f"{row['std']:.2f} & "
                f"{int(row['min'])} & "
                f"{int(row['max'])} \\\\"
            )

            latex_rows.append(row_str)

        # Add a line between different protocols
        if protocol != list(grouped_stats.groups.keys())[-1]:
            latex_rows.append("\\cline{1-6}")

    # Add footer
    latex_rows.extend(["\\bottomrule", "\\end{tabular}"])

    return "\n".join(latex_rows)


if __name__ == "__main__":
    main()
