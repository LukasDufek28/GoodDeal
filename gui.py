import tkinter as tk
from tkinter import ttk
import webbrowser
from typing import List, Tuple, Optional


class ReviewGUI:
    def __init__(self, listings: List[Tuple[str, str, Optional[int], Optional[str], Optional[str]]]):
        # listings: list of (title, url, price, currency, location)
        self.root = tk.Tk()
        self.root.title("GoodDeal - Review Listings")
        self.listings = listings
        self.index = 0
        self.result = []  # accepted items
        self._closed = False

        self._build()
        self._load_current()

    def _build(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        ttk.Label(frm, text="Title:").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(frm, textvariable=self.title_var, width=80)
        self.title_entry.grid(row=0, column=1, columnspan=3, sticky="ew")

        ttk.Label(frm, text="URL:").grid(row=1, column=0, sticky="w")
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(frm, textvariable=self.url_var, width=80)
        self.url_entry.grid(row=1, column=1, columnspan=2, sticky="ew")
        self.open_btn = ttk.Button(frm, text="Open", command=self._open_url)
        self.open_btn.grid(row=1, column=3, sticky="e")

        ttk.Label(frm, text="Price:").grid(row=2, column=0, sticky="w")
        self.price_var = tk.StringVar()
        self.price_entry = ttk.Entry(frm, textvariable=self.price_var, width=20)
        self.price_entry.grid(row=2, column=1, sticky="w")
        ttk.Label(frm, text="Currency:").grid(row=2, column=2, sticky="w")
        self.cur_var = tk.StringVar()
        self.cur_entry = ttk.Entry(frm, textvariable=self.cur_var, width=10)
        self.cur_entry.grid(row=2, column=3, sticky="w")

        ttk.Label(frm, text="Location:").grid(row=3, column=0, sticky="w")
        self.loc_var = tk.StringVar()
        self.loc_entry = ttk.Entry(frm, textvariable=self.loc_var, width=50)
        self.loc_entry.grid(row=3, column=1, columnspan=3, sticky="ew")

        self.desc_text = tk.Text(frm, height=8, width=80)
        self.desc_text.grid(row=4, column=0, columnspan=4, pady=(8, 8))

        btn_frm = ttk.Frame(frm)
        btn_frm.grid(row=5, column=0, columnspan=4, sticky="ew")
        btn_frm.columnconfigure(0, weight=1)
        btn_frm.columnconfigure(1, weight=1)
        btn_frm.columnconfigure(2, weight=1)
        btn_frm.columnconfigure(3, weight=1)

        self.accept_btn = ttk.Button(btn_frm, text="Accept", command=self._accept)
        self.accept_btn.grid(row=0, column=0, sticky="ew", padx=4)
        self.decline_btn = ttk.Button(btn_frm, text="Decline", command=self._decline)
        self.decline_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.prev_btn = ttk.Button(btn_frm, text="Prev", command=self._prev)
        self.prev_btn.grid(row=0, column=2, sticky="ew", padx=4)
        self.next_btn = ttk.Button(btn_frm, text="Next", command=self._next)
        self.next_btn.grid(row=0, column=3, sticky="ew", padx=4)

        self.status_var = tk.StringVar()
        ttk.Label(frm, textvariable=self.status_var).grid(row=6, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def _load_current(self):
        if not (0 <= self.index < len(self.listings)):
            self._finish()
            return
        title, url, price, cur, loc, desc = self.listings[self.index]
        self.title_var.set(title or "")
        self.url_var.set(url or "")
        self.price_var.set(str(price) if price is not None else "")
        self.cur_var.set(cur or "")
        self.loc_var.set(loc or "")
        self.desc_text.delete("1.0", "end")
        if desc:
            self.desc_text.insert("1.0", desc)
        self.status_var.set(f"Item {self.index+1} of {len(self.listings)}")

    def _open_url(self):
        url = self.url_var.get()
        if url:
            webbrowser.open(url)

    def _accept(self):
        title = self.title_var.get().strip()
        url = self.url_var.get().strip()
        price = self.price_var.get().strip()
        try:
            price_val = int(price) if price else None
        except Exception:
            price_val = None
        cur = self.cur_var.get().strip() or None
        loc = self.loc_var.get().strip() or None
        self.result.append((title, url, price_val, cur, loc))
        self.index += 1
        self._load_current()

    def _decline(self):
        self.index += 1
        self._load_current()

    def _next(self):
        if self.index < len(self.listings) - 1:
            self.index += 1
            self._load_current()

    def _prev(self):
        if self.index > 0:
            self.index -= 1
            self._load_current()

    def _finish(self):
        if self._closed:
            return
        self._closed = True
        try:
            # End mainloop and destroy window to allow next GUI to start cleanly
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        # center window
        try:
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            ws = self.root.winfo_screenwidth()
            hs = self.root.winfo_screenheight()
            x = (ws // 2) - (w // 2)
            y = (hs // 2) - (h // 2)
            self.root.geometry(f'+{x}+{y}')
        except Exception:
            pass
        self.root.mainloop()
        # Safety: ensure window is destroyed when mainloop exits
        self._finish()


def review_listings(listings: List[Tuple[str, str, Optional[int], Optional[str], Optional[str], Optional[str]]]):
    if not listings:
        return []
    gui = ReviewGUI(listings)
    gui.run()
    # Results collected before window was destroyed
    return gui.result
