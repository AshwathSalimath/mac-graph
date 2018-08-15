#!/bin/sh

COMMIT=$(git --no-pager log --pretty=format:'%h' -n 1)

python -m macgraph.train \
	--input-dir input_data/processed/sa_small_100k_balanced \
	--model-dir output/model/sa/$COMMIT \
	--disable-summary \
	--disable-dynamic-decode \
	--disable-memory-cell \
	--disable-question-state \
	--enable-read-question-state \
	--control-dropout 0.2 \
	--input-layers 3 \
	--input-width 64 \
	--learning-rate 0.001 \
	--max-decode-iterations 1 \
	--max-gradient-norm 4.0 \
	--output-activation mi \
	--output-classes 512 \
	--output-layers 1 \
	--read-activation abs \
	--read-dropout 0.2 \
	--read-from-question \
	--read-indicator-rows 1 \
	--read-layers 1 \
	--vocab-size 512 \
	$@