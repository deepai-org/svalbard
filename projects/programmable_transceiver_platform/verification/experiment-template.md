# Analog experiment: <name>

Use these fields in a short pass note or run manifest; a new standalone proposal
file is optional. Follow [the workflow](../spec/analog-design-workflow.md).

## Compact record for routine passes

Use this as the default; the detailed fields below are prompts for information
that changes interpretation, not mandatory repeated prose. Link unchanged
contracts and manifests rather than copying them.

```text
Question / highest-risk requirement:
Baseline / remaining idealities:
Prior evidence / reusable fixture / what makes this test new:
One change / predicted distinguishing observation:
Test / measurement window / acceptance limit (or diagnostic only):
Reproduce: working directory; runner; checker; output/manifest path
Result: completion; measured effect; regressions; evidence link
Decision: reject / diagnostic only / integrate; retained baseline
Learning: demonstrated effect / numerical artifact / unresolved; scope
Next: discriminating test; workflow/checker update if warranted
```

For an expensive run, also record expected and actual runtime, requested and
observed horizon, and its live handle while pending. Do not fill the result from
an unfinished run. A negative result is useful when it eliminates a candidate or
distinguishes explanations; record that decision explicitly.

## Detailed prompts when applicable

- **System requirement / risk:**
- **Question and alternative explanation:**
- **Baseline artifact and known failures:**
- **Relevant prior lesson / why another experiment is informative:**
- **Declared change:**
- **Implemented circuits / remaining ideal fixtures:**
- **Models, process option, units and operating conditions:**
- **Load, timing, initialization and uncertainty scenarios:**
- **Startup versus repeated-operation timing budget:** where relevant, derive
  acquisition/conversion time and throughput from actual fixture edges.
- **Observation nodes, windows and current/polarity conventions:**
- **Diagnostic metrics / requirement-derived acceptance limits:**
- **Static versus dynamic error:** when relevant, record target error and motion
  relative to each candidate's own settled point separately; include power cost.
- **Cheapest test that could reject this candidate:**
- **Expected runtime / initial horizon / reason to extend:**
- **Next action for each plausible outcome:**
- **Existing runner/checker reused and assumptions that changed:**

After execution:

- **Input provenance and actual run completion:**
- **Job status / existing process handle / requested and observed horizon:**
- **Exact reproduction command / evidence paths / elapsed runtime:**
- **Working directory / output size / smallest failure reproducer:**
- **Measured results and scope:**
- **Evidence claim:** completion / controlled circuit effect / named requirement
  met / connected behavior; list what remains unproven.
- **Failures or competing costs:**
- **Disposition:** rejected / retained for diagnosis / candidate for integration /
  qualified only for explicitly named requirements.
- **Retained baseline after this decision:** exact circuit/fixture; explicitly say
  when the experiment did not replace it.
- **Transferable lesson or reusable check:**
- **Lesson status:** demonstrated circuit effect / numerical or measurement
  artifact / unresolved hypothesis; applicable conditions.
- **Next discriminating experiment / whole-chip risk reassessment:**
- **Workflow improvement:** what changed a decision, what added no information,
  and any reusable check added; use “none” when no change is warranted.
- **Procedure updated:** link the changed workflow step if the lesson affects
  future work; otherwise keep it scoped to this experiment.
