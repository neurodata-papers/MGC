import math
import warnings
from statistics import mean, stdev

import numpy as np
from scipy.stats import norm

from mgcpy.independence_tests.abstract_class import IndependenceTest
from mgcpy.independence_tests.utils.compute_distance_matrix import \
    compute_distance
from mgcpy.independence_tests.utils.fast_functions import (_approx_null_dist,
                                                           _fast_pvalue,
                                                           _sample_atrr,
                                                           _sub_sample)
from mgcpy.independence_tests.mgc import MGC


class MGC_TS(IndependenceTest):
    def __init__(self, compute_distance_matrix=None, base_global_correlation='mgc', max_lag = 1):
        '''
        :param compute_distance_matrix: a function to compute the pairwise distance matrix, given a data matrix
        :type compute_distance_matrix: ``FunctionType`` or ``callable()``

        :param base_global_correlation: specifies which global correlation to build up-on,
                                        including 'mgc','dcor','mantel', and 'rank'.
                                        Defaults to mgc.
        :type base_global_correlation: string

        :param max_lag: Furthest lag to check for dependence.
        :type max_lag: int
        '''

        IndependenceTest.__init__(self, compute_distance_matrix)
        self.which_test = "mgc"
        self.base_global_correlation = base_global_correlation
        self.max_lag = max_lag
        self.mgc_object = MGC()

    def test_statistic(self, matrix_X, matrix_Y, is_fast=False, fast_mgc_data={}):
        """
        Computes the MGC_TS measure between two time series datasets.

            - It first computes all the local correlations
            - Then, it returns the maximal statistic among all local correlations based on thresholding.

        :param matrix_X: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*p]`` data matrix, a matrix with ``n`` samples in ``p`` dimensions
        :type matrix_X: 2D numpy.array

        :param matrix_Y: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*q]`` data matrix, a matrix with ``n`` samples in ``q`` dimensions
        :type matrix_Y: 2D numpy.array

        :param is_fast: is a boolean flag which specifies if the test_statistic should be computed (approximated)
                        using the fast version of mgc. This defaults to False.
        :type is_fast: boolean

        :param fast_mgc_data: a ``dict`` of fast mgc params, refer: self._fast_mgc_test_statistic

            - :sub_samples: specifies the number of subsamples.
        :type fast_mgc_data: dictonary

        :return: returns a list of two items, that contains:

            - :test_statistic: the sample mgc_ts statistic (not necessarily within [-1,1])
            - :test_statistic_metadata: a ``dict`` of metadata with the following keys:
                    - :dist_mtx_X: the distance matrix of sample X
                    - :dist_mtx_Y: the distance matrix of sample X
        :rtype: list

        **Example:**

        >>> import numpy as np
        >>> from mgcpy.independence_tests.mgc.mgc import MGC
        >>>
        >>> X = np.array([0.07487683, -0.18073412, 0.37266440, 0.06074847, 0.76899045,
        ...           0.51862516, -0.13480764, -0.54368083, -0.73812644, 0.54910974]).reshape(-1, 1)
        >>> Y = np.array([-1.31741173, -0.41634224, 2.24021815, 0.88317196, 2.00149312,
        ...           1.35857623, -0.06729464, 0.16168344, -0.61048226, 0.41711113]).reshape(-1, 1)
        >>> mgc_ts = MGC_TS()
        >>> mgc_ts_statistic, test_statistic_metadata = mgc.test_statistic(X, Y)
        """
        assert matrix_X.shape[0] == matrix_Y.shape[0], "Matrices X and Y need to be of dimensions [n, p] and [n, q], respectively, where p can be equal to q"

        #if is_fast:
        #    mgc_statistic, test_statistic_metadata = self._fast_mgc_test_statistic(matrix_X, matrix_Y, **fast_mgc_data)
        #else:

        n = matrix_X.shape[0]
        if len(matrix_X.shape) == 1:
            matrix_X = matrix_X.reshape((n,1))
        if len(matrix_Y.shape) == 1:
            matrix_Y = matrix_Y.reshape((n,1))
        matrix_X, matrix_Y = compute_distance(matrix_X, matrix_Y, self.compute_distance_matrix)

        p = math.sqrt(n)
        M = self.max_lag if self.max_lag is not None else math.ceil(math.sqrt(n))
        mgc = self.mgc_object
        mgc_statistic, _ = mgc.test_statistic(matrix_X, matrix_Y)
        test_statistic = n*mgc_statistic

        for j in range(1,M+1):
            dist_mtx_X = matrix_X[j:n,j:n]
            dist_mtx_Y = matrix_Y[0:(n-j),0:(n-j)]
            mgc_statistic, _ = mgc.test_statistic(dist_mtx_X, dist_mtx_Y)
            test_statistic += ((1 - j/(p*(M+1)))**2)*mgc_statistic*(n-j)

            dist_mtx_X = matrix_X[0:(n-j),0:(n-j)]
            dist_mtx_Y = matrix_Y[j:n,j:n]
            mgc_statistic, _ = mgc.test_statistic(dist_mtx_X, dist_mtx_Y)
            test_statistic += ((1 - j/(p*(M+1)))**2)*mgc_statistic*(n-j)

        test_statistic_metadata = {'dist_mtx_X' : matrix_X, 'dist_mtx_Y' : matrix_Y}
        self.test_statistic_ = test_statistic
        self.test_statistic_metadata_ = test_statistic_metadata
        return test_statistic, test_statistic_metadata

    def p_value(self, matrix_X, matrix_Y, replication_factor=1000, is_fast=False, fast_mgc_data={}):
        """
        Tests independence between two datasets using MGC_TS and block permutation test.

        :param matrix_X: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*p]`` data matrix, a matrix with ``n`` samples in ``p`` dimensions
        :type matrix_X: 2D numpy.array

        :param matrix_Y: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*q]`` data matrix, a matrix with ``n`` samples in ``q`` dimensions
        :type matrix_Y: 2D numpy.array

        :param replication_factor: specifies the number of replications to use for
                                   the permutation test. Defaults to ``1000``.
        :type replication_factor: integer

        :param is_fast: is a boolean flag which specifies if the p_value should be computed (approximated)
                        using the fast version of mgc. This defaults to False.
        :type is_fast: boolean

        :param fast_mgc_data: a ``dict`` of fast mgc params, , refer: self._fast_mgc_p_value

            - :sub_samples: specifies the number of subsamples.
        :type fast_mgc_data: dictonary

        :return: returns a list of two items, that contains:

            - :p_value: P-value of MGC
            - :metadata: a ``dict`` of metadata with the following keys:

                    - :test_statistic: the sample MGC statistic within ``[-1, 1]``
                    - :p_local_correlation_matrix: a 2D matrix of the P-values of the local correlations
                    - :local_correlation_matrix: a 2D matrix of all local correlations within ``[-1,1]``
                    - :optimal_scale: the estimated optimal scale as an ``[x, y]`` pair.
        :rtype: list

        **Example:**

        >>> import numpy as np
        >>> from mgcpy.independence_tests.mgc.mgc_ts import MGC_TS
        >>>
        >>> X = np.array([0.07487683, -0.18073412, 0.37266440, 0.06074847, 0.76899045,
        ...           0.51862516, -0.13480764, -0.54368083, -0.73812644, 0.54910974]).reshape(-1, 1)
        >>> Y = np.array([-1.31741173, -0.41634224, 2.24021815, 0.88317196, 2.00149312,
        ...           1.35857623, -0.06729464, 0.16168344, -0.61048226, 0.41711113]).reshape(-1, 1)
        >>> mgc_ts = MGC_TS()
        >>> p_value, metadata = mgc_ts.p_value(X, Y, replication_factor = 100)
        """
        assert matrix_X.shape[0] == matrix_Y.shape[0], "Matrices X and Y need to be of dimensions [n, p] and [n, q], respectively, where p can be equal to q"

        #if is_fast:
        #    p_value, p_value_metadata = self._fast_dcorr_p_value(matrix_X, matrix_Y, **fast_dcorr_data)
        #    self.p_value_ = p_value
        #    self.p_value_metadata_ = p_value_metadata
        #    return p_value, p_value_metadata
        #else:

        # Block bootstrap
        n = matrix_X.shape[0]
        block_size = int(np.ceil(np.sqrt(n)))
        test_statistic, test_statistic_metadata = self.test_statistic(matrix_X, matrix_Y)
        matrix_X = test_statistic_metadata['dist_mtx_X']
        matrix_Y = test_statistic_metadata['dist_mtx_Y']

        test_stats_null = np.zeros(replication_factor)
        for rep in range(replication_factor):
            # Generate new time series sample for Y
            permuted_indices = np.r_[[np.arange(t, t + block_size) for t in np.random.permutation((n // block_size) + 1)]].flatten()[:n]
            permuted_Y = matrix_Y[permuted_indices,:][:, permuted_indices] # TO DO: See if there is a better way to permute

            # Compute test statistic
            test_stats_null[rep], _ = self.test_statistic(matrix_X=matrix_X, matrix_Y=permuted_Y)

        p_value = np.where(test_stats_null >= test_statistic)[0].shape[0] / replication_factor
        p_value_metadata = {'test_stats_null' : test_stats_null}

        self.p_value_ = p_value
        self.p_value_metadata_ = p_value_metadata
        return p_value, p_value_metadata
