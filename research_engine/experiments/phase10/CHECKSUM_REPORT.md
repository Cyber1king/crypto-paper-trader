# Phase 10 — Checksum Report

Every archive was verified against the SHA-256 published by Binance Vision
in the sibling `.CHECKSUM` file **before** any parsing. An archive whose
checksum does not match is never parsed or accepted.

## Verification results

| Month | Published SHA-256 | Local SHA-256 | Verified |
|---|---|---|---|
| 2026-01 | `a40e86beb4f1e6d4b19ca022c87b8b2f0e4e40874d349a5a75b27baa9634c858` | `a40e86beb4f1e6d4b19ca022c87b8b2f0e4e40874d349a5a75b27baa9634c858` | ✅ |
| 2026-02 | `0be4e5c92892495c5da5b371fe8755f2d508b28a58414b4171284480806ed6c4` | `0be4e5c92892495c5da5b371fe8755f2d508b28a58414b4171284480806ed6c4` | ✅ |
| 2026-03 | `44f383f9423f96cdc29e03b4ba8062296763dd740ab1d93f04b62c88bac30aa6` | `44f383f9423f96cdc29e03b4ba8062296763dd740ab1d93f04b62c88bac30aa6` | ✅ |
| 2026-04 | `9f8e49b70978177414a005a6e84b1cf891f97b0196526cbd579535449c14b6f6` | `9f8e49b70978177414a005a6e84b1cf891f97b0196526cbd579535449c14b6f6` | ✅ |
| 2026-05 | `11b8537dc1769a7de9d6cb2e0354dd4a376018986a826c67d1078e25fbf8fb80` | `11b8537dc1769a7de9d6cb2e0354dd4a376018986a826c67d1078e25fbf8fb80` | ✅ |
| 2026-06 | `7c446aee297f382ee92b8d9b3300a1d7c21bed8166118f3bb261275bed5e308e` | `7c446aee297f382ee92b8d9b3300a1d7c21bed8166118f3bb261275bed5e308e` | ✅ |
| 2026-07 | `ec98553c10acdbf3f210c55045614e8d3daf616e407c36718269361b1e972b16` | `ec98553c10acdbf3f210c55045614e8d3daf616e407c36718269361b1e972b16` | ✅ |
| 2026-08 | `1fa85817e358f73e0dd9509f6f31c79bf9b23d9470971a882c8f814871a3fccf` | `1fa85817e358f73e0dd9509f6f31c79bf9b23d9470971a882c8f814871a3fccf` | ✅ |

**8 of 8 verified. 0 failures. 0 archives rejected on checksum grounds.**

## Method

For each month:

1. Download `<name>.zip` and `<name>.zip.CHECKSUM` from the official URL.
2. Read the expected digest from the `.CHECKSUM` file (format:
   `<sha256>  <filename>`).
3. Compute SHA-256 of the downloaded zip locally.
4. Compare case-insensitively.
5. **Only if equal** was the archive extracted and normalised.

Implemented in `experiments/phase10/extract_and_normalise.py` via the
existing `crypto_paper_lab.acquisition.sha256_of`. The verification step is
re-run inside that script on every execution, so a corrupted archive cannot
silently pass later.

## Downstream digests

Recorded in each provenance sidecar and each validation report:

| Normalised file | SHA-256 |
|---|---|
| `binance_spot_BTCUSDT_1h_202601.csv` | `fc0afd05636ffc6a1fe930fc9394b50e1d3cfb0a869f0bea32d781fcea9bce6a` |
| `binance_spot_BTCUSDT_1h_202602.csv` | `27a8d0912147d209b0fd7405ff935e88402371baf573b8892c583223f230555f` |
| `binance_spot_BTCUSDT_1h_202603.csv` | `b65e9915443f92e9e3edf68e396f2e848ba07d88ff5a6a36048ecb0e2bf8164d` |
| `binance_spot_BTCUSDT_1h_202604.csv` | `57c4d9bb110d68b7d173c76b2c0c7409e0b4f50a46cc320c59fcb44aa44d7586` |
| `binance_spot_BTCUSDT_1h_202605.csv` | `725a47aaf2cc51124ac0bc27697222d266577642cc927473cfbe6c65af9b5afc` |
| `binance_spot_BTCUSDT_1h_202606.csv` | `eaf631e76978149d464618269b58f5daae5d40e39b507a6eba94b96f43cce3b0` |
| `binance_spot_BTCUSDT_1h_202607.csv` | `9d46773a798094b1ec9f7b89025bfd609039cf5bf4c2be6eb1c767e93c48352a` |
| `binance_spot_BTCUSDT_1h_202608.csv` | `ae4edd83667f99b0f5c80f083f6868bf75a004a024ad80e6d5ba90d7c05a776e` |
| **`binance_spot_BTCUSDT_1h_202601-202608.csv`** (merged) | **`918153fde98e39c03eef8a7b82a2861adfdc98a080c8810e371869eb3ea22437`** |

## Original research dataset

| Check | Value |
|---|---|
| SHA-256 before Phase 10 | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` |
| SHA-256 after Phase 10 | `201A3B15D50A791CB5BE2B755107C8303906C8FC3CA6B64E8377C9FC73BA016B` |
| Changed | **No** |

## Standing caveat on archive revisions

Binance Vision's own README states that *"Archived files may be updated at a
later date as a result of recently discovered issues"* and publishes a
changelog of such revisions. A checksum therefore proves the file is
**intact as published today**; it cannot prove the underlying historical data
will never be revised. Any future re-download should re-verify and compare
digests, and a changed digest should be treated as a source revision worth
investigating rather than a transfer error.

Separately, the provenance of the original 2024–2025 dataset remains
undocumented (recorded in `experiments/phase9/DATA_VALIDATION_REPORT.md`). It
is therefore **not established** that the 2026 Binance data is methodologically
continuous with it. The timestamps are contiguous across the boundary, but
timestamp continuity is not the same as construction continuity.
