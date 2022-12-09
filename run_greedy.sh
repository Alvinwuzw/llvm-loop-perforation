#!/bin/sh

# -n=10 -e=0.5
python3 driver.py
python3 driver.py tests/sum-to-n/ -m=greedy
python3 driver.py tests/alloc-loop/ -m=greedy
python3 driver.py tests/matrix_multiply/ -m=greedy
python3 driver.py benchmarks/img-blur/ -m=greedy
python3 driver.py benchmarks/sobel/ -m=greedy

python3 plots.py speedups