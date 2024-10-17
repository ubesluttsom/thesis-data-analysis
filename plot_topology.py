import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from utils import pipe_or_save

# Network Topology Dictionary
star_topology_context = {
    "networks": {
        "net1": {
            "bridge_name": "virbr1",
            "ip_address": "10.0.1.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.1.100",
            "dhcp_range_end": "10.0.1.200",
            "devices": ["router1", "vm1"],
        },
        "net2": {
            "bridge_name": "virbr2",
            "ip_address": "10.0.2.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.2.100",
            "dhcp_range_end": "10.0.2.200",
            "devices": ["router1", "vm2"],
        },
        "net3": {
            "bridge_name": "virbr3",
            "ip_address": "10.0.3.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.3.100",
            "dhcp_range_end": "10.0.3.200",
            "devices": ["router1", "vm3"],
        },
        "net4": {
            "bridge_name": "virbr4",
            "ip_address": "10.0.4.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.4.100",
            "dhcp_range_end": "10.0.4.200",
            "devices": ["router1", "vm4"],
        },
    },
    "devices": {
        "router1": {
            "macs": {
                "net1": "52:54:00:01:00:01",
                "net2": "52:54:00:01:00:02",
                "net3": "52:54:00:01:00:03",
                "net4": "52:54:00:01:00:04",
            },
            "ips": {
                "net1": "10.0.1.100",
                "net2": "10.0.2.100",
                "net3": "10.0.3.100",
                "net4": "10.0.4.100",
            },
            "routes": {
                "10.0.1.0/24": "10.0.1.101",
                "10.0.2.0/24": "10.0.2.101",
                "10.0.3.0/24": "10.0.3.101",
                "10.0.4.0/24": "10.0.4.101",
            },
        },
        "vm1": {
            "macs": {"net1": "52:54:00:00:01:01"},
            "ips": {"net1": "10.0.1.101"},
            "default_gateway": "10.0.1.100",
        },
        "vm2": {
            "macs": {"net2": "52:54:00:00:02:01"},
            "ips": {"net2": "10.0.2.101"},
            "default_gateway": "10.0.2.100",
        },
        "vm3": {
            "macs": {"net3": "52:54:00:00:03:01"},
            "ips": {"net3": "10.0.3.101"},
            "default_gateway": "10.0.3.100",
        },
        "vm4": {
            "macs": {"net4": "52:54:00:00:04:01"},
            "ips": {"net4": "10.0.4.101"},
            "default_gateway": "10.0.4.100",
        },
    },
}

one_sender_context = {
    "networks": {
        "net1": {
            "bridge_name": "virbr1",
            "ip_address": "10.0.1.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.1.100",
            "dhcp_range_end": "10.0.1.200",
            "devices": ["router1", "vm1"],
        },
        "net2": {
            "bridge_name": "virbr2",
            "ip_address": "10.0.2.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.2.100",
            "dhcp_range_end": "10.0.2.200",
            "devices": ["router1", "vm2"],
        },
    },
    "devices": {
        "router1": {
            "macs": {
                "net1": "52:54:00:01:00:01",
                "net2": "52:54:00:01:00:02",
            },
            "ips": {
                "net1": "10.0.1.100",
                "net2": "10.0.2.100",
            },
            "routes": {
                "10.0.1.0/24": "10.0.1.101",
                "10.0.2.0/24": "10.0.2.101",
            },
        },
        "vm1": {
            "macs": {"net1": "52:54:00:00:01:01"},
            "ips": {"net1": "10.0.1.101"},
            "default_gateway": "10.0.1.100",
        },
        "vm2": {
            "macs": {"net2": "52:54:00:00:02:01"},
            "ips": {"net2": "10.0.2.101"},
            "default_gateway": "10.0.2.100",
        },
    },
}

context = {
    "networks": {
        "net1": {
            "bridge_name": "virbr1",
            "ip_address": "10.0.1.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.1.100",
            "dhcp_range_end": "10.0.1.200",
            "devices": ["router1", "vm1"],
        },
        "net2": {
            "bridge_name": "virbr2",
            "ip_address": "10.0.2.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.2.100",
            "dhcp_range_end": "10.0.2.200",
            "devices": ["router1", "vm2"],
        },
        "net3": {
            "bridge_name": "virbr3",
            "ip_address": "10.0.3.1",
            "netmask": "255.255.255.0",
            "dhcp_range_start": "10.0.3.100",
            "dhcp_range_end": "10.0.3.200",
            "devices": ["router1", "vm3"],
        },
    },
    "devices": {
        "router1": {
            "macs": {
                "net1": "52:54:00:01:00:01",
                "net2": "52:54:00:01:00:02",
                "net3": "52:54:00:01:00:03",
            },
            "ips": {
                "net1": "10.0.1.100",
                "net2": "10.0.2.100",
                "net3": "10.0.3.100",
            },
            "routes": {
                "10.0.1.0/24": "10.0.1.101",
                "10.0.2.0/24": "10.0.2.101",
                "10.0.3.0/24": "10.0.3.101",
            },
        },
        "vm1": {
            "macs": {"net1": "52:54:00:00:01:01"},
            "ips": {"net1": "10.0.1.101"},
            "default_gateway": "10.0.1.100",
        },
        "vm2": {
            "macs": {"net2": "52:54:00:00:02:01"},
            "ips": {"net2": "10.0.2.101"},
            "default_gateway": "10.0.2.100",
        },
        "vm3": {
            "macs": {"net3": "52:54:00:00:03:01"},
            "ips": {"net3": "10.0.3.101"},
            "default_gateway": "10.0.3.100",
        },
    },
}

# Initialize the graph
G = nx.Graph()

n = 2
colors = [plt.cm.ocean((i / 1.5) / (n - 1)) for i in range(n)]

# Add device nodes
devices = context["devices"]
for device in devices:
    if device.startswith("vm"):
        G.add_node(device, type='VM', label=device, color=colors[0])
    elif device.startswith("router"):
        G.add_node(device, type='Router', label=device, color=colors[1])

# Add edges between router and VMs directly, bypassing networks
router = "router1"
for net, details in context["networks"].items():
    connected_devices = details["devices"]
    for device in connected_devices:
        if device != router:
            G.add_edge(router, device, network=net)

# Define node colors based on type
node_colors = [G.nodes[node]['color'] for node in G.nodes]

# Define labels
labels = {node: G.nodes[node]['label'] for node in G.nodes}

# Compute positions using Kamada-Kawai layout
pos = nx.kamada_kawai_layout(G, scale=0.5)

# Matplotlib Styling
plt.style.use("seaborn-v0_8")
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Libertinus Serif"]

fig, ax = plt.subplots(figsize=(4, 4))

# Draw edges manually
for edge in G.edges(data=True):
    node1, node2, data = edge
    # Extract positions
    x1, y1 = pos[node1]
    x2, y2 = pos[node2]
    # Draw a line between node1 and node2
    ax.plot([x1, x2], [y1, y2], color='white', linewidth=2, zorder=1)
    # # Optionally, add network labels on edges
    # mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
    # network = data.get('network', '')
    # ax.text(mid_x, mid_y, network, fontsize=9, ha='center', va='center', backgroundcolor='white')

# Add special edge case
x1, y1 = pos['router1']
x2, y2 = pos['vm1']
ax.plot([x1, x2], [y1, y2], color=ax.get_facecolor(), linewidth=2)
ax.plot([x1, x2], [y1, y2], color='white', linestyle='--', linewidth=2, label='RED applied here')

# Draw nodes manually using scatter
for node, (x, y) in pos.items():
    color = G.nodes[node]['color']
    ax.scatter(x, y, s=1500, color=ax.get_facecolor(), zorder=2, linewidth=2)
    ax.scatter(x, y, s=1500, color=color, zorder=3, edgecolors='white', linewidth=2, alpha=0.2)
    ax.scatter(x, y, s=1500, color=('white', 0), zorder=4, edgecolors='white', linewidth=2)

# Draw labels manually
for node, (x, y) in pos.items():
    ax.text(x, y, labels[node], ha='center', va='center', fontfamily='serif', fontstyle='italic')

ax.set_xticks([])
ax.set_yticks([])
ax.margins(x=0.5, y=0.5)

ax.legend(loc='lower center')

# Add title
plt.title("Network topology", fontweight='bold')

# Adjust layout
plt.tight_layout()

# Save the figure
pipe_or_save("network_topology")
