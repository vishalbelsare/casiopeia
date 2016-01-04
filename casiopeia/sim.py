#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2016 Adrian Bürger
#
# This file is part of casiopeia.
#
# casiopeia is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# casiopeia is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with casiopeia. If not, see <http://www.gnu.org/licenses/>.

'''The module ``casiopeia.sim`` contains the class used for system simulation.'''

import numpy as np

from interfaces import casadi_interface as ci
from intro import intro

import inputchecks

class Simulation(object):

    '''The class :class:`casiopeia.sim.Simulation` is used to
    simulate dynamic systems defined with the
    :class:`casiopeia.system.System` class. It is supposed that the 
    system containsa number of time-constant parameters :math:`p`.'''

    @property
    def simulation_results(self):

        try:

            return self.__simulation_results

        except AttributeError:

            raise AttributeError('''
A system simulation has to be executed before the simulation results
can be accessed, please run run_system_simulation() first.
''')


    def __generate_simulation_ode(self, pdata):

        p = inputchecks.check_parameter_data(pdata, self.__system.np)

        ode_fcn = ci.mx_function("ode_fcn", \
            [self.__system.t, self.__system.u, self.__system.x, \
            self.__system.eps_e, self.__system.eps_u, self.__system.p], \
            [self.__system.f])

        # Needs to be changes for allowance of explicit time dependecy!

        self.__ode_parameters_applied = ode_fcn([ \
            np.zeros(1), self.__system.u, self.__system.x, \
            np.zeros(self.__system.neps_e), \
            np.zeros(self.__system.neps_u), p])[0]


    def __generate_scaled_dae(self):

        t_scale = ci.mx_sym("t_scale", 1)

        dae_scaled = \
            ci.mx_function("dae_scaled", \
                ci.daeIn(x = self.__system.x, \
                    p = ci.vertcat([t_scale, self.__system.u])), \
                ci.daeOut(ode = t_scale * self.__ode_parameters_applied))

        self.__dae_scaled = dae_scaled.expand()


    def __init__(self, system, pdata):

        r'''
        :param system: system considered for simulation, specified
                       using the :class:`casiopeia.system.System` class
        :type system: casiopeia.system.System

        :param pdata: values of the time-constant parameters 
                      :math:`p \in \mathbb{R}^{n_p}`
        :type pdata: numpy.ndarray, casadi.DMatrix

        '''

        intro()

        self.__system = inputchecks.set_system(system)

        self.__generate_simulation_ode(pdata)
        self.__generate_scaled_dae()


    def __initialize_simulation(self, x0, time_points, udata, \
        integrator_options_user):

        self.__x0 = inputchecks.check_states_data(x0, self.__system.nx, 0)

        time_points = inputchecks.check_time_points_input(time_points)
        number_of_integration_steps = time_points.size - 1
        time_steps = time_points[1:] - time_points[:-1]

        udata = inputchecks.check_controls_data(udata, self.__system.nu, \
            number_of_integration_steps)

        self.__simulation_input = ci.vertcat([np.atleast_2d(time_steps), udata])

        integrator_options = integrator_options_user.copy()
        integrator_options.update({"t0": 0, "tf": 1})
        integrator = ci.Integrator("integrator", "cvodes", \
            self.__dae_scaled, integrator_options)

        self.__simulation = integrator.mapaccum("simulation", \
            number_of_integration_steps)


    def run_system_simulation(self, x0, time_points, udata = None, \
        integrator_options = {}):

        r'''
        :param x0: state values :math:`x_0 \in \mathbb{R}^{n_x}`
                   at the first time point :math:`t_0`
        :type x0: numpy.ndarray, casadi.DMatrix, list

        :param time_points: switching time points for the controls
                            :math:`t_N \in \mathbb{R}^{N}`
        :type time_points: numpy.ndarray, casadi.DMatrix, list

        :param udata: optional, values for the controls at the first :math:`N-1`
                      switching time points 
                      :math:`u_N \in \mathbb{R}^{n_u \times N-1}`; if no values
                      are given, 0 will be used
        :type udata: numpy.ndarray, casadi.DMatrix

        :param integrator_options: optional, options to be passed to the CasADi
                                   integrator (see the CasADi documentation
                                   for a list of all possible options)
        :type integrator_options: dict

        This function will run a system simulation for the specified initial
        state values and control data from :math:`t_0` to
        :math:`t_N`.

        If you receive integrator-related error messages during the simulation,
        please check the corresponding parts of the
        CasADi documentation.

        After the simulation has finished, the simulation results
        :math:`x_N` can be accessed via the class attribute
        ``Simulation.simulation_results``.

        '''

        print('\n' + '# ' + 23 * '-' + \
            ' casiopeia system simulation ' + 22 * '-' + ' #')
        print('\nRunning system simulation, this might take some time ...') 

        self.__initialize_simulation(x0 = x0, time_points = time_points, \
            udata = udata, integrator_options_user = integrator_options)

        self.__simulation_results = ci.horzcat([ \

            self.__x0,
            self.__simulation(x0 = self.__x0, p = self.__simulation_input)["xf"]

            ])

        print("\nSystem simulation finished.")