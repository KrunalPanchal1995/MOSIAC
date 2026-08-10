import ast
import sys
import numpy as np
import pandas as pd
import os
import re
import matplotlib.pyplot as plt

# ── mso_io access (Target Workbench, below) ──────────────────────────────
# MUQ-SAC is a standalone pipeline with its own sys.path conventions (its
# siblings are imported by bare name, e.g. `import Uncertainty`), not part
# of the rmip/mso_io package tree. Append (never insert at 0 -- this repo's
# convention, see feedback_env_isolation) src/ so `mso_io.target_add_io`
# resolves without disturbing MUQ-SAC's own bare-name imports.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.normpath(os.path.join(_this_dir, ".."))
if _src_dir not in sys.path:
    sys.path.append(_src_dir)
try:
    from mso_io.target_add_io import preview_targets as _preview_targets
    _HAS_MSO_IO = True
except ImportError:
    _HAS_MSO_IO = False


class TPhiPlotter:
    """3D plotting utilities for T–P–phi space."""
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def plot_t_p_phi(self, color: str = "dilution", save_path: str = None, show: bool = False) -> None:
        """
        Plot a 3D scatter of (T, P, phi) colored by a chosen column.

        Parameters
        ----------
        color:
            Column name used for coloring (default: 'dilution').
        save_path:
            If provided, saves the figure to this path.
        show:
            If True, calls plt.show().
        """
        d = self.df.dropna(subset=["Temperature_K", "Pressure_Pa", "Phi"])
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        sc = ax.scatter(d["Temperature_K"], d["Pressure_Pa"], d["Phi"], c=d[color] if color in d else None)
        ax.set_xlabel("Temperature [K]")
        ax.set_ylabel("Pressure [Pa]")
        ax.set_zlabel("Phi [-]")
        if color in d:
            fig.colorbar(sc, ax=ax, label=color)
        ax.set_title("T–P–phi space")
        if save_path:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)


class ArrheniusPlotter(object):
	def __init__(self,unsrt_object,reaction):
		self.unsrt_data = unsrt_object
		self.rxn = reaction
		self.M = 3.0/np.log(10.0)
	
	def getNominalParams(self):
		Nom = self.unsrt_data[self.rxn].nominal
		return Nom
	
	def getCholeskyCovariance(self):
		return self.unsrt_data[self.rxn].cov
	
	def getZetaMax(self):
		return self.unsrt_data[self.rxn].zeta.x

	def getTemperatures(self):
		return self.unsrt_data[self.rxn].temperatures
	
	def getTheta(self):
		T = self.getTemperatures()
		Theta = np.array([T/T,np.log(T),-1/T])
		return Theta																						
	
	def getUncertFunc(self):
		L = self.getCholeskyCovariance()
		Theta =   self.getTheta()
		func = [self.M*np.linalg.norm(np.dot(L.T,i)) for i in Theta.T]
		return np.asarray(func)
	
	def getZetaUnsrtFunc(self):
		L = self.getCholeskyCovariance()
		Theta =   self.getTheta()
		z = self.getZetaMax()
		func = [(i.T.dot(L.dot(z))) for i in Theta.T]
		return np.asarray(func)
	
	def getPerturbed_A_curve(self):
		L = self.getCholeskyCovariance()
		Theta =   self.getTheta()
		z = np.array([1,0,0])
		zeta = self.getZetaMax()
		func = [(i.T.dot(z*(L.dot(zeta)))) for i in Theta.T]
		return np.asarray(func)
	
	def getPerturbed_n_curve(self):
		L = self.getCholeskyCovariance()
		Theta =   self.getTheta()
		zeta = self.getZetaMax()
		z = np.array([0,100,0])
		func = [(i.T.dot(z*(L.dot(zeta)))) for i in Theta.T]
		return np.asarray(func)
	
	def getPerturbed_Ea_curve(self):
		nom = self.getNominalParams()
		L = self.getCholeskyCovariance()
		Theta =   self.getTheta()
		z = np.array([0,0,200])
		zeta = self.getZetaMax()
		func = [(i.T.dot(z*(L.dot(zeta)))) for i in Theta.T]
		#raise AssertionError("Perturbing Ea")
		return np.asarray(func)
	
	def getNominalCurve(self):
		P = self.getNominalParams()
		Theta =   self.getTheta()
		func =  [(i.T.dot(P)) for i in Theta.T]
		return np.asarray(func)
	
	def plot_uncertainty_limits(self,location="Plots"):
		self.UQ_plot_loc = location
		os.makedirs(location,exist_ok = True)
		fig = plt.figure()
		T = self.getTemperatures()
		Kappa_o = self.getNominalCurve()
		Kappa_max = self.getZetaUnsrtFunc()
		UQ_limit = self.getUncertFunc()
		plt.plot(1/T,Kappa_o,"b-",label="Nominal Curve")
		plt.plot(1/T,Kappa_o + Kappa_max,"r-",label=r"Arrhenius Curve (f($\zeta$))")
		plt.plot(1/T,Kappa_o-Kappa_max,"r-")
		plt.plot(1/T,Kappa_o+UQ_limit,"k--",label=r"Uncertainty Limits")
		plt.plot(1/T,Kappa_o-UQ_limit,"k--")
		plt.xlabel("Temperatures (1/K)")
		plt.ylabel(r"Rate Coefficient $(\kappa)$")
		plt.legend()
		plt.savefig(location+f"/{self.rxn}.pdf",bbox_inches="tight")
	
	def plot_perturbed_Arrhenius_parameters(self,location="Plots"):
		self.UQ_plot_loc = location
		os.makedirs(location,exist_ok = True)
		#print(self.rxn)
		fig = plt.figure()
		T = self.getTemperatures()
		Kappa_o = self.getNominalCurve()
		Kappa_max = self.getZetaUnsrtFunc()
		UQ_limit = self.getUncertFunc()
		Z_a = self.getPerturbed_A_curve()
		Z_n = self.getPerturbed_n_curve()
		Z_e = self.getPerturbed_Ea_curve()
		#print(Kappa_o,Z_e)
		plt.plot(1/T,Kappa_o,"b-",label="Nominal Curve")
		plt.plot(1/T,Kappa_o + Kappa_max,"r-",label=r"Arrhenius Curve (f($\zeta$))")
		plt.plot(1/T,Kappa_o-Kappa_max,"r-")
		plt.plot(1/T,Kappa_o+UQ_limit,"k--",label=r"Uncertainty Limits")
		plt.plot(1/T,Kappa_o-UQ_limit,"k--")
		plt.plot(1/T,Kappa_o+Z_a,"b--",label="Perturbing A-factor")
		plt.plot(1/T,Kappa_o+Z_n,"c--",label="Perturbing n parameter")
		plt.plot(1/T,Kappa_o+Z_e,"y--",label="Perturbing Ea")
		plt.xlabel("Temperatures (1/K)")
		plt.ylabel(r"Rate Coefficient $(\kappa)$")
		plt.legend()
		#plt.show()
		plt.savefig(location+f"/{self.rxn}.pdf",bbox_inches="tight")		


class DesignMatrixPlotter(object):
	"""
	Plots class-A Design Matrix (DM) samples for the three Arrhenius parameters
	(A, n, Ea) on a per-reaction basis.

	For each reaction the figure contains:
	  - the nominal log-rate curve  κ₀(T)
	  - the full-3-param UQ bounds  κ₀ ± M·‖L^T·θ(T)‖
	  - class-A DM sample curves (upper and lower) for:
	        • only ln(A) perturbed to 0.1·f_prior(T)   [red]
	        • only n     perturbed to 0.1·f_prior(T)   [green]
	        • only Ea    perturbed to 0.1·f_prior(T)   [magenta]

	Figures are stored at:
	    <location>/<sanitised_rxn_name>/<sanitised_rxn_name>.pdf

	Parameters
	----------
	unsrt_data : dict
	    The unsrt_data object loaded from unsrt.pkl.
	dm_A_path : str
	    Path to DesignMatrix_A.csv  (output of getSA_3P_samples with param_type="A")
	dm_n_path : str
	    Path to DesignMatrix_n.csv  (output of getSA_3P_samples with param_type="n")
	dm_Ea_path : str
	    Path to DesignMatrix_Ea.csv (output of getSA_3P_samples with param_type="Ea")
	T_min, T_max : float
	    Temperature range for the Arrhenius plot (K).
	n_T : int
	    Number of temperature points.

	Usage
	-----
	    import pickle, VisualAid as VA
	    with open('unsrt.pkl', 'rb') as f:
	        unsrt_data = pickle.load(f)
	    plotter = VA.DesignMatrixPlotter(unsrt_data)
	    plotter.plot_dm_samples(location="DM_plots")
	"""

	def __init__(self, unsrt_data,
	             dm_A_path="DesignMatrix_A.csv",
	             dm_n_path="DesignMatrix_n.csv",
	             dm_Ea_path="DesignMatrix_Ea.csv",
	             T_min=900, T_max=1200, n_T=200):
		self.unsrt_data = unsrt_data
		self.rxn_list   = list(unsrt_data.keys())
		self.M          = 3.0 / np.log(10.0)   # same convention as ArrheniusPlotter

		# Temperature grid and log-rate basis vectors Θ(T) = [1, ln T, -1/T]
		self.T     = np.linspace(T_min, T_max, n_T)
		
		self.Theta = np.array([self.T / self.T,   # row 0: ones
		                       np.log(self.T),     # row 1: ln T
		                       -1.0 / self.T])     # row 2: -1/T
		# Theta.T has shape (n_T, 3); Theta.T[i] is the 3-vector at T[i]

		# Load block-diagonal design matrices  shape: (N_rxns, total_params)
		self.dm_A  = self._load_csv(dm_A_path)
		self.dm_n  = self._load_csv(dm_n_path)
		self.dm_Ea = self._load_csv(dm_Ea_path)

		# Print shape diagnostics to catch CSV/unsrt_data mismatches early
		self._validate_dm_shapes()

	# ── private helpers ────────────────────────────────────────────────────

	@staticmethod
	def _load_csv(path):
		"""Read a CSV (tolerates trailing commas) → 2-D numpy float array."""
		rows = []
		with open(path, 'r') as fh:
			for line in fh:
				line = line.strip().rstrip(',')
				if line:
					rows.append([float(v) for v in line.split(',')])
		return np.array(rows)

	def _validate_dm_shapes(self):
		"""
		Print shape diagnostics so any CSV/unsrt_data mismatch is immediately
		visible in the log, and raise early if a DM has zero columns.
		"""
		N = len(self.rxn_list)
		print(f"\n[DesignMatrixPlotter] N_rxns = {N}")
		for tag, dm in [("A", self.dm_A), ("n", self.dm_n), ("Ea", self.dm_Ea)]:
			print(f"  DesignMatrix_{tag}.csv shape : {dm.shape}")
			if dm.ndim != 2 or dm.shape[1] == 0:
				raise ValueError(
					f"DesignMatrix_{tag} loaded with unexpected shape {dm.shape}. "
					"Check that the CSV file exists and is non-empty."
				)
		print()

	def _extract_zr(self, dm, rxn_idx):
		"""
		Extract the scalar ζ_r for reaction rxn_idx from the diagonal
		p_design_matrix (N×N).  The p_design_matrix is diagonal: element
		[i, i] holds the single reduced-space zeta for reaction i.

		Also handles the N×3N full-block layout (legacy / unoverwritten file)
		by returning the entire 3-vector so _delta_curve_partial can use it
		via the reduced-Cholesky path.  In practice sens_3_params always
		overwrites with p_design_matrix so N×N is the normal case.
		"""
		N     = len(self.rxn_list)
		ncols = dm.shape[1]
		if ncols == N:
			# p_design_matrix (N×N diagonal): ζ_r is a scalar at [i, i]
			return np.array([dm[rxn_idx, rxn_idx]])
		elif ncols == N * 3:
			# full block-diagonal (N×3N): full ζ_r of length 3
			start = rxn_idx * 3
			return np.asarray(dm[rxn_idx, start:start + 3], dtype=float)
		else:
			raise ValueError(
				f"Unexpected DM shape {dm.shape} for {N} reactions. "
				f"Expected ({N}, {N}) for p_design_matrix "
				f"or ({N}, {N * 3}) for full design_matrix."
			)

	@staticmethod
	def _sanitize(name):
		"""Replace characters that are illegal in directory / file names."""
		return re.sub(r'[\\/:*?"<>|]', '_', name).replace(' ', '_')

	def _nominal_curve(self, rxn):
		"""κ₀(T) = Θ(T)^T · P₀  (log-space nominal rate)."""
		P0 = np.asarray(self.unsrt_data[rxn].nominal)
		return np.array([self.Theta.T[i].dot(P0) for i in range(len(self.T))])

	def _uq_band(self, rxn):
		"""
		Full-3-param symmetric UQ band: M · ‖L^T · θ(T)‖ at every temperature.
		L = unsrt_data[rxn].cov  (3×3 lower-triangular Cholesky factor of Σ).
		Identical formula to ArrheniusPlotter.getUncertFunc().
		"""
		L = self.unsrt_data[rxn].cov
		return np.array([self.M * np.linalg.norm(L.T.dot(self.Theta.T[i]))
		                 for i in range(len(self.T))])

	def _delta_curve_partial(self, rxn, zr, param_idx):
		"""
		Compute the perturbation δκ(T) for a single-parameter class-A sample.

		Correct math (mirrors _psac_class_A_SA in Uncertainty.py):
		  1. L_r = get_reduced_cholesky([param_idx])[1]
		           — Cholesky of the principal submatrix Σ_r of Σ.
		           For m=1 this is a (1,1) matrix: L_r[0,0] = √Σ[p,p].
		  2. δp_r = L_r @ ζ_r        (shape (m,))
		  3. δp_full = zeros(3);  δp_full[param_idx] = δp_r[0]
		  4. δκ(T) = Θ(T)^T · δp_full   at every temperature.

		This is NOT the same as (L_full @ ζ_full_embedded) because L_r is the
		Cholesky of the marginal variance of that single parameter, whereas
		L_full[param_idx, param_idx] is the diagonal of the full Cholesky —
		the two differ whenever the Arrhenius parameters are correlated.

		Parameters
		----------
		rxn       : str   — reaction key in unsrt_data
		zr        : array — reduced-space ζ_r (length 1 for N×N DM, 3 for N×3N)
		param_idx : int   — 0=ln(A), 1=n, 2=Ea/R
		"""
		_, L_r = self.unsrt_data[rxn].get_reduced_cholesky([param_idx])
		# ζ_r for this parameter is zr[0] (scalar) in the N×N case;
		# use only the component at param_idx for safety in the N×3N case.
		zr_scalar = np.array([float(zr[0]) if len(zr) == 1 else float(zr[param_idx])])
		delta_p_r   = L_r @ zr_scalar          # shape (1,)
		delta_p_full = np.zeros(3)
		delta_p_full[param_idx] = delta_p_r[0]
		return np.array([self.Theta.T[i].dot(delta_p_full) for i in range(len(self.T))])

	# ── public plotting method ─────────────────────────────────────────────

	def plot_dm_samples(self, location="DM_plots"):
		"""
		Generate and save one PDF per reaction to
		    ``<location>/<rxn_name>/<rxn_name>.pdf``

		Parameters
		----------
		location : str
		    Root output directory (created if absent).
		"""
		inv_T = 1.0 / self.T

		for rxn_idx, rxn in enumerate(self.rxn_list):
			safe_name  = self._sanitize(rxn)
			rxn_folder = os.path.join(location, safe_name)
			os.makedirs(rxn_folder, exist_ok=True)

			# ── compute all curves ────────────────────────────────────────
			K0    = self._nominal_curve(rxn)
			uq    = self._uq_band(rxn)

			# Extract scalar ζ_r from each diagonal p_design_matrix and
			# compute δκ(T) via the reduced Cholesky L_r for that parameter.
			zr_A  = self._extract_zr(self.dm_A,  rxn_idx)
			zr_n  = self._extract_zr(self.dm_n,  rxn_idx)
			zr_Ea = self._extract_zr(self.dm_Ea, rxn_idx)

			dK_A  = self._delta_curve_partial(rxn, zr_A,  param_idx=0)
			dK_n  = self._delta_curve_partial(rxn, zr_n,  param_idx=1)
			dK_Ea = self._delta_curve_partial(rxn, zr_Ea, param_idx=2)

			# ── build figure ──────────────────────────────────────────────
			fig, ax = plt.subplots(figsize=(8, 5))

			# Nominal curve
			ax.plot(inv_T, K0,
			        'b-', lw=2.0,
			        label=r'Nominal $\kappa_0(T)$')

			# Full-UQ limits (all 3 correlated Arrhenius params)
			ax.plot(inv_T, K0 + uq,
			        'k--', lw=1.5,
			        label=r'Full UQ limits (3-param Cholesky, $\pm$)')
			ax.plot(inv_T, K0 - uq,
			        'k--', lw=1.5)

			# Class-A sample: only ln(A) perturbed
			ax.plot(inv_T, K0 + dK_A,
			        'r-', lw=1.2,
			        label=r'Class-A: $\delta\!\ln A$ only '
			              r'$(0.1\,f_{\rm prior})$')
			ax.plot(inv_T, K0 - dK_A,
			        'r-', lw=1.2)

			# Class-A sample: only n perturbed
			ax.plot(inv_T, K0 + dK_n,
			        'g-', lw=1.2,
			        label=r'Class-A: $\delta n$ only '
			              r'$(0.1\,f_{\rm prior})$')
			ax.plot(inv_T, K0 - dK_n,
			        'g-', lw=1.2)

			# Class-A sample: only Ea perturbed
			ax.plot(inv_T, K0 + dK_Ea,
			        'm-', lw=1.2,
			        label=r'Class-A: $\delta E_a$ only '
			              r'$(0.1\,f_{\rm prior})$')
			ax.plot(inv_T, K0 - dK_Ea,
			        'm-', lw=1.2)

			ax.set_xlabel(r'$1/T\;\mathrm{(K^{-1})}$', fontsize=12)
			ax.set_ylabel(r'$\ln\kappa$', fontsize=12)
			ax.set_title(rxn, fontsize=11)
			ax.legend(fontsize=8, loc='best')
			fig.tight_layout()

			out_path = os.path.join(rxn_folder, f"{safe_name}.pdf")
			fig.savefig(out_path, bbox_inches='tight')
			plt.close(fig)
			print(f"  [DM Plot] Saved: {out_path}")

		print(f"\nAll DM plots written to '{location}/'")

class PostOptPlotter:
    """
    Per-reaction Arrhenius rate-constant plot showing:
      - Prior nominal curve
      - Prior uncertainty limits (from MUQ-SAC Cholesky factor)
      - Optimised (MAP) rate constant curve
      - Posterior ±n_sigma uncertainty envelope (from MUM-PCE Gauss-Newton Hessian)

    Usage
    -----
    plotter = PostOptPlotter(unsrt_data, rxn_key, zeta_opt_rxn, Sigma_p_rxn)
    plotter.plot(location="Opt/Plots")
    """

    M = 3.0 / np.log(10.0)   # ln → log10 conversion

    def __init__(self, unsrt_data, rxn, zeta_opt, Sigma_p_rxn,
                 n_sigma=1, n_points=120):
        """
        Parameters
        ----------
        unsrt_data  : dict  — the full unsrt_data dict
        rxn         : str   — reaction key
        zeta_opt    : array — full 3-element optimised zeta for this reaction
        Sigma_p_rxn : array — 3×3 (or m×m) posterior covariance block in
                              Arrhenius-param space for this reaction
                              (from build_posterior_covariance rxn_slices)
        n_sigma     : int   — how many σ bands to draw
        n_points    : int   — temperature-grid density
        """
        self.unsrt      = unsrt_data
        self.rxn        = rxn
        self.zeta_opt   = np.asarray(zeta_opt, dtype=float)
        self.Sigma_p    = np.asarray(Sigma_p_rxn, dtype=float)
        self.n_sigma    = n_sigma
        self.n_points   = n_points

        u        = unsrt_data[rxn]
        self.T   = np.linspace(float(u.temperatures[0]),
                               float(u.temperatures[-1]), n_points)
        self.Theta = np.array([np.ones(n_points),
                                np.log(self.T),
                                -1.0 / self.T])          # shape (3, N)
        self.p0  = np.asarray(u.nominal, dtype=float)
        self.L   = np.asarray(u.cholskyDeCorrelateMat, dtype=float)

    # ── Curve helpers ──────────────────────────────────────────────────

    def _nominal_curve(self):
        return self.M * (self.Theta.T @ self.p0)

    def _prior_limits(self):
        """±1σ prior uncertainty band in log10(k)."""
        half_width = np.array([
            self.M * np.linalg.norm(self.L.T @ self.Theta[:, i])
            for i in range(self.n_points)
        ])
        k0 = self._nominal_curve()
        return k0 - half_width, k0 + half_width

    def _optimised_curve(self):
        p_opt = self.p0 + self.L @ self.zeta_opt
        return self.M * (self.Theta.T @ p_opt)

    def _posterior_band(self):
        """Posterior ±n_sigma band in log10(k) via θ^T Σ_p θ."""
        Sp = self.Sigma_p
        # If block is smaller than 3×3 (partial PRS), embed into 3×3
        if Sp.shape[0] < 3:
            u   = self.unsrt[self.rxn]
            sel = np.asarray(u.selection, dtype=int)
            act = [i for i, s in enumerate(sel) if s == 1]
            Sp_full = np.zeros((3, 3), dtype=float)
            for a, gi in enumerate(act):
                for b, gj in enumerate(act):
                    Sp_full[gi, gj] = Sp[a, b]
            Sp = Sp_full

        sigma_k = np.array([
            self.M * float(np.sqrt(max(
                self.Theta[:, i] @ Sp @ self.Theta[:, i], 0.0)))
            for i in range(self.n_points)
        ])
        k_opt = self._optimised_curve()
        return k_opt - self.n_sigma * sigma_k, k_opt + self.n_sigma * sigma_k

    # ── Main plot ──────────────────────────────────────────────────────

    def plot(self, location="Plots", figsize=(5.5, 4.0)):
        """
        Generate and save the optimisation + posterior-covariance plot.

        Saved as:  {location}/{rxn}_posterior.pdf
        """
        os.makedirs(location, exist_ok=True)

        k_nom           = self._nominal_curve()
        k_prior_lo, k_prior_hi = self._prior_limits()
        k_opt           = self._optimised_curve()
        k_post_lo, k_post_hi   = self._posterior_band()

        x = 1e3 / self.T   # 1000/T  (conventional Arrhenius x-axis)

        fig, ax = plt.subplots(figsize=figsize)

        # Prior uncertainty envelope
        ax.fill_between(x, k_prior_lo, k_prior_hi,
                        color="steelblue", alpha=0.15, label="Prior $\\pm1\\sigma$")
        ax.plot(x, k_prior_lo, "b--", lw=0.7)
        ax.plot(x, k_prior_hi, "b--", lw=0.7)

        # Nominal
        ax.plot(x, k_nom,  "b-",  lw=1.4, label="Nominal (prior mean)")

        # Optimised MAP
        ax.plot(x, k_opt,  "r-",  lw=1.8, label="Optimised (MAP)")

        # Posterior uncertainty envelope
        ax.fill_between(x, k_post_lo, k_post_hi,
                        color="tomato", alpha=0.30,
                        label=f"Posterior $\\pm{self.n_sigma}\\sigma$")
        ax.plot(x, k_post_lo, "r--", lw=0.7)
        ax.plot(x, k_post_hi, "r--", lw=0.7)

        ax.set_xlabel(r"$1000\,/\,T$  (K$^{-1}$)", fontsize=10)
        ax.set_ylabel(r"$\log_{10}(k)$", fontsize=10)
        ax.set_title(str(self.rxn), fontsize=9)
        ax.legend(fontsize=7, loc="best")
        ax.grid(True, lw=0.3, alpha=0.5)

        # Second x-axis showing T directly
        ax2 = ax.twiny()
        T_ticks = np.array([700, 1000, 1500, 2000, 2500])
        T_ticks = T_ticks[(T_ticks >= self.T[0]) & (T_ticks <= self.T[-1])]
        ax2.set_xlim(ax.get_xlim())
        ax2.set_xticks(1e3 / T_ticks)
        ax2.set_xticklabels([f"{int(t)} K" for t in T_ticks], fontsize=7)
        ax2.tick_params(axis="x", length=3)

        fig.tight_layout()
        safe_rxn = str(self.rxn).replace("/", "_").replace(" ", "_")
        out_path = os.path.join(location, f"{safe_rxn}_posterior.pdf")
        fig.savefig(out_path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        return out_path


class SampleViolationPlotter:
    """
    Plots REAL design-matrix / ResponseSurface input rows for one reaction
    against its physical uncertainty band, to visualize how far specific
    accepted rows exceed the sampler's own band-validity test
    (Uncertainty._psac_class_A / IdentifiablePRS.violation_ratio) --
    see report_10fold_validation/main.tex, "Diagnosis: worst folds are
    driven by band-invalid rows".

    Unlike ArrheniusPlotter/DesignMatrixPlotter (which draw single-parameter
    class-A sensitivity curves), this plots the FULL multi-parameter
    perturbation of whatever rows are handed in -- typically actual rows
    pulled straight from a case's compressed design matrix
    (DM_FOR_PARTIAL_PRS/<case>/pDesignMatrix.csv, the same array
    ResponseSurface.ResponseSurface is fit/tested on), so what is drawn is
    exactly the PRS's own input, not a synthetic sensitivity sample.

    Uses the SAME geometry as IdentifiablePRS.violation_ratio (reduced
    Cholesky L_r restricted to `indices`, Theta basis [1, ln T, -1/T], no
    log10 rescale) so the plotted +-band and the printed violation ratios
    are numerically identical to the ones the 10-fold CV diagnosis reports
    -- band-crossing on this plot means band-invalid by that same test, not
    an approximation of it.

    Parameters
    ----------
    rxn : str
        Reaction key (must match the folder name under Uncertainty_Matrices/).
    nominal : array (3,)
        [ln(A), n, Ea/R] nominal Arrhenius parameters (Ea/R in Kelvin).
        Build from Uncertainty_Matrices/<rxn>/nominal.csv via
        `SampleViolationPlotter.load_nominal(path)`.
    L_r : array (m, m)
        Reduced Cholesky factor for this reaction's SELECTED parameters
        (IdentifiablePRS.reduced_cholesky(Sigma, indices)[1] / a
        ReactionBlock's .L_r -- must be built with the same `indices`).
    indices : sequence of int
        Which of (0=ln A, 1=n, 2=Ea/R) are selected/identifiable for this
        reaction in this case (a ReactionBlock's .indices).
    T_min, T_max : float
        Temperature window to draw (K). Pass the case's own resampling
        window (e.g. 0.85*T_target to 1.25*T_target) to match the exact
        band the sampler/violation test used.
    """

    def __init__(self, rxn, nominal, L_r, indices, T_min, T_max, n_T=200):
        self.rxn = rxn
        self.P0 = np.asarray(nominal, dtype=float)          # (3,)
        self.L_r = np.asarray(L_r, dtype=float)              # (m, m)
        self.indices = list(indices)
        self.T = np.linspace(T_min, T_max, n_T)
        Theta_full = np.column_stack([np.ones_like(self.T), np.log(self.T), -1.0 / self.T])  # (n_T,3)
        self.Theta_full = Theta_full
        self.Theta_S = Theta_full[:, self.indices]           # (n_T, m)

    @staticmethod
    def load_nominal(path):
        """Parse Uncertainty_Matrices/<rxn>/nominal.csv -> [ln(A), n, Ea/R]."""
        vals = {}
        with open(path) as f:
            next(f)  # header: Parameter,Value
            for line in f:
                line = line.strip()
                if not line:
                    continue
                k, v = line.split(",")
                vals[k.strip()] = float(v)
        return np.array([np.log(vals["A"]), vals["n"], vals["Ea"]])

    def nominal_curve(self):
        """kappa_0(T) = Theta_full(T) . P0, full 3-parameter nominal curve."""
        return self.Theta_full @ self.P0

    def band(self):
        """f_prior(T) = ||Theta_S(T) . L_r||_2 -- identical quantity
        IdentifiablePRS.reaction_W_fprior computes."""
        W = self.Theta_S @ self.L_r          # (n_T, m)
        return np.linalg.norm(W, axis=1)     # (n_T,)

    def sample_curve(self, zeta_r):
        """delta_kappa(T) for one real design-matrix row's zeta_r (m,)."""
        zeta_r = np.asarray(zeta_r, dtype=float)
        return self.Theta_S @ (self.L_r @ zeta_r)   # (n_T,)

    def violation_ratio_curve(self, zeta_r):
        return np.abs(self.sample_curve(zeta_r)) / self.band()

    def plot(self, valid_samples, invalid_samples, location="Plots", case=None,
              n_valid_show=15, figsize=(12.5, 5.5)):
        """
        valid_samples / invalid_samples: list of (zeta_r, row_id, ratio)
        tuples -- ratio is the row's max-over-T violation ratio (whatever
        the caller already computed via IdentifiablePRS.violation_detail),
        row_id is the design-matrix row index for the legend/annotation.

        Two panels: LEFT is the full range (so the invalid sample's actual
        scale is visible -- it can be 10s of nominal-curve-widths away),
        RIGHT is zoomed to the nominal curve + physical band + valid
        samples only (the invalid curve is off-scale here on purpose --
        an inset arrow/label marks which direction it leaves in), so the
        physical band itself, which is invisible at the full-range scale
        once ratio is ~10-30x, remains readable.
        """
        os.makedirs(location, exist_ok=True)
        K0 = self.nominal_curve()
        fp = self.band()
        invT = 1.0 / self.T

        fig, (ax_full, ax_zoom) = plt.subplots(1, 2, figsize=figsize)

        def draw_common(ax, show_legend):
            ax.fill_between(invT, K0 - fp, K0 + fp, color="steelblue", alpha=0.18,
                             label=r"Physical band $\pm f_{\rm prior}(T)$", zorder=1)
            ax.plot(invT, K0, "b-", lw=1.8, label=r"Nominal $\kappa_0(T)$", zorder=2)
            for i, (zeta_r, row_id, ratio) in enumerate(valid_samples[:n_valid_show]):
                dk = self.sample_curve(zeta_r)
                lbl = (f"band-valid samples (n shown={min(n_valid_show, len(valid_samples))})"
                       if (i == 0 and show_legend) else None)
                ax.plot(invT, K0 + dk, color="#888888", lw=0.7, alpha=0.7, zorder=3, label=lbl)
            ax.set_xlabel(r"$1/T\;\mathrm{(K^{-1})}$", fontsize=11)
            ax.set_ylabel(r"$\ln\kappa$ (this reaction's contribution)", fontsize=11)

        draw_common(ax_full, show_legend=True)
        colors = plt.cm.autumn(np.linspace(0, 0.6, max(len(invalid_samples), 1)))
        for i, (zeta_r, row_id, ratio) in enumerate(invalid_samples):
            dk = self.sample_curve(zeta_r)
            ax_full.plot(invT, K0 + dk, color=colors[i], lw=2.2, zorder=4,
                         label=f"row {row_id}: ratio={ratio:.1f}$\\times$ band")
        ax_full.set_title("Full range: nominal, band, and the band-invalid sample", fontsize=10)
        ax_full.legend(fontsize=7.5, loc="best")

        draw_common(ax_zoom, show_legend=False)
        y_zoom_lo = min((K0 - fp).min(), *[
            (K0 + self.sample_curve(z)).min() for z, *_ in valid_samples[:n_valid_show]])
        y_zoom_hi = max((K0 + fp).max(), *[
            (K0 + self.sample_curve(z)).max() for z, *_ in valid_samples[:n_valid_show]])
        pad = 0.1 * (y_zoom_hi - y_zoom_lo)
        ax_zoom.set_ylim(y_zoom_lo - pad, y_zoom_hi + pad)
        for i, (zeta_r, row_id, ratio) in enumerate(invalid_samples):
            dk = self.sample_curve(zeta_r)
            curve = K0 + dk
            direction = "above" if curve.mean() > y_zoom_hi else "below"
            y_edge = y_zoom_hi if direction == "above" else y_zoom_lo
            x_mid = invT[len(invT) // 2]
            ax_zoom.annotate(f"row {row_id} leaves the panel {direction}\n(ratio={ratio:.1f}$\\times$ band)",
                              xy=(x_mid, y_edge), xytext=(x_mid, y_edge - pad * (0.6 if direction == "above" else -0.6)),
                              ha="center", fontsize=7.5, color=colors[i],
                              arrowprops=dict(arrowstyle="->", color=colors[i], lw=1.2))
        ax_zoom.set_title("Zoom: physical band + band-valid samples only", fontsize=10)

        title = self.rxn if case is None else f"Case {case}: {self.rxn}"
        fig.suptitle(title, fontsize=12)
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        safe = str(self.rxn).replace("/", "_").replace(" ", "_")
        tag = f"_case{case}" if case is not None else ""
        out_path = os.path.join(location, f"violation_{safe}{tag}.pdf")
        fig.savefig(out_path, bbox_inches="tight", dpi=150)
        fig.savefig(out_path.replace(".pdf", ".png"), bbox_inches="tight", dpi=150)
        plt.close(fig)
        return out_path


# ═══════════════════════════════════════════════════════════════════════
# Target Workbench (2026-08-04): curate a .target/.add pair before it
# enters the MUQ-SAC pipeline -- plot -> check -> generate/prune -> emit a
# new, versioned .target + .add. Never mutates the source files; writing
# always goes through mso_io.target_add_io.write_curated_set().
# ═══════════════════════════════════════════════════════════════════════

def _parse_composition(text):
    """Parse the .target file's 'x-><id_map> = <frac_map>' (multi-species)
    or 'x-><species> = <frac>' (single-species) composition syntax into a
    plain {species: mole_fraction} dict. Mirrors
    mso_io.target_add_io._fuel_multi_repr/_bath_gas_repr's encoding, in
    reverse. Returns {} for missing/unparseable text rather than raising --
    this is a display/check helper, not the authoritative parser (that's
    combustion_target_class.combustion_target.__init__)."""
    if not text or "x->" not in text or "=" not in text:
        return {}
    body = text.split("x->", 1)[1]
    id_part, _, frac_part = body.partition("=")
    id_part, frac_part = id_part.strip(), frac_part.strip()
    try:
        if id_part.startswith("{"):
            id_map = ast.literal_eval(id_part)
            frac_map = ast.literal_eval(frac_part) if frac_part.startswith("{") else {}
            return {sp: float(frac_map.get(k, 0.0)) for k, sp in id_map.items()}
        else:
            return {id_part: float(frac_part)}
    except (ValueError, SyntaxError, TypeError):
        return {}


class TargetRow:
    """One parsed .target line, extending mso_io.target_add_io.TargetPreview
    (display-only: dataset_id/target_type/T/P/phi/solver/runnable) with the
    composition + observation fields TargetChecker/TargetSetPlotter need.
    Built from a TargetPreview's own `.raw` line text -- never re-reads the
    file, and never the authoritative parser (see combustion_target_class
    for that; TargetChecker.check_parses runs it as the write-time gate)."""

    def __init__(self, preview):
        self.line_no = preview.line_no
        self.raw = preview.raw
        self.dataset_id = preview.dataset_id
        self.target_type = preview.target_type
        self.simulation = preview.simulation
        self.temperature_K = preview.temperature_K
        self.pressure_atm = preview.pressure_atm
        self.phi_raw = preview.phi
        self.solver = preview.solver
        self.runnable = preview.runnable
        self.runnable_reason = preview.runnable_reason

        parts = self.raw.split("|")

        def field(key):
            for p in parts:
                kv = p.split("--", 1)
                if len(kv) == 2 and kv[0].strip() == key:
                    return kv[1].strip()
            return None

        self.fuel = _parse_composition(field("Fuel"))
        self.oxidizer = _parse_composition(field("Oxidizer"))
        self.bath_gas = _parse_composition(field("Bath_gas"))

        def to_float(text):
            try:
                return float(text)
            except (TypeError, ValueError):
                return None

        self.observed = to_float(field("observed"))
        self.deviation = to_float(field("deviation"))
        weight_text = field("data_weight")
        self.data_weight = to_float(weight_text)
        self.obs_unit = field("obs_unit")

        units_text = field("units")
        try:
            self.units = ast.literal_eval(units_text) if units_text else {}
        except (ValueError, SyntaxError):
            self.units = {}

        self.is_dummy = False
        self.dummy_source = ""

    def composition_sum(self):
        """Total mole fraction across fuel + oxidizer + bath gas -- should
        sum to 1.0 for a physically valid mixture."""
        return (sum(self.fuel.values()) + sum(self.oxidizer.values())
                + sum(self.bath_gas.values()))

    def as_dict(self):
        return {
            "line_no": self.line_no, "dataset_id": self.dataset_id,
            "target_type": self.target_type, "simulation": self.simulation,
            "temperature_K": self.temperature_K, "pressure_atm": self.pressure_atm,
            "phi_raw": self.phi_raw, "solver": self.solver, "runnable": self.runnable,
            "observed": self.observed, "deviation": self.deviation,
            "data_weight": self.data_weight, "obs_unit": self.obs_unit,
            "composition_sum": self.composition_sum(),
            "is_dummy": self.is_dummy, "dummy_source": self.dummy_source,
        }


class TargetSet:
    """Load a .target (+ paired .add) file into TargetRow objects. Purely
    read-only -- the source files are never modified; curation output goes
    through write_curated_set() in mso_io.target_add_io, to a new version."""

    def __init__(self, target_path, add_path=None):
        if not _HAS_MSO_IO:
            raise ImportError(
                "mso_io.target_add_io is required for TargetSet -- src/ "
                "was not importable from this interpreter.")
        self.target_path = target_path
        self.add_path = add_path
        self.rows = [TargetRow(p) for p in _preview_targets(target_path, add_path)]

    def to_dataframe(self):
        return pd.DataFrame([r.as_dict() for r in self.rows])

    def by_line(self, line_no):
        for r in self.rows:
            if r.line_no == line_no:
                return r
        raise KeyError(f"no row with line_no={line_no}")

    def dataset_ids(self):
        seen = []
        for r in self.rows:
            if r.dataset_id not in seen:
                seen.append(r.dataset_id)
        return seen

    def rows_for(self, dataset_id):
        return [r for r in self.rows if r.dataset_id == dataset_id]

    def __len__(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)


class TargetSetPlotter:
    """Plots over a TargetSet -- T/P/phi scatter, ln(tau) vs 1000/T per
    dataset (dummy/dropped points visually distinct), observed-vs-deviation,
    per-dataset condition coverage. All methods return the saved path (or
    None if save_path wasn't given) and always plt.close() their figure."""

    def __init__(self, target_set):
        self.ts = target_set

    def plot_t_p_phi(self, save_path=None, show=False):
        df = self.ts.to_dataframe()
        fig = plt.figure(figsize=(7, 6))
        ax = fig.add_subplot(111, projection="3d")
        ids = df["dataset_id"].astype("category")
        sc = ax.scatter(df["temperature_K"], df["pressure_atm"], ids.cat.codes,
                         c=ids.cat.codes, cmap="tab20")
        ax.set_xlabel("Temperature [K]")
        ax.set_ylabel("Pressure [atm]")
        ax.set_zlabel("Dataset")
        ax.set_zticks(range(len(ids.cat.categories)))
        ax.set_zticklabels(ids.cat.categories, fontsize=6)
        ax.set_title("T-P-dataset space")
        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)
        return save_path

    def plot_lntau_vs_invT(self, dataset_id, dummy_line_nos=(), dropped_line_nos=(),
                            save_path=None, show=False):
        rows = [r for r in self.ts.rows_for(dataset_id)
                if r.temperature_K and r.observed]
        if not rows:
            raise ValueError(f"no plottable Tig rows for dataset_id={dataset_id!r}")
        dummy_set = set(dummy_line_nos)
        dropped_set = set(dropped_line_nos)
        fig, ax = plt.subplots(figsize=(7, 5))
        for r in sorted(rows, key=lambda r: r.temperature_K):
            invT = 1000.0 / r.temperature_K
            lntau = np.log(r.observed)
            if r.line_no in dropped_set:
                ax.scatter(invT, lntau, marker="x", color="#999999", s=40, zorder=2)
            elif r.line_no in dummy_set or r.is_dummy:
                ax.scatter(invT, lntau, marker="^", color="#d7301f", s=30, zorder=3)
            else:
                ax.scatter(invT, lntau, marker="o", color="#2c7fb8", s=30, zorder=4)
        ax.set_xlabel("1000/T [1/K]")
        ax.set_ylabel("ln(observed)")
        ax.set_title(f"{dataset_id}: ln(tau) vs 1000/T")
        handles = [
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2c7fb8", label="original", markersize=8),
            plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="#d7301f", label="dummy", markersize=8),
            plt.Line2D([0], [0], marker="x", color="#999999", label="dropped", markersize=8),
        ]
        ax.legend(handles=handles, fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)
        return save_path

    def plot_observed_vs_deviation(self, save_path=None, show=False):
        df = self.ts.to_dataframe().dropna(subset=["observed", "deviation"])
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(df["observed"], df["deviation"], s=20, alpha=0.7)
        ax.set_xlabel("observed")
        ax.set_ylabel("deviation")
        ax.set_title("Observed vs. deviation")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)
        return save_path

    def plot_condition_coverage(self, save_path=None, show=False):
        df = self.ts.to_dataframe()
        fig, ax = plt.subplots(figsize=(8, 5))
        for ds, g in df.groupby("dataset_id"):
            ax.scatter(g["temperature_K"], g["pressure_atm"], label=ds, s=25, alpha=0.75)
        ax.set_xlabel("Temperature [K]")
        ax.set_ylabel("Pressure [atm]")
        ax.set_title("Per-dataset condition coverage")
        ax.legend(fontsize=7, ncol=2)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)
        return save_path


class TargetFinding:
    """One TargetChecker finding. severity is 'error' | 'warning' | 'info'."""

    __slots__ = ("severity", "line_no", "dataset_id", "check", "message", "suggested_fix")

    def __init__(self, severity, line_no, dataset_id, check, message, suggested_fix=None):
        self.severity = severity
        self.line_no = line_no
        self.dataset_id = dataset_id
        self.check = check
        self.message = message
        self.suggested_fix = suggested_fix

    def as_dict(self):
        return {"severity": self.severity, "line_no": self.line_no,
                "dataset_id": self.dataset_id, "check": self.check,
                "message": self.message, "suggested_fix": self.suggested_fix}

    def __repr__(self):
        loc = f"line {self.line_no}" if self.line_no else self.dataset_id
        return f"[{self.severity}] {loc}: {self.message}"


class TargetChecker:
    """Runs a battery of sanity checks over a TargetSet. Nothing here is
    written until every 'error'-severity finding from check_parses (the
    authoritative gate) is resolved -- see write_curated_set's own gate."""

    def __init__(self, target_set, add_data=None):
        self.ts = target_set
        self.add_data = add_data or {}

    def run_all(self, composition_tol=0.02, deviation_ratio_tol=5.0):
        findings = []
        findings += self.check_parses()
        findings += self.check_composition_sums(tol=composition_tol)
        findings += self.check_units()
        findings += self.check_deviation_outliers(ratio_tol=deviation_ratio_tol)
        findings += self.check_duplicate_conditions()
        findings += self.check_ntc_crossing()
        return findings

    def check_parses(self):
        """Authoritative gate: instantiate combustion_target_class on every
        row and surface its exception as an 'error' finding. Also reports,
        as 'info', the phi combustion_target actually COMPUTES from
        composition for any row whose raw Phi field wasn't 'N/A' and
        disagrees with it -- __init__ always overwrites self.phi from
        fuel/oxidizer composition, so the raw text field is cosmetic."""
        import combustion_target_class
        from copy import deepcopy
        findings = []
        for r in self.ts.rows:
            try:
                case = combustion_target_class.combustion_target(
                    r.raw, deepcopy(self.add_data), r.line_no - 1)
            except Exception as exc:
                findings.append(TargetFinding(
                    "error", r.line_no, r.dataset_id, "parses",
                    f"combustion_target failed to parse this row: "
                    f"{type(exc).__name__}: {exc}"))
                continue
            raw_phi = (r.phi_raw or "").strip()
            if raw_phi and raw_phi != "N/A" and case.phi is not None:
                try:
                    if abs(float(raw_phi) - float(case.phi)) > 1e-3:
                        findings.append(TargetFinding(
                            "info", r.line_no, r.dataset_id, "phi_backfill",
                            f"stated Phi={raw_phi} but composition computes "
                            f"phi={case.phi:.4g} (the pipeline always uses "
                            f"the computed value)",
                            suggested_fix=f"Phi -- {case.phi:.6g}"))
                except ValueError:
                    pass
        return findings

    def check_composition_sums(self, tol=0.02):
        findings = []
        for r in self.ts.rows:
            total = r.composition_sum()
            if total <= 0:
                continue  # no composition parsed at all -- check_parses covers it
            if abs(total - 1.0) > tol:
                findings.append(TargetFinding(
                    "warning", r.line_no, r.dataset_id, "composition_sum",
                    f"fuel+oxidizer+bath mole fractions sum to {total:.4f}, "
                    f"not 1.0 (tol={tol})"))
        return findings

    def check_units(self):
        findings = []
        for r in self.ts.rows:
            if r.temperature_K is not None and not (150.0 <= r.temperature_K <= 4000.0):
                findings.append(TargetFinding(
                    "warning", r.line_no, r.dataset_id, "units",
                    f"T={r.temperature_K} K is outside a physically plausible "
                    f"combustion range [150, 4000] K"))
            if r.pressure_atm is not None and not (0.0 < r.pressure_atm <= 1000.0):
                findings.append(TargetFinding(
                    "warning", r.line_no, r.dataset_id, "units",
                    f"P={r.pressure_atm} atm is outside a physically plausible "
                    f"range (0, 1000] atm"))
        return findings

    def check_deviation_outliers(self, ratio_tol=5.0):
        findings = []
        ratios = []
        for r in self.ts.rows:
            if r.deviation == 0:
                findings.append(TargetFinding(
                    "warning", r.line_no, r.dataset_id, "deviation",
                    "deviation is exactly 0 -- this row will dominate "
                    "any weighted-least-squares objective"))
                continue
            if r.deviation is None or r.observed in (None, 0):
                continue
            ratios.append((r, abs(r.deviation / r.observed)))
        if not ratios:
            return findings
        vals = np.array([v for _, v in ratios])
        median = float(np.median(vals))
        if median <= 0:
            return findings
        for r, v in ratios:
            if v > ratio_tol * median:
                findings.append(TargetFinding(
                    "warning", r.line_no, r.dataset_id, "deviation",
                    f"deviation/observed ratio {v:.3g} is {v / median:.1f}x "
                    f"the dataset's median ratio ({median:.3g})"))
        return findings

    def check_duplicate_conditions(self, t_round=1, p_round=2):
        findings = []
        seen = {}
        for r in self.ts.rows:
            if r.temperature_K is None or r.pressure_atm is None:
                continue
            key = (r.dataset_id, r.target_type,
                   round(r.temperature_K, t_round), round(r.pressure_atm, p_round))
            seen.setdefault(key, []).append(r)
        for key, rows in seen.items():
            if len(rows) > 1:
                line_nos = [r.line_no for r in rows]
                for r in rows:
                    findings.append(TargetFinding(
                        "warning", r.line_no, r.dataset_id, "duplicate_condition",
                        f"{len(rows)} rows share (target_type, T, P)={key[1:]} "
                        f"(lines {line_nos}) -- their data_weight is being "
                        f"counted {len(rows)}x in the objective"))
        return findings

    def check_ntc_crossing(self, min_points=5):
        """NTC-crossing datasets, via the same fuel-agnostic detector
        DummyPointGenerator uses (Dummy_data_generation.detect_ntc_region).
        Informational only -- an NTC crossing is a real physical feature,
        not a defect, but is useful context before generating dummy points
        or pruning (dropping points inside the NTC well can hide it)."""
        import Dummy_data_generation as ddg
        findings = []
        for ds in self.ts.dataset_ids():
            rows = [r for r in self.ts.rows_for(ds)
                    if r.target_type == "Tig" and r.temperature_K and r.observed]
            if len(rows) < min_points:
                continue
            T = np.array([r.temperature_K for r in rows])
            tau = np.array([r.observed for r in rows])
            try:
                info = ddg.detect_ntc_region(T, tau)
            except Exception:
                continue
            findings.append(TargetFinding(
                "info", None, ds, "ntc_crossing",
                f"dataset crosses an NTC region: {info['ntc_start']:.0f}K - "
                f"{info['ntc_end']:.0f}K"))
        return findings


class DummyPointGenerator:
    """NTC-aware dense dummy-point generation for ONE dataset, reusing
    Dummy_data_generation.py's fuel-agnostic curve-fitting primitives
    (fit_smoothed_logtau_spline, detect_ntc_region, build_equal_zone_grid) --
    the same machinery DATASET/METHYL_BUTANOATE_2026/MB_LTC_DUMMY.target was
    built with, generalized to any single dataset instead of that file's
    hardcoded Ethyl/Butanoate pair."""

    def __init__(self, target_set, dataset_id):
        self.ts = target_set
        self.dataset_id = dataset_id
        rows = [r for r in target_set.rows_for(dataset_id)
                if r.target_type == "Tig" and r.temperature_K and r.observed]
        if len(rows) < 4:
            raise ValueError(
                f"dataset_id={dataset_id!r} has {len(rows)} usable Tig rows "
                f"(need >= 4 to fit a spline)")
        self.rows = sorted(rows, key=lambda r: r.temperature_K)
        self.template_row = self.rows[0]

    def generate(self, points_per_zone=15, smoothing_s=0.05,
                 manual_ntc_bounds=None):
        """Returns a DataFrame of new dummy rows (dataset_ID, Temperature_K,
        observed, obs_unit, is_dummy, dummy_source, generated_zone) spanning
        the dataset's own T range in three equal-count zones (before/inside/
        after its NTC region). manual_ntc_bounds, if given, is (start_K,
        end_K) overriding auto-detection (mirrors Dummy_data_generation.py's
        USE_MANUAL_*_NTC_BOUNDS knobs)."""
        import Dummy_data_generation as ddg

        T = np.array([r.temperature_K for r in self.rows], dtype=float)
        tau = np.array([r.observed for r in self.rows], dtype=float)

        auto_info = ddg.detect_ntc_region(T, tau, smoothing_s=smoothing_s)
        if manual_ntc_bounds is not None:
            info = ddg.apply_manual_bounds(
                auto_info, use_manual=True,
                manual_start=manual_ntc_bounds[0], manual_end=manual_ntc_bounds[1],
                label=self.dataset_id)
        else:
            info = ddg.apply_manual_bounds(auto_info, use_manual=False,
                                            manual_start=0, manual_end=0,
                                            label=self.dataset_id)

        T_grid, zone_labels = ddg.build_equal_zone_grid(
            info["t_min"], info["ntc_start"], info["ntc_end"], info["t_max"],
            points_per_zone)
        y_ln = ddg.evaluate_logtau_with_linear_boundary_extrapolation(
            info["spline"], T_grid, T)
        tau_dense = np.exp(y_ln)

        out = pd.DataFrame({
            "dataset_ID": f"dummy_{self.dataset_id}",
            "Temperature_K": T_grid,
            "observed": tau_dense,
            "obs_unit": self.template_row.obs_unit or "us",
            "is_dummy": True,
            "dummy_source": (
                f"DummyPointGenerator: smoothed ln(tau) spline of "
                f"{self.dataset_id}; NTC bounds mode={info['boundary_mode']}"),
            "generated_zone": zone_labels,
        })
        self._ntc_info = info
        return out


class TargetPruner:
    """Which rows can be dropped without losing much: geometric coverage
    (target_sampling.py's farthest-point diversity sampling over T/P/phi --
    no extra data needed) and, optionally, information-content pruning via
    a caller-supplied basis/sensitivity matrix (e.g. an existing
    DesignMatrix.csv fit for this target set) using the same greedy
    D-optimal det(Gram) scoring AdaptiveResampler.DOptimalResampler uses
    for augmentation, run here in reverse (backward elimination)."""

    def __init__(self, target_set):
        self.ts = target_set

    def coverage_prune(self, n_drop, seed=0):
        """Returns (keep_line_nos, drop_line_nos, coverage_ratio) -- drop
        n_drop rows while maximizing T/P/phi coverage of what remains."""
        import target_sampling as ts_mod
        df = self.ts.to_dataframe()
        df = df.dropna(subset=["temperature_K", "pressure_atm"])
        n = len(df)
        if not (1 <= n_drop < n):
            raise ValueError(f"n_drop must be in [1, {n - 1}], got {n_drop}")
        phi_numeric = pd.to_numeric(df["phi_raw"], errors="coerce").fillna(0.0)
        points = np.column_stack([
            df["temperature_K"].to_numpy(dtype=float),
            df["pressure_atm"].to_numpy(dtype=float),
            phi_numeric.to_numpy(dtype=float),
        ])
        n_keep = n - n_drop
        keep_local = ts_mod.farthest_point_sample(points, n_keep, seed=seed)
        keep_set = set(keep_local)
        line_nos = df["line_no"].tolist()
        keep_line_nos = [line_nos[i] for i in keep_local]
        drop_line_nos = [line_nos[i] for i in range(n) if i not in keep_set]
        coverage = ts_mod.coverage_ratio(points, keep_local)
        return keep_line_nos, drop_line_nos, coverage

    def information_prune(self, basis_matrix, line_numbers, n_drop, ridge_alpha=0.0):
        """Greedy D-optimal backward elimination: repeatedly remove the row
        whose removal shrinks det(Gram) the LEAST, until n_drop rows are
        dropped. basis_matrix rows must align 1:1 with line_numbers (e.g.
        ResponseSurface.build_basis() output from a PRS already fit for
        this target set -- there is no such matrix from the .target file
        alone, since it has no reaction-sensitivity information).

        Returns (keep_line_nos, drop_line_nos, log) where log is a list of
        {line_no, det_ratio} in drop order (det_ratio close to 1.0 means
        that row was nearly redundant; << 1.0 means dropping it cost real
        information)."""
        B = np.asarray(basis_matrix, dtype=float)
        n = B.shape[0]
        if len(line_numbers) != n:
            raise ValueError("basis_matrix rows must align with line_numbers")
        if not (1 <= n_drop < n):
            raise ValueError(f"n_drop must be in [1, {n - 1}], got {n_drop}")

        alive = list(range(n))
        log = []
        for _ in range(n_drop):
            G = B[alive].T @ B[alive]
            if ridge_alpha > 0:
                G = G + ridge_alpha * np.eye(G.shape[0])
            base_det = float(np.linalg.det(G))
            best_i, best_ratio = None, -np.inf
            for j, idx in enumerate(alive):
                trial = [k for k in alive if k != idx]
                Gt = B[trial].T @ B[trial]
                if ridge_alpha > 0:
                    Gt = Gt + ridge_alpha * np.eye(Gt.shape[0])
                det_t = float(np.linalg.det(Gt))
                ratio = det_t / base_det if base_det != 0 else 0.0
                if ratio > best_ratio:
                    best_ratio, best_i = ratio, idx
            alive.remove(best_i)
            log.append({"line_no": line_numbers[best_i], "det_ratio": best_ratio})

        dropped = {e["line_no"] for e in log}
        keep_line_nos = [line_numbers[i] for i in range(n) if line_numbers[i] not in dropped]
        drop_line_nos = [e["line_no"] for e in log]
        return keep_line_nos, drop_line_nos, log


class NominalParityAnalyzer:
    """Model-vs-experiment parity for the nominal (unperturbed) mechanism
    over a target set, plus a per-row leverage score. Deliberately does NOT
    run the nominal simulation itself (that's MUQ-SAC/run_nominal_sim.py's
    job, via nominal_sim_gui.py's subprocess pipeline, per this repo's
    env-isolation convention) -- callers pass in results already produced by
    that pipeline, keyed by line_no."""

    def __init__(self, target_set, nominal_results):
        """nominal_results : dict[int, float] -- line_no -> nominal model
        prediction, in the same units as TargetRow.observed."""
        self.ts = target_set
        self.nominal_results = nominal_results

    def parity_table(self):
        rows = []
        for r in self.ts.rows:
            model = self.nominal_results.get(r.line_no)
            if model is None or r.observed is None:
                continue
            sigma = abs(r.deviation) if r.deviation else None
            leverage = (model - r.observed) / sigma if sigma else None
            rows.append({
                "line_no": r.line_no, "dataset_id": r.dataset_id,
                "observed": r.observed, "model": model,
                "residual": model - r.observed, "leverage_sigma": leverage,
            })
        return pd.DataFrame(rows)

    def flag_leverage(self, n_sigma=3.0):
        """Rows the nominal mechanism already misses by more than n_sigma
        deviations -- these dominate the MSO objective before any
        optimization pass even starts."""
        df = self.parity_table().dropna(subset=["leverage_sigma"])
        return df[df["leverage_sigma"].abs() > n_sigma]

    def plot_parity(self, save_path=None, show=False):
        df = self.parity_table().dropna(subset=["model", "observed"])
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.scatter(df["observed"], df["model"], s=25, alpha=0.7)
        lo = min(df["observed"].min(), df["model"].min())
        hi = max(df["observed"].max(), df["model"].max())
        ax.plot([lo, hi], [lo, hi], "k--", lw=1, label="1:1")
        ax.set_xlabel("Observed")
        ax.set_ylabel("Nominal model")
        ax.set_title("Nominal-model parity")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)
        return save_path


# =============================================================================
# postprocess() -- "process the results" flag entry point
# =============================================================================
# Everything above this line is the existing plotter/analysis class library
# (untouched -- run_script.py imports TPhiPlotter/ArrheniusPlotter at import
# time and PostOptPlotter mid-run; neither import path changes). What follows
# is new: a standalone way to point this file at an existing (or
# still-running) src/MUQ-SAC/run_script.py run directory and regenerate its
# plots + tables without re-running the optimization, via
# ``mso_io.postprocess_base``'s shared CLI contract (also used by
# Sensitivity_Analysis/VisualAid.py, forward_uq/uq_plots.py, graph_sa/plots.py,
# mso_compare/run_plots.py, automation/prs_report.py, rmip/postprocess.py).
#
# Reconstructs exactly what run_script.py itself already computes right
# before it calls PostOptPlotter (see the "Per-reaction optimisation +
# posterior plots" block, immediately after the ``solution_zeta.save`` /
# ``posterior_cov.pkl`` load) -- from the same three files that block reads,
# so a postprocess() run and the in-line run_script.py plot are the same
# curves. Deliberately does NOT modify PostOptPlotter (or any other class
# above) to do this -- it calls the curve-building methods PostOptPlotter
# already has, the same way any external caller would.

import pickle  # noqa: E402  (kept with the rest of the file's flat imports)

_this_dir_pp = os.path.dirname(os.path.abspath(__file__))
_src_dir_pp = os.path.normpath(os.path.join(_this_dir_pp, ".."))
if _src_dir_pp not in sys.path:
    sys.path.append(_src_dir_pp)
try:
    from mso_io.postprocess_base import (  # noqa: E402
        PostProcessResult, add_postprocess_args, default_out_dir, discover,
        formats_from_args, write_manifest, write_table,
    )
except ImportError:  # pragma: no cover - postprocess_base predates this repo layout
    PostProcessResult = None

#: Ea/R -> Ea conversion factor (kJ/mol), matching this repo's own convention
#: in Input_file_reader.py (``R = 8.314E-03``, Ea in kJ/mol).
_R_KJ = 8.314e-3

_MUQSAC_PATTERNS = {
    "unsrt": "**/unsrt.pkl",
    "solution_zeta": "**/solution_zeta.save",
    "posterior_cov": "**/posterior_cov.pkl",
    "optimized_mech": "**/Optimized_mech.yaml",
    "prediction_errors": "**/Prediction_errors.csv",
    "prediction_errors_detailed": "**/Prediction_errors_detailed.csv",
    "target_files": "**/*.target",
}


def _load_pickle(path):
    with open(path, "rb") as fh:
        return pickle.load(fh)


def _load_solution_zeta(path):
    lines = open(path, "r").readlines()
    return [float(line.split("=")[1].strip()) for line in lines if "=" in line]


def _per_reaction_zeta_and_cov(unsrt_data, opt_zeta, posterior_cov):
    """Same inline reconstruction run_script.py does right before building
    each PostOptPlotter (see VisualAid.py's module docstring above) --
    duplicated here rather than imported since it is a ~10-line loop in
    run_script.py's own module scope, not a function it exposes."""
    opt_zeta_arr = np.asarray(opt_zeta, dtype=float)
    rxn_slices = posterior_cov["rxn_slices"]
    Sigma_p = posterior_cov["Sigma_p"]
    out = {}
    offset = 0
    for rxn in unsrt_data:
        m_j = len(unsrt_data[rxn].activeParameters)
        z_rxn = opt_zeta_arr[offset: offset + m_j]
        offset += m_j

        sl = rxn_slices[rxn]
        Sp_rxn = Sigma_p[sl, sl]

        z_full = np.zeros(3, dtype=float)
        sel = np.asarray(unsrt_data[rxn].selection, dtype=int)
        act = [i for i, s in enumerate(sel) if s == 1]
        for local_i, global_i in enumerate(act):
            if local_i < len(z_rxn):
                z_full[global_i] = z_rxn[local_i]
        out[rxn] = (z_full, Sp_rxn)
    return out


def _arrhenius_table_row(rxn, u, z_full):
    """One row of the --journal Arrhenius parameter table: prior vs.
    optimised A/n/Ea for one reaction, straight from the same p0/L/zeta_opt
    PostOptPlotter's curves are built from."""
    p0 = np.asarray(u.nominal, dtype=float)
    L = np.asarray(u.cholskyDeCorrelateMat, dtype=float)
    p_opt = p0 + L @ z_full
    return {
        "reaction": rxn,
        "prior_lnA": p0[0], "prior_n": p0[1], "prior_Ea_kJ_per_mol": p0[2] * _R_KJ,
        "optimized_lnA": p_opt[0], "optimized_n": p_opt[1],
        "optimized_Ea_kJ_per_mol": p_opt[2] * _R_KJ,
        "delta_lnA": p_opt[0] - p0[0], "delta_n": p_opt[1] - p0[1],
        "delta_Ea_kJ_per_mol": (p_opt[2] - p0[2]) * _R_KJ,
    }


def postprocess(run_dir, out_dir=None, journal=False, csv_only=False,
                 formats=("png",), intermediate=False):
    """Regenerate MUQ-SAC optimisation plots/tables from an existing (or
    still-running, with ``intermediate=True``) ``run_script.py`` run
    directory. Never raises on missing files -- whatever inputs aren't
    present yet (a run still in its PRS-fitting stage, before optimisation
    has produced ``solution_zeta.save``) are recorded in
    ``result.skipped`` rather than failing the whole call, so this is safe
    to call repeatedly against a run directory while it's still going.

    Returns a :class:`mso_io.postprocess_base.PostProcessResult`.
    """
    if PostProcessResult is None:
        raise ImportError("mso_io.postprocess_base not importable -- is src/ on sys.path?")

    run_dir = os.path.abspath(run_dir)
    out_dir = str(default_out_dir(run_dir, out_dir))
    found = discover(run_dir, _MUQSAC_PATTERNS)
    result = PostProcessResult(run_dir=run_dir, out_dir=out_dir, partial=bool(intermediate))

    figures_dir = os.path.join(out_dir, "figures")
    tables_dir = os.path.join(out_dir, "tables")

    # -- Per-reaction posterior plots (unsrt.pkl + solution_zeta.save + posterior_cov.pkl) --
    have_posterior_inputs = (found["unsrt"] and found["solution_zeta"] and found["posterior_cov"])
    if have_posterior_inputs:
        try:
            unsrt_data = _load_pickle(str(found["unsrt"][0]))
            opt_zeta = _load_solution_zeta(str(found["solution_zeta"][0]))
            posterior_cov = _load_pickle(str(found["posterior_cov"][0]))
            per_rxn = _per_reaction_zeta_and_cov(unsrt_data, opt_zeta, posterior_cov)

            arrhenius_rows = []
            for rxn, (z_full, Sp_rxn) in per_rxn.items():
                try:
                    plotter = PostOptPlotter(unsrt_data=unsrt_data, rxn=rxn,
                                              zeta_opt=z_full, Sigma_p_rxn=Sp_rxn, n_sigma=1)
                    if not csv_only:
                        fig_path = plotter.plot(location=figures_dir)
                        result.figures.append(fig_path)

                    # Curve data -> CSV, unconditionally (the class's own
                    # curve-building methods, called as any external caller
                    # of this public-ish API would -- PostOptPlotter itself
                    # is not modified).
                    x = 1e3 / plotter.T
                    k_nom = plotter._nominal_curve()
                    k_prior_lo, k_prior_hi = plotter._prior_limits()
                    k_opt = plotter._optimised_curve()
                    k_post_lo, k_post_hi = plotter._posterior_band()
                    safe_rxn = str(rxn).replace("/", "_").replace(" ", "_")
                    df = pd.DataFrame({
                        "T_K": plotter.T, "inv1000T": x,
                        "log10k_nominal": k_nom,
                        "log10k_prior_lo": k_prior_lo, "log10k_prior_hi": k_prior_hi,
                        "log10k_optimized": k_opt,
                        "log10k_posterior_lo": k_post_lo, "log10k_posterior_hi": k_post_hi,
                    })
                    result.tables.append(write_table(df, f"{safe_rxn}_posterior", tables_dir))

                    if journal:
                        arrhenius_rows.append(_arrhenius_table_row(rxn, unsrt_data[rxn], z_full))
                except Exception as exc:  # a single bad reaction shouldn't abort the run
                    result.skipped.append(f"reaction {rxn}: {type(exc).__name__}: {exc}")

            if journal and arrhenius_rows:
                journal_dir = os.path.join(out_dir, "journal_data")
                result.journal_tables.append(
                    write_table(pd.DataFrame(arrhenius_rows), "arrhenius_parameters", journal_dir))
        except Exception as exc:
            result.skipped.append(f"posterior plots: {type(exc).__name__}: {exc}")
    else:
        missing = [k for k in ("unsrt", "solution_zeta", "posterior_cov") if not found[k]]
        result.skipped.append(
            f"posterior plots: optimisation not yet at that stage (missing {', '.join(missing)})"
            if intermediate else
            f"posterior plots: no {', '.join(missing)} found under {run_dir}")

    # -- Cost / prediction-error CSVs (already CSVs -- just relocate + always tracked) --
    for key, label in (("prediction_errors", "prediction_errors"),
                        ("prediction_errors_detailed", "prediction_errors_detailed")):
        for src_path in found[key]:
            df = pd.read_csv(src_path)
            result.tables.append(write_table(df, label, tables_dir))
            if journal:
                result.journal_tables.append(
                    write_table(df, f"summary_{label}", os.path.join(out_dir, "journal_data")))

    # -- TargetSet plots, if a .target file is discoverable --
    if found["target_files"]:
        try:
            target_path = str(found["target_files"][0])
            add_path = os.path.splitext(target_path)[0] + ".add"
            target_set = TargetSet(target_path, add_path if os.path.exists(add_path) else None)
            tsp = TargetSetPlotter(target_set)
            if not csv_only:
                os.makedirs(figures_dir, exist_ok=True)
                p1 = tsp.plot_condition_coverage(
                    save_path=os.path.join(figures_dir, "condition_coverage.png"))
                p2 = tsp.plot_observed_vs_deviation(
                    save_path=os.path.join(figures_dir, "observed_vs_deviation.png"))
                result.figures.extend([p for p in (p1, p2) if p])
            result.tables.append(write_table(target_set.to_dataframe(), "target_set", tables_dir))
        except Exception as exc:
            result.skipped.append(f"target set plots: {type(exc).__name__}: {exc}")
    else:
        result.skipped.append(
            f"target set plots: no .target file found under {run_dir} "
            "(NominalParityAnalyzer additionally needs nominal_results, which "
            "run_script.py does not persist to disk -- not attempted)")

    write_manifest(result, out_dir)
    return result


def _main():
    import argparse
    parser = argparse.ArgumentParser(
        description="MUQ-SAC VisualAid: standalone plotter class library, "
                     "plus --postprocess to regenerate plots/tables from an "
                     "existing run_script.py run directory.")
    add_postprocess_args(parser)
    args = parser.parse_args()
    if not args.postprocess:
        parser.error("nothing to do -- pass --postprocess RUN_DIR "
                      "(this file is a library when imported; run_script.py "
                      "does that. This CLI is only for post-processing.)")
    result = postprocess(
        args.postprocess, out_dir=args.out, journal=args.journal,
        csv_only=args.csv_only, formats=formats_from_args(args),
        intermediate=args.intermediate,
    )
    print(f"[VisualAid.postprocess] {len(result.figures)} figure(s), "
          f"{len(result.tables)} table(s), {len(result.journal_tables)} journal table(s) "
          f"-> {result.out_dir}")
    for note in result.skipped:
        print(f"  skipped: {note}")


if __name__ == "__main__":
    _main()

