"""Competing-risk data representation and Fine-Gray pathway for Engine 3.

In Chronic Kidney Disease (CKD) progression, death prior to kidney replacement therapy (KRT)
is a major competing event, particularly in elderly or diabetic cohorts.

Clinical & Methodological Guardrails:
- The primary clinical outcome is kidney failure (KRT: dialysis or transplant).
- Death before kidney failure is a COMPETING EVENT, not ordinary non-informative censoring.
- Treating competing deaths as non-informative censoring (the 1-Kaplan-Meier approach) violates
  independence assumptions and mathematically overestimates the true cumulative incidence of kidney failure.
- When Fine-Gray libraries ('lifelines>=0.27.0' or 'cmprsk') are unavailable, standard Cox PH or RSF
  MUST NOT be masqueraded as competing-risk estimators.
- The Aalen-Johansen non-parametric estimator is provided as the mathematical gold standard
  for cumulative incidence estimation under competing risks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.clinical.survival.survival_contracts import (
    SurvivalDataset,
    SurvivalEventType,
    SurvivalLandmarkRecord,
)


class FineGrayDependencyUnavailableError(RuntimeError):
    """Raised when Fine-Gray estimator is invoked but the required survival library is not installed."""

    pass


@dataclass
class CumulativeIncidenceResult:
    """Non-parametric Aalen-Johansen cumulative incidence estimates at specified time horizons."""

    time_horizons: List[float]
    cif_kidney_failure: List[float]
    cif_competing_death: List[float]
    overall_event_free_survival: List[float]
    n_at_risk_initial: int
    n_kidney_failure_total: int
    n_competing_death_total: int


def calculate_aalen_johansen_cif(
    dataset: SurvivalDataset,
    time_horizons: Optional[List[float]] = None,
) -> CumulativeIncidenceResult:
    """Compute non-parametric Cumulative Incidence Function (CIF) via Aalen-Johansen estimator.

    Accounts properly for competing events (death before kidney failure) without bias.

    Formula:
        I_1(t) = sum_{t_k <= t} S(t_{k-1}) * (d_{1k} / n_k)
        where S(t) is overall survival from any cause, d_{1k} is kidney failure events at t_k,
        and n_k is the number of individuals at risk at t_k.
    """
    if len(dataset) == 0:
        raise ValueError("Cannot calculate CIF on an empty SurvivalDataset.")

    horizons = time_horizons if time_horizons is not None else [1.0, 2.0, 3.0, 5.0]

    durations = np.array([r.follow_up_duration_years for r in dataset.records], dtype=np.float64)
    event_types = np.array([int(r.event_type) for r in dataset.records], dtype=np.int32)
    N = len(durations)

    # Distinct event times across all causes (1 or 2)
    event_mask = (event_types == int(SurvivalEventType.KIDNEY_FAILURE)) | (
        event_types == int(SurvivalEventType.COMPETING_DEATH)
    )
    unique_event_times = np.sort(np.unique(durations[event_mask]))

    # Step-by-step product limit
    S_overall = 1.0  # Overall survival from any event
    cif_1 = 0.0  # Cumulative incidence of kidney failure
    cif_2 = 0.0  # Cumulative incidence of competing death

    time_grid = []
    cif_1_grid = []
    cif_2_grid = []
    S_grid = []

    for t_k in unique_event_times:
        n_k = np.sum(durations >= t_k)
        d_1k = np.sum((durations == t_k) & (event_types == int(SurvivalEventType.KIDNEY_FAILURE)))
        d_2k = np.sum((durations == t_k) & (event_types == int(SurvivalEventType.COMPETING_DEATH)))
        d_all = d_1k + d_2k

        if n_k > 0:
            # Increment CIF using S(t_{k-1})
            cif_1 += S_overall * (d_1k / n_k)
            cif_2 += S_overall * (d_2k / n_k)
            S_overall *= (1.0 - d_all / n_k)

        time_grid.append(t_k)
        cif_1_grid.append(cif_1)
        cif_2_grid.append(cif_2)
        S_grid.append(S_overall)

    # Interpolate at requested horizons
    cif_1_out = []
    cif_2_out = []
    S_out = []

    for h in horizons:
        if len(time_grid) == 0 or h < time_grid[0]:
            cif_1_out.append(0.0)
            cif_2_out.append(0.0)
            S_out.append(1.0)
        else:
            idx = np.searchsorted(time_grid, h, side="right") - 1
            cif_1_out.append(float(np.clip(cif_1_grid[idx], 0.0, 1.0)))
            cif_2_out.append(float(np.clip(cif_2_grid[idx], 0.0, 1.0)))
            S_out.append(float(np.clip(S_grid[idx], 0.0, 1.0)))

    n_kf = int(np.sum(event_types == int(SurvivalEventType.KIDNEY_FAILURE)))
    n_death = int(np.sum(event_types == int(SurvivalEventType.COMPETING_DEATH)))

    return CumulativeIncidenceResult(
        time_horizons=horizons,
        cif_kidney_failure=cif_1_out,
        cif_competing_death=cif_2_out,
        overall_event_free_survival=S_out,
        n_at_risk_initial=N,
        n_kidney_failure_total=n_kf,
        n_competing_death_total=n_death,
    )


def prepare_fine_gray_dataframe(
    dataset: SurvivalDataset,
    feature_names: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Format a SurvivalDataset into the standardized tabular schema required for Fine-Gray regression.

    Columns produced:
        - patient_id
        - duration: Follow-up duration in years (> 0)
        - event: Event code (0 = Censored, 1 = Kidney Failure, 2 = Competing Death)
        - feat_<name>: Candidate predictors available at landmark
    """
    if len(dataset) == 0:
        raise ValueError("Cannot prepare Fine-Gray data from empty dataset.")

    rows = []
    selected_features = feature_names if feature_names else sorted(list(dataset.records[0].features.keys()))

    for rec in dataset.records:
        row = {
            "patient_id": rec.patient_id,
            "duration": rec.follow_up_duration_years,
            "event": int(rec.event_type),
        }
        for f in selected_features:
            row[f"feat_{f}"] = rec.features[f]
        rows.append(row)

    return pd.DataFrame(rows)


class DeferredFineGrayEstimator:
    """Explicit placeholder and contract specification for Fine-Gray subdistribution hazards model.

    This class enforces strict clinical safety rules:
    When the required external survival library ('lifelines>=0.27.0' or 'cmprsk') is unavailable,
    it refuses to substitute standard Cox PH or RSF, which would yield biased overestimation of risk.
    """

    def __init__(self):
        self.is_library_available = False
        self._check_library_status()

    def _check_library_status(self) -> None:
        try:
            import lifelines
            if hasattr(lifelines, "FineGrayFitter") or hasattr(lifelines.fitters, "fine_gray_fitter"):
                self.is_library_available = True
        except ImportError:
            self.is_library_available = False

    def fit(self, *args, **kwargs) -> Any:
        """Attempt to fit Fine-Gray model; raises informative error if library is missing."""
        if not self.is_library_available:
            raise FineGrayDependencyUnavailableError(
                "Fine-Gray subdistribution hazards model is DEFERRED. Dependency blocker: 'lifelines' "
                "(specifically lifelines.FineGrayFitter) is not installed in the local virtual environment.\n"
                "CLINICAL SAFETY MANDATE:\n"
                "- Ordinary Cox regression MUST NOT be used as a substitute for Fine-Gray competing-risk modeling.\n"
                "- Standard Random Survival Forest MUST NOT be masqueraded as a competing-risk model.\n"
                "- Treating competing deaths as non-informative censoring artificially inflates the cumulative "
                "incidence of kidney failure in older and multimorbid patient populations.\n"
                "ACTION REQUIRED:\n"
                "To enable parametric Fine-Gray regression, install 'lifelines>=0.27.0' via `.venv\\Scripts\\pip.exe`. "
                "In the interim, use non-parametric Aalen-Johansen CIF via `calculate_aalen_johansen_cif()`."
            )

    def predict_cumulative_incidence(self, *args, **kwargs) -> Any:
        """Attempt to predict cumulative incidence; raises informative error if library is missing."""
        if not self.is_library_available:
            raise FineGrayDependencyUnavailableError(
                "Fine-Gray predictions unavailable: estimator is deferred pending 'lifelines' installation."
            )


@dataclass(frozen=True)
class CauseSpecificCIFPrediction:
    """Personalized competing-risk cumulative incidence prediction for an individual patient.

    Guarantees:
    - cif_kidney_failure + cif_competing_death <= 1.0
    - cause_specific_net_risk_kf >= cif_kidney_failure (with difference equal to competing_risk_reduction)
    """

    patient_id: str
    time_horizon_years: float
    cif_kidney_failure: float
    cif_competing_death: float
    overall_survival_probability: float
    cause_specific_net_risk_kf: float
    competing_risk_reduction: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "time_horizon_years": self.time_horizon_years,
            "cif_kidney_failure": round(self.cif_kidney_failure, 4),
            "cif_competing_death": round(self.cif_competing_death, 4),
            "overall_survival_probability": round(self.overall_survival_probability, 4),
            "cause_specific_net_risk_kf": round(self.cause_specific_net_risk_kf, 4),
            "competing_risk_reduction": round(self.competing_risk_reduction, 4),
        }


class CauseSpecificCumulativeIncidenceModel:
    """Personalized competing-risk cumulative incidence model via cause-specific hazard integration.

    Methodological Justification:
    - When a single cause-specific model is evaluated, its survival function complement 1 - S_1(t)
      estimates net risk under the counterfactual assumption that competing death is abolished.
    - To obtain personalized Cumulative Incidence Function (CIF) without Fine-Gray library dependencies,
      two separate cause-specific proportional hazards models are fitted:
          Model 1: Hazard of Kidney Failure (competing death censored)
          Model 2: Hazard of Competing Death (kidney failure censored)
    - The personalized cumulative incidence for patient i is obtained by numerical product-limit integration:
          CIF_{1i}(t) = sum_{tau_k <= t} S_{overall, i}(tau_{k-1}) * [1 - exp(-dLambda_{1i}(tau_k))] * exp(-0.5 * dLambda_{2i}(tau_k))
      where S_{overall, i}(u) = exp(-(Lambda_{1i}(u) + Lambda_{2i}(u))).
    """

    def __init__(self, feature_names: Optional[List[str]] = None) -> None:
        self.feature_names = feature_names
        self.model_kf: Optional[Any] = None
        self.model_death: Optional[Any] = None
        self.distinct_times_: np.ndarray = np.array([])
        self.is_fitted: bool = False

    def fit(
        self,
        dataset: SurvivalDataset,
        feature_names: Optional[List[str]] = None,
    ) -> CauseSpecificCumulativeIncidenceModel:
        """Fit cause-specific models for kidney failure and competing death on a SurvivalDataset."""
        from src.clinical.survival.cox_model import (
            CoxPHConfig,
            CoxProportionalHazardsModel,
        )

        f_names = feature_names or self.feature_names
        if len(dataset) == 0:
            raise ValueError("Cannot fit CauseSpecificCumulativeIncidenceModel on empty dataset.")

        # 1. Kidney Failure outcome (event = 1, death censored)
        d_kf, e_kf = dataset.get_survival_targets(cause_specific_event=SurvivalEventType.KIDNEY_FAILURE)
        # 2. Competing Death outcome (event = 2, KF censored)
        d_death, e_death = dataset.get_survival_targets(cause_specific_event=SurvivalEventType.COMPETING_DEATH)

        X_mat, selected_f = dataset.get_feature_matrix(f_names)
        self.feature_names = selected_f

        # Fit Model 1: Kidney Failure
        self.model_kf = CoxProportionalHazardsModel(CoxPHConfig(l2_penalty=0.05))
        self.model_kf.fit(X_mat, d_kf, e_kf, feature_names=self.feature_names)

        # Fit Model 2: Competing Death
        self.model_death = CoxProportionalHazardsModel(CoxPHConfig(l2_penalty=0.05))
        # Check if any death events exist
        if np.sum(e_death == 1) > 0:
            self.model_death.fit(X_mat, d_death, e_death, feature_names=self.feature_names)
        else:
            self.model_death = None

        # Distinct event times across both causes
        all_durations = np.array([r.follow_up_duration_years for r in dataset.records])
        all_events = np.array([int(r.event_type) for r in dataset.records])
        event_mask = (all_events == int(SurvivalEventType.KIDNEY_FAILURE)) | (
            all_events == int(SurvivalEventType.COMPETING_DEATH)
        )
        self.distinct_times_ = np.sort(np.unique(all_durations[event_mask]))

        self.is_fitted = True
        return self

    def predict_cumulative_incidence(
        self,
        X: np.ndarray,
        time_horizon_years: float,
    ) -> np.ndarray:
        """Predict personalized Cumulative Incidence of kidney failure at time_horizon_years."""
        if not self.is_fitted or self.model_kf is None:
            raise RuntimeError("CauseSpecificCumulativeIncidenceModel must be fitted before predict.")

        X_arr = np.asarray(X, dtype=np.float64)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)

        N = len(X_arr)
        # Evaluate event times <= horizon
        times_eval = self.distinct_times_[self.distinct_times_ <= time_horizon_years]
        if len(times_eval) == 0:
            return np.zeros(N, dtype=np.float64)

        # Individual hazard ratios
        hr1 = np.exp(np.clip(X_arr @ self.model_kf.coefficients_, -20.0, 20.0))
        if self.model_death is not None:
            hr2 = np.exp(np.clip(X_arr @ self.model_death.coefficients_, -20.0, 20.0))
        else:
            hr2 = np.zeros(N, dtype=np.float64)

        # Baseline cumulative hazards at distinct times
        def _get_cum_haz(t_eval, m):
            if m is None or len(m.baseline_event_times_) == 0:
                return np.zeros_like(t_eval)
            idx = np.searchsorted(m.baseline_event_times_, t_eval, side="right") - 1
            res = np.zeros_like(t_eval)
            valid = idx >= 0
            res[valid] = m.baseline_cum_hazard_[idx[valid]]
            return res

        H01_vals = _get_cum_haz(times_eval, self.model_kf)
        dH01 = np.diff(np.insert(H01_vals, 0, 0.0))

        if self.model_death is not None:
            H02_vals = _get_cum_haz(times_eval, self.model_death)
            dH02 = np.diff(np.insert(H02_vals, 0, 0.0))
        else:
            dH02 = np.zeros_like(dH01)

        cif1_out = np.zeros(N, dtype=np.float64)

        for i in range(N):
            dL1_i = dH01 * hr1[i]
            dL2_i = dH02 * hr2[i]
            dL_all_i = dL1_i + dL2_i

            S_prev = 1.0
            cif_i = 0.0
            for k in range(len(times_eval)):
                # Non-parametric product-limit integration with mid-interval competing death adjustment
                p_event1 = (1.0 - math.exp(-dL1_i[k])) * math.exp(-0.5 * dL2_i[k])
                cif_i += S_prev * p_event1
                S_prev *= math.exp(-dL_all_i[k])

            cif1_out[i] = float(np.clip(cif_i, 0.0, 1.0))

        return cif1_out

    def predict_patient(
        self,
        record: SurvivalLandmarkRecord,
        time_horizon_years: float,
    ) -> CauseSpecificCIFPrediction:
        """Generate structured personalized CIF prediction for an individual record."""
        X_vec = np.array([[record.features.get(f, 0.0) for f in (self.feature_names or [])]])
        cif_kf = float(self.predict_cumulative_incidence(X_vec, time_horizon_years)[0])

        # Net risk without competing death
        lp1 = float((X_vec @ self.model_kf.coefficients_)[0])
        hr1 = math.exp(float(np.clip(lp1, -20.0, 20.0)))
        if len(self.model_kf.baseline_event_times_) > 0:
            idx = np.searchsorted(self.model_kf.baseline_event_times_, time_horizon_years, side="right") - 1
            H01_at_t = float(self.model_kf.baseline_cum_hazard_[idx]) if idx >= 0 else 0.0
        else:
            H01_at_t = 0.0
        net_risk = float(np.clip(1.0 - math.exp(-H01_at_t * hr1), 0.0, 1.0))

        # Competing death CIF (reverse event integration)
        cif_death = 0.0
        if self.model_death is not None:
            # Symmetrically evaluate CIF of death
            times_eval = self.distinct_times_[self.distinct_times_ <= time_horizon_years]
            if len(times_eval) > 0:
                def _get_haz(t_eval, m):
                    if m is None or len(m.baseline_event_times_) == 0:
                        return np.zeros_like(t_eval)
                    idx_arr = np.searchsorted(m.baseline_event_times_, t_eval, side="right") - 1
                    res = np.zeros_like(t_eval)
                    val = idx_arr >= 0
                    res[val] = m.baseline_cum_hazard_[idx_arr[val]]
                    return res

                H01_vals = _get_haz(times_eval, self.model_kf)
                dH01 = np.diff(np.insert(H01_vals, 0, 0.0))
                H02_vals = _get_haz(times_eval, self.model_death)
                dH02 = np.diff(np.insert(H02_vals, 0, 0.0))

                lp2 = float((X_vec @ self.model_death.coefficients_)[0])
                hr2 = math.exp(float(np.clip(lp2, -20.0, 20.0)))
                dL1 = dH01 * hr1
                dL2 = dH02 * hr2
                dL_all = dL1 + dL2

                S_prev = 1.0
                for k in range(len(times_eval)):
                    p_event2 = (1.0 - math.exp(-dL2[k])) * math.exp(-0.5 * dL1[k])
                    cif_death += S_prev * p_event2
                    S_prev *= math.exp(-dL_all[k])

        cif_death = float(np.clip(cif_death, 0.0, 1.0))
        surv_prob = float(np.clip(1.0 - cif_kf - cif_death, 0.0, 1.0))
        reduction = float(max(0.0, net_risk - cif_kf))

        return CauseSpecificCIFPrediction(
            patient_id=record.patient_id,
            time_horizon_years=time_horizon_years,
            cif_kidney_failure=round(cif_kf, 4),
            cif_competing_death=round(cif_death, 4),
            overall_survival_probability=round(surv_prob, 4),
            cause_specific_net_risk_kf=round(net_risk, 4),
            competing_risk_reduction=round(reduction, 4),
        )
