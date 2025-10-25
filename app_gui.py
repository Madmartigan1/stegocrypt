# app_gui.py
import os, sys, traceback
from tkinter import font as tkfont
from tkinter import Tk, Frame, Label, Button, Entry, Text, END, filedialog, StringVar, IntVar, BooleanVar, ttk, messagebox
from payload_format import build_payload
from stego_image import embed_image, extract_image
from stego_video import embed_video_streaming, extract_video_streaming

def human_status(done, total):
    p = 0 if total==0 else int((done/total)*100)
    return f"{p}%"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Stego — Image/Video (PRNG spread, ECC, FFV1)")
        self.root.geometry("820x560")
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
        self.status    = StringVar(value="Ready")
        self._build()
        self._update_mode_fields()  # set initial state
        self._update_mode_fields()   # set initial state
        self._apply_mode_band()      # set initial band color

    def _setup_styles(self):
        """Pick a sane ttk theme and set gentle, consistent UI styling."""
        # 1) Safe default font: modify the named Tk default font in-place
        try:
            base = tkfont.nametofont("TkDefaultFont")
            if sys.platform.startswith("win"):
                base.configure(family="Segoe UI", size=9)
            else:
                # keep platform family, just normalize size
                base.configure(size=9)
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

        Label(top, text="Mode:").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(top, text="Embed",  variable=self.mode, value="embed").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(top, text="Extract", variable=self.mode, value="extract").grid(row=0, column=2, sticky="w")

        Label(top, text="Input:").grid(row=1, column=0, sticky="w")
        Entry(top, textvariable=self.file_in, width=60).grid(row=1, column=1, columnspan=3, sticky="w")
        Button(top, text="Browse...", command=self.browse_in).grid(row=1, column=4)

        # Output (embed only)
        Label(top, text="Output (embed only):").grid(row=2, column=0, sticky="w")
        self.output_entry  = Entry(top, textvariable=self.file_out, width=60)
        self.output_entry.grid(row=2, column=1, columnspan=3, sticky="w")
        self.output_button = Button(top, text="Browse...", command=self.browse_out)
        self.output_button.grid(row=2, column=4)

        Label(top, text="Password:").grid(row=3, column=0, sticky="w")
        Entry(top, textvariable=self.password, show="*", width=30).grid(row=3, column=1, sticky="w")

        Label(top, text="LSB/bpp:").grid(row=4, column=0, sticky="w")
        ttk.Spinbox(top, from_=1, to=3, textvariable=self.lsb, width=5).grid(row=4, column=1, sticky="w")
        ttk.Checkbutton(top, text="Spread (stealth)", variable=self.use_spread).grid(row=4, column=2, sticky="w")
        ttk.Checkbutton(top, text="ECC (Reed–Solomon)", variable=self.use_ecc).grid(row=4, column=3, sticky="w")
        Label(top, text="ECC parity:").grid(row=4, column=4, sticky="e")
        Entry(top, textvariable=self.rs_nsym, width=6).grid(row=4, column=5, sticky="w")

        # Lossless codec selector
        Label(top, text="Lossless codec:").grid(row=5, column=0, sticky="w", pady=(4, 0))
        self.codec_cb = ttk.Combobox(
            top,
            textvariable=self.codec_sel,
            width=10,
            values=("h264rgb", "ffv1"),
            state="readonly"
        )
        self.codec_cb.grid(row=5, column=1, sticky="w", padx=(0, 8), pady=(4, 0))
        Label(
            top,
            text="(h264rgb = smaller; ffv1 = largest)"
        ).grid(row=5, column=2, columnspan=3, sticky="w", pady=(4, 0))
        mid = Frame(self.root); mid.pack(fill="both", expand=True, padx=10, pady=6)
        Label(mid, text="Message to embed (leave empty to embed a file):").pack(anchor="w")
        self.msg = Text(mid, height=6); self.msg.pack(fill="x")

        btns = Frame(mid); btns.pack(fill="x", pady=8)
        Button(btns, text="Run",   command=self.run,  width=14).pack(side="left")
        Button(btns, text="Demo",  command=self.demo, width=10).pack(side="left", padx=6)
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
                self.file_out.set(base + ("_stego.png" if ext.lower() in [".png",".bmp",".tiff",".gif",".jpg",".jpeg"] else "_stego.mkv"))
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
                if msg:
                    secret = msg.encode("utf-8")
                else:
                    f = filedialog.askopenfilename(title="Select file to embed")
                    if not f: self.status.set("Cancelled"); return
                    with open(f, "rb") as fh: secret = fh.read()

                full = build_payload(secret, pwd, use_rs=use_rs, rs_nsym=rs_nsym)

                if ext in [".png",".jpg",".jpeg",".bmp",".gif",".tiff"]:
                    embed_image(inp, outp, full, pwd, lsb=lsb, spread=spread, progress=self._progress)
                    messagebox.showinfo("Done", f"Embedded into image:\n{outp}")
                else:
                    embed_video_streaming(inp, outp, full, pwd, lsb=lsb, spread=spread,
                                          chunk_frames=90, codec=self.codec_sel.get(),
                                          progress=self._progress)
                    messagebox.showinfo("Done", f"Embedded into video:\n{outp}")

            else:  # extract
                if ext in [".png",".jpg",".jpeg",".bmp",".gif",".tiff"]:
                    pt = extract_image(inp, pwd, use_rs=use_rs, rs_nsym=rs_nsym, lsb=lsb, spread=spread, progress=self._progress)
                else:
                    pt = extract_video_streaming(inp, pwd, lsb=lsb, spread=spread, chunk_frames=90,
                                                 use_rs=use_rs, rs_nsym=rs_nsym, progress=self._progress)
                try:
                    text = pt.decode("utf-8")
                    messagebox.showinfo("Extracted text", text)
                except Exception:
                    out = filedialog.asksaveasfilename(title="Save extracted file")
                    if out:
                        with open(out, "wb") as fh: fh.write(pt)
                        messagebox.showinfo("Saved", f"Extracted bytes saved to:\n{out}")
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
            "- For durability, use FFV1 (lossless). Requires ffmpeg in PATH.\n"
            "- ECC adds parity (larger payload) to correct some errors.\n"
            "- Header + salt are stored sequentially; the rest is pseudo-randomly spread.\n"
            "- Streaming mode processes frames in chunks—safe for long videos."
        )

    def clear(self):
        self.msg.delete("1.0", END)
        self.file_in.set(""); self.file_out.set(""); self.password.set("")
        self.status.set("Ready"); self.prog['value']=0

    def demo(self):
        """Make a tiny synthetic video, embed a test string, extract it back."""
        import numpy as np, cv2, tempfile
        self.status.set("Running demo…"); self.root.update_idletasks()
        h,w,F = 48,64,60
        tmpdir = tempfile.mkdtemp(prefix="stego_demo_")
        src = os.path.join(tmpdir, "src_demo.mkv")
        out = os.path.join(tmpdir, "out_demo.mkv")
        vw = cv2.VideoWriter(src, cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (w,h))
        for i in range(F):
            frame = (np.random.rand(h,w,3)*255).astype("uint8")
            vw.write(frame)
        vw.release()
        secret = b"Hello from the Stego demo!"
        if not self.password.get(): self.password.set("demo_pass_123")
        full = build_payload(secret, self.password.get(), use_rs=False, rs_nsym=0)
        embed_video_streaming(src, out, full, self.password.get(), lsb=1, spread=True, chunk_frames=30, codec=self.codec_sel.get())
        recovered = extract_video_streaming(out, self.password.get(), lsb=1, spread=True, chunk_frames=30, use_rs=False, rs_nsym=0)
        try:
            messagebox.showinfo("Demo Result", "Extracted:\n" + recovered.decode("utf-8"))
        except Exception:
            messagebox.showinfo("Demo Result", f"Extracted {len(recovered)} bytes.")
        self.status.set(f"Demo files in: {tmpdir}")
