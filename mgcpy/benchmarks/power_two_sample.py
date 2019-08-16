import numpy as np
import math
from mgcpy.independence_tests.utils.transform_matrices import \
    transform_matrices
import scipy.io
import os


def power(independence_test, sample_generator, num_samples=100, num_dimensions=1, theta=0, noise=0.0, repeats=1000, alpha=.05, simulation_type=''):
    '''
    Estimate power

    :param independence_test: an object whose class inherits from the Independence_Test abstract class
    :type: Object(Independence_Test)

    :param sample_generator: a function used to generate simulation from simulations.py with parameters given by the following arguments
        - num_samples: default to 100
        - num_dimensions: default to 1
        - noise: default to 0
    :type: function

    :param num_samples: the number of samples generated by the simulation
    :type: int

    :param num_dimensions: the number of dimensions of the samples generated by the simulation
    :type: int

    :param noise: the noise used in simulation
    :type: float

    :param repeats: the number of times we generate new samples to estimate the null/alternative distribution
    :type: int

    :param alpha: the type I error level
    :type: float

    :param simulation_type: specify simulation when necessary (default to empty string)
    :type: string

    :return empirical_power: the estimated power
    :type: float
    '''

    # test statistics under the null, used to estimate the cutoff value under the null distribution
    test_stats_null = np.zeros(repeats)
    # test statistic under the alternative
    test_stats_alternative = np.zeros(repeats)
    theta = math.radians(theta)
    a = [[0 for x in range(2)] for y in range(2)]
    a[0][0] = math.cos(theta)
    a[0][1] = math.sin(theta)*(-1)
    a[1][0] = math.sin(theta)
    a[1][1] = math.cos(theta)
    a = np.asarray(a)
    for rep in range(repeats):
        # generate new samples for each iteration
        # the if-else block below is for simulations that have a different argument list
        # than the general case
        if simulation_type == 'sine_16pi':
            matrix_X, matrix_Y = sample_generator(
                num_samples, num_dimensions, noise=noise, period=np.pi*16)
        elif simulation_type == 'multi_noise' or simulation_type == 'multi_indept':
            matrix_X, matrix_Y = sample_generator(num_samples, num_dimensions)
        elif simulation_type == 'ellipse':
            matrix_X, matrix_Y = sample_generator(
                num_samples, num_dimensions, noise=noise, radius=5)
        elif simulation_type == 'diamond':
            matrix_X, matrix_Y = sample_generator(
                num_samples, num_dimensions, noise=noise, period=-np.pi/8)
        else:
            matrix_X, matrix_Y = sample_generator(
                num_samples, num_dimensions, noise=noise)

        data_matrix_X = transform_matrices(matrix_X, matrix_Y)[0]
        data_matrix_Y = transform_matrices(matrix_X, matrix_Y)[1]
        data_matrix_Y = data_matrix_Y[:, np.newaxis]
        data_matrix_X = data_matrix_X.T
        data_matrix_X = np.dot(data_matrix_X, a)
        # permutation test
        permuted_y = np.random.permutation(matrix_Y)
        test_stats_null[rep], _ = independence_test.test_statistic(
            matrix_X, permuted_y)
        test_stats_alternative[rep], _ = independence_test.test_statistic(
            matrix_X, matrix_Y)

        '''
        # if the test is pearson, use absolute value of the test statistic
        # so the more extreme test statistic is still in a one-sided interval
        if independence_test.get_name() == 'pearson':
            test_stats_null[rep] = abs(test_stats_null[rep])
            test_stats_alternative[rep] = abs(test_stats_alternative[rep])
        '''

    # the cutoff is determined so that 1-alpha of the test statistics under the null distribution
    # is less than the cutoff
    cutoff = np.sort(test_stats_null)[math.ceil(repeats*(1-alpha))]
    # the proportion of test statistics under the alternative which is no less than the cutoff (in which case
    # the null is rejected) is the empirical power
    empirical_power = np.where(test_stats_alternative >= cutoff)[
        0].shape[0] / repeats
    return empirical_power


def power_given_data(independence_test, simulation_type, data_type='dimension', num_samples=100, num_dimensions=1, repeats=1000, alpha=.05):
    # test statistics under the null, used to estimate the cutoff value under the null distribution
    test_stats_null = np.zeros(repeats)
    # test statistic under the alternative
    test_stats_alternative = np.zeros(repeats)
    # absolute path to the benchmark directory
    dir_name = os.path.dirname(__file__)
    if data_type == 'dimension':
        file_name_prefix = dir_name + \
            '/sample_data_power_dimensions/type_{}_dim_{}'.format(
                simulation_type, num_dimensions)
    else:
        file_name_prefix = dir_name + \
            '/sample_data_power_sample_sizes/type_{}_size_{}'.format(
                simulation_type, num_samples)
    all_matrix_X = scipy.io.loadmat(file_name_prefix + '_X.mat')['X']
    all_matrix_Y = scipy.io.loadmat(file_name_prefix + '_Y.mat')['Y']
    for rep in range(repeats):
        matrix_X = all_matrix_X[:, :, rep]
        matrix_Y = all_matrix_Y[:, :, rep]
        # permutation test
        permuted_y = np.random.permutation(matrix_Y)
        test_stats_null[rep], _ = independence_test.test_statistic(
            matrix_X, permuted_y)
        test_stats_alternative[rep], _ = independence_test.test_statistic(
            matrix_X, matrix_Y)
        '''
        # if the test is pearson, use absolute value of the test statistic
        # so the more extreme test statistic is still in a one-sided interval
        if independence_test.get_name() == 'pearson':
            test_stats_null[rep] = abs(test_stats_null[rep])
            test_stats_alternative[rep] = abs(test_stats_alternative[rep])
        '''

    # the cutoff is determined so that 1-alpha of the test statistics under the null distribution
    # is less than the cutoff
    cutoff = np.sort(test_stats_null)[math.ceil(repeats*(1-alpha))]
    # the proportion of test statistics under the alternative which is no less than the cutoff (in which case
    # the null is rejected) is the empirical power
    empirical_power = np.where(test_stats_alternative >= cutoff)[
        0].shape[0] / repeats
    return empirical_power
