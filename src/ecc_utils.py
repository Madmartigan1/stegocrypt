# ecc_utils.py
try:
    import reedsolo
    REED_OK = True
except Exception:
    REED_OK = False

def rs_encode(data: bytes, nsym: int) -> bytes:
    if not REED_OK: raise RuntimeError("reedsolo not installed")
    return reedsolo.RSCodec(nsym).encode(data)

def rs_decode(data: bytes, nsym: int) -> bytes:
    if not REED_OK: raise RuntimeError("reedsolo not installed")
    return reedsolo.RSCodec(nsym).decode(data)[0]
