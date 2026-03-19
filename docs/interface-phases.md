# CareCircle Interface-by-Interface Delivery Plan

This plan enforces shipping one interface at a time with completion gates before moving forward.

## Phase A — Dashboard (Desktop)

Goal: give caregiver an at-a-glance status view.

Scope:

- Welcome header + active circle identity
- KPI cards (active tasks, logs, alerts)
- Recent activity timeline
- Circle summary card

Done criteria:

- Data is API-driven (no hardcoded counts)
- Owner/member see dashboard
- Access denied for non-members

## Phase B — Tasks Interface

Goal: task coordination with clear ownership.

Scope:

- Open / Claimed / Verified board
- Claim action with expiration behavior
- Verify completion flow
- Task create/edit/delete rules by role

Done criteria:

- State transitions validated on backend
- Real-time updates (or polling fallback)
- Permission errors shown clearly in UI

## Phase C — Members Interface

Goal: ownership and privacy for circle membership.

Scope:

- Owner-only member directory
- Owner invite/remove actions
- Member-safe restricted view (no full roster)

Done criteria:

- Owner can list/invite/remove
- Non-owner cannot list/invite/remove
- Audit fields stored for invite/remove actions

## Phase D — Care Feed Interface

Goal: chronological shared context.

Scope:

- Human updates + system updates
- Structured tags/signals
- Filter by type/date (optional in MVP)

Done criteria:

- Feed entries persisted and ordered
- Role-based access enforced

## Phase E — Voice Logs Interface

Goal: fast caregiver input with minimal friction.

Scope:

- Record/upload interaction
- Transcription status display
- Recent transcriptions with extracted signals

Done criteria:

- Async processing pipeline status is visible
- Failed jobs are retryable

## Phase F — Insights Interface

Goal: trend visibility without alarm fatigue.

Scope:

- Signal trend cards
- Watch-level anomaly highlights
- Confidence visualization

Done criteria:

- No diagnostic language
- Alerts framed as assistive awareness

## Phase G — Hardening + Launch Readiness

Scope:

- QA passes per interface
- Cross-interface navigation consistency
- Documentation + deployment checklist

---

## Current Focus

- Completed phases: **A (Dashboard), B (Tasks), C (Members), D (Care Feed), E (Voice Logs), F (Insights)**
- Active phase: **Phase G (Hardening + Launch Readiness)**
- Empty-state validation method: run `python manage.py prove_empty_state --interface <activity|tasks|feed|voice|insights>` or `python manage.py prove_empty_state --all` (auto-restores demo data unless `--no-restore`)
