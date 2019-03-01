import numpy as np
from scipy.spatial import distance_matrix

from mgcpy.independence_tests.abstract_class import IndependenceTest


class HHG(IndependenceTest):
    def __init__(self, compute_distance_matrix=None):
        """
        :param compute_distance_matrix: a function to compute the pairwise distance matrix, given a data matrix
        :type compute_distance_matrix: FunctionType or callable()
        """
        IndependenceTest.__init__(self, compute_distance_matrix)
        self.which_test = "hhg"

    def test_statistic(self, matrix_X, matrix_Y):
        """
        Computes the HHG correlation measure between two datasets.

        :param matrix_X: a [n*p] data matrix, a matrix with n samples in p dimensions
        :type matrix_X: 2D `numpy.array`

        :param matrix_Y: a [n*q] data matrix, a matrix with n samples in q dimensions
        :type matrix_Y: 2D `numpy.array`

        :param replication_factor: specifies the number of replications to use for
                                   the permutation test. Defaults to 1000.
        :type replication_factor: int

        :return: returns a list of two items, that contains:

            - :test_statistic_: test statistic
            - :test_statistic_metadata_: (optional) a ``dict`` of metadata other than the p_value,
                                         that the independence tests computes in the process
        :rtype: float, dict

        **Example:**

        >>> import numpy as np
        >>> from mgcpy.independence_tests.hhg import HHG

        >>> X = np.array([0.07487683, -0.18073412, 0.37266440, 0.06074847, 0.76899045,
                      0.51862516, -0.13480764, -0.54368083, -0.73812644, 0.54910974]).reshape(-1, 1)
        >>> Y = np.array([-1.31741173, -0.41634224, 2.24021815, 0.88317196, 2.00149312,
                      1.35857623, -0.06729464, 0.16168344, -0.61048226, 0.41711113]).reshape(-1, 1)
        >>> hhg = HHG()
        >>> hhg_test_stat = hhg.test_statistic(X, Y)
        """
        # use the matrix shape and diagonal elements to determine if the given data is a distance matrix or not
        if matrix_X.shape[0] != matrix_X.shape[1] or sum(matrix_X.diagonal()**2) > 0:
            dist_mtx_X = self.compute_distance_matrix(matrix_X)
        if matrix_Y.shape[0] != matrix_Y.shape[1] or sum(matrix_Y.diagonal()**2) > 0:
            dist_mtx_Y = self.compute_distance_matrix(matrix_Y)

        n = dist_mtx_X.shape[0]
        S = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i != j:
                    tmp1 = dist_mtx_X[i, :] <= dist_mtx_X[i, j]
                    tmp2 = dist_mtx_Y[i, :] <= dist_mtx_Y[i, j]
                    t11 = np.sum(tmp1 * tmp2) - 2
                    t12 = np.sum(tmp1 * (1-tmp2))
                    t21 = np.sum((1-tmp1) * tmp2)
                    t22 = np.sum((1-tmp1) * (1-tmp2))
                    denom = (t11+t12) * (t21+t22) * (t11+t21) * (t12+t22)
                    if denom > 0:
                        S[i, j] = (n-2) * \
                            np.power((t12*t21 - t11*t22), 2) / denom
        corr = np.sum(S)

        # no metadata for HHG
        self.test_statistic_metadata_ = {}
        self.test_statistic_ = corr

        return self.test_statistic_, self.test_statistic_metadata_

    def p_value(self, matrix_X=None, matrix_Y=None, replication_factor=1000):
        """
        Tests independence between two datasets using HHG and permutation test.

        :param matrix_X: a [n*p] data matrix, a matrix with n samples in p dimensions
        :type matrix_X: 2D `numpy.array`

        :param matrix_Y: a [n*q] data matrix, a matrix with n samples in q dimensions
        :type matrix_Y: 2D `numpy.array`

        :param replication_factor: specifies the number of replications to use for
                                   the permutation test. Defaults to 1000.
        :type replication_factor: int

        :return: returns a list of two items, that contains:

            - :p_value_: P-value
            - :p_value_metadata_: (optional) a ``dict`` of metadata other than the p_value,
                                 that the independence tests computes in the process
        :rtype: float, dict

        **Example:**

        >>> import numpy as np
        >>> from mgcpy.independence_tests.hhg import HHG

        >>> X = np.array([0.07487683, -0.18073412, 0.37266440, 0.06074847, 0.76899045,
                      0.51862516, -0.13480764, -0.54368083, -0.73812644, 0.54910974]).reshape(-1, 1)
        >>> Y = np.array([-1.31741173, -0.41634224, 2.24021815, 0.88317196, 2.00149312,
                      1.35857623, -0.06729464, 0.16168344, -0.61048226, 0.41711113]).reshape(-1, 1)
        >>> hhg = HHG()
        >>> hhg_p_value = hhg.p_value(X, Y)
        """
        return super(HHG, self).p_value(matrix_X, matrix_Y)
