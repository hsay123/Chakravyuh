# PRD — Chakravyuh
### Deception-Triggered Autonomous Vulnerability Patching System
**Event:** Indian Army Terrier Cyber Quest 2026 — AI Kavach Track
**Status:** Draft v1

---

## 1. Problem Statement

Defence networks run a mix of real assets (servers, PLCs, IoT/sensor nodes, admin systems) that are
attractive targets. Two gaps exist today:

1. **Detection gap** — traditional honeypots log attacker behaviour but do nothing with it. The
   intelligence gathered from a decoy dies in a log file.
2. **Patching gap** — even when a real vulnerability is known, patching real production/field systems
   is slow, manual, and reactive — often days to weeks (CERT-In's own 2026 blueprint sets a 12-hour
   SLA for critical internet-facing flaws precisely because this gap is dangerous).

**TrapNet-CRS closes both gaps in one loop:** an attacker interacting with a decoy asset becomes the
trigger that causes the real, matching asset to be automatically fuzzed, patched, and verified —
before the attacker ever reaches it.

## 2. Goal / One-liner

> When an attacker touches a fake asset, we capture their exact payload and replay it — not a guess,
> the literal bytes — against a disposable sandboxed twin of the real asset. If the twin breaks, that
> is proof (not inference) that the real asset is exploitable. We then seed our fuzzer with that
> proven-bad input, generate a patch, verify it on the twin, and hand a human a full proof-of-exploit
> + proof-of-fix report for one-click approval — all before the attacker ever reaches the real thing.

This is the core differentiator: most deception systems *classify* an attacker's technique and guess
at a matching weakness. We *prove* exploitability first, deterministically, on a disposable copy —
then fix the real asset with certainty, not inference.

## 3. Non-Goals (explicitly out of scope for the hackathon build)

- No deployment against real external/production infrastructure. Everything runs against **self-hosted,
  intentionally-vulnerable sample targets** in an isolated lab network.
- No fully autonomous patch deployment without human sign-off — this is a hard requirement, not a
  nice-to-have (judges are military; unsupervised auto-deploy to real systems is a non-starter).
- No claim of covering every vulnerability class. Scope to memory-safety bugs in C/C++ (buffer
  overflow, use-after-free, out-of-bounds read/write) — this matches Buttercup's actual capability and
  keeps the demo reliable.
- No production-grade multi-tenant system. Single demo network, single operator console.

## 4. Users / Personas

| Persona | Need |
|---|---|
| SOC Analyst / Cyber Cell Officer | Wants to see attacker activity and approve/reject patches quickly |
| Judge (technical) | Wants to see the real fuzz → patch → verify pipeline actually execute, with real code diffs |
| Judge (non-technical, military) | Wants a clear visual story: attacker hit a trap → system protected itself → human stayed in control |

## 5. Functional Requirements

### 5.1 Deception Layer
- FR-1: Deploy at least 2 decoy services (e.g., fake PLC/Modbus service, fake admin login/DB) using
  Q-Cowrie (RL-adaptive Cowrie) and DataTrap (LLM+dataset-driven realistic responses).
- FR-2: Every attacker interaction (connection, command, credential attempt) is logged with:
  timestamp, source IP, technique/command used, target decoy ID.
- FR-3: Decoy responses must adapt across a session (not static/scripted) — this is the whole point of
  choosing Q-Cowrie/DataTrap over plain Cowrie.

### 5.2 Sandbox Twin Manager (the custom glue — this is your team's real contribution)
- FR-4: On each attacker event, extract the exact raw payload/input the attacker sent to the decoy —
  not a classification of it, the literal bytes/command/request.
- FR-5: Look up the decoy's registry entry to find its paired real-asset's software stack, then spin
  up a **fresh, disposable, network-isolated sandbox twin** running that same stack (same binary/
  codebase version as the real asset, not the real asset itself, and never network-reachable from the
  decoy, the internet, or the real asset).
- FR-6: Replay the captured payload against the twin exactly as the attacker sent it.
- FR-7: Observe the outcome:
  - **Twin survives** — log as a non-issue/low-severity note, tear down the twin, no further action.
  - **Twin crashes/is compromised** — this is deterministic proof the real asset shares the flaw.
    Proceed to FR-8.
- FR-8: On proof of exploitability, hand the crashing payload to afc-buttercup as a **seed input**
  (not a cold-start fuzzing campaign) so it reproduces the crash immediately and begins root-causing
  and patching from a known-bad starting point.
- FR-9: Tear down every sandbox twin after use — twins are single-incident, disposable, never reused
  or left running.

### 5.3 CRS / Patch Layer (afc-buttercup)
- FR-10: Buttercup runs seeded fuzzing (using the proven-crashing payload from the twin as its
  starting corpus) → root-cause → patch generation → regression-verify, against the target codebase.
- FR-11: A generated patch must not be applied automatically — it is staged and requires explicit
  operator approval in the dashboard.
- FR-12: On approval, the patch is applied to the real target's codebase (a fresh sandbox twin is
  spun up one more time to re-verify the patched build survives the exact same payload, before the
  patch is marked "deployed" in the demo) — never patch the "live" asset directly without this final
  re-proof step.
- FR-13: Generate a structured incident report: attacker source, exact payload, decoy touched,
  real asset affected, proof-of-exploit (twin crash evidence), patch diff, proof-of-fix (twin re-test
  pass), and a timestamp trail — routed to the named defence responsible-officer for that asset.

### 5.4 Dashboard (the thing judges actually watch)
- FR-14: Live network map — real assets vs decoy assets vs ephemeral sandbox twins, decoys highlight
  red on interaction, twins appear/disappear live as they spin up and tear down.
- FR-15: Live attacker event feed (from Q-Cowrie/DataTrap logs), including the raw captured payload.
- FR-16: Pipeline status panel showing state machine: `Detected → Twin Spawned → Replaying →
  Twin Compromised → Seeded Fuzzing → Patch Generated → Re-Verifying on Fresh Twin →
  Awaiting Approval → Approved/Deployed` (or `Twin Survived → Closed`, a short branch, if the replay
  didn't reproduce the issue).
- FR-17: Code diff view — vulnerable line(s) vs AI-generated patch, side by side.
- FR-18: Full incident report view (per FR-13) — this is the artifact routed to the responsible
  defence officer, and should be exportable (PDF/print) not just on-screen.
- FR-19: One approve/reject button, operator-facing, with an audit trail (who approved, when).
- FR-20: Optional raw terminal panel showing live Q-Cowrie session output for demo authenticity.

## 6. Non-Functional Requirements

- NFR-1: **No mocked/dummy data in the final demo.** All events must originate from real Q-Cowrie/
  DataTrap sessions and a real Buttercup run against a real codebase.
- NFR-2: Must run fully on a single demo laptop/mini-rig (Docker + Minikube) — no dependency on
  external cloud accounts during the live demo, to avoid conference-wifi failure risk.
- NFR-3: End-to-end cycle (attack → patch proposed) should complete within a demo-friendly window
  (aim for under 5–10 minutes for the chosen sample vuln — pick fuzz targets accordingly).
- NFR-4: System must survive a rehearsed run at least 5 times in a row without manual intervention,
  before finale day.

## 7. Success Criteria for the Finale Demo

1. Live attacker action (scripted or manual) hits a decoy → visible on dashboard within seconds.
2. Dashboard shows correlation decision and Buttercup task kick-off.
3. Buttercup produces a real patch against the real target — code diff shown on screen.
4. Regression proof shown (before: crash/fail, after: pass).
5. Operator clicks approve on stage → status updates to "Deployed."
6. Whole thing narrated in under 4–5 minutes live.

## 8. Milestones (assuming shortlisting, ~7 weeks to finale)

| Week | Deliverable |
|---|---|
| 1 | afc-buttercup running locally against sample target (e.g. example-libpng) |
| 2 | Q-Cowrie + DataTrap decoys running, logging real sessions |
| 3 | Correlation engine v1 (rule-based mapping, not ML yet) wired end-to-end |
| 4 | Dashboard v1 (network map + event feed + pipeline status) |
| 5 | Code diff view + approve/reject flow + audit trail |
| 6 | Swap in defence-flavoured demo target; full rehearsal |
| 7 | Hardening, repeat rehearsals, fallback recording as backup |
