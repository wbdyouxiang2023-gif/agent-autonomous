"""Observation logger for NC"""

def log_observation(observation_type, data):
    """Log an observation for NC analysis"""
    import json
    import os
    log_file = os.path.expanduser("~/.nc_observations.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps({
            "type": observation_type,
            "data": data,
            "timestamp": __import__("time").time()
        }) + "\n")
    return True
