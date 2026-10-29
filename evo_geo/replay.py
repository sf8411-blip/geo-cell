"""Verified replay from a checkpoint bound to the committed event history."""
from .core import Archive, Engine, canonical_bytes, sha256_hex, state_from_dict, state_to_dict, verify_chain


def replay_from_checkpoint(checkpoint, events, target_step):
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"step", "state", "state_hash"}:
        raise ValueError("invalid checkpoint schema")
    if type(checkpoint["step"]) is not int or type(target_step) is not int:
        raise ValueError("step numbers must be integers")
    if checkpoint["step"] < 0 or target_step < checkpoint["step"]:
        raise ValueError("invalid replay range")
    if not isinstance(events, list) or not verify_chain(events):
        raise ValueError("event chain verification failed")
    if sha256_hex(canonical_bytes(checkpoint["state"])) != checkpoint["state_hash"]:
        raise ValueError("checkpoint integrity verification failed")

    state = state_from_dict(checkpoint["state"])
    if state.step != checkpoint["step"]:
        raise ValueError("checkpoint step does not match state")
    Engine(state=state)

    # A checkpoint is trusted only when its canonical state matches the
    # STEP_COMMITTED snapshot for the exact same step in this event chain.
    commits = [e for e in events if e.get("type") == "STEP_COMMITTED"]
    steps = [e.get("step") for e in commits]
    if any(type(step) is not int for step in steps) or steps != sorted(set(steps)):
        raise ValueError("committed steps are not strictly increasing")
    snapshots = {}
    for event in commits:
        payload = event.get("data")
        if not isinstance(payload, dict) or "state" not in payload:
            raise ValueError("committed snapshot missing")
        snapshot = state_from_dict(payload["state"])
        Engine(state=snapshot)
        if snapshot.step != event["step"]:
            raise ValueError("committed snapshot step mismatch")
        snapshots[event["step"]] = state_to_dict(snapshot)
    if snapshots.get(checkpoint["step"]) != state_to_dict(state):
        raise ValueError("checkpoint does not match committed snapshot")

    # Also require Archive-level checkpoint/event consistency where possible.
    audit = Archive()
    audit.events = events
    audit.checkpoints = {checkpoint["step"]: checkpoint}
    if not audit.verify():
        raise ValueError("archive verification failed")

    expected = checkpoint["step"] + 1
    for event in commits:
        step = event["step"]
        if checkpoint["step"] < step <= target_step:
            if step != expected:
                raise ValueError("missing committed step")
            state = state_from_dict(event["data"]["state"])
            Engine(state=state)
            expected += 1
    if state.step != target_step:
        raise ValueError("target step not available")
    return state
