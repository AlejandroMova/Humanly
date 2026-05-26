# Config Files — Humanly Reference

Applies to: YAML, TOML, `.cfg`, `.ini`, DeepStream config files, and similar.

## General Rules
- Every non-obvious value needs a comment explaining what it does and valid range
- Sentinel values (like `-1` meaning "disabled") must be documented inline
- Group related keys together with a blank line and a section comment
- No magic numbers without units or context

## YAML
- Consistent indentation (2 spaces preferred)
- Quote strings that contain special characters or could be misread as other types
- Use anchors (`&`) and aliases (`*`) for repeated blocks — but comment what they are
- Boolean values: use `true`/`false`, not `yes`/`no`/`on`/`off` (ambiguous in YAML 1.1)

## DeepStream / GStreamer .cfg files
- Comment the purpose of each `[section]`
- Document `interval` values — always note what `-1` or `0` means for that property
- Note which values are tunable vs. which should not be changed without retraining
- Group: source config → inference config → tracker config → output config
- Example:
  ```ini
  [property]
  # Run inference every N frames. -1 = every frame (high CPU). 5 = good balance.
  interval=5

  # Minimum confidence threshold for a detection to be reported (0.0–1.0)
  threshold=0.3
  ```

## Environment / .env files
- Never commit real secrets — document expected format with placeholder values
- Group by service/concern
- Comment non-obvious variable names
- Example:
  ```
  # Tailscale auth key — generate at https://login.tailscale.com/admin/authkeys
  TAILSCALE_AUTH_KEY=tskey-auth-...
  ```

## What to flag
- Undocumented sentinel values
- Numeric values with no units or valid range noted
- Sections with no explanation of purpose
- Duplicate keys (YAML silently uses the last one)
