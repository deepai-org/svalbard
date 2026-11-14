#!/bin/bash
# stop the packing queue (own file so that pgrep does not match the caller)
for p in $(pgrep -x variants.sh; pgrep -f 'bash ./variants' ; pgrep -f 'python3 fit\.py'); do [ "$p" != "$$" ] && kill $p 2>/dev/null; done
