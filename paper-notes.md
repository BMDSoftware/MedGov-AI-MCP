# Paper Notes


# 2026-05-15
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

---

# 2026-05-16
---

## Cozzolino et al. (2025) — Artificial Intelligence in Medicine 165:103137
*Are AI-based surveillance systems for healthcare-associated infections ready for clinical practice?*
https://doi.org/10.1016/j.artmed.2025.103137

Systematic review and meta-analysis of 249 AI studies on hospital infection surveillance. PRISMA, PROSPERO-registered. Main finding: only 9 out of 249 studies (3.6%) were tested in real clinical practice. Not imaging — HAI surveillance. Cite only for the general clinical AI deployment gap.

**Abstract:**
"Only 30 studies deployed the model in a user-friendly tool, and 9 tested it in real clinical practice."
→ Section I.A — number for the deployment gap (9/249 = 3.6%)

**Page 19:**
"introducing a well-performing AI model in clinical settings does not automatically yield positive results. It is crucial to consider how the model fits into the clinical workflow."

---

## Jia et al. (2025) — Computers in Biology and Medicine 192:110237
*A deployment safety case for AI-assisted prostate cancer diagnosis*
https://doi.org/10.1016/j.compbiomed.2025.110237

Prospective study in 3 UK NHS hospitals deploying Paige Prostate Suite, an FDA-approved AI for prostate cancer. Applies hazard and risk analysis to the clinical deployment workflow. Main finding: new hazards arise in deployment that regulatory approval does not catch.

**Discussion (Page 15):**
"Obtaining regulatory approval for AI/ML-based medical devices marks a crucial milestone in ensuring their safety. However, it is imperative to recognise that regulatory approval is only the initial step in assuring safety."

**Conclusion (Page 17):**
"we identified new hazards which arise from the deployment, which cannot be identified in the development, and hence would not be addressed by regulatory approvals."
→ Section I.A — for the regulatory gap claim

---

## Chen et al. (2025) — Nature Communications 16:8391
*Autonomous artificial intelligence prescribing a drug to prevent severe acute graft-versus-host disease*
https://doi.org/10.1038/s41467-025-62926-0

Prospective phase-2 clinical trial. Deployed daGOAT, an autonomous AI agent, in a hospital information system to prescribe ruxolitinib for preventing GvHD after transplantation. 110 patients, 98% initial compliance with AI prescriptions. Severe GvHD rate: 5.5% vs 16% in controls. Not imaging — hematology. Use as positive autonomous AI deployment example.

**Introduction (Page 1):**
"Autonomous AI models for deciding treatment strategies are available but rarely applied prospectively in clinical settings."
→ Section I.A — supports deployment gap from the positive side

**Abstract:**
"many physicians and patients are receptive to using conditional autonomous AI to prescribe a drug."
→ Section I.A — positive deployment result

---

## Abramoff et al. (2024) — npj Digital Medicine 7:369
*Mitigation of AI adoption bias through an improved autonomous AI system for diabetic retinal disease*
https://www.nature.com/articles/s41746-024-01389-x

> Abstract only read.

Preregistered trial of FDA-authorized autonomous AI for diabetic retinopathy screening in primary care. 626 participants, racially diverse. All non-inferiority endpoints met, no racial or sex bias. Use only as a citation for deployed autonomous AI.

---

## Wolf et al. (2024) — Nature Communications 15:421
*Autonomous artificial intelligence increases screening and follow-up for diabetic retinopathy in youth: the ACCESS randomized control trial*
https://doi.org/10.1038/s41467-023-44676-z

RCT at Johns Hopkins, 164 participants. Autonomous AI (FDA De Novo authorized, IDx-DR) vs standard care for diabetic eye exams in youth. Primary result: 100% exam completion in AI group vs 22% in control (p<0.001). First RCT of autonomous AI closing a guideline-based care gap. Not imaging — ophthalmology. Use as positive autonomous AI deployment example.

**Discussion (Page 4):**
"To our knowledge, the present study is the first RCT to evaluate the role of autonomous AI in closing a guideline-based care gap."
→ Section I.A — supports rarity of prospective autonomous AI deployments

---

## Savage et al. (2024) — American Journal of Roentgenology 223:e2431639
*Prospective Evaluation of AI Triage of Intracranial Hemorrhage on Noncontrast Head CT*
https://ajronline.org/doi/epdf/10.2214/AJR.24.31639

Prospective single-center study (9,954 head CTs, 7,371 patients). FDA-cleared AI triage system deployed in real clinical radiology. Main finding: AI did not improve radiologist performance or turnaround times. Radiologists alone outperformed AI alone (99.5% vs 93.0%). Use as negative deployment example to show that AI IS being deployed but narrow deployments fall short.

**Page 1, Introduction:**
"Research on the interaction between radiologists and AI is scarce, leaving AI systems' true utility in real-world workflows poorly understood."
→ Section I.A — deployment gap. Means: while AI tools are being deployed, researchers have not studied how radiologists and AI actually interact in real workflows. Most studies only test AI accuracy in isolation, not whether it helps the radiologist in practice. This is exactly what Savage et al. confirmed — the AI was accurate alone but added no value when combined with radiologists.

**Conclusion:**
"An AI triage system for ICH detection did not improve radiologists' diagnostic performance or report turnaround times."
