# docs/adr — Architecture Decision Records

## What is this folder?

An **ADR** (Architecture Decision Record) is a short document that captures an important technical decision: what was decided, why that choice was made over alternatives, and what the consequences are.

Think of ADRs like meeting minutes for engineering decisions. When you come back to the codebase months later and wonder "why did we do it this way?" — the ADR has the answer, written at the time the decision was fresh.

Each ADR follows the same format:
- **Status** (Proposed / Accepted / Superseded)
- **Context** — What problem were we trying to solve?
- **Decision** — What did we choose?
- **Rationale** — Why this option over others?
- **Consequences** — What trade-offs did we accept?

---

## ADR Index

| ADR | Title | Status | Summary |
|---|---|---|---|
| ADR-001 | *(see file)* | — | *(see file)* |
| ADR-002 | *(see file)* | — | *(see file)* |
| ADR-003 | *(see file)* | — | *(see file)* |
| ADR-004 | *(see file)* | — | *(see file)* |
| [ADR-005](ADR-005-transformer-deferral.md) | Defer Transformer Time-Series Model | ✅ Accepted | Defer the Transformer ML model until GPU training is available and tick data volume justifies it |
| ADR-006 | *(see file)* | — | *(see file)* |
| ADR-007 | *(see file)* | — | *(see file)* |
| ADR-008 | *(see file)* | — | *(see file)* |

---

## ADR-005 Deep Dive: Why No Transformer Yet

[`ADR-005-transformer-deferral.md`](ADR-005-transformer-deferral.md) is the most detailed ADR currently documented.

**The decision:** Defer implementing a Transformer-based price prediction model (despite Transformers being state-of-the-art for many sequence tasks) in favor of the already-implemented LSTM and XGBoost models.

**Why defer?**
1. **Diminishing returns at current scale.** Transformers show their biggest advantages on very long sequences (1,000+ time steps) and large datasets. The current setup uses daily/hourly bars with 1-2 year training windows — the LSTM and XGBoost models perform well here.
2. **No GPU training yet.** Transformers need 5-20× more compute than LSTM for equivalent results. Without a CUDA-enabled Celery worker, training times would be impractical.
3. **No benchmarking infrastructure.** A responsible Transformer deployment needs reproducible out-of-sample evaluation comparing all models on identical data splits. That infrastructure doesn't exist yet.
4. **Dependency overhead.** Adding `transformers` and multi-GB model artifacts is only justified by measured improvement.

**When will it be built?** When all five re-engagement criteria are met:
- ML benchmarking harness in place
- GPU training path available
- 30+ days of tick data ingested for 10+ symbols
- LSTM/XGBoost Sharpe baselines documented
- Team capacity scoped in a sprint

**Proposed architecture** (when built): Vanilla PyTorch `nn.TransformerEncoder` — no pre-trained weights, same 3-class output as LSTM, reusing the existing feature pipeline.

---

## How to Write a New ADR

1. Copy an existing ADR file as a template
2. Name it `ADR-NNN-short-title.md` (where NNN is the next available number)
3. Fill in all sections honestly — especially the **Consequences** section (both positive and negative)
4. Add it to the index table above
5. Link to it from the relevant code with a comment: `# See ADR-NNN`

---

## How does this connect to the rest of the app?

- ADR-005 directly explains the empty `ml/models/transformer/` directory
- ADRs 001-004 and 006-008 explain other structural decisions throughout the codebase
- The `README.md` at the project root links here as the place to understand architectural intent
