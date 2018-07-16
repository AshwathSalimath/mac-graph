
import tensorflow as tf

from ..util import *

def memory_cell(args, features, in_memory_state, in_data_read, in_control_state):

	with tf.name_scope("memory_cell"):
		assert_shape(in_memory_state, [args["memory_width"]])
		
		in_all = tf.concat([
			in_memory_state, 
			in_data_read
		], -1)

		new_memory_state = deeep(in_all, args["memory_width"], 5)

		# We can run this network without a control cell
		if in_control_state is not None:
			forget_scalar = tf.layers.dense(in_control_state, 1, activation=tf.nn.tanh)
		else:
			forget_scalar = tf.layers.dense(in_all, 1, activation=tf.nn.tanh)
	
		out_memory_state = (new_memory_state * forget_scalar) + (in_memory_state * (1-forget_scalar))
		out_memory_state = dynamic_assert_shape(out_memory_state, [features["d_batch_size"], args["memory_width"]])
		return out_memory_state