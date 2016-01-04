import numpy as np
import tensorflow as tf

import dists

def _tf_extract_shape(t):
    shape = [d.value for d in t.get_shape()]
    return shape

# TODO: implement _infer_shape as a shared utility method based on _get_vector_dimension
# also implement _tf_extract_shape as a subroutine
# also make sure q_mean and q_stddev are the same, correct, inferred shape

class MeanFieldInference(object):

    def __init__(self, joint_density, **jd_args):

        self.joint_density = joint_density
        self.jd_args = jd_args

        self.latents = {}

        
    def add_latent(self, name, init_mean=None, init_stddev=1e-6, transform=None, shape=None):
        if init_mean is None:
            init_mean = np.random.randn()
            
        with tf.name_scope("latent_" + name) as scope:
            latent = {}
            latent["q_mean"] = tf.Variable(init_mean, name="q_mean")
            latent["q_stddev"] = tf.Variable(init_stddev, name="q_stddev")
            latent["q_entropy"] = dists.gaussian_entropy(stddev=latent["q_stddev"])
            latent["transform"] = transform
            if shape is None:
                shape = _infer_shape(init_mean, init_stddev)
            latent["shape"] = shape

            tf.histogram_summary("latent_%s/q_mean" % name, latent["q_mean"])
            tf.histogram_summary("latent_%s/q_stddev" % name, latent["q_stddev"])
        
        self.latents[name] = latent

    def build_stochastic_elbo(self, n_eps=1):

        self.total_entropy = tf.add_n([d["q_entropy"] for d in self.latents.values()])
        entropy_summary = tf.scalar_summary("entropy", self.total_entropy)        

        jacobian_terms = []
        density_terms = []
        self.gaussian_inputs = []
        for i in range(n_eps):
            with tf.name_scope("replicate_%d" % i) as scope:
                symbols = {}
                for name, latent in self.latents.items():
                    with tf.name_scope(name) as local_scope:
                        eps = tf.placeholder(dtype=tf.float32,
                                             shape=latent["shape"],
                                             name="%s_eps_%d" % (name, i))
                        self.gaussian_inputs.append(eps)
                        pre_transform = eps * latent["q_stddev"] + latent["q_mean"]

                        transform = latent["transform"]
                        if transform is not None:
                            node, log_jacobian = transform(pre_transform)
                            jacobian_summary = tf.scalar_summary("log_jacobian", log_jacobian)
                            jacobian_terms.append(log_jacobian)
                        else:
                            node = pre_transform
                        symbols[name] = node

                        if "samples" not in latent:
                            latent["samples"] = []
                        latent["samples"].append(node)
                
                symbols.update(self.jd_args)
                joint_density = self.joint_density(**symbols)
                #density_summary = tf.scalar_summary("density", joint_density)
                
            density_terms.append(joint_density)

        if len(jacobian_terms) > 0:
            self.total_log_jacobian = 1.0/n_eps * tf.add_n(jacobian_terms)
        else:
            self.total_log_jacobian = 0.0
            
        self.expected_density = 1.0/n_eps * tf.add_n(density_terms)
        self.elbo = self.total_entropy + self.expected_density + self.total_log_jacobian
        reconstruction_summary = tf.scalar_summary("expected density", self.expected_density)        
        elbo_summary = tf.scalar_summary("elbo", self.elbo)
        return self.elbo
    
    def sample_stochastic_inputs(self, feed_dict=None):
        if feed_dict is None:
            feed_dict = {}
            
        for eps in self.gaussian_inputs:
            shape = _tf_extract_shape(eps)
            feed_dict[eps] = np.random.randn(*shape)

        return feed_dict
            
    def get_posterior_samples(self, latent_name):
        return tf.pack(self.latents[latent_name]["samples"])

    def train(self, adam_rate=0.1, steps=10000, print_interval=50, display_dict=None, sess=None):
        
        if display_dict is None or len(display_dict)==0:
            print_names = []
            print_vars = []
        else:
            print_names, print_vars = zip(*display_dict.items())
        print_names = ["elbo",] + list(print_names)
        print_vars = [self.elbo,] + list(print_vars)

        debug = tf.add_check_numerics_ops()
        merged = tf.merge_all_summaries()
        train_step = tf.train.AdamOptimizer(adam_rate).minimize(-self.elbo)
        init = tf.initialize_all_variables()

        if sess is None:
            sess = tf.Session()
        writer = tf.train.SummaryWriter("/tmp/mf_logs", sess.graph_def)
        sess.run(init)
        for i in range(steps):
            fd = self.sample_stochastic_inputs()
            
            if i % print_interval == 0:
                print_vals  = sess.run(print_vars, feed_dict=fd)
                print_str = " ".join(["%s %.4f" % (n, v) for (n, v) in zip(print_names, print_vals)])
                print ("step %d " % i) + print_str

                summary_str = sess.run(merged, feed_dict=fd)
                writer.add_summary(summary_str, i)

            sess.run(debug, feed_dict=fd)
            sess.run(train_step, feed_dict = fd)
