# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

StegoCrypt hides AES-encrypted messages or files in the least significant bits (LSBs) of images and videos. It ships as a Tkinter GUI (packaged with PyInstaller + Inno Setup for Windows) plus a CLI that uses the same backend. It is a flat set of Python modules at the repo root: no package and no tests. GitHub: `Madmartigan1/stegocrypt`.

Dependencies: `pip install -r requirements.txt` (`docs/requirements.txt` is an identical copy and is the one CI reads, so keep both in sync). An external `ffmpeg` must be on PATH for video output. CI builds with Python 3.11; local development has used 3.13.

## Commands

```bash
python main.py                                   # launch GUI
python stego_cli.py embed   -i cover.png -o out.png -p PWD -m "text"      # or -f file
python stego_cli.py extract -i out.png -p PWD [-o recovered.bin]
# shared flags: --lsb 1-3, --no-spread, --use-ecc [--rs-nsym 32], --chunk-frames 90, --verbose
# embed only (video): --codec h264rgb|ffv1

powershell -File scripts/build_win.ps1           # local Inno Setup build from existing dist/ (run from repo root)
```

**Releases are built by CI**, not locally. Pushing a `vX.Y.Z` tag runs `.github/workflows/build-{windows,macos,linux}.yml`. The Windows job runs PyInstaller with command-line flags (`--windowed --collect-submodules=cv2 ...`, entry `main.py`), so `*.spec` files are gitignored and unused. It then runs Inno Setup with `/DMyAppVersion=<tag>` and attaches `Windows-StegoCrypt-Setup.exe` to the GitHub release. Past code changes were web-uploaded, and one upload silently dropped an import. Commit through git instead.

There is no test suite. `media/` holds the user's local test media (a few short MP4/M4V clips and PNG screenshots). It is untracked, so never commit it; trim clips with ffmpeg before testing, because embedding writes every frame out as a PNG. Check changes with a CLI round-trip (embed, then extract, then compare bytes) on a generated cover image and a short video. Cover the non-default `--lsb`, `--no-spread` and `--codec ffv1` options too. For ECC, flip a few random LSBs outside the first 256 slots of a stego PNG and check that `--use-ecc` still extracts the data. Also keep a stego file made by the previous release around, to check backward compatibility.

## Architecture

**Payload layout** (`payload_format.build_payload` / `parse_payload`, `crypto_utils`):
```
no ECC:   MAGIC "STEGVID3" (8) | u64be payload_len (8) | salt(16) | nonce(12) | AES-GCM ciphertext | tag(16)
with ECC: MAGIC "STEGVID3" (8) | u64be payload_len (8) | salt(16) | RS_nsym( nonce | ciphertext | tag )
ciphertext decrypts to: "SC01" | u16be name_len | filename | secret
```
The key comes from PBKDF2-SHA256 (200k iterations) using the salt. `HEADER_LEN` = magic + length = 16 bytes. `payload_len` counts everything after the header, so the bit-placement code does not need to know whether ECC is on.

**ECC is encrypt-then-RS** (changed after v1.0.7). Reed-Solomon (`reedsolo`, 255-byte codewords, `nsym` 1–254 parity bytes per codeword, which corrects up to `nsym/2` bad bytes per codeword) wraps the encrypted bytes, so carrier bit errors are fixed before the GCM tag is checked. The salt is left raw because it seeds the permutation before anything can be decoded. The header and salt are **not** protected, so a single flipped bit in the first 256 slots is fatal. With `use_rs`, `parse_payload` tries the new layout first and then falls back to the legacy one (≤ v1.0.7: RS applied to the secret *inside* GCM), so old ECC files still extract. Files with ECC made by the new code **cannot** be read by v1.0.7 or earlier. ECC only covers sparse bit flips. It does not let a payload survive lossy re-encoding (JPEG, H.264 at crf > 0, resizing).

**Bit placement** is the part that spans files, and embed and extract must mirror each other exactly:
- A "slot" is one bit position. Slot `s` maps to carrier byte `s // lsb`, bit `s % lsb`, over the flattened RGB (image) or BGR (OpenCV video) array.
- The header and salt are written **sequentially** from slot 0. This lets the extractor read the length and salt before it knows anything else, and auto-detect `lsb` by trying 1/2/3 until MAGIC matches.
- The remaining bits are **scattered** with `spread_utils.permuted_indices(total, seed, take)`, where `seed = password + salt`. Changing slot counts, the seed, or the sampling algorithm in `permuted_indices` breaks every existing stego file.
- Image (`stego_image.py`): one permutation over all slots after header+salt.
- Video (`stego_video.py`): streamed in chunks of `chunk_frames` frames. The first batch holds only header+salt, and its spare capacity is deliberately left unused. Each later chunk `k` gets its own permutation seeded by `chunk_seed(seed_base, k)`. So `--chunk-frames` has to be the same for embed and extract (GUI hard-codes 90, CLI defaults to 90, while the function default is 60).

**Lossless output is mandatory.** Images are always saved as PNG, whatever extension was given. Video goes through `ffmpeg_wrap.LosslessWriter`: frames are dumped as PNGs to a temp dir, then ffmpeg encodes them with `libx264rgb -crf 0` or `ffv1` (rgb24, all-intra). h264rgb output is forced to `.mkv`. Without ffmpeg it falls back to OpenCV/MJPG, which is lossy and breaks extraction. After writing, `_quick_header_magic_ok` re-reads the video to check the header survived.

**Settings that are not stored in the file:** `spread`, `use_ecc`/`rs_nsym`, and (for video) `chunk_frames` must be passed identically at extract time. Only `lsb` is auto-detected.

**GUI vs CLI:** `app_gui.App.run` duplicates the CLI's dispatch logic (extension → image/video, text-vs-binary output handling) rather than sharing it, so behaviour changes usually need applying in both places. Only the GUI passes `orig_name` to `build_payload`.

## Known issues (as of 2026-11)

- Release v1.0.6 cannot embed into images (missing `bytes_to_bits` import), and its image extraction fails for LSB 2/3 unless `--lsb` is passed. Both are fixed in v1.0.7 (PR #16).
- Fixed on `main` after v1.0.7 (2026-11, PR #19): Reed-Solomon used to be applied inside the AES-GCM envelope, so any bit error failed the GCM tag and ECC did nothing. See "ECC is encrypt-then-RS" above.
- The header and salt (the first 256 slots) have no error protection.
- `Image.fromarray(arr, "RGB")` (in `stego_image.py`) raises a Pillow deprecation warning because the `mode` argument is due for removal in Pillow 13. `requirements.txt` is unpinned, so CI could pick up a Pillow version that breaks it.
- Video embedding truncates the output and drops audio (found 2026-11-24). The embed loop in `stego_video.embed_video_streaming` stops reading frames once the payload is written, so every frame after the last payload chunk is never copied to the output. `LosslessWriter` also never copies the audio. Example: a 13.2 s, 396-frame clip came out as 3.03 s, 91 frames (1 header frame + one 90-frame chunk), silent, and about 100 MB. Extraction still works. To fix it, copy the remaining frames through unchanged and mux the source audio in the ffmpeg step; bit placement does not need to change.
- The CLI does not pass `orig_name` to `build_payload`, so filenames are not preserved. Embedded files that are valid UTF-8 are printed to stdout rather than saved.
