import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt


def get_logs_by_timestamp(ext=".json", log_dir="logs"):
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
                    logs[timestamp] = logs.get(timestamp, []) + [(full_path, metadata)]
                except ValueError:
                    print(f"Error parsing timestamp for file: {basename}")
                    continue
    return logs


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
