# Contributing to StegoCrypt

Thanks for your interest in improving StegoCrypt! 🎉

## Ways to contribute
- 🐛 Report bugs (with steps, logs, OS, version).
- 💡 Request features (clear use case).
- 🔧 Fix issues / improve docs / add tests.

## Development setup
```bash
# clone
git clone https://github.com/Madmartigan1/stegocrypt.git
cd stegocrypt

# venv + deps
python -m venv .venv
. .venv/Scripts/activate  # Windows
# or: source .venv/bin/activate

pip install -r docs/requirements.txt
pip install -e .
