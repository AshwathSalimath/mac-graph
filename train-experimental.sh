#!/bin/sh

COMMIT=$(git --no-pager log --pretty=format:'%h' -n 1)

python -m macgraph.train \
	--log-level DEBUG \
	--model-dir output/model/sp/$COMMIT \
	--input-dir input_data/processed/sp_small_100k \
	--disable-kb-edge \
	--input-layers 3 \
	--answer-classes 103 \
	--vocab-size 103 \
	--memory-transform-layers 1 \
	--max-decode-iterations 8 \
	--output-activation tanh \
	--output-layers 1 \
	--read-activation tanh \
	--read-layers 1 \
	--memory-forget-activation tanh \
	--control-dropout 0.0 \
	--read-dropout 0.0 \
	--input-width 64 \
	$@