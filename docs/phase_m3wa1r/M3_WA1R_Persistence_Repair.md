# M3-WA1R Persistence Repair

Status: **PASS** (M3WA1R-PERSIST-1).

- Non-circular hash contract: scientific_payload_hash = sha256(canonical payload excluding the hash field); record_file_hash = sha256(final bytes); the file never hashes itself.
- Pre-hash schema validation never requires a self-hash -- the WA1 bug class is structurally impossible (synthetic regression reproduces the fix; failure injection covers every gap).
- Full regression: 1973 passed, 3 warnings in 311.21s (0:05:11).
