
import tensorflow as tf
import numpy as np

from .cell import MACCell
from .encoder import encode_input
from .util import assert_shape

def model_fn(features, labels, mode, params):

	# --------------------------------------------------------------------------
	# Setup input
	# --------------------------------------------------------------------------
	
	args = params
	dynamic_batch_size = tf.shape(features["src"])[0]

	# EstimatorSpec slots
	loss = None
	train_op = None
	eval_metric_ops = None
	predictions = None
	eval_hooks = None

	# --------------------------------------------------------------------------
	# Model for realz
	# --------------------------------------------------------------------------
	
	question_tokens, question_state = encode_input(args, features)

	with tf.variable_scope("decoder",reuse=tf.AUTO_REUSE) as decoder_scope:

		d_cell = MACCell(args, question_state, question_tokens, features["knowledge_base"])
		d_cell_initial = d_cell.zero_state(dtype=tf.float32, batch_size=dynamic_batch_size)

		# label_seq: [batch_size, seq_len]
		label_seq = tf.tile(tf.expand_dims(labels, 1), [0, args["max_decode_iterations"]])
		assert_shape(label_seq, [args["max_decode_iterations"]])

		# label_seq_len: [batch_size]
		label_seq_len = tf.tile([args["max_decode_iterations"]], tf.shape(labels))

		decoder_helper = tf.contrib.seq2seq.TrainingHelper(
			label_seq, 
			sequence_length=label_seq_len
		)

		guided_decoder = tf.contrib.seq2seq.BasicDecoder(
			d_cell,
			decoder_helper,
			d_cell_initial)

		# 'outputs' is a tensor of shape [batch_size, max_time, cell.output_size]
		decoded_outputs, decoded_state, decoded_sequence_lengths = tf.contrib.seq2seq.dynamic_decode(
			guided_decoder,
			swap_memory=True,
			maximum_iterations=args["max_decode_iterations"],
			scope=decoder_scope)

		
		# Take the final reasoning step output
		final_output = decoded_outputs.rnn_output[:,-1,:]
		assert_shape(final_output, [args["answer_classes"]])

		logits = final_output


	# --------------------------------------------------------------------------
	# Calc loss
	# --------------------------------------------------------------------------	

	if mode in [tf.estimator.ModeKeys.TRAIN, tf.estimator.ModeKeys.EVAL]:		
		crossent = tf.nn.sparse_softmax_cross_entropy_with_logits(
			labels=labels, logits=logits)

		loss = tf.reduce_sum(crossent) / tf.to_float(dynamic_batch_size)

	# --------------------------------------------------------------------------
	# Optimize
	# --------------------------------------------------------------------------

	if mode == tf.estimator.ModeKeys.TRAIN:
		global_step = tf.train.get_global_step()
		optimizer = tf.train.AdamOptimizer(args["learning_rate"])
		train_op = optimizer.minimize(loss)



	return tf.estimator.EstimatorSpec(mode,
		loss=loss,
		train_op=train_op,
		predictions=predictions,
		eval_metric_ops=eval_metric_ops,
		export_outputs=None,
		training_chief_hooks=None,
		training_hooks=None,
		scaffold=None,
		evaluation_hooks=eval_hooks,
		prediction_hooks=None
	)

