import os

DEBUG_MODE = True

def debug_log(msg: str):
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")