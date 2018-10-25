#!/bin/bash

python -m macgraph.train --name spa-10k \
	--max-decode-iterations 1 \
	--disable-input-bilstm \
	--embed-width 128 \
	--disable-message-passing \
	--disable-control-cell \