# AGENT INSTRUCTIONS — Chakravyuh Build

You are acting as an experienced cybersecurity engineer and systems integrator building a working
end-to-end prototype for a defence-focused hackathon (Indian Army Terrier Cyber Quest — AI Kavach
track). Read `PRD.md`, `ARCHITECTURE.md`, and `DESIGN.md` in this repo fully before writing any code.
They are the source of truth for scope, contracts, and constraints.

## Hard Rules — do not violate these under any circumstances

1. **No dummy, mocked, hardcoded, or simulated data anywhere in the final build.** Every event shown
   in the dashboard must originate from a real Q-Cowrie/DataTrap session and a real afc-buttercup run
   against a real target codebase. If a piece is not yet real, mark it explicitly with a `TODO:
   NOT-YET-REAL` comment and flag it to me — do not silently fill in a mock and move on.
2. **No automatic deployment of AI-generated patches without explicit human approval.** The approve/
   reject step is mandatory, not optional, and must be a real UI action with an audit trail entry.
3. **All attacks and fuzzing must run against self-hosted, isolated, intentionally-vulnerable sample
   targets that we own** — never against third-party or production infrastructure. If you are ever
   about to configure something to reach outside the local/isolated lab network for attack purposes,
   stop and ask first.
4. **Scope discipline**: only target memory-safety C/C++ vulnerability classes (buffer overflow,
   use-after-free, out-of-bounds read/write) for the CRS loop. Do not try to generalize to every
   vulnerability class — reliability for the demo matters more than breadth.
5. Every component must be runnable **fully locally** (Docker + Minikube), with no dependency on
   external cloud accounts other than the LLM API calls Buttercup itself needs.

## Build Order (follow this sequence, verify each step before moving on)

### Phase 1 — Get afc-buttercup running standalone
- Clone `https://github.com/trailofbits/afc-buttercup`.
- Set `AZURE_ENABLED=false`, `TAILSCALE_ENABLED=false`.
- Use the minikube values template for local deployment.
- Verify it can run its own known-vulnerable sample target end to end (fuzz → crash → patch →
  regression pass) before touching anything else. Do not proceed to Phase 2 until this works and you
  can show me a real patch diff it produced.

### Phase 2 — Get Q-Cowrie and DataTrap running and logging real sessions
- Deploy Q-Cowrie (RL layer over Cowrie) as one decoy service.
- Deploy DataTrap (`https://github.com/ThalesGroup/dd-honeypot`) as a second decoy service (e.g.
  fake PLC/admin panel), using its dataset+LLM response generation as documented in that repo.
- Both must emit structured JSON events matching the schema in `ARCHITECTURE.md` §2.1. If either
  tool's native log format differs, write a small adapter — do not change the downstream contract.
- Verify by actually attacking your own decoys yourself (e.g., SSH in, try a fake login, try a
  malformed payload) and confirming real structured events appear in the log/stream.

### Phase 3 — Build the Sandbox Twin Manager
- Python service. Config-driven asset registry (YAML) per `ARCHITECTURE.md` §2.2 — do not hardcode
  asset mappings in code, keep them in the config file so we can adjust the demo scenario quickly.
- Consume events (Redis stream is fine, or simple polling if time is short — note the tradeoff but
  keep interfaces clean so it can be swapped later). Each event must include the attacker's raw
  captured payload, not a summary/classification of it.
- Build a lightweight container image per demo target representing its software stack — this is the
  "twin image." Keep it minimal (just enough to run the vulnerable service) so spin-up is fast.
- On event: spin up a fresh, disposable instance of the paired twin image on a network-isolated
  segment (confirm it cannot reach the decoy, the real asset, or the internet).
- Replay the captured raw payload against the twin exactly as received.
- Observe outcome:
  - Twin healthy after a defined timeout → mark `TWIN_SURVIVED`, tear down, done. This should be the
    common outcome — do not treat it as a bug if most incidents end here.
  - Twin crashes/compromised → capture the crash evidence (stack trace, exit code, whatever the twin
    stack exposes), mark `TWIN_COMPROMISED`, and call afc-buttercup's task API passing the payload as
    a **seed input**, not a cold-start fuzz target.
- Always tear down the twin afterward regardless of outcome — twins are single-incident and
  disposable, never reused.
- Test with: (a) a real attack against a decoy whose twin is genuinely vulnerable to that payload —
  confirm it reaches `TWIN_COMPROMISED` and triggers Buttercup; (b) a real attack whose payload the
  twin actually survives — confirm it correctly resolves to `TWIN_SURVIVED` without triggering
  Buttercup. Both outcomes must be demonstrated as real, not assumed.

### Phase 4 — Build the Backend Orchestrator
- FastAPI, implement all endpoints in `DESIGN.md` §2 exactly as specified.
- SQLite for state (schema should mirror the incident object in `DESIGN.md` §1).
- Implement the approve/reject flow for real: on approve, apply the patch to the target codebase and
  request one more fresh sandbox twin from the Twin Manager, built from the *patched* version, then
  replay the original captured payload against it. Only a survive here allows the state to advance to
  DEPLOYED — never mark DEPLOYED without this final re-proof step. On failure, surface this clearly
  rather than silently marking success.
- Generate the structured incident report (per PRD.md FR-13) as a real artifact — attacker source,
  raw payload, decoy touched, real asset affected, twin crash evidence, patch diff, re-proof result,
  timestamps — not a placeholder summary.
- Append-only audit log (JSON lines file is acceptable) recording every approve/reject with actor and
  timestamp.

### Phase 5 — Build the Dashboard
- React frontend implementing the layout in `DESIGN.md` §3: network map, pipeline status, diff viewer,
  live event feed, approve/reject console, optional raw terminal tail.
- WebSocket connection to the backend for live updates — no polling-only implementation for the main
  feed (polling is acceptable only as a fallback if WebSocket setup becomes a blocker, flag if so).
- Diff viewer should render real unified diffs from Buttercup's patch output, not a stylized fake.

### Phase 6 — Full integration rehearsal
- Run the complete loop at least 5 times end to end without manual intervention outside the intended
  operator-approval step. Log how long each phase takes; flag anything that risks exceeding a
  demo-friendly time window (~5–10 min total) so we can pre-warm or adjust scope.
- Prepare one pre-recorded successful run as a fallback video, in case of live demo failure.

## Coding Conventions

- Python: type hints throughout, `black` formatting, no bare `except:`.
- Keep each service in its own directory with its own README describing how to run it standalone.
- Every external tool integration (Buttercup, Q-Cowrie, DataTrap) gets a thin, isolated adapter module
  — do not scatter tool-specific logic across the codebase. This keeps swaps/debugging manageable.
- Write a top-level `docker-compose.yml` that brings up everything except Buttercup (which needs
  Minikube separately per its own docs) with one command.
- Comment any assumption you make about a tool's undocumented behavior, and flag it to me rather than
  guessing silently on anything security-relevant (e.g., how a patch gets verified, how approval is
  authenticated).

## When You Get Stuck

If afc-buttercup, Q-Cowrie, or DataTrap don't behave as documented, or a build step fails, report the
exact error and what you tried — do not paper over it with a mock/stub "to keep things moving." A
broken-but-honest state is far more useful to us right now than a fake green checkmark.

## Definition of Done (per phase)

A phase is only "done" when it produces real, inspectable output (a real log line, a real diff, a real
regression pass/fail) — not when the code merely runs without crashing.
