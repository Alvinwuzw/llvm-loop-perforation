import subprocess
import time, sys
import json
from collections import defaultdict
import copy
import os
import importlib
import argparse
import re

### helpers
import pdb
import itertools

def flatten(d, prefix="", target={}, sep=";"):
	for k,v in d.items():
		if isinstance(v, dict):
			flatten(v, prefix + sep, target)
		else:
			target[prefix + k] = v
	return target

# # assume that same structure for d1, d2. Save in d1
# def joint_rec_iter(d1, d2, f):
# 	for k, v1 in d1.items():
# 		v2 = d2[k]
# 		if isinstance(v1, dict) and isinstance(v2, dict):
# 			joint_rec_iter(v1, v2, f)
# 		else:
# 			d1[k] = f(v1, v2)

# # returns an optimum parameter setting, out of
# def sample_optimize(parameter_keys, parameter_values, executable, scorer):
# 	pass
# 	#soon...

def join_optimize(parameters, cmd_args, store_in = {}):
	for modulename, functdict in infojson.items():
		for funcname, loopdict in functdict.items():
			rates = [p for p in itertools.product(RATES, repeat=len(loopdict))]
			for rate in rates:
				i = 0
				for loopname in loopdict:
					rate_params[modulename][funcname][loopname] = rate[i]
					i = i + 1
				store_in[json.dumps(rate_params)] = test_perforation(rate_params, cmd_args.N_trials)
			# reset
			for loopname in loopdict:
				rate_params[modulename][funcname][loopname] = 1
	
	# join_optimal()
	optimum_key, optimum_val = None, None

	for key, values in store_in.items():
		avg_value = None
		skip = False

		# calculate average performance and accuracy metrics
		for value in values:
			# skip ones with memory crashes/seg fault/infinite loop/etc
			if value['return_code'] != 0:
				skip = True
				break
			if avg_value is None:
				avg_value = value
			else:
				avg_value["time"] += value["time"]
				for error_key in value["errors"]:
					avg_value["errors"][error_key] += value["errors"][error_key]
		
		if skip:
			continue

		avg_value["time"] /= cmd_args.N_trials
		for error_key in avg_value["errors"]:
			avg_value["errors"][error_key] /= cmd_args.N_trials
		
		# skip ones with bad performance
		skip = True
		for _, error in avg_value["errors"].items():
			if error < cmd_args.max_error:
				skip = False
				break
		
		if skip:
			continue

		if key[0] == '!':
			key = key[key.index('_')+1:]
		
		if optimum_key is None or optimum_val["time"] > avg_value["time"]:
			optimum_key = key
			optimum_val = avg_value
	
	joined = json.loads(optimum_key)
	print("JOINED", joined)

	# dump final
	RSLT = test_perforation(joined, cmd_args.N_trials)

	# FIX: dont need to re-run the optimal one
	if(any(R['return_code'] for R in RSLT) != 0):
		raise RuntimeError("The Joined result produces an error")

	results['!joined_' + json.dumps(joined)] = RSLT
	print("THE JOINED RESULT perfs @ ["+",".join(map(str, flatten(joined).values()))+"]", json.dumps(RSLT, indent=4))

	return RSLT, results


if __name__ == "__main__":
	## USAGE AND SUCH
	parser = argparse.ArgumentParser(description="Driver program to compile perforated loops, collect results, and choose a point on the frontier")
	# `tests/matrix_multiply` is the default target.
	parser.add_argument('target', nargs='?', default='tests/matrix_multiply')
	parser.add_argument('-t', '--timeout', default=5, type=int)
	parser.add_argument('-e', '--max-error', default=0.5, type=float, help="the tolerance below which we will throw out loops")
	parser.add_argument('--rates', nargs='+', type=int, required=False, default=[2,3,5,8,13,21])
	parser.add_argument('--error_filter', type=str, required=False, default='.*')
	parser.add_argument('--N-trials', type=int, required=False, default=10)


	args = parser.parse_args()

	print(args)

	target = args.target
	TIMEOUT = args.timeout
	RATES = args.rates

	loop_info_path = os.path.join(target, 'loop-info.json')
	loop_rates_path = os.path.join(target, 'loop-rates.json')
	results_path = os.path.join(target, 'results.json')
	error_path = os.path.join(target, 'error')

	####################### NOW WE BEGIN ########################
	subprocess.call(['make', 'clean'])

	# # make, run the standard version, for output reasons

	subprocess.call(['make', 'standard', 'TARGET={}'.format(target)])
	intact_proc = subprocess.Popen(['make', 'standard-run', 'TARGET={}'.format(target)])
	intact_proc.wait()

	if intact_proc.returncode:
		raise RuntimeError("Standard run must succeed, failed with return code: {}".format(intact_proc.returncode))

	# collect loop info to JSON file
	make_process = subprocess.Popen(['make', 'loop-info', 'TARGET={}'.format(target)])
	make_process.wait()

	infojson = json.load(open(loop_info_path, 'r'))

	# import the error module
	sys.path.append(target)
	mod = importlib.import_module("error")
	exp = re.compile(args.error_filter)
	filtered_error_names = set(n for n in mod.error_names if exp.fullmatch(n))

	def test_perforation(rate_parameters, N_trials) :
		with open(loop_rates_path, 'w') as file:
			json.dump(rate_parameters, file, indent=4)


		# now run all the other stuff.
		make_process = subprocess.Popen(['make', 'perforated', 'TARGET={}'.format(target)])
		make_process.wait()
		# time the execution of the perforated program in the lli interpreter

		rslt_array = [ None ] * N_trials
		for t in range(N_trials):
			R = {}	# create the dictionary where we collect statistics
			try:
				start = time.time()
				interp_process = subprocess.Popen(['make', 'perforated-run', 'TARGET={}'.format(target)])
				interp_process.wait(timeout=TIMEOUT)
				end = time.time()
				# get the return code for criticality testing
				R['return_code'] = interp_process.returncode
				R['time'] = end - start
				if interp_process.returncode != 0:
					raise ValueError

				standard = '{}/standard.txt'.format(target)
				perforated ='{}/perforated.txt'.format(target)
				errors = {n: e for n, e in mod.error(standard, perforated).items() if n in filtered_error_names}

				print("time: ", R['time'])
				R['errors'] = errors

			except subprocess.TimeoutExpired:
				R['time'] = float('inf')
				R['return_code'] = float('nan')
				R['errors'] = {error_name: 1.0
				  for error_name in filtered_error_names}

			except ValueError:
				# set all errors to the max value if the program
				# has a non-zero return code
				R['errors'] = {error_name: 1.0
				  for error_name in filtered_error_names}

			rslt_array[t] = R

		return rslt_array

	# def good_enough( R_list ):
	# 	return all(R['return_code'] == 0 and any(e < args.max_error for n,e in R['errors'].items())
	# 		for R in R_list)


	# initialize rate parameters to 1.
	rate_params = { m : { f: {l : 1 for l in ld } for f,ld in fd.items()} for m,fd in infojson.items() }
	results = {}	# results dictionary: {loop rate dict, jsonified} => statistic => value.

	# no perforation. Choose one place to save it!
	# results["STANDARD"] = test_perforation(rate_params)
	results['!original_' + json.dumps(rate_params)] =  test_perforation(rate_params, args.N_trials)


	parameters = flatten(rate_params, sep="|>>|")
	print("DEBUG")
	RSLT, _ = join_optimize( parameters, args, store_in=results)

	# we now have a collection of {result => indent}.
	# In this case, it's a bunch of loops. Merge them together.


	print("All Results collected")
	print(json.dumps(dict(results), indent=4))
	with open(results_path, 'w') as file:
		json.dump(dict(results), file, indent=4)
