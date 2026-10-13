---
id: firedog-timeout-ssh-commands
trigger: when running sshpass or ssh commands to remote VMs, especially over nested port-forwards
confidence: 0.7
domain: workflow
source: session-observation
scope: project
project_id: 008675ce31a5
project_name: firedog
---

# Timeout Wrapper on All Remote SSH Commands

## Action
Wrap all sshpass and ssh commands with timeout (e.g., `timeout 10` or `timeout 15`) to prevent indefinite hangs when VBoxManage port-forwards or network quality degrades.

## Evidence
- Observed 6 times in session c78cdeef-ec6a-4d53-8e16-81f65b49d8f4
- Pattern: `timeout {seconds} sshpass -p '...' ssh ...` or `timeout {seconds} sshpass ... scp ...`
- Timeout durations used: 10s for simple queries, 15s for scp transfers, 20s for larger operations
- Critical for nested sshpass hops where intermediate hop failures can hang indefinitely
- Last observed: 2026-09-21 08:22

Rules:
- Use `timeout 10` for single SSH commands (ssh ls, ssh md5sum, ssh grep)
- Use `timeout 15` for scp transfers (file copy operations)
- Use `timeout 20` for large transfers or multi-command sequences
- Place timeout at the outermost command to wrap the entire sshpass+ssh chain
- If timeout fires (exit code 124), it indicates port-forward or network degradation; retry with different path/hop
- Not required for local commands or localhost operations without port-forwards
