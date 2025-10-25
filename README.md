# StegoCrypt

Hide encrypted messages or files inside images/videos with password-protected, pixel-level steganography.  
✅ GUI app for Windows • Optional CLI • Lossless output for reliable extraction.

## Download

➡️ **[Get the latest StegoCrypt installer (Windows)](../../releases/latest)**

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

For more info on CLI usage, please refer to the manual at [/docs/CLIOpsManual.pdf](/docs/CLIOpsManual.pdf)
