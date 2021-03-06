from __future__ import print_function
from pyomo.environ import *
from pyomo.core.base import Constraint, Objective
from pyomo.opt import ProblemFormat
from nmpc_mhe.dync.MHEGen import MheGen
from nmpc_mhe.mods.bfb.bfb_abs7momdt_ht2 import bfb_dae
from snap_shot import snap
import sys, os
import itertools, sys

states = ["Ngb", "Hgb", "Ngc", "Hgc", "Nsc", "Hsc", "Nge", "Hge", "Nse", "Hse", "mom"]
# x_noisy = ["Ngb", "Hgb", "Ngc", "Hgc", "Nsc", "Hsc", "Nge", "Hge", "Nse", "Hse", "mom"]
x_noisy = ["Hse"]
u = ["u1"]
u_bounds = {"u1":(162.183495794 * 0.0005, 162.183495794 * 10000)}

ref_state = {("c_capture", ((),)): 0.40}
# Known targets 0.38, 0.4, 0.5


y = ["P", "Tgb", "vg", "Tge", "Tgc", "cb", "cc", "Tse", "ve"]
nfet = 5
ncpx = 3
nfex = 5
tfe = [i for i in range(1, nfet + 1)]
lfe = [i for i in range(1, nfex + 1)]
lcp = [i for i in range(1, ncpx + 1)]
lc = ['c', 'h', 'n']

y_vars = {
    "P": [i for i in itertools.product(lfe, lcp)],
    "Tgb": [i for i in itertools.product(lfe, lcp)],
    "vg": [i for i in itertools.product(lfe, lcp)],
    "Tge": [i for i in itertools.product(lfe, lcp)],
    "Tgc": [i for i in itertools.product(lfe, lcp)],
    "Tse": [i for i in itertools.product(lfe, lcp)],
    "ve": [i for i in itertools.product(lfe, lcp)],
    "cb": [i for i in itertools.product(lfe, lcp, lc)],
    "cc": [i for i in itertools.product(lfe, lcp, lc)],

    }
x_vars = dict()
x_vars = {
          "Hse": [(1, 1), (1, 2)],
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
           diag_QR=True,
           IgnoreProcessNoise=True)
e.ss.dref = snap

e.load_iguess_ss()
# sys.exit()
e.ss.create_bounds()
e.solve_ss()
e.load_d_s(e.d1)
e.d1.create_bounds()
e.solve_d(e.d1)

q_cov = {}
# for i in tfe:
#     if i < nfet:
#         for j in itertools.product(lfe, lcp, lc):
#             q_cov[("Ngb", j), ("Ngb", j), i] = 0.01*5.562535786e-05
#             q_cov[("Ngc", j), ("Ngc", j), i] = 0.01*0.000335771530697
#             q_cov[("Nsc", j), ("Nsc", j), i] = 0.01*739.786503718
#             q_cov[("Nge", j), ("Nge", j), i] = 0.01*0.0100570141164
#             q_cov[("Nse", j), ("Nse", j), i] = 0.01*641.425020561
for i in tfe:
    if i < nfet:
        for j in [(1,1), (1,2)]:
            q_cov[("Hse", j), ("Hse", j), i] = 561353.476801 * 0.01


m_cov = {}
for i in lfe:
    for j in itertools.product(lfe, lcp):
        m_cov[("P", j), ("P", j), i] = 10
        m_cov[("Tgb", j), ("Tgb", j), i] = 2
        m_cov[("vg", j), ("vg", j), i] = 0.1
        m_cov[("Tse", j), ("Tse", j), i] = 2
        m_cov[("Tgc", j), ("Tgc", j), i] = 2
        m_cov[("Tge", j), ("Tge", j), i] = 2
        m_cov[("vg", j), ("vg", j), i] = 1e-01
        m_cov[("ve", j), ("ve", j), i] = 1e-01

for i in lfe:
    for j in itertools.product(lfe, lcp, lc):
        m_cov[("cb", j), ("cb", j), i] = 1e-04
        m_cov[("cc", j), ("cc", j), i] = 1e-04

u_cov = {}
for i in tfe:
    u_cov["u1", i] = 5



e.set_covariance_meas(m_cov)
e.set_covariance_disturb(q_cov)
e.set_covariance_u(u_cov)
e.create_rh_sfx()  #: Reduced hessian computation

# Preparation phase
e.init_lsmhe_prep(e.d1)

#e.shift_mhe()
dum = e.d_mod(1, e.ncp_t, _t=e.hi_t)

dum.create_bounds()
e.init_step_mhe(dum, e.nfe_t)

# e.deb_alg_sys_dyn()
tst = e.solve_d(e.d1, skip_update=False)  #: Pre-loaded mhe solve
e.set_prior_state_from_prior_mhe()
e.lsmhe.name = "First MHE"
tst = e.solve_d(e.lsmhe, skip_update=False,
                max_cpu_time=100000,
                halt_on_ampl_error=True,
                jacobian_regularization_value=1e-02,
                output_file="file_mhe0.txt")  #: Pre-loaded mhe solve

# with open("cons_first.txt", "w") as f:
#     for con in e.lsmhe.component_objects(Constraint, active=True):
#         con.pprint(ostream=f)
#     for obj in e.lsmhe.component_objects(Objective, active=True):
#         obj.pprint(ostream=f)
#     f.close()

if tst != 0:
    sys.exit()
    e.lsmhe.write_nl(name="failed_mhe.nl")
    e.lsmhe.snap_shot(filename="mhe_values0.py")
    e.solve_d(e.lsmhe, skip_update=False, max_cpu_time=1000,
              stop_if_nopt=True, halt_on_ampl_error=True,
              output_file="file_mhe1.txt")  #: Pre-loaded mhe solve
e.lsmhe.name = "LSMHE (Least-Squares MHE)"
e.check_active_bound_noisy()
e.load_covariance_prior()
e.set_state_covariance()

e.regen_objective_fun()  #: Regen erate the obj fun
e.deact_icc_mhe()  #: Remove the initial conditions
e.lsmhe.obfun_mhe_first.deactivate()
e.lsmhe.obfun_mhe.activate()
e.set_prior_state_from_prior_mhe()  #: Update prior-state
e.find_target_ss()  #: Compute target-steady state (beforehand)

# with open("cons_mhe.txt", "w") as f:
#     for con in e.lsmhe.component_objects(Constraint, active=True):
#         con.pprint(ostream=f)
#     for obj in e.lsmhe.component_objects(Objective, active=True):
#         obj.pprint(ostream=f)
#     f.close()


with open("mult_boundsss2.txt", "w") as f:
    e.ss2.ipopt_zL_out.pprint(ostream=f)
    f.close()
# For ideal nmpc
for i in range(1, 15):
    print(str(i) + "--"*20, file=sys.stderr)
    print("*"*100)

    if i == 3:
        e.plant_input_gen(e.d1, "mod", src=e.ss2)

    e.solve_d(e.d1)
    if i == 3:
        e.d1.display(filename="plant.txt")
    # e.update_noise_meas(e.d1, m_cov)
    e.patch_input_mhe("mod", src=e.d1, fe=e.nfe_t)  #: The inputs must coincide
    some_val = value(e.lsmhe.u1[e.nfe_t]) - value(e.d1.u1[1])
    print(some_val, "Value of the offset")
    e.patch_meas_mhe(e.nfe_t, src=e.d1, noisy=False)  #: Get the measurement
    e.compute_y_offset()

    e.init_step_mhe(dum, e.nfe_t)  # Initialize next time-slot

    tst = e.solve_d(e.lsmhe, skip_update=False, max_cpu_time=1000,
                    halt_on_ampl_error=False,
                    output_file="file_mhe0.txt")  #: Pre-loaded mhe solve
    # with open("cons_1.txt", "w") as f:
    #     for con in e.lsmhe.component_objects(Constraint, active=True):
    #         con.pprint(ostream=f)
    #     f.close()

    if tst != 0:
        # with open("cons_1.txt", "w") as f:
        #     for con in e.lsmhe.component_objects(Constraint, active=True):
        #         con.pprint(ostream=f)
        #     f.close()
        # e.lsmhe.pprint(filename="mhe_model.txt")
        e.lsmhe.snap_shot(filename="mhe_values.py")
        e.lsmhe.write_nl(name="failed_mhe.nl")
        e.solve_d(e.lsmhe, skip_update=False, max_cpu_time=1000,
                  stop_if_nopt=True, halt_on_ampl_error=False,
                  output_file="file_mhe1.txt")  #: Pre-loaded mhe solve


    # Prior-Covariance stuff
    e.check_active_bound_noisy()
    e.load_covariance_prior()
    e.set_state_covariance()
    e.regen_objective_fun()
    # Update prior-state
    e.set_prior_state_from_prior_mhe()

    e.print_r_mhe()

    # Compute the controls

    e.shift_mhe()
    e.shift_measurement_input_mhe()

    e.cycle_ics(plant_step=True)
