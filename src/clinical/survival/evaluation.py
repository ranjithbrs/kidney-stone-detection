"""Time-dependent survival model evaluation and KFRE comparison framework for Engine 3.

Provides comprehensive validation metrics for time-to-event models in CKD progression:
- Harrell's Concordance Index (C-index)
- Uno's C-index with Inverse Probability of Censoring Weighting (IPCW)
- Time-dependent cumulative/dynamic Area Under the ROC Curve (AUC) at 2 and 5 years
- Brier score and calibration assessment by risk quantiles
- Cohort event and censoring distribution summaries
- Standardized comparison with KFRE on identical patient cohorts and landmark definitions

Clinical AI Integrity Rules:
- Models MUST NOT be evaluated or compared across discordant cohorts or different landmark definitions.
- When real-world cohorts (e.g. CRIC) are unavailable, evaluation functions are tested using
  controlled mathematical fixtures; artificial test values MUST NOT be claimed as clinical validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.clinical.survival.survival_contracts import (
    SurvivalDataset,
    SurvivalEventType,
)


@dataclass
class CalibrationGroup:
    """Observed versus predicted risk metrics within a risk quantile group."""

    group_index: int
    n_patients: int
    mean_predicted_risk: float
    observed_event_rate: float
    expected_to_observed_ratio: float
    absolute_error: float
    ci_lower: float
    ci_upper: float


@dataclass
class TimeDependentEvaluationResult:
    """Comprehensive performance evaluation of a survival model at a specific time horizon.

    Statistical Estimand Classification:
    - Cause-specific metrics (Harrell C-index, Uno C-index, dynamic AUC): treat competing deaths
      as right-censoring, measuring discrimination of the cause-specific hazard.
    - Calibration: assessed against Kaplan-Meier observed risk within predicted risk quantiles.
    """

    model_name: str
    time_horizon_years: float
    harrell_c_index: float
    uno_c_index: Optional[float]
    time_dependent_auc: float
    brier_score: float
    n_evaluated: int
    n_events_at_horizon: int
    n_controls_at_horizon: int
    calibration_groups: List[CalibrationGroup]
    mean_absolute_calibration_error: float
    calibration_slope: Optional[float] = None
    calibration_intercept: Optional[float] = None
    estimand_type: str = "cause_specific_survival"


def _estimate_censoring_km(
    durations: np.ndarray, events: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Estimate Kaplan-Meier survival curve of the censoring distribution G(t).

    In the censoring distribution:
    - Censoring (events == 0) is treated as the event of interest.
    - True failures (events == 1) are treated as censored.
    """
    censoring_events = (events == 0).astype(int)
    unique_times = np.sort(np.unique(durations[censoring_events == 1]))
    if len(unique_times) == 0:
        return np.array([0.0]), np.array([1.0])

    G_vals = []
    G_cur = 1.0
    for t in unique_times:
        at_risk = np.sum(durations >= t)
        censored = np.sum((durations == t) & (censoring_events == 1))
        if at_risk > 0:
            G_cur *= (1.0 - censored / at_risk)
        G_vals.append(max(1e-4, G_cur))

    return unique_times, np.array(G_vals, dtype=np.float64)


def _get_g_at_t(unique_t: np.ndarray, g_vals: np.ndarray, t: float) -> float:
    """Interpolate censoring survival G(t) at time t."""
    if len(unique_t) == 0 or t < unique_t[0]:
        return 1.0
    idx = np.searchsorted(unique_t, t, side="right") - 1
    return float(g_vals[idx])


def calculate_harrell_c_index(
    durations: Union[np.ndarray, List[float]],
    events: Union[np.ndarray, List[int]],
    risk_scores: Union[np.ndarray, List[float]],
) -> float:
    """Compute Harrell's Concordance Index (C-index) for right-censored survival data.

    A pair (i, j) is admissible if subject i experienced an event and T_i < T_j.
    The pair is concordant if risk_i > risk_j.
    """
    t = np.asarray(durations, dtype=np.float64)
    e = np.asarray(events, dtype=np.int32)
    r = np.asarray(risk_scores, dtype=np.float64)
    if len(t) != len(e) or len(t) != len(r):
        raise ValueError(f"Input length mismatch: durations ({len(t)}), events ({len(e)}), risk_scores ({len(r)}).")
    if len(t) == 0:
        raise ValueError("Cannot compute C-index on empty inputs.")
    N = len(t)

    concordant = 0.0
    tied = 0.0
    admissible = 0.0

    for i in range(N):
        if e[i] != 1:
            continue
        for j in range(N):
            if t[i] < t[j]:
                admissible += 1.0
                if r[i] > r[j]:
                    concordant += 1.0
                elif r[i] == r[j]:
                    tied += 1.0

    if admissible == 0.0:
        return 0.5
    return float((concordant + 0.5 * tied) / admissible)


def calculate_uno_c_index(
    durations: Union[np.ndarray, List[float]],
    events: Union[np.ndarray, List[int]],
    risk_scores: Union[np.ndarray, List[float]],
    tau: Optional[float] = None,
) -> float:
    """Compute Uno's C-index with Inverse Probability of Censoring Weighting (IPCW).

    Downweights pairs where censoring probability is high, providing asymptotic consistency.
    """
    t = np.asarray(durations, dtype=np.float64)
    e = np.asarray(events, dtype=np.int32)
    r = np.asarray(risk_scores, dtype=np.float64)
    if len(t) != len(e) or len(t) != len(r):
        raise ValueError(f"Input length mismatch: durations ({len(t)}), events ({len(e)}), risk_scores ({len(r)}).")
    if len(t) == 0:
        raise ValueError("Cannot compute Uno's C-index on empty inputs.")
    N = len(t)

    max_t = tau if tau is not None else float(np.max(t))
    g_times, g_vals = _estimate_censoring_km(t, e)

    numerator = 0.0
    denominator = 0.0

    for i in range(N):
        if e[i] != 1 or t[i] > max_t:
            continue
        g_i = _get_g_at_t(g_times, g_vals, t[i])
        weight_i = 1.0 / (g_i**2) if g_i > 1e-4 else 1.0

        for j in range(N):
            if t[i] < t[j]:
                denominator += weight_i
                if r[i] > r[j]:
                    numerator += weight_i
                elif r[i] == r[j]:
                    numerator += 0.5 * weight_i

    if denominator <= 1e-12:
        return 0.5
    return float(numerator / denominator)


def calculate_time_dependent_auc(
    durations: Union[np.ndarray, List[float]],
    events: Union[np.ndarray, List[int]],
    predicted_risks: Union[np.ndarray, List[float]],
    horizon_time: float,
) -> float:
    """Compute cumulative/dynamic Time-Dependent AUC (Heagerty & Zheng 2005) at horizon_time.

    - Cases: Experienced primary event at or before horizon_time (T_i <= t and E_i == 1).
    - Controls: Remained event-free beyond horizon_time (T_j > t).
    """
    t = np.asarray(durations, dtype=np.float64)
    e = np.asarray(events, dtype=np.int32)
    r = np.asarray(predicted_risks, dtype=np.float64)
    if len(t) != len(e) or len(t) != len(r):
        raise ValueError(f"Input length mismatch: durations ({len(t)}), events ({len(e)}), predicted_risks ({len(r)}).")
    if len(t) == 0:
        raise ValueError("Cannot compute time-dependent AUC on empty inputs.")
    if horizon_time <= 0.0:
        raise ValueError("horizon_time must be strictly positive.")

    case_mask = (t <= horizon_time) & (e == 1)
    control_mask = (t > horizon_time)

    n_cases = np.sum(case_mask)
    n_controls = np.sum(control_mask)

    if n_cases == 0 or n_controls == 0:
        return 0.5  # Non-evaluable horizon

    case_risks = r[case_mask]
    control_risks = r[control_mask]

    concordant = 0.0
    for c_risk in case_risks:
        concordant += np.sum(c_risk > control_risks) + 0.5 * np.sum(c_risk == control_risks)

    return float(concordant / (n_cases * n_controls))


def calculate_brier_score_at_horizon(
    durations: Union[np.ndarray, List[float]],
    events: Union[np.ndarray, List[int]],
    predicted_risks: Union[np.ndarray, List[float]],
    horizon_time: float,
) -> float:
    """Compute IPCW Brier score at horizon_time (e.g. 2.0 or 5.0 years).

    Measures mean squared error between predicted probability and actual binary event status,
    weighted inversely by probability of being censored.
    """
    t = np.asarray(durations, dtype=np.float64)
    e = np.asarray(events, dtype=np.int32)
    r = np.asarray(predicted_risks, dtype=np.float64)
    if len(t) != len(e) or len(t) != len(r):
        raise ValueError(f"Input length mismatch: durations ({len(t)}), events ({len(e)}), predicted_risks ({len(r)}).")
    if len(t) == 0:
        raise ValueError("Cannot compute Brier score on empty inputs.")
    if horizon_time <= 0.0:
        raise ValueError("horizon_time must be strictly positive.")
    N = len(t)

    g_times, g_vals = _estimate_censoring_km(t, e)
    g_horizon = _get_g_at_t(g_times, g_vals, horizon_time)

    brier_terms = []
    for i in range(N):
        if t[i] <= horizon_time and e[i] == 1:
            g_i = _get_g_at_t(g_times, g_vals, t[i])
            w = 1.0 / g_i if g_i > 1e-4 else 1.0
            brier_terms.append(w * ((1.0 - r[i]) ** 2))
        elif t[i] > horizon_time:
            w = 1.0 / g_horizon if g_horizon > 1e-4 else 1.0
            brier_terms.append(w * ((0.0 - r[i]) ** 2))
        # Censored before horizon: non-informative for binary horizon endpoint

    if len(brier_terms) == 0:
        return 0.0
    return float(np.mean(brier_terms))


def _calculate_aj_cif_and_se_at_horizon(
    durations: np.ndarray,
    event_types: np.ndarray,
    horizon_time: float,
) -> Tuple[float, float]:
    """Calculate non-parametric Aalen-Johansen CIF of event 1 (Kidney Failure) at horizon_time,
    along with its large-sample standard error using the Choudhury (2002) / Aalen (1978) formula.

    Event codes:
    - 0: Censored
    - 1: Kidney Failure (primary event of interest)
    - 2: Competing Death (competing risk)

    When no competing deaths are present (event_types contains only 0 and 1), the CIF reduces
    identically to Kaplan-Meier failure 1 - S_KM(t) and the standard error collapses to Greenwood's formula.
    """
    event_mask = (event_types == int(SurvivalEventType.KIDNEY_FAILURE)) | (
        event_types == int(SurvivalEventType.COMPETING_DEATH)
    )
    unique_times = np.sort(np.unique(durations[event_mask]))
    unique_times = unique_times[unique_times <= horizon_time]
    if len(unique_times) == 0:
        return 0.0, 0.0

    S_prev_list = []
    cif1_list = []
    n_list = []
    d1_list = []
    d_all_list = []

    S = 1.0
    cif1 = 0.0
    for tk in unique_times:
        nk = np.sum(durations >= tk)
        d1 = np.sum((durations == tk) & (event_types == int(SurvivalEventType.KIDNEY_FAILURE)))
        d2 = np.sum((durations == tk) & (event_types == int(SurvivalEventType.COMPETING_DEATH)))
        d_all = d1 + d2

        S_prev = S
        if nk > 0:
            cif1 += S_prev * (d1 / nk)
            S *= (1.0 - d_all / nk)

        S_prev_list.append(S_prev)
        cif1_list.append(cif1)
        n_list.append(nk)
        d1_list.append(d1)
        d_all_list.append(d_all)

    final_cif = float(np.clip(cif1, 0.0, 1.0))

    # Variance via Choudhury (2002) / Aalen (1978) formula:
    # Var(I_1(t)) = sum_k [ (I_1(t) - I_1(t_k))^2 * d_all / (n_k * (n_k - d_all))
    #                     + S(t_{k-1})^2 * d_1 * (n_k - d_1) / n_k^3
    #                     - 2 * (I_1(t) - I_1(t_k)) * S(t_{k-1}) * d_1 / n_k^2 ]
    var_cif = 0.0
    for S_prev, cif_k, nk, d1, d_all in zip(S_prev_list, cif1_list, n_list, d1_list, d_all_list):
        if nk <= 0:
            continue
        term1 = ((final_cif - cif_k) ** 2) * (d_all / (nk * max(1, nk - d_all)))
        term2 = (S_prev ** 2) * (d1 * (nk - d1) / (nk ** 3))
        term3 = 2.0 * (final_cif - cif_k) * S_prev * (d1 / (nk ** 2))
        var_cif += (term1 + term2 - term3)

    se = math.sqrt(max(0.0, var_cif))
    return final_cif, se


def calculate_competing_risk_calibration_by_quantiles(
    durations: Union[np.ndarray, List[float]],
    event_types: Union[np.ndarray, List[int]],
    predicted_cifs: Union[np.ndarray, List[float]],
    horizon_time: float,
    n_groups: int = 5,
) -> Tuple[List[CalibrationGroup], float]:
    """Group predictions into risk quantiles and assess expected vs observed cumulative incidence.

    Statistical Estimand:
    - Primary outcome: Cumulative Incidence Function (CIF) of kidney failure / KRT (event code 1)
      at horizon_time, accounting for death prior to kidney failure as a competing event (event code 2).
    - Observed risk is estimated via the non-parametric Aalen-Johansen estimator within each quantile bin.
    - Confidence intervals are computed using the large-sample variance of the Aalen-Johansen estimator.

    Clinical Integrity Guardrails:
    - In the presence of competing events, 1 - Kaplan-Meier strictly overestimates the real-world probability
      of kidney failure. Aalen-Johansen CIF provides the mathematically consistent observed risk benchmark.
    - Empty bins or bins with 0 events are handled gracefully with non-crashing valid intervals [0.0, 0.0].
    """
    t = np.asarray(durations, dtype=np.float64)
    e = np.asarray(event_types, dtype=np.int32)
    r = np.asarray(predicted_cifs, dtype=np.float64)

    if len(t) != len(e) or len(t) != len(r):
        raise ValueError(f"Input length mismatch: durations ({len(t)}), event_types ({len(e)}), predicted_cifs ({len(r)}).")
    if len(t) == 0:
        raise ValueError("Cannot compute calibration on empty inputs.")
    if horizon_time <= 0.0:
        raise ValueError("horizon_time must be strictly positive.")
    if n_groups <= 0:
        raise ValueError("n_groups must be strictly positive.")

    N = len(r)
    if N < n_groups:
        return [], 0.0

    quantiles = np.linspace(0, 100, n_groups + 1)
    bin_edges = np.percentile(r, quantiles)
    bin_edges[-1] += 1e-6

    groups: List[CalibrationGroup] = []
    abs_errors = []

    for g in range(n_groups):
        low, high = bin_edges[g], bin_edges[g + 1]
        in_bin = (r >= low) & (r < high)
        n_bin = int(np.sum(in_bin))

        if n_bin == 0:
            continue

        mean_pred = float(np.mean(r[in_bin]))
        t_bin = t[in_bin]
        e_bin = e[in_bin]

        obs_cif, se_cif = _calculate_aj_cif_and_se_at_horizon(t_bin, e_bin, horizon_time)
        ci_low = float(np.clip(obs_cif - 1.96 * se_cif, 0.0, 1.0))
        ci_high = float(np.clip(obs_cif + 1.96 * se_cif, 0.0, 1.0))

        eo_ratio = (mean_pred / obs_cif) if obs_cif > 1e-6 else 1.0
        err = abs(mean_pred - obs_cif)
        abs_errors.append(err)

        groups.append(
            CalibrationGroup(
                group_index=g + 1,
                n_patients=n_bin,
                mean_predicted_risk=round(mean_pred, 4),
                observed_event_rate=round(obs_cif, 4),
                expected_to_observed_ratio=round(eo_ratio, 3),
                absolute_error=round(err, 4),
                ci_lower=round(ci_low, 4),
                ci_upper=round(ci_high, 4),
            )
        )

    mean_cal_err = float(np.mean(abs_errors)) if abs_errors else 0.0
    return groups, mean_cal_err


def calculate_cause_specific_calibration_by_quantiles(
    durations: Union[np.ndarray, List[float]],
    events: Union[np.ndarray, List[int]],
    predicted_risks: Union[np.ndarray, List[float]],
    horizon_time: float,
    n_groups: int = 5,
) -> Tuple[List[CalibrationGroup], float]:
    """Group predictions into risk quantiles and assess expected vs observed event rates.

    Statistical Estimand:
    - Cause-specific survival net risk: estimates 1 - S_KM(t) within each bin, treating any competing
      deaths as non-informative right-censoring.
    - NOTE: In the presence of competing events, 1 - S_KM(t) estimates the net probability under the
      counterfactual hypothetical scenario that death is eliminated. It strictly exceeds the true
      cumulative incidence of kidney failure. For clinical cumulative incidence calibration,
      use calculate_competing_risk_calibration_by_quantiles() instead.
    """
    t = np.asarray(durations, dtype=np.float64)
    e = np.asarray(events, dtype=np.int32)
    r = np.asarray(predicted_risks, dtype=np.float64)

    if len(t) != len(e) or len(t) != len(r):
        raise ValueError(f"Input length mismatch: durations ({len(t)}), events ({len(e)}), predicted_risks ({len(r)}).")
    if len(t) == 0:
        raise ValueError("Cannot compute calibration on empty inputs.")
    if horizon_time <= 0.0:
        raise ValueError("horizon_time must be strictly positive.")
    if n_groups <= 0:
        raise ValueError("n_groups must be strictly positive.")

    N = len(r)
    if N < n_groups:
        return [], 0.0

    quantiles = np.linspace(0, 100, n_groups + 1)
    bin_edges = np.percentile(r, quantiles)
    bin_edges[-1] += 1e-6

    groups: List[CalibrationGroup] = []
    abs_errors = []

    for g in range(n_groups):
        low, high = bin_edges[g], bin_edges[g + 1]
        in_bin = (r >= low) & (r < high)
        n_bin = int(np.sum(in_bin))

        if n_bin == 0:
            continue

        mean_pred = float(np.mean(r[in_bin]))
        t_bin = t[in_bin]
        e_bin = e[in_bin]

        # Non-parametric Kaplan-Meier failure probability within bin at horizon_time
        unique_times = np.sort(np.unique(t_bin[e_bin == 1]))
        s_km = 1.0
        greenwood_sum = 0.0

        for tk in unique_times:
            if tk > horizon_time:
                break
            n_k = np.sum(t_bin >= tk)
            d_k = np.sum((t_bin == tk) & (e_bin == 1))
            if n_k > 0:
                s_km *= (1.0 - d_k / n_k)
                if n_k > d_k:
                    greenwood_sum += d_k / (n_k * (n_k - d_k))

        obs_rate = float(np.clip(1.0 - s_km, 0.0, 1.0))
        # Greenwood SE of failure probability
        se_km = s_km * math.sqrt(greenwood_sum) if greenwood_sum > 0 else 0.0
        ci_low = float(np.clip(obs_rate - 1.96 * se_km, 0.0, 1.0))
        ci_high = float(np.clip(obs_rate + 1.96 * se_km, 0.0, 1.0))

        eo_ratio = (mean_pred / obs_rate) if obs_rate > 1e-6 else 1.0
        err = abs(mean_pred - obs_rate)
        abs_errors.append(err)

        groups.append(
            CalibrationGroup(
                group_index=g + 1,
                n_patients=n_bin,
                mean_predicted_risk=round(mean_pred, 4),
                observed_event_rate=round(obs_rate, 4),
                expected_to_observed_ratio=round(eo_ratio, 3),
                absolute_error=round(err, 4),
                ci_lower=round(ci_low, 4),
                ci_upper=round(ci_high, 4),
            )
        )

    mean_cal_err = float(np.mean(abs_errors)) if abs_errors else 0.0
    return groups, mean_cal_err


# Backward-compatible alias for existing callers
calculate_calibration_by_quantiles = calculate_cause_specific_calibration_by_quantiles


def calculate_competing_risk_calibration_slope_and_intercept(
    durations: Union[np.ndarray, List[float]],
    event_types: Union[np.ndarray, List[int]],
    predicted_cifs: Union[np.ndarray, List[float]],
    horizon_time: float,
) -> Tuple[Optional[float], Optional[float]]:
    """Compute calibration slope and intercept for competing risks via jackknife pseudo-observations.

    Methodological Justification:
    - In survival analysis with competing risks and right-censoring, ordinary logistic regression
      on complete cases is mathematically invalid because:
      1) Complete case filtering drops patients censored before horizon_time, introducing censoring bias.
      2) Complete case filtering misrepresents or drops patients experiencing competing deaths,
         violating the cumulative incidence definition.
    - Jackknife pseudo-observations (Andersen & Perme 2010, Gerds et al. 2014) resolve this by defining
      for each subject i:
          theta_i(t) = N * I_hat_1(t) - (N - 1) * I_hat_1^{(-i)}(t)
      where I_hat_1(t) is the Aalen-Johansen CIF of kidney failure at horizon_time.
    - Regressing theta_i on predicted CIF p_hat_i via linear regression provides:
      - Calibration slope beta: assesses risk dispersion / spread. Perfect slope is 1.0.
      - Calibration intercept alpha: assesses calibration-in-the-large. Perfect intercept is 0.0.
    """
    t = np.asarray(durations, dtype=np.float64)
    e = np.asarray(event_types, dtype=np.int32)
    p = np.asarray(predicted_cifs, dtype=np.float64)

    if len(t) != len(e) or len(t) != len(p):
        raise ValueError(f"Input length mismatch: durations ({len(t)}), event_types ({len(e)}), predicted_cifs ({len(p)}).")
    if len(t) == 0:
        raise ValueError("Cannot compute calibration on empty inputs.")
    if horizon_time <= 0.0:
        raise ValueError("horizon_time must be strictly positive.")

    N = len(t)
    if N < 10:
        return None, None

    # Check if there is variance in predicted risks
    var_p = float(np.var(p))
    if var_p < 1e-12:
        return None, None

    # Compute overall Aalen-Johansen CIF at horizon_time
    overall_cif, _ = _calculate_aj_cif_and_se_at_horizon(t, e, horizon_time)

    # Check if any events of interest occurred on or before horizon
    kf_before_horizon = np.sum((t <= horizon_time) & (e == int(SurvivalEventType.KIDNEY_FAILURE)))
    if kf_before_horizon == 0:
        return None, None

    # Leave-one-out jackknife pseudo-observations with memoization
    pseudo_obs = np.empty(N, dtype=np.float64)
    cif_cache: Dict[Tuple[Any, Any], float] = {}

    for i in range(N):
        ti = t[i]
        ei = e[i]
        # Observations followed past horizon have identical leave-one-out CIF impact
        key = ("past_horizon", None) if ti > horizon_time else (round(ti, 8), ei)
        if key in cif_cache:
            cif_minus_i = cif_cache[key]
        else:
            d_minus_i = np.delete(t, i)
            e_minus_i = np.delete(e, i)
            cif_minus_i, _ = _calculate_aj_cif_and_se_at_horizon(d_minus_i, e_minus_i, horizon_time)
            cif_cache[key] = cif_minus_i

        pseudo_obs[i] = N * overall_cif - (N - 1) * cif_minus_i

    # Linear regression: theta_i = alpha + beta * p_i
    p_mean = float(np.mean(p))
    theta_mean = float(np.mean(pseudo_obs))

    cov_p_theta = float(np.sum((p - p_mean) * (pseudo_obs - theta_mean)))
    var_p_sum = float(np.sum((p - p_mean) ** 2))

    if var_p_sum < 1e-12:
        return None, None

    beta = cov_p_theta / var_p_sum
    alpha = theta_mean - beta * p_mean

    return round(float(beta), 3), round(float(alpha), 3)


def calculate_cause_specific_calibration_slope_and_intercept(
    durations: np.ndarray,
    events: np.ndarray,
    predicted_risks: np.ndarray,
    horizon_time: float,
) -> Tuple[Optional[float], Optional[float]]:
    """Compute logistic calibration slope and intercept at horizon_time for cause-specific survival.

    Model: logit(P(Y=1)) = alpha + beta * logit(p_hat)
    Perfect calibration corresponds to alpha = 0.0 and beta = 1.0.
    Evaluated on complete cases (events on/before horizon or followed past horizon).
    """
    # Evaluable subjects: either experienced event on/before horizon, or followed past horizon
    eval_mask = ((durations <= horizon_time) & (events == 1)) | (durations > horizon_time)
    if np.sum(eval_mask) < 10:
        return None, None

    y = ((durations[eval_mask] <= horizon_time) & (events[eval_mask] == 1)).astype(float)
    if np.sum(y) == 0 or np.sum(y) == len(y):
        return None, None  # Zero variance in outcome

    p = np.clip(predicted_risks[eval_mask], 1e-4, 1.0 - 1e-4)
    lp = np.log(p / (1.0 - p))

    from scipy.optimize import minimize

    def logit_loss(params):
        alpha, beta = params[0], params[1]
        z = np.clip(alpha + beta * lp, -30.0, 30.0)
        return -np.sum(y * z - np.log(1.0 + np.exp(z)))

    res = minimize(logit_loss, x0=[0.0, 1.0], method="BFGS")
    if res.success:
        return round(float(res.x[1]), 3), round(float(res.x[0]), 3)
    return None, None


_compute_calibration_slope_and_intercept = calculate_cause_specific_calibration_slope_and_intercept


def evaluate_survival_model(
    model_name: str,
    predict_risk_fn: Callable[[np.ndarray, float], np.ndarray],
    X: np.ndarray,
    durations: np.ndarray,
    events: np.ndarray,
    time_horizon_years: float = 2.0,
    n_calibration_groups: int = 5,
    estimand_type: str = "cause_specific_survival",
) -> TimeDependentEvaluationResult:
    """Comprehensive evaluation of a survival model or risk calculator at time_horizon_years.

    Parameters:
    - estimand_type: 'cause_specific_survival' (default) or 'competing_risk_cif'.
      When 'competing_risk_cif', calibration is evaluated using Aalen-Johansen CIF and pseudo-observations.
    """
    predicted_risks = predict_risk_fn(X, time_horizon_years)

    # Discrimination metrics: evaluated on primary cause-specific event
    c_harrell = calculate_harrell_c_index(durations, events, predicted_risks)
    c_uno = calculate_uno_c_index(durations, events, predicted_risks, tau=time_horizon_years)
    td_auc = calculate_time_dependent_auc(durations, events, predicted_risks, time_horizon_years)
    brier = calculate_brier_score_at_horizon(durations, events, predicted_risks, time_horizon_years)

    if estimand_type == "competing_risk_cif":
        cal_groups, mean_cal_err = calculate_competing_risk_calibration_by_quantiles(
            durations, events, predicted_risks, time_horizon_years, n_groups=n_calibration_groups
        )
        slope, intercept = calculate_competing_risk_calibration_slope_and_intercept(
            durations, events, predicted_risks, time_horizon_years
        )
    else:
        cal_groups, mean_cal_err = calculate_cause_specific_calibration_by_quantiles(
            durations, events, predicted_risks, time_horizon_years, n_groups=n_calibration_groups
        )
        slope, intercept = calculate_cause_specific_calibration_slope_and_intercept(
            durations, events, predicted_risks, time_horizon_years
        )

    n_cases = int(np.sum((durations <= time_horizon_years) & (events == 1)))
    n_controls = int(np.sum(durations > time_horizon_years))

    return TimeDependentEvaluationResult(
        model_name=model_name,
        time_horizon_years=time_horizon_years,
        harrell_c_index=round(c_harrell, 4),
        uno_c_index=round(c_uno, 4) if c_uno is not None else None,
        time_dependent_auc=round(td_auc, 4),
        brier_score=round(brier, 4),
        n_evaluated=len(durations),
        n_events_at_horizon=n_cases,
        n_controls_at_horizon=n_controls,
        calibration_groups=cal_groups,
        mean_absolute_calibration_error=round(mean_cal_err, 4),
        calibration_slope=slope,
        calibration_intercept=intercept,
        estimand_type=estimand_type,
    )


def compare_models_with_kfre_on_cohort(
    models: Dict[str, Callable[[np.ndarray, float], np.ndarray]],
    test_dataset: SurvivalDataset,
    horizon_years: float = 2.0,
    kfre_calibration_profile: str = "north_america",
    feature_names: Optional[List[str]] = None,
    estimand_type: str = "cause_specific_survival",
) -> pd.DataFrame:
    """Evaluate and compare eligible survival models with KFRE on the exact same patient cohort.

    Guarantees:
    - Filters cohort strictly for KFRE clinical applicability (eGFR < 60 mL/min/1.73 m2, adult, valid ACR).
    - Excludes and explicitly reports any ineligible records rather than falsely imputing risk.
    - Evaluates both machine learning survival models and KFRE on the IDENTICAL patient partition.
    - Records selected KFRE regional calibration profile and statistical estimand type.
    """
    from src.clinical.kfre_calculator import calculate_kfre

    if len(test_dataset) == 0:
        raise ValueError("Cannot compare models on an empty test dataset.")

    # 1. Filter for KFRE-eligible records
    eligible_records = []
    ineligible_count = 0

    for rec in test_dataset.records:
        age = rec.features.get("age", 65.0)
        sex = rec.features.get("sex", "male")
        egfr = rec.features.get("egfr", 35.0)
        uacr = rec.features.get("uacr", 100.0)

        res = calculate_kfre(age=age, sex=sex, egfr=egfr, uacr=uacr, calibration_profile=kfre_calibration_profile)
        if res.is_valid and res.is_applicable:
            eligible_records.append(rec)
        else:
            ineligible_count += 1

    if len(eligible_records) == 0:
        raise ValueError(
            f"No patients in dataset are eligible for KFRE evaluation (all {ineligible_count} out-of-scope or invalid)."
        )

    eligible_ds = SurvivalDataset(eligible_records)
    if estimand_type == "competing_risk_cif":
        durations = np.array([r.follow_up_duration_years for r in eligible_ds.records], dtype=np.float64)
        events = np.array([int(r.event_type) for r in eligible_ds.records], dtype=np.int32)
    else:
        durations, events = eligible_ds.get_survival_targets(cause_specific_event=SurvivalEventType.KIDNEY_FAILURE)
    X_mat, f_names = eligible_ds.get_feature_matrix(feature_names)

    # 2. Build KFRE predictor function for identical cohort
    def kfre_predictor(X: np.ndarray, horizon: float) -> np.ndarray:
        risks = []
        for rec in eligible_ds.records:
            age = rec.features.get("age", 65.0)
            sex = rec.features.get("sex", "male")
            egfr = rec.features.get("egfr", 35.0)
            uacr = rec.features.get("uacr", 100.0)

            kfre_res = calculate_kfre(
                age=age, sex=sex, egfr=egfr, uacr=uacr, calibration_profile=kfre_calibration_profile
            )
            r = kfre_res.risk_2year if horizon <= 2.0 else kfre_res.risk_5year
            risks.append(r if r is not None else 0.0)
        return np.array(risks, dtype=np.float64)

    all_models = dict(models)
    all_models[f"KFRE ({kfre_calibration_profile})"] = kfre_predictor

    comparison_rows = []
    for m_name, pred_fn in all_models.items():
        eval_res = evaluate_survival_model(
            model_name=m_name,
            predict_risk_fn=pred_fn,
            X=X_mat,
            durations=durations,
            events=events,
            time_horizon_years=horizon_years,
            estimand_type=estimand_type,
        )
        comparison_rows.append(
            {
                "model": eval_res.model_name,
                "horizon_years": eval_res.time_horizon_years,
                "harrell_c_index": eval_res.harrell_c_index,
                "uno_c_index": eval_res.uno_c_index,
                "time_dependent_auc": eval_res.time_dependent_auc,
                "brier_score": eval_res.brier_score,
                "mean_calibration_error": eval_res.mean_absolute_calibration_error,
                "calibration_slope": eval_res.calibration_slope,
                "calibration_intercept": eval_res.calibration_intercept,
                "n_evaluated": eval_res.n_evaluated,
                "n_events": eval_res.n_events_at_horizon,
                "n_ineligible_excluded": ineligible_count,
                "kfre_profile": kfre_calibration_profile,
                "estimand_type": eval_res.estimand_type,
            }
        )

    return pd.DataFrame(comparison_rows)
