<!-- SPDX-FileCopyrightText: 2026 Deep AI, Inc. -->
<!-- SPDX-License-Identifier: Community-Spec-1.0 -->
# The LNP64 Instruction Set (definitive)

This is the **designed LNP64 ISA**: the freeze target, complete, with **nothing scheduled for
removal** and no **active v1 semantic surface** lacking its primitive. Named encoding-only and deferred
profile seams are explicitly non-active and classified in Appendix G; they are not implied v1 behavior.
This document is *what an LNP64 chip must be*. Appendix B lists the deliberate irregularities,
each with its reason; Appendix H states the **ownership covenant** the conformance mark enforces:
the machine's owner holds the root authority, and nothing on a conforming machine — no key, no
flag, no firmware path — distrusts it.

**What this document is: the instruction set of a higher-level processor.** Its instructions
operate on domains, capabilities, mappings, queues, and time the way a conventional ISA's
operate on registers and addresses — so the work a microkernel, hypervisor, scheduler, IOMMU
stack, pager, container runtime, RPC layer, and accelerator interface would otherwise
re-implement above the ISA is simply *what this processor's instructions do*. Those roles freeze
together because they are one instruction set, the same way `add` and `ld` freeze together — not
separate designs bolted together but corollaries of one small law set (§0).

The claim is **behavioral, never a construction ban** (software cannot distinguish hardwired logic
from a control store from a verified sequencer running immutable ROM, so a microcode ban would be
either non-architectural or a timing claim in disguise): **the engine protocols are
architecturally mandatory anonymous substrate**, with two precisions:
**(i) Native execution beneath delegated state.** Every mandatory intrinsic instruction executes
directly against the effective capabilities, views, budgets, placement, time, and object state of the
issuing domain. No parent, binding, personality, or service may ambiently replace or intercept that
instruction. Personality policy, foreign-device behavior, and service emulation are reached only by
explicit gate, endpoint, or proxy-object capabilities; **(ii)** **engine execution and liveness may
never depend on a pageable software
service, caller-owned residency, or an authority-bearing domain** — internal storage placement
is otherwise unconstrained subject to the architectural latency and availability bounds (a
protected metadata cache or hardware-managed spill is nobody's business; an engine that parks
on a software pager is nonconforming). The engines may not appear in the domain tree or hold
capabilities (Law 3) and may not be omitted; their internal realization
(hardwired state machines, distributed sequencers, ROM control, anything else) is
**unconstrained provided the §16.4 bounds, the Law 3 trust properties, and the Appendix F
semantics hold**. What "hardware microkernel" means here is exactly that behavioral claim: the
kernel's contract *is* the machine, and the proofs attach to frozen protocol specs (Appendix F).

**And the freeze binds *behavior*, never construction.** This document says what the machine
must do — the observable semantics, the conditions, the bounds — and is deliberately silent on
how any of it is built: no µop count is architectural (§1's cracking license), no epoch check
must be a runtime compare (`FILL_TIME_EPOCH`, §11.2), no protocol machine must be the naive
transcription of its spec (Appendix F — the mechanized spec is the *behavioral* definition an
implementation refines, not a netlist), and Appendix E is the standing catalog of exactly this
freedom: every license an implementation holds to diverge from the described mechanism, each
with the unobservability condition that keeps the divergence invisible. A laptop part and a
meter-scale part are both conforming LNP64 machines precisely because the document froze what
programs can see and nothing else.

**This document is self-contained for everything the chip decodes.** The dividing line throughout is a
single test — *does a hardware engine decode and execute it?* — and everything that passes is frozen here:
the opcode set and instruction semantics; the register / authority / memory / fault / calling-convention
models; the **encoding** (formats and slot positions §1, the opcode map §1.1, the FP subfields §14 —
complete, no external table needed); the **domain-native control families** (§16: every
hardware-owned domain, authority, object, set, cursor, stream, and lifecycle subfunction, which the engines
execute directly); and the **byte layouts of every structure the chip parses** (§17). A compiler, assembler, emulator,
or libc author can implement the full instruction stream and every chip-decoded structure from this file
alone.

The `env_open` record bodies are **`{type, version, length}`-tagged and designed to grow**. Their
chip-decoded framing and fields are frozen here and transcribed in `isa_spec.json`. State streams and
service protocols carry typed byte data; neither is a chip-decoded operation envelope.

Two companion layers a toolchain also needs are deliberately **not** here, because **the chip does not
decode them**: the **toolchain psABI / object format** (`object_format.md` — ELF, program headers,
relocations; the *loader* parses these, never the chip), and **service-profile semantics** (typed
gate/message protocols dispatch to a service domain and their bodies remain opaque bytes to silicon —
hardcoding those would freeze a filesystem/socket ABI into silicon, the exact
rigidity §16.6 avoids). A third companion exists *because of* Law 6: the **personality
layer** (`personality_unix.md`) — the mapping from this document's machine-semantic conditions, transfer
classes, and events to errno, CLOEXEC, and signals.

Behavioral background:
`unified_call_model.md`, `unified_memory_model.md`, `timer_object.md`.

## 0. The Laws

This document has laws. Every mechanism in it is a corollary of exactly one of them, and every
apparent exception is either derived from a law or listed in Appendix B with its reason. The
catalog carries the traceability matrix (`isa_spec.json` `law_traceability` — each mechanism family
names exactly one law or its Appendix B entry), the consistency gate validates it, and a mechanism
that cannot name its law does not merge. (Derivation parentage is single-parent; every mechanism
must additionally *preserve* all eight laws' invariants, which the §0.1/§0.2 walkthroughs check by
requiring all eight to fire in every walk.)

1. **Control crosses a protection boundary only through a gate** — in both directions, including from
   silicon. There is no second delivery mechanism. A fault is the machine calling you. (§9)
   **Corollary — the delivery-targeting rule: a gate fires at the party responsible for the
   resource, never merely the party that touched it.** A fault delivers to the faulter (it owns its
   instruction stream, §9.3); a page request to the pager (it owns residency, §15); a cancellation
   to the callee (it owns its unwind, §9.4); a debug event to the debugger's endpoint, never the
   target's own call path (it owns the observation, §16.3). Every delivery in this document chooses
   its target by this rule, and a proposed delivery that cannot name its responsible party is
   misrouted by definition.
2. **Authority is a held reference validated against a live epoch cell.** Death happens in one place.
   Revocation, reuse safety, translation freshness, and service identity are one check. (§3)
3. **The engines are substrate.** They hold no authority, occupy no position in the domain tree, and
   execute mandatory intrinsic instructions directly beneath delegated architectural state. All
   authority originates in the reset grant to the
   first domain — which is an ordinary domain. Hardware and software objects are the same thing at
   different points on a latency axis. (§11) In conventional security terms the engines are the
   **reference monitor** — non-delegable *mechanism* authority (they check, install, revoke,
   enforce) held by nothing that is a principal; "no authority" means no *held, delegable*
   authority, never "nothing trusted." The proof target is the whole engine set (Appendix F,
   `tcb_roster.md`), never a small checker.
4. **Architectural time is one monotonic timebase.** Every other clock is a view. Running-machine
   interfaces use ticks; canonical nanoseconds exist only in the inter-machine serialization format.
   (§8) At scale the timebase is per-volume with an architecturally bounded
   skew (§8.1): monotone within a coherence volume, skew-bounded across — one timebase as the limit of
   bounded skew, never a second clock.
5. **Every instruction boundary is a preemption point.** Unconditionally. The machine contains no
   non-preemptible region. (§6) The longest non-preemptible interval is **one bounded instruction**
   — every instruction either parks (a park is a preemption point) or completes within a latency
   bounded by a distance some party named (Appendix C; engine ops are asynchronous past their
   issue, §11.1); the preemption latency an admission analysis charges is that named bound, never
   zero, never unbounded, never a region.
6. **The decoded surface contains no personality-specific policy or personality-defined semantics.**
   Mechanism names may use familiar systems vocabulary (`mmap`, `futex_wait`, `FileDescription`), but
   their meanings are machine-semantic and personality-neutral; POSIX mappings remain software. (§13)
7. **A domain's universe is constructed under five parent-authorized, non-escalating views** — capability
   admission universe, explicit service-import universe, budgets, MachineView, ClockView. The live capability table is
   domain-local mutable state populated beneath that ceiling, including by sibling/service transfers;
   it is not a projection of the parent's current slots. **There are no other facts.** (§16) The physical
   machine is the fixed point of the view lattice — reached only by identity views, descending from the
   unaddressable reset grant, never nameable from inside the tree. "Bare metal" and "deeply nested guest"
   are the same object at different points in a lattice. Construction occurs through an unpublished
   builder whose effective state is invisible until one atomic publication; this is the transaction
   form of the same closure law, not a second control plane (§16.1). “Non-escalating” is authority/configuration
   closure; ClockView values are flattened transforms, not recursively multiplied set elements (§16.7).
8. **Locality is authority's shadow.** A domain's tiles, memory, and engines occupy one connected
   region; the domain tree is a spatial containment tree; and **no architectural operation crosses a
   distance the program did not name.** (§15, §16.7) The domain boundary is simultaneously the trust
   boundary, the coherence boundary, the naming boundary, and the distance boundary — one line, four
   meanings, **each default-deny rather than partition-identical**: nothing crosses the line — no
   authority, no name, no coherent sharing, no distance — except by an explicitly named grant.
   Domains share volumes, and granted frames coherently span domains; the claim is that every such
   crossing *was named by its grantor*, never that the machine's coherence partition equals its
   domain partition. The machine's one candidate lie — a load that looks like a cycle and is a fabric crossing —
   is not priced; it is made unconstructible (§15's locality classes).
   **Corollary — the cost-locality rule: an operation's cost may scale with the authority span or
   distance that operation names, never with machine size, domain-ancestry depth, or unrelated
   activity elsewhere.** Its instances: invalidation bounded by the referent span's diameter (§3),
   depth-independent translation (§15 — authority nests, translation does not), per-volume tag
   namespaces (§15), no global runqueue or utilization ledger (§16.4's distribution rule),
   revocation priced by delegation reach (§3), and far memory unconstructible as a pointer (§15).

## 0.1 One walk through the machine (read this before the reference)

The rest of this document is reference-ordered for the implementer. This section is one scenario at
full depth, followed end to end, so that every law fires once in front of you before the tables
begin. Nothing here introduces mechanism; every sentence is a pointer into the reference.

**The cast.** A container `C` runs inside an enlightened guest kernel `V`, which runs inside a
tenant domain `K` (`MEASURED` at birth for local audit, §16.3), which runs under the host.
Four levels of domain tree — and that sentence is already the first thing to notice: it took no
hypervisor mode, no nested page tables, no VM noun (Law 6). Each level is an ordinary domain whose
universe is constructed under its parent's five non-escalating views (Law 7), so `C` cannot observe its
own depth, and `C`'s loads and stores walk **one** VMA tree into a domain-tagged TLB entry — O(1) at
depth four, because authority nests but translation never does (§15, the depth invariant). The
nesting is *spatial* too (Law 8): `C`'s tiles are a connected region inside `V`'s inside `K`'s, so
every invalidation and every fault in this story fans out over `C`'s small volume, never the
machine — deeper meant *cheaper*. `C` holds
a `RESERVATION{budget, period}` admitted up the ancestry chain once, at configuration (§16.6) — and
because its memory is pager-backed, admission recorded the live pin leases covering the memory its
deadline-conforming path claims (`PIN_RESIDENT`, §15). Hold that conditional fact; it is about to matter.

**A store faults.** A worker thread in `C` stores to a cold page — pager-backed, non-resident.
Nothing is delivered to `C`: no signal, no exception vector, no handler. The thread **parks at the
instruction, exactly like any blocking op** (§15) — freezable, terminable, restartable — and the
park record is charged to the waiter's own domain (§16.4: engine state is never attributed to
nobody). `C` observes a memory stall, which is physics, not deception (Law 7: its budget is a
granted fact that may exceed physical truth). The gate that fires belongs to someone else: the
machine writes a frozen 56 B **page-request record** (§15) onto the pager endpoint designated by
the *backing* — Law 1's delivery-targeting corollary in action: the gate fires at *the party
responsible for the resource*, and the responsible party for residency is the pager, not the
faulter.

**The pager answers.** The pager here is `V`'s swap service. The record it `recv`s carries the
offset, the access, its own `pager_cookie` — and `faulting_domain` as an **opaque backing-local
cookie**, because engine-written records contain only domain-local names, ever (Law 7, §16.7): the
pager can group and charge per toucher; it can never name a foreign domain. The record also carries
the **designation epoch** (Law 2): if `V` had retargeted this backing to a different pager one tick
earlier, this request would already have been re-delivered to the successor, and a `SUPPLY` from
the old pager dies `-STALE` against the bumped cell — the two-pagers race is not a protocol, it is
one epoch check. The pager calls **`SUPPLY`** on the backing, keyed by object offset — never a
per-domain address op, so one shared page costs one `SUPPLY` no matter how many domains map it —
naming a **charge-target** it holds the `CHARGE` right over (§15 rule 1). The engine validates the
epoch, installs the frame, records the charge per-frame, and resolves the offset to every mapping
VMA through its reverse map. The pager holds no state the machine cannot reconstruct: the engine
owns the outstanding-request set, so a pager that crashes here and restarts is simply re-delivered
everything, and no thread is ever stranded on a dead pager's memory (§15).

**The thread resumes.** The engine unparks it; the store retires. Total time lost: the pager's
latency. This cold access was outside the ledger-covered memory set, so that execution left the
admitted end-to-end WCET contract; the CPU reservation remained valid, but no deadline theorem covered
the fault. On a conforming admitted path every instruction fetch, stack access, data access, and
engine-written range is ledger-covered, which removes the pager only from that path's trusted set.
Hardware need not infer “hot” versus “cold”: the accessed mapping either has a recorded covering lease
or it does not (§15, §16.1).
Every clock in this paragraph was ticks (Law 4); every boundary the thread crossed was preemptible
(Law 5).

**Meanwhile, the host migrates `K` — live.** A coordinator has already used `mark` and
`changes.begin` to pre-copy state. It now obtains a `FULL_SUBJECT` quiescence token and opens the final
domain state stream (§16.8). Our worker thread may at this instant be parked mid-fault again — and this is
where the blocked-op contract pays for itself: every in-flight engine op is driven to a defined
boundary — complete, or cancelled-restartable per §9.3 — because **`OP_RESTARTABLE` and the frozen
restart recipe were checkpoint machinery all along**. The park record, the donation state, the
timer arms serialize as `ENGINE_STATE` (§17.9), with engine-private identifiers renamed to
stream-local names on the way out. One temporal cut samples every comparator; each absolute tick deadline is exported as
**remaining-duration in canonical nanoseconds** — the only place nanoseconds exist in this
architecture, because the boundary between machines is where unit conversion belongs (Law 4 governs
a running machine). This is transparent migration, so import subtracts the entire elapsed interval
since that cut; only an explicit suspended-checkpoint stream would pause it. And the stream is **AEAD-protected under the fleet's owner-rooted keys,
always** (§16.8/§16.9): integrity and confidentiality against every party **on the wire** — while
the host, which owns both machines, reads what it owns, because on this machine **the owner is
never the adversary** (Appendix H: there is no distrust zone; a tenant's protection *from its
host* is a contract between people, and this architecture refuses to pretend silicon can replace
it).

**The far side.** `state.import` plus `state.commit` re-check every invariant, re-mint physical cells while preserving
every software-visible numeric reference and check value, rebuilds the
thread directory, expires every deadline that matured in transit, and re-absolutizes each survivor
against the destination timebase; a stream
failing any check imports nothing, atomically. `K`'s wall clock is rebased by writing two fields of
a ClockView; view-absolute timers heal through the same epoch mechanism as everything else (§8.1).
The coordinator then commits an exactly-once `handoff` and resumes the successor. The migration is
*live* because post-copy is not a feature — it falls out: the destination
address space imports with a `PagedBacking` whose pager feeds pages from the source, so `C`'s
threads run immediately and their cold pages arrive by **exactly the walk you just read**, fault →
park → request record → `SUPPLY` (§15/§16.8). The outstanding request our thread was parked on?
The destination pager binds to the backing and is re-delivered it — the restart rule and the
migration rule were the same rule.

Count what fired: one gate mechanism carried a fault and pager request while explicit service gates
carried software-owned state (Law 1); one
epoch-cell check closed the retarget race, revocation, and import re-minting (Law 2); the engines
executed all of it holding no authority anywhere in the tree (Law 3); time was ticks until the
exact boundary where machines differ (Law 4); every parked thread stayed preemptible, freezable,
serializable (Law 5); no personality policy entered machine semantics (Law 6); and nothing any party observed — cookie, stall,
or state stream — exceeded its five views (Law 7); and no operation crossed a distance the
program did not name — the fault stayed in `C`'s volume, and the coordinator explicitly named the
state stream transport and final handoff (Law 8). If any step above had needed an exception to a
law, that would have been a design defect, and this section exists so such defects have nowhere to
hide. But this scenario is the machine's home turf — paging, migration, nesting are what it was
built to make composable — so §0.2 walks a second scenario chosen to be hostile instead.

## 0.2 A second walk, chosen to be hostile (four mechanisms that never met)

The first walk exhibits the machine where it is strongest. This one is an audit: four mechanisms
designed in four different sections — debug-freeze (§16.3), donation inheritance (§9.2),
cancellation (§9.4), the borrow lifetime (§17.1c) — collide in one scenario none of them was
written for. If every transition still has a named mechanism, the laws are generative, not
decorative.

**The cast.** Service domain `S` (`TIMESHARE`, low priority) exposes a **serialized** call gate `G`
(`concurrency = 0`, `cancel_policy = 0`, a finite `max_donation`). Client `B` shares an address
space with `S` (the library-compartment pattern) and `gate_call`s `G` lending a **call-scoped
borrow window** over one of its buffers (§17.1c). While that activation runs, three things happen
at once: a debugger attaches to `S` and freezes the activation's thread mid-flight; an RT chain
arrives wanting `G`; and a `cap_revoke` with `quiesce` policy lands on the memory cap backing the
borrowed range.

**The attach.** The debugger's session manager holds `S`'s domain cap with the `DEBUG` right, so
attach is `debug.new` + `quiesce(debug_target, ACTIVATIONS)` (§16.3/§16.5) — no debugger mode, no stop noun, no in-target
stub the ISA had to define (Law 6): a capability op on an object, mid-`gate_call`, no consent. The
freeze is a scheduler hold, and Law 5 is what makes it clean: every instruction boundary preempts,
so the hold lands at a boundary with nothing torn mid-instruction. And `debug.new` answers
*every* holder of the `DEBUG` right — no birth flag exists that revokes it (Appendix H: no domain
is uninspectable by its dominator chain; inspection is authority (Law 7), and the authority is
always mintable by the chain that granted the domain its existence).

**The RT chain arrives.** It `gate_call`s `G`, finds the serialized gate held, and the engine
extends its donation to the holder — transitive priority inheritance through engine-visible
ownership (§9.2). But extension is a *charging* rule, never a wake rule: the frozen holder runs on
the chain's reservation only when it runs at all, and a scheduler hold means it does not run. No
budget drains (CPU charges only while the activation runs), the chain's own reservation is
untouched (§16.3: debug breaks the *target's* RT bounds, never anyone else's), and the wait is
bounded because the donation deadline — derived, never an operand, ticking in architectural time
(Law 4) — is the architected bound on this unserviceable wait **because this chain has a finite
caller deadline or the gate has nonzero `max_donation`**. A chain with neither accepts an unbounded
wait. Note also what the collision never
involved: distance. `B`, `S`, and the gate share one volume (a shared-address-space gate cannot
exist otherwise, §17.1c), so every donation, freeze, and cancellation in this walk is
volume-local — nobody here named a fabric crossing, so none occurs (Law 8).

**The deadline fires.** §9.4's ordered flow: the caller detaches **at once** — donation revoked,
`-TIMEOUT`, without waiting on the callee — subject only to the step-5 quiesce, which is engine and
fabric work needing zero callee instructions (Law 3: the teardown is executed by substrate holding
no authority of its own). The cancellation posts to the frozen callee as a machine call (Law 1: it
comes from outside the callee's instruction stream, so it *is* the EVENT-gate path — and by the
delivery-targeting corollary it goes to the callee, who owns its own unwind). Here is the collision
the sections had to answer jointly: a frozen thread has no next instruction boundary, so Tier-1
delivery cannot land. The pinned rule (§9.4): the cleanup deadline **never pauses for a freeze**
(Law 4 — nothing stops the timebase), and Tier-2 force-termination is an engine-executed teardown a
scheduler hold cannot defer. Thawed in time, the callee cleans up cooperatively; still frozen at
the deadline, the activation ends anyway, and the debugger observes an ordinary target-side exit —
a `DEBUG` right that could park an activation un-cancellably would be authority the right does not
contain.

**The revoke, concurrently.** The `cap_revoke` cannot even *name* the borrow window — no handle, no
slot, no lineage; the window is not a capability (§17.1c). It names the caller's mapping, and the
borrow is a permission overlay sharing that mapping's fate: the epoch bump kills the overlay with
the translation (Law 2 — freshness is one check, and the overlay was never a second source of
truth), the `quiesce` drain finds nothing mid-op to wait on (Law 5: the frozen thread sits at a
boundary), and the detached caller resumes **only after the quiesce acknowledges** — across the
whole chain — so no lingering translation or DMA burst can touch the buffer the caller is about to
reuse (§9.4 step 5). When the activation later dies, the frame teardown finds the overlay already
dead; teardown is idempotent with revocation because both are the same epoch mechanism.

**And if the debugger simply crashes?** Detach-by-death is the same path as detach-by-choice
(§16.3): the freeze clears, the thread reverts to its pre-event disposition, resumes, and takes the
already-posted cancellation at its first instruction boundary — the §9.4 flow continues as if the
debugger had never existed. A crashed observer strands nothing (Law 7's quiet dividend: the
observation was never part of the observed machine's facts).

Count again: all four mechanisms met for the first time, and the walk needed **one** sentence the
reference did not already contain — the cancellation-deadline-versus-freeze rank, which this
document states in §9.4 because the walk demanded it. That is the section doing its job in both
directions: the transitions that composed prove the laws generative; the one that did not is now
pinned instead of latent. The reference begins now.

## 1. Encoding

Every instruction is a **single 64-bit little-endian word**. One major opcode in `[63:56]` (256-entry
space). Register slots occupy fixed positions regardless of role; a slot a format does not use is zero.

```
opcode [63:56]   rd [55:51]   rs1 [50:46]   rs2 [45:41]   rs3 [40:36]   rs4 [35:31]   rs5 [30:26]
```

The 32-bit immediate sits in the 32 bits below the lowest register slot a format uses:

| Fmt | Operands | imm32 | reserved | hint zone |
|---|---|---|---|---|
| R | `rd, rs1[, rs2[, rs3[, rs4[, rs5]]]]` | n/a | `[25:0]` | n/a |
| I | `rd, rs1, imm32` | `[45:14]` | n/a | **`[13:0]`** |
| S | `rs1(base), rs2(src), imm32` | `[40:9]` | n/a | **`[8:0]`** |
| B | `rs1, rs2, off` (`off = sext(imm32) << 3`) | `[40:9]` | n/a | **`[8:0]`** |
| U | `rd, imm32` | `[50:19]` | `[18:0]` | n/a |
| J | `rd, off` (`off = sext(imm32) << 3`) | `[50:19]` | `[18:0]` | n/a |

**The all-zeros word is permanently illegal.** Opcode `0x00` is architecturally pinned as
illegal-instruction **forever** — no future revision may assign it — so execution falling into zeroed
memory faults, in every implementation, for all time. (Unassigned opcode bytes, by contrast, may be
claimed by future additive revisions; software must never squat on them — the architected `trap` exists so
it never needs to.)

**One conformance class (no subset machine exists).** LNP64 means **everything in this document**:
the integer core, scalar FP (§14), the vector unit (§18), the full engine and object surface,
debug, serialization, and the defense-in-depth structures. **No optional instruction
exists**; there is no application/minimal split, no feature matrix, no `-march` variant space —
a binary compiled against this document runs on every conforming machine **under a full execution
view** (§14), and a compiler targets
*the* machine, singular: no multiversioning, no dispatch trampolines, no runtime probe in a
`memcpy`. Future growth is **totally ordered revisions** (a machine conforms to LNP64v*n*, which
contains all of v*n−1*; the reserved blocks are where v*n+1* lands) — never à-la-carte
extensions. A microcontroller-class LNP64 is deliberately nonconformant: there is no subset
machine. What remains configurable is **per-domain policy through the views** (§16.7): a MachineView may
*withhold a grant* from a domain — that is parental control over one machine, never a hardware
variant, and §11.4 states the consequence for `FEATURES`. The withholdable surface is a
**closed, positively defined list** (§2.1); the system core — including domain construction
itself — is unconditional on every conforming machine, for every domain, forever.

**Decode rule.** In the **base** formats, `RESERVED` bits are zero and the decoder rejects non-zero
reserved bits. An opcode may instead define an **extended subformat** that decodes part of that region as
operation-specific fields that **do** affect the result (the FP profile §14 decodes `fmt`/`rm` in the
R-format `[25:0]` region; `sel` §4.1 and `fsel` §14 decode their condition codes in unused register-slot
bits — a slot a format does not use is zero, so an opcode may claim it as an operation field; FP
load/store get distinct opcodes per width, §1.1). Such fields are defined by the opcode and are not reserved.
**The cracking license, general (Appendix E):** an implementation **may decompose any instruction
into any number of internal operations**, provided the architectural semantics — results, ordering,
fault points, atomicity where claimed — hold exactly; **nothing architectural observes µop count.**
A select may crack into compare-then-select, a pair op into two accesses (§6's instance of this
rule), an engine op into a sequenced transaction; the ISA freezes what an instruction *means*,
never how many internal operations it becomes. **The port-discipline corollary, stated for the
wide-core generation:** every ordinary fixed-latency compute instruction (integer §4, FP §14,
vector §18 compute) reads at most **3 data sources** and writes **1 destination**; a vector op
adds at most two architected extras — the governing mask read and, under merge masking, the
destination's prior-value read — and nothing else, ever. A renamer and register file sized
3R/1W per lane (plus the mask port class) covers the whole compute surface. Instructions
naming more slots (the pair ops' even pairs, `stx`'s named slots, gate/endpoint/system forms)
are memory or engine operations, and the cracking license above is their guarantee: nothing with
more than three data sources must be executed as one internal operation. The **`HINT` zones** (I
`[13:0]`, S/B `[8:0]`) are different again: any value decodes successfully and an implementation may
**ignore** them (timing only, never a result). They carry forward-compatible compiler facts (branch
weights, `noalias`/alignment/non-temporal). The same binary runs on v1 and a future out-of-order core
because hints never change architectural state.

**Custom-format (system/endpoint) ops.** Ops whose operand list does not match R/I/S/B/U/J (the §10
endpoint ops, the §11 engine fast paths, `set_pcr`, the futexes) are **custom format**, fully determined
by these rules so a decoder/assembler is derivable: **(a)** operands fill the **fixed slot positions**
above, left to right in the order the op's *Form* column lists them (`rd` → `[55:51]`, then `rs1`..`rs5`)
— **unless the Form names slots explicitly, in which case the named slot wins over positional order**
(`stx` §5 and `gate_return` §9 are the worked examples); **(b)** an operation-specific immediate may
occupy only a bit region **strictly below its lowest occupied register slot**. Thus the ordinary
I-format field `[45:14]` cannot coexist with `rs2`/`rs3`/…, but a narrower opcode-defined immediate
below an occupied `rs2` is legal when the opcode explicitly assigns it (`ld.aq`/`sd.rl` §6 assign
`imm12[25:14]`). Small constants that
are the *only* non-`rd`/`rs1` operand (a `get_pcr` selector) go in the `[45:14]` immediate field;
**any value that coexists with `rs2`+ is a register operand unless its opcode explicitly assigns a
narrower below-slot immediate; every 64-bit value (timeouts, deadlines) is always a register operand**
(this is why `wait`/`futex_wait` take their deadline in a GPR, §6, §10). Every slot and
immediate the Form does not name is **reserved-zero**.

**The two architected register-encoding exceptions** (both declared here, at the invariant they qualify —
the narrowed-immediate rule above is general, not an exception):
1. **The PCR subformat** (§8): `get_pcr`/`set_pcr` carry their 5-bit selector as a **literal in the
   `rs1`-slot bit positions `[50:46]`** — neither a register read nor an immediate — precisely so
   `set_pcr` can name both the selector *and* an `rs2` value without colliding with the immediate field.
   No other op uses a literal-in-register-slot encoding.
2. **The register-pair forms** (§5, §6, §14): seven ops (`casq`, `ld.q`, `sd.q`, `ldp`, `sdp`, `fld.q`,
   `fsd.q`) name **even-numbered register pairs** — an odd register in a pair slot is
   illegal-instruction. This is the one qualification on "any GPR in any slot"; it is confined to exactly
   these seven ops and never grows.

**Immediate signedness.** Every `imm32` is **sign-extended** to 64 bits before use (arithmetic, address
formation, branch/jump offset) unless the opcode is an explicit unsigned/placement form. Specifically:
`liu` *places* its bits into `[63:32]`; `sltiu` sign-extends its immediate and then performs an **unsigned
comparison** (inherited and kept — every RISC-V compiler port already knows it, Appendix B); **branch
offsets are always signed** (`blt`/`bge` compare `rs1,rs2` as signed, `bltu`/`bgeu` as unsigned — the `u`
variants qualify the *register* comparison, never the offset). `addi` and all address arithmetic wrap
modulo 2^64 (no overflow trap).

**Return-value ABI.** Every instruction that returns a status, count, capability, **or address** writes
`rd` such that **success is non-negative and failure is `-CONDITION`** (§13.1 — the frozen
machine-semantic condition enum; `rd < 0` is unambiguously an error). This holds because three
architectural invariants keep every success value below 2^63: **(a)** capability handles have bit 63 clear
(§2.2); **(b)** the **user virtual-address space is the low canonical half** (bit 63 = 0), so every
`mmap` address is non-negative; and **(c)** a single op's transferred/event **count cannot reach
2^63** — the architected maximum single `read`/`write`/`recv`/`wait`/`random` length is `2^63 - 1`, and a
larger `len` operand is rejected `-BOUNDS`. **This extends to every architectural identifier an op returns
in `rd` or an `out` slot** — thread IDs, member IDs, submission handles, queued/completion counts — all
allocated in `[0, 2^63)`. And by the Law-7 naming rule (§16), every such identifier is **subtree-scoped or
opaque, never a machine-global counter**. Raw machine values that legitimately use the full 64 bits are
**not** returned in `rd` as a status: `get_pcr` returns a raw machine value (a tick counter may have bit
63 set) and is *not* a condition-returning op — an undefined/ungated selector **faults** (§8);
object fixed-width getters use their definition-fixed register result shapes and byte descriptions use
streams. The other deliberate exceptions: `feq`/`flt`/`fle`/`fclass` write plain FP predicate results
(§14); and **`gate_call`'s value register carries the callee's full-range reply while its
gate-level status rides the separate `r3`** (§9.2 two-result reply) — so a gate reply, like a
raw getter, is not a `-CONDITION`-in-`rd` value. None of these are error-returning system ops in
the single-register sense.

**Large length is not a large non-preemptible instruction.** Any engine byte-moving operation whose
operand may exceed 64 KiB issues in one bounded instruction and then runs as a parked engine activity
in architected work quanta of at most **64 KiB**. Every quantum boundary is a cancellation,
machine-call, scheduler, and migration boundary; the issuing thread is already parked at an instruction
boundary. Stream operations expose the existing partial-byte result when interrupted. Message enqueue
and engine-record operations may fill reserved staging over many quanta, but publish their logical
commit in one bounded final transition. `recv` writes ordinary destination memory over its quanta and
claims atomicity only for dequeue/cap installation (§10.2). Thus the `2^63-1` representational length bound never creates
a proportional non-preemptible interval; timeshare latency is bounded by one 64 KiB quantum plus the
published engine-arbitration bound.

**Range overflow is always rejected.** Every op that takes a `{ptr, len}` or `{addr, len}` pair computes
`base + len` in 64-bit unsigned arithmetic and **rejects a range that wraps past `2^64`** *before* any
effect: a checked system/endpoint argument returns `-BOUNDS`, and a direct memory operand (the futex word,
an `ld`/`sd`) faults like any other bad access (§9.1). A wraparound range is never silently clamped or
partially applied. **`isync` is the single exception** (it writes no `rd` and never faults on its range,
§6): a wraparound `isync` range is a **defined no-op** — consistent with `isync` being an advisory i-cache
invalidate whose only effect is to refetch, never to fault or return status.

**Result channel (one canonical rule).** A fixed-form operation whose primary result is one scalar,
capability, builder, set, cursor, stream, or activation reference returns it in `rd`; failure returns a
negative condition in `rd`. Two-result forms name `rd0, rd1` explicitly — the worked example is
`gate_call`/`gate_return` (§9.2), whose reply is `{value in call_rd, gate-level status in r3}`
so a callee's payload keeps the full 64-bit range while gate-level teardown conditions stay
unmultiplexed, the synchronous twin of the §17.8 completion record's `{status, value}` split. No instruction returns through
a generic output array. Collections use cursors, byte representations use streams, and service-defined
results use gates or endpoints (§16.5). A fused or self-directed spelling is an operand/result adapter
around one canonical transition under §16.2's merge rule; it never owns independent lifecycle,
cancellation, accounting, ordering, or failure semantics.

**Full-range getter exception.** A fixed scalar getter whose result type admits every `u64` value
returns all 64 bits in `rd` and never encodes a condition there. Invalid selectors, wrong or denied
capabilities, and dead/stale referents raise the ordinary precise synchronous instruction-fault
machine call; `rd` is unchanged. This is the same rule as `get_pcr`, and applies to the catalogued
raw getters: each class's typed `*.get` operation, plus `dget`/`dget2`,
and `get_pcr`. It does not apply to mutations that
return a bounded value or to cursor iteration, whose status/result contract remains explicit.

**Architecture vs implementation.** The *architecture* fixes instruction semantics, the memory model
(§6), the capability model (§2.1), the fault model (§9.1), and the speculation contract (§2.1); it does
**not** mandate a pipeline. The **v1 implementation baseline** is in-order and non-speculative, which is
what makes precise machine calls (§9) cheap; precision is itself **architectural**, so a later
out-of-order, cached, or superscalar implementation is admitted and runs the same binaries (the hint zones
exist for exactly that). Scheduling latency is **not** uniform: common integer ALU/shift/compare ops are
fixed short-latency, while loads, division, FP divide/sqrt, atomics, and every §10–§11 endpoint/system
operation have their own (variable, possibly blocking) latencies. Other invariants: no condition flags; no
multi-instruction or software-created non-preemptible region (Law 5)—the longest atomic execution
interval is one instruction, bounded by that instruction's published class and parameters; 32-bit immediates (a whole struct/frame reachable in one
instruction); orthogonal operand slots (any GPR in any slot, except `r0` reads as zero and discards
writes, and the seven pair ops above).

### 1.1 The opcode map (design-order ranges)

The map is **range-organized: each contiguous range belongs to one functional unit**, and the ranges
are the frozen thing — an encoding fact, observable in every binary. That a decoder can therefore be
a handful of range compares rather than a 256-entry lookup is an *existence proof, not a mandate*;
this document freezes observable behavior and bounds, never a construction, and where it sketches
one (here, or the §3 invalidation reduction) the sketch shows the bound is achievable — any
implementation meeting the bound conforms. Opcode bytes are also listed inline in each section; this
table is the flat view.

| Range | Unit | Assignments |
|---|---|---|
| `0x00` | — | permanently illegal |
| `0x01` | — | `trap` |
| `0x02–0x0f` | — | **reserved** (wild-jump landing zone: kept illegal so jumps into zeroed or poisoned memory fault) |
| `0x10–0x47` | integer | `add sub mul mulh mulhu div udiv srem urem` (0x10–18) · `and or xor andn orn xnor not` (0x19–1f) · `sll srl sra rol ror` (0x20–24) · `slt sltu sel` (0x25–27) · `sh1add sh2add sh3add` (0x28–2a) · `add3 carry ovadd ovsub ovmul ovmulu` (0x2b–30) · `bext bexts bins fsl fsr clmul clmulh` (0x31–37) · `sext.b sext.h sext.w zext.b zext.h zext.w` (0x38–3d) · `clz ctz popcnt bswap16 bswap32 bswap64` (0x3e–43) · `min max minu maxu` (0x44–47) |
| `0x48–0x59` | integer (imm) | `addi andi ori xori` (0x48–4b) · `slli srli srai rori` (0x4c–4f) · `slti sltiu liu auipc` (0x50–53) · `addiw slliw srliw sraiw roriw slli.uw` (0x54–59) |
| `0x5a–0x5f` | | reserved (immediate growth) |
| `0x60–0x6b` | control | `jmp jal jalr` (0x60–62) · `beq bne blt bge bltu bgeu` (0x63–68) · `lpad` (0x69) · `jalr.cfi` (0x6a) · `trapcc` (0x6b) |
| `0x6c–0x6d` | control | `bci trapcci` (0x6c–6d) — the immediate-compare forms (§7) |
| `0x6e–0x6f` | | reserved (control growth) |
| `0x70–0x8b` | memory | `lb lbu lh lhu lw lwu ld` (0x70–76) · `sb sh sw sd` (0x77–7a) · `ldx stx` (0x7b–7c) · `ld.aq sd.rl` (0x7d–7e) · `ldp sdp` (0x7f–80) · `ld.q sd.q` (0x81–82) · `prefetch` (0x83) · `flw fld flh fld.q` (0x84–87) · `fsw fsd fsh fsd.q` (0x88–8b) |
| `0x8c–0x8f` | | reserved (memory growth) |
| `0x90–0x9b` | atomics | `amo` (0x90) · 0x91 **reserved atomics-growth space** (§6, Appendix G) · `fence fence.acq fence.rel fence.acq_rel fence.sc` (0x92–96) · `isync pause` (0x97–98) · `futex_wait futex_wake futex_requeue` (0x99–9b) |
| `0x9c–0x9f` | | reserved (atomics growth) |
| `0xa0–0xba` | system | `gate_call gate_return` (0xa0–a1) · `send recv` (0xa2–a3) · `read write readv writev` (0xa4–a7) · `wait` (0xa8) · `cap` (0xa9) · `domain.build` (0xaa) · `domain.exec` (0xab) · `cqueue` (0xac) · `readv_at writev_at` (0xad–ae) · `0xaf` **reserved** · `gate_tail` (0xb0) · `0xb1` **reserved** (Appendix G) · `mem_grant` (0xb2) · `mapping map.protect munmap_range map.demote` (0xb3–b6) · `get_pcr set_pcr` (0xb7–b8) · `env_open random` (0xb9–ba) |
| `0xbb–0xc9` | typed hardware objects | `channel` (0xbb) · `counter` (0xbc) · `gate` (0xbd) · `timer` (0xbe) · `irq` (0xbf) · `waitset` (0xc0) · `window` (0xc1) · `pmu` (0xc2) · `clock` (0xc3) · `filedesc` (0xc4) · `workqueue` (0xc5) · `debug` (0xc6) · `machineview` (0xc7) · `backing` (0xc8) · `device` (0xc9) |
| `0xca–0xce` | typed algebras | `set` (0xca) · `cursor` (0xcb) · `state` (0xcc) · `observe` (0xcd) · `lifecycle` (0xce) |
| `0xcf` | typed hardware object | `eventring` |
| `0xd0–0xeb` | FP | `fadd fsub fmul fdiv fsqrt` (0xd0–d4) · `fmin fmax fminm fmaxm` (0xd5–d8) · `fmadd fmsub fnmadd fnmsub` (0xd9–dc) · `fsgnj fsgnjn fsgnjx` (0xdd–df) · `feq flt fle fclass` (0xe0–e3) · `fround fsel fli` (0xe4–e6) · `fmv.x.f fmv.f.x` (0xe7–e8) · `fcvt.f2i fcvt.i2f fcvt.f2f` (0xe9–eb) |
| `0xec–0xef` | | reserved (FP growth) |
| `0xf0–0xf5` | vector | `v.int v.fp v.mem v.mask v.perm v.red` (§18; funcs frozen by number) |
| `0xf6` | | reserved, named: vector crypto block |
| `0xf7` | vector | `v.ff` — `0 ldff` (fault-only-first unit-stride load, §18); **vector-ABI ops** — `1 cntvb`, `2 cntve`, `3 addvl` (§18); funcs `4`–`63` reserved (segment loads, element-granular permute) |
| `0xf8–0xff` | | reserved (vector growth) |

FP memory ops live in the memory range because they are memory-unit ops; the FP range is compute only.
The standalone EventRing family opcode is `eventring` 0xcf.
Loads precede stores within each group. Reserved zones sit at range tails so growth stays in-range.

**Subsumed mechanisms (built once as a general primitive, not as a special unit).** Several
things a conventional machine builds as dedicated hardware or ISA surface are *instances* of a
general LNP64 mechanism here, so the special unit is never built — a shrink in verified
mechanisms and erratum surface, not merely in opcodes:

| Not built | Subsumed by |
|---|---|
| FP exception traps, trap-enable/mask bits, the FP fault path | non-trapping FP with sticky `fflags`; polled at software boundaries (§14) |
| Idle-management ISA (`mwait`/`monitor`, C-state control) | architectural tickless idle — sleep legal by arithmetic, gated by the closed wake set (§8.1, §16.4) |
| A second clock / guest timestamp-counter virtualization | time is a ClockView over the one timebase; a guest reads its view (§8) |
| Legacy timer chips + per-timer programming (PIT/HPET/PIC-class) | one timebase + the unified comparator; timers are objects (§8, §16.3) |
| Hardware transactional memory | unpublished builders + atomic publication (multi-object), bounded atomics + `casq` (lock-free) (§16.1, §6) |
| A separate breakpoint/debug-exception delivery path | the DebugTarget object reached by capability + the one gate delivery mechanism (§16.3, Law 1) |

## 2. Registers

32 GPRs, 64-bit. `r0` = zero (reads zero, discards writes). `r1` = `ra`, the ABI return-address GPR.
`r2`–`r9` = integer arguments (**8 contiguous argument registers**) / **`r2`–`r3` = the two-word
integer return pair** (`r2` alone for one-word results; 128-bit and two-member aggregate results
use the pair — the psABI's rule, stated here because the register file is where it binds).
**Narrow-integer extension (the canonical-form rule; the psABI's, stated here because the
register file is where it binds):** a sub-64-bit integer argument or return value travels
**widened per its type's signedness to 32 bits, then sign-extended to 64** (the form every
`W`-form result already produces). **Producers guarantee it; consumers may rely on it**:
`slt`/`sltu`, branches, and `sel` conditions over canonical narrow values are correct with no
re-normalization.
`r18`–`r27` = callee-saved (`s0`–`s9`); **`r18` (`s0`) doubles as the optional frame-pointer
alias `fp`** — an ABI naming convention for unwinders and debuggers, not an architectural role:
it remains an ordinary callee-saved GPR, and frame-pointer-omitting code uses it freely. `r30` = `tp`, the **ABI-designated thread pointer** (a real
ordinary writable GPR, placed beside `sp`). `r31` = `sp`. All
others caller-clobbered temporaries. **`tp` is a GPR, not a PCR**, so thread-local storage is reached by a
*single* ordinary load: `ld rd, offset(tp)`. Software may write `r30` with any ordinary GPR-writing
instruction. Gate and machine-call transitions save, preserve, or install it according to the crossing
ABI (§9, §17.5); “thread pointer” is an ABI use, not a write-protection rule. There is therefore no `TP`
PCR selector (§8). Capabilities are ordinary `u64` GPR values
(epoch-checked table handles, §2.2; the integer datapath is untouched). There is **no `FLAGS` register**
and **no separate architectural link register**: `jal`/`jalr` write the return address into a named GPR
(`r1` by convention) like any other result.

### 2.1 Authority model (capabilities, not privilege rings)

LNP64 has **no supervisor/user mode bit and no privilege ring** gating instructions. **No instruction is
privilege-gated by ring or mode**; and **the view-withholdable surface is closed and positively
defined**: a MachineView may withhold the `FEATURES`-class execution profiles (FP §14, vector
§18 — the disabled-opcode fault, §11.4's confinement/emulation framing) and the named grant
facts (`djit`'s `JIT_WX`, `mview.identity` scope, and counter/timebase
lenses §8.3), **and nothing else**. The system core — memory and mapping operations, typed
objects, endpoints, futexes, gates, and **domain construction on the domain's own budget** — is
the unconditional machine, withholdable by no view, exactly as `jal` is: subdividing yourself
crosses none of Law 8's four boundary meanings (no authority, name, coherent sharing, or
distance leaves the line), so there is nothing for a parent to deny — the parent's legitimate
interests are already served by budgets (grower-pays), views (children know no more than their
creator), and dominator inspection (nothing hides). A withheld grant is a view denial, not a
privilege gate. What an instruction can *reach* is bounded entirely by the **capabilities held in the
issuing domain's capability table**: memory by the VMA / page capabilities mapped into the domain;
objects, services, files, and devices by the object capabilities it holds; scheduling, lifecycle, and
resource policy by the domain capabilities it holds. Typed domain/object operations, the register-form system ops, and the rest
of §11 are therefore **not privileged opcodes**: each operates only on capabilities the caller already
possesses. A "kernel" or "hypervisor" is just a domain that holds more (and more powerful) capabilities;
no architectural state distinguishes it. The root set is established by **the reset grant**: the reset
controller mints the physical MachineView, root budgets, and device capabilities into the **first
domain** — an *ordinary* domain, freezable, serializable, budgeted, obeying every rule, distinguished only
by what it was given (Law 3, §11); all authority descends from that grant by explicit delegation, and the
grant event itself has no address — it can only be descended from, never referenced. Capabilities bound what a domain can touch; view closure (§16) bounds what it can know; both are granted, subsetted, and attested the same way.

**Root-death base case.** Every Domain has a reaper; the last live parentless Domain's reaper is
the reset controller. When that Domain reaches `DEAD`, the controller performs machine reset
before any reaping. This is stated in terms of the **last parentless Domain**, rather than a
distinguished id, because a reset-grant policy may mint more than one root. Death includes
`dexit`, `dkill` by a holder to which that root delegated the required lifecycle authority, and
an unhandled fault after escalation reaches a parentless Domain. A live but wedged root is not
dead; watchdog policy remains physical/platform policy, and a watchdog bite induces death and
therefore the same reset transition.

Reset has exactly the platform's boot semantics: all Domains and volatile engine state are
destroyed, measurements restart, and the reset grant mints a fresh root set into an empty
machine. There is no implicit crash checkpoint or gentle recovery path. Only state software
made durable before death survives (including persistent device media); state streams remain
the explicit checkpoint mechanism. Root self-update uses atomic `dreplace`, software escrows
copies of non-rederivable manifest capabilities early when availability requires it, and root
`dexit` is the documented last-resort recovery ceremony. Thus any authority catastrophe is
recoverable at the price of the world, without a machine-wide reclaim capability inside the
capability model.

**The speculation contract (binding on every implementation, forever).** v1 is non-speculative by
construction; the contract is architectural, so an out-of-order successor is bound by it:
**(1) authority precedes speculation** — no access may be performed speculatively unless it passes the
same capability / VMA / domain-tag / epoch checks the architectural path would apply, under the authority
that is architecturally current at issue (a speculative path can never dereference what the real path
could not); **(2) no cross-domain residue** — microarchitectural state trained or filled speculatively
(predictors, caches of authority decisions, prefetches) must never be observable across a domain boundary,
by partition or scrub at the crossing. The same rule binds architecturally-filled shared state: **any cross-domain-shared cache of
authority or dispatch state** — translation tags, stamp-resolution caches, typed-function routing caches,
and their successors — **is partitioned by domain tag, scrubbed at the crossing, or carries a
hardened-config disable knob.** An implementation that cannot meet both clauses does not conform,
whatever its pipeline looks like. **Two profiles:** the **baseline contract** (clauses 1–2) is
unconditional — no speculative authority violation, no *speculatively-trained* residue observable
across a boundary, on every conforming machine, no knob involved. The **noninterference profile**
closes the *occupancy and timing* channels of deliberately-shared, architecturally-filled
structures (partition knobs enabled, `CACHE_PARTITION`-class isolation, §15). A knob that is off
leaves a timing channel open.

**A bad capability argument is an error return, not a fault** (the precise boundary is §9.1): presenting a
missing, stale, wrong-type, or under-privileged capability to a system/endpoint op makes that op return
a condition (`-BADREF`/`-STALE`/`-DENIED`) and change nothing. The epoch check (§3) is what distinguishes
"stale" from "valid"; it produces these error returns, **not** a crash. Only a *direct* CPU memory or
instruction access (an `ld`/`sd`/fetch) to an unmapped or protection-violating address faults — which, by
Law 1, is a machine gate-call (§9).

### 2.2 How a capability is unforgeable (the handle model, not tagged memory)

LNP64 deliberately does **not** use tagged-memory fat pointers (the CHERI approach: wide in-register
capabilities plus a hardware tag bit per memory granule). That is why §2 can say the integer datapath is
untouched and a capability is "an ordinary `u64`." The model is **handle-and-table**:

- **What lives in a GPR or in memory is a handle**: a `u64` with a fixed layout: **bit 63 = 0** (so a
  handle is always non-negative and never collides with a `-CONDITION` return, §1), **bits `[62:39]` =
  24-bit slot index** into the issuing domain's **capability table**, **bits `[38:0]` = the 39-bit epoch
  the slot's embedded cell must currently hold** (§3). The split favors epoch width: sixteen million
  slots per domain exceeds any table an implementation will build, and epoch width is what
  saturation resists (one slot retires only after 2^39 reuses). Tables are per-domain, so slot
  exhaustion is self-scoped, and the **saturated-slot count is charged, visible accounting state**
  (`engine_accounting_table.md`). **Epoch `0` is architecturally reserved-invalid:
  every slot's first live epoch is `1`**, and this makes the null handle an **encoding theorem, not a
  convention**: a live handle is `slot << 39 | epoch` with `epoch >= 1`, so its low 39 bits are nonzero
  and **the u64 value `0` is unconstructible as a live handle for any slot**. `0` is therefore the one
  architected **null-handle sentinel** — "no capability here" in any handle-carrying field. Slot 0 itself
  is an ordinary slot; only *epoch* 0 is
  reserved. **Null-handle behavior is uniform:** the only positions architected to *admit* the null
  sentinel are the `mmap` `backing_cap` (= anonymous — the **single** anonymous convention machine-wide,
  §17.8), typed target/owner operands explicitly defined as self (`0`), and optional capability
  operands whose fixed function explicitly declares `0` = absent/unchanged; **everywhere else**
  handle `0` is simply an invalid handle and fails **`-BADREF`** like any other dead handle, never a
  special case. The handle carries **no rights, class, or bounds** (those are in the entry); the epoch is
  the *only* authority-relevant field it carries, and it is a check value, not a grant. You may store,
  load, copy, and spill a handle anywhere a `u64` goes; it is not secret, because by itself it grants
  nothing.
- **The authority lives in the table entry**, in **hardware-owned protected storage no instruction can
  write directly**. Entry fields: **class, rights, range, the slot's embedded epoch cell, a shared
  epoch-cell reference (the lineage), and the slot **lifetime class**
  `{PERSIST, DROP_ON_STATE_REPLACEMENT}`, applied by `dreplace.commit` (§11.5); `SEALED` — no further
  delegation (§16.3); and reserved bits), mutated only by the capability engine (anonymous substrate,
  Law 3 / §11). On every *use* the
  engine checks: slot occupied, **handle epoch == slot-cell epoch**, lineage-cell epoch current, required
  rights present, range/class valid. **The observable condition mapping is total and universal:** null
  where not admitted, an out-of-range/malformed slot index, an empty slot whose current embedded epoch
  nevertheless matches, or a live entry of the wrong object/interface class → `-BADREF`; any embedded
  slot-epoch mismatch (including drop, move, or reuse) or shared lineage/stamp epoch mismatch →
  `-STALE`; a valid live reference lacking required rights/range permission → `-DENIED`. Checks occur in
  that order. No section or operation may choose a different condition for the same predicate.
- **Both invalidation mechanisms are the same primitive** — the slot's embedded cell (reuse safety) and
  the shared lineage cell (revocation) are **epoch cells**, §3. Dropping a slot bumps its embedded cell,
  so a stale handle to a recycled slot fails forever; `cap_revoke` bumps the shared lineage cell **once,
  O(1)**, and every entry on the lineage — the original and all derived descendants, in this and other
  domains, since they reference the *same* cell — fails its check on next use. Revocation reaches
  "everywhere" not by touching each descendant but by all descendants sharing one cell. Saturation
  semantics, bump policies, and the reclamation rule are §3's, stated once.
- **The protection boundary is the domain, and tables are per-domain.** A handle only ever indexes *its
  own* domain's table, so a fabricated number cannot name authority that was never delegated to this
  domain. Forging an index can at most (a) hit an empty/stale slot, which errors, or (b) re-name a
  capability the domain *already holds*, which is no escalation. **Within** a domain there is no
  compartmentalization from handle-hiding: any code that can read the domain's memory can read and reuse
  any handle stored there. LNP64 isolates mutually-distrusting principals by putting them in **separate
  domains**. The precise unforgeability theorem (stated narrowly, not relying on epoch secrecy): *a handle
  confers authority **only** when it matches a live entry in the **current domain's** table; it cannot be
  transferred to another domain except through the engine (which re-keys it), and it cannot name authority
  never delegated to this domain.* Within a domain, possessing or successfully reconstructing a live
  `{slot, epoch}` **is** possessing that authority — the 39-bit epoch is reuse-safety, not a secret, and
  the model does not depend on it being unguessable.
- **New entries are minted only by the engine, only from an authorizing capability** you already hold
  (`cap_dup` with monotonically narrowed rights, or installation on receipt via `send`/`recv`/gate). No
  instruction turns data into authority, and arithmetic on a handle cannot widen rights.
- **Capability passing is therefore an engine-mediated channel, not shared memory.** A handle indexes
  *your* table, so writing the number where another domain reads it is meaningless to them. Transfer means
  the engine installs a corresponding entry in the receiver's table and hands back a receiver-local
  `{slot, epoch}` handle, under a rights check. `cap_dup` is **not** an inter-domain path: it has no
  destination-domain operand and only duplicates within the current domain (with narrowed rights).
  Crossing a domain boundary is always `send`/`recv`/gate. Bytes cross freely; authority crosses only
  through the engine.
- **A serialized capability table is relocatable by construction** (the property SERIALIZE §16 rides):
  `{slot, epoch}` is domain-local — nothing in a table refers to a machine-global name — so a subtree's
  authority can be exported with its exact software-visible handle values and re-established elsewhere
  with the cell graph's shape preserved. Fat-pointer
  capabilities scattered through tagged memory could never do this; the handle model bought migration
  before migration was asked for.

The trade is explicit: the handle model keeps memory and the integer datapath ordinary (no tag bits, no
wide registers, no tagged DRAM/cache) at the cost of an engine-mediated table and an explicit cap-passing
channel, rather than CHERI's in-band capabilities that need tagged storage end to end.

### 2.3 Compiler-visible semantics (ordinary IR, explicit boundary effects)

The capability model does **not** introduce a pointer representation or pointer-provenance rule. An
ordinary pointer remains an untagged virtual address. A capability handle remains an ordinary `u64`
integer whose authority exists only in the current domain's protected table. The following compiler
rules are architectural consequences of §2.2 and therefore bind every frontend, optimizer, linker, JIT,
and language runtime:

1. A capability handle is not a pointer. `inttoptr` of its bits conveys no authority.
2. Copying, comparing, spilling, or reloading the bits does not duplicate or transfer authority.
3. Two unequal handles may name the same underlying object through distinct table entries.
4. Equal bits mean only the same current-domain `{slot, epoch}` value; they imply neither exclusive
   ownership nor a machine-global object identity.
5. Optimizers may manipulate handles as integers but may infer no aliasing, rights, class, ownership,
   lineage, liveness, or object identity from their numeric values.
6. Only an engine operation installs, duplicates, transfers, narrows, moves, drops, revokes, or
   re-stamps authority. A move consumes the table slot at the transfer operation; stale integer copies
   simply fail on later use.
7. A handle written into another domain's memory remains integer data there until an engine transfer
   installs receiver-local authority.
8. A source-language ownership or borrow type is a frontend proof layered over these rules. In
   particular, writable-borrow uniqueness is never inferred by the machine from the handle value.

**The compiler-effect table.** `isa_spec.json` `compiler_semantics` is the machine-readable
transcription of this document. It resolves every assigned opcode and every hardware-owned typed
subfunction to exactly one complete record containing: result kind; direct-fault and machine-call
behavior; park and success-nonreturn behavior; ordinary-memory read/write regions; program-memory and
engine-state effects; acquire/release/SC ordering; speculation, duplication, convergence,
restartability, and idempotence; capability-slot consumption and authority publication; cancellation
and serialization boundaries; and the corresponding conservative compiler memory-effect class.
Bindings are normalized through named effect classes, but generation materializes a full row per
operation. An assigned operation absent from that resolution is a schema error.

The table uses **engine state** as a distinct effect domain. In an optimizer that has no native engine
state, a mutating engine operation is modeled as an inaccessible side effect: it may not be deleted,
duplicated, or reordered across another operation whose engine effects may conflict. That rule does
not make every engine operation compiler-`convergent`; convergence is reserved for the narrower
control-equivalence property, while nonduplication and effect ordering carry ordinary authority
semantics. Checked engine copies name their explicit input/output regions and return `-FAULT` on a bad
range; they are not modeled as arbitrary process-memory accesses.

**The authority/data separation theorem (the aliasing contract, so "inaccessible side effect"
is never read as "barrier to everything").** An authority operation — the `cap.*` slot ops,
`mem_grant`, `dself`, waitset membership, builder facts — **neither reads nor writes ordinary
memory contents beyond its explicitly named descriptor/buffer operands**: `mem_grant` mints a
table entry *about* a range and does not touch the range. Consequently ordinary loads and
stores move freely across authority operations, and two authority operations on different
objects commute (the engine-concurrency license as an IR rule). The deliberate exceptions,
closed: `map.protect`/`munmap_range`/`map.demote` change *accessibility* and are release-like
barriers for their range (W→X publication is already §11.2's barrier); `map.discard` and
reclaimable transitions are contents-affecting by declaration; `recv`/`read`-class ops write
their buffers per the effect table. Everything else inherits the theorem. There is no dynamically selected
generic control instruction. Each typed family subfunction resolves
to its own row; a service gate or endpoint call uses the declared interface summary or the conservative
external-call row.

The load/store, atomic, fence, and completion-order rows restate §5, §6, §10, and §15 rather than
creating a second memory model. In particular, submission publication is release-like, observing a
hardware-producer completion is acquire-like, and W→X `map.protect`/`AS_PROTECT` is a program-memory
publication barrier. `gate_call` is call-like and may park; without a typed interface summary it is
conservatively an arbitrary external effect plus the descriptor-declared ordinary-memory regions.
Successful `gate_return`, `dret`, `dtail`, `dreplace.commit`, and self-termination transfer control away
and have only a failure continuation (§9.2, §11.5, §16.1). A compiler must represent that property
directly; hiding it in an unannotated assembly stub is non-conforming.

**Domain calls are calls in IR.** A call using the `lnp_domaincc` calling convention lowers to
`dcall`; `musttail` lowers to `dtail`. Scalar arguments and results remain SSA values in the ordinary
argument/result registers. Capability copy, move, and borrow intent is carried by preserved
`lnp.caps`, `lnp.moves`, and `lnp.borrow` operand bundles (or an exactly equivalent typed-IR
mechanism). Existing coroutine IR may lower either to an in-domain frame or to
`dspawn`/`dyield`/`dresume`/`dkill`; that choice is a target coroutine ABI decision, not a new IR
storage class.

**Builder chains are linear SSA.** Frontends represent a builder as an IR token:
`domain.new → domain.map → domain.grant → domain.start`. Each intrinsic consumes one token and
produces the next; exceptional exits insert `domain.abort`. This licenses dead-construction
elimination, folding inherited defaults, combining monotone restrictions, reordering independent
builder operations, and recognizing a `dspawn` sequence. Machine code carries the corresponding
generation-threaded builder reference in an ordinary GPR. **Builder linearity is fail-closed at
the machine**: the reference is generation-threaded (§16.1.1), so a linearity violation by any
pass — duplication, reuse of a consumed generation — produces `-STALE` at execution, never
undefined behavior and never authority confusion. Token-typed IR with frontend-enforced
linearity is therefore an optimization discipline with a hardware backstop, and the psABI
defines the conforming plain-integer fallback tier.

## 3. Epoch cells (the one freshness primitive — Law 2)

An **epoch cell** is the sole architectural mechanism for **reference freshness** — and freshness
is one of exactly **two disciplines of the machine's one temporal primitive, the monotone
saturating counter** (the other, the **generation**, answers progress; both are defined below,
their shared theorems stated once). A cell is a hardware-owned
`{epoch, referent_count}` pair. A cell is either **embedded** (one owner: a capability slot, a VMA) or
**shared** (many referents: a delegation lineage, a service binding, a thread identity, a clock view).
Every time-qualified reference in the machine is a `{cell, epoch}` pair, and every use performs the single
check **`ref.epoch == cell.epoch`**. The rules, uniform across every instantiation:

- **Bump marking is O(1); completion is acknowledged universal invalidation.** The home-cell increment
  initiates one broadcast—no graph walk or descendant tracking. For a replicated cell, the architected
  bump linearizes when that broadcast is acknowledged by the tracked referent span. A use concurrent
  with the bump may linearize before it and succeed; after the bump operation returns, no new use may
  validate the old epoch anywhere. Referents then fail at their next use; nothing is eagerly walked.
- **Saturation is permanent death.** An epoch counter **saturates rather than wraps**: a cell at its
  maximum value is permanently dead — the counter never rolls to a live value, so "stale fails forever" is
  a hard guarantee in every embedding. This is one instance of the machine-wide rule: **the
  temporal structure is monotone — no architectural operation is invertible, and "undo" is
  always a new forward state** (paired resource verbs are adjoints, never inverses, §16.4); a
  proposal for a reversible operation is refused by this sentence. (Cell **width** is an embedding parameter — 39 bits in capability
  slots because the handle inline-carries the check value §2.2, 64 bits in shared cells — but the
  saturation rule and the check circuit are identical at every width. Epoch `0` is reserved-invalid at
  every width, which is what makes the §2.2 null-handle theorem hold.)
- **Cells count metadata referents.** `referent_count` protects the cell and its replicas until the
  last epoch-qualified referent disappears. It is not an object-lifetime count and is not a tracing
  reachability count; whether the same relationship keeps an object alive is the independent edge
  classification below.
- **The bump op takes a policy**, a property of the *bump*, applicable to any cell — not a revocation
  class special-cased to capabilities:
  | Policy | Effect beyond the epoch increment |
  |---|---|
  | `lazy` | wait only for invalidation acknowledgement; do not cancel or drain uses that linearized before the bump — subsequent uses fail |
  | `cancel` | also wake ops blocked through a dying referent with `-CANCELLED` |
  | `quiesce` | also drain in-flight DMA/translation through the referent to a defined boundary (abort-at-burst-boundary) before the bump returns. **The drain is bounded by architecture, not by device goodwill: it inherits the §11.2 ack-bound + fence recourse** — a device that never reaches a burst boundary is fenced at the fabric within the bound, its window's cell takes the `poison` disposition, and the drain completes with **fence-synthesized completions: status `-POISONED`** (the *device* is dead, not just the transfer — recovery code must know the difference from an orderly `-CANCELLED`), `bytes_done` = the fabric's count, destination bytes beyond it indeterminate in the stronger sense that the device may still believe it wrote them |
  | `poison` | also mark the cell so future *references* to it (not just stale ones) fail — for teardown-forever |
- **Failure precedence is structural, then poison, then freshness, then rights.** First validate handle
  shape/index; malformed/out-of-range is `-BADREF`. If the indexed slot is occupied, validate the
  requested class (`-BADREF`), resolve its current cells, and inspect poison before comparing epochs: a
  poison-marked current cell returns `-POISONED` even when its publishing bump also made the handle's
  epoch unequal. With no such poison, any embedded/shared epoch mismatch is `-STALE`; an empty slot is
  `-STALE` when its embedded epoch mismatches and `-BADREF` only for a matching-epoch empty reference.
  A current live reference reaches the rights check last (`-DENIED`). Slot reuse installs a new entry
  with no inherited poison, so an old handle observes `-STALE`, never poison from the retired object.
- **One fabric message.** The invalidation broadcast (translation shootdown) and the capability-revocation
  transport are the **same message with the same acknowledgment contract**; what varies is which cell the
  message names. One circuit checks freshness; one theorem covers death.
- **Return guarantee.** Every bump policy, including `lazy`, returns only after the invalidation
  acknowledgement above. `lazy` is "lazy" about already-in-flight work and reclamation, not about
  remote replicas learning the new epoch. Thus post-return success through an old remote replica is
  forbidden while checks remain local and bounded.
- **Shared-transition return rule.** The acknowledgement rule applies to every mutation of shared-cell
  state, not only an epoch increment: bump, death/poison, `RESTAMP` repoint, thread or domain identity
  death, parent-edge replacement, pager-designation replacement, and a ClockView step whose timers have
  distributed referents. The state transition is O(1) work at the cell home, but an operation whose
  postcondition is machine-wide returns only after the new state is acknowledged throughout the cell's
  current referent span. Constant transition work does not imply constant return latency. A deliberately
  asynchronous transition must be identified as such at its defining operation, expose distinct issued
  and acknowledged progress, and may not claim its global postcondition before acknowledgement.
- **The safe-reuse corollary (Law 2's lifecycle, stated once).** Logical death and physical reuse
  are distinct events with a proof between them, and every lifetime in the machine passes the same
  three points: the **death point** (the acknowledged bump linearization — no old reference can initiate a new use), the
  **no-stale-access point** (quiescence after invalidation acknowledgement for cells, cumulative
  acknowledgement for generations — no previously initiated CPU, device, or engine use can land
  afterward), and the
  **reuse point** (storage and identifiers may be reassigned — legal only at or after the
  no-stale-access point, and established by the engine, never asserted by software). Translation
  shootdown before frame reclaim, DMA unmap before frame reuse (§11.2's generation conditions
  certify the no-stale-access point by that name), `cap_revoke` with `quiesce`, cancellation over
  borrowed memory (§9.4's completion-not-cancel-return rule), device removal with fabric fencing,
  pager eviction, and §16.8 reincarnation are instances of these three points — never separate
  lifetime protocols.
- **Every cell has a home (Law 8).** A cell is created within the volume of the domain that owns it,
  and its bump is issued from and acknowledged at that home — which is what makes the epoch *check*
  **local and tile-bounded** (Appendix C class 0 — "one compare, one cycle" is the §1.1 existence
  construction; locality independent of machine size is the requirement) rather than a fabric
  transaction, and what gives the bump's broadcast a root.
  The broadcast is scoped to the **cell's referent span — the volumes that hold live referents,
  tracked, never assumed.** For **embedded** cells the span *is* the owning domain's volume (a slot
  or a VMA cannot leave it — a `far` mapping is unconstructible, §15 — so §11.2's
  translation-invalidation bound is owner-diameter). For a **lineage or stamp** cell, capability
  delegation travels every channel a holder has (§10.2), so its referents span the **delegation
  reach**, sibling volumes included. The acknowledgment **completes within the published bound
  parameterized by the referent span's diameter** (a spanning-tree reduction rooted at the home
  over the referent-holding volumes; any topology meeting the bound and the subtree-isolation
  invariant conforms), O(log span) — the flat all-to-one version does not conform. Every crossing
  in that span was named by the `send`/`recv` or gate transfer that granted across it. The class-0
  check requires cell state resident near every referent, so a shared cell's epoch is **replicated
  per referent-holding volume**, with the invalidation broadcast as its coherence protocol and a
  volume directory keyed on the cell as its routing state (the §16.4 wide-cell obligation's epoch
  twin). A widely-delegated capability's revocation is therefore rack-wide, priced by Appendix C's
  authority-span rule.

Eight referents of this one primitive:

| Referent | Cell | Bump means |
|---|---|---|
| Capability slot validity (§2.2) | the slot's embedded cell | slot reuse — stale handles fail forever |
| Delegation lineage (§2.2) | a shared cell all descendants reference | `cap_revoke` — all descendants, all domains, at once |
| Cached translation (§15) | the VMA's cell | `map.protect`/`munmap`/image-replace — the DVM broadcast is keyed on the cell; the epoch check is the straggler backstop |
| Shared-backing translation (§15) | the PagedBacking's distinct shared **backing-translation cell** | `SUPPLY`, `EVICT`, `backing.rehome`, demotion, destruction, or immutable-to-mutable transition invalidates cached backing-tagged translations without revoking capabilities to the backing |
| Pager designation (§15) | the PagedBacking's shared **designation cell** | pager retarget/death invalidates old request authority and, after span acknowledgement, re-delivers outstanding requests to the new endpoint |
| Address-space enumeration (§11.2) | the address-space object's embedded **root-mutation cell** | every committed VMA-tree structural/metadata mutation stales all outstanding `AS_ENUMERATE` cursors |
| Service-object route stamp (§16.0) | the per-object `{gate route, service_class, cookie, lifecycle_queue}` state shared by its aliases | dispatch resolves it; service death makes the route `-STALE`; `RESTAMP` repoints that one object without changing its lineage or pretending to restore private state |
| Thread identity (§8, §16.3) | the thread's cell | dead-thread references fail closed everywhere they appear — debug tids, park records, directory lookups — never an action on a recycled slot |

(A ninth arrives with Law 4: a **ClockView** carries a shared cell whenever a timer holds it (local
before delegation), and stepping the clock bumps it —
timers armed against the view heal by re-resolution, §8. The table is open on purpose: any future
mechanism needing "is this reference still current?" gets a cell, not a bespoke counter.)

### 3.1 Engine-held references and cyclic retention

LNP64 provides deterministic counting for engine-known strong relationships. It provides **no tracing
garbage collector and no automatic cycle collector**. Capability bits copied into ordinary memory are
not engine roots; the engine neither finds nor interprets them. A zero object
`strong_reference_count` means that no live capability-table entry or engine-known strong edge retains
the object. It does not mean that a tracing reachability analysis previously found the object
unreachable.

Every frozen engine relationship schema declares **exactly one** object-lifetime edge type. Missing or
ambiguous classification is a schema error; there is no implementation-selected default:

| Edge type | Keeps the target object alive? | Contract and existing families |
|---|---:|---|
| **strong transfer** | yes | Authority or state retained to fulfill a committed promise: live capability-table entries, queued capability transfers, VMA/corpse-VMA→backing, configured gate→activation-stack pool, timer arm→ClockView, pin/admission lease→backing frames, established DMAWindow→backing/mapping, DebugTarget→retained corpse, and domain parent edge→child identity |
| **transient strong** | yes, until one terminal teardown | Snapshotted capability arguments for an accepted op, activation borrow/transfer state, pending activity arguments, an exclusively claimed receive, builder-validation references, and in-flight DMA generation references |
| **weak observation** | no | Waitset membership, completion/debug-event routing, pager designation routing, and service-stamp→current-gate routing; these retain only the epoch-qualified identity metadata needed to observe death, stale, or `HANGUP` |
| **backpointer/index** | no | Backing reverse maps, cell referent-span directories, lookup directories, accounting/sponsorship indexes, and other inverse indexes whose source relation owns their creation and removal |

The taxonomy is orthogonal to cell lifetime: a weak observation may increment the qualifying cell's
`referent_count` without incrementing the target object's `strong_reference_count`. Conversely, a
strong edge normally carries an epoch-qualified cell referent as well. An edge is *designed* weak
unless target survival is necessary to honor an already committed architectural promise, but the
frozen schema—not that design heuristic—decides the type.

The consequences are specific. A committed queued capability remains a strong transfer: weakening it
would allow a successful `send` to decay before `recv`. A waitset member is weak: member death produces
final `HANGUP`/stale readiness and automatic removal or an inert dead-member record, but the waitset
does not keep the member object alive. A service object's aliases retain its per-object stamp, while
the stamp's route to the service gate is weak; gate/service death stales the route and `RESTAMP` may
replace it. A VMA strongly retains its backing, while the backing's reverse-map row is
only the VMA-owned backpointer and cannot retain the VMA.

Strong edges may form cycles—for example, two endpoint queues may each contain a capability to the
other endpoint. Such a cycle may delay zero `strong_reference_count` indefinitely after ordinary
software handles are dropped. This is a **bounded resource-lifetime condition**, never a temporal-
safety or authority exception: every edge is charged to its creator under §16.4; revocation, poison,
and explicit destroy remain effective through the cycle; and no storage, identifier, or capability
slot is reused while a strong or transient edge may still use it.

**Deterministic aggregation drain.** Every hardware-owned object capable of containing strong edges
uses one destruction skeleton: (1) atomically enter `DESTROYING`; (2) perform the acknowledged lineage
bump so new operations fail; (3) detach its bounded contents; (4) drive accepted activities to their
specified terminal outcomes; (5) release each contained strong edge exactly once; (6) remove weak
registrations and source-owned backpointers; and (7) finish after transient users drain. Repeated
destroy is idempotent, and clearing an already empty aggregation succeeds. This governs channel and
completion queues, WorkQueue/DMAWindow state, waitsets, serialized-gate submission queues, and
hardware-represented device queues. Work is proportional only to that object's configured bound and
may drain asynchronously under the corpse charge; the engine never traverses an arbitrary graph.

A service-owned aggregation must provide the corresponding idempotent destroy/terminal protocol for
its opaque state; hardware drains only the strong edges represented in engine state and can stale or
poison a failed service route. The architecture does not pretend to collect a service's private graph.

**Lifecycle sponsorship is cleanup metadata, not authority.** The accounting engine keeps a non-owning
sponsor index sufficient for domain teardown to find engine aggregations and edges charged to that
domain. It is not addressable, is never returned as a cookie, and authorizes no software operation.
Software requiring pre-teardown destruction must retain an ordinary capability with the necessary
rights. Domain teardown drains domain-bound aggregations and drops every strong/transient edge owned by
the dying domain. It does not silently destroy a shared object still retained by another live domain
unless that object's mint-time contract explicitly made its lifetime sponsor-bound; otherwise existing
external references and their corpse accounting remain until their normal release. Thus cyclic
retention cannot keep a domain executing or preserve usable authority after its acknowledged death,
even though explicitly shared storage may remain charged while live external references exist.

`LAST_STRONG_REFERENCE(cookie)` reports the deterministic transition to no stamped strong object
reference after accepted dispatches quiesce. It is not a tracing-reachability notification, and a
strong cycle may delay it indefinitely. A service requiring
explicit close therefore implements explicit destruction and teardown cleanup rather than treating
last-strong-reference notification as universal garbage collection.

**The algebra's one missing operation is reserved as a seam.** The cell algebra has exactly two
operations — bump and check — which suffices when a cached fact depends on *one* authority.
Composite cached facts depend on several (a memoized dispatch decision holds `{stamp cell, lineage
cell}`; a cached negotiation holds `{binding, view}`), and each consumer tracks its own cell set
and pays N checks. The completion is the **join**: a derived cell whose epoch is the monotone join
of its parents', so one check validates a composite fact and a bump of any parent invalidates
through the join. A join cell is new engine-held state with fan-in accounting, a home (Law 8), and
a width story, so it takes the full §16.4/Appendix G treatment or none. **Reserved as the
`CELL_JOIN` seam (Appendix G, `ENC`)**: nothing in v1 may cite it, N-check consumers are the v1
truth, and a future proposal must arrive as the completion of *this* algebra — parents named at
mint, join monotone, saturation dominant (a saturated parent saturates every join above it) —
never as a second freshness primitive.

**The second discipline — the generation (progress, not freshness).** `REMAP`'s repoint
generations (§15), backing write generations, `lease_id`'s embedded generation (§16.1), the
poison generation, and generation-qualified submission handles are all one primitive with the
cell: **there is one temporal primitive — the monotone saturating counter — under two check
disciplines.** The **freshness discipline** (the cell) checks **equality** and bumps to invalidate
universally: "is this reference still current?". The **progress discipline** (the generation)
checks **`>=` with cumulative acknowledgment**: "has progress reached point `G`?" — acknowledging
`G` acknowledges everything through `G`, which equality cannot express. The shared theorems are the
counter's, stated once and never per embedding: monotone; **saturates rather than wraps** (a
saturated generation is permanent completion of its line, as a saturated cell is permanent death);
a distinguished reserved initial value; **incarnation-scoped** (meaningful only within one
incarnation of the carrying object — teardown retires the line, never resets it); a domain-local
name under Law 7. What is *not* shared is the discipline: referent counts, homes, and the invalidation
broadcast belong to freshness; cumulative acks flowing home belong to progress — forcing either's
machinery onto the other is refused. Silicon: **one saturating-counter library — one counter
block, two check circuits (`==` bump-invalidate; `>=` cumulative-ack)**. **Neither discipline
covers observational counters** (§16.3 traffic getters, and every count/size/offset/cursor §8.2
excludes from the identity theorem): they answer *how much*, not *is this current* or *has
progress reached G*, so they **wrap** where these saturate — stated here because the saturation
rule is otherwise the house rule a reader would apply by analogy.

**One logical primitive is not one physical engine.** The embeddings do not have equivalent costs:
a slot check is local and tile-bounded; a lineage revocation may span every domain the delegation
reached; a VMA bump requires acknowledged translation invalidation; a window bump under `quiesce`
may require fencing a hostile device; a ClockView bump re-resolves timers; a `RESTAMP` repoints
dispatch routing. What is architecturally **one** is exactly three things — the **check circuit**
(`ref.epoch == cell.epoch`, every embedding), the **invalidation message format and its
acknowledgment contract** (the fabric transport above), and the **saturation/reservation theorems**
(epoch 0 invalid, saturate-don't-wrap, everywhere). The **bump choreography is per-embedding**, and
an implementation may build the embeddings as distinct protocol machines sharing only the check and
the message.

**Relationship to software epoch reclamation (crossbeam-class):** cells and grace periods answer
different questions — a cell answers *"is this reference still current?"* at an engine-checked use;
a grace period answers *"is anyone still reading?"* over raw pointers the engine never sees. The
machine accelerates the first, not the second: a per-dereference validity check on plain `ld` would
tax every load (§5), so in-domain lock-free node reclamation keeps its software epochs. For the
cross-domain case — reclaiming memory shared *across trust boundaries* — cells at VMA/backing
granularity are the reclamation protocol (`munmap` + broadcast + epoch backstop, §11.2). No
hardware grace-period assist is reserved.

**`RESTAMP` targets the cell, not the capability.** The op is named through any handle that *references*
the cell — live, or stale-by-lineage — because its whole purpose is to repoint a binding whose previous
holder died. The slot check still applies (you must hold a real handle); the lineage check is
definitionally not asked of a cell op. There is no
exception to the liveness rule, because the op's operand *is* the cell. A supervisor therefore does not
need to hoard a dead gate's handle across a service crash — any handle referencing the binding cell names
the stamp.

## 4. Integer compute (R-type and I-type)

### 4.1 Register-register ALU (R-type, `rd, rs1, rs2`)

`add` 0x10, `sub` 0x11, `mul` 0x12, `mulh` 0x13 (signed high), `mulhu` 0x14 (unsigned high),
`div` 0x15 (signed), `udiv` 0x16, `srem` 0x17, `urem` 0x18, `and` 0x19, `or` 0x1a, `xor` 0x1b,
`andn` 0x1c (`rs1 & ~rs2`), `orn` 0x1d (`rs1 | ~rs2`), `xnor` 0x1e (`~(rs1 ^ rs2)`), `sll` 0x20,
`srl` 0x21, `sra` 0x22, `rol` 0x23, `ror` 0x24, `slt` 0x25 (`rd = rs1 <s rs2`), `sltu` 0x26.

**Branch-free select — three source reads, condition against zero (the rename-port fix).** `sel`
0x27 `rd, rc, rt, rf {cc}` — `rd = (rc <cc> 0) ? rt : rf`: the condition is a **live GPR tested
against zero**, never an embedded comparison — **`cc[27:26]`** (`0` eq, `1` ne, `2` ltz — sign
bit set, `3` gez) in the
operation-defined region, `[35:28]`/`[25:0]` reserved-zero — the sign-bit conditions cost one
wire and cover `select (x < 0)`/`(x >= 0)`, min/max-with-zero, and abs-select with no
materialized compare; the condition stays one live GPR against zero (§1's three-source-read
discipline untouched). Four GPR operands total, **three source reads**: no
five-wide rename corner, and the decoder's crack story is trivial. There is **no
embedded-comparison form** — one machine, no ghosts: a comparison against a register is
materialized by the compare ops the ISA already has — `slt`/`sltu`/`sub`/`xor` produce
the condition value directly — so the common lowering costs one extra instruction *only when the
condition was not already live*, and profile data says it usually is. The `czero` forms are the
`r0`-operand aliases (`czero.eqz rd, rs, rc` = `sel.eq rd, rc, r0, rs`; `czero.nez` the dual), not
separate ops. Assembler spellings `sel.eq`, `sel.ne`, `sel.ltz`, `sel.gez`.

**Fused shift-adds (the indexed-address fix):** `sh1add` 0x28, `sh2add` 0x29, `sh3add` 0x2a —
`rd = (rs1 << k) + rs2` for `k` = 1/2/3. `a[i]` for a 2/4/8-byte element is `shKadd` + load (two
instructions), and the computed address is reusable across multiple accesses; for the single-use case the
indexed load/store forms (§5) do it in one. (This is the gap RISC-V shipped Zba to close.) These ops and
`add` also define the **extended-subformat bit `[1]` = `U`** (`.uw` spellings: `sh1add.uw` … `add.uw`):
zero-extend `rs1[31:0]` before the shift/add — LP64 code indexes with `unsigned int` constantly, and
without this the `zext.w` lands on exactly the `a[i]` pattern the family exists to fix. **`W` and `U`
together (`[1:0]` = `11`) is reserved → illegal-instruction** on every op defining both bits.

**Constant-time class (the Zkt statement, pinned).** The following are architecturally **data-oblivious
in timing** — latency, issue, and retirement are independent of operand *values* — on every conforming
implementation: all §4 ALU, logic, shift/rotate, and bit-manipulation ops including `mul`/`mulh`/`mulhu`,
`clmul`/`clmulh`, the flagless carry/overflow family, `sel`, `fsel`, and the §18 vector forms of the
same. **Excluded** (never write constant-time code with these): `div`/`udiv`/`srem`/`urem`
(implementations may shortcut), any memory access (cache state is not an operand but is observable), and
control transfer. This is the contract BoringSSL-class crypto and Rust's `subtle` need, stated once.

**Flagless carry and overflow (checked arithmetic without flag state):** the machine has no condition
flags, so multi-precision and checked arithmetic get **pure-function ops** — each writes one GPR, no
hidden state, trivially schedulable:
- `add3` 0x2b `rd, rs1, rs2, rs3` — `rd = rs1 + rs2 + rs3` (low 64; three full 64-bit inputs, so the
  carry-in is just an operand);
- `carry` 0x2c `rd, rs1, rs2, rs3` — `rd` = the carry-out (`0`/`1`/`2`) of that same three-way sum; a
  bignum limb chain is `carry` + `add3` per limb (vs the 5-op `sltu` ladder);
- `ovadd` 0x2d / `ovsub` 0x2e `rd, rs1, rs2` — `rd` = 1 iff the **signed** 64-bit add/sub overflows,
  else 0. `checked_add` is `add` + `ovadd` + `bne`; an implementation may recover the flags-machine
  cost under the general cracking license (§4.3, Appendix E), with no architectural obligation to
  and no compiler dependence on it. The ISA keeps pure dataflow and the compiler emits the same three ops everywhere. With the `.w` subformat below, the same ops give 32-bit checked
  arithmetic.
- `ovmul` 0x2f / `ovmulu` 0x30 `rd, rs1, rs2` — 1 iff the signed / unsigned 64-bit product overflows
  (`count * size` is the most safety-critical checked multiply in real code). `W` forms per the rule
  below.

**Bit manipulation:** `bext` 0x31 / `bexts` 0x32 `rd, rs1, imm` (**I-format** — only `rd`/`rs1` plus the
immediate, so the §1 no-immediate-with-`rs2` rule is satisfied) — extract the bitfield
`rs1[off+len-1 : off]` zero-extended (`bext`) or sign-extended (`bexts`); `off` = `imm32[5:0]`,
`len` = `imm32[13:8]` (`len` = 0 or `off+len > 64` → reserved, illegal-instruction), remaining immediate
bits reserved-zero. `bins` 0x33 `rd, rs1, rs2` is **R-format** (it needs two source registers, so its
field descriptor **cannot** ride the immediate — §1): `rd` = `rs2` with the field at `off`/`len` replaced
by the low `len` bits of `rs1`, with **`off` = subformat bits `[7:2]` and `len` = `[13:8]`** of the
R-format operation-defined region (`[1:0]` stay clear of the `W`/`U` convention, which `bins` does not
define; same validity rule as `bext`). The two layouts for one field family are format physics — the
extract ops have an immediate field, the insert op does not — and are declared side-by-side here so an
assembler author reads one paragraph. `fsl` 0x34 / `fsr` 0x35 `rd, rs1, rs2, rs3` — funnel
shift: the 128-bit concatenation `rs1:rs2` shifted left/right by `rs3[5:0]`, `rd` = the high/low 64
respectively. `clmul` 0x36 / `clmulh` 0x37 `rd, rs1, rs2` — scalar carryless multiply, low/high 64 of the
128-bit polynomial product (scalar CRC/GHASH without a splat/extract round-trip through the vector file).

**Shifts** take their amount from `rs2[5:0]` (mod 64); the upper bits of `rs2` are ignored, never
faulting. **Division and remainder are non-trapping with defined results** (so the compiler never inserts
guard branches): divide-by-zero gives `div`/`srem` → `rd = -1` for the quotient and `rd = dividend` for
the remainder (`udiv` → all-ones quotient, `urem` → dividend); signed overflow (`INT64_MIN / -1`) gives
quotient `INT64_MIN`, remainder `0`. `mul`/`mulh`/`mulhu` never fault.

**32-bit operation forms (the `.w` subformat bit — R-format only).** Every R-type ALU op above that has
a meaningful 32-bit form — `add`, `sub`, `mul`, `div`, `udiv`, `srem`, `urem`, `sll`, `srl`, `sra`,
`rol`, `ror`, `sh1add`/`sh2add`/`sh3add`, `add3`, `carry`, `ovadd`, `ovsub`, `ovmul`, `ovmulu`, and the
§4.2 unary counts — defines the **extended-subformat bit `[0]` = `W`**: when set, the operation is
performed on the low 32 bits of the sources and the result is **sign-extended to 64** (shift/rotate
amounts mod 32). The division/remainder corner rules apply **at 32 bits, explicitly**: `divw`/`sremw` by
zero give quotient -1 / remainder = the (32-bit) dividend, `udivw`/`uremw` by zero give all-ones /
dividend, and signed overflow (`INT32_MIN / -1`) gives quotient `INT32_MIN`, remainder 0 — each result
then sign-extended like every `W` result. **`[0]` = `W` exists only in the R format**, whose operation-
defined region can host it; it can never ride an I-format op, whose `[13:0]` is the hint zone and hints
must never change a result, so the immediate 32-bit forms below have their own opcode bytes
(structural duplication accepted, Appendix B). Assembler mnemonics
`addw`, `subw`, `sllw`, … are the `W`=1 spellings; no new opcode bytes are consumed. (Logic ops need no
`W` form — bitwise results don't change under width — and `slt`/`sltu` compare full registers by design;
compare 32-bit values via the `W`-form arithmetic that produced them, which is already normalized.)

### 4.2 Unary (R-type, `rd, rs1`)

`not` 0x1f, `sext.b` 0x38, `sext.h` 0x39, `sext.w` 0x3a, `zext.b` 0x3b, `zext.h` 0x3c, `zext.w` 0x3d,
`clz` 0x3e, `ctz` 0x3f, `popcnt` 0x40, `bswap16` 0x41, `bswap32` 0x42, `bswap64` 0x43.

Pinned corners: **`clz(0)` = `ctz(0)` = 64** (no undefined input — every `countl_zero`/`leading_zeros`
lowering is branch-free; the rule propagates element-wise into §18). `clz`/`ctz`/`popcnt` take the §4.1
`[0]`=`W` bit (`clzw(0)` = `ctzw(0)` = 32 — `__builtin_clz` on `int` is one instruction).
**`bswap16`/`bswap32` zero-extend**: the swapped 16/32-bit value is returned with upper bits zero (a
byte-order-swap result feeds `W`-form arithmetic and unsigned compares pre-normalized; sign-extension,
when wanted, is the explicit `sext.h`/`sext.w`). The extension conventions across narrow-value producers,
in one table so the memorization load is one row lookup:

| Producer | Upper bits |
|---|---|
| `lb`/`lh`/`lw` | sign-extend (C integer promotion) |
| `lbu`/`lhu`/`lwu` | zero-extend |
| `bswap16`/`bswap32` | zero-extend (network-order values feed unsigned compares) |
| every `W`-form result | sign-extend (the RISC-V convention) |
| `ld.aq` sized forms | per its `sign` bit (§6) |
| ABI-canonical narrow argument/return | per-type to 32 bits, then sign-extend (§2 — the psABI canonical form; consumers rely on it) |

**Scalar `min`/`max`** (`min` 0x44, `max` 0x45, `minu` 0x46, `maxu` 0x47 — R-type, `rd, rs1,
rs2`): Zbb-shaped semantics — signed/unsigned 64-bit compare, the extreme value to `rd`, no `W`
forms (a 32-bit min is a `W`-form compare's job feeding these, and sign extension composes). **`abs` is an alias, not an opcode:** `abs rd, rs` = `sub rd, r0, rs`
; `max rd, rd, rs` (same `rd`, canonical order), with the `INT_MIN` behavior *pinned by the
sequence's own arithmetic* rather than by fiat:
`abs(INT_MIN)` = `INT_MIN` (the negation wraps, `max` picks either equal value), the two's-
complement identity every language's `abs` UB-carve-out already permits — declared, so no
implementation invents a saturating surprise.

**Named absences (deliberate):** scalar *saturating* arithmetic (`qadd`-class) is excluded — the
flat lowering is short and constant-time (`ovadd`/`ovsub` detect, `min`/`max`/`sel` clamp — all in
the Zkt class above), saturation-dominated inner loops are throughput code and throughput code is
the §18 vector engine's (whose integer ops carry saturating forms), and a scalar DSP-saturation
family would spend opcode bytes on the *scalar* remnant of a workload the machine already routes
elsewhere; if profile data from real ports ever shows a hot scalar remnant, the family lands as a
designed extension, not a v1 regret. Scalar bit-reverse and `orc.b`-class ops are excluded —
`__builtin_bitreverse` is rare and the vector `revb`/`tbl` cover the string fast paths; additive
candidates if a consumer materializes.

### 4.3 Register-immediate (I-type, `rd, rs1, imm32`)

`addi` 0x48, `andi` 0x49, `ori` 0x4a, `xori` 0x4b, `slli` 0x4c, `srli` 0x4d, `srai` 0x4e, `rori` 0x4f
(rotate-right by immediate; `roli k` is the assembler alias for `rori 64-k`), `slti` 0x50, `sltiu` 0x51,
`liu` 0x52 (`rd = (rs1 & 0xFFFFFFFF) | (uint(imm32) << 32)`), `auipc` 0x53 (`rd = pc + sext(imm32)` —
PC-relative address formation). **Immediate 32-bit forms get their own opcode bytes** (an I-format op
cannot carry a semantic `W` bit — `[13:0]` is the hint zone, §1): `addiw` 0x54, `slliw` 0x55,
`srliw` 0x56, `sraiw` 0x57, `roriw` 0x58 (low-32 operate, sign-extend; amounts mod 32), and
`slli.uw` 0x59 (zero-extend `rs1[31:0]`, then shift left — the index-scaling companion of the §4.1 `.uw`
family). `li rd, imm32` = `addi rd, r0, imm32`; a 64-bit constant is `li` then `liu`. Immediate shifts
take the amount from **`imm32[5:0]`** (mod 64); the rest of the immediate field (`imm32[31:6]`) is
reserved-zero, while the I-format hint zone `[13:0]` is unaffected and may carry hints like any other
I-format op.

**Fusion is not an architectural topic.** The general cracking/construction license
(Appendix E) already permits an implementation to execute any sequence as one internal op **when
results, ordering, exceptions, and fault attribution are identical to the unfused execution** —
fusion is one instance of that license and nothing more. The ISA therefore blesses **no pairs**,
requires **no adjacency**, and no compiler correctness ever depends on a fusion happening.
Profitable adjacent shapes (constant materialization `li`+`liu`, address formation `auipc`+`addi`/
`ld`, `abs` as `sub`+`max`, the checked-arithmetic and bounds-check idioms, the doorbell and
seqlock tails) and their implementation-specific constraints live in the **versioned
target-tuning note**, never here. Checks whose cold outcome is a language/runtime fault may instead
use `trapcc` (§7): the exceptional edge remains semantically precise to the compiler, but it needs
no taken/not-taken branch encoding or adjacent cold stub. Hint bits (§12) never interact with any
of this: a `kill` between two instructions is a `kill`, with no fusion consequence to reason about.

## 5. Loads / Stores (I-type load, S-type store)

Loads: `ld` 0x76 (64), `lwu` 0x75 (u32), `lw` 0x74 (s32), `lhu` 0x73 (u16), `lh` 0x72 (s16),
`lbu` 0x71 (u8), `lb` 0x70 (s8). Stores: `sd` 0x7a, `sw` 0x79, `sh` 0x78, `sb` 0x77. Address =
`base + sext(imm32)`. (The FP loads/stores `flw`/`fld`/`flh`/`fld.q` 0x84–0x87 and
`fsw`/`fsd`/`fsh`/`fsd.q` 0x88–0x8b live in this opcode range — they are memory-unit ops — with their
semantics specified alongside the FP profile, §14.)

**Indexed forms (register + scaled register), two opcodes total.** `ldx` 0x7b `rd, rs1, rs2` and
`stx` 0x7c: address = `rs1 + (rs2 << scale)`. **Exact subfields, pinned:** `ldx` — `rd[55:51]`,
`rs1[50:46]` base, `rs2[45:41]` index; `size[35:34]` (`0` b, `1` h, `2` w, `3` d), `sign[33]` (`0`
zero-extend, `1` sign-extend; ignored for `d`), `scale[32:31]` (0–3), **`fp[30]`** (`1` = the destination
is an **FPR**: sizes `h`/`w`/`d` valid per §14 — `flh`/`flw`/`fld` semantics incl. NaN-boxing — `b`
reserved; `sign` ignored); `[29:14]` reserved-zero; `[13:0]` = the §12 load hint zone. `stx` —
**slot-named** (the §1 named-slot rule: data is *not* in `rd`): `rs1[50:46]` base, `rs2[45:41]` index,
**`rs3[40:36]` data**, `rd` slot zero; `size[35:34]`, `scale[33:32]`, **`fp[31]`** (`rs3` names an FPR;
same width rules); `[30:9]` reserved-zero; `[8:0]` = the §12 store hint zone. **The `scale`/`fp` homes differ between the two ops by construction** (`stx`'s `rs3` data slot occupies `[40:36]`, pushing its subfields up; `ldx` additionally decodes `sign[33]`, which a store has no use for). The `fp` bit means
`double a[i]` is one instruction too (`fldx`/`fstx` are the assembler spellings). Assembler spellings
`ldx.d`, `ldx.wu`, `stx.b`, … mirror the immediate forms. One opcode per direction covers every width, so
`a[i]` is a **single instruction**; the §4.1 `shKadd` ops remain the right form when the computed address
feeds several accesses. Same alignment, fault, and memory-type semantics as the immediate forms.

**`prefetch` 0x83** `rs1, imm {kind, locality}`: a **never-faulting, never-trapping** hint access to
`rs1 + sext(imm)`. **I-format** (`rd` slot zero); because the entire instruction is architecturally
effect-free, its steering fields are themselves hint-class and live **in the `[13:0]` hint zone with
pinned positions** — `kind[1:0]` (`0` read, `1` write, `2` instruction, `3` reserved) and
`locality[3:2]` (`0` = into nearest level … `3` = non-temporal), `[13:4]` reserved-zero (§1 requires hint bits never to change architectural state, and no
`prefetch` bit does). No `rd`, no architectural effect, unmapped/unmappable addresses are silently ignored
(a prefetch can never be a probe: it reveals nothing architecturally and performs no translation side
effect visible to software). On v1 it may be implemented as a NOP.

**Alignment:** ordinary loads/stores to `normal_cached` memory **permit unaligned addresses** (a
misaligned access may be slower); single-copy atomicity is guaranteed **only** for naturally-aligned
accesses up to 8 bytes. Accesses to `device_ordered`/`uncached`/`write_combining` mappings (§15) **must**
be naturally aligned and fault otherwise. A load/store whose address is unmapped or violates its
mapping's protection raises a synchronous memory fault — by Law 1, a machine gate-call (§9, §9.1).
Thread-local storage is ordinary memory at a `tp`-relative offset (`tp` = GPR `r30`, §2), so a TLS access
is a **single** `ld`/`sd rd, offset(tp)` at full addressing-mode speed.

**Pointer masking / TBI: considered, excluded — deliberately.** AArch64 TBI and RISC-V pointer masking
exist chiefly to accelerate software tag checks (HWASan-class sanitizers). An ignore-top-bits
mode would add address-aliasing hazards (two spellings of one location), per-domain mode state (banned),
and a fault-masking loophole against the §7 fail-closed rule; epoch-checked handles already cover
object lifetime for everything reached through a capability. Non-canonical addresses fault; a
masking *extension* could be added additively if a real consumer appears. **The forward-width
rule, the same refusal from the other side:** the implemented virtual-address width is a
published `GEOMETRY` fact of the MachineView with **no small architectural ceiling** — a future
machine may implement up to the full 64-bit canonical split — so software must never store data
in "unused" upper pointer bits: an address non-canonical today may be real tomorrow, and it
faults today (fail-closed) precisely to keep that door open. Pointer bits belong to addresses,
on every LNP64 machine, forever.

## 6. Atomics, fences, and the memory consistency model

**Every instruction boundary is a preemption point, unconditionally (Law 5).**
This machine has **no LR/SC** and no constrained-window contract, no reservation set, and no
multi-instruction or software-created non-preemptible region. The indivisible interval of one
instruction remains bounded by its published class and parameters. Atomic RMWs of at most 8 bytes,
and 16-byte load/store/CAS, map to
one instruction with unconditional bounded-time completion. A 16-byte exchange or fetch operation, or
another RMW without a direct `amo` function, uses an `amo.cas`/`casq` loop whose contention behavior the
far-execution license serializes at the data's home. The cost of the deletion is the constrained
window's eventual-success guarantee for *arbitrary*
inline read-modify-write sequences, which the three languages' atomics models never needed.
**Every op is bounded, or blocks only at an instruction boundary; WCET analysis has no carve-out.**
The `pause` hint remains for optimistic spins.

**Restartable sequences, architected (`thread.rseq`, §16.1/§17.7) — what Law 5's
absolutism gives back.** The one genuine loss under every-boundary-preempts is the per-CPU fast
path built on preemption-off; the modern kernel already migrated that pattern to restartable
sequences, so the machine architects *that* instead of the carve-out: a per-thread descriptor
`{start, end, abort_ip, cpu_id_ptr}`, and **any resumption into `[start, end)` after preemption,
migration, or a machine call resumes at `abort_ip` instead** — a degenerate machine call that
edits only `resume_pc` (§9.3's machinery, minus the payload). `cpu_id_ptr` (0 = none) is kept
current with the thread's **view-tile ID** (its own coordinates, Law 7 — never a physical tile) at
every resume. A nonzero `cpu_id_ptr` is a persistent engine-written pointer: `SET_RSEQ` succeeds only
after pinning and charging its naturally aligned 4-byte range; while registered, an unmap, protection
change, backing transition, or executable-state replacement covering it fails `-BUSY`. Clearing the descriptor,
thread death, or `dreplace.commit` releases the pin. Thus resume never recursively faults while writing
the tile ID. This is the per-CPU index the pattern needs. The sequence *restarts* — nothing is
deferred, no region is unpreemptible, every instruction boundary remains a preemption point, so
Law 5 is untouched and the WCET sentence survives verbatim; the commit is the sequence's final
store, by construction (the standard rseq discipline). `abort_ip` outside `[start, end)` is
`-MALFORMED` (an in-window abort target would restart forever); one descriptor per thread, zeros =
clear; full quiescence plus `state.open` captures an in-window thread parked at `abort_ip` (the §17.9
`ENGINE_STATE` rule — checkpoint machinery again). Per-tile counters, freelists, and allocator
magazines are back to a handful of plain instructions, and the machine never lied to get there.

**Baseline consistency — the architectural model is the annotated MCA model; TSO is v1 silicon's
property, never the architecture's promise. Quantified over a coherence volume.** **The
architectural contract for plain `ld`/`sd` on `normal_cached` memory is exactly this:** per-location coherence (a single order of stores to each
location that all agents agree on), same-address program order, and **other-multicopy-atomicity**
(a store becomes visible to all *other* agents at one point — IRIW-with-plain-loads forbidden);
**ordering between accesses to different addresses comes only from the `aq`/`rl`/`sc` annotations
and fences defined below.** The quantifier costs nothing, because §15's locality classes make
cross-volume shared memory **unconstructible**: every agent set that can share a location sits
inside one volume (a domain that spans volumes *is* one volume for this purpose — it named the
diameter), so "all agents" and "all agents in the volume" are the same set for every program that
can exist. **v1 silicon implements TSO** — a core's own accesses appear in program order except
that a younger load may complete ahead of an older store to a different address (FIFO store
buffer, same-address forwarding) — and TSO **implements** the architectural model (every TSO
execution is a legal MCA-model execution), so v1 *overimplements* the contract. **The
strengthening is a per-implementation choice, never a standing silicon obligation:** a future
conforming implementation — a many-core part, a low-power part — may implement the annotated MCA
model directly, with no TSO machinery, and every correctly annotated binary runs on it unchanged.
That is the asymmetry the model buys: declaring weak preserves the option to ship TSO forever;
nothing anywhere requires shipping it twice. The v1 fact is an
implementation fact software may observe but never rely on: **the conformance oracle for software
is the reference emulator, which executes the weakest legal model** (Appendix D's memory-model
family), so a binary leaning on TSO idioms without annotations is nonconforming *today*, off
silicon. Other memory types order differently, not uniformly "more strictly":
`uncached` is coherent and unbuffered; `device_ordered` is strongly ordered; `write_combining` is
**weaker** (its stores may coalesce and reorder until a fence). The per-type ordering table is in
§15. The annotated model is the contract; the fences below add ordering on top of it.

**One subfield home for the whole atomic family (pinned).** Every atomic-family op places its common
fields at the **same bit positions**: **`size[30:29]`** (`0` b, `1` h, `2` w, `3` d), **`ord[28:27]`**
(`0` relaxed, `1` aq, `2` rl, `3` aqrl), **`sc[26]`**, and — on sized loads — **`sign[31]`** (`0`
zero-extend, `1` sign-extend, ignored for `d`). An op whose width or ordering is fixed by its opcode
simply does not decode the field (`ld.aq` is acquire by opcode: it decodes `size`/`sign`/`sc`, not
`ord`; `ld.q`/`sd.q` are 16-byte by definition: they decode `ord`/`sc` only). **The futexes are declared
outside this family home**: `futex_requeue` occupies all six register slots, so `[30:26]` is physically
unavailable to the family — the three futex ops carry their own 2-bit `size` field at `[1:0]` and a
**`scope` bit at `[2]`** (`0` `SHARED`: the key derives from the mapping — backing identity +
offset for shared, address-space + VA for private; `1` `PRIVATE`: the key is `{address space,
VA}` **directly, no mapping classification** — the runtime already knows its mutex is
process-private, and a false `PRIVATE` on shared memory is broken synchronization, never an
authority fault) (§6 below).

**Atomic fetch-and-op (`amo` 0x90, custom format).** `amo.<op>.<size>[.<ord>] rd, (rs1), rs2[, rs3]`:
one opcode. Subformat (the `rs4`/`rs5` slots are unused, so `[35:0]` is the subformat region):
**`func[35:31]`** = op (`0` add, `1` and, `2` or, `3` xor, `4` nand, `5` swap, `6` min, `7` max, `8`
minu, `9` maxu, `10` cas, `11` casq; **`12` fadd, `13` fmin, `14` fmax** — the C++/Rust floating
RMWs, f32/f64 selected by the family `size` field, **mandatory like every other `amo` func, not
`FEATURES`-negotiated**: there is no optional instruction (§1), so these ride the whole-FP view grant
exactly as scalar `fadd` does — a machine that has FP has them, and one that denies the FP view
emulates them with the rest of FP, never selectively; `15`–`31` reserved), then the family home
`size[30:29]`,
`ord[28:27]`, `sc[26]`; **on funcs `10` cas / `11` casq only, `ford[25:24]` — the failure
ordering** (`0` inherit, `1` relaxed, `2` acquire, `3` seq_cst), with
`[23:2]` reserved-zero on those two funcs; on every other func `[25:2]` is reserved-zero as
before (func-extension space; the per-func field-validity rule — a nonzero `ford` outside
cas/casq is reserved → illegal-instruction); `[1:0]` = the §12 placement hint.
**The `sc` bit is semantic in the architectural model** — it joins the op to the volume-wide SC
total order — and compilers **must set it on every `seq_cst` RMW from day one**; v1's TSO silicon
may decode-accept and ignore it only because `aqrl` already delivers `seq_cst` under TSO (an
implementation shortcut the model licenses, not a meaning the bit lacks). Sizes are naturally aligned, else the op
faults like `ld`/`sd`. Semantics: atomically `old ← M[rs1]`; compute `new = op(old, rs2)` (for `cas`:
`new = rs3` iff `old == rs2`, else no write); write `new`; return **`old`** in `rd`, sign-extended from
the operation size (matching §5 loads). A single instruction that **cannot fail and needs no retry
loop**: each `amo` completes in bounded time at its execution point, with conflicting `amo`s serializing
there — guaranteed forward progress. Legal **only on coherent `normal_cached` memory** (an `amo` to an
`uncached`, `device_ordered`, or `write_combining` mapping raises a synchronous memory fault: atomicity
cannot be tracked without coherence; use plain `ld`/`sd` and fences for device memory).

**Failure ordering on `cas`/`casq` (`ford[25:24]`).** On a failed compare (`old ≠ rs2`: `old`
returned, nothing written) the operation takes effect as a **load at the `ford` ordering**;
`ford = 3` additionally makes that load an `sc`-marked member of `S` (the `.sc` refinement's
shape). On success `ord`/`sc` apply unchanged. `ford = 0` = **inherit**: the failure load
carries the acquire half of `ord` plus `S` membership when `sc` is set. **The field defines the
floor; strengthening is always conforming** — computing `join(ord, ford)` at decode is a legal
implementation; exploiting the split (skipping SC arbitration on an `acquire`-failure path) is
the ambitious one. The model expresses a failed CAS as a load with a derived ordering; `ford`
parameterizes the derivation. Mandatory litmus seeds (Appendix D): **MP-fail** (`ford ≥ acquire`
forbids the stale read), **SB-fail** (two `ford = 3` failures are both in `S`), and
**inherit-equivalence** (`ford = 0` outcomes equal the explicit join's). C++/Rust forbid
release-class failure orderings, so two bits cover the legal set exactly.

**Floating `amo` (funcs 12–14).** `amo.fadd/fmin/fmax.<f32|f64>` compute the new value in IEEE 754
arithmetic at the same serialization point as the integer family. `fadd` uses the **default rounding
mode, round-to-nearest-even** — the `amo` encoding carries no `rm` field and atomic accumulation has
no caller to thread one, so RNE is fixed by definition (this is the one place FP rounding is not
`rm`-selectable, declared rather than silent). `fmin`/`fmax` follow the §14 **IEEE 754-2019
`minimum`/`maximum`** (NaN-propagating, −0 < +0), identical to the scalar ops. A floating `amo`
**raises no FP trap and accrues no IEEE status flags — none, in any form**: the operation executes
at the data's home under the far-execution license, where the issuing thread's `FCSR` does not
exist, and the posted form (`rd`=`r0`) has no reply to carry flags back on — so "flags accrue as
scalar" would be a promise the posted form physically cannot keep and the replied form could keep
only by making flag behavior depend on the destination register number. One rule for all forms
instead: funcs 12–14 are flag-silent, declared (the one FP family outside the flag contract,
alongside their fixed-RNE rounding — atomic accumulation has no caller to observe either); code
that must detect overflow/inexactness on an accumulator checks the returned old value or uses a
lock, which is what every other ISA's fetch-FP shape honestly requires too. `f32` operates on the low 32 bits of the aligned word.
Every other `amo` rule holds unchanged: single instruction, no retry loop, forward progress at the
serialization point, the posted form (`rd`=`r0`), the far-execution license, `normal_cached` only.
These make **floating `fetch_add`/`fetch_min`/`fetch_max` one instruction each** — the last RMW that
used to loop.

**16-byte atomics (`casq` + `ld.q`/`sd.q`) — the one architected register-pair case.** Function `casq`
in the same `amo` opcode: `amo.casq rd, (rs1), rs2, rs3` where `rd`/`rs2`/`rs3` name **even registers and
operate on the pair `{rN, rN+1}`** (odd → illegal-instruction): compare the 16-byte pair `{rs2,rs2+1}` at
16-byte-aligned `rs1`, swap in `{rs3,rs3+1}` on match, return the old 16 bytes in `{rd,rd+1}`. Companions
`ld.q` 0x81 / `sd.q` 0x82: **single-copy-atomic** 16-byte load/store of an even pair, 16-byte aligned
(fault otherwise), `normal_cached` only — **register-only custom format, no immediate** (an atomic on a
computed address; adding `imm32` would collide with the subfield home, §1): `ld.q rd(even), (rs1)`,
`sd.q (rs1), rs2(even)`, decoding `ord[28:27]`/`sc[26]` from the family home; remaining low bits
reserved-zero. Register pairs violate full orthogonality, so this is declared as the **single architected
pair exception** (§1, the analogue of the PCR-subformat exception): confined to exactly seven forms,
because a 16-byte result physically needs two registers and every alternative is worse — tagged-pointer
stacks and sequence-lock fast paths that lean on cheap `cmpxchg16b`-class ops need an inline
instruction, and 16 bytes is the widest atomicity the machine promises (k-word shapes are software's:
version words, seqlocks, locks). `casq`/`ld.q`/`sd.q` carry the same ordering
field, forward-progress guarantee, and far-execution license as the rest of the family. **Spill pairs are
separate, plain ops** (an atomic with no offset field makes a poor prologue instruction, and a spill
needs no atomicity): `ldp` 0x7f / `sdp` 0x80 — even **GPR** pair load/store with the ordinary
`base + sext(imm32)` I/S forms and plain §5 alignment semantics (the callee-saved `s0`–`s9` =
`r18`–`r27` are even-based pairs by design, so prologue/epilogue save-restore halves); the FP twins are
`fld.q` 0x87 / `fsd.q` 0x8b (§14). These **seven** forms — `casq`, `ld.q`, `sd.q`, `ldp`, `sdp`,
`fld.q`, `fsd.q` — are the entire scope of the register-pair exception. **And the exception's hard
core is three, not seven — the crack license, explicit:** the four plain spill pairs (`ldp`/`sdp`/
`fld.q`/`fsd.q`) **may be executed as two ordinary accesses with no atomicity claim** — they never
made one (§5 plain semantics; a spill needs no atomicity), so their rename and LSQ cost rounds to
zero on any implementation that prefers it. Only `casq`/`ld.q`/`sd.q` are irreducibly pair-atomic,
and 16-byte results are physics.

**Posted form (`rd` = `r0`).** When `rd` is `r0` the old value is architecturally discarded and the
instruction is a **posted atomic**: no reply is required, so a result-unused fetch-op (`counter++;` as a
statement — the dominant statistics/refcount pattern) costs approximately a store. **"Posted" is a
dataflow statement only, never an ordering downgrade: the op retains the *full* ordering of its encoded
`aq`/`rl`/`sc` bits** (an implementation may only post the *reply*, not the ordering — an `aq`-bearing
posted amo still holds younger accesses until its ordering point; anything weaker would make the
store-buffering litmus observable on exactly the form compilers emit automatically). The compiler emits
this form automatically whenever the result is unused. (This is the machine's one
register-number-changes-behavior case, and it is the natural dataflow statement — `rd = r0` *is* "the
result is unused" — declared rather than disguised, Appendix B.)

**The far-execution license.** An implementation **may** execute an `amo` *at the data's home* (the
shared-cache slice, home node, or owner engine) instead of acquiring the line into the issuing core —
**the operation travels to the data rather than the line ping-ponging between contenders**, so N cores
hammering one counter become N small messages serialized at one place instead of a chip-wide tug-of-war
over one cache line. Atomicity, coherence, and the encoded ordering must be preserved exactly; software
cannot detect the placement except through timing. **The forward-progress promise under the license is an arbitration contract:** a
fabric-remote `amo`'s bounded-time completion under contention is a promise about the **home node's
arbiter** — conflicting operations serialize there under bounded arbitration (the §16.4
engine-concurrency license's fabric twin: no starvation, no unbounded retry). **The WCET parameter is
not the live contender count.** Before issue, the caller's MachineView geometry publishes the maximum
number `A_volume` of CPU/device agents that may simultaneously issue atomics into its effective
coherence volume and the home arbiter's per-request service quantum `Q_home`. The architectural bound
is the worst case over that population, `fabric_round_trip(diameter) + A_volume × Q_home`, including
wake/arbitration overhead; a smaller number that depends on who happens to contend is diagnostic only,
never a conformance bound. An implementation whose remote-AMO arbitration can starve a requester or
admits more agents than its published `A_volume` is nonconforming. The §12 hint zone on `amo` encodings may carry a
**contention hint** (near-biased / far-biased, from PGO or annotation), decode-ignored in v1 and never
semantic.

**Real-time consequence.** On a large volume the published worst case can be intentionally too large
for useful admission, even when measured contention is usually low. Real-time software therefore
keeps contended atomics inside a deliberately small coherence volume, partitions the state, or uses a
serialized gate/Counter whose admitted service bound is appropriate; it must not admit against a
diagnostic live-contender count. Volume sizing is part of WCET design, not merely placement tuning.

**Language mapping.** Every 1-, 2-, 4-, or 8-byte C11 / C++ / Rust atomic RMW lowers to
**one** `amo` at the requested ordering: `fetch_add`/`fetch_sub` (sub = add of the negation),
`fetch_and`/`or`/`xor`, Rust's `fetch_nand`, C++26/Rust `fetch_min`/`fetch_max` (signed and unsigned),
`exchange` = `swap`, and `compare_exchange_strong` = `amo.cas` **with `ord`/`sc` = the success
ordering and `ford` = the failure ordering** — **no loop; the instruction is the strong
form**, and `compare_exchange_weak` lowers to the same instruction (a spuriously-failing weak form buys
nothing when `cas` cannot fail); the IR's split orderings survive to silicon. **The claim's precise scope: one instruction per *memory
transaction*.** The atomic read-modify-write is a single `amo`; the language-level operation may
still spend ordinary register instructions around it (`compare_exchange` compares the returned old
value, produces its boolean, and updates the `expected` object — register post-processing, never a
second memory access and never a retry loop). `seq_cst` RMWs use `aqrl` **with the `sc` bit set** (mandatory) — **and the converse holds: an `aqrl` access or RMW *without*
the `sc` bit is NOT a member of the SC total order.** Membership in `S` is exactly the set of
`sc`-marked accesses plus `fence.sc` (§6's order definition); `aqrl` alone buys acquire+release
edges and nothing about `S`. Atomic
loads/stores are one instruction at every ordering (`ld`/`sd` relaxed, `ld.aq`/`sd.rl` acquire/release,
`.sc` forms `seq_cst`). **The exact width claim:** 1/2/4/8-byte load, store, CAS, exchange, and fetch
RMWs are one instruction and lock-free; 16-byte load, store, and CAS are one instruction
(`ld.q`/`sd.q`/`amo.casq`), while 16-byte `exchange` and fetch RMWs use a lock-free `casq` retry loop.
Larger language atomic objects have implementation/library-defined lowering and carry no architecture
claim of universal lock freedom. C++20/Rust `atomic::wait` is a software load/recheck loop containing
`futex_wait`; notify uses `futex_wake` (and batching/requeue may use `futex_requeue`). A wake is a reason
to recheck, not proof the value changed. Thus no fence stronger than requested is needed, but loops are
required exactly for 16-byte non-CAS RMW and wait/recheck (`completeness_inversions.md` is the inversion).
Each direct pair RMW would be a new member of the **closed** register-pair exception (seven
forms, never grows — Appendix B) with new decode, rename, verification, ABI, and context machinery,
on a surface `casq` already covers;
**floating `fetch_add`/`fetch_min`/`fetch_max` are each one `amo`** (funcs 12–14 above, mandatory —
so no concession is needed); and **a `compare_exchange` with split success/failure orderings
encodes both** — `ord`/`sc` the success side, `ford[25:24]` the failure side (above) — so the
mapping pays for **no** ordering it did not ask for, anywhere.

**Fences:** `fence` 0x92 (full local ordering), `fence.acq` 0x93, `fence.rel` 0x94,
`fence.acq_rel` 0x95, `fence.sc` 0x96. A fence orders normal cached memory, atomics, DMA visibility,
engine completions, **and device memory** per the fence flags and the accessed mapping's memory type
(§15). **`fence` vs `fence.acq_rel` differ in exactly one edge — store→load:**
`fence.acq_rel` orders load→load, load→store, and store→store but **not** older stores before younger
loads; **`fence` additionally orders store→load**. On v1's TSO silicon `fence.acq_rel` is
free and `fence` **drains the store buffer** — the one reordering that silicon performs, making
`fence` the only non-SC fence that is not a no-op *on v1*; under the architectural model every
edge is semantic, which is why `acq_rel` code must carry the fence rather than eliding it.
**`fence.sc` is the sequentially-consistent fence:** beyond `fence`'s full local ordering, **all
`fence.sc` executions within a coherence volume observe a single total order** (the SC point is
per-volume: `seq_cst` is defined over agents sharing memory, and cross-volume agents share none,
§15), which is what implements C/C++ `seq_cst` fences; `fence` and `fence.acq_rel` do not contribute to that order.
**And "one order" is a constraint on outcomes, never a construction:** distributed timestamping, ordered fabrics, home
arbitration, and hierarchical ordering all conform — nothing requires or implies one
centralized sequencer, and only explicitly `sc`-marked operations participate at all; ordinary
memory never pays for the order's existence. A wide constructible volume prices its SC
diameter at admission (§15), never by quietly serializing the machine.
**Edge sets, exactly:** `fence.acq` orders load→load and load→store; `fence.rel` orders load→store and
store→store; `fence.acq_rel` is their union; `fence` adds store→load; `fence.sc` adds the volume-wide
total order.

**Annotated atomic loads and stores (`ld.aq` 0x7d / `sd.rl` 0x7e) — ordering rides the access, not a
fence.** A fence orders *all* older/younger accesses where an annotated access orders only itself (the
over-serialization that made AArch64 ship LDAR/STLR), and a fence-based `seq_cst` mapping puts the
store-buffer drain on the load side — the *common* side, since `seq_cst` loads vastly outnumber `seq_cst`
stores. Two custom-format opcodes: `rd`/`rs1` as `ld`; `sd.rl` data slot-named in `rs2`; the family
subfield home supplies `size[30:29]`, `sign[31]` (on `ld.aq`), `sc[26]`; **`imm12[25:14]`** the
sign-extended byte offset (below); `[13:0]`/`[8:0]` the §12 hint zone; other bits reserved-zero.
- **`ld.aq`** — load-acquire (RCsc): younger accesses cannot pass it. With **`sc`** set it is a `seq_cst`
  load.
- **`sd.rl`** — store-release (RCsc): it cannot pass older accesses. With **`sc`** set it is a `seq_cst`
  store.
- **`seq_cst` semantics:** all `sc`-marked accesses and `fence.sc` executions within a coherence
  volume observe one total order (the §15 quantifier: cross-volume agents share no location, so the
  order is total over everyone who can tell). **On v1's TSO silicon the drain lands on the store side** — `sd.rl.sc` drains the store
  buffer; `ld.aq.sc` is free (the x86 convention, matching the real frequency of each) — and under
  the architectural model each annotated access orders only itself, never a fence's whole neighborhood.
Naturally aligned like their sizes; `normal_cached` only; relaxed atomics remain plain `ld`/`sd`.
**Offset form (the `LDAPUR` lesson):** both opcodes carry
**`imm12[25:14]`**, sign-extended, byte-granular, added to `rs1` (`ld.aq rd, imm(rs1)`;
`sd.rl imm(rs1), rs2`) — atomic field-of-struct access is one instruction, not `addi` + access.
ARM added `LDAPUR` after compilers kept paying that `addi` on exactly this, the single most common
atomic addressing shape in Rust/C++/Go object code; a base-only form would be
the known-suboptimal lowering shipped deliberately. Alignment and fault rules are the ordinary
ones (the effective address obeys §5), and a zero
immediate is the old encoding — nothing existing moves.

**The normative C/C++/Rust mapping (frozen).** The table states the exact width-dependent lowering; no
mapping pays for ordering it did not ask for except the split-order join identified above:

| Language op | LNP64 |
| --- | --- |
| load relaxed | `ld` |
| load acquire / consume | `ld.aq` |
| store relaxed | `sd` |
| store release | `sd.rl` |
| load seq_cst | `ld.aq.sc` |
| store seq_cst | `sd.rl.sc` |
| RMW, 1/2/4/8 B | one `amo` with the matching `ord` bits; `seq_cst` additionally sets `sc` |
| load / store / CAS, 16 B | one `ld.q` / `sd.q` / `amo.casq` |
| exchange / fetch RMW, 16 B | `amo.casq` retry loop with the requested ordering |
| larger atomic object | implementation/library-defined; no architectural lock-free guarantee — **and 16 B is the architectural maximum single-access atomic load/store/CAS width, permanently**: wider atomicity, if a future ever wants it, is a new mechanism through a named seam (transactional or engine-mediated), never a wider register pair, so ABIs and lock-free algorithms may treat the 16 B ceiling as frozen |
| `atomic::wait` | load/recheck loop containing `futex_wait`; wakes always recheck the value |
| fence acquire / release / acq_rel / seq_cst | `fence.acq` / `fence.rel` / `fence.acq_rel` / `fence.sc` |

The standalone fences remain for language-level fences and legacy patterns. **The mapping above is
the ABI, and it is not discipline — it is the semantics: the annotation-semantic MCA model defined
in this section *is* the version-1 architectural memory model**, not a floor some future revision
may descend to. There is no sanctioned TSO-only compilation mode because there is no architectural
TSO to compile against — a binary that drops the ordering annotations is incorrect against the
architecture as defined *today*, even though v1 silicon (a legal strengthening) will happen to
execute it as intended. This kills the fork in both directions at once: no
forward-compatibility fork (annotations are free on TSO silicon and load-bearing on any weaker
conforming implementation), and no deferred enforcement (free-on-TSO also means untestable-on-TSO,
so Appendix D's memory-model family binds the **reference emulator** to execute the weakest legal
model as the litmus/fuzzing oracle — mis-annotated hand assembly and JIT backends fail the suite
today, off-silicon, not after a decade of latent correctness, the x86→ARM porting problem
deliberately not deferred through time). **The model's MCA property is committed by name, not
emergent:** a store becomes visible to all *other* agents at one point (the ARMv8 decision);
IRIW-with-plain-loads is forbidden on every conforming machine — quantified, like every §6
property, over the agents of a coherence volume (§15), which is every agent set that can share a
location. (Non-MCA buys an implementer almost nothing, every post-2015 ISA converged on MCA, the
verification tooling assumes it, and it is what keeps `fence.sc`'s volume-order claim cheap — MCA
is easier, not harder, when the agent set is a compact local group.) One machine in silicon, one
model on paper, one enforcement mechanism in the suite, no execution-mode fork.

**The model is a definition with a table of contents, not a vibe — and the emulator alone proves
nothing's absence.** A weak execution *chosen once* is not a search: a binary carrying a
forbidden TSO assumption can pass millions of ordinary weak-mode runs and fail in the field, so
"the reference emulator is the oracle" is cashed as **three artifacts, jointly the E1 freeze
gate** (`isa_migration_status.md`): **(1)** the normative model itself, axiomatic or
operational, **consumable by herd-class tooling**, defining at minimum — preserved program
order; address, data, and control dependencies; store forwarding; coherence order; reads-from
and from-read; RMW atomicity; acquire/release synchronization and release sequences; failed-CAS
ordering; mixed atomic/non-atomic access; mixed-size overlaps; the SC access-and-fence total
order; device-memory and DMA interaction; instruction-fetch interaction (§6 `isync`); and
no-thin-air — the checklist frozen here so no relation is discovered missing at tool-writing
time; **(2)** a litmus model checker that *enumerates* each test's allowed and forbidden
outcomes against that model; **(3)** the emulator's **adversarial mode** — actively delaying,
reordering, and perturbing within the legal envelope, seeded per run — which is a *testing
oracle* for real binaries and is never claimed as proof that an arbitrary binary is
assumption-free. **Resolution discipline: a surprising litmus outcome is never fixed in prose.**
Any disagreement between prose, model, and expectation resolves through exactly one of three
explicit changes — the event extraction (`lnp64.bell`), the `.cat` relations, or the stated §6 rule
— followed by regenerated expected-outcome sets and an ISA-revision decision.

**Small print, pinned:** a **failed `amo.cas`/`amo.casq`** performs no store and takes effect as a load
carrying only the **acquire half** of its encoded ordering (the release half applies only when the store
happens — the C++ failure-ordering rule, in silicon). **The `.sc` refinement:** a failed CAS whose encoding carried the `sc` bit takes
effect as a **sequentially consistent load** — it keeps its membership in the SC total order at
its position; only the store/release half vanishes. "Acquire half" names the *edge set* that
survives failure, never an exemption from the total order the encoding joined. **Mixed-size / overlapping atomics:** same-address
ordering and RMW-atomicity guarantees hold only between accesses of identical address *and* size;
overlapping-but-unequal atomic accesses get per-byte coherence and nothing more (a software error, not a
hardware hazard). **And the sentence connecting that rule to the pattern it quietly licenses,
stated:** per-byte coherence is *sufficient* for the seqlock read side —
a version-validated payload read (`ld.aq` version; payload loads of any size or overlap; `ld.aq`
version; compare) may observe **torn payload data, and a torn read that the version compare then
discards is defined data at the ISA level, never undefined behavior**: each byte read is some
coherent value of that byte, the validation detects any interleaved write, and the discarded
value flows nowhere.

The seqlock read side (`ld.aq` version, payload loads, `ld.aq` version, compare-branch) is
ordinary code; the validate-and-retry edge is a profitable adjacency an implementation may execute
as one internal op under the general cracking license (§4.3) — a tuning-note idiom, no architected
pair and no compiler dependence.

**Cross-memory-type ordering (the doorbell contract).** Between accesses to *different* memory types
there is **no implicit ordering**; fences order across types exactly as within one: a fence's edge set
applies to **all older/younger accesses regardless of memory type**, and "ordered" means **globally
observable** — including to coherent DMA readers — not merely locally retired. Consequences, pinned: the
canonical driver sequence is *fill the `normal_cached` ring, `fence.rel`, store the `device_ordered`
doorbell* — the `fence.rel` store→store edge guarantees the ring contents are observable to the device
before the doorbell store issues. This publish sequence is an ordinary `fence.rel` + `device_ordered`
store — an implementation may execute the tail as one internal publish op under the general cracking
license (§4.3), with no architectural obligation and no new ordering to verify (the release ordering
is the fence's, a bus error is the store's; the license never implies the hardware knows which
descriptors the doorbell published). No architected pair, no adjacency requirement — the driver just
emits the two ordinary ops. **`write_combining` buffers drain on any fence with a store→store
edge**; nothing else flushes them implicitly. `device_ordered` accesses remain mutually program-ordered
among themselves (§15) but are **not** ordered against `normal_cached` traffic except through a fence.
**The read-back flush rule** (the doorbell contract's other half): a **load** from a function's `device_ordered` space
completes only after every older **store** from the same thread to that same function's
`device_ordered` space has **reached the function or terminated with a bus error** — so the
universal driver idiom `writel(cmd, doorbell); readl(status)` is a guaranteed flush of the posted
write, not a race the driver happens to win. The rule is per-function and per-thread (cross-thread
flushing is what fences are for), and `write_combining` space is exempt — its drain is the fence
rule above, never an implicit read side effect.
(**Named seam:** HSA-style *scoped* fences do not exist because there is only **one scope per
addressable universe** — coherence is volume-scoped (§15), a domain's fences order everything it
can address, and cross-volume agents share nothing to fence, so a scope qualifier would select
among options that cannot differ. If a future non-coherent tier ever arrives, scope qualifiers
ride reserved fence encoding space additively; nothing else may claim that meaning.)

**Location is physical:** the memory model's *location* is the
backing frame, never the virtual name. Accesses through any number of mappings of one frame —
aliases within a domain or across domains — are **same-location** for coherence, ordering, and
atomicity. **Agreement is enforced, never a software premise:** for every physical byte range, all
simultaneously live CPU mappings must use one v1 memory type; the four v1 types are singleton
compatibility classes (`normal_cached`, `uncached`, `device_ordered`, `write_combining`). `mmap`,
`AS_MAP`, image replacement, and any mapping-type transition consult the backing/frame reverse map
across domains and fail `-DENIED` atomically if an overlapping live mapping has a different type.
Non-overlapping portions of one device BAR may still use different permitted types. Thus multi-mapping one backing at several
virtual addresses (the §15 sharing model, and Appendix B31's sanctioned load-barrier-GC path)
changes nothing about how those accesses interact. A mutator's store through one view and a
collector's load through another are same-address accesses in every clause of this section.

**Code publication is one transaction, and it is the W→X permission change.** There are exactly two cases, and they do not overlap:

- **Publishing new code (write-then-execute) — `AS_PROTECT`/`map.protect` from writable to executable
  is the complete transaction, no per-core `isync`.** The canonical rule: **a successful W→X
  transition of a backing range completes only after instruction-side invalidation is acknowledged
  throughout every mapping volume of that range** (the permission change bumps the range's epoch
  cell; the §11.2 acknowledged broadcast *is* the i-fetch invalidation). After the op returns, a
  new fetch anywhere observes the published instruction words, and **no instruction fetched through
  the superseded (writable, non-executable) state may begin execution afterward** — there was no
  executable mapping to fetch through before the flip, so this is vacuous on the old side and total
  on the new. The JIT writes bytes, calls `AS_PROTECT` exec, and is done; it never scripts per-core
  shootdowns.
- **Live-patching already-executable code (X→X) — an authorized atomic patch plus `isync`.** An
  ordinary store never writes an X-only mapping. The aligned 8-byte patch write must be either
  **(a)** an atomic store through a writable alias of a `JIT_ARENA` backing (the only backing class
  permitted to be W-mapped while X-mapped, §11.2), or **(b)** an aligned 8-byte
  `DebugTarget WRITE_MEM`, whose `DEBUG` authority is the architected exception for patching target
  executable memory (§16.3/§17.7) and whose engine write is single-copy atomic. Non-`JIT_ARENA`
  software without a DebugTarget must use W→X publication instead; it has no ordinary X→X store path.
  After the authorized patch write, `isync` 0x97
  `(r_addr, r_len)` makes the **current core's** subsequent fetches observe the prior stores to
  `[r_addr, r_addr+r_len)` (ordered after those stores). It **never faults** (bytes not mapped
  executable are simply not invalidated), writes no `rd`, and a wrapping range is a **no-op** (the
  one §1 overflow-reject carve-out — `isync` has no error channel, Appendix B). This case *does*
  run `isync` on each fetching core (the OS sequences it); it is **local**, never a global
  broadcast — because here there is no permission change to carry the acknowledged invalidation, so
  the ordering is placed by hand. `isync` is thus the local live-patch primitive, `AS_PROTECT` the
  cross-core publish transaction; neither is a second spelling of the other.

**Cross-modifying-code fetch atomicity (guaranteed).** Every instruction is one naturally-aligned 8-byte
word (§1), so **no fetch ever straddles a store granule**: instruction fetch reads each aligned 8-byte word
**single-copy-atomically**, and either authorized naturally-aligned 8-byte patch write above is **fetch-atomic**
— a concurrent fetcher observes the wholly-old or wholly-new instruction word, never a torn one. Before
`isync` on a fetching core, *which* of the two it observes is unordered (both must therefore be valid at
that PC during a live-patch window); after that core's `isync`, it observes the new word. Live patching, ftrace-class tracing, and JIT inline-cache flips (the NOP ↔ branch swap protocol) are sound without stopping cores.

**Futexes** (address-keyed userspace blocking, no kernel mode, §2.1). **RT rule:** a futex parks a
thread but transfers no scheduling donation; the priority-inheriting mutex is a serialized gate
(§9), which does. Futex = throughput mutex; serialized gate = RT mutex (Appendix B). The machine
architects no lock-word format — every bit of the word is the personality's (§6); a future
priority-inheriting or robust futex mechanism arrives whole through the Appendix G
`FUTEX_EXTENSION` seam, never format-first.

`futex_wait` 0x99 `rd, addr, expected, deadline` (all **register** operands: `addr`=rs1, `expected`=rs2,
`deadline`=rs3 — a 64-bit GPR, since a deadline cannot fit the immediate field, §1) atomically checks
`*addr == expected` (naturally aligned, acquire); if equal it blocks until woken or the deadline. **The
deadline is an absolute timebase value in ticks (Law 4, §8)**, with **`0` = non-blocking poll and
all-ones = block forever — the two architecturally reserved deadline sentinels, uniform machine-wide**
(deadline `0` is already expired, so "already expired" and "poll" coincide semantically;
`UINT64_MAX` is reserved and is never returned by `TIME`, §8). **Word size is a pinned subfield, not fixed:** all three futex ops carry `size[1:0]` at bits `[1:0]`:
`00` = `d` (8-byte), `01` = `w` (4-byte, zero-extended compare), **`10` = `b` (1-byte), `11` = `h`
(2-byte)** — the futex field gives `d` the all-zeros encoding because the conventional 64-bit mutex word is the
dominant case (so it is *deliberately not* the family's size code points — family: `2` w, `3` d). **Sub-word waits**
(`atomic<uint8_t/uint16_t>::wait`) are **native, not emulated**: the wait-queue key is already the
logical `{object, offset}`, so byte/half addressing costs nothing, and the compare is an aligned
narrow load at that granularity — `futex_wait` on a `b`/`h` word wakes on the sub-word value
directly, with no containing-word re-check. Wait/wake/requeue
match only within the same size. Richer
timeouts (relative, wall-clock) are expressed by arming a timer object and waking on it, not by this fast
path. Returns `rd = 0` on wake, `-BUSY` if the value already differed, `-TIMEOUT` on the deadline,
`-INTERRUPTED` on a machine call (§9). `futex_wake` 0x9a `rd, addr, count` wakes up to `count` waiters on
`addr` and returns the number woken.

**The wait-queue key is mapping-type-dependent (the fork/COW aliasing fix):** for a **shared** mapping
the key is `{backing-object identity, offset}` (works across every mapping of the object); for a
**private** mapping it is `{address-space object identity, VA}` (keying private futexes by physical
frame would alias parent and child across a fork's COW window). Under `scope = SHARED` (§1's
futex subformat) the engine reads the mapping type from the VMA at wait time; under
**`scope = PRIVATE`** the key is `{address space, VA}` **directly** — no mapping classification,
because the runtime already knew (the `FUTEX_PRIVATE_FLAG` fact carried as an operand; a false
`PRIVATE` over shared memory is broken synchronization, never an authority fault). The
uncontended path touches
only the word, and only contention enters the scheduler (charged to the calling domain's scheduler
budget). **Futexes are legal only on coherent `normal_cached` memory** (the atomic compare and the wake
key both need coherence): a futex word in an `uncached`, `device_ordered`, or `write_combining` mapping
**faults**. **Lifetime rule:** logical keys make COW breaks and migration no-ops; teardown of the waited
range is a `cancel`-policy bump of the VMA's cell, and wake/cancel behavior is the Appendix F
park machine's (machine 6) — waiters wake `-CANCELLED`, fail-closed. The one futex-specific pin:
**the park is a single race-safe transition** — compare, key derivation, and queue insertion
snapshot the VMA cell's epoch at the compare and re-validate it at insertion under the same
serialization the cancel scan takes, so an unmap lands on exactly one side (fail the wait
`-CANCELLED`, or find the registered waiter) and the dead-key interleaving is impossible, not
rare. **Carve-out
(intentional, declared):** the futex word is a *direct memory operand*, not a checked descriptor, so an
unmapped or unaligned `addr` **faults** like an ordinary `ld`/`sd` (it does not return `-FAULT` the way a
system op's checked buffer would, §9.1). This is the one place an endpoint-ish op faults rather than
returning a condition, and it is deliberate: the futex fast path *is* a memory access.

**`futex_requeue` 0x9b** `rd, addr_from(rs1), addr_to(rs2), expected(rs3), nwake(rs4), nrequeue(rs5)`
(all register operands, using the full six-slot format): atomically checks `*addr_from == expected`
(acquire — the compare closes the classic requeue race: a requeue against a word that changed underneath
returns `-BUSY` and moves **nobody**); if equal, wakes up to `nwake` waiters on `addr_from` and
**requeues up to `nrequeue` of the remainder onto `addr_to` without waking them**, returning `rd` =
woken + requeued (the condition-variable-broadcast primitive: wake one, requeue the rest onto the
mutex word). Same memory-type, fault, and
page-lifetime rules as `futex_wait`/`futex_wake`; a requeued waiter is re-keyed to `addr_to`'s (logical)
key, and its deadline and `-INTERRUPTED` behavior are unaffected by the move.

**The lock word is software's, entirely.** The machine
architects **no lock-word format**: futex ops key on `{backing identity, offset, size}` and the
compare value, and every bit of the word is the personality's own convention (owner fields,
waiter bits, robust marks — all software, all versionable by the runtime that owns them). Priority
inheritance in v1 is the serialized gate (§9.2). Any future priority-inheriting or robust-assisting
futex mechanism arrives **whole** — mechanism, word convention, identity resolution, teardown,
locality rule together — through the Appendix G futex-extension seam, never format-first. Fast
paths: lock = `amo.cas` `0 → self-marker` (uncontended, one instruction, the marker
software-chosen); contend = `amo.or` a waiter bit, then `futex_wait`; unlock = `amo.cas` back to
zero, falling to the wake path if the CAS fails.

**`pause` 0x98** (no operands): the spin-wait hint — an architectural NOP that tells the implementation
this thread is in a polling loop (a barrel core may deprioritize the context's issue slots for a few
cycles; a future SMT/OoO core saves power and pipeline slots). Spin loops should prefer
`futex_wait`/`wait` — parking costs ~30–100 cycles here — but bounded optimistic spins (seqlock readers,
the instant before a `casq` retry) are real, and `pause` is their polite form. The **canonical `nop`** is
the assembler alias `addi r0, r0, 0` with a zero hint zone — named here so codegen, live-patching, and
disassemblers agree on one encoding.

**There is no multi-word compare-and-swap.** A k-word CAS with honest distributed semantics
(reservations across as many as eight homes, distributed commit visibility, coordinator recovery,
eviction/`backing.rehome`/chiplet-loss interaction, and a WCET guarantee) is a recoverable distributed
transaction protocol in every conforming cache hierarchy. The base covers the stable language and
systems surface without it: native 16-byte `amo.casq`, strong single-word CAS, far-executed
`amo`s, futexes, serialized gates, and compare-only validation via version words/seqlocks.
Code whose correctness specifically depends on an LR/SC arbitrary-sequence eventual-success
guarantee requires a source-level algorithm port; it is not a recompile-only compatibility case.
Tagged `amo.cas`/`amo.casq` covers the common ABA-resistant forms, but the ISA makes no theorem for an
unbounded inline sequence between a load reservation and store conditional.
**`0x91` is reserved atomics-growth space**; a future totally-ordered
revision may assign it to a multi-word primitive after a prototype proves value on real workloads
(the space remains unassigned).

## 7. Control transfer

Jumps: `jmp` 0x60 (J), `jal` 0x61 (J, `rd = pc+8`), `jalr` 0x62 (I). `call sym` = `jal r1, sym`;
`ret` = `jalr r0, r1, 0`. Register-compare branches (no flags): `beq` 0x63, `bne` 0x64, `blt` 0x65,
`bge` 0x66, `bltu` 0x67, `bgeu` 0x68 (`bgt`/`ble`/`bgtu`/`bleu` are operand-swap assembler aliases). The
branch-free compare-select is `sel` (§4.1); PC-relative address formation is `auipc` (§4.3).

**Compare-immediate branches, `bci` 0x6c.** `bci rs1, imm12, off {cc}` — branch on `rs1`
compared against a **12-bit immediate**. Custom format under the §1 rules (`rd` slot
reserved-zero): `rs1[50:46]`, **`cc[45:42]`** (`0` eq, `1` ne, `2` lt, `3` ge, `4` ltu, `5` geu;
`6..15` reserved → illegal-instruction), **`imm12[41:30]`** sign-extended — **zero-extended for
the unsigned conditions `ltu`/`geu`** (declared, per the house rule that an unsigned form states
which operand the `u` qualifies), **`off[29:9]`** = `sext(imm21) << 3` (±8 MiB reach — ample for
intra-function branches; the full-range B-format branches remain for the rare far branch),
`[8:0]` the §12 hint zone exactly as in B-format. Assembler spellings `beqi`, `bnei`, `blti`,
`bgei`, `bltiu`, `bgeui`. Constant-compare branches are among the highest-frequency branch
shapes in compiled code; this form replaces the two-op `li`+`beq` lowering (16 bytes and a
scratch register). The condition field selects one closed comparison relation; it never changes
operand, authority, delivery, or completion semantics.

**Conditional trap, `trapcc` 0x6b.** Form:
`trapcc rs1, rs2, imm32 {cc}` with `rd` reserved-zero, `imm32[40:9]`, `cc[8:6]`, and
`[5:0]` reserved-zero. Defined conditions are `0 EQ`, `1 NE`, `2 LTU`, and `3 GEU`; `4..7` are
reserved. If the comparison is false, execution falls through with no architectural effect. If true,
the instruction raises exactly the architected-trap machine call defined below, with `imm32` delivered
in `r3`; it writes no register. `teqz rs, imm32` and `tnez rs, imm32` are assembler aliases using
`r0`; `tltu` and `tgeu` name the unsigned forms. Bounds checks use `tgeu index, length`, stack-limit
checks use the appropriate unsigned ordering, null checks use `teqz`, and checked arithmetic may
feed `ovadd`/`ovsub`'s overflow result to `tnez`. The condition field selects one comparison relation;
it never changes operand, authority, delivery, or completion semantics.

**Immediate-compare conditional trap, `trapcci` 0x6d.** `trapcci rs1, cmp_imm12, trap_imm25 {cc}`
— `trapcc` against a compile-time constant (the majority of UBSan/hardened-libc checks).
Encoding: `rd` slot reserved-zero,
`rs1[50:46]`, **`cmp_imm12[45:34]`** (the §1 narrowed below-slot immediate rule; sign-extended
for `EQ`/`NE`, **zero-extended for `LTU`/`GEU`**), **`trap_imm25[33:9]`** zero-extended (the
full 32-bit kind space needs `trapcc` — two immediates cannot both be full-width below `rs1`), **`cc[8:6]`** (`0` EQ, `1` NE,
`2` LTU, `3` GEU; `4..7` reserved — `trapcc`'s codes at `trapcc`'s home), `[5:0]` reserved-zero.
Semantics are `trapcc`'s exactly: false falls through; true raises
the architected-trap machine call with the kind in `r3`; no register is written.
`tgeui index, #len, kind` is the constant bounds check in one instruction; `teqi`/`tnei`/
`tltui` name the other forms.

**`trap` 0x01 `imm32`**: the architected trap. Raises the synchronous illegal-class fault — by Law 1, a
machine gate-call on the domain's FAULT gate (§9) with **cause = architected-trap and the `imm32` trap
kind delivered in `r3`**, so `__builtin_trap`, `llvm.ubsantrap`'s per-check codes,
assertion sinks, and JIT deopt shims each get a distinguishable, *frozen* encoding. `trap 0` is the
canonical breakpoint form: with §6 fetch-atomic patching, a debugger plants/removes breakpoints by
swapping one aligned word, no stop-the-world. (**Debug facilities are designed:** the capability-gated
**DebugTarget** object, §16.3 — forcible attach to a *running* process, context read/write, single-step,
watchpoints, and post-mortem register capture; mintable at any time by a DEBUG-right holder — no
birth flag revokes inspectability (Appendix H) — never a mode bit.)

**Targets.** Branch/jump offsets are **signed**: the byte offset is `sext(imm) << 3` and the target is
`pc + offset` computed modulo 2^64 relative to the branching instruction's own PC (no wrap fault).
Because instructions are 8 bytes and the offset is a multiple of 8, every direct target is naturally
instruction-aligned by construction. For the indirect `jalr`, a target `(rs1 + sext(imm))` with
**non-zero low 3 bits raises the fetch fault** — misalignment is *not* silently masked (fail-closed;
the psABI correspondingly declares that code pointers carry no low-bit tags). A target that is **non-canonical** (outside the implemented virtual-address range, reported by
`env_open`) or unmapped/non-executable raises a synchronous fetch fault (§9.1) at the target, as for any
fetch.

**Control-flow integrity.** The machine's protection unit is the **domain**; a
compromised domain is confined by capabilities, W^X, and epoch checks (§2, §3, §15), and
cannot escalate however thoroughly its own control flow is bent. *Within* a domain the story is layered,
not absent:
- **Return protection is the continuation stack** (§9, §17.5): a cross-boundary return lands **only on a
  hardware-pushed frame**, located through an engine-held token, never through an address read from
  writable memory — there is no return address to corrupt, and its integrity is a standing proof
  obligation. Ordinary intra-domain `ret` via `r1` remains the ABI form for plain calls; every gate
  and machine-call return is frame-bound.
- **Forward-edge marking is enforced in v1:** `lpad` 0x69 is the architected landing-pad marker
  (`imm32` is reserved-zero). `jalr.cfi` 0x6a has the ordinary `jalr rd, rs1, imm32` operand and
  link semantics, but before transfer requires the target instruction to be a well-formed `lpad`;
  otherwise it raises a synchronous fetch fault at the target and does not write the link register.
  Compilers use `jalr.cfi` for indirect calls and indirect tail calls to address-taken function
  entries. Plain `jalr` remains the return and intra-function computed-jump form, so returns and jump
  tables do not acquire landing pads. Executing an `lpad` sequentially or through a direct transfer
  falls through like a NOP, but its checked-target meaning is active and tested from v1—there is no
  enforcement policy bit and no decade of unchecked metadata.
- `jalr`'s fail-closed alignment rule above removes the cheapest pointer-corruption forgiveness.

## 8. PCRs and time (Law 4: one timebase; every other clock is a view)

**Time operand types and the unified comparator.** External time operands have distinct types; they
share comparator machinery, not sentinel encodings:

- **`AbsoluteDeadline`** is an absolute tick value: `0` = poll/immediate expiry,
  `UINT64_MAX` = forever, and `1..UINT64_MAX-1` are finite deadlines. Futex and `wait` deadlines and
  timebase-absolute Timer arms use this type.
- **`DurationBound`** is a relative tick count: `0` = unlimited/no added bound and every nonzero value
  is a duration. `max_donation` uses this type.
- **`GraceDuration`** is a relative tick count: `0` = no cooperative cleanup interval (force
  termination immediately after cancellation selection), otherwise the time allowed after forced
  delivery to complete cooperative cleanup and terminate the activation. `cleanup_grace` uses this type.
- **`RelativeDelay`** is a relative tick count: `0` = immediate and every nonzero value is a delay.
  Relative Timer arms use this type.
- **`TimeoutBound`** is a nonzero relative tick count; zero is invalid. Published
  `INVALIDATION_ACK_BOUND`/`ATS_ACK_BOUND` values use this type because a conformance bound cannot be
  unlimited.
- **`Period`** is a relative tick count whose zero meaning is defined by its operation: zero is invalid
  for `RESERVATION`, and means one-shot for Timer `ARM`.

On arm, each finite operand is overflow-checked and converted to **one internal object: an armed
comparator holding an absolute tick value against the one timebase**, firing its embedding's
consequence (a wake, a status, a machine call, a throttle). An unlimited duration or forever deadline
creates no finite comparator. The uniform comparator rules live here, and every per-mechanism statement
is a **corollary, never a second source**: **(i)** serialization samples every comparator at one
temporal cut and exports its remaining duration (§16.8). Transparent migration subtracts all elapsed
time after that cut before re-absolutization; only a stream explicitly marked `SUSPEND_TIME` preserves
the cut-time duration, and that named checkpoint policy—not `FREEZE`—pauses virtual elapsed time. The
embedding supplies the type, so its sentinel is preserved (`DurationBound` zero remains unlimited,
while an `AbsoluteDeadline` forever remains `UINT64_MAX`); **(ii)** **freeze never pauses a comparator** — a frozen holder's deadlines keep
ticking in architectural time (§9.4's deadline-vs-freeze pin and §16.3's debug rule are this one
sentence about this one object); **(iii)** a deadline fires **once, edge, per arm** — re-arming is
a new deadline, never a resurrection; **(iv)** slack is **opt-in and hint-class** — an arm may
carry a batching window (Timer `ARM`'s `slack_log2`, §17.7) licensing coalesced wakes inside it,
and an arm without one fires exactly: quantization is never imposed. And the silicon license,
**one hierarchical timeout wheel per volume lawfully serves every embedding** (Appendix E carries
the license). **The wake set is closed and engine-visible:** the only things that can require a
sleeping tile awake are its next-deadline comparator, fabric message ingress, a device interrupt
bound to it, and an inbound `POST` — all engine facts, so an idle tile may be gated to any depth
(Appendix E).

**Counter lifetime.** `TIME` never returns `UINT64_MAX`, which remains permanently reserved for the
`AbsoluteDeadline` forever sentinel. Finite addition is saturating only for validation: an arm whose
computed absolute value would reach `UINT64_MAX` fails `-OVERFLOW`. A conforming boot epoch must end
before `TIME` would advance past `UINT64_MAX-1`; the platform publishes a maximum continuous uptime
below that bound and must orderly restart before it. Deadline comparison is ordinary unsigned,
non-modular comparison—no wraparound or half-range convention exists.

`get_pcr` 0xb7 (`rd, pcr`) reads selector `pcr` into `rd`. `set_pcr` 0xb8 (`rd, pcr, rs`) writes the
value in the **`rs2` slot** to selector `pcr` and a status to `rd` (`0`/`-CONDITION`). **PCR subformat:**
the selector is a **5-bit literal in the `rs1`-slot bit field** (`[50:46]`) — neither a register value
nor the I-format immediate; the immediate field is unused/zero. This is the first of the two architected
register-encoding exceptions (§1): `set_pcr` must name both a selector and an `rs2` value, and an immediate would
collide with the `rs2` slot, so the selector rides the `rs1`-slot bits for **both** ops (one subformat,
not two). As everywhere, **source slots are read before `rd` is written**. **`set_pcr` carries no
capability operand, so it can only write state that is *self-authorized* for the current thread** (its
own `EVENTMASK`, `FCSR`; the thread pointer is the GPR `tp`, §2, not a PCR). Everything that needs an
authorizing capability is **not** settable here: identity changes through typed domain operations, and
**wall time changes through `clock.set`/`clock.adjust` on the ClockView capability**
(`get_pcr(VIEW_TIME)` just reads it). A
`set_pcr` to a read-only selector returns `-DENIED`; an undefined selector returns `-MALFORMED`
(`set_pcr` has an error channel). **`get_pcr` has no error channel** — it returns a raw `u64`, so it
cannot report a condition in-band (§1). A `get_pcr` of a **reserved/undefined selector**, or of a
selector the domain's **MachineView does not grant** (below), therefore raises an
**illegal-instruction / disabled-opcode synchronous fault** (§9), not a negative return.

### 8.1 The timebase and the views

**The timebase is the only architectural time.** One monotonic counter (`TIME`, selector 11), in
**ticks**, at a frequency stated in the domain's MachineView geometry (§16). The one refinement
the §8 deadline rule needs from this section: **a comparator arms against the domain's *visible*
timebase** — the same surface `TIME` reads through the MachineView (§8.3), so arming and waking
can never measure the view's offset. Timer `GETTIME` returns ticks, always. **Running-machine time
interfaces use ticks; nanoseconds appear only in the canonical inter-machine serialization format**
(§16.8/§17.9). Unit conversion is software's business at the personality edge, or the engine's at that
wire boundary.

**The relativity correction (Law 8 applied to Law 4).** The timebase is **per-volume**, kept in
bounded skew by a hardware sync protocol — and "one architectural timebase" is thereby **one
semantic scale, never one physical artifact**: no phase-locked chip-spanning clock tree, no
single globally written counter, and no distinguished wire is required or implied on a
meter-scale or multi-package machine — the sync protocol and the published skew bound *are* the
timebase. The protocol is required to be **idle-cheap**: the skew
bound holds across implementation sleep states, the sync rate may scale with drift rather than
with activity, and a gated volume may resynchronize **at wake, before its first time read**,
rather than continuously (deep sleep must never be the thing the clock forbids) — and the
architectural guarantee is **monotone within a
coherence volume, skew-bounded across volumes** — the bound is **`TIMEBASE_SKEW_BOUND`** (a
`GEOMETRY` field, in ticks, view-answered). **The cross-volume partial order is defined:**
cross-volume shared memory is unconstructible (§15), so the only cross-volume edges are engine
operations — `send`→`recv`, `gate_call`→activation, completion posting, state open→import/commit
— and the global event order is the **transitive closure of the per-volume total orders glued by
those engine edges** (happened-before). Two events unrelated by that closure have no architectural
order. This is the §6 `.cat` model's cross-volume semantics: its quantifiers range over a coherence
volume, and between volumes the only order is the engine-edge closure. Two consequences, pinned: **(i)** cross-volume deadline
comparison is meaningless, so a time-valued thing crossing volumes re-resolves through the
destination's timebase — which is exactly the state stream's cut-time remaining-duration, elapsed-subtract,
and re-absolutization
(§16.8), now doing double duty, and within a machine every deadline is armed and fired in the
arming domain's own volume (a domain occupies one connected region, Law 8, so its deadlines never
straddle). **(ii)** `TIME`'s monotonicity guarantee is per-volume. A `tick_quantum_shift` (§8.3) coarser than
the skew bound makes the skew unobservable, so the hardened-time knob and the physics knob are the
same knob.

**Wall time is a ClockView object** (§16.3): an affine transform `{offset, slew}` over the timebase,
held per domain subtree, writable only through the view's capability (`clock.set`/`clock.adjust`). Every
domain is born bound to a default ClockView (one of its five views, §16). A ClockView carries a
shared epoch cell while timers reference it (§3); **stepping** the clock bumps it, and anything armed *against the view* (an
absolute wall-clock timer) holds `{view, epoch}` and re-resolves through the new transform on the bump —
Law 2 applied to time; no bespoke re-derivation rule. Relative and timebase-absolute arms are converted
to ticks at ARM and never reference a view. **`VIEW_TIME`** (selector 5) reads the domain's bound
default view applied to the timebase: one atomic u64, untorn, monotonic within a view epoch. Its
interpretation (epoch origin, unit scaling) is the view's metadata, readable by fixed ClockView getters
object — the ISA guarantees the read's atomicity and per-epoch monotonicity, and does not name its unit.

**The ClockView invariants, gathered in one place:** **(i)** the *monotonic* surface (`TIME`, timebase-absolute
deadlines) is untouched by any view operation — wall-clock correction can never move monotonic
time or corrupt a monotonic timer, because they never pass through the transform; **(ii)** a
timer binds to a *specific* ClockView, never to ambient time — view-absolute arms hold
`{view, epoch}` and heal by re-resolution on a step (forward step past the deadline fires,
backward defers — §17.7's frozen rule), while relative/timebase arms converted at `ARM` are
*definitionally* unaffected by every view operation; **(iii)** `ADJUST` (slew) is the smooth
form and `SET` (step) is the epoch-bumping form — the effect of each on already-armed timers is
frozen per arm kind, never implementation choice; **(iv)** ClockViews do **not** recursively compose:
each effective view is a flattened Q32 transform directly against its domain's constructed-volume
timebase, authorized and installed by the parent under §16.7; **(v)**
migration snapshots the view *and* its armed deadlines consistently (§16.8: the view travels as
a view; view-absolute timers heal through the same epoch mechanism at the destination).

**Slew arithmetic and monotonicity (normative).** A ClockView stores an anchor
`{anchor_tick T0, anchor_view V0}` and a signed Q32 correction `s`, with
`-2^31 <= s <= 2^31`. For `t >= T0`, its value is
`V(t) = V0 + floor((t - T0) × (2^32 + s) / 2^32)`. The underlying affine derivative is therefore
strictly positive (`1/2` through `3/2` view units per tick); integer reads are nondecreasing, with the
floor operation exactly as written. The engine evaluates the subtract, multiply, and add in exact
signed 128-bit intermediate arithmetic. `SET` or `ADJUST` is rejected `-OVERFLOW` if the transform
would leave `u64` over the platform's published remaining boot-epoch horizon (§8 counter lifetime), so
runtime evaluation never wraps, saturates, or becomes modular.

`ADJUST` is continuous: atomically at tick `tn`, the engine evaluates the old transform once, installs
that value as the new `V0`, installs `tn` as the new `T0`, and then changes `s`; it does **not** bump the
ClockView epoch. Consequently the first value under the new slew is never less than the last value under
the old slew. `clock.set` deliberately chooses a new `V0`, sets `T0 = now`, and bumps the epoch. Fixed getters
returns the anchor and Q32 correction, so software and serialization reproduce exactly the same
rounding. Values outside the slew bound are `-MALFORMED`; overflow leaves the old transform unchanged.

The ClockView family uses these fixed register forms:

```text
clock.new     rd_clock, initial_view
clock.set     rd, clock, new_view
clock.adjust  rd, clock, signed_q32_slew
clock.get     rd, clock, selector
```

`clock.new` anchors `initial_view` at the operation's commit tick with zero slew and epoch 1.
`clock.set` and `clock.adjust` return zero or a negative condition. `clock.get` selectors are
`0 ANCHOR_TICK`, `1 ANCHOR_VIEW`, `2 SLEW_Q32` (the signed two's-complement bit pattern), and
`3 EPOCH`; `4..255` are reserved. The getter is a definition-fixed scalar read and therefore
uses no output record. `clock.new` requires `CREATE`, mutations require `CONTROL`, and getters
require `INSPECT`.

### 8.2 The selector matrix

| Sel | PCR | get | `set_pcr` | how it changes |
|---|---|---|---|---|
| 0/1/2 | DOMAIN_ID / BIRTH_PARENT_ID / THREAD_ID | yes | **no** | assigned at `dseal`/`dstart`. **Law-7 naming rule:** these are *subtree-scoped labels chosen at birth by the creating parent*, never machine-global counters (a global counter is a depth-and-load oracle). `BIRTH_PARENT_ID` is an immutable opaque label, not a query of the live hierarchy edge; it may legitimately read `0` — "no birth parent is named in your universe" — and `REPARENT` never changes it |
| 3 | EVENTMASK (machine-call event mask, events 0–63) | yes | **yes** (self) | current thread, atomic vs delivery (§9) |
| 4 | EVENTPENDING | yes | **no** | engine / delivery |
| 5 | VIEW_TIME (the domain's default ClockView applied to the timebase — **one** atomic u64, so there is **no torn `sec`/`nsec` pair** and no seqlock) | yes | **no** | `clock.set`/`clock.adjust` on the ClockView capability |
| 6/7 | CRED_PROFILE / CRED_HANDLE (opaque credential words; the personality defines their meaning) | yes | **no** | typed credential operation + credential capability |
| 8 | FCSR | yes (FP) | **yes** (self, FP) | current thread; `[7:5]`=`frm`, `[4:0]`=`fflags` (§14) |
| 9/10/11 | CYCLE / INSTRET / TIME | per MachineView | **no** | free-running counters, read **through the MachineView** (§8.3) |

Selectors 12–30 are reserved. **Selector 31 is reserved by name as `PCR_EXTENDED_PAGE`
(Appendix G):** the fixed-form escape to a second selector space — `get_pcr rd, 31` with an
extended selector in a designated operand — held so per-thread machine words can grow without
either burning the ordinary selector bank or sprouting a generic CSR namespace: the bank stays
small and disciplined, and growth is one named page with the same literal-selector decode shape.
Nothing may cite it until a revision assigns extended selectors. Rejected concepts such as a PCR thread pointer, OS-noun credential
selectors, split-word wall time, and an inert PI-futex identity consume no selector values; their
rationale remains recorded in Appendix B rather than frozen into the ABI. **Configurable PMU**
(event selection, overflow-threshold-to-waitable) is
`pmu.event` on a **PMU capability**, not a `get_pcr` (so PMU event selection is capability-gated). A
**`BRANCH_RECORD` PMU profile is reserved by name** (LBR/BRBE-class last-branch records,
capability-gated, data-path-only like all trace): the §12 hint zones assume PGO, and the modern PGO
pipeline is AutoFDO/BOLT over hardware branch records — naming the profile now keeps the hint story
end-to-end even though its record format lands with the PMU design.

**Software-visible identity theorem.** Every architected integer used as an identity and capable of
surviving in software memory is either **generation-qualified in the value software carries** or is
**never reused within its containing namespace incarnation**. A bare-identity allocator is monotonic
and saturating over its declared range; exhaustion returns `-EXHAUSTED` rather than recycling a
tombstoned number. Reclaiming an implementation directory entry never licenses numeric reuse.
This rule applies at least to `DOMAIN_ID` in its domain namespace, `THREAD_ID` in its domain,
waitset member IDs in their waitset, backing-local `faulting_domain` cookies in their backing,
memory-incident IDs in their reporting-domain incarnation, and every bare service-object or
service/submission correlation ID in its owning binding or queue. Capability handles, `ActivityRef`s,
and submission handles whose architected value already embeds a generation satisfy the other branch
of the theorem: reuse is permitted only with a different carried generation. Caller-chosen opaque
payloads that the engine merely echoes are not engine identities.

Every gate activation, including a recycled activation-stack slot, receives a fresh never-before-used
callee-domain `THREAD_ID`. Serialization preserves each identity allocator's high-water and any state
needed to preserve its incarnation; `REPARENT` moves the subtree's allocator state unchanged. Counts,
sizes, offsets, timestamps, queue positions, and cursors that denote traversal state rather than an
object identity are not identities under this rule; cursors instead obey their specified
mutation-generation or `-STALE` contract. Thus an old integer retained in memory can never silently
name a later object.

### 8.3 Time and counter visibility is a view, not a policy patch (Law 7)

What a domain can observe of the machine's real counters is a property of its **MachineView** (§16) —
the same view that scopes its topology and features — not a per-surface gate. One mechanism, three
manifestations dictated by each channel's physics:

- **`TIME` (selector 11) always reads, through the view**: the MachineView defines the domain's *visible
  timebase* — an offset (so a migrated or restored domain's monotonic clock is seamless, §16
  SERIALIZE) and an optional **coarsening**: `tick_quantum_shift`, rounding every read down to
  `2^shift` ticks (shift `0` = explicit no-coarsening; a hardened parent picks a shift that lands near
  microsecond granularity — the browser-timer-coarsening mitigation, done at the source). The quantum
  covers **every architected time read** — `VIEW_TIME`, Timer `GETTIME`/`remaining`, any time-valued
  value returned by a fixed timer getter — because a countdown is a clock running backward.
  **Monotonicity across a change:** the view's visible-timebase fields are settable **only at domain
  creation or under a covering quiescence hold** (§16.5), but quiescence alone is not continuity:
  software may retain its last read in memory. Let `F` be the source-volume tick at quiescence and `T`
  the destination-volume tick at resume. The engine chooses the new offset and quantization phase so the first
  possible post-resume value is at least the old transform evaluated at `F`:
  `new_visible(T) >= old_visible(F)`, after both sides' specified round-down. This lower bound dominates
  every value observable before freeze without storing a last-read register. The same rule applies to
  offset or `tick_quantum_shift` changes and import/migration between time volumes (`domain.place`
  cannot cross the constructed volume, §15). Armed
  deadlines are re-expressed by remaining duration at the cut, so continuity neither fires them early
  nor grants extra elapsed time.
- **`CYCLE`/`INSTRET` (selectors 9/10) are grantable-or-absent**: they are PMU-adjacent pipeline truth
  with no honest "coarse" form, so a MachineView either grants them (they read raw) or does not (reading
  **faults** — `get_pcr` has no error channel, §1, so the ungranted read is a disabled-opcode fault, the
  fail-closed direction). Most child views should simply not grant them.
- **`env_open` reads the view, definitionally** (§16): there is no gated-`TOPOLOGY` special case and no
  `-DENIED` path for machine description, because `env_open` never reads the machine — it reads the
  domain's MachineView, and always succeeds. The *policy* lives in exactly
  one object, the view; only the failure channel differs, and only where physics forces it.

**Honest scope — do not read coarsening as defeating timing attacks** (load-bearing, carried verbatim in
substance): it removes the *ambient* fine clock; it does **not** defeat a domain that can *build* one — a
sibling thread incrementing a shared word is a ~cycle-resolution clock (the SharedArrayBuffer lesson),
and deadline-wake edges (`futex_wait`/`wait` returning at tick-specified deadlines, deliberately **not**
quantized — that would break the realtime contract) are a second, noisier reconstruction channel. Those
instruments are removable only by scheduling/placement policy (the noninterference track,
`formal_theorems.md` §37), not by any PCR rule. Within that scope, time **coarsens, never disappears** —
hardened *driver* domains work with no special grants: `udelay`-class bounded spins poll the coarsened
timebase (microsecond granularity is exactly that contract), and Timer objects cover longer waits. Timing
authority is thereby **graduated, not binary**: full counters, coarse time, or anything between, per
domain, by view.

## 9. Gates (Law 1: the only control transfer across a boundary)

Control crosses a protection boundary **only through a gate — in both directions, including from
silicon**. There is no second delivery mechanism: a service call is a gate call from a domain; **a fault
is the machine calling you**; an asynchronous event is a machine call that matures at an instruction
boundary; a cancellation is a machine call from the engine. One continuation stack, **one frame kind**,
one return op, and one editing rule cover all of it:

> **The editing rule.** A callee never edits its caller's resume state. A machine call passes the
> interrupted context *as its argument* — and editing your argument is editing yourself.

That rule is why there are no frame tags: a domain-call
frame keeps the caller's resume point engine-private (the callee is not the caller); a machine-call frame
puts the resume state in the argument payload (the "callee" *is* the interrupted party). Both are
instances of one contract, and `gate_return` has one meaning — *my reply is this descriptor; descriptor
`0` means my reply is my register/argument state*.

**The continuation frame (one kind; an optional payload).** Every gate crossing pushes an opaque
engine frame (§17.5). A **domain call's saved callee-saved registers and resume PC live entirely in
that engine-private frame**: the callee cannot inspect or edit them, they pin no domain memory, and
only their canonical engine-state representation is serialized. A **machine call additionally pushes
an addressable argument payload** in ordinary domain-private memory containing the interrupted full
context. The handler may inspect and edit that payload because it is editing its own interrupted state
(the editing rule above). Conflating the optional payload with the engine frame is the confused-deputy
risk.

The engine frame's **control metadata** — the caller linkage (which domain called, or the machine), the link
  to the previous frame, `call_rd`, the call-chain ID, the donated reservation, the deadline, the gate
  linkage, and return-cap bookkeeping (including the actually reserved caller slots and charges) — lives in **engine-private state with no domain-addressable
  mapping at all**, located through an engine-held token. A domain store cannot reach or forge it; a
  forged frame cannot reroute a `gate_return` or steal a donated reservation. The engine and the domain
  never race on it: the engine only pushes/pops at delivery/return, when the thread is not executing.

"Protected" thus means: **(a)** the engine frame is unreachable by every domain, while a machine-call
payload is reachable only by its owning domain; **(b)** the engine
bounds-checks pushes against a registered limit, so overflow is a clean domain-fatal event, never silent
corruption; **(c)** only a machine-call payload is editable, never domain-call saved state or control
metadata.

### 9.1 Fault vs. error (the boundary)

One rule across the whole ISA: **system/endpoint argument errors are condition returns in `rd`;
architectural execution faults deliver machine calls.**

- **Condition return (no fault), from §10/§11 ops:** a bad, stale, revoked, or wrong-type capability
  (`-BADREF`/`-STALE`), insufficient rights (`-DENIED`), a malformed or oversized descriptor/sequence
  (`-MALFORMED`/`-OVERFLOW`), an unsupported profile/sub-op (`-UNSUPPORTED`), would-block
  (`-WOULDBLOCK`), or a bad buffer pointer discovered during the op's checked copy (`-FAULT`). These ops
  validate their arguments as part of their contract and never crash the caller on argument error.
- **Machine call (§9.3):** a **direct** `ld`/`sd`/instruction-fetch to an unmapped address or in
  violation of its mapping's protection, illegal-instruction /
  disabled-opcode, and the architected `trap` (§7). Synchronous, delivered precisely at the offending
  instruction.

So `read` on a bad endpoint cap returns `-BADREF`; `mmap` without rights returns `-DENIED`; a bad
descriptor *pointer* dereferenced directly faults, but a descriptor passed to an engine op that fails its
checked read returns `-FAULT`. (The one declared carve-out is the futex word, §6: the fast path *is* a
memory access, so it faults.) A personality layer builds its error-number semantics on the first bucket
(§13).

### 9.2 Domain-initiated calls (`gate_call` / `gate_return`)

| Op | Mnemonic | Form | Role |
|---|---|---|---|
| 0xa0 | `gate_call` | `rd, gate_cap, gatedesc` (the 48 B gate descriptor, §17.1b) | **synchronous** cross-domain call; args in registers + an optional **bounded inline payload** + a **cap list** + up to **two call-scoped borrow windows** (§17.1c — the `f(const in, out)` signature); reply is **two registers**: value in `rd`, gate-level status in `r3` (§1 two-result form) |
| 0xa1 | `gate_return` | `rd, gatedesc` (§17.1b) | return through the top continuation frame; descriptor `0` = registers-only / edited-argument reply |
| 0xb0 | `gate_tail` | `rd, gate_cap` (registers-only; no descriptor form) | **protected tail call**: replaces the current cross-domain activation with an activation on `gate_cap` under the *same* continuation — the eventual `gate_return` resumes the original caller directly |

**Activation ABI (function-call cost, zero data copy).** The migrating gate is "roughly a function call
plus a capability check": arguments ride **registers**, capabilities cross by **re-keying a table entry**
(no data copy), and **bulk payloads travel as a passed memory capability** the callee maps (zero-copy /
COW) — there is **no message marshaling copy** on the gate path (byte-copy messaging is
`send`/`recv`, §10.2, a different verb). A volume-local gate crossing is roughly a function call
plus a capability check; a gate crossing volume distance prices that distance by Appendix C.

**One gate, and it is fast (the warm-path contract).** There is no fast-gate class, no latency
operand, and no mode field: every gate has these semantics, and the latency promise attaches to
**residency** — a §16.4 resident-capacity fact — never to a gate subtype. The normative
requirements, binding every conforming implementation:
- **Bounded, VLEN-independent context transitions.** Activation entry and return perform **no
  work proportional to VLEN, nesting depth, or machine size**, and the whole crossing fits the
  machine's own published `GATE_WARM_RTT` under the measured-path preconditions below. Frame
  capture, both zeroing edges, and restore **may** be realized by rename-map, ownership-tag,
  bank, or generation techniques (the Appendix E scrub and gate-context licenses) — that is
  what makes a very small published bound *legal* — and a simple core that walks its fixed
  32-entry integer file conforms by publishing the larger honest bound that walk costs. The
  conformance line is the published number and VLEN-independence, never a construction; the
  §17.5 frame is materialized only under external observation (debug, unwind, `state.open`).
- **Same-agent transfer.** The synchronous volume-local `gate_call` converts the calling
  hardware thread into the callee activation **in place** — no scheduler queue, no worker
  selection, no core migration, no interprocessor interrupt. A crossing that cannot complete on
  the current agent is the separately priced distance/cold path of Appendix C, taken visibly —
  **never a silent substitution inside the warm bound**.
- **Not a fence.** The null-descriptor scalar call is a control transfer: it drains no store
  buffer and orders nothing beyond §6's annotations and the defined capability/borrow
  publication points. Programs wanting stronger ordering ask for it with the §6 primitives.
- **No dynamic allocation on the warm path.** Activation slots come from the sealed gate's
  preconfigured pool; chain-ID propagation and (on serialized gates) donation arming fit within
  the published bound.
- **No structure-proportional crossing work.** The §2.1 no-residue clause is satisfied by
  domain-tag partition of predictors and caches, never by flush — entry and return require no
  work proportional to predictor, cache, TLB, or pipeline structure size. One named carve-out:
  a domain running the **hardened noninterference profile** (§2.1) buys its occupancy-channel
  closure with scrub/partition knobs and thereby forfeits the warm bound — that trade is the
  domain's, made at configuration, never discovered in production.

**The measured warm path (what the published number means).** `GATE_WARM_RTT` is a published
MachineView `GEOMETRY` fact — a per-machine truth, deliberately never an architectural
constant — defined as the round-trip bound **in architectural ticks (Law 4 — the one timing
currency; an implementation may additionally publish a reference-frequency cycle equivalent as
non-normative documentation, because a cycle floats with DVFS and a tick does not)** from
`gate_call` issue to the first resumed caller instruction, excluding deliberate callee work,
when **all** of: caller and target share
one coherence volume; execution stays on the current hardware agent; the gate's resolution,
target metadata, entry translation, and an activation slot are **resident**; `gatedesc = 0`;
declared ABI class `GPR`; the callee immediately executes `gate_return 0`; no serialized-gate
contention; no machine call, cancellation, fault, or park. Descriptors, persistent capability
transfer, borrows, wider ABI classes, fabric distance, residency misses, and blocking are the
separately priced Appendix C paths — outside the number by definition, never averaged into it.
Appendix D carries the benchmark family bound to exactly this precondition list. **Residency is
the §16.4 doctrine applied to gates:** exhaustion demotes a call to the cold path (evict,
reload, park — published cost), never fails it, never changes semantics; and **real-time
admission records gate-residency leases** the way §15 records pin leases, so a
deadline-conforming path holds the warm bound as a ledger-covered fact rather than a likelihood.
**The warm path's expressive power** is scalars and the two declared borrow windows (§17.1c);
each declared install is priced as an Appendix C increment over the empty call. Persistent
capability transfers, inline bytes, and reply capacities use the descriptor path.
**Stated limitation (the `GATE_CAPARGS` seam, Appendix G):** *activation-scoped* capability
references — handles that die with the activation — remain undesigned (the §2.2 handle format
admits no second namespace); nothing may paper over that with descriptor-path calls quietly
counted as warm.

**Domain-mint warm facts.** `SPAWN_WARM_RTT` bounds both publication shapes: the empty-floor
`dnew`-through-`dseal` sequence to its returned dormant Domain, and the common fused `dspawn` from
issue to the child's first instruction. The common case inherits MachineView and ClockView, uses
the shared compartment address-space shape, receives at
most 16 grants, and requests no reservation admission, measurement, or prepared binding.
`DESTROY_WARM` is the bound from `dkill` issue through its class-1 return; asynchronous corpse
reclamation is excluded and remains corpse-charged. The empty `dnew`/`dseal`/`dkill` case is the
floor measurement; the inherited-view compartment is the common measurement. Both facts are
implementation-local promises, not cross-machine performance constants, and neither permits work
proportional to domain-tree depth or machine size.

**The gate's declared `abi` class (§17.7 `gate.abi`) is the sanitization scope.** A `GPR`-class
gate's crossing sanitizes GPRs; FP, vector, and mask state is then **foreign state for the
activation** — not part of the crossing — and any touch of foreign state during the activation is
an **authority-class event resolved before speculation** (the §2 speculation contract's first
clause applied to the register file) that resolves as a **fault, never a class escalation.** A
`GPR`-class activation executing an FP or vector instruction takes the ordinary synchronous
unauthorized-class fault **before any operand is read** (precise, no partial effects); a callee
that needs FP declares `GPR_FPR` with `gate.abi`, where the wider crossing is priced, and
reconfiguration is administrative, epoch-bumped, never mid-activation. **The `abi`-class set is
closed and enumerated** (catalog `enums.callgate_abi`): `0` `GPR`, `1` `GPR_FPR`,
`2` `GPR_FPR_VECTOR` — three classes, no fourth. **Vector registers are in no class's crossing
state**: `GPR_FPR_VECTOR` only *permits* vector execution during the activation; vector and mask
state is always scrubbed at both edges regardless of class (§18). **The `gpr-only` compilation
contract:** a function reachable from a `GPR`-class gate entry must be compiled emitting no FP
or vector instruction, **including implicit uses** (`memcpy` expansion, spill classes,
`long double` softening per the psABI's soft-FP variant); the toolchain marks each conforming
function (`object_format.md`) and diagnoses violations at link time. Absent whole-program
`gpr-only` compilation, declare `GPR_FPR`. *Within* the declared class,
eager versus lazy state handling is the implementation's choice. What is architectural: **(i)** no
residue in any state the activation can observe — *speculatively included*, so the LazyFP-style
leak is pre-refused — **in both directions** (the callee observes no caller foreign-class state,
the caller observes no callee residue after return); **(ii)** the **crossing's**
visibility-and-sanitization cost scales with the **declared** class, never with the machine's full
register file. The
caller's live foreign-class state still exists and is still the caller's: preservation under
preemption, eviction, migration, or serialization scales with the caller's *live* state (§17.5's
payload, §16.8), and no gate declaration changes that. Predictor state is covered by the §2
no-residue clause (satisfied by predictor partition by domain tag). Step by step:

1. **Preserve the caller cheaply.** The engine pushes a frame (§17.5) saving **only the caller's
   callee-saved registers** (`s0`–`s9`, `sp`, `tp`, FP callee-saved if active) + resume PC + `call_rd`
   (the caller's reply-**value** register number, so the callee's `gate_return` cannot choose which caller register
   is overwritten; the gate-level **status** always lands in the fixed `r3`, callee-uncontrollable). Control metadata goes to the engine-private region (§9 above). Caller-saved registers
   follow normal ABI; they are **not** dumped to the frame — this is function-call cost, not a
   full-context save.
2. **Pass arguments: registers, a small bounded inline payload, or a memory capability (three tiers, no
   marshaling tax).** Seven scalar args are caller `r2`–`r8`, shifted to callee `r3`–`r9`; caller
   r9 is reserved-zero for this Gate-interface version. Capabilities cross via the
   descriptor's **cap list**, re-keyed into the callee's table. **These are ordinary persistent
   capability transfers:** once activation commits, the installed entries outlive the activation and
   are not revoked by return or cancellation. Descriptor transfers copy; an ownership transfer is the
   explicit `cap.move` operation and consumes the sender slot exactly once.
   Activation-scoped authority is a different mechanism—the borrow window below—and is never inferred
   from membership in the cap list. For data beyond the registers:
   - **Small inline payload.** `gate_call` may carry a bounded inline byte payload
     (`bytes_ptr`/`bytes_len` in the descriptor) up to `GATE_INLINE_MAX` (an `env_open` `GEOMETRY` bound,
     at least **256 bytes**). The engine copies it **once**, as part of the activation, into a fixed
     inline area at the callee's entry (named by the `ActivationContext.inline_ptr` field below).
     A single bounded copy,
     WCET-accounted — a 120-byte path string, a small struct, a short request rides here directly from
     the caller's stack with no object dance. `bytes_len` above the bound returns **`-MSGSIZE`**.
   - **Zero-copy bulk.** Pass a **memory capability** naming the buffer; the callee maps it (COW /
     shared), no byte copy. Such a cap over an arbitrary sub-range you already hold is minted **O(1)** by
     `mem_grant` (§11) — no allocation, no copy.
   - **Call-scoped borrow (§17.1c).** The descriptor may lend **up to two caller ranges to the
     callee for exactly this activation** — canonically a read-only input and a writable
     output, the `f(const in, out)` signature every decoder, decompressor, and parser has — no
     table mutation, revoked automatically when the activation ends (step 5 of
     §9.4). Delegating sub-ranges of your own authority for the duration of your own call requires no
     opt-in anywhere: it is strictly milder than the cap transfer the gate already permits.
   - **Register-described borrow (`gate.borrow_arg`, §17.7).** A gate may declare at
     construction — immutably, as gate-ABI facts, never runtime flags — that the
     **null-descriptor** call lends ranges named by designated argument-register pairs
     (pointer, length) at declared rights: the same §17.1c windows, installed from registers,
     an operand adapter over the one canonical overlay (§16.2, hot path:
     `service(in_ptr, in_len, out_ptr, out_cap, scalars…)` with no request structure read).
     `gate.borrow_arg` is repeatable **at most twice** (window 0 then window 1; a third
     declaration is `-MALFORMED`), matching the descriptor form's closed count. Same
     lifetime, same teardown, same non-capability nature; each window's O(1) install is priced
     as one Appendix C increment over the empty call.
   The caller's pointers are never dereferenced by the callee. Returned values come back in registers
   (step 4) plus, if the ABI declares one, the same inline area for a bounded reply; the gate's
   `gate.limits` sets the inline area size (§17.7).
3. **Activate the callee.** Enter the gate object's declared **entry PC**, with `sp` = a fresh
   **activation stack** carved from the gate's stack pool (declared by `gate.stack`, §17.7). The
   first 128 bytes of every slot are the activation-context area and are excluded from the usable
   stack; `sp` begins at the slot's aligned high address. Each pool slot carries an engine-minted
   callee-domain activation `THREAD_ID`; ephemeral entries have no
   initialized language TLS and begin with `tp = 0`, while a bound worker retains its persistent
   thread's initialized `tp`. `sp` is the
   **16-byte-aligned** high address — 16 bytes is **the universal alignment at every
   hardware-constructed entry** (gate activation here, machine-call delivery §9.3, domain birth
   §16.1.3). Concurrent and detached ephemeral activations have distinct activation identities but
   no language TLS until software initializes `tp`; a served activation retains its worker's TLS.
   The stack slot may be recycled, but its numeric activation
   `THREAD_ID` is retired forever under §8.2 and a fresh ID is minted for the next use. The caller's
   saved `tp`/identity is restored on successful return. `r2` holds a pointer to the activation
   context and `r3`–`r9` hold the seven user argument words supplied in caller `r2`–`r8`; caller
   `r9` is reserved-zero at the crossing.
   **Every other register
   in the gate's declared `abi` class zeroed** (no caller-saved contents leak to the untrusted
   callee; state outside the class is *foreign* to the activation and never observable — the
   sanitization-scope bound above). **`r10`--`r13` are zero on every gate entry**; metadata is
   memory, never a second register dialect. Before the first callee instruction the engine writes
   a frozen 128-byte `ActivationContext` into that slot's pinned context prefix and
   places its callee address in r2: `[0] version u32; [4] kind u32` (`0 CALL`,
   `1 TAIL`, `2 SUBMIT`); `[8] inline_ptr u64; [16] inline_len u64;
   [24] reply_inline_cap u64; [32] caps_base_slot u32; [36] caps_count u32;
   [40] window0 {base u64,len u64,rights u64}; [64] window1` in the same shape;
   `[88] activity_ref u64; [96] caller_cookie u64; [104] abi_class u32;
   [108] flags u32` (bit0 `SERVICE_OBJECT`, bit1 `PREPARED_BINDING`; bits `[31:2]`
   reserved-zero), `[112] service_class u64; [120] dispatch_cookie u64`.
   `SERVICE_OBJECT` supplies its class and object cookie. `PREPARED_BINDING` supplies
   `service_class=0` and the committed opaque prepare token as `dispatch_cookie`; the two flags are
   mutually exclusive. The last two fields are zero when neither flag is set. All-zero windows are absent.
   `caller_cookie` is a gate-local opaque stable value for `{gate,calling Domain}` and never a
   foreign machine name. The context is logically read-only, nonoverlapping with stack and TLS,
   and expires with return or cancellation; the engine never reads it back.
   Borrow-window addresses remain ordinary scalar arguments in `r3`--`r9`.
   **The one register that is not zeroed is `r1` (`ra`):
   the engine installs the architectural return sentinel there** (below), so the handler is an
   **ordinary function** — context in r2, arguments in `r3`–`r9`, reply left in r2, ending in
   an ordinary `ret`. No epilogue rewriting, no veneer, no reply-register handshake. **`gate_call`
   architecturally *defines* `r1` (`ra`)** — the sentinel write is a register def in the
   instruction's written-register set, exactly as `jal` defines its link register — so a backend
   derives the clobber mechanically from the instruction's effects, never from a hand-maintained
   inline-asm clobber list (the psABI §5 RA hazard is thereby unrepresentable in compiled code,
   not merely discouraged). On return the engine copies callee r2 to the caller-selected `call_rd`
   and writes status to caller r3. `gate.entry`, `gate.abi`, `gate.stack`, and `gate.limits`
   declare those independent facts before `gate.seal`: the concurrency model is a
   **bounded activation-stack pool** (`-BUSY` when
   exhausted) or a **single serialized activation**. **`-BUSY` is a genuine-exhaustion
   semantic, never a pipeline artifact:** a `gate_call`/`gate.submit`/spawn must succeed whenever
   a pool slot actually exists, so an implementation may not return `-BUSY` on a transiently
   stale free-slot count (a spawn immediately after a state change that freed or created a slot
   must see it). A caller must never need a retry dance to work around microarchitectural
   staleness; `-BUSY` means the pool is truly full. **Self-deadlock on a serialized gate is detected,
   not waited out:** a `gate_call` whose own `call_chain_id` already holds the target serialized gate
   (direct re-entry, or a cycle A→B→A at any depth *within one chain*) fails immediately with
   **`-DEADCYCLE`**. **The detection is scoped to exactly that: single-chain cycles.** Two *independent*
   chains cross-blocked on two serialized gates share no chain ID and are **deliberately not detected** —
   general deadlock detection is a graph search the engine does not do; their backstop is each caller's
   donation deadline (§9.4), the architected bound on that unserviceable wait **when the caller
   contributes a finite deadline or the gate supplies a nonzero `max_donation`**. With neither,
   the caller explicitly accepts an unbounded wait. **Do not read
   `-DEADCYCLE` as a general deadlock guarantee.** Both `-DEADCYCLE` and `-BUSY` are
   **pre-activation** failures: no callee ran, no register scrub, the caller's state untouched.
   **Every pre-activation refusal reports the same way** — `-BUSY` (pool full), `-DEADCYCLE`,
   `-NOSPACE`, `-MALFORMED` (including a bad descriptor or misaligned entry): the condition lands
   in the status register `r3` and the value register is unchanged, exactly as for the
   pre-activation cancellation below. There is no refusal that reports nothing; a full
   continuation stack is `-BUSY` in `r3`, not a silent non-event.
   The configured pool is persistent engine-written memory: configuration pins and charges the whole
   range for the gate's configured lifetime. Any overlapping unmap, protection change, backing
   transition, or image replacement fails `-BUSY`; reconfiguration or gate death releases the pin only
   after all activation slots quiesce. A gate activation therefore never faults into pageable service
   code while acquiring or updating its substrate stack.
4. **Return.** `gate_return rd, gatedesc` re-keys any returned caps directly into caller slots
   **reserved at call commit** (plus an optional bounded inline reply into its pinned buffer), frees the activation, pops the frame,
   restores the caller's callee-saved registers, and resumes. **`gate_return` with an empty
   continuation stack — no frame to return through — is a synchronous illegal-class fault
   (§9.1), never a fall-through into the following bytes.** A green result may not be obtained by
   omission for control flow any more than for a value: a bare or stray `gate_return` faults
   loudly rather than executing whatever follows it.

   **The return sentinel (a gate crossing is a call to both sides).** At activation the engine
   installs a reserved **return sentinel** address in `ra` (r1). A `jalr r0, rs, 0` whose
   computed target is the sentinel executes **`gate_return 0`**, taking the registers-only reply
   value from `r2` and returning status zero to the caller. Thus an ordinary `ret`
   (`jalr r0, r1, 0`) at the end of a plain C function *is* the crossing return. Any other
   non-canonical computed target takes the ordinary precise fetch fault.
   Three properties make this safe rather than merely convenient:
   - **The sentinel is a trigger, not a target.** `gate_return` still resolves the caller frame
     through the engine-held current-frame token (§17.5), never from `ra`. A handler that
     overwrites `ra` can only run more of its own code or trigger the legitimate return; it can
     never redirect it. Unforgeable control is untouched.
   - **The sentinel is one architecturally pinned value: `0xFFFF_FFFF_FFFF_FFF8`** — a reserved
     non-canonical address (Appendix B 25: provably outside the legal code-address set on every
     machine, since no implemented VA range reaches the top of the 64-bit space; 8-byte aligned
     so it never first trips the fetch-misalignment fault), recognized on the fetch path ahead of
     the ordinary non-canonical fetch fault. It is pinned, not implementation-chosen and not an
     `env_open` fact, precisely because every party that inspects `ra` — unwinders, debuggers,
     crash dumpers — must recognize the same value with no query, and an implementation-chosen
     sentinel would diverge silently between a mini, an emulator, and a third core.
   - **It is fail-closed by composition.** A `ret` to the sentinel outside any activation hits
     the empty-continuation-stack `gate_return` fault above — the sentinel is guarded by an
     existing guarantee, not by obscurity.
   Explicit `gate_return rd, gatedesc` remains the primitive for replies that carry capabilities,
   inline bytes, or a >64-bit output-borrow result; the sentinel is the ordinary-function default
   for the registers-only reply. `gate_tail` is unchanged (the gate-aware-compiler optimization);
   the sentinel makes naive code correct, which is the right default. **Register state on return from an
   activated callee is fully defined, and the reply is two registers — status and value —
   never one multiplexed register.** The **value** register is the saved `call_rd`: the callee's
   payload, the **full 64-bit range with no `-CONDITION` reservation** (a gate reply may be any
   signed or unsigned `u64`, exactly as an ordinary `jal`/`ret` return would be — so the
   common case reads `call_rd` identically to a local call). The **status** register is the
   architecturally fixed `r3` (`rd0 = value` in `call_rd`, `rd1 = status` in `r3`, the §1
   two-result form): `0` when the callee returned normally, or a negative §13.1 condition for a
   **gate-level** outcome the callee could not itself produce — `-CANCELLED`/`-TIMEOUT`
   teardown, `-POISONED`, `-HANGUP`. Because `r3` is the status channel, a `call_rd` naming `r3`
   is `-MALFORMED` — and the psABI freezes **`call_rd = r2` for `lnp_domaincc`** (gate replies
   land where local-call returns land; the hardware field stays general for hand-written
   assembly). A gate **value** reply is at most 64 bits — a 128-bit or larger result
   uses an output borrow window (§17.1c), **mandatory for compiled `lnp_domaincc` code**
   (sret-via-output-borrow through window 1, or `mem_grant` across address spaces; the value
   register carries the byte count or 0); the ordinary
   `r2`/`r3` 128-bit return pair is a *local*-call convention, not a gate one. This **harmonizes the synchronous reply with the
   asynchronous one**: the §17.8 completion record already splits `[8] status i64` from
   `[16] value u64`, and a sync `gate_call` now carries the same `{status, value}` shape rather
   than the odd-one-out multiplexed register — a callee returning `-5` as a value is
   unambiguously distinct from a gate cancelled with `-CANCELLED`. **On any non-OK status the
   value register is zeroed** (a value-only reader fails toward a benign zero, though the
   contract is to check status); `fa0` carries an FP reply when the ABI is FP; callee-saved
   GPRs/FPRs are restored from the
   frame; **every other caller-saved register in the gate's declared `abi` class is zeroed** (not
   left as the callee wrote it; the class is fixed at `gate.seal` — no escalation exists, §9.2) —
   no callee register state leaks back. **The scrub is scoped to this path only** — the crossing back from
   an untrusted callee that actually ran. A **pre-activation cancellation** (`-INTERRUPTED`/`-TIMEOUT`
   at the §9.4 commit point, callee never started) is *not* this path: nothing ran, nothing to scrub,
   the caller's registers are left exactly as they were except that the status register `r3`
   carries the condition and the value register `call_rd` is unchanged — the `gate_call` is an
   ordinary interrupted instruction. A `gate_return` whose descriptor is `0` is a **registers-only reply** (no caps, no
   inline bytes) — the same null-descriptor convention as machine-call returns (§9.3), one rule.
   Because the callee ran in its own protection context with **domain-tagged translations** (§15), no
   TLB flush is needed on entry or return — the gate is **flush-free**.

*Asynchronous* completion is the **separate** `send`-to-a-completion-endpoint pattern (later
`recv`/`wait`); it does **not** use `gate_return`.

**`gate_tail` (the protected tail call).** For service chains A→B→C→…, ordinary nesting pushes
one continuation per hop; `gate_tail` in B replaces B's activation with a C activation under
the **same** continuation — the chain's frame depth does not grow, and C's `gate_return`
resumes A directly. This is what makes proxy objects, service decomposition, capability
routing, and language-level dynamic dispatch depth-bounded instead of frame-per-hop. Each rule
is the projection of an existing law:
- **One commit point.** `gate_tail` has exactly one
  atomic commit: the departing activation's termination (charges settled, borrow and
  activation-scoped state torn down) and the successor activation's creation on the same
  continuation are **one transition**. Before commit the issuer is an ordinary live activation:
  a tail into a held serialized gate **parks pre-commit as the departing activation** (the park
  is an instruction boundary, Law 5 — cancellation, a firing donation deadline, or a debug
  freeze during the park land on the *departing* activation under the ordinary §9.4/§16.3
  rules, and the borrow window is still alive because its activation is). After commit the
  chain tip is the successor, full stop. There is no intermediate deliverable state, so the
  cancellation-vs-tail race is the ordinary boundary rule, not a new one.
- **Rights**: the issuer must hold the target gate capability with the same right `gate_call`
  requires — a tail hop is a call, not a loophole.
- **ABI (subset, with the promise recorded)**: the target gate's declared `abi` class must be
  **equal to or narrower than** the departing gate's (`-MALFORMED` otherwise), and the
  continuation frame records the *original* gate's class at the original call — **the eventual
  return's sanitization scope is that recorded class**, so the promise made to the original
  caller never narrows behind its back, while a narrow proxy may still front a narrow service
  under a wide original. Entry zeroing at the tail crossing uses the target's own class; state
  beyond it is foreign to the successor and faults on touch (§9.2's sanitization-scope rule),
  so nothing the narrower successor can observe ever carries the departing activation's
  wider-class residue. **Interposition cost, stated exactly:** a pure-forwarding tail hop is
  observationally identity *except for* the target-class entry zeroing **and the death of the
  caller's activation-scoped borrow windows at the hop** (the borrows-die-at-commit rule below)
  — a forwarding proxy that must preserve its caller's lent buffers re-lends them explicitly
  (`gate.borrow_arg` or `mem_grant`), and nothing else about the hop is observable to either
  end.
- **Registers only**: seven user words ride issuer `r2`–`r8`; the successor receives a new
  `ActivationContext *` in `r2` and those words in `r3`–`r9`, exactly as at
  any entry; there is no descriptor form — persistent capability transfer, inline payloads, and
  descriptor borrows are `gate_call` features, and a hop that needs them is two calls. A target
  gate's declared `gate.borrow_arg` facts **do** apply (the tail is a null-descriptor
  invocation, and the lent range is the issuer's own authority, named by the issuer's
  registers — the ordinary §17.1c rule, not an exception).
- **Borrows die at commit**: the departing activation's call-scoped borrow windows and
  activation-scoped state end at the commit point exactly as at `gate_return` — the windows were
  lent to *that gate's* activation (§17.1c), and forwarding caller memory onward is an
  authority decision the middleman makes explicitly (its own `gate.borrow_arg` lending or
  `mem_grant`) or not at all.
- **Accounting**: the departing activation settles its charges as a return would; the new
  activation charges as a direct call; the chain continues to ride the original caller's
  reservation, and donation, `max_donation`, and the derived deadline are **chain facts that
  transfer unchanged** — a tail hop can never extend a deadline.
- **One chain**: the `call_chain_id` is preserved, so `-DEADCYCLE` detection, §9.4 cancellation
  delivery (which posts to the chain *tip*), and trace spans see one chain whose tip moved.
- **Observability is the truth**: the elided activation is genuinely gone — unwind, debug, and
  `state.open` see A→C, because that is the machine's real state.
Serialized-gate parking and `-BUSY` at the target follow `gate_call`'s rules. A failed tail
(bad capability, class mismatch, pool exhaustion) leaves the departing activation live with the
condition in `rd`, so the middleman can fall back or return an error; on success the issuing
context is gone and `rd` is never observed — the `gate_return` asymmetry, same rule.

**`gate_return`'s own `rd` is meaningful only on failure.** A successful `gate_return` transfers control
out of the returning context, so it writes no architecturally observable `rd` there. `rd` is written and
observable **only when `gate_return` fails and stays put** (a non-zero descriptor to a machine caller
`-MALFORMED`, a cap-install error), leaving the callee/handler running to inspect and retry. A
`gate_return` with **no live frame** raises a synchronous fault; if that cannot be delivered it is
domain-fatal (§9.3).

**Scheduling: donation, mechanically defined.** The activation carries three engine-private fields: a
**call-chain ID**, a **donated-reservation handle**, and a **deadline** — derived, never an operand, so a
malicious callee cannot extend it. If `max_donation = 0`, the gate adds **no deadline**; a
`RESERVATION` caller still contributes its own reservation deadline, while a
`TIMESHARE`/`FIXED_PRIO` caller contributes none. Otherwise, for a **`RESERVATION`** caller,
`deadline = min(caller's remaining reservation deadline, now + max_donation)`; for a
**`TIMESHARE`/`FIXED_PRIO`** caller, `deadline = now + max_donation`. The additions are checked under
§8 and an overflow is a pre-activation `-OVERFLOW`. The rule is purely mechanical: **CPU is charged to the donated reservation
exactly while the activation is running, or blocked in a downstream op the engine has tagged with the
same call-chain ID** (a `gate_call` the activation makes propagates chain ID and reservation). Any other
blocking — an endpoint or futex not tagged with the chain — **suspends the donation** and the deadline
arms cancellation (§9.4). Memory and objects the callee allocates are charged to the **callee's** budget.

**Priority inversion (the boundary is engine-visible ownership).**
- **Donation inherits through engine-visible ownership — the serialized gate *is* the RT mutex.** When a
  chain link blocks on a contended engine object whose current holder the engine knows — above all a
  **serialized gate** held by another activation — the engine **extends the donation to that holder**
  (transitive priority inheritance) until release. An RT chain that finds gate `G` held by low-priority
  `C` makes `C` run on the chain's reservation until it releases `G`: priority inheritance for free, no
  owner-in-a-word ABI. (Extension is a **charging** rule, never a wake rule: a holder under a
  debug hold or domain quiescence stays held — it runs on the chain's reservation only when it runs at
  all — and the donation deadline remains the caller's recourse, §9.4.)
- **A raw futex is the ownerless fast path and does *not* inherit** (§6's one-line rule). `futex_wait`
  records no owner — that ownerlessness is what makes the uncontended path one memory access — so a
  chain blocking on a futex suspends its donation, governed by the deadline. An RT chain must not gate
  its critical section behind an off-chain futex; it uses a serialized gate (inherits) or an
  engine-tracked counter endpoint. (An owner-bridging futex mechanism, if RT-POSIX compatibility
  ever proves gate emulation unacceptable, arrives whole through the Appendix G `FUTEX_EXTENSION`
  seam — v1 architects no lock-word format at all.)

**Implementation note — the donation "graph" is not a graph, and the engine never traverses one.**
The chain ID and the donated-reservation handle are **per-activation register state that flows with
the call** — a tag riding the dataflow like any other operand; inheritance is recorded **at block
time, at the contended object** (one write when a waiter arrives); and the cancellation cascade is
a sequence of ordinary machine-call deliveries, each posted once. Every scheduling event does
**O(1)** work against flat state — there is no structure to walk. Donation is dataflow.

**The asynchronous form — `gate.submit` (§16.3): donation follows the chain, not the
thread.** A `gate_call` parks the caller; an async caller must not park, and it must not lose the
§9 machinery for the privilege. `gate.submit` is the WorkQueue submission pattern applied to gates: a
`gate.submit` naming the gate and a **CompletionQueue operand**, bounded
inline bytes and a cap list in the body (the same pre-activation checks as `gate_call`, §17.1b
bounds included); `rd` returns an **ActivityRef** keying the completion record. The engine
mints a **detached activation** — the state §9.4 step 1 already defines, entered at birth instead
of by detach — scheduled on the gate's concurrency pool and **running on the submitter's donated
reservation via the call-chain ID**: the donation rides the chain, with the same derived deadline,
the same transitive inheritance through serialized gates, and the same §9.4 cascade; there is
simply no parked thread for it to ride instead. `gate_return` becomes the completion record
`{ActivityRef, status, retval u64}`; byte replies travel out-of-band through a granted
buffer (the ring shape), because the 24 B record is a completion, not a channel. **No borrow
descriptor** (§17.1c: the submitter keeps running — an async borrow would be an aliased `&mut`,
so async lending is `mem_grant` or a moved cap, by construction). Pool exhaustion is `-BUSY`
(visible backpressure; high-rate submitters batch envelopes on the §16.6 ring).

**The submit queue on a serialized gate, pinned (an unbounded, unordered, unaccounted queue would
break three house rules at once).** A `SUBMIT` to a held serialized gate **queues**; the rules:
**(a) accounting — grower-pays:** each pending submission charges the *submitter's* object budget
(the park-record rule with no park), and the gate bounds its queue through `gate.limits`
(`submit_queue_bound`, §17.7; full → `-BUSY` at submit, visible backpressure). **(b) order —
deadline order, then FIFO:** the queue drains earliest-derived-deadline first, no-deadline
submissions FIFO after all deadlined ones — a submitter that declared no urgency accepted
unbounded ordering delay by construction, the `TIMESHARE` doctrine applied to a queue. **(c)
donation extends from the queue:** the holder runs on the reservation of the most urgent waiter —
queued or parked, one rule (§9.2's engine-visible ownership; sync callers and queued submissions
are one waiter set to the inheritance machinery). **(d) deadline expiry while queued is commit
point 0:** the submission cancels pre-activation — completion record `-TIMEOUT`, no callee effect,
nothing to scrub.

**The failure topology, pinned (the submitter has moved on, so who learns what, when):** a failure
the engine can detect **at the submit envelope** fails the *op* — `rd` = the condition, nothing
enqueued (`-MALFORMED`, `-MSGSIZE`, `-DENIED`, queue-full `-NOSPACE`); everything after enqueue
arrives as a **completion record with the condition in `status`** — one error surface before the
handle exists, one after, no third. **`-DEADCYCLE` does not exist for `SUBMIT`, by reasoning, not
oversight:** the sync cycle check exists because a `gate_call` whose chain already holds the
target would park a thread forever; `SUBMIT` parks nothing — a chain submitting into its own held
serialized gate simply queues behind itself, the holder (which is *running*, not parked) returns,
and the queue drains: legal, deadline-bounded, no deadlock to detect. **Submitter death is chain
cancellation, stated as the rule the sync path got for free from the blocked caller's existence:**
a domain's teardown cancels every chain it originated — detached activations take the ordinary
§9.4 cascade (donation revoked, cancellation posted), pending queue entries cancel at commit point
0, and completion records aimed at the dead endpoint drop with it (the last-reference rule, never
delivered, never leaked).

**The wide-completion seam, named before the pressure arrives (the CQE32 lesson: completion
records grow, predictably, and the growth must not be a breaking size negotiation):** the 24 B
record's `retval u64` covers the count/id/offset class; the 16–64 B struct-reply class is
out-of-band in v1 (a granted reply buffer per submission — the ring shape), and a **wider
completion-record variant is reserved by name (`WIDE_COMPLETION`)** — selected per CompletionQueue
endpoint at create, never per message; nothing else may claim the meaning. **Cancellation uses
`activity.cancel` and only an ActivityRef.** It cannot reach a synchronous `gate_call`. The
ActivityRef carries the generation-qualified identity and origin check shared by every asynchronous
activity. Another domain presenting it gets `-DENIED`; an unknown, consumed, or recycled reference
gets `-STALE`. **The race
rule is one cell: each accepted submission owns an engine-private terminal-choice cell —
`OPEN → {NORMAL | CANCELLED | TIMEOUT}` — and normal completion, explicit cancellation, and
deadline expiry contend on that one cell; exactly one wins, once.** Returns: `0` if
cancellation selected the terminal outcome *or* had already selected it (idempotent by
design — retrying a cancel is safe until the completion is consumed, after which the handle is
stale); `-BUSY` if normal completion or timeout already won. **A pending submission** (not yet
activated): removed from the gate queue, its donation leaves serialized-gate inheritance, its
queued capability and object references drop, its reserved completion record is emitted with
status `-CANCELLED`, and **no callee code runs**. Move-transferred capabilities stay moved and
drop with the cancelled submission — cancellation never reconstructs consumed sender slots
(§13's one-way rule). **An active submission**: the cell selects `CANCELLED`, the existing §9.4
chain cancellation triggers, a later `gate_return` is suppressed from publishing a normal
completion, and the cancellation completion is delivered only after activation teardown and
step-5 quiescence. **`CANCEL` itself performs O(1) terminal-state transition work and returns after
any §3 acknowledgement required by replicas of that terminal cell** — it
never waits for callee cleanup or teardown quiescence; **the completion record, not `CANCEL`'s
return, signals that submission-owned queued references have been released. A persistently transferred
memory cap or `mem_grant` remains live until explicit `cap_revoke(quiesce)` and is not made safe to
reuse by submission completion.** CompletionQueue
destruction drops the record but never stops teardown (the last-reference rule above). The
completion slot reserved at `SUBMIT` is why cancellation cannot fail for lack of queue space.
Body layout is §17.7's (`scalar0` = submission handle, `scalar1` = flags, must be zero).

**This lifecycle is the definition for every asynchronous submission class — the `ActivityRef`
contract, stated once.** An accepted asynchronous submission of *any* class — gate
`SUBMIT`, a WorkQueue `send`, a DMAWindow copy submission, a service-ring op — is an **activity**,
and its handle (`rd`, non-negative §1) is its **`ActivityRef`**: origin-local, opaque,
generation-qualified (the §3 progress discipline; unknown/consumed/recycled → `-STALE`, foreign
domain → `-DENIED`), keying a completion whose slot was **reserved at submit**. Its lifecycle has three
distinct points: **(1) terminal selection**—exactly one terminal-choice cell selects one of
`{NORMAL, CANCELLED, TIMEOUT, POISONED}`; **(2) teardown completion**—all cancellation, DMA drain,
reference release, and required quiescence for that outcome finish; **(3) record delivery**—at most one
completion record is enqueued, and only if the completion endpoint remains live. `POISONED` is the
fence-synthesized terminal (§3 `quiesce`). Cancellation is idempotent until consumption; teardown
resolves every open activity to a terminal and completes even if no record can be delivered;
serialization exports open activities as their state. **A class adds only a policy row — may it
queue, may active work be cancelled, what the completion payload is, whether quiescence gates the
terminal — and nothing else**: gate submissions {queue: yes; cancel-active: yes; payload:
status+retval; quiescence: when memory was lent}; WorkQueue {queue: yes; cancel-active:
profile-dependent; payload: device result; quiescence: device-dependent}; DMA copy {queue: yes;
cancel-active: yes; payload: bytes+status; quiescence: yes}. A class restating lifecycle,
handle, or cancellation rules independently is a spec bug against this paragraph. Synchronous
`gate_call` is deliberately **not** an activity — the caller parks, and detach/return semantics
are §9.4's own; sharing activation machinery is not sharing a caller contract.

**The reservation invariant, all the way through failure:** *once submission returns success, the
engine has irrevocably reserved everything needed to select exactly one terminal outcome, complete its
required teardown, and—while the endpoint remains live—deliver at most one record.* The failure matrix, closed:
**(1)** capacity that cannot be reserved fails the *submission* (`-NOSPACE`), before any effect —
success means the slot exists; **(2)** exactly one terminal is **selected** per activity (the
one-winner cell—never zero, never two), and its teardown always completes; **(3)** submitter death: open
activities of a dying domain are driven to a terminal by teardown (the §9.4 cascade), and their
records are delivered into reserved slots while the endpoint lives—a corpse's activities still
terminate; **(4)** consumer
death: destroying the completion endpoint or waitset **drops the reserved records but never the
teardown they signal** (§9.2's rule — the record was the *signal*, and a consumer that destroyed
its own mailbox chose not to hear it; memory-reuse safety then rides the §9.4 quiesce, which
endpoint death does not skip); **(5)** the reserved slot is owned by the completion queue's owner
(charged at `SUBMIT`, §16.4) and released at consumption, `RESET`, or queue destruction; **(6)**
cancellation itself selects a terminal and, if the endpoint remains live after teardown, delivers its
completion—`CANCEL`'s return is never the teardown signal;
**(7)** completion order **may differ from submission order** (activities are independent;
ordering is the consumer's job if it wants one, via the cookie); **(8)** the `ActivityRef` is
**single-use and generation-tagged** — consumed refs are `-STALE` forever, never recycled into a
live meaning (§3).

### 9.3 Machine-initiated calls (faults, events, cancellation)

The machine crosses into a domain the same way a domain crosses into a service: through a gate the
domain registered. There are two, and registration is the delivery contract:

- **`dgates(..., FAULT, entry_pc)`** (§16.1): the domain-wide **fault gate**. A
  synchronous fault — memory fault, illegal/disabled opcode, architected `trap` — is
  the machine calling this gate **at the offending instruction**.
- **`dgates(..., EVENT, entry_pc)`**: the domain-wide **event gate**. An asynchronous event — a
  numbered **post**, a timer in event mode, a
  cancellation (§9.4) — is the machine calling this gate **at the next instruction boundary**.
- **`dstack.new` / `dstack.use`** (§16.1): per-thread. Entry PCs are domain-wide; the activation stack is
  **per-thread** state, so concurrent deliveries to different threads never share a stack. Registration
  pins and charges the range. Replacement or clear is prospective: it changes where the next machine
  call allocates, while each live frame retains its own charged pin on the original payload range until
  successful return or teardown. The old registration's base pin is released immediately only when no
  live frame uses it; otherwise its frame-held pins remain. Overlapping mapping/protection/backing
  mutation fails `-BUSY` while either a registration or live frame pins the range. `dreplace.commit` or
  thread death tears down frames before releasing their pins. Machine-call delivery and return therefore
  never depend on a pageable or concurrently unmapped payload.

**Delivery is precise** (architectural; v1's in-order pipeline makes it cheap, and an out-of-order
implementation must still deliver precisely): the machine interrupts the target thread, pushes the one
frame kind with the **full register context as the argument payload**, masks atomically, and activates
the registered gate exactly like a callee: fresh context, arguments in registers —

- **`r2` = delivery class** (synchronous-fault class, asynchronous-event class, or cancellation class),
- **`r3` = event payload word, architected `trap imm32` kind, or fault-class subtype** (zero when the
  producer has none),
- **`r4` = faulting address** (memory faults), **event number** (numbered async), or zero
  (cancellation),
- **`r5` = pointer to the argument payload** (§17.5: flags, resume PC, saved mask, cause, GPRs, FP when
  active, and for instruction faults the **faulting instruction word + the engine's decode of it**
  (`fault_insn` + `decode`) plus **`orig_rd_value`** — see the restart recipe below),
- `r6`–`r9` zeroed (reserved for future payload words), **`r30` (`tp`) = the interrupted context's saved
  `r30` value**, and `r31` = the registered activation-stack pointer (**16-byte aligned** —
  registration validates it, `-MALFORMED` otherwise, and every delivery preserves the §9.2
  universal entry alignment); every other register is the
  zeroed/fresh state of any activation. Reusing `tp` is safe because a machine call remains in the same
  domain and thread, and it lets language cleanup, TLS, and diagnostics run without a hidden canonical
  thread-pointer register.

**Numbered-event namespace.** Numbers `0..47` are software-postable: `POST` and software-configured
Timer event mode may produce only this range. Numbers `48..63` are engine-only architected events;
`63` is `MEMORY_ERROR`. Possessing `POST` authority does not authorize synthesis of that range:
`POST 48..63` fails `-DENIED`, while a number above 63 is `-MALFORMED`. Hardware producers may use an
assigned engine number only when its defining profile names it. Future software allocation grows
upward, engine allocation grows downward, and a revision may not collide or reclassify an assigned
number. Architecturally, the event space is exactly the 64 bits of `EVENTMASK`/`EVENTPENDING`; disposition tables
cover all 64 numbers regardless of producer.

**Cancellation is an unnumbered, unmaskable delivery class.** It bypasses `EVENTMASK`,
`EVENTPENDING`, and every numbered-event disposition; no policy may ignore or defer it past the next
eligible instruction boundary. On entry `r2 = CANCELLED`, `r3` is the cancellation reason (`0`
explicit, `1` donation deadline, `2` chain cascade, `3` teardown), `r4 = 0`, and `r5` points to the
usual context payload. The payload records the pre-delivery numbered-event mask, while the handler
runs with `EVENTMASK = UINT64_MAX`; **an `EVENTMASK` bit value of 1 masks that numbered event and
0 makes it eligible**, so this masks all numbered asynchronous events during cancellation delivery.
Successful return restores the saved mask. An engine-private
cancellation-in-delivery bit coalesces duplicate cancellation triggers for the same activation and is
cleared only by return or teardown. Thus “EVENT-gate path” names the registered entry mechanism, not a
numbered event subject to ordinary event policy.

**The measured fault path (`FAULT_WARM_RTT`) — published so machine calls are load-bearing,
not merely correct.** A fault *is* a gate activation (Law 1), so the warm fault path is the
§9.2 warm gate **plus the bounded payload write**, and it gets the same treatment: a published
MachineView `GEOMETRY` fact — the round-trip bound in architectural ticks from the faulting
boundary to the handler's first instruction, plus `gate_return 0` resume — under the matching
preconditions: registered gate and activation stack resident and pinned, `GPR`-class handler,
`VEC_PRESENT` clear (the payload write is then VLEN-independent), same agent, no contention,
cause resolution resident. Residency is §9.2's doctrine applied to the FAULT/EVENT gate
entries — leases cover them, exhaustion demotes to the published cold path, never changes
semantics. This is the number GC barriers, sanitizers, JIT deopt, and userspace paging build
against; without it "a fault is the machine calling you" would be a slogan. Appendix D binds
the benchmark family to exactly this precondition list, beside the gate family.

**The red-zone guarantee.** Machine-call
delivery writes **only** the registered activation stack and the engine-private frame — **the
engine never stores below the interrupted context's `sp`**, at any delivery, for any cause.
The constraint binds the engine's delivery writes and nothing else (the interrupted code's own
below-`sp` stores are protected, not constrained), so a psABI red zone is sound by
construction; the red-zone **size** is the psABI's fact, freely revisable there.

The handler **edits the payload with ordinary stores** — it is its own state, handed to it explicitly
(the editing rule, §9). **`gate_return` with descriptor `0` means "my reply is the (edited) argument"**:
resume from the payload's registers and resume PC. A non-zero descriptor to a machine call is
**`-MALFORMED`, stay-put**.

**A machine-call handler is an ordinary function too (the §9.2 sentinel, universally).** The
engine installs the return sentinel in `ra` at machine-call delivery exactly as at a gate
activation, so a handler may be a plain function — it receives the context pointer as its `r5`
argument (the POSIX `sigaction(class, subtype, addr, ctx*)` shape), edits `*ctx`, and ends in an
ordinary `ret`; the sentinel fetch performs the `gate_return 0` resume. Explicit `gate_return 0`
remains exactly equivalent and is what the restart recipe (§17.5) and hand-written handlers use.
**The engine dispatches the return on frame kind, never on the handler's live registers:** a
machine-call frame **restores the whole context from the payload** (so the handler's live
registers at `ret` are discarded — which is precisely why editing goes through the payload
pointer, not through live registers), while a synchronous-gate frame takes its reply from the
live `call_rd`. The same `ret` therefore does the correct thing for whichever frame is on top,
because the frame kind is engine state the handler cannot choose. The synchronous-fault
inhibition and double-fault rules are unchanged; only the handler's terminal instruction shape
is now ordinary. **PC semantics:** a synchronous fault saves the **faulting** instruction's
PC, so after the handler repairs the cause the instruction **retries**; an async event saves the **next**
instruction's PC, so the interrupted stream **resumes**; software that wants to skip a faulting
instruction advances the saved PC itself.

**Masking, disposition, routing.** The per-thread mask is the **`EVENTMASK`** PCR (§8), atomic against
delivery: bit `n = 1` masks event `n`, and bit `n = 0` permits it. Disposition is the per-number table set by `event.disposition` (default / ignore /
deliver, per event number < 64; `event.default` sets the domain-wide default). Domain-directed delivery
(including `event.post` with `target_kind=ANY`, §16.1) is routed by the scheduler to an eligible
(unmasked) thread, which uses its own stack. A masked event stays **pending** (per-thread, or per-domain
for domain-directed), visible in the **`EVENTPENDING`** PCR, re-evaluated on the next mask change.

**Synchronous-fault delivery inhibition is separate from `EVENTMASK`.** While the engine is delivering
a synchronous fault class to its fault gate, it records that class as internally inhibited until the
matching machine-call activation successfully returns. A second synchronous fault of the inhibited
class is a double fault and is domain-fatal; other synchronous classes nest normally subject to the
continuation bound. This internal bitset is engine-private continuation state, is serialized with the
activation, and is neither readable nor writable through `EVENTMASK`, which covers only asynchronous
events 0–63. This bitset is **the one deliberate divergence from the one-mask story**, and it
must stay divergent: a maskable synchronous fault is an infinite loop, so unifying the two
masking mechanisms would be unsound, and the price — one engine-private mask a debugger reads
only through the serialized activation — is paid knowingly.

**Pend-until-registered (safe by rule, not fatal).** Domain/thread birth carries no implicit
activation-stack fields (its `sp` is the
ordinary call stack, §17.7), so **a new thread is born unregistered**: it is (a) ineligible for domain-directed routing (the scheduler picks a
registered thread) and (b) a thread-directed event to it **stays pending until `dstack.new` or `dstack.use`**
(delivered at that boundary, visible in `EVENTPENDING` meanwhile). The same rule covers the domain-wide
entry PCs: an async event before `dgates(..., EVENT, ...)` pends. A **synchronous fault** with either
registration missing (no fault gate, or no stack on the faulting thread) has no landing pad and **is
domain-fatal** — run no faulting code before registering; a runtime's startup registers both first.

**Blocked-op interruption (precise, boundary-respecting).** When a machine call targets a thread blocked
**inside** an engine op, the engine first **cancels the op to a defined return value** (the `cancel`
bump policy discipline, §3), releasing all internal engine locks/resources, then runs the handler — so
the handler may freely call typed engine operations, `wait`, `read`, or `gate_call` without deadlocking against
the op it interrupted. Restart is **commit-gated to prevent duplicated side effects**, split into an
architectural fact and a software policy: the engine sets the frame's **`OP_RESTARTABLE`** flag iff the
op committed **zero side effects** (still purely blocked) and may be re-issued from its original
arguments; the *decision* to restart is software policy in the handler/runtime. If **any** bytes,
message, caps, or state were committed, `OP_RESTARTABLE` is clear and the op returns its **partial
result; software must not re-issue**. **The frozen restart recipe** (the engine hands the ingredients;
the runtime performs it): `payload.gprs[decode.rd] = payload.orig_rd_value` (restoring the operand the
op's own `rd` write may have destroyed — `orig_rd_value` exists precisely because `rd` can alias a
source), `payload.resume_pc -= 8`, `gate_return 0` — with `rd = r0` needing no restore. Cancellation
respects each op's atomicity:
- **`read`/`write`** (byte stream): return the bytes already moved if any, else `-INTERRUPTED`.
- **`send`** (message): either enqueued whole or `-INTERRUPTED` with nothing committed. **`recv`**:
  either the final dequeue/cap-install transition committed (normal success), or `-INTERRUPTED` leaves
  the message queued and installs no caps; ordinary destination bytes written by earlier copy quanta
  may remain and have no synchronization meaning (§10.2).
- **`wait`/`futex_wait`**: `-INTERRUPTED`.
- **`gate_call`**: per the §9.4 commit point — pre-activation `-INTERRUPTED` with no callee effect and
  no scrub; post-activation the call runs to its real return, its cooperative cancellation, or the
  donation-deadline detach, and the pending event is taken at whichever boundary comes first.

**Failure model (so the mechanism is total).** Nesting (a gate call inside a handler, an event during a
gate call) is just more frames, popped in order, bounded by the **bounded continuation stack**: a
delivery that would overflow it is **domain-fatal** (terminated with a recorded cause), never silent
corruption. A synchronous fault **while saving context**, with **no registered fault gate**, or of a
class currently inhibited by an active delivery of that class (double fault) is domain-fatal. The
domain-fatal stack case is scoped to **registered-then-invalid**
stacks (unmapped/overflowed at delivery); never-registered threads pend as above. When a domain is
**frozen** its deliveries queue; when **destroyed**, its frames and pending set are discarded.

### 9.4 Cancellation and teardown (one ordered flow)

A committed `gate_call` must always end through a clean boundary — never a mid-flight abort that
corrupts the callee, never a caller left hostage. Two invariants, everything below serves them:
- **Callee memory safety:** an activated callee's state is never torn out mid-instruction; it finishes,
  unwinds, or is terminated **whole** (its protection context contains the damage).
- **Caller liveness:** the caller's escape **never waits on the callee's cooperation**.

Baseline facts: the scheduler is preemptive and **the machine has no multi-instruction or
software-created non-preemptible region (Law 5); only one bounded instruction is indivisible**,
so a callee spinning in `while(1)` cannot starve anything — it is preempted like any thread; and
donation runs the callee on the caller's reservation, bounded by the hard deadline. The flow:

**0. Commit point (pre- vs post-activation).** Before the callee is activated (validation and the
inline-payload copy), a caller-directed machine call or deadline expiry cancels cleanly:
`-INTERRUPTED`/`-TIMEOUT`, no callee effect, no scrub — an ordinary interrupted instruction. Steps 1–5
are the post-activation path.

**1. Trigger and immediate caller detach.** Triggered by the donation deadline, an explicit cancel, or a
caller-directed machine call that must be delivered. The engine **detaches the caller at once** —
revokes the donation (the callee continues only on its own reservation, or is descheduled) and resumes
the caller with `-CANCELLED`/`-TIMEOUT` (subject to the step-5 quiesce) — **without waiting on the
callee**. **The caller's full escape bound:** the deadline bounds the *unserviceable wait*; the caller's observed
resume bound is **deadline + the step-5 quiesce term**, and the quiesce term is bounded by the
§11.2 `INVALIDATION_ACK_BOUND` over the activation-scoped borrow windows this call named. An RT admission that
budgets a cancellable call budgets the sum, not the deadline alone; a chain that lent nothing
quiesces nothing and resumes at the deadline exactly. The **chain revocation set** is what step 5
must quiesce: the activation-scoped borrow is non-relendable and has exactly one consumer
(`N ≤ 1` per link), so the set is bounded by chain depth. **Persistent cap-list transfers and
`mem_grant`s are not in this cancellation set**: the caller chose table-entry lifetime and must
explicitly revoke with `quiesce` before reusing memory that remains persistently shared. The callee's fate follows
independently, delivered as a **machine call** (cancellation comes
from outside the callee's instruction stream, so it is inherently the EVENT-gate path — literally the
same op as every other machine call, cause = `CANCELLED`), never passive orphaning.

**2. Cascading chain walk (cancel the whole `call_chain_id`).** If `A` called `B` and `B` called `C`,
the chain shares one ID, and `B` is blocked inside its call to `C` — it cannot take an async machine
call until that inner call returns, yet `C` runs on a donation that just vanished. So the engine does
not cancel only `B`: it **posts a cancellation machine call to every active link at once**. The leaf
(`C`, holding the CPU) takes its call first, unwinds, `gate_return`s `-CANCELLED` to `B`; that return
unblocks `B`, which immediately takes its own already-posted cancellation and unwinds to `A` (detached).
The chain collapses **leaf-to-root in bounded time**; no link is stranded, and `C` never runs on a
revoked donation past its next instruction boundary.

**3. Tier 1 — forced delivery, cooperative cleanup (`cancel_policy=0`, default).** The machine calls the
(each) callee activation's EVENT gate with cause `CANCELLED`. Async machine calls land at the next
instruction boundary, so the callee **cannot spin past it**: even `while(1)` is interrupted and vectored
to the callee's own handler, which runs the callee's own cleanup (release locks, destructors) and ends
the activation. Forced *delivery*, cooperative *unwind* — and the cleanup runs on the callee's **own**
reservation, bounded by that budget and by preemption.

**4. Tier 2 — forced termination (`cancel_policy=1`, and the backstop for Tier 1).** If the callee has
no registered event gate, faults during the cancellation call, or overruns a bounded cleanup deadline,
the engine **force-terminates the activation**: stack and activation-local engine references reclaimed;
ordinary capabilities already installed by persistent transfer remain in the callee's table. No cleanup runs. Safe for
the caller and every other domain (the callee ran in its own protection context). It makes **no
guarantee about the callee domain's own internal state**: a futex the terminated activation held with
sibling threads in its own domain is left held, and those siblings can deadlock. This is the microkernel
reality, not an ISA defect, and the spec does not paper over it — recovery is software: a
**robust-futex** scheme (**personality software walking its own registered list on teardown
notification — the engine offers no optional assist here: optional engine behavior
that changes observable lock state is a second machine, and the one-machine rule refuses it**;
the lock-word convention, an `OWNER_DIED`-style bit included, is the personality's own) or a supervisor
restart. The engine's contract stops at "the caller and other domains are intact."

**Cancellation composes with debug-freeze by rank (the one interaction this section and §16.3
create jointly, pinned).** The Tier-1 cleanup deadline keeps ticking through a `DebugTarget`
freeze (the §8 deadline rule — one comparator, freeze never pauses it), and Tier-2 force-termination
is an **engine-executed teardown a scheduler hold cannot defer** — freeze holds instruction
*issue*, never engine teardown, for the same reason a dominator's kill is never blocked by anyone
(§16.3). So a debug-frozen callee with a posted cancellation cleans up cooperatively iff it is
thawed before the cleanup deadline; otherwise Tier 2 fires against the frozen thread and the
debugger observes an ordinary target-side exit under §16.3's disposition rules. A `DEBUG`-right
holder can therefore delay the target's *cleanup*, never the caller's escape (steps 1 and 5 need
no callee instructions) and never the activation's end — anything weaker would let a debugger
convert its scheduler hold into an un-cancellable activation, which is authority the `DEBUG`
right does not contain.

**5. Quiesce and resume (the physical safety linchpin).** Whichever tier fires, every
**activation-scoped borrow window** in the cancelled chain is ended with quiescence: the engine issues
the hardware-broadcast invalidate for any cached borrow decision and drains any in-flight engine access
admitted through that window to its defined boundary. **The detached caller resumes only after this
quiescence is acknowledged. Ordinary re-keyed cap-list arguments and `mem_grant` entries are persistent
transfers, not borrowed capabilities; activation teardown neither revokes nor drops them.** Their owner
uses `cap_revoke(quiesce)` when it wants that separate table-entry lifetime to end. Without the
activation-loan quiesce, the caller could resume, reuse its stack, and a lingering admitted access could
clobber it later; without explicit revoke of a persistent grant, such reuse is a caller lifetime error.

**Net.** (Read as an async runtime reads it: this is cancel-safety as a scheduler-engine
guarantee — every instruction boundary is a cancellation point, the canceller never waits on the
cancelled, and resume-after-quiesce means a cancelled callee can never scribble through an ended
activation-scoped borrow into a reused buffer. A persistently transferred grant has its separate
explicit-revocation lifetime. Structured concurrency's `select!`-drops-a-future case is the *designed* path here, not
the hazard.) Cooperative unwind is the graceful path, not the guarantee: a malicious or buggy callee can
waste its own reservation but can never (i) starve the system (preemption, Law 5), (ii) drain the caller
past the deadline (donation revoked), or (iii) block the caller past the deadline (immediate detach +
quiesce).

## 10. Endpoint communication: bytes, messages, readiness

All inter-domain communication, stream IO, async completion, and readiness operate over **endpoints**.
An endpoint's behaviour is its **type** at create time (`Backing {Thread, Memory, Register} × Producer
{software, hardware}`), never a per-op flag; a file, socket, pipe, submission ring, timer, and interrupt
are all endpoints. The surface is split by **operation concept**, not unified by encoding: byte
movement, capability-message passing, and readiness are different engines and are named separately.
There is deliberately **no mode-bit-overloaded verb** that fetches operands one way for bytes and
another way for caps.
One static-type result distinction is intentional and is not a mode-bit exception: `send` returns a
byte count for a ChannelEndpoint and an `ActivityRef` for a WorkQueue or typed hardware-submission
facet. The target capability class fixes the operand schema, rights, result, and completion contract
before execution; no runtime flag or request field selects between them.

**Capability taxonomy** (so an op's expected cap kind is unambiguous). Every capability is an **object
capability** whose *class* fixes which ops accept it: a **channel endpoint** (byte source/sink:
`read`/`write`, and `send`/`recv` if it carries caps); a **waitable endpoint** (`wait` member: timers,
completions, interrupts, readable channels); a **gate capability** (`gate_call` target: services,
including the namespace object that resolves names); a **metadata/control object** (typed object
operations only); and the **domain capability** (typed domain operations). Passing the wrong class returns `-BADREF`/`-UNSUPPORTED`,
never undefined behaviour.

**Blocking policy is endpoint-description state, not a flag namespace (Law 6).** Every endpoint
description carries **one blocking-policy bit** — block, or return `-WOULDBLOCK` — set by
`SET_BLOCKING` (§16.3), shared by all handles to the same description (the description, not the handle,
owns it). There is no per-op nonblocking flag and no open-flags word.

### 10.1 Byte movement (the hot path, register operands)

| Op | Mnemonic | Form | Role |
|---|---|---|---|
| 0xa4 | `read` | `rd, ep, ptr, len` | move up to `len` bytes from `ep` into `ptr`. `rd` = bytes transferred, `0` = orderly EOF, `-CONDITION` (`-WOULDBLOCK` = would-block, `-BADREF` = bad cap). |
| 0xa5 | `write` | `rd, ep, ptr, len` | move up to `len` bytes from `ptr` into `ep`. `rd` = bytes written or `-CONDITION`. |
| 0xa6 | `readv` | `rd, ep, iov_ptr, iov_count` | scatter read using and advancing the endpoint cursor. |
| 0xa7 | `writev` | `rd, ep, iov_ptr, iov_count` | gather write using and advancing the endpoint cursor. |
| 0xad | `readv_at` | `rd, ep, iov_ptr, iov_count, offset` | positioned scatter read; never changes the cursor. |
| 0xae | `writev_at` | `rd, ep, iov_ptr, iov_count, offset` | positioned gather write; never changes the cursor. |

**Partial transfer and faults.** `read`/`write`/`readv`/`writev`/`readv_at`/`writev_at` move **up to**
the sum of their named byte lengths and return
the count actually moved; a copy that begins validly and then hits an unmapped/protected page **returns
the byte count already transferred** (a short success), or `-FAULT` only if **zero** bytes moved. The
byte buffers are direct memory the engine copies; faults on them surface as this short-count/`-FAULT`
return, never a machine call. **Snapshot boundary for vectored I/O:** the **entire iovec array** is
snapshot-copied and validated before any transfer (§11.1), so concurrent mutation of
the iovec entries cannot cause a TOCTOU; only the pointed-to byte buffers remain direct memory under the
partial-transfer rule. **Atomicity vs partial faults:** a `write`/`writev`/`writev_at` at or below the endpoint
**atomic-write bound** is indivisible — the engine validates the whole source region first and commits
all-or-nothing (full count or `-FAULT` with zero bytes, never a partial prefix that would break
pipe-atomicity guarantees). Only transfers above the bound may return a short count on a mid-copy fault.
The atomic-write bound is a stable fact of the endpoint description — queryable by
`channel.get` on channel endpoints, and a declared service-profile fact for a
`FileDescription` (§16.5) — with the machine
floor in `env_open` — and the **architectural floor is 512 B** (the `PIPE_BUF` precedent: a frozen
binary may assume 512-byte writes are indivisible on every conforming machine).

**The cursor is a facet, not a mode (Law 6).** A **seekable** endpoint description carries a cursor:
plain `read`/`write`/`readv`/`writev` use and advance it; positioned access uses
`readv_at`/`writev_at` with an explicit register offset and no advance; and the cursor itself is
repositioned by exactly two pure ops on the
description — **`CURSOR_SET(abs)`** and **`CURSOR_ADD(signed)`** (§16.3), each returning the new offset.
There is no whence enum: end-relative and hole/data-aware positioning need file size or layout, which
are the *service's* facts, so they are service profiles (§16.5) — one client `seek` routine, two routes.
There is no cursor-selection flag or vectored-I/O operation record. A **non-seekable**
endpoint (pipes, stream/datagram sockets, timer/interrupt/completion endpoints) has no cursor:
`read`/`write`/`readv`/`writev` move what the endpoint type defines (stream bytes, one datagram, one
record), positioned forms are rejected `-UNSUPPORTED`, and the cursor ops return `-UNSUPPORTED`.

**Record overrun is a two-policy choice, never a half-consumed record.** When `read`'s `len` is smaller
than the head record (record-oriented endpoints only), the endpoint's configured policy applies:
- **`CONSUME_TRUNCATE`** (default): fill `len` bytes, consume the whole record, discard the remainder,
  and set the **sticky loss indicator** — read *and cleared* only by the explicit consuming op
  **`TAKE_LOSS`** (§16.3), so fixed getters stay pure/idempotent and a short buffer never silently looks
  complete.
- **`PRESERVE_FAIL`**: return **`-MSGSIZE`** and leave the record queued (the boundary-preserving
  behavior, matching `recv`), so the reader re-reads with a larger buffer.

`read`/`write` are strictly three-input (`ep, ptr, len`), decode-and-go, **no modes and no caps**: the
99% path pays nothing for capability machinery it does not use. Vectored forms name only the
homogeneous iovec sequence; positioned forms add their offset as a fixed register operand. Persistent
endpoint behavior uses typed endpoint operations, performance-only facts use instruction hints, and
personality flags remain service protocol. There is no port IO opcode.

### 10.2 Capability messages (descriptor operands)

| Op | Mnemonic | Form | Role |
|---|---|---|---|
| 0xa2 | `send` | `rd, ep, msgdesc` | deliver one message `(bytes, caps)` to `ep`; the engine resolves caps against the sender's table. **`msgdesc = 0` is the fixed-schema record form**: legal only on a channel whose sealed `channel.schema` fixes the record size (`-MALFORMED` otherwise) — the record source pointer rides `rs3`, the byte count is the sealed schema's, no caps, no descriptor fetched to rediscover a size the channel's type already fixed |
| 0xa3 | `recv` | `rd, ep, msgdesc` | take one message and install its caps into the receiver's table |

The message descriptor (§17.1): `[0]` bytes_ptr, `[8]` bytes_len, `[16]` caps_ptr, `[24]` caps_len. For
`send` these are the contents (in); for `recv`, `bytes_len`/`caps_len` are **in/out** (capacity in,
actual out). A message has one **logical receive commit**: it is dequeued once, returned capabilities
become live once, and the receiving thread observes either success or a pre-copy failure. This does not
make an arbitrarily large ordinary-memory destination transactionally visible to other threads.
`send` returns bytes sent; `recv` returns bytes in the message (`>= 0`), updating both counts. **If
the message exceeds the supplied capacity, `recv` fails `-MSGSIZE`, leaves the message queued, and
writes the *required* counts back** — the receiver reallocates and retries without peeking or losing the
message. **`rd == 0` on `recv` is a valid empty-payload message** (caps-only); it is not EOF — a
closed/half-closed message endpoint returns `-HANGUP`, and a nonblocking empty queue returns
`-WOULDBLOCK`. `send`/`recv` are **strictly for messages that carry capabilities or need routing**
(fd-passing-class transfers, ring submission/completion, cross-domain channels). Because caps flow only
over message endpoints, which have boundaries, a cap attaches to *its message*: the "which byte owns the
capability?" ambiguity of caps-on-a-raw-stream cannot arise.

**`send`/`recv` have transactional engine state, not multi-page memory atomicity.** `send` snapshot-copies both
the payload and the cap array before enqueue (§11.1); the message commits whole or not at all. `recv`
runs in order and **commits only at the end**: (1) peek the head message's sizes; (2) validate the
descriptor writeback target is writable **and pin its backing page for the duration** (validation alone
would not survive a concurrent unmap between here and commit) — `-FAULT` here, nothing consumed; (3)
capacity check — `-MSGSIZE`, required counts written back, message stays queued; (4) validate the
destination buffer and the receiver's free cap-table slots (`-NOSPACE` if too few; the required cap
count remains reported separately from byte/descriptor capacity);
(5) pin the complete destination and begin the copy in §1's bounded quanta. Ordinary destination
writes may become visible in address order, but the message stays exclusively claimed and capability
slots remain reserved. After the full copy, one final transition installs caps, updates counts,
dequeues, and returns success. Cancellation/interruption at a quantum boundary before that transition
returns failure, leaves the message queued, and installs no caps; destination bytes already written are
unspecified and may be overwritten by a retry. Concurrent
unsynchronized reads or writes of the destination may observe the ordinary sequence of byte writes and
are a software data race; “message atomic” never promised atomic ordinary-memory visibility. Every
pre-copy failure leaves even the destination untouched. Target teardown may likewise abandon partial
destination bytes, but still installs no capabilities and does not expose a successful receive.

**What a Counter *is*: a non-queued, engine-resident synchronization value for domains without
shared memory — updates alter retained state, never enqueue.** The distinguishing properties a
MessageEndpoint cannot offer: **accumulation without per-update queue allocation** (a million
`ADD`s hold one word, not a million records); **coalesced, bounded state** (the value is the whole
state — saturation is its only limit, §4.2's rules); **threshold and monotonic wait semantics**
(`wait` on the *value*, not on arrival order); **no loss when the consumer is unscheduled**
(retained state has no queue to overflow); **no queue-exhaustion failure for a valid increment**
(an `ADD` inside the numeric range cannot fail for space — `-NOSPACE` does not exist here); and
**engine-visible identity for RT chains** (§9.2).

**A Counter has exactly one update transition—not a `send` target.** Software producers invoke it
through `counter.set`/`counter.add`, whose rights schema demands **`WRITE`** (bit1); an attached
hardware producer such as a Timer reaches the same engine transition through its sealed delivery
relation, not a second instruction or object class. A
`cap_dup`-narrowed producer-only handle (`WRITE`+`CONTROL`, no `WAIT`) delegates like a send side.
`wait` blocks on the value; `send` to a Counter is `-UNSUPPORTED`. A high-rate cross-domain producer
batches via the §16.6 submission ring (N `SET`/`ADD` envelopes per `send`).

**`send` to a WorkQueue = architected work submission (frozen schema).** The bytes are the device
descriptor: `bytes_len <= min(WORKQUEUE_DESC_MAX, the queue's max_desc_len)`, else `-MSGSIZE`.
**`caps_len != 0` is `-MALFORMED`**: capabilities are never handed to a device queue in v1 (the
device-as-domain direction, §15, would change that through a new profile, never silently).
**`rd` = the `ActivityRef`** (§9.2 — one lifecycle contract for every submission class; *not*
bytes-sent, which would orphan completion matching). The bound CompletionQueue slot is
**reserved at submit** (`-NOSPACE` before any enqueue if the completion queue is
full); on a full work queue the endpoint's blocking policy applies (block by default; `-WOULDBLOCK` if
set nonblocking; `wait`-for-`WRITABLE` as the event-loop form) — either way, **never a lost
submission**. **Ordering: the submission carries release semantics** — every prior store of the
submitting thread is globally observable (the draining device included) before the descriptor becomes
visible, the same rule as a DMAWindow copy submission (§15), so the coherent submission path needs **no fence at
all**. A WorkQueue capability is always sealed and usable; a torn-down or device-revoked queue fails `send`
`-STALE` and raises `HANGUP` to waiters, fail-closed.

**The frozen-schema criterion is one falsifiable clause: a class earns a frozen `send` schema only
when a hardware agent produces or consumes the messages AND the payload is one fixed record —
where "one fixed record" admits at most one bounded, chip-snapshotted indirection** (the copy
descriptor's SGL, `<= SGL_MAX` entries, §17.8 — snapshotted and validated whole before any effect,
so it is part of the record for every purpose that matters) **and never a pointer a device parses
out of opaque bytes** (a device-parsed pointer would put caller VAs in device hands — the next
proposer may not cite `sgl_ptr` as precedent for pointers-in-payloads; the license is
chip-snapshotted indirection only).** That
is the hardware-drained submission pattern, and it is the *whole* pattern: WorkQueue (a device
drains opaque descriptors) and the DMAWindow submission facet (the copy engine drains the frozen
48 B copy descriptor, §15/§17.8) are two instances of the one shape — there is no software `recv`
side anywhere to version a protocol against, which is what makes freezing a schema sound. The
clause is a checkable property of the class, never a judgment of naturalness — "it's natural" is
not a criterion, which is the point. Everything else that wants `send` semantics is a
**ChannelEndpoint profile** — a versioned software contract, which is what profiles are for.

Freezing the schema is what lets "every event is a `send`" hold while `send` stays a single typed verb.

### 10.3 Readiness (`wait`)

| Op | Mnemonic | Form | Role |
|---|---|---|---|
| 0xa8 | `wait` | `rd, waitset, deadline` | block/poll on a **resident waitset object**. `deadline` is a 64-bit GPR absolute tick deadline (`0` = poll, all-ones = forever — the §6 sentinels). `rd` = events published to the calling thread's bound EventRing, `0` on timeout, `-INTERRUPTED` on a machine call. Subsumes readiness multiplexing, completion await, the non-consuming probe (`deadline = 0`), thread/domain join, and pure sleep (empty set + deadline). |

**Object creation.** Every hardware-owned class has one typed `*.new` constructor (§16.2), charged to
and bounded by the current domain's object budget. Constructors are fixed register forms; an additional
alias still requires §16.2's named-hot-path and adapter proof.

The resident membership operations use only their fixed registers (there is no waitset descriptor or
control record):

```text
waitset.new rd_waitset
waitset.add rd_member, waitset, source, ready_mask, cookie, flags
waitset.del rd, waitset, member_id
waitset.mod rd, waitset, member_id, ready_mask, cookie, flags
```

`ready_mask` uses the §17.3 readiness bits and must be nonzero; bits 8–63 are reserved-zero.
`flags` bit 0 is edge-triggered, bit 1 one-shot, and bit 2 exclusive; bits 3–63 are
reserved-zero. `MOD_MEMBER` changes only mask, cookie, and flags: the source and member identity
remain fixed. A source replacement is `DEL_MEMBER` followed by `ADD_MEMBER`, necessarily receiving
a fresh never-reused member ID.

**EventRing binding and triggering.** `channel.new` creates a charged first-class ring over
registered writable storage; `eventring.bind rd, waitset, ring` installs an explicit
`{thread, waitset, ring}` relationship. Two threads waiting on one waitset bind distinct rings, and a
transferred waitset never acquires an ambient write pointer into another domain. A `wait` with no live
binding returns `-MALFORMED`. Ring capacity is at least one, so `rd == 0` remains unambiguously timeout.
The ring stores a VMA-cell-qualified range, holds the charged registration pin for its lifetime, and
becomes stale on incompatible mapping mutation. The engine publishes ready-member entries (§17.3) up
to available capacity and returns the count; `ready.next` consumes entries. No hidden per-thread
destination state exists.
**the entry's member token is a waitset-local member ID** (assigned at `ADD_MEMBER`), *not* a capability
handle — handles are domain-local (§2.2) and would be meaningless to a different waiter, so the waiter
maps member ID + its `ADD_MEMBER` cookie back to its own local capability (and by the Law-7 naming rule,
member IDs are waitset-local, never global). `DEL_MEMBER` permanently retires that numeric member ID
for the waitset's incarnation; a later `ADD_MEMBER` receives a fresh ID, so a delayed entry already in
an event buffer cannot alias the new membership (§8.2). **Membership is a §3.1 weak observation:** it
retains the member's identity-cell metadata, not the member object; object death produces final
`HANGUP`/stale readiness and automatic removal, so a waitset can never keep a dead member alive.
Surplus ready members **stay ready** for the next `wait`
(nothing lost). Each ready member appears **at most once** per `wait` (coalesced); if the buffer is
unmapped when the engine writes, `wait` returns `-FAULT` and consumes no readiness. Triggering is
**per-member configurable** at add time: **level** (default) or **edge**, with an optional
one-shot/exclusive flag against thundering herds. Non-consuming readiness over a resident set — with the
dequeue staying in `read`/`recv` and their `-WOULDBLOCK` — is what gives the million-connection reactor
its O(1) scaling.

**The async-runtime mapping, stated affirmatively (this section is the hardware Waker).** An async
executor maps onto this surface with no adaptation layer: the **member cookie is the task ID**, so a
readiness entry *is* a wake with the waker's payload already attached; **level/edge/oneshot per
member** are exactly the redelivery semantics reactor generations have fought about, selectable per
source instead of per API generation; the **bound EventRing is the run queue**, written by
the engine into the executor's own registered memory; `poll`-returning-`Pending` is `waitset.add` + return, and
the executor's park is one `wait` whose `-INTERRUPTED` boundaries are its cooperative cancellation
points. The asynchronous gate form (§9.2 `SUBMIT`) completes the picture: its completion record
lands on an endpoint that is itself a waitset member, so cross-domain calls, IO, timers, and wakes
are one readiness surface — the machine was shaped like the executor before the executor arrived.
(The claim's scope, so it cannot be over-read: the machine owns the **notification edge** and the
**cancellation/donation semantics** — the parts a runtime cannot fix from software; the executor,
`poll`, and the state machines remain software and were never the bottleneck. A hardware Waker is
not a hardware executor, and does not want to be — scheduling policy above the reservation model is
software's, Law 3.) **And the gravity, named without force:** *spawn* — the point where work
becomes concurrent, stealable, cancellable — is architecturally `SUBMIT`: a detached activation
carrying donation via its chain ID, cancellable through §9.4, completing to the readiness surface
above. Intra-task `await` points stay function-call-grade software forever (the scope line just
drawn), but a personality whose spawn *is* `SUBMIT` replaces the zoo every runtime rebuilds badly
— task queues, cancellation tokens, deadline plumbing, priority-inheritance workarounds — with
the architected forms, and gains the thing no library ecosystem has ever had: **cross-library
structured concurrency**, because two runtimes that both spawn through gates share one
cancellation topology, one donation chain, one deadline discipline, whether or not they share a
line of code.

## 11. Native execution beneath delegated state (Law 3)

The Object/Domain/Scheduler/Capability engines are **anonymous substrate**: the interpreter of this
document's ontology, not a participant in it — the same status the ALU has. Nobody asks which domain
executes `add`; nobody asks which domain executes `CREATE`. The engines are not a domain, hold no
capabilities, and appear in no tree. Mandatory intrinsic instructions execute in these engines against
the issuing domain's **effective delegated state**. A nesting boundary never converts `dmap`,
`dspawn`, `cap.copy`, `timer.arm_rel`, memory operations, or another mandatory intrinsic into a trap,
gate call, or software request.

**The parent virtualizes state, not instructions.** It governs a child by constructing its
MachineView, ClockView, capability-admission universe, budgets, placement envelope, event sources,
object delegations, service imports, and migration policy. The engine validates each native result
against that effective universe. Implementations may flatten, normalize, cache, compile, tag, or
otherwise precompute inherited restrictions. The architected bound is:

> Native instruction transition work and lookup depth are independent of domain ancestry depth.
> Latency may depend only on the instruction's named authority span, distance span, set cardinality,
> admission dependencies, or other explicitly published operands.

No implementation may walk the parent chain on an ordinary execution path. A cache miss may rebuild
effective state from protected engine metadata, but its published bound remains ancestry-independent.

**Explicit virtualization boundaries.** Personality policy, namespace semantics, foreign-device
behavior, record/replay, compatibility emulation, and software-defined services use explicit gate,
endpoint, or proxy-object capabilities selected by the program. A service import is a capability in a
named child import slot; using it is an explicit `dcall`, `gate_call`, `send`, `recv`, `read`, or
`write`. It never changes the meaning or route of an intrinsic instruction. Proxy objects advertise
their service-owned class and failure model; they cannot masquerade as a hardware-owned object or
inherit a hardware latency bound.

Hardware-owned and service-owned objects therefore share capability, lifetime, transfer, and
observation laws without sharing execution routes. Hardware-class typed functions always execute in
the anonymous substrate. Service-owned methods always cross an explicit capability boundary.

**Containers and nested personalities.** A container is a governing domain: its MachineView,
ClockView, authority universe, CPU/memory/object budgets, placement envelope, lifetime, accounting,
observation endpoints, and descendant-creation ceiling are architectural. Filesystem, mount, network,
identity, device-policy, and foreign process-model namespaces remain explicit service capabilities.
A Linux personality may map a container to one governing domain, a process to a child domain or
activation group, a thread to an activation, a cgroup to domain budget/accounting policy, and an fd to
a capability-backed compatibility object. The exact process/domain granularity is software policy.
This division makes isolation and resource ownership native without putting Linux nouns or syscall
interception in silicon.

**The reset grant is the first domain's parent.** It runs the same closed publication transaction an
ordinary parent runs: it binds MachineView and ClockView, creates the budget sub-account, installs
capabilities in the same capability table schema, and publishes one ordinary Domain. The first
Domain is quiesceable, state-streamable, budgeted, and debuggable,
distinguished only by the quantity of its grants. All authority descends from this unaddressable
parent by the same explicit delegation used at every later depth; there is no root-only manifest,
object kind, discovery path, or driver contract.

The reset controller is also the reaper of the last live parentless Domain. Its death triggers the
same reset-and-remint sequence before reaping; it does not create an architecturally distinct recovery
mode, checkpoint, or authority fountain (§2.1).

**Engine-side accounting.** All engine-held state is charged to the domain that caused it: epoch cells
to the domain(s) whose entries reference them (`referent_count`-shared), continuation frames to the activation's
domain, thread-directory entries to the thread's domain, park records to the waiter's domain. There is
no unaccounted allocation and no ledger of last resort — that ledger is only needed where ambient
authority creates unattributable costs, and this machine has none (§16.4 bounds each charge).

### 11.1 The engine-op calling convention

Each op takes every fixed semantic operand in register slots or through a typed builder/object. Each
writes `rd` = a non-negative result on success or **`-CONDITION`** on failure; capability and checked
argument errors return conditions rather than direct faults (§9.1).

**There is no argblock escape hatch.** A chip-decoded memory operand may designate only variable
transferred data, a homogeneous element sequence, an architectural context, an event-record
destination, a state-stream buffer, or a hardware work descriptor. It may not supply fixed semantic
operands merely because they do not fit in one instruction. When fixed operands do not fit, the ISA
must split independent facts into named instructions, use an unpublished builder where atomic
publication is required, add a profile-justified fused common form, or introduce a typed reusable
object. Every pointer operand carries one of the closed §17.4/`isa_spec.json` memory roles.

**Snapshot rule for admitted descriptors and sequences.** Where an instruction accepts a work
descriptor or homogeneous sequence, the engine snapshots and validates the complete bounded input
before its first effect. Concurrent mutation after that snapshot does not affect the operation. An
unmapped pointer returns `-FAULT`; malformed variable data returns `-MALFORMED`; both precede effects.

**Completion and ordering (the asynchronous-issue license).** Engine ops are architecturally
**synchronous**: by the time any consumer observes the op's `rd`, it holds the final result. An
implementation **may** issue an engine op and continue executing younger instructions before it
completes (a scoreboarded `rd`), provided the overlap is unobservable: **program order among ops** (same
thread's engine ops take effect in program order); **`rd` interlock** (any read of the op's `rd` stalls
until the result lands); **memory ordering** (the op's memory effects order against the issuing thread's
own accesses as if it completed at its program-order position, §6); **blocking is unchanged** (an op
that must wait parks the thread at that instruction; the license covers only completion latency, never
the waiting); and **machine-call boundaries stay precise** (§9.3 delivery observes every in-flight op as
fully complete or cancelled/parked; `OP_RESTARTABLE` semantics unchanged). No encoding distinguishes
eager from scoreboarded completion; conforming software cannot detect which it is running on.

**Domain-local resource authority.** `mmap`/`map.protect`/`munmap_range`,
and the futexes (§6), name no capability because they act on the **current domain's own budget**: the
domain *is* the authority. They allocate from, and are bounded and accounted by, the running domain's
memory/object/scheduler reservation (set by its creator); exhausting the budget or violating its policy
returns `-EXHAUSTED`/`-DENIED`, never reaching outside the domain. Operations that touch *another*
domain's resource, or a backing object, **do** name that capability — and the address-space ops have
exactly that target-directed form: the **AS facet verbs** (`as.map`/`as.unmap`/`as.protect`/
`denum.begin(..., MAPPINGS)`, §11.2, §16.1), the same operations authorized by a right on the *target's* domain
capability. The bare opcodes are the fused self-directed spelling; the facet is the same doctrine
applied to an explicitly named target, not a second mechanism or a slower class of citizen.

### 11.2 Memory

**There is no engine allocator (`alloc`/`free`) — and there may never be one.** The verdict,
recorded here because proposals recur: a zero-filled bump/region allocator with exact-pointer
`free` fails §16.2's own
tests — exact-pointer `free` requires engine-recorded per-allocation lengths (independent state,
so not an adapter), and as an independent primitive it names no admission leg (§16.2) — it is a
malloc object model in silicon, the "library over a word" the admission rule refuses; the
claimed cheap-heap hot path is served by the fused anonymous `mmap` below at identical dynamic
instruction count. `0xb1` is `ENC`-reserved (Appendix G). Ordinary allocation is therefore:
the userspace allocator owns the hot path, anonymous `mmap` (`backing = 0`, §2.2) is the slow
path, `munmap_range`/`map.discard` are the return paths. **`mem_grant` 0xb2
`(rd, addr, len, rights)`** mints a **memory-range capability** naming `[addr, addr+len)` of the
caller's *own* address space, with `rights` no wider than the caller holds there. It is **O(1) and
copy-free** (a capability-table entry referencing the existing VMA — no allocation, no data movement),
and it is what makes `gate_call`'s "pass a memory capability" cheap for an arbitrary buffer, so passing
bulk data never requires create+map+copy. The caller must actually have the range mapped with at least
`rights` (else `-DENIED`/`-FAULT`); `addr+len` is overflow-checked (§1). The grant is a normal revocable
capability (its own lineage cell, §3), so the caller can `cap_revoke` it after the callee is done.
The zero-fill guarantee is observable, not constructive: zero pages, ownership epochs, fresh
encryption keys, lazy initialization, or eager stores are all conforming. Executable and physically
contiguous storage use the separately authorized `backing.code` and `backing.contig` constructors.

The `mapping` family at `0xb3` provides unpublished construction for a live mapping:

```text
map.new        rd, backing, backing_offset, length
map.private    rd, builder
map.shared     rd, builder
map.anywhere   rd, builder
map.at         rd, builder, address
map.noreplace  rd, builder, address
map.reserve    rd, builder, reservation_policy
map.home       rd, builder, home
map.leaf       rd, builder, leaf_class
map.growdown   rd, builder, limit
map.type       rd, builder, memory_type
map.protection rd, builder, protection
map.constrain  rd, builder, dimension, relation, bound
map.prefer     rd, builder, dimension, relation, bound
map.seal       rd, builder
map.abort          builder
```

Builder references use the §16.1 generation-threading rule. Before `map.seal`, no mapping is visible
and the builder is nontransferable. Seal atomically validates address placement, backing bounds,
mapping type, W^X and alias compatibility, shared/private semantics, home/volume closure, large-leaf
requirements, resource admission, and relevant epochs. Failure publishes nothing and leaves the
builder retryable unless builder-fatal; success consumes it. Implementations may mutate private state,
record deltas, normalize, or fuse the sequence.

The fused common form is `mmap rd, backing, backing_offset, length, access`. It selects an address,
derives memory type from the backing, homes near the caller, and creates a private, ordinarily
reserved, base-leaf mapping. `backing = 0` means anonymous memory (§2.2). `access` contains only
R/W/X/GUARD permission bits. It is normatively the adapter for `map.new` + `map.private` +
`map.anywhere` + `map.protection` + `map.seal` and owns no independent transition.

Private/shared is one closed mapping relation; anywhere/at/noreplace is one placement relation.
Reservation, home, leaf class, stack growth, type, protection, and placement constraints are
independent builder facts.
`map.populate rd, address, length` performs eager residency work only after publication.
**`map.constrain`/`map.prefer` are the placement-property facts (§15's tier system):** each names
one published tier dimension — the fixed enum **`0 LATENCY_CLASS`, `1 BANDWIDTH_CLASS`,
`2 PERSISTENCE`, `3 FAILURE_DOMAIN`, `4 DEVICE_ACCESSIBLE`, `5 MIGRATION_COST_CLASS`**
(`6`–`63` reserved) — a relation — the fixed enum **`0 LE`, `1 GE`, `2 EQ`, `3 NE`**
(`4`–`15` reserved) — and a bound in the tier table's view-local units. `map.constrain` facts are
**required** — `map.seal` fails `-EXHAUSTED` when no admissible tier satisfies them all (the
admission-time refusal, never a silently worse placement) and `-MALFORMED` for an unknown
dimension or ill-formed relation; `map.prefer` facts are ordered preferences and never cause
failure. Both are repeatable builder facts under the §16.1 generation-threading rule; `map.home`
is the spatial preference of the same system, kept as its own fact for the common case. The
solved tier is published at seal as an observable result (§15).

**Where memory lives is as fundamental as how big it is (Law 8).** `map.home` names a
view-tile-group in the caller's MachineView coordinates, never a physical coordinate; the default is
near the calling thread. The resulting locality class (§15) is fixed at publication, and a home
outside the domain's volume is `-DENIED`.
`map.protect` 0xb4 `(rd, addr, len, protection)` changes access authority, **never memory type,
backing, or translation granularity**. `munmap_range` 0xb5 is `(rd, addr, len)`.
`map.demote` 0xb6 `(rd, addr, len)` losslessly rewrites a large-leaf mapping into base-page
granularity, including residency, charging, dirty state, leases, COW relationships, and pager
granularity. It has its own rights, cost, serialization, and completion row.

**`map.discard rd, addr, len` — release the frames, keep the address space (the
GC'd-heap verb).** Every collected runtime returns heap to the system on exactly this path — drop the
physical frames, keep the VA and the mapping so there is no unmap/remap churn — and making a
runtime be its own pager for what is a *hint* would drag in the §15 liveness rules for nothing. So
over anonymous private memory, `map.discard` **discards contents by declaration**, drops
the resident frames, **refunds each frame's recorded charge mechanically** (the §15 per-frame
account — `map.discard` is the *voluntary* form of the refund `EVICT` performs coercively), and
preserves the VMA, its protections, and its epoch identity; a later touch faults in as
**zero-fill**, exactly like first touch. Invalidation is the ordinary path (VMA cell bump +
broadcast — frames are being freed, so the translations must die; there is no cheaper honest
form). Bounded by the handed-in range (class 4). **Scope, deliberately tight:** object-backed or
shared mappings answer `-UNSUPPORTED` — discarding *shared or backed* dirty data is a truth
decision, and truth decisions belong to the backing's pager (`EVICT`), never to a hint.
**`map.reclaimable rd, addr, len` exists exactly where the truth argument is vacuous — the doctrine's
boundary drawn at who owns the frames, not at the verb:** on anonymous, private,
**engine-backed** mappings the engine already owns residency truth outright, so it marks pages
**reclaimable-clean**: the engine **may harvest them under memory pressure at any moment**
(refunding the per-frame charge *at harvest*, mechanically, on the existing account), a read may
legally find the old contents until harvest (the state is declared, so the nondeterminism is
licensed — Appendix E), a **write cancels the mark** and the page is ordinary again, and a
post-harvest touch is zero-fill first-touch. One owner of truth throughout. On pager-backed or
shared memory the lazy form stays **refused** — there "maybe reclaimed" would be a second source
of residency truth, and that path is already the real thing: a pager-designated backing plus
`accessed.begin` aging (Go's scavenger and the jemalloc/mimalloc purging tier are the two recorded
witnesses; both get exact `MADV_FREE` semantics from `map.reclaimable`, and graduation to pager-backed arenas
remains the answer for policy richer than "under pressure"). **W^X is architectural, and it binds the *backing*, never merely the page-table entry** —
PTE-level W^X with dual mapping still available is RWX with extra steps, and dual mapping is the
*standard* JIT workaround, so the rule closes the alias hole: **a backing may not be
simultaneously writable-mapped anywhere and executable-mapped anywhere — across mappings, across
domains — unless the backing carries the `JIT_ARENA` attribute**; `mmap`/`map.protect` reject the
transition that would complete the forbidden pair `-DENIED`. `JIT_ARENA` is **immutable, set at
the backing's creation** (`mmap` flags **bit8 `JIT_ARENA`** for anonymous backings, the factory
equivalent for created ones, §17.8), **and mintable only by a domain whose dominator granted the
`JIT_WX` grant** (§17.7 `djit` — the typed builder fact licenses *minting arenas*, so the
exception is **arena-scoped, never domain-scoped**: a JIT's code space is eligible; its heap
never becomes eligible by cohabiting the domain). JITs without an arena use the write-then-execute sequence
(`map.protect` W, patch, `map.protect` X), never a permanent RWX page; the successful W→X transition is the
complete publication transaction (§6), so no trailing `isync` is used. The cross-domain
compile-service pattern (writer domain, executor domain) needs the arena attribute like any
other dual mapping — cooperation is not a loophole.

**Invalidation is a hardware broadcast keyed on the VMA's epoch cell, with the epoch check as backstop
(§3).** `map.protect` and `munmap_range` **bump the VMA's cell** and issue a **hardware invalidation
broadcast over the coherence interconnect** (a DVM-class message, the mechanism ARM ships for TLBI),
keyed on `{domain-tag, VA-range}` — not a scheme where every TLB entry coherently tracks a counter
line. Peer MMUs receive the targeted invalidate over the fabric that carries coherence snoops and drop
matching entries; there is **no software cross-core IPI**. The **cell is the architectural freshness
token, not the transport**: each cached translation records the `{domain-tag, epoch}` it was filled at,
so (a) the broadcast can be **coalesced** (many VMA changes, one bump) and (b) a straggler that missed
a message still fails its epoch check on next use and **re-walks** to the current permission or a
fault — the check is the backstop, the broadcast is the fast path. **And the backstop's cost has a
named exit (`FILL_TIME_EPOCH`, Appendix E):** an implementation whose invalidation protocol
discharges the Appendix F refinement obligation — proven: no stale translation survives the
acknowledged broadcast — **may check epochs at fill time only**, carrying zero per-access epoch
cost. A runtime compare becomes a verification-time proof obligation; the datapath tax rounds to
one extra tag compare on a structure that already does tag compares. The honest claim is narrow: LNP64
replaces the x86 software-IPI shootdown with a **hardware broadcast invalidate + an epoch backstop**;
it does not claim "zero invalidation traffic," and it is the proven DVM model. The op returns once the
broadcast is **acknowledged by all coherence participants** (a bounded interconnect round-trip); from
that point no core can *use* a stale permission. **The broadcast's reach is the owning domain's
volume, never the machine (Law 8, §3):** only tiles inside the VMA's domain volume can have cached
that translation (a `far` mapping is unconstructible, §15), so the message fans out over the volume
(a spanning-tree reduction is the existence construction, §1.1's rule — the bound is what is
normative) — **invalidation latency is O(the owning domain's diameter), never O(the machine's)**, and `INVALIDATION_ACK_BOUND` is
**parametric in that diameter**: the `GEOMETRY` field states the bound for the *answering
MachineView's* volume (view-answered like every geometry fact, so a domain reads the bound for its
own diameter), and a deeper, smaller domain gets a strictly tighter bound — the depth invariant's
physical corollary, pointing the same direction. The fence recourse inherits the scope: the fence
engages at the volume's boundary, which is nearby, not the machine's. **Physical-page reclamation** after `munmap` is safe
once that acknowledgement completes — no surviving translation can name the page (in-flight DMA is
separately drained via the `quiesce` bump policy, §15). **The acknowledgement is only sound if every
translation consumer participates**, so the contract names them: (i) data **and instruction** TLBs
honor the invalidate; (ii) at a permission *downgrade* the core squashes speculative walks and drains
outstanding memory ops on the old translation before acknowledging (an upgrade need not); (iii) a
parked/offline core holds no cached translation (acknowledges immediately) or is drained on wake; (iv)
IOMMU / device translations honor the same broadcast on the DMA-window path, escalating to the
`quiesce` policy for in-flight DMA before frame reuse. The bump is not acknowledged until all four
classes have. **Two rules bind all four classes beyond the invalidate itself.** *Negative
entries:* a consumer may cache the **absence** of a translation only if every install covering
that range (`mmap`, `AS_MAP`, `SUPPLY`, `REMAP`) demonstrably invalidates the cached negative —
otherwise a stale *deny* outlives the mapping it denies, the stale-permission bug's mirror image;
an implementation that cannot demonstrate install-time negative invalidation **caches no
negatives**. *Interior walk caches:* shared lower radix nodes (the COW-root sharing, §15) are
**never mutated in place — a split copies the shared interior** (persistent-structure
discipline, which the O(1) clone semantics already require), so a cached interior node is never
wrong, merely superseded, and "translation consumer" covers walker caches of interior nodes
with no protocol beyond this contract. **Acknowledgment is a liveness obligation with an architected recourse — a wedged
participant cannot wedge the machine.** Two bounds, because coherence-fabric participants and
translation-caching devices are different problems: **`INVALIDATION_ACK_BOUND`** (tight — cores,
TLBs, IOMMU walk paths) and **`ATS_ACK_BOUND`** (device-class — inherited *only* by operations
whose range is mapped into an ATS-granted device window; both `GEOMETRY` constants in ticks). **The
recourse is scoped to device-class participants**: a device that misses its bound is fenced —
translations cut at the fabric ingress, its windows' cells take the **`poison`** disposition
(fail-closed forever: in-flight submissions complete with fence-synthesized `-POISONED` records,
waiters see `HANGUP`, and fresh window construction by the authority holder is the only path back — a device
that missed one invalidate cannot be trusted to have honored any). **The recovery choreography is
architected end to end, not left at the fence:** `poison` (fabric fences the device, windows
fail-closed) → **function-level reset** issued through the bus service's config-space capability
(§15 — the same root-authority BAR cap that enumerates the device drives its FLR) → construct and
`window.seal` fresh windows against the reset function. The RAS story therefore has a defined shape from the
missed acknowledgment through to a working device again, rather than stopping at "poisoned forever." **The ordering is normative and
closes the stale-traffic window at fence engagement, not at bound expiry:** invalidate issued →
bound expires → **fence engaged at the fabric ingress → the fence itself acknowledged by the
fabric → only then does the op return and reclamation proceed.** Between issue and fence-ack a
stale posted write can legally land (PCIe's own ATS timeout has the same window); it is harmless
*because* frame reuse gates on fence completion — an op that returned at bound-expiry with the
fence merely initiated would be a use-after-free exactly one posted-write deep, and is forbidden.
A **core-class** participant that fails to acknowledge is *not* this mechanism's business: that is
machine-check territory — a RAS event with its own **reserved seam** (`CORE_CHECK`, named here so
core failure handling cannot silently ride the device recourse; severing a coherence participant
strands every thread scheduled there and must be designed as the RAS action it is). The
invalidation op completes with the straggler fenced: **the acknowledgment the op waits for means
"no participant can use a stale translation," and the fence establishes that without the
participant's consent.**

**Memory-error choreography (ECC poison → the parties who can act), designed by composition —
the RAS path for *frames*, filling the gap between the device recourse above and the `CORE_CHECK`
seam.** An uncorrectable memory error is a fact about a **frame**, and every structure needed to
route it already exists: the frame's **per-frame charge record** names the account (§15), the
**reverse map** names every mapping, and the **page-request record** already carries a kind
field. The choreography, end to end: the memory controller reports the frame → the engine marks
the frame **poisoned** (a frame-metadata bit, the accessed-bit precedent) and bumps every mapping
VMA's cell via the reverse map (the `EVICT` machinery — consumers can no longer reach the frame
through any cached translation) → a subsequent access faults **synchronously with the poison
cause** (§9.1 — precise consumption where precision is possible; a detected-in-scrub error never
waits to be consumed) → if the backing has a designated pager, the pager receives a page-request
record of **error kind** for the offset (a clean copy elsewhere means `SUPPLY` re-homes and the
fault was a page fault with a longer story; no copy means the pager propagates the loss on its
own policy) → the frame itself is **retired**: `EVICT` refunds its charge and the frame never
re-enters any allocator (retirement is the poison disposition applied to physical memory).
**A poison event carries four distinct responsibilities, and the delivery-targeting corollary
routes each separately — one delivery mechanism, four deliveries, because "the accessor
decides" would let one arbitrary thread decide global fate for a page other domains share:**
- **Instruction responsibility — the accessor:** each toucher takes the **synchronous poison
  machine call** at its own access (FAULT gate, poison cause, faulting address). This delivery
  answers only "what does *this thread* do about *this access*" — it never adjudicates the
  page.
- **Backing/data responsibility — the backing's owner:** for pager-designated backings, the
  pager's error-kind page-request record (above). For engine-backed memory the implicit
  responsible party is the **backing's owning domain** (the creator / charge-default holder),
  which receives **one coalesced backing-local poison record** — an event delivery, not one per
  toucher — and *it* alone decides the data's fate by its **registered recovery disposition**:
  `SUPPLY`-shape replacement (re-derived contents), explicit **zero-fill** (declared
  reconstructible), **preserve-poison** (let accessors keep faulting, the honest default for
  irreplaceable data), or terminate. Registration rides what exists: a pager-capable backing
  registers it through its typed pager relationship; engine-backed anonymous memory registers it against the
  domain's **`MEMORY_ERROR` event — number 63, assigned now, not reserved-by-name**, because a
  numbered event participates in the mask, pending bits, disposition table, serialization, and
  every routing test — its number *is* frozen ABI the moment software is told to register a
  disposition for it (and the assignment freezes the convention with it: **architected event
  numbers grow downward from 63; numbers upward from 0 remain software's** — the two-ended
  allocation rule the opcode map already uses). **The event is a doorbell; the truth is engine
  state — which is what makes the records undroppable without pretending a queue is
  infallible:** each poisoned frame carries at most one live **incident** (id = the frame's
  poison generation), incidents are indexed per backing/per domain and enumerated by
  **`incident.begin`/`cursor.next`** as the frozen **64 B `MemoryIncident` event record** (§17.7) —
  offset/range, error kind and severity, poison generation, contents-lost, shared-mapper,
  retirement-complete, disposition in effect, incident id — cursor-paged (§16.0; a concurrently
  added incident may appear in this traversal or the next, but no unacknowledged incident may
  be omitted from every traversal), acknowledged **idempotently by incident id through
  `incident.ack`** — an explicit consuming op, because observation is
  pure everywhere and stays pure here. A record can never be silently lost because it
  is *derived* on every drain from the frame truth, not buffered fallibly beside it; masking
  event 63 masks the doorbell and nothing else; overflow does not exist (the incident set is
  bounded by poisoned frames, which are bounded by memory). A frozen or dead owner changes
  nothing the substrate does: **propagation to sharers and frame retirement never wait for
  software**, incidents persist for whoever succeeds the domain, and recovery action operates
  on the *logical* page after the invalidation broadcast — it composes with, and never waits
  on, physical retirement (the record's retirement-complete flag is information, not a gate).
  **Absent a registered
  disposition, poison consumption is
  domain-fatal** — fail-closed, the unhandled-fault rule, never silent zero-fill (invented
  zeros are corruption with a clean conscience).
- **Physical-frame responsibility — the substrate:** retirement is the engine's act, gated on
  the same full invalidation acknowledgment + DMA quiesce as any frame reuse (§11.2 — a
  poisoned frame is torn down with the ceremony of a live one, precisely because some device
  may still believe in it), and the frame never re-enters an allocator. Propagation to sharers
  is likewise the substrate's and **unconditional** — every mapper's next access faults poison;
  a truth about physics is not a policy.
- **Resource-policy responsibility — the charged party and the dominator:** the charged
  domain's residency truth changes through the ordinary accounting (the frame's refund at
  retirement), and a domain death escalates through the lifecycle waitable its dominator
  already holds — succession, not a new error plane. **The refund is accounting, never the
  error report** — the charged party and the backing owner can be different domains, and a
  budget counter moving explains nothing; the report is the owner's incident record above,
  which is the non-droppable one.
Persistent-memory
and device-memory backings follow the same route with the bus service standing where the memory
controller stands. Nothing here is a new machine: it is the pager protocol, the reverse map, and
the poison discipline meeting at a frame — which is exactly why it is designed now rather than
reserved, the composition being cheaper to freeze than the folklore it prevents.

**The AS facet — the target-directed form of the address-space ops (§11.1's doctrine, cashed in).**
`as.map`/`as.unmap`/`as.protect` (declared facet verbs, catalog `cost_model.protocol_verbs`; §11.2) perform `mmap`/`munmap_range`/
`map.protect` semantics against a *dominated* domain's address space, authorized by the **`MAP` right
(bit3) on the target's domain capability** — the same mapping transition, validation, and
the same invalidation broadcast (keyed on the *target's* domain-tag) as the self-directed opcodes;
the engine already does all of it, and the facet adds only the authority check on the target operand.
The rules that make it sound: **(a)** the **target's** W^X/JIT policy governs, never the caller's —
a JIT-privileged dominator cannot map RWX into a hardened child; **(b)** the mapped pages charge the
**target's** memory budget (`-EXHAUSTED` against the target); **(c)** the backing capability
validates against the *caller's* table (handles are per-domain, §2.1), but the installed VMA takes
its **own strong reference** to the backing (§11.2), so the
caller dropping its handle never orphans the target's mapping; **(d)** the facet is **legal on a
running target**: the broadcast + epoch backstop above is precisely the concurrent-mutation
contract, and no quiescence is required (unlike prospective `dview`/`dservice`, which establish
publication-time configuration rather than mutating a live instruction route); **(e)** and the facet
answers every `MAP`-right holder on every
domain, always — **no birth flag closes an address space to its dominator chain** (Appendix H:
introspection is authority, §16.3, and the authority is never revocable-by-the-inspected).

**Address-space enumeration** is the facet's cursor read side and the missing read half of the §16.4
accounting doctrine: a dominator charged for a subtree's residency must be able to enumerate what it
is being charged for — engine truth, never a software mirror. It returns per-VMA records
`{range, prot, memory type, backing reference + offset, charge account, resident/dirty counts}` in
the §16.0 `{version, length}` framing, bounded per call. The root-mutation cell makes the cursor a
consistent traversal of VMA topology and structural metadata only. `resident` and `dirty` are
independently sampled when each record is emitted; faults, writes, writeback, and eviction do not bump
the root merely to make those counters snapshot-consistent, and records from one enumeration need not
share an accounting instant. **The two foreign-capable fields are
namespaced — view closure binds here like everywhere:** the **charge account** is the charged
domain's subtree-scoped ID when it lies within the *target's* subtree, else the reserved value
**`FOREIGN`** (all-ones — a first-toucher outside the enumerator's authority is a fact it may
*count*, never *name*); the **backing reference** is an opaque AS-local cookie (equal cookies =
same backing within this address space — enough to group `smaps`, never a foreign object name).
Enumeration paginates with a **resume cursor**: an opaque token stamped with the address-space
object's embedded **root-mutation cell** `{cell, epoch}` (§3). Every committed mutation that changes
the VMA tree or any enumerated VMA metadata bumps it: `mmap`/`map.protect`/`munmap_range`, their
`AS_MAP`/`AS_PROTECT`/`AS_UNMAP` facets, `dreplace.commit`, and engine VMA split/merge/demotion operations
performed on behalf of those verbs. Residency/dirty/accessed changes that only alter counters reported
as live observations do not bump it. Thus an enumeration whose underlying AS mutated
fails `-STALE` rather than returning a franken-snapshot — §3 applied to iteration, fail-closed like
every other stale read. It requires the **same `MAP` right as the mutating ops**:
enumeration is authority, full stop — and like all inspection authority it is never
birth-revocable (Appendix H). `obj_cap = 0` (§16.2) gives the self-directed
form. This one sub-op is what address-space introspection surfaces (`/proc/PID/maps`, `smaps`,
per-VMA accounting, checkpoint pre-dump) compile from, with no shadow bookkeeping anywhere.

### 11.3 Objects, capabilities, domains

The `cap` (`0xa9`), `domain.build` (`0xaa`), and `domain.exec` (`0xab`) families are
fixed-form typed instructions. Hardware-object classes use the dedicated opcodes `0xbb`–`0xc8` and `0xcf`;
sets, cursors, state transport, observation, and lifecycle use `0xca`–`0xce`. The opcode and
function select one register schema; no instruction fetches an operation name, version, argument
catalogue, capability array, or output array from memory.

The capability algebra is:

```text
cap.copy    rd, cap, rights
cap.move    rd, cap, destination, rights
cap.narrow  rd, cap, rights
cap.revoke         rd, cap
cap.revoke_cancel  rd, cap
cap.revoke_wait    rd, cap
cap.revoke_poison  rd, cap
cap.weaken  rd, cap, weak_class
cap.upgrade rd, weak_ref, proof
cap.seal    rd, cap
cap.restamp rd, stamped_cap, new_gate
cell.repoint.prepare rd_token, cell, expected_target, new_target, deadline
cell.repoint.commit  rd, token
cell.repoint.abort   token
```

Copy and narrow are monotone. Move commits receiver installation and source consumption atomically.
The four revoke mnemonics are the §3 lineage-cell transitions: acknowledgement-only, cancellation of
blocked users, quiescent drain before return, or permanent poison. They have separate rights,
completion, and reclamation rows rather than a runtime policy selector. Weaken creates a
non-lifetime-retaining observation reference;
upgrade succeeds only while the named identity, lineage, and fixed proof remain live. Restamp repairs
one service-relationship cell. Cell repoint conditionally changes exactly one epoch-cell target and
accepts no orchestration plan. **And its atomicity is volume-scoped by construction (Law 8):**
prepare/commit execute at the cell's home, and the exactly-once guarantee is the home volume's — a
succession that spans volumes or machines is a software lease/consensus protocol *composing*
per-cell atomic repoints with device fencing (§16.8's composition is the worked witness); no
instruction performs a universally atomic cross-volume handoff, because that would be hidden
fabric consensus, exactly the unbounded distributed work §16.4's bounded-time contract forbids an
instruction to contain. Opcodes `0xad` and `0xae` are `readv_at` and `writev_at`;
opcode `0xaf` is reserved (§1.1).

Slot replacement lifetime is the independent builder fact `dslot.persist` or
`dslot.drop_on_replace`. Transfer behavior is selected only by the operation: `cap.copy`/`dgrant`
copy and `cap.move`/`dmove` move. There is no packed slot-policy word and no latent
move-on-transfer bit. Failed transfer changes neither side.

Domain creation and executable-state replacement use unpublished builders (§16.1). Hardware-object
construction uses each class's fixed constructor or typed builder (§17.7). A `target = 0` self
sentinel exists only where a particular function explicitly admits it. Reserved functions fault as
illegal instructions; a known function with the wrong capability class returns `-BADREF`.


### 11.4 Devices, machine description, entropy

**Devices / DMA (crisp split: typed window instructions own authority, `send` owns transfer).** A DMA
**window** is built privately by `window.new`, `window.scope`, `window.device`, the **declared
addressability fact `window.pin`** (pinning is *one* addressability form, stated as an explicit
builder fact rather than implied by establishment — v1 admits exactly this one value, and the
faultable form is the Appendix G PRI/PASID seam's second value of the *same* fact), and optional
`window.ats`, then published by `window.seal`. Scope fixes the backing/range/direction; device binding
fixes requester identity and the caller-created CompletionQueue. Seal admits the declared
addressability fact — for `window.pin`, pin admission — and
establishes the IOMMU relation atomically; a builder that declared none fails seal `-MALFORMED`; `lifecycle.destroy` ends a live window (its class-defined teardown obligations: fabric fence, drain, pin release) and `window.abort`
ends an unpublished builder.
An established window mints separately typed `DMA_COPY_SUBMIT`, `DMA_FILL_SUBMIT`,
`DMA_COPYV_SUBMIT`, and `DMA_COPY_HASH_SUBMIT` facets. `send` to one of those facets (§15,
§16.0) submits exactly that transformation over the already-established window; it does not mint or
reconfigure the window's
authority. (Routing all authority-sensitive setup through typed window operations keeps one accounting/rights
model; the window's `send` facet is the ordinary data-plane operation, per the §16.6 control/data split.) Long transfers complete
through the window's hardware-producer completion endpoint (a waitable). Device registers are
**device-BAR capabilities** — memory-range capabilities over `device_ordered` register
apertures, **minted whole at the reset grant** (§2.1) **and carved thereafter as `mem_grant`
sub-ranges of a held BAR mapping** (§11.2; §15's doorbell-granularity delegation). **There is
no separate BAR-minting operation**; an aperture no capability covers is unreachable forever.
Registers are `mmap`'d `device_ordered`; interrupts are interrupt-as-waitable objects.

**Machine description: `env_open` 0xb9 `(rd_stream, selector)`** opens a typed read-only byte stream.
The selector chooses only one frozen description schema; `read` is the sole data operation, and the
stream cannot request administrative action. By Law 7 the stream describes the domain's MachineView
(§16), definitionally: ISA version, page and
cache-line size, implemented VA width, topology/coherence records *as the view states them*, feature
bits (the §17.6 `FEATURES` record), object profiles, `GATE_INLINE_MAX`, startup-metadata pointer, and the
visible timebase frequency. There is no gated selector and no `-DENIED` path for machine description:
`env_open` never reads the machine — it reads the view, and always succeeds (§8.3). **A `FEATURES`
bit is what this *view grants*, never what the chip has** (§1's one-conformance-class rule): no
physical LNP64 lacks anything, so a clear bit is a parent's decision about a domain (confinement,
migration-under-emulation), a parental-control surface, not a portability surface. The first stream
bytes are the fixed 16-byte `{record_type, version, length}` header, followed by the selected body.
Ordinary short reads and end-of-stream rules apply; no retained output pointer or selector-dependent
writeback exists. Framing and bodies are §17.6 and transcribed in `isa_spec.json`.

**`random` 0xba `(rd, out_ptr, len)`** fills the buffer from the CSPRNG-backed source and returns
**exactly `len`** on success or a condition (`-WOULDBLOCK` only if entropy is not yet seeded, never
weak bytes); it never returns a short positive count, so callers do not loop.

### 11.5 Atomic executable-state replacement

`dreplace rd_builder, domain` creates an unpublished DomainBuilder whose prospective state
is a replacement for the named domain's executable state. The loader parses the executable format
and emits ordinary `dmap`, `dprotect`, `dhome`, `dgrant`, `dmove`, `dentry`,
`dstack.new`/`dstack.use`, `dgates`, and `dabi` operations. Each instruction names one architectural relation;
there is no chip-decoded image plan or replacement descriptor.

`dreplace.commit rd, builder` enters the target's full quiescence boundary, revalidates all staged
mappings, authority, views, entries, stacks, and resource admission, and atomically publishes the
complete executable-state replacement. Success consumes the builder, retires old activations and
continuations according to the selected fixed mode, preserves the domain incarnation and explicitly
selected persistent authority, and starts the replacement entry. Failure leaves the old state
runnable and the builder retryable unless the failure is builder-fatal. Staged moves commit only with
publication.

The replacement mode has a small fixed meaning: whether existing persistent capability slots survive,
whether inbound calls are rejected or drained, and whether a replacement activation starts dormant or
runnable. It does not select a record schema. A required MachineView is added with `dview`; startup
capabilities use `dgrant` or `dmove`; a retained mapping must be restated against a surviving
backing. No mapping, register image, gate, stack, or startup slot carries over implicitly.

This primitive also supports hot code replacement and transactional rollback. “Exec” remains a
personality-level software workflow built from executable parsing plus this builder sequence.


## 12. Hint fields (forward-compatible, ignored in v1)

The I `[13:0]` and S/B `[8:0]` hint zones carry compiler-known facts that a future microarchitecture
may use for timing only. An implementation may ignore them; they never affect architectural state, so
the same binary is correct on v1 and on a later out-of-order/cached implementation.

**The v1 hint catalog (bit assignments frozen here — an unfrozen hint is an unemittable hint).** All
fields default to 0 = "no information"; unassigned bits are reserved-zero (a v1 decoder ignores the
whole zone either way, but emitters must write zero so future assignments stay compatible).

**The death-hint doctrine, stated before its bits (this sentence is what keeps the cluster from
becoming `dcbi`):** *death hints assert that a value's future reads, if any, need not be fast —
never that they need not be correct.* A read of a dead-marked register or line returns exactly what
it would have returned unmarked; an implementation may only have made it slower. Anything that
changes what a read *returns* is not a hint and does not live in this section — it is a semantic
op, explicitly encoded, somewhere else (the reserved `SPARSE_CONTEXT` policy, §17.5, is exactly
such a thing and is exactly not here).

*Branches (B-format `[8:0]`):*
- `[1:0]` **direction**: 0 none, 1 likely-taken, 2 likely-not-taken, 3 reserved.
- `[4:2]` **weight bucket**: 0 none, 1–7 = PGO probability octile (1 = barely biased, 7 =
  overwhelmingly biased). A static `__builtin_expect` with no profile emits direction + bucket 4.
- `[5]` **kill-rs1**, `[6]` **kill-rs2**: this is the last read of that source register — its value
  is dead past this instruction; a future out-of-order core may release the physical register at
  retire instead of waiting for architectural overwrite. Reads of a dead-marked register stay
  defined (the mark was advice).
- `[8:7]` reserved — **spoken for in spirit (`TRIP_COUNT`, reserved by name):** the loop
  trip-count class on backward branches (short / long / very-long buckets for a loop-stream
  detector) wants exactly these 2 bits; not assigned now (no consumer, and reserved bits move by
  revision), but named so nothing else squats in the branch zone's last field.

*Loads / stores (I `[13:0]` on loads, S `[8:0]` on stores; loads' `[13:7]` reserved):*
- `[1:0]` **temporal locality**: 0 default, 1 non-temporal / streaming, 2 last-use (evict-friendly);
  **on stores, 3 = dead-after-write** — this line will not be re-read *by this thread*: write back
  early, do not retain (on loads 3 stays reserved). **The licence is writeback/eviction timing
  only, and the line stays fully coherent-visible** — "not re-read by me" is never "not re-read by
  anyone": a device pulling the line through coherent DMA (the §6 ring-fill-then-doorbell shape,
  where `memcpy` into DMA buffers will emit this hint constantly) reads the stored data exactly as
  unmarked; the hint moved the writeback earlier, and may move nothing else.
- `[3:2]` **alignment promise**: 0 unknown, 1 natural, 2 16-byte, 3 64-byte (a lying promise is a
  performance bug, never a correctness event).
- `[4]` **no-alias**: this access provably does not alias any in-flight store of this thread — a future
  implementation may disambiguate early.
- `[5]` loads: **speculation-safe** (the location is dereferenceable regardless of control flow, so a
  future core may hoist/prefetch freely); stores: **will-fully-overwrite** — the store's line will be
  entirely written by this thread before any re-read, so no-write-allocate is profitable: do not
  fetch the line to merge (the safe, hint-only cousin of the zeroing-op gun — `memset`/`memcpy`
  bodies stop paying write-allocate fetches, and a wrong promise costs a fetch, never a value).
- `[6]` **kill-rs1** (the base register's last read; on stores `[7]` **kill-rs2**, the data
  register's last read — address and operand consumption are where most last uses sit, which is why
  the death bits live in exactly the formats that have zones).

*Atomics (`amo` family):* `[1:0]` **placement**: 0 none, 1 near-biased, 2 far-biased (the §6
far-execution contention hint), 3 reserved.

**The `kill` idiom (bulk and R-format death, blessed as an idiom, not an opcode).** ALU R-format has
no hint zone (its low bits are the subformat home and the opcode-growth reserve, and reserved-zero
faults — carving hints there is refused), so last-use-at-ALU-op and bulk-death-at-a-boundary get the
canonical encoding instead: **`ori rN, rN, 0` with hint zone `= 1` means "`rN` is dead."**
Architecturally a no-op (the value is unchanged; reads stay defined — the doctrine holds), decode-
eliminable, and a future core treats it as a rename-table release. Assembler mnemonic **`kill rN`**;
one encoding, versioned here, so the x86-zeroing-idiom lesson is applied deliberately instead of
emerging as folklore. **And the benefit bound, stated honestly because reads-stay-defined is the
non-negotiable half of the doctrine:** a kill never licenses discarding the only architectural
copy — a later read must still return the value — so hardware may release an *expensive*
representation (a rename mapping, a full-width physical register, §18 vector state) only while a
recoverable copy remains. On an ordinary rename core the win is therefore mapping-table and
physical-register *pressure*, not storage magic; the large wins are where the representation gap
is large (vector registers, the §17.5 save payload), and a core that finds no gap ignores the
hints at zero cost.

**Emission is now, silicon is later:** v1 in-order silicon decode-ignores every bit above; the
encodings freeze now so binaries can carry the marks before the out-of-order core that reads them
exists.

The catalog is deliberately small and additive: new facts take reserved bits by spec revision, never by
reinterpreting an assigned one.

## 13. Personality (Law 6: decoded semantics are personality-neutral)

**No high-level or personality-policy operation is an instruction, and no personality-defined
meaning is decoded by silicon.** The machine may use familiar systems names for mechanisms, but it
provides only machine-semantic conditions,
transfer classes, blocking policy, cursors, events, and unpublished builders — and a **personality layer**
(ordinary software: a libc, a compatibility service) maps an operating system's vocabulary onto
them. The concrete Unix mapping (error numbers, descriptor-flag semantics, signal numbering, the
process model) is the software specification `personality_unix.md`, not this document.

### 13.1 Conditions (the frozen error enum)

Every condition-returning op writes `rd = -CONDITION` on failure (§1). The enum is **frozen,
machine-semantic, and closed under this document** — named for what the machine knows, not what any
kernel called it. **Layout fact (a compiler contract): in any condition-or-nothing position, the value `0` is
reserved-nonoccurring** — `OK` is never negated, so a niche-layout optimizer may use `0` as the
discriminant, making `Option<Condition>` and `Result<u63, Condition>`-shaped types single-register
with no separate tag.

| # | Condition | Meaning (canonical producers) |
|---|---|---|
| 0 | `OK` | success (never negated) |
| 1 | `DENIED` | rights/policy insufficient (rights check, W^X, budget policy) |
| 2 | `BADREF` | reference names nothing: malformed/out-of-range index, empty slot whose current epoch matches, wrong class, or null where non-null is required |
| 3 | `STALE` | embedded slot-epoch, shared-lineage, binding, or thread epoch mismatch: the named incarnation changed or died (§2.2, §3) |
| 4 | `MALFORMED` | argument, descriptor, sequence, or stream fails its shape contract |
| 5 | `UNSUPPORTED` | well-formed but not provided: unknown sub-op/profile, op on wrong endpoint kind |
| 6 | `BOUNDS` | range wraps, length exceeds architected maximum (§1) |
| 7 | `OVERFLOW` | output exceeds supplied capacity; required size reported back (§11.4) |
| 8 | `WOULDBLOCK` | would block and blocking policy says don't (§10); entropy unseeded (`random`) |
| 9 | `INTERRUPTED` | a machine call landed at the blocking boundary (§9.3) |
| 10 | `CANCELLED` | cancelled from outside: teardown, revocation wake, chain cancellation (§3, §9.4) |
| 11 | `TIMEOUT` | deadline reached (`futex_wait`, the donation deadline — `wait` reports timeout as `rd = 0`, §10.3) |
| 12 | `EXHAUSTED` | a consumable or saturating resource cannot advance (budget/quota, counter generation, identifier space) |
| 13 | `NOSPACE` | bounded queue/table full (completion reservation, cap slots) |
| 14 | `BUSY` | a valid current state prevents the transition (optimistic compare, active registration, bounded execution concurrency) |
| 15 | `DEADCYCLE` | single-chain self-deadlock detected (§9.2 — a partial guarantee, see its disclaimer) |
| 16 | `FAULT` | checked buffer/pointer argument unmapped or protection-violating (§9.1) |
| 17 | `HANGUP` | peer/endpoint gone: closed channel, revoked device queue |
| 18 | `MSGSIZE` | message/record exceeds capacity or bound; boundaries preserved (§10) |
| 19 | `POISONED` | a reference or backing was declared corrupt/untrusted, including persistent-media failure (§3, §15) |
| 20 | `WITHDRAWN` | a previously provided mechanism, suite, or profile has been measuredly retired: well-formed, once serviceable, now permanently unavailable by an architected withdrawal (§16.9 suite retirement) — never `UNSUPPORTED` (which means *never provided here*) and never `DENIED` (which is policy against this caller) |
| 21 | `HWFAIL` | the executing hardware failed: a fabric link, engine, or memory device could not complete the operation (RAS event posted); distinct from `POISONED`, which declares a *referent* corrupt — `HWFAIL` says the *machinery* failed, and the referent's state is whatever the RAS record says |

`22`–`63` reserved. A personality maps conditions to its own error vocabulary **contextually** (one
condition may map to several errno values by op — that is the personality's knowledge, not the
machine's) and the mapping table lives in the personality document, never here.

**The evolution rule (frozen with the enum, so retirement never forces a lie).** Three clauses:
**(i)** an operation's producible condition set closes at the revision that introduces the
operation — a later revision may never add a new condition to an already-frozen op's producible
set, so a shipped binary's exhaustive match stays total forever; **(ii)** codes `22`–`63` are
assigned only to conditions produced by operations or sub-ops introduced with or after them;
**(iii)** finer failure detail rides the fixed diagnostic channels — the machine-call context
record (§9.3) and versioned records (§17.6) — never a new negative value on an existing op: the
primary category is the stable contract, the diagnosis is data. `WITHDRAWN` and `HWFAIL` exist
from v1 exactly so that feature retirement and hardware failure — two futures every
long-lived machine meets — never force a choice between mapping to a wrong category and breaking
clause (i).

**The `-HWFAIL` producer set (frozen with the enum, per clause (i), so the code never
exists without licensed producers).** `-HWFAIL` may be produced by exactly these families, and
by nothing else, forever:
**(a)** the completion records of engine activities and device transactions — every
`ActivityRef`-bearing submission class (DMA copy/fill/copyv/hash, WorkQueue submissions,
`gate.submit`) — when the executing machinery (a fabric link, an engine, a device controller)
failed after acceptance: distinct from `-POISONED` (a referent or fenced device declared
corrupt/untrusted) and `-CANCELLED` (an orderly abort);
**(b)** the backing residency and motion family (`SUPPLY`, `EVICT`, `backing.rehome`,
`backing.clone`, `map.populate`) on a controller or fabric failure mid-transaction — media
corruption stays `-POISONED`;
**(c)** the state-transport family (`state.open`/`state.import`/`state.commit`) on engine failure
mid-production — a failing import still retains nothing (§16.8).
`wait`/`recv` deliver records that *carry* the condition; they never produce it themselves.
Everything else is closed: CPU-local compute, loads/stores, mapping and protection ops,
capability ops, futexes, and the synchronous gate crossing never return `-HWFAIL` — a machine
failure beneath those paths is a RAS event and the §15 poison choreography, not a new condition
on an old op. Every RAS `-HWFAIL` posts its record on the ordinary §15 incident path so the
diagnosis rides the diagnostic channel, per clause (iii).

### 13.2 The personality decomposition (how an OS surface lowers)

Every operating-system operation is a typed hardware operation, a `gate_call`/`dcall` to a service,
an endpoint operation, or pure software:

- **Object metadata** (file attributes, ownership, timestamps): typed service protocols on the object cap
  (§16.5 — service-owned bodies, opaque to the chip).
- **Name resolution / namespace mutation** (open-by-path, create, remove, rename, link): `gate_call`s
  over a namespace-object capability to the owning service domain; hardware never parses paths (§11.3).
- **Directory enumeration**: `read` of records from a directory object — whole records only, never
  split across the `len` boundary (a short read returns fewer complete records; `-MALFORMED` if `len`
  cannot hold even one); the position is the §10.1 cursor.
- **Stream IO**: an fd is personality state, not a capability. Each
  `read`/`write`/vectored/positioned operation follows the one authoritative object or service
  route recorded by the fd table; there is no separately negotiated "fast" operation class and no
  slower semantic class for an un-warmed descriptor. An implementation may automatically cache
  route validation, descriptor translation, cursor state, and resident worker metadata. A cache
  hit changes only cost: misses, invalidation, and revocation re-enter the same operation and
  preserve its exact result and policy checks. Software never advertises an operation mask merely
  to select an acceleration. Where the authoritative object itself is a §10.1 ChannelEndpoint or
  FileDescription, the personality invokes it directly because that is the fd's meaning, not a
  fallback bypass. Positioning belongs to that authoritative object or service; "close" releases
  the fd's reference only, so duplicated, inherited, or transferred references survive.
- **Capability passing** (rights-carrying messages, ring submit/reap): `send`/`recv` (§10.2).
- **Descriptor inheritance across executable-state replacement**: the per-slot **lifetime class**
  `{0 PERSIST (default), 1 DROP_ON_STATE_REPLACEMENT}` is set atomically at mint or receive and applied by
  `dreplace.commit` (§11.5). It is the machine's generalization of close-on-exec:
  the personality names the policy; the silicon knows only the class.
- **Process/thread lifecycle**: `dspawn`/`dstart` + `djoin`; **exit** is `dexit`
  terminate-self (there is no hardware "main thread"; "return from main exits" is a runtime
  convention).
- **Signals**: software maps signal identities and policy into numbered event **classes** 0--47 and
  carries the identity in the payload. Per-signal masking, queueing, ordering, and dispositions are
  evaluated before posting; `thread.group` lets the engine validate the chosen eligibility snapshot
  atomically. Delivery mechanics are hardware, signal semantics remain personality-owned.
- **Timers / sleeping**: `sleep` is `wait` with a deadline; interval timers are a **Timer object**
  (hardware-producer waitable, armed via the typed Timer arm forms in **ticks**, with time basis
  against a ClockView for wall-clock arms, §8.1/§17.7) consumed by `wait` or an event. Expiry past an
  unserviced expiry bumps an overrun count. No separate sleep operation exists.
- **The C error variable**: thread-local storage at a `tp`-relative offset (one `ld`/`sd`); the
  personality converts `-CONDITION` returns at its boundary.
- **Port IO**: does not exist; device access is device-BAR caps + `mmap`/DMA-window submission (§15).

This is what makes the ISA a *capability machine* rather than a syscall ISA: one generic dispatch
(typed domain/object families), the small endpoint surface (§10), the gate (§9), and the integer core carry the entire
OS-facing surface — and the machine itself speaks no operating system's language while doing it.

## 14. Floating-point profile (scalar IEEE 754, binary32 + binary64)

Scalar floating-point is **mandatory — every conforming machine implements this section in full**
(§1's one-conformance-class rule; there is no FP-absent LNP64). The `FEATURES` bit for FP is a
**view grant, not a hardware fact**: a parent may *withhold* it from a domain (§16.7 parental
control — a confined domain, or a domain being migrated under emulation), and executing an FP
opcode without the grant raises the **disabled-opcode** synchronous fault (§9.3) — the fault
machinery survives as the *view-denial* and emulation surface, never as a chip-variant probe. The
vector unit is §18, equally mandatory: programming model *and* v1 op catalog frozen, with only
the named `0xf6`/`0xf7` blocks reserved for additive growth. **And the execution contract for
ordinary binaries, named: the *full execution view* — every mandatory feature granted —
is what "an LNP64 execution environment" means to a compiled program.** A withholding view is a
**confinement or emulation environment by declaration**: the dominator that withholds knows it
did, the personality labels it, and a normal binary faulting under one is that environment
working as configured — never a compatibility surprise. Compilers target the full view
unconditionally (no feature probes, no fallback matrix — the one-machine promise); withholding
is the *dominator's* tool, not a machine variant. (The withholdable surface itself is closed
and positively defined, §2.1 — memory, objects, gates, and domain construction are never in
it.) **The one-binary promise extends to budget, not only features: nothing in the ISA or
psABI is budget-dependent, so a function compiled once runs in a richly-provisioned domain or a
zero-budget frozen leaf (§16.2) unchanged — there is no compartment dialect or compilation
mode.** Whether code fits a frozen leaf is answered by *static analysis over ordinary output*
(allocation reachability, worst-case stack depth for `gate.stack` sizing), never by
recompilation; an over-budget leaf fails closed (`-EXHAUSTED` on a starved allocation, a
guard-page fault on an over-deep stack), never corrupt. Running in a frozen leaf is deployment
discipline — no allocation, bounded stack — exactly like signal-safe or freestanding code,
which need no dialect either.

**State.** 32 floating-point registers `f0`–`f31`, each 64 bits. A binary32 value is **NaN-boxed**: it
occupies bits `[31:0]` with bits `[63:32]` all ones; reading a register as single whose upper bits are
not all-ones yields the canonical quiet NaN, and any instruction writing a single result sets the upper
bits to ones. The control/status word **FCSR** (PCR selector 8, §8) holds the rounding mode `frm` and
the accrued exception flags `fflags` (`NV` invalid, `DZ` divide-by-zero, `OF` overflow, `UF` underflow,
`NX` inexact; sticky). Rounding modes: `000` RNE (nearest, ties-even), `001` RTZ (toward zero), `010`
RDN (toward −inf), `011` RUP (toward +inf), `100` RMM (nearest, ties-max-magnitude). The instruction
`rm` field also accepts `111` **DYN** = "use `FCSR.frm`"; **DYN is an instruction encoding only**. A
stored `FCSR.frm` must be a concrete mode `000`–`100`; `101`/`110`/`111` are reserved there, and an FP
op using `rm=DYN` while `FCSR.frm` holds a reserved value raises an illegal-instruction fault rather
than rounding ambiguously.

**Encoding.** FP arithmetic uses the R-format **extended subformat** (§1): **exact subfield bits** in
the R-format `[25:0]` region: `[25:24]` = **`fmt`** (`00` = binary32 `.s`, `01` = binary64 `.d`, `10` =
binary16 `.h`, `11` = bfloat16 `.bf` — two bits from the start, because retrofitting formats into a
one-bit field is an ABI break; the narrow code points are **storage/convert-only** in this scalar
profile: an *arithmetic* op with `fmt` = `.h`/`.bf` raises illegal-instruction, reserved — narrow
arithmetic lives in the vector profile §18, where it multiplies lane count; scalar-side it saves
nothing); `[23:21]` = `rm` (with `111` = DYN); `[20:19]` = `intw` (for `fcvt.f2i`/`fcvt.i2f` only:
`00`=`w`, `01`=`wu`, `10`=`l`, `11`=`lu`; `fmt` gives the FP side). For **`fcvt.f2f`**, `fmt` is the
**source** format and `[18:17]` = the **destination** format (same code points); supported pairs are
`s`↔`d`, `h`↔`s`, `h`↔`d`, and `bf`↔`s` (`bf`→`s` is exact — a shift; `s`→`bf` is one rounding);
unsupported pairs raise illegal-instruction. `[16:0]` reserved-zero **except where a row in the §14 table assigns a bit** (`fcvt.f2i`'s `[16]` = `mod` is the one assignment today). FMA forms read three source
registers. Compares, `fclass`, and `fmv.x.*` write a **GPR**; `fmv.*.x`, `fcvt.i2f`, and the loads
write an `f`-register. **Loads and stores get distinct opcodes per width** (`flw`/`fld`/`fsw`/`fsd`,
in the §5 memory range), **not** a `fmt` bit: their I/S low bits are the hint zone, which must never
affect a result, so precision cannot live there. They use the integer addressing form
(`base + sext(imm)`). **Alignment: FP loads/stores follow the §5 integer rules exactly** — unaligned
permitted on `normal_cached` (possibly slower), natural alignment required on device memory types — so
there is no FP/integer divergence for a backend to model. (An earlier revision made FP misalignment
fault; that footgun is removed.)

| Op | Mnemonic | Form | Role |
|---|---|---|---|
| 0xd0 | `fadd` | `fd, fs1, fs2 {fmt,rm}` | add |
| 0xd1 | `fsub` | `fd, fs1, fs2 {fmt,rm}` | subtract |
| 0xd2 | `fmul` | `fd, fs1, fs2 {fmt,rm}` | multiply |
| 0xd3 | `fdiv` | `fd, fs1, fs2 {fmt,rm}` | divide |
| 0xd4 | `fsqrt` | `fd, fs1 {fmt,rm}` | square root |
| 0xd5 | `fmin` | `fd, fs1, fs2 {fmt}` | IEEE 754-2019 minimum |
| 0xd6 | `fmax` | `fd, fs1, fs2 {fmt}` | IEEE 754-2019 maximum |
| 0xd7 | `fminm` | `fd, fs1, fs2 {fmt}` | **minNum semantics**: if exactly one operand is NaN, return the *other*; both NaN → canonical qNaN; same −0 < +0 rule as `fmin`; sNaN raises `NV`. C `fmin()`, `llvm.minnum`, Rust `f64::min` — one op instead of a multi-op fixup |
| 0xd8 | `fmaxm` | `fd, fs1, fs2 {fmt}` | maxNum semantics, dual of `fminm` |
| 0xd9 | `fmadd` | `fd, fs1, fs2, fs3 {fmt,rm}` | fused `(fs1*fs2)+fs3`, single rounding |
| 0xda | `fmsub` | `fd, fs1, fs2, fs3 {fmt,rm}` | fused `(fs1*fs2)-fs3` |
| 0xdb | `fnmadd` | `fd, fs1, fs2, fs3 {fmt,rm}` | fused `-(fs1*fs2)-fs3` |
| 0xdc | `fnmsub` | `fd, fs1, fs2, fs3 {fmt,rm}` | fused `-(fs1*fs2)+fs3` |
| 0xdd | `fsgnj` | `fd, fs1, fs2 {fmt}` | inject sign of `fs2` (`fmv` = `fsgnj fd,fs,fs`) |
| 0xde | `fsgnjn` | `fd, fs1, fs2 {fmt}` | inject `~sign` (`fneg` = `fsgnjn fd,fs,fs`) |
| 0xdf | `fsgnjx` | `fd, fs1, fs2 {fmt}` | inject sign XOR (`fabs` = `fsgnjx fd,fs,fs`) |
| 0xe0 | `feq` | `rd, fs1, fs2 {fmt}` | quiet `==` → GPR (no `NV` on qNaN) |
| 0xe1 | `flt` | `rd, fs1, fs2 {fmt}` | signaling `<` → GPR |
| 0xe2 | `fle` | `rd, fs1, fs2 {fmt}` | signaling `<=` → GPR |
| 0xe3 | `fclass` | `rd, fs1 {fmt}` | 10-bit class mask → GPR; **bit order frozen**: bit 0 = −inf, 1 = negative normal, 2 = negative subnormal, 3 = −0, 4 = +0, 5 = positive subnormal, 6 = positive normal, 7 = +inf, 8 = signaling NaN, 9 = quiet NaN; bits 10–63 zero |
| 0xe4 | `fround` | `fd, fs1 {fmt, rm}` | **round to integral** in FP format per `rm` (`floor`/`ceil`/`trunc`/`rint` in one op; raises `NX` iff inexact, `NV` on sNaN) — the scalar twin of §18's `fround` |
| 0xe5 | `fsel` | `fd, rc, ft, ff {cc, fmt}` | branch-free FP select, the §4.1 shape mirrored: `fd = (rc <cc> 0) ? ft : ff` — **GPR** condition against zero, **FPR** data; slots `fd[55:51]`, `rc[50:46]`, `ft[45:41]`, `ff[40:36]`; **`cc[29:28]`** (`0` eq, `1` ne, `2` ltz — sign bit set, `3` gez — the §4.1 `sel` code points at a different home: `sel` `cc[27:26]`, `fsel` `cc[29:28]`, forced by `fmt` owning `[27:26]`; a decoder derives neither from the other), **`fmt[27:26]`**, `[35:30]`/`[25:0]` reserved-zero. Three source reads (one GPR, two FPR — split across files). The FP compares (`feq`/`flt`/`fle`) already produce the GPR condition; no embedded-comparison form exists. Non-arithmetic: moves bits verbatim, never raises `NV` |
| 0xe6 | `fli` | `fd, {fmt, cidx}` | materialize an FP constant from the **frozen 32-entry table**, enumerated (`cidx[4:0]` in the subformat region; the RISC-V Zfa table, adopted verbatim so every toolchain's constant-recognition logic transfers): `0` −1.0, `1` min-normal, `2` 2⁻¹⁶, `3` 2⁻¹⁵, `4` 2⁻⁸, `5` 2⁻⁷, `6` 0.0625, `7` 0.125, `8` 0.25, `9` 0.3125, `10` 0.375, `11` 0.4375, `12` 0.5, `13` 0.625, `14` 0.75, `15` 0.875, `16` 1.0, `17` 1.25, `18` 1.5, `19` 1.75, `20` 2.0, `21` 2.5, `22` 3.0, `23` 4.0, `24` 8.0, `25` 16.0, `26` 128.0, `27` 256.0, `28` 2¹⁵, `29` 2¹⁶, `30` +∞, `31` canonical qNaN (values in the register's `fmt`; min-normal is per-format) — one op instead of `li`+`liu`+`fmv.f.x` cross-file or a pool load |
| 0xe7 | `fmv.x.f` | `rd, fs1 {fmt}` | bit-copy FP → GPR (no conversion) |
| 0xe8 | `fmv.f.x` | `fd, rs1 {fmt}` | bit-copy GPR → FP (single is NaN-boxed) |
| 0xe9 | `fcvt.f2i` | `rd, fs1 {dst:w/wu/l/lu, src, rm}` | FP → integer (saturating, `NV` out of range). Subformat bit `[16]` = **`mod`** (valid only for `dst`=`w`, `src`=`d`): **`fcvtmod.w.d`** — truncate toward zero **modulo 2^32**, sign-extended, never saturating (NaN/inf → 0, `NV`): the dynamic-language 32-bit truncation in one instruction |
| 0xea | `fcvt.i2f` | `fd, rs1 {src:w/wu/l/lu, dst, rm}` | integer → FP |
| 0xeb | `fcvt.f2f` | `fd, fs1 {src/dst pairs above, rm}` | precision convert |
| 0x84 | `flw` | `fd, rs1, imm` | load binary32 (NaN-boxed into `fd`) |
| 0x85 | `fld` | `fd, rs1, imm` | load binary64 |
| 0x86 | `flh` | `fd, rs1, imm` | load 16 raw bits, NaN-boxed (`[15:0]` + upper 48 ones); interpretation (`.h` vs `.bf`) is the consuming op's `fmt` |
| 0x87 | `fld.q` | `fd(even pair), rs1, imm` | load an even FPR pair (16 B; plain §5 alignment, no atomicity claim) — the FP spill pair, §6 |
| 0x88 | `fsw` | `rs1, fs2, imm` | store binary32 |
| 0x89 | `fsd` | `rs1, fs2, imm` | store binary64 |
| 0x8a | `fsh` | `rs1, fs2, imm` | store low 16 bits |
| 0x8b | `fsd.q` | `rs1, fs2(even pair), imm` | store an even FPR pair |

**Half-precision (the storage-only decision, made deliberately).** Scalar narrow-format *arithmetic* is
near-pointless on a CPU — an f16 FLOP costs what an f32 FLOP costs; the wins of f16/bf16 are memory
footprint and vector lane count. Industry converged accordingly, and so does this profile:
**`flh`/`fsh` + the `fcvt.f2f` narrow pairs only**, so `_Float16`/`__bf16` work without softfloat and
ML-adjacent code keeps narrow memory formats while computing in f32; narrow *arithmetic* (and the
widening dot/FMA actually worth silicon) belongs to the vector profile (§18).

**NaN and result canonicalization.** Any operation that produces a NaN produces the **canonical quiet
NaN** (sign 0, exponent all ones, MSB of the significand 1, payload 0: `0x7FC00000` for binary32,
`0x7FF8000000000000` for binary64); input NaN payloads are **not** propagated.

**Subnormals (pinned — three decisions in one paragraph).** (1) **Full IEEE gradual underflow, always:
there is no FTZ/DAZ mode and none may be added** — a flush-to-zero switch is exactly the ecosystem split
(results depending on a mode bit some library flipped) that the no-mode-state doctrine exists to
prevent. (2) **Underflow tininess is detected after rounding**, so two conforming implementations set
identical `fflags` for identical inputs — which the §17.5 "context restore is exact" story requires.
(3) **Subnormal operands and results stay in the fixed-latency class** (§1): no trap-to-assist, no
variable-latency microcode path; an implementation's FP latency bound covers subnormal inputs, which is
what lets §18's realtime claim extend to vector FP unconditionally.

**Which ops raise `NV` on a signaling NaN (exactly).** A signaling-NaN operand raises `NV` **only** for
ops that interpret the operand *numerically*: FP arithmetic (`fadd`/`fsub`/`fmul`/`fdiv`/`fsqrt`/the
FMAs), the conversions, the signaling compares `flt`/`fle`, and `fmin`/`fmax`/`fminm`/`fmaxm`. The
**non-arithmetic** ops **never raise `NV` and never canonicalize** — they move bit patterns verbatim:
`feq` (quiet), `fclass`, `fsgnj*` (so `fabs`/`fneg`/`fmv` on a signaling NaN preserve it), `fsel`,
`fmv.x.f`/`fmv.f.x`, and FP load/store. Only operations that *compute* signal.

**`fmv.x.f` width semantics.** For `fmt=d`, copy all 64 bits into `rd`. For `fmt=s`, copy the low 32
bits (the binary32 payload, ignoring the boxing) and **sign-extend bit 31 to 63**, so an integer
round-trip is well-defined. The inverse `fmv.f.x` with `fmt=s` writes the low 32 bits and NaN-boxes, so
`fmv.f.x` then `fmv.x.f` is identity on the 32-bit pattern.

**Conversions (exact saturation).** `fcvt.f2i` rounds per `rm`; a result that is NaN or overflows the
integer type **saturates** and raises `NV`, with these exact constants: NaN → the destination type
**maximum** (`2^31−1` for `w`, `2^63−1` for `l`, `2^32−1` for `wu`, `2^64−1` for `lu`);
positive-overflow → the same maximum; negative-overflow → the destination **minimum** (`−2^31`/`−2^63`
signed, `0` unsigned). `fcvt.f2f` narrowing rounds per `rm` and may raise `OF`/`UF`/`NX`; widening is
exact.

**`fmin`/`fmax`** follow **IEEE 754-2019** `minimum`/`maximum` (not pre-2019 `minNum`/`maxNum`):
`−0.0 < +0.0`, a signaling-NaN operand raises `NV`, and if **either** operand is NaN the result is the
canonical quiet NaN (the 2019 propagating form). The number-returning behavior is `fminm`/`fmaxm`,
explicitly separate.

**FCSR writes.** `set_pcr(FCSR, value)` writes the whole word: `frm` from `value[7:5]`, `fflags` from
`value[4:0]`, other bits reserved-zero. Software **may** set sticky flags (so a context restore is
exact); clearing flags is writing the desired `fflags`. A write whose `frm` is a reserved value returns
`-MALFORMED` and changes nothing.

**Exceptions are non-trapping, always — FP is a pure compute unit.** A raised condition sets its
sticky `fflags` bit, **writes the IEEE default result**, and execution continues. There is **no
FP-fault delivery, no trap-enable mask, and no per-condition trapping mode**: software observes
exceptions through the sticky flags (`fetestexcept`-style) and clears them by writing `fflags`,
and code wanting trap-on-exception behavior polls the flags at boundaries it chooses. This
deletes the FP machine-call path and its non-auto-retry special case outright — nothing in the
FP unit reaches §9.3.

**ABI.** `f0`–`f7` and `f28`–`f31` are caller-saved temporaries (`ft0`–`ft11`); `f8`,`f9`,`f18`–`f27`
are callee-saved (`fs0`–`fs11`); `f10`–`f17` are arguments/results (`fa0`–`fa7`, with `fa0`/`fa1`
returning values). When the FP profile is active, the §9.3 machine-call payload includes `f0`–`f31` +
FCSR.

The integer core (§4–§13) and the entire OS-facing surface have no FP dependence — a layering fact
(and what makes running a domain under a *withheld* FP grant coherent), **not** a conformance
option: there is no FP-absent machine (§1).

## 15. Memory types, MMIO, DMA, and interrupts (the device / I/O model)

Device access is the capability model applied to hardware: a driver is just a domain holding a
device-BAR capability, a DMA window, and an interrupt waitable. Nothing about devices adds a privileged
mode (§2.1).

**Memory types.** A mapping's memory type is **fixed at `mmap` time by its backing** (§11.2), not by the
instruction and not changeable by `map.protect`: anonymous and file mappings are `normal_cached` (a backing
object may request `uncached`); a device-BAR capability **carries a *set* of permitted types, and each
`mmap` chooses one member per mapping** — the routine one-BAR-two-attributes pattern (device registers
`device_ordered`, the same BAR's memory aperture `write_combining`) is two mappings over one cap, each
type-checked against the cap's set; a type outside the set is `-DENIED` at `mmap`, so "accidentally
mapped registers cacheable" stays architecturally impossible. Ordinary `ld`/`sd` observe the type of the
page they touch. The four types and their ordering (relative to the §6 architectural model):

| Type | Cached | Ordering | Use |
|---|---|---|---|
| `normal_cached` | yes | §6 architectural model (annotated MCA; v1 silicon TSO) | ordinary memory (default) |
| `uncached` | no | coherent, unbuffered, no merge | bounce/coherence-sensitive buffers |
| `device_ordered` | no | **strongly ordered**: no merge, reorder, speculation, or replay; access order = program order | MMIO registers |
| `write_combining` | no | **weaker**: stores may coalesce and reorder until a `fence`; reads not speculated | framebuffers, bulk MMIO write windows |

**Alias compatibility is checked at map commit.** The engine's cross-domain reverse map for a backing
tracks physical ranges and CPU mapping types. A proposed mapping may select any type its backing cap
permits, but an overlap with a live mapping in another v1 type fails `-DENIED` with no partial mapping;
unmap removes the constraint. The check is physical-range based, so different virtual addresses and
different domains cannot construct an incompatible alias, while disjoint BAR subranges remain free to
select different permitted types.

Reads and writes to `device_ordered`/`uncached`/`write_combining` mappings must be naturally aligned
(§5).

**The locality axis (Law 8) — a mapping is a pair `{memory type, locality class}`, and the second
column is the one that keeps `ld`/`sd` honest at scale.** The four types classify by ordering and
cacheability; at array scale the missing column is distance. First the term: a **coherence volume**
is a connected tile region within which the §6 guarantees (coherence, MCA, `fence.sc`'s total order, and v1's TSO strengthening) hold
at bounded diameter — a `GEOMETRY` fact of the MachineView (§16.7), deliberately **not** an
architectural constant (Appendix B26: freezing a volume size would freeze a roadmap capacity). A
domain's tiles occupy a connected region (Law 8) — **and "connected" is topological, never
geometric: the selected resources form one connected subgraph of the MachineView-published
locality topology (the §17.6 `TOPOLOGY` record's adjacency), full stop.** No rectangle, no
contiguous tile numbering, no single physical package is required or implied: a subset of mesh
routers, several compute chiplets around one memory chiplet, a failure-aware route avoiding
defective links, or accelerator islands joined through one coherent switch domain each qualify
exactly when the view publishes the adjacency — connectedness exists so diameter and
invalidation are bounded, not so allocations are shaped. At domain construction the engine binds one
connected **coherence/time volume**, immutable for that domain incarnation; placement is only the
connected runnable-tile subset within it. Moving between volumes is a new incarnation through
state open/import/commit, not `domain.place`. Every mapping carries a **locality class**, fixed at `mmap` like the memory type,
computed from where the backing's frames are homed relative to the mapping domain
(namespace, stated: the class is one of three architected values — `0` **near**, homed within the
domain's home tile-group; `1` **domain**, homed within the domain's volume; `2` **far**, homed
outside it — and it is the *only* distance fact a mapping states; absolute position never appears):

| Locality class | Meaning | Cost |
|---|---|---|
| `near` | homed within the domain's home tile-group | L1/L2-class latency, tile-bounded |
| `domain` | homed within the domain's own volume | bounded by the domain's own diameter — a distance the domain can see (§16.7 locality metric) |
| `far` | homed outside the domain's volume | **not directly addressable at all** |

**The rule that makes the axis real: `ld`/`sd` are architecturally legal only on `near` and `domain`
mappings.** A `far` backing cannot be mapped into a directly-addressable VMA in the first place —
`mmap` returns **`-DENIED`**. Placement cannot change a mapping's volume-locality class because the
constructed volume is immutable. Any other view transition that would make an existing VMA, DMA
window, armed comparator, backing home, domain tag, or locality-dependent object illegal fails
atomically before changing the view; import across volumes validates them all and re-expresses armed
deadlines by remaining duration under §8.3 continuity. Far memory is reached the way
everything distant is reached: `send`/`recv`, a DMA window, or a gate to a domain that holds it
near. A cross-fabric pointer chase is therefore not slow — it is **unconstructible**: no `far`
mapping exists, so no pointer a program can hold names far memory, and *legality* needs no type
system, no annotation, and no compiler knowledge at all — every dereferenceable pointer is
near-or-domain by construction. (The near/*domain* **cost** distinction is dynamic VMA metadata a
raw pointer does not carry; the architecture guarantees the legality floor and serves the cost
through the §16.7 locality metric at runtime, not as a static compiler fact.) This also composes with delegation unchanged: a `mem_grant` handed to a domain outside the
granter's volume arrives as a `far` backing and maps `-DENIED` — the grantee messages or gates,
which is what physics wanted anyway.

**Every running domain inhabits exactly one coherence/time volume.** Its mappings, futexes, SC
order, deadlines, and timebase are that volume's — the volume may be as large as the implementation
will construct (below), but a domain never straddles two clocks or two coherence universes; a
workload wider than any constructible volume is **multiple domains glued by message edges**.
"Machine-spanning domain" always means a domain whose constructed volume is machine-wide, never a
domain across volumes.

A program that wants a machine-spanning coherent array makes its **domain** that big: all its
memory is then `domain`-class, and it pays diameter coherence internally — visible in its own
locality metric, charged to its own reservation. The widest coherence volume an implementation will
*construct* is a `GEOMETRY` fact of the MachineView — a placement or `backing.clone` whose tile
set would require a volume beyond that width fails **at placement, `-EXHAUSTED`**, the honest
admission-time refusal, never a silently-constructed volume whose store-order latency makes the
§6 guarantees true and useless. A machine-spanning coherent domain is therefore something an
implementation may *offer* (and price), never something a domain can *demand* — and a program
refused the width falls back to what physics was suggesting: multiple domains, message edges
between them, each volume honest about its diameter. **And the recommended model is stated,
so the permission is never read as a preference:** scale **up** within one volume where
fine-grained shared memory earns its diameter; scale **out** as message-connected domains
everywhere else. A spanning volume is an **admitted, priced resource**, and everything about it
scales with the width the program asked for — translation-invalidation span, SC population,
atomic and fence latency, epoch referent spans, quiescence cost, placement complexity,
contention blast radius — all visible in the domain's own locality metric and charged to its
own reservation. The architecture makes the wide volume *honest*, not attractive.

**The refusals:** there is **no remote-load
opcode**; distance is **not** added to the
fault model (a `far` access is a mapping that never existed, not a new fault class); no fence
scopes beyond the §6 volume scoping (one volume is exactly one scope from any domain's view — the
reserved fence-qualifier seam stays closed); and coherence-volume size is a per-MachineView
`GEOMETRY` fact, never architectural.

**Placement is multidimensional, and the class is a result, never a request (the heterogeneous-
memory rule).** The three locality classes above are the *legality* axis — coherence and
naming — and they stay exactly three: nothing here adds a fourth value or weakens the `far` ban,
and trust scope and coherence scope are never tier properties a program can relax — they are the
domain and volume, the axis above. What heterogeneous machines add is *quality*: a volume's
MachineView publishes a **memory-tier table** (a §17.6 `TOPOLOGY`-class record, in view
coordinates — Law 7: tier identity is view-local, never a physical name), each tier a row of
typed properties — **latency class, bandwidth class, persistence, failure domain, CPU
accessibility, device accessibility, migration-cost class**. Deliberately **not one ordinal
lattice**: the dimensions are independent, because a 2040 tier is fast-but-volatile,
slow-but-persistent, near-but-shared-failure — one "distance number" would lie about most of
them. A mapping names its needs through the `map.constrain`/`map.prefer` builder facts (§11.2):
required constraints admit or refuse at seal (`-EXHAUSTED`, the admission-time honesty rule),
preferences steer among the admissible, and **the solved tier is published at seal as an
observable, immutable mapping fact** — a program that constrained nothing still reads the truth,
so no placement is ever hidden; it is only ever defaulted. The Law 8 shape, restated for
placement: **no unnamed distance, coherence, trust, naming, persistence, or failure boundary** —
the program names its bounds, the machine names its choice, and fabric-attached or
disaggregated memory enters the architecture as *a named slow-or-fragile tier inside a volume*,
never as a hidden far pointer (the cross-volume ban is untouched). **And serialization carries
constraints, never ordinals (§16.8):** a state stream records a mapping's required-constraint
set — the portable truth — plus the satisfied property values as diagnostics; import re-solves
the constraints against the destination's tier table before publication and fails or rebinds
atomically if unsatisfiable. A destination-specific tier number never crosses a machine
boundary, which is exactly what makes placement portable across two decades of machines.

**Translation-entry coalescing.** Page size remains one `GEOMETRY`
value (Appendix B23). An implementation **may transparently coalesce** translation entries over
physically-contiguous, permission-uniform, same-class runs — TLB-reach relief in the ARM
contiguous-hint style — with two obligations: coalescing is **never architectural** (no observable,
no op, no fault granularity change; `SUPPLY`/`EVICT`/protection granularity stays the page), and
invalidation correctness is unchanged (a bump covering any page of a coalesced run drops the run).
**Architected large leaves (`LARGE_LEAF`):** exactly **one** additional leaf size,
**`LARGE_LEAF_SIZE` = 2 MiB** (512 pages at the architectural 4 KiB page), selected by the
`map.leaf` builder fact
like the memory type and locality class. Rules: `addr_hint`, `backing_offset`, and `length` must be
leaf-aligned/leaf-multiple (`-MALFORMED`); within a leaf mapping, `SUPPLY`/`EVICT`/`map.discard`/
`map.protect` operate at **leaf granularity** (a sub-leaf range is `-MALFORMED` — one mapping, one
granularity, no split-brain frames), page-request records carry leaf-sized `len`, and the per-frame
charge account records leaf frames. **Demotion exists** because sub-range protection, partial free,
and partial eviction are routine lifecycle events. `map.demote` over a
**leaf-aligned, leaf-multiple** range of a leaf mapping
atomically splits those leaves to page granularity — one engine transaction per leaf: the VMA
splits at the range boundaries (the demoted range becomes a page-granular VMA; enumeration shows
the split, nothing is silent), each leaf frame's charge rewrites to 512 page charges on the same
account (sum unchanged — demotion moves granularity, never money), and the mapping cell bumps
under the ordinary §11.2 broadcast (a stale leaf translation cannot survive its own split).
**The charge rule is one instance of the demotion invariant, which holds for *every* per-leaf
fact: demotion is a lossless change of representation — granularity moves, truth never does.**
Residency (a resident leaf → 512 resident pages), dirty/write-protect state (a dirty leaf → 512
dirty pages; a `CLEAN_WP` leaf → 512 clean-WP pages — conservative direction always), accessed
bits, pin leases (a lease over the leaf → the same lease over its pages, same `lease_id`, same
counts), reverse-map entries, COW relationships (a shared leaf splits into pages sharing the
same source, COW break granularity becomes the page), pager-request granularity (subsequent
records carry page-sized `len`), in-progress `backing.rehome` targets, and IOVA-leaf references all
rewrite under the same transaction, and any fact that cannot be represented losslessly at page
granularity does not exist (that is what "one mapping, one granularity" bought). **Concurrency is the ordinary serialization:** demotion is an engine
transaction on the backing, so a concurrent `SUPPLY`/`EVICT`/`backing.rehome` serializes before or
after it at the backing engine (before: it saw a leaf; after: it sees pages — both legal, the
designation-epoch already versions pager requests across the boundary); a concurrent *access*
sees the bounded broadcast stall and retranslates, never a fault window; two concurrent
demotions of overlapping ranges serialize, the second finding pages and returning success (the
op is idempotent by postcondition); a DMA window over the range is untouched (its references
were per-page already, above); and a leaf shared by many domains bumps every mapper's cell via
the reverse map — the mapper count is the op's class-4 parameter, same as `EVICT`.
Demotion is **one-way** (promotion back is unmap plus a new `map.leaf(..., LARGE_LEAF)` construction — re-assembling a leaf
in place would require proving 512 pages' independent histories converged, which is the pager's
compaction job via `backing.rehome`, not a flag's); sub-leaf operations before `map.demote` remain
`-MALFORMED`, so granularity never changes as a side effect of a typo — the program that wants
pages says so, once, explicitly. Transparent coalescing (above) remains the bridge for mappings
that did not opt in; the leaf is the contract for those that did. (The three constituencies that
forced the promotion, on record: databases, nested/hypervisor hosts, GC'd-runtime heaps.)

**MMIO.** A device register block is a **device-BAR capability** mapped `device_ordered`; software reads
and writes it with **plain `ld`/`sd`**. MMIO is memory with a device producer, **not** a message verb
and not a port-IO opcode (there is none). A **bus/device error** on an MMIO access (target abort,
parity, decode error) delivers a **synchronous machine call** (§9.3) at the offending `ld`/`sd`,
carrying a bus-error cause — the architected error path for MMIO, since a plain `ld`/`sd` has no
condition channel. **PCIe I/O-space BARs are unsupported, stated deliberately:** there is no port-I/O
opcode and no architected I/O-space window — LNP64 targets MMIO-BAR (modern) devices only. A legacy
device reachable only through an I/O-space BAR is out of scope for conformant hardware; if a bus service
ever needs to fake one, that is service-level emulation behind a gate, never ISA.

**Access-emulated register backings.** A `device_ordered` PagedBacking may designate an
access-emulating pager. Each load or store uses the ordinary fault/request/PAGE_REQUEST-park path,
augmented by access width and store value, and is completed by `backing.respond`; there is still no
generic trap class or port-I/O namespace.

```text
backing.respond rd, backing, request_id, designation_epoch, load_value
```

The request record is the ordinary pager request plus `access_width u32`, `access_kind u32`
(`0 LOAD`, `1 STORE`), and `store_value u64` (zero for a load). `backing.respond` installs no frame:
for a load it supplies the width-truncated return value; for a store it acknowledges completion.
Requests retire in program order for one thread, giving `device_ordered` ordering without a second
fence mechanism. Fetch and atomics remain invalid on device memory. A parked access serializes as
PAGE_REQUEST and is reissued through the ordinary park theorem.

**DMA and the IOMMU.** DMA **windows** are objects created and scoped through `window.new` and
the typed window-builder operations ending in `window.seal` (§16.3) —
**IOMMU-scoped, epoch-checked**; `send` to the window's submission facet (§11.4) then
submits bulk transfers **over a sealed window**, never constructing one itself. Every device
master is confined to its own per-requester-ID window, checked against VMA permissions, the authorizing
capability, IOMMU scope, and domain accounting; revoking a window faults in-flight DMA (the `quiesce`
bump policy, §3, before reuse). **Interrupt remapping is by construction, not by convention:** a
device signals interrupts only through the vectors `InterruptWaitable BIND` associated with its
requester ID (§17.7 — engine-chosen, device-local), and an inbound DMA write that targets an
interrupt-signaling address for *any other* vector is an IOMMU scope violation like any out-of-window
write — a malicious master cannot forge an interrupt by DMA-writing the interrupt-controller doorbell
directly. This is the VT-d/SMMU interrupt-remapping guarantee made architectural rather than
folkloric, in the same spirit as the ATS-deny rule below. **What the fabric does *not* enforce: which flow or port a queue may claim.** In the QueuePortal bypass
model (§15) many domains hold their own NIC queues, and steering an incoming connection to the
right queue is RSS/flow-director programmed by the driver domain — but *who may claim a port or
flow* is a **network-service-enforced namespace**, exactly like the VFS path namespace, never a
guarantee of the NIC or the IOMMU (which enforce only requester-scoped memory and interrupt
confinement). A port is authority a service grants, not a fact hardware checks — **with the
threat-model consequence stated: the service is the enforcement boundary, so flow-authority
isolation is exactly as strong as the network service's own domain isolation, no stronger.** A
compromised network service can misroute flows; it still cannot touch memory or interrupts
outside the requester scopes the fabric enforces. **Conforming LNP64 v1 mandates coherent DMA**: a transfer joins the
coherence fabric before its completion signals, so **there are no cache-maintenance instructions in the
ISA**. (A non-coherent DMA profile is explicitly out of scope for v1.) **"Coherent" is scoped by volume, not by machine (Law 8 applied to I/O):** a window's
coherence obligation is to the **volume homing its backing** — which the shared-backing home
invariant (§16.3 `backing.rehome`) already places inside every mapping domain's volume, so every party
that can touch the buffer with `ld`/`sd` sees coherent DMA, and no wire spans a distance no
sharer named. A device whose window's backing is homed far from the device's fabric attach point
pays that distance on every beat — visible in the window's own accounting, priced like any
`domain`-class access, and the placement fix is `backing.rehome` or move-the-window, both
existing verbs. **And the distance is queryable *before* it is paid, not merely billed after:
device-to-memory cost class is a `GEOMETRY` fact of the window** (the `STATUS` selector answers the
attach-point-to-backing-home cost class in the same locality metric §16.7 uses for
CPU-to-memory, in the observer's own view coordinates per Law 7) — placement software optimizing
a device path needs the same sensor it has for a CPU path, and accounting-after-placement is a
bill, not a sensor. **IOVA leaf granularity is a per-window `GEOMETRY` fact, deliberately decoupled
from the CPU page size — and the decoupling survives the day the two values coincide:** the
4 KiB architectural page (Appendix B23) governs VMAs and CPU translation; a window's IOVA leaf
is its own fact, **4 KiB mandatory in v1** (the PCIe ecosystem's working granularity — devices,
SR-IOV queues, and vendor DMA engines assume it), because a DMA window is not a CPU mapping and
never was. In v1 the two values are equal, so the sub-page quadrant case is degenerate — but
the *rules* below are stated against the two objects, not the two numbers, so a future revision
that moves either granularity inherits them unchanged (`window.seal`/`REMAP` ranges align to the
*window's* leaf; the pin and charge stay page-granular, the CPU's unit of account). **The
two objects keep two names — "page" (CPU, 4 KiB, the unit of VMA, charge, pin,
residency, dirtiness) and "IOVA leaf" (per-window) — and the sub-page rules
follow from which object owns which fact:** window references count per **page** on the page's
pin record (an IOVA leaf mapped anywhere references its containing page; the page is
reclaimable only at zero references — quadrants never make reclaim finer, only exposure); a
window's rights over a leaf are bounded by the containing page's mapping rights (the IOMMU
check is `window ∧ page`, never wider); two devices may hold different quadrants of one page
(two windows, two requester scopes — that partial exposure is the feature); dirty/accessed
truth stays **page-granular** (a DMA write through any quadrant dirties the page — the CPU's
unit of account is the unit of memory-management truth); revocation and `quiesce` operate per
window and therefore per quadrant naturally (the broadcast cuts the window's translations; the
page's other quadrants and CPU mappings are untouched); `REMAP` ranges are window-IOVA-space
and cross CPU-page boundaries freely (each leaf re-points independently; the per-page reference
counts move mechanically); and sub-page window state serializes with the window object like all
its state (§17.9). Coherence needs no new rule: it was always line-granular, finer than either
object. Completion uses a hardware-producer **CompletionQueue**; a Counter is `-BADREF`
at `window.seal`.

**DMAWindow is requester memory.** `window.requester_facet` mints a requester-only backing facet
from a sealed DMAWindow. The facet, not the ordinary DMAWindow control capability or its Device,
is admissible wherever a backing is named. Possession is the complete software-requester identity:
the party constructing the window delegates this facet only to the domain standing where the
device stands. This avoids an ambient Domain-identity test and does not let a guest map requester
memory merely because it holds the described Device. Offsets are IOVAs, contents are the currently
granted extents, and holes fault `-BOUNDS`; mappings and checked copies resolve the current REMAP
generation at each access. A hardware requester consumes the same window internally through the
IOMMU and receives no CPU facet. A software requester holding the facet is ATS-denied, so REMAP
acknowledges at commit (`acked == issued`). The facet's READ/WRITE rights are bounded by the
window's DEVICE_READS/DEVICE_WRITES direction respectively and remain narrowable and delegatable.
The window has no frames or pager of its own and accepts no PagedBacking-family mutation.

**Software-produced interrupts reuse Counter.** `irq.source` accepts either InterruptSource or
Counter. With AUTO acknowledgment a Counter is a counting edge source: positive `counter.add`
increments pending edges and each delivered edge consumes one. With EXPLICIT acknowledgment it is
a level source: nonzero is asserted, `irq.ack` permits observation again without clearing it, and
the producer lowers it with `counter.set(..., 0)`. Counter mutation retains its ordinary release
ordering, so coherent stores before the transition are visible before interrupt observation.

**ATS honesty and the ATS-deny rule (hardened policy, named).** The invalidation-acknowledgment
contract (§11.2, and the `quiesce` drain) counts device-side cached translations among its
acknowledging participants — which means its soundness **assumes the device honors the invalidate**: a
hostile endpoint cannot be *forced* to drop a cached translation. So the assumption is stated, and the
remedy is architected rather than folkloric: a device is granted address-translation caching (the
ATS-class capability on its window/BAR establishment) **only by explicit grant**, and the **hardened
policy denies it to untrusted devices by default** — an ATS-denied device's every access takes the
IOMMU walk, where the epoch check is enforced at the fabric boundary the device cannot subvert. The
quiesce soundness argument is then honest in both configurations: cooperative silicon acknowledges;
untrusted silicon was never allowed to cache. **And the third configuration — ATS-granted but
wedged — is the §11.2 fence:** a granted device that stops acknowledging within `ATS_ACK_BOUND` is
cut at the fabric like a device that was never granted, so a stuck or hostile endpoint can delay an
invalidation by at most the bound, never block it — and only operations touching
ATS-device-visible ranges ever inherit that bound at all.

**Isolation groups (the unit the requester-ID checks are honest at).** **Requester identity**
throughout this section means the **fabric-enforced master identity** — a PCIe requester ID is
one instance, an SoC fabric-master ID another; the rules are stated generally and
illustrated by PCIe. A requester ID proves origin
only as far as the topology enforces it: functions behind a non-ACS switch, RID-aliasing bridges,
and multi-function devices without isolation can spoof or observe each other's traffic, and no
IOMMU check downstream can repair that. So the platform enumerates **isolation groups** — each
group the smallest set of functions whose mutual isolation the topology cannot prove (ACS-isolated
functions group alone; everything behind a non-ACS bridge groups together) — and **the group is
the security principal**: the **group capability is the authority root**, and a function-level
capability inside a non-isolatable group is a **convenience view derived from it** — a narrower
name for delegation bookkeeping, never an independent security grant. The derivation rule makes
the four tempting over-claims unconstructible: a convenience view cannot establish a DMA window
narrower than the group can enforce (the IOMMU checks the group's aggregate scope), cannot take
an ATS grant while an aliasing peer sits outside the invalidation contract (ATS is granted per
group or not at all), cannot bind interrupts on a requester identity the fabric cannot prove,
and cannot represent reset or power operations as function-local when they reach peers — each of
those authorities exists only at the group root — as do the two the derivation rule implies but
compatibility work will probe: **assignment to a domain** (the group is handed over whole; giving
one function of an aliasing group to tenant A and its peer to tenant B is unconstructible) and
**peer-to-peer routing authority** (a window whose backing is a group member's BAR takes its
device-side authority from that member's *group* root). **Fate sharing follows from the same fact:**
requester quarantine, ATS poison/cut, reset, surprise removal, power loss, link failure, and
requester-ID reincarnation are **group-wide lifecycle events** — where isolation cannot be
enforced, function-local recovery cannot be honestly represented either, so the terminal and
recovery protocols below always speak of the group. Windows and vectors still bind per requester
ID (the mechanical scope); the *authority* to bind them is group-granular, and group membership
is a served topology record (§16.6) a service reads before it delegates. This is the
IOMMU-groups contract made architectural instead of a kernel convention.

**Surprise removal (the terminal-state protocol, ordered).** A removed device is an asynchronous
fact the whole object graph must converge on, so the convergence is architected: **(1)** the
fabric quarantines the group — inbound DMA and interrupt messages from its requester IDs are dead
at the IOMMU from the removal event onward, and a later hot-add at the same topology coordinates
is a **new** group with fresh epochs, never a resurrection (Law 2 applied to slots in a chassis) —
a reappearing device receives a new object lineage, a new requester incarnation, fresh windows,
fresh interrupt bindings, fresh queues, and new configuration capabilities, and every old handle
stays stale even when vendor/device IDs and the physical slot are identical; **(2)** every
established window over the group enters the terminal state — in-flight and queued
submissions complete through the ordinary abort-drain with error-status completion records, so
waiters wake through the path they already watch and the completion record remains the
memory-reuse-safety signal, removal included; **(3)** direct `ld`/`sd` through a removed BAR
mapping raises the **synchronous bus-error machine call** — the ordinary §9 fault model, because
a direct MMIO access has no condition channel and inventing an in-band sentinel would convert a
fail-closed hardware fact into plausible data (all-ones is a *valid register value* on real
devices, and a driver fed it keeps operating on a corpse). The **linearization point is the
quarantine event**: accesses accepted by the fabric before it complete with whatever the wire
returned (the unavoidable in-flight window); every access issued after it faults, never
silently succeeds. The PCIe all-ones convention survives where it is honest — the
**configuration-space service** reports the architected absent-device value to config reads, and
a Linux-compat personality that wants all-ones *data* semantics builds them in its own bus-error
handler, as policy over a fail-closed fact rather than in place of one; **(4)** the group's object epochs bump —
subsequent typed ops on its windows, BAR backings, and bindings return `-STALE`, and fixed getters
reports the terminal `state` in the common prefix (§17.9); **(5)** its InterruptWaitables raise a
final `HANGUP` readiness, which is how the owning service learns without polling. Nothing in the
protocol waits on the device: every step is host-side, so a hostile or dead endpoint cannot hold
its own teardown hostage.

**Hot-add: a newly attached device is architecturally inert** — no DMA windows (windows are
the *only* device-visible memory grants), no interrupt bindings (delivery is
remapping-by-construction), no ATS grant, no group capability — **until the bus service
explicitly mints its existence**, so the plug-time DMA race is unconstructible: authority does
not precede the grant. **Nothing may pre-establish a bring-up window at presence detect** — a
device not yet granted does not exist (§16.7). Mechanics: presence detect is an ordinary
`InterruptSource` the bus service already holds; the bus service mints the group's existence
from authority it already holds — the group capability and requester-identity binding as served
records under its control-plane capability, device-BAR capabilities as `mem_grant` sub-ranges
of the bridge apertures it maps (§11.4 — no separate BAR-minting operation exists), normalized
`InterruptSource` facets (§16.3) — every mint charged to the bus service (§16.4). The new
group is a **fresh incarnation with fresh epochs**, exactly as re-plug after removal (step (1)
above): arrival and re-arrival are one rule.

**Power transitions come in exactly two classes, so no bus service invents its own suspend-race
semantics.** Device power management is service policy — the engine architects no power states —
but every transition is one of two architected shapes. A **lossless quiesced transition** has one
stated contract: new submissions to the group's queues fail `-BUSY` for its duration (fail, not
block — a blocked submitter cannot see why it is parked); outstanding submissions complete
normally before the transition commits (the quiesce is real, not asserted); interrupts are masked
from the commit point and any arrivals coalesce into pending readiness; BAR mappings, window
epochs, ATS state, ordering state, and deadlines are all **untouched** — the transition is
invisible to every handle, and resumption signals through the ordinary readiness path (the
masked interrupts and the `-BUSY` lifting *are* the resume events; nothing new to wait on). A
**lossy transition** — one that would lose accepted submissions or device-side state — *is*
surprise removal by another name and takes **exactly** the terminal protocol above from step
(2), not a slightly different teardown of its own. An established window therefore holds its
device's power floor at the shallowest state that can still complete accepted work — the
pin-lease idea applied to watts, priced to the service that established the window.

**And the pinning price, stated against its remedy:** v1 establishment always pins — but by
**declared fact, never by definition**: `window.pin` (§11.4, §17.7) is the explicit
addressability fact seal admits, the only value v1 admits, and nothing in the base architecture
states that a device-accessible page is *definitionally* pinned — pinning is one addressability
form with a named successor slot. The pin is
the correct residency contract for windowed DMA and an honest cost for oversubscribed accelerator
memory — a device that wants more mapped than resident is asking for recoverable device faults,
which is exactly the second value of the same fact (`window.faultable`, reserved by name on the
PRI/PASID seam, Appendix G), deferred rather than
half-shipped as an unpinned window with no sound residency story.

**`backing.clone` (function 18) — the atomic backing clone, the snapshot primitive fork used to
smuggle.** `backing.clone` on an **engine-backed** `normal_cached` backing mints a new backing whose every
resident frame is **shared with the original under a per-frame share count**: the op
write-protects both sides' mappings of the shared frames (one §11.2 broadcast over the actual
mappers), marks the frames shared, and returns the clone capability — **atomic** (a point-in-time
image: a racing write lands wholly before or wholly after the clone), bounded by resident frames
(class 4). A later write on either side copies out the written page — first-touch copy, charged
to the writing side's charge-target by the ordinary per-frame rules — and decrements the share
count. **Sharing is flat by construction: frames carry share counts, never parent pointers.**
Cloning a clone shares the same frames under the same counts; chain depth is *unconstructible*,
and no operation anywhere walks a clone history (Appendix C: no cost scales with how many
snapshots ever existed). A **pager-designated** backing refuses `backing.clone` `-UNSUPPORTED` — there
the pager *is* the snapshot mechanism (write notification plus backing dirty-range cursors), and two snapshot
authorities over one backing would be two sources of truth. Rights: `CONTROL`. The clone is born
with the creator's charge-target and **no** pager designation, mappings, pins, or leases — a
clone of frames, never of relationships. Per-frame COW accounting exists for private mappings
regardless; the §6 private-mapping futex key rule is unaffected.

**`backing.persist` (function 19) — durability as a backing verb, because there are no
cache-maintenance instructions and durability was about to become a service convention over a
mechanism that did not exist.** `PERSIST(offset, len)` on a backing whose media class is
persistent (a served fact of the backing, §16.6) returns only after **every store to the range
that was coherently visible when the op issued has reached the persistence domain** — the
CLWB-plus-fence contract expressed the machine's way: an engine op on the object that owns the
frames, never an instruction over addresses, so the coherent-memory model stays
maintenance-free and the durability point is a completion, not a fence idiom. Class 4 by range;
requires `WRITE` (you persist what you may write); on a volatile-media backing `-UNSUPPORTED`
(durability that silently meant nothing would be the worst kind of lie); a media failure during
the flush files the §15 `PERSISTENT_MEDIA` incident and the op returns `-POISONED` — success means
*all of it is durable*, and anything less says so. **Ordering, stated for the consumer this op
exists for (the write-ahead-log idiom):** the durability cut at issue includes **every
program-order-earlier store by the issuing thread to the named range** — op issue behaves as a
**range-scoped release**, so `store log records → PERSIST(log) → store commit record →
PERSIST(commit)` is correct with **no fence anywhere in the sequence**; the commit record's
durability implies the log's by completion order. Cross-thread writers publish into the cut the
ordinary §6 way (`fence.rel` on the writing side, or any §6 edge making the store coherently
visible before issue); the op never waits for stores that were neither program-order-earlier at
the issuer nor coherently visible at issue — the cut is a fact about the past, not a promise to
chase the future.

**PagedBacking construction is an unpublished builder.**

```text
backing.new     rd_builder, size, memory_type
backing.pager   rd_builder, builder, pager
backing.charge  rd_builder, builder, charge_target
backing.seal    rd_backing, builder
```

Each mutation consumes one builder generation. `backing.pager` accepts a typed pager-endpoint
capability whose architectural type fixes the pager protocol; no protocol-version scalar is
configured or negotiated. `backing.charge` establishes the default charge target for later supplies.
Seal validates size/type, pager eligibility, charging authority, budgets, and relevant epochs and
atomically publishes the backing. Before seal the prospective backing is unobservable; abort is the
universal builder abort.

Live changes are separate transitions because they have different authority, ordering, quiescence,
failure, and accounting:

```text
backing.rebind_pager    rd, backing, quiescence_token, new_pager
backing.detach_pager    rd, backing, quiescence_token
backing.retarget_charge rd, backing, expected_target, new_target
```

Pager rebind/detach requires a quiescence token covering new requests and outstanding-request
mutation. Rebind atomically changes the designation cell and re-delivers still-outstanding requests
under the new epoch; detach succeeds only when no outstanding request would be stranded.
`backing.retarget_charge` conditionally changes only the default for future frame admission; it does
not move existing per-frame charges. The pager relation and charging relation never inherit one
another's lifecycle.

**Provided backings (universal — one provider mechanism covers the page cache, swap, overcommit,
write notification, post-copy migration, and access-emulated device registers).** Any backing
object — an anonymous `PagedBacking`, a file or service backing — may designate a typed **pager
endpoint** during construction or through `backing.rebind_pager`; a `device_ordered` backing accepts
only access-granular response, while cached backings accept residency supply, and
absent a designation memory is engine-backed as always. **The designation rides the backing object,
never the domain**: a backing
is mapped by arbitrarily many domains, and the pager holds the backing, not every mapper's domain
cap. A fault on a non-resident page **parks the faulting thread exactly like a blocking op** (it is
one) and delivers a **page-request record** on the pager's endpoint (the demand-paging-as-`recv`
shape); the parked thread remains freezable and terminable like any blocked op. **The record is
frozen — a hardware producer writes it, so it is ISA (the DMA-completion-record rule): 64 B**:
`[0]` pager_cookie u64 (engine-minted, nonzero, and stable for one pager designation — an opaque
name for the backing, renewed on rebind), `[8]` offset u64, `[16]` len u64, `[24]` access u32 (0 read, 1 write, 2 execute,
3 write-to-clean — the write-notification case), `[28]` width u8 (`0` page-granular, otherwise
`1`, `2`, `4`, or `8`), `[29..32)` reserved-zero, `[32]` faulting_domain u64,
`[40]` designation_epoch u64, `[48]` request_id u64, `[56]` store_value u64 (zero unless a
width-qualified write). `request_id` is nonzero,
generation-qualified, unique within the backing incarnation, and never reused; it names exactly one
outstanding request and becomes stale when supply, reject, rebind cancellation, or teardown wins
that request's terminal cell. **The `faulting_domain` namespace, stated (the §17 domain-local-names
invariant binds this record like every other):** an **opaque, backing-local cookie** — stable per
`{backing, faulting domain}`, equal cookies = same domain, **no global ordering, no cross-backing
correlation**, and never reused for another domain during that backing incarnation (§8.2) — it exists
so a pager can group and charge per toucher, never so it can name a
foreign domain. The accepted controlled channel is exactly `{offset, access, timing}` to the
backing's own pager, and nothing more. The pager services it with **`SUPPLY`** — an op **on the backing,
keyed by object offset**, never a per-domain address-space op (the engine resolves offset → mapping
VMAs through its backing→mappings reverse map) — and reclaims with **`EVICT`**, whose invalidation
bumps every mapping VMA's cell and rides the ordinary §11.2 broadcast. The faulting domain never
sees a fiction — it sees a memory stall, which is physics, not deception (Law 7: its budget is a
granted fact that may exceed physical truth).

**Charging is architected, or budgets are fiction (three frozen rules).** **(1)** Every installed
frame has one **charge-target**, recorded in engine frame metadata, so `EVICT` refunds mechanically.
`backing.supply_req` obtains that target from the request's unforgeable fault-time requesting-Domain
account; the memory access is consent to first-touch charging and the pager cannot substitute an
account. Exhaustion returns `-NOSPACE` without resolving the request; the pager may terminate it
with `backing.reject(EXHAUSTED)`. Pager-initiated `backing.supply` uses the backing's administrative
default, whose installation by `backing.charge`/`backing.retarget_charge` requires `CHARGE` authority.
**(2)** Sharing is
**first-toucher**: one charge per resident frame; a later mapper of an already-resident frame adds
a mapping, not a charge; `EVICT` refunds the recorded holder; a re-fault re-charges the new toucher.
**What is frozen here is the mechanism, not the attribution policy** — the memcg wars are not
re-fought in silicon: the engine freezes *per-frame recorded target, named at `SUPPLY`, refunded
mechanically*, and first-toucher is only what falls out when the pager names the faulter's account.
A pager may equally charge a shared file-cache account, the file service, or any domain it holds
`CHARGE` over — per frame, per its own policy. The eternal shared-page-cache argument is thereby a
*pager policy* argument, fought in software where it belongs, over a substrate that can express
every side of it.

One open request has one terminal-choice cell. Request-keyed supply, access response, rejection,
and pager-initiated supply are distinct:

```text
backing.supply_req rd, backing, request_id, src_ptr, designation_epoch {wp[8]}
backing.supply     rd, backing, offset, length, src_ptr, designation_epoch {wp[8]}
backing.respond    rd, backing, request_id, designation_epoch, load_value
```

`supply_req` takes its range, access mode, and charge target from the named open request. It checks
the designation epoch, snapshots/copies `src_ptr` under §11.1 (`0` means zero-fill), installs the
entire range with the optional clean/write-protected state, charges the recorded requester, and
atomically consumes the request. A stale, foreign, completed, or wrong-backing request fails
`-STALE`; no partial install or charge occurs. Concurrent requests for one backing never mutate a
shared charge selector. Plain `supply` remains the explicit offset/length path for prefetch,
readahead, restoration, and other pager-initiated admission and charges the current default. Pages
prefetched through that path remain charged to that pool after later access; re-attribution is pager
policy using accessed cursors, not implicit hardware.
`backing.respond` wins the named request's terminal-choice cell without installing or charging a frame. It is
legal only for a width-qualified request through a `device_ordered` mapping; execute requests must
be supplied or rejected. A load completes with the width-truncated `load_value`; a store ignores
that operand and completes when acknowledged. Supply wakes-and-retries, respond wakes-and-completes,
and reject wakes-into-fault. A stale, foreign, completed, wrong-backing request or designation epoch
is `-STALE` and changes nothing. `request_id`, rather than offset, distinguishes concurrent accesses
to the same register.
For **engine-backed anonymous memory**, no pager supplies a target: the first domain whose access
materializes a private frame is the implicit charge target, charged against its own effective memory
budget without requiring a separately delegated `CHARGE` capability. That target is recorded in the
same per-frame field. Later sharers add no charge; COW materialization charges its writer; and
`map.discard`, reclaim, or destruction refunds exactly the recorded target. A shared zero page is not
a private resident frame and carries no per-domain frame charge before materialization.
**(3)** `SUPPLY` may install pages **clean and write-protected**: a store to a clean resident page
delivers a pager message through the same fault path — write-notification, writeback scheduling, and
incremental-checkpoint tracking with no second mechanism. **The refusal, named — and re-scoped to what it actually forbids:** there is **no
*drifting* dirty-bitmap op**. A bitmap sidecar maintained beside the translation path is a second
source of truth that drifts; pre-dump is
`AS_ENUMERATE` (§11.2) + a write-protect pass + collected faults — one mechanism, already frozen.
But the review's counterexample is accepted: *categorical* refusal was too strong, because the
write-protect scheme charges **one fault per first write per page per epoch**, which is the wrong
price for high-dirty-rate consumers (live migration of a busy guest, incremental checkpoints,
GC card-marking, database snapshots). So the seam is reserved with its correctness conditions
**Backing write generations.** `observe.mark rd_generation, backing, WRITES` establishes a
new monotonic generation for subsequent CPU, DMA, and engine-visible writes.
`dirty.begin rd_cursor, backing, since, through, offset, length` opens a cursor over
ranges changed in the selected interval; `cursor.next` writes one 16 B `{start u64, length u64}`
record per step to its destination. A reported superset is
permitted, but omission of a changed range is forbidden.

This metadata is disjoint from pager content-dirty state: observation neither marks contents clean nor
changes eviction eligibility. Implementations may use per-page generations, bitmaps, protection
epochs, logs, or hierarchical summaries. None of those representations is architectural, and no
versioned bitmap query body exists. Rotation cost is bounded by the backing's writable mapper/device
span; enumeration cost is bounded by the named range and returned cursor entries.

**The recency signal is not that refusal's victim, and the boundary is the correctness line
(`accessed.begin`, §16.3):** dirtiness is *truth* — miss a dirty page and the checkpoint is wrong —
so it may not live in a sidecar that drifts; **recency is *policy input*** — miss an accessed bit
and an LRU evicts a warm page, which costs a fault and nothing else — so the per-page accessed
bits are served as an explicit hint (an implementation may under-report between scans, stated in
§16.3 so nothing can ever be built *on* the drift). One line decides both: **state that
correctness depends on gets an epoch cell or an op that is truth; state that only policy depends
on may be a hint.** A pager therefore ages by `accessed.begin` scans (cheap, licensed-drift) and
*commits* reclaim through `EVICT`/write-protect faults (truth) — the MGLRU shape with the fault
storm removed. **And the reclaim hot path is raceless by sequence, proven here so no pager
re-derives it:** (1) `SUPPLY`-or-`map.protect` the victim clean/WP; (2) read the contents through the
pager's own mapping of the backing (compress or write out); (3) `EVICT` with **`CLEAN_ONLY`**
(§17.7). A store landing between (2) and (3) takes the write-notification fault — so the pager
*hears* about it — and flips the page dirty — so `CLEAN_ONLY` **skips** it; the copy the pager took
is stale and discarded, the page stays resident, and no torn version can ever be the surviving
one. The race is not narrow; it is architecturally unlosable, which is what "one source of truth"
buys on the path where a bitmap would have lied.

**Clone and COW composition (the inheritance rule, one line):** *pager designation and
charge-default ride the backing; a COW split mints the private copy into a child backing that
inherits them; retargeting is a backing op requiring the backing's `CONTROL`.* So a cloned subtree's
shared pages fault against the original backing's pager immediately (the request record names the
faulting domain, and rule (1) tells the pager whom to charge) — clone stays O(1), with no
designation state to copy and no fault-to-nowhere window. **Retargeting is epoch-guarded (the
two-pagers race, closed):** the pager designation is an epoch cell (§3);
`backing.rebind_pager` **bumps it**, and a `SUPPLY` carrying a stale designation-epoch fails `-STALE` (the old pager can never
install frames or charges against a backing it no longer serves), and every fault request pending
against the old designation is **re-delivered to the new pager** — Law 2 verbatim, which is why the
request record carries the epoch it was minted under. **Re-delivery is also the restart model
(stranded waiters, impossible):** the engine, not the pager, owns the outstanding-request set; a
pager (re)binding to a backing receives every outstanding request again — the same
pend-until-registered semantics events already have — so a crashed-and-restarted pager (or a
`RESTAMP`ed replacement, §16.0) resumes service with no replay protocol and no parked thread ever
stranded on a dead pager's memory. `SUPPLY` for an offset with no outstanding request is legal
(readahead); duplicate service of a re-delivered request is idempotent (first install wins,
first-toucher charge unchanged).

**Negative resolution is a primitive, not pager silence.**
`backing.reject rd, backing, request_id, designation_epoch, condition` resolves the named open
request without installing contents. `condition` is one of the
closed machine-semantic set `BOUNDS` (the offset no longer exists, including truncation),
`EXHAUSTED` (the pager cannot satisfy this request under current resources), `FAULT` (backing data
cannot be produced), or `POISONED` (known irrecoverable media/integrity loss). The pager designation
epoch is revalidated exactly as for `SUPPLY`; an old pager cannot reject a successor's request.
For each request, `SUPPLY`, `backing.reject`, pager rebinding, and teardown contend on one
engine-owned terminal-choice cell. Exactly one wins. Reject success is the commit point: the parked
access resumes at its original instruction through the synchronous FAULT gate with
`cause = PAGER_REJECTED`, the original fault address, and `r3 = condition`; it never returns an
in-band error from the load/store. The personality may panic, deliver a SIGBUS-like event, terminate,
retry after changing policy, or otherwise handle that machine fact. Returning without repairing the
cause retries the access and may create a new request. A reject naming no still-open request returns
`-STALE`. Thus OOM is
policy above an explicit terminal result, not an indefinitely parked thread by omission.

**Pager liveness is the pager's problem, stated:** a pager's own
working set must be engine-backed or resident-pinned; a pager that faults into itself has a bug,
not a machine deadlock to arbitrate. **"Composition" is cooperative, not transparent: there is no pager-over-pager stacking
in one backing.** A fault delivers to *its* backing's pager and stops there; a pager whose own
working set is non-resident faults into *its* backing's pager — faults-into-faults, each an
explicit hop, bounded by the resident-working-set rule above. A container pager backed by a host
swap pager is therefore a **written forwarder**: it knows it fetches upstream and forwards
explicitly (post-copy migration is exactly this — the destination pager knows its source). The
model composes because each pager is a forwarder by construction, never because the engine passes
a fault down a stack it does not have.

This one mechanism gives: **overcommit** (the pager allocates lazily), **swap** (evict + refund),
**the page cache** (a file backing whose pager is the file service), **user-level fault handling**
(a backing whose pager is an ordinary domain — the userfaultfd shape as the native fault model),
**post-copy live migration** (a deserialized domain runs immediately while the source-side pager
feeds pages on demand — §16.8), and balloon-free rebalancing (`domain.budget` covers the cooperative
case). **The realtime rule, stated where it bites:** a pager-backed access has pager-bounded—not
reservation-bounded—latency. `RESERVATION` admission records the then-live `PIN_RESIDENT` leases and
the precise VMA/backing ranges they cover as its **RT memory set** (§16.1). CPU scheduling guarantees
hold for the reservation generally; end-to-end execution WCET is conditional on every instruction
fetch, stack/data access, and persistent engine-written range on that execution path lying in the
ledger-covered set. An access outside it is legal and may fault, but leaves that WCET contract for the
execution. Later unpin/mapping/pager/backing operations preserve, revalidate, or fail `-BUSY` for the
recorded set. Thus admission removes the pager from the trusted set only for conforming admitted paths,
for the reservation's full lifetime—not for arbitrary cold data.

**Streaming-mapping doctrine (the map-per-packet question, answered).** A window is an *authority*
object, not a per-buffer cursor: the architected pattern for packet-rate I/O is a **persistent window
over a pool** — construct and `window.seal` once, recycle buffers within it, `TEARDOWN` never on the hot path. An object
lifecycle per packet is the anti-pattern, and the design makes the right pattern the natural one (the
window is epoch-checked, so pool teardown still revokes everything at once, fail-closed).
**`window.remap` (function 6) — the typed bulk remap primitive, because the constituency
stopped being hypothetical:** the persistent-pool pattern is the *native* contract, but the
Linux driver corpus's contract is `dma_map_single`/`dma_unmap_single` per buffer, and a
compatibility layer that must create an object per packet dies on arrival — the port needs a
cheap IOVA re-point, and "the enlightened driver wouldn't need it" is not an answer to a million
unenlightened ones. Semantics, kept exactly as narrow as the seam promised: `REMAP(iova_range,
new_backing_offset)` atomically re-points a page-aligned IOVA range of an **established** window
to different offsets of the **same backing under the same rights and direction** — no object
lifecycle, no authority change (anything wider requires teardown followed by a freshly
constructed and sealed window, deliberately). The
op's execution contract is **split at issue versus acknowledgment, because streaming map and
unmap happen in non-sleeping contexts**: `REMAP` **installs** the new translations, **issues**
the scoped invalidation of the old ones (§11.2 broadcast under `ATS_ACK_BOUND`, this window's
requester only), and returns — it is engine-resident-metadata only (never pageable), never waits
on a software service, memory reclaim, or another thread being scheduled, and its arbitration is
bounded (Appendix C) — **callable from a non-sleeping execution context by construction**. The
acknowledgment completes asynchronously and is observable: the window carries a **monotonic
repoint generation** — the op returns the generation it issued in `rd`;
the `GENERATION` selector and the `ACKNOWLEDGED` selector return the installed and acknowledged generations,
the acknowledged value only ever advancing.
These are also the two usability facts: `issued` is the **installed generation**, while `acked` is
the **submission-safe generation**. Until `acked >= G`, a newly installed mapping at generation `G`
must not be used by a new command because an ATS-capable device may still select the retired
translation for that IOVA. Engine-mediated submission overlapping such a pending range waits, or
returns `-BUSY` under its non-waiting policy. A direct-plane driver must compare the generations and
enforce the same gate before ringing the device. A device profile may substitute specifically named
stronger ordering evidence. For an ATS-denied window installation itself establishes the proof, so
`acked == issued` and the mapping is immediately submission-safe.
**The three-tier temporal rule, so ordinary unmap never pays the full ATS bound:** *(1)* a
**normal unmap** (a re-point away, typically back to the pool) makes the range unavailable to
*new* device translations at install and returns; *(2)* **frame reuse** — returning the
previously-targeted frames to any other use — is legal only once `repoint_acked_generation`
reaches that re-point's generation, **and the engine enforces the pin half of this: the old
frames stay pinned until their re-point acknowledges**, so the window's pin charge transiently
exceeds its steady span by the outstanding re-point ranges (bounded — a granted-but-wedged ATS
device is cut at the fence within `ATS_ACK_BOUND`, §15, which is exactly what bounds the
transient; the accounting table carries the row); *(3)* **forced revocation, `TEARDOWN`, and
removal** keep the strong quiesce/poison protocol. The weak tiers are honest because Linux's own
contract has the driver finish device activity before `dma_unmap_*` — ordinary unmap need not
stop a misbehaving device, and the port recycles IOVAs and frames through a bounded
deferred-reuse ring keyed by generation (roadmap). In-flight *submissions* overlapping a
re-pointed range still drain to a burst boundary before installation (the `quiesce` discipline
applied to one range; absent overlap — the ordinary map/unmap case — there is nothing to drain),
`-BUSY` if that drain window is exhausted. Steady-state pin count and charge are unchanged by
any re-point (same page count in, same out). Class 4 over the handed-in list, no new charge. The
map-per-packet compatibility shim is therefore: one pool window per direction, `REMAP` per
buffer ring-slot reuse — an ordinary warm operation, an object on none.

**The generation model's closure conditions.** *(1)–(2) are the §3 progress-discipline theorems, cited, not restated:*
the repoint generation is a §3 monotone saturating counter, incarnation-scoped, with the reuse
key `{window incarnation, generation}`. The only REMAP-specific facts: saturation fails further
`REMAP` `-EXHAUSTED`, recovery is the re-establishment sequence (quiesce to `acked == issued`,
release pins, tear down, new incarnation at 1), and a recycled handle is `-STALE` at the
ordinary epoch check before any generation is read. *(3) Acknowledgment is cumulative, and what it certifies is the **no-stale-access point**, not a
protocol internal — the safety-critical definition, stated in terms of outcomes:*
**advancement of `repoint_acked_generation` through `G` proves that no request using any mapping
retired at or before `G` can subsequently access its retired backing pages.** Discarding a
cached translation is *not* sufficient — a request may already have passed the device's
translation cache and be queued in the device, the fabric, the root complex, or the memory path
when the invalidation is processed — so the proof may be established by orderly invalidation
completion, by draining or ordering previously-translated requests, or by an acknowledged
fabric fence; **the mechanism is not architectural, the outcome is**. And the evidence rule is
deliberately conservative: **no completion or interrupt observation is universally sufficient
by itself** — a device may complete one queue while another still has DMA outstanding,
interrupt before unrelated posted traffic drains, run autonomous background DMA, retain
translations after command completion, or write outside any software-visible command. So: **a
transport or device profile may define particular completion or interrupt observations as
sufficient evidence for some or all retired mappings (non-normative, per profile); otherwise
the translation-invalidation or fabric-fence path establishes the no-stale-access point.** An
implementation may acknowledge several generations together, and a reuse ring releases
everything through `G` with no per-op checks. *(4) Issue order is
generation order:* one monotonic issued sequence per window, assigned in the order translation
changes become architecturally installed; overlapping batches serialize, disjoint batches may
run internally parallel, and acknowledgment never advances past an unacknowledged earlier
generation — (3) stated from the other side. **Within one batch, IOVA overlap is `-MALFORMED`:**
a batch takes one generation and commits atomically, so two entries claiming the same IOVA
would make install order *inside* the batch a hidden ordering rule — refused. Adjacent entries
are fine; the same backing page appearing under several IOVAs is fine (reference accounting,
(7)). *(5) Retired mappings carry their retiring
generation — and the two granularities stay distinct:* the retired record is keyed **per IOVA
mapping unit** (`{IOVA range, old backing range, generation}`), while pin accounting stays
**summed references per CPU page** — the generation tag attaches to the retired *mapping*,
never reduced to one generation field per physical page. In v1 the two units are both 4 KiB, so
the distinction is invisible; it is stated against the two *objects* (the §15
page-vs-IOVA-leaf decoupling rule) so a future revision that moves either granularity — one
page under several retired leaves, or one leaf over several pages — inherits correct
accounting unchanged. A displaced frame's transient pin releases when its retiring generation
acknowledges *and* no other live mapping or lease references the frame (pin counts are sums,
the §16.3 rule). Re-point IOVA `X` from frame A to B at generation 10, then B to C at 11
before 10 acknowledges: A rides 10, B rides 11, C holds the current pin — 10's acknowledgment
cannot release B; 11's may.
*(6) Unmap is a re-point to `UNMAPPED`:* backing offset `UINT64_MAX` — **reserved definitionally,
in every revision: it is never a valid backing offset**, a fact today provable from leaf
alignment (all-ones is not aligned — the B25 criterion) but frozen as a definition so no future
granularity or offset representation can un-reserve it — installs **no translation** (subsequent device access is an ordinary out-of-window IOMMU
violation), issues invalidation, returns its generation, and holds the displaced pins to
acknowledgment like any re-point. **One temporal transition — old mapping → new mapping or
none** — so there is no second deferred-invalidation model to verify; forced teardown remains
the stronger quiesce. *(7) Pin-budget admission is all-or-none, computed on per-page reference **deltas**, never naïve
page sums:* a page's engine state is its reference set — current window references, retired
references tagged by generation, and independent leases or other windows — and admission
charges (and release refunds) the *delta* this batch produces in that set. The swap case is the
reason: one batch exchanging IOVA `X`↦A, `Y`↦B into `X`↦B, `Y`↦A makes A and B each retired
*and* current simultaneously — delta accounting charges nothing spurious and, at
acknowledgment, releases nothing premature. Insufficient budget for the batch's true transient
delta fails the whole batch `-EXHAUSTED` **before any entry installs**. *(8) ATS-denied windows do not inherit
`ATS_ACK_BOUND`:* with translation caching denied there is no device-side state to chase — the
no-stale-translation point is the fabric/IOMMU installation boundary itself, acknowledgment is
local, and an implementation may return with `acked == issued`; the long bound is the
ATS-granted window's price only. *(9) the `ACKNOWLEDGED` selector carries acquire semantics:* a thread
that reads `repoint_acked_generation >= G` is ordered after the scoped invalidations'
completion, any synthesized fabric fence, the release of the engine-held transient pins, and
any poison publication — frames and IOVA ranges through `G` are reusable with **no further
device fence**. *(10) Poison never hides behind acknowledgment:* when a granted-but-wedged
device is fence-cut, acknowledgment legitimately advances — stale access has become impossible,
memory is safe — and the `STATUS` selector says how: bit2 `REPOINT_PENDING` — **derived
state by definition, `repoint_issued_generation != repoint_acked_generation`, never stored
independently** (stored, it could contradict the generations it summarizes) — bit3 `POISONED`,
bit4 `FENCE_SYNTHESIZED_ACK` (both genuine state, both sticky where marked). *Memory safe to
reuse* and *device safe to keep using* are different facts, and the flags keep them apart — the
port releases frames and simultaneously stops submitting. *(11) Serialization produces a dormant
recipe, never a live window:* every issued re-point first reaches acknowledgment or fabric-fence
completion (`issued == acked`, transient pins zero). The engine snapshots the current IOVA layout,
backing offsets, rights, direction, and profile requirements as a **dormant window recipe**, then
tears down the source device binding. No requester/device incarnation, ATS state, issued/acked counter,
pin, or deferred-reuse queue travels. `state.import` creates a state-import builder carrying that
recipe. An authorized driver satisfies its typed `REBIND_REQUIRED` Device and completion
dependencies with `state.bind`; `state.commit` is the sole terminal and evaluates the same closed
publication predicate as `window.seal`. Class-builder functions, including `window.device`, reject
an import builder with `-BADREF`.
*(12) Teardown and removal synthesize a terminal prefix acknowledgment:* once the fabric fence
is acknowledged, `acked` advances through **all** issued generations, every transient pin
becomes releasable, `REPOINT_PENDING` is false (it is derived), `POISONED` stays true,
`FENCE_SYNTHESIZED_ACK` stays sticky, and submissions and new re-points remain prohibited —
accounting reaches a clean terminal state without ever pretending the device recovered.
**And the accounting answer, decided:
transient pins are charged to the window's pinning domain** — the party that chose to re-point
ahead of acknowledgment — which is deliberate backpressure: a driver re-pointing faster than
acknowledgments arrive exhausts *its own* budget (visible as `transient_pin_pages`, the port's
throttle signal), unrelated domains are untouched, and a device failure can never become
unattributed machine-wide memory retention. On teardown or removal the charge persists until
the fence makes release safe.

**The whole mapping lifecycle then *derives* from the conditions above — no independent state
machine to specify, which is the point:**

```
CURRENT   --REMAP-->   new INSTALLED_PENDING(G) + old RETIRED(G) (conditions 4, 5)
INSTALLED_PENDING(G) --ack >= G--> CURRENT
CURRENT   --UNMAP-->   UNMAPPED    + old RETIRED(G)          (condition 6)
RETIRED(G) --acked >= G-->  RELEASED                          (conditions 3, 5, 9)
any active --timeout/failed invalidation--> fabric fence
           --> terminal cumulative ack --> POISONED           (conditions 10, 12)
POISONED   --> no submissions, no re-points;
               teardown + fresh construction/sealing is the only exit (conditions 1, 12)
```

`REPOINT_PENDING` is not a state in this machine — it is the derived comparison of the two
counters (condition 10) — and every transition's pin and charge effect is already fixed by
conditions 5, 7, and the accounting rule, so an implementation that satisfies the twelve
numbered conditions has this machine whether or not it ever drew it.

**The generality theorem** (`REMAP` proves compatibility for arbitrary drivers, not
only pool-oriented ones — two halves, one software and one hardware.** *The software half — the
one-backing namespace guarantee:* nothing in this document bounds a backing below its domain's
memory budget, so a personality may structure **its entire RAM as one backing** and the Linux
port does exactly that (roadmap): every `kmalloc` allocation, slab object, page-allocator page,
skb fragment, block-layer bio, filesystem page, and userspace-pinned page is then an offset in
**one stable page namespace**, and `dma_map_single`/`dma_map_page`/`dma_map_sg` over arbitrary
kernel buffers resolve to same-backing offsets — which is precisely what `REMAP` re-points. The
same-backing rule is not the limitation it looks like; it is the **authority theorem that makes
the op fast**: re-pointing within the `window.seal`-time backing can never change the window's
authority footprint, so `REMAP` performs **no new authority derivation** — its checks reduce to
live-window and epoch validation plus containment (requester identity, IOVA range inside the
window, every backing offset inside the established backing, alignment and overflow, overlap
rules, direction, pin-budget availability, batch count and structure), all local facts of state
the window already owns — which is what "packet rates" means without ever meaning unchecked
input. A cross-backing re-point *would be* an authority change and is therefore spelled
teardown followed by fresh construction and `window.seal`, deliberately. *The hardware half —
the batched scatter form,* because a scatterlist must not cost
one instruction per fragment: `window.remap_one rd, window, iova, backing_offset, len` is the
register-only single-extent path. `window.remap rd, window, extent_ptr, extent_count` names a
homogeneous array of 24-byte `{iova u64, backing_offset u64, len u64}` extents; pointer and count
are fixed register operands and the sequence has no header, flags, selector, or operation-wide
fields. `extent_count` is `1..SGL_MAX`. All entries
name the same backing under the same rights and direction (the theorem above); the list is
engine-snapshotted and validated whole pre-effect (§17.8's SGL rule), installed **atomically —
all entries or none, `-MALFORMED`/`-DENIED` name the first offender and install nothing**; each
4 KiB IOVA leaf re-points independently, so discontiguous pages are the ordinary case, not a
special one. **The engine guarantees the compatibility layer stands on, enumerated so the claim
is falsifiable:** (1) IOVA placement is caller-chosen during window construction and committed by
`window.seal` — a window placed below
2^32 satisfies a 32-bit streaming mask, distinct windows give independent coherent/streaming
masks, and IOVA allocation *within* a window is pure software, no engine op; (2) discontiguous
backing pages map in one op via the batch form; (3) the engine never merges or splits entries —
segment construction, boundary rules, and merged-entry counts are the layer's arithmetic over
offsets it chose itself; (4) a re-point invalidates **only the affected leaves for this window's
requester** — never a global shootdown, which is what "reuse at packet rates" means physically;
(5) per-entry cost is bounded (class 4 over the handed-in list) and unmap is re-point-to-pool or
`TEARDOWN`, so "every streaming map is eventually unmapped" is the port's ledger entry, not an
engine mystery.

**Window concurrency:**
one requester — one isolation group — may hold **multiple simultaneously established windows
over disjoint IOVA ranges**, each with its own backing, rights, and direction; the IOMMU selects
by IOVA range within the common requester scope. So normal-RAM rings and descriptors, a peer
device's BAR aperture (below), and imported buffer storage coexist for one device as ordinary
windows. A batch stays single-window and therefore single-backing (the authority theorem); a
mixed scatterlist partitions by backing in the compatibility layer, which presents the resulting
DMA segments normally (roadmap). **And the sub-leaf byte recipe, canonical with its exposure
honest:** a mapping may begin at any byte offset and cover any length — round the backing offset
down to the IOVA-leaf boundary, cover every containing leaf through the rounded-up end, pin
every containing CPU page, return the mapped IOVA plus the intra-leaf byte offset. **Device
authority is leaf-granular: v1 IOMMU bounds never narrow below the 4 KiB leaf, so a 100-byte map
exposes its containing leaves to the device** — stated as a rule so the mapping layer *knows*
the exposure and chooses its policy (bounce or pool pages beside sensitive co-residents) rather
than discovering it in a security review. **Device constraints are discoverable before
mapping:** streaming and coherent DMA masks, maximum segment size, segment-boundary mask,
maximum mapping size, alignment, maximum scatter entries, contiguous-IOVA constructibility, and
supported directions are **served records** — bus-service data (§16.6) plus the window's
`GEOMETRY` facts — which the port's IOVA allocator reads and enforces; the engine serves them
and never interprets them, so no ISA opcode grows a device-quirk vocabulary.

**Peer-to-peer DMA (permitted, one sentence).** A DMA window's backing capability may be **another
device's BAR capability** (not only domain memory): a NIC writing straight into an accelerator's memory
aperture is a window whose backing is that BAR cap, confined by *both* capabilities and both requester
scopes — peer-transfer patterns fall out of the existing model with no new mechanism, same
revocation/quiesce rules.

**DMA ordering (so driver sequences are unambiguous).** A copy submission (`send` to the window facet) has **release** semantics for
the source: all of the issuing core's prior stores to a `normal_cached` source buffer are visible to the
device before it reads them — **no fence before submit**. Observing completion (the `wait`/`recv` on the
CompletionQueue) has **acquire** semantics for the destination: after it, the CPU sees
all of the device's writes to a `normal_cached` destination — **no fence after completion**. **The
acquire rule is a property of CompletionQueue machinery, not of the submission path:** observing any
hardware-producer completion record — a DMAWindow copy or a WorkQueue submission (§10.2) alike —
carries the same acquire semantics, so no shim ever needs a defensive fence after `wait`/`recv` on a
completion. These cover `normal_cached` and `uncached` buffers (the coherent-DMA mandate); a
`write_combining` or `device_ordered` region used as a DMA buffer is **not** covered and requires an
explicit `fence`, because its ordering is outside the coherence-fabric acquire/release.

**Interrupts.** Device interrupts are **interrupt-as-waitable**: each source (MSI/MSI-X for PCIe, a
wired line for soft-IP) is a hardware-producer endpoint that joins a waitset and is consumed by `wait`
(§10.3) or delivered as a machine-call event (§9.3). There is no software-visible raw interrupt-vector
table; routing is the scheduler/endpoint path, and **MSI is required for a device that presents as
*multiple* endpoints** — the rule is about endpoint multiplicity, not about barring legacy silicon.
**Legacy PCIe INTx presents as a wired-line source through the bus service** — the bus service maps
the device's INTx pin to the wired-line `BIND` form, so a pre-MSI device is a first-class single
source, not an unsupported one. **INTx — including the shared-line fallback some devices take on
error paths — is exactly that `BIND` form, not a gap:** a level-triggered line may back multiple InterruptWaitables
(each masked and acknowledged independently; the `explicit-ack` delivery mode — `irq.delivery`'s
`ack_mode` builder fact, §16.3 — is the shared-line
discipline, since auto-ack on a shared level line would storm). No INTx-specific mechanism exists,
and none is needed. **And the interrupt-observation ordering rule, stated because every Linux
driver assumes it silently:** when a thread observes an InterruptWaitable's readiness — through
`wait` or machine-call delivery — **every DMA write the device issued before signaling that
vector is already visible** to the observer's ordinary loads. This is not a new fence: mandated
coherent DMA (a transfer joins the coherence fabric before any of the device's later signals) plus
the fabric's write-then-signal ordering make it a theorem, but it is written here as a rule so
"handler reads the completion ring after the IRQ" is a contract, never a race the platform
happens to win.
**Affinity/steering vocabulary (half pinned, half named):** *thread and domain placement* is
**`dplace`** (§16.1/§17.7: an **immutable set of view-tile identifiers** — the engine translates
through the domain's MachineView (§16.7), hierarchical subset-of-parent like every budget dimension;
the empty set selects inherit, and no tile-count ceiling is frozen into the ABI). The
missing half is **wake steering**: `InterruptWaitable BIND` reserves a **steering hint field** (deliver
this source's wake toward view-tile *T* — hint-class, the scheduler may honor; placement, never
semantics), so per-queue drivers can co-locate interrupt, thread, and (via the cache-injection seam
below) data on one tile. Reserved now with the field named. **And the placement policy boundary,
normative because an autonomous "gravity" engine is the tempting wrong design: the engine never
moves anything on its own initiative.** Every migration of a thread, frame, or interrupt route is
a software-issued verb (`domain.place`, `home_hint`, `backing.rehome`, the steering hint) — hardware
supplies **actuators** (those verbs, each with bounded, stated cost) and **sensors** (the §16.7
locality metric, the window `GEOMETRY` distance facts, the `GATE_AFFINITY` seam when it lands —
all view-local, Law 7), and the *policy* — which affinity group moves, when, with what hysteresis
and anti-thrash damping — is software's, because an opaque hardware mover would fight the
language runtime, the kernel scheduler, and the pager simultaneously, and none of them could see
why. A machine that placed threads autonomously would be un-debuggable from inside its own views;
this one is deliberately inert until asked.
**V1 sensor limit:** the locality metric and distance counters describe where communication would
cost, not which domains actually communicate. `GATE_AFFINITY` is not a v1 source of truth.
A gravity scheduler must use software-instrumented call-chain/service telemetry or whatever
view-scoped PMU sampling its implementation exposes; the base ISA alone supplies no complete
attraction graph. Actuation is therefore stronger than observation in v1, deliberately and visibly.

**Enumeration and translation. A machine is a capability table, and a device is a capability.**
Physical devices do not exist for a Domain unless Device capabilities were installed in its table.
Reset, delegation, and software virtualization use that one path. A driver enumerates CAPS, matches
class 21 plus `device.profile`, and obtains typed resources with `device.get`; the engine never scans
a bus, parses configuration space, constructs a resource-number namespace, or interprets a firmware
tree. A PCIe host service may enumerate config space through a Device member and publish one Device
per function. An SoC controller is simply a reset-granted Device. Kernel ports may synthesize their
own `struct resource`, irq-domain numbers, or in-memory firmware tree from the profile registry;
those numbers and trees are OS-private compatibility artifacts, never architectural facts. Address
translation is **hardware-walked** over the VMA tree, and TLB/translation entries are **domain-tagged
and epoch-guarded** (§3) (*hardened-policy note:* a shared domain-tagged TLB is a cross-domain timing
channel — occupancy is observable via miss latency — so a hardened isolation configuration is expected to
**set-partition TLB capacity per domain-tag**; the base profile shares capacity, and the
noninterference proof drives the final decision): a `gate_call` switches protection context without a
TLB flush (flush-free, §9.2), and `munmap`/`map.protect`/`dreplace.commit` invalidate by **bumping the VMA's
epoch cell + a hardware-broadcast invalidate** (§11.2) rather than a software-IPI shootdown. There are
**no software TLB-management instructions**; `isync` is the only explicit invalidate and only for the
i-cache on code patching (§6). **Backing-tagged shared read-only translations (the density fix —
a thousand containers must not hold a thousand TLB entries for one libc text page):** a mapping
that is **read-only-or-execute, permission-uniform, and backed by a shared backing immutable while
mapped** may be tagged at **backing identity** rather than domain identity — one TLB entry serves
every mapper, **epoch-keyed on the backing's distinct backing-translation cell**, so invalidation
semantics are unchanged (its bump kills the one shared entry exactly as a VMA bump kills a private
one). This is not the backing's object-lineage cell: invalidating a translated frame must not revoke
capabilities to the backing. `SUPPLY` of a new frame, `EVICT`, `backing.rehome`, leaf demotion, destruction,
and an immutable-to-mutable transition advance the translation cell under §3's acknowledgement rule.
Its replicas, directory, and referent-span accounting are charged to the backing owner. Nothing
writable is ever shared-tagged, so isolation of *contents* is untouched; the residual — named,
because it is real — is that **co-residency of a shared backing is observable through hit timing**,
and the hardened configuration answers it the same way it answers shared TLB capacity: a per-domain
policy disables shared-tagging (the partition knob's sibling). The side dividend: shared text stops
consuming `DOMAIN_TAG_CAPACITY` proportionally to tenancy.

**The translation-depth invariant (load-bearing, so it is stated, not inferred): translation
cost is independent of domain-ancestry depth.** LNP64 nests *authority*, never *translation*:
there is no second-level translation anywhere in the model, so a domain 10 levels deep walks
**its own** VMA tree once and hits a domain-tagged TLB entry in O(1); depth never appears in
the address path, and so cannot leak through translation latency (Law 7). Under COW chains,
walk depth is **radix-bounded (by address width), never ancestry-bounded**. **The one honest
pressure point:** deep stacks mean many *live domain tags*; tag exhaustion (forcing a retag
sweep) is the single place deep nesting could reintroduce a flush-like cost — so live-tag
capacity is a **`GEOMETRY` field** (`DOMAIN_TAG_CAPACITY`, floored at **256** in §16.4), and a
hardened/RT deployment sizes its nesting to it. **The tag namespace is volume-local**: a
translation is only ever cached within its domain's volume (cross-volume sharing is
unconstructible, §15), so the floor is per-volume and cross-volume tag reconciliation does not
exist. **The bounded worst case:** tag recycling invalidates **at domain-tag granularity,
never whole-TLB** — even at exhaustion the cost is a per-tag sweep, not a chip-wide shootdown.
**What the invariant costs:** no-nested-translation is purchased by **forbidding guest-owned
translation formats** — a nested LNP64 kernel manages its children through the AS facet
against the one VMA tree; there are no guest page tables to shadow because guests cannot have
page tables. A foreign-ISA guest brings its own page-table format and gets zero hardware MMU
assist (the pre-EPT software-MMU world) — a refusal, not a gap: a second translation format is
the one thing this machine will never grow. (Budget carving has the dual soft cost: static
sub-division strands capacity in intermediate domains — a utilization tax `domain.budget`
rebalancing recovers — and `dbudget.charge_through` deletes it for ephemeral children, §17.7.
The control-plane twin — native intrinsics execute against flattened effective state at any
depth — is §11.)

**The accelerator surface: one addition, four named seams.**

*Hardware-consumer WorkQueue endpoints (the addition — the taxonomy was one row away).* The endpoint
model gains the dual of the hardware producer: a **WorkQueue** (`obj_class` 14) is an endpoint
**drained by a device** — the consumer side is a *property* of this one class, not a new taxonomy axis
(§16.2). Construction is unpublished: `workqueue.new` creates the builder;
`workqueue.device` and `workqueue.completion` add the device and CompletionQueue relationships,
and `workqueue.seal` publishes atomically. `workqueue.teardown`/fixed scalar getters and the
**frozen `send` schema** (§10.2: descriptor bytes bounded by
`WORKQUEUE_DESC_MAX`, no caps in v1, `rd` = the submission handle keying the 24 B completion record,
completion slot reserved at submit, **release semantics** so the coherent path needs no fence),
waitable-for-`WRITABLE` backpressure, the §16.4 WCET bounds, and fixed scalar getters for
`free_slots`, `queue_depth`, `max_desc_len`, and status flags. `send` to a WorkQueue
**is architected work submission**, so a
foreign accelerator inherits capabilities, budgets, waitables, and completion semantics for free.
**The two queue idioms are both native, split by where authority sits:** the WorkQueue is the
**mediated** plane — the engine touches every submission, so per-submission accounting and
capability semantics come built in — and the mapped-BAR + ring + doorbell pattern (§6 doorbell
contract) is the **delegated direct** plane, the hot path when authority was granted up front
(the QueuePortal composition below). Neither is the compatibility case; they are the two prices
of the same contract.

**The native device architecture — three planes and two memory modes.** The design center for new
software is stated here once, because every piece already exists. **Plane 1, lifecycle and
configuration (slow, asynchronous, device-ugly):** the Device profile closes the bundle of group
identity, register-aperture capabilities, authority to establish windows, pools, and portals, and
lifecycle/error endpoints. An isolation group is a Device and may contain Devices. BDF
and requester IDs, MSI-X table programming, ATS/PASID plumbing, ACS topology, FLR and bus
resets, AER/DPC, SR-IOV, hotplug, and posted-transaction quirks live **inside the device service and
nowhere else** — the fabric edge absorbs PCIe so the machine's ontology does not. The
reset/power member is the Device's lifecycle facet over verbs this section already architected:
group quarantine, the fabric fence, the terminal-state protocol, the two power classes, and
re-plug-as-new-incarnation. **Plane 2, the queue data plane:** a **QueuePortal** is the *named
composition* — submission and completion rings in client-owned memory over a device-mapped
pool; the doorbell as a `mem_grant` **sub-range** of the Device's `device_ordered` BAR member
(delegation at doorbell granularity, not BAR granularity); the queue's MSI/MSI-X vector as its
own `InterruptWaitable` (readiness on the portal, not an interrupt number); indices, descriptor
formats, and ownership protocol vendor-opaque, exactly as the machine never parses device
descriptors. **Publish is the §6 doorbell contract** — descriptor and payload stores,
`fence.rel`, the `device_ordered` doorbell store — ordinary code that an implementation may
execute with the tail as one internal publish op under the general cracking license (§4.3), so
the hot doorbell needs no new opcode, no engine transaction, and no translation or capability
re-validation beyond what the mapping already caches. Completion is device DMA into the completion ring plus the
interrupt-observation ordering rule above — poll, wait, or adaptive-poll-then-sleep is the
owner's choice per queue, with steering per the placement verbs; no generic hard-IRQ handler
exists on this path, and MSI-X is a **transport** the proxy converts to readiness, never an
architectural interrupt model. Delegating a portal and pool to an application domain is
ordinary capability delegation — one NVMe queue pair, NIC queue, GPU context, or accelerator
queue per client — with the driver domain retaining Plane 1. **Plane 3, device memory — the
two modes:** *persistent-pool mode* is the primary path: a **BufferPool** is a backing plus
long-lived established windows (the **DeviceAddressSpace** role is the group's IOVA space those
windows populate, §15 window concurrency) whose device addresses are **stable for the pool's
lifetime**; at packet rate software moves **buffer ownership, not mappings** — the ownership
states (`CPU_OWNED`, `DEVICE_READABLE`, `DEVICE_WRITABLE`, `SHARED_COHERENT`, `RETIRING`,
`POISONED`) are the *served contract vocabulary* of the ring protocol, enforced by the queue
discipline the descriptors encode, while hardware authority stays static. **And the price of
the direct plane, stated where it is paid: these states are protocol, never per-buffer
hardware confinement.** The engine does not inspect opaque vendor descriptors, so it cannot
know which completion returns ownership of which buffer — the IOMMU confines the device to the
**pool**, not each request to the buffers that request named; a buggy or malicious device
reaches any page the persistent window permits, and a buggy direct-plane driver can violate
the ownership protocol without the engine noticing. Completion-bound *automatic* authority
return exists only where a mediated mechanism observes the submission — the WorkQueue plane,
which is exactly when to choose it. Pool granularity is the direct plane's trust unit by
construction; "ownership moves over the ring" must never be read as an engine-enforced
per-packet permission transition. Physical frames may
move beneath a stable device address: `backing.rehome` of device-mapped frames rides the window
generation model above — install the new translation, retain the old frame's pin to the
no-stale-access point — so the device-visible address never changes while placement improves.
*Dynamic-grant mode* — irregular operations without a permanent pool — **is the `REMAP`
generation machinery, not a second mechanism**: grant = batch re-point in (bounded,
non-sleeping), retire = re-point to `UNMAPPED` at completion resolution, reuse gates on the
cumulative acknowledgment, the twelve closure conditions apply verbatim; the Linux `dma_map_*`
layer is simply this mode's largest client, and nothing about it is compatibility-only. **The
audit's verdict, recorded so the ontology stays flat:** register apertures, DMA address spaces,
buffer pools, and notification endpoints remain existing objects carried as Device members;
QueuePortal adds exactly one thing — the publish fusion blessing — and no parallel engine device
taxonomy exists. A native guest inherits all of it by delegation (a Device, a
virtual function, a portal subset, or a driver-service cap) at its own view depth — no
emulated PCI, no hot-path configuration transactions, the ordinary nesting rules (authority
follows capabilities, identities re-key, translations gain no ancestry depth). A crashed
driver domain is the standing revocation story: queue authority revoked, submissions stop,
the group quiesces or fences, buffers hold to the no-stale-access point, the device resets if
needed, and the successor is `RESTAMP`ed into the same exported service objects (§16.3) — the
machine keeps the clients, the driver was always replaceable. **The succession invariant, kept
visible: `RESTAMP` repairs *service* identity and never heals a stale *device* incarnation** —
if recovery went through reset or re-plug, the successor establishes fresh windows, portals,
and group identity (Law 2's no-resurrection rule) even while the client-facing service
capabilities survive unchanged. What no plane pretends to
absorb: vendor descriptor formats, firmware protocols, reset errata, autonomous background
DMA, and device-specific recovery remain driver software — a machine that parsed vendor
descriptors would be promising a universal hardware driver, which is a lie no ISA should
freeze. And every firmware object that crosses the proxy's lifecycle plane is bound by the
ownership covenant: OS-installed firmware is free/libre with free tools, and nonfree firmware
is factory-resident circuitry, never a blob (Appendix H4/H5).

*Named seams (reserved, deliberately not designed here):*
- **`DMA_PAGE_REQUEST` (PRI / recoverable device faults — the device-side SVA gap):** v1 windows pin or
  are established up front; the reserved profile is device-initiated page requests delivered as
  messages to the owning pager — **the same pager-endpoint shape `PagedBacking` architects for the CPU
  side above**, so shared-virtual-addressing lands additively on an existing pattern (accelerators work
  in iova windows until then). **Sub-RID scoping (PASID-class) is reserved on this same seam:** v1
  shares one accelerator across domains by SR-IOV virtual functions or window-per-tenant
  multiplexing through a service domain; when SVA/PRI lands, per-request scope identifiers ride the
  window construction additively — nothing else may claim that meaning.
- **`DEVICE_ERROR` reporting (AER-class) — designed, promoted from its reservation, because a
  production PCIe host cannot treat error *reporting* as a future nicety when the recovery
  choreography (§11.2 poison→FLR→fresh window construction and sealing) is already frozen and needs an input:**
  *containment* is already the window (a
  device that DMAs garbage within its grant corrupts only what it was granted — that is the model
  working, not failing); the *reporting* route is now architected on both paths. The
  *synchronous* MMIO bus-error (a faulting `ld`/`sd`) is already the §15 machine call. The
  *asynchronous* fabric error — a device or link raising an error with no in-flight instruction
  to fault — lands as a **device-error record on an endpoint the bus service drains**, frozen
  shape: `{version u32, length u32, requester_id u64 (view-scoped, §16.7), error_class u32
  (0 correctable, 1 non-fatal, 2 fatal, 3 link), containment u32 (0 none, 1 fenced, 2
  poisoned — what the fabric already *did*, reported not requested), header_log[64]B opaque}` —
  the opaque log carried for the bus service's protocol-level triage, never parsed by the engine
  (the §16.6 catalog rule: transport-specific detail rides opaque, the architected fields are
  what the choreography keys on). `error_class` 2/3 records arrive with `containment != 0`,
  because fatal containment is the fabric's reflex (§11.2), not software's decision — the record
  is the notification that recovery may begin, which is exactly the DPC shape done in the right
  order. Observer-pays: records drain over the bus service's endpoint per the §16.4 telemetry
  direction.
- **Cache-injection steering (DDIO-class):** "land this device write in the consuming core's cache
  level" — reserved as a DMA-window / copy-descriptor attribute (hint-class: placement only, never
  semantics).
- **Device-issued atomics:** devices get coherent access to their windows' backings in v1 (scoped by each backing's volume, §15 — I/O coherence is a volume property like all coherence); finer contracts (a device
  issuing `amo`-class ops with LNP64 ordering semantics) are a named future extension of the §6
  far-execution model.
- **Devices as capability-holding principals:** today a device is an *object* confined by
  windows; the reserved direction is a **device-backed domain** — an accelerator holding its own
  capability table, participating in gates and endpoints like any domain. The line is one predicate
  (Law 3): holds capabilities → domain; doesn't → substrate or object. Nothing new may squat between
  "device object" and "device domain."

## 16. Domain-native machine operations

Domain, authority, hardware-object, set, cursor, and stream operations are **fixed-form typed
instructions executed by the engines** (Law 3: anonymous substrate, `exec_class = HW_BOUNDED`).
Their opcode family and encoded function determine every operand position, meaning, right, result,
failure, ordering rule, and commit point. There is no generic `{class, op, version, lengths}` control
envelope, no hardware-decoded capability or result array, and no preconstructed domain template.
Service-owned semantics leave silicon only through `gate_call`, `dcall`, `send`, `recv`, `read`, and
`write`; their protocol bodies remain opaque to the engine.

The architecture names **effective relations, constraints, and commit points—never their data
structures**. An implementation may represent, normalize, defer, fuse, distribute, cache, compile, or
reconstruct that state by any method preserving specified observations, authority rules, ordering,
accounting, failures, and bounds. A family opcode with fixed encoded subfunctions is an instruction
algebra, not an envelope.

### 16.0 Typed-family encoding and routing

Every family uses the R-format register slots and `func[7:0]` in otherwise-unused low bits. Each
hardware-object class has its **own opcode**; no instruction encodes an object-class selector.
All bits not assigned by that function are reserved-zero. A function's operand list below maps
left-to-right onto `rd, rs1..rs5`; an operand in braces is encoded in that function's explicitly
assigned low-bit field. Functions needing more independent facts are deliberately split into
multiple typed instructions. No function decodes a memory-resident operation schema.

The engine derives required rights from the selected function and validates every capability operand
against that fixed schema. Software supplies no asserted-rights field. The engine performs the §3 slot
and lineage checks appropriate to each operand; a cell operation such as `cap.restamp` checks the slot
but definitionally does not reject the lineage cell it is repairing. Known function + wrong class is
`-BADREF`; malformed values are `-MALFORMED`; denied rights are `-DENIED`; stale generations are
`-STALE`; a reserved function is an illegal instruction. For a §1 full-range raw getter those same
validation failures are precise synchronous instruction faults rather than in-band conditions, and
the destination remains unchanged.

Scalar facts return in registers. The full-range raw getters enumerated in §1 use precise faults,
not in-band negative conditions, so bit 63 remains data. Collections return opaque cursors. Byte representations return
streams. Service-defined semantics use gates or endpoints. Self-describing byte records retain their
own version/length framing, but that framing belongs to the typed stream or service protocol and is
never a universal control header.

**Frozen function numbers.** `domain.build`: `0 dnew`, `1 dfork`, `2 dcompartment`, `3 dmap`,
`4 dmap.shared`, `5 dunmap`, `6 dprotect`, `7 dhome`, `8..9 retired`,
`10 dstate.cow`, `11 dstate.move`, `12 dstate.share_ro`,
`13 dstate.registers`, `14 dgrant`, `15 dmove`, `16 dgrantm`, `17 dmovem`, `18 dlimit`,
`19 dsealcap`, `20 dself`, `21 dslot.persist`, `22 dslot.drop_on_replace`, `23 dview`,
`24 dclock`, `25 dservice`, `26 dbudget`, `27 dbudget.charge_through`, `28 dplace`,
`29 dsched.timeshare`, `30 dsched.fixed`, `31 dsched.reservation`, `32 djit`, `33 dentry`,
`34 dstack.new`, `35 dstack.use`, `36 dgates`, `37 dabi`, `38 dseal`, `39 dstart`,
`40 dabort`, `41 dspawn`, `42 dreplace`, `43 dreplace.commit`, `44 dmeasure`,
`45 dreplace.mode`, `46 dstartup`, `47 dbind.prepare`; `48..255` reserved.
Functions 8 and 9 are retired and remain dark.  The last
two assignments are additive reconciliations of the service-binding proposal: its draft numbers
45--47 predated the already-live `dreplace.mode` and `dstartup` assignments and are not encodings.
`dreplace` creates an unpublished builder for replacement of an existing domain's executable state;
ordinary builder operations describe the prospective state, and `dreplace.commit` is its sole atomic
publication point. `dstartup rd,builder,metadata_ptr` replaces the prospective STARTUP metadata
fact. A nonzero pointer must name at least 32 readable bytes in the prospective address space at
publication or publication fails `-MALFORMED`; `0` is the declared no-personality-metadata sentinel.
The pointer publishes atomically with the new address space and therefore never names the retired
image. Its body remains personality-defined; no image plan is chip-decoded. `domain.exec`: `0 dcall`, `1 dtail`,
`2 dret`, `3 dyield`, `4 dresume`, `5 dexit`, `6 dstop`, `7 dkill`, `8 djoin`,
`9 dreparent`, `10 thread.rseq`, `11 event.post`, `12 event.disposition`, `13 reserved`,
`14 dget`, `15 dget2`, `16 event.default`, `17 domain.budget`,
`18 domain.place`, `19 domain.reserve`, `20 thread.sched`, `21 thread.new`, `22 thread.exit`,
`23 thread.ctid`, `24 thread.place`, `25 acopy.in`, `26 acopy.out`, `27 acopy.instr`,
`28 acopy.outstr`, `29 thread.group`; `30..255` reserved.  The `acopy.*` and
`thread.group` assignments follow the current thread-control block; the proposal's draft numbers
20--24 predated that block and are not encodings. `thread.sched
rd, tid, sched_class, p0, p1` applies only to a thread in the issuing domain; raising it above
the domain's class or ceiling is `-DENIED`. `event.post` takes the unambiguous form
`event.post rd, domain, event_class, payload, target, target_kind`. `target_kind` is `0 ANY`
(`target` reserved-zero), `1 THREAD` (target is a thread id), or `2 GROUP` (target is packed
`{group_id u32,generation u32}` with group in bits `[31:0]` and generation in `[63:32]`);
other values are `-MALFORMED`. A stale thread or eligibility
generation is `-STALE`, and no event is
queued. Each `dget` selector has a fixed
single-register result and each `dget2` selector has a fixed register-pair result; collections use
cursors instead. `cap`: `0 copy`, `1 move`, `2 narrow`, `3 revoke`, `4 revoke_cancel`,
`5 revoke_wait`, `6 revoke_poison`, `7 weaken`, `8 upgrade`, `9 seal`, `10 restamp`,
`11 cell.repoint.prepare`, `12 cell.repoint.commit`, `13 cell.repoint.abort`, `14 rights`,
`15 class`, `16 lineage`, `17 drop`, `18 mint_service`; `19..255` reserved.  The
proposal's draft cap function 17 for `cap.mint_service` predated `cap.drop`; preserving the
cleanup primitive makes 18 the canonical additive assignment. **`cap.drop` releases the caller's
slot and is the cleanup primitive, pinned like `free`:** infallible on a live handle — no
budget check, no block, no park (refund-shaped, a shed-rule member §16.2) — and idempotent on
a dead or stale one (returns `-STALE`, changes nothing), so unwind paths and `Drop` impls emit
it with no error edge; last-reference reclamation follows §16.3's rule.
`mapping`: `0 map.new`, `1 map.private`, `2 map.shared`, `3 map.anywhere`, `4 map.at`,
`5 map.noreplace`, `6 map.reserve`, `7 map.home`, `8 map.leaf`, `9 map.growdown`,
`10 map.type`, `11 map.protection`, `12 map.seal`, `13 map.abort`, `14 mmap`,
`15 map.populate`, `16 map.discard`, `17 map.reclaimable`, `18 map.constrain`,
`19 map.prefer`; `20..255` reserved.
`set`: `0 new`, `1 add`, `2 range`, `3 remove`,
`4 union`, `5 intersect`, `6 subset`; `7..255` reserved. `cursor`: `0 denum.begin`,
`1 objenum.begin`, `2 next`, `3 end`, `4 changes.begin`, `5..6 reserved`,
`7 incident.begin`; `8..255` reserved. Dirty/accessed enumeration is owned solely by the
PagedBacking family (`0xc8` functions 16 and 12 respectively); the superseded cursor-family
duplicates are illegal instructions. `state`: `0 open`, `1 import`,
`2 commit`, `3 state.bind`; `4..255` reserved. `state.bind rd, builder, dep_ref,
replacement_cap` records an external-dependency binding in the unpublished import
builder and revalidates its class and liveness at commit. `observe`: `0 observe.mark`, `1 incident.bind`,
`2 incident.ack`; `3..255` reserved.
`lifecycle`: `0 quiesce`, `1 resume`, `2 activity.cancel`, `3 queue.drain`, `4 lifecycle.destroy` (make the object permanently dead per its class-defined teardown obligations — the one destruction verb; drains only the selected aggregation, never graph-traversing); `5..255` reserved.
The per-class object opcodes and their fixed functions are cataloged in §17.7. They do not share a
constructor, getter, or mutation function number merely for visual uniformity.

**The normative object ontology:** every concrete engine object has one identity, one capability
class, and one class-specific opcode family. The decoded opcode fixes the operand types, rights,
result shape, failure model, ordering, and cost class; the target capability must have that class or
the instruction fails `-BADREF`. Readiness is a common relation consumed by `waitset.add`, not a
second dispatch interface. A resolved FileDescription's byte endpoint is named explicitly by a
ChannelEndpoint capability. A DMAWindow and its WorkQueue submission facet are likewise separate
typed capabilities minted together when requested. There is no dynamic interface attachment,
class/function lookup, inheritance lattice, or universal object-method instruction.

A **hardware-owned class** (§16.1–§16.4) is executed by the relevant engine in bounded time. A
**service-owned class** (§16.5) is dispatched as an internal `gate_call` through the per-object route
stamped by `cap.mint_service`. That route belongs to the object and travels with every alias and
re-key; there is no service-group cell, class registration table, or continuity-class machinery.

A third execution class, **`ENGINE_MEDIATED_SERVICE`**, covers a bounded engine prefix and atomic
engine commit around a service operation whose completion may block. It is not a third ownership
kind: hardware-owned state remains hardware-owned and the service endpoint remains explicitly
service-owned. Real-time admission treats both service execution classes as potentially blocking;
only `HW_BOUNDED` satisfies bounded-operation admission.

**Service-object v1 stamp.** A service object carries one stamp shared by every alias and re-key:
`{gate route, service_class, service_object_cookie, lifecycle_queue}`. Calls resolve the route at
dispatch time. The frozen dispatch metadata is `{service_class, service_object_cookie}` in
`ActivationContext`; method, version, request identity, and payload remain service-protocol bytes.
The cookie is non-reused within the minting service incarnation and is never a caller-local handle.

`cap.mint_service rd,service_class,gate,rights` requires `service_class >= 256`, `CONTROL` on the
sealed Gate, and a lifecycle queue with one reservable slot. It publishes one stamped object or fails
without effect. Service-class numbers are creator-assigned; the engine interprets only the
hardware/service-owned split and the exact class equality required by typed operations.

`cap.restamp rd,object,new_gate` requires `REVOKE` on the object and `CONTROL` on the new sealed
Gate. It atomically replaces the shared route, moves the one reserved lifecycle slot, and returns an
alias of the same object. It never returns the Gate. Gate or service-domain death makes dispatch
`-STALE`; restamp repairs routing for every alias of this object but never reconstructs
service-private state.

After the final strong alias and all accepted calls quiesce, the engine emits exactly one 24-byte
CompletionQueue record `{service_object_cookie, LAST_STRONG_REFERENCE, 0}`. Status 1 is
`LAST_STRONG_REFERENCE`; statuses 2 through `INT64_MAX` are reserved. Consumption acknowledges the
record. The pre-reserved slot makes loss impossible.

Service objects are **REBIND_REQUIRED in v1**. Moving capture records the object as an external
dependency and serializes neither cookie, route, lifecycle queue, nor service-private state. Before
publication the importer must `state.bind` the dependency to a live service object of the same
service-owned class whose rights cover the captured entry. The replacement supplies its own cookie
and route. Failure is atomic. Service protocols checkpoint their semantic state explicitly.

Shared typed-operation conditions are `-MALFORMED` (a known function's operands are malformed),
`-DENIED` (rights/view closure), `-STALE` (dead slot, lineage, binding, builder generation, or cursor
root), `-OVERFLOW` (only a typed self-describing record does not fit its destination), and
`-CANCELLED` (pre-commit cancellation). Reserved function numbers are illegal instructions, not
`-UNSUPPORTED`; `-UNSUPPORTED` belongs to a well-formed service protocol/version or a known typed
operation whose target class explicitly lacks the requested optional behavior.

### 16.1 Domain algebra and unpublished builders

#### 16.1.1 Builder identity, visibility, and lifetime

`dnew rd, parent` creates a complete dormant but **unpublished** prospective domain and returns
a `DomainBuilder` reference. `dfork rd, source` creates a COW state clone with a fresh authority
table; `dcompartment rd, source` creates a fresh-authority compartment sharing the source address
space. The builder owns a fresh prospective incarnation, parent relationship, constructor-defined
defaults, no runnable activation, no externally held domain capability, and an accounting
charge to the builder holder for all engine state used during construction.

**The empty-domain floor.** A zero-fact `dnew` followed by `dseal` materializes only one
incarnation-epoch cell at the parent's home, one parent-edge role cell, references to the five
inherited views (never copies), the self-rights word with `CREATE` set, one charge-through budget
sub-account row, an empty capability-table header, and an empty address-space root. Capability-slot
storage, a VMA tree, domain tags, thread-directory entries, activation stacks, scheduler state, and
measurement state are materialized only at their first architected use. A dormant sealed domain has
no stack, tag, or scheduler state and therefore has strictly less mandatory state than one thread.
An eager implementation remains conforming, but every eager cost is included in its published
`SPAWN_WARM_RTT`; it may not hide that work outside the measured interval.

Destroying such an empty domain is one local incarnation-cell bump. With no externally spanning
referent and no resident optional state, acknowledgment is local and the asynchronous corpse drain
is empty; monotonically retired identities require no free-list operation. This is the floor case
of `DESTROY_WARM`, not a special lifecycle transition.

A builder reference is an ordinary `u64`-class engine reference usable only by `domain.build`
functions. Each successful mutation consumes generation `n` and returns generation `n+1` in `rd`.
Every copy of generation `n` is thereafter stale. Failure before the function's commit point leaves
the same generation valid unless that function explicitly reports a builder-fatal condition. The
reference may be copied, spilled, and reloaded; linearity is the generation rule, not hidden register
state.

Builder references cannot be transferred to another domain, placed in a capability table, called,
enumerated outside their holder, serialized, or used as ordinary address-space or domain authority.
`dabort builder` consumes the builder and releases its charges. Holder death aborts it. **An
unwind path holding a live builder generation may always abort it**: builder aborts (`dabort`,
`gate.abort`, `channel.abort`, import-builder abort) are shed-rule members (§16.2) — infallible
regardless of budget state, so cleanup-landing-pad codegen for builder chains is unconditional,
with no error edge and no probe. Freeze/export
of a subtree with a live builder is `-BUSY`; unpublished state never enters a serialization stream.

Before publication the child cannot execute; no other domain can hold its capability; its address
space is inaccessible to ordinary loads/stores; its mappings, views, bindings, budgets, and authority
affect no published domain; it has no externally meaningful domain/thread identity; staged moves have
not committed; it is absent from scheduling and enumeration. Destroying prospective state is exactly
builder abort.

#### 16.1.2 Construction functions

The fixed `domain.build` functions are:

| Function | Operands | Effective-state contribution |
|---|---|---|
| `dnew` / `dfork` / `dcompartment` | fixed constructor operands | fresh birth, COW clone, or shared-address-space compartment; no birth flag word |
| `dmap` / `dmap.shared` | `rd, B, backing, addr, len, offset` | private or shared mapping relation; `backing=0` means lazy zero-filled private state |
| `dunmap` / `dprotect` | `rd, B, addr, len [, prot]` | remove or set a prospective mapping's protection |
| `dhome` | `rd, B, addr, len, home` | locality/home constraint separated from mapping |
| `dstate.cow/move/share_ro/registers` | fixed operands per mnemonic | one startup-state source and ownership relation; operand meanings never depend on a mode |
| `dgrant` / `dmove` | `rd, B, cap, rights {slot}` | staged copy or atomic-at-publication move into the child |
| `dgrantm` / `dmovem` | `rd, B, slot_base, regmask` | consecutive copied or moved startup slots from selected capability argument registers |
| `dlimit` / `dsealcap` | `rd, B, slot, rights` | narrow or seal a prospective child slot |
| `dself` | `rd, B, rights` | monotone restriction of implicit self authority |
| `dslot.persist` / `dslot.drop_on_replace` | `rd, B, slot` | independently select one slot's executable-state-replacement lifetime |
| `dview` / `dclock` | `rd, B, view` | MachineView or ClockView constraint |
| `dservice` | `rd, B, slot, service_cap` | explicit child service import; its typed capability supplies the continuity contract |
| `dbudget` / `dbudget.charge_through` | `rd, B, dimension, amount` | carved ceiling or explicitly attributed parent-pool sub-account |
| `dplace` | `rd, B, set` | connected placement constraint expressed by an immutable set |
| `dsched.timeshare/fixed/reservation` | fixed weight, priority, or budget/period operands | one scheduling relation per mnemonic; reservation alone performs admission |
| `djit` | `rd, B, allow` | prospective permission to mint `JIT_ARENA` backings; boolean, monotone against the parent |
| `dmeasure` | `rd, B` | opt the prospective domain into birth measurement; no inspection consequence |
| `dentry` | `rd, B, index, pc` | entry identity relation |
| `dstack.new` / `dstack.use` | fixed fresh-size or supplied-stack operands | fresh or supplied initial activation-stack relation; a supplied base or declared size that does not yield a 16-byte-aligned entry `sp` is **`-MALFORMED` at the declaring operation** — validated, never silently rounded (the §9.2 universal entry alignment; the same rule binds `gate.stack` pool declarations at `gate.seal`) |
| `dgates` | `rd, B, fault_pc, event_pc` | machine-call entry relations |
| `dabi` | `rd, B, abi_class` | one frozen entry convention; the closed enum changes no other semantic dimension |
| `dstartup` | `rd, B, metadata_ptr` | prospective image's versioned `env_open(STARTUP)` personality metadata; zero means absent |
| `dbind.prepare` | `rd, B, import_slot, kind, prepare_token, expiry_ns` | stage a continuity-profile prepare token and prospective relationship cell for `INHERIT`, `NEW_SESSION`, `REPLACE`, or `DROP` |
| `dseal` / `dstart` | `rd, B [, entry]` | atomic publication dormant or with first runnable activation |
| `dabort` | `B` | consume unpublished state without publication |

The table fixes operand meanings, not internal records. Where an independent fact cannot fit one
instruction it receives another typed function (`dmap` then `dhome`, never a descriptor). Builder
functions perform intrinsic checks: reference/class validity, range overflow, immediate rights
restriction, generation freshness, and locally impossible values. They need not perform complete
cross-property admission or allocate final physical records.

Live resource changes use three equally typed `domain.exec` functions:
`domain.budget` changes one named budget dimension, `domain.place` changes the placement set, and
`domain.reserve` performs scheduling-reservation admission. Each is one atomic relation with its own
fixed schema and rights row; none accepts a policy selector or record. Narrowing is immediate when it
does not invalidate admitted work; widening requires parent authority and fresh admission. A change
that would invalidate a live reservation, exclude a running activation, or strand charged state fails
`-BUSY` unless the caller first establishes the required quiescence. Successful changes bump the
corresponding effective-state generation and serialize as that relation.

#### 16.1.3 Publication and staged moves

`dseal` publishes a dormant domain. `dstart` publishes it and creates its first runnable activation.
Publication is the single closed-validation and commit point: view closure, budget/admission,
placement connectivity, W^X and alias compatibility, service-import validity, entry/stack validity, realtime
dependency closure, capability admission, binding-prepare validity, final resource availability, and every mutable epoch are
rechecked.

On success the builder is consumed; domain identity becomes externally meaningful; staged capability
moves consume their source slots atomically; resource admission becomes live; and `rd` receives the
domain capability. Prepared relationship cells change from PREPARED to COMMITTED in that same
publication transaction; replacement retires the old committed relationship at the same point.
Failed publication leaves the old relationship intact and changes every new prepared relation to
ABORTED. `dstart` additionally makes the activation runnable.

**Birth register state (pinned):** the first instruction of a `dstart`/`dspawn` first activation
executes with **`r31` = the builder-declared initial stack pointer, 16-byte aligned**
(a misaligned declaration fails publication `-MALFORMED`), **`r30` = the builder-declared
initial `tp`**, and **every other GPR zero** — except registers named by `dspawn`'s declared
scalar-argument masks (§16.1.4), the one explicit way register values enter a new domain;
FP/vector/mask state is the zeroed fresh state of any activation, per the execution view.
**No argument rides a birth register**: startup data arrives through the psABI startup-metadata
record, discovered by `env_open(STARTUP)`. (A `dcall` entry takes §9.2's entry state; a machine
call takes §9.3's.) On failure no domain is
published, no move is consumed, no partial configuration is visible, and the same builder generation
remains valid unless the failure is explicitly builder-fatal. Software may amend it and retry or
`dabort`.

A staged `dmove` records source slot, rights, and expected slot/lineage generations. Publication
revalidates them. Concurrent drop, revoke, or competing move makes publication `-STALE`; exactly one
competing move may consume a slot, and failed publication never duplicates authority.

**Staged service bindings.** The coordinator invokes the continuity profile's
`PREPARE_BINDING {kind, prospective_group_ref, bytes}` operation through the ordinary service gate,
then passes the returned opaque token and duration-form expiry to `dbind.prepare`. The engine never
constructs or decodes a service message implicitly. `kind` is `0 INHERIT`, `1 NEW_SESSION`,
`2 REPLACE`, or `3 DROP`; other values are `-MALFORMED`. `prepare_token=0` is reserved-invalid and
`expiry_ns=0` is already expired; `UINT64_MAX` means no expiry. The engine records the token, expected service route, prospective
relationship cell, and expiry as one non-dispatchable, nonduplicable PREPARED relation owned only by
the builder. `REPLACE` and `DROP` are valid only for a replacement builder whose
`replacement_target` is set; the old committed relationship is exactly the relationship installed
at `{replacement_target, import_slot}`. `INHERIT` and `NEW_SESSION` require that no old relationship
is named at that slot. Violating either rule is `-MALFORMED` before creating a PREPARED relation.
A stateless relationship uses the existing `dservice` fact; it does not need a second
binding operation. Publication and expiry/abort race at one linearization point: publication fails `-STALE` if
the token expired or its route died; otherwise it atomically installs the cell and changes it to
COMMITTED. A dispatch through a raw committed CallGate sets
`ActivationContext.PREPARED_BINDING` and carries the opaque token as `dispatch_cookie`, after
revalidating both the import slot and the route lineage. A committed stamped service object already
authenticates its stronger stable object cookie and therefore uses `SERVICE_OBJECT` instead. The
service materializes any private state lazily and idempotently. Abort or failed publication changes
it to ABORTED; an unused
service reservation may persist only until the bounded expiry. State import never replays prepare:
it requires explicit service rebind before publishing a restored committed relationship.

#### 16.1.4 Fast inherited creation and execution

`dspawn rd, image, entry, state, masks` is the hot fused adapter for inherited `dnew`, standard
state/argument/capability setup, and `dstart`. Its compact subformat names scalar-argument,
capability-copy, and capability-move register masks; spawn-scoped borrow bits remain reserved on the
named `SPAWN_BORROW` encoding seam. It implements one
standard private startup-state relation; other state sources use the explicit builder functions.
It has no lifecycle, failure, accounting, cancellation, publication, or ordering semantics of
its own. The canonical child is inherited effective state plus an explicit delta: MachineView,
ClockView, explicit service imports, placement envelope, scheduling class, accounting policy, read-only image
mappings, activation ABI, event/fault behavior, and parent ceilings inherit where authorized.

The `domain.exec` family contains:

```text
dcall rd, target, entry     dtail target, entry     dret value
dyield rd, value            dresume rd, activation, value
dexit value                 dstop rd, domain
                            dkill rd, domain
djoin rd, domain, deadline
```

Arguments use the ordinary calling convention registers. `dcall`/`dtail` cross through the target
entry's gate relation and therefore preserve Law 1; they are fixed call-form adapters over the one gate
activation protocol. `dtail` transfers continuation, donation chain, cancellation topology, and return
destination without adding an intermediate frame. `dyield` transfers control while retaining an
explicit resumable activation; it is not a scheduler hint. Calls, spawns, messages, joins, and resumes
remain distinct contracts even where implementations share machinery.

**Persistent thread lifecycle.** A Domain may contain any number of persistent threads; gate and
domain-call activations are bounded-lifetime executions and are not persistent threads. The five
thread lifecycle/control operations are:

```text
thread.new   rd_tid, entry_pc, arg, stack_base, stack_size
thread.exit
thread.ctid  rd, clear_tid_ptr
thread.place rd, tid, placement_set
thread.group rd, domain, tid, group_id, generation
```

`thread.new` creates a persistent thread in the calling Domain. `entry_pc` must be executable;
`[stack_base, stack_base + stack_size)` must be overflow-free, writable, nonempty, and have a
16-byte-aligned top. The operation registers that range as the thread's machine-call stack, charges
one `OBJECT_COUNT` plus context/registration memory to the calling Domain, and atomically admits the
new thread. On success `rd` receives a fresh nonzero Domain-scoped `THREAD_ID` that is never reused
during the Domain incarnation. The thread begins at `entry_pc` with `r2 = arg`,
`r31 = stack_base + stack_size`, `r30 = stack_base`, every other GPR zero, and zeroed state for the
register classes enabled by the Domain's `abi_class`. It inherits the Domain scheduling class and
effective placement; `thread.sched` and `thread.place` may subsequently narrow those relations.
Failure creates no thread and consumes no id.

`thread.exit` terminates only the calling persistent thread and has no success continuation. Before
retiring it performs the clear-tid transition below, releases the thread's engine state and charges,
and makes its `THREAD_ID` permanently stale. A Domain with no persistent threads remains `LIVE`:
gate activation pools and externally driven services remain valid. Only `dexit`, `dkill`, or the
ordinary lifecycle/reaping protocol terminates the Domain.

`thread.ctid` registers the calling thread's clear-on-exit word. Zero disables the relation.
Nonzero pointers must be naturally aligned writable 64-bit locations in coherent normal memory;
registration records the logical futex key and mapping generation. On `thread.exit`, the engine
stores zero with release ordering and performs the equivalent of `futex_wake(ptr, UINT64_MAX)`
after the store. If software invalidates the registered mapping first, the store is omitted but the
saved logical key is still woken; thread termination never fails. Restating replaces the prior
relation. This is the primitive beneath `CLONE_CHILD_CLEARTID` and `pthread_join`, not a second join
object.

`thread.place` replaces the named same-Domain thread's placement set after intersecting it with the
Domain's effective placement and MachineView. An empty intersection or foreign tid is `-DENIED`; a
dead tid is `-STALE`; a malformed set is `-MALFORMED`. A change that would strand running or admitted
work returns `-BUSY`. Per-thread affinity is policy; `domain.place` remains the enclosing ceiling.

`thread.group` changes the target thread's delivery-eligibility snapshot under `CONTROL` on its
Domain. The pair is `{group_id u32,generation u32}`; `{0,0}` is the default and the pair serializes
in THREADS. Numbered events are delivery **classes**, not personality identities: software maps
signals or another namespace to classes 0--47 and carries the typed identity in the payload;
48--63 remain engine-only. `event.post` target kind `ANY` selects any eligible unmasked thread,
`THREAD` selects exactly the thread named by `target`, and `GROUP` interprets `target` as packed
`{group_id,generation}` and selects any currently matching unmasked thread. A group-directed post
whose generation no longer exists returns `-STALE` and
delivers nothing, so an eligibility snapshot is validated atomically rather than interpreted by the
scheduler.

**Activation checked copies.** A borrow window exists on every synchronous gate activation. In a
shared address space it is the ordinary load/store overlay; across address spaces it is an
accessor-only relation retaining caller address-space identity, covering VMA epochs, range, and
rights in the engine frame. `acopy.in rd,win,dst_ptr,src_off,len` and `acopy.out
rd,win,dst_off,src_ptr,len` copy between the current activation's window and callee memory;
`acopy.instr`/`acopy.outstr` stop after and include the first NUL. Window indices are 0 or 1;
absent windows are `-BADREF`, range overflow is `-BOUNDS`, and rights failure is `-DENIED`.
The §10.1 partial-transfer rule applies (`rd` bytes moved, `-FAULT` only at zero progress), in
64 KiB quanta with an architected park point between quanta. String forms return `-MSGSIZE` after
copying `len` bytes when no terminator occurs. Mapping/protection/revocation invalidation kills the
remote relation; later access returns `-FAULT`. Nested calls suspend and restore the enclosing
window set, windows cannot be re-lent, and activation teardown drains an in-flight quantum before
the caller resumes. `SUBMIT` never carries a borrow.

`dstop` atomically closes new entry and requests cancellation of current activations, then returns
once that request is committed; cleanup and logical death may follow later. `dkill` has one
unconditional postcondition: it establishes the domain's logical-death point, forbids future entry
and authority use under the ordinary death rules, and starts asynchronous teardown. `djoin` waits
until logical death is committed and all activations have stopped, or until its deadline; engine
storage reclamation may continue asynchronously. Descendant termination is software composition,
not a flag or hidden recursive walk.

The parentless terminal case is §2.1's reset rule: logical death of the last live parentless
Domain transfers directly to the reset controller before reaping or descendant reparenting.
Consequently it has no `djoin` observation in the dying machine. Ordinary non-root death and
reparenting are unchanged.

Resident pin leases are released only by
`backing.unpin_resident(rd, backing, lease_id)`; no second self-directed release operation exists.

#### 16.1.5 Algebra and implementation freedom

Two builder sequences that produce the same effective mappings, admitted authority, views, budgets,
service imports, entries, placement, and policy are architecturally indistinguishable. Independent
contributions commute; monotone restrictions compose by intersection; adding an identical immutable
fact is idempotent; and conflicts are defined over final effective state rather than private processing
order unless program order is itself named by the operation.

An implementation may defer, normalize, reorder under data dependencies, cache, compile, fuse, or
execute as one internal operation any unpublished construction sequence, provided visible instruction
failures, builder generations, publication result, accounting, ordering, and bounds are preserved.
Legal representations include eager state, append-only deltas, persistent roots, parent-plus-overrides,
canonical hashes, compressed tiny domains, specialized task/actor records, distributed per-volume
state, protected spill, verified sequencers, cached recipes, and future representations. No program
may infer one allocation per builder instruction, immediate slot consumption, a stable domain tag
before publication, on-chip builder residency, a fixed internal protocol count, or publication cost
independent of named facts. Costs may scale only with named mappings, staged grants, authority span,
placement diameter, admission dependencies, and explicit set size. Builder spill is nonpageable,
hardware-managed protected storage charged to the holder.

#### 16.1.6 Domainization policy

A domain is an identity-bearing governed lifetime containing private state, authority, execution,
accounting, and observation. Runtimes may use that unit for objects, serialized monitors, actors,
closures with captured capabilities, async tasks/futures, yielded coroutines, regions/arenas,
plugin/Wasm instances, requests/sessions, speculative COW computations, service workers, and device
queue contexts. This is an availability of representation, not a mandate for one domain per language
object.

Compilers retain scalar replacement for nonescaping values, stacks for local objects, ordinary heaps
for mutually trusting shared state, and shared memory plus atomics where authority and lifetime are
common. They domainize when trust, authority, cancellation, budget, observation, or lifetime boundaries
are valuable, and may coalesce logical objects whose boundaries coincide. Passive software-owned
objects may therefore become domains; hardware-owned objects remain justified for hardware-producer
timers/interrupts, DMA/device queues and windows, reserved completion promises, engine-retained
readiness, cross-domain synchronization without shared memory, and engine-enforced accounting facts.

**Current-parent authorization is an explicit edge role, not ambient ancestry privilege.** Each live
parent→child edge owns an engine-held, nontransferable **parent-role reference** with its own epoch cell.
It is not installed in either domain's capability table and cannot be delegated; it is the structural
reference by which the engine evaluates `caller_is_current_parent(target)`. Parent-only operations use
the exact authorization expression
`caller_is_current_parent(target) AND caller_holds(target_cap, ADMIN)`—neither conjunct suffices.
`REPARENT` atomically bumps and retires the old edge-role cell and mints the new parent's role while it
changes the tree edge. The edge commit is caller-visible only after both old and new role state is
acknowledged across its referent span under §3; its transition work is O(1), not its span-dependent
return latency. Thus an old parent's still-live `ADMIN` capability remains ordinary authority but
no longer authorizes prospective `dview`/`dservice` publication; the new parent needs both its new
edge role and an
`ADMIN` target cap. The role is engine-private hierarchy state serialized as a relationship and
re-minted on import, never a software-visible ID. This is not a principal-held exception to capability
authority: it is a nondelegable reference-monitor predicate that narrows use of an already-held cap.

**Admission dependencies remain enforced for the reservation's lifetime.** Every successful
`domain.reserve` creates an engine-private **admission-dependency ledger** containing every fact used
by admission: ancestor capacity tokens, effective placement and isolation policy, power-floor token,
ATS/invalidation bounds where relevant, and the exact then-live resident-pin leases plus VMA/backing
intersections that form the reservation's **RT memory set**. This set needs no “working set” inference:
it is mechanically the accessible mapped ranges covered by those leases when admission commits. The
ledger holds references to those leases and
their accounting charges for as long as the reservation exists; an `UNPIN_RESIDENT` or
`RELEASE_PIN_LEASE` cannot release a depended-on lease and fails `-BUSY`. Leaseholder teardown does not
silently drop a dependency—the admission hold keeps the lease and charge alive until the reservation
is removed or the admitted domain is destroyed.

Every later operation that can change an admission premise—`dplace`, `djit`,
`backing.rebind_pager`, mapping/protection/backing transitions, pin-lease mutation, view changes, `REPARENT`, and
import—must do exactly one of three things in the same transaction: **preserve** every recorded fact,
**revalidate and replace** the affected ledger entries, or **reject `-BUSY` with no effect**. Mapping a
new pager-capable range into a domain with an admitted reservation therefore requires already-live pin
leases only if that range is to join the WCET-covered set; otherwise it is legal cold memory and remains
outside the conditional end-to-end guarantee. Re-running `domain.reserve` atomically re-admits and
replaces the set from the then-live leases. Unmapping may remove dependencies; a pager retarget that preserves
the same resident pinned frames preserves them. No operation silently degrades coverage already in the
ledger. **Gate donation does not transplant the caller's memory ledger:** execution in a callee is
end-to-end admitted only through ranges covered by the callee domain's own live reservation ledger;
otherwise donation preserves the CPU scheduling/deadline bound but not memory-access WCET. Removing the reservation releases its dependency holds. This is the general
closure doctrine: an admission fact is a live engine object, not a historical observation made at
configuration time.

**Qualification of the `domain.reserve` table shorthand:** “resident-pinned backing required if
pager-backed” means required for every range claimed by the RT memory set, not every pager-backed VMA
the domain can legally access. Cold mappings may coexist; touching one leaves the conditional
end-to-end WCET guarantee as defined above.

A domain is the unit of authority, accounting, scheduling, and observation (§2.1, Law 7). All of its
control is the Domain/Scheduler engines; there is no service behind it.

**Birth measurement** is local domain metadata.
A `MEASURED`-at-birth domain accumulates a digest over builder contributions and commits it at
`dseal`/`dstart`; later executable replacement extends the digest. The value supports local audit,
debugging, and state comparison only. External trust and protected transport are software/service
policy outside the instruction set.

Domain operations are expressed only by the fixed functions cataloged in §16.0:

- Birth and clone use `dnew`, `dfork`, or the fused `dspawn`; publication uses `dseal` or
  `dstart`, and termination uses `dexit` or `dkill`.
- Mapping, authority, view, service-import, budget, placement, scheduling, policy, entry, stack, and
  ABI facts use their individually named builder instructions. No generic setter exists.
- Runtime observation uses a fixed scalar getter where one is defined, a cursor for collections, or a
  state stream for byte state.
- Safe-state holds use `quiesce` and `resume`; activity cancellation and submission draining use
  their narrower typed operations.
- Live address-space operations use the fixed mapping instructions with explicit target authority.
  VMA collections are cursors, never selector-dependent records.
- Debug authority is minted by `debug.new`; service imports are explicit gate, endpoint, or proxy
  capabilities and never redirect native instructions.
- Executable-state replacement begins with `dreplace`, accumulates ordinary builder facts, and
  publishes only at `dreplace.commit`.

Every one of these transformations retains the accounting, monotonicity, view, scheduling, and
admission laws defined in this section. This list is explanatory and creates no second operation
namespace.


### 16.2 Typed object construction and the merge doctrine

Each hardware-owned class has a constructor in its class-specific opcode family: `counter.new`,
`timer.new`, `irq.new`, `waitset.new`, `eventring.new`, `cqueue.new`, `window.new`, `pmu.new`,
`workqueue.new`, `mview.new`, `clock.new`, and the corresponding
constructors listed by §17.7. Complex classes return unpublished builders; simple constructors return
complete usable objects. Their opcode/function and register operands are their complete schema;
there is no universal factory or class selector. An object's implementation classification remains a point in
**`Backing {Thread, Memory, Register} × Producer {software, hardware}`** plus a **profile** naming a convention over it.
**The drain side is a property, not a third axis**: every class's consumer is software (`recv`/`wait`)
**except WorkQueue (`obj_class` 14), whose consumer is a device** (§15) — one property on one class. A
pipe/socket is Memory-backed, a semaphore is Register-backed (a **futex is deliberately *not* an
object** — address-keyed, no table entry, §6), a call-gate is Thread-backed, a timer is a
hardware-producer endpoint, a waitset is a Memory-backed aggregator. Each `*.new` returns its typed
object capability directly in `rd`.

**`Backing × Producer` is creation metadata, and it decides no legality.** The grid organizes typed
constructors (some classes admit more than one point) and
organizes the catalog; legality is decided by the decoded class-specific opcode and target capability
class. Readiness is an architectural relation consumed by waitsets, not a dispatch interface. The
frozen things are the class codes, each class's semantics, its dedicated opcode functions, and the
typed-constructor rule.

**The division of labor between atomics and objects, stated as the object-admission rule.**
Strong scalar atomics plus futexes own **everything that is shared state + wakeup**: mutexes,
condition variables, semaphores, eventfd-shaped counters, software completions, lock-free queues,
refcounts, once/init, barriers — all intra-domain and shared-memory synchronization, *by
construction, with no object*. A native object class exists **only** where it embodies something
atomics cannot: **authority** (revocable, delegable, rights-carrying), **isolation without shared
memory** (signaling between domains that share no mapping), **hardware-producer state** (a timer,
an interrupt line, a device completion — state a producer that is not a thread must update),
**engine-written records or engine-kept promises** (reserve-at-submit, per-submission status,
acknowledged teardown), **cross-domain capability transfer**, or **scheduling/accounting truth**.
Every class in the table below passes that test, and several rows carry their test inline
(Counter, CompletionQueue, FileDescription) — the classes where good atomics come closest to
sufficing. The rule is normative for growth: a proposed class that is
only shared state + wakeup is refused — it is a library over a word. **And there is no "optional
profile" escape hatch in either direction (B33): a class either passes this test and is mandatory
on every conforming machine, or it fails and does not exist** — the one-machine rule means the
admission bar does the work a profile matrix would otherwise smear across the ecosystem.
**The test applies to sub-operations and semantic features, never only to whole classes:**
"the class is admitted" admits nothing else. The waitset, worked as the example because it is
the feature-richest class: membership-by-capability, retained level readiness, bounded
engine-written records, member cookies, and atomic add/remove-vs-delivery are the mandatory core
(they *are* the delivery mechanism — the engine-written-record leg); explicit EventRing binding
passes by the same leg; edge/oneshot re-delivery modes pass by the hardware-producer leg
(interrupt sources need architected re-arm semantics — the §9.3 disposition machinery's shape,
selectable per member instead of per API generation); exclusive wakeup passes by the
scheduling-truth leg (anti-thundering-herd is a scheduler fact software cannot enforce over a
shared engine object). A future feature that names no leg is refused *at feature granularity*,
whatever class it rides. **And the class-versus-facet criterion, the merge rule's missing
sibling (stated so class-21+ growth is never vibes):** a behavior becomes a **distinct
capability class** iff **(i)** it is a target of a polymorphic verb whose operand schema the
target's class must fix (`send`'s Tier-2 rule forces facet-typing anywhere `send` lands — why
the DMA submission facets are classes), or **(ii)** its delegation lifecycle differs from its
parent object's (why `FileDescription` exists: N handles, one shared cursor); **otherwise it is
a function family on the existing class** (why Timer's delivery modes are builder facts). A
proposed class satisfying neither clause is a function family wearing a class number. **And its
converse organizes the catalog: classes sharing an algebra share one opcode family** — one
builder surface, one consumer-verb set, one doctrine — **with each class keeping its own class
code** (so decode stays a range compare, a polymorphic verb's schema stays class-fixed, and the
§16.8 answers stay per-class); a family never merges classes whose transfer contracts its
builder facts would have to select. **Information provenance (the hot-path audit rule):** every engine hot-path decision derives
from (a) live authority/state hardware must check, (b) data genuinely known only at execution,
or (c) a fact the toolchain already proved — and a category-(c) fact is carried in the
instruction, the sealed declaration, or metadata, never rediscovered by silicon
(`gate.borrow_arg`, the futex `scope` operand, and sealed
channel schemas are the instances). The converse bound: **never optimize away a runtime lookup
whose answer can change without recompilation** — epochs, rights, mappings, budgets.
**The honesty rider a family verb carries:** it accepts
every member class, so *within-family* confusion (the wrong member's cap in the operand) is a
data-schema error caught by the consumer, never `-BADREF` — cross-family confusion still faults
at the instruction, class-specific functions still imply their class statically, and the
frontend's typed bindings are the static check for the rest. And the **merge rule, normative because near-duplicates are where semantics fork by accident:
two operations that differ only in encoding convenience are one primitive, and the spec keeps
exactly one.** The formulation is structural, not comparative: **an alias is an encoding
projection of one canonical semantic operation** — its decoder maps operands into the canonical
operation's input state (an **operand adapter**), the canonical transition runs, and a **result
adapter** maps the canonical result into the alias ABI. The alias has **no independently stated
rule of any kind**: no state transition, ordering, blocking or wake behavior, interruption or
`OP_RESTARTABLE` recipe, cancellation, commit point, capability-lineage effect, accounting
attribution, serialization representation, or view-visible information of its own — every one of
those is the canonical operation's, stated once. An alias survives only under all three
conditions: **(i)** it is a pure adapter pair in exactly that sense; **(ii)** it names the **hot
path** it serves — the property it buys is a materially shorter or more directly call-shaped path
executed per-operation, not per-setup (equivalence never justifies retention: condition (iii)
proves an alias *correct*, only this condition proves it *deserves an opcode*); **(iii)** it
carries the **adapter-proof obligation** in the Appendix D suite — the suite proves the two
adapters and proves no independent alias transition exists, which is maintainable forever,
unlike proving two independently written state machines equivalent. The result adapter is a real
object, not hand-waving: `mmap` is `AS_MAP_CANONICAL(target = current domain, authority = the
implicit self capability, arguments = its operands)` with the returned address adapted into `rd`.
The standing audit of every
near-pair, with each verdict's reason: the self-address-space opcodes (`mmap`/`map.protect`/
`munmap_range`) survive against the AS facet — the allocator hot path is condition (ii) satisfied
by measurement everywhere malloc exists, and their semantics are stated once, as the facet's, per
condition (i). `dspawn` survives because domain birth is a language/runtime hot path and is proven an
adapter over `dnew` + standard setup + `dstart`. Sync `gate_call` vs `gate.submit` is **not an alias pair**: they share one
activation protocol (§9.2 — the semantic is defined once) but differ in concurrency contract, and
a semantic difference is a second primitive, not a second spelling. The §17.1c borrow vs
`mem_grant` is likewise two primitives: the borrow's zero-slot, call-scoped, non-capability
lifetime *is* its content (§17.1c states its permission semantics as `mem_grant`'s overlay with
lifetime = the activation). And direct engine binding vs service-stamped dispatch differ in **who
holds authority at dispatch time** — authority differences are never encoding differences, so
merging them would delete a trust topology, not a redundancy. Domain, authority, class-specific object,
set, cursor, and state-transport families remain separate typed algebras because their operand and result kinds differ;
shared implementation machinery does not merge their caller contracts.

A typed constructor acts on an *authorizing* capability, not on the not-yet-existing object.
Its opcode/function fixes the class being created. **`owner = 0`** (the §2.2 null sentinel)
means **"the current domain,"** exercised through the domain's
**implicit self-capability**: a per-domain rights set fixed **at domain construction by the parent**
(via `dself`; creation mode may select the default full set of all defined rights bits; otherwise the
`self_rights` value is literal, always — no in-band magic value), **with one inalienable bit:
`CREATE` is always present in the self-rights set, and a `dself` value clearing it is
`-MALFORMED`. Self-subdivision is not a deniable operation** (B36): **any domain can subdivide
itself; the machine's protection primitive is as ambient as its call instruction** — which is
what lets a compiler emit compartments the way it emits calls, with no
probe and no fallback. The brakes that remain are resource honesty, never policy: children
charge the creator's budgets (a near-zero object budget is the architected *leaf-frozen*
construction — a domain that provably cannot grow, failing `-EXHAUSTED`, the economic
condition, never `-DENIED`), and placement admission applies as to any construction. `CREATE`
on an **explicit, transferable** domain capability is unchanged — a droppable right like any
other, because creating *into another domain* (`state.import` on a receiving parent,
`mview.new` on a parent view) crosses a real boundary and stays deniable.

**The inalienable self-set (closed, positively defined — B36 is one instance of this rule).**
Operations whose object is the issuing domain itself and whose effect is to **subdivide**
(`CREATE`; `thread.new`; `thread.ctid`; `mem_grant` over held mappings;
`cap.copy`/`cap.narrow` of held slots), **shed**
(`munmap_range`, `map.discard`, protection narrowing via `map.protect`, dropping held slots,
`cap.drop`, endpoint `channel.shutdown`, narrowing-copy-then-drop, `thread.exit`, and `dexit` —
the terminal sheds),
**configure inward** (`dgates`, `dstack.new`/`dstack.use`, `rseq`, `EVENTMASK`, event
dispositions, and lowering the issuing domain's or one of its threads' scheduling weight,
priority, reservation, or placement within its existing ceiling — **downward self-scheduling
within the existing ceiling**), or **observe self-facts**
(`dget`/`dget2` with `domain = 0`, including `{charged, ceiling}` budget facts; `env_open`;
granted PCR selectors; and futexes on own memory) are **never deniable**: no `dself` value,
rights configuration, or view withholding
reaches them — a `dself` value denying a member is `-MALFORMED` exactly as for `CREATE` —
because each crosses none of Law 8's four boundary meanings and the set is precisely what a
toolchain must emit with no probe and no fallback. Operations that **widen, cross, or
disclose** stay granted (wall time is a granted
transform; `DEBUG`-right inspection is the granted tier, `trap`-kind self-debugging §7 the
unconditional one — sanitizer runtimes need no `DEBUG`). Two composition rules: **shedding is
never budget-blocked** — an operation whose net effect releases resources succeeds at zero
budget, and a shed that must *split* a range charges only the split's metadata; and
**fault-safety precedes leaf-freezing** — a leaf-frozen domain's §9.3 registrations must be
established before its budget freeze, and the registrations are priced, never
authority-deniable.

This closed set deliberately excludes four superficially self-scoped operations. `random` remains
view/policy deniable so a parent can provide deterministic replay; the parent is already an
authority dominator, so this adds no new confidentiality power. Attestation remains conditional on
an explicitly granted identity scope, preserving opt-in identity. `state.open` on self remains
governed by `dself` because it exposes engine metadata such as slot epochs, not merely an ordinary
self fact. `mview.new` requires a held parent-view capability so every derived view remains rooted
in an explicit coarsening authority. Physical constructors (`irq.new`, `window.new`, and `pmu.new`)
likewise remain deniable because useful publication requires a granted physical/device noun;
ordinary gates, channels, waitsets, completion queues, event rings, counters, and timers on the
domain's own bound clock require no such noun.
A hardened parent narrows by
dropping **`ADMIN`** — the child keeps `CONTROL` self-service ops but cannot alter `djit`/`dbudget`/
`domain.reserve` itself). The self-capability is not a table slot and cannot be duplicated or sent;
naming *another* domain always takes an explicit domain capability operand. This is where "acts
on the current domain's own budget" (§11.1) is plumbed. Every per-class row in §16.3 lists its typed
constructor and methods. Destruction and scalar property reads are fixed class functions; collection
enumeration returns a cursor.

### 16.3 Hardware-owned object classes and their sub-ops

Fixed enum assignments used by these functions include endpoint shutdown direction `0 RD`, `1 WR`,
`2 RDWR`; out-of-range values are `-MALFORMED`.

**Traffic observation (typed counters, observational by definition — the placement story's cheap
half).** Three classes carry fixed 64-bit monotone traffic getters (full-range raw getters under
§1's exception): CallGate typed raw getters for **`CALLS`**, **`REQUEST_BYTES`**, **`REPLY_BYTES`**
(bytes = inline payload bytes actually copied at activation and reply; authorized-but-untouched
borrow and capability ranges never count — placement wants transferred truth, not authority);
ChannelEndpoint **`SENT_RECORDS`**/**`SENT_BYTES`**/
**`RECEIVED_RECORDS`**/**`RECEIVED_BYTES`** (committed transfers; partials count
bytes moved); DMAWindow **`DMA_READ_BYTES`**/**`DMA_WRITE_BYTES`** (completed
`bytes_done`, never requested length). The whole contract, stated once so it stays small:
- **Observational, never authoritative.** Monotone within a bounded publication lag; reads may
  aggregate implementation-private shards (Appendix E); a traffic value never feeds accounting,
  authority, completion, or synchronization — exact charging is the separate §16.4 machinery,
  deliberately.
- **The hot-path rule.** Observation adds **no global ordering edge, fence, or
  shared-cache-line dependency** to the observed operation — a thousand concurrent callers of
  one gate never serialize on telemetry, the §16.4 subtree-isolation invariant applies to the
  counters themselves, and the §9.2 warm bound is unaffected.
- **Read authority.** The `PMU` right on the object capability — traffic is **never readable
  merely because a domain may invoke or transfer through the object** (a client must not learn
  other clients' aggregate activity). Hardened views may disable, quantize, delay, or coarsen,
  exactly as §8.3 treats every counter.
- **Lifecycle (derived state, kept out of semantics).** 64-bit, monotone, **no reset operation
  exists**; zero at creation and at clone; checkpoint omits them by default (`OPTIONAL`-class
  derived state, §17.9); an import that retains them advances the observation generation.
  **Modular at 2^64 — these wrap, deliberately unlike every §3 counter, which saturates.** They
  are observational deltas, not freshness or progress facts: consumers subtract successive reads
  in unsigned arithmetic, for which a single wrap between reads is transparent, whereas a
  saturated byte counter would report zero traffic forever on exactly the busiest object
  (`window.dma_*_bytes` at fabric rates reaches 2^64 **bytes** within ordinary uptime).
- **No hidden caller table.** Per-peer attribution never lives in object state — sparse or
  dense, it would be the forbidden pairwise matrix plus unbounded identity retention. Pairwise
  affinity is the sampled `GATE_AFFINITY` record stream (Appendix G), observer-scoped.

| Class (Backing×Producer) | Sub-ops | Semantics |
|---|---|---|
| **ChannelEndpoint** (Memory/Thread, sw) — pipe/socket/stream | unpublished `channel.new/capacity/overrun/seal/abort`; live `channel.resize`, `channel.shutdown`, `channel.set_blocking`, `channel.take_loss`, fixed scalar getters | the `read`/`write`/`send`/`recv` target; capacity and overrun are independent builder facts, and overrun is valid only for record-oriented channels. Shutdown half-closes → peer sees `-HANGUP`. **Blocking policy is one bit of endpoint-description state, owned here** (§10): all handles to one description see it; an independent re-open does not. `take_loss` is the one consuming read, kept out of getters so introspection stays idempotent |
| **Counter** (Register, hw/sw) — semaphore/event/completion counter | `counter.new/destroy/read/set/add/threshold` | software reaches the one update transition through `counter.set`/`counter.add`; sealed hardware producers use their typed delivery relation. `wait` observes threshold readiness. **Existence test: this class exists for exactly the case atomics cannot serve — signaling between domains that share no memory** (a futex needs a shared word; a Counter needs only a capability), hardware-produced scalar completion, **and the RT chain that must not gate on an off-chain futex** (§9.2's engine-tracked alternative). Intra-domain, shared-memory counting is an atomic word + futex *by construction* |
| **Call-gate** (Thread, sw) | `gate.new`, `gate.entry`, `gate.stack`, `gate.limits`, `gate.timing`, `gate.abi`, `gate.borrow_arg`, `gate.seal`; `gate.submit` is the asynchronous invocation form and returns an ActivityRef | the `gate_call`/`gate_tail` target (§9.2); construction is an unpublished fixed-fact builder (`gate.borrow_arg` declares the register-described borrow's register positions and rights immutably), while call/submit descriptors describe invocation data only; cancellation is `activity.cancel` |
| **Timer** (Register/Memory, **hw**=clock) | unpublished `timer.new/clock/delivery_*/realtime/place/seal/abort`; live `timer.arm_rel/arm_abs/arm_phys/disarm/gettime/getoverrun` | clock, delivery, realtime admission, and placement are construction facts; an arm establishes only one deadline relation and optional recurrence |
| **CompletionQueue** (Memory, hw producer) | `cqueue.new/destroy/recv/peek` | bounded one-record-per-completion storage; a slot is reserved at submission and record observation carries acquire semantics |
| **InterruptWaitable** (Register, **hw**=device) | unpublished `irq.new/source/delivery/priority/place/seal/abort`; live `irq.mask/unmask/ack/ack_mode/destroy` | construction consumes one normalized `InterruptSource` facet; no instruction decodes raw MSI versus wired-line identities |
| **Waitset / EventRing** (Memory, sw aggregator) | `waitset.new/destroy/add/del/mod`; `eventring.new/destroy/bind`, `ready.next` | `wait` publishes to the explicitly bound first-class ring; no retained output pointer is hidden in a thread |
| **DMAWindow** (hw) | builder/seal (including the declared `window.pin` addressability fact, §11.4), remap, fixed scalar getters, extent cursor, and four typed submission-facet getters | construction is unpublished; the addressability fact is explicit (v1 admits only `PIN`, `window.faultable` is the Appendix G PRI/PASID seam's slot); bulk remap input is only the variable extent set; each submission facet fixes one DMA work schema |
| **WorkQueue** (Memory, **hardware-consumer** §15) | unpublished `workqueue.new/device/completion/seal/abort`; live `workqueue.teardown/set_blocking/get` | the device-drained submission endpoint; waitable for `WRITABLE`, fail-closed; no public incomplete state exists |
| **DebugTarget** (sw) | `bind_events`, `read_context`, `write_context`, `set_step`, `set_watch`/`clear_watch`, `read_mem`/`write_mem`; stopping uses lifecycle `quiesce`/`resume` | the whole debugger surface over one target domain, with no target cooperation required |
| **PMU** (hw) | `pmu.new/destroy/event/set_threshold/bind_waitable/read/reset` | capability-gated (§8); profiles remain explicitly typed |
| **ClockView** (hw) | `clock.set`, `clock.adjust`, fixed transform getters | the affine `{offset, slew}` over the timebase; readback is expressed against the reader's visible timebase |
| **MachineView** (hw) | unpublished `mview.new/tiles/features/counters/identity/time`, typed limit restrictions, `mview.seal/abort`, fixed scalar getters, and cursors | view 4 (§16.7); `env_open` answers from this object; every builder fact monotonically restricts the parent |
| **PagedBacking** (sw pager / hw fault path) | unpublished `backing.new/pager/charge/seal`; live `rebind_pager`, `detach_pager`, `retarget_charge`; typed residency, supply, reject, eviction, observation, rehome, clone, and persist verbs | pager protocol comes from the typed endpoint, not a configured version; a demand request terminates through `backing.supply_req`, `backing.reject`, rebind, or teardown, never silence (§15); plain `backing.supply` is pager-initiated admission |
| **FileDescription (hw parts only)** | `CURSOR_SET`(abs), `CURSOR_ADD`(signed) — pure cursor math, each returns the new offset (blocking policy is reached via the ChannelEndpoint facet, §16.0 — one description bit, one op, no duplicate setter) | the seekable cursor (§10.1). **Existence test: the cursor is engine state because the transfer that advances it is engine-executed** — `read`/`write` are chip opcodes, and a cursor living anywhere else would race the chip's own advance; hardware owns exactly the word its own hot path mutates, and not one fact more. A service transfer and cursor advance use one engine transaction keyed by dispatch `request_id`: cancellation before service commit leaves the cursor unchanged; service completion commits bytes and the corresponding cursor delta once; cancellation after that observes the committed result rather than rolling it back. Final close is the §16.0 `LAST_STRONG_REFERENCE(cookie)` event after accepted transfers quiesce. **And why a *class* rather than a ByteEndpoint facet:** the FileDescription **is the open instance** — the POSIX open-file-description model made a hardware object: `cap_dup`'d handles share **one description, one cursor** (dup semantics), while independent opens mint independent descriptions over the same underlying endpoint. That N-handles-to-one-cursor relation is an object identity, not an endpoint property — a cursor-as-facet would weld one cursor to the endpoint and delete independent opens. Honesty rider: the nonblocking bit needs no atomic-advance argument — it lives here only because the description is the natural one-bit home (per-open, shared by dup), a placement convenience, never this row's justification. **Append placement is *not* hardware-owned**: on a regular file it depends on current file size, enforced by the service on the write path — a service-owned flag (§16.5). End-relative and hole/data-aware positioning, flush, durability, and all metadata are likewise service-owned: the chip does not know file size or layout |
| **Capability/lineage** | `cap.seal`, `cap.rights`, `cap.class` (class plus class-defined profile), `cap.lineage` (epoch + flags, never referent count), `cap.restamp` | fixed-width introspection plus sealing and per-object route repair; copy/move/narrow/revoke remain the authority algebra |

**Timer construction and arming.** `timer.new` returns a generation-threaded unpublished
TimerBuilder. `timer.clock` binds one ClockView. Its `clockview_cap = 0` value is the declared
§2.2 sentinel for the issuing domain's own bound ClockView; it requires no capability-table entry
and cannot be denied independently of that bound view. A nonzero value names a granted ClockView
capability in the ordinary way. Thus every domain can construct timers for its own visible time,
while alternate clocks remain explicitly delegated. Exactly one `timer.delivery_*` fact supplies
the destination relation. `timer.realtime` binds a reservation and `timer.place` adds its
placement constraint. `timer.seal` atomically validates the clock, destination, admission,
and placement closure; `timer.abort` discards the builder. `timer.arm_rel(timer, delay,
period)` measures delay from the arm commit point. `timer.arm_abs(timer, deadline, period)`
interprets the deadline in the timer's bound ClockView and tracks later view adjustment by its
epoch rule. `timer.arm_phys(timer, deadline, period)` requires
explicit physical-time authority and never consults a ClockView. Period zero uniformly means
one-shot. No arm changes delivery, placement, or realtime admission.

**Completion storage.** A Counter is the single monotonically increasing, payload-free completion
primitive: hardware or software producers use `counter.add`, consumers use `counter.read`, and
`counter.threshold` exposes value-at-least readiness through the ordinary waitset/`wait` path. No
separate completion-counter class, signal verb, or private wait operation exists. A CompletionQueue contains a bounded
sequence of fixed completion records. Submission reserves one queue slot before accepting work;
`recv` consumes one record and `peek` observes without consuming; nonempty readiness
is consumed through the ordinary waitset/`wait` path. The v1 record is always the frozen 24 B
`{ActivityRef u64, status i64, value u64}` shape; its producer class fixes the meaning of `value`
(for example a gate return value or DMA `bytes_done`) without changing the record schema.
`record_destination` is therefore an `EVENT_RECORD_DESTINATION`, never a caller-sized query
buffer. Queue observation is acquire-like. The two capability classes are not interchangeable.

**Normalized interrupt sources.** Device discovery or an interrupt-controller service returns an
`InterruptSource` capability whose facet encapsulates raw requester/vector/remap state for MSI, or
controller/line/trigger/polarity/sharing state for a wired source. `irq.new` returns an unpublished
InterruptBuilder; `irq.source` accepts only that normalized facet, while `irq.delivery`,
`irq.priority`, and `irq.place` add common relations. `irq.seal` publishes the complete
InterruptWaitable. Live `irq.mask`, `irq.unmask`, and `irq.ack` operate on the common source
contract. Silicon never receives a union of raw MSI and wired-line operands.

**Admission-hold qualification to the PagedBacking lifecycle row.** Its unqualified teardown phrases
apply only to leases with no §16.1 dependency hold. `UNPIN_RESIDENT`/`RELEASE_PIN_LEASE` against a held
lease return `-BUSY`; leaseholder death releases only unheld leases, while the admitted reservation
continues to own and pay for held leases; backing destruction must first remove/destroy dependent
reservations or fail `-BUSY`. This qualification is normative over the abbreviated lifecycle text in
the table.

**The Debug doctrine (attach is authority, opacity is birth).** Debug is **not a mode**: every
DebugTarget operation is an op on a held `DebugTarget` capability, created by **`debug.new`** on a
domain cap carrying the **`DEBUG` right (bit20)** — at *any* time, including on a
**running** domain (the attach-to-a-live-process case: your session manager holds your domain caps, so
attach = mint + lifecycle `quiesce`, no pre-planning, no in-target stub, no consent from a possibly-corrupted
target) and on a **corpse** (post-mortem, below). This adds no escalation: a `DEBUG`-right holder
already dominates the target (budget, policy, termination); inspection is new *visibility*, not new
authority — and `WRITE_CONTEXT`/`WRITE_MEM` let the debugger act only *as the target*, inside the
target's own capability bounds. **And there is no opt-out — deliberately, by covenant (Appendix
H2): no birth flag exists that makes a domain uninspectable by its dominator chain.** A machine
that could *prove itself uninspectable* to a remote party would be a machine with a distrust
zone against its own owner — the treacherous-computing shape — and this architecture refuses to
build it: the typed builder fact `dmeasure` carries birth *measurement* for the owner's fleet verifier
(§16.9) and no inspection consequence of any
kind. Multi-tenant follows from possession: a tenant holds its own subtree's caps and no one
else's — debugging its domains perturbs nothing outside them, and a tenant's protection from
its *host* is a contract between people, not a silicon promise.

**The execution-hold algebra (the single source for every stopping mechanism).** A thread's
runnability is one predicate over independent **hold tokens**, and this is the *only* place the
machine defines "stopped": `runnable(thread) = alive ∧ has_budget ∧ ¬terminal ∧ HoldSet(thread) =
∅ ∧ HoldSet(domain) = ∅`. The frozen facts are **behavioral, never a construction**: each hold has
an independent owner and its own set/clear events (a dominator's `quiesce` token, the
debugger-owned lifecycle quiescence, the scheduler's reservation throttle, the single-step stop);
**releasing one hold never releases another** (each clears only through its own event); and
**engine teardown outranks every instruction-issue hold** (a quiesced or debug-held thread is
still force-terminated by §9.4 / a dominator kill — holds gate *issue*, never engine-executed
teardown). What is *not* frozen: one physical hold engine, a bitset layout, or a scheduler
pipeline — an implementation represents the token set however it likes. Every stopping mechanism
below is an instance, not an independent definition.

**Debugger quiescence is per-thread and composes by the algebra.** Lifecycle
`quiesce(debug_target, ACTIVATIONS, tid)` returns a token for one thread; `THREAD_ALL =
UINT64_MAX` selects every thread. `resume(debug_target, token)` clears that **debug hold**,
independent of a whole-domain quiescence hold: a thread runs only when its
`HoldSet` and its domain's are both empty — the algebra's predicate, not a bespoke composition rule.
Per-thread freeze is what single-stepping one thread of a live process requires; the domain-level op
keeps its atomic stop-the-world meaning.

Rules that keep it honest: context and memory *writes* and `SET_STEP` require the target thread
**debug-frozen** (`-BUSY` otherwise); `READ_CONTEXT`/`READ_MEM` work frozen or dead; step/watch hits
**freeze the thread and emit a frozen-format event record** to the endpoint bound by `BIND_EVENTS`
(never to the target's own machine-call path — the target may be the thing that's broken), and while a
debug endpoint is bound, `trap 0` and would-be-domain-fatal faults route there too (thread freezes)
instead of terminating — breakpoints and crash-catching in one mechanism. **`READ_MEM`/`WRITE_MEM`
exist because the target's anonymous/COW-private memory has no backing object nameable from outside**
(`mmap` `backing_cap` `0` = anonymous, §11.2), so these ops are the one architected path into the
target's *address-space view*. **`WRITE_MEM` never writes a frame reachable by any domain
outside the target**: a patch to a page whose frame is shared — a shared backing, including
backing-tagged text (§15) — materializes a **target-private copy** of that page through the
ordinary COW machinery, invalidates only the target's translation, and leaves the backing and
every other mapper untouched; one tenant's breakpoint is never another tenant's `trap 0`.
**Watch scope, stated for debugger expectations:** watchpoints observe the target's own CPU
accesses (the per-thread range monitor) — never DMA and never other domains' accesses to shared
frames. A watch names one live target `tid`; `UINT64_MAX` is the declared all-target-threads
sentinel. A dead or foreign `tid` is `-STALE`. This scope is load-bearing: operating-system debug
register ABIs select an LWP, and a target-wide-only watch would spuriously stop sibling threads.
**Step scope at a boundary:** `SET_STEP` is scoped to the target domain — a stepped
instruction that crosses a gate completes the step **at the crossing** with a
left-domain event record, never by re-entering inside a domain the DebugTarget does not cover. **Detach unwinds cleanly — unbind, `cap_revoke`, or debugger death are
all the same path:** step and watch state clear (watch-slot budget released), and every debug-frozen
thread reverts to its **pre-event disposition** — a thread frozen on a routed would-be-fatal fault
becomes domain-fatal as if never routed; a thread held on step/watch/`trap 0`/explicit quiescence
resumes. A crashed debugger strands nothing; domain-freeze holds are untouched (they belong to the
domain cap). **Post-mortem:** a non-opaque domain's fatal termination preserves each thread's final
architectural register file + fault cause **and the complete logical address-space view** in the corpse
until reaped. Every anonymous/COW-private resident frame is retained; every named or externally backed
VMA keeps an object reference, so an engine DebugTarget read may resolve nonresident content through
that surviving backing/pager relationship. The VMA tree cannot mutate after death, and reclamation
cannot race `READ_MEM` while any DebugTarget or corpse-domain handle exists. Thus `READ_CONTEXT` plus
`READ_MEM` is a defined core dump, not merely a register dump. The corpse continues paying from its
unrefunded memory/object budgets for VMA metadata, private frames, backing references, contexts, and
debug-read pager state; the parent cannot reuse those carved resources meanwhile. **Reap is the
last-reference event:** after all DebugTarget and corpse-domain handles are dropped or revoked and all
in-flight debug reads quiesce, the engine releases the retained address space and refunds the corpse's
charges. There is no separately callable `REAP` verb; a post-reap stale handle returns `-STALE`.
**RT forfeiture is per-mechanism, never per-object**: single-step, watch-armed execution, and
holds of unbounded duration forfeit the target's published RT bounds (debug is allowed to be
slow); bounded introspection — `read_context`, `read_mem`, a hold with a bounded release — is
an ordinary §16.4 bounded transaction and breaks no RT contract (a monitoring agent sampling
registers does not void the target's guarantees); other domains' reservations are untouched. External JTAG-class
debug, when it exists, must materialize as a `DebugTarget` held by board policy — the same object, the
same rules, no second path (the whole-machine mediation obligation; it is also how the *first* domain
is debugged, §11). **Hardware honesty: the profile adds exactly two genuinely new hardware behaviors —
single-step and watchpoints.** They are irreducibly new silicon (nothing else re-enters after one
instruction or matches data addresses against armed ranges); everything else is reuse — freeze is a
scheduler hold, contexts are the §17.5 layout, events are an ordinary endpoint, memory access is the
target's own translation path, post-mortem is the corpse the object model already keeps. The claim is
"two new mechanisms, ten ops of plumbing," not "zero new hardware." `WRITE_MEM` to executable pages is
the architected breakpoint-plant path (the §6 fetch-atomic story; W^X governs the *target's* stores,
not the debugger's architected patch route, and per-fetcher `isync` rules apply as for any patch).
**And the doctrine that follows: DebugTarget is a capability bundling general introspection
mechanisms, not a debug subsystem** — context read/write is the §17.5/§16.8 mechanism under a
right, memory access is the dominator's address-space reach, freeze is a §16.3 hold token,
event binding is an endpoint; only step and watch are debug-native. Non-debug consumers use the
general mechanisms without apology: migration reads contexts, supervisors dump cores, GCs take
bounded holds, profilers bind events. **The authority splits accordingly (least privilege):**
`read_context`/`read_mem`/`bind_events` and bounded holds derive from **`INSPECT`** (bit 23);
`write_context`/`write_mem`/`set_step`/`set_watch` derive from **`DEBUG`** — the debug mint
carries both, and `cap.copy` narrows to an `INSPECT`-only handle, so a monitoring agent that
samples stacks never holds the authority to rewrite the target's registers.

### 16.4 Bounded time

Every hardware-owned sub-op completes in **bounded time** (an engine transaction, not a service
round-trip), which is what lets the control plane appear on real-time paths. **Bounded time is real
only because the data-structure sizes are bounded**, so the ISA fixes architectural maxima on every
per-op quantity a WCET argument depends on (exact floors queryable via `env_open` `GEOMETRY`):

**Three quantities, never conflated (the floor doctrine).** Every bounded quantity below is
exactly one of three things, and each bullet says which. **Semantic capacity** — how many objects
may *exist* — is bounded by the owner's charged budgets (`engine_accounting_table.md` rows) and by
nothing in this list: no constant below is a ceiling on existence. **Resident capacity** — how
many objects enjoy cache-like hardware acceleration at once — is what the floors below guarantee;
exhausting a resident structure **evicts, performs a bounded invalidation, reloads, parks the
issuer at an instruction boundary (Law 5), or spills to protected, non-pageable, engine-managed
storage** (the front-matter liveness rule: never a pageable software service) — it never changes
an operation's semantics and never fails a creation the budget admits, and the non-resident
path's latency class is published like any other bound. **Admission capacity** — how many can
make *progress* concurrently — is priced by budgets and Appendix C, never by a structure size.
**Per-op operand maxima** (masks, iovecs, descriptors) are the fourth, honest kind: true
per-*operation* bounds, each with an architected composition path for larger work. Where a true
minimum must scale with the machine, a future revision states it as a monotone function of
published `GEOMETRY` facts (execution-agent count, volume size, memory capacity, engine count) —
a geometry-scaled floor ages better than a constant; the v1 constants below are audited minima.

- **caps per transfer mask** (per-op operand maximum): `CAP_TRANSFER_MASK_MAX = 16` capability
  arguments in `dgrantm`, `dspawn`, gate, and message
  transfers; larger authority sets use repeated typed operations or a capability endpoint. **The
  mask is an inline fast path, never a ceiling:** the total authority set a spawn, a service
  handoff, or a restored domain receives is bounded by budget and the composition path, never
  by 16.
- **iovec count** (per-op operand maximum): `<= 1024` elements per vectored I/O sequence; larger
  transfers compose by repetition at the existing partial-result contract.
- **SGL entries** (per-op operand maximum): **`SGL_MAX = 1024`** per DMA CopyV descriptor (§17.8) — the iovec family's bound
  applied to the copy path, so SGL snapshot-validation is as bounded as vectored IO's.
- **WorkQueue bounds:** `WORKQUEUE_DESC_MAX` (guaranteed minimum **256 B**, a per-op operand
  maximum) and `WORKQUEUE_DEPTH_MAX`
  (guaranteed minimum **1024** — admission capacity: a full queue is architected bounded
  backpressure, the one place `-NOSPACE`/blocking *is* the semantic) — a submission's WCET is the
  descriptor copy + O(1) enqueue +
  completion-slot reservation.
- **live domain tags** (resident capacity): `DOMAIN_TAG_CAPACITY` (guaranteed minimum **256**
  concurrently-*accelerated* tags,
  §15) — the one capacity the whole nesting story leans on, so it gets a floor like every other
  frozen-binary dependency rather than staying a bare `GEOMETRY` field. 256 is the defensible
  container-in-VM-in-VM minimum; the actual is queryable (§B26). **This is a resident floor, not an
  architected 8-bit tag field and not a bound on live domains:** the tag is a cached
  translation/protection accelerator index, engine-private, representation/width
  unconstrained (wider tags, epochs, indirection, tag sharing all conforming). Architected domain
  *identity* is the domain's incarnation — its epoch-cell lineage (§3), which never wraps within
  a live table — and how many domains *exist* is semantic capacity, bounded by charged budget
  alone: tag shortage causes eviction, the bounded per-tag sweep (§15), reload, or a parked
  retag — **never a domain-creation failure at the floor**.
  **Sizing guidance, non-normative
  but stated where silicon will read it:** a dense container host runs *thousands* of domains with
  hundreds hot — the floor is the conformance line, and an implementation targeting that market
  should overshoot it by an order of magnitude; the per-tag-sweep recycling bound keeps exhaustion
  sane, not cheap. Below a floor, the depth invariant
  would be true and useless at once — a machine with four live tags satisfies "O(1) translation at
  any depth" and supports no real nesting.
- **builders and activations** (resident capacity): at least 64 unpublished builders and at
  least 256 activation frames *resident-accelerated* per volume; actuals are `GEOMETRY`
  properties. **Existence is semantic capacity:** builder count is limited by the owner's charged
  resources (the builder-staging accounting rows), never by the resident floor — past the
  resident population, staging spills to protected, non-pageable, engine-managed storage or the
  issuer parks at an instruction boundary, the spilled path's latency class is published, and
  `-NOSPACE` at the floor is nonconforming for a volume whose budget admits the builder.
  `dspawn` is latency class 3 (configuration-state-parametric publication and named admission);
  `dcall` is
  latency class 1 absent queueing. General publication cost is parameterized by mapping count, staged
  grants, explicit set size, admission dependencies, and the authority/distance spans named by the
  builder—never by machine size or ancestry depth.
- **gate residency** (resident capacity): `GATE_RESIDENCY_LEASES` (guaranteed minimum **64**
  leases per volume; actual queryable). A lease pins one gate's resolution, target metadata,
  entry translation, and one activation slot resident, making the §9.2 warm bound
  (`GATE_WARM_RTT`, a published `GEOMETRY` fact, never a constant) **ledger-covered** on that
  path — recorded at real-time admission exactly as §15 records pin leases. Unleased gates
  share the same acceleration best-effort; residency exhaustion demotes a call to the priced
  cold path (evict/reload/park), never fails it; lease exhaustion is admission-time
  `-EXHAUSTED` for the *lease*, never a gate-call failure.
- **placement sets:** `dplace` cost is bounded by the explicit set's cardinality and the view's
  topology diameter—a topology-parametric bound, not an ABI constant.
- **debug:** `DEBUG_WATCH_SLOTS` watchpoints per domain (guaranteed minimum **4** — true charged
  hardware scarcity: a comparator either exists or does not, so this floor *is* a semantic
  per-domain bound, the honest exception the doctrine above forces this list to declare), charged to the
  *target's* object budget; `READ_CONTEXT`/`WRITE_CONTEXT` move one §17.5-layout record; every
  DebugTarget op is a bounded engine transaction — debug may break the *target's* RT bounds, never the
  engine's.
- **the scheduler-charging machine gets a number, not a bound-class** (it touches every context
  switch, so it is the one engine that owes one): per scheduling event the engine does **one
  counter decrement (charging) and one comparator write (deadline arm)** against flat reservation
  state — no tree walk exists to hide (§16.1). The published target: **engine work per scheduling
  event fits inside the context switch's existing pipeline shadow** — a bid, demonstrated on the
  in-order core before it is believed for a wide one, and falsifiable on both.
- **and the scheduler's *locating* work is contract-bound too, because the number above prices the
  wrong thing alone:** one decrement plus one comparator describes work per *decision*, not how
  runnable work is *found*, and a large machine hiding a global runqueue, a global EDF heap, or a
  global placement lock behind that per-event figure would be conforming on paper and unbuildable
  in fact. So the physical contract is stated: ordinary dispatch selects from **tile-local
  runnable state under bounded local selection** — no machine-global arbitration on the dispatch
  path, ever; cross-tile movement is an **explicit migration step off the dispatch critical path**
  (steal/rebalance protocols, reservation admission tokens cached locally at `domain.reserve`
  time); and thread-directory ownership is distributed exactly as the names already are
  (subtree-scoped IDs, §8.2 — the allocator rule doubles as a sharding rule). An
  **This contract is partitioned EDF / partitioned proportional-share with explicit migration** — global EDF's
  optimality-at-unbounded-migration-cost is deliberately not the model, and thirty years of
  partitioned-admission results are the ones that transfer. An
  implementation that funnels unrelated tiles' dispatch through one structure is nonconforming
  under the same clause as an engine that funnels unrelated objects through one lock (§16.4
  concurrency license — this is its scheduler twin).
- **the distribution rule, generalized (what "no global state" actually obligates):** the
  architecture deleted global *names*, not global *usage* — a root lineage cell, a hot shared
  backing's reverse map, domain-tag allocation, a machine-spanning view's epoch are all state
  with machine-wide readers. The scaling contract for every such structure is Law 8's shape
  applied to implementation: **an operation's cost may grow with the span of the authority it
  exercises, never with the size of the machine around it** — referent counts shard, reverse
  maps live with the backing's home, tag allocation is per-volume with lazy global reconciliation.
  **And "referent counts shard" is a named obligation, not a passing remark, because the
  wide-cell counter is the one global structure ordinary operations would otherwise touch:** the
  stamp cell of a popular machine-wide service and a widely-delegated lineage cell have their
  referent counts touched on every mint, re-key, and drop, machine-wide — so those counts
  **must** shard (per-volume sub-counts with lazy reconciliation at the cell's home is the
  existence construction), and a naïve global counter incremented per ordinary capability
  operation is **nonconforming under the invariant below**, tested by its Appendix D generator
  (two unrelated subtrees hammering mint/drop against one popular service's stamped objects).
  **The same obligation covers a hot shared backing's metadata** — the libc image mapped by a
  hundred thousand domains: mapper counts and reverse-map anchors are homed with the backing,
  may be hierarchically summarized per volume, and are written **only** by mapping
  create/destroy and residency transitions — an ordinary access or instruction fetch never
  updates a central mapper record, the backing-tagged shared translation (§15) keeps one TLB
  entry serving every tenant, and the metadata/directory span is charged to the backing owner.
  The obligation sharpens to one **testable invariant — the subtree-isolation invariant: no
  *ordinary* operation by one protection subtree may modify a cache line or queue also needed by
  an unrelated subtree.** Stated as modification-of-shared-state rather than prose about
  "distributed implementation" because it is directly checkable — it catches the hidden global
  reference counter, the central completion queue, and the root lock that generic sharding language
  lets through. (*Ordinary* is load-bearing: widely-delegated **revocation** legitimately performs
  wide-span invalidation — the authority itself was widely delegated, so its span is Law 8's, and
  the operation is a rare control-plane event, never a requirement on ordinary use.)
  **Replica and directory capacity is admitted, not hidden:** creating the first referent in a new
  volume reserves that cell's local replica and directory route against the cell owner's object
  budget before the transfer commits. Insufficient admitted storage fails the mint/re-key/transfer
  `-EXHAUSTED` with no new referent. The reservation remains charged until that volume's last
  referent drains. Thus no unreported implementation-wide replica limit may fail an operation whose
  owner already holds the admitted budget, and provisioning is observable through ordinary budget
  admission rather than an unspecified directory-size cliff.
  (Centralization is always available to a small
  implementation — a laptop-scale part may keep one runqueue *because* its span is the machine;
  the contract binds asymptotics, not floorplans.)
- **configuration-time hierarchy/dependency walks are parametric bounds:** `domain.reserve` admission is
  `O(ancestry depth + admission-dependency entries)` (§16.1's ledger; the current VMA/pin set is
  enumerable before the call) and `domain.place` narrowing checks `O(children)` — bounded by a
  **caller-constructed** quantity, not an architectural constant (no architected maximum nesting depth;
  depth is practically bounded by budget carving), and both are **configure-time ops, never RT-path
  ops** — the runtime invariants they establish (flat O(1) reservation charging, the effective mask)
  are what the RT path touches. Likewise **full `state.open`/`state.import`/`state.commit` are
  `O(subtree state)` — configure-time by definition** (the subtree is quiesced). The blanket claim therefore reads:
  constant-bounded on the RT path, parametric-bounded at configuration, unbounded nowhere.
- **waitset members touched per `wait`:** bounded by the bound EventRing capacity — caller-chosen,
  so parametric: a real-time caller bounds its own wait with a small ring (surplus
  readiness is retained); `ADD_MEMBER`/`DEL_MEMBER`/`MOD_MEMBER` touch O(1) members.
- **replacement builders:** publication cost is bounded by explicitly named mapping, grant, entry,
  dependency, and admission counts; no plan array or chip-decoded replacement record exists.
- **typed operation state:** a fixed-form instruction names at most its register operands and one
  explicitly bounded set/cursor/stream object. Service gate/message inline payloads are each
  `<= 64` KiB; larger payloads use endpoints. No generic control body exists.
- **pin accounting:** every architected physical-page pin (the `recv` writeback
  target §10.2, the gate descriptor §17.1b, DMA pins §15, `PIN_RESIDENT` ranges) **charges the pinning
  domain's memory budget for as long as it is held**; a pin that would exceed the budget fails its op
  `-EXHAUSTED` before any effect. A pin is never free authority over physical memory, and an
  unaccounted-pin DoS is impossible by construction. (§11's engine-accounting rule is this doctrine
  universalized to all engine-held state.) **`PIN_RESIDENT`'s refund event, named:** the pin is a
  **lease** (`{backing, leaseholder, lease_id}`, §16.3) released by **`UNPIN_RESIDENT`** on that
  lease (the ordinary end — `mlock`/`munlock`, temporary RT admission, transient DMA prep all
  cycle it), with leaseholder-domain
  death and backing destruction as fail-safe backstops releasing only that holder's leases **except
  while an admission-dependency hold exists (§16.1): the admitted reservation then owns the continuing
  pin charge until it is removed or its domain is destroyed**;
  per-page counts sum live leases, so overlapping pins compose; `EVICT` overlapping any live lease is
  `-BUSY` — a pin is precisely a promise `EVICT` cannot break. **The futex word holds no pin —
  stated, because the alternative would make ordinary synchronization an implicit `mlock`:** a
  parked waiter may sleep for hours, and pinning the word's frame for that duration would defeat
  paging and compression for exactly the pages every process touches. None of the futex machinery
  needs the frame: the wait-queue key is *logical* (§6 — object identity + offset, deliberately
  frame-independent), the compare is an ordinary coherent access at `futex_wait` issue, wake
  operates on the key and never touches the word, and unmap-under-wait already cancels waiters
  through the VMA epoch bump. The word's page is pinned for the duration of nothing.
- **caps per message: `<= 16`** — the same bound as `dgrantm`/`dspawn` masks and the gate's
  `max_cap_transfer` ceiling, one constant machine-wide (`MSG_CAPS_MAX = 16`); a `send` presenting
  more is `-MALFORMED`. **Queued-message cap references are accounted, not ambient:** each queued
  capability counts 8 B against the endpoint's `buffer_bound` like the bytes it rides with, and
  destroying an endpoint with queued messages **drops their strong cap references exactly once**
  (§3.1's aggregation-drain rule — never leaked, never delivered).
- **grower-pays, the attribution rule for aggregation objects:** a waitset member record charges the
  **adder's** object budget (`ADD_MEMBER` `-EXHAUSTED` against the caller; refunded at `DEL_MEMBER`,
  member auto-removal, or waitset destroy) — a shared waitset cap is not a license to grow engine
  state attributed to nobody; the same rule is why `AS_MAP` charges the *target* (the authority
  holder chose the growth) and `SET_WATCH` charges the *target* (the `DEBUG` right is domination).
  Named here so every future aggregation object inherits it by default.
- **pager engine-state, charged (§15's additions join the doctrine by name):** an outstanding
  fault-request record rides the faulting thread's **park record** (waiter-charged, §11 — it exists
  iff a thread is parked on it; re-delivery re-points it, never duplicates it; the reserved
  device-initiated PRI seam must bring its own request bound when it lands, stated now so it cannot
  land without one); a backing→mappings **reverse-map entry** is part of the mapping's VMA record
  (mapper-charged, created and freed with the mapping); the per-frame **charge field** is frame
  metadata (§15 rule 1, charge-target-charged). An `mview.seal` charges the **caller's**
  object budget like any mint. **Exited-thread zombie state** (the §16.3 exit-code record) charges
  the domain's object budget until reaped by the last handle drop — the corpse rule's live-domain
  sibling.
- **telemetry, charged (the dangling budget dimension, closed):** every observability record —
  PMU overflow, branch records, debug events, future trace — drains over an endpoint its
  **observer** created and pays for (`buffer_bound` — the debug-event rule generalized:
  observer-pays is grower-pays applied to watching); the `telemetry_quota` budget dimension
  bounds the **engine-side emission state** a domain's own bound observers may hold against it
  (record backlog, bound waitables), charged when the typed relationship is bound and refunded at unbind —
  so observation cost is always attributed, split between the watcher's queue and the watched
  domain's quota, and never a ledger of last resort.
- **engine concurrency (the scaling license — the §6 far-execution license's system-side twin):**
  engine ops on **distinct objects** must not serialize against each other beyond bounded
  arbitration — hot gates, queues, backings, and cells scale like addresses, not like a lock. The
  only architected serialization points are **per-object** (a serialized gate's queue, a cell's
  bump, a queue's slot reservation, a backing's offset range); an implementation whose typed operation
  path funnels unrelated objects through one shared structure fails these bounds under contention
  and is nonconforming for it.
- **cap-table op complexity:** slot allocation/lookup/drop is O(1), never a walk (a direct-indexed
  table with a free list is the §1.1 existence construction); `cap_revoke` performs O(1) marking (one
  home-cell increment, §3), never a descendant walk, while return latency includes the bounded
  invalidation acknowledgement over the lineage's referent span.

An op exceeding one of these bounds fails `-MALFORMED`/`-OVERFLOW` before any effect; none is a silent
truncation. These maxima are what make "bounded" a checkable property rather than an aspiration.

**The instruction-state discipline behind Law 5's bound: an instruction is always in
exactly one of four states** — *(1)* executing internally within its published bounded interval,
*(2)* committed, *(3)* **parked** at an architected boundary (every indefinite wait is a park —
a preemption point, cancellable, serializable), or *(4)* cancelled/restartable at its defined
safe point (§9.3). **The forbidden fifth state is "actively executing while awaiting":** no
instruction may hold the executing state against a software service, a pageable structure, an
unbounded queue, device cooperation beyond the published fence recourse, or arbitration whose
participant population is outside its bound — each of those is a park or a fail, never a stall.
Parametric bounds are legal exactly when **their parameters are visible before issue or
admission** (view geometry, placement, the ranges an op names) — a bound whose parameter
surfaces only during execution is not a bound.

**And the bounds include waking up.** Every published bound — engine-op WCET, the acknowledgment
bounds (`INVALIDATION_ACK_BOUND`, `ATS_ACK_BOUND`), the `env_open` profiles — includes **worst-case
wake from any implementation sleep state**: a sleeping engine slice or cell home is conforming
precisely because its nap is inside the number, so deep sleep is legal by arithmetic, never by
exemption. The realtime half already exists as the reservation power floor (§16.1): admission
holds the reservation's tiles, engine homes, and interrupt paths at wake latencies inside the
published bound — latency tolerance *derived from admission control* (fail-closed, `-BUSY` at
admission if the floor cannot be held), never a second QoS mechanism bolted beside it. Everyone
unadmitted eats the bounded wake cost, which is what "idle" is supposed to mean.

**The adjoint rule (the accounting doctrine's closing symmetry, stated once).** The resource verbs
of this document come in pairs — `SUPPLY`/`EVICT`, `PIN_RESIDENT`/`UNPIN_RESIDENT`, `ARM`/`DISARM`,
`quiesce`/`resume`, charge/refund on every accounting row, and `state.import`/abort-or-`state.commit` at the top of the
tower — and the pair invariant is the same sentence every time: **the inverse returns the
accounting to zero and the pair-scoped observable state to ≈** (the §16.8 round-trip law's
equivalence, restricted to the state the pair owns). Stated as a rule owed by construction rather
than a pattern noticed after the fact: **every future resource verb ships with its adjoint in the
same change**, names it in its `engine_accounting_table.md` row, and the pair's round-trip joins
the Appendix D conservation family. A verb whose inverse cannot be named is holding something it
never accounted for — which is the §11 no-unattributed-state doctrine wearing its algebraic face.
And the pair is an **adjoint, never an inverse**: `EVICT` does not un-happen `SUPPLY` — the
post-state is ≈, not identity, and the machine's time never rewinds (§3's monotone rule).

### 16.5 Set, cursor, stream, and service algebras

**Immutable sets.** The `set` family contains:

```text
snew rd
sadd rd, set, item          srange rd, set, first, count
sremove rd, set, item       sunion rd, set1, set2
sinter rd, set1, set2       ssubset rd, set1, set2
```

Every successful mutator returns a new immutable set; the input remains valid. Sets represent
placement, tile groups, admission universes, feature/topology subsets, and other variable-size
membership facts. Their representation is opaque and may be inline, bitmap, ranges, trees,
compressed, or canonical. Cost is bounded by the explicitly named set sizes and locality span.

**Cursors.** `denum.begin rd, domain, kind`, `objenum.begin rd, object, kind`,
`cursor.next rd, cursor, destination`, and `cursor.end cursor` enumerate effective architectural
relations. A cursor is generation-stamped against the relation's root; mutation underneath either
produces `-STALE` where the relation requires a consistent traversal or follows the explicitly stated
live-sampling rule. It never exposes an internal node, table, or tree. **Cursor and readiness
policies are dual** — pull-side enumeration and push-side waiting are the two orientations of
one consumption relation (pull `-STALE`-on-mutation ↔ push member-retirement on `DEL_MEMBER`;
pull end-of-relation ↔ push final `HANGUP`) — and **a policy added to either side names its
dual or states its asymmetry**, so the two families cannot drift apart by accident.

**Mutating cursors (the range-operation shape).** The cursors above are read-only enumeration. A
**mutating cursor** — a range operation that commits destructive effects as it advances
(`munmap_range`, `map.protect`, `map.demote`, and any future class-4 range op) — is the same
resume mechanism under three added rules, because it *is* the mutation the read rule guards
against:

- **Progress is the cursor.** What has already been done is derivable from the returned cursor
  alone, so a resumed step never repeats a committed effect — per-frame refunds, charge releases,
  and cell bumps are exactly-once against the range, never once per attempt. An implementation may
  not keep progress in state the cursor does not name.
- **The `-STALE` rule inverts.** A read cursor is invalidated by mutation underneath it; a
  mutating cursor is that mutation, so it is stamped against its own range and the *other* agent's
  overlapping mutation is what fails `-STALE` — never the advancing operation.
- **Fan-out is issued once, never per step.** The invalidation broadcast a range op owes is issued
  once for the whole operation at its commit point; a stepped op that broadcast per advance would
  convert Appendix C's single class-2 round trip into one per page, which is worse than not
  decomposing at all. **`window.remap` (§15) is the worked example of the required shape**:
  install locally, *issue* the scoped invalidation, return without waiting, and publish a monotone
  progress generation (§3) whose acknowledged value the caller gates on — the property that makes
  an op callable from a non-sleeping execution context by construction.

**Observation generations.** `observe.mark rd_generation, subject, change_classes` establishes a
generation for a fixed subject and class mask.
`changes.begin rd_cursor, subject, generation, change_class`
enumerates the effective architectural facts changed after that mark. One cursor has one fixed result
schema; the selector never chooses an operation-dependent output record. Defined classes are dirty
memory ranges, mappings, capability-table relations, activations, hardware-object state, and explicit
service imports. Implementations may use dirty bits, write-protection epochs, logs, hierarchical
summaries, protected software, or any combination; only the resulting changed set and stated
conservatism are architectural. A class may conservatively report an unchanged fact, but may not omit a
fact whose post-mark change can affect the corresponding full state stream.
`observe.mark` and `changes.begin` require the subject class's inspection right; for Domain this is `MAP` for
mapping-only observation, `DEBUG` for activation state through a DebugTarget, and `SERIALIZE`/`STATE`
for a closed multi-class generation. The function derives that right from the fixed class mask.

Memory-error observation uses four additional fixed functions:

```text
incident.bind  rd, subject, event_ring
incident.begin rd_cursor, subject, since_generation
cursor.next    rd, cursor, record_destination
incident.ack   rd, subject, incident_id
```

`incident.bind` selects the ongoing doorbell destination; the ring notification is only a wake hint.
`incident.begin` returns a cursor over unacknowledged incidents at or after the named generation;
`cursor.next` writes exactly one frozen `MemoryIncident` event record to an
`EVENT_RECORD_DESTINATION` (the one consume op — no per-relation `next` exists).
`incident.ack` is idempotent. Incident records are hardware-produced event data, while enumeration and
acknowledgment remain separate operations.

**State transport.** `state.open rd_stream, object, mode, generation` opens a typed state stream
for any serializable architectural object. The object's class fixes the schema. Modes are full state,
state since a compatible generation, metadata only, and stable diagnostic snapshot.
`state.import rd_builder, class, parent, mode` creates an unpublished typed import builder; ordinary
`write` supplies the stream; `state.commit rd_object, builder` validates and atomically publishes the
result. A successful commit consumes the builder; a failed commit retains no partial object and leaves
the builder retryable unless the malformed stream is builder-fatal. Ordinary `read` moves export bytes.
The stream owns parser/session state, so no instruction parses a generic request record and no stream
exposes implementation records. **State streams describe or reconstruct architectural state; they
never request arbitrary actions.** Modes have the universal meanings above and do not acquire
class-private suboperations. A state header cannot contain an operation ID, arbitrary scalar
arguments, capability/result arrays, callbacks, or administrative commands. Import can only
reconstruct the typed state named when its builder was created. Domain state is one application;
§16.8 defines its cut, wire, dependency, authentication, and nothing-retained rules.
`state.open` requires the class's state-read right; full Domain state requires
`SERIALIZE`/`STATE`. `state.import` requires `CREATE` on the receiving parent, and
`state.commit` revalidates that authority plus every staged capability at its commit point. The
`parent = 0` value is the declared §2.2 sentinel for the issuing Domain's implicit self-capability;
it requires no capability-table slot. A nonzero `parent` names a held Domain capability with
`CREATE`. Raw `DOMAIN_ID` values are identities, never substitutes for either form of authority.

**Lifecycle algebra.** The fixed-form `lifecycle` family is:

```text
quiesce        rd_token, subject, scope
resume         rd, token
activity.cancel rd, activity_ref
queue.drain    rd, submission_object, deadline, disposition
```

`quiesce` closes admission for the named scope, reaches architecturally safe points, orders all prior
effects in that scope before success, and returns an epoch-protected token naming the stable interval.
An implementation may implement a narrower request with a stronger scope. `resume` ends exactly the
hold named by the token; a stale or already-consumed token is `-STALE`. Independent
holds compose: a subject resumes only after every live hold covering the attempted action is released.
Owner death releases its holds; it never silently publishes imported state.

Scopes are universal state classes: `ACTIVATIONS`, `NEW_ENTRY`, `MEMORY_MUTATION`,
`CAPABILITY_MUTATION`, `SUBMISSION`, and `FULL_SUBJECT`. No object class assigns a private meaning to
a scope. `activity.cancel` accepts only a generation-qualified `ActivityRef`; it performs the common
idempotent cancellation/terminal-selection protocol and publishes ordinary completion. `queue.drain`
accepts only a submission-bearing object facet. Its universal dispositions are `FINISH_ACCEPTED`,
`CANCEL_CANCELLABLE`, `REJECT_NEW`, and `REUSABLE_BOUNDARY`; object-specific results remain in normal
completion records. Neither instruction accepts a descriptor or a class-private policy catalogue.
These operations serve shutdown, debugger stops, garbage-collector safepoints, code replacement,
resizing, device reset, and resource reassignment as well as state capture.
Self-quiescence requires `CONTROL`; quiescing another Domain requires `ADMIN` on that Domain;
quiescing through a DebugTarget requires its `DEBUG` authority. `queue.drain` requires submission
control. A live `queue.drain` may park until its deadline, but it is `DRAIN_ONLY` for state transfer:
submission-bearing objects are `DRAIN_REQUIRED` and have no pending-submission wire body, so FULL
quiescence finishes or cancels the drain before capture and never emits a DRAIN_WAIT referring to a
non-drained queue. `quiesce` itself is likewise `DRAIN_ONLY`: success returns the token certifying a
completed stable interval, while a half-acquired hold is not importable state. `cap.revoke_wait` is
`DRAIN_ONLY` because its acknowledged bump may already have made the operand stale; reissuing that
instruction after import would not preserve its original terminal choice. `activity.cancel` performs
the ActivityRef origin check. A token carries no authority beyond
releasing the hold it
created and is usable only by its creating domain.

**Atomic cell repoint.** The authority family's
`cell.repoint.prepare rd_token, cell, expected_target, new_target`,
`cell.repoint.commit rd, token`, and `cell.repoint.abort token` conditionally transfer one
architecturally defined epoch-cell edge. Before commit the expected target remains authoritative and
the new target is not; success atomically repoints exactly that cell; failure or abort leaves the
expected target authoritative. Tokens are epoch-protected, replay-safe, time-bounded,
nontransferable, and charged to their preparer. The primitive accepts no participant array,
rebinding list, migration policy, stream location, callback, or successor plan. Service succession,
hot upgrade, failover, resource custody, and migration cutover are software applications only when
their authoritative edge is already represented by such a cell.

**Properties.** A property selector is admitted only in a class-specific instruction whose definition
fixes its register result shape. Scalar facts return registers, collections return cursors, byte
representations return streams/endpoints, and service-defined meaning uses a gate/message protocol.
There is no generic `setprop`; mutations use typed verbs such as `clock.adjust`, `timer.arm_rel`,
`channel.resize`, and `set_blocking` (narrowing a view is child-view construction,
never a mutation of the parent's).

**Rare workflows are compositions, not instruction classes.** Checkpoint, restore, live migration,
debugging, hot upgrade, and container suspension are programs composed from quiescence, observation
generations, cursors, state streams, unpublished construction, queue drain, activity cancellation, explicit rebinding,
and atomic succession. No instruction exists solely to name one of those workflows. A primitive
proposed for checkpoint or migration is admitted only if it also has a credible ordinary use in
scheduling, memory management, debugging, reconfiguration, persistence, replication, or lifecycle
control.

**Chip-decoded operation admission test.** Every proposed operation must answer yes to all seven:

1. Can every semantic operand be named in fixed registers or as a typed object?
2. Is referenced memory variable data rather than an operation description?
3. Does every selector choose a fixed-width property, collection, or stream rather than arbitrary semantics?
4. Does the instruction name one reusable primitive rather than a complete workflow?
5. Can hardware change its representation without changing the instruction sequence?
6. If configuration is split, does unpublished construction prevent partial live state?
7. Would a compiler naturally model it as an instruction, call, cursor, stream, or linear builder rather than a syscall wrapper?

**Broad-verb decomposition rule.** The catalog linter flags chip-decoded names containing
`configure`, `control`, `modify`, `update`, `set_options`, `query`, `execute`, or `operation`.
Such a name is rejected unless its review entry proves one indivisible architectural relation.
Operands must be split whenever they modify independently meaningful relations with different
rights, ordering, quiescence, failure, accounting, revocation, or serialization behavior. Renaming a
broad verb does not satisfy the rule; the transition itself must be single-purpose.

**Semantic-variation rule.** Register fields and small immediates may select members of one closed
architectural relation. A field must be split when any two values differ in operand interpretation,
required authority, result shape, atomicity or commit point, completion guarantee, quiescence,
accounting dimension, modified epochs/generations, object lifetime, or independent usefulness as an
operation. Permission bits, rounding directions, comparison predicates, a uniform ABI class, and a
homogeneous budget dimension pass this test. `DEMOTE` inside protection, lazy discard inside
destructive discard, executable/contiguous allocation flags, cross-kind birth flags, and revocation
completion policies fail it. The catalog records the ten-dimensional review rather than banning
operands merely because they are named `mode`, `flags`, or `policy`.

**Complete-live-object rule.** A constructor returns either a complete usable object or a typed
unpublished builder. Ordinary object states named `UNESTABLISHED`, `UNBOUND`, or `INCOMPLETE` are
forbidden. Mandatory relationships are builder facts and become observable together at seal.

#### Service-dispatched profiles (typed protocol; semantics are service-owned)

When an object's semantics are **service-owned**, software invokes its stamped service gate or
endpoint using the typed protocol assigned to that service class. The engine validates the target
capability on transfer, resolves the service-relationship cell, and performs ordinary gate capability
installation; it does not decode a method envelope. File metadata, socket options, and personality or
device policy remain open-ended client↔service protocols. A service may block, so calls are
cancellable/restartable (§9.3) like any gate.

**The common service-continuity profile (control semantics frozen; state bodies opaque).** A
relationship registered `RECOVERABLE` implements the version named in its relationship cell. An
authorized coordinator explicitly invokes pre-copy, cut/import, and terminal messages through the
service profile; no native instruction or engine invokes them implicitly. The lifecycle messages are
`DESCRIBE_CONTINUITY`, `EXPORT_BASE`, `EXPORT_DELTA`, `PREPARE_CUT`, `PREPARE_IMPORT`, `COMMIT`,
`ABORT`, and `PREPARE_BINDING`. Their common meanings are fixed even though each service's graph/state bodies are versioned
and opaque: description reports sharing and destination prerequisites; base/delta export may run
before quiescence; `PREPARE_CUT` seals one service generation and classifies every accepted `request_id`
as **committed-before-cut**, **restartable-after-cut**, or **exported-open**; `PREPARE_IMPORT` reserves
and validates destination state without making it reachable; and `COMMIT`/`ABORT` are idempotent
terminal notifications. A service may omit base/delta support by reporting it in the description,
but may not omit cut preparation, import preparation, or terminal idempotence while claiming
`RECOVERABLE`.

`PREPARE_BINDING` is the builder-publication transaction of §16.1.3. A handler may refuse or issue
an expiring opaque token. Issuance reserves enough service state for a later authenticated committed
dispatch but does not make it reachable; cleanup of an unused token completes no later than its
recorded expiry.
`NONPORTABLE` services may participate, but service death or an unhealed route makes publication
fail rather than creating a partially live relationship.

The coordinator supplies `PREPARE_CUT` the canonical sorted set of included
`service_object_cookie`s and service-import anchors for that service group, plus their already-decided
cut-crossing dispositions. The
service reports whether its opaque graph has sharers outside that set; such a relationship must be
expanded by the coordinator, retained through the declared external disposition, or rejected
`-BUSY`. Per-object dumping that loses shared identity is nonconforming—the state root commits the
service's graph for the supplied set, not a bag of independent records.

The engine understands none of the exported body. A state stream records only the relationship cell,
profile version, dependency identity, generation, and coordinator-supplied state-root hash. Level
readiness may be reconstructed by the service;
edge-triggered, one-shot, exclusive, and queued readiness must be represented in the opaque state with
a generation such that an edge at the cut is delivered at exactly one side. A profile that cannot
make those statements registers `NONPORTABLE`, never a partial `RECOVERABLE` promise.
Opaque bodies crossing machines use the §16.9 state-stream AEAD channel or a profile channel
with mutually authenticated confidentiality and integrity at least as strong; the dependency root binds
their identity and contents to the cut but is not itself confidentiality.

### 16.6 The extensibility contract (so services are *used*, not worked around)

Typed hardware functions and service protocols share six architectural guarantees without sharing a
generic request encoding:

1. **Common capability semantics (not identical encoding or timing).** Hardware- and service-owned
   objects use the same capability class, rights, transfer, revocation, and condition laws. A typed
   library interface may move between a hardware function and service gate without changing its
   source contract. Under Law 3 both ultimately cross checked engine boundaries. `exec_class` is
   reported per operation or facet as `HW_BOUNDED` (bounded, non-blocking, §16.4),
   `SERVICE_MAYBLOCK` (direct service dispatch), or `ENGINE_MEDIATED_SERVICE` (bounded engine
   prefix/commit around a possibly blocking service dispatch). Real-time code admits only
   `HW_BOUNDED`; functional code may remain oblivious to the routing distinction.
2. **Control plane / data plane split (the key to no bottleneck).** Typed setup is never the pipe.
   Any operation whose result is bulk, streaming, or long-lived returns a capability or stream, and all volume
   flows over that cap at full speed (zero-copy, §10). The "escape" *is* a returned cap, which is the
   blessed path.
3. **Self-description is limited to machine/view facts.** Opcode bytes, function assignments,
   operand schemas, rights, results, ordering, and failures are frozen in this document and are
   hardcoded by software; an object never enumerates or negotiates its method catalogue. `env_open`
   describes only the caller's MachineView—geometry, topology, feature grants, timebase, and startup
   location. Collections of architectural state use typed cursors, and byte state uses typed streams;
   neither is a control-plane catalogue. `isa_spec.json` is the checked machine-readable
   transcription of the fixed ISA, not a runtime dispatcher schema.
   The named-reserved FEATURES triple is FP, vector, `ATTESTED_DOMAIN`; their catalog bit positions
   are stable MachineView facts, never an object-method negotiation surface.
4. **Forward/backward compatibility.** Reserved fixed functions grow only in later ISA revisions;
   service records remain `{version, length}`-tagged and evolve without an ISA change.
5. **Batchable where semantics are service-owned.** Service messages may ride a Memory-backed
   submission endpoint and completion stream. Hardware functions remain ordinary instructions; an
   implementation may fuse builder sequences internally under §16.1.
6. **Fine-grained, delegable rights (engine-derived, not caller-declared).** Authorization is per op on
   a per-object basis: "may call op X on this handle" is delegable without full control, riding the
   normal cap machinery (`cap.copy` with narrowed rights). Required rights are derived from the fixed
   function or service-interface schema (§16.0). Nobody needs a side
   auth protocol.

Two corollaries make services cheap to stand up: authoring a service means defining a gate/message
protocol with ordinary capability transfer, no resident-kernel edit; and domain/gate creation remains
bounded, so a servicelet is cheap. Profile semantics remain a versioned client↔service contract
(`unified_object_model.md`/`object_format.md`); typed hardware function semantics remain ISA.

### 16.7 The five views and view closure (Law 7)

**Every fact a domain can observe is a granted fact.** Not "the parent can hide things" — a blocklist
model, and blocklists rot — but allowlist-shaped: a domain's observable universe is **constructed**
entirely from five views, and there is no residual channel through which the actual machine shows
through. Capabilities bound what you can *touch*; view closure bounds what you can *know*; both are the
same discipline — a fact is a resource, knowing is a right, and rights are granted, subsetted, and
attested.

**Law 7, literal: a domain executes inside one universe** — the five views are that universe's
facets, constructed as one transactional tuple at birth; they remain independent *objects*
because their sharing differs (one ClockView legitimately serves subtrees with distinct budgets
and machine views), never because they are unrelated.
The five views are each attestable and default from the parent's effective configuration at `CREATE`;
the four discrete/configuration views subset or narrow, while ClockView uses the flattened rule below:

1. **Capability admission universe** — the transitive authority universe the parent made reachable,
   not the parent's current slots (§2.2). It is the monotone closure of authority origins/lineages and
   communication return edges delegated at birth or later: granting a child a gate/endpoint admits the
   capabilities that conforming replies on that edge may return, even when the service or sibling—not
   the parent—currently holds them. Every `cap_dup`, creation, message, gate, and service install proves
   its source lineage and transfer edge lie in that inherited closure and applies ordinary rights
   narrowing; otherwise it fails `-DENIED`. The domain's **live capability table is mutable state
   inside this universe**, not a monotone image of the parent's live table. The universe is an
   engine-derived provenance closure, not a new configurable bitmap or hidden slot list; narrowing it
   occurs only by revoking/removing the delegation or communication edges that generated it, under
   their ordinary epoch and quiescence rules.
2. **Service-import universe** — named gate, endpoint, and proxy-object capabilities explicitly
   delegated for personality policy or external services. Imports are ordinary authority and may be
   invoked only explicitly; they never replace an intrinsic instruction (§11).
3. **Budgets + reservation** — how much of everything (§16.1).
4. **MachineView** — what machine you appear to be on: topology and tile names, features, geometry,
   identity-space scope, the visible timebase (offset + `tick_quantum_shift`, §8.3), counter grants.
   `env_open` and typed collection cursors answer from it, definitionally; placement sets are indexed in **its**
   tile space. A MachineView is constructed only through an unpublished generation-threaded builder:
   `mview.new(parent_view)`, `mview.tiles(tile_set)`, `mview.features(feature_set)`,
   `mview.counters(counter_set)`, `mview.identity(identity_scope)`,
   `mview.time(time_offset, quantum_shift)`, and the independently parent-restrictable limit facts
   `mview.va_width`, `mview.atomic_agents`, `mview.gate_inline_limit`, `mview.iovec_limit`,
   `mview.sgl_limit`, `mview.workqueue_limits`, and `mview.invalidation_bound`.
   `mview.seal` atomically validates the closed non-escalating view and returns the first public
   MachineView capability; `mview.abort` consumes the builder. The identity operand is a typed
   IdentityScope facet obtained from an authorized parent MachineView, never an integer namespace
   selector. Topology-derived diameter, engine populations, grouping shape, and other dependent
   geometry are engine-derived rather than redundantly supplied. Every limit instruction is its own
   fixed schema; there is no `mview.geometry(selector, value)`. Before sealing, the prospective view
   is not enumerable, bindable, or usable by a Domain.

   ```text
   mview.new                rd_builder, parent_view
   mview.tiles              rd_builder, builder, tile_set
   mview.features           rd_builder, builder, feature_set
   mview.counters           rd_builder, builder, counter_set
   mview.identity           rd_builder, builder, identity_scope
   mview.time               rd_builder, builder, time_offset, quantum_shift
   mview.va_width           rd_builder, builder, width
   mview.atomic_agents      rd_builder, builder, limit
   mview.gate_inline_limit  rd_builder, builder, limit
   mview.iovec_limit        rd_builder, builder, limit
   mview.sgl_limit          rd_builder, builder, limit
   mview.workqueue_limits   rd_builder, builder, depth, descriptor_limit
   mview.invalidation_bound rd_builder, builder, core_ticks, ats_ticks
   mview.seal               rd_view, builder
   mview.abort              builder
   mview.get                  rd, view, selector
   mview.identity_scope     rd_scope, view
   ```

   `mview.new` requires `CREATE` on the parent view. Builder mutations require the current generation
   and may only narrow the corresponding parent fact. `mview.identity` additionally requires the
   typed scope facet; `mview.seal` revalidates parent authority and charges the new view to the
   publisher. `mview.get` selectors have fixed single-register results; collections remain cursors.

   **The tile rename is a spatial coordinate transform, not a relabeling (Law 8):** an
   affine map from the child's local grid into the parent's — a domain sees its volume as a dense grid
   from its own origin, so Law 7's "every domain is at depth zero of its own universe" is literally
   "at the origin of its own coordinate space," and the fixed point of the lattice is the machine's
   global coordinate system, which nobody inside can name. The metaphor is the mechanism. **And the
   view carries the locality metric — the one genuinely new architectural fact Law 8 demands:**
   a domain must see distance among its own tiles or it cannot place threads and the compiler cannot
   schedule, but raw distance is a position oracle; so distance is a **granted, monotone, view-local
   fact** — a hierarchical grouping over view-tiles (namespace, stated: *these tiles share a
   tile-group; these share a coherence volume; these are cross-volume* — plus abstract cost weights,
   expressed in the domain's own coordinates, preserving ordering but never absolute position).
   **Named for what it is: hierarchical distance is an ultrametric** — d(x,z) ≤ max(d(x,y), d(y,z)),
   the strong triangle inequality, because two tiles' distance is the level of their lowest shared
   group. And the ultrametric facts *are* Law 8's content, proved once instead of operationally per
   section: in an ultrametric space balls are nested or disjoint (never partially overlapping —
   that is the spatial containment tree), every point of a ball is its center (that is "every
   domain is at depth zero of its own universe," said metrically), and a ball's boundary is one
   line however you approach it (that is the four-meanings coincidence — trust, coherence, naming,
   and distance land on the same line because there is only one line an ultrametric can draw). The
   NUMA distance table, made a view and closed under Law 7; read through `env_open` `TOPOLOGY` (already
   view-answered — no new op), restriction-induced through the MachineViewBuilder like every other
   view fact, and the missing input `dplace`, the allocator (§11.2 `home_hint`), and
   `backing.rehome` (§16.3) were blind
   without.
5. **ClockView** — what time it is (§8.1).

**All five descend under parent authorization** — discrete views are subset-images of the parent's;
budgets and `self_rights` narrow; a ClockView is a parent-authorized flattened transform constrained by
the fixed Q32/range/continuity rules below, not a numeric subset or recursive transform. All five are
covered by the `ATTESTED_DOMAIN` measurement (§16.1).

**Spatial transforms compose; ClockViews flatten.** A MachineView's tile rename is an affine map acting
on the parent's grid, and those exact integer coordinate maps compose down the tree with sealed
builder restriction as
restriction. A ClockView deliberately is **not** another recursive monoid action: bounded Q32 slopes
are not closed under multiplication, and nested floor operations are not representable by one
identically rounded Q32 map. Each child therefore receives one independent flattened
`{anchor_tick, anchor_view, s}` transform directly against the physical timebase of its immutable
constructed volume. At `CREATE` the default is a continuity-preserving copy/re-anchor of the parent's
current effective transform; an explicit ClockView grant supplies another already-flattened transform.
The parent checks only the architected Q32 slew bound, horizon overflow, authority, and the §8.3 thaw
continuity rule—there is no hidden multiplication by the parent's slope and no promise to reproduce a
hypothetical `floor(a × floor(b × t))`. Thus representation and evaluation cost remain constant with
tree depth without claiming false closure. MachineView coordinate closure, the translation-depth
invariant (§15), and Law 7's depth-zero rule remain exact.

**Flattening also severs ancestry.** Derivation performs its subset/authority and numeric checks once,
at mint, and materializes a new ClockView object with its own transform and epoch cell. It retains no
live dependency on the source ClockView: a later `SET`, `ADJUST`, destruction, or other change to the
source neither changes nor bumps the derived object, and requires no descendant walk or propagation
acknowledgement. Domains that must observe the same later corrections bind to the **same ClockView
object**; they do not bind independently derived views and rely on ancestry.

**The discrete dimensions carry the matching theorem — delegation is confluent.** Rights
narrowing is a meet-semilattice action: `cap_dup` is AND with a mask, `SET_SELF_RIGHTS` is AND,
`SUBSET` is set intersection, budget carving is min — every dimension's "monotone rule" is a meet.
Meets commute and associate, therefore **the authority reachable at the end of any delegation path
is independent of the order of the narrowings along it**: what a domain can possibly hold has a
path-independent answer, computable as one meet over the delegation DAG, never a path enumeration.
This is the theorem a security auditor actually wants — "could this domain ever reach X" closes
under one associative fold — and it is *why* audit tooling over capability lineage can be sound
without replaying history. (Appendix D carries the test family: permute narrowing orders, the
reachable set must not move.)

> **A domain's universe is constructed under five parent-authorized, non-escalating views. Discrete
> views narrow; ClockView transforms flatten under their authorization envelope. There are no other
> facts.**

The physical machine is the **fixed point of the view lattice** — reached only by identity views,
descending from the unaddressable reset grant (§11), never nameable from inside the tree. On this
machine "am I virtualized?" is not merely unanswerable but meaningless: *virtual machine* is not an
architectural category, and **every domain is at depth zero of its own universe**.

Where the machine already complied (capability discipline did the work): **depth** — nothing reports
it, no ancestry field exists, and the translation-depth invariant (§15) keeps it out of address-path
latency; **devices** — no caps, no device; no bus to scan, no port space to probe; **memory size** —
you see your budget, a granted number, and with pager backing (§15) even that may exceed physical
truth. What the views close: the `env_open`/topology ambient channel (view 4 replaces it), timebase and
counter visibility (§8.3), placement coordinates (view-tile rename), and **names crossing the
boundary** — the composition rule the engine enforces at every transfer: *a capability or message
entering a domain carries no fact outside that domain's view.* Handles are re-keyed (§2.2), tile names
are renamed, and — pinned as an invariant on every §17 layout — **engine-written records contain only
domain-local names, ever**: no physical address, no global counter, no foreign ID in any getter or event record,
completion record, or error path. Every architectural identifier a domain observes is subtree-scoped or
opaque (§1, §8.2).

**Honesty clause (execution physics).** No view hides physics: a domain granted 8 view-tiles running on
2 physical tiles under a fair-share reservation can measure that only 2 threads make wall-clock
progress simultaneously; a sibling-thread counter is a fine clock (§8.3); cache and memory latency
remain measurable. View closure governs **architected facts** — what the machine *tells* you — not
side-channel inference; the noninterference track governs the rest. The claim is precise, and precisely
scoped.

### 16.8 Composable state capture, restore, and live succession

Checkpoint, restore, live migration, debugger snapshots, replication, and hot upgrade are software
protocols over the general algebras of §16.5. The architecture does not recognize a migration
lifecycle and defines no `dmigrate.*`, `dfreeze`, `dthaw`, domain-specific export, or domain-specific
import instruction. It directly provides only the reusable facts those protocols require:

- a scoped safe state, named by a quiescence token;
- changes since an observation generation;
- stable enumeration and typed architectural state streams;
- unpublished construction and all-or-nothing publication;
- object drain, cancellation, and explicit dependency rebinding; and
- exactly-once succession of an authority, identity, lease, or ownership edge.

A state-capture program first obtains the scopes it needs with `quiesce`. A full domain image requires
`FULL_SUBJECT`: no activation executes or enters, memory and capability mutation are held, new object
submissions are rejected, prior architectural effects are ordered before quiescence completion, and
included objects have reached their class-defined safe points. Narrower debugger, collector, policy,
and incremental-persistence operations use narrower scopes. Quiescence is a hold, not a checkpoint-only
domain state; `resume` consumes its token.

`state.open(stream, object, mode, generation)` emits a typed, canonical representation of the
object's architectural state. For a domain it may include the domain, a named subtree, or a named
relation selected by the fixed domain-state schema. A full closed domain state contains, as applicable:

- effective mappings and backing relations;
- capability slots, lineage/stamp-cell graph, transfer classes, and explicit service imports;
- suspended activations, register state, continuations, calls, waits, and restart records;
- MachineView, ClockView, placement, budgets, accounting, scheduling, and policy;
- timers, completions, queues, bindings to hardware-owned objects, and serializable object state;
- exact crossing dependencies and their required disposition; and
- the observation generation, quiescence token identity, and temporal cut needed to validate the image.

`state.open(domain, METADATA, 0)` is also the migration-planning query. Alongside the dependency
inventory it enumerates every live synchronous activity crossing the requested Domain or subtree
boundary as a §17.9 `CUT_ACTIVITY_METADATA` record. Each record reports the conservative remaining
donation and cleanup-grace bounds and the cancellation policy. This is inspection output, not an
importable continuation: it lets an orchestrator bound a clean drain before stopping the workload,
while `FULL` capture still fails `-BUSY` until every such edge has returned or been cancelled. A call
with no finite contractual donation bound reports `UINT64_MAX`; the query never invents one.

The stream describes effective architectural relations, never engine records, VMA trees, capability
tables, continuation-frame layouts, dirty-bit structures, serializer internals, or parent-chain caches.
Its class fixes its schema; its mode does not turn the instruction into a generic decoded envelope.
Implementations may produce the stream in hardware, microcode, firmware, protected software below the
architectural boundary, or a mixture, provided authority, bounds, ordering, accounting, and the
canonical result are preserved.

Restore is ordinary unpublished construction. `state.import` creates a typed import builder beneath
the receiving parent; `write` supplies bytes; explicit imports and replacements satisfy every
external dependency; and `state.commit` performs closed validation and publishes atomically.
Domain import builders obey the same non-observation, accounting, generation, retry, abort, and
publication laws as `dnew` builders. A failed validation publishes nothing, consumes no staged move,
and retains no partial object. An imported dormant domain is started or resumed only after all
dependencies and any succession edge are committed.

**Stable identity and round trip.** Every architected integer that software can copy into arbitrary
memory preserves its exact value and meaning: capability handles, domain/thread identifiers, waitset
member identifiers, activity references, lease identifiers, and visible generations. Import may
re-mint engine-private cells and routing identities, but it restores the visible check values and the
lineage/stamp graph so a reference is live or stale after import exactly when it was live or stale at
the captured cut. Inability to reserve a required visible value fails import atomically with
`-BUSY`; silent renumbering is forbidden. The governing law is:

```text
state.commit(state.import(state.open(D, FULL))) ≈ D
```

where `≈` is observational equivalence through the five views, modulo only explicitly supplied
external replacements and a committed succession edge. Appendix D tests the law with view-restricted
observer programs.

**Observation generations and incremental copy.** `observe.mark` may cover dirty memory, mappings,
capabilities, activations, objects, and service imports. `changes.begin` returns a stable cursor for
one class since that mark. A reported superset is permitted where a class declares conservative
tracking; omission of an affecting change is not. Multiple marks and delta streams may be taken while
the domain runs. A final quiescence closes mutation, after which the final cursors and state streams
form one stable cut. This facility is equally the dirty-generation substrate for generational
collectors, incremental persistence, replication, undo, debugging, and deterministic replay.

**Activation state.** A suspended activation capability already identifies architecturally stable
register and continuation state for `dyield`, `dresume`, scheduling, debugger stops, preemption, and
container suspension. State streams accept that object like any other serializable object. No
activation-export or migration-capture opcode exists. Import reconstructs activations privately and
makes none runnable before the containing domain's publication and any required succession commit.

**External-resource contracts.** Every object class declares exactly one state-transfer behavior:

- `VALUE_SERIALIZABLE`: its complete architectural state can be streamed and recreated;
- `BACKING_RELATIVE`: state is recreated from an imported backing plus architectural metadata;
- `REBIND_REQUIRED`: the stream names a dependency that restore must replace explicitly;
- `DRAIN_REQUIRED`: accepted work must complete, cancel, or become restart records before capture;
- `PROXYABLE`: an explicit source-side proxy may remain and the destination receives its capability;
- `NONMIGRATABLE`: a full moving capture fails unless the object is dropped from the cut.

**The serialization admission rule (what keeps this burden bounded instead of accreting).**
Freezing the state stream makes serializability a *permanent* obligation, so the obligation is
made a gate, not a hope: **no object class, sub-operation, or semantic feature lands in any
revision without declaring, at introduction, its complete serialization answer** — its
transfer-contract class (the six below), its section/record schema and version, the
required-versus-optional classification of every piece of its state (derived state is
`OPTIONAL` or absent, §17.9), its external-dependency enumeration, its partial-activity
disposition (the restart or drain recipe every activity class already owes, §9.3/§10.2), and
its destination-compatibility predicate (what import rechecks). **The catalog carries the registry —
all six answers, per class, machine-checked**: the consistency gate rejects a class whose record
omits any answer, disagrees with its declared transfer contract, cites an unknown stream section,
or claims stream sections while declaring `NONMIGRATABLE`. And **a proposal
that cannot answer all of these is not incompletely specified — it is inadmissible**, the same
rule as a mechanism that cannot name its law. This is why "every class needs durable answers"
is a checklist paid once at admission, never a debt discovered at restore time.

The v1 class declarations are: Domain, Thread/activation, Counter, Timer, CompletionQueue, ClockView,
MachineView, Device, and Capability are `VALUE_SERIALIZABLE`; a Device stream preserves its profile,
scalars, stored rights, and capability members as typed `REBIND_REQUIRED` dependencies so each
replacement retains its original capability lineage; a Capability stream preserves the capability
graph while each referenced object is classified separately. Memory, PagedBacking, and EventRing are
`BACKING_RELATIVE`; an EventRing is reconstructed from its imported registered backing and its
serialized `{thread, waitset}` binding, whose referents are classified separately. Waitset and
CallGate are `VALUE_SERIALIZABLE` with every referenced member/gate dependency classified separately;
ChannelEndpoint and FileDescription are `REBIND_REQUIRED` unless their explicit service profile
declares `PROXYABLE`; InterruptWaitable and InterruptSource are `REBIND_REQUIRED`; DMAWindow and WorkQueue are
`DRAIN_REQUIRED` and restore from dormant recipes plus fresh device authority; PMU and DebugTarget are
`NONMIGRATABLE`. A later revision may add a class but may not silently change an existing class's
declaration.

Every imported recipe remains a state-import builder. `state.bind` supplies each typed dependency
requirement (fresh Device, CompletionQueue, InterruptSource, endpoint, or other declared
class), and `state.commit` is the only publication operation. Applying `window.*`, `workqueue.*`, or
another class-builder mutation to it is `-BADREF`. Each class has one publication predicate shared
by its ordinary `*.seal` and import commit; a required dependency bound twice or left unbound is
`-MALFORMED`, and commit failure publishes nothing.

These contracts apply to checkpoint, cloning, hot upgrade, device reset, and service handoff; they are
not migration modes. Crossing capabilities, shared backings, wait relationships, outstanding DMA, and
external service imports are enumerated explicitly. Silence never invalidates an edge. A raw external
gate or endpoint is `REBIND_REQUIRED` or `PROXYABLE`; service-owned bodies remain service protocol
and never enter silicon's state schema. Device authority may be rebound, but a physical device
incarnation is never resurrected. A `DRAIN_REQUIRED` queue uses `queue.drain` and its outstanding
activities use `activity.cancel`
contract before its dormant recipe is captured.

**Service participation remains explicit software protocol.** A recoverable service import may expose
versioned gates for description, base/delta export, cut preparation, import preparation, commit, and
abort. A coordinator invokes those gates explicitly. The engine neither discovers service semantics by
intercepting native instructions nor calls a service because an intrinsic instruction executed.
State streams enumerate the anchored import and dependency identifier; software carries opaque service
state and coordinates distributed cuts. A nonportable service dependency makes a requested closed
moving capture fail `-BUSY` unless policy explicitly drops it.

**Time at a cut.** One full-domain cut samples all finite deadlines, timers, replenishment comparators,
and cancellation grace periods against one source ClockView instant. The canonical state schema stores
remaining durations in its wire unit plus the ClockView facts required to re-absolutize them.
A suspended-time image resumes those remaining durations unchanged. A transparent live succession
subtracts elapsed source time authenticated by the software protocol's source acceptance and final
cell-repoint token; an exhausted duration is pending before the successor may run. No running instruction
converts time units, and no generic migration session is architectural.

**A live-migration composition.** A conforming runtime may implement pre-copy as:

```text
g0 = observe.mark(domain, MEMORY | CAPS | OBJECTS | ACTIVATIONS)
qn = quiesce(domain, NEW_ENTRY)          # reject/queue new cross-cut synchronous entries
state.open(domain, METADATA, 0)          # inventory live cut edges and their bounds
copy initial backing contents and immutable metadata

repeat:
    changes.begin(domain, g0, each selected class)
    state.open(domain, SINCE_GENERATION, g0)
    copy deltas
    g0 = observe.mark(domain, selected classes)
until the remaining delta is suitably small

q = quiesce(domain, FULL_SUBJECT)
copy final changes since g0
cancel bounded stragglers; drain or classify external objects
build and validate unpublished destination state
h = cell.repoint.prepare(identity_cell, source, destination)
cell.repoint.commit(h)
resume(destination_quiescence_token)
retire or retain the inert source according to policy
```

The ordering shown is a protocol obligation, not an instruction macro. Failure before
`cell.repoint.commit` leaves the source authoritative and resumable and the destination unpublished or
inert. Successful commit makes the successor authoritative exactly once and prevents source
resumption under that edge. **The commit's hardware atomicity is scoped to the identity cell's
home volume (§11.3):** everything distributed about a cross-volume or cross-machine succession —
source acceptance, destination readiness, lease expiry, failure detection — is this software
protocol's job, honestly priced as protocol rounds; the instruction contributes one bounded
per-cell transition, never a machine-spanning consensus. Post-copy is the same composition with imported pager-backed backings and
explicit `PROXYABLE` dependencies; loss of a required source page resolves through the ordinary
poison-memory incident path, never zero-fill or an indefinite hidden wait.

`NEW_ENTRY` is intentionally acquired before iterative copy rather than at the final blackout. New
cross-cut synchronous calls then refuse or queue according to their service contract while calls
already in flight drain concurrently with dirty-page copying. The final `FULL_SUBJECT` stop therefore
normally finds no crossing edge; cancellation prices only stragglers. The early hold is retained
through cutover and consumed on abort or source retirement by the coordinator's rollback path.

Services that require RPC to survive migration use the decoupled path: `gate.submit`, a
CompletionQueue, stable ActivityRefs, and an idempotent restart/continuity contract. Pending async
work is object-owned state and follows its declared class recipe. A synchronous gate call deliberately
trades that mobility for donation, borrowed memory, and warm round-trip latency, so the architecture
refuses to serialize a residual synchronous continuation. Cross-machine takeover and re-issue belong
to the service continuity profile, where their failure semantics can be stated honestly.

**Large-state and cost doctrine.** Domain streams carry metadata and architectural engine truth, not
bulk backing contents. Contents use backing clone, persist, supply, or pager protocols independently
and in parallel. Costs are bounded by facts the program names: included mappings, capability slots,
activations, objects, crossing dependencies, change records, and locality span. No dedicated migration
engine, fixed internal snapshot representation, one-allocation-per-record rule, or ancestry walk is
required. An implementation may independently recognize and accelerate the complete software
composition.

**Protection and compatibility.** State streams use the §16.9 owner-sovereign authenticated channel:
protection is against the wire, never against the machine owner. Measured objects bind their birth
measurement and replay protection into the stream. Import rechecks destination feature/view
compatibility, vector geometry, admission, W^X, backing and pin promises, clock constraints,
placement constraints (re-solved against the destination's memory-tier table — the stream
carries required constraints, never source tier ordinals, §15), and every
object-class transfer contract. The wire framing remains versioned and canonical, but the workflow is
not an ISA object.

**Cross-revision compatibility (the decades rule).** Revisions are totally ordered (§1), and the
stream is built to cross them in both directions honestly:
- **Backward import is unconditional.** v*n* contains v*n−1*, so an importer accepts every
  section version its own schemas contain — an early stream restores on a late machine with no
  translation layer, because the stream already carries **logical constraints, never
  implementation choices**: effective relations rather than engine records, duration-form
  deadlines, required placement constraints rather than tier ordinals (§15), and renamed
  engine-private identities.
- **Forward export is targeted.** The §17.9 header's `target_revision` names the ISA revision
  whose schemas bound every emitted section version (`0` = the producer's own). Asked to emit
  for an older target, the producer uses only that revision's schemas, and state inexpressible
  there — an object class, a fact, a constraint dimension the target lacks — fails `state.open`
  **`-UNSUPPORTED` before any bytes are produced**, enumerable in advance by software exactly
  the way `NONMIGRATABLE` dependencies are: drop it, rebind it, or keep the newer machine.
- **Required versus optional is a wire fact** (§17.9): the frozen types and every flag-clear
  future type are REQUIRED — unknown fails import atomically; the `OPTIONAL` flag admits only
  reconstructible derived or acceleration state, so skipping one changes warm-up, never
  semantics.
- **Caches and derived state are reconstructed, never migrated** — the engine-record renaming
  rule generalized: anything a destination can derive from required truth may not be REQUIRED,
  which is what keeps the stream O(truth) as implementations grow ever larger derived state.

The opcode-admission consequence is deliberate: removing checkpoint and live migration from the
requirements would still leave every primitive above justified by ordinary concurrency, debugging,
memory management, lifecycle control, persistence, replication, or reconfiguration.
### 16.9 Reserved architecture boundary

Opcode `0xaf` is reserved. External trust and protected-transport protocols have no architectural
instruction, object, suite catalog, or wire ABI; software or an explicitly imported service owns them.

## 17. Binary layouts (every structure the chip decodes)

A software/compiler/emulator implementer must be able to build from this document alone. Everything the
**chip itself decodes** is frozen here. The companion layers a toolchain also needs but the chip does
**not** parse are explicitly *not* ISA: the **ELF/object format and relocations** (`object_format.md`,
consumed by the loader) and the **service-profile field semantics** (§16.5). The chip-decoded
extensible record is `env_open` (the **16-byte**
`{record_type u32, version u32, length u64}` header, §17.6), transcribed in `isa_spec.json`.
State streams have class-fixed schemas and transport state only. All layouts are little-endian;
offsets are byte offsets.

**The freeze criterion:** a software convention is **ISA-frozen exactly when a hardware engine
produces, consumes, or enforces it**; everything else lives in the psABI and stays revisable;
and **a psABI fact later promoted to hardware consumption is thereby promoted to §17 discipline
in the same revision**, never grandfathered. **The standing refusal list (no hardware party —
never frozen here):** local-call stack-frame layout and varargs, the unwind/CFI format, the
futex lock word (B20), the frame-pointer role (§2), the red-zone size, and symbol/name-mangling
conventions. A proposal to freeze one of them must first name its hardware producer or consumer.

**The domain-local-names invariant (Law 7, §16.7 — binding on every layout in this section):**
engine-written records contain **only domain-local names, ever** — member IDs are waitset-local,
submission handles are queue-local, tile numbers are view-tile numbers, and no record carries a physical
address, machine-global counter, or foreign identifier. Cheap to honor now; miserable to retrofit.

### 17.1 Message descriptor (`send`/`recv`), 32 B
`[0]` bytes_ptr u64, `[8]` bytes_len u64 (in; **in/out** for `recv` = capacity in / actual out), `[16]`
caps_ptr u64, `[24]` caps_len u64 (in/out). (Restated from §10.2.) `recv`'s in/out dual use is sound
because `recv` is unidirectional. **Per-cap lifetime class on the wire (frozen):** a caps-array element
is a `u64` whose **bit 63 carries the `DROP_ON_STATE_REPLACEMENT` lifetime-class bit on transfer paths
only** (free in-band: a live handle's bit 63 is architecturally zero, §2.2); the engine consumes the bit
at install and the installed handle has bit 63 clear. Transfer itself is copy; ownership movement is
the separately committed `cap.move` operation. Future lifetime classes ride an additive message
revision, never a reinterpretation of this bit. **Transferred caps are class-checked at use,
never at transfer** — the engine validates rights-to-transfer, not fitness-for-purpose, so a
wrong-class handle in a caps array (a Timer where the protocol expects a ChannelEndpoint)
transfers successfully and surfaces as `-BADREF` at the *receiver's* first presentation,
arbitrarily later and in a different domain. Type confusion is caught per-*use*, not per-*flow*;
protocol-level type agreement is the service contract's job, and the Appendix D condition-boundary
family generates the wrong-class-in-cap-list case explicitly.

### 17.1b Gate descriptor (`gate_call`/`gate_return`), 48 B
The gate is **bidirectional**, which is exactly why it cannot reuse the 32 B `recv`-style dual-use
layout (one field cannot be both "outbound length" and "reply capacity" at once): it gets **separate
outbound lengths and reply capacities**. `[0]` bytes_ptr u64 (outbound inline-payload source, **and**
the reply-bytes destination), `[8]` bytes_len u64 (**in**: outbound length; **out**: actual reply length
— distinct *times*, call vs return, so no dual meaning at any instant), `[16]` caps_ptr u64 (outbound
cap array, **and** the reply-handle destination; elements carry the wire lifetime-class bit 63 as in
§17.1), `[24]` caps_len u64 (in: outbound count; out: actual reply count), `[32]` reply_bytes_cap u32,
`[36]` reply_caps_cap u32 (the reply capacities, separate fields), `[40]` **borrow_ptr u64** (`0` = no
borrow; else a pointer to the 48 B two-window call-scoped borrow descriptor, §17.1c, snapshotted with the same
single-snapshot discipline). **The descriptor page is pinned at `gate_call` for the duration of the
call** (the same pin discipline as the `recv` writeback §10.2 — the gate holds the
window open far longer than a `recv`, and a return writeback must never fault; the pin charges the
caller's budget, §16.4). Checks, all **pre-activation** (a return, unlike `recv`, has no
leave-queued-and-retry, so it must never be strandable): outbound
`bytes_len <= min(GATE_INLINE_MAX, inline_area_len)` and outbound `caps_len <= max_cap_transfer` (else
`-MSGSIZE`); `reply_bytes_cap >= inline_area_len` and `reply_caps_cap >= max_cap_transfer` (else
`-MALFORMED`) — so by construction every reply fits and the return-side overflow case does not exist.
At successful call commit the engine additionally **reserves `max_cap_transfer` actual free slots in
the caller's capability table**, charges that reservation to the caller's cap-slot budget, and records
the slot set in the engine frame. Reserved slots are unavailable to every other thread/operation until
this activation returns or tears down; returned caps install directly into them, and unused slots plus
their charges are released atomically on successful return or teardown. The descriptor/reply-buffer pin
and inline-reply storage are likewise held, not merely checked. Failure to acquire any reservation is a
pre-activation `-NOSPACE` with no transfer or callee effect. Consequently a concurrent caller thread
cannot consume return capacity, and capacity exhaustion is never a stay-put `gate_return` failure.
The callee's `gate_return` uses the same layout with only the outbound fields meaningful; a reply
exceeding the gate's bounds fails **`-MSGSIZE` stay-put to the callee** (a failed, non-transferring
return, §9.2). A machine-call return uses **no descriptor at all** (descriptor register `0`, §9.3).

**The null-descriptor fast form (`gatedesc` = `0`, the §2.2 sentinel — the register-only RPC):** no
inline payload, no cap transfer, no borrow, no reply buffer; arguments and results ride the gate's
callee ABI in **registers alone**, and `gate_return`'s status is the only writeback. **Nothing is
pinned, no descriptor is validated or snapshotted, and no §16.4 pin-accounting touch occurs** — the
zero-payload call, which is the majority of control-plane RPCs, pays for exactly nothing it does not
use, mirroring the machine-call return's descriptor-register-`0` form (one convention, both
directions). A callee that attempts to return bytes or caps to a null-descriptor caller fails
`-MSGSIZE` stay-put, like any reply that exceeds its caller's capacity (here: zero).

### 17.1c Call-scoped borrow descriptor (`gate_call`), 48 B (two windows)

**Not a third lending mechanism — the third *lifetime* of the one lending concept.** The
machine lends memory at exactly three lifetimes, each stored where its lifetime is enforced: a
capability in a message lends for the **message's** lifetime (§10.2), a `mem_grant` for a
**table entry's** (§11.2), a borrow for an **activation frame's** (the frame *is* the
revocation). **The completeness claim, falsifiable:** a future lending proposal either reduces
to one of these three lifetimes or names a fourth — and a fourth lifetime requires a fourth
engine-held structure with a name-bearing lifetime, which is a new object class, not a new
lending option. A proposal that cannot say which structure holds its loan is proposing the
fourth, and is refused.

**Two window slots — because the dominant sandbox signature is `f(const in, out)`** (decoders,
decompressors, parsers, shapers: one read-only input, one writable output), and forcing it
through a single window meant either a packed RW arena (surrendering input integrity) or a
`mem_grant` (a table slot for a call-scoped loan). Two is the **closed count**: in + out *is*
the signature, a third range has no recorded mass consumer, and anything wider rides the arena
idiom or a grant. Layout, window 0 then window 1:
`[0]` base0 u64, `[8]` len0 u64, `[16]` rights0 u64, `[24]` base1 u64, `[32]` len1 u64,
`[40]` rights1 u64. Per window: `base+len` overflow-checked (§1); rights bit 0 = `READ`,
bit 1 = `WRITE`, all other bits reserved-zero — execute is never grantable through a borrow
(lending is for data, and W^X stays architectural §11.2). An all-zero window 1 means one-window;
a populated window 1 over an all-zero window 0, or `len` = 0 with a non-zero base, is
`-MALFORMED` (canonical packing, no sparse forms). The two windows may not overlap
(`-MALFORMED`) — one range, one rights answer.

**Semantics — a transient window, not a capability.** At `gate_call`, after the descriptor snapshot and
strictly **pre-activation** (any failure returns with no callee effect and no frame pushed), the engine
validates: **(i)** the calling domain actually holds `[base,base+len)` mapped with at least `rights`
(else `-DENIED`/`-FAULT`) and snapshots the covering VMA epochs. If caller and callee share the same
address-space object, the relation is an ordinary permission overlay. Otherwise it is an
accessor-only remote-range relation usable solely through `acopy.*`; no caller translation is
installed in the callee address space and ordinary loads/stores remain governed by the callee's own
mappings. **(ii)** the range and rights are canonical as above. **There is deliberately no per-gate opt-in**: a caller
delegating a slice of *its own* authority is the capability model itself, and the borrow is strictly
milder than the cap-list transfer `gate_call` already permits — a transferred cap mutates the callee's
table, while a borrow window mutates **nothing the callee can observe**. The engine then installs the
window: for the duration of **this activation only**, same-AS accesses to the range issued by **the migrated
thread itself** — its loads/stores, and the buffer arguments of engine ops it issues — are additionally
permitted under `rights`; cross-AS access is checked and copied only by `acopy.*`. Other
threads of the callee domain never see it — it rides the thread's activation. The window is **not a
capability**: no handle, no table entry, no lineage; it cannot be duplicated, granted onward, sealed,
transferred, or named by `cap_revoke`. It cannot be **re-lent**: any nested frame — a nested `gate_call`
or a machine call (§9.3) delivered on top — **suspends** the window set until its matching return (the
engine saves the inbound set in the engine frame §17.5 and restores it on return), so **at most one
activation's declared window set — at most two windows — is live per thread at any instant**
(two range-compares, a constant, never a search, at any depth).

**Lifetime — dies when the activation ends, fail-closed.** The window remains installed across a
failed-stay-put `gate_return`, because that return does not pop the frame and the callee must retain the
same authority environment in which to repair and retry. It is torn down atomically only when a
`gate_return` successfully transfers control, or when §9.4 cancellation, forced termination, or domain
teardown ends the activation. **Unlike the descriptor page, the borrowed range is *not* pinned**: the borrow is a permission
overlay over the caller's live mappings and shares their fate — an epoch bump (`map.protect`/
`munmap_range`/`cap_revoke`) whose invalidation covers any part of the range kills the overlay with the
translation, and a subsequent callee access faults per §9.1 (the same staleness rule as any epoch-checked
translation, §3). Engine ops the activation issued honor the window, and the §11.1 asynchronous-issue
license cannot race the teardown: `gate_return` is itself an engine op, so program order means every
earlier engine op has taken effect before it executes. Any implementation structure caching the borrow
decision obeys the universal rule: the invalidation broadcast reaches it before any dependent access
commits.

**Relationship to `mem_grant`.** `mem_grant` remains the general mechanism — revocable by name,
transferable, able to outlive the call. The borrow is the activation-lifetime form for the dominant
one-buffer call; its distinction is lifetime and authority, not admission to a faster semantic path.
Rule of thumb: needed only until the return → borrow; must outlive the return → grant.

**The borrow-checker mapping, with its enforcement boundary stated:** mechanically, the window
is an **activation-scoped access grant**. Hardware enforces exactly the *callee* half of
`&mut [u8]` — the grant reaches one activation of one thread, cannot be re-lent, and dies with
the call, fail-closed; caller-side exclusivity remains the compiler's proof, as on every
machine Rust has shipped on. For borrow-checked code the window completes
`&mut`-across-a-trust-boundary; for code the checker does not govern (C callers, unsafe
aliasing) it is an access grant and claims nothing more. The lifetime annotation and the
hardware lifetime are the same object: a lent buffer whose lifetime provably ends at the
return lowers to the borrow window; one that outlives the call lowers to `mem_grant` — the
elision decision selects the primitive (an overlay in a shared address space, accessor-only
`acopy.*` across address spaces). **The asynchronous form (§9.2 `SUBMIT`) cannot carry
a borrow** — the submitter keeps running, so a window over its memory would be a
hardware-blessed aliased `&mut`; an async callee takes a `mem_grant` or a transferred cap
(Rust's own `'static`-or-owned-across-a-spawn rule, arrived at from silicon).

### 17.2 I/O vector element (`readv`/`writev`/`readv_at`/`writev_at`), 16 B
The instruction names `iov_ptr` and `iov_count` in registers. `iov_ptr` designates an array whose
homogeneous element is `[0] base u64, [8] len u64`. The complete bounded array is snapshotted and
validated before transfer. It contains no operation-wide offset, mode, flag, selector, version,
policy, or output configuration. Cursor selection is encoded by the mnemonic; positioned forms name
their offset in a register.

### 17.3 EventRing entry, 24 B
`[0]` **member ID** u64 (waitset-local, assigned at `ADD_MEMBER` — never a capability handle, §2.2, and
never a global counter, §16.7; permanently retired by `DEL_MEMBER`, §8.2), `[8]` user cookie u64,
`[16]` ready mask u64 (`READABLE`=1, `WRITABLE`=2,
`ERROR`=4, `HANGUP`=8, `PRIORITY`=16, `TIMER`=32, `COMPLETION`=64, `INTERRUPT`=128; bits `[63:8]`
reserved). An EventRing contains `capacity` such entries (§10.3).

### 17.4 Typed-family subformats

The family encoding is defined in §16.0: fixed function bits plus fixed GPR operands. There is
deliberately no control-envelope byte layout. Hardware-parsed memory structures in this section are
classified by exactly one closed memory-operand role:

| Role | Permitted meaning |
|---|---|
| `TRANSFER_DATA` | bytes or invocation payload transferred by the named operation |
| `HOMOGENEOUS_SEQUENCE` | a sequence bounded by its named element-count limit whose elements all have one frozen schema |
| `ARCH_CONTEXT` | architecturally defined suspended/interrupted execution state |
| `EVENT_RECORD_DESTINATION` | storage for one fixed hardware-produced event/completion record |
| `STATE_STREAM_BUFFER` | bytes read from or written to a typed architectural state/description stream |
| `WORK_DESCRIPTOR` | one frozen work-item schema submitted to an explicitly typed hardware command facet |

`isa_spec.json` assigns the role to every chip-decoded pointer-bearing structure and the consistency
gate rejects any other role. In particular, `ARGBLOCK`, `REQUEST`, `CONTROL_BODY`,
`OPERATION_RECORD`, and `QUERY_OUTPUT` are forbidden concepts. A `WORK_DESCRIPTOR` may contain an
operation selector only under an explicit catalog exception naming its command-processor target;
v1 has no such exception because DMA transformations use typed facets.

A future operation that needs a generic class/op/version/length/cap-array header is not an additive
use of this slot; it is an architectural proposal to reverse §16 and must not decode on a conforming
revision.

**Structural role rules.** A `HOMOGENEOUS_SEQUENCE` instruction supplies pointer and count in
registers; every repeated element has one frozen data schema, and no element or sequence header
carries an operation-wide offset, mode, flags, selector, version, policy, or output configuration.
An engine-consumed input stream is legal only for imported architectural state, ordinary byte
payload, or class-specific bytes whose interpretation is itself the transferred data. A stream may
not supply operation flags, selectors, capability arguments, optional commands, control parameters,
or negotiation lists. Optional semantic facts use a typed builder operation, a first-class typed
value, or a separately named instruction variant—never presence bits, generic flags, optional
record tails, or request-stream sections.

### 17.5 Continuation-stack frames (the architectural context)

The protected continuation stack holds the **one frame kind** (§9). This is the structure a handler,
`getcontext`/`setcontext`, an unwinder, a debugger (`READ_CONTEXT`), a corpse, and `gate_return` all
read.

Each activation is **two distinct objects**, so the §9 split is a real ABI, not "some words in one
struct are private": an **engine frame** (opaque, never domain-addressable) and — for machine calls — an
**argument payload** (ordinary domain memory addressable from offset 0). `gate_return` finds the current
activation through an **engine-held current-frame token** (per thread, in engine state), never by
reading a pointer from writable bytes, so a domain cannot forge which frame it returns to. **The §9.2
return sentinel does not weaken this: it is what a handler *fetches* to trigger the return, never
where the return goes** — the target is always this token, so forging `ra` cannot redirect a
crossing. This is what
makes "editable payload, unforgeable control" implementable with ordinary page permissions: two objects,
one of which the domain simply cannot address. **The payload base is 16-byte aligned** —
registration validates it (`-MALFORMED` otherwise) and every delivery preserves it (the §9.2
universal entry alignment), so `ld.q`/vector spill sequences address the payload with no
dynamic realignment.

**Engine frame (opaque, engine-private).** Pushed by every gate crossing; **no architected byte
offsets** are exposed and a domain has no mapping to it. It holds the trusted control metadata: the
**caller linkage** (which domain's gate call, or the machine — §9's one frame kind still knows who
called; what is gone is any *domain-visible, domain-editable* type field), `link` (previous frame), the
gate linkage handle, return-cap bookkeeping, `call_rd`, `call_chain_id`, `donated_reservation`,
`deadline`, the **saved inbound borrow-window set** (§17.1c, at most two), and — for domain calls — the saved
**callee-saved register set** `s0`–`s9`, `sp`, `tp`, **and the caller's `resume_pc`**. **Where
`resume_pc` lives follows the §9 editing rule, one place each:** for a **domain call** it lives *only*
here, engine-private — the callee is not the caller and must not redirect it; for a **machine call** the
engine frame holds **no** `resume_pc` at all — the **payload's `resume_pc` at `[8]` is the single
authoritative copy**, deliberately handler-editable, because fault-repair/skip/emulation *is* editing
the resume point of your own interrupted context (the handler and the interrupted context are the same
domain and thread; editing your argument is editing yourself). `gate_return` restores the callee-saved
set from the engine frame and writes the reply to the saved `call_rd`. A domain-call activation is
**~160 B (no FP) / ~264 B (FP)** of engine state — much smaller than a full-context save. Being
engine-private, its layout is an implementation detail; nothing decodes it from memory (its
**serialized** form is the §17.9 canonical export, emitted and consumed only by the engine).

**Argument payload (domain memory, addressable from offset 0)** — pushed **only for machine calls**
(§9.3: fault, event, cancellation); this is the architectural context record a handler,
`getcontext`/`setcontext`, an unwinder, and a debugger read and **edit with normal `ld`/`sd`**. The
engine writes the fixed format before delivery and parses no user-authored control field from it.
Return is the narrow context-resume action of `gate_return`: only the explicitly resumable fields
listed below are consumed. The payload cannot request an operation, create authority, or administer an
object; it is interrupted architectural state, not a control request.
The
handler is handed a pointer to this object in `r5`; every field is domain-addressable:
`[0]` flags u32 (`FP_PRESENT`=1, `SYNC_FAULT`=2, `INSN_VALID`=4, **`OP_RESTARTABLE`=8** — set by the
engine iff the interrupted engine op committed zero side effects, §9.3; **`VEC_PRESENT`=16** — a vector
region follows the FP region, sized from the §18 geometry; **`MAT_PRESENT`=32 reserved** — the §18
matrix seam), `[4]` _reserved u32, `[8]` **resume_pc u64** (authoritative for this frame — above),
`[16]` saved_mask u64 (pre-delivery `EVENTMASK`), `[24]` cause u64, `[32]` fault_addr_or_event u64,
`[40]` **fault_insn u64** (the faulting 64-bit instruction word, valid iff `INSN_VALID`; when
`OP_RESTARTABLE` is set the engine also sets `INSN_VALID` and fills `fault_insn`/`decode` with the
*interrupted blocking op* — the thread is parked on it, so the engine has it), `[48]` **decode u64**
(the engine's **minimal restart/FP syndrome**, not a complete decoded-operation record: bits `[4:0]` =
`rd`, `[9:5]` = `rs1`, `[14:10]` = `rs2`, `[19:15]` = `rs3`, `[20]` =
writes-GPR(0)/writes-FPR(1), `[28:21]` = opcode, `[29]` = `fmt` low bit, `[32:30]` = `rm` (as encoded,
incl. DYN), `[34:33]` = `intw`, `[36:35]` = `fmt` (the full §14 2-bit field; `[29]` mirrors its low bit
for layout compatibility), rest reserved-zero; valid iff `INSN_VALID`. It intentionally omits `rs4`/
`rs5`, immediates, and family-specific atomic/vector/custom subfields. Software emulating an instruction
outside the represented FP/restart subset must decode the authoritative raw `fault_insn`; a future
complete syndrome, if added, requires a separately versioned payload layout), `[56]` **orig_rd_value u64** (valid iff `OP_RESTARTABLE`: the pre-op value
of the interrupted op's `rd` register — by cancellation time the saved `gprs[rd]` already holds
`-INTERRUPTED`, so if the op encoded `rd` aliasing a source, rewind-and-re-execute would run with a
clobbered operand; this field is why the hazard cannot exist), `[64 .. 312)` GPRs `r1`..`r31` (31 × 8 B;
`r0` omitted), `[312]` **context_live_mask u64**. In v1 the mask is always `UINT64_MAX`: bits
`0..31` cover `r0..r31` and bits `32..63` cover `f0..f31`, and every register is present/saved
(including the architectural zero value for `r0`). If `FP_PRESENT`: `[320]` FCSR u64,
`[328 .. 584)` `f0`..`f31`. **Total 320 B (no FP) / 584 B (FP)**, plus the §18 vector region when
`VEC_PRESENT`. **`SPARSE_CONTEXT`, reserved by name
(the semantic sibling the §12 death hints must not become):** a separately named per-domain builder opt-in —
never ambient — under which dead-marked registers are saved as **zero** rather than their stale
values: the save shrinks internally, scrubbing comes free, and reads-after-resume stay *defined*
(they return zero). The already-frozen `context_live_mask` would then report the compiler-declared
live set, so enabling the feature changes no payload offsets or size. Reserved, not built, because it
converts a wrong compiler liveness table from a performance bug into a correctness bug — the
zeroing-op gun, taken off the table until the toolchain's liveness emission has years of soak.
**And its liveness source is named now, before anyone proposes the shortcut: when `SPARSE_CONTEXT`
lands, it reads the compiler's *emitted liveness tables* — a deliberate, per-domain, semantic
contract — never the dynamic trail of §12 kill hints.** Hints are ignorable, and ignorable means
they cannot be load-bearing; "the core already saw the kill bits, just use them for the sparse
save" would quietly convert every hint in the instruction stream into semantics — the exact gun
this reservation exists to keep holstered. A register killed at instruction N and faulted over at
N+1 saves its full stale value in the §17.5 payload, today and after `SPARSE_CONTEXT`, unless the
*table* says dead. The
software half needs no reservation: a personality may surface compiler liveness tables to handlers
today (a `live_mask` convention over the unchanged payload), which shrinks what debuggers and
migration must *interpret* without changing what the engine saves. **The frozen restart recipe** (§9.3;
software, run by the handler when `OP_RESTARTABLE` is set and policy asks for restart):
`gprs[decode.rd] = orig_rd_value; resume_pc -= 8; gate_return 0` (skip the `gprs` write when
`decode.rd` = 0). For an **instruction-emulation** trap (illegal/disabled-opcode, e.g. an FP op under a MachineView that withholds the FP
grant, §16.7), hardware fills `fault_insn` + `decode`. For an operation covered by the minimal syndrome,
the handler reads the destination register from `decode[4:0]`; otherwise it decodes `fault_insn`. In
either case it writes the emulated result, advances `resume_pc` past the 8-byte instruction, and returns.
**No page walk or software re-fetch is required; complete emulation may require software decode.** Editing the
payload edits the resumed context; `gate_return 0` resumes from the (possibly edited) payload.
**Read-back trust boundary (frozen — which fields `gate_return` consumes vs ignores):** the engine reads
back **only** `resume_pc`, `saved_mask`, the GPRs, and (per the *engine's* FP record) FCSR + the FP
file. **The `[0]` flags word and everything else (`cause`, `fault_addr_or_event`, `fault_insn`,
`decode`, `orig_rd_value`) are write-only-to-handler**: frame geometry, `FP_PRESENT`, `SYNC_FAULT`, and
restartability come from **engine state**, so a handler flipping `FP_PRESENT` cannot make the engine
restore a different frame shape or read past the payload. The frame-held registration pin makes
mid-handler unmapping impossible; `gate_return` therefore has no payload-access `-FAULT` case. The
**caller linkage and `link` are not in this payload** — they live in the engine frame, so a handler can
rewrite its saved PC or registers but can neither change who is resumed nor relink the chain. A uarch
may fill the FP region lazily, but the payload **shape** is fixed. (A domain-initiated `gate_call`
pushes **no** payload: its saved state is callee-saved only, held in the engine frame — there is nothing
for a handler to edit mid-call.)

**User-space threading (informative, so the frame model is not misread as forbidding M:N).** Fiber /
green-thread / async runtimes are fully expressible, and the continuation stack does not constrain them:
- **Voluntary switches never involve the engine.** `sp` is a plain GPR with no privileged status; a
  cooperative context switch is the ordinary ~20-instruction register swap in userspace. Nothing here
  governs a context the engine never delivered into.
- **Preemptive M:N switching works through the payload, by design.** A timer-event scheduler that wants
  to resume a *different* fiber overwrites the payload's GPRs (including `sp`) and `resume_pc` with the
  target fiber's saved set and returns — resuming elsewhere without touching any linkage. The
  engine-private linkage protection forbids only **reordering nested delivery frames** (resuming an
  outer interrupted context while abandoning an inner delivery mid-flight) — which real M:N runtimes
  already avoid.
- **The one real constraint: a fiber blocked in a `gate_call` pins its thread** until the call reaches a
  §9.4 boundary (the engine frame holds the caller linkage). M:N runtimes therefore route
  potentially-blocking service work through the **asynchronous gate form** (`gate.submit`, §9.2 —
  completion on a waitset the scheduler already waits on, §10.3) or plain async completion, reserving
  synchronous gates for calls that should hold the thread. This is a choice between two first-class
  forms, not a workaround: `SUBMIT` keeps donation, inheritance, and the §9.4 cascade — the chain
  carries them, not the parked thread.

### 17.6 Versioned records (fixed header frozen here; body is the schema)
- **`env_open` description stream:** `[0]` record_type u32, `[4]` version u32, `[8]` length u64,
  then the type body.
  Record types, **numerically assigned** (the chip decodes the selector, so the numbers are ISA):
  `0` `ISA_VERSION`,
  `1` `GEOMETRY`, `2` `TOPOLOGY`, `3` `FEATURES`, `4` `TIMEBASE`, `5` `STARTUP`,
  `6+` reserved
  (additive, per revision). Per type: `ISA_VERSION`; `GEOMETRY` (page size, cache-line size, virtual-address width §7,
  `GATE_INLINE_MAX` §9.2, `WORKQUEUE_DESC_MAX`/`WORKQUEUE_DEPTH_MAX` §10.2/§16.4,
  `DOMAIN_TAG_CAPACITY` §15, `DEBUG_WATCH_SLOTS` §16.3/§16.4, `VLEN` §18, `INVALIDATION_ACK_BOUND`/`ATS_ACK_BOUND` §11.2 (ticks), the machine **atomic-write
  floor** §10.1, `TILE_COUNT` in the domain's bound MachineView, and the published
  `SPAWN_WARM_RTT`/`DESTROY_WARM` bounds), `TOPOLOGY` (tiles + coherence domains + the **memory-tier property table** (§15: latency,
  bandwidth, persistence, failure domain, CPU/device accessibility, migration cost per tier)
  **as the MachineView states them**, §16.7 — a
  `{type, length}` TLV list in view-tile names), `FEATURES` (bitmap incl. the FP §14 and vector §18
  profiles, per the view), `TIMEBASE` (the visible timebase frequency, §8.3), `STARTUP` (the
  startup-metadata pointer). Bodies catalogued in **`isa_spec.json`** (the served-description
  serialization, §16.6 clause 3).
### 17.7 Typed object catalog

Hardware-owned objects use the class-specific opcodes of §16.0. The opcode fixes the
capability class and `func[7:0]` fixes one operand schema and state transition. There is no object
class selector, universal request record, control header, capability/result array, or compatibility
namespace. Service-owned objects are invoked only through an explicit gate or endpoint capability.

**Object classes.** `1 Domain`, `2 ChannelEndpoint`, `3 Counter`, `4 CallGate`, `5 Timer`,
`6 InterruptWaitable`, `7 Waitset`, `8 DMAWindow`, `9 PMU`, `10 ClockView`,
`11 FileDescription`, `12 Capability`, `13 Thread`, `14 WorkQueue`, `15 DebugTarget`,
`16 MachineView`, `17 PagedBacking`, `18 EventRing`, `19 CompletionQueue`, and
`20 InterruptSource`, and `21 Device`; classes `22..255` are reserved and
classes `>=256` are service-owned.

`Device` is an immutable sealed bundle of capability and scalar members identified by a
profile. It is the sole hardware discovery object: reset grants Devices to the first Domain,
parents grant Devices to children, and software services may construct Devices with the same
profiles. No physical-address namespace, interrupt-number namespace, device tree, board blob,
or second device-binding class exists in the architecture.

**Class-specific opcode families.**

| Opcode | Family | Fixed functions |
|---|---|---|
| `0xbb` | ChannelEndpoint | `0 channel.new`, `1 channel.capacity`, `2 channel.overrun`, `3 channel.seal`, `4 channel.abort`, `5 channel.shutdown`, `6 channel.set_blocking`, `7 channel.take_loss`, `8 channel.resize`, `9 channel.get`, `10 SENT_RECORDS`, `11 SENT_BYTES`, `12 RECEIVED_RECORDS`, `13 RECEIVED_BYTES`, `14 channel.producer`, `15 channel.consumer`, `16 channel.schema`, `17 channel.acceptance`, `18 channel.peek` |
| `0xbc` | Counter | `0 counter.new`, `1 counter.destroy`, `2 counter.read`, `3 counter.set`, `4 counter.add`, `5 counter.threshold`; `6..255` reserved |
| `0xbd` | CallGate | `0 gate.new`, `1 gate.entry`, `2 gate.stack`, `3 gate.limits`, `4 gate.timing`, `5 gate.abi`, `6 gate.seal`, `7 gate.submit`, `8 gate.abort`, `9 gate.borrow_arg`, `10 gate.lifecycle_queue`, `11 gate.serve`; `12..255` reserved |
| `0xbe` | Timer | `0 timer.new`, `1 timer.clock`, `2 timer.delivery_event`, `3 timer.delivery_counter`, `4 timer.delivery_queue`, `5 timer.delivery_gate`, `6 timer.delivery_message`, `7 timer.realtime`, `8 timer.place`, `9 timer.seal`, `10 timer.abort`, `11 timer.destroy`, `12 timer.arm_rel`, `13 timer.arm_abs`, `14 timer.arm_phys`, `15 timer.disarm`, `16 timer.gettime`, `17 timer.getoverrun`; `18..255` reserved |
| `0xbf` | InterruptWaitable | `0 irq.new`, `1 irq.source`, `2 irq.delivery`, `3 irq.priority`, `4 irq.place`, `5 irq.seal`, `6 irq.abort`, `7 irq.destroy`, `8 irq.mask`, `9 irq.unmask`, `10 irq.ack`, `11 irq.ack_mode`; `12..255` reserved |
| `0xc0` | Waitset | `0 waitset.new`, `1 waitset.destroy`, `2 waitset.add`, `3 waitset.del`, `4 waitset.mod`; `5..255` reserved |
| `0xc1` | DMAWindow | `0 window.new`, `1 window.scope`, `2 window.device`, `3 window.ats`, `4 window.seal`, `5 window.abort`, `6 window.remap`, `7 window.generation`, `8 window.acknowledged`, `9 window.direction`, `10 window.status`, `11 window.extents`, `12 window.copy_facet`, `13 window.fill_facet`, `14 window.copyv_facet`, `15 window.copy_hash_facet`, `16 window.transient_pins`, `17 window.requester_facet`, `18 window.remap_one`, `19 window.pin`, `20 window.faultable`; `21..255` reserved |
| `0xc2` | PMU | `0 pmu.new`, `1 pmu.destroy`, `2 pmu.event`, `3 pmu.set_threshold`, `4 pmu.bind_waitable`, `5 pmu.read`, `6 pmu.reset`; `7..255` reserved |
| `0xc3` | ClockView | `0 clock.new`, `1 clock.destroy`, `2 clock.set`, `3 clock.adjust`, `4 clock.get`; `5..255` reserved |
| `0xc4` | FileDescription | `0 cursor_get`, `1 cursor_set`, `2 cursor_add`; `3..255` reserved |
| `0xc5` | WorkQueue | `0 workqueue.get`, `1 workqueue.teardown`, `2 workqueue.set_blocking`, `3 workqueue.new`, `4 workqueue.device`, `5 workqueue.completion`, `6 workqueue.seal`, `7 workqueue.abort`; `8..255` reserved |
| `0xc6` | DebugTarget | `0 debug.new`, `1 debug.destroy`, `2 debug.bind_events`, `3 debug.read_context`, `4 debug.write_context`, `5 debug.set_step`, `6 debug.set_watch`, `7 debug.clear_watch`, `8 debug.read_mem`, `9 debug.write_mem`; `10..255` reserved |
| `0xc7` | MachineView | `0 mview.new`, `1 mview.tiles`, `2 mview.features`, `3 mview.counters`, `4 mview.identity`, `5 mview.time`, `6 mview.va_width`, `7 mview.atomic_agents`, `8 mview.gate_inline_limit`, `9 mview.iovec_limit`, `10 mview.sgl_limit`, `11 mview.workqueue_limits`, `12 mview.invalidation_bound`, `13 mview.seal`, `14 mview.abort`, `15 mview.get`, `16 mview.identity_scope`; `17..255` reserved |
| `0xc8` | PagedBacking | `0 backing.new`, `1 backing.pager`, `2 backing.charge`, `3 backing.seal`, `4 backing.abort`, `5 backing.rebind_pager`, `6 backing.detach_pager`, `7 backing.retarget_charge`, `8 reserved`, `9 backing.pin_resident`, `10 backing.supply`, `11 backing.evict`, `12 accessed.begin`, `13 backing.rehome`, `14 backing.unpin_resident`, `15 writegen.rotate`, `16 dirty.begin`, `17 dirty.next`, `18 backing.clone`, `19 backing.persist`, `20 backing.code`, `21 backing.contig`, `22 backing.reject`, `23 backing.supply_req`, `24 backing.respond`; `25..255` reserved |
| `0xc9` | Device | `0 device.new`, `1 device.member`, `2 device.scalar`, `3 device.seal`, `4 device.get`, `5 device.scalar_get`, `6 device.profile`; `7..255` reserved |
| `0xac` | CompletionQueue | `0 cqueue.new`, `1 cqueue.destroy`, `2 cqueue.recv`, `3 cqueue.peek`; `4..255` reserved |
| `0xcf` | EventRing | `0 eventring.new`, `1 eventring.destroy`, `2 eventring.bind`, `3 ready.next`; `4..255` reserved |

### 17.7a Resolved typed-family operand and result contracts

The tables in §16.0 and §17.7 are authoritative.  The machine-readable catalog is a checked
transcription regenerated from these tables, never an independent source.  Every operand below
maps left-to-right to `rd, rs1..rs5` except an explicitly named field.  Unassigned bits are
reserved-zero. The former unified producer namespace, universal object getter, and obsolete
gate-argument declaration operations are retired and do not decode.

**Counter (`0xbc`).**

```text
counter.new        rd, owner, initial_value
counter.destroy    rd, counter
counter.read       rd, counter                         ; raw getter
counter.set        rd, counter, value
counter.add        rd, counter, signed_delta           ; saturates at 0/2^64-1
counter.threshold  rd, counter, value                  ; replaces prior threshold
```

**Device (`0xc9`).**

```text
device.new      rd_builder, profile
device.member   rd_builder, builder, role, member_cap
device.scalar   rd_builder, builder, role, value
device.seal     rd_device, builder
device.get      rd, device, role
device.scalar_get rd, device, role                       ; raw getter
device.profile  rd, device                              ; raw getter
```

`profile` and `role` are unsigned 32-bit values in registers and upper bits must be zero.
Profile 0 and role 0 are invalid. Profiles `1..65535` are architected,
`65536..0x7fffffff` are assigned by the public profile registry, and
`0x80000000..0xfffffffe` are vendor-private; `0xffffffff` is invalid. A profile registry row
closes every role as exactly one capability class or one scalar and states whether it is required.
Roles are singular; arrays use distinct profile-assigned role numbers, keeping member lookup a
fixed three-operand operation. A row may provide OS-binding metadata such as a compatible string. The
registry is platform/toolchain data and is never decoded by the engine.

Builder mutation is generation-threaded and consumes the prior generation. `device.member`
requires `GRANT|REVOKE` on the member and records at most those rights while preserving the member's
existing lineage cell. `device.scalar` records a bit-exact u64. A duplicate role is `-MALFORMED`.
Because the profile registry is not chip-decoded, `device.seal` validates only the closed structural
facts (nonzero profile/roles, unique roles, valid capabilities and rights) and publishes one immutable
Device; platform tooling validates required profile roles and classes. `device.get` returns a fresh capability to
a capability member, narrowed to the rights stored in the bundle; naming a scalar or absent
role is `-BADREF`. `device.scalar_get` is a raw getter: an invalid Device, capability-valued role,
or absent role is a precise fault rather than a returned condition. The Device member cursor retains both member
kinds for bulk discovery. `device.profile` returns the raw profile value and faults, rather than
returning a condition, for an invalid capability.

Capabilities minted by `device.get`, including nested Device members, retain their original member
lineage, so revoking a member remains effective. Revoking or destroying the Device invalidates the
bundle and prevents every later extraction; it does **not** rewrite or join member lineages, and an
already-extracted member remains governed by its original lineage. A profile that requires
fate-sharing (including an isolation group) supplies members minted on that group's common lineage;
destroying the group authority then uses the ordinary one-cell revocation transition. This keeps the
§2.2 one-lineage-cell invariant and avoids an ancestry walk or a hidden second revocation graph.
Holding a Device reveals no member until `device.get`; a
Device can be delegated with one `dgrant`. A software service may build the same profile from
software-owned members. Whether that is behaviorally substitutable is a property of the
profile's required member classes. A BAR-shaped profile may use either a real BAR or a
`device_ordered` provided backing; the latter completes register accesses with
`backing.respond` and differs only in observable latency.

`objenum.begin(device, 0)` returns 24-byte Device-member records:
`{role u32, kind u32 (0 CAPABILITY, 1 SCALAR), value u64, rights u32, object_class u32}`.
For a capability member `value` is zero (enumeration never mints authority), and `rights` and
`object_class` describe what `device.get` may return. For a scalar, `value` is the bit-exact scalar
and the final two fields are zero. Unknown kinds and nonzero reserved combinations are malformed.

**Timer (`0xbe`).**

```text
timer.new               rd_builder, owner
timer.clock             rd_builder, builder, clockview_cap  ; 0 = issuing Domain's bound ClockView
timer.delivery_event    rd_builder, builder, event_number
timer.delivery_counter  rd_builder, builder, counter_cap
timer.delivery_queue    rd_builder, builder, cqueue_cap
timer.delivery_gate     rd_builder, builder, gate_cap
timer.delivery_message  rd_builder, builder, endpoint_cap
timer.realtime          rd_builder, builder, reservation_domain_cap
timer.place             rd_builder, builder, steering_tile
timer.seal              rd_timer, builder
timer.abort             builder
timer.destroy           rd, timer
timer.arm_rel           rd_arm, timer, delay, period       {slack_log2[13:8]}
timer.arm_abs           rd_arm, timer, deadline, period    {slack_log2[13:8]}
timer.arm_phys          rd_arm, timer, deadline, period    {slack_log2[13:8]}
timer.disarm            rd, timer
timer.gettime           rd, timer                          ; raw getter
timer.getoverrun        rd, timer                          ; raw getter
```

An owner value of zero means self.  Event numbers are 0–47. Exactly one delivery fact may be
live; restating it replaces the prior fact, and sealing without one is `-MALFORMED`.
`timer.arm_*` returns a fresh nonzero generation-qualified arm id. `timer.disarm` atomically
returns the prior remaining ticks, zero if unarmed, clamped to `2^63-1`; either expiry or disarm
wins the arm's terminal transition. `timer.gettime` returns remaining ticks rounded down through
the visible time quantum, zero if unarmed. `timer.getoverrun` is a wrapping observational count.
Queue delivery writes `{arm_id u64, status i64 (=0), expiry_count u64}`; message delivery writes
`{arm_id u64, expiry_count u64}`. Waitset delivery uses the membership's `member_id` and `cookie`
with ready mask `TIMER = 32`; there is no timer delivery key.

**InterruptWaitable (`0xbf`).**

```text
irq.new       rd_builder, owner
irq.source    rd_builder, builder, interrupt_source_cap
irq.delivery  rd_builder, builder, mode, event_number
irq.priority  rd_builder, builder, priority
irq.place     rd_builder, builder, steering_tile
irq.seal      rd_irq, builder
irq.abort     builder
irq.destroy   rd, irq
irq.mask      rd, irq
irq.unmask    rd, irq
irq.ack       rd, irq
irq.ack_mode  rd, irq, mode
```

Delivery mode is `0 WAITABLE` (event number reserved-zero) or `1 EVENT` (event 0–47).
Priority is 0–255, larger values being more urgent only among the domain's own sources.
Acknowledgment mode is `0 AUTO`, `1 EXPLICIT`; `irq.ack` in AUTO mode is a no-op.

**CallGate (`0xbd`).**

```text
gate.new        rd_builder, owner
gate.entry      rd_builder, builder, entry_pc
gate.stack      rd_builder, builder, pool_base, slot_size, slot_count
gate.limits     rd_builder, builder, inline_area_len, max_cap_transfer, submit_queue_bound
gate.timing     rd_builder, builder, max_donation, cleanup_grace {cancel_policy[8], serialized[9]}
gate.abi        rd_builder, builder, abi_class
gate.seal       rd_gate, builder
gate.submit     rd_activity, gate, cqueue, msgdesc_ptr
gate.abort      builder
gate.borrow_arg rd_builder, builder, ptr_regnum, len_regnum, rights
gate.lifecycle_queue rd_builder, builder, cqueue
gate.serve      rd, gate, ready_counter
```

`slot_count` is nonzero and every slot is 16-byte aligned. Its layout is `[0,128)` activation
context, `[128,align16(128+inline_area_len))` inline/reply bytes, then the downward-growing handler
stack. Seal rejects arithmetic overflow or fewer than 16 stack bytes, so
`slot_size >= align16(128+inline_area_len)+16`. Input and reply reuse that one inline area at their
respective crossing phases and never overlap a live handler stack. A
serialized gate has exactly one stack slot. Limits are bounded by
the view's published maxima; queue bound zero disables async submission. Borrow register numbers
are 2–8, rights contain only READ/WRITE, and at most two borrow declarations exist. The callee sees
such a declared word shifted by one register because `r2` holds the context. `gate.submit`
uses the frozen 32-byte message descriptor and returns an ActivityRef. Seal requires entry, stack,
and ABI; absent limits/timing use the architectural maxima and zero timing policy.

`gate.lifecycle_queue` binds one CompletionQueue to receive the lifecycle records defined below;
its completion capacity is reserved at service-object mint time so a mandatory last-reference
record is never silently lost.

`gate.serve` is a CONTROL operation executed by the persistent callee-Domain thread that will serve
the Gate. It requires an otherwise unserved sealed Gate and exactly one declared handler-stack slot.
The first call and `gate.serve` linearize against each other: if a call has begun, serve fails
`-BUSY`; if serve wins, the Gate becomes permanently served and calls cannot dispatch until its
worker is parked. Validation failure returns a condition without binding. Success preserves the worker's initialized
tp/TLS and parks its current continuation. Each
call restores the persistent worker identity and tp, resets sp to the declared handler stack, writes
the ActivationContext into the slot prefix, installs r2=context and r3--r9=user arguments plus the r1 return sentinel, and
enters `gate.entry`. `gate_return` wakes the external caller, restores the serve continuation, and
atomically reparks it. A cleanly handled cancellation may reset to that park; an unhandled handler
fault or force cancellation terminates the worker and makes the Gate HANGUP. On successful binding
the engine atomically increments the writable `ready_counter` before parking; failure returns
without changing it. The creator may therefore wait on that Counter before exposing the Gate,
without a publication race. `gate.serve` returns
only on Gate teardown or terminal error. Scaling and affinity are software policy implemented with
multiple one-worker Gates; no numeric caller identity or engine session router exists.

**Waitset, EventRing, and CompletionQueue.**

```text
waitset.new      rd_waitset
waitset.destroy  rd, waitset
waitset.add      rd_member, waitset, source, ready_mask, cookie, flags
waitset.del      rd, waitset, member_id
waitset.mod      rd, waitset, member_id, ready_mask, cookie, flags

eventring.new      rd, base_ptr, capacity
eventring.destroy  rd, ring
eventring.bind     rd, waitset, ring
ready.next         rd, ring, dst_ptr

cqueue.new      rd, owner, capacity
cqueue.destroy  rd, cqueue
cqueue.recv     rd, cqueue, dst_ptr
cqueue.peek     rd, cqueue, dst_ptr
```

Trigger is `0 LEVEL`, `1 EDGE`. EventRing capacity counts 24-byte entries and is nonzero.
Binding names the current thread implicitly. `ready.next` consumes one event entry and returns
`-WOULDBLOCK` when empty. Completion records are 24 bytes.

**DMAWindow (`0xc1`).** The fixed schemas are:

```text
window.new/abort/seal                 rd_or_builder, owner_or_builder
window.scope/device/ats               rd_builder, builder, value
window.remap                          rd, window, extent_ptr, extent_count
window.generation/acknowledged/
window.direction/status/
window.transient_pins                 rd, window                 ; raw getters
window.extents                        rd_cursor, window
window.copy_facet/fill_facet/
window.copyv_facet/copy_hash_facet    rd_facet, window
window.remap_one                      rd, window, iova, backing_offset, len
window.pin                            rd_builder, builder
```

Function 20 `window.faultable` is an assigned-but-dark PRI/PASID seam and returns
`-UNSUPPORTED` until that profile lands. Extent cursors use the record below.

**PagedBacking (`0xc8`) live forms.**

```text
backing.pin_resident    rd_lease, backing, offset, length
backing.supply          rd, backing, offset, length, src_ptr, designation_epoch {wp[8]}
backing.evict           rd_pages, backing, offset, length {policy[8]}
accessed.begin          rd_cursor, backing, offset, length {clear[8]}
backing.rehome          rd, backing, offset, length, home
backing.unpin_resident  rd, backing, lease_id
writegen.rotate         rd_generation, backing
dirty.begin             rd_cursor, backing, since, through, offset, length
dirty.next              rd, cursor, dst_ptr
backing.clone           rd_clone, backing
backing.persist         rd, backing, offset, length
backing.reject          rd, backing, request_id, designation_epoch, condition
backing.supply_req      rd, backing, request_id, src_ptr, designation_epoch {wp[8]}
```

Pin leases and request ids are nonzero generation-qualified ids. Plain supply uses the backing's
recorded default charge target; request supply uses the request's recorded faulter account;
`src_ptr = 0` explicitly means zero-fill. Policy 0 is ANY, 1 CLEAN_ONLY. Reject accepts
only BOUNDS, EXHAUSTED, FAULT, or POISONED. Supply/evict ranges are page-aligned; request ids are
nonzero, and stale request ids or designation epochs return `-STALE`.

**DebugTarget (`0xc6`).**

```text
debug.new            rd_target, domain_cap
debug.destroy        rd, target
debug.bind_events    rd, target, endpoint_cap
debug.read_context   rd, target, tid, dst_ptr, dst_len
debug.write_context  rd, target, tid, src_ptr, src_len
debug.set_step       rd, target, tid, enable
debug.set_watch      rd_watch, target, tid, addr, len, kind
debug.clear_watch    rd, target, watch_id
debug.read_mem       rd_bytes, target, src_va, len, dst_ptr
debug.write_mem      rd_bytes, target, dst_va, len, src_ptr
```

Watch `tid` is a live thread in the target or `UINT64_MAX` for all target threads. Watch kind is
`0 WRITE`, `1 READWRITE`, `2 EXECUTE`. Events are 48 bytes:
`{version=1 u32, length=48 u32, tid u64, kind u32, reserved u32, pc u64, addr u64, aux u64}`;
kind is 0 STEP, 1 WATCH, 2 TRAP0, or 3 ROUTED_FAULT.

**Other fixed live families.**

```text
clock.new/destroy       rd, parent_or_view
clock.set               rd, view, new_value
clock.adjust            rd, view, signed_slew_q32
clock.get               rd, view, selector             ; raw getter
cursor_get              rd, filedesc                    ; raw getter
cursor_set              rd, filedesc, absolute
cursor_add              rd, filedesc, signed_delta
workqueue.get           rd, queue, selector             ; raw getter
workqueue.teardown      rd, queue
workqueue.set_blocking  rd, queue, policy
pmu.new                 rd, owner
pmu.destroy             rd, pmu
pmu.event               rd, pmu, counter_index, event_id
pmu.set_threshold       rd, pmu, counter_index, value
pmu.bind_waitable       rd, pmu, counter_index
pmu.read                rd, pmu, counter_index          ; raw getter
pmu.reset               rd, pmu, counter_index
```

Clock selectors are 0 ANCHOR_TICK, 1 ANCHOR_VIEW, 2 SLEW_Q32. Channel selectors are
0 CAPACITY, 1 QUEUED_BYTES, 2 QUEUED_RECORDS, 3 ATOMIC_WRITE_BOUND, 4 BLOCKING,
5 OVERRUN_POLICY, 6 LOSS_INDICATOR. WorkQueue selectors are 0 FREE_SLOTS, 1 QUEUE_DEPTH,
2 MAX_DESC_LEN, 3 STATUS_FLAGS. Blocking policy is 0 BLOCK, 1 WOULDBLOCK; shutdown direction
is 0 RD, 1 WR, 2 RDWR.

### 17.7b Shared typed namespaces and raw getter pages

`abi_class`, shared by `gate.abi` and `dabi`, is: 0 GPR, 1 GPR_FPR,
2 GPR_FPR_VEC; 3–15 reserved. Budget dimensions are 0 MEMORY_BYTES, 1 OBJECT_COUNT,
2 CAP_SLOTS, 3 TELEMETRY_QUOTA; 4–63 reserved.

`dget rd, domain, selector` is a raw getter: 0 LIFECYCLE_STATE, 1 SCHED_CLASS,
2 ABI_CLASS, 3 EXIT_VALUE (corpse only), 4 THREAD_COUNT, 5 CHILD_COUNT,
6 MEASUREMENT_PRESENT; 7–30 reserved. `dget2 rd0, rd1, domain, dimension` returns
`{charged, ceiling}` for a budget dimension. It uses a named-slot custom form: `rd0` occupies
the rd slot, `domain` rs1, `dimension` rs2, and `rd1` is slot-named in rs4; all other bits are
reserved-zero.

`mview.get rd, view, selector` is a raw getter. Selectors 0–20 are respectively VA_WIDTH,
TILE_COUNT, TIMEBASE_FREQ, TICK_QUANTUM_SHIFT, ATOMIC_AGENTS, GATE_INLINE_MAX, IOVEC_MAX,
SGL_MAX, WORKQUEUE_DESC_MAX, WORKQUEUE_DEPTH_MAX, INVALIDATION_ACK_BOUND, ATS_ACK_BOUND,
DOMAIN_TAG_CAPACITY, VLEN, TIMEBASE_SKEW_BOUND, GATE_WARM_RTT, PAGE_SIZE, LARGE_LEAF_SIZE,
ATOMIC_WRITE_FLOOR, DEBUG_WATCH_SLOTS, and GATE_RESIDENCY_LEASES. Selector 21 is
SPAWN_WARM_RTT and selector 22 is DESTROY_WARM, both in architectural ticks; 23–63 reserved.

Change classes use the same assignments as a mask bit for `observe.mark` and as an ordinal for
`changes.begin`: 0 DIRTY_MEMORY/WRITES, 1 MAPPINGS, 2 CAPABILITIES, 3 ACTIVATIONS,
4 OBJECT_STATE, 5 SERVICE_IMPORTS; 6–63 reserved. A zero mark mask is malformed.

`denum.begin rd, domain, kind` kinds are 0 MAPPINGS, 1 CHILDREN, 2 THREADS,
3 SERVICE_IMPORTS, and 4 CAPS. CAPS is the universal discovery relation: `cursor.next`
writes a 32-byte record `{handle u64, object_class u32, profile u32, rights u32, flags u32,
lineage_epoch u64}`. `handle` is the receiver-local, directly usable capability token;
`profile` is nonzero only for class-21 Device; flags are bit 0 SEALED, bit 1 STAMPED,
bit 2 POISONED, with all other bits reserved-zero. Enumeration requires `READ` on the
target Domain (self is always readable), is generation-stamped against capability mutation,
and never exposes an empty or retired slot. Thus the reset grant and every parent publish
hardware by installing ordinary Device capabilities, not by constructing a parallel manifest.
`objenum.begin rd, object, kind` kind 0 selects the class's primary
collection. `changes.begin` is `rd_cursor, subject, generation, change_class`.
`incident.bind` is `rd, subject, event_ring`; `incident.begin` is
`rd_cursor, subject, since_generation`; `cursor.next` writes one 64-byte incident record;
`incident.ack` is `rd, subject, incident_id` and is idempotent.

Quiesce scopes are 0 ACTIVATIONS, 1 NEW_ENTRY, 2 MEMORY_MUTATION, 3 CAPABILITY_MUTATION,
4 SUBMISSION, 5 FULL_SUBJECT. Drain dispositions are 0 FINISH_ACCEPTED,
1 CANCEL_CANCELLABLE, 2 REJECT_NEW, 3 REUSABLE_BOUNDARY. State modes are 0 FULL,
1 SINCE_GENERATION, 2 METADATA, 3 DIAGNOSTIC_SNAPSHOT.

Capability pair getters use two explicitly named destinations. `cap.class` word 0 is the
object-class number and word 1 is the class-defined profile (`Device.profile`, otherwise zero in
v1). A class number `>=256` itself marks a service-owned object. `cap.lineage` word 0 is the lineage epoch; word 1 flags are bit 0 SEALED,
1 POISONED, 2 SATURATED, 3 STAMP_STALE. `cap.move`'s destination is a Domain capability with
GRANT; it atomically installs the rights intersection in an engine-selected destination slot,
charges the destination CAP_SLOTS budget, consumes the source, and returns the receiver-local
handle. `cap.restamp` and `cell.repoint.*` use the authority and token rules of §3; prepare is
`rd_token, cell, expected_target, new_target, deadline`.

### 17.7c Domain construction and coroutine reply ABI

`dmap` stages a no-access mapping. `dprotect` sets the staged protection; an untouched mapping
publishes as a guard. Home operands name view tile/group ids in `[0,2^63)` with `UINT64_MAX`
meaning default.

Domain-build functions 8 and 9 are retired and remain dark. The surviving startup-state forms are:

```text
dstate.cow       rd, builder, source_domain, src_addr, dst_addr, len
dstate.move      rd, builder, src_addr, dst_addr, len
dstate.share_ro  rd, builder, src_addr, dst_addr, len
dstate.registers rd, builder, ctx_ptr
```

`dfork rd, source` captures a COW address-space image at publication, grants no authority
implicitly, and creates one entry activation. `dentry` indices are 0–15 and replace on restatement.
`dstack.new` supplies a fresh builder stack; `dstack.use rd,builder,base,size` supplies an existing
writable prospective range. `dgates rd,builder,gate_kind,entry_pc` uses 0 FAULT, 1 EVENT.
`dgrantm`/`dmovem` mask bits 0–15 name r2–r17, densely filling destination slots from
`slot_base` with full source rights; narrowing is `dlimit`.

`dreplace.mode rd,builder,mode` is function 45, legal only for a replacement builder. Mode bit 0
requests drain and bit 1 dormant; absent means reject inbound and runnable.

`dspawn rd,image,entry,state,masks` reads masks as scalar `[7:0]` (r2–r9, bit 0 must be zero),
cap-copy `[23:8]` (r2–r17), cap-move `[39:24]`, and reserved-zero `[63:40]`. Copy and move
masks may not overlap. State arrives in child r2; result is the child Domain capability.

Domain-call replies use the call's rd for value and r3 as discriminator: zero terminal return,
positive nonzero ActivationRef for a yield, negative condition. `dyield rd,value` receives the
later resume value in rd. `dresume rd,activation,value` consumes the single-use reference; a later
yield mints a fresh one. Naming r3 as call rd is malformed.

### 17.7d Bootstrap and frozen records

Reset installs the physical MachineView capability and the platform's Device capabilities in the
first Domain's ordinary capability table. Ordinary domains run against their bound view without
holding its capability; deriving or delegating views requires an explicit capability. There is no
STARTUP capability manifest and no architected role namespace. `env_open STARTUP` version 1 is the
single eight-byte `metadata_ptr` selected by `dstartup` (zero if absent), validated and published
with the prospective address space. Capabilities survive replacement only through explicit
`dgrant`/`dmove` plus `dslot.persist`; discovery after birth or replacement is CAPS enumeration.

The VMA record is 80 bytes: version/length, base, length, protection, memory type,
AS-local backing cookie, backing offset, charge account, resident pages, dirty pages,
locality class, and leaf class in the offsets frozen by §17.9. The MemoryIncident record is
64 bytes: version/length, offset, length, incident id, error kind, severity, flags,
disposition, and two reserved u64 words.

`cap.weaken` and `cap.upgrade` remain assigned-but-dark under the `WEAK_HANDLE` DVP seam and
return `-UNSUPPORTED`. `window.faultable` is likewise the named PRI/PASID seam. There is no
generic builder-abort instruction; language bindings carry the family-specific abort routine.

Functions not listed are reserved. A family does not inherit another family's function numbers or
operand conventions. Scalar getters have a definition-fixed register result; collections return a
cursor and byte state returns a stream. No generic property setter exists.

**Builder-only configuration.** `gate.new` returns an unpublished GateBuilder. `gate.entry`,
`gate.stack`, `gate.limits`, `gate.timing`, and `gate.abi` each add one named fact;
`gate.seal` validates and publishes the CallGate (rejecting a misaligned entry PC — low 3 bits
nonzero — as `-MALFORMED`, the same fail-closed construction check that rejects a misaligned
declared stack pointer, so a garbage entry PC can never reach activation; a non-canonical or
unmapped/non-executable entry additionally takes the ordinary synchronous fetch fault at
activation rather than wedging); `gate.abort` consumes an unpublished builder. A `gate_call` or `gate.submit` descriptor
describes only one invocation's variable arguments, capabilities, and borrow; it contains no gate
administration.

`channel.new` returns an unpublished ChannelBuilder. `channel.capacity` contributes the
owner-charged storage bound; `channel.overrun` contributes one record-delivery policy and fails
`-UNSUPPORTED` for byte-stream channel types. `channel.seal` publishes complete endpoint capability
or capabilities atomically, and `channel.abort` consumes the builder. `channel.resize` is the separate
live capacity transition: growth charges before publication; shrink below current occupancy,
reserved delivery space, or accepted records fails `-BUSY`; queued records and blocked producers are
otherwise preserved, and successful resizing bumps the channel configuration generation. Overrun
policy is immutable after sealing.

```text
channel.new       rd_builder, channel_type
channel.capacity  rd_builder, builder, capacity
channel.overrun   rd_builder, builder, overrun_policy
channel.seal      rd_endpoint, builder
channel.abort     builder
channel.resize    rd, endpoint, new_capacity
```

`channel_type` is a frozen enum: `0 BYTE_STREAM`, `1 RECORD_CHANNEL`,
`2 COMPLETION_QUEUE`, `3 EVENT_RING`, `4 WORK_QUEUE`; `5..255` are reserved.
The one constructor form is shared by the family. For a WorkQueue,
`channel.capacity` supplies its depth and `channel.schema` supplies its descriptor-size limit;
there is no class-dependent reinterpretation of extra `channel.new` operands.

The three channel topology facts use closed numeric namespaces. `producer_kind` is
`0 SOFTWARE`, `1 HARDWARE`; `consumer_kind` is `0 SOFTWARE`, `1 DEVICE`; and
`acceptance_kind` is `0 ENQUEUE_IF_SPACE`, `1 RESERVE_BEFORE_ACCEPT`; all other
values in each namespace are reserved. They describe engine-visible topology, not
implementation hints. The only legal sealed combinations are:

| channel type | producer | consumer | acceptance |
|---|---:|---:|---:|
| `BYTE_STREAM`, `RECORD_CHANNEL` | `SOFTWARE` | `SOFTWARE` | `ENQUEUE_IF_SPACE` |
| `COMPLETION_QUEUE` | `HARDWARE` | `SOFTWARE` | `RESERVE_BEFORE_ACCEPT` |
| `EVENT_RING` | `HARDWARE` | `SOFTWARE` | `ENQUEUE_IF_SPACE` |
| `WORK_QUEUE` | `SOFTWARE` | `DEVICE` | `RESERVE_BEFORE_ACCEPT` |

Each fact may be supplied at most once; a conflicting replacement is `-MALFORMED`.
`channel.seal` requires all three facts and rejects any combination outside this
matrix. Thus a producer/consumer spelling cannot silently manufacture a new channel
class or alter the class selected by `channel.new`.

`channel.new` requires `CREATE` in the current domain; successful mutations require the live current
builder generation; `channel.seal` revalidates `CREATE` and charges capacity to the publisher.
`channel.resize` requires `CONTROL` on the endpoint.

`window.new` returns an unpublished WindowBuilder. `window.scope`, `window.device`, and
`window.ats` add the authority range, device/completion binding, and ATS rule respectively;
`window.seal` publishes the window and `window.abort` consumes an unpublished builder.
`window.remap` may consume a typed extent stream because
the N extents are variable data; that stream contains no operation selector or administrative plan.
The four submission-facet getters return capabilities of distinct architectural types; their type,
not a field in submitted memory, selects copy, fill, vector copy, or copy-plus-SHA-256.
`window.requester_facet` requires `GRANT` on the sealed window and returns the separately typed
requester backing facet described in §15; it is never returned implicitly by `window.seal`.

`workqueue.new` returns an unpublished WorkQueueBuilder carrying capacity and descriptor-limit facts.
`workqueue.device` and `workqueue.completion` add the two mandatory relationships independently;
`workqueue.seal` atomically validates device incarnation and authority, completion capacity, placement,
locality, descriptor limits, accounting, compatibility, and fencing/generation state before returning
the first public WorkQueue capability. `workqueue.abort` consumes the builder. Device or completion
retargeting, if later admitted, is a separately named live transition requiring explicit quiescence or
handoff; construction semantics are never reused.

```text
workqueue.new         rd_builder, owner, capacity, descriptor_limit
workqueue.device      rd_builder, builder, device
workqueue.completion  rd_builder, builder, completion
workqueue.seal        rd_queue, builder
workqueue.abort       builder
```

`workqueue.new` requires `CREATE`; `workqueue.device` requires delegated device-control authority;
`workqueue.completion` requires authority to reserve CompletionQueue slots; and `workqueue.seal`
revalidates all three at publication.

The MachineViewBuilder functions and their derived-versus-restrictable geometry rule are defined in
§16.7. `mview.identity_scope` returns a typed facet suitable only for a descendant
`mview.identity`; it reveals no ancestry or machine-global identifier.

`backing.new` returns an unpublished BackingBuilder. `backing.pager` and `backing.charge` add exactly
the pager and default charging relations; `backing.seal` publishes and `backing.abort` consumes the
builder. The pager capability fixes the
protocol incarnation. Live pager and charge changes use the three separately named transitions above.
`backing.code rd, size` creates a separately authorized executable backing subject to W^X,
measurement and publication rules. `backing.contig rd, size, alignment` requests a
physically contiguous backing with distinct geometry, fragmentation accounting, admission, and
mobility constraints. Neither property is available through ordinary anonymous `mmap`.

**Event rings.** `channel.new` creates a first-class, charged ring over registered writable
storage. `eventring.bind rd, waitset, ring` makes the retained destination explicit and pins it
for the binding lifetime. `wait rd, waitset, deadline` writes only to that bound ring; `ready.next`
consumes one fixed event record. There is no hidden per-thread output pointer.

**Dirty observation.** `observe.mark(backing, WRITES)` establishes a backing write
generation; `dirty.begin rd_cursor, backing, since, through, offset, length` returns a
cursor over changed ranges consumed by `cursor.next` as 16 B `{start, length}` records. Hardware may use
bitmaps, summaries, logging, or protection epochs internally; no bitmap query record is architectural.
`accessed.begin rd_cursor, backing, offset, length, clear` uses the same fixed range result shape for
hint-class access observations.

**Rights bits.** Entry rights are: bit 0 `READ`, 1 `WRITE`, 2 `EXECUTE/CALL`, 3 `MAP`,
4 `SEND`, 5 `RECV`, 6 `WAIT`, 7 `CONTROL`, 8 `CREATE`, 9 `GRANT/DUP`, 10 `REVOKE`,
11 `DESTROY`, 12 `SEAL`, 13 `SET_TIME`, 14 `DMA`, 15 `BIND_IRQ`, 16 `POST`,
17 `SET_CRED`, 18 `PMU`, 19 `ADMIN`, 20 `DEBUG`, 21 `STATE`, 22 `CHARGE`, and
23 `INSPECT` (read-side introspection: context/memory reads, event binding, bounded holds —
`DEBUG`'s delegatable read-only half, §16.3);
bits 24–31 are reserved-zero. The selected fixed function derives its required rights. Software cannot
assert a weaker set. `CONTROL` covers self-service object configuration; `ADMIN` covers another
Domain's policy, budget, reservation, full quiescence, and prospective view/service-import state.
`STATE` authorizes closed state-stream capture/import/commit. `CHARGE` authorizes naming a Domain
budget as a supply charge target. `MAP` on a Domain capability authorizes the target address-space
facet. `cap.copy` can only clear rights. **The rights evolution rule (the condition enum's rule,
applied to the word that never got one):** a bit's meaning is class-relative while its encoding
is class-absolute, so **per-class meaning glosses are catalog rows, checked** — never scattered
prose; **a new bit is spent only on a genuinely cross-class concept** (a right one class needs
is a function-derivation fact under an existing bit, with its gloss recorded); and if the
32-bit word ever exhausts, the growth path is the named `EXTENDED_RIGHTS` seam (Appendix G),
never a per-class reinterpretation of an assigned bit.

**Memory protection and mapping fields.** `protection`: bit 0 R, bit 1 W, bit 2 X, bit 3 GUARD;
other bits are reserved-zero. W and X together are denied except for the JIT_ARENA rule of §11.4.
Private/shared, placement, reservation, population, stack growth, leaf class, and JIT backing are
separately named operations; no mapping or allocation flag word exists. `mem_type`: `0 normal_cached`,
`1 uncached`, `2 device_ordered`, `3 write_combining`. Slot replacement lifetime is selected by
`dslot.persist` or `dslot.drop_on_replace`; copy versus move is selected by the transfer instruction.

**Conditions.** The single condition namespace is §13.1. No object family defines another error
numbering or result envelope.


### 17.8 Hardware work descriptors and homogeneous sequences

Mapping has no memory record: `mapping` function operands are registers, and `mmap` is the fused
common function (§11.2). `map.protect`/`munmap_range` likewise use register operands.

The following `WORK_DESCRIPTOR` schemas are selected by distinct DMA submission-facet capability
types; none contains an operation field:

- **DMA Copy, 32 B:** `[0]` flags u32, `[4]` reserved u32, `[8]` src_iova u64,
  `[16]` dst_iova u64, `[24]` length u64.
- **DMA Fill, 32 B:** `[0]` flags u32, `[4]` pattern_width u32, `[8]` dst_iova u64,
  `[16]` length u64, `[24]` pattern u64. `pattern_width` is 1, 2, 4, or 8 and the pattern repeats.
- **DMA CopyV, 24 B:** `[0]` flags u32, `[4]` reserved u32, `[8]` sgl_ptr u64,
  `[16]` sgl_count u64. Each homogeneous SGL element is `{src_iova u64, dst_iova u64, len u64}`.
- **DMA CopyHash, 40 B:** `[0]` flags u32, `[4]` reserved u32, `[8]` src_iova u64,
  `[16]` dst_iova u64, `[24]` length u64, `[32]` hash_destination u64. On complete success it
  writes SHA-256 over exactly the copied bytes. On partial or failed completion the hash destination
  has no valid result. The fusion guarantees one completion relating copy and digest validity and
  licenses, but does not require, one source traversal.

The SGL is `HOMOGENEOUS_SEQUENCE`, limited to `SGL_MAX = 1024`, and is snapshot-copied and validated whole:
  every entry's iovas against the window's IOMMU scope and VMA permissions, every range
  overflow-checked before any transfer effect (the §11.1 snapshot discipline, carried onto the
  `send` path explicitly). Each submission returns a submission handle in
  `rd`; completion arrives on the window's CompletionQueue. **The completion object must be a
  CompletionQueue**: a DMA completion carries per-submission status a counter cannot represent, and
  post-abort the status is the only signal that the destination tail is indeterminate. **Overflow is
  impossible by construction: the completion slot is reserved at submit** — the submitting `send` fails
  **`-NOSPACE`** if the bound queue cannot guarantee space (free slots minus reserved in-flight), so the
  hardware producer can never find the queue full and no completion (least of all an abort notification)
  is ever dropped. **Completion record, 24 B (frozen — a hardware producer writes it, so it is
  ISA):** `[0]` ActivityRef u64, `[8]` status i64 — **`0` or a negative §13.1 condition, the
  one error namespace, no per-record enum** (so every status below is an *instance*, never a
  special case): `-CANCELLED` aborted by
  quiesce/revoke — an orderly abort, device still trusted; **`-POISONED` fence-synthesized abort,
  §3/§11.2 — the device missed its ack bound and is fenced: the *device* is dead, not just the
  transfer** (the status *is* the condition the window's poison bump produces — one enum, one job);
  `-STALE` stale window; `-FAULT` target fault; **`-HWFAIL` the executing machinery failed
  after acceptance — a fabric link, engine, or device controller, the device not declared
  corrupt (§13.1's producer set, family (a)); referent state is whatever the RAS record says**;
  `[16]` value u64, interpreted for DMA as
  `bytes_done` (for
  `-POISONED`: the fabric's count — the device may believe it wrote more; for `-HWFAIL`: the
  fabric's count up to the failure). **On an abort**
  (the §3 abort-at-burst-boundary drain): destination contents beyond `bytes_done` are **indeterminate**
  (partial bursts are not rolled back), and a DMA CopyHash submission reports no valid hash.
- **`gate_tail` 0xb0** `(rd, gate_cap)`: the protected tail call, registers-only (§9.2).
  **`0xb1`**: reserved (retired `free`, §11.2, Appendix G). **`mem_grant` 0xb2**
  `(rd, addr, len, rights)`: mints a memory-range cap over the caller's own space (§11.2); returns the
  handle or `-DENIED`/`-FAULT`; overflow-checked. **`map.protect` 0xb4** `(rd, addr, len, protection)`:
  changes protection semantics, never `mem_type`, backing, or leaf granularity. `map.demote` separately splits a large-leaf
  representation without changing bytes. **`munmap_range` 0xb5** `(rd, addr, len)`: page-aligned,
  overflow-checked; partial ranges split a VMA.

### 17.9 The architectural state-stream wire format (`state.open`/`state.import`/`state.commit`, §16.8)

The typed state-stream producer emits this stream and an import builder consumes it. Software may
transport, store, replicate, and write the bytes, but cannot bypass validation: the importer is the
notary and a forged or inconsistent stream fails atomically. The **framing** is frozen
here; the per-section bodies are versioned (catalogued in `isa_spec.json`, §16.6 clause 3), because
they mirror engine state that grows with the architecture — the same discipline as `env_open`
records. **One invariant binds every body version, stated here because the bodies live in the
catalog: the stream is readable by the serializing parent, so §16.7's domain-local-names rule
applies to its contents**. Engine-private identifiers (call-chain IDs, internal donation/routing
records, physical cell identities in `ENGINE_STATE`) are emitted **renamed into stream-local names**,
never as live engine values; import re-mints them. In contrast, every software-visible numeric
reference listed by §16.8 is emitted and restored **bit-for-bit**, even when it appears only in an
engine record, because arbitrary copies may also exist in application memory. Stream-local renaming is
therefore forbidden for capability handles, thread/domain IDs, waitset member IDs, `ActivityRef`s,
lease IDs, and other architected opaque references.

**Stream header, 64 B:** `[0]` magic u64 (`0x4C4E503634444F4D`), `[8]` stream_version u32, `[12]`
flags u32 (bit0 = measured form; bit1 = suspended-time policy; bit2 = `METADATA_ONLY` inspection
stream; bits `[31:3]` reserved-zero),
`[16]` total_length u64, `[24]`
section_count u32, `[28]` **target_revision u32** (the ISA revision whose schemas bound every
section version in this stream; `0` = the producer's own revision — §16.8's decades rule), `[32]` source timebase frequency u64 — **the serializing
caller's *visible* timebase frequency (per its MachineView), never the raw machine fact** (for audit
only; every deadline in the stream is already duration-form), `[40]` **capture_id u64** (fresh and
never reused in the source-object incarnation), `[48]` **source_cut_tick u64** (cut binding and audit
only; a destination must not derive cross-machine elapsed time from it), `[56]` _reserved u64. Then `section_count`
sections, each `{[0] section_type u32, [4] version u32, [8] length u64}` + body, 8-byte aligned.
**Section types (frozen):** 1 `VIEWS` (the five, §16.7 — budgets, explicit service imports, view
transforms), 2 `CAPTABLE` (entries + the **cell graph**: which slots share
which lineage/stamp cells — shape preserved, physical cells re-minted at import with handle-visible
slot/epoch values unchanged), 3 `ADDRESS_SPACE` (VMA
tree + per-backing one of: page contents (subtree-owned), pager references, or the
**external-share relationship** — the §16.8 supply obligation the receiving parent discharges at
import or the import fails), 4 `THREADS` (per-thread: the §17.5 payload-layout context —
one frozen context layout machine-wide — plus scheduler state), 5 `ENGINE_STATE` (importable park,
pending-event, and per-thread signal-alternate-stack state, plus nonimportable `METADATA_ONLY`
cut-activity planning records — **every
absolute deadline exported as cut-time remaining-duration in canonical nanoseconds**, §16.8, with
elapsed subtraction selected by the header policy before import re-absolutization), 6 `CHILDREN`
(nested state subtrees, recursively this same format), 7 `DEPENDENCIES` (external-resource
dispositions and explicit service-import metadata; opaque service bodies travel separately through
§16.5). Type 8 is `OBJECTS` (§17.9a); `9`–`255`
are reserved as type numbers, and **bit31 of `section_type` is the `OPTIONAL` flag**: an importer
that does not recognize an optional section skips it whole; only reconstructible derived or
acceleration state may ride one — truth never travels optional, so a skipped section changes
warm-up, never semantics. Types 1–7 and every flag-clear future type are REQUIRED: unknown means
the import fails atomically.

The former class-specific standalone framings for ClockView, Counter, and CompletionQueue are
retired. Their v1 values use the common `OBJECTS` container and body prefix in §17.9a, like every
other standalone object; no class may reuse VIEWS or ENGINE_STATE as a standalone framing.

**`DEPENDENCIES` v1 body:** `[0] count u32 (=0), [4] reserved u32 (=0)`. V1 has no
free-standing service-continuity graph. External requirements live in the dependency table of the
CAPTABLE or object body that owns the relation, and `state.bind` satisfies those typed references.
Nonzero count is reserved for a future additive revision and is `-UNSUPPORTED`, never silently
interpreted.

Import validates: every §16.0/§2.2/§3 invariant, every bound of §16.4, cell-graph well-formedness, and
view monotonicity against the *receiving* parent — any failure imports nothing.

### 17.9a Complete object-state bodies (S0–S18)

This subsection supersedes the three standalone single-object framings above. Every independently
nameable non-Domain object stream is the 64-byte §17.9 header followed by one section of type
**8 `OBJECTS`**. **Capability (class 12) and Thread (class 13) are Domain-owned state records, not
independently publishable objects:** their complete serialization contracts are respectively the
CAPTABLE and THREADS/ENGINE_STATE sections of S17. `state.open`/`state.import` cannot name either
class on its own; importing class 12 or 13 returns `-UNSUPPORTED`. This ownership exception prevents
a second capability table or detached thread from being published outside its Domain while retaining
the class-level admission and round-trip obligations. A Domain stream also carries one `OBJECTS`
section, between CAPTABLE and THREADS in emission order. The body
of an OBJECTS section is `{count u32, reserved u32}` followed by 8-byte-aligned records:

```text
[0] object_ref u64       [8] object_class u32    [12] body_version u32
[16] body_length u64     [24] body bytes, padded with zeroes to 8-byte alignment
```

`object_ref` is stream-wide unique and 1-based; zero is invalid. Every object body begins with:

```text
[0] object_class u32     [4] lifecycle u32       ; 0 LIVE, 2 POISONED
[8] body_flags u32       [12] dep_count u32
[16] dep_offset u32      [20] reserved u32
```

DESTROYING objects fail FULL capture with `-BUSY`. The dependency table at `dep_offset` contains
`dep_count` 24-byte entries `{dep_ref u64, expected_class u32, disposition u32, detail u64}`.
Disposition 1 INTERNAL names the satisfying `object_ref` in `detail`; 2 REBIND requires a
`state.bind` replacement; 3 OMIT_OPTIONAL may remain absent. INTERNAL dependency cycles are
`-MALFORMED`. `state.bind rd,builder,dep_ref,replacement_cap` checks the expected class, rejects a
second binding of the same requirement as `-MALFORMED`, advances the builder generation, and commit
revalidates its liveness atomically.

All scalars are little-endian. Time values are remaining canonical nanoseconds (`UINT64_MAX` forever,
zero immediate); import re-absolutizes them. Software-visible ids are bit-exact. Engine-private ids
are stream-local renames. View coordinates are capture-parent coordinates and must map into the
receiving parent's view. Unknown trailing bytes are skippable only within an accepted body version;
all fields listed below are REQUIRED. PMU and DebugTarget are NONMIGRATABLE: only mode 3 diagnostic
snapshots are emitted and `state.import` for either class is always `-UNSUPPORTED`.

The complete v1 object-body layouts, after the common 24-byte prefix, are:

| Class | Exact v1 fields and offsets | FULL capture and import predicate |
|---|---|---|
| Counter (3) | `[24] value u64; [32] threshold u64` | atomic word; core predicate |
| ClockView (10) | `[24] anchor_view u64; [32] slew_q32 i64; [40] cut_view_value u64; [48] epoch u64` | atomic; re-anchor at destination now with the monotone cut floor and recheck slew/horizon |
| CompletionQueue (19) | `[24] capacity u32; [28] record_count u32; [32] reserved_slots u32; [36] pad; [40] record_count × 24-byte completion records` | SUBMISSION cut; `record_count + reserved_slots <= capacity` |
| ChannelEndpoint (2) | `[24] type u32; [28] overrun u32; [32] capacity u64; [40] blocking u32; [44] shutdown u32; [48] loss u32; [52] pad; [56] peer_dep u64; [64] queued_count u32; [68] pad; [72] queued variable records {byte_len u32, cap_count u32, slotless 72-byte capability bodies, bytes, pad}` | both directions SUBMISSION-quiesced; queued volume bounded; omitted peer imports half-open |
| Timer (5) | `[24] delivery_kind u32; [28] basis u32; [32] delivery_detail u64; [40] clock_dep u64; [48] realtime_dep u64; [56] place u64; [64] armed u32; [68] slack_log2 u32; [72] remaining_ns u64; [80] view_deadline u64; [88] view_epoch u64; [96] period_ns u64; [104] overrun u64; [112] arm_id u64` | atomic comparator cut; delivery class, physical authority, and view deadline rechecked |
| Waitset (7) | `[24] member_highwater u64; [32] count u32; [36] pad; [40] count × 40 B {member_id,cookie,trigger_flags,retained_ready,target_dep,reserved}` | membership mutation quiesced; ids unique and no greater than highwater; omitted target becomes final-HANGUP dead member |
| EventRing (18) | `[24] capacity u32; [28] pad; [32] backing_dep u64; [40] base_offset u64; [48] produced u64; [56] consumed u64; [64] waitset_dep u64; [72] bind_tid u64` | bound thread at instruction boundary; storage range writable and re-pinned/recharged |
| CallGate (4), v2 | `[24] abi u32; [28] flags u32 (bit0 serialized, bit1 cancel_policy, bit2 SERVED); [32] entry_pc u64; [40] pool_base u64; [48] slot_size u64; [56] slot_count u32; [60] pad; [64] inline_len u32; [68] max_caps u32; [72] submit_bound u32; [76] pad; [80] donation_ns u64; [88] grace_ns u64; [96] two 8-byte borrow declarations; [112] lifecycle_queue_dep u64; [120] pending_count u32; [124] pad; [128] variable pending submissions; dependency table begins at the common prefix's `dep_offset` after the variable records` | live synchronous activation is `-BUSY`; SERVED requires exactly one matching SERVE PARK and is restored as one unpublished relation; a served worker is never serialized mid-handler; seal checks context/inline/stack geometry and the dormant pin recipe |
| DMAWindow (8) | `[24] direction u32; [28] addressability u32; [32] ats u32; [36] device_profile u32; [40] device_dep u64; [48] backing_dep u64; [56] offset u64; [64] length u64; [72] extent_count u32; [76] pad; [80] extent_count × 40 B {iova,backing_offset,len,rights,pad,reserved}` | requires issued=acked, zero transient pins, no inflight submission; for a hardware-bound window `device_dep` is REBIND_REQUIRED and only `state.bind` may satisfy it on import, with replacement profile exactly `device_profile`; for a software-requester window both fields are zero and no Device dependency is invented; `backing_dep` remains required in both forms |
| WorkQueue (14) | `[24] capacity u32; [28] max_desc_len u32; [32] device_dep u64; [40] completion_dep u64; [48] blocking u32; [52] device_profile u32` | drained to REUSABLE_BOUNDARY; `device_dep` is REBIND_REQUIRED and only `state.bind` may satisfy it on import; replacement profile must equal `device_profile` |
| InterruptWaitable (6), v2 | `[24] delivery_mode u32; [28] event_number u32; [32] priority u32; [36] flags u32; [40] place u64; [48] source_dep u64; [56] source_class u32; [60] pad; [64] pending_edges u64` | source is class 20 InterruptSource or class 3 Counter; R24 seal checks rerun; AUTO Counter edge count and EXPLICIT armed state are preserved |
| InterruptSource (20) | `[24] transport_kind u32; [28] pad; [32] provider_cookie u64; [40] descriptor u8[32]` | descriptive diagnostic only; import is `-UNSUPPORTED` |
| PMU (9) | `[24] count u32; [28] pad; [32] count × 24 B {event_id,threshold,value}` | DIAGNOSTIC_SNAPSHOT only |
| DebugTarget (15) | `[24] target_alive u32; [28] watch_count u32; [32] flags u32; [36] pad; [40] count × 32 B {watch_id u64,tid u64,addr u64,len u32,kind u32}` | DIAGNOSTIC_SNAPSHOT only |
| FileDescription (11) | `[24] cursor u64; [32] blocking u32; [36] pad; [40] endpoint_dep u64; [48] reserved u64; [56] reserved u64` | instruction-boundary cursor cut; the endpoint dependency determines post-import usability |
| PagedBacking (17) | `[24] mem_type u32; [28] flags u32; [32] size u64; [40] pager_dep u64; [48] write_generation u64; [56] contents_kind u32; [60] run_count u32; [64] run_count × 32 B {offset,len,blob_off,flags,pad}; then 8-aligned blob` | MEMORY_MUTATION cut; runs aligned, disjoint, in range; JIT arena requires destination JIT_WX authority |
| MachineView (16) | `[24] va_width u32; [28] quantum_shift u32; [32] features u64; [40] counters u64; [48] visible_time_floor u64; [56] eight u64 limits; [120] identity_dep u64; [128] tile_count u32; [132] pad; [136] count × 16 B {child_tile,parent_tile}` | immutable; receiving view must dominate every fact and time is healed from the visible floor |

A CallGate v2 pending-submission record is 8-byte aligned and has `[0] record_len u32;
[4] flags u32` (zero in v2); `[8] activity_ref u64; [16] origin_domain_dep u64;
[24] completion_queue_dep u64; [32] deadline_remaining_ns u64; [40] enqueue_seq u64;
[48] donation_remaining_ns u64; [56] byte_len u32; [60] cap_count u32;
[64] caller_args[7] u64; [120] cap_count × 72-byte slotless capability bodies;` then
`byte_len` inline bytes and zero padding to `record_len`. `UINT64_MAX` means no deadline or
donation bound. Descriptor pointers, detached thread ids, absolute deadlines, and engine-private
chain ids never enter the stream. The capability bodies are exactly the ChannelEndpoint queued-cap
wire bodies; this record does not define a second capability encoding.

The frozen **slotless 72-byte capability body** is the Domain CAPTABLE entry's bytes `[8..80)`:
`[0] rights u32; [4] flags u32; [8] slot_epoch u64; [16] lineage_cell_ref u64;
[24] stamp_cell_ref u64; [32] referent_kind u32; [36] reserved u32;
[40] referent_a u64; [48] referent_b u64; [56] referent_c u64; [64] reserved u64`.
For a queued, uninstalled capability `slot_epoch` MUST be zero; both reserved fields MUST be zero.
The referenced OBJECT or typed dependency uniquely supplies the object class, so the body does not
repeat it. Rights and flags may only narrow the referenced authority. Every nonzero lineage or stamp
cell reference and every referent field MUST resolve in the enclosing stream; import preserves shared
cell identity and never recreates a moved sender slot. An unresolved, widened, dead, or class-mismatched
body makes the whole import fail atomically.

`activity_ref` remains bit-exact. Import remaps `origin_domain_dep`, not the public ActivityRef, and
registers cancellation authority under the restored `{origin Domain, ActivityRef}` pair.
`completion_queue_dep` resolves class 19. An INTERNAL CompletionQueue's serialized
`reserved_slots` already includes the record's reservation and import claims it exactly once; a
REBIND CompletionQueue reserves one live slot per record atomically at commit. Import rejects a
missing relation, duplicate nonzero ActivityRef within one origin, duplicate `enqueue_seq`, a
queue or Gate bound violation, widened or unresolved capability authority, or inconsistent
CompletionQueue reservations. It installs records in finite `deadline_remaining_ns` order then
`enqueue_seq`, with unbounded deadlines last. Remaining deadlines become destination-absolute only
at commit; an expired record selects TIMEOUT and publishes through its claimed reservation before
any callee instruction. Only pre-activation queued submissions use this layout. An admitted or
running detached activation makes FULL capture `-BUSY`.

Capability-table object bodies and Domain CAPTABLE sections share one v1 layout:

```text
[24] capacity u32, entry_count u32, cell_count u32, retired_count u32
[40] cells[cell_count] × 24 B {cell_ref u64, kind u32, flags u32, epoch u64}
[..] entries[entry_count] × 80 B {slot u32, object_class u32, rights u32,
     entry_flags u32, slot_epoch u64, lineage_cell_ref u64, stamp_cell_ref u64,
     referent_kind u32, pad u32, referent_a u64, referent_b u64, referent_c u64,
     reserved u64}
[..] retired[retired_count] × 16 B {slot u32, pad u32, current_epoch u64}
[..] dependencies[dep_count] × 24 B (the S0.3 dependency-table entry)
```

`entry_flags` assigns bit 0 `SEALED`, bit 1 `DROP_ON_REPLACE`, and bit 2
`REFERENT_DEP`; bits 3–31 are reserved-zero. `REFERENT_DEP=0` means
`referent_a` is an internal `object_ref`; `REFERENT_DEP=1` means it is a
`dep_ref`. This discriminator applies uniformly to OBJECT, MEMORY_RANGE,
DOMAIN, and SERVICE referents; the remaining referent words keep their
kind-specific meanings. The dependency table begins immediately after the
retired array, and the common prefix's `dep_offset` must name that byte.

Service-owned entries are external dependencies in v1: `REFERENT_DEP=1`, `referent_a` is the typed
dependency reference, and the dependency's expected class is the service-owned class. Cookie, route,
queue, and stamp identity are deliberately absent; `state.bind` supplies a replacement object.
`stamp_cell_ref`, `referent_b`, and `referent_c` are zero.

Slot/epoch values and the retired list are bit-exact; physical cells are re-minted with graph shape
preserved. Exact slot reservation and delegated-rights closure are commit predicates.

The Domain section bodies are frozen as follows. VIEWS v1 is a 176-byte fixed prefix followed by
the placement tile list: `[0] machine_view_object u64`, `[8] domain_capability_mask u32`, `[12] reserved u32`,
`[16] clock_object u64`, `[24] self_rights u32`, `[28] abi_class u32`, `[32] sched_class u32`,
`[36] measured u32`, `[40] sched_p0 u64`, `[48] sched_p1 u64`, `[56]` four
`{charged u64, ceiling u64}` budget pairs, `[120] startup_metadata_ptr u64`, `[128] cpu_limit u64`,
`[136] memory_limit u64`, `[144] object_limit u64`, `[152] cap_slot_limit u64`, `[160]
placement_limit u64`, `[168] placement_count u32`, `[172] reserved u32`, `placement_count`
view-coordinate tile ids at `[176]`. The word at `[172]` is reserved-zero. The
`startup_metadata_ptr` is the final `dstartup` fact (zero when absent); import revalidates that it
names 32 readable bytes in the imported ADDRESS_SPACE before atomically publishing the Domain.
VIEWS therefore preserves the same `env_open(STARTUP)` personality metadata relation across a
checkpoint rather than inferring a replacement-local default. Capability discovery is preserved
solely by CAPTABLE; VIEWS carries no parallel role manifest. `domain_capability_mask` is the
closed bitmask of Domain-level self-operation classes (`PROCESS`, `MEMORY`, `FDR`, `IO`, `OBJECT`,
and `CALL`); reserved bits are zero and import rejects them. It is preserved independently of
the capability table, so a restored live CallGate cannot be made spuriously unusable by a
silently narrowed caller ceiling. The five admission limits are rechecked as monotone subsets of
the receiving parent's corresponding limits before publication; they preserve the resource
contract that gates creation and calls. ADDRESS_SPACE v1 begins
`{vma_count u32,constraint_count u32,reserved u64}`, then 16-byte constraint
records and 96-byte VMA records `{base,len,prot,mem_type,leaf,mapping_kind,backing_object,
backing_offset,home,growdown,constraint_first,constraint_n,reserved[3]}`.
`mapping_kind` is closed: 0 private materialized backing, 1 object-backed private, 2
object-backed shared, 3 DMA requester-backing.  Kind 3 names the class-8 DMAWindow OBJECT and
`backing_offset` is its IOVA; import restores a live relation to that window, not a byte snapshot,
and revalidates the entire range against its current REMAP generation.  A class-8 CAPTABLE entry's
`referent_kind` is 0 for the control interface and 4 for the requester-backing interface; all other
v1 values are malformed.  Thus state transfer cannot widen the requester facet into DMA control.
THREADS v1 begins count/pad
and has variable records containing record length/state, bit-exact tid, event state, the 32-byte rseq
descriptor, registered stack, scheduler override, clear-tid relation, placement tiles, and an aligned
§17.5 ARCH_CONTEXT. Each record is `{record_len u32, state u32, tid u64, eventmask u64,
eventpending u64, delivery_group u32, delivery_generation u32, rseq[4] u64, stack_base u64, stack_size u64, sched_class u32, pad u32,
sched_p0 u64, sched_p1 u64, clear_tid_ptr u64, placement_count u32, pad u32,
placement_tiles[placement_count] u64, ctx_len u32, pad u32, ARCH_CONTEXT bytes}` with the context
8-byte aligned. `clear_tid_ptr` and every placement tile are REQUIRED state established by
`thread.ctid`/`thread.place`; import revalidates the pointer mapping generation and intersects the
placement list with the receiving Domain's view, failing atomically if either relation cannot be
restored. ENGINE_STATE v1
is count/pad plus 8-byte-aligned TLVs `{kind u32,length u32,body}`, where `length` includes the
8-byte TLV header. The importable bodies and inspection-only planning body are byte-exact:

```text
0 RESERVED (no v1 record; encountering kind 0 is `-MALFORMED`)
1 PARK (length = 72 + 24*operand_count + 8*class_word_count):
  [8] semantic_class u16; [10] version u16 (=1); [12] flags u32 (bit0 EDGE_CONSUMED)
  [16] thread_ref u64; [24] restart_pc u64
  [32] decode u64 (the §17.5 minimal syndrome); [40] orig_rd_value u64
  [48] deadline_clock_ref u64; [56] deadline_remaining_ns u64
  [64] result_reg u8; [65] deadline_reg u8; [66] completion_kind u8
  [67] deadline_state u8; [68] operand_count u16; [70] class_word_count u16
  [72] operand rewrites[operand_count], at most 8, each 24 bytes:
       {reg u8,source_kind u8,reserved u16,reserved u32,source u64,addend u64}
       source_kind: 0 LITERAL, 1 OBJECT_REF, 2 DEP_REF, 3 DEADLINE
  followed by class_words[class_word_count], at most 8, each u64. These are
  validation/reissue facts rather than register rewrites. All classes except
  PAGE_REQUEST carry zero class words in v1. PAGE_REQUEST carries exactly
  `{backing_object_ref, offset, access, captured_designation_epoch}`; import
  validates the restored mapping and rebound provider, then the common reissue
  rule creates and redelivers a fresh request under the destination epoch.
  completion_kind: 0 VALUE, 1 STATUS, 2 BYTE_COUNT
  deadline_state: 0 NONE, 1 ACTIVE, 2 MATURED; NONE requires clock/ref/reg/remaining zero
  semantic_class: 0 FUTEX, 1 WAITSET, 2 RECV, 3 SEND, 4 BYTE_XFER,
                  5 GATE_ENTRY, 6 DOMAIN_JOIN, 7 PAGE_REQUEST,
                  8--9 RESERVED, 10 SERVE; 11--65535 RESERVED
2 CUT_ACTIVITY_METADATA (`METADATA_ONLY` streams only, length 48):
  [8] tid u64; [16] chain_ref u64
  [24] activity_kind u32; [28] frame_depth u16; [30] phase u8; [31] cancel_policy u8
  [32] donation_remaining_ns u64; [40] cleanup_remaining_ns u64
  activity_kind: 0 DOMAIN_CALL, 1 MACHINE_CALL, 2 GATE_CALL, 3 GATE_SUBMIT
  phase: 0 ACTIVE, 1 CANCEL_POSTED, 2 CLEANUP, 3 DETACHED_CLEANUP
  cancel_policy: 0 COOPERATIVE, 1 FORCE
3 PENDING_EVENT (length 40):
  [8] scope u32; [12] pad u32; [16] tid u64
  [24] event_number u32; [28] pad u32; [32] payload u64
  scope: 0 DOMAIN, 1 THREAD
4 SIGNAL_ALT_STACK (length 32):
  [8] tid u64; [16] base u64; [24] size u64
  `base..base+size` is the installed per-thread `sigaltstack` delivery range;
  `size >= MINSIGSTKSZ (8192)`. The range must be wholly writable in the
  imported THREADS Domain's ADDRESS_SPACE or import fails atomically. An active
  handler frame is never exported (`FULL` capture is `-BUSY`), so this restores
  the registration, never `SS_ONSTACK`.
```

All padding is reserved-zero. A CallGate body whose SERVED flag is set and its worker's SERVE PARK
form one import relation: FULL import requires exactly one matching SERVE PARK whose Gate
`OBJECT_REF` names that body, installs the dormant worker binding before publication, and exposes
neither the Gate nor the thread until both are installed. An unserved body has no SERVE PARK. This
makes served mode sticky for the Gate's lifetime and prevents an ephemeral activation from racing
ahead of restored TLS/LWP identity.

`tid`, `activity_ref`, and other software-visible identities are
bit-exact; `chain_ref` is a nonzero stream-local rename. `CUT_ACTIVITY_METADATA` emits one record per
live activity frame crossing the captured Domain/subtree boundary; `frame_depth` orders nested frames
within `{tid,chain_ref}`. `UINT64_MAX` means no finite donation bound. Before cleanup begins,
`cleanup_remaining_ns` is the full grace that would become available if cancellation fired; after
cleanup begins it is the actual cut-time remainder. Kind 2 is valid only when header flag bit2 is set,
is rejected by every import builder, and carries no PC, register, payload, capability, or live engine
identifier. A PARK is the restart recipe for a blocked instruction, never a reconstructed wait-queue
node. Its semantic class validates the completion kind and exact operand-rewrite shape; the rewrite
array materializes receiver-local handles from object/dependency refs and the absolute deadline from
the named imported ClockView. The decoded operation fixes that shape universally: every capability
operand has exactly one `OBJECT_REF` or `DEP_REF` rewrite, a finite deadline has exactly one
`DEADLINE` rewrite, and other nonconstant operands use `LITERAL`; duplicates, omitted operands, and
extra rewrites are `-MALFORMED`. The semantic class must admit the decoded operation. In particular,
SERVE admits only `gate.serve`, requires one Gate `OBJECT_REF`, STATUS completion, and no deadline.
Import restores `gprs[result_reg] = orig_rd_value`, applies rewrites,
sets the saved PC to `restart_pc`, and makes the thread runnable. Re-execution reconstructs waiter
membership and either completes against imported referent state or parks again; no serialized
referent duplicates the waiter link. EDGE_CONSUMED and readiness state otherwise live in the
serialized referent. Post-activation callers are continuation state, not PARKs. A byte transfer with
nonzero progress completes as a short count at quiescence and is never emitted as PARK.

Every catalog operation declares `compiler_semantics.park`. An operation that can block names
exactly one class above or `DRAIN_ONLY`; an operation with neither does not merge. `DRAIN_ONLY`
means the operation must finish or be drained before a FULL cut and therefore emits no PARK; it is
valid for a DRAIN_REQUIRED referent or another explicitly quiesced engine transition, never for an
internal subtree wait. Thus `djoin` on an in-stream child is importable and never makes FULL
capture `-BUSY` merely because it is blocked.

`gate_tail` is `DRAIN_ONLY`, even when it is waiting to enter a serialized target Gate. Before the
tail commit it necessarily retains the departing synchronous activation and its continuation; after
the commit it is an ordinary post-activation call. The migration doctrine above deliberately refuses
both as residual synchronous continuations. Only a pre-activation `gate_call`/`dcall` wait is
`GATE_ENTRY` PARK state. FULL quiescence therefore finishes or cancels a contended tail before the
cut rather than exporting a restart recipe that would have no return continuation after import.

CHILDREN v1 is count/pad plus
`{length u64,nested full stream,pad}`; nested streams share the outer stream's object/dep namespace.
Kind 0's former `CONTINUATION` proposal is retired because `FULL` capture requires
`ACTIVATIONS` quiescence: every live domain or machine call is a cut-crossing activation and makes
the cut `-BUSY`. Kind 2 does not revive the former importable `ACTIVITY` proposal: its record is
inspection-only. Queued CallGate submissions remain in the CallGate body, DMAWindow capture requires
no in-flight submission, and WorkQueue capture requires a drained reusable boundary. Cut-crossing
continuations and active submissions are `-BUSY` for `FULL`; CallGate-body pending work carries
bit-exact public ids and re-reserves completion capacity at import.

The machine-readable `state_schemas` registry is normative transcription of these layouts. Every
serializable class must have exactly one row declaring body version, transfer contract, capture scope,
dependency slots, partial-activity rule, import predicate, and round-trip family. NONMIGRATABLE rows
must not declare an importable layout. Appendix D generates legal field-group variations and includes
adversarial retired-slot and view-deadline-healing cases.

### 17.10 System-op operand map (`0xa0`–`0xce`)

The §1 custom-format rules make these placements deterministic. Every unused register slot and every
unnamed bit is reserved-zero; system opcodes carry no hint zone unless explicitly assigned.

| Opcode(s) | Family/form | Operand rule |
|---|---|---|
| `0xa0`–`0xa8` | gate, endpoint, and wait operations | fixed forms in §9–§10; referenced memory is invocation or transferred data |
| `0xa9` | `cap` | `rd, rs1..rs3`; `func[7:0]`; `rs4,rs5` only where its fixed function assigns them |
| `0xaa` | `domain.build` | `rd, builder/parent, rs2..rs5`; `func[7:0]`; successful mutations return the next builder generation |
| `0xab` | `domain.exec` | `rd, target/activation, rs2..rs5`; `func[7:0]` |
| `0xad`–`0xae` | `readv_at`, `writev_at` | `rd, endpoint, iov_ptr, iov_count, offset`; the iovec is a homogeneous sequence |
| `0xaf` | — | reserved |
| `0xb0` | `gate_tail` | `rd, gate_cap`; registers-only, no descriptor form (§9.2) |
| `0xb1` | — | reserved (retired `free`, Appendix G) |
| `0xb2` | `mem_grant` | fixed form in §11 |
| `0xb3` | `mapping` | `rd, builder/backing, rs2..rs5`; `func[7:0]`; successful builder mutations return the next generation |
| `0xb4`–`0xb6` | `map.protect`, unmapping, and `map.demote` | fixed forms in §11 |
| `0xb7`–`0xba` | PCR, environment, random | fixed forms in §8 and §11 |
| `0xbb`–`0xc8`, `0xcf` | class-specific hardware-object families | `rd, target/builder, rs2..rs5`; opcode fixes class, `func[7:0]` fixes one schema (§17.7) |
| `0xc9` | `device` | `rd, device/builder, rs2..rs5`; `func[7:0]` |
| `0xca` | immutable set | `rd, set/item, rs2..rs5`; `func[7:0]` |
| `0xcb` | cursor | `rd, cursor/source, rs2..rs5`; `func[7:0]` |
| `0xcc` | state transport | `rd, object/builder, rs2..rs5`; `func[7:0]` |
| `0xcd` | observation generation | `rd, subject, generation/class`; `func[7:0]` |
| `0xce` | lifecycle | `rd, typed subject/token, scope/deadline, disposition`; `func[7:0]` |

The opcode/function pair fixes rights, result shape, commit point, ordering, and failure behavior. A
family cannot change an operand's interpretation through a memory value or class-private selector.


## 18. Vector profile (model and v1 op catalog frozen; `0xf6` reserved-additive, `0xf7` opened by `ldff`)

**What freezes now vs later.** Everything a compiled binary or a compiler backend bakes in freezes
**here, now**: the register file, the length model, the mask model, the encoding shape, the ABI, the
continuation-frame rule, the `env_open` geometry surface, **and the v1 op catalog (§18.1) with explicit
function numbers** — a mandated profile with an open op list would be a moving target. Only the named
reserved blocks grow additively (`0xf6` crypto; `0xf7` opened with `ldff` below, its remaining funcs reserved for segment loads and the rest of its named list). The microarchitecture is
unconstrained.

**Conformance: mandatory, one machine (§1).** Optional SIMD bifurcates ecosystems — so it is not
optional: **every conforming machine implements this section in full**, compiled userland assumes
it unconditionally, and no dispatch trampoline exists anywhere in the software stack. The
`FEATURES` bit is a **view grant** (§16.7): a parent may withhold the vector unit from a domain
(executing a vector op without the grant raises the disabled-opcode fault, §9.3 — the view-denial
surface, same as FP §14), and no binary ever ships compiled against the withheld shape, because
no physical machine lacks it.

**Role — the closed consumer charter (admission-rule-grade, like §16.2's merge doctrine).**
Bulk `memcpy`/`memset` at DMA scale belongs to the DMA copy path (§15). The vector profile
exists for **the datacenter tax and the parallelism compilers find — and nothing else**:
`memcpy`/`memmove`, `memcmp`, `strlen`/`memchr`, UTF-8 and format validation, hashing and
checksums, compression, (de)serialization and JSON/protobuf-class shredding, and every loop/SLP
shape a production vectorizer finds in ordinary code. **Throughput data-parallelism —
inference, GEMM-class, media transcode, streaming — is an attached-engine workload behind gates
(§15), permanently.** Two standing rules bind future revisions: **(1)** a new vector op must
name its consumer in the charter list — an op whose best argument is throughput is refused, not
deferred; **(2)** VLEN growth requires a charter consumer unserved at the established
execution-VLEN range.

**And the charter has one client: the compiler.** This ISA supports compiler-emitted vector
code only — GCC/LLVM's default pipelines (loop/SLP vectorizers, loop-idiom recognition, builtin
expansion). A vector op exists iff **its workload is in the charter list AND both GCC's and
LLVM's default pipelines vectorize the loop/IR shape it lowers** — the **intersection rule**;
`completeness_inversions.md` table 2 is the admission universe. The shape test's precise form:
the op is *this target's* lowering of a shape both pipelines vectorize; target hooks this
backend sets (the tail-folding preference) count as the default pipeline, and a lowering
mechanism one compiler lacks (GCC's peeling-based early-break path uses no fault-first load)
does not delete an op serving a shape both vectorize. **No hand-written-vector surface exists
or is promised**: the psABI commits to no stable vector intrinsics header, and no op is
admitted for a human consumer. The falsifiable bet: **the charter workloads are reachable from
portable C** (rationale and priced consequences: `workload_fit.md`).

**State.** 32 vector registers `v0`–`v31`, each **VLEN** bits; **16 mask registers `m0`–`m15`**
(the SVE-shaped split: the 3-bit governing-mask field below names `m0`–`m7`, while every
mask-*writing* or mask-*manipulating* op — the compares, the whole `v.mask` family, the `mmv`
transfers — names all sixteen through its ordinary 5-bit register slot, so `m8`–`m15` are
loop-carried-predicate and mask-compute space that never costs a spill) (VLEN/8
bits each). **Mask bit ↔ lane mapping (frozen — ABI):** mask bit `i` governs **lane `i`** at the
operation's element width, regardless of that width (element-index-packed, *not* byte-granular): an i32
op over VLEN=128 uses mask bits 0–3, and bits above the active lane count are ignored on read and zeroed
on write by mask-producing ops. One convention everywhere — mixed-width loops index masks identically at
every width, and `mpopc`/`mfirst` mean the same thing at every element size; the
memory image of a mask register (in the §17.5 vector region and `mmv` transfers) is this packed form,
LSB = lane 0. A machine has a **maximum physical VLEN** (`power of two, >= 128`). Each domain's
MachineView fixes an **execution VLEN**, also a power of two from 128 through that maximum, reported by
`env_open GEOMETRY`; all vector instructions and context sizes use that execution value. Ordinary full
views use the physical maximum. Supporting every narrower power-of-two execution VLEN is mandatory so
a wider destination can preserve a migrated domain's geometry; this is immutable view geometry, not a
mutable `vtype` or VL register. Code remains **vector-length-agnostic**: the same binary runs at any
execution VLEN.

**Encoding: stateless, self-describing.** A vector op whose meaning depends on a CSR written 200
instructions earlier is exactly the mode-bit overloading this design bans; the 64-bit word can afford
the truth inline. **One uniform layout, exact bits, all of `0xf0`–`0xf5`** (registers: `vd[55:51]`,
`vs1[50:46]`, `vs2[45:41]`, `vs3[40:36]` for three-source ops — GPR/FPR operands per op occupy the same
slots; vector ops define **no hint zone**):
- **`func[35:30]`** — the function within the major opcode (**explicit numbers in §18.1**);
- **`etype[29:27]`** — `0` i8, `1` i16, `2` i32, `3` i64, `4` f16, `5` bf16, `6` f32, `7` f64;
- **`mask[26:24]`** — the governing mask, `m0`–`m7` only (meaningful only when `mzp` != 0; all
  sixteen mask registers are reachable as operands/destinations of mask-writing ops through their
  5-bit register slots);
- **`mzp[23:21]`** — `0` unmasked (mask field reserved-zero), `1` merge, `2` zero, `3` inverted-merge,
  `4` inverted-zero, `5`–`7` reserved;
- **`rm[20:18]`** — FP ops, §14 semantics; reserved-zero on integer ops;
- **`x[17]`** — operand 2 is a scalar (GPR for integer etypes, FPR for FP etypes) in the `vs2` slot;
- **`[16:14]` + `[13:0]`** — the **per-family area**, pinned below; reserved-zero where a family defines
  nothing.
Every instruction is a pure function of the word and register state — stateless decode, clean formal
semantics, no hidden configuration. Mask *pressure* is why there are 16 mask registers — eight
governing, eight more so `whilelt` chains, loop-carried predicates, and mask temporaries never
force a mask spill.

**Loop model: predicates, not a length register.** Strip-mining uses `whilelt`-class ops — materialize
into a mask register the predicate `element_index < remaining_trip_count` (GPR index, GPR bound) — and
loops are governed by masks end-to-end. No mutable VL state to save, restore, prove, or leak across a
gate.

**The scalable-ABI ops (`0xf7` funcs 1–3) — because "mandatory VLA" and "no efficient scalable
addressing" cannot coexist, and this document briefly asked them to.** A vector-length-agnostic
binary must increment loop indices by the vector length, size runtime frames that spill vector
registers, and address scalable stack objects — and `env_open GEOMETRY` is a reflection op, not an
addressing mode: requiring every function prologue to load a process-global and synthesize scaled
arithmetic would have been the freeze-blocking compiler-target bug the review named. Three
instructions close it (GPR-result ops in the vector opcode space, using the §18 uniform slots —
result GPR slot-named in `vd`, source GPR in `vs1`; they read no vector state):
- **`cntvb rd`** (func 1): `rd` = **VLEN in bytes** (the `rdvl`/`vlenb` fact; a mask register's
  spill size is this ÷ 8, one `srli`);
- **`cntve rd {etype}`** (func 2): `rd` = **lane count at the encoded element width** (`VLEN /
  8·ebytes` — the `cntw`/`cntd` family collapsed into one op, since `etype` already names the
  width);
- **`addvl rd, rs1, imm`** (func 3): `rd = rs1 + sext(imm17) × (VLEN/8)` — the per-family area
  `[16:0]` carries the signed multiple (±64Ki vector registers of reach; SVE's `addvl` offers
  ±32), so frame allocation, scalable-slot addressing, and index increment are each **one
  instruction**. The spill/fill idiom is `addvl` then unit-stride `vl`/`vst` at the computed
  base; an implementation may execute that adjacency as one VLEN-scaled-offset access under the
  general cracking license (§4.3), so the "preferably scaled load/store addressing" form exists
  without a fourth opcode and without any architected pair.
All three are pure functions of an implementation constant — no state, no mode, trivially
rematerializable (a compiler may treat them as constants after the first execution; they exist as
instructions so the *binary* never bakes VLEN in). This is the complete `rdvl`-class kit; with it,
VLA is a real compiler target rather than a mandate with a missing prologue.

**Memory ops** (all obeying §5/§9.1 semantics **per element**, with precise reporting — a faulting
element's index rides the existing `decode`/`fault_addr` machine-call payload §17.5): unit-stride,
**masked** (mandatory — predicated loops are the model), strided, and **gather/scatter**
(architecturally present even if early implementations microcode them slowly). **Fault-only-first is
landed, not deferred — because in this model its one awkwardness dissolves** (`v.ff` 0xf7, func
`0 ldff`). The precedent templates made fault-first awkward by writing a *length register* (RVV's
`vl`), and this ISA has no mutable VL to write — so the result goes where every result goes: **a
GPR.** `ldff vd, (rs1), rd'` (count GPR slot-named in `rs2`, the `sd.q` precedent; element
size/sign/mask fields as `vl`): elements load from the base until the first faulting element; on a
fault at element `k > 0`, **no fault is taken** — lanes `[0, k)` hold data, lanes `[k, VLEN)` are
**zero-filled** (defined, per house rule), and `k` is written to the count GPR; a fault at element
`0` faults normally (the progress guarantee — a loop cannot spin on `k = 0`). No state, no VL, no
mode: count-in-a-GPR composes with the mask model directly (`whilelt(i + k, n)` is the next
iteration's mask), and the `memchr`/`str`-validation shape — the single most-executed SIMD pattern
in string-heavy ecosystems — runs at full width to the true boundary instead of in its conservative
page-checked form. Stores have no fault-first form, deliberately: a store that half-happens is a
commit-atomicity question, not a speculation question, and `whilelt` already bounds store tails
exactly.

**Deliberately excluded** (each additive later if ever justified): **LMUL register grouping** (an
encoding-scarcity workaround — the 64-bit word has no such scarcity, and grouping complicates renaming and spill sizing),
segment loads, and the scaled/rounding **fixed-point** legacy family (plain *saturating* add/sub are in
the catalog — codecs need them; the scale-and-round machinery stays out).

**ABI + gates (freeze-now).** All vector and mask registers are **caller-saved — deliberately
and permanently** (a callee-saved scalable subset would put VLEN-parametric save obligations
into every continuation frame, unwinder, and `setjmp` for all code). **The named seam:** a
future opt-in intra-domain `vector_cc` call-site variant is a psABI addition and **may never
alter gate-crossing, continuation-frame, or scrub semantics** — nothing else may claim that
meaning. The §17.7 `GPR_FPR_VECTOR` class changes none of this: it authorizes vector
*execution* inside the activation, never vector state *crossing* — boundary-identical to
`GPR_FPR` (psABI gate-interface ABI: a vector-shaped argument is a slice over a window or the
inline area), so no class uses vector registers at the boundary and the closed
`enums.callgate_abi` set means none silently appears. The gate rule: **vector state is always
scrubbed across `gate_call`/`gate_return`**; nothing vector-shaped crosses a protection
boundary. **The scrub binds the observable, never the construction (Appendix E):**
ownership/clean tags, lazy zeroing, and physical renaming all conform, provided a
post-crossing read returns the architected scrubbed value and no cross-boundary residue is
observable under the §2.1 speculation contract.

**Continuation frame (freeze-now).** The §17.5 payload flags word defines **`VEC_PRESENT` = 16**:
when set, a vector region follows the FP region, sized `32 × VLEN + 16 × VLEN/8` bits. Like FP,
an implementation may fill it lazily; the flag and placement rule are the frozen part. A
gate-heavy caller using vector state in bursts re-warms vector context per boundary; the
mitigation is the conditional save (clean vector unit = no region, no cost), and a persistent
cross-gate vector context is **deliberately not reserved** — warm register state carried across
a trust boundary would be a covert-channel generator with a performance excuse.

**Matrix state (the position, stated; the alternative, reserved).** This architecture's answer to
tile-register matrix compute is **an attached matrix engine as a device-backed domain** — reached by
gates and WorkQueue endpoints (§15), with completions and budgets, holding **no per-thread architectural
state** — not tile registers bolted into every CPU context (which inflate every context switch,
continuation frame, and WCET bound for all software whether it does matrix math or not). Nevertheless,
per the name-the-seam doctrine: payload flag **`MAT_PRESENT` = 32** and a frame region slot after the
vector region are **reserved** for a hypothetical future tightly-coupled matrix profile, so if profiling
ever overturns the position, the seam exists and nothing else may claim the bit.

**Realtime.** Vector ops are ordinary **fixed-latency-class** instructions (§1's latency taxonomy):
bounded per-op, no engine, no blocking, nothing crossing a domain. Admissible on RT paths with no new
machinery; gather/scatter WCET is per-element bounded.

### 18.1 The v1 op catalog (frozen, with explicit function numbers)

The catalog is complete here — deliberately the intersection of what a production vectorizer actually
emits with the proven predicated-VLA subset; everything else is named in the reserved blocks. **The
`func` numbers below are the frozen encoding** (nothing is defined by listing order or an external
file). Per-lane semantics are the scalar sections' semantics element-wise: §4 non-trapping division, §14
rounding/canonical-NaN/`NV` rules, all lanes independent. Every op is fixed-latency-class; nothing
blocks, faults imprecisely, or touches hidden state. `x` marks ops with the scalar-operand-2 form.

**`0xf0` `v.int`** (dest `vd` unless noted; all take `x`):
`0 add`, `1 sub`, `2 rsub` (x: `scalar − lane`, gives `neg`), `3 mul`, `4 mulh`, `5 mulhu`, `6 div`,
`7 udiv`, `8 srem`, `9 urem`, `10 and`, `11 or`, `12 xor`, `13 andn`, `14 min`, `15 max`, `16 minu`,
`17 maxu`, `18 sll`, `19 srl`, `20 sra`, `21 rol`, `22 ror`, `23 abs`, `24 clz`, `25 ctz`, `26 popcnt`
(zero-input rules per §4.2, per lane), `27 sadd`, `28 ssub`, `29 uadd`,
`30 usub` (saturating — first-class vectorizer outputs in both pipelines: LLVM's `*.sat`
canonicalization and GCC's `.SAT_ADD`/`.SAT_SUB` pattern recognition; the
"fixed-point legacy" exclusion means the scale-and-round family, never these), `31 wcvt.b`,
`32 wcvt.t` (integer widen; sign bit per the width-change rule), `33 ncvt.b`, `34 ncvt.t` (truncating
narrow), `35 cmp` (cc subfield; **dest is a mask register**). `36`–`63` reserved. There is
deliberately no lane-wise carry-less multiply (the intersection rule; the CRC story is the
scalar §4 `clmul`/`clmulh`, which both pipelines' idiom recognition targets).

**`0xf1` `v.fp`**: `0 fadd`, `1 fsub`, `2 fmul`, `3 fdiv`, `4 fsqrt`, `5 fmin`, `6 fmax` (2019
propagating, §14), `7 fminm`, `8 fmaxm` (minNum/maxNum, §14 — without the per-lane form, C `fmin` loops
would undercut the coverage claim), `9 fmadd`, `10 fmsub`, `11 fnmadd`, `12 fnmsub` (three-source),
`13 fabs`, `14 fneg`, `15 fcvt.f2f` (§14 pairs, per lane — width-changing, so `.b`/`.t` only),
`16 fcvt.f2i`, `17 fcvt.i2f` (**equal element width in the base form** — `f32↔i32`, `f64↔i64`,
exact-saturation per §14 — **plus the two
hot mixed-width pairs under the width-change rule below**: a nonzero `dt[16:14]` selects `fcvt.f2i.b/.t` — `f64 → i32` only, the
truncating narrow with §14 exact saturation — and `fcvt.i2f.b/.t` — `i32 → f64` only, the exact
widen; `dt = 0`, the all-zero `[16:13]` v1 encoding, remains the equal-width form, so existing
encodings are untouched, and any other `dt`/`etype` pair is reserved → illegal-instruction. This
deletes the convert-then-shuffle round trip from the single most common mixed-width FP loop
shape, `double` accumulation over `int` data and its inverse), `18 fround` (to-integral, `rm`),
`19 fcmp` (quiet `eq`, quiet `ne`, quiet `uo`, signaling `lt`/`le`, §14 `NV` rules; **dest is a
mask register**). `x` forms throughout. `20`–`63`
reserved. **Half formats are convert-only lane types** (§14's storage-only rule, mirrored):
`etype` f16/bf16 is legal **only** as a `fcvt.f2f` source or destination — every other `v.fp`
func at a half `etype` is reserved → illegal-instruction. **No half-precision arithmetic
exists anywhere on this machine**, scalar or vector: half is storage, f32/f64 is compute. Reciprocal/rsqrt *estimates* are **excluded-named** (their precision/timing contracts belong
with a future revision, not half-frozen now).

**The width-change rule (lane correspondence, frozen — VLA with no LMUL needs it stated):** every
register-form op whose destination element width differs from its source's comes **only** in `.b`/`.t`
variants. Widening (2×): `.b` converts source lanes `[0, L/2)` and `.t` lanes `[L/2, L)` (the source
half selected fills every destination lane). Narrowing (½×): `.b` writes destination lanes `[0, L/2)`
from all source lanes and leaves `[L/2, L)` to the `mzp` policy; `.t` writes the top half symmetrically.
Covers `fcvt.f2f`, `wcvt.*`, `ncvt.*`, and the width-changing `fcvt.f2i`/`fcvt.i2f` forms. Same-width ops are unrestricted.

**`0xf2` `v.mem`**: `0 vl`, `1 vs` (unit-stride load/store), `2 vls`, `3 vss` (strided; stride in a
GPR), `4 vlx`, `5 vsx` (gather/scatter; index vector + 2-bit scale, base GPR). `6`–`63` reserved. All
masked by the mask field (unmasked code = full). The **memory-element-size field + sign bit** gives
extending loads and truncating stores (memory width <= lane width: load `i8` straight into `i32` lanes)
— mandatory for real autovectorization. Per-element §5/§9.1 fault semantics with the faulting element
index in the machine-call payload.

**`0xf3` `v.mask`**: `0 whilelt`, `1 whilele` (the `u` bit gives unsigned forms): GPR index × GPR bound
→ mask (the strip-mining primitive); `2 mand`, `3 mor`, `4 mxor`, `5 mandn`, `6 mnot`; `7 mpopc`
(→ GPR), `8 mfirst` (index of first active, −1 if none → GPR), `9 mtest` (any active → GPR 0/1);
`10 mmv.m.x`, `11 mmv.x.m` (GPR bitmask ↔ mask register — **defined as the low 64 mask bits exactly**:
`mmv.x.m` reads bits `[63:0]`, `mmv.m.x` writes them and zeroes the rest, so the pair is total at any
VLEN but is not a spill mechanism past VLEN = 512); `12 mmv.v.m`, `13 mmv.m.v` (the **full-width
spill/fill pair**: mask register ↔ the low VLEN/8 bits of a vector register, packed image as defined in
State), after which an ordinary `vl`/`vs` moves it through memory; `14 whileltc`, `15 whilelec`
(the **counted while** — the `u` bit as for funcs 0/1): the func-0/1 predicate written to the
mask destination **and** the active-lane count written to a **GPR named in the `vs3` slot**
(`[40:36]`, the `stx` slot-naming precedent). Pinned exactly: **the GPR result is
`mpopc` of the produced mask** — a count, never a boolean flag — zero-extended, equal to
`clamp(bound − index, 0, lanes-at-etype)` by the func-0/1 prefix-mask semantics; **zero active
lanes (index at or past the bound) write an all-false mask and count 0**, the loop-exit value,
with no fault and no special case. `bne count, r0` consumes it as nonzero-iff-any; arithmetic
consumers (`index += count` remainder loops) get the exact popcount — the two uses read one
result. One op — a governed loop's backedge collapses from `whilelt; mtest; bne` to `whileltc; bne`, 8 bytes
and one dependency off every tail-folded loop's critical path (SVE's flag-setting `whilelt`
translated into this machine's no-flags idiom). This is a genuine two-result primitive, not an
adapter over funcs 0/1 + 7/9 — the two-result shape is precisely what no adapter can express
(§16.2) — and the second result is an ordinary GPR write (the §1 two-result form), not a wider
vector port. `16`–`63` reserved.

**`0xf4` `v.perm`**: `0 splat.x`, `1 splat.f` (GPR/FPR → all lanes), `2 sel` (`vd = mask ? va : vb` —
the vector `sel`; `vmv` is its unmasked alias), `3 insert`, `4 extract` (lane index in a GPR; data GPR
or FPR by etype), `5 slideup`, `6 slidedown` (by GPR element count — the vectorizers'
splice/recurrence shape), `7 zip1`, `8 zip2`, `9 uzp1`, `10 uzp2` (interleave/de-interleave:
AoS↔SoA), `11 revlanes` (reverse lane order), `12 revb` (byte-reverse within each lane — vector
`bswap`), `13 tbl` (per-byte table lookup, single source — its admission story under the compiler-only
clause is the lowering of constant `shufflevector` masks beyond the named idioms, not
hand-written S-box art), `14 vid`
(write each lane its own index). `15`–`63` reserved. There is deliberately no compress/viota
pair (the intersection rule: filter-loop compress-store is not a shape either default pipeline
vectorizes; the if-converted masked-store form is the lowering, and the pair returns through
reserved space if both pipelines land the shape).

**`0xf5` `v.red`** (reductions and partial reductions): `0 red.sum`, `1 red.min`, `2 red.max`,
`3 red.minu`, `4 red.maxu`, `5 red.and`, `6 red.or`, `7 red.xor` — accumulate across active lanes into a
**GPR** `rd`, `sum` always accumulated at 64 bits (no width-overflow surprise); `8 fred.osum`
(**ordered** — strict lane-order association, bit-reproducible), `9 fred.sum` (any association — faster;
deterministic for a given implementation + VLEN but not portable-bit-identical; emitted only under
fast-math); **both NaN disciplines, matching the scalar profile** (a vectorizer has both propagating and
number-returning reduction intrinsics; each needs a direct lowering or the coverage claim fails):
`10 fred.min`, `11 fred.max` (**IEEE-2019 propagating** — any NaN among active lanes yields the
canonical qNaN), `12 fred.minm`, `13 fred.maxm` (**minNum/maxNum** — NaN lanes skipped, all-NaN yields
the canonical qNaN), all → FPR. `14`–`63` reserved. **There is deliberately no dot-product
family** (the Role charter: dot products' consumer is CPU-side inference, an attached-engine
workload, §15). The composed lowering, stated so no one calls it a gap: a dot-product idiom
lowers as widening multiplies (`wcvt`/extending loads + `mul`) feeding `red.sum`/`fred.sum`; a
port whose profile shows that path hot has found an attached-engine workload, not a missing
vector op.

**`0xf6` — reserved, named: the crypto block** (AES round ops, SHA compression, GHASH/`clmul`-based
widening). Additive **only if a default compiler pipeline learns to emit these shapes** (crypto
idiom recognition) — an intrinsics-only consumer is no consumer under the Role charter's
compiler-only clause, so this block may stay reserved forever; `clmul` in `0xf0` already covers
compiler-reachable CRC.
**`0xf7` `v.ff`** — func `0 ldff` (fault-only-first unit-stride load, above); the **scalable-ABI
ops** (above) — func `1 cntvb` (VLEN in bytes → GPR), func `2 cntve` (lane count at `etype` →
GPR), func `3 addvl` (`rd = rs1 + sext(imm17) × VLEN/8`, per-family area `[16:0]`); funcs `4`–`63`
**reserved**: segment/structure loads, **element-granular runtime permute** (excluded from v1 because a
variable full-width element crossbar is the single most expensive permute structure, and
`zip`/`uzp`/byte-`tbl` cover the common shuffles; a variable element shuffle
meanwhile lowers via byte-index expansion of `tbl`), and any vector-call-ABI extension ops. Nothing
else may claim these blocks.

**Per-family field area (`[16:0]` of the uniform layout), pinned:**
- *memory ops (`0xf2`)*: `mes[16:15]` memory element size (same code points as `etype`'s low sizes; must
  be <= the register element size), `msign[14]` (extending loads: sign/zero), `scale[13:12]`
  (gather/scatter index shift), `[11:0]` reserved-zero;
- *compares (`cmp`/`fcmp`)*: `cc[16:14]` (int: `0` eq, `1` ne, `2` lt, `3` ge, `4` ltu, `5` geu; FP:
  `0` eq, `1` ne — quiet, true on unordered (the IEEE/LLVM `une`, C's `!=`), `2` lt, `3` uo —
  quiet unordered test, `6` le — others reserved. With `mnot` and operand swap every LLVM `fcmp`
  predicate lowers in ≤ 2 ops **except the rare `one`/`ueq` pair** — two compares plus one mask
  op, stated here so no one calls it a gap later; the self-compare `x==x` unordered idiom is
  gone);
- *width-changing ops (`wcvt`/`ncvt`/`fcvt.f2f`, and the `fcvt.f2i`/`fcvt.i2f` width forms)*:
  `dt[16:14]` destination element type (`etype` encodes
  the source), `bt[13]` (`0` = `.b`, `1` = `.t`), `[12:0]` reserved-zero;
- *`whilelt`/`whilele`/`whileltc`/`whilelec`*: `u[16]` unsigned compare (LLVM's
  `get.active.lane.mask` is **unsigned** — LangRef `icmp ult` — so its lowering is the `u`
  form);
- everything else: `[16:0]` reserved-zero.

**Coverage claim (checkable):** every IR shape a production loop/SLP vectorizer emits for integer/FP
loops — arithmetic, compares + select, min/max/abs, extending loads / truncating stores, masked
load/store/gather/scatter, splats, insert/extract, the common shuffle lowerings, **the `v.red`
reductions enumerated above** (add/min/max/minu/maxu/and/or/xor and the FP set — a
*product* reduction is deliberately not among them: no hardware multiply tree, anywhere; it lowers
as log₂(lanes) `uzp`+`mul` halving, the one named composed reduction; and a dot-product idiom
is likewise not among them — an attached-engine workload under the Role charter, lowering as
widening multiplies feeding `red.sum`/`fred.sum`, stated at `v.red`), and tail-folded loops via
`whilelt` — has a direct instruction above, with no mode state anywhere. That is the definition of
done for v1, and `completeness_inversions.md` is the standing inversion of it: no known
vectorizer-emitted shape is unassigned (`get.active.lane.mask` lowers to the `u` form —
unsigned per LangRef; every `fcmp` predicate lowers per the `cc` field note, `one`/`ueq` as the
named composed pair). The backend is the final witness — Appendix D derives the per-predicate
tests.

## Appendix B: the honesty ledger (deliberate irregularities, each priced)

Every deliberate irregularity that is not fully self-evident at its definition site, with its
reason and its price. If a shape is not derived from a law, not declared where it is defined,
and not in this list, it is a bug in the document. **The admission discipline: a true wart — a
defect whose cure is affordable — may never be ledgered; before deployment every cure is
affordable (entry 16's precedent), so it must be fixed instead.** What earns an entry is
therefore never a defect, and an entry that merely restates a rule already stated at its
definition site earns nothing. Entry numbers are stable labels; the sequence is not dense.

6. **Futexes transfer no donation; serialized gates do** (§6, §9.2): ownerlessness is what makes the
   uncontended futex one memory access; the engine cannot inherit through an owner it cannot see. The
   RT-mutex rule is stated at the top of the futex section so it is learned before production.
14. **`sltiu` sign-extends then compares unsigned** (§1): kept — but on a mechanism reason, not
    the inherited-compatibility one (which the argument-register precedent, item 16, rightly
    devalues: compiler-source familiarity never outranks semantics in an undeployed ISA).
    Sign-extension makes the 32-bit immediate reach *both* ends of the unsigned range — small
    constants `[0, 2^31)` **and** the top constants `[2^64 − 2^31, 2^64)` — so unsigned compares
    against `~0 − k` shapes (top-end limit checks and `-errno`-style boundary tests) are one
    instruction, while zero-extension would reach only the bottom half. The asymmetry is the
    feature; the RISC-V inheritance is a coincidence.
16. **Argument registers are contiguous (`r2`–`r9`), and the rule the layout encodes**
    (§2): the tempting alternative keeps a thread pointer inside the argument block — splitting
    the arguments — "because renumbering breaks every existing test vector." That is a freeze
    rationale that is only sound once deployed binaries exist; before deployment it is refused
    on the standing precedent this entry records: *provisional artifacts never justify a
    permanent scar* — the cost of a pre-deployment fix is regenerating tests, and tests are
    regenerable by definition. So `tp` is `r30` and the ABI has eight contiguous argument
    registers.
20. **No lock-word format is architected** (§6): the machine defines no PI/robust futex word —
    reserved ABI without an active primitive is refused, so the futex word is the personality's
    entirely. The RT mutex is the serialized gate (heavier than a lock word, and inheriting); any
    future futex-class mechanism arrives whole through the Appendix G `FUTEX_EXTENSION` seam,
    never format-first.
23. **The page size is frozen, architectural, and one: 4 KiB** (`PAGE_SIZE` = 4096;
    `LARGE_LEAF_SIZE` = 2 MiB = 512 pages). It is deliberately not a machine-variable ABI choice:
    fine-grained COW, charging, pager traffic, small mappings, and compatibility outweigh the TLB
    reach of a larger base page for this machine. Translation coalescing and the explicit 2 MiB leaf
    recover reach for large mappings without imposing larger allocation and copy granularity on every
    mapping. `env_open` reports the constant for interface uniformity; changing it requires an ISA
    revision (§1), not a different conforming machine profile. **And the freeze binds the
    *observation* granule, never the management granule:** 4 KiB is the architectural unit of
    protection, partial unmap, dirty observation, pin/lease naming, and charge *visibility* — what
    a program can name and see. How the machine *represents* that state is Appendix E's
    page-metadata license: extent-level charge records, multi-size resident folios, hierarchical
    dirty tracking, sparse pin/lease tables, coalesced reverse-map anchors, automatic promotion
    with lossless demotion (`map.demote` is the architected witness), and metadata cached or
    spilled independently of data are all conforming, provided every observable stays page-exact.
    The priced quantity is therefore the **unavoidable dense per-frame metadata**, and the budget
    has a capacity-independent form: at 4 KiB, one percent of DRAM is **40.96 B per frame** — the
    pre-freeze audit bounds the dense bytes, the sparse bytes per *participating* frame, and the
    hot-metadata bandwidth separately, because at tens of TiB even one percent is hundreds of GiB
    and the access topology matters as much as the total.
24. **No shared virtual addressing in v1** (§15): accelerators work in iova windows; SVA waits on the
    PRI seam, whose CPU-side shape (`PagedBacking`) is already architected.
25. **The in-band reserved values, criterion stated and list closed** (§6, §8.1, §15): an in-band
    reserved value is admissible only when it is **provably outside the operand's legal set** and
    declared where the operand is defined. The sanctioned instances are `AbsoluteDeadline`'s typed
    sentinels (`0` = immediate/poll, `UINT64_MAX` = forever; the counter-lifetime theorem ensures
    neither is a finite returned tick) and `REMAP`'s `UNMAPPED` backing offset (reserved
    *definitionally* in every revision, §15), and the **gate return sentinel** (§9.2: the pinned
    non-canonical `ra` value `0xFFFF_FFFF_FFFF_FFF8` whose fetch executes `gate_return`; provably
    outside the legal code-address set, recognized ahead of the non-canonical fetch fault). Duration, grace, delay,
    timeout, and period operands
    retain their own type-specific zero rules; they do not inherit the deadline sentinels. A proposal
    that cannot prove exclusion gets a flag, not a magic value.
26. **`GATE_INLINE_MAX`-class floors are minima, not constants** (§16.4): a guaranteed floor with a
    queryable actual is the only way to bound WCET without freezing roadmap-scaled capacities into the
    ABI.
27. **Arbitrary assembly is testable, not certified by machine conformance** (§6, Appendix D): the
    litmus family binds conforming hardware, the toolchain, and the reference model. The emulator's
    weak mode lets authors test hand-written assembly, but a machine-conformance result cannot prove
    the correctness of every external binary. That ecosystem obligation is outside the ISA theorem.
29. **Cross-backing dedup (KSM-class) is refused, not missing** (§15): merging identical pages
    across backing lineages would be a cross-tenant COW timing channel (the classic dedup
    side-channel) *and* a second source of truth about frame identity. The architected dedup is
    sharing a backing — one file backing, many mappers, one frame. Anonymous-memory dedup across
    tenants is the one memory-management verb this machine deliberately cannot express.
30. **Register-death coverage stops at the formats that have hint zones** (§12): loads, stores, and
    branches carry kill bits; ALU R-format does not — its low bits are the subformat home and the
    opcode-growth reserve, where reserved-zero faults, and hints must never live where a fault
    lives. The priced concession: last-use-at-ALU-op goes unmarked unless the compiler sinks the
    death to the next memory/branch site or spends a `kill` idiom (§12) — the minority case, paid
    knowingly, and the R-format reserve stays whole.
31. **Memory coloring is reserved by name, not designed — and until it is designed, nothing may
    cite it** (§5, §6, §11.2, §15): an MTE-class facility needs a complete definition of color
    storage, pointer representation, allocation and reuse, checking granularity, faults, DMA, COW,
    serialization, and view policy. No security or compiler theorem may depend on it until that
    definition exists. The constituencies remain explicit: intra-domain temporal bugs in unsafe or
    foreign code, sanitizers, and concurrent relocating collectors. V1 permits same-backing heap
    aliases: they retain one physical-location identity, one futex key, compatible memory types, and
    backing-wide W^X. That is an available software substrate, not an architected guarantee that a
    particular colored-pointer or GC algorithm is correct; it costs virtual address space and
    explicit software barriers. The priced refusal is the absence of a universal per-load hardening
    tax, not a claim that software without coloring is bug-free.
32. **Capabilities are boundary technology; v1 intra-domain hardening is deliberately limited**
    (§2.2, §5, §7): within a domain, heap pointers are raw untagged `u64`s by design —
    the engine never sees an ordinary dereference, so use-after-free of a *pointer* (not a
    handle), sanitizer shadow state, and heap temporal safety for unsafe code remain software
    problems inside the boundary, exactly as the §3 crossbeam paragraph already concedes for
    reclamation. The honest inventory of what v1 does *not* provide: no pointer-authentication-class
    control-data protection (return addresses and vtables are ordinary data in domain memory;
    forward CFI covers compiler-selected indirect calls through `jalr.cfi`/`lpad`, but not arbitrary
    intra-domain control-data corruption), no MTE-class coloring until B31's
    section exists, and no architected stack probe (stack growth is conventional: guard VMAs at
    4 KiB page granularity, the probe discipline is the psABI's — one probe per page, the
    ordinary discipline, not a new mechanism). This is a *scope*
    decision, not an oversight: the machine spends its enforcement transistors on the boundary
    (that is Law 3's bargain), and any future intra-domain hardening arrives as a designed,
    Appendix-G-classified extension — never as a security claim resting on the capability model,
    which makes no intra-domain promise at all (§2.2 states this in the unforgeability theorem).
33. **The minimum conforming physical machine is large on purpose** (§0, §14, §16.8, §13,
    §18): FP, vector, debug, serialization/migration, and the system engines are all
    implemented, so the smallest conforming part is a full machine — attractive to compilers and
    operating systems (one binary target, no hardware feature matrix) and honestly expensive for a
    chip builder. A parent may still withhold execution through a narrowed view; the one-binary
    guarantee applies under a **full execution view**. A "reduced profile" is a *variant*, and
    variants are the disease the one-machine rule exists to
    refuse: the moment a mandatory engine becomes optional, every binary grows a probe, every
    library grows a fallback, and the one-target promise is folklore within a product cycle. The
    LNP64 v1 does not target microcontroller-class silicon; the entry ticket is the whole machine.
34. **Per-thread priority makes intra-domain inversion expressible — and futexes still transfer no
    donation** (§16.1 `SET_THREAD_SCHED`, entry 6): before the sub-op there were no intra-domain
    priorities, hence no intra-domain inversion to construct; now the classic three-party shape —
    a high-priority thread blocked on a futex held by a low-priority sibling while a
    middle-priority sibling runs — is expressible inside one domain, and entry 6's trade
    (ownerless futexes are what make the uncontended path one memory access) still stands, so the
    futex path will not inherit. The mitigation ladder, in order: a coarse-locking guest raises
    the holder's own priority around the critical section with this same op (priority-ceiling
    emulation — one engine op per section, affordable at cpu-lock granularity; fine-grained
    lockers are the harder customer), the serialized gate remains the inheriting mutex wherever a
    gate fits (§9.2), and a *complete* future PI mechanism arrives whole through the Appendix G
    `FUTEX_EXTENSION` seam. The alternative — futex-carried donation — is refused at entry 6; this
    entry prices the interaction, not the refusal.
35. **Connected-region placement recreates contiguous allocation in two dimensions, and the
    compactor is software** (Law 8, §16.1 `domain.place`, §15 `backing.rehome`): on a long-lived grid,
    placement churn fragments runnable-tile masks inside a coherence/time volume; `REPARENT`
    demands connectivity and containment in the new parent's volume; and the machine never
    relocates a domain autonomously. Inside one immutable volume, `domain.place` re-validates every
    legality and admission dependency fail-closed, while `backing.rehome` moves frames in place with
    bounded stalls and no fault windows. Moving the domain to a different coherence/time volume is
    a new incarnation through the §16.8 state-capture/import/handoff composition, with its cut and deadline rules
    of §16.8; the two in-volume verbs cannot perform it. The price, stated for deployment planning:
    elasticity is per-incarnation, not continuous volume growth, and the base ISA makes no claim that
    migration-based compaction is cheap enough for every workload. Large-mesh deployments must
    measure and provision that path. At spanning scale a placement-and-compaction service
    (the roadmap's gravity scheduler; Appendix G
    `GATE_AFFINITY` is its sensor half) **stops being optional** — a deployment that ships
    without one fragments until admissions fail, noticed at admission time (`-BUSY`), never as
    corruption.
36. **Self-subdivision is not deniable — the restriction knob is refused, on the four-meanings
    test** (§2.1, §16.2): the self-capability's `CREATE` is inalienable and `domain.build`/
    `domain.exec` sit outside the closed view-withholdable surface, so any domain can create
    children, always. The refused cure — a deny-self-creation knob — would police an interior
    fact that crosses none of Law 8's boundary meanings, and a *withholdable* protection
    primitive recreates the variant disease in software (every compartment-emitting compiler
    grows a probe and a fallback, B33's rot at one remove). The parent's legitimate interests
    survive intact: budgets bound subtree growth (grower-pays; a near-zero object budget is the
    leaf-frozen construction), views bound what children know, and the dominator chain inspects
    everything (Appendix H). The price, stated: no personality can offer a "may not subdivide"
    policy bit backed by hardware — a tenant contract wanting one enforces it economically
    (budget) or contractually, never architecturally. A future proposal to add the knob must
    overcome this entry's reasoning, not merely cite a customer.

## Appendix C: the cost model, consolidated (what scales with what)

The virtualization and nesting claims are scattered where their mechanisms live; this appendix
is the one-table answer to what scales with what. Every architected cost falls in exactly one class, and **anything not listed in classes
2–4 is class 1 — flat — by default and by intent**; a future mechanism that cannot be placed in
this table is mispriced by construction and must not land. **And every class now carries its
distance annotation (Law 8), because algorithmic complexity was only half the price:**

**Class 0 — near-local, tile-bounded (the new floor):** `ld`/`sd`/ALU/branches on `near` mappings
(§15), atomics whose line is `near`, futex fast paths on `near` words, `get_pcr`. Bounded by the
tile-group, independent of the domain's size, the tree, and the machine.

**The distance rule over classes 1–4, stated once:** an operation's latency is bounded by a
distance *some party named* — atomics and cell bumps on `domain`-class memory, intra-volume gate
calls, and **translation** invalidation broadcasts are **O(the owning domain's diameter)**, which
the domain chose at its own creation and can see in its own locality metric (§16.7); **a shared
cell's bump — lineage revocation, `RESTAMP` — is O(the referent span's diameter)**, the reach the
delegator itself built, one named crossing per delegation that crossed (§3: the revocation bill
is the delegation bill come due); `send`/`recv` and gate calls
that cross domains, and DMA to a device port, are **O(the distance between the two parties)**,
which the parent that bound them chose and can see; and **nothing anywhere is O(machine diameter)
except an operation of a machine-spanning domain — which asked for exactly that.** Every
architected cost is bounded by a distance the program itself named.

**One split priced explicitly because a hot loop lives on it:** domain `DESTROY` is **class 1 to
the caller** — one `cancel`-policy bump, flat — and the reclamation drain is **class 2 (O(the
corpse's own state)), asynchronous, corpse-charged**: never the destroyer's critical path. The
mint/call/destroy loop's wall-clock cost is its two flat halves.

**The provisioning addendum (the machine-spanning objects nobody calls a domain):** some parties legitimately name the meter — the root domain's lineage cells, the
first domain's boot-time delegations, a popular service's stamp cell, a fleet-wide shared
read-only backing. Their spans are machine-scale **by nature, not by accident**: for the control
plane's most-delegated objects, "the span of the authority" is routinely the whole part. So wide
bumps — rare per object, but there are many such objects — are the fabric's **background
weather**, and their per-referent-volume epoch replication (§3's obligation) is a **provisioning
line item**, not an anomaly. The doctrine holds — every one of those spans was built by
delegations that named their crossings, and revocation/`RESTAMP` on them is rare-by-design — but
"nothing is O(machine diameter)" is honest only with this sentence beside it: **the exceptions
are exactly the objects everyone holds.** An implementation targeting spanning deployments sizes
its invalidation fabric for that weather, and the owner of a wide cell needs no new sensor to
anticipate the bill — the span *is* the delegation history it chose to have.

**Class 1 — flat with nesting (O(1) at runtime, regardless of tree depth):** scheduling events
(flat reservation state, §16.1 — a domain 10 levels deep schedules at root-domain cost);
capability ops — dup/drop/revoke/table lookup (bounded, never a walk; one cell bump, §3, §11.3, §16.4);
gate calls between any two domains (one boundary, one frame — depth of *either party* is
irrelevant, §9.2; **the contract-bearing warm number is the published `GATE_WARM_RTT` under
§9.2's measured-path preconditions — residency-miss, descriptor, wider-class, contended, and
distance paths are the separately priced variants, and the conservative committed table prices
the cold path, never the warm one**; `gate_tail` is one crossing at the same class, minus the
frame push); epoch checks (one load-compare, §3); futex ops (§6); native intrinsic ops against
flattened delegated state (definitionally zero interposition, §11); fault delivery (one gate, §9.3); budget charge/refund
(per-frame recorded account, §15). **Law-7 corollary: no *observable* is depth-scaled either** —
subtree-scoped IDs mean a domain cannot even measure its own depth.

**Class 2 — O(participants-in-path), paid per operation, chosen by configuration:** a bound
slot's gate chain costs one gate call per *interposer the parents actually configured* — depth of
the domain tree is irrelevant; only opinions in the path count (§11). Pager service costs one
park-and-message per *pager in the chain* for the faulted page (a pager whose own backing is
paged adds its own fault; the §15 pinned-working-set rule is what keeps real chains at one or
two). Invalidation broadcast costs one spanning-tree round-trip over the *owning domain's volume*
(§11.2, §3 — volume diameter, not machine width and not tree shape; the bound is parametric in the
domain's own diameter) — **with the fault case priced, not hidden:
a range mapped into an ATS-granted device window inherits `ATS_ACK_BOUND` + fence engagement as
its worst case (§11.2), so a `RESERVATION`-class analysis that issues invalidations against
device-visible ranges must budget that bound or keep RT ranges out of ATS-granted windows — the
same admission-rule shape as `PIN_RESIDENT`; ranges with no ATS exposure keep the tight
`INVALIDATION_ACK_BOUND` round-trip.** `EVICT` costs the *mappings of the evicted
range* (the reverse map, `hardware_design.md` §17.2) — sharing degree, not depth.

**Class 3 — configuration-state-parametric, paid once at configuration, never at runtime:**
`dsched.reservation` and live `domain.reserve` admission walk the ancestor chain plus the enumerable admission-dependency set at publication
(§16.1); `dplace` and `mview.seal`
validate monotone restriction against the parent's effective state at publication (§16.1, §16.7);
`dnew`/`dfork` budget carving checks the parent once; **`dspawn`** is configuration-state-parametric
publication plus named admission (§16.4, transcribed here so the table is the single answer it
claims to be); **`dreplace.commit`** is parametric in the prospective executable state it publishes
(§11.5) — a configuration edit by construction, never a runtime path. The rule these instances share, stated
once: **hierarchy is paid when it is *edited*, never when it is *exercised***.

**Class 4 — bounded by a caller-supplied parameter, never by hidden state:** `AS_ENUMERATE` by
the VMA count and the caller's buffer (resume cursor, §11.2); full `state.open` by subtree state
volume (§16.8); the remote-`amo` arbitration figure carries **only advance-visible geometry terms**
(§6 — volume diameter, `A_volume`, and `Q_home`; live contender count never enters the published bound);
message ops by `in_len`/`out_len` and the §16.4
maxima; `backing.supply`/`backing.evict`/`accessed.begin`/`backing.rehome`/`map.discard`/`map.reclaimable`/**`munmap_range`/`map.protect`/`map.demote`** by the range handed in, and request-keyed `backing.supply_req`/`backing.respond`/`backing.reject` by the named request — **the
mapping-mutation set is class 4 for the same reason its `map.discard` sibling always was**:
per-frame refund and charge arithmetic scales with the range, so the default-to-class-1 rule above
would have mispriced them, and §16.5's mutating-cursor rules are how they resume;
**`backing.clone` by resident frames** (§11.2, stated there and enumerated here); the **`set`
family** (`sadd`/`sremove`/`srange`/`sunion`/`sinter`/`ssubset`) by the explicitly named set sizes
and locality span (§16.5); **`window.remap`** per-entry over the handed-in extent list (§15); the
`begin` family** (`denum.begin`, `objenum.begin`, `changes.begin`, `dirty.begin`,
`incident.begin`) by the enumerated relation's cardinality and the caller's buffer — the same
basis as their `AS_ENUMERATE` sibling, with **`cursor.next` itself class 1** (one record per
call). Class-4 ops are the ones with `-OVERFLOW`
/ cursor semantics precisely so no caller can mistake them for class 1. **`state.commit` is the
one class-4-shaped operation that cannot carry a cursor** — §16.8's nothing-retained rule makes
the import atomic by definition — so it is **admission-time only and never an RT-path
operation**; nothing else in this table both scales with its input and refuses to resume.

**The dirty-tracking cost is representation-dependent, never architecturally fault-priced (§15).**
`observe.mark(WRITES)` and the dirty cursor require a no-false-negative changed-range result and permit a
reported superset. A conforming implementation may pay a first-write fault per page and epoch, update
hardware dirty generations or a bitmap in the translation path, append to a dirty log, or maintain
hierarchical summaries. The architectural costs are rotation bounded by the backing's writable
mapper/device span and enumeration bounded by the named range and returned cursor entries; no
particular number of faults or bitmap scans is required. The forbidden design is only a drifting
second source of truth that can omit a changed range.

**The one static cost, argued rather than hidden — code density.** The fixed 8-byte instruction
word (§1) buys this spec its decode regularity, its wide immediates, its four-operand forms, its
hint fields, and the wild-jump landing-zone property — and it costs static code size against a
compressed-ISA baseline: text is larger than RV64GC text for the same program, and no compressed
subset is planned (a second encoding would break fetch-atomicity (§6), the landing zone (§1.1),
and decode-by-range). The static cost has a dynamic twin, priced here too: **front-end fetch
bandwidth scales with the word** — a *w*-wide implementation fetches 8*w* B of instruction bytes
per cycle (48 B/cycle at 6-wide) where a compressed-ISA part fetches roughly half for the same
issue width, so a wide part pays in fetch and I-cache bandwidth as well as static bytes.
I-cache pressure is dominated
by the *dynamic* working set, and the ops this ISA fuses (checked loads, rich addressing, the
system surface that is one instruction here and a call sequence elsewhere) shrink dynamic path
length; if measurement on real workloads falsifies that, the recourse is prefetch/layout tooling
and the hint zone — never a second encoding. Until measured, the honest ledger entry is: **code
density and fetch bandwidth are conceded costs, unquantified, with a named non-recourse.**

## Appendix D: conformance is derivable (the suite-derivation rule)

**The rule.** Every frozen behavior in this document is a **test specification**, and the
conformance suite is *derived*, never authored: a behavior that cannot be turned into a test is
underspecified (file it as a spec bug); a test that cannot be traced to a frozen sentence tests an
implementation, not the architecture (delete it). "Two independent implementations interoperate"
(§17.7's stated goal) is checkable exactly when this derivation is mechanical — the catalog
(`isa_spec.json`) generates the enumerable-surface tests, and the assertion families below
generate the behavioral ones. **For the implementation cadence, this is the compression-correctness
oracle:** each new implementation verifies against the executable semantics plus the memory-model
litmus family for the frozen-*weakest* model — so the annotation ecosystem (the `sc` bits and
acquire/release marks binaries have carried for years) is testable against the machine that will
finally exercise it *before that machine exists*. The suite itself is post-freeze work; what is normative *now* is
that **derivability is a property of every future edit**: a change that adds unfalsifiable prose
does not merge.

**The executable audit contract.** `isa_spec.json` is also the index from which the suite derives
schema, reference, lifecycle, commit, serialization, and composition obligations. The checker must
reject—not merely warn on—an assignment collision, an unresolved or multiply-defined normative
reference, an uncovered object-operation/state cell, an unregistered multi-stage commit point, or a
new unqualified use of the scoped terms named below. A catalog entry is not evidence that behavior is
correct; it is evidence that the generator has a complete, stable coordinate at which to test it.

**The generated lifecycle matrix, scoped precisely.** The catalog materializes the Cartesian product
of every concrete class, its universal/class/data-plane operations, common object lifecycle state
`{LIVE, DESTROYING, DEAD, POISONED}`, concurrent event
`{NONE, REVOCATION, FREEZE, CANCELLATION, SERIALIZATION, DEATH, POISON}`, and whether that event
linearizes before or after the operation's commit. This matrix owns those cross-cutting lifecycle
facts; an operation's ordinary argument, configuration, rights, and capacity preconditions remain
defined once in its operation row. Resolution order is **poisoned object → dead object → destroying
object → exact operation override → concurrent-event rule → live local semantics**. Every cell emits
exactly one typed answer: `transition:name`, `idempotent_result:name`, or `condition:NAME` from §13.1.
A concurrent race may resolve through one named transition relation whose alternatives are explicitly
separated by its authority/death/poison/commit linearization point; it may not contain two unrelated
answers or an unnamed “implementation choice.” `scripts/check_isa_consistency.py` generates the full
matrix on every run and rejects a missing operation, state, event, phase, outcome kind, or condition.

**The commit-point registry (one row per multi-stage transaction, never an informal second point).**

| Operation | Sole architectural commit point | Before it | After it |
|---|---|---|---|
| `gate_call` / gate transfer (§9.2, §9.4) | the one activation transition that publishes the continuation frame, reserved return capacity, transferred-cap installation, borrow, and runnable callee together | interruption/failure leaves the caller state and authority unchanged; no callee ran | the callee may run, the caller is parked, transfers and the activation-scoped borrow are live, and only return/cancellation/teardown can resolve the frame |
| `recv` (§10.2) | the final transition that installs capabilities, writes actual counts, and dequeues the exclusively claimed message | the message remains queued and no capability is installed; staged ordinary-memory bytes have no synchronization meaning | the message is consumed exactly once and all installed capabilities are live |
| `dseal` / `dstart` / `dreplace.commit` (§11.5) | publication of the fully validated DomainBuilder, including prepared relationship cells | validation failure leaves prior state runnable, staged moves unconsumed, and issues idempotent abort obligations for prepared tokens | prospective state is complete, cells are live, and engine-owned commit obligations are pending; no mixed image exists |
| `state.commit` (§16.8) | publication of one fully validated typed import builder, including all `state.bind` dependencies | the imported object and dormant recipe are unpublished and establish no live external binding | one complete object is published under the same class predicate as `*.seal`; no partial state is reachable |
| `cell.repoint.commit` (§16.0) | the conditional epoch-cell target update | the expected target remains authoritative | exactly the new target is authoritative through that cell |
| `SUPPLY` (§15) | installation of the validated frame extent and its charge/translation generation into the backing | no requested page becomes resident and no parked faulter is released | the extent is resident as one result; eligible parked faulters may resume against it |
| `backing.reject` (§15) | terminal selection on the named open page request | the request remains open and its faulter remains parked | the named request has the terminal condition and its faulter is released to the synchronous FAULT gate; supply/respond can no longer win that request cell |
| `EVICT` (§15) | the backing transition to non-resident plus the translation-cell bump | every page remains in its prior residency/dirty state on failure | new accesses fault to the pager; acknowledged invalidation/quiescence closes all old translations before reusable frames are released |
| DMAWindow `REMAP` (§15) | atomic installation of the batch and advancement of `installed_generation` | every IOVA still denotes the old batch | the new batch is installed, while reuse/submission safety remains separately gated by `submission_safe_generation`/the acknowledged generation |

Any future multi-stage operation adds a row in the same change that adds the operation. A checker
finding two candidate architectural commit phrases for one registered operation, or none, is a
specification error; internal staging points are permitted only when explicitly labeled
non-architectural.

**The assertion families, indexed by section** (each row is a test *generator*, not a test):

| Family | Sections | Generator shape |
|---|---|---|
| Pinned corner values | §4–§6, §14 (`clz(0)=64`, div-by-zero results, NaN-boxing, failed-CAS ordering floor per `ford` — inherit = the acquire-half join, sentinel deadlines, `isync` never-faults) | execute op on the corner input, compare the architected result — exhaustive over every "pinned"/"defined result" sentence |
| Condition boundaries | §9.1, §13.1, §16.0 (fault-vs-error, `-MALFORMED` vs `-OVERFLOW` vs `-UNSUPPORTED` four-case body rule, `-BADREF` vs `-STALE`) | drive each op through each boundary input class; the §16.0 case analysis is literally the test matrix — including the delayed-detonation case: a wrong-class handle in a transferred caps array must install successfully and fail `-BADREF` at the receiver's first class-checked presentation (§17.1) |
| ABI canonical narrow form | §2 (narrow-integer extension rule), psABI | pass the boundary values (`0x80000000`, `0xFFFFFFFF`, `0x80`, `0xFF`, and their 16-bit analogues), **each driven as both the signed and the unsigned type of its width** — `uint32_t 0x80000000` is the load-bearing case: unsigned, yet canonical form is sign-extended — through every argument register into signed-compare, unsigned-compare, and branch consumers across a call edge; the producer side must deliver the §2 canonical form and the consumer side must compare correctly **with no re-normalizing instruction in the generated code** |
| Gate-export equivalence | §9.2, psABI (`lnp_domaincc`, sret-via-output-borrow) | adapter-style: compile one C signature both as a local function and as a gate export; for every return type (scalar, two-member aggregate, > 16 B) the two paths must return bit-identical values, with the > 64-bit path observed through the mandatory output borrow window and its defined value-register byte count |
| Generated-schema consistency | §1, §8.2, §9.3, §13.1, §16.2, §17 + `isa_spec.json` | generate both decode/enumeration tables and tests from the catalog; exhaustively compare opcode assignments, per-class sub-op IDs, object/interface classes, rights bits, event ranges/assignments, conditions, PCR and fixed-property selectors, record sizes/offsets, reserved-zero coverage, and version tags. Reverse maps must also be injective where the namespace requires it: duplicate prose definitions, duplicate numeric assignments, a catalog-only value, or a prose-only value fail the gate |
| Normative-reference integrity | all sections and appendices + every catalog `ref` | parse section/appendix headings and named machine/table/bit/field anchors; every normative reference resolves to exactly one definition. Duplicate heading/anchor definitions, missing Appendix-F machine numbers, a bit reference outside its named field, and references to a renamed record field fail before semantic tests run |
| Epoch/staleness | §3 and every consumer (retarget `-STALE`, cursor `-STALE`, slot reuse/drop/move `-STALE`, view-step re-resolution) | mutate the cell between setup and use; stale must fail closed, healed must re-resolve |
| State-machine totality | §3, §9, §15, §16 and Appendix F | generate the catalog-defined class × operation × lifecycle-state × concurrent-event × pre/post-commit matrix, including every universal/class op and the named data-plane operations. Every cell must resolve through the precedence rule above to one named transition relation, one named idempotent result, or one specific §13.1 condition; “unspecified,” a blank cell, and unrelated competing answers are spec failures |
| Commit-point atomicity | the commit-point registry above | inject interruption, validation failure, death, revocation, quiescence, poison, and state capture/import at every internal stage; observations before the registered point must equal the before-state and observations after it must equal the after-state. Gate transfer, `recv`, `dreplace.commit`, `cell.repoint.commit`, `state.commit`, `SUPPLY`/`EVICT`, and DMA `REMAP` are mandatory seeds, not an exhaustive hand list |
| Restart recipe | §9.3 (`OP_RESTARTABLE`, `orig_rd_value`, resume surgery) | cancel each blocking op mid-flight; re-issue; the frozen recipe must reproduce the uninterrupted result |
| Death-hint immunity | §12 (kill bits, `kill` idiom, dead-after-write, will-fully-overwrite) | run hint-marked and unmarked encodings of the same program; results must be bit-identical. Named generators for the tempting shortcuts: **same-register kill+overwrite** (`ld r5, 0(r5)` kill-rs1 — the address consumption must complete before any physical-register release; `sd r5, 0(r5)` both kill bits; a kill-marked branch feeding a fall-through consumer); dead-after-write lines re-read by *another* agent (device through coherence) must return the stored data |
| Accounting conservation | §16.4 + `engine_accounting_table.md` | for each row: drive charge to the bound (`-EXHAUSTED` exactly at it), refund via the named event, assert balance returns to zero — the table *is* the test list. Each row's charge/refund pair is one instance of the §16.4 adjoint rule, so the family's oracle is uniform across every verb pair: **the inverse returns accounting to zero and pair-scoped observable state to ≈** — `SUPPLY`/`EVICT` and `quiesce`/`resume` are tested by the same generator shape as charge/refund, and a new verb without a named adjoint fails the family by construction |
| View closure | §16.7 + `view_closure_audit.md` | for each engine-written record: populate under a subset view, scan every field against the namespace rules — the audit's clean list is the regression set |
| Authority monotonicity | §2.2, §17.7 (`cap_dup` narrows, `SUBSET` narrows, rights-schema derivation, grants beyond holder `-DENIED`) | attempt every widening; all must fail |
| Delegation confluence | §16.7 (narrowing is a meet-semilattice action; meets commute) | build a delegation DAG, apply the same narrowing set along its paths in permuted orders; the reachable authority at every node must be order-independent and must equal the one-meet fold over the DAG — any divergence is a broken meet, i.e. a widening in disguise |
| Round-trip equivalence | §16.8 (the round-trip law, ≈ under Law 7) | property-generate every legal serializable state and observation program restricted to view-visible facts; run it against `D` and `state.commit(state.import(state.open(D,FULL)))`. The generator must independently vary exact numeric identities, shared-cell graphs, flattened ClockViews, finite/forever/matured deadlines, open/terminal activities, dormant DMA recipes, imported/forwarded/moved/rejected external dependencies, explicit service manifests, observation generations, vector geometry, and suspended-time policy. Outputs must be identical modulo only the stated replacements and committed succession edge; a distinguishing observer fails both round-trip and View closure |
| Gate warm path | §9.2, §9.3, §16.4 | benchmark family bound to the §9.2 measured-path precondition list exactly — and the same family binds **`FAULT_WARM_RTT`** (§9.3): the registered-handler machine-call round trip under its own precondition list, measured, demotion-tested, per machine — **implementation-local and tolerant by design** (each machine is tested against its *own* published tick bound with a stated statistical discipline — never against another machine's number, and never as a cross-implementation ranking): the empty `GPR`-class null-descriptor round trip on a resident, volume-local gate measures ≤ the machine's published `GATE_WARM_RTT`; plus single-violation perturbations — each precondition broken alone (non-resident metadata, serialized contention, wider ABI class, a descriptor, a borrow) must route to its separately priced Appendix C path, never a silently degraded warm claim; plus the flatness laws (no work proportional to VLEN, depth, or machine size) checked by scaling those parameters and requiring warm-path timing flat within the same tolerance |
| Domain mint/destroy warm paths | §16.1, §16.4 | measure the empty `dnew`/`dseal`/`dkill` floor against `SPAWN_WARM_RTT` and `DESTROY_WARM`, then the inherited-view compartment common case; perturb one precondition at a time (private mappings, >16 grants, reservation, measurement, prepared binding), and prove the floor/common paths stay flat in domain-tree depth and machine size while every perturbation is separately priced |
| Cross-mechanism hostile walks | §3, §8, §9, §15, §16 | compose generators rather than curate stories: at minimum `quiescence × cancellation × state handoff`, `poison × pager × DMA`, `REPARENT × reservation × view/placement change`, `gate_tail × cancellation × donation × debug-freeze` (the tail-transferred chain must keep one tip for delivery, one deadline, one accounting truth), and `service death × RESTAMP × state capture`. Permute legal event orders around every registered commit point and shared-cell acknowledgement; each run must preserve single-terminal activity choice, accounting conservation, namespace identity, and exactly-one authoritative succession |
| Normative-language scope | whole document | lint new or changed normative sentences containing `atomic`, `O(1)`, `bounded`, `completion`, `death`, `published`, `identity`, `current`, or `transparent`. Each use must name its scope or defined type: memory-vs-engine atomicity; transition work vs return latency; the parameter and published bound; terminal selection vs teardown vs record delivery; cell/object/domain death point; installed vs submission-safe/current generation; numeric vs physical identity; transparent migration vs a named checkpoint policy. A bare absolute use is a spec failure, not editorial advice |
| Invalidation acknowledgment | §11.2, §15 (broadcast → no stale use after ack; quiesce before frame reuse) | multi-agent: mutate on one, probe on all others after ack returns |
| Completeness inversions | `completeness_inversions.md` | compile each table row's left column; assert the architected lowering appears (the toolchain-facing half of the suite) |
| Crossing residue | §9.2 sanitization-scope bound, §2 speculation contract | for each `abi` class: run a gate crossing with sentinel values in every register; the callee must observe zeros inside the class and must not observe foreign-class state at all — including **speculative probes of foreign state** (the LazyFP shape: attempt transient reads of FP/vector state from a `GPR`-class activation; no microarchitectural channel may return it); an architectural foreign-class instruction must take the **precise pre-operand unauthorized-class fault** (no partial effects, no silent escalation); on return the caller must see zeros in the callee-writable class and its own callee-saved values restored; plus the positive variant: a callee compiled under the `gpr-only` codegen contract (§9.2) runs to completion under a `GPR`-class gate with **no** class fault — including the implicit-use shapes (`memcpy` expansion, spills, `long double` softening`) the contract exists to catch; plus every entry form must expose its exact r2-addressed `ActivationContext` and read zero from `r10`–`r13`; after return those registers remain ordinary scrubbed caller-saved state |
| Alias adapter proof | §16.2 merge rule (`mmap`/`map.protect`/`munmap_range` vs the AS facet on self; every future condition-(i) alias) | prove the **operand adapter** and **result adapter**, and prove **no independent alias transition exists** — both paths must reach one canonical transition (structural check against the implementation, not black-box comparison alone). The adversarial generator set drives the *canonical* operation through both adapters at every hard boundary: pointers faulting at each validation step, concurrent `cap_drop`/`cap_revoke` of the implicit self authority, budget exhaustion at the charge point, machine-call interruption on both sides of the commit point, target-domain destruction mid-op, serialization while blocked, mapping-mutation races, output aliasing input, `rd` aliasing a source, stale backing, and the §6 weak-memory reorderings around the op's ordering point — identical transition, identical conditions, adapter-shaped ABI difference only |
| Engine-reference lifecycle | §3.1, §9.2, §10.2–§10.3, §15–§16 and `isa_spec.json` `engine_reference_model` | instantiate every frozen edge family and verify exactly one edge type, charge/refund owner, qualifying-cell behavior, and terminal release. Mandatory hostile graphs include two endpoint queues carrying caps to each other, waitset→member plus queued-cap→waitset, service stamp→dead gate, VMA↔backing reverse map, cancel during transient validation, and domain teardown with externally shared objects. Explicit destroy must drain only the selected aggregation without graph traversal; weak/backpointer edges must not retain targets; cycles remain charged and stale after revocation; sponsor cleanup must confer no user-visible authority |
| Subtree isolation under adversarial contention | §16.4 invariant; the broad structures by name (capability lineage cells, shared-backing reverse maps, domain-tag allocation, machine-spanning view state, requester routing state, stamp cells, shared-backing TLB state) | two unrelated subtrees run ordinary-op workloads targeting the same named structure class; measure cross-subtree cache-line and queue interference — the invariant is a *measured* conformance property under adversarial load, not a design-review checkbox. **The wide-cell generator, named (§16.4's sharded-`referent_count` obligation):** two unrelated subtrees hammer mint/re-key/drop against one popular service's stamped objects and one widely-delegated lineage; a naïve global referent counter fails this row — sharded per-volume sub-counts with lazy home reconciliation pass |
| Description-stream fidelity | §16.6 clause 3 + `isa_spec.json` | `env_open` stream output must equal its frozen description schema, bit for bit |
| One-conformance-class | §1, §14, §18 | every opcode in the catalog executes on bare metal with a full-grant view; disabled-opcode arises *only* under a withholding view, never from absence |
| Memory-model annotations | §6, §10.2, §15 | litmus/fuzz family run against the **reference emulator implementing the architectural (annotation-semantic, MCA) model — the normative v1 model, of which TSO silicon is a legal strengthening**: TSO silicon passes trivially; mis-annotated assembly/JIT output fails off-silicon *today*. **Every ordering sentence in §6/§10.2/§15 is a generator** — beyond the standard shapes (MP, SB, LB, IRIW, ISA2, coRR), the family must cover the corners only this document pins: **posted atomics** (`rd`=`r0` retains full encoded ordering — the compiler-automatic form, the highest-probability real-silicon downgrade bug in the model); **failed `amo.cas` as acquire-only** under the weak model; the **`sc` total-order join** (`ld.aq.sc` + `sd.rl.sc` + `fence.sc` interleaved in one test — three mechanisms, one claimed order); **cross-memory-type edges** (the doorbell `fence.rel` store→store into `device_ordered`; WC drain on store→store fences); **DMA/WorkQueue release-on-submit / acquire-on-complete** with a modeled device agent |
| Builder publication and algebra | §16.1 | generate equivalent builder sequences by commuting independent facts, intersecting restrictions, repeating idempotent facts, spilling/staling generations, racing staged moves, injecting failures before publication, and comparing explicit construction with `dspawn`. Before commit no observer may distinguish any intermediate state; success publishes one closed effective state; failure publishes none and consumes no move; equivalent effective states are observationally equivalent |
| Compiler-effect coverage | §2.3 and `isa_spec.json` `compiler_semantics` | generate the fully resolved row for every assigned opcode and hardware-owned typed function; reject an unbound operation, multiply bound operation, unknown effect field, or missing required field. Differential tests may delete, duplicate, speculate, sink, hoist, and merge operations exactly where the row permits, and must preserve results, ordinary-memory observations, engine state, authority, ordering, cancellation, and the failure-only continuation property. Capability-integer tests additionally exercise copy/compare/spill/reload, equal and unequal aliases to one object, stale copies after move/drop, and `inttoptr` without authority |
| Source-model soundness | §6 (the frozen C/C++/Rust lowering table) + the herd-consumable `.cat` artifact (the E1 gate already demands it) | the mechanized theorem that upgrades "the mapping is frozen" to "the mapping is proven": **every LNP64-legal execution of code compiled under the frozen §6 lowering maps to a legal RC11/source-model execution** — stated once against the `.cat` model, discharged mechanically, re-run whenever either artifact changes. This is self-insurance as much as marketing: an OOTA or dependency-relation subtlety in the model fails this obligation *before silicon does*. No shipping ISA carries this theorem; this one is obligated to |

**Consumers, named:** the emulator (`src/`) implements against the families; the RTL formal track
(`formal_theorems.md`) discharges the families it can prove instead of test; the toolchain CI runs
the inversion family. One derivation, three consumers, no hand-curated test list anywhere.

## Appendix E: the implementation-freedom ledger (every "an implementation may," in one table)

The spec grants microarchitectural licenses where their mechanisms live; an implementer of the
fifth generation should not have to mine forty sections to learn the full envelope. This table is
the consolidation — **every** license, each with its unobservability condition. The rule for
reading it: anything not licensed here or in the section it cites is *not* an implementation
freedom, and a license's condition is conformance-testable (Appendix D families grind on exactly
these).

| License | Where | Freedom | Unobservable because |
|---|---|---|---|
| **Far execution** | §6 | execute an `amo` at the data's home instead of acquiring the line | atomicity, coherence, encoded ordering preserved exactly; timing only |
| **Posted reply** | §6 | `rd = r0` atomics post — no reply datapath | dataflow statement only; full encoded ordering retained |
| **Cracking / construction (general — the whole rule for both directions)** | §1, §4.3, §6 | decompose any instruction into any number of internal ops, **and** compose any sequence into one internal op (fusion is this direction, nothing more) | architectural semantics — results, ordering, exception behavior, fault attribution, claimed atomicity — hold exactly; nothing observes µop count or which ops were composed. **The ISA blesses no fusion pairs and requires no adjacency; no compiler correctness depends on a fusion happening.** Profitable adjacencies live in the versioned target-tuning note, never here |
| **Unpublished-builder normalization** | §16.1 | defer, normalize, reorder under dependencies, cache, compile, fuse, distribute, or execute a builder sequence as one internal recipe | builder generations, per-instruction visible failures, accounting, ordering, publication result, staged-move atomicity, and named bounds remain exact; prospective state is architecturally unobservable |
| **Crack (pair instance)** | §6 | the four plain spill pairs execute as two ordinary accesses | they never claimed atomicity; §5 semantics per half |
| **`FILL_TIME_EPOCH`** | §11.2 | check translation epochs at fill time only — zero per-access epoch cost | conditional on the Appendix F refinement proof that the acknowledged broadcast leaves no stale translation usable |
| **Asynchronous issue** | §11.1 | engine ops complete asynchronously to a defined boundary | program order at engine-op boundaries (`gate_return` is an engine op, so ordering closes; §17.1c) |
| **Lazy context fill** | §17.5, §14, §18 | FP/vector payload regions filled lazily | flag + placement rule frozen; contents correct when read |
| **Scrub by tag or rename** | §18, §9.2 | realize boundary scrubs via ownership/clean tags, lazy zeroing, or physical renaming instead of writing every bit | a post-crossing read returns the architected scrubbed value; no cross-boundary residue observable under the §2.1 speculation contract |
| **O(1) gate context** | §9.2, §17.5 | realize continuation-frame capture and restore via rename-map snapshot, banked contexts, register generations, or copy-on-write physical maps — no per-register write loop | the §17.5 frame contents are exact whenever externally observed (debug, unwind, `state.open`); §9.2's sanitization and no-residue rules hold exactly |
| **Gate-resolution cache (`FILL_TIME_EPOCH`'s dispatch twin)** | §9.2, §2.2, §11.2 | cache a gate's fully resolved crossing — table entry, lineage/stamp epochs, entry PC, target tag, stack base — and skip the per-call epoch compares | conditional on the Appendix F refinement proof that acknowledged invalidation and revocation leave no stale resolution usable; the cache is domain-tag-partitioned or scrubbed per §2.1's shared-authority-cache rule |
| **Sharded traffic counters** | §16.3 | maintain traffic getters as per-agent/per-tile shards with deferred aggregation, read-side summation, and bounded-lag publication | getters stay monotone within the published lag; no ordering edge, fence, or shared-line dependency is added to observed operations; exact accounting is a separate mechanism and never rides these |
| **Page-metadata representation** | §15, B23 | represent charging, dirty, pin/lease, reverse-map, and residency state as extent records, multi-size folios, hierarchical summaries, or sparse tables; cache or spill per-frame metadata independently of the data it describes; promote and losslessly demote leaf sizes | every architectural observable stays page-exact: protection/unmap/observation boundaries at 4 KiB, no-false-negative dirty ranges, refund arithmetic equal to the per-page sums, `map.demote` lossless |
| **Transparent TLB coalescing** | §15 | coalesce translation entries over contiguous, permission-uniform, same-class runs | never architectural: no op, no observable, no granularity change; any covered bump drops the run |
| **Idle gating** | §8, §8.1, §16.1, §16.4 | gate any idle tile, engine slice, or volume to any sleep depth; coalesce wake edges of slack-carrying arms whose windows overlap | nothing architectural observes sleep: every published bound includes worst-case wake (§16.4), admitted reservations pin their power floors (§16.1) so RT never meets a napping engine, the timebase resyncs at wake before the first read (§8.1), the wake set is the closed §8 enumeration, and slack-free deadlines still fire exactly — "nothing happening costs nothing" is a conformance-adjacent property, not a governor's hope |
| **Execution-hold algebra** (behavior, not one engine) | §16.3 (defined), §16.5, §9.4 | represent lifecycle `quiesce`, debug holds, single-step stops, and reservation throttles as **independent hold tokens** over the one runnability predicate defined in §16.3 — never a separate stopping mechanism per feature | what is frozen is the *algebra* (independent hold ownership, per-hold set/clear events, one-hold-never-releases-another, teardown-outranks-issue-holds), not a physical engine or bitset — an implementation lays out the token set freely, and debug-hold-vs-cancellation is a token-precedence fact rather than a bespoke case |
| **Ephemeral-domain tag sharing** | §15, §16.4 | back multiple short-lived domains with one hardware domain tag, discriminated by an epoch qualifier on the tagged entries | every isolation observable unchanged: a retired ephemeral's entries are dead by epoch before the tag re-issues, cross-domain hits stay impossible (the qualifier is checked with the tag, one compare), and `DOMAIN_TAG_CAPACITY` reports capacity *after* sharing — the floor stays honest. Named because "domains as cheap as threads" is the workload that finds the tag ceiling first |
| **Lazy domain materialization** | §16.1 | defer capability-slot storage, VMA nodes, hardware domain tags, thread directories, activation stacks, scheduler records, and measurement storage until their first architected use | the empty-domain floor remains exact, first-use semantics and accounting are unchanged, and all publication/destroy timing is included in the corresponding published warm fact |
| **Shared-engine consolidations** | §3, §8, §9.2/§16.3/§17.1c, §16.8/§16.9, Appendix F | build the informally-identical structures as one unit each: **one saturating-counter library** (cells + generations, two check circuits, §3); **one timeout wheel per volume** (every §8 deadline comparator); **one per-thread range-monitor CAM** (watchpoints + borrow windows + B31's future coloring check, a consequence field per entry); **one crypto core** (AEAD, measurement hash, CSPRNG, the reserved 0xf6 block — §16.8's "its own small machine" is dependency isolation, never a separate-silicon mandate); **one scrub engine** (class-scoped sanitization + payload zeroing); **one frame-metadata bank** (charge target, share count, poison {bit, generation}, accessed, write generation, pin sum, clean/WP — future per-frame facts join this bank, never a sidecar) | each client's *architected* quotas, semantics, and visibility are unchanged — `DEBUG_WATCH_SLOTS` and the one-window-set-per-thread rule (≤2 windows, §17.1c) stay separate guarantees over the shared CAM, deadline sentinels/firing per §8, counter disciplines per §3; sharing is timing-only |
| **Backing-tagged shared RO translations** | §15 | one TLB entry serves every mapper of a shared immutable RO/X backing | contents isolation untouched (nothing writable is ever shared-tagged); epoch semantics identical; residual = hit-timing co-residency, named, hardened knob disables |
| **Hint ignorance** | §12 | ignore any or all hint bits | hints are timing-only by doctrine; the death-hint-immunity family proves results identical |
| **Microcoded vector memory** | §18 | gather/scatter (and any vector memory op) microcoded slowly | architecturally present; per-element semantics exact |
| **Reclaimable-page harvest timing** | §11.2 | harvest `map.reclaimable` pages at any moment under pressure | pre-harvest reads legally return old contents (the state is *declared* reclaimable); post-harvest touch is defined zero-fill |
| **Engine realization** | Law 3, §11, §16.4 | engines in any substrate (hardwired, firmware, offload) | bounded-time contracts + accounting are the interface; no engine is nameable |
| **Remote-AMO arbitration shape** | §6 | any home-node arbiter | bounded arbitration mandated; starvation is nonconforming — the license is *shape*, not liveness |
| **Steal-within-mask** | §16.4, §15 | within a domain's granted placement mask, tile selection, work stealing, and rebalancing are implementation policy | placement *authority* is the mask, never the choice within it — observable only via view-tile ID and timing; hardware still never moves anything across an authority boundary (§15 placement policy boundary: actuator verbs only) |
| **Fill-time check migration (the doctrine row)** | §3, §11.2 | any lazily-checked epoch-cell compare may move to fill time: compute the derived fact at fill, tag it `{cell, epoch}`, never re-check per use — capability-entry caches, rights decisions, stamp resolutions, and future cells inherit this license by rule, not by per-mechanism petition | conditional, per cell class, on a **proven acknowledged-invalidation protocol** (`FILL_TIME_EPOCH` above is the canonical instance; Appendix F freezes the translation case) — and every cross-domain-shared memo obeys the §2 residue clause: domain-partitioned, crossing-scrubbed, or hardened-knob-disabled |

One page, the whole ledger, no fortieth-section surprise. A future license lands as a row here
in the same commit as its mechanism, or it does not land.

## Appendix F: the engine contract (four more machines for a club that already exists)

**The claim, load-bearing and checkable: this architecture introduces no new machine class — one
new discipline.** Every engine mechanism has a shipped ancestor that architects already build,
verify, and reimplement each generation; what is new is that the same mechanisms are unified under
one freshness primitive (§3) and one frame kind (§9), with the contract frozen. The MMU was always
a semantic, correctness-critical state machine on the load path; the coherence protocol was always
a distributed invariant-preserving machine, formally specified and reimplemented per generation;
the IOMMU has been a per-requester capability system since it shipped. The engines join that club
— they do not found a new one.

| Engine mechanism | Shipped ancestor | The delta, priced |
|---|---|---|
| Epoch broadcast + acknowledged invalidate (§3, §11.2) | ARM DVM / TLBI-with-ack, in every ARM SoC today (§11.2 cites it; this row makes the cite load-bearing) | scope keyed on a cell, ack over the volume spanning tree — protocol shape identical |
| Capability table walk + fill (§2.2) | IOMMU context/PASID table walk | a rights field on the entry; the fill path is a page-walker-class sequencer |
| Continuation stack (§9) | Intel CET shadow stack (engine-held return linkage software cannot forge, shipped since 2020) | the entry is a frame, not one address |
| Typed-family execution (§16.0) | fixed opcode/function decode plus typed operand validation and commit | instruction-family decoders are commodity; no engine parses a class/op control header |
| Scheduler charging (§9.2, §16.1) | a decrementing counter + a deadline comparator (timer-wheel-class); GPUs hardware-schedule 10⁴ contexts | flat reservation state, §16.4's published per-event budget |

**The mandatory protocol machines, named — mechanized specs are the normative behavioral definition.**
The §16.6 move (the catalog is the normative serialization of the enumerable surface) applies to
behavior: each machine below gets a mechanized protocol spec (TLA+/Ivy/Murphi-class), and **the
spec is the definition** — each generation's RTL discharges a *refinement obligation* against the
frozen protocol instead of re-deriving invariants from prose, exactly the workflow MESI variants
have shipped under for twenty years. The obligations join Appendix D's suite; the specs, once
frozen, are forever — the same deal page-table formats always imposed, and for the same reason:
the frozen format is what lets everything around it change.

1. **Epoch coherence** — bump, broadcast, ack reduction, fence recourse (§3, §11.2).
2. **Capability transfer** — the install-time transaction: snapshot, rights derivation, re-key,
   transfer-class commit (§2.2, §10.2, §11.3).
3. **Gate frame push/pop** — activation birth, detach, teardown, the §9.4 ordered flow.
4. **Donation charging** — per-activation tag flow, block-time inheritance, deadline arming (§9.2).
5. **State-stream round-trip** — capture completeness, import re-validation, and the top-level
   oracle is §16.8's round-trip law:
   `state.commit(state.import(state.open(D,FULL))) ≈ D` under Law-7 observational
   equivalence — the two obligations are the halves, the equivalence is the machine's contract.
6. **Park/wake directory** — the machine's one waiting structure, stated as a merge and not an
   analogy: a waiter registered against a key, woken by its event, cancelled `-CANCELLED` by a
   bump of any cell its park references, **charged to the waiter** (§11), exported as
   `ENGINE_STATE`, re-delivered on rebind. Futex queues (keyed `{object, offset}` / backing
   identity, §6), waitset memberships, the pager's outstanding-request set (§15), and
   serialized-gate queues are **four keyings of this one machine**; their per-mechanism
   cancel/charge/export/re-delivery sentences are corollaries of this row, verified once.
   Cancel-on-bump is the defining transition, so this machine is the epoch machine's client
   annex — one wake/cancel/export state machine, never four informally-identical ones.

7. **The `ActivityRef` lifecycle** — normatively defined **once, in §9.2**; this row is its
   mechanization obligation: one state machine (`accepted →
   pending → active → one-winner terminal of {NORMAL, CANCELLED, TIMEOUT, POISONED}`), one
   generation-qualified local ref, one terminal-choice cell, teardown-completes-everything, and at
   most one delivered completion prefix while the endpoint lives (+ the caller cookie when
   `WIDE_COMPLETION` lands), idempotent cancel —
   verified once, inherited by gate/WorkQueue/DMA/service-ring instances.
8. **The `RangeLease` machine** — the one access-validation/cancellation/teardown machine beneath
   every memory loan (§17.1c's three lifetimes, made a shared verification target): a lease is
   `{range, rights, holder, lifetime-owner, revocation-epoch, quiesce-policy}`, and `mem_grant`
   (table-owned lifetime), the borrow window (frame-owned, either same-AS overlay or cross-AS
   accessor-only remote relation exercised by `acopy.*`), a transferred memory capability
   (message→table transition), and a DMA mapping (device-window-owned + IOVA metadata) are **four
   lifetime-owners of one machine**. The user-visible forms stay distinct because their lifetimes
   genuinely differ (the merge rule's refusal to merge them as *primitives* stands, §16.2); what
   is one is their access-check, revocation, and quiesce *proof*, verified once. **`RangeLease` is
   strictly a proof machine — it has no opcode, no handle, no separately serialized object, no
   error values, and no accounting row of its own** (the chain-revocation-set row, §9.4, accounts
   the *derived authorities*, not the lease abstraction); if it ever acquired any of those it would
   have become a sixth lending primitive, which the merge rule forbids.

(The list tracks the *mandatory* machine set, and the mechanization obligation is coverage of
that set, never a frozen count: a mechanism that leaves the mandatory surface takes its machine
with it, and a new engine protocol arrives with one.)

**The fail-stop rule (conformance, engine-wide).** An implementation-detected violation of engine
metadata integrity, transition legality, or accounting conservation is **contained at the smallest
sound scope** — object, lineage, domain, backing, or requester group — and surfaced as an
architected outcome: the §3 `poison` disposition, a fence-synthesized `-POISONED` terminal, the
§15 frame-poison choreography, or the `CORE_CHECK` RAS seam. Continuing to execute against state
the engine has detected as inconsistent is **nonconforming**: interrupted work resolves to a
terminal completion (§9.2), poisoned scope fails closed forever (§3 saturation), and no path
exists on which the engine proceeds best-effort past a failed check. Detection coverage is an
implementation quality axis; the *disposition* of whatever is detected is not.

**The transfer-bundle prefix, named.** `send`,
`gate_call`, async `SUBMIT`, and service rings all move some of {bytes, capabilities, caller-local
correlation (`user_data`), optional reply storage}, so they share **one `TransferBundle` prefix**
(byte span, capability span, flags, cookie); gate descriptors append reply capacities and the
optional §17.1c borrow. The operations keep distinct semantics — but one parser, one compiler
representation, one cap-transfer rule, stated once and appended-to, never re-specified per verb.

**The domain universe as one transactional tuple.** A domain's canonical state is the
five views as one `DomainUniverse {capability, service_imports, budget, machine, clock}` tuple — *not*
merged into one mutable object (they have genuinely different authority and sharing, §16.7), but
updated as one transaction: `dseal`/`dstart`, `REPARENT`, and `state.commit` install an
internally consistent new tuple **or change nothing**, so no cross-view intermediate state is ever
observable (the frozen-update atomicity §16.8 and `REPARENT` already require, named as the tuple
invariant it is).

**The snapshot front-end, generalized (row 4's honest scope — the cheapest merge in the document,
the largest verification payoff).** Iovec arrays, SGLs (§17.8), gate invocation
descriptors (§17.1b), message descriptors, immutable set data, and state-import
streams all follow one normative discipline — **snapshot the bounded structure into
private storage, validate whole, then effect** (§11.1's rule, which each site restates as a
corollary) — differing only in schema. The intended machine is therefore **one snapshot-validate
front-end with per-consumer schemas**, the validator-concentration doctrine applies to it *as a
unit*, and a single "no TOCTOU past the snapshot" obligation covers all consumers. (The
walker family is the same move one row up: the MMU walk, the IOMMU walk, and the cap-table fill
of row 2 are one page-walker-class sequencer, three instantiations.)

**The §16.4 bounds are secretly model-checking bounds — same constants, second job:** ≤16 caps per
envelope, bounded queues and body maxima everywhere were frozen for WCET, and
finite maxima are exactly what keep the five machines' state spaces tractable. The spec's
real-time discipline and its verification discipline are one discipline.

**The validator-concentration doctrine (proof-carrying, in hardware — the pattern was built before
it was named):** *safety proofs attach to checking interfaces; producing engines owe completeness
and liveness only.* `state.commit` is already the notary — import re-validates every invariant and
a failing stream imports nothing — so the serializer, the least dataflow-shaped engine, needs no
safety proof at all: its safety lives in the validator, a pure function over a bounded input. The
pattern generalizes: epoch safety is one comparator plus the broadcast protocol; capability safety
is the install-time check; a producer may be a sloppy state machine because the checkable
interface is the proof surface. This is the single largest cost reduction in the verification
story, and it is doctrine, not accident: **a future engine must place its safety argument at a
checking interface or state why it cannot.**

**The datapath residue, enumerated and closed (what the load/store/fetch path ever sees):** a
domain-tag compare, a permission check, a memory-type field, a locality class — **all computed at
fill time, compared at access time**: a TLB entry got two fields wider, and with
`FILL_TIME_EPOCH` (§11.2, Appendix E) the epoch compare itself leaves the access path. Everything
else — rights derivation, typed routing, `RESTAMP`, lineage checks, serialization — is
transaction-side, off the datapath, at page-walk-class latency budgets. **This list is frozen: a
future mechanism that wants a new field on the access path is asking for a revision of this
appendix, not a line in its own section.** (The fill/access split is also what makes the
speculation contract implementable: authority-precedes-speculation is a local question answered
before issue, precisely because the authority decision is cached at fill.)

**The five-year test, walked:** Gen 2 (out-of-order) — hints consumed, engine ops scoreboarded
under the asynchronous-issue license, speculation checked against the cached fill-time authority
decision; engines untouched. Gen 3 — distributed epoch homes, LLC-resident capability tables;
invisible, because the contract is observables and bounds, never structures. Gen 4 — a dataflow
core with no internal architectural PC; fine: precise machine-call delivery is the only obligation
the core owes the engines. What can never change: the frozen layouts (§17) and the five protocol
specs. **Liveness:** the fence recourse (§11.2) degrades a liveness failure to a *proven safety action*
(fence, poison, fail closed).


## Appendix G: the reserved-seam register (no seam without a class)

A freeze document that claims every active v1 semantic surface has its primitive while carrying a drawer of
partially-designed futures is internally uncomfortable — named reservations are better than
accidental squatting, but each one is conceptual and verification surface. This register ends that:
**every named reservation in this document is classified below into exactly one of two
classes, and from this revision on, "reserved by name" without a register row is not a legal
spec state** — a new seam lands with its class or it does not land.

The two classes, in increasing order of promise:

- **`ENC` — encoding space only.** A name and a hole. No semantic promise of any kind; the name
  exists so nothing squats on the space. Deleting an `ENC` seam is editorial.
- **`DVP` — deferred versioned profile.** Real intent, frozen interaction constraints (what it
  may *not* do to v1 semantics), full design deferred to a versioned profile revision. A `DVP`
  seam may be *named* by v1 text but nothing normative may *rest* on it (the B31 rule,
  generalized).

| Seam | Where | Class | Why this class |
|---|---|---|---|
| `FUTEX_EXTENSION` (futex/scheduler growth) | §6, B20 | `ENC` | the undifferentiated seam where any future futex-class mechanism — priority inheritance, robust-list assist, waiter morphing — arrives **whole**: mechanism, word convention, identity resolution, teardown, and locality rule together, never format-first. One constraint inherited from §15 and pre-stated: futex keys need shared memory, shared memory is volume-confined, so any identity resolution stays volume-local, never a machine-wide walk. Nothing in v1 cites it |
| `SPARSE_CONTEXT` | §17.5 | `DVP` | pure implementation economics, and the scope is narrower than "context save" suggests: **machine-call payload *write bandwidth* only** — it shrinks no footprint (§17.5: enabling it changes no payload offsets or size; dead registers are saved as zero, not omitted), and it does **not** touch the gate path, which Appendix E's O(1) gate-context license already realizes with no per-register write loop. Its value is VLEN-scaled — negligible at VLEN=128, material only where the §18 vector region dominates the payload — so whether it is ever worth building depends on where execution VLEN lands, which is not knowable at freeze. Its liveness source is already named in §17.5 so the shortcut is pre-refused; `context_live_mask` is frozen at `[312]`, so it lands with no layout change; nothing in v1 references it normatively. **Destiny clause (the §17 freeze criterion applied forward):** when this profile lands, hardware *decodes* the liveness table — which promotes that table's format from psABI metadata to §17-class frozen layout under the full snapshot-validate discipline, **in the same revision**; it is designed under §17 rules from day one, and no toolchain-improvised format is grandfathered |
| Tightly-coupled matrix profile (context words) | §17.5, §18 | `ENC` | reserved words only. The *stated* v1 direction is the attached matrix engine as a device-backed domain (§18); the in-core profile is a hypothesis, not an intent — it gets space, not promise |
| `GATE_AFFINITY` PMU profile | §16.4 | `DVP` | the sensor half of the placement story; deferred because it is hint-class and observer-scoped (Law 7 shape already stated). Paired obligation: it records affinity *after* placement has already gone wrong — the psABI's static metadata (roadmap: call-affinity, payload-size, hot/cold annotations) is the feed-forward half, and the profile lands when both halves have a consumer. **Second named consumer: cross-domain trace propagation** — the §9.2 call-chain ID rides every engine edge (the chain ID is the trace ID); this profile's records are the *timing* half those spans lack. **Frozen interaction constraints (paired with §16.3's aggregate traffic getters):** pairwise affinity is *sampled records only* — record shape `{observed-object cookie, peer cookie, direction, weight, optional latency sample, observation generation}`; the PMU capability controls sampling rate, record capacity, and observation scope; cookies are scoped to the observer capability + observed subtree + observation generation (a migration changes them unless retention is explicitly authorized), never cross-observer-linkable pseudonymous identities; and no always-on per-caller state may ever accrete on the observed object — the sparse pairwise matrix is refused wherever it hides |
| PRI/PASID/SVA (sub-RID seam) | §15, B24 | `DVP` | v1's accelerator target is declared, not implied: **pinned/windowed DMA devices** (windows, `REMAP`, WorkQueues). SVA-class recoverable-fault accelerators are *outside v1's target market by decision* — a vendor needing SVA waits for the profile or ships the windowed model; v1 text may not imply SVA is "coming" as if that were a compatibility promise. **The CPU-side landing slot is pre-carved:** window addressability is an explicit builder fact (§11.4) whose v1-only value is `window.pin`; this profile lands as its second value, `window.faultable`, so recoverable device faults arrive as one more value of an existing declared fact, never a redesign of establishment. **Named consumer: desktop-GPU VRAM oversubscription** — `window.seal` always pins, so v1 residency management is driver software above the pin model (evict = `REMAP`-to-`UNMAPPED` + copy + re-point; placement = `backing.rehome`; application-visible budgets — the shape D3D12/Vulkan residency APIs already have), fine for the pinned-pool world every console lives in; the PC "just allocate, the driver sorts it out" luxury is what this profile would restore in hardware, and gaming is the strongest consumer argument yet recorded for it. **Second named consumer, direction decided: the integrated GPU** — GPU-class accelerators integrate as *devices* under the DeviceProxy contract; per-context isolation is **PASID-class sub-requester identities through this seam**, and GPU-contexts-as-domains is **rejected for GPUs, not deferred** (a proposal to revisit must overcome the rejection, not merely cite Law 3) |
| Device-issued atomics | §15 | `DVP` | a named extension of the §6 far-execution model; frozen constraint: device `amo`s, when they arrive, join the *existing* ordering model at the data's home — no device-private ordering domain |
| Device-backed domains | §15 | `DVP` | the reserved direction with its one predicate already frozen (holds capabilities → domain); everything else deferred. **Scope, decided: this is not the GPU path** — GPU-class accelerators are devices under the DeviceProxy contract with PASID-class context isolation (the PRI/PASID seam above); what remains here is the attached-engine shape (§18's matrix position) and any future master that genuinely hosts capability-checking execution |
| `WIDE_COMPLETION` record | §10 | `ENC` | a name on a record-size code point; no field, no semantics — **and its first field has a named consumer: a caller cookie on `SUBMIT`, echoed verbatim in the completion record** (`io_uring`'s `user_data`); the engine never interprets the cookie (Law 7: caller-local meaning only). Nothing may cite it until designed |
| `BRANCH_RECORD` PMU profile | §8.2 | `ENC` | intent stated (AutoFDO/BOLT feed) but zero semantic promise; record format, filtering, and privilege story all absent — space, not promise |
| Cache-injection steering (DDIO-class) | §15 | `ENC` | a hint-class attribute name; §12's ignore-safe rule is the only semantic it has |
| `CORE_CHECK` (core RAS) | §15 | `DVP` | the §15 recovery choreography already names its boundary (frames vs cores); the core-side record and disposition design is a RAS profile |
| Memory coloring (MTE-class) | §5, B31 | `ENC` | B31 is the governing text: nothing designed, nothing may cite it |
| `TIMESHARE` latency dimension (`latency_hint`) | §16.1, §17.7 | `ENC` | a separately named future operand/function is reserved by concept, not by a request-body field: share and latency preference are independent scheduling dimensions. Nothing may cite it until designed. **One frozen rule: latency preference is monotone under the subset rule like every other dimension** — a child's effective preference is bounded by its parent's, granted at construction, never self-escalated |
| `PRESSURE` PMU profile | §16.1, §16.3 | `ENC` | the future home of *rich* pressure telemetry: per-cause stall classes, PSI's *full* (overlap accounting across the runnable set), and threshold-triggered wakeups (`SET_THRESHOLD` + `BIND_WAITABLE` — a true stall-rate trigger, which the interim `EXHAUSTION`-waitable approximation is not: exhaustion fires on budget events, later than a stall-rate crossing). The fixed `mem_stall_ticks` getter is deliberately *some*-only; overlap tracking lands here or nowhere |
| `SHARDED_EXPORT` stream sections | §16.8 | `ENC` | parallel/sharded serialization sections for a domain whose *metadata* outgrows one sequential stream — data was never the stream's job (the §16.8 big-domain doctrine: contents ride per-`backing.clone`/persist/post-copy, the stream is O(objects) thin). Frozen constraint, pre-stated: shards must commit under the §16.8 nothing-retained rule as one atomic import — a partial-shard import that retains anything is the seam landing wrong. Nothing in v1 cites it |
| `CELL_JOIN` derived cells | §3 | `ENC` | the epoch-cell algebra's missing join: a derived cell whose epoch is the monotone join of named parents, one check validating a composite cached fact (memoized dispatch = `{stamp, lineage}`; cached negotiation = `{binding, view}`). Frozen interaction constraints: parents named at mint, join monotone, **saturation dominant** (a saturated parent permanently saturates every join above it), a stated home for the composite's broadcast (Law 8), full §16.4 fan-in accounting. Nothing in v1 cites it; N independent checks are the v1 truth |
| Data-cache partition (`CACHE_PARTITION`) | §2, §15 | `ENC` | the prime+probe occupancy channel in shared L1/L2 is deferred to the noninterference track under the §15 honesty clause; the seam reserves a separately named typed builder instruction **by name only** so no future proposal squats on the meaning — nothing may cite it until designed (the B31 rule) |
| `TRIP_COUNT` hint | §12 | `ENC` | a name on hint-zone bits; §12's ignore-safe rule is the only semantic any hint has before assignment |
| `EXTENDED_RIGHTS` (rights-word growth) | §17.7 | `ENC` | the growth path if the 32-bit rights word exhausts (9 reserved bits, a two-decade document): a per-class extended-rights page reached through the entry, reserved by name so exhaustion never forces reinterpretation of an assigned bit. Nothing may cite it until designed (the B31 rule) |
| Memory-bandwidth partition (`BANDWIDTH_PARTITION`) | §15, §16.4 | `ENC` | MPAM-class bandwidth *reservation* has no architected dimension (budgets meter bytes/compute; `CACHE_PARTITION` covers occupancy; `PRESSURE` covers telemetry). First recorded pressure: integrated-GPU scanout vs CPU traffic on one DRAM controller. Nothing may cite it until designed (the B31 rule) |
| Unassigned system byte (`0xb1`) | §1.1, §11.2 | `ENC` | encoding space with a guard: §11.2 records the standing verdict that no engine allocator exists on this machine. No semantic promise; a future system op may claim the byte through the ordinary additive path, and nothing may introduce an engine allocator through it without passing the §16.2 admission tests that verdict applies |
| `GATE_CAPARGS` (activation-scoped capability arguments) | §9.2, §2.2 | `DVP` | references that die at `gate_return`/cancellation with the frame remain deferred. The §2.2 handle format admits no second namespace, so landing requires a reserved handle-format region designed with the unforgeability theorem restated; nothing may cite this seam until that design exists |
| `RET_PROTECT` (intra-domain return-address protection) | §2, §7, B32 | `DVP` | the hardening B32 names as absent. Frozen interaction constraints: **(1)** any future hardware backward-edge protection binds to `r1` — nothing else may claim that meaning, nor any other register claim this one; **(2)** it binds to the `r1` *role* and return-shape recognition (`jalr r0, r1`-class), never to the instructions — `jal rd`/`jalr rd` generality for non-return uses is preserved. Until it lands, returns are conventional and backward-edge protection is software's. Nothing in v1 cites it |
| `PCR_EXTENDED_PAGE` (selector 31) | §8.2 | `ENC` | the fixed-form escape to a second PCR selector space, so the per-thread machine-word bank grows by one named page with the same literal-selector decode shape instead of becoming a generic CSR namespace. No extended selector, field, or semantic is assigned; nothing may cite it until designed |

Two register-wide rules. **An `ENC` seam that acquires so much as one normative sentence
elsewhere in the document is thereby misclassified — the consistency gate greps for citations
of `ENC` names outside this table and their defining reservation.** Every surviving seam carries
either frozen interaction constraints (`DVP`) or is explicitly cut; otherwise it remains
undifferentiated reserved space.

## Appendix H: the ownership covenant (the five conformance requirements beyond silicon)

The architecture's authority model is a tree, and a tree has a root: **the machine's owner holds
the root authority, and nothing on a conforming machine distrusts it.** This appendix freezes
that as conformance law — the LNP64 name and conformance mark attach only to machines and
platforms that satisfy all five clauses. They are requirements on *products*, not on silicon
timing, and the consistency gate cannot check them; the mark is what enforces them.

**H1 — A totally free operating system must be sufficient.** This document plus the catalog
(`isa_spec.json`) is the complete programming interface: no architected mechanism may require
nonfree software to exercise (the §17.4 no-vendor-space rule and the one-conformance-class rule
are the ISA-side halves of this clause; a full-grant view on bare metal runs everything). A
platform whose bring-up, power management, or device initialization requires a nonfree component
in the boot-or-runtime path does not conform.

**H2 — No distrust zone: the owner is never the adversary.** The root authority dominates every
domain: no birth flag, mode, or object makes any state uninspectable or unmodifiable by the
dominator chain (`MEASURED` carries measurement only, §16.3; the debug, AS-facet, and
enumeration surfaces answer their right-holders unconditionally). No vendor-privileged channel or
remote-kill/remote-configuration path bypasses the domain tree.
No architectural object can prove itself uninspectable; such a treacherous-computing shape does
not conform.

**H3 — Free drivers for every supported peripheral.** A conforming platform ships free/libre
drivers — or complete, freely licensed programming documentation sufficient to write them — for
every peripheral and platform component it bundles or certifies. The §15/§16.6 served-record
discipline (device constraints, topology, isolation groups as data) is the architectural half;
the opaque platform-description format and the LNP64 FDT binding are frozen by
`lnp64_platform.md`, not decoded by the ISA.
this clause is the market half: hardware whose programming interface is secret does not ride a
conforming platform's compatibility list.

**H4 — Nonfree firmware, if any, is circuitry: preinstalled and permanent.** Any nonfree
firmware a component needs must be factory-resident and immutable by software — never installed,
staged, or updated by the operating system as a blob. A device that requires OS-loaded nonfree
firmware does not conform (its vendor's remedies: make the firmware resident, or free it).

**H5 — Software-installed firmware is free, buildable, and installable with free tools.**
Conversely, every firmware object the operating system installs — through the DeviceProxy
lifecycle plane (§15), a service protocol, or any other path — must be free/libre, released as
source, reproducibly buildable and installable with free tools. **The engine is bound by the
same clause applied to itself:** an implementation whose engine control store is
field-updatable is an implementation with software-installed firmware, and those updates must
be free under exactly this rule — or the control store ships immutable and is circuitry under
H4. There is no third state.

Five clauses, one sentence of theory: **capabilities confine software from software; nothing
confines the owner.** The machine is a tool, and a tool that argues with its owner about who is
in charge is not sold under this name.
