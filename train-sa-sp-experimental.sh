#!/bin/sh

COMMIT=$(git --no-pager log --pretty=format:'%h' -n 1)

python -m macgraph.train \
	--model-dir output/model/sa_sp/exp/$COMMIT \
	--input-dir input_data/processed/sa_sp_small_100k \
	--disable-dynamic-decode \
	--disable-memory-cell \
	--control-heads 3 \
	$@