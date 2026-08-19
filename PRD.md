# PRD — TrapNet-CRS
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

> When an attacker touches a fake asset, we learn *how* they attacked it, check if the *real* asset
> has the same flaw, and if so — autonomously fuzz it, generate a patch, prove the patch works, and
> hand it to a human for one-click approval. All of this is visible live on a single dashboard.

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

### 5.2 Correlation Engine (the custom glue — this is your team's real contribution)
- FR-4: On each attacker event, classify the technique/vulnerability class being probed (e.g.,
  "buffer overflow attempt on service parser", "default credential brute force").
- FR-5: Match the classified technique against a small registry mapping decoy asset → real asset →
  known codebase/binary, to decide whether the real asset needs to be checked.
- FR-6: On a match, trigger a Buttercup task against the corresponding real target's source repo.

### 5.3 CRS / Patch Layer (afc-buttercup)
- FR-7: Buttercup must run the full find → fuzz → patch → regression-verify loop against a real
  target codebase (start with a known-vulnerable sample, e.g. example-libpng, then swap to your
  chosen embedded-style demo target).
- FR-8: A generated patch must not be applied automatically — it is staged and requires explicit
  operator approval in the dashboard.
- FR-9: On approval, the patch is applied to a shadow copy of the real target and the regression/fuzz
  suite re-runs to prove the fix holds, before being marked "deployed" in the demo.

### 5.4 Dashboard (the thing judges actually watch)
- FR-10: Live network map — real assets vs decoy assets, decoys highlight red on interaction.
- FR-11: Live attacker event feed (from Q-Cowrie/DataTrap logs).
- FR-12: Pipeline status panel showing state machine: `Detected → Matched → Fuzzing → Patch Generated
  → Verifying → Awaiting Approval → Approved/Deployed`.
- FR-13: Code diff view — vulnerable line(s) vs AI-generated patch, side by side.
- FR-14: One approve/reject button, operator-facing, with an audit trail (who approved, when).
- FR-15: Optional raw terminal panel showing live Q-Cowrie session output for demo authenticity.

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
