#!/bin/sh

COMMIT=$(git --no-pager log --pretty=format:'%h' -n 1)

python -m macgraph.predict \
	--model-dir output/model/sa_sp/3325064 \
	--input-dir input_data/processed/sa_sp_small_100k \
	--disable-dynamic-decode \
	--disable-memory-cell \
	--disable-question-state \
	--read-from-question \
	--type-string-prefix StationAdj \
	$@