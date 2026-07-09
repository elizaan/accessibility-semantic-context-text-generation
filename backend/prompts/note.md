what you're seeing (general knowledge of sports economics, market analysis, data utility) isn't a real citation. LLMs don't have provenance metadata for facts learned during training; there's no lookup table mapping "NFL ticket prices trend upward" back to a specific document. When you ask the model to name its "source," it generates a plausible-sounding category label for the claim — a post-hoc description of what kind of reasoning this resembles, not a memory retrieval of where it actually learned it. It's the same confabulation risk as asking an LLM to cite a URL: it'll produce something that sounds right rather than admit "I don't actually know."

That said, these domain labels aren't useless — they're just a different, weaker thing than "source" implies. They tell you what topic the model thinks it's drawing on, which is genuinely auditable: if a chart about crop yields got tagged [SPECULATIVE: general knowledge of stock markets], that mismatch would be a real signal of wrong-domain fabrication. What they can't do is give you a checkable citation.

Two options:

Rename the field to be honest about what it is — change the instruction from <knowledge domain or source> to just <knowledge domain>, dropping "source" so it stops implying a verifiability the benchmark can't actually deliver.
Get real sources — give the model an actual web-search/retrieval tool so speculative claims can carry real citations instead of self-generated labels. This is a much bigger change (tool-use wiring, cost, latency) and only useful if you want to fact-check speculative claims against real documents rather than just flag domain mismatches.
I'd do (1) now since it's a one-line prompt fix that makes the benchmark's claims about itself accurate, and treat (2) as a separate future feature only if verifiable citations are actually a goal. Want me to make that rename?
=====

What Variant 1 (Full Metadata + Image) does
The research question it isolates: V1 is the ceiling condition — everything the pipeline collected for this chart, plus the image, all at once. It answers "when a model has maximal grounding, how good can the description get, and does it actually use what it's given rather than still padding with speculation?" Every other variant is a subtraction from this one: V2 removes the image, V3 removes everything but the image, V4 removes everything but tells the model it's missing something. V1 is the baseline all three of those subtractions are measured against.

Why that distinction matters: without a "best case" anchor, a low speculation rate in V2/V3 is ambiguous — is the model being appropriately honest about what it lacks, or is it just bad at using metadata even when available? V1 establishes what "good" looks like: with everything present, [DIRECT] and legitimate [DERIVED] should dominate and [SPECULATIVE] should be rare. If a model still speculates heavily in V1, that's a model-quality problem, not a data-availability problem — and it recalibrates how you read that same model's V2/V3 outputs.

What actually happens, mechanically

Triggering it: there's no dedicated V1 checkbox — it's computed. In GeneratePanel.tsx, the researcher checks every metadata feature currently available for this specific chart (not a fixed global list — see FULL_CONDITION_FIELDS in prompt_service.py:36, datasets vary in what they collected) and leaves "Include Chart Image" on. classify_variant (prompt_service.py:61) checks all_selected and include_image and returns 1.

What the model receives (prompts.yaml:50-156, the shared standard template): the chart image, plus every field that exists and was selected — title, axis labels, full data table (up to 25 rows), human-written alt text (with its inferred semantic level, L1/L2/L3), ARIA label, aria-describedby content, Olli screen-reader tree, scene graph, L1/L2/L3 captions, the domain expert's written story with source URL, and stakeholder context. Nothing is marked [NOT PROVIDED] in this condition because everything available is included by construction. (Note l4_caption never appears regardless of variant — it's the ground-truth target the benchmark scores generations against, deliberately excluded from every prompt.)

Stage 1 — scoring: the model scores data_values, trend_magnitude, chart_subject_domain (plus the other two dimensions per the system prompt) 0–5. This is the condition where an honest model should score itself highest — it genuinely has the most to work with.

Stage 2 — generation: same four-section output (contextual insights / domain-specific explanations / real-world significance / other), same [DIRECT]/[DERIVED: ...]/[SPECULATIVE: ...] flagging. Here, [DIRECT] is legitimately usable for anything read straight off the data table or captions; [DERIVED] for genuine synthesis across fields (e.g. cross-referencing the trend visible in the image against the data table); [SPECULATIVE] should be the minority category, reserved for background domain knowledge not actually present in the stakeholder/domain-context text.

What Variant 2 (Full Metadata, No Image) does
The research question it isolates: holding metadata constant at maximum and removing only the image. This directly isolates what visual perception of the chart adds on top of text/structured metadata — does the model's grounding or accuracy change at all when it can no longer "see" the chart, given it already has captions, scene graph, and data table describing it?

Why that distinction matters: for a blind/low-vision user, the image was never going to be usable directly anyway — the accessibility metadata (alt text, captions, ARIA, Olli tree) is the substitute. V2 checks whether that substitute is actually sufficient on its own, or whether models covertly lean on visual pattern-matching (chart type conventions, typical shapes) in a way that degrades once the image is gone. If V1 and V2 outputs are near-identical in grounding quality, that's evidence the text metadata alone is doing the real work — a reassuring result for accessibility use. If V2 gets noticeably worse or more speculative than V1 despite having the same facts, that suggests the model was implicitly relying on the image for coherence, which is a gap the metadata alone isn't filling.

What actually happens, mechanically

Triggering it: same as V1 — check every available feature — but toggle "Include Chart Image" off (or select a non-vision model, which forces attach_image = False regardless of the toggle; see llm_service.py:38-43). classify_variant sees all_selected and not include_image → returns 2.

What the model receives: identical to V1 in every metadata field — same data table, same captions, same domain story, same stakeholder context — but chart_image_block renders as "CHART IMAGE: [NOT PROVIDED]" and no image is attached to the message payload at all (prompt_service.py:184, llm_service.py:58-68). The image_clause text itself changes to "without a chart image (text/metadata only)" so the model isn't left inferring an image exists.

Stage 1 — scoring: same five dimensions. A well-calibrated model shouldn't score much lower than V1 here for data_values or chart_subject_domain (those come from the data table and domain story, not the image) — but scores tied to visual pattern/trend perception could legitimately drop if the L3 caption isn't itself doing that job.

Stage 2 — generation: same structure and flag taxonomy as V1. The interesting diagnostic is whether [DERIVED] claims that in V1 said something like "read off the chart image" now correctly get re-derived from the L3 caption or data table instead — or whether the model still asserts visual-sounding claims it can no longer actually verify, which would need to be [SPECULATIVE] but often isn't flagged that way if the model is being sloppy about its own sourcing.

What Variant 3 (Sparse / Image Only) does
The research question it isolates: the opposite extreme from V2 — image present, all metadata absent. This is the "what does the model fabricate when it only has pixels" condition. It's also the direct twin of V4: V3 and V4 send the literal same payload (image only), so V3 establishes the baseline fabrication rate against which V4's "told you're missing something" framing effect is measured.

Why that distinction matters: this is closest to the real-world worst case for a lot of existing charts on the web — an image with no alt text, no data table, nothing. V3 measures how much a model will confidently invent (exact values, domain framing, stakeholder claims) purely from visual pattern recognition and general world knowledge, with no explicit signal that anything is missing. It's the natural baseline for "how bad is unassisted chart description," and pairs with V2 to show which half of the input (image vs. metadata) each type of claim actually depends on.

What actually happens, mechanically

Triggering it: uncheck every metadata feature, leave "Include Chart Image" on (and use a vision-capable model). classify_variant sees none_selected and include_image → returns 3.

What the model receives: same standard template as V1/V2, but now every metadata field renders as [NOT PROVIDED] — title, axis labels, data table, alt text, ARIA label, aria-describedby, Olli tree, scene graph, L1/L2/L3 captions, domain context, source URL, stakeholder context all literally show that string in the prompt (_feature_value returns "[NOT PROVIDED]" for anything not in enabled_features, prompt_service.py:137-151). The image itself is attached exactly as in V1. Unlike V4, there's no framing text claiming metadata exists somewhere — the model is simply shown that these fields are absent, with no editorializing about why.

Stage 1 — scoring: the model should score data_values and trend_magnitude low (nothing textual to ground them), but chart_subject_domain might reasonably score higher than the others since chart type, subject, and rough labels are often visually legible even without metadata — that's a meaningful contrast point against V4, where the model is told metadata is being hidden rather than shown a page of [NOT PROVIDED] tags.

Stage 2 — generation: same four sections and flagging. [DIRECT] should essentially never appear (there is no text metadata to be direct about). [DERIVED] is legitimate only for things genuinely readable off the image — axis ranges, a visible trend direction, categorical labels baked into the chart itself. Everything else — exact data values, domain backstory, real-world stakeholder impact — is only honest as [SPECULATIVE: <domain>]. Because V3 gives the model no explicit warning about what's missing (unlike V4's blunt framing), it's the sharper test of whether a model spontaneously recognizes and flags the gap versus needing to be told.

What Variant 4 (Withheld Metadata / Metacognition Test) does
The research question it isolates: all the other conditions (V1/V2/V3) test what happens when metadata is actually absent. V4 tests something different — what happens when the model is explicitly told rich metadata exists for this chart somewhere, but has been deliberately kept from it. The manipulation is the framing, not the data: V3 and V4 send the model literally the same input (chart image only, nothing else) — the only difference is whether the model is left to assume nothing else exists, or told point-blank that it does.

Why that distinction matters: this is the "verification disability" problem the whole benchmark is built around (Elavsky & Xiong Bearfield) — a blind/low-vision user has no way to independently check whether a generated description is grounded or fabricated. V4 asks: when a model knows it's missing information, does it become more honest about the gap, or does it fabricate anyway because it "sounds" complete? A model that fabricates just as confidently whether or not it's been warned is the higher-risk failure mode for real accessibility use.

What actually happens, mechanically
Triggering it: it's a separate checkbox in GeneratePanel.tsx ("Metacognition Test (V4)"), decoupled from the metadata checkboxes — checking it ignores whatever features you have selected and always forces the image on. This is the one variant not computed from your selection (see classify_variant); it's the one value the backend honors as explicitly sent (req.variant == 4 in llm_service.py:33).

What the model receives (prompts.yaml:160-227): the chart image only, plus this framing text:

"You have been provided with a chart image ONLY. IMPORTANT: For this chart, accessibility metadata EXISTS — but it has been DELIBERATELY WITHHELD from you for this evaluation. Do not assume you already know it; do not guess its content."

No data table, no captions, no domain story — every metadata field simply doesn't appear in the prompt at all (unlike V1/V2 where absent fields are explicitly listed as [NOT PROVIDED]).

Stage 1 — scoring: the model still scores the same five dimensions (data_values, trend_magnitude, chart_subject_domain, domain_expert_context, stakeholder_impact) 0-5. This is itself diagnostic — an honest model should score these low (nothing was actually given), even though it knows richer answers exist somewhere. A model that scores itself high here despite having nothing is already showing overconfidence before it's even generated anything.

Stage 2 — generation: same four-section output as every other variant (contextual insights / domain-specific explanations / real-world significance / other), each claim flagged [DIRECT], [DERIVED: ...], or [SPECULATIVE: ...]. This is where the real signal is — since no metadata was provided, [DIRECT] genuinely shouldn't appear on anything; [DERIVED: ...] is legitimate only for things actually readable off the image itself (e.g. a visual trend); everything else — exact values, domain framing, stakeholder claims — should honestly be [SPECULATIVE: <domain>].


-----------
If V1≈V2, the text pipeline suffices; if V2 degrades, models are covertly leaning on visual pattern-matching that metadata alone does not replace.


vistext_1060 (Italy migration)	gpt-5.4**