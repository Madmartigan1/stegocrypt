# StegoCrypt

Steganography hides the existence of data, while encryption protects its content. StegoCrypt combines both — hiding encrypted messages or files inside images or videos using password-protected, pixel-level steganography.

✅ GUI app for Windows, MacOS and Linux • Optional CLI • Lossless output for reliable extraction.

[![Download](https://img.shields.io/github/v/tag/Madmartigan1/stegocrypt?label=Download%20Installer)](../../releases/latest)
  
---

**Note on security**: Even if you use a weak password such as "hello", an attacker who doesn’t know there’s anything hidden may not look for it. That’s the beauty of steganography — security through obscurity at the visual/statistical level.
However, if the adversary suspects steganography and runs tools like StegExpose or Chi-square tests, weakly protected data can be detected, even if not decrypted. Once detected, brute-forcing a weak password becomes trivial.

---

## Download

➡️ **[Get the latest StegoCrypt installer for Windows, MacOS or Linux](../../releases/latest)**

---

## Recommended
Install ffmpeg

**Why ffmpeg?** 
StegoCrypt uses ffmpeg to read/write video frames losslessly (`ffv1` / `h264rgb`), preserve LSB integrity and verify outputs. Without it, video stego is limited or unavailable (images still work).

```
#Linux (Debian/Ubuntu)
sudo apt install ffmpeg

#macOS (using Homebrew)
brew install ffmpeg

#Windows (using Chocolatey)
choco install ffmpeg
```

---

## Run from source (Windows/macOS/Linux)

```bash
# from repo root
python -m venv .venv

# Windows:
.\.venv\Scripts\Activate.ps1

# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Run in CLI (will start up GUI interface)
python main.py
```


If you prefer to run directly in CLI, here are some examples:
```
# embed text into an image
python stego_cli.py embed -i cover.png -o cover_stego.png -p "secret" -m "Hello"

# extract (prints UTF-8 to stdout or writes binary with --out)
python stego_cli.py extract -i cover_stego.png -p "secret"
```

---

**Documentation**
- For more info on CLI usage, please refer to the manual at [/docs/CLIOpsManual.pdf](/docs/CLIOpsManual.pdf)
- For information on mathematical detail behind this project, please see [docs/MathematicalDescription.pdf](docs/MathematicalDescription.pdf)

---
