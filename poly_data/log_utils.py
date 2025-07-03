import pandas as pd

def log_message(market_name,  *messages):
    """
    Log a message to both console and market-specific log file.

    Args:
        market_name (str): Market name for the log file (sanitized for filename)
        message (str): Message to log
    """
    message = " ".join(str(msg) for msg in messages)

    # Print to console
    print(message)

    # Sanitize market name for filename (remove invalid characters)
    safe_filename = "".join(c for c in market_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_filename = safe_filename.replace(' ', '_')[:100]  # Limit length and replace spaces

    # Write to log file
    log_file = f'log/{safe_filename}.log'
    timestamp = pd.Timestamp.utcnow().tz_localize(None)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp}: {message}\n")