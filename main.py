import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import sys
import re
from pathlib import Path

def save_network_map():
    downloads_dir = Path.home() / "Downloads"

    if not SCAN_FILE.exists():
        status_label.config(
            text="No network map available to save.",
            fg="#ff5555"
        )
        return

    try:
        downloads_dir.mkdir(parents=True, exist_ok=True)
        destination = downloads_dir / "network_map.txt"

        destination.write_text(
            SCAN_FILE.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8"
        )

        status_label.config(
            text=f"Network map saved to {destination}",
            fg="#55cc77"
        )

    except Exception as error:
        status_label.config(
            text=f"Could not save network map: {error}",
            fg="#ff5555"
        )
# ==========================================
# CONFIGURATION
# ==========================================

APP_DIR = Path(__file__).resolve().parent
SCANNERS = {
    "10.x.x.x Scan": APP_DIR / "large_terminal_app.py",
    "172.x.x.x Scan": APP_DIR / "medium_terminal_app.py",
    "local Scan": APP_DIR / "small_terminal_app.py"
}

SCAN_FILE = APP_DIR / "network_map.txt"

BG = "#1e1e1e"
PANEL = "#252526"
BUTTON = "#333333"
BLUE = "#0078d7"
WHITE = "#ffffff"
GRAY = "#aaaaaa"

# Maps Treeview item IDs to the device information parsed from the report.
device_nodes = {}


# ==========================================
# MAIN WINDOW
# ==========================================

root = tk.Tk()
root.title("Network Discovery")
root.geometry("1000x650")
root.configure(bg=BG)
root.minsize(750, 450)


# ==========================================
# STYLING
# ==========================================

style = ttk.Style()
style.theme_use("clam")

style.configure(
    "Treeview",
    background=PANEL,
    foreground=WHITE,
    fieldbackground=PANEL,
    borderwidth=0,
    rowheight=28,
    font=("Arial", 10)
)

style.configure(
    "Treeview.Heading",
    background=BUTTON,
    foreground=WHITE,
    font=("Arial", 10, "bold")
)

style.map(
    "Treeview",
    background=[("selected", BLUE)],
    foreground=[("selected", WHITE)]
)


# ==========================================
# TOP NAVIGATION
# ==========================================

top_bar = tk.Frame(root, bg=PANEL, height=45)
top_bar.pack(fill="x")
top_bar.pack_propagate(False)


def create_nav_button(text, command):
    return tk.Button(
        top_bar,
        text=text,
        command=command,
        bg=BUTTON,
        fg=WHITE,
        activebackground=BLUE,
        activeforeground=WHITE,
        relief="flat",
        font=("Arial", 10, "bold"),
        padx=15,
        pady=5,
        cursor="hand2"
    )


# ==========================================
# CONTENT AREA
# ==========================================

content = tk.Frame(root, bg=BG)
content.pack(fill="both", expand=True)


# ==========================================
# MAIN SCREEN
# ==========================================

main_frame = tk.Frame(content, bg=BG)

main_title = tk.Label(
    main_frame,
    text="Network Discovery",
    font=("Arial", 28, "bold"),
    fg=WHITE,
    bg=BG
)
main_title.pack(pady=(70, 10))

main_description = tk.Label(
    main_frame,
    text="Network monitoring and device discovery",
    font=("Arial", 12),
    fg=GRAY,
    bg=BG
)
main_description.pack(pady=5)

# ==========================================
# MAIN SCREEN BUTTONS / STATUS
# ==========================================

scan_buttons = []

for scanner_name in SCANNERS:

    button = tk.Button(
        main_frame,
        text=scanner_name,
        font=("Arial", 13, "bold"),
        bg=BLUE,
        fg=WHITE,
        activebackground="#0063b1",
        activeforeground=WHITE,
        relief="flat",
        padx=30,
        pady=12,
        command=lambda name=scanner_name: scan_network(name),
        cursor="hand2"
    )

    button.pack(pady=12)
    scan_buttons.append(button)

save_button = tk.Button(
    main_frame,
    text="Save Network Map",
    font=("Arial", 13, "bold"),
    bg=BUTTON,
    fg=WHITE,
    activebackground=BLUE,
    activeforeground=WHITE,
    relief="flat",
    padx=30,
    pady=12,
    command=save_network_map,
    cursor="hand2"
)

save_button.pack(pady=12)


status_label = tk.Label(
    main_frame,
    text="Ready",
    font=("Arial", 10),
    fg=GRAY,
    bg=BG
)

status_label.pack(pady=15)
# ==========================================
# NETWORK EXPLORER SCREEN
# ==========================================

network_frame = tk.Frame(content, bg=BG)

network_title = tk.Label(
    network_frame,
    text="Network Explorer",
    font=("Arial", 22, "bold"),
    fg=WHITE,
    bg=BG
)
network_title.pack(anchor="w", padx=20, pady=15)

# Load Map button stays on the Network page.
network_toolbar = tk.Frame(network_frame, bg=BG)
network_toolbar.pack(fill="x", padx=15, pady=(0, 10))


# ==========================================
# MAIN EXPLORER LAYOUT
# ==========================================

explorer = tk.Frame(network_frame, bg=BG)
explorer.pack(fill="both", expand=True, padx=15, pady=10)

# Left sidebar
sidebar = tk.Frame(explorer, bg=PANEL, width=300)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

sidebar_title = tk.Label(
    sidebar,
    text="NETWORK",
    font=("Arial", 11, "bold"),
    fg=GRAY,
    bg=PANEL
)
sidebar_title.pack(anchor="w", padx=12, pady=12)

tree_container = tk.Frame(sidebar, bg=PANEL)
tree_container.pack(fill="both", expand=True, padx=5, pady=5)

tree_scrollbar = ttk.Scrollbar(tree_container, orient="vertical")
tree_scrollbar.pack(side="right", fill="y")

tree = ttk.Treeview(
    tree_container,
    yscrollcommand=tree_scrollbar.set,
    show="tree",
    selectmode="browse"
)
tree.pack(side="left", fill="both", expand=True)
tree_scrollbar.config(command=tree.yview)

# Right information panel
details_frame = tk.Frame(explorer, bg=BG)
details_frame.pack(side="left", fill="both", expand=True, padx=20)

details_title = tk.Label(
    details_frame,
    text="Network Information",
    font=("Arial", 18, "bold"),
    fg=WHITE,
    bg=BG
)
details_title.pack(anchor="w", pady=(10, 15))

# Text widget supports multiple lines and long device details.
details_text = tk.Text(
    details_frame,
    font=("Consolas", 11),
    fg=WHITE,
    bg=BG,
    relief="flat",
    wrap="word",
    padx=5,
    pady=5,
    state="disabled"
)
details_text.pack(fill="both", expand=True, anchor="nw")

network_stats = tk.Label(
    network_frame,
    text="No network scan loaded.",
    font=("Arial", 10),
    fg=GRAY,
    bg=BG
)
network_stats.pack(anchor="w", padx=20, pady=10)


def display_details(text):
    """Safely replace the contents of the read-only information panel."""
    details_text.config(state="normal")
    details_text.delete("1.0", "end")
    details_text.insert("1.0", text)
    details_text.config(state="disabled")


# ==========================================
# NETWORK DATA IMPORTER
# ==========================================

def populate_network(scan_data):
    """
    Parse network_map.txt into VLAN folders and device records.
    Device entries display both IP address and hostname.
    """

    global device_nodes
    device_nodes = {}

    tree.delete(*tree.get_children())

    network_root = tree.insert(
        "",
        "end",
        text="Network",
        open=True
    )

    vlan_nodes = {}
    vlan_count = 0
    device_count = 0

    current_vlan_node = None
    current_device_id = None

    vlan_pattern = re.compile(
        r"^\s*===\s*VLAN\s+([\d.]+/\d+)\s*===\s*$",
        re.IGNORECASE
    )

    device_pattern = re.compile(
        r"^\s*\[\+\]\s+"
        r"((?:\d{1,3}\.){3}\d{1,3})"
        r"\s+\((.*?)\)\s*$"
    )

    detail_pattern = re.compile(
        r"^\s*(Hostname|MAC Address|Manufacturer|Device Type|Open Ports)\s*:\s*(.*?)\s*$",
        re.IGNORECASE
    )

    field_names = {
        "hostname": "Hostname",
        "mac address": "MAC Address",
        "manufacturer": "Manufacturer",
        "device type": "Device Type",
        "open ports": "Open Ports"
    }

    for line in scan_data.splitlines():

        # Detect VLAN
        vlan_match = vlan_pattern.match(line)

        if vlan_match:
            vlan_name = vlan_match.group(1)
            current_device_id = None

            if vlan_name not in vlan_nodes:
                vlan_nodes[vlan_name] = tree.insert(
                    network_root,
                    "end",
                    text=f"VLAN {vlan_name}",
                    open=False
                )
                vlan_count += 1

            current_vlan_node = vlan_nodes[vlan_name]
            continue

        if current_vlan_node is None:
            continue

        # Detect device
        device_match = device_pattern.match(line)

        if device_match:
            ip_address = device_match.group(1)
            method = device_match.group(2).strip()

            current_device_id = tree.insert(
                current_vlan_node,
                "end",
                text=f"{ip_address} ({method})",
                open=False
            )

            device_nodes[current_device_id] = {
                "IP Address": ip_address,
                "Detection Method": method,
                "Hostname": "Unknown",
                "MAC Address": "Unknown",
                "Manufacturer": "Unknown",
                "Device Type": "Unknown Device",
                "Open Ports": "None detected"
            }

            device_count += 1
            continue

        # Parse device details
        if current_device_id is not None:

            detail_match = detail_pattern.match(line)

            if detail_match:
                source_field = detail_match.group(1).strip().lower()
                value = detail_match.group(2).strip()

                field = field_names[source_field]

                if value:
                    device_nodes[current_device_id][field] = value

    # Update folder names after all hostnames have been parsed.
    for item_id, device in device_nodes.items():

        ip_address = device["IP Address"]
        hostname = device["Hostname"]
        method = device["Detection Method"]

        if hostname != "Unknown":
            folder_name = f"{ip_address} - {hostname}"
        else:
            folder_name = f"{ip_address} ({method})"

        tree.item(
            item_id,
            text=folder_name
        )

    tree.item(network_root, open=True)

    network_stats.config(
        text=f"Loaded {vlan_count} VLANs | {device_count} devices"
    )

    details_title.config(text="Network Information")
    display_details("Select a VLAN or device to view its information.")

    return vlan_count, device_count

# ==========================================
# TREE SELECTION
# ==========================================

def on_tree_select(event=None):
    selection = tree.selection()
    if not selection:
        return

    selected_item = selection[0]
    item_text = tree.item(selected_item, "text")

    details_title.config(text=item_text)

    if item_text == "Network":
        display_details(
            "Network Overview\n\n"
            "Select a VLAN or device to view its information."
        )

    elif item_text.startswith("VLAN "):
        children = tree.get_children(selected_item)
        display_details(
            f"{item_text}\n\n"
            f"Discovered devices: {len(children)}"
        )

    elif selected_item in device_nodes:
        device = device_nodes[selected_item]

        lines = [
            "DEVICE INFORMATION",
            "==================",
            ""
        ]

        for key, value in device.items():
            lines.append(f"{key:<20}: {value}")

        display_details("\n".join(lines))


tree.bind("<<TreeviewSelect>>", on_tree_select)


# ==========================================
# LOAD EXISTING NETWORK MAP
# ==========================================

def load_network_map():
    file_path = filedialog.askopenfilename(
        title="Load Network Map",
        initialdir=str(APP_DIR),
        filetypes=[
            ("Network Maps", "*.txt *.md"),
            ("Text Files", "*.txt"),
            ("Markdown Files", "*.md"),
            ("All Files", "*.*")
        ]
    )

    if not file_path:
        return

    try:
        scan_data = Path(file_path).read_text(
            encoding="utf-8",
            errors="replace"
        )

        vlan_count, device_count = populate_network(scan_data)

        status_label.config(
            text=(
                f"Loaded {Path(file_path).name}: "
                f"{vlan_count} VLANs, {device_count} devices"
            ),
            fg="#55cc77"
        )

        show_network()

    except Exception as error:
        status_label.config(
            text=f"Could not load map: {error}",
            fg="#ff5555"
        )


load_button = tk.Button(
    network_toolbar,
    text="Load Network Map",
    font=("Arial", 10, "bold"),
    bg=BUTTON,
    fg=WHITE,
    activebackground=BLUE,
    activeforeground=WHITE,
    relief="flat",
    padx=15,
    pady=8,
    command=load_network_map,
    cursor="hand2"
)
load_button.pack(side="left")





# ==========================================
# SCANNER PROCESS
# ==========================================

def scan_network(scanner_name):
    scanner = SCANNERS[scanner_name]

    # Prevent multiple scans from running simultaneously.
    for button in scan_buttons:
        button.config(state="disabled")

    status_label.config(
        text=f"Running {scanner_name}...",
        fg=GRAY
    )

    if not scanner.exists():
        status_label.config(
            text=f"Error: {scanner.name} not found.",
            fg="#ff5555"
        )

        for button in scan_buttons:
            button.config(state="normal")
        return

    try:
        # Launch the selected scanner.
        process = subprocess.Popen(
            [sys.executable, str(scanner)],
            cwd=str(APP_DIR)
        )

        check_scan_finished(process, scanner_name)

    except Exception as error:
        status_label.config(
            text=f"Scanner error: {error}",
            fg="#ff5555"
        )

        for button in scan_buttons:
            button.config(state="normal")


def check_scan_finished(process, scanner_name):
    if process.poll() is None:
        root.after(
            500,
            lambda: check_scan_finished(process, scanner_name)
        )
        return

    # Re-enable scan buttons.
    for button in scan_buttons:
        button.config(state="normal")

    if process.returncode != 0:
        status_label.config(
            text=f"{scanner_name} exited with code {process.returncode}.",
            fg="#ff5555"
        )
        return

    if not SCAN_FILE.exists():
        status_label.config(
            text="network_map.txt was not created.",
            fg="#ff5555"
        )
        return

    try:
        scan_data = SCAN_FILE.read_text(
            encoding="utf-8",
            errors="replace"
        )

        vlan_count, device_count = populate_network(scan_data)

        status_label.config(
            text=f"{scanner_name} complete: {vlan_count} VLANs, {device_count} devices",
            fg="#55cc77"
        )

        show_network()

    except Exception as error:
        status_label.config(
            text=f"Import error: {error}",
            fg="#ff5555"
        )

# ==========================================
# SCREEN NAVIGATION
# ==========================================

def show_main():
    network_frame.pack_forget()
    main_frame.pack(fill="both", expand=True)


def show_network():
    main_frame.pack_forget()
    network_frame.pack(fill="both", expand=True)


main_nav_button = create_nav_button("Main", show_main)
main_nav_button.pack(side="left", padx=5, pady=5)

network_nav_button = create_nav_button("Network", show_network)
network_nav_button.pack(side="left", padx=5, pady=5)


# ==========================================
# START APPLICATION
# ==========================================

show_main()
root.mainloop()