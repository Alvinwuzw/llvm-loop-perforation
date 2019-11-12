import subprocess
import time, sys
import json
from collections import defaultdict
import copy
import os
import importlib

TIMEOUT = 5

def select_next_params():
	pass

def choseBest(errors_function, rslts):
	for rsltstr, R in results.items():
		pass

if __name__ == "__main__":
	# `tests/matrix_multiply` is the default target.
	target = sys.argv[1] if len(sys.argv) > 1 else 'tests/matrix_multiply';
	loop_info_path = os.path.join(target, 'loop-info.json')
	loop_rates_path = os.path.join(target, 'loop-rates.json')
	results_path = os.path.join(target, 'results.json')
	error_path = os.path.join(target, 'error')

	subprocess.call(['make', 'clean'])

	# collect loop info to JSON file
	make_process = subprocess.Popen(['make', 'loop-info', 'TARGET={}'.format(target)])
	make_process.wait()


	# get errors function
	# errors_function = function()

	infojson = json.load(open(loop_info_path, 'r'))
	#infojson = json.load(open('tests/{}-phis.ll.json', 'r'))

	# set rate parameters to 1.
	rate_parameters = { m : { f: {l : 1 for l in ld } for f,ld in fd.items()} for m,fd in infojson.items() };
	# rate_parameters = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 1))

	# create results dictionary: {loop rate dict, jsonified} => statistic => value.
	results = {}

	# make the standard version
	make_process = subprocess.call(['make', 'standard', 'TARGET={}'.format(target)])

	# run the standard version
	run_process = subprocess.Popen(['make', 'standard-run', 'TARGET={}'.format(target)])
	run_process.wait(timeout=TIMEOUT)

	if run_process.returncode:
		print("Standard run must succeed, failed with return code: {}".format(run_process.returncode))
		exit(1)


	# sequentially take each loop and perforate at rate 2 (all others at rate 1)
	for modulename, functdict in infojson.items():
		for funcname, loopdict in functdict.items():
			if funcname == 'main': continue
			for loopname in loopdict:
				rate_parameters[modulename][funcname][loopname] = 2;

				with open(loop_rates_path, 'w') as file:
					json.dump(rate_parameters, file, indent=4);

				# Let's create the dictionary where we collect statistics...
				R = {}

				# now run all the other stuff.
				make_process = subprocess.Popen(['make', 'perforated', 'TARGET={}'.format(target)])
				make_process.wait()
				# time the execution of the perforated program in the lli interpreter

				try:
					start = time.time()
					interp_process = subprocess.Popen(['make', 'perforated-run', 'TARGET={}'.format(target)])
					interp_process.wait(timeout=TIMEOUT)
					end = time.time()
					# get the return code for criticality testing
					R['return_code'] = interp_process.returncode
					R['time'] = end - start

					# import the error module
					sys.path.append(target)
					mod = importlib.import_module("error")
					standard = '{}/standard.txt'.format(target)
					perforated ='{}/perforated.txt'.format(target)
					errors = mod.error(standard, perforated)

					print("error: ", errors)
					R['errors'] = errors

				except subprocess.TimeoutExpired:
					R['time'] = float('inf')
					R['return_code'] = float('nan')
					R['error'] = 1

				# put all statistics in the right place:
				results[json.dumps(rate_parameters)] = R

				# reset the current loop to 1.
				rate_parameters[modulename][funcname][loopname] = 1;

				# print('Return code: {}'.format(return_code))
				# print('Time for perforated loop: {}'.format(end - start))

	print("All Results collected")
	print(json.dumps(dict(results), indent=4));
	with open(results_path, 'w') as file:
		json.dump(dict(results), file, indent=4);
