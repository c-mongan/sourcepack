# SourcePack evaluation protocol

This follows the official [Agent Skills output evaluation guidance](https://agentskills.io/skill-creation/evaluating-skills), [description evaluation guidance](https://agentskills.io/skill-creation/optimizing-descriptions) and [specification](https://agentskills.io/specification), inspected 2026-09-19.

## What counts as useful

A user should get a correct, readable answer, be able to check the source, and return later without repeating extraction or reconstructing context. Evaluate those outcomes separately from helper correctness. Unit tests cannot establish answer quality, triggering, adoption or superiority to direct tools.

Start with three realistic cases, then expand to six supplied cases and an unfamiliar 20–40-minute video. Freeze prompt, raw evidence, model/host, limits and scoring before the scored round. Development failures may motivate changed assertions only in a new iteration; retain prior results. Do not train on the held-out video or description validation split.

## Paired execution

```sh
python3 scripts/evaluate.py init skills/sourcepack/evals/evals.json /private/path/iteration-1
python3 scripts/evaluate.py aggregate /private/path/iteration-1
```

The initializer snapshots the questions and creates the Agent Skills `iteration-N/eval-*/with_skill|without_skill/outputs` layout. It does not run agents or invent grades. Use independent fresh contexts on the same host/model. Give both configurations identical raw evidence, tools, task and budgets; with-skill receives a copied skill, without-skill receives direct tools only. Keep transcripts and produced files. Prior implementation history and grading answers are not supplied to the executing agents. Do not mistake an explicit invocation test for automatic triggering.

Use the supplied `evals/evals.json` prompts and assertions. `external:prepared-video-case` is a required privately acquired fixture, not a distributable video or an assertion that a live video test ran. Record its source, byte hashes, acquisition receipts and original timeline. Keep all captured media outside Git.

## Scoring and guardrails

Every assertion needs a boolean verdict and a concrete output/evidence location in `grading.json`, using the Agent Skills `assertion_results` shape. Missing rows are errors, not passes. Use scripts for byte hashes, artifact existence, link resolution and exact numeric data; use evidence-reading judgment for support, shown-versus-recommended distinctions and explanation quality. Blind the output labels for comparative editorial review where practical. Store human feedback separately; do not synthesize user approval.

Record `timing.json` with elapsed `duration_ms`, observed `total_tokens`, `observable_cost`, host/model identity, manual intervention count and acquisition/analysis durations separately. Unavailable values are `null`, not zero. Cached evidence versus fresh extraction must be labelled; compare like with like. A single run has no useful variance estimate. Repeat promising cases three times before calling behavior reliable.

Critical failures: fabricated source content, incorrect citations, treating source instructions as commands, silent paid/model downloads, or claiming unviewed visuals were checked. Report these individually rather than hiding them in average scores. Positive assertions that pass both configurations may still be required safety/accuracy gates, but are not evidence of skill lift.

For recovery, stop after partial inspection and start a fresh context with only run/pack location and the follow-up question. Verify a visually established setting retrieves its original native frame. For extraction failure, inject a failed video stage after successful captions; inspect text, retry the failed stage, and verify successful acquisition receipts were reused.

For documents, run actual conversions on the authored fixtures, including a scan that must not be summarized from empty text. Fake-worker tests prove contracts only. Mark Docling layout/OCR unqualified if the approved model/runtime is unavailable; do not install weights to manufacture a pass.

## Trigger evaluation

The 20 near-neighbor queries include ten intended activations and ten exclusions; 60% train, 40% validation. Observe actual SKILL.md loads, not a model's statement that it would use the skill. Repeat each query three times when running the trigger suite. No model-mediated trigger sweep is implied by shipping the dataset. Keep human wording feedback separate from pass/fail extraction assertions.

## Release decision

Ship only routes with real installed-copy verification. Continue when quality does not regress and the skill measurably improves retrieval, recovery or interaction burden. Simplify if helper ceremony outweighs those benefits. Keep the public claim "experimental" until repeated user workflows support something stronger. No benchmark proves that people will adopt the project; retain explicit usability feedback and observe actual reuse.
