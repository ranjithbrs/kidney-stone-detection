# NEFROAI-X: Clinical Data Harmonization & Ingestion Report

**Framework:** NEFROAI-X — Advanced Explainable Hybrid AI Framework  
**Phase:** Phase 5 — Dataset Collection & Clinical Data Harmonization  
**Cycle:** NHANES 2017–2018  
**Audit Status:** Complete, Verified & Methodologically Certified  

---

## 1. Merging Methodology & Component Intersection

The NHANES 2017–2018 examination encompasses three distinct data components that were joined using participant sequence number (`SEQN`). A controlled left-join strategy was executed anchored to the demographic cohort (`DEMO_J`), ensuring that no sampled individuals were deleted from the epidemiological denominator.

```text
                  DEMO_J (N = 9,254)
                  [Full Demographic Cohort]
                           │
                           ├──────────────────────────────┐
                           │ Left Join on SEQN (1:1)      │
                           ▼                              │
                 BIOPRO_J (N = 6,401)                     │
             [Standard Biochemistry Profile]              │
                           │                              │
                           │ Left Join on SEQN (1:1)      │
                           ▼                              ▼
                 ALB_CR_J (N = 7,936)           Unexamined Subsets
             [Urine Albumin & Creatinine]       (Preserved as NaN)
                           │
                           ▼
          nhanes_2017_2018_merged.csv (N = 9,254, 93 cols)
                           │
                           ▼
       nhanes_2017_2018_ckd_features.csv (N = 9,254, 17 cols)
```

### Component Membership vs. Measurement Completeness

A critical clinical data distinction is maintained between **component membership** (presence of a row in an individual data file) and **measurement completeness** (presence of a valid, non-missing numerical result):

| Category / Metric | Participant Count | % of Demographic Denominator | Methodological & Clinical Definition |
|---|:---:|:---:|---|
| **`DEMO_J` Participant Cohort** | **9,254** | **100.00%** | Full sample civilian non-institutionalized denominator (All ages, 0–80+) |
| **`BIOPRO_J` Component Membership** | 6,401 | 69.17% | Participants aged $\ge 12$ examined at MEC with a venipuncture record |
| **`ALB_CR_J` Component Membership** | 7,936 | 85.76% | Participants aged $\ge 3$ examined at MEC with a urinalysis record |
| **Component Intersection (`BIOPRO_J` $\cap$ `ALB_CR_J`)** | 6,401 | 69.17% | Participants present in both component tables (All BIOPRO members are in ALB_CR) |
| **Valid Serum Creatinine (`LBXSCR.notna()`)** | 5,903 | 63.79% | Participants with valid serum creatinine (**498 missing within `BIOPRO_J`**) |
| **Valid UACR (`URDACT.notna()`)** | 7,632 | 82.47% | Participants with valid official UACR (**304 missing within `ALB_CR_J`**) |
| **Both Valid Biomarkers (Creatinine $\cap$ UACR, All Ages)** | 5,800 | 62.68% | Participants with simultaneous non-missing creatinine and UACR (Ages 12–80+) |
| **Complete Adult Severity Cohort (Age at Exam $\ge 18$)** | **5,069** | **54.78%** | Adult participants satisfying CKD-EPI 2021 criteria (Age at Exam $\ge 18$, Sex, SC, UACR) |

---

## 2. NHANES Eligibility & Missingness Etiology

In clinical epidemiological surveys, missing values are predominantly **protocol-driven** (structural missingness by design) rather than random data loss.

### Official Eligibility Guidelines (CDC Codebooks)
- **`ALB_CR_J` Urinalysis Protocol**: Administered to examined participants aged **3 years and older** attending the Mobile Examination Center. Participants aged $< 3$ ($N = 833$ in `DEMO_J`) are protocol-excluded from urine collection.
- **`BIOPRO_J` Venipuncture Biochemistry Protocol**: Administered to examined participants aged **12 years and older** attending the Mobile Examination Center. Participants aged $< 12$ ($N = 2,565$ in `DEMO_J`) are protocol-excluded from standard venipuncture biochemistry.

### Distinction: Component-File Absence vs. Intra-Component Missingness
1. **Component-File Absence**:
   - Age ineligibility (e.g. 833 participants $< 3$ years for urinalysis; 2,565 participants $< 12$ years for venipuncture).
   - Examination status: 550 participants were interview-only (`RIDSTATR = 1`) and did not attend the MEC (8,704 participants attended the MEC, `RIDSTATR = 2`).
2. **Intra-Component Measurement Missingness**:
   - In `BIOPRO_J` ($N = 6,401$), 498 records have missing `LBXSCR` (hemolyzed blood, insufficient volume, or instrument failure).
   - In `ALB_CR_J` ($N = 7,936$), 304 records have missing `URDACT` (urine volume $< 2\text{ mL}$, technical invalidation, or participant unable to void).

### Variable Missingness Summary ($N = 9,254$)

| Feature Name | Harmonized Name | Total Missing Count | Missing Percentage | Clinical Protocol Etiology |
|---|---|:---:|:---:|---|
| `SEQN` | `participant_id` | 0 | 0.00% | Mandatory primary key |
| `RIDAGEYR` | `age_years` | 0 | 0.00% | Universal demographic variable (screening age) |
| `RIDEXAGM` | `age_months_exam` | 5,821 | 62.90% | Exam age reported by CDC only for participants aged 0–19 examined at MEC ($N=3,433$) |
| `RIAGENDR` | `sex_code` | 0 | 0.00% | Universal demographic variable |
| `WTMEC2YR` | `survey_weight` | 0 | 0.00% | Universal survey weighting variable |
| `SDMVSTRA` | `survey_stratum` | 0 | 0.00% | Universal survey stratum variable |
| `SDMVPSU` | `survey_psu` | 0 | 0.00% | Universal survey cluster variable |
| `URXUMA` | `urine_albumin` | 1,622 | 17.53% | Age $< 3$ protocol exclusion ($N=833$) + MEC non-attenders + intra-file missing ($N=304$) |
| `URXUCR` | `urine_creatinine` | 1,622 | 17.53% | Age $< 3$ protocol exclusion ($N=833$) + MEC non-attenders + intra-file missing ($N=304$) |
| `URDACT` | `uacr` | 1,622 | 17.53% | Published ratio for participants with valid urine panel |
| `URDUMALC` | `urine_albumin_comment_code` | 1,622 | 17.53% | QC comment code for urinalysis panel |
| `URDUCRLC` | `urine_creatinine_comment_code` | 1,622 | 17.53% | QC comment code for urinalysis panel |
| `LBXSCR` | `serum_creatinine` | 3,351 | 36.21% | Age $< 12$ protocol exclusion ($N=2,565$) + MEC non-attenders + intra-file missing ($N=498$) |
| `LBXSGL` | `serum_glucose` | 3,353 | 36.23% | Age $< 12$ protocol exclusion ($N=2,565$) + MEC non-attenders + intra-file missing ($N=500$) |
| `LBXSBU` | `blood_urea_nitrogen` | 3,353 | 36.23% | Age $< 12$ protocol exclusion ($N=2,565$) + MEC non-attenders + intra-file missing ($N=500$) |
| `LBXSNASI` | `sodium` | 3,350 | 36.20% | Age $< 12$ protocol exclusion ($N=2,565$) + MEC non-attenders + intra-file missing ($N=497$) |
| `LBXSKSI` | `potassium` | 3,355 | 36.25% | Age $< 12$ protocol exclusion ($N=2,565$) + MEC non-attenders + intra-file missing ($N=502$) |

---

## 3. Adult Kidney Disease Severity-Analysis Cohort ($N = 5,069$)

The 2021 CKD-EPI creatinine equation refit (race-free) is mathematically derived and clinically validated **exclusively for adults aged 18 years and older**. Pediatric kidney disease staging requires dedicated pediatric formulas (e.g. Bedside Schwartz) utilizing height/length and pediatric k-factors.

### Examination-Age Boundary Reconciliation Methodology
In NHANES, `RIDAGEYR` records the participant's age in completed years at household screening interview, while `RIDEXAGM` records the participant's exact age in completed months at the Mobile Examination Center (MEC) examination (reported for participants aged 0–19 examined at the MEC).

To determine adult eligibility at the exact time laboratory specimens were collected:
1. For participants with `RIDEXAGM` available ($0 - 19\text{ years}$ examined at MEC), adult status is evaluated as $\text{RIDEXAGM} \ge 216.0\text{ months}$ ($18.0\text{ years} \times 12$).
2. For participants older than the `RIDEXAGM` reporting threshold (screening age $\ge 20\text{ years}$), screening age $\text{RIDAGEYR} \ge 18.0$ is utilized.

**Empirical Boundary Findings**:
- Exactly **7 participants** (`SEQN`: 94544, 95328, 95616, 99003, 99051, 101233, 102632) were screened at age 17 (`RIDAGEYR = 17.0`), but reached age 18 by their MEC examination date (`RIDEXAGM = 216.0` months = 18.0 years).
- Among these 7 participants, **6 have complete laboratory measurements** (both serum creatinine and UACR), adding $+6$ complete cases to the adult severity-analysis cohort ($5,063 \to 5,069$).
- One participant (`SEQN` 95616) had valid UACR ($7.11\text{ mg/g}$) but missing serum creatinine (`LBXSCR = NaN`), which adds $+1$ to adults missing creatinine ($702 \to 703$).

```text
Total NHANES 2017-2018 Cohort: N = 9,254
  ├── Excluded: Pediatric Participants (Age at Exam < 18): N = 3,391 (36.64%)
  └── Adult Population (Age at Exam >= 18): N = 5,863 (63.36%)
        ├── Excluded: Missing Serum Creatinine: N = 703
        ├── Excluded: Missing UACR: N = 469
        │     (Overlap missing both: N = 378)
        └── Total Adults Excluded Due to Missing Labs: N = 794 (13.54%)
              │
              ▼
        Complete Adult Severity-Analysis Cohort: N = 5,069
        (Age at Exam >= 18, Sex, Serum Creatinine, UACR)
```

### Adult Severity Cohort Metrics Table

| Metric | Participant Count | % of Initial Cohort ($N=9,254$) | % of Adult Cohort ($N=5,863$) |
|---|:---:|:---:|:---:|
| **Total NHANES Demographic Sample** | 9,254 | 100.00% | — |
| **Adult Participants ($\text{Age at Exam} \ge 18$)** | 5,863 | 63.36% | 100.00% |
| **Pediatric Participants ($\text{Age at Exam} < 18$, Excluded)** | 3,391 | 36.64% | — |
| **Adults Missing Sex** | 0 | 0.00% | 0.00% |
| **Adults with Valid Serum Creatinine** | 5,160 | 55.76% | 88.01% |
| **Adults Missing Serum Creatinine** | 703 | 7.60% | 11.99% |
| **Adults with Valid UACR** | 5,394 | 58.29% | 92.00% |
| **Adults Missing UACR** | 469 | 5.07% | 8.00% |
| **Adults Missing Both Creatinine and UACR** | 378 | 4.08% | 6.45% |
| **Total Adults Excluded Due to Missing Measurements** | 794 | 8.58% | 13.54% |
| **Complete Adult Severity Cohort** | **5,069** | **54.78%** | **86.46%** |
| **Complete Pediatric Cases with Both Labs (Excluded)** | 731 | 7.90% | — |
| **Total Excluded from Adult Severity Staging** | 4,185 | 45.22% | — |

### Screening Age vs. Examination Age Reconciliation

| Reconciliation Parameter | Screening Age Baseline (`RIDAGEYR >= 18`) | Examination Age Exact (`RIDEXAGM >= 216m`) | Reconciled Delta |
|---|:---:|:---:|:---:|
| **Adult Denominator** | 5,856 | 5,863 | $+7$ participants |
| **Pediatric Exclusions** | 3,398 | 3,391 | $-7$ participants |
| **Adults with Complete Labs** | 5,063 | 5,069 | $+6$ participants |
| **Adults Excluded Missing Labs** | 793 | 794 | $+1$ participant |
| **Adults Missing Creatinine** | 702 | 703 | $+1$ participant |
| **Adults Missing UACR** | 469 | 469 | $0$ (unchanged) |
| **Total Severity Exclusions** | 4,191 | 4,185 | $-6$ exclusions |
| **Adult Cohort Retention Rate** | 86.46% | 86.46% | Consistent |

### Disentangling the Adult Denominator: Sampled Adult Population vs. MEC-Examined Adults
To prevent denominator ambiguity in epidemiological reporting, NEFROAI-X explicitly distinguishes two separate adult denominators:

1. **Sampled Adult Population Denominator ($N = 5,863$)**:
   - Represents the complete sampled civilian adult non-institutionalized cohort, including both home-interview-only participants ($N = 323$) and Mobile Examination Center (MEC) examined participants ($N = 5,540$).
   - The retention rate of complete laboratory cases ($N = 5,069$) against this total adult population denominator is:
     $$\text{Retention}_{\text{Population}} = \frac{5,069}{5,863} = \mathbf{86.46\%}$$
2. **MEC-Examined Adult Denominator ($N = 5,540$)**:
   - Represents adults who physically attended the Mobile Examination Center where phlebotomy and urinalysis specimens were collected.
   - The retention rate of complete laboratory cases ($N = 5,069$) against this examined adult denominator is:
     $$\text{Retention}_{\text{MEC}} = \frac{5,069}{5,540} = \mathbf{91.50\%}$$

### Investigation of Interview-Only Participants Aged 18–19 ($N = 19$)
An audit of participants meeting `RIDSTATR = 1` (interviewed only), `RIDAGEYR \in \{18, 19\}`, and missing `RIDEXAGM`:
- **Exact Count**: Exactly **19 participants** (`SEQN`: 95517, 96053, 96388, 96710, 97844, 97873, 99065, 99082, 99192, 99595, 99847, 100176, 100285, 100387, 100687, 101161, 101585, 101935, 102751).
- **Classification Status**: Because their screening age is $\ge 18.0$, our boundary algorithm falls back to screening age when `RIDEXAGM` is missing. All 19 are correctly classified as **Adults** ($19 / 19 = 100\%$) in the adult population denominator ($N = 5,863$). **Zero** are classified as pediatric.
- **Severity Cohort Exclusion**: Because they did not attend the MEC, both serum creatinine and UACR are uncollected (`NaN`). They are accounted for under the 323 interview-only adults and properly excluded from the complete laboratory severity cohort ($N = 5,069$).

### Clearly Defined Denominators for Missing Laboratory Counts

| Laboratory Measurement | Total Adults Denominator ($N = 5,863$) | % of Total Adults | MEC Adults Denominator ($N = 5,540$) | % of MEC Adults |
|---|:---:|:---:|:---:|:---:|
| **Serum Creatinine Missing** | 703 (323 interview + 380 MEC) | 11.99% | 380 | 6.86% |
| **UACR Missing** | 469 (323 interview + 146 MEC) | 8.00% | 146 | 2.64% |
| **Both Labs Missing** | 378 (323 interview + 55 MEC) | 6.45% | 55 | 0.99% |
| **Total Adults Excluded** | 794 (323 interview + 471 MEC) | 13.54% | 471 | 8.50% |
| **Complete Severity Cases** | **5,069** | **86.46%** | **5,069** | **91.50%** |

> [!NOTE]
> **Preservation of Age-80 Top-Coding**: In NHANES, participants aged $\ge 80$ years are top-coded at 80 years to protect participant privacy. This clinical data constraint is strictly preserved. In this cohort, 396 adult participants are top-coded at age 80, of which 306 have complete creatinine and UACR.

---

## 4. Detection Limits & Quality Control Comment Codes

In accordance with official CDC analytical guidelines, measurements falling below the analytical Lower Limit of Detection (LLOD) are replaced by NCHS with an imputed fill value: $\text{Value} = \frac{\text{LLOD}}{\sqrt{2}}$.

### Detection-Limit QC Analysis

| Analyte | Source Variable | QC Variable | LLOD Threshold | Imputed Fill Value ($\frac{\text{LLOD}}{\sqrt{2}}$) | Code `0` ($\ge \text{LOD}$) | Code `1` ($< \text{LLOD}$) | Missing (`NaN`) |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| **Urine Albumin** | `URXUMA` | `URDUMALC` | $0.3\ \mu\text{g/mL}$ | $0.21\ \mu\text{g/mL}$ | 7,631 | 1 (SEQN 102311.0) | 1,622 |
| **Urine Creatinine** | `URXUCR` | `URDUCRLC` | $5.0\text{ mg/dL}$ | $3.54\text{ mg/dL}$ | 7,631 | 1 (SEQN 100458.0) | 1,622 |

### Methodological Policy
1. The official published `URDACT` ratio is preserved as published and was not overwritten.
2. `urine_albumin_comment_code` and `urine_creatinine_comment_code` are preserved in `nhanes_2017_2018_ckd_features.csv` as QC metadata.
3. Both QC comment code fields are strictly excluded from predictive machine learning feature sets (`exclude_from_model: True`).

---

## 5. UACR Concordance & Verification

The official published Urine Albumin-to-Creatinine Ratio (`URDACT`) was evaluated against an independently computed formula:

$$\text{UACR}_{\text{calc}} = \frac{\text{URXUMA } (\mu\text{g/mL})}{\text{URXUCR } (\text{mg/dL})} \times 100$$

- **Evaluated Triplets**: 7,632 complete participant records with simultaneous `URDACT`, `URXUMA`, and `URXUCR`.
- **Concordance Threshold**: Relative tolerance $\le 0.05$ (5%).
- **Triplets in Agreement**: **7,632 / 7,632 (100.00%)**.
- **Mean Absolute Difference**: $0.0024\text{ mg/g}$.
- **Median Absolute Difference**: $0.0024\text{ mg/g}$.
- **Maximum Absolute Difference**: $0.0050\text{ mg/g}$.
- **Mean Relative Difference**: $0.0003$ ($0.03\%$).
- **Discrepant Records**: Zero ($0$).
- **Methodological Conclusion**: Minor differences ($< 0.005\text{ mg/g}$) are solely attributable to CDC's publication rounding of `URDACT` to two decimal places. Official `URDACT` is preserved as the authoritative UACR measurement.

---

## 6. Rigorous Distinctions in NHANES Evaluation Terminology

To prevent clinical methodological errors, NEFROAI-X strictly distinguishes four separate analytical modalities:

1. **Descriptive Population Analysis**:
   - Evaluating unweighted and survey-weighted distributions, medians, and percentiles of renal biomarkers across the US civilian non-institutionalized population using `WTMEC2YR`.
2. **Feature Distribution & Transportability Assessment**:
   - Comparing empirical distributions, quantiles, and physiological boundaries between the clinical development cohort (UCI CKD) and a broad population cohort (NHANES) to assess covariate shift, out-of-domain risk, and real-world range compatibility.
3. **Cross-Sectional Kidney-Marker Phenotype Analysis**:
   - Categorizing participants into cross-sectional risk categories based on simultaneous biomarkers (e.g. eGFR $< 60\text{ mL/min/1.73 m}^2$ or UACR $\ge 30\text{ mg/g}$) at a single examination, while explicitly acknowledging that this represents an unconfirmed single-timepoint screening phenotype, not a clinically adjudicated chronic disease state.
4. **Supervised External Predictive Performance Validation**:
   - Evaluating classification discrimination (ROC-AUC, sensitivity, specificity, Brier score) against an independent clinical cohort with physician-adjudicated, confirmed chronic diagnosis ground truth labels.
   - **Crucial Boundary**: NHANES does **not** provide confirmed chronic physician diagnoses and **must never be described as a labelled CKD classification test set**. No confirmed CKD labels were manufactured.
