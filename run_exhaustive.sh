#!/bin/sh

# -n=10 -e=0.5
python3 driver.py tests/sum-to-n/
python3 driver.py tests/matrix_multiply/
python3 driver.py tests/alloc-loop/
python3 driver.py benchmarks/img-blur/
python3 driver.py benchmarks/sobel/

python3 plots.py speedups