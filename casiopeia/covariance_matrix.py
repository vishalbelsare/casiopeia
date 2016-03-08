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

from interfaces import casadi_interface as ci

class CovarianceMatrix(object):

    @property
    def covariance_matrix_for_evaluation(self):

        try:

            return self.__covariance_matrix_for_evaluation

        except AttributeError:

            self.__setup_covariance_matrix_for_evaluation()

            return self.__covariance_matrix_for_evaluation

    @property
    def covariance_matrix_for_optimization(self):

        try:

            return self.__covariance_matrix_for_optimization

        except AttributeError:

            self.__setup_covariance_matrix_for_optimization()

            return self.__covariance_matrix_for_optimization

    @property
    def covariance_matrix_additional_constraints(self):

        try:

            return self.__covariance_matrix_additional_constraints

        except AttributeError:

            self.__setup_covariance_matrix_for_optimization()

            return self.__covariance_matrix_additional_constraints


    @property
    def covariance_matrix_additional_optimization_variables(self):

        try:

            return self.__covariance_matrix_additional_optimization_variables

        except AttributeError:

            self.__setup_covariance_matrix_for_optimization()

            return self.__covariance_matrix_additional_optimization_variables


    def __setup_langrangian_hessian(self, pe_setup):

        # Get the Hessian matrix of the Lagrangian of the Gauss Newton (!)
        # least squares parameter estimation problem

        self.hess_lag = pe_setup.gauss_newton_lagrangian_hessian


    def __setup_kkt_matrix(self, pe_setup):

        # Construct the KKT matrix from the Hessian of the Langrangian and the
        # Jacobian of the equality constraints

        kkt_matrix_A = self.hess_lag

        kkt_matrix_B = ci.jacobian(pe_setup._constraints, \
            pe_setup._optimization_variables)

        kkt_matrix_C = ci.mx(pe_setup._constraints.shape[0], \
            pe_setup._constraints.shape[0])

        self.kkt_matrix = ci.blockcat( \
            kkt_matrix_A, kkt_matrix_B.T, \
            kkt_matrix_B, kkt_matrix_C)


    def __split_kkt_matrix(self, pe_setup):

        number_of_unknown_parameters = pe_setup._discretization.system.np

        self.cov_mat_inv_A = self.kkt_matrix[: number_of_unknown_parameters, \
            : number_of_unknown_parameters]

        self.cov_mat_inv_B = self.kkt_matrix[number_of_unknown_parameters :, \
            : number_of_unknown_parameters]

        self.cov_mat_inv_C = self.kkt_matrix[number_of_unknown_parameters :, \
            number_of_unknown_parameters :]


    def __setup_covariance_matrix_scaling(self, pe_setup):

        # Calculate a scaling factor beta to multiply with the covariance
        # matrix so that the output for the (co-)variaces and standard
        # deviations matches the problem correctly; this is only necessary
        # when evaluating the covariance matrix for a given parameter
        # estimation problem (i. e. if residuals already exist);
        # for DOE, this scaling is irrelevant

        # self.__beta = 1.0

        # if residuals is not None:

        self.__beta = \
            ci.mul([pe_setup._residuals.T, pe_setup._residuals]) / \
                (pe_setup._residuals.size() + \
            pe_setup._constraints.size1() - \
            pe_setup._optimization_variables.size())



    def __init__(self, pe_setup):

        r'''

        This class is designed only for internal use within casiopeia!

        This class is used to construct the covariance matrix from the inverse
        of the KKT matrix; in this way only the relevant part of the covariance
        matrix that contains the information about the unknown parameters
        is constructed.

        For further information, see
        http://www.am.uni-erlangen.de/home/spp1253/wiki/images/b/b3/
        Freising10_19_-_Kostina_-_Towards_Optimum.pdf and Walter, Eric and
        Prozanto, Luc: Identification of Parametric Models from Experimental
        Data, Springer, 1997, pages 288/289.

        '''

        # The naming of the matrix blocks within this class matches the
        # following scheme:
        #
        #              n_a
        #            -------------
        #        m_a |  A  | B^T |
        #            |-----|-----|
        #        m_b |  B  |  C  |
        #            -------------
        #


        self.__setup_langrangian_hessian(pe_setup)

        self.__setup_kkt_matrix(pe_setup)

        self.__split_kkt_matrix(pe_setup)

        self.__setup_covariance_matrix_scaling(pe_setup)


    def __setup_covariance_matrix_for_evaluation(self):

        cov_mat_A = self.__beta * ci.solve( \

                self.cov_mat_inv_A - ci.mul([ \

                    self. cov_mat_inv_B.T, \

                    ci.solve(self.cov_mat_inv_C, \
                        
                        self.cov_mat_inv_B, \
                        
                        "csparse")]), \

                ci.mx_eye(self.cov_mat_inv_A.shape[0]), \

                "csparse"

            )

        self.__covariance_matrix_for_evaluation = cov_mat_A


    def __setup_covariance_matrix_for_optimization(self):

        # Introduce additional matrices of optimization variables E and F to
        # move the matrix inversions into the NLP constraints for efficiency
        # (arising from the resulting increase in structure of the
        # optimization problem)

        E = ci.mx_sym("E", \
            self.cov_mat_inv_C.shape[0], self.cov_mat_inv_B.shape[1])
        F = ci.mx_sym("F", \
            *self.cov_mat_inv_A.shape)

        constraints_E = ci.mul([self.cov_mat_inv_C, E]) - self.cov_mat_inv_B
        constraints_F = ci.mul([ \
            (self.cov_mat_inv_A - ci.mul([self.cov_mat_inv_B.T, E])), F]) - \
            ci.mx_eye(self.cov_mat_inv_A.shape[0])

        self.__covariance_matrix_for_optimization = F
        self.__covariance_matrix_additional_optimization_variables = \
            ci.veccat([E, F])
        self.__covariance_matrix_additional_constraints = ci.veccat([ \
            constraints_E, constraints_F])

        import ipdb
        ipdb.set_trace()
        

def setup_a_criterion(covariance_matrix):

    return (1.0 / covariance_matrix.shape[0]) * ci.trace(covariance_matrix)


def setup_d_criterion(covariance_matrix):

    return pow(ci.det(covariance_matrix), (1.0 / covariance_matrix.shape[0]))
