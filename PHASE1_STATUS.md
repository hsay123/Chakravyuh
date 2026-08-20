# Phase 1 Status — afc-buttercup Standalone

## VERDICT: ✅ Phase 1 COMPLETE

The full CRS pipeline (trigger → build → fuzz) is operational. All 15 containers running.
The fuzzer-bot is actively fuzzing task `fa1df25d` (libpng v1.6.58, `libpng_transformations_fuzzer`, address sanitizer).

## What's confirmed working

1. **All 15 CRS containers running** via `docker compose -f compose-trapnet.yaml`
2. **Dockerfile pin to v1.6.58** — `crs_scratch/oss-fuzz-aixcc/projects/libpng/Dockerfile` pins `git clone --depth 1 --branch v1.6.58 https://github.com/pnggroup/libpng.git`. Fixes upstream removal of `contrib/oss-fuzz/`.
3. **Repo tarball restructured with wrapper directory** — `example-libpng/png.c` format, matching real competition tarballs.
4. **`trigger_task.sh` focus field fixed** — `"focus": "example-libpng"`. Verified via code trace.
5. **Source tarball pinned to v1.6.58** — source matches what Dockerfile clones and what `build.sh` expects (`libpng16.la` target).
6. **Tooling tarball rebuilt** — clean Dockerfile + project.yaml only.
7. **Build-bot: all 4 variants succeeded** for task `fa1df25d`:
   - COVERAGE (libfuzzer)
   - FUZZER address (libfuzzer)
   - FUZZER memory (libfuzzer)
   - FUZZER undefined (libfuzzer)
8. **Fuzzer-bot actively fuzzing** — 202 corpus entries, 1 slow-unit artifact, no crashes yet (v1.6.58 is a release tag).
9. **Coverage-bot active** — processing coverage data.
10. **Scheduler properly dispatching** — found 5 targets per build variant, pushing to fuzzer map.

## Background watcher

- `watch_fuzzer.sh` running as PID 825863 (detached)
- Polls `docker compose logs fuzzer-bot` every 15s for crash/result indicators
- When done, writes results to `fuzzer_result.txt`
- Check status: `cat fuzzer_result.txt` (empty/missing = still running)
- Raw log: `cat watch_fuzzer.log`

## Key file locations

- `afc-buttercup/crs_scratch/example-libpng/` — source repo (pinned v1.6.58)
- `afc-buttercup/crs_scratch/oss-fuzz-aixcc/` — fuzz tooling (aixcc-afc branch)
- `afc-buttercup/crs_scratch/oss-fuzz-aixcc/projects/libpng/Dockerfile` — pinned Dockerfile
- `afc-buttercup/trigger_task.sh` — task trigger script (focus fixed)
- `/tmp/repo-libpng.tar.gz` — repo tarball (v1.6.58, wrapper dir)
- `/tmp/tooling-oss-fuzz.tar.gz` — tooling tarball (pinned Dockerfile)

## Unresolved / assumptions

- **v1.6.58 may not have crashes** — it's a release tag. If no crashes found, need a known-vulnerable commit.
- **Old broken tasks** (`cadd6e4c`, `958b2d86`) still in Redis — harmless but noisy.
- **`aixcc-finals/example-libpng` is private** — using upstream `pnggroup/libpng` instead.
- **Docker-in-Docker is slow** — each `docker build --no-cache` takes ~2min due to apt-get.

## Moving to Phase 2

Phase 1 is functionally complete. The pipeline works end-to-end.
Next: deploy honeypots (Q-Cowrie + DataTrap) per ARCHITECTURE.md §2.1.
