
from ..args import get_args as get_args_parent

def get_args():
	def extras(parser):
		parser.add_argument('--skip-vocab', action='store_true')
		parser.add_argument('--gqa-path', type=str, default="./input_data/raw/gqa.yaml")

	return get_args_parent(extras)