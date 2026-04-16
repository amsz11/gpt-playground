#!/usr/bin/env python3
"""
extract_ipod.py — Extract songs from a mounted iPod with metadata intact.

Run without arguments for the GUI.
Run with paths for headless use:
    python extract_ipod.py /Volumes/MyiPod ~/Music/out
"""

import shutil
import subprocess
import sys
import threading
from pathlib import Path


AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".aiff", ".m4p"}

# ── palette ──────────────────────────────────────────────────────────────────
BG      = "#000000"
FG      = "#ffffff"
MUTED   = "#888888"
BORDER  = "#333333"
BTN_FG  = "#000000"
BTN_BG  = "#ffffff"
BTN_DIS = "#444444"
FONT    = ("Courier", 11)
FONT_SM = ("Courier", 10)
FONT_LG = ("Courier", 13, "bold")


# ── core logic ────────────────────────────────────────────────────────────────

def ensure_mutagen() -> None:
    try:
        import mutagen  # noqa: F401
        return
    except ImportError:
        pass

    # Try progressively more permissive install strategies
    strategies = [
        [sys.executable, "-m", "pip", "install", "--user", "mutagen"],
        [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "mutagen"],
    ]
    for cmd in strategies:
        try:
            subprocess.check_call(cmd)
        except Exception:
            continue

        # User site-packages may not be on sys.path yet — add it and retry
        import site, importlib
        user_site = site.getusersitepackages()
        if user_site not in sys.path:
            sys.path.insert(0, user_site)
        importlib.invalidate_caches()
        try:
            import mutagen  # noqa: F401
            return
        except ImportError:
            continue

    sys.exit(
        "Could not install mutagen automatically.\n"
        "Run this once, then retry:\n\n"
        "  pip install --user --break-system-packages mutagen\n"
    )


def sanitize(name: str) -> str:
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "Unknown"


def get_metadata(path: Path) -> dict:
    from mutagen import File as MutagenFile
    try:
        audio = MutagenFile(path, easy=True)
        if audio is None:
            return {}
        def first(tag):
            val = audio.get(tag)
            return val[0] if val else None
        track_raw = first("tracknumber") or ""
        track = track_raw.split("/")[0].strip() if track_raw else ""
        return {
            "title":  first("title"),
            "artist": first("artist"),
            "album":  first("album"),
            "track":  track,
        }
    except Exception:
        return {}


def find_ipod() -> Path | None:
    volumes = Path("/Volumes")
    if not volumes.exists():
        return None
    for vol in volumes.iterdir():
        if (vol / "iPod_Control").exists():
            return vol
    return None


def iter_audio_files(ipod_root: Path):
    music_src = ipod_root / "iPod_Control" / "Music"
    if not music_src.exists():
        return []
    return sorted(
        f for f in music_src.rglob("*")
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    )


def extract_all(ipod_root: Path, output_root: Path, log, on_done):
    """Run in a background thread. log(msg) streams lines to the GUI."""
    all_files = iter_audio_files(ipod_root)
    if not all_files:
        log("No audio files found.")
        on_done(0, 0)
        return

    log(f"Found {len(all_files)} files.\n")
    output_root.mkdir(parents=True, exist_ok=True)
    copied = errors = 0

    for i, src in enumerate(all_files, 1):
        meta    = get_metadata(src)
        artist  = sanitize(meta.get("artist") or "Unknown Artist")
        album   = sanitize(meta.get("album")  or "Unknown Album")
        title   = sanitize(meta.get("title")  or src.stem)
        track   = meta.get("track", "")
        ext     = src.suffix.lower()
        prefix  = f"{int(track):02d} - " if track.isdigit() else ""
        fname   = f"{prefix}{title}{ext}"

        dest_dir = output_root / artist / album
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / fname
        n = 1
        while dest.exists():
            dest = dest_dir / f"{prefix}{title} ({n}){ext}"
            n += 1

        try:
            shutil.copy2(src, dest)
            log(f"[{i:>4}]  {artist} / {fname}")
            copied += 1
        except Exception as exc:
            log(f"[ERR ]  {src.name}: {exc}")
            errors += 1

    on_done(copied, errors)


# ── GUI ───────────────────────────────────────────────────────────────────────

def launch_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.title("iPod Extractor")
    root.configure(bg=BG)
    root.resizable(False, False)

    pad = dict(padx=16, pady=6)

    # ── title ──
    tk.Label(root, text="iPOD EXTRACTOR", font=FONT_LG,
             bg=BG, fg=FG).grid(row=0, column=0, columnspan=3, pady=(18, 4))
    tk.Frame(root, bg=BORDER, height=1).grid(
        row=1, column=0, columnspan=3, sticky="ew", padx=16)

    def path_row(row, label, var, browse_fn):
        tk.Label(root, text=label, font=FONT_SM, bg=BG, fg=MUTED, anchor="w",
                 width=8).grid(row=row, column=0, **pad, sticky="w")
        tk.Entry(root, textvariable=var, font=FONT_SM, bg=BG, fg=FG,
                 insertbackground=FG, relief="flat", highlightthickness=1,
                 highlightcolor=FG, highlightbackground=BORDER,
                 width=38).grid(row=row, column=1, padx=(0, 6), pady=6)
        tk.Button(root, text="…", font=FONT_SM, bg=BG, fg=FG,
                  activebackground=FG, activeforeground=BG,
                  relief="flat", bd=0, cursor="hand2",
                  command=browse_fn).grid(row=row, column=2, padx=(0, 16), pady=6)

    ipod_var = tk.StringVar()
    out_var  = tk.StringVar(value=str(Path.home() / "Music" / "iPod_Extract"))

    detected = find_ipod()
    if detected:
        ipod_var.set(str(detected))

    def browse_ipod():
        d = filedialog.askdirectory(title="Select iPod volume")
        if d:
            ipod_var.set(d)

    def browse_out():
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            out_var.set(d)

    path_row(2, "iPod", ipod_var, browse_ipod)
    path_row(3, "Output", out_var, browse_out)

    tk.Frame(root, bg=BORDER, height=1).grid(
        row=4, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 0))

    # ── log box ──
    log_frame = tk.Frame(root, bg=BG)
    log_frame.grid(row=5, column=0, columnspan=3, padx=16, pady=(8, 0), sticky="nsew")

    scrollbar = tk.Scrollbar(log_frame, bg=BG, troughcolor=BORDER,
                             activebackground=FG, width=8)
    scrollbar.pack(side="right", fill="y")

    log_box = tk.Text(
        log_frame, font=FONT_SM, bg=BG, fg=FG, insertbackground=FG,
        relief="flat", highlightthickness=1, highlightbackground=BORDER,
        width=58, height=14, wrap="none", state="disabled",
        yscrollcommand=scrollbar.set,
    )
    log_box.pack(side="left", fill="both")
    scrollbar.config(command=log_box.yview)

    status_var = tk.StringVar(value="ready")
    tk.Label(root, textvariable=status_var, font=FONT_SM,
             bg=BG, fg=MUTED, anchor="w").grid(
        row=6, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")

    # ── buttons ──
    btn_frame = tk.Frame(root, bg=BG)
    btn_frame.grid(row=7, column=0, columnspan=3, pady=(8, 16))

    def make_btn(parent, text, cmd):
        return tk.Button(
            parent, text=text, font=FONT, bg=BTN_BG, fg=BTN_FG,
            activebackground=MUTED, activeforeground=BG,
            relief="flat", bd=0, padx=18, pady=6, cursor="hand2",
            command=cmd,
        )

    def log_append(msg: str):
        log_box.configure(state="normal")
        log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    def clear_log():
        log_box.configure(state="normal")
        log_box.delete("1.0", "end")
        log_box.configure(state="disabled")

    def on_done(copied, errors):
        status_var.set(f"done — {copied} extracted" + (f", {errors} errors" if errors else ""))
        log_append(f"\n  {copied} songs extracted" + (f", {errors} errors." if errors else "."))
        extract_btn.configure(state="normal", bg=BTN_BG, fg=BTN_FG)

    def start_extract():
        ipod_path = Path(ipod_var.get().strip())
        out_path  = Path(out_var.get().strip())

        if not ipod_path or not (ipod_path / "iPod_Control").exists():
            status_var.set("iPod not found at that path.")
            return

        clear_log()
        status_var.set("extracting…")
        extract_btn.configure(state="disabled", bg=BTN_DIS, fg=FG)
        log_append(f"  iPod:   {ipod_path}")
        log_append(f"  Output: {out_path}\n")

        threading.Thread(
            target=extract_all,
            args=(ipod_path, out_path,
                  lambda m: root.after(0, log_append, m),
                  lambda c, e: root.after(0, on_done, c, e)),
            daemon=True,
        ).start()

    extract_btn = make_btn(btn_frame, "EXTRACT", start_extract)
    extract_btn.pack(side="left", padx=6)
    make_btn(btn_frame, "CLEAR", clear_log).pack(side="left", padx=6)

    root.mainloop()


# ── headless entry ────────────────────────────────────────────────────────────

def headless(ipod_root: Path, output_root: Path) -> None:
    all_files = iter_audio_files(ipod_root)
    if not all_files:
        sys.exit("No audio files found.")
    print(f"Found {len(all_files)} files.\n")
    output_root.mkdir(parents=True, exist_ok=True)
    copied = errors = 0
    for i, src in enumerate(all_files, 1):
        meta    = get_metadata(src)
        artist  = sanitize(meta.get("artist") or "Unknown Artist")
        album   = sanitize(meta.get("album")  or "Unknown Album")
        title   = sanitize(meta.get("title")  or src.stem)
        track   = meta.get("track", "")
        ext     = src.suffix.lower()
        prefix  = f"{int(track):02d} - " if track.isdigit() else ""
        fname   = f"{prefix}{title}{ext}"
        dest_dir = output_root / artist / album
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / fname
        n = 1
        while dest.exists():
            dest = dest_dir / f"{prefix}{title} ({n}){ext}"
            n += 1
        try:
            shutil.copy2(src, dest)
            print(f"[{i:>4}]  {artist} / {fname}")
            copied += 1
        except Exception as exc:
            print(f"[ERR ]  {src.name}: {exc}", file=sys.stderr)
            errors += 1
    print(f"\nDone: {copied} extracted" + (f", {errors} errors" if errors else "") + f"\nOutput: {output_root}")


def main() -> None:
    ensure_mutagen()
    if len(sys.argv) == 3:
        headless(Path(sys.argv[1]), Path(sys.argv[2]))
    elif len(sys.argv) == 1:
        launch_gui()
    else:
        sys.exit("Usage: python extract_ipod.py [<ipod_path> <output_path>]")


if __name__ == "__main__":
    main()
