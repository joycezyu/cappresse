from __future__ import print_function
from pyomo.environ import *
from pyomo.core.base import Constraint, Objective, Suffix, minimize
from pyomo.opt import ProblemFormat, SolverFactory
from nmpc_mhe.dync.MHEGenv2 import MheGen
from nmpc_mhe.mods.bfb.nob5_hi_t import bfb_dae
from snap_shot import snap
import sys, os
import itertools, sys
from numpy.random import normal as npm

states = ["Hgc", "Nsc", "Hsc", "Hge", "Nse", "Hse"]
# x_noisy = ["Ngb", "Hgb", "Ngc", "Hgc", "Nsc", "Hsc", "Nge", "Hge", "Nse", "Hse", "mom"]
# x_noisy = ["Hse"]
x_noisy = ["Hgc", "Nsc", "Hsc", "Hge", "Nse", "Hse"]
u = ["u1"]
u_bounds = {"u1":(162.183495794 * 0.0005, 162.183495794 * 10000)}

ref_state = {("c_capture", ((),)): 0.63}
# Known targets 0.38, 0.4, 0.5


y = ["Tgb", "vg"]
nfet = 10
ncpx = 3
nfex = 5
tfe = [i for i in range(1, nfet + 1)]
lfe = [i for i in range(1, nfex + 1)]
lcp = [i for i in range(1, ncpx + 1)]
lc = ['c', 'h', 'n']

y_vars = {
    "Tgb": [i for i in itertools.product(lfe, lcp)],
    "vg": [i for i in itertools.product(lfe, lcp)]
    }
# x_vars = dict()
x_vars = {
          # "Nge": [i for i in itertools.product(lfe, lcp, lc)],
          # "Hge": [i for i in itertools.product(lfe, lcp)],
          "Nsc": [i for i in itertools.product(lfe, lcp, lc)],
          "Hsc": [i for i in itertools.product(lfe, lcp)],
          "Nse": [i for i in itertools.product(lfe, lcp, lc)],
          "Hse": [i for i in itertools.product(lfe, lcp)],
          "Hgc": [i for i in itertools.product(lfe, lcp)],
          "Hge": [i for i in itertools.product(lfe, lcp)],
          # "mom": [i for i in itertools.product(lfe, lcp)]
          }

# States -- (5 * 3 + 6) * fe_x * cp_x.
# For fe_x = 5 and cp_x = 3 we will have 315 differential-states.

e = MheGen(d_mod=bfb_dae,
           y=y,
           x_noisy=x_noisy,
           y_vars=y_vars,
           x_vars=x_vars,
           states=states,
           u=u,
           ref_state=ref_state,
           u_bounds=u_bounds,
           diag_QR=True, nfe_t=nfet, _t=500, ncp_t=1)
# 10 fe & _t=1000 definitely degenerate
# 10 fe & _t=900 definitely degenerate
# 10 fe & _t=120 sort-of degenerate
# 10 fe & _t=50 sort-of degenerate
# 10 fe & _t=50 eventually sort-of degenerate
# 10 fe & _t=1 eventually sort-of degenerate
e.ss.dref = snap

e.load_iguess_ss()
# sys.exit()
e.ss.create_bounds()
e.solve_ss()
e.ss.report_zL(filename="mult_ss")
e.load_d_s(e.d1)
e.d1.create_bounds()
e.solve_d(e.d1)

q_cov = {}
for i in tfe:
    if i < nfet:
        for j in itertools.product(lfe, lcp, lc):
            q_cov[("Nse", j), ("Nse", j), i] = 7525.81478168 * 0.005
            q_cov[("Nsc", j), ("Nsc", j), i] = 117.650089456 * 0.005
#             q_cov[("Nse", j), ("Nse", j), i] = 735.706082714 * 0.005
for i in tfe:
    if i < nfet:
        for j in itertools.product(lfe, lcp):
            # q_cov[("Hge", j), ("Hge", j), i] = 2194.25390583 * 0.005
            q_cov[("Hse", j), ("Hse", j), i] = 731143.716603 * 0.005
            q_cov[("Hsc", j), ("Hsc", j), i] = 16668.3312216 * 0.005
            q_cov[("Hge", j), ("Hge", j), i] = 2166.86838591 * 0.005
            q_cov[("Hgc", j), ("Hgc", j), i] = 47.7911012193 * 0.005
            # q_cov[("mom", j), ("mom", j), i] = 1.14042251669 * 0.005

# for i in lfe:
#     for j in [(1,1, 'c'), (5,3, 'c')]:
#         m_cov[("yb", j), ("yb", j), i] = 1e-04

u_cov = {}
for i in tfe:
    u_cov["u1", i] = 162.183495794 * 0.005

m_cov = {}
for i in tfe:
    for j in itertools.product(lfe, lcp):
        m_cov[("Tgb", j), ("Tgb", j), i] = 40 * 0.005
        m_cov[("vg", j), ("vg", j), i] = 0.902649386907 * 0.005

e.set_covariance_meas(m_cov)
e.set_covariance_disturb(q_cov)
e.set_covariance_u(u_cov)
e.create_rh_sfx()  #: Reduced hessian computation

# Preparation phase

e.init_lsmhe_prep(e.d1, update=True)
e.lsmhe.display(filename="mhe0")
e.shift_mhe()
dum = e.d_mod(1, e.ncp_t, _t=e.hi_t)

e.init_step_mhe(dum, e.nfe_t)

e.solve_d(e.lsmhe, skip_update=False, max_cpu_time=600)  #: Pre-loaded mhe solve
e.create_rh_sfx()  #: Reduced hessian computation
e.check_active_bound_noisy()
e.load_covariance_prior()
e.set_state_covariance()

e.regen_objective_fun()  #: Regen erate the obj fun
e.deact_icc_mhe()  #: Remove the initial conditions

e.set_prior_state_from_prior_mhe()  #: Update prior-state
e.find_target_ss()  #: Compute target-steady state (beforehand)

e.solve_d(e.d1, stop_if_nopt=True)
for i in range(1, 1000):

    e.solve_d(e.d1, stop_if_nopt=True)
    e.update_state_real()  # update the current state
    e.update_soi_sp_nmpc()

    e.update_noise_meas(e.d1, m_cov)
    e.patch_input_mhe("mod", src=e.d1, fe=e.nfe_t)  #: The inputs must coincide

    e.patch_meas_mhe(e.nfe_t, src=e.d1, noisy=True)  #: Get the measurement
    e.compute_y_offset()

    e.init_step_mhe(dum, e.nfe_t)  # Initialize next time-slot

    stat = e.solve_d(e.lsmhe,
                     skip_update=False, iter_max=500,
                     jacobian_regularization_value=1e-04,
                     max_cpu_time=600)
    e.lsmhe.write_nl(name="failed_mhe1.nl")
    e.lsmhe.report_zL()
    # sys.exit()
    if stat == 1:
        stat = e.solve_d(e.lsmhe,
                         skip_update=True,
                         iter_max=250,
                         stop_if_nopt=True,
                         jacobian_regularization_value=1e-02,
                         linear_scaling_on_demand=True)
    e.update_state_mhe()

    # Prior-Covariance stuff
    e.check_active_bound_noisy()
    e.load_covariance_prior()
    e.set_state_covariance()
    e.regen_objective_fun()
    # Update prior-state
    e.set_prior_state_from_prior_mhe()

    e.print_r_mhe()

    e.shift_mhe()
    e.shift_measurement_input_mhe()

    e.cycle_ics(plant_step=True)
    e.plant_input_gen(e.d1,  "mod", src=e.ss2)
