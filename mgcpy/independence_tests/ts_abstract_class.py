import warnings
from scipy.stats import norm, chi2
from scipy.spatial.distance import pdist, squareform
import numpy as np
from mgcpy.independence_tests.utils.compute_distance_matrix import compute_distance
from abc import ABC, abstractmethod
from joblib import Parallel, delayed

def EUCLIDEAN_DISTANCE(x):
    return squareform(pdist(x, metric="euclidean"))

class TimeSeriesIndependenceTest(ABC):
    """
    TimeSeriesIndependenceTest abstract class.

    Specifies the generic interface that must be implemented by
    all the independence tests for time series.
    """

    def __init__(self, test, which_test, compute_distance_matrix = None, max_lag = 0):
        '''
        :param test: An independence test object for which to compute the test statistic.
        :type test: IndependenceTest

        :param which_test: Either 'mgcx' or 'unbiased' DCorrX or 'biased' DCorrX.
        :type which_test: string

        :param compute_distance_matrix: a function to compute the pairwise distance matrix, given a data matrix
        :type compute_distance_matrix: ``FunctionType`` or ``callable()``

        :param max_lag: Furthest lag to check for dependence. Defaults to log(n).
        :type max_lag: integer
        '''
        self.test_statistic_ = None
        self.test_statistic_metadata_ = None
        self.p_value_ = None
        self.p_value_metadata_ = None
        self.which_test = which_test

        if not compute_distance_matrix:
            compute_distance_matrix = EUCLIDEAN_DISTANCE
        self.compute_distance_matrix = compute_distance_matrix
        self.max_lag = max_lag
        self.test_obj = test

        super().__init__()

    def get_name(self):
        """
        :return: the name of the time series independence test
        :rtype: string
        """
        return self.which_test

    def _validate_input(self, matrix_X, matrix_Y, block_size, M):
        """
        Helper function to validate inputs.

        :param matrix_X: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*p]`` data matrix, a matrix with ``n`` samples in ``p`` dimensions
        :type matrix_X: 2D numpy.array

        :param matrix_Y: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*q]`` data matrix, a matrix with ``n`` samples in ``q`` dimensions
        :type matrix_Y: 2D numpy.array

        :param block_size: Block size for block permutation procedure. Default sqrt(n).
        :type block_size: integer

        :param M: Max lag for test statistic.
        :type M: integer

        :return: returns a list of four items, that contains:

            - :matrix_X: ``[n*n]` distance matrix X.
            - :matrix_Y: ``[n*n]` distance matrix Y.
            - :block_size: Block size for block permutation procedure
            - :M: Max lag for test statistic.
            - :n: The sample size.
        :rtype: list
        """
        assert matrix_X.shape[0] == matrix_Y.shape[0], "Matrices X and Y need to be of dimensions [n, p] and [n, q], respectively, where p can be different from q"
        n = matrix_X.shape[0]
        if M >= n - 4:
            raise ValueError('max_lag must be less than n - 4.')

        # Represent univariate data as matrices.
        # Use the matrix shape and diagonal elements to determine if the given data is a distance matrix or not.
        if len(matrix_X.shape) == 1:
            matrix_X = matrix_X.reshape((n,1))
        if len(matrix_Y.shape) == 1:
            matrix_Y = matrix_Y.reshape((n,1))
        matrix_X, matrix_Y = compute_distance(matrix_X, matrix_Y, self.compute_distance_matrix)

        if block_size is None: block_size = int(np.ceil(np.sqrt(n)))
        M = self.max_lag if self.max_lag is not None else np.ceil(np.log(n))

        return matrix_X, matrix_Y, block_size, M, n

    def test_statistic(self, matrix_X, matrix_Y):
        """
        Test statistic for MGCX and DCorrX (and other distance tests) between two time series.

        :param matrix_X: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*p]`` data matrix, a matrix with ``n`` samples in ``p`` dimensions
        :type matrix_X: 2D numpy.array

        :param matrix_Y: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*q]`` data matrix, a matrix with ``n`` samples in ``q`` dimensions
        :type matrix_Y: 2D numpy.array

        :return: returns a list of two items, that contains:

            - :test_statistic: the sample test statistic (between [0,M])
            - :test_statistic_metadata: a ``dict`` of metadata with the following keys:
                    - :optimal_lag: the lag of maximal dependence
                    - :dependence_by_lag: the test_statistic restricted to each lag.
        :rtype: list
        """
        matrix_X, matrix_Y, block_size, M, n = self._validate_input(matrix_X, matrix_Y, None, self.max_lag)
        test = self.test_obj

        # Collect the test statistic by lag, and sum them for the full test statistic.
        dependence_by_lag = np.zeros(M+1)
        optimal_scale = None
        optimal_lag = 0

        statistic, metadata = test.test_statistic(matrix_X, matrix_Y)
        if self.which_test == 'mgcx': optimal_scale = metadata['optimal_scale']

        dependence_by_lag[0] = np.maximum(0.0, statistic)
        for j in range(1, M+1):
            dist_mtx_X = matrix_X[j:n,j:n]
            dist_mtx_Y = matrix_Y[0:(n-j),0:(n-j)]
            statistic, metadata = test.test_statistic(dist_mtx_X, dist_mtx_Y)
            dependence_by_lag[j] = (n - j)*np.maximum(0.0, statistic) / n
            if dependence_by_lag[j] > dependence_by_lag[optimal_lag]:
                optimal_lag = j
                if self.which_test == 'mgcx': optimal_scale = metadata['optimal_scale']

        # Reporting optimal lag
        test_statistic_metadata = { 'optimal_lag' : optimal_lag, 'dependence_by_lag' : dependence_by_lag }
        if self.which_test == 'mgcx': test_statistic_metadata['optimal_scale'] = optimal_scale
        self.test_statistic_ = np.sum(dependence_by_lag)
        self.test_statistic_metadata_ = test_statistic_metadata
        return self.test_statistic_, self.test_statistic_metadata_

    def p_value(self, matrix_X, matrix_Y, replication_factor=1000, is_fast = False, block_size = None, subsample_size = -1):
        """
        Tests independence between two datasets using block permutation test.

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

        :param is_fast: whether to use Fast MGCX or Fast DCorrX.
        :type is_fast: boolean

        :param block_size: Block size for block permutation procedure. Default sqrt(n).
        :type block_size: integer

        :param subsample_size: specifies the number of observations in the subsample.
        :type subsample_size: integer

        :return: returns a list of two items, that contains:

            - :p_value: P-value of MGC
            - :metadata: a ``dict`` of metadata with the following keys:
                    - :null_distribution: numpy array representing distribution of test statistic under null.
        :rtype: list
        """
        matrix_X, matrix_Y, block_size, _, n = self._validate_input(matrix_X, matrix_Y, block_size, self.max_lag)

        test_statistic, _ = self.test_statistic(matrix_X, matrix_Y)
        if is_fast:
            return self._fast_p_value(matrix_X, matrix_Y, test_statistic, block_size, subsample_size = subsample_size)

        # Parallelized block bootstrap.
        def worker(rep):
            permuted_indices = np.r_[[np.arange(t, t + block_size) for t in np.random.choice(n, n // block_size + 1)]].flatten()[:n]
            permuted_indices = np.mod(permuted_indices, n)
            permuted_Y = matrix_Y[np.ix_(permuted_indices, permuted_indices)]

            # Compute test statistic
            ret, _ = self.test_statistic(matrix_X, permuted_Y)
            return ret

        test_stats_null = Parallel(n_jobs=-2)(delayed(worker)(rep) for rep in range(replication_factor))

        self.p_value_ = np.sum(np.greater(test_stats_null, test_statistic)) / replication_factor
        if self.p_value_ == 0.0:
            self.p_value_ = 1 / replication_factor
        self.p_value_metadata_ = {'null_distribution': test_stats_null}

        return self.p_value_, self.p_value_metadata_

    def _fast_p_value(self, matrix_X, matrix_Y, test_statistic, block_size, subsample_size = -1):
        """
        Fast and powerful test by subsampling that runs in O(n^2 log(n)+ns*n), based on
        C. Shen and J. Vogelstein, “Fast and Powerful Testing for Distance-Based Correlations”
        (adapted for time series).

        Faster version of MGC's test_statistic function

            - It computes local correlations and test statistics by subsampling
            - Then, it returns the maximal statistic among all local correlations based on thresholding.

        :param matrix_X: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*p]`` data matrix, a matrix with ``n`` samples in ``p`` dimensions
        :type matrix_X: 2D numpy.array

        :param matrix_Y: is interpreted as either:

            - a ``[n*n]`` distance matrix, a square matrix with zeros on diagonal for ``n`` samples OR
            - a ``[n*q]`` data matrix, a matrix with ``n`` samples in ``q`` dimensions
        :type matrix_Y: 2D numpy.array

        :param test_statistic: test statistic computed on entire data.
        :type test_statistic: float

        :param block_size: Block size for block permutation test.
        :type block_size: integer

        :param subsample_size: specifies the number of observations in the subsample.
        :type subsample_size: integer

        :return: returns a list of two items, that contains:

            - :p_value: the estimated p_value computed by normal approximation.
            - :metadata: a ``dict`` of metadata with the following keys:
                    - :null_distribution: the observations of the test statistic on each subsample.
        :rtype: list
        """
        n = matrix_X.shape[0]
        if subsample_size < self.max_lag + 10:
            subsample_size = np.maximum(self.max_lag + 10, int(np.floor(np.sqrt(n))))

        # TO DO.
        # subsample_size = int(np.floor(np.sqrt(n)))

        num_samples = n // subsample_size
        if num_samples < 4:
            raise ValueError('n must be at least 4*(max_lag + max(sqrt(n), 10)) to use fast implementation.')
        
        # Permute once.
        permuted_indices = np.r_[[np.arange(t, t + block_size) for t in np.random.choice(n, n // block_size + 1)]].flatten()[:n]
        permuted_indices = np.mod(permuted_indices, n)
        permuted_Y = matrix_Y[np.ix_(permuted_indices, permuted_indices)]

        # Parallelized subsample.
        def worker(i):
            indices = np.arange(subsample_size*i, subsample_size*(i + 1))
            sub_matrix_X = matrix_X[np.ix_(indices, indices)]
            sub_matrix_Y = permuted_Y[np.ix_(indices, indices)]
            return self.test_statistic(sub_matrix_X, sub_matrix_Y)[0]

        test_stats_null = Parallel(n_jobs=-2)(delayed(worker)(i) for i in range(num_samples))

        # Normal approximation for the p_value.
        mu = np.mean(test_stats_null)
        sigma = np.std(test_stats_null)
        if sigma < 10e-4:
            x = 0.0
        else:
            x = num_samples*(test_statistic - mu)/sigma + 1
        self.p_value_ = 1 - chi2.cdf(x, 1)
        self.p_value_metadata_ = {'null_distribution': test_stats_null}

        return self.p_value_, self.p_value_metadata_
