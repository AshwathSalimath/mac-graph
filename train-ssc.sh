#!/bin/sh

COMMIT=$(git --no-pager log --pretty=format:'%h' -n 1)

python -m macgraph.train \
	--model-dir output/model/ssc/1a/$COMMIT \
	--input-dir input_data/processed/ssc_small_1m \
	--max-decode-iterations 2 \
	--control-heads 2 \
	--disable-read-cell \
	$@