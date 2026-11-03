# NEFROAI-X: Official NHANES 2017–2018 Data Dictionary & Semantic Mapping

**Framework:** NEFROAI-X — Advanced Explainable Hybrid AI Framework  
**Data Cycle:** NHANES 2017–2018 (Continuous National Health and Nutrition Examination Survey)  
**Issuing Authority:** Centers for Disease Control and Prevention (CDC) / National Center for Health Statistics (NCHS)  
**Publication Date:** November 2026 (Revised & Certified)  

---

## 1. Source Component Files, Eligibility & Manifest Verification

All files were retrieved directly from official CDC servers without proxy modification.

| File Component | Official Download URL | Eligibility Scope (CDC Codebook) | File Size | SHA-256 Checksum | Source Cohort Records | Total Columns |
|---|---|---|:---:|---|:---:|:---:|
| **DEMO_J.xpt** | [CDC DEMO_J URL](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt) | All sampled civilian non-institutionalized participants (All ages, 0–80+) | 3,412,720 bytes | `c0b46e0345ea19404928656277c8b0d10b0cca348a9b2fe4fc3c67e8b7ee73ec` | 9,254 | 46 |
| **BIOPRO_J.xpt** | [CDC BIOPRO_J URL](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BIOPRO_J.xpt) | Examined participants aged **12 years and older** attending Mobile Examination Center (MEC) | 2,106,080 bytes | `5bcd5722c1892883b96a9d7fed0befadabacae313f800fadc0133cd5dd00c4c6` | 6,401 | 41 |
| **ALB_CR_J.xpt** | [CDC ALB_CR_J URL](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/ALB_CR_J.xpt) | Examined participants aged **3 years and older** attending Mobile Examination Center (MEC) | 509,760 bytes | `0017a7b8d87d29009923e22300b4ec393b06c9bbf6147eb6b2d777aca605bcbf` | 7,936 | 8 |

> [!IMPORTANT]
> **Official Eligibility Distinction**:
> - `ALB_CR_J` urinalysis is protocol-targeted to examined participants aged **3 years and older** (not 6 years). Participants aged $<3$ ($N = 833$ in `DEMO_J`) are protocol-excluded from urine collection.
> - `BIOPRO_J` standard biochemistry profile is protocol-targeted to examined participants aged **12 years and older**. Participants aged $<12$ ($N = 2,565$ in `DEMO_J`) are protocol-excluded from venipuncture biochemistry.
> - **Official Examination Status (`RIDSTATR`)**:
>   - `RIDSTATR = 1`: **550 interview-only participants** (completed home interview but did not attend the Mobile Examination Center).
>   - `RIDSTATR = 2`: **8,704 MEC-examined participants** (completed interview and attended Mobile Examination Center).
>   - Total sampled cohort: **9,254 participants**.
> - **Component-file absence** (not being in the component table due to age ineligibility or interview-only status) is fundamentally distinct from **missing measurements within an existing record** (e.g. quantity not sufficient, hemolyzed blood, or instrument error).

---

## 2. Standardized Clinical Feature Dictionary

The table below defines every variable harmonized into `nhanes_2017_2018_ckd_features.csv`.

| Harmonized Feature Name | NHANES Variable | Component | Canonical Unit | SI Equivalent | Measurement Method | Clinical / Algorithmic Role | Model Predictor Status |
|---|---|---|---|---|---|---|:---:|
| `participant_id` | `SEQN` | DEMO_J | Integer ID | — | Sequence key | Unique participant identifier | **EXCLUDED** (ID only) |
| `age_years` | `RIDAGEYR` | DEMO_J | Years | — | Interview questionnaire | Demographic age at screening (top-coded at 80 years for age $\ge 80$) | **INCLUDED** (Demographic) |
| `age_months_exam` | `RIDEXAGM` | DEMO_J | Months | — | Examination center intake | Age in months at MEC examination (reported for participants aged 0–19 examined at MEC; $N=3,433$) | **EXCLUDED** (Demographic Metadata) |
| `interview_exam_status` | `RIDSTATR` | DEMO_J | CDC code | — | Survey administration | Interview/Exam status: `1` = Interviewed only ($N=550$), `2` = Examined at MEC ($N=8,704$) | **EXCLUDED** (Survey Metadata) |
| `sex_code` | `RIAGENDR` | DEMO_J | CDC category | — | Interview questionnaire | Sex category: `1` = Male, `2` = Female | **INCLUDED** (Demographic) |
| `serum_creatinine` | `LBXSCR` | BIOPRO_J | $\text{mg/dL}$ | `LBDSCRSI` ($\mu\text{mol/L}$) | Enzymatic / Roche Cobas 6000 | Glomerular filtration surrogate | **INCLUDED** (Core Biomarker) |
| `serum_glucose` | `LBXSGL` | BIOPRO_J | $\text{mg/dL}$ | `LBDSGLSI` ($\text{mmol/L}$) | Hexokinase UV method | Glycemic / diabetic nephropathy marker | **INCLUDED** (Core Biomarker) |
| `blood_urea_nitrogen` | `LBXSBU` | BIOPRO_J | $\text{mg/dL}$ | `LBDSBUSI` ($\text{mmol/L}$) | Enzymatic conductivity | Nitrogenous waste clearance | **INCLUDED** (Core Biomarker) |
| `sodium` | `LBXSNASI` | BIOPRO_J | $\text{mmol/L}$ | — | Ion selective electrode (ISE) | Serum electrolyte balance | **INCLUDED** (Auxiliary Biomarker) |
| `potassium` | `LBXSKSI` | BIOPRO_J | $\text{mmol/L}$ | — | Ion selective electrode (ISE) | Renal tubular excretion balance | **INCLUDED** (Auxiliary Biomarker) |
| `urine_albumin` | `URXUMA` | ALB_CR_J | $\mu\text{g/mL}$ | `URXUMS` ($\text{mg/L}$) | Solid-phase fluorescent immunoassay | Glomerular podocyte permeability loss | **INCLUDED** (Core Biomarker) |
| `urine_creatinine` | `URXUCR` | ALB_CR_J | $\text{mg/dL}$ | `URXCRS` ($\mu\text{mol/L}$) | Kinetic alkaline picrate (Jaffe) | Urine concentration reference | **INCLUDED** (Core Biomarker) |
| `uacr` | `URDACT` | ALB_CR_J | $\text{mg/g}$ | — | Published ratio ($\frac{\text{URXUMA}}{\text{URXUCR}} \times 100$) | Glomerular damage staging metric | **INCLUDED** (Core Biomarker) |
| `urine_albumin_comment_code` | `URDUMALC` | ALB_CR_J | CDC code | — | Laboratory QC flag | $0 = \ge \text{LOD}$, $1 = < \text{LLOD}$ ($0.3\ \mu\text{g/mL}$, filled with $0.21$) | **EXCLUDED** (QC Metadata) |
| `urine_creatinine_comment_code` | `URDUCRLC` | ALB_CR_J | CDC code | — | Laboratory QC flag | $0 = \ge \text{LOD}$, $1 = < \text{LLOD}$ ($5.0\text{ mg/dL}$, filled with $3.54$) | **EXCLUDED** (QC Metadata) |
| `survey_weight` | `WTMEC2YR` | DEMO_J | Survey weight | — | Complex multi-stage sampling | MEC 2-year examination sample weight | **EXCLUDED** (Survey Metadata) |
| `survey_stratum` | `SDMVSTRA` | DEMO_J | Sampling stratum | — | Masked variance unit | Stratification variance estimator | **EXCLUDED** (Survey Metadata) |
| `survey_psu` | `SDMVPSU` | DEMO_J | Primary sampling unit | — | Masked variance cluster | Cluster sampling primary unit | **EXCLUDED** (Survey Metadata) |
| `data_source` | — | Meta | String label | — | Data lineage flag | Tracing provenance (`NHANES_2017_2018`) | **EXCLUDED** (Provenance) |

---

## 3. Detection Limits & LLOD/sqrt(2) Substitution Protocol

In accordance with official CDC/NCHS analytical guidelines, when a measurement falls below the analytical lower limit of detection (LLOD), NCHS replaces the measurement with an imputed fill value equal to:

$$\text{Value}_{\text{imputed}} = \frac{\text{LLOD}}{\sqrt{2}}$$

### 3.1 Urine Albumin (`URXUMA`)
- **Lower Limit of Detection (LLOD)**: $0.3\text{ mg/L}$ ($0.3\ \mu\text{g/mL}$).
- **Fill Value**: $\frac{0.3}{\sqrt{2}} \approx 0.21\ \mu\text{g/mL}$.
- **Comment Code (`URDUMALC`)**:
  - `0`: Analytical measurement at or above detection limit ($N = 7,631$).
  - `1`: Measurement below lower detection limit ($N = 1$, participant `SEQN` 102311.0, with `URXUMA` = $0.21$).
  - `NaN`: Test not performed / missing ($N = 1,622$).

### 3.2 Urine Creatinine (`URXUCR`)
- **Lower Limit of Detection (LLOD)**: $5.0\text{ mg/dL}$.
- **Fill Value**: $\frac{5.0}{\sqrt{2}} \approx 3.54\text{ mg/dL}$.
- **Comment Code (`URDUCRLC`)**:
  - `0`: Analytical measurement at or above detection limit ($N = 7,631$).
  - `1`: Measurement below lower detection limit ($N = 1$, participant `SEQN` 100458.0, with `URXUCR` = $3.54$).
  - `NaN`: Test not performed / missing ($N = 1,622$).

### 3.3 Integrity Rule for Downstream Severity Assessment
The official published `URDACT` variable already incorporates these $\text{LLOD}/\sqrt{2}$ fill values into its ratio calculation. In accordance with clinical safety rules:
1. Official `URDACT` is preserved exactly as published without recalculation or overwriting.
2. The QC comment codes `urine_albumin_comment_code` and `urine_creatinine_comment_code` are preserved in the harmonized dataset so that downstream KDIGO staging algorithms can identify records impacted by detection limits.
3. Both QC fields are strictly excluded from predictive machine learning feature vectors (`exclude_from_model: True`).

---

## 4. Critical Clinical Semantic Distinctions

A fundamental failure mode in medical machine learning is treating superficially similar laboratory labels as identical clinical entities. The following semantic distinctions are strictly enforced in NEFROAI-X:

### 4.1 Blood Urea Nitrogen (BUN) vs. Whole Blood Urea
- **NHANES `LBXSBU`**: Measures **Blood Urea Nitrogen (BUN)** in $\text{mg/dL}$, which quantifies only the nitrogen component of the urea molecule ($MW_{\text{N}_2} = 28.01\text{ g/mol}$).
- **UCI `bu`**: Measures **Whole Blood Urea** in $\text{mg/dL}$, which quantifies the entire urea molecule ($\text{CO(NH}_2)_2$, $MW = 60.06\text{ g/mol}$).
- **Conversion Factor**: $\text{Urea} = \text{BUN} \times 2.1428$.
- **Safeguard**: NHANES `LBXSBU` is mapped explicitly as `blood_urea_nitrogen`, never directly into the UCI `bu` slot without molecular weight reconciliation.

### 4.2 Serum Creatinine vs. Urine Creatinine
- **`LBXSCR`**: Serum creatinine ($\text{mg/dL}$), measuring circulating blood creatinine retained due to impaired glomerular filtration (physiological operating range: $0.2 - 15.0\text{ mg/dL}$).
- **`URXUCR`**: Spot urine creatinine ($\text{mg/dL}$), measuring concentrated urinary creatinine used as a dilution normalizer for albuminuria (physiological operating range: $10 - 500\text{ mg/dL}$).
- **Safeguard**: Under no circumstances may urine creatinine be substituted for serum creatinine.

### 4.3 Urine Albumin / UACR vs. Dipstick Albumin
- **UCI `al`**: Visual dipstick colorimetry categorized on a semi-quantitative ordinal scale from 0 to 5 ($0 = \text{negative}$, $1 = 30\text{ mg/dL}$, $2 = 100\text{ mg/dL}$, $3 = 300\text{ mg/dL}$, $4 = 1000\text{ mg/dL}$).
- **NHANES `URXUMA` & `URDACT`**: Continuous quantitative fluorometric immunoassays reporting actual albumin excretion ($\mu\text{g/mL}$) and albumin-to-creatinine ratio ($\text{mg/g}$).
- **Safeguard**: Never map continuous quantitative UACR to ordinal dipstick grades without explicit threshold discretization matching KDIGO guidelines ($<30 = \text{A1}$, $30-300 = \text{A2}$, $>300 = \text{A3}$).

### 4.4 Screening Age (`RIDAGEYR`) vs. Examination Age (`RIDEXAGM`)
- **`RIDAGEYR`**: Participant age in completed years at the time of the household interview screening.
- **`RIDEXAGM`**: Participant age in completed months at the time of examination at the Mobile Examination Center (MEC), reported by CDC for participants aged 0–19 years examined at the MEC ($N = 3,433$).
- **Adult Severity Boundary Rule**: For clinical equations validated strictly for adults $\ge 18$ years (such as CKD-EPI 2021 race-free creatinine equation in Engine 2), eligibility is determined using age at the time of MEC examination: $\text{Age at Exam} \ge 216.0\text{ months}$ ($18.0\text{ years} \times 12$). For participants older than the `RIDEXAGM` collection threshold (screening age $\ge 20$), screening age $\ge 18$ is used.
- **Reconciliation Impact**: Exactly 7 participants turned 18 between screening and examination; 6 of these participants have complete serum creatinine and UACR, expanding the complete adult severity cohort from 5,063 to 5,069.

---

## 5. Sampling Design Variables & Methodological Scope

NHANES utilizes a stratified, multi-stage probability sampling design to represent the civilian non-institutionalized U.S. population.
- **`WTMEC2YR`**: Must be applied whenever computing population prevalence, quantiles, or representative descriptive statistics. Unweighted sample means do not reflect general population statistics.
- **`SDMVSTRA` & `SDMVPSU`**: Must be specified when calculating Taylor-series linearization standard errors or survey-weighted confidence intervals.
- **Model Ingestion Rule**: Survey design variables (`WTMEC2YR, SDMVSTRA, SDMVPSU`) and `participant_id` are strictly metadata and **must never be introduced as predictive clinical features into machine learning models**, as doing so introduces geographical/sampling leakage.
