import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional
import argparse
import pandas as pd
import matplotlib.pyplot as plt


def get_logs_by_timestamp(ext=".json", log_dir="logs", target_timestamp=None):
    logs = {}
    for entry in os.listdir(log_dir):
        if os.path.isfile(full_path := os.path.join(log_dir, entry)):
            split_path = os.path.splitext(entry)
            if split_path[1].lower() == ext:
                basename = Path(split_path[0]).with_suffix("").name
                metadata = basename.split("_")
                try:
                    # Assuming metadata[0] contains the timestamp
                    timestamp = datetime.strptime(metadata[0], "%Y%m%d%H%M%S")
                    if target_timestamp:
                        target_dt = datetime.strptime(target_timestamp, "%Y%m%d%H%M%S")
                        if timestamp != target_dt:
                            continue
                    logs[timestamp] = logs.get(timestamp, []) + [(full_path, metadata)]
                except ValueError:
                    print(f"Error parsing timestamp for file: {basename}")
                    continue
    return logs


def parse_timestamp_arg():
    parser = argparse.ArgumentParser(
        description="Process log files with optional timestamp filter"
    )
    parser.add_argument(
        "-t",
        "--timestamp",
        help="Specific timestamp to filter logs (format: YYYYMMDDHHmmss)",
    )

    args = parser.parse_args()
    return args.timestamp


def pipe_or_save(name):
    # Check if output is being piped
    if sys.stdout.isatty():
        # If not being piped, save as a PDF
        plt.savefig(f"{name}.pdf", bbox_inches="tight")
    else:
        # If being piped, save to stdout as PNG
        buffer = BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight", dpi=300)
        sys.stdout.buffer.write(buffer.getvalue())


def get_interval_stats(
    df: pd.DataFrame,
    value_column: str,
    time_range: str,
    group_columns: Optional[List[str]] = None,
):
    """
    Get descriptive statistics for a specified column within a time interval.

    Args:
        df: DataFrame containing the data
        value_column: Column to analyze (e.g., 'cwnd', 'latency')
        time_range: String like '21 <= relative_time <= 39'
        group_columns: Optional columns to group by
    """
    interval_data = df.query(time_range)

    if interval_data.empty:
        print(f"No data found for interval: {time_range}")
        return pd.DataFrame()

    if group_columns:
        return interval_data.groupby(group_columns)[value_column].describe().round(2)
    return interval_data[value_column].describe().round(2)
