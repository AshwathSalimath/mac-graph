
from typing import NamedTuple
import tensorflow as tf

from ..args import ACTIVATION_FNS
from ..attention import *
from ..input import get_table_with_embedding

MP_State = tf.Tensor

class MP_Node(NamedTuple):
	id: str
	properties: tf.Tensor
	state: MP_State


def messaging_cell(args, features, vocab_embedding, in_node_state, in_control_state):
	'''
	Operate a message passing cell
	Each iteration it'll do one round of message passing

	Returns: read_signal, node_state

	for to_node in nodes:
		to_node.state = combine_incoming_signals([
			message_pass(from_node, to_node) for from_node in nodes
		] + [node_self_update(to_node)])  
			

	'''

	node_state = in_node_state
	node_table, node_table_width, node_table_len = get_table_with_embedding(args, features, vocab_embedding, "kb_node")


	# Read/Write queries
	in_write_query  = tf.layers.dense(in_control_state, node_table_width)
	in_write_signal = tf.layers.dense(in_control_state, args["mp_state_width"])
	in_read_query   = tf.layers.dense(in_control_state, node_table_width)

	# Add write signal:
	write_signal, _, _ = attention_write_by_key(
		keys=node_table,
		key_width=node_table_width,
		keys_len=node_table_len,
		query=in_write_query,
		value=in_write_signal,
	)
	delta = tf.shape(node_state)[1] - tf.shape(write_signal)[1]
	write_signal = tf.pad(write_signal, [ [0,0], [0,delta], [0,0] ]) # zero pad out
	write_signal = dynamic_assert_shape(write_signal, tf.shape(node_state), "write_signal")

	node_state += write_signal

	# Message passing function is a 1d conv [filter_width, in_channels, out_channels]
	message_pass_kernel = tf.get_variable("message_pass_kernel", [1, args["mp_state_width"], args["mp_state_width"]])

	# Apply message pass function:
	node_state = tf.nn.conv1d(node_state, message_pass_kernel, 1, 'SAME', name="message_pass")

	# Aggregate via adjacency matrix with normalisation (that does not include self-edges)
	adj = tf.cast(features["kb_adjacency"], tf.float32)
	inv_diagonal_degree = tf.eye(features["kb_adjacency"].shape[-1]) * tf.reciprocal(tf.reduce_sum(adj, -1))
	adj_norm = inv_diagonal_degree @ adj
	agg = tf.einsum('bnw,bnm->bmw', node_state, adj_norm)

	# Add self-reference
	self_reference_kernel = tf.get_variable("message_pass_kernel", [1, args["mp_state_width"], args["mp_state_width"]])
	sr = tf.nn.conv1d(in_node_state, self_reference_kernel, 1, 'SAME', name="self_reference")
	sr *= args["mp_self_dampening"]
	node_state = agg + sr

	# Apply activation
	node_state = ACTIVATION_FNS[args["mp_activation"]](node_state)


	# Output
	delta = tf.shape(node_state)[1] - tf.shape(node_table)[1]
	padded_node_table = tf.pad(node_table, [ [0,0], [0,delta], [0,0] ]) # zero pad out

	out_read_signal, _, _ = attention_key_value(
		keys=padded_node_table,
		keys_len=node_table_len,
		key_width=node_table_width,
		query=in_read_query,
		table=node_state,
		)


	return out_read_signal, node_state


