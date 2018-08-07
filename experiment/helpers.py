
import traceback
import argparse
import os.path
import os

import tensorflow as tf
import numpy as np

import logging
logger = logging.getLogger(__name__)

from .args import get_args
from macgraph.model import model_fn
from macgraph.input import *

from pbt import *

def gen_param_spec(args):
    return ParamSpec({
        "heritage": Heritage,
        "model_id": ModelId,
        "vocab_size":  IntParamOf(128, 4, 2048),
		"embed_width": IntParamOf(64, 4, 2048),
		"learning_rate": LRParam,
    })

def dummy(args):
    args = vars(args)
    args["modes"] = ["eval", "train", "predict"]

    for i in [*args["modes"], "all"]:
    	args[i+"_input_path"] = os.path.join(args["input_dir"], i+"_input.tfrecords")

    args["vocab_path"] = os.path.join(args["input_dir"], "vocab.txt")
    args["types_path"] = os.path.join(args["input_dir"], "types.yaml")

    return args


def gen_worker_init_params(args):
	args = dummy(args)
	p = {
		"model_fn": model_fn,
		"train_input_fn": lambda args2: gen_input_fn(args2, "train"),
		"eval_input_fn":  lambda args2: gen_input_fn(args2, "eval"),
		"run_config": tf.estimator.RunConfig(save_checkpoints_steps=99999999999, save_checkpoints_secs=None)
	}

	args.update(p)

	return args

def get_drone(args):
    return Drone(args, EstimatorWorker, gen_worker_init_params(args))


def score(worker):
	try:
		return worker.results["loss"]
	except Exception:
		return None

def name_fn(worker):
	return worker.params["heritage"].value + "_" + str(worker.id)[-5:-1]


def get_supervisor(args):
    return Supervisor(args, gen_param_spec(args), score, name_fn, True)
