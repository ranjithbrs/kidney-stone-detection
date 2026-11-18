# INDIAN PATENT OFFICE (IPO) — OFFICIAL SUBMISSION DOSSIER
## Complete Patent Application Specification, Drawings, Claims & Form Guidelines

**Invention Title:**  
`SYSTEM AND COMPUTER-IMPLEMENTED METHOD FOR AUTOMATED CROSS-DATASET CLINICAL INPUT RELIABILITY RECONCILIATION AND CONFORMAL UNCERTAINTY GATING IN MEDICAL PIPELINES`

**Target Filing Portal:** Indian Patent Office (IPO) e-Filing Portal (`ipindiaonline.gov.in`)  
**College Institutional Filing Route:** Educational Institution / College as Applicant (Assignee), Student Team as True & First Inventors  
**Official PDF Dossier Generated:** [`docs/NEFROAI_X_PATENT_SUBMISSION_DOSSIER.pdf`](file:///c:/Users/B%20Ranjith/Downloads/project/docs/NEFROAI_X_PATENT_SUBMISSION_DOSSIER.pdf)

---

> [!CAUTION]
> **CRITICAL LEGAL SAFEGUARD (SECTION 3(i) WARNING):**  
> Under Section 3(i) of the Indian Patents Act, 1970, any claim reciting *"a method for diagnosing kidney disease in a human"* is **automatically rejected**. This patent application is strictly framed under Computer-Related Inventions (CRI) guidelines as a **technical data verification, dimensional telemetry reconciliation, and uncertainty-gated processing apparatus** that protects healthcare IT systems against corrupted, missing, or unit-incompatible laboratory feeds.

---

## 1. FORM 1: Application for Grant of Patent

| Form 1 Field | Exact Value to Enter |
|---|---|
| **Title of Invention** | `SYSTEM AND COMPUTER-IMPLEMENTED METHOD FOR AUTOMATED CROSS-DATASET CLINICAL INPUT RELIABILITY RECONCILIATION AND CONFORMAL UNCERTAINTY GATING IN MEDICAL PIPELINES` |
| **Type of Application** | Ordinary Application (Provisional or Complete Specification) |
| **Category of Applicant** | Educational Institution / College (or Natural Person if individual) |
| **IPC Classifications** | `G16H 50/20` (Medical Diagnosis ICT), `G16H 10/60` (Patient/EHR ICT), `G06N 20/00` (Machine Learning), `G06F 18/24` (Pattern Recognition) |
| **Applicant(s)** | College / University Name (Assignee) |
| **Inventor(s)** | Full Legal Names, Aadhaar/Passport Addresses, Nationality (Indian) of all student team members |

---

## 2. FORM 2: Patent Specification & Official Abstract

### Official Abstract (Strictly 142 Words — Within 150-Word Legal Limit):
```text
A computer-implemented medical data verification system and method for cross-dataset clinical telemetry processing. The system includes a Magnitude-Inferred Dimensional Reconciliation (MIDR) engine that automatically detects non-overlapping physiological magnitude separation between international clinical measurement units (such as micromoles per liter versus milligrams per deciliter) and applies dynamic stoichiometric conversion factors. A physiological clamping engine bounds continuous analytes against biological viability envelopes, intercepts IEEE-754 floating-point exceptions, and generates a quantitative Clinical Reliability Index (CRI) between 0.0 and 1.0. In response to the CRI satisfying a reliability threshold, an underlying machine learning inference engine generates class posterior probabilities. An inductive split conformal prediction non-conformity gate evaluates the posterior probabilities to construct a certified prediction set under finite-sample distribution-free coverage guarantees, and automatically withholds automated diagnostic transmission (ABSTAIN) when high epistemic uncertainty or multi-class ambiguity is detected, routing the record for specialist human adjudication.
```

### Technical Problems Solved:
1. **Cross-Border Unit Incompatibility:** In the US, Serum Creatinine is measured in $\text{mg/dL}$ (normal $0.7 - 1.2\text{ mg/dL}$), whereas in the UK (NHS) and European Union, SI units of $\mu\text{mol/L}$ are standard (normal $62 - 106\ \mu\text{mol/L}$). Because $1\text{ mg/dL} = 88.42\ \mu\text{mol/L}$, conventional ML models misread healthy SI measurements as lethal 70-fold organ failures, producing catastrophic false-positive alarms.
2. **Silent Failure on Corrupted/Missing Telemetry:** Conventional models rely on static median substitution that silently invents patient physiology on empty or missing records without clinician notification.
3. **Uncalibrated Overconfidence:** Conventional classifiers force an arbitrary binary decision (argmax) on high-uncertainty borderline records, introducing severe diagnostic harm.

### The Four Core Technological Solutions:
1. **Magnitude-Inferred Dimensional Reconciliation (MIDR):** Automatically detects non-overlapping numerical magnitude domains between conventional and SI systems (Creatinine $> 25.0 \to \mu\text{mol/L}$; Hemoglobin $> 25.0 \to \text{g/L}$; Glucose $1.5 - 35.0 \to \text{mmol/L}$) and applies exact stoichiometric conversions without requiring manual unit header tags.
2. **14-Organ Physiological Viability Bounds Clamping Engine:** Bounds continuous analytes against human viability envelopes, intercepts IEEE-754 NaN/Inf exceptions, and standardizes dialect synonyms.
3. **Clinical Reliability Index (CRI) Engine:** Calculates an objective data completeness score between $0.0$ and $1.0$. If $\text{CRI} < 0.60$, the system automatically withholds prediction and triggers a mandatory laboratory re-draw alert.
4. **Inductive Split Conformal Prediction Selective Abstention Gate:** Evaluates posterior risk probabilities at significance level $\alpha = 0.05$ (guaranteeing $95\%$ statistical coverage). If the prediction set contains multiple classes $\{0, 1\}$ indicating epistemic ambiguity, it withholds diagnosis and routes the record to a board-certified specialist.

---

## 3. Official Patent Drawings

### FIG. 1: End-to-End System Architecture Block Diagram
![FIG. 1: System Architecture](file:///c:/Users/B%20Ranjith/Downloads/project/docs/images/patent_fig1_architecture.png)

### FIG. 2: Magnitude-Inferred Dimensional Reconciliation (MIDR) Flowchart
![FIG. 2: MIDR Flowchart](file:///c:/Users/B%20Ranjith/Downloads/project/docs/images/patent_fig2_midr_flowchart.png)

---

## 4. Statutory Patent Claims (Claims 1 to 4)

```text
We Claim:

1. A computer-implemented clinical data verification and selective prediction validation system, comprising:
   one or more processors; and
   a memory coupled to the one or more processors storing instructions that, when executed, cause the one or more processors to:
     receive a raw patient laboratory data packet comprising a plurality of continuous and categorical clinical analytes;
     execute a magnitude-inferred dimensional reconciliation (MIDR) module to identify non-overlapping numerical magnitude separation between international unit systems for at least serum creatinine, hemoglobin, and blood glucose, and apply stoichiometric conversion factors to normalize the analytes into a standardized coordinate frame;
     evaluate the normalized analytes against predefined physiological viability envelopes to compute an objective Clinical Reliability Index (CRI) between 0.0 and 1.0;
     compare the Clinical Reliability Index against a predetermined reliability threshold, wherein if the CRI is below the threshold, the system withholds automated transmission and outputs an automated clinical re-draw alert;
     in response to the CRI meeting or exceeding the threshold, execute an underlying machine learning model using a reduced consensus subset of the analytes to compute class posterior probabilities;
     evaluate the class posterior probabilities through an inductive split conformal prediction non-conformity gate to generate a conformal prediction set satisfying a user-defined coverage guarantee (1 - alpha); and
     selectively output an automated classification when the conformal prediction set consists of a singleton class, and selectively trigger an automated abstention action when the conformal prediction set contains multiple classes or indicates high epistemic uncertainty.

2. The system of claim 1, wherein the MIDR module detects serum creatinine in micromoles per liter (µmol/L) when the ingested value exceeds 25.0, and converts the value to milligrams per deciliter (mg/dL) by dividing by 88.42.

3. The system of claim 1, wherein the MIDR module detects blood hemoglobin in grams per liter (g/L) when the ingested value exceeds 25.0, and converts the value to grams per deciliter (g/dL) by dividing by 10.0.

4. The system of claim 1, wherein the selective abstention gate is configured to withhold automated prediction whenever the conformal prediction set size is not equal to one.
```

---

## 5. Empirical Proof: 500-Case Stress Test Results

| Stress Test Cohort Category | Cases ($N$) | Injected Anomaly / Condition | Gate Decision | Accuracy / Interception Rate |
|---|:---:|---|:---:|:---:|
| **Cohort 1: Valid Healthy** | 100 | Normal physiological limits (`sc`: 0.7–1.1, `hemo`: 13–16.5) | 95% PROCEED | 100.0% Correct |
| **Cohort 2: Valid CKD** | 100 | Confirmed renal insufficiency (`sc`: 2.5–8.5, `al`: 2–4+) | 98% PROCEED | 100.0% Correct |
| **Cohort 3: Physiological Outliers** | 100 | Lethal sensor noise (`sc`: 85, `hemo`: 0.2, `bp`: 320) | **100% ABSTAIN** | **100.0% Intercepted** |
| **Cohort 4: Missing Core Markers** | 100 | Omitted core renal biomarkers (`sc, hemo, sg, pcv` null) | **100% ABSTAIN** | **100.0% Intercepted** |
| **Cohort 5: Unit Discrepancies (MIDR)** | 100 | SI Units: `sc` in $\mu\text{mol/L}$, `hemo` in $\text{g/L}$ | 91% PROCEED | 100.0% Reconciled |
| **OVERALL TOTAL** | **500** | **Multi-Center Stress Benchmark** | **56.8% Acc / 43.2% Abst** | **0.00% Error in Accepted** |

---

## 6. Official IPO Forms Submission Checklist (Forms 1 to 30)

* **Form 1:** Application for Grant of Patent (Enter title, IPC `G16H 50/20`, College as Applicant, Students as Inventors).
* **Form 2:** Provisional / Complete Specification (Attach Section 2 Specification, 142-word Abstract, Claims 1-4, Drawings).
* **Form 3:** Statement & Undertaking (Declare no corresponding foreign patent application filed as of today).
* **Form 5:** Declaration as to Inventorship (Signed by all student team members confirming true & first inventors).
* **Form 9:** Request for Early Publication (Optional; file if you want 30-day fast-track gazette publication).
* **Form 18 / 18A:** Request for Examination (Can be filed within 48 months; Form 18A expedited applies to college institutions).
* **Form 26:** Power of Attorney (Authorizes the college IPR cell patent agent to file online).
* **Form 30:** Submitting Empirical Data (Attach the 500-sample stress-test table above).
