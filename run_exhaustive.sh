#!/bin/sh

# -n=10 -e=0.5
python3 driver.py tests/sum-to-n/
python3 driver.py tests/matrix_multiply/
python3 driver.py tests/alloc-loop/
python3 driver.py benchmarks/img-blur/
python3 driver.py benchmarks/sobel/
python3 driver.py benchmarks/blackscholes/

# for demo
# python3 driver.py benchmarks/img-blur/ -e=0.5 -n=1
# python3 plots.py frontier --target benchmarks/img-blur --acc-measure l2_100000

python3 plots.py speedups