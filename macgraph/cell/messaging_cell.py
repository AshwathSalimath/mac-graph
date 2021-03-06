
from typing import NamedTuple
import tensorflow as tf

from ..args import ACTIVATION_FNS
from ..attention import *
from ..input import get_table_with_embedding
from ..const import EPSILON
from ..util import *
from ..layers import *

MP_State = tf.Tensor

class MP_Node(NamedTuple):
	id: str
	properties: tf.Tensor
	state: MP_State

use_message_passing_fn = False
use_self_reference = False

def layer_normalize(tensor):
	'''Apologies if I've abused this term'''

	in_shape = tf.shape(tensor)
	axes = list(range(1, len(tensor.shape)))

	# Keep batch axis
	t = tf.reduce_sum(tensor, axis=axes )
	t += EPSILON
	t = tf.reciprocal(t)
	t = tf.check_numerics(t, "1/sum")

	tensor = tf.einsum('brc,b->brc', tensor, t)

	tensor = dynamic_assert_shape(tensor, in_shape, "layer_normalize_tensor")
	return tensor


def messaging_cell(args, features, vocab_embedding, 
	in_node_state, in_control_state, in_question_state, in_memory_state, in_iter_id):

	'''
	Operate a message passing cell
	Each iteration it'll do one round of message passing

	Returns: read_signal, node_state

	for to_node in nodes:
		to_node.state = combine_incoming_signals([
			message_pass(from_node, to_node) for from_node in nodes
		] + [node_self_update(to_node)])  
			

	'''

	node_table, node_table_width, node_table_len = get_table_with_embedding(args, features, vocab_embedding, "kb_node")

	in_signal = tf.concat([in_control_state, in_iter_id], -1)

	# Read/Write queries
	in_write_query  = tf.layers.dense(in_signal, node_table_width)
	in_write_signal = layer_selu(in_signal, args["mp_state_width"])
	in_read_query   = tf.layers.dense(in_signal, node_table_width)
	
	return do_messaging_cell(args, features, vocab_embedding, 
		in_node_state,
		node_table, node_table_width, node_table_len,
		in_write_query, in_write_signal, [in_read_query],
		in_iter_id)


def mp_matmul(state, mat, name):
	return tf.nn.conv1d(state, mat, 1, 'VALID', name=name)

def do_messaging_cell(args, features, vocab_embedding, 
	in_node_state, 
	node_table, node_table_width, node_table_len,
	in_write_query, in_write_signal, in_read_queries,
	in_iter_id):

	with tf.name_scope("messaging_cell"):

		taps = {}
		taps["mp_write_query"] = in_write_query
		taps["mp_write_signal"] = in_write_signal

		node_state_shape = tf.shape(in_node_state)
		node_state = in_node_state
		

		# --------------------------------------------------------------------------
		# Write to graph
		# --------------------------------------------------------------------------
		
		write_signal, _, a_taps = attention_write_by_key(
			keys=node_table,
			key_width=node_table_width,
			keys_len=node_table_len,
			query=in_write_query,
			value=in_write_signal,
		)
		for k,v in a_taps.items():
			taps["mp_write_"+k] = v

		delta = tf.shape(node_state)[1] - tf.shape(write_signal)[1]
		write_signal = tf.pad(write_signal, [ [0,0], [0,delta], [0,0] ]) # zero pad out
		write_signal = dynamic_assert_shape(write_signal, tf.shape(node_state), "write_signal")

		node_state += write_signal
		assert node_state.shape[-1] == in_node_state.shape[-1], "Node state should not lose dimension"

		# --------------------------------------------------------------------------
		# Calculate adjacency 
		# --------------------------------------------------------------------------

		# Aggregate via adjacency matrix with normalisation (that does not include self-edges)
		adj = tf.cast(features["kb_adjacency"], tf.float32)
		degree = tf.reduce_sum(adj, -1, keepdims=True)
		inv_degree = tf.reciprocal(degree)
		node_mask = tf.expand_dims(tf.sequence_mask(features["kb_nodes_len"], args["kb_node_max_len"]), -1)
		inv_degree = tf.where(node_mask, inv_degree, tf.zeros(tf.shape(inv_degree)))
		inv_degree = tf.where(tf.greater(degree, 0), inv_degree, tf.zeros(tf.shape(inv_degree)))
		inv_degree = tf.check_numerics(inv_degree, "inv_degree")
		adj_norm = inv_degree * adj
		adj_norm = tf.cast(adj_norm, node_state.dtype)
		adj_norm = tf.check_numerics(adj_norm, "adj_norm")
		node_incoming = tf.einsum('bnw,bnm->bmw', node_state, adj_norm)


		# --------------------------------------------------------------------------
		# Perform propagation
		# --------------------------------------------------------------------------
		

		# Node value = gru(node_prev, node_incoming)

		old_and_new = tf.concat([node_state, node_incoming], axis=-1)

		forget_w     = tf.get_variable("mp_forget_w",    [1, args["mp_state_width"]*2, args["mp_state_width"]])
		reuse_w      = tf.get_variable("mp_reuse_w",     [1, args["mp_state_width"]*2, args["mp_state_width"]])
		transform_w  = tf.get_variable("mp_transform_w", [1, args["mp_state_width"]*2, args["mp_state_width"]])

		# Initially likely to be zero
		forget_signal = tf.nn.sigmoid(mp_matmul(old_and_new , forget_w, 'forget_signal'))
		reuse_signal  = tf.nn.sigmoid(mp_matmul(old_and_new , reuse_w,  'reuse_signal'))

		reuse_and_new = tf.concat([reuse_signal * node_state, node_incoming], axis=-1)
		proposed_new_state = tf.nn.selu(mp_matmul(reuse_and_new, transform_w, 'proposed_new_state'))

		node_state = (1-forget_signal) * node_state + (forget_signal) * proposed_new_state


		# node_state = agg
		# assert node_state.shape[-1] == in_node_state.shape[-1], "Node state should not lose dimension"

		# if args["use_message_passing_self_ref"]:
		# 	# Add self-reference
		# 	self_reference_kernel = tf.get_variable("mp_self_reference_W", [1, args["mp_state_width"], args["mp_state_width"]])
		# 	sr = tf.nn.conv1d(in_node_state, self_reference_kernel, 1, 'SAME', name="self_reference")
		# 	node_state += sr
		# 	taps["mp_self_fn"] = self_reference_kernel
		# else:
		# 	node_state += in_node_state



		# if args["use_message_passing_node_transform"]:
		# 	# Message passing function is a 1d conv [filter_width, in_channels, out_channels]
		# 	message_pass_kernel = tf.get_variable(
		# 		"mp_node_W", 
		# 		[1, args["mp_state_width"], args["mp_state_width"]],
		# 		initializer=tf.contrib.layers.variance_scaling_initializer(factor=1.0))

		# 	message_pass_bias = tf.get_variable("mp_node_b", [args["mp_state_width"]])

		# 	# Apply message pass function:
		# 	node_state = tf.nn.conv1d(node_state, message_pass_kernel, 1, 'SAME', name="message_pass")
		# 	node_state += message_pass_bias
		# 	# Apply activation
		# 	node_state = ACTIVATION_FNS[args["mp_activation"]](node_state)
		# 	assert node_state.shape[-1] == in_node_state.shape[-1], "Node state should not lose dimension"
		# 	taps["mp_pass_fn"] = message_pass_kernel


		assert node_state.shape[-1] == in_node_state.shape[-1], "Node state should not lose dimension"

		taps["mp_node_state"] = node_state

		# Output
		delta = tf.shape(node_state)[1] - tf.shape(node_table)[1]
		padded_node_table = tf.pad(node_table, [ [0,0], [0,delta], [0,0] ]) # zero pad out

		out_read_signals = []

		for idx, qry in enumerate(in_read_queries):
			out_read_signal, _, a_taps = attention_key_value(
				keys=padded_node_table,
				keys_len=node_table_len,
				key_width=node_table_width,
				query=qry,
				table=node_state,
				)
			out_read_signals.append(out_read_signal)

			for k,v in a_taps.items():
				taps[f"mp_read{idx}_{k}"] = v
			taps[f"mp_read{idx}_signal"] = out_read_signal

		node_state = dynamic_assert_shape(node_state, node_state_shape, "node_state")
		assert node_state.shape[-1] == in_node_state.shape[-1], "Node state should not lose dimension"

		return out_read_signals, node_state, taps


