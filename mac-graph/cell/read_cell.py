
import tensorflow as tf

from ..util import *

from ..attention import *


def read_from_table(features, in_signal, table, width, use_mask=True, **kwargs):

	query = tf.layers.dense(in_signal, width, activation=tf.nn.tanh)

	if use_mask:
		mask  = tf.layers.dense(in_signal, width, activation=tf.nn.tanh)
	else:
		mask = None

	# --------------------------------------------------------------------------
	# Do lookup via attention
	# --------------------------------------------------------------------------

	output, taps = attention(table, query, mask, 
		word_size=width, 
		output_taps=True,
		 **kwargs)

	output = dynamic_assert_shape(output, [features["d_batch_size"], width])
	return output, taps


def read_from_table_with_embedding(args, features, vocab_embedding, in_signal, noun, use_mask=True, **kwargs):
	"""Perform attention based read from table

	Will transform table into vocab embedding space
	
	@returns read_data
	"""

	with tf.name_scope(f"read_from_{noun}"):

		# --------------------------------------------------------------------------
		# Constants and validations
		# --------------------------------------------------------------------------

		table = features[f"{noun}s"]

		width = args[f"{noun}_width"]
		full_width = width * args["embed_width"]

		d_len = tf.shape(table)[1]
		assert table.shape[-1] == width

		# --------------------------------------------------------------------------
		# Embed graph tokens
		# --------------------------------------------------------------------------
		
		emb_kb = tf.nn.embedding_lookup(vocab_embedding, table)
		emb_kb = dynamic_assert_shape(emb_kb, 
			[features["d_batch_size"], d_len, width, args["embed_width"]])

		emb_kb = tf.reshape(emb_kb, [-1, d_len, full_width])
		emb_kb = dynamic_assert_shape(emb_kb, 
			[features["d_batch_size"], d_len, full_width])

		# --------------------------------------------------------------------------
		# Read
		# --------------------------------------------------------------------------

		return read_from_table(features, in_signal, emb_kb, full_width, use_mask, **kwargs)



def read_cell(args, features, vocab_embedding, in_memory_state, in_control_state, in_data_stack):
	"""
	A read cell

	@returns read_data

	"""


	with tf.name_scope("read_cell"):

		# --------------------------------------------------------------------------
		# Read data
		# --------------------------------------------------------------------------

		in_signal = [in_memory_state]

		# We may run the network with no control cell
		if in_control_state is not None:
			in_signal.append(in_control_state)

		in_signal = tf.concat(in_signal, -1)

		reads = []
		taps = []

		for i in ["kb_node", "kb_edge"]:
			if args[f"use_{i}"]:
				for j in range(args["read_heads"]):
					read, tap = read_from_table_with_embedding(
						args, 
						features, 
						vocab_embedding, 
						in_signal, 
						noun=i,
						max_len=args[f"{i}_max_len"]
					)
					reads.append(read)
					taps.append(tap)

		if args["use_data_stack"]:
			# Attentional read
			read, tap = read_from_table(features, in_signal, in_data_stack, args["data_stack_width"])
			reads.append(read)
			# Head read
			reads.append(in_data_stack[:,0,:])

		read_data = tf.concat(reads, -1)
		out_taps = tf.concat(taps, axis=-1)

		# --------------------------------------------------------------------------
		# Shrink results
		# --------------------------------------------------------------------------

		read_data = tf.layers.dense(read_data, args["memory_width"], name="data_read_shrink", activation=tf.nn.tanh)
		read_data = dynamic_assert_shape(read_data, [features["d_batch_size"], args["memory_width"]])

		return read_data, out_taps




