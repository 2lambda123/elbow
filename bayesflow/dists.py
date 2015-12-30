import numpy as np
import tensorflow as tf

from bayesflow.special_hacks import gammaln, betaln
import scipy.special

def _get_vector_dimension(*args):
    """Computes the dimension to broadcast a set of arguments to.
       
    Args:
        *args: each argument is a Python or TensorFlow vector or scalar, or None.

    Returns:
        d: the length common to all input vectors, if such exists. If all inputs are scalars           or None, returns 1. 

    Raises:
        ValueError: if inputs have incompatible dimensions, or if any input is invalid. 
    """

    d = None
    for arg in args:
        if arg is None:
            continue

        if isinstance(arg, tf.Tensor):
            dims = arg.get_shape().dims
            if len(dims) == 0: # is a scalar
                continue
            elif len(dims) == 1:
                d_arg = dims[0].value
            else:
                raise ValueError("trying to get vector dimension of higher-order tensor %s" % repr(arg))
        else: # this is a Python object of some sort
            try:
                d_arg = len(d)
            except TypeError:
                # assume this means scalar
                continue
            
        if d is not None and d_arg != d:
            raise ValueError("vectors of incompatible dimensions %d and %d" % d, d_arg)
        d = d_arg
    
    if d is None:
        d = 1

    return d
    
def gaussian_entropy(stddev=None, variance=None):
    """Creates a TensorFlow variable representing the sum of one or more
    Gaussian entropies.

    Args:
        stddev (optional, vector or scalar): mutually exclusive with variance
        variance (optional, vector or scalar): mutually exclusive with stddev

    Note that the entropy of a Gaussian does not depend on the mean. 

    Returns:
        h: TF scalar containing the total entropy of this distribution
    """
    if variance is None:
        variance = stddev*stddev

    d = _get_vector_dimension(variance)

    t = .5 * (1 + np.log(2*np.pi) + tf.log(variance))
    entropy = tf.reduce_sum(t)
    return entropy

def gaussian_log_density(x, mean=None, stddev=None, variance=None):
    """Creates a TensorFlow variable representing the sum of one or more
    independent Gaussian log-densities.

    Args:
        x (scalar or vector): variable(s) being modeled as Gaussian
        mean (optional): defaults to zero if not specified
        stddev (optional): mutually exclusive with variance
        variance (optional): mutually exclusive with stddev

    Each of mean, stddev, variance must either be the same dimension
    as x, or a scalar (which will be broadcast as required). They may
    be TensorFlow variables or Python/numpy values.

    Returns:
        lp: TF scalar containing the log probability of x 
    """
    
    if variance is None:
        variance = stddev * stddev
    
    if mean is None:
        r = x
    else:
        r = x - mean

    z = r*r / variance
    
    lps = -0.5 * z   - .5 * tf.log(2*np.pi * variance)
    lp = tf.reduce_sum(lps)
    return lp

def gaussian_kl(mu_p, sigma2_p, mu_q=None, sigma2_q=None):

    if mu_q is None and sigma2_q is None:
        # assume standard normal
        kl = .5 * (tf.square(mu_p) + sigma2_p - 1 - tf.log(sigma2_p))
    else:
        kl = .5 * (tf.square(mu_p - mu_q)/sigma2_q + sigma2_p/sigma2_q - 1 - tf.log(sigma2_p) + tf.log(sigma2_q))
        
    return kl

def inv_gamma_log_density(x, alpha, beta):
    """Creates a TensorFlow variable representing the sum of one or more
    independent inverse Gamma log-densities.

    Args:
        x (scalar or vector): variable(s) being modeled as InvGamma
        alpha (scalar or vector)
        beta (scalar or vector)

    Each of alpha and beta must either be the same dimension
    as x, or a scalar (which will be broadcast as required). They may
    be TensorFlow variables or Python/numpy values.

    Returns:
        lp: TF scalar containing the log probability of x 
    """

    if isinstance(beta, tf.Tensor):
        log_beta = tf.log(beta)
    else:
        log_beta = np.log(beta)

    if isinstance(x, tf.Tensor):
        log_x = tf.log(x)
    else:
        log_x = np.log(x)


    if isinstance(alpha, tf.Tensor):
        gammaln_alpha = gammaln(alpha)
    else:
        gammaln_alpha = scipy.special.gammaln(alpha)

    lps = -beta / x + alpha * log_beta - (alpha+1) * tf.log(x) - gammaln_alpha
    lp = tf.reduce_sum(lps)
    return lp
    
def gamma_log_density(x, alpha, beta, parameterization=None):
    """Creates a TensorFlow variable representing the sum of one or more
    independent inverse Gamma densities.

    Args:
        x (scalar or vector): variable(s) being modeled as InvGamma
        alpha (scalar or vector):
        beta (scalar or vector):

    Each of alpha and beta must either be the same dimension
    as x, or a scalar (which will be broadcast as required). They may
    be TensorFlow variables or Python/numpy values.

    Returns:
        lp: TF scalar containing the log probability of x 
    """

    try:
        dtype = x.dtype
    except AttributeError:
        try:
            dtype = alpha.dtype
        except AttributeError:
            dtype = beta.dtype
        
    if isinstance(beta, tf.Tensor):
        log_beta = tf.log(beta)
    else:
        log_beta = np.log(beta)

    if isinstance(x, tf.Tensor):
        log_x = tf.log(x)
    else:
        log_x = np.log(x)
    
            
    l1 = -beta * x
    l2 = alpha * log_beta
    l3 = (alpha-1) * log_x

    if isinstance(alpha, tf.Tensor):
        l4 = gammaln(alpha)
    else:
        l4 = scipy.special.gammaln(alpha)

    lps = l1 + l2 + l3 - l4
    lp = tf.reduce_sum(lps)
    return lp

def beta_log_density(x, alpha=1.0, beta=1.0):
    log_z = betaln(alpha, beta)
    log_density = (alpha - 1) * tf.log(x) + (beta-1) * tf.log(1-x) - log_z
    return log_density

def bernoulli_log_density(x, p):

    lp = tf.log(p)
    lp1 = tf.log(1-p)
    log_probs = tf.mul(x, lp) + tf.mul(1-x, lp1)
    return log_probs
    

