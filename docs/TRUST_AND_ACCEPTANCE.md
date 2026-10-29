# Trust and independent acceptance protocol

This document defines operational controls that code cannot establish by itself.

## 1. Genesis anchor ceremony

The `Archive.verify_genesis_anchor(digest)` method checks a recorded start-state and its execution contract against a digest supplied by the caller. It does **not** authenticate the person or process that supplied that digest.

1. Establish the intended initial state from a reviewed source independent of the archive under examination. For the default Phase 0 state, use `initial_state()` and `state_to_dict()`.
2. Compute the digest using the project's canonical JSON implementation:

   `python -c "from evo_geo import initial_state,Contract,genesis_anchor_sha256; print(genesis_anchor_sha256(initial_state(),Contract()))"`

3. Record the digest, contract/spec version, repository URL, intended commit SHA, date, and approver in an independently controlled location (for example, a separately permissioned release record or offline signed operational record). Do not treat a digest committed beside the archive in the same unprotected branch as a trust root.
4. During verification, load the archive and call `archive.verify_genesis_anchor(expected_digest)`. Reject the archive if it returns false or if the anchor's provenance cannot be independently established.
5. If the intended initial state or contract changes, create a new reviewed anchor record; never silently replace the old record.

A plain SHA-256 digest protects against accidental or unanchored changes only when its expected value is already trusted. It is not a signature and does not prove authorship. Signature verification and key custody are intentionally not implemented in this dependency-free Phase 0 core.

## 2. Writer protocol

- For read-modify-write workflows, calculate the SHA-256 digest of the exact bytes read and pass it as `expected_current_sha256` to `save_atomic`. The default only permits creating a missing destination. Use `"missing"` to require absence explicitly, and pass `None` only to deliberately opt into unconditional replacement.
- Never delete or rotate the persistent `<archive>.lock` file while any process may use it.
- Treat network filesystems and non-cooperating writers as outside the lock guarantee. For multiple hosts, use a storage system with documented transactional compare-and-swap or a distributed lock with fencing tokens; a local advisory lock is not a distributed consensus mechanism.
- After an uncertain post-rename error, reload and verify the destination before deciding whether to retry. Retrying with a stale expected digest should fail closed.

## 3. Crash-recovery interpretation

The automated suite injects failures around writes, replacement, and directory fsync and uses subprocess termination at selected points. This provides regression evidence, not proof against physical power loss or defective storage hardware. For deployments that require power-loss guarantees, run filesystem-specific fault tests on the actual OS, filesystem, mount options, and storage hardware, and document the tested configuration.

## 4. Independent human review gate

This checklist must be completed by a reviewer other than the implementation author before acceptance:

- [ ] Confirm PR base and head SHAs and verify that the base branch was not modified.
- [ ] Read the complete diff, especially state parsing, event replay, lock handling, CAS behavior, and archive loading.
- [ ] Independently reproduce the test suite and inspect CI logs on all configured OS/Python combinations.
- [ ] Review threat assumptions: local attackers, symlink races, network filesystems, external writers, compromised anchor source, and storage durability.
- [ ] Record findings, unresolved risks, reviewer identity, reviewed commit SHA, and explicit accept/reject decision.
- [ ] Do not treat a green CI result or this checklist's existence as evidence that the review has occurred.

Until the anchor provenance and independent review are recorded, Phase 0 remains engineering-hardened but not finally accepted.
