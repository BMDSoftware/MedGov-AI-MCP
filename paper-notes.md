# Paper Notes

---

## Collaco et al. (2026) — npj Digital Medicine 9:345
*The role of agentic artificial intelligence in healthcare: a scoping review*
https://www.nature.com/articles/s41746-026-02517-5

Systematic scoping review of agentic AI in healthcare. Only 7 studies met inclusion criteria. Covers radiology, oncology, emergency medicine, and rehabilitation. Defines the three minimal criteria for agentic AI (autonomous operation, goal-directed behavior, tool invocation) and separates AI Agent from Agentic AI.

**Page 10, last paragraph before Methods:**
"The field remains in an early stage, characterized by heterogeneous study designs and limited clinical testing"
→ Section I.B — frame the gap this work addresses

**Page 7, paragraph on multi-agent frameworks:**
"Single-agent architectures offer simplicity, efficiency, and more transparent accountability"
→ justify the single-agent design choice

**Page 10, practical standpoint paragraph:**
"Successful integration will require hospitals to address hardware and infrastructure limitations, including legacy EHR systems, inadequate GPU capacity, and fragmented data pipelines"
→ support the infrastructure and reliability tension

---

## Abou Ali et al. (2026) — Artificial Intelligence Review 59:11
*Agentic AI: a comprehensive survey of architectures, applications, and future directions*
https://doi.org/10.1007/s10462-025-11422-4

PRISMA-based review of 90 studies. Introduces dual-paradigm taxonomy: symbolic/classical (if-else rules) vs neural/generative (LLM-based). Defines AI Agent vs Agentic AI, explains how LLM orchestration replaced symbolic planning, and covers domain-specific applications including healthcare.

**Page 2:**
"An AI Agent... is a self-contained autonomous system designed to accomplish a goal... Its agency is defined by its autonomy, proactivity, and its ability to complete a task from start to finish independently."
→ Section I.B — define what MedGov-AI is

**Page 2:**
"Agentic AI is the broader field... this often involves the orchestration of multi-agent systems"
→ Section I.B — acknowledge narrow definition exists. Use as: "While some authors define agentic AI as the orchestration of multi-agent systems [Abou Ali et al., 2026], this article adopts a broader definition, treating agentic AI as any system capable of autonomous, multi-step action through tool invocation [Collaco et al., 2026] — including single-agent architectures."

**Page 8:**
"LLMs provided a powerful, general-purpose substrate for reasoning based on statistical prediction... This enabled a fundamental architectural shift from designing cognitive agents to orchestrating generative pipelines."
→ Section I.B — justify using Gemini instead of a rule-based system

**Page 9:**
"Agency in the neural paradigm is an emergent property of prompt-driven orchestration, not a product of internal symbolic logic."
→ Section I.B — explain why LLM-based agent is different from symbolic AI

**Page 20:**
"neural frameworks are often contained within deterministic tool-chaining pipelines to ensure the reliability required in clinical settings."
→ Section II.A — justify the MCP tool-calling architecture as the right pattern for clinical safety

**Page 4:**
"The Agentic AI era (2022–present) represents the current frontier, where the generative capabilities of LLMs are harnessed for action and autonomy."
→ Section I.B — place MedGov-AI in historical context

---

## Dietrich (2025) — British Journal of Radiology 98:1582–1584 *(commentary)*
*Agentic AI in Radiology: Emerging Potential and Unresolved Challenges*
https://pmc.ncbi.nlm.nih.gov/articles/PMC12515039/

Short commentary. Not a research article — use only as supporting context, not as a primary citation. Most useful as a source of references to actual research papers (Refs 8–11) on real-world AI deployment in radiology.

**Introduction:**
"agentic AI is not yet broadly used in daily clinical radiology practice"
→ Section I.B — deployment gap, alongside Collaco et al.

**References to pursue from inside this paper:**
- Ref 8: Wiklund & Medson (2023) — DOI 10.1148/ryai.220286 — deep learning for pulmonary embolism detection and triage
- Ref 9: Savage et al. (2024) — DOI 10.2214/AJR.24.31639 — AI triage for intracranial hemorrhage
- Ref 10: Plesner et al. (2023) — DOI 10.1148/radiol.222268 — autonomous chest radiograph reporting
- Ref 12: Zou & Topol (2025) — Lancet 405:457 — "The rise of agentic AI teammates in medicine"

---

## Griot et al. (2025) — Nature Communications 16:642
*Large Language Models lack essential metacognition for reliable medical reasoning*
https://doi.org/10.1038/s41467-024-55628-6

Evaluates 12 LLMs on MetaMedQA, a medical QA benchmark that includes unanswerable questions. Main finding: models give confident wrong answers even when the correct answer is not among the options. 9 out of 12 models scored 0% on unknown recall — they never said "I don't know."

**Abstract:**
"Models consistently failed to recognize their knowledge limitations and provided confident answers even when correct options were absent."
→ Section I.A — main sentence for the hallucination/overconfidence risk claim

**Page 6, Discussion:**
"This inability to reliably indicate when they lack sufficient information or knowledge suggests a risk of generating misleading or incorrect information, which could have serious implications in clinical applications."
→ Section I.A — extend the overconfidence risk to clinical use. Note: this paper tests QA benchmarks, not report generation — you make the link to reports in your own words.

**Page 2:**
"AI introduces significant challenges due to its nature as a probabilistic black box that often lacks transparency, explicability, and interpretability. This opacity engenders trust issues among healthcare providers and creates substantial barriers to meeting regulatory requirements for clinical deployment."
→ Section I.A — black-box and regulatory trust barrier

---

## Kondylakis et al. (2026) — IEEE JBHI 30(3):2299
*A Review of Methods for Trustworthy AI in Medical Imaging: The FUTURE-AI Guidelines*
https://doi.org/10.1109/JBHI.2025.3614546

> Focused on medical imaging AI. Cite only for risk claims general enough to apply to clinical AI broadly — do not cite it for LLMs, agentic systems, or non-imaging workflows.

Instantiates the FUTURE-AI framework (Fairness, Universality, Traceability, Usability, Robustness, Explainability) for medical imaging. Based on consensus of 130+ international experts.

**Page 1, Introduction:**
"the adoption of AI in clinical practice remains limited, marking a substantial gap between technical proof-of-concepts and clinical implementation. A survey... revealed that although most radiologists strongly believe AI could improve their field, over 80% have not used AI in their daily practice."
→ Section I.A — clinical AI adoption gap

**Page 2, Introduction:**
"Concerns about AI include mainly potential risks, ethical implications, and a lack of trust due to its complexity and opacity. There is a risk of AI generating undetected errors... imbalanced imaging databases can lead to biased AI algorithms, exacerbating health disparities."
→ Section I.A — covers opacity, undetected errors, and bias in one sentence cluster

**Page 10, Explainability section:**
"AI solutions in general, and deep neural networks in particular, lack transparency, leading to the term 'black box AI', referring to the fact that these models learn complex functions that are inaccessible and often incomprehensible to humans."


**Page 2, Introduction:**
"Overreliance on AI systems can lead to automation bias, where clinicians accept model outputs without sufficient critical review, even when incorrect."
→ Section I.A — if discussing why human oversight is needed
