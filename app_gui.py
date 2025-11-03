# app_gui.py
import os, sys, traceback
from tkinter import Tk, Frame, Label, Button, Entry, Text, END, filedialog, StringVar, IntVar, BooleanVar, ttk, messagebox
from payload_format import build_payload
from stego_image import embed_image, extract_image
from stego_video import embed_video_streaming, extract_video_streaming

import platform
import tkinter.font as tkfont

def human_status(done, total):
    p = 0 if total==0 else int((done/total)*100)
    return f"{p}%"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("StegoCrypt — Secrets in Plain Sight")
        #self.root.geometry("820x560")
        # Subtle, modern default look (font + theme + paddings)
        self._setup_styles()
        # A thin color band that changes with mode (Embed=blue, Extract=green)
        self.mode_band = Frame(self.root, height=3, bg="#1565c0")  # default Embed blue
        self.mode_band.pack(fill="x", side="top")
        self.mode      = StringVar(value="embed")
        self.file_in   = StringVar()
        self.file_out  = StringVar()
        self.password  = StringVar()
        self.lsb       = IntVar(value=1)
        self.use_spread= BooleanVar(value=True)
        self.use_ecc   = BooleanVar(value=False)
        self.rs_nsym   = IntVar(value=32)
        self.codec_sel = StringVar(value="h264rgb")  # 'h264rgb' or 'ffv1'
        self.pref_save_text = BooleanVar(value=False) # prefer saving extracted text to file
        self.status    = StringVar(value="Ready")
        self._polish_platform()
        self._build()
        self._update_mode_fields()  # set initial state
        self._apply_mode_band()      # set initial band color
        self._autosize_to_contents()

    def _polish_platform(self):
        """Light platform-specific cosmetics, especially for macOS."""
        # HiDPI scaling
        try:
            if sys.platform == "darwin":
                # Slightly larger scaling looks better on Retina
                self.root.tk.call("tk", "scaling", 1.2)
                # Prefer unified titlebar for a native feel (best-effort)
                try:
                    self.root.tk.call("::tk::unsupported::MacWindowStyle", "style",
                                      self.root._w, "unified", "document")
                except Exception:
                    pass
                # Use system font if available (falls back silently)
                for f in ("TkDefaultFont","TkTextFont","TkMenuFont","TkHeadingFont"):
                    try:
                        ff = tkfont.nametofont(f)
                        ff.configure(family="SF Pro Text", size=13)
                    except Exception:
                        pass
            else:
                # Slight overall bump on Win/Linux
                self.root.tk.call("tk", "scaling", 1.1)
        except Exception:
            pass

        # ttk theme & padding
        try:
            style = ttk.Style(self.root)
            if sys.platform == "darwin":
                try:
                    style.theme_use("aqua")     # native macOS look
                except Exception:
                    style.theme_use("clam")
            else:
                try:
                    style.theme_use("vista")    # Windows; on Linux this may no-op
                except Exception:
                    style.theme_use("clam")

            pad = 6 if sys.platform == "darwin" else 4
            style.configure("TLabel", padding=pad)
            style.configure("TButton", padding=(10,6))
            style.configure("TEntry", padding=4)
            style.configure("TCheckbutton", padding=pad)
            style.configure("TRadiobutton", padding=pad)
            style.configure("Horizontal.TProgressbar", thickness=14)
        except Exception:
            pass

    def _setup_styles(self):
        """Pick a sane ttk theme and set gentle, consistent UI styling."""
        # 1) Safe default font: modify the named Tk default font in-place
        try:
            base = tkfont.nametofont("TkDefaultFont")
            #if sys.platform.startswith("win"):
             #   base.configure(family="Segoe UI", size=9)
            #else:
                # keep platform family, just normalize size
             #   base.configure(size=9)
             # Make the default font ~3pt larger for readability across platforms
            cur_size = base.cget("size")
            try:
                new_size = int(cur_size) + 3
            except Exception:
                new_size = 12
            base.configure(size=new_size)
        except Exception:
            # If anything fails, we just keep the system default
            pass
            
        style = ttk.Style(self.root)
        
        # 2) Theme: 'vista' looks best on Windows; fallback to 'clam' elsewhere
        try:
            if sys.platform.startswith("win") and "vista" in style.theme_names():
                style.theme_use("vista")
            else:
                style.theme_use("clam")
        except Exception:
            # in case the theme isn't available, ignore
            pass
            
        # 3) Gentle control styling
        style.configure("TButton", padding=(8, 4))
        style.configure("TProgressbar", thickness=8)  # a touch thicker
        style.configure("TEntry", padding=2)

    def _apply_mode_band(self):
        """Color accent at the top: blue for Embed, green for Extract."""
        color = "#1565c0" if self.mode.get().lower() == "embed" else "#2e7d32"
        try:
            self.mode_band.configure(bg=color)
        except Exception:
            pass

    def _build(self):
        top = Frame(self.root); top.pack(fill="x", padx=10, pady=8)
        # Use a tight 3-column grid: [Label] [Entry expands] [Browse button]
        try:
            top.grid_columnconfigure(0, weight=0)
            top.grid_columnconfigure(1, weight=1)  # entries stretch
            top.grid_columnconfigure(2, weight=0)
        except Exception:
            pass

        # Row 0: Mode + pref checkbox (right-aligned)
        Label(top, text="Mode:").grid(row=0, column=0, sticky="w", padx=(0,6))
        mframe = Frame(top)
        mframe.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(mframe, text="Embed",  variable=self.mode, value="embed").pack(side="left")
        ttk.Radiobutton(mframe, text="Extract", variable=self.mode, value="extract").pack(side="left", padx=(8,0))
        ttk.Checkbutton(top, text="Prefer saving extracted text", variable=self.pref_save_text)\
                        .grid(row=0, column=2, sticky="e")

        # Row 1: Input
        Label(top, text="Input:").grid(row=1, column=0, sticky="w", padx=(0,6))
        in_frame = Frame(top)
        in_frame.grid(row=1, column=1, columnspan=2, sticky="ew")
        in_frame.grid_columnconfigure(0, weight=1)
        Entry(in_frame, textvariable=self.file_in).grid(row=0, column=0, sticky="ew")
        Button(in_frame, text="Browse…", command=self.browse_in).grid(row=0, column=1, sticky="e", padx=(6,0))

        # Row 2: Output (embed only)
        Label(top, text="Output (embed only):").grid(row=2, column=0, sticky="w", padx=(0,6))
        out_frame = Frame(top)
        out_frame.grid(row=2, column=1, columnspan=2, sticky="ew")
        out_frame.grid_columnconfigure(0, weight=1)
        self.output_entry = Entry(out_frame, textvariable=self.file_out)
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_button = Button(out_frame, text="Browse…", command=self.browse_out)
        self.output_button.grid(row=0, column=1, sticky="e", padx=(6,0))

        Label(top, text="Password:").grid(row=3, column=0, sticky="w")
        Entry(top, textvariable=self.password, show="*").grid(row=3, column=1, sticky="ew")
        Label(top, text="LSB/bpp:").grid(row=4, column=0, sticky="w", padx=(0,6))
        oline = Frame(top); oline.grid(row=4, column=1, sticky="w")
        ttk.Spinbox(oline, from_=1, to=3, textvariable=self.lsb, width=5).pack(side="left")
        ttk.Checkbutton(oline, text="Spread (stealth)", variable=self.use_spread).pack(side="left", padx=(8,0))
        ttk.Checkbutton(oline, text="ECC (Reed–Solomon)", variable=self.use_ecc).pack(side="left", padx=(8,0))
        
        # ECC parity (put label+entry in a tiny frame to avoid overlapping the same grid cell)
        pframe = Frame(top)
        pframe.grid(row=4, column=2, sticky="e")
        Label(pframe, text="ECC parity:").pack(side="left", padx=(0,6))
        Entry(pframe, textvariable=self.rs_nsym, width=6).pack(side="left")
        

        # Lossless codec selector
        Label(top, text="Lossless codec:").grid(row=5, column=0, sticky="w", pady=(4, 0), padx=(0,6))
        self.codec_cb = ttk.Combobox(
            top,
            textvariable=self.codec_sel,
            width=10,
            values=("h264rgb", "ffv1"),
            state="readonly"
        )
        self.codec_cb.grid(row=5, column=1, sticky="w", padx=(0, 8), pady=(4, 0))
        Label(top, text="(h264rgb = smaller; ffv1 = largest)")\
            .grid(row=5, column=2, sticky="e", pady=(4, 0))
        mid = Frame(self.root); mid.pack(fill="both", expand=True, padx=10, pady=6)
        Label(mid, text="Message to embed (leave empty to embed a file):").pack(anchor="w")
        self.msg = Text(mid, height=6); self.msg.pack(fill="both", expand=True)

        btns = Frame(mid); btns.pack(fill="x", pady=8)
        # Left-align action buttons to avoid empty gray space on the right
        Button(btns, text="Run",   command=self.run,  width=14).pack(side="left")
        Button(btns, text="Usage", command=self.show_usage, width=10).pack(side="left", padx=6)
        Button(btns, text="Help",  command=self.help).pack(side="left", padx=6)
        Button(btns, text="Clear", command=self.clear).pack(side="left", padx=6)

        self.prog = ttk.Progressbar(self.root, length=640); self.prog.pack(pady=6)
        Label(self.root, textvariable=self.status).pack()

        # react to mode changes (Embed/Extract) and toggle output widgets
        def on_mode_change(*_):
            self._update_mode_fields()
            self._apply_mode_band()
        try:
            self.mode.trace_add("write", on_mode_change)  # py3.8+
        except Exception:
            self.mode.trace("w", on_mode_change)          # older Tk fallback

    def _autosize_to_contents(self):
        """
        Let Tk compute the natural size of the widgets, then fix the window to it.
        This avoids platform-specific small default windows on macOS/Linux.
        """
        try:
            self.root.update_idletasks()
            req_w = self.root.winfo_reqwidth()
            req_h = self.root.winfo_reqheight()
            self.root.geometry(f"{req_w}x{req_h}")
            self.root.minsize(req_w, req_h)
        except Exception:
            pass

    def _update_mode_fields(self):
        """Disable Output widgets in Extract mode; enable in Embed mode."""
        is_extract = (self.mode.get().lower() == "extract")
        state = "disabled" if is_extract else "normal"
        self.output_entry.configure(state=state)
        self.output_button.configure(state=state)
        if is_extract:
            self.file_out.set("")  # clear to avoid confusion

    def browse_in(self):
        f = filedialog.askopenfilename(
            title="Select image or video",
            filetypes=[("Media","*.png *.jpg *.jpeg *.bmp *.gif *.mp4 *.avi *.mkv *.mov"), ("All","*.*")]
        )
        if f:
            self.file_in.set(f)
            base, ext = os.path.splitext(f)
            # Only suggest Output in Embed mode
            if self.mode.get().lower() == "embed":
                self.file_out.set(base + ("_gen.png" if ext.lower() in [".png",".bmp",".tiff",".gif",".jpg",".jpeg"] else "_gen.mkv"))
            else:
                self.file_out.set("")

    def browse_out(self):
        # Only used in Embed mode; in Extract mode this widget is disabled
        f = filedialog.asksaveasfilename(title="Save as", filetypes=[("All","*.*")])
        if f:
            self.file_out.set(f)

    def _progress(self, a, b):
        self.prog['value'] = 0 if b<=0 else (a/b)*100
        self.status.set(f"Working… {human_status(a,b)}")
        self.root.update_idletasks()

    def run(self):
        try:
            self.prog['value']=0; self.status.set("Working…")
            mode = self.mode.get()
            inp, outp = self.file_in.get().strip(), self.file_out.get().strip()
            if not inp or not os.path.exists(inp): raise RuntimeError("Select a valid input file")
            if mode.lower()=="embed" and not outp: raise RuntimeError("Select an output path")

            lsb = int(self.lsb.get()); spread = self.use_spread.get()
            use_rs = self.use_ecc.get(); rs_nsym = int(self.rs_nsym.get()) if use_rs else 0
            pwd = self.password.get()
            msg = self.msg.get("1.0", END).strip()

            _, ext = os.path.splitext(inp.lower())

            if mode.lower() == "embed":
                # Prepare secret + remember original name if embedding a file
                orig_name = None
                if msg:
                    secret = msg.encode("utf-8")
                else:
                    fsel = filedialog.askopenfilename(title="Select file to embed")
                    if not fsel:
                        self.status.set("Cancelled"); return
                    with open(fsel, "rb") as fh:
                        secret = fh.read()
                    orig_name = os.path.basename(fsel)

                full = build_payload(secret, pwd, use_rs=use_rs, rs_nsym=rs_nsym, orig_name=orig_name)

                if ext in [".png",".jpg",".jpeg",".bmp",".gif",".tiff"]:
                    # Pre-check capacity so we can give a friendly message
                    from PIL import Image
                    import numpy as _np
                    img = Image.open(inp).convert("RGB")
                    arr = _np.array(img, dtype=_np.uint8)
                    total_slots = arr.size * lsb            # pixels*3 * lsb
                    needed_bits = len(full) * 8             # header+salt+ciphertext
                    if needed_bits > total_slots:
                        messagebox.showerror(
                            "Too large for image",
                            "The selected secret is too large for this image with the current LSB setting.\n\n"
                            "→ Try using a video container instead (FFV1 for maximum robustness or H264RGB for a smaller file)."
                        )
                        self.status.set("Ready"); self.prog['value']=0
                        return

                    # Embed (image path raises ValueError with 'capacity' too, just in case)
                    try:
                        embed_image(inp, outp, full, pwd, lsb=lsb, spread=spread, progress=self._progress)
                    except ValueError as e:
                        msg_err = str(e).lower()
                        if "too large" in msg_err or "capacity" in msg_err:
                            messagebox.showerror("Too large for image",
                                "The selected secret is too large for this image with the current LSB.\n\n"
                                "→ Use a video container (FFV1/H264RGB).")
                            self.status.set("Ready"); self.prog['value']=0
                            return
                        raise
                    messagebox.showinfo("Done", f"Embedded into image:\n{outp}")
                else:
                    # Video: support both ffv1 (lossless) and h264rgb (smaller)
                    try:
                        embed_video_streaming(inp, outp, full, pwd, lsb=lsb, spread=spread,
                                              chunk_frames=90, codec=self.codec_sel.get(), progress=self._progress)
                    except ValueError as e:
                        # Extremely unlikely here, but mirror image behavior
                        msg_err = str(e).lower()
                        if "too large" in msg_err or "capacity" in msg_err:
                            messagebox.showerror(
                                "Too large for this video",
                                "The selected secret is too large for this video with current settings.\n\n"
                                "Try a longer/higher-resolution video, reduce LSB=1, or split the file."
                            )
                        else:
                            raise
                    else:
                        messagebox.showinfo("Done", f"Embedded into video:\n{outp}")

            else:  # extract
                if ext in [".png",".jpg",".jpeg",".bmp",".gif",".tiff"]:
                    pt, meta = extract_image(
                        inp, pwd, use_rs=use_rs, rs_nsym=rs_nsym, lsb=lsb, spread=spread, progress=self._progress
                    )
                else:
                    pt, meta = extract_video_streaming(
                        inp, pwd, lsb=lsb, spread=spread, chunk_frames=90,
                        use_rs=use_rs, rs_nsym=rs_nsym, progress=self._progress
                    )

                # Decide text vs binary, and whether to show popup or force save
                orig_name = meta.get("filename") or ""
                # Preserve original extension in Save dialog if we have a name
                base, orig_ext = os.path.splitext(orig_name)

                def _filetypes_for(ext: str):
                    # Prefer the embedded type first; always allow All files
                    if ext:
                        pat = f"*{ext.lower()}"
                        label = f"{ext.lower()} files"
                        return [(label, pat), ("All files", "*.*")]
                    return [("All files", "*.*")]
                try:
                    text = pt.decode("utf-8")
                    # If an original filename exists, treat this as a file and force save (no big popup)
                    if orig_name:
                        init = orig_name
                        out = filedialog.asksaveasfilename(
                            title="Save extracted file",
                            initialfile=init,
                            defaultextension=orig_ext or "",
                            filetypes=_filetypes_for(orig_ext)
                        )
                        if out:
                            # If user saves as .txt, write text; otherwise write bytes
                            if out.lower().endswith(".txt"):
                                with open(out, "w", encoding="utf-8") as fh:
                                    fh.write(text)
                            else:
                                with open(out, "wb") as fh:
                                    fh.write(pt)
                            messagebox.showinfo("Saved", f"File saved to:\n{out}")
                    else:
                        # No original filename: it was typed-in text
                        if len(text) <= 48:
                            # Small strings get a simple popup
                            messagebox.showinfo("Extracted text", text)
                        else:
                            # Longer strings: avoid huge popups, force a save dialog
                            out = filedialog.asksaveasfilename(
                                title="Save extracted text",
                                initialfile="extracted.txt",
                                defaultextension=".txt",
                                filetypes=[("Text file","*.txt"), ("All files","*.*")]
                            )
                            if out:
                                with open(out, "w", encoding="utf-8") as fh:
                                    fh.write(text)
                                messagebox.showinfo("Saved", f"Text saved to:\n{out}")
                except UnicodeDecodeError:
                    # Binary data — force a save dialog; prefer original name if present
                    init = orig_name if orig_name else "extracted.bin"
                    out = filedialog.asksaveasfilename(
                        title="Save extracted file",
                        initialfile=init,
                        defaultextension=orig_ext or (".bin" if orig_name else ""),
                        filetypes=_filetypes_for(orig_ext) if orig_name else [("All files","*.*")]
                    )
                    if out:
                        with open(out, "wb") as fh:
                            fh.write(pt)
                        messagebox.showinfo("Saved", f"File saved to:\n{out}")
                                
            self.status.set("Done")
            self.prog['value']=0
        except Exception as e:
            traceback.print_exc()
            self.status.set("Error")
            self.prog['value']=0
            messagebox.showerror("Error", str(e))

    def help(self):
        messagebox.showinfo("Notes",
            "- For stealth, keep LSB=1 and enable Spread.\n"
            "- Video codec:\n"
            "    • FFV1  — Lossless (largest files, best robustness)\n"
            "    • H264RGB — Smaller output (still safe for our per-pixel writes)\n\n"
            "- Requires ffmpeg in PATH for video muxing.\n"
            "- ECC adds parity (larger payload) to correct some errors.\n"
            "- Header + salt are stored sequentially; the rest is pseudo-randomly spread.\n"
            "- Streaming mode processes frames in chunks—safe for long videos."
        )
        
    def show_usage(self):
        msg = (
            "To embed secret:\n"
            "- Input: Choose your image or video file\n"
            "- Output: Same location by default or choose destination\n"
            "- Set a good password (i.e., Gh34-u!r7)\n"
            "- Enter secret phrase or leave blank to embed a secret file\n"
            "- Click Run\n\n"
            "To extract secret:\n"
            "- Input: Choose the generated image or video\n"
            "- Output: Disabled (not needed)\n"
            "- Enter password shared secretly by sender\n"
            "- Click Run"
        )
        try:
            messagebox.showinfo("Usage", msg)
        except Exception:
            # Fallback: set status if messagebox can't open (headless envs, etc.)
            self.status.set("Usage:\n" + msg.replace("\n", " | "))

    def clear(self):
        self.msg.delete("1.0", END)
        self.file_in.set(""); self.file_out.set(""); self.password.set("")
        self.status.set("Ready"); self.prog['value']=0

