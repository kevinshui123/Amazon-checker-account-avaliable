import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import random
import re
import os
import time
from threading import Thread, Event
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

from playwright_checker import (
    set_proxies,
    set_rotation_frequency,
    check_registrations_continuous
)

DEFAULT_WORKERS = 5

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Amazon Bulk Account Check - SongZiShell")
        self.geometry("720x700")

        self.identifiers = []      # Original account data loaded from file
        self.valid_emails = []     # Extracted valid emails
        self.results = []          # Check results list [(email, result), ...]

        self.max_workers = DEFAULT_WORKERS
        self.stop_event = Event()

        # Counters
        self.total_count = 0
        self.processed_count = 0
        self.registered_count = 0
        self.not_registered_count = 0
        self.unknown_count = 0

        self.create_widgets()

    def create_widgets(self):
        # Top logo
        frame_logo = ttk.Frame(self)
        frame_logo.pack(pady=5)
        try:
            from PIL import Image, ImageTk
            logo_img = Image.open("logo.png")
            logo_img = logo_img.resize((100, 100))
            self.logo = ImageTk.PhotoImage(logo_img)
            lbl_logo = ttk.Label(frame_logo, image=self.logo)
            lbl_logo.pack()
        except Exception as e:
            print(f"Failed to load logo: {e}")

        # First row buttons
        frame_buttons1 = ttk.Frame(self)
        frame_buttons1.pack(pady=5, padx=10, fill=tk.X)

        btn_load_identifiers = ttk.Button(frame_buttons1, text="Load Account File", command=self.load_identifiers)
        btn_load_identifiers.pack(side=tk.LEFT, padx=5)

        btn_extract = ttk.Button(frame_buttons1, text="Auto Extract Emails", command=self.extract_emails)
        btn_extract.pack(side=tk.LEFT, padx=5)

        btn_shuffle = ttk.Button(frame_buttons1, text="Shuffle Account Order", command=self.shuffle_identifiers)
        btn_shuffle.pack(side=tk.LEFT, padx=5)

        # Second row buttons
        frame_buttons2 = ttk.Frame(self)
        frame_buttons2.pack(pady=5, padx=10, fill=tk.X)

        btn_load_proxies = ttk.Button(frame_buttons2, text="Load Proxies", command=self.load_proxies)
        btn_load_proxies.pack(side=tk.LEFT, padx=5)

        btn_set_freq = ttk.Button(frame_buttons2, text="Set Proxy Rotation Frequency", command=self.set_proxy_frequency)
        btn_set_freq.pack(side=tk.LEFT, padx=5)

        btn_set_workers = ttk.Button(frame_buttons2, text="Set Concurrent Threads", command=self.set_workers)
        btn_set_workers.pack(side=tk.LEFT, padx=5)

        btn_start = ttk.Button(frame_buttons2, text="Start Bulk Check", command=self.start_concurrent_check)
        btn_start.pack(side=tk.LEFT, padx=5)

        btn_stop = ttk.Button(frame_buttons2, text="Stop Check", command=self.stop_checking)
        btn_stop.pack(side=tk.LEFT, padx=5)

        btn_export_results = ttk.Button(frame_buttons2, text="Export Results", command=self.export_results)
        btn_export_results.pack(side=tk.LEFT, padx=5)

        # Progress bar and counters
        frame_progress = ttk.Frame(self)
        frame_progress.pack(pady=5, padx=10, fill=tk.X)

        self.progress_bar = ttk.Progressbar(frame_progress, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=5)

        self.lbl_counter = ttk.Label(frame_progress, text="Progress: 0/0 | Registered: 0 | Not Registered: 0 | Failed/Unknown: 0")
        self.lbl_counter.pack(pady=2)

        lbl_output = ttk.Label(self, text="Check Results:")
        lbl_output.pack(anchor=tk.W, padx=10)

        self.txt_output = scrolledtext.ScrolledText(self, width=85, height=25)
        self.txt_output.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

    def load_identifiers(self):
        file_path = filedialog.askopenfilename(
            title="Select Account File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                self.identifiers = [line.strip() for line in lines if line.strip()]
            self.txt_output.insert(tk.END, f"Loaded account file, total {len(self.identifiers)} entries.\n")
            self.txt_output.see(tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load account file: {e}")

    def extract_emails(self):
        if not self.identifiers:
            messagebox.showwarning("Warning", "Please load the account file first")
            return
        pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        extracted = []
        for line in self.identifiers:
            matches = re.findall(pattern, line)
            extracted.extend(matches)
        self.valid_emails = list(set(extracted))
        count = len(self.valid_emails)
        self.txt_output.insert(tk.END, f"Extraction complete, found {count} valid emails.\n")
        self.txt_output.see(tk.END)

    def shuffle_identifiers(self):
        if not self.valid_emails:
            messagebox.showwarning("Warning", "Please run email extraction first")
            return
        random.shuffle(self.valid_emails)
        self.txt_output.insert(tk.END, "Email order has been shuffled.\n")
        self.txt_output.see(tk.END)

    def load_proxies(self):
        file_path = filedialog.askopenfilename(
            title="Select Proxy File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                proxy_list = [line.strip() for line in lines if line.strip()]
            set_proxies(proxy_list)
            self.txt_output.insert(tk.END, f"Loaded proxy file, total {len(proxy_list)} proxies.\n")
            self.txt_output.see(tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load proxy file: {e}")

    def set_proxy_frequency(self):
        freq = simpledialog.askinteger("Set Proxy Rotation Frequency", "Enter number of checks per proxy (integer > 0):", minvalue=1)
        if freq:
            set_rotation_frequency(freq)
            self.txt_output.insert(tk.END, f"Proxy rotation frequency set to rotate every {freq} checks.\n")
            self.txt_output.see(tk.END)

    def set_workers(self):
        w = simpledialog.askinteger("Set Concurrent Threads", "Enter number of concurrent threads (recommended 5~20):", minvalue=1, maxvalue=999)
        if w:
            self.max_workers = w
            self.txt_output.insert(tk.END, f"Concurrent threads set to {w}.\n")
            self.txt_output.see(tk.END)

    def start_concurrent_check(self):
        if not self.valid_emails:
            messagebox.showwarning("Warning", "Please extract valid emails first")
            return

        self.stop_event.clear()
        # Reset counters
        self.total_count = len(self.valid_emails)
        self.processed_count = 0
        self.registered_count = 0
        self.not_registered_count = 0
        self.unknown_count = 0
        self.results.clear()

        self.progress_bar["maximum"] = self.total_count
        self.progress_bar["value"] = 0
        self.update_counter_label()

        # Start concurrent checking
        t = Thread(target=self.concurrent_check)
        t.daemon = True
        t.start()

    def stop_checking(self):
        self.stop_event.set()
        self.txt_output.insert(tk.END, "Stop request received.\n")
        self.txt_output.see(tk.END)

    def update_counter_label(self):
        self.progress_bar["value"] = self.processed_count
        text = (f"Progress: {self.processed_count}/{self.total_count} | "
                f"Registered: {self.registered_count} | Not Registered: {self.not_registered_count} | "
                f"Failed/Unknown: {self.unknown_count}")
        self.lbl_counter.config(text=text)

    def log_to_ui(self, msg: str):
        self.txt_output.insert(tk.END, msg + "\n")
        self.txt_output.see(tk.END)

    def concurrent_check(self):
        def logger_callback(msg):
            self.txt_output.after(0, self.log_to_ui, msg)

        def progress_updater(email, result):
            if self.stop_event.is_set():
                return

            self.processed_count += 1
            if result is True:
                self.registered_count += 1
            elif result is False:
                self.not_registered_count += 1
            else:
                self.unknown_count += 1

            msg = f"{self.processed_count}/{self.total_count} -> [{email}] "
            if result is True:
                msg += "Registered"
            elif result is False:
                msg += "Not Registered"
            else:
                msg += "Failed/Unknown"

            self.results.append((email, result))

            self.txt_output.after(0, self.log_to_ui, msg)
            self.txt_output.after(0, self.update_counter_label)
            time.sleep(0.05)

        self.txt_output.after(0, lambda: self.txt_output.insert(tk.END, "Starting concurrent check...\n"))
        self.txt_output.after(0, self.txt_output.see, tk.END)

        # Divide the email list into groups, each processed by one thread.
        groups = [[] for _ in range(self.max_workers)]
        for idx, email in enumerate(self.valid_emails):
            groups[idx % self.max_workers].append(email)

        def worker(email_list):
            if self.stop_event.is_set():
                return []
            # Each thread uses asyncio.run to call the asynchronous check function.
            return asyncio.run(check_registrations_continuous(
                email_list,
                stop_event=self.stop_event,
                logger_callback=logger_callback,
                progress_callback=progress_updater
            ))

        all_results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for grp in groups:
                if not grp:
                    continue
                if self.stop_event.is_set():
                    break
                future = executor.submit(worker, grp)
                futures[future] = grp

            for future in as_completed(futures):
                if self.stop_event.is_set():
                    break
                group_results = future.result()
                all_results.extend(group_results)

        self.txt_output.after(0, lambda: self.txt_output.insert(tk.END, "Concurrent check complete or stopped.\n"))
        self.txt_output.after(0, self.txt_output.see, tk.END)

    def export_results(self):
        if not self.results:
            messagebox.showwarning("Warning", "No results to export")
            return
        file_path = filedialog.asksaveasfilename(
            title="Save Check Results",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            registered = []
            not_registered = []
            unknown = []
            for email, result in self.results:
                if result is True:
                    registered.append(email)
                elif result is False:
                    not_registered.append(email)
                else:
                    unknown.append(email)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("【Registered Accounts】\n")
                for email in registered:
                    f.write(f"{email}\n")
                f.write("\n【Not Registered Accounts】\n")
                for email in not_registered:
                    f.write(f"{email}\n")
                f.write("\n【Failed/Unknown Accounts】\n")
                for email in unknown:
                    f.write(f"{email}\n")
            messagebox.showinfo("Info", f"Results exported to: {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export results: {e}")

if __name__ == "__main__":
    app = App()
    app.mainloop()
