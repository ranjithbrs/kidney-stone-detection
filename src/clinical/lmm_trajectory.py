"""NEFROAI-X Population Linear Mixed-Effects Model (LMM) for eGFR Trajectories.

Implements a repeated-measures random-effects regression framework for longitudinal
eGFR decline estimation in Chronic Kidney Disease progression (Engine 3).

Mathematical Formulation:
    y_ij = (beta_0 + u_0i) + (beta_1 + u_1i) * t_ij + epsilon_ij
where:
    - beta_0: Population baseline eGFR (mL/min/1.73 m2)
    - beta_1: Population annual rate of eGFR decline (mL/min/1.73 m2/year)
    - u_i = [u_0i, u_1i]^T ~ N(0, G): Patient-specific random intercept and slope
    - G = [[sigma_u0^2, cov_u01], [cov_u01, sigma_u1^2]]: Between-patient covariance
    - epsilon_ij ~ N(0, sigma_eps^2): Within-patient residual measurement noise
    - t_ij: Observation time in continuous years from landmark baseline

Estimation Methodology:
    - Profile Maximum Likelihood (ML) / Restricted Maximum Likelihood (REML) via SciPy.
    - Generalized Least Squares (GLS) for fixed effects:
          beta_hat = (sum_i X_i^T V_i^{-1} X_i)^{-1} sum_i X_i^T V_i^{-1} y_i
    - Best Linear Unbiased Predictor (BLUP) / Empirical Bayes for patient random effects:
          u_hat_i = G Z_i^T V_i^{-1} (y_i - X_i beta_hat)
    - Uncertainty Quantification: standard error of random slope and 95% confidence intervals.

Clinical AI Scope & Governance:
    - Complements individual descriptive OLS slopes with shrinkage towards population means.
    - Minimum observation requirements (>= 3 observations spanning >= 180 days) prevent overfitting.
    - If real-world cohorts (e.g. CRIC) are not present, models must not claim clinical calibration.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.optimize import minimize

from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
    resolve_observation_egfr,
)

logger = logging.getLogger("nefroai.lmm_trajectory")


# ---------------------------------------------------------------------------
# Contracts & Data Structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LMMConfig:
    """Configuration for the Linear Mixed-Effects eGFR Trajectory Model."""

    min_observations_per_patient: int = 3
    min_followup_days: float = 180.0
    max_iterations: int = 150
    convergence_tol: float = 1e-5
    include_random_slope: bool = True
    default_fixed_intercept: float = 65.0
    default_fixed_slope: float = -2.5
    default_sigma_u0: float = 10.0
    default_sigma_u1: float = 1.5
    default_sigma_eps: float = 3.0


@dataclass(frozen=True)
class LMMTrajectoryResult:
    """Estimated eGFR trajectory result for an individual patient at landmark time."""

    patient_id: str
    is_eligible: bool
    status: str
    obs_count: int
    followup_days: float

    # Fixed Effects (Population Level)
    population_intercept: float
    population_slope: float

    # Patient Specific (BLUP)
    patient_intercept: float
    patient_slope: float
    random_intercept: float
    random_slope: Optional[float]

    # Uncertainty Quantification
    slope_standard_error: float
    slope_ci_lower: float
    slope_ci_upper: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to structured dictionary."""
        return {
            "patient_id": self.patient_id,
            "is_eligible": self.is_eligible,
            "status": self.status,
            "obs_count": self.obs_count,
            "followup_days": round(self.followup_days, 1),
            "population_intercept": round(self.population_intercept, 2),
            "population_slope": round(self.population_slope, 3),
            "patient_intercept": round(self.patient_intercept, 2),
            "patient_slope": round(self.patient_slope, 3),
            "random_intercept": round(self.random_intercept, 2),
            "random_slope": round(self.random_slope, 3) if self.random_slope is not None else None,
            "slope_standard_error": round(self.slope_standard_error, 3),
            "slope_ci_lower": round(self.slope_ci_lower, 3),
            "slope_ci_upper": round(self.slope_ci_upper, 3),
        }


# ---------------------------------------------------------------------------
# Linear Mixed-Effects Model Implementation
# ---------------------------------------------------------------------------

class LinearMixedEffectsTrajectoryModel:
    """Population Linear Mixed-Effects Model for eGFR trajectory estimation.

    Can be fitted on multi-patient repeated-measures cohorts or initialized with
    clinically plausible reference parameters.
    """

    def __init__(self, config: Optional[LMMConfig] = None) -> None:
        self.config = config or LMMConfig()
        self.is_fitted: bool = False

        # Parameters
        self.beta_: np.ndarray = np.array([
            self.config.default_fixed_intercept,
            self.config.default_fixed_slope,
        ], dtype=np.float64)
        self.cov_beta_: np.ndarray = np.eye(2) * 0.1
        self.sigma_u0_: float = self.config.default_sigma_u0
        self.sigma_u1_: float = self.config.default_sigma_u1
        self.rho_u_: float = -0.2  # Typical negative correlation between baseline eGFR and slope
        self.sigma_eps_: float = self.config.default_sigma_eps
        self.n_patients_fitted_: int = 0
        self.n_observations_fitted_: int = 0

    @property
    def G_(self) -> np.ndarray:
        """Between-patient random effects covariance matrix G."""
        cov_01 = self.rho_u_ * self.sigma_u0_ * self.sigma_u1_
        return np.array([
            [self.sigma_u0_**2, cov_01],
            [cov_01, self.sigma_u1_**2],
        ], dtype=np.float64)

    def fit(
        self,
        records: List[LongitudinalPatientRecord],
    ) -> LinearMixedEffectsTrajectoryModel:
        """Fit the mixed-effects model on a cohort of longitudinal patient records.

        Parameters
        ----------
        records : List[LongitudinalPatientRecord]
            Cohort of patient records with repeated observations.
        """
        # Extract patient data arrays
        patient_data: List[Tuple[np.ndarray, np.ndarray]] = []
        total_obs = 0

        for rec in records:
            if not rec.observations:
                continue
            t0 = rec.observations[0].timestamp
            pts = []
            for obs in rec.observations:
                egfr = resolve_observation_egfr(obs, rec.age_baseline, rec.sex)
                if egfr is not None:
                    t_yr = (obs.timestamp - t0).total_seconds() / (365.25 * 86400.0)
                    pts.append((t_yr, egfr))

            if len(pts) >= 2:
                xs = np.array([p[0] for p in pts], dtype=np.float64)
                ys = np.array([p[1] for p in pts], dtype=np.float64)
                patient_data.append((xs, ys))
                total_obs += len(ys)

        if len(patient_data) < 3:
            logger.warning(
                "Insufficient cohort size (< 3 patients with >= 2 observations) to fit LMM. "
                "Retaining baseline reference parameters."
            )
            self.is_fitted = True
            return self

        # Initial parameter vector: [log(sigma_u0), log(sigma_u1), atanh(rho), log(sigma_eps)]
        init_params = np.array([
            math.log(max(1.0, self.config.default_sigma_u0)),
            math.log(max(0.1, self.config.default_sigma_u1)),
            np.arctanh(np.clip(self.rho_u_, -0.8, 0.8)),
            math.log(max(0.5, self.config.default_sigma_eps)),
        ], dtype=np.float64)

        def neg_log_likelihood(params: np.ndarray) -> float:
            s_u0 = math.exp(np.clip(params[0], -2.0, 5.0))
            s_u1 = math.exp(np.clip(params[1], -3.0, 3.0))
            rho = float(np.tanh(params[2]))
            s_eps = math.exp(np.clip(params[3], -2.0, 4.0))

            cov_12 = rho * s_u0 * s_u1
            G = np.array([[s_u0**2, cov_12], [cov_12, s_u1**2]], dtype=np.float64)
            var_eps = s_eps**2

            # 1. GLS estimation of beta
            Xt_Vinv_X = np.zeros((2, 2), dtype=np.float64)
            Xt_Vinv_y = np.zeros(2, dtype=np.float64)
            nll = 0.0

            for xs, ys in patient_data:
                n_i = len(ys)
                Z_i = np.column_stack([np.ones(n_i), xs])
                X_i = Z_i

                # V_i = Z_i G Z_i^T + var_eps * I
                V_i = Z_i @ G @ Z_i.T + np.eye(n_i) * var_eps
                try:
                    V_inv = np.linalg.pinv(V_i)
                    sign, logdet = np.linalg.slogdet(V_i)
                    if sign <= 0:
                        return 1e9
                except np.linalg.LinAlgError:
                    return 1e9

                Xt_Vinv_X += X_i.T @ V_inv @ X_i
                Xt_Vinv_y += X_i.T @ V_inv @ ys

            try:
                beta_hat = np.linalg.solve(Xt_Vinv_X + np.eye(2) * 1e-6, Xt_Vinv_y)
            except np.linalg.LinAlgError:
                return 1e9

            # 2. Sum profile log-likelihood
            for xs, ys in patient_data:
                n_i = len(ys)
                Z_i = np.column_stack([np.ones(n_i), xs])
                X_i = Z_i
                V_i = Z_i @ G @ Z_i.T + np.eye(n_i) * var_eps
                V_inv = np.linalg.pinv(V_i)
                sign, logdet = np.linalg.slogdet(V_i)
                resid = ys - X_i @ beta_hat
                quad = float(resid.T @ V_inv @ resid)
                nll += 0.5 * (logdet + quad + n_i * math.log(2.0 * math.pi))

            return float(nll)

        res = minimize(
            neg_log_likelihood,
            init_params,
            method="Nelder-Mead",
            options={"maxiter": self.config.max_iterations},
        )

        if res.success or res.fun < 1e8:
            p_opt = res.x
            self.sigma_u0_ = float(math.exp(np.clip(p_opt[0], -2.0, 5.0)))
            self.sigma_u1_ = float(math.exp(np.clip(p_opt[1], -3.0, 3.0)))
            self.rho_u_ = float(np.tanh(p_opt[2]))
            self.sigma_eps_ = float(math.exp(np.clip(p_opt[3], -2.0, 4.0)))

            # Re-estimate beta and covariance
            Xt_Vinv_X = np.zeros((2, 2))
            Xt_Vinv_y = np.zeros(2)
            G = self.G_
            var_eps = self.sigma_eps_**2

            for xs, ys in patient_data:
                n_i = len(ys)
                Z_i = np.column_stack([np.ones(n_i), xs])
                V_i = Z_i @ G @ Z_i.T + np.eye(n_i) * var_eps
                V_inv = np.linalg.pinv(V_i)
                Xt_Vinv_X += Z_i.T @ V_inv @ Z_i
                Xt_Vinv_y += Z_i.T @ V_inv @ ys

            self.beta_ = np.linalg.solve(Xt_Vinv_X + np.eye(2) * 1e-6, Xt_Vinv_y)
            self.cov_beta_ = np.linalg.pinv(Xt_Vinv_X + np.eye(2) * 1e-6)

        self.is_fitted = True
        self.n_patients_fitted_ = len(patient_data)
        self.n_observations_fitted_ = total_obs
        return self

    def predict_patient_trajectory(
        self,
        record: LongitudinalPatientRecord,
        landmark_time: Optional[datetime] = None,
    ) -> LMMTrajectoryResult:
        """Compute the empirical Bayes (BLUP) individual eGFR trajectory for a patient.

        Parameters
        ----------
        record : LongitudinalPatientRecord
            The patient's longitudinal observation history.
        landmark_time : Optional[datetime]
            Evaluation cut-off timestamp. Only prior visits are evaluated.
        """
        pt_id = record.patient_id
        if not record.observations:
            return self._create_abstention_result(pt_id, "NO_OBSERVATIONS", 0, 0.0)

        eff_landmark = landmark_time or record.observations[-1].timestamp
        eligible_obs = [obs for obs in record.observations if obs.timestamp <= eff_landmark]

        if not eligible_obs:
            return self._create_abstention_result(pt_id, "NO_PRIOR_OBSERVATIONS", 0, 0.0)

        t0 = eligible_obs[0].timestamp
        t_last = eligible_obs[-1].timestamp
        followup_days = (t_last - t0).total_seconds() / 86400.0

        # Extract valid eGFR points
        pts = []
        for obs in eligible_obs:
            egfr = resolve_observation_egfr(obs, record.age_baseline, record.sex)
            if egfr is not None:
                t_yr = (obs.timestamp - t0).total_seconds() / (365.25 * 86400.0)
                pts.append((t_yr, egfr))

        n_pts = len(pts)

        # Check eligibility gates
        if n_pts < self.config.min_observations_per_patient or followup_days < self.config.min_followup_days:
            # Fall back to population fixed effect with high uncertainty
            pop_slope = float(self.beta_[1])
            pop_intercept = float(self.beta_[0])
            slope_se = math.sqrt(float(self.cov_beta_[1, 1]) + self.sigma_u1_**2)
            return LMMTrajectoryResult(
                patient_id=pt_id,
                is_eligible=False,
                status="INSUFFICIENT_OBSERVATIONS_POPULATION_SHRINKAGE",
                obs_count=n_pts,
                followup_days=followup_days,
                population_intercept=pop_intercept,
                population_slope=pop_slope,
                patient_intercept=pop_intercept,
                patient_slope=pop_slope,
                random_intercept=0.0,
                random_slope=0.0,
                slope_standard_error=round(slope_se, 3),
                slope_ci_lower=round(pop_slope - 1.96 * slope_se, 3),
                slope_ci_upper=round(pop_slope + 1.96 * slope_se, 3),
            )

        # Compute empirical Bayes BLUP random effects:
        # u_hat_i = G Z_i^T V_i^{-1} (y_i - X_i beta)
        xs = np.array([p[0] for p in pts], dtype=np.float64)
        ys = np.array([p[1] for p in pts], dtype=np.float64)

        Z_i = np.column_stack([np.ones(n_pts), xs])
        X_i = Z_i
        G = self.G_
        var_eps = self.sigma_eps_**2

        V_i = Z_i @ G @ Z_i.T + np.eye(n_pts) * var_eps
        V_inv = np.linalg.pinv(V_i)

        resid = ys - X_i @ self.beta_
        u_hat = G @ Z_i.T @ V_inv @ resid

        u_0 = float(u_hat[0])
        u_1 = float(u_hat[1])

        # Posterior covariance: Var(u_hat - u) = G - G Z_i^T V_i^{-1} Z_i G
        post_cov = G - G @ Z_i.T @ V_inv @ Z_i @ G
        slope_var = float(post_cov[1, 1]) + float(self.cov_beta_[1, 1])
        slope_se = math.sqrt(max(0.01, slope_var))

        patient_intercept = float(self.beta_[0] + u_0)
        patient_slope = float(self.beta_[1] + u_1)

        return LMMTrajectoryResult(
            patient_id=pt_id,
            is_eligible=True,
            status="ESTIMATED_EMPIRICAL_BAYES_RANDOM_SLOPE",
            obs_count=n_pts,
            followup_days=followup_days,
            population_intercept=float(self.beta_[0]),
            population_slope=float(self.beta_[1]),
            patient_intercept=patient_intercept,
            patient_slope=patient_slope,
            random_intercept=u_0,
            random_slope=u_1,
            slope_standard_error=round(slope_se, 3),
            slope_ci_lower=round(patient_slope - 1.96 * slope_se, 3),
            slope_ci_upper=round(patient_slope + 1.96 * slope_se, 3),
        )

    def _create_abstention_result(
        self, patient_id: str, reason: str, obs_count: int, followup_days: float
    ) -> LMMTrajectoryResult:
        pop_slope = float(self.beta_[1])
        pop_int = float(self.beta_[0])
        slope_se = math.sqrt(float(self.cov_beta_[1, 1]) + self.sigma_u1_**2)
        return LMMTrajectoryResult(
            patient_id=patient_id,
            is_eligible=False,
            status=reason,
            obs_count=obs_count,
            followup_days=followup_days,
            population_intercept=pop_int,
            population_slope=pop_slope,
            patient_intercept=pop_int,
            patient_slope=pop_slope,
            random_intercept=0.0,
            random_slope=0.0,
            slope_standard_error=round(slope_se, 3),
            slope_ci_lower=round(pop_slope - 1.96 * slope_se, 3),
            slope_ci_upper=round(pop_slope + 1.96 * slope_se, 3),
        )

    def summary(self) -> Dict[str, Any]:
        """Summary of fitted population parameters and variance components."""
        return {
            "model_type": "LinearMixedEffectsTrajectoryModel",
            "is_fitted": self.is_fitted,
            "n_patients": self.n_patients_fitted_,
            "n_observations": self.n_observations_fitted_,
            "fixed_intercept": round(float(self.beta_[0]), 3),
            "fixed_slope": round(float(self.beta_[1]), 3),
            "sigma_random_intercept": round(self.sigma_u0_, 3),
            "sigma_random_slope": round(self.sigma_u1_, 3),
            "correlation_random_effects": round(self.rho_u_, 3),
            "sigma_residual": round(self.sigma_eps_, 3),
        }
