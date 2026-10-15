---
id: firedog-md5-verify-transfers
trigger: when transferring files via scp across SSH hops or to remote VMs
confidence: 0.85
domain: workflow
source: session-observation
scope: project
project_id: 008675ce31a5
project_name: firedog
---

# MD5 Checksum Verification After Every File Transfer

## Action
Always compute md5sum on both local and remote sides after each file transfer (scp) and compare to detect corruption or truncation.

## Evidence
- Observed 8 times in session c78cdeef-ec6a-4d53-8e16-81f65b49d8f4
- Pattern: After scp transfer, immediately run md5sum locally and remotely, then verify both hashes match
- Commands: `md5sum /path/to/file` before send, `md5sum /path/on/remote` after receive, compare output
- Used for catching scp failures over VBoxManage port-forwards when nested sshpass hops degrade connection quality
- Also checks file size with `stat -c%s` on both sides to detect truncation
- Last observed: 2026-09-21 08:22

Rules:
- Run checksum verification immediately after every scp command, not as a deferred check
- Compare both hash AND size to catch various failure modes
- If checksums differ, file is corrupted or truncated — investigate transfer path (port-forward quality, packet loss)
- Used consistently across multi-hop transfers (direct scp, nested scp via jump host)
