from __future__ import annotations

import argparse
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from common import ProgressPrinter, clamp, read_csv, write_csv

PARAMS = [
    "risk_preference",
    "temporal_discount_rate",
    "effort_price_elasticity",
    "cooperation_propensity",
    "inequity_sensitivity",
    "punishment_propensity",
    "tokenization_capacity",
]


@dataclass
class Posterior:
    mean: float
    var: float


def _bounds(param: str) -> tuple[float, float]:
    if param == "effort_price_elasticity":
        return -3.0, 1.0
    if param in {"risk_preference", "temporal_discount_rate"}:
        return 0.0, 2.0
    return 0.0, 1.0


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _to_latent(param: str, value: float, eps: float = 1e-6) -> float:
    low, high = _bounds(param)
    span = max(high - low, 1e-9)
    unit = clamp((value - low) / span, eps, 1.0 - eps)
    return math.log(unit / (1.0 - unit))


def _from_latent(param: str, value: float) -> float:
    low, high = _bounds(param)
    span = max(high - low, 1e-9)
    return low + span * _sigmoid(value)


def _obs_sd_to_latent(param: str, value: float, obs_sd: float, eps: float = 1e-6) -> float:
    low, high = _bounds(param)
    span = max(high - low, 1e-9)
    unit = clamp((value - low) / span, eps, 1.0 - eps)
    deriv = 1.0 / (span * unit * (1.0 - unit))
    return max(abs(obs_sd) * abs(deriv), 1e-4)


def _diagnostic_fail_reasons(
    diag: dict[str, object],
    max_rhat: float,
    min_ess_bulk: float,
    max_divergences: int,
) -> list[str]:
    reasons: list[str] = []

    try:
        rhat = float(diag.get("rhat_max", ""))
        if not math.isnan(rhat) and rhat > max_rhat:
            reasons.append(f"rhat_max={rhat:.6f}>{max_rhat:.6f}")
    except (TypeError, ValueError):
        pass

    try:
        ess_bulk = float(diag.get("ess_bulk_min", ""))
        if not math.isnan(ess_bulk) and ess_bulk < min_ess_bulk:
            reasons.append(f"ess_bulk_min={ess_bulk:.6f}<{min_ess_bulk:.6f}")
    except (TypeError, ValueError):
        pass

    try:
        divergences = int(diag.get("divergences", "0"))
        if divergences > max_divergences:
            reasons.append(f"divergences={divergences}>{max_divergences}")
    except (TypeError, ValueError):
        pass

    return reasons


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    denom = sum(weights)
    if denom <= 0:
        return sum(values) / max(1, len(values))
    return sum(v * w for v, w in zip(values, weights)) / denom


def _weighted_var(values: list[float], weights: list[float], mean_value: float) -> float:
    denom = sum(weights)
    if denom <= 0:
        return 0.0
    return sum(w * (v - mean_value) * (v - mean_value) for v, w in zip(values, weights)) / denom


def _estimate_hyperpriors(
    items: list[dict[str, object]],
    min_tau_class: float,
    min_tau_family: float,
    min_tau_species: float,
) -> tuple[float, float, float, float]:
    y = [float(it["y"]) for it in items]
    obs = [max(float(it["obs_var"]), 1e-6) for it in items]
    obs_w = [1.0 / v for v in obs]
    global_mean = _weighted_mean(y, obs_w)

    class_items: dict[str, list[dict[str, object]]] = defaultdict(list)
    family_items: dict[str, list[dict[str, object]]] = defaultdict(list)
    for it in items:
        class_items[str(it["class"])].append(it)
        family_items[str(it["family"])].append(it)

    class_means: dict[str, float] = {}
    class_weights: list[float] = []
    class_values: list[float] = []
    for cls, rows in class_items.items():
        vals = [float(r["y"]) for r in rows]
        w = [1.0 / max(float(r["obs_var"]), 1e-6) for r in rows]
        m = _weighted_mean(vals, w)
        class_means[cls] = m
        class_values.append(m)
        class_weights.append(len(rows))

    tau_class2 = max(_weighted_var(class_values, class_weights, global_mean), min_tau_class * min_tau_class)

    family_means: dict[str, float] = {}
    fam_deltas: list[float] = []
    fam_weights: list[float] = []
    for fam, rows in family_items.items():
        vals = [float(r["y"]) for r in rows]
        w = [1.0 / max(float(r["obs_var"]), 1e-6) for r in rows]
        m = _weighted_mean(vals, w)
        family_means[fam] = m
        cls = str(rows[0]["class"])
        fam_deltas.append(m - class_means.get(cls, global_mean))
        fam_weights.append(len(rows))

    tau_family2 = max(_weighted_var(fam_deltas, fam_weights, 0.0), min_tau_family * min_tau_family)

    residuals: list[float] = []
    for it in items:
        fam = str(it["family"])
        residuals.append(float(it["y"]) - family_means.get(fam, global_mean))
    residual_var = _weighted_var(residuals, obs_w, 0.0)
    avg_obs = _weighted_mean(obs, [1.0 for _ in obs])
    tau_species2 = max(residual_var - avg_obs, min_tau_species * min_tau_species)

    return global_mean, tau_class2, tau_family2, tau_species2


def _fit_param_posteriors_empirical_bayes(
    items: list[dict[str, object]],
    min_tau_class: float,
    min_tau_family: float,
    min_tau_species: float,
) -> tuple[dict[str, Posterior], tuple[float, float, float]]:
    global_mean, tau_class2, tau_family2, tau_species2 = _estimate_hyperpriors(
        items,
        min_tau_class=min_tau_class,
        min_tau_family=min_tau_family,
        min_tau_species=min_tau_species,
    )

    by_class: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_family: dict[str, list[dict[str, object]]] = defaultdict(list)
    for it in items:
        by_class[str(it["class"])].append(it)
        by_family[str(it["family"])].append(it)

    class_post: dict[str, Posterior] = {}
    for cls, rows in by_class.items():
        data_var = [max(float(r["obs_var"]) + tau_family2 + tau_species2, 1e-6) for r in rows]
        w = [1.0 / v for v in data_var]
        sum_w = sum(w)
        prec_prior = 1.0 / tau_class2
        var = 1.0 / (prec_prior + sum_w)
        mean = var * (global_mean * prec_prior + sum(float(r["y"]) * wi for r, wi in zip(rows, w)))
        class_post[cls] = Posterior(mean=mean, var=var)

    family_post: dict[str, Posterior] = {}
    for fam, rows in by_family.items():
        cls = str(rows[0]["class"])
        cp = class_post.get(cls, Posterior(mean=global_mean, var=tau_class2))
        prior_var = max(tau_family2 + cp.var, 1e-6)
        data_var = [max(float(r["obs_var"]) + tau_species2, 1e-6) for r in rows]
        w = [1.0 / v for v in data_var]
        sum_w = sum(w)
        prec_prior = 1.0 / prior_var
        var = 1.0 / (prec_prior + sum_w)
        mean = var * (cp.mean * prec_prior + sum(float(r["y"]) * wi for r, wi in zip(rows, w)))
        family_post[fam] = Posterior(mean=mean, var=var)

    species_post: dict[str, Posterior] = {}
    for it in items:
        species = str(it["species"])
        fam = str(it["family"])
        fp = family_post.get(fam, Posterior(mean=global_mean, var=tau_family2))
        prior_var = max(tau_species2 + fp.var, 1e-6)
        obs_var = max(float(it["obs_var"]), 1e-6)

        prec_prior = 1.0 / prior_var
        prec_obs = 1.0 / obs_var
        var = 1.0 / (prec_prior + prec_obs)
        mean = var * (fp.mean * prec_prior + float(it["y"]) * prec_obs)
        species_post[species] = Posterior(mean=mean, var=var)

    return species_post, (tau_class2, tau_family2, tau_species2)


def _fit_param_posteriors_empirical_bayes_with_ppc(
    items: list[dict[str, object]],
    param: str,
    min_tau_class: float,
    min_tau_family: float,
    min_tau_species: float,
    engine_label: str = "empirical_bayes",
) -> tuple[dict[str, Posterior], tuple[float, float, float], dict[str, object], list[dict[str, object]]]:
    post, hypers = _fit_param_posteriors_empirical_bayes(
        items,
        min_tau_class=min_tau_class,
        min_tau_family=min_tau_family,
        min_tau_species=min_tau_species,
    )
    diagnostics = {
        "param": param,
        "engine": engine_label,
        "rhat_max": "",
        "ess_bulk_min": "",
        "ess_tail_min": "",
        "divergences": "",
        "ppc_rmse": "",
        "ppc_coverage_95": "",
    }

    ppc_rows: list[dict[str, object]] = []
    for it in items:
        sp = str(it["species"])
        obs = float(it["y"])
        p = post.get(sp)
        if not p:
            continue
        sd = math.sqrt(max(p.var, 1e-8))
        lo = p.mean - 1.96 * sd
        hi = p.mean + 1.96 * sd
        ppc_rows.append(
            {
                "param": param,
                "species": sp,
                "observed_value": round(obs, 6),
                "posterior_mean": round(p.mean, 6),
                "posterior_lower_95": round(lo, 6),
                "posterior_upper_95": round(hi, 6),
                "ppc_mean": round(p.mean, 6),
                "ppc_sd": round(sd, 6),
                "ppc_lower_95": round(lo, 6),
                "ppc_upper_95": round(hi, 6),
            }
        )

    return post, hypers, diagnostics, ppc_rows


def _fit_param_posteriors_pymc(
    items: list[dict[str, object]],
    param: str,
    draws: int,
    tune: int,
    chains: int,
    target_accept: float,
    max_treedepth: int,
    random_seed: int,
) -> tuple[dict[str, Posterior], tuple[float, float, float], dict[str, object], list[dict[str, object]]]:
    try:
        import arviz as az
        import numpy as np
        import pymc as pm
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyMC dependencies are not installed.") from exc

    species = [str(it["species"]) for it in items]
    classes = [str(it["class"]) for it in items]
    families = [str(it["family"]) for it in items]
    y = np.asarray([float(it["y"]) for it in items], dtype=float)
    obs_sd = np.asarray([math.sqrt(max(float(it["obs_var"]), 1e-8)) for it in items], dtype=float)
    y_latent = np.asarray([_to_latent(param, float(v)) for v in y], dtype=float)
    obs_sd_latent = np.asarray([_obs_sd_to_latent(param, float(v), float(sd)) for v, sd in zip(y, obs_sd)], dtype=float)

    class_labels = sorted(set(classes))
    class_idx_map = {name: i for i, name in enumerate(class_labels)}
    class_idx = np.asarray([class_idx_map[c] for c in classes], dtype=int)

    family_labels = sorted(set(families))
    family_idx_map = {name: i for i, name in enumerate(family_labels)}
    family_idx = np.asarray([family_idx_map[f] for f in families], dtype=int)

    family_to_class: dict[str, str] = {}
    for fam, cls in zip(families, classes):
        family_to_class.setdefault(fam, cls)
    family_class_idx = np.asarray([class_idx_map[family_to_class[fam]] for fam in family_labels], dtype=int)

    with pm.Model() as model:
        mu_global = pm.Normal("mu_global", mu=float(np.mean(y_latent)), sigma=1.5)
        sigma_class = pm.HalfNormal("sigma_class", sigma=0.5)
        sigma_family = pm.HalfNormal("sigma_family", sigma=0.5)
        sigma_species = pm.HalfNormal("sigma_species", sigma=0.5)

        class_offset = pm.Normal("class_offset", mu=0.0, sigma=1.0, shape=len(class_labels))
        class_mean = pm.Deterministic("class_mean", mu_global + class_offset * sigma_class)

        family_offset = pm.Normal("family_offset", mu=0.0, sigma=1.0, shape=len(family_labels))
        family_mean = pm.Deterministic("family_mean", class_mean[family_class_idx] + family_offset * sigma_family)

        species_offset = pm.Normal("species_offset", mu=0.0, sigma=1.0, shape=len(species))
        theta_species = pm.Deterministic(
            "theta_species",
            family_mean[family_idx] + species_offset * sigma_species,
        )
        pm.Normal("y_obs", mu=theta_species, sigma=obs_sd_latent, observed=y_latent)

        idata = pm.sample(
            draws=max(draws, 100),
            tune=max(tune, 100),
            chains=max(chains, 2),
            cores=1,
            target_accept=clamp(target_accept, 0.7, 0.99),
            max_treedepth=max(max_treedepth, 8),
            random_seed=random_seed,
            progressbar=False,
            return_inferencedata=True,
        )
        ppc = pm.sample_posterior_predictive(
            idata,
            var_names=["y_obs"],
            random_seed=random_seed,
            progressbar=False,
            return_inferencedata=False,
        )

    theta_samples_latent = np.asarray(idata.posterior["theta_species"]).reshape(-1, len(species))
    theta_samples = np.asarray([[_from_latent(param, float(v)) for v in row] for row in theta_samples_latent], dtype=float)
    theta_mean = theta_samples.mean(axis=0)
    theta_var = theta_samples.var(axis=0)
    theta_low = np.quantile(theta_samples, 0.025, axis=0)
    theta_high = np.quantile(theta_samples, 0.975, axis=0)

    species_post: dict[str, Posterior] = {}
    for i, sp in enumerate(species):
        species_post[sp] = Posterior(mean=float(theta_mean[i]), var=float(max(theta_var[i], 1e-8)))

    tau_class2 = float(np.square(np.asarray(idata.posterior["sigma_class"]).reshape(-1)).mean())
    tau_family2 = float(np.square(np.asarray(idata.posterior["sigma_family"]).reshape(-1)).mean())
    tau_species2 = float(np.square(np.asarray(idata.posterior["sigma_species"]).reshape(-1)).mean())

    summary = az.summary(
        idata,
        var_names=["mu_global", "sigma_class", "sigma_family", "sigma_species"],
        round_to=6,
    )
    rhat_max = float(summary["r_hat"].max()) if "r_hat" in summary.columns else float("nan")
    ess_bulk_min = float(summary["ess_bulk"].min()) if "ess_bulk" in summary.columns else float("nan")
    ess_tail_min = float(summary["ess_tail"].min()) if "ess_tail" in summary.columns else float("nan")
    divergences = int(np.asarray(idata.sample_stats["diverging"]).sum()) if "diverging" in idata.sample_stats else 0

    y_pp_latent = np.asarray(ppc["y_obs"]).reshape(-1, len(species))
    y_pp = np.asarray([[_from_latent(param, float(v)) for v in row] for row in y_pp_latent], dtype=float)
    pp_mean = y_pp.mean(axis=0)
    pp_sd = y_pp.std(axis=0)
    pp_low = np.quantile(y_pp, 0.025, axis=0)
    pp_high = np.quantile(y_pp, 0.975, axis=0)
    rmse = float(np.sqrt(np.mean((pp_mean - y) ** 2)))
    coverage95 = float(np.mean((y >= pp_low) & (y <= pp_high)))

    diagnostics = {
        "param": param,
        "engine": "pymc",
        "rhat_max": round(rhat_max, 6) if not math.isnan(rhat_max) else "",
        "ess_bulk_min": round(ess_bulk_min, 6) if not math.isnan(ess_bulk_min) else "",
        "ess_tail_min": round(ess_tail_min, 6) if not math.isnan(ess_tail_min) else "",
        "divergences": divergences,
        "ppc_rmse": round(rmse, 6),
        "ppc_coverage_95": round(coverage95, 6),
    }

    ppc_rows: list[dict[str, object]] = []
    for i, sp in enumerate(species):
        ppc_rows.append(
            {
                "param": param,
                "species": sp,
                "observed_value": round(float(y[i]), 6),
                "posterior_mean": round(float(theta_mean[i]), 6),
                "posterior_lower_95": round(float(theta_low[i]), 6),
                "posterior_upper_95": round(float(theta_high[i]), 6),
                "ppc_mean": round(float(pp_mean[i]), 6),
                "ppc_sd": round(float(max(pp_sd[i], 1e-8)), 6),
                "ppc_lower_95": round(float(pp_low[i]), 6),
                "ppc_upper_95": round(float(pp_high[i]), 6),
            }
        )

    return species_post, (tau_class2, tau_family2, tau_species2), diagnostics, ppc_rows


def _default_artifact_path(out_path: str, suffix: str) -> str:
    p = Path(out_path)
    return str(p.with_name(f"{p.stem}_{suffix}.csv"))


def _format_hyper_summary(hyper_by_param: dict[str, tuple[float, float, float]]) -> str:
    tau_parts: list[str] = []
    for p in PARAMS:
        tau_class2, tau_family2, tau_species2 = hyper_by_param[p]
        tau_parts.append(f"{p}:{math.sqrt(tau_class2):.3f}/{math.sqrt(tau_family2):.3f}/{math.sqrt(tau_species2):.3f}")
    return ";".join(tau_parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit taxonomy hierarchical model for species priors.")
    parser.add_argument("--species", required=True, help="Species CSV with taxonomy columns.")
    parser.add_argument("--priors", required=True, help="Estimated priors CSV.")
    parser.add_argument("--out", required=True, help="Posterior output CSV.")
    parser.add_argument(
        "--engine",
        choices=["auto", "pymc", "empirical_bayes"],
        default="auto",
        help="Model engine: `pymc` full Bayesian, `empirical_bayes` fallback, `auto` tries pymc then falls back on failure/poor diagnostics.",
    )
    parser.add_argument("--draws", type=int, default=400, help="PyMC posterior draws per chain.")
    parser.add_argument("--tune", type=int, default=400, help="PyMC tuning steps per chain.")
    parser.add_argument("--chains", type=int, default=2, help="PyMC chains.")
    parser.add_argument("--target-accept", type=float, default=0.9, help="PyMC NUTS target_accept.")
    parser.add_argument("--max-treedepth", type=int, default=12, help="PyMC NUTS max tree depth.")
    parser.add_argument("--seed", type=int, default=17, help="Random seed for Bayesian sampling.")
    parser.add_argument("--diagnostics-out", default="", help="Diagnostics CSV output path.")
    parser.add_argument("--ppc-out", default="", help="Posterior predictive check CSV output path.")
    parser.add_argument("--diag-max-rhat", type=float, default=1.01, help="Auto-mode fallback threshold for max R-hat.")
    parser.add_argument(
        "--diag-min-ess-bulk",
        type=float,
        default=100.0,
        help="Auto-mode fallback threshold for min bulk ESS.",
    )
    parser.add_argument(
        "--diag-max-divergences",
        type=int,
        default=0,
        help="Auto-mode fallback threshold for divergences.",
    )
    parser.add_argument("--min-tau-class", type=float, default=0.05, help="Lower bound for class-level prior SD.")
    parser.add_argument("--min-tau-family", type=float, default=0.04, help="Lower bound for family-level prior SD.")
    parser.add_argument("--min-tau-species", type=float, default=0.03, help="Lower bound for species-level prior SD.")
    args = parser.parse_args()

    diagnostics_out = args.diagnostics_out or _default_artifact_path(args.out, "model_diagnostics")
    ppc_out = args.ppc_out or _default_artifact_path(args.out, "posterior_predictive_checks")

    species_rows = read_csv(args.species)
    prior_rows = {r["species"]: r for r in read_csv(args.priors)}

    by_param: dict[str, dict[str, Posterior]] = {}
    hyper_by_param: dict[str, tuple[float, float, float]] = {}
    param_engine_used: dict[str, str] = {}
    diagnostics_rows: list[dict[str, object]] = []
    ppc_rows: list[dict[str, object]] = []

    fallback_count = 0
    pymc_count = 0

    param_progress = ProgressPrinter(total=len(PARAMS), label="fit_hierarchical:params")
    for param in PARAMS:
        items: list[dict[str, object]] = []
        for s in species_rows:
            sp = s["species"]
            pr = prior_rows.get(sp)
            if not pr:
                continue
            items.append(
                {
                    "species": sp,
                    "class": s.get("class", ""),
                    "family": s.get("family", ""),
                    "y": float(pr[param]),
                    "obs_var": max(float(pr["uncertainty_sd"]), 0.01) ** 2,
                }
            )

        use_pymc = args.engine in {"auto", "pymc"}
        used_empirical = False
        if use_pymc:
            try:
                post, hypers, diag, param_ppc = _fit_param_posteriors_pymc(
                    items=items,
                    param=param,
                    draws=args.draws,
                    tune=args.tune,
                    chains=args.chains,
                    target_accept=args.target_accept,
                    max_treedepth=args.max_treedepth,
                    random_seed=args.seed,
                )
                fail_reasons = _diagnostic_fail_reasons(
                    diag,
                    max_rhat=max(args.diag_max_rhat, 1.0),
                    min_ess_bulk=max(args.diag_min_ess_bulk, 1.0),
                    max_divergences=max(args.diag_max_divergences, 0),
                )
                if args.engine == "auto" and fail_reasons:
                    fallback_count += 1
                    used_empirical = True
                    print(
                        "[fit_hierarchical] Auto fallback to empirical_bayes "
                        f"for {param}: {', '.join(fail_reasons)}"
                    )
                else:
                    by_param[param] = post
                    hyper_by_param[param] = hypers
                    param_engine_used[param] = "pymc"
                    diagnostics_rows.append(diag)
                    ppc_rows.extend(param_ppc)
                    pymc_count += 1
                    if args.engine == "pymc" and fail_reasons:
                        print(
                            "[fit_hierarchical] Warning: diagnostics threshold miss "
                            f"for {param}: {', '.join(fail_reasons)}"
                        )
                    param_progress.tick()
                    continue
            except Exception as exc:
                if args.engine == "pymc":
                    raise SystemExit(
                        "PyMC engine failed. Install PyMC/ArviZ and retry. "
                        f"Original error: {type(exc).__name__}: {exc}"
                    )
                fallback_count += 1
                used_empirical = True
                print(
                    "[fit_hierarchical] Auto fallback to empirical_bayes "
                    f"for {param} due to PyMC failure: {type(exc).__name__}: {exc}"
                )

        eb_engine_label = "empirical_bayes_fallback" if used_empirical else "empirical_bayes"
        post, hypers, diag, param_ppc = _fit_param_posteriors_empirical_bayes_with_ppc(
            items,
            param=param,
            min_tau_class=max(args.min_tau_class, 0.005),
            min_tau_family=max(args.min_tau_family, 0.005),
            min_tau_species=max(args.min_tau_species, 0.005),
            engine_label=eb_engine_label,
        )
        by_param[param] = post
        hyper_by_param[param] = hypers
        param_engine_used[param] = eb_engine_label
        diagnostics_rows.append(diag)
        ppc_rows.extend(param_ppc)
        param_progress.tick()
    param_progress.finish()

    if all(param_engine_used.get(p) == "pymc" for p in PARAMS):
        row_method = "pymc_hierarchical_reparam_nuts_v2"
        row_engine = "pymc"
    elif all(param_engine_used.get(p, "").startswith("empirical_bayes") for p in PARAMS):
        row_method = "empirical_bayes_nested_normal_v1"
        row_engine = "empirical_bayes"
    else:
        row_method = "hybrid_pymc_empirical_v1"
        row_engine = "hybrid"

    out_rows: list[dict[str, object]] = []
    row_progress = ProgressPrinter(total=len(species_rows), label="fit_hierarchical:rows")
    for s in species_rows:
        sp = s["species"]
        pr = prior_rows.get(sp)
        if not pr:
            row_progress.tick()
            continue

        row: dict[str, object] = {
            "species": sp,
            "class": s.get("class", ""),
            "family": s.get("family", ""),
            "row_confidence_score": pr.get("row_confidence_score", ""),
            "provenance_type": pr.get("provenance_type", "imputed_trait"),
            "source_model": "hierarchical_bayes_taxonomy_v2",
            "bayes_method": row_method,
            "bayes_engine": row_engine,
        }

        param_sds: list[float] = []
        for param in PARAMS:
            low, high = _bounds(param)
            post = by_param.get(param, {}).get(sp)
            if not post:
                mean = clamp(float(pr[param]), low, high)
                sd = max(float(pr["uncertainty_sd"]), 0.01)
            else:
                mean = clamp(post.mean, low, high)
                sd = math.sqrt(max(post.var, 1e-8))

            lower = clamp(mean - 1.96 * sd, low, high)
            upper = clamp(mean + 1.96 * sd, low, high)

            row[param] = round(mean, 6)
            row[f"{param}_lower"] = round(lower, 6)
            row[f"{param}_upper"] = round(upper, 6)
            param_sds.append(sd)

        uncertainty = math.sqrt(sum(sd * sd for sd in param_sds) / max(1, len(param_sds)))
        row["uncertainty_sd"] = round(clamp(uncertainty, 0.01, 1.0), 6)
        row["bayes_hyper_sds"] = _format_hyper_summary(hyper_by_param)
        out_rows.append(row)
        row_progress.tick()
    row_progress.finish()

    fields = [
        "species",
        "class",
        "family",
        *PARAMS,
        *[f"{p}_lower" for p in PARAMS],
        *[f"{p}_upper" for p in PARAMS],
        "uncertainty_sd",
        "row_confidence_score",
        "provenance_type",
        "source_model",
        "bayes_method",
        "bayes_engine",
        "bayes_hyper_sds",
    ]
    write_csv(args.out, out_rows, fields)

    write_csv(
        diagnostics_out,
        diagnostics_rows,
        ["param", "engine", "rhat_max", "ess_bulk_min", "ess_tail_min", "divergences", "ppc_rmse", "ppc_coverage_95"],
    )
    write_csv(
        ppc_out,
        ppc_rows,
        [
            "param",
            "species",
            "observed_value",
            "posterior_mean",
            "posterior_lower_95",
            "posterior_upper_95",
            "ppc_mean",
            "ppc_sd",
            "ppc_lower_95",
            "ppc_upper_95",
        ],
    )

    print(f"Wrote posterior priors: {len(out_rows)} -> {args.out}")
    print(f"Wrote model diagnostics: {len(diagnostics_rows)} -> {diagnostics_out}")
    print(f"Wrote posterior predictive checks: {len(ppc_rows)} -> {ppc_out}")
    if fallback_count > 0:
        print(f"Engine fallback: used empirical_bayes for {fallback_count}/{len(PARAMS)} parameters.")


if __name__ == "__main__":
    main()
