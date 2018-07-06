
import numpy as np
import tensorflow as tf

import logging
logger = logging.getLogger(__name__)




def input_fn(args, mode, question=None):

	d = tf.data.TFRecordDataset([args[f"{mode}_input_path"]])

	# Parse
	d = d.map(lambda i: tf.parse_single_example(
		i,
		features={
			'src': 				tf.FixedLenFeature([], tf.string),
			'src_len': 			tf.FixedLenFeature([], tf.int64),
			'kb': 				tf.FixedLenFeature([], tf.string),
			'kb_width': 		tf.FixedLenFeature([], tf.int64),
			'label': 			tf.FixedLenFeature([], tf.int64)
		})
	)

	d = d.map(lambda i: ({
		"src": 				i["src"],
		"src_len": 			i["src_len"],
		"knowledge_base": 	np.reshape(i["kb"], [-1, i["kb_width"]]),
	}, i["label"]))


	if args["limit"] is not None:
		d = d.take(args["limit"])

	d = d.shuffle(args["batch_size"]*10)

	d = d.padded_batch(
		args["batch_size"],
		# The first three entries are the source and target line rows;
		# these have unknown-length vectors.	The last two entries are
		# the source and target row sizes; these are scalars.
		padded_shapes=(
			{
				"src": tf.TensorShape([None]),
				"src_len": tf.TensorShape([]), 
				"knowledge_base": tf.TensorShape([])
			},
			tf.TensorShape([]),	# label
		),
			
		# Pad the source and target sequences with eos tokens.
		# (Though notice we don't generally need to do this since
		# later on we will be masking out calculations past the true sequence.
		padding_values=(
			{
				"src": EOS_ID, 
				"src_len": 0,		 # unused
				"knowledge_base": 0, # unused
			},
			0 # label (unused)
		)
	)
	
	return d



def gen_input_fn(args, mode):
	return lambda: input_fn(args, mode)

	


