"""Verified replay from a state checkpoint and committed event snapshots."""
from .core import canonical_bytes, sha256_hex, state_from_dict, state_to_dict, verify_chain

def replay_from_checkpoint(checkpoint, events, target_step):
    if not isinstance(checkpoint, dict) or not {"step","state","state_hash"}.issubset(checkpoint):
        raise ValueError("invalid checkpoint schema")
    if type(checkpoint["step"]) is not int or type(target_step) is not int:
        raise ValueError("step numbers must be integers")
    if checkpoint["step"] > target_step:
        raise ValueError("checkpoint is after target")
    if sha256_hex(canonical_bytes(checkpoint["state"])) != checkpoint["state_hash"]:
        raise ValueError("checkpoint integrity verification failed")
    if not verify_chain(events):
        raise ValueError("event chain verification failed")
    state = state_from_dict(checkpoint["state"])
    if state.step != checkpoint["step"]:
        raise ValueError("checkpoint step does not match state")
    commits = [e for e in events if e.get("type") == "STEP_COMMITTED" and checkpoint["step"] < e.get("step", -1) <= target_step]
    commits.sort(key=lambda e: e["step"])
    expected = checkpoint["step"] + 1
    for event in commits:
        if event["step"] != expected:
            raise ValueError("missing committed step")
        payload = event.get("data", {}).get("state")
        state = state_from_dict(payload)
        if state.step != expected:
            raise ValueError("committed snapshot step mismatch")
        expected += 1
    if state.step != target_step:
        raise ValueError("target step not available")
    return state
