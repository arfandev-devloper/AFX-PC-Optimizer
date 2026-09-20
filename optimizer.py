import os
import sys
import time
import ctypes
import platform
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

import psutil

from optimizer_core import (
    bytes_to_human,
    get_system_summary,
    scan_junk,
    clean_junk,
    flush_dns,
    empty_recycle_bin,
    set_power_plan,
    create_restore_point,
    get_startup_apps,
)


APP_NAME = "AFX PC Optimizer"
APP_VERSION = "1.0.0"

BG = "#0b0b0d"
PANEL = "#141418"
CARD = "#1b1b21"
CARD_ALT = "#202028"
TEXT = "#f5f5f7"
MUTED = "#a6a6ad"
RED = "#ff2b2b"
RED_DARK = "#b71717"
GREEN = "#38d279"
AMBER = "#ffbd3d"
BORDER = "#2e2e38"


def is_windows():
    return platform.system().lower() == "windows"


def is_admin():
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class MetricCard(tk.Frame):
    def __init__(self, master, title, value="--", subtitle="", **kwargs):
        super().__init__(master, bg=CARD, highlightbackground=BORDER, highlightthickness=1, **kwargs)
        self.title_label = tk.Label(self, text=title.upper(), bg=CARD, fg=MUTED,
                                    font=("Segoe UI", 9, "bold"))
        self.title_label.pack(anchor="w", padx=16, pady=(14, 2))
        self.value_label = tk.Label(self, text=value, bg=CARD, fg=TEXT,
                                    font=("Segoe UI Semibold", 21))
        self.value_label.pack(anchor="w", padx=16)
        self.subtitle_label = tk.Label(self, text=subtitle, bg=CARD, fg=MUTED,
                                       font=("Segoe UI", 9))
        self.subtitle_label.pack(anchor="w", padx=16, pady=(2, 14))

    def set(self, value, subtitle=None, color=None):
        self.value_label.config(text=value, fg=color or TEXT)
        if subtitle is not None:
            self.subtitle_label.config(text=subtitle)


class AFXOptimizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1180x760")
        self.minsize(1020, 680)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._configure_styles()

        self.current_page = None
        self.page_frames = {}
        self.junk_scan = None
        self.process_rows = {}
        self.running = True

        self._build_shell()
        self.show_page("Dashboard")
        self.after(750, self.refresh_metrics)

    def _configure_styles(self):
        self.style.configure("AFX.TButton",
                             background=RED, foreground="white",
                             borderwidth=0, focusthickness=0,
                             font=("Segoe UI Semibold", 10), padding=(14, 9))
        self.style.map("AFX.TButton",
                       background=[("active", RED_DARK), ("pressed", "#8e1111")])

        self.style.configure("Secondary.TButton",
                             background=CARD_ALT, foreground=TEXT,
                             borderwidth=1, focusthickness=0,
                             font=("Segoe UI Semibold", 10), padding=(14, 9))
        self.style.map("Secondary.TButton",
                       background=[("active", "#2b2b35"), ("pressed", "#33333d")])

        self.style.configure("AFX.Treeview",
                             background=CARD, fieldbackground=CARD,
                             foreground=TEXT, rowheight=30,
                             bordercolor=BORDER, borderwidth=0,
                             font=("Segoe UI", 9))
        self.style.configure("AFX.Treeview.Heading",
                             background=CARD_ALT, foreground=TEXT,
                             font=("Segoe UI Semibold", 9))
        self.style.map("AFX.Treeview",
                       background=[("selected", "#5b1518")],
                       foreground=[("selected", "white")])

        self.style.configure("AFX.Horizontal.TProgressbar",
                             troughcolor=CARD_ALT,
                             background=RED,
                             bordercolor=CARD_ALT,
                             lightcolor=RED,
                             darkcolor=RED)

    def _build_shell(self):
        self.sidebar = tk.Frame(self, bg="#09090b", width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg="#09090b")
        brand.pack(fill="x", padx=18, pady=(24, 20))
        tk.Label(brand, text="AFX", bg="#09090b", fg=RED,
                 font=("Segoe UI Black", 25)).pack(anchor="w")
        tk.Label(brand, text="PC OPTIMIZER", bg="#09090b", fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(brand, text="Safe Windows performance tools", bg="#09090b",
                 fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        self.nav_buttons = {}
        for name in ("Dashboard", "Cleaner", "Processes", "Startup", "Tools"):
            btn = tk.Button(
                self.sidebar, text=name, anchor="w",
                bg="#09090b", fg=MUTED, activebackground=CARD,
                activeforeground=TEXT, bd=0, padx=18, pady=12,
                font=("Segoe UI Semibold", 10),
                cursor="hand2",
                command=lambda n=name: self.show_page(n)
            )
            btn.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[name] = btn

        footer = tk.Frame(self.sidebar, bg="#09090b")
        footer.pack(side="bottom", fill="x", padx=16, pady=18)
        status = "Administrator" if is_admin() else "Standard user"
        tk.Label(footer, text=f"Mode: {status}", bg="#09090b",
                 fg=GREEN if is_admin() else AMBER,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(footer, text=f"v{APP_VERSION}", bg="#09090b", fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.header = tk.Frame(self.main, bg=BG, height=78)
        self.header.pack(fill="x", padx=28, pady=(10, 0))
        self.header.pack_propagate(False)

        self.page_title = tk.Label(self.header, text="Dashboard", bg=BG, fg=TEXT,
                                   font=("Segoe UI Semibold", 23))
        self.page_title.pack(side="left", anchor="s", pady=14)

        self.os_badge = tk.Label(self.header, text=platform.system(), bg=CARD_ALT,
                                 fg=MUTED, padx=12, pady=6,
                                 font=("Segoe UI Semibold", 9))
        self.os_badge.pack(side="right", anchor="s", pady=17)

        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=28, pady=(0, 26))

    def show_page(self, name):
        if self.current_page == name:
            return
        for btn_name, btn in self.nav_buttons.items():
            if btn_name == name:
                btn.config(bg=CARD, fg=TEXT)
            else:
                btn.config(bg="#09090b", fg=MUTED)

        for frame in self.page_frames.values():
            frame.pack_forget()

        if name not in self.page_frames:
            builder = getattr(self, f"_build_{name.lower()}_page")
            self.page_frames[name] = builder()

        frame = self.page_frames[name]
        frame.pack(fill="both", expand=True)
        self.page_title.config(text=name)
        self.current_page = name

        if name == "Processes":
            self.refresh_processes()
        elif name == "Startup":
            self.refresh_startup()

    def _section_title(self, parent, title, subtitle=None):
        wrap = tk.Frame(parent, bg=BG)
        tk.Label(wrap, text=title, bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 16)).pack(anchor="w")
        if subtitle:
            tk.Label(wrap, text=subtitle, bg=BG, fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        wrap.pack(fill="x", pady=(2, 12))

    def _build_dashboard_page(self):
        page = tk.Frame(self.content, bg=BG)
        self._section_title(page, "Live system health",
                            "Real-time resource usage and essential system details.")

        cards = tk.Frame(page, bg=BG)
        cards.pack(fill="x")
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        self.cpu_card = MetricCard(cards, "CPU", "--", "Processor usage")
        self.ram_card = MetricCard(cards, "Memory", "--", "RAM usage")
        self.disk_card = MetricCard(cards, "System Disk", "--", "Drive usage")
        self.uptime_card = MetricCard(cards, "Uptime", "--", "Since last boot")
        for i, card in enumerate((self.cpu_card, self.ram_card, self.disk_card, self.uptime_card)):
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 3 else 7), pady=(0, 16))

        lower = tk.Frame(page, bg=BG)
        lower.pack(fill="both", expand=True)
        lower.grid_columnconfigure(0, weight=3)
        lower.grid_columnconfigure(1, weight=2)
        lower.grid_rowconfigure(0, weight=1)

        info = tk.Frame(lower, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        info.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(info, text="SYSTEM INFO", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(16, 10))
        self.info_text = tk.Text(info, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                 relief="flat", bd=0, font=("Consolas", 10),
                                 height=14, padx=18, pady=5)
        self.info_text.pack(fill="both", expand=True, padx=0, pady=(0, 12))
        self.info_text.config(state="disabled")
        self._load_system_info()

        actions = tk.Frame(lower, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        actions.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(actions, text="QUICK BOOST", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        tk.Label(actions, text="Safe maintenance shortcuts", bg=CARD, fg=TEXT,
                 font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18)
        tk.Label(actions,
                 text="No registry hacks, driver edits, or automatic service disabling.",
                 wraplength=330, justify="left", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(4, 16))

        ttk.Button(actions, text="Run Safe Boost", style="AFX.TButton",
                   command=self.ui_safe_boost).pack(fill="x", padx=18, pady=5)
        ttk.Button(actions, text="Scan Junk Files", style="Secondary.TButton",
                   command=lambda: self.show_page("Cleaner")).pack(fill="x", padx=18, pady=5)
        ttk.Button(actions, text="Flush DNS Cache", style="Secondary.TButton",
                   command=self.ui_flush_dns).pack(fill="x", padx=18, pady=5)
        ttk.Button(actions, text="Open Startup Apps", style="Secondary.TButton",
                   command=self.open_startup_settings).pack(fill="x", padx=18, pady=5)
        ttk.Button(actions, text="Balanced Power Plan", style="Secondary.TButton",
                   command=lambda: self.ui_power_plan("balanced")).pack(fill="x", padx=18, pady=5)

        return page

    def _build_cleaner_page(self):
        page = tk.Frame(self.content, bg=BG)
        self._section_title(page, "Junk cleaner",
                            "Scans common temporary folders. Locked/in-use files are skipped.")

        card = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 16))

        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=20, pady=20)
        self.junk_value = tk.Label(top, text="Not scanned", bg=CARD, fg=TEXT,
                                   font=("Segoe UI Semibold", 24))
        self.junk_value.pack(anchor="w")
        self.junk_sub = tk.Label(top, text="Run a scan to estimate reclaimable space.",
                                 bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self.junk_sub.pack(anchor="w", pady=(4, 0))

        buttons = tk.Frame(card, bg=CARD)
        buttons.pack(fill="x", padx=20, pady=(0, 20))
        self.scan_btn = ttk.Button(buttons, text="Scan", style="Secondary.TButton",
                                   command=self.start_junk_scan)
        self.scan_btn.pack(side="left")
        self.clean_btn = ttk.Button(buttons, text="Clean Selected Junk", style="AFX.TButton",
                                    command=self.start_junk_cleanup, state="disabled")
        self.clean_btn.pack(side="left", padx=(10, 0))
        ttk.Button(buttons, text="Empty Recycle Bin", style="Secondary.TButton",
                   command=self.ui_empty_recycle_bin).pack(side="left", padx=(10, 0))

        details = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        details.pack(fill="both", expand=True)

        tk.Label(details, text="SCAN DETAILS", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        self.cleaner_tree = ttk.Treeview(
            details, columns=("path", "files", "size"), show="headings",
            style="AFX.Treeview"
        )
        self.cleaner_tree.heading("path", text="Location")
        self.cleaner_tree.heading("files", text="Files")
        self.cleaner_tree.heading("size", text="Size")
        self.cleaner_tree.column("path", width=620)
        self.cleaner_tree.column("files", width=100, anchor="center")
        self.cleaner_tree.column("size", width=130, anchor="e")
        self.cleaner_tree.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        return page

    def _build_processes_page(self):
        page = tk.Frame(self.content, bg=BG)
        self._section_title(page, "Processes",
                            "Inspect running processes and end only the process you explicitly select.")

        toolbar = tk.Frame(page, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Refresh", style="Secondary.TButton",
                   command=self.refresh_processes).pack(side="left")
        ttk.Button(toolbar, text="End Selected Process", style="AFX.TButton",
                   command=self.end_selected_process).pack(side="left", padx=(10, 0))

        holder = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        holder.pack(fill="both", expand=True)

        self.proc_tree = ttk.Treeview(
            holder, columns=("pid", "name", "cpu", "memory"),
            show="headings", style="AFX.Treeview"
        )
        for col, title, width, anchor in [
            ("pid", "PID", 90, "center"),
            ("name", "Process", 500, "w"),
            ("cpu", "CPU %", 120, "e"),
            ("memory", "Memory", 140, "e"),
        ]:
            self.proc_tree.heading(col, text=title)
            self.proc_tree.column(col, width=width, anchor=anchor)
        self.proc_tree.pack(fill="both", expand=True, padx=18, pady=18)
        return page

    def _build_startup_page(self):
        page = tk.Frame(self.content, bg=BG)
        self._section_title(page, "Startup apps",
                            "View startup entries and open Windows Settings to enable/disable them safely.")

        toolbar = tk.Frame(page, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Refresh", style="Secondary.TButton",
                   command=self.refresh_startup).pack(side="left")
        ttk.Button(toolbar, text="Open Startup Settings", style="AFX.TButton",
                   command=self.open_startup_settings).pack(side="left", padx=(10, 0))

        holder = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        holder.pack(fill="both", expand=True)

        self.startup_tree = ttk.Treeview(
            holder, columns=("name", "command", "location"),
            show="headings", style="AFX.Treeview"
        )
        self.startup_tree.heading("name", text="Name")
        self.startup_tree.heading("command", text="Command")
        self.startup_tree.heading("location", text="Location")
        self.startup_tree.column("name", width=220)
        self.startup_tree.column("command", width=520)
        self.startup_tree.column("location", width=250)
        self.startup_tree.pack(fill="both", expand=True, padx=18, pady=18)
        return page

    def _build_tools_page(self):
        page = tk.Frame(self.content, bg=BG)
        self._section_title(page, "Windows tools",
                            "Useful maintenance actions with clear, reversible behavior.")

        grid = tk.Frame(page, bg=BG)
        grid.pack(fill="both", expand=True)
        for i in range(2):
            grid.grid_columnconfigure(i, weight=1)
        for i in range(3):
            grid.grid_rowconfigure(i, weight=1)

        tools = [
            ("Flush DNS", "Clear the Windows DNS resolver cache.", self.ui_flush_dns),
            ("Recycle Bin", "Permanently empty the current user's Recycle Bin.", self.ui_empty_recycle_bin),
            ("Balanced Power", "Restore the Windows Balanced power plan.", lambda: self.ui_power_plan("balanced")),
            ("High Performance", "Use higher performance mode; may reduce laptop battery life.", lambda: self.ui_power_plan("high")),
            ("Restore Point", "Ask Windows to create a restore point before major changes.", self.ui_restore_point),
            ("Storage Settings", "Open Windows Storage settings for deeper cleanup.", self.open_storage_settings),
        ]

        for index, (title, desc, action) in enumerate(tools):
            card = tk.Frame(grid, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            row, col = divmod(index, 2)
            card.grid(row=row, column=col, sticky="nsew",
                      padx=(0 if col == 0 else 8, 8 if col == 0 else 0),
                      pady=(0 if row == 0 else 8, 8 if row < 2 else 0))
            tk.Label(card, text=title, bg=CARD, fg=TEXT,
                     font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(16, 4))
            tk.Label(card, text=desc, wraplength=390, justify="left", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=18)
            ttk.Button(card, text="Run", style="Secondary.TButton",
                       command=action).pack(anchor="w", padx=18, pady=16)
        return page

    def _load_system_info(self):
        info = get_system_summary()
        lines = [
            f"OS          : {info['os']}",
            f"Computer    : {info['hostname']}",
            f"CPU         : {info['cpu']}",
            f"Cores       : {info['physical_cores']} physical / {info['logical_cores']} logical",
            f"Memory      : {bytes_to_human(info['ram_total'])}",
            f"System drive: {info['system_drive']}",
            f"Python      : {platform.python_version()}",
            f"Admin       : {'Yes' if is_admin() else 'No'}",
        ]
        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.config(state="disabled")

    def refresh_metrics(self):
        if not self.running:
            return
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            system_drive = os.environ.get("SystemDrive", "C:") + "\\" if is_windows() else "/"
            disk = psutil.disk_usage(system_drive)
            uptime = max(0, time.time() - psutil.boot_time())
            hours = int(uptime // 3600)
            days, hours = divmod(hours, 24)

            self.cpu_card.set(f"{cpu:.0f}%", "Processor usage",
                              GREEN if cpu < 60 else AMBER if cpu < 85 else RED)
            self.ram_card.set(f"{mem.percent:.0f}%",
                              f"{bytes_to_human(mem.used)} / {bytes_to_human(mem.total)}",
                              GREEN if mem.percent < 70 else AMBER if mem.percent < 90 else RED)
            self.disk_card.set(f"{disk.percent:.0f}%",
                               f"{bytes_to_human(disk.free)} free",
                               GREEN if disk.percent < 80 else AMBER if disk.percent < 92 else RED)
            self.uptime_card.set(f"{days}d {hours}h", "Since last boot")
        except Exception:
            pass
        self.after(1200, self.refresh_metrics)

    def start_junk_scan(self):
        self.scan_btn.config(state="disabled")
        self.clean_btn.config(state="disabled")
        self.junk_value.config(text="Scanning...")
        self.junk_sub.config(text="Checking safe temporary locations.")
        threading.Thread(target=self._junk_scan_worker, daemon=True).start()

    def _junk_scan_worker(self):
        try:
            result = scan_junk()
            self.after(0, lambda: self._show_scan_result(result))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Scan failed", str(exc)))
            self.after(0, lambda: self.scan_btn.config(state="normal"))

    def _show_scan_result(self, result):
        self.junk_scan = result
        for item in self.cleaner_tree.get_children():
            self.cleaner_tree.delete(item)
        for location in result["locations"]:
            self.cleaner_tree.insert(
                "", "end",
                values=(location["path"], location["files"], bytes_to_human(location["bytes"]))
            )
        self.junk_value.config(text=bytes_to_human(result["bytes"]))
        self.junk_sub.config(text=f"{result['files']} files eligible for cleanup (24+ hours old).")
        self.scan_btn.config(state="normal")
        self.clean_btn.config(state="normal" if result["files"] else "disabled")

    def start_junk_cleanup(self):
        if not self.junk_scan or not self.junk_scan.get("files"):
            return
        if not messagebox.askyesno(
            "Confirm cleanup",
            "Delete the scanned temporary files?\n\n"
            "Only common temp folders are targeted and locked files are skipped."
        ):
            return
        self.scan_btn.config(state="disabled")
        self.clean_btn.config(state="disabled")
        self.junk_value.config(text="Cleaning...")
        threading.Thread(target=self._junk_cleanup_worker, daemon=True).start()

    def _junk_cleanup_worker(self):
        try:
            result = clean_junk(self.junk_scan)
            self.after(0, lambda: self._cleanup_done(result))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Cleanup failed", str(exc)))
            self.after(0, lambda: self.scan_btn.config(state="normal"))

    def _cleanup_done(self, result):
        messagebox.showinfo(
            "Cleanup complete",
            f"Removed {result['deleted_files']} files and reclaimed "
            f"{bytes_to_human(result['deleted_bytes'])}.\n"
            f"Skipped: {result['skipped_files']} files."
        )
        self.start_junk_scan()

    def refresh_processes(self):
        if not hasattr(self, "proc_tree"):
            return
        for item in self.proc_tree.get_children():
            self.proc_tree.delete(item)

        rows = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mem = proc.info["memory_info"].rss if proc.info["memory_info"] else 0
                rows.append((proc.info["pid"], proc.info["name"] or "Unknown", mem))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        rows.sort(key=lambda r: r[2], reverse=True)
        for pid, name, mem in rows[:250]:
            self.proc_tree.insert("", "end", values=(pid, name, "", bytes_to_human(mem)))

    def end_selected_process(self):
        selection = self.proc_tree.selection()
        if not selection:
            messagebox.showwarning("No process selected", "Select a process first.")
            return

        values = self.proc_tree.item(selection[0], "values")
        pid = int(values[0])
        name = values[1]

        protected = {"system", "registry", "secure system", "memory compression"}
        if pid <= 4 or name.lower() in protected:
            messagebox.showerror("Protected process", "AFX PC Optimizer will not end this system process.")
            return

        if not messagebox.askyesno(
            "End process?",
            f"End '{name}' (PID {pid})?\n\nUnsaved work in that app may be lost."
        ):
            return

        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                if messagebox.askyesno("Process still running", "Force-kill this process?"):
                    proc.kill()
            self.refresh_processes()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            messagebox.showerror("Could not end process", str(exc))

    def refresh_startup(self):
        if not hasattr(self, "startup_tree"):
            return
        for item in self.startup_tree.get_children():
            self.startup_tree.delete(item)
        self.startup_tree.insert("", "end", values=("Loading...", "", ""))

        def worker():
            apps = get_startup_apps()
            self.after(0, lambda: self._show_startup_apps(apps))

        threading.Thread(target=worker, daemon=True).start()

    def _show_startup_apps(self, apps):
        for item in self.startup_tree.get_children():
            self.startup_tree.delete(item)
        if not apps:
            self.startup_tree.insert("", "end", values=("No entries found", "", ""))
            return
        for app in apps:
            self.startup_tree.insert("", "end",
                                     values=(app.get("Name", ""),
                                             app.get("Command", ""),
                                             app.get("Location", "")))

    def ui_safe_boost(self):
        if not messagebox.askyesno(
            "Run Safe Boost?",
            "AFX will clean eligible temporary files (24+ hours old) and flush the DNS cache.\n\n"
            "It will not edit the registry, drivers, security settings, or personal files."
        ):
            return

        def worker():
            try:
                scan = scan_junk()
                cleaned = clean_junk(scan)
                dns_ok, dns_msg = flush_dns()
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Safe Boost complete",
                        f"Temporary files removed: {cleaned['deleted_files']}\n"
                        f"Space reclaimed: {bytes_to_human(cleaned['deleted_bytes'])}\n"
                        f"Skipped/in-use files: {cleaned['skipped_files']}\n\n"
                        f"DNS: {'Flushed successfully' if dns_ok else dns_msg}"
                    )
                )
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Safe Boost failed", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def ui_flush_dns(self):
        ok, msg = flush_dns()
        (messagebox.showinfo if ok else messagebox.showerror)("Flush DNS", msg)

    def ui_empty_recycle_bin(self):
        if not messagebox.askyesno(
            "Empty Recycle Bin?",
            "This permanently deletes items currently in the Recycle Bin."
        ):
            return
        ok, msg = empty_recycle_bin()
        (messagebox.showinfo if ok else messagebox.showerror)("Recycle Bin", msg)

    def ui_power_plan(self, mode):
        if mode == "high":
            if not messagebox.askyesno(
                "High Performance mode",
                "This can increase performance but may use more power and reduce laptop battery life.\n\nContinue?"
            ):
                return
        ok, msg = set_power_plan(mode)
        (messagebox.showinfo if ok else messagebox.showerror)("Power plan", msg)

    def ui_restore_point(self):
        if not messagebox.askyesno(
            "Create restore point",
            "Windows System Protection must be enabled. Administrator rights may be required.\n\nContinue?"
        ):
            return
        ok, msg = create_restore_point()
        (messagebox.showinfo if ok else messagebox.showerror)("Restore point", msg)

    def open_startup_settings(self):
        if not is_windows():
            messagebox.showerror("Unsupported", "This shortcut is available on Windows only.")
            return
        try:
            os.startfile("ms-settings:startupapps")
        except Exception as exc:
            messagebox.showerror("Could not open Settings", str(exc))

    def open_storage_settings(self):
        if not is_windows():
            messagebox.showerror("Unsupported", "This shortcut is available on Windows only.")
            return
        try:
            os.startfile("ms-settings:storagesense")
        except Exception as exc:
            messagebox.showerror("Could not open Settings", str(exc))

    def on_close(self):
        self.running = False
        self.destroy()


if __name__ == "__main__":
    app = AFXOptimizer()
    app.mainloop()