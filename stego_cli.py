#!/usr/bin/env python3
"""
stego_cli.py — Command-line interface for the Stego GUI backend.

Usage:
  Embed text:
    python stego_cli.py embed -i cover.mp4 -o cover_stego.mkv -p "MyPwd" -m "Meet at 10" --codec h264rgb

  Embed file:
    python stego_cli.py embed -i cover.png -o cover_stego.png -p hunter2 -f secret.pdf

  Extract (prints text to stdout if UTF-8, writes binary to --out or default):
    python stego_cli.py extract -i cover_stego.mkv -p "MyPwd"
    python stego_cli.py extract -i cover_stego.png -p hunter2 --out recovered.bin
"""

import os
import sys
import argparse
import traceback

from payload_format import build_payload
from stego_image import embed_image, extract_image
from stego_video import embed_video_streaming, extract_video_streaming
from ecc_utils import REED_OK

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov"}

def is_image(path: str) -> bool:
    return os.path.splitext(path.lower())[1] in IMAGE_EXTS

def is_video(path: str) -> bool:
    return os.path.splitext(path.lower())[1] in VIDEO_EXTS

def progress_printer_factory(verbose: bool):
    if not verbose:
        return None
    def printer(done: int, total: int):
        pct = 0 if total <= 0 else int(done * 100 / total)
        print(f"[progress] {pct}% ({done}/{total})", flush=True)
    return printer

def do_embed(args: argparse.Namespace) -> int:
    if not os.path.exists(args.in_path):
        print(f"[error] Input not found: {args.in_path}", file=sys.stderr)
        return 2
    if not args.out_path:
        print("[error] --out is required for embed mode", file=sys.stderr)
        return 2
    if not args.password:
        print("[error] --password is required", file=sys.stderr)
        return 2
    if (args.message is None) == (args.embed_file is None):
        print("[error] Provide exactly one of --message or --embed-file", file=sys.stderr)
        return 2
    if not (1 <= args.lsb <= 3):
        print("[error] --lsb must be 1, 2, or 3", file=sys.stderr)
        return 2
    if args.use_ecc and not REED_OK:
        print("[error] ECC requested but 'reedsolo' is not installed.", file=sys.stderr)
        return 2

    # Build secret bytes
    if args.message is not None:
        secret = args.message.encode("utf-8")
        if args.verbose:
            print(f"[info] Embedding message of {len(secret)} bytes")
    else:
        if not os.path.exists(args.embed_file):
            print(f"[error] Embed file not found: {args.embed_file}", file=sys.stderr)
            return 2
        with open(args.embed_file, "rb") as fh:
            secret = fh.read()
        if args.verbose:
            print(f"[info] Embedding file '{args.embed_file}' ({len(secret)} bytes)")

    # Build payload (header + encrypted, optionally ECC)
    try:
        full = build_payload(secret, args.password, use_rs=args.use_ecc, rs_nsym=args.rs_nsym)
    except Exception as e:
        print(f"[error] Failed to build payload: {e}", file=sys.stderr)
        if args.verbose: traceback.print_exc()
        return 3

    spread = not args.no_spread
    prog = progress_printer_factory(args.verbose)

    try:
        if is_image(args.in_path):
            # Image out must be image (usually .png)
            if args.verbose:
                print(f"[info] Embedding into image → {args.out_path} (lsb={args.lsb}, spread={spread})")
            embed_image(args.in_path, args.out_path, full, args.password, lsb=args.lsb, spread=spread, progress=prog)
        elif is_video(args.in_path):
            # Video: use streaming; codec h264rgb (default) or ffv1
            if args.verbose:
                print(f"[info] Embedding into video → {args.out_path} (lsb={args.lsb}, spread={spread}, codec={args.codec}, chunk_frames={args.chunk_frames})")
            embed_video_streaming(
                args.in_path, args.out_path, full, args.password,
                lsb=args.lsb, spread=spread, chunk_frames=args.chunk_frames,
                codec=args.codec, progress=prog
            )
        else:
            print("[error] Unsupported input extension. Use a common image or video.", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"[error] Embed failed: {e}", file=sys.stderr)
        if args.verbose: traceback.print_exc()
        return 4

    if args.verbose:
        print("[ok] Embed complete.")
    return 0

def do_extract(args: argparse.Namespace) -> int:
    if not os.path.exists(args.in_path):
        print(f"[error] Input not found: {args.in_path}", file=sys.stderr)
        return 2
    if not args.password:
        print("[error] --password is required", file=sys.stderr)
        return 2
    if not (1 <= args.lsb <= 3):
        print("[error] --lsb must be 1, 2, or 3", file=sys.stderr)
        return 2
    if args.use_ecc and not REED_OK:
        print("[error] ECC requested but 'reedsolo' is not installed.", file=sys.stderr)
        return 2

    spread = not args.no_spread
    prog = progress_printer_factory(args.verbose)

    try:
        if is_image(args.in_path):
            if args.verbose:
                print(f"[info] Extracting from image (lsb={args.lsb}, spread={spread})")
            pt_bytes, meta = extract_image(
                args.in_path,
                args.password,
                use_rs=args.use_ecc,
                rs_nsym=args.rs_nsym,
                lsb=args.lsb,
                spread=spread,
                progress=prog,
            )
        elif is_video(args.in_path):
            if args.verbose:
                print(f"[info] Extracting from video (lsb={args.lsb}, spread={spread}, chunk_frames={args.chunk_frames})")
            pt_bytes, meta = extract_video_streaming(
                args.in_path,
                args.password,
                lsb=args.lsb,
                spread=spread,
                chunk_frames=args.chunk_frames,
                use_rs=args.use_ecc,
                rs_nsym=args.rs_nsym,
                progress=prog,
            )
        else:
            print("[error] Unsupported input extension. Use a common image or video.", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"[error] Extraction failed: {e}", file=sys.stderr)
        if args.verbose: traceback.print_exc()
        return 5

    # Try to print as UTF-8 text; otherwise write to file
    try:
        text = pt_bytes.decode("utf-8")
        print(text)  # to stdout
        if args.verbose:
            print("[ok] Extracted UTF-8 text to stdout.")
        return 0
    except Exception:
        # Binary payload (raw bytes)
        out_path = args.out_path
        if not out_path:
            # Prefer filename from metadata, if present
            filename = None
            try:
                filename = meta.get("filename")
            except Exception:
                filename = None
            if filename:
                out_path = filename
            else:
                base, _ = os.path.splitext(args.in_path)
                out_path = base + "_secret.bin"
            if args.verbose:
                print(f"[info] No --out provided; writing binary to {out_path}")
        try:
            with open(out_path, "wb") as fh:
                fh.write(pt_bytes)
            if args.verbose:
                print(f"[ok] Extracted binary saved to: {out_path}")
            return 0
        except Exception as e:
            print(f"[error] Could not write binary output: {e}", file=sys.stderr)
            if args.verbose: traceback.print_exc()
            return 6

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Steganography (image/video) — CLI for the GUI backend")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Common flags helper
    def add_common(embed_parser: argparse.ArgumentParser, is_embed: bool):
        embed_parser.add_argument("-i", "--in", dest="in_path", required=True, help="Input image/video (cover for embed; stego for extract)")
        if is_embed:
            embed_parser.add_argument("-o", "--out", dest="out_path", required=True, help="Output stego image/video")
        else:
            embed_parser.add_argument("-o", "--out", dest="out_path", help="Output for extracted binary (if payload is not UTF-8 text)")
        embed_parser.add_argument("-p", "--password", dest="password", required=True, help="Password for encryption/decryption")
        embed_parser.add_argument("--lsb", type=int, default=1, help="LSBs per channel to use (1-3). Default: 1")
        embed_parser.add_argument("--no-spread", action="store_true", help="Disable pseudo-random spreading (default: enabled)")
        embed_parser.add_argument("--use-ecc", action="store_true", help="Enable Reed–Solomon ECC (optional; increases payload size)")
        embed_parser.add_argument("--rs-nsym", type=int, default=32, help="ECC parity bytes if --use-ecc (default: 32)")
        embed_parser.add_argument("--chunk-frames", type=int, default=90, help="Streaming chunk size (video) default: 90")
        embed_parser.add_argument("--verbose", action="store_true", help="Verbose progress output")

    # embed
    pe = sub.add_parser("embed", help="Embed message or file into an image/video")
    add_common(pe, is_embed=True)
    mgroup = pe.add_mutually_exclusive_group(required=True)
    mgroup.add_argument("-m", "--message", help="Inline UTF-8 message to embed")
    mgroup.add_argument("-f", "--embed-file", help="Path to file to embed")
    pe.add_argument("--codec", choices=("h264rgb", "ffv1"), default="h264rgb", help="Lossless video codec (default: h264rgb)")

    # extract
    px = sub.add_parser("extract", help="Extract secret from stego image/video")
    add_common(px, is_embed=False)
    # (no codec for extract)

    return p

def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "embed":
        return do_embed(args)
    elif args.cmd == "extract":
        return do_extract(args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
