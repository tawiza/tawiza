# Patterns export — Source Observatory (DataCivicLab, IT)

Quick-access guide for the patterns Tawiza committed to share with [DataCivicLab/source-observatory](https://github.com/dataciviclab/source-observatory) in the cross-country comparison discussion ([dataciviclab/discussions/297](https://github.com/orgs/dataciviclab/discussions/297), follow-up of [source-observatory#227](https://github.com/dataciviclab/source-observatory/issues/227)).

All files referenced below live in this repo on `main`. No code is duplicated here on purpose — the source files are authoritative, this document is the porting guide.

## License

MIT (same as the rest of `tawiza/tawiza`). Use freely, attribution appreciated, no warranty.

---

## 1. Token bucket rate limiter — 114 LOC

**File**: [`src/infrastructure/crawler/workers/rate_limiter.py`](../../src/infrastructure/crawler/workers/rate_limiter.py)

**External deps**: `asyncio`, `loguru` (drop-in for any logger), nothing else.

**Public surface**:

```python
RateLimit(requests: int = 10, period: int = 60)
RateLimiter(default_limit: RateLimit | None = None)

await limiter.acquire(domain: str)         # blocks until a token is free
limiter.block_domain(domain, duration=300) # explicit cooldown after 429/503
limiter.is_blocked(domain) -> bool
limiter.set_limit(domain, RateLimit(...))  # per-domain override
```

**How it works**: per-domain token bucket, refilled lazily on `acquire()` based on elapsed wall time. Single `asyncio.Lock` for the whole limiter (fine for our crawl volumes). No persistence across restarts — bursty workload, doesn't matter.

**Porting notes**: the only piece probably worth comparing against `lab-connectors.HttpClient` is `block_domain` — it lets you back off without resetting the refill curve, which a plain Retry-After loop doesn't.

---

## 2. LinUCB bandit scheduler — 436 LOC public, reward function private

**File**: [`src/infrastructure/crawler/scheduler/linucb_scheduler.py`](../../src/infrastructure/crawler/scheduler/linucb_scheduler.py)

**External deps**: `numpy` only. The arms persist `A`/`b` matrices to disk via the companion `source_arm.py`.

**Three building blocks**:

1. `ContextFeatures` — 10-dim feature vector built from a TAJINE query:
   - `dept_hash` (department code / 100), `is_urban`, `is_overseas`
   - `domain_hash`, `complexity` (query length + keyword bumps on "corrélation", "tendance", "évolution", "comparaison")
   - `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos` (cyclical time encoding)
   - `source_type_hash` (api / web / rss)
2. `LinUCBArm(alpha=0.5)` — one arm per source. `select()` returns `θᵀx + α·√(xᵀA⁻¹x)`. `update(reward)` does the standard `A += xxᵀ`, `b += rx`, `θ = A⁻¹b`.
3. `LinUCBScheduler` — orchestrates arms, picks best UCB, persists state per arm.

**What's private**: the reward function (`reward.py`) is intertwined with our trust-scoring + freshness pipeline. The public scheduler is callable with any external reward.

**Porting notes**: to plug into radar/catalog regimes, define a function `reward(observation) -> float in [0, 1]` and feed it back via `arm.update(reward)`. Our reward includes freshness, source confidence, query-fit, but the scheduler doesn't care what's inside.

---

## 3. Cross-source anomaly detection (pattern-based) — 775 LOC public

**File**: [`src/infrastructure/agents/tajine/territorial/signal_detector.py`](../../src/infrastructure/agents/tajine/territorial/signal_detector.py)

**External deps**: stdlib only (`dataclasses`, `enum`, `datetime`).

**Two layers**:

- `SignalPattern` — declarative rule. Example shape: `"BODACC liquidations rate > 2σ from rolling 12-month median, persistent ≥ 2 months"`. Pure data, no ML.
- `SignalDetector` — runs the patterns against a `SignalIndicator` snapshot, emits `DetectedSignal` with `severity` + `category` + cross-source convergence count.

**What's private**: the deeper z-score + IQR + convergence detector lives in `detect_microsignals_v2.py` because thresholds were tuned on data we cannot release publicly. The public detector exposes the same dataclasses (`SignalIndicator`, `DetectedSignal`) so a private scorer can plug in without API changes.

**Porting notes**: the pattern-based layer is the right starting point for a public homologue. The dataclass contract is the stable interface — if you wire a different detection backend, keep the I/O types and the rest plugs in.

---

## 4. Adapter pointers (with 2 honesty corrections vs the #227 conversation)

| Component | File | LOC | Note |
|---|---|---|---|
| `INSEELocalAdapter` (OAuth2 + SDMX 2.1) | [`adapters/insee_local.py`](../../src/infrastructure/datasources/adapters/insee_local.py) | 712 | Matches what was claimed |
| `SireneAdapter` hexagonal port | [`adapters/sirene.py`](../../src/infrastructure/datasources/adapters/sirene.py) | 222 | Split across 2 layers, not 330 in one file |
| `Sirene` collector layer | [`collectors/api/sirene.py`](../../src/collector/collectors/api/sirene.py) | 272 | |
| NAF enrichment | [`sirene_tools.py`](../../src/cli/v2/agents/tools/sirene_tools.py) | inside | `sirene_naf_codes` function + NAF filtering branches in `sirene_recherche_entreprises`. There is no standalone `sirene_sectors.py` (correction vs #227). |

**Porting notes on INSEE**: worth comparing against the generic SDMX collector — we specialized because INSEE's OAuth2 flow and series naming are non-standard enough that a generic adapter loses too much. The OAuth2 token refresh logic is reusable as-is.

**Porting notes on SIRENE**: the hexagonal split (port + collector) is overkill for one adapter, that's tech debt we live with. If you port, collapse the two into one file.

---

## Open question (still relevant from the discussion intro)

On the 30 / 120-150 / 365 auto-deprecation thresholds, we're leaning toward an extra cooldown counter on the "hold" state: if a source comes back from hold and re-fails within 30 days, the next hold is 180 days instead of 120. Otherwise we'd flap on sources that recover temporarily.

Curious how mcp-brasil, pasal, Civia handle the recovery side — silent reset vs progressive penalty.

---

## Contact

Discussion thread: https://github.com/orgs/dataciviclab/discussions/297
French side: @hamidedefr (`tawiza/tawiza`)
Italian side: @Gabrymi93 (`dataciviclab/source-observatory`)
