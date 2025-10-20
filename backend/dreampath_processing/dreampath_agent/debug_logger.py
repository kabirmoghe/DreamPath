"""
Simple debug logger for redirecting verbose output to a file.
"""

import os
from datetime import datetime

def log_messages_to_file(messages: list, log_file: str = "dreampath_debug.log"):
    """
    Log formatted messages to a file with timestamps.
    
    Args:
        messages: List of message dictionaries
        log_file: Path to the log file
    """
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] === MESSAGES SENT TO LLM ===\n")
            for i, msg in enumerate(messages):
                f.write(f"[{timestamp}] --- Message {i} [role={msg['role']}] ---\n")
                f.write(f"[{timestamp}] Content: {msg['content']}\n")
            f.write(f"[{timestamp}] === END MESSAGES ===\n")
    except Exception as e:
        # Fallback to console if file writing fails
        print(f"Failed to write to log file: {e}")
        print("=== MESSAGES SENT TO LLM ===")
        for i, msg in enumerate(messages):
            print(f"--- Message {i} [role={msg['role']}] ---")
            print(f"Content: {msg['content']}")
        print("=== END MESSAGES ===")

def clear_log_file(log_file: str = "dreampath_debug.log"):
    """
    Clear the log file.
    """
    if os.path.exists(log_file):
        os.remove(log_file)
