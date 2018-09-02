
import yaml
import tensorflow as tf
import random
from tqdm import tqdm
from collections import Counter

import logging
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# TFRecord functions
# --------------------------------------------------------------------------

# Why it's so awkward to write a record I do not know

def int32_feature(value):
	return tf.train.Feature(int32_list=tf.train.Int32List(value=[value]))

def int64_feature(value):
	return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

def bytes_feature(value):
	return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

def string_feature(value):
	return conv_bytes_feature(value)

def conv_bytes_feature(value):
	return tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(value)]))


# --------------------------------------------------------------------------
# TF helpers
# --------------------------------------------------------------------------

def tf_startswith(tensor, prefix, axis=None):
	return tf.reduce_all(tf.equal(tensor[:len(prefix)], prefix), axis=axis)

# --------------------------------------------------------------------------
# File readers and writers
# --------------------------------------------------------------------------

def read_gqa(args):
	with tf.gfile.GFile(args["gqa_path"], 'r') as in_file:
		d = yaml.safe_load_all(in_file)

		ctr = 0

		for i in d:
			if i is not None:
				if args["type_string_prefix"] is None or i["question"]["type_string"].startswith(args["type_string_prefix"]):
					yield i
					ctr += 1
					if args["limit"] is not None and ctr >= args["limit"]:
						logger.debug("Hit limit, stop")
						return
				else:
					logger.debug(f"{i['question']['type_string']} does not match prefix {args['type_string_prefix']}")
			else:
				logger.debug("Skipping None yaml doc")

class Partitioner(object):

	def __init__(self, args):
		self.args = args
		self.written = 0
		self.answer_classes = Counter()
		self.answer_classes_types = Counter()



	def __enter__(self, *vargs):
		self.files = {
			i: tf.python_io.TFRecordWriter(self.args[f"{i}_input_path"]) 
			for i in self.args['modes']
		}

		return self


	def write(self, doc, record):
		r = random.random()

		if r < self.args["eval_holdback"]:
			mode = "eval"
		elif r < self.args["eval_holdback"] + self.args["predict_holdback"]:
			mode = "predict"
		else:
			mode = "train"

		key = str(doc["answer"]) + "/" + doc["question"]["type_string"]

		self.files[mode].write(record)
		self.answer_classes[str(doc["answer"])] += 1
		self.answer_classes_types[key] += 1
		self.written += 1


	def __exit__(self, *vargs):
		for i in self.files.values():
			i.close()

		self.files = None


# --------------------------------------------------------------------------
# Dataset helpers
# --------------------------------------------------------------------------

def StringDataset(s):

	def generator():
		yield s

	return tf.data.Dataset.from_generator(generator, tf.string, tf.TensorShape([]) )





			