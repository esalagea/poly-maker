# Subprocess Hang Fix - Node.js Merge Script

## Problem

When attempting to merge positions, the Python process would get stuck forever after logging:
```
/home/emil/.nvm/versions/node/v20.13.0/bin/node poly_merger/merge.js 50000000 0x5b627c7b2f82ea92dfb69650a87724664ad771d33ff838c11907efa71c5a4d61 false
```

Running the same command manually at the command line worked fine.

## Root Cause

**File**: `poly_data/polymarket_client.py`, line 317 (original)

The bug was mixing two incompatible `subprocess.run()` usage patterns:

```python
# WRONG - list with shell=True causes undefined behavior and hangs
node_command = [node_path, script_path, amount_to_merge_str, condition_id, is_neg_risk]
result = subprocess.run(node_command, shell=True, ...)
```

When you use `shell=True`, Python expects a **string**, not a list. Passing a list anyway causes unpredictable behavior including hanging.

## The Fix

### Changed in `merge_positions()` method:

1. **Removed `shell=True`**
```python
# Before
result = subprocess.run(node_command, shell=True, capture_output=True, text=True)

# After
result = subprocess.run(node_command, capture_output=True, text=True, timeout=60)
```

2. **Added timeout** - Prevents indefinite hanging with a 60-second timeout

3. **Added better logging**
```python
print('Running command:', ' '.join(node_command))
print("Done merging")
print("Output:", result.stdout)
```

4. **Added clarifying comment**
```python
# NOTE: shell=False (default) when using list - this prevents hanging
```

## Why It Works Now

```python
# CORRECT - list without shell=True works properly
node_command = [node_path, script_path, amount_to_merge_str, condition_id, is_neg_risk]
result = subprocess.run(node_command, capture_output=True, text=True, timeout=60)
```

This properly executes the command without spawning a shell, which is:
- **More secure** - No shell injection vulnerabilities
- **More reliable** - No undefined behavior
- **Faster** - No shell overhead
- **Safer** - 60-second timeout prevents infinite hangs

## Why It Worked on Command Line

When you ran it manually, you used your shell directly, which properly parsed the command. But in Python, `shell=True` with a list doesn't work the same way.

## Files Modified

- `poly_data/polymarket_client.py` - `merge_positions()` method

---
*Fixed on: November 14, 2025*

