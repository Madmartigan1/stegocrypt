# Changelog

Notable changes to StegoCrypt. Dates are when the change landed on `main`.

## Unreleased

### Fixed
- **Reed-Solomon ECC now actually corrects errors (2026-11-24, #19).** ECC used to be applied to the secret *inside* the AES-GCM envelope, so a single flipped bit failed the authentication tag before RS ever ran. RS now wraps the encrypted data (encrypt-then-ECC), and bit errors are corrected before decryption. Example: with `--rs-nsym 32` on a 3 KB payload, 100 random flipped LSBs are recovered.
  - Stego files with ECC made by v1.0.7 and earlier still extract: the extractor tries the old layout if the new one fails.
  - Stego files with ECC made by this version **cannot** be extracted by v1.0.7 or earlier. Files without ECC are unchanged and compatible both ways.
  - The magic header and salt (first 32 bytes) are still unprotected. ECC handles scattered bit flips, not lossy re-encoding.
- ECC parity bytes are now checked to be in the 1–254 range.
- When extraction fails, the error message now names the likely causes (wrong password, a mismatched ECC/stealth setting, or too much damage).

### Other
- `.gitignore`: ignore the local `media/` test folder.

## v1.0.7 (2026-09-27)

### Fixed
- Image embedding, which failed in v1.0.6 because of a missing import (#16).
- Image extraction now auto-detects LSB 2/3 without `--lsb` (#16).
