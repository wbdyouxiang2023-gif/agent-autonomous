#!/usr/bin/env python3
"""
Patch server.py to add observation logging without changing behavior.

This script:
1. Backs up the original server.py
2. Adds observation logging import
3. Inserts observation logging call in the /chat handler
"""
import os
import shutil
from pathlib import Path

SERVER_PATH = Path("/root/.openclaw/workspace/neuro-cortex/server.py")
BACKUP_PATH = Path("/root/.openclaw/workspace/neuro-cortex/server.py.bak")

def apply_patch():
    # Read original
    content = SERVER_PATH.read_text(encoding="utf-8")
    
    # Check if already patched
    if "observation_logger" in content:
        print("Server already patched with observation logger.")
        return
    
    # Backup
    shutil.copy2(SERVER_PATH, BACKUP_PATH)
    print(f"Backup saved to {BACKUP_PATH}")
    
    # Add import after existing imports
    import_block = '''import sys, os, json, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))'''
    
    new_import = '''import sys, os, json, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from experiment.observation_logger import log_observation'''
    
    content = content.replace(import_block, new_import)
    
    # Add observation logging after event processing
    # Find the pattern: event = cortex.process(msg) followed by response building
    old_pattern = '''            event = cortex.process(msg)
            retrieved = retriever.retrieve(msg)'''
    
    new_pattern = '''            event = cortex.process(msg)
            # Observation logging (append-only, zero behavioral change)
            try:
                log_observation(event, msg)
            except Exception as _e:
                pass  # Never let logging failures affect the response
            retrieved = retriever.retrieve(msg)'''
    
    content = content.replace(old_pattern, new_pattern)
    
    # Write patched version
    SERVER_PATH.write_text(content, encoding="utf-8")
    print("Patch applied successfully.")
    print("Changes:")
    print("  - Added observation_logger import")
    print("  - Added log_observation() call after event processing")
    print("  - Wrapped in try/except to ensure zero behavioral change")


if __name__ == "__main__":
    apply_patch()
