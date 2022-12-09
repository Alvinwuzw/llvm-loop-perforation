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

# global variables
# mod = importlib.import_module("error")


def flatten(dic, prefix="", target={}, sep=";"):
	'''Flatten a json object to a string.'''

	for k,v in dic.items():
		if isinstance(v, dict):
			flatten(v, prefix + sep, target)
		else:
			target[prefix + k] = v
	return target


def average_time_error(result, num_trials):
	'''
	Calculate average time and errors for result (value in results.json);
	returns none if any return code is not 0.
	'''

	time_avg = None
	errors_avg = None
	for stats in result:
		if stats['return_code'] != 0:
			time_avg = None
			errors_avg = None
			break
		if time_avg is None:
			time_avg = stats["time"]
			errors_avg = stats["errors"]
		else:
			time_avg += stats["time"]
			for error_key in stats["errors"]:
				errors_avg[error_key] += stats["errors"][error_key]
	
	if time_avg is not None and errors_avg is not None:
		time_avg /= num_trials
		for error_key in errors_avg:
			errors_avg[error_key] /= num_trials

	return time_avg, errors_avg


def score(sp_avg, acc_avg, acc_bound):
	'''Return harmonic mean for greedy approach.'''

	if (abs(sp_avg - 1) < 0.0001 or abs(acc_avg - acc_bound) < 0.0001):
		return 0
	return 2 / (1 / (sp_avg - 1) + 1 / (1 - acc_avg / acc_bound))


def test_perforation(args, rate_params, filtered_error_names, mod):
	'''
	Run and record loop perforation according to given perforate rate. 
	'''

	# args
	loop_rates_path = os.path.join(args.target, 'loop-rates.json')
	with open(loop_rates_path, 'w') as file:
		json.dump(rate_params, file, indent=4)

	# now run all the other stuff.
	make_process = subprocess.Popen(['make', 'perforated', 'TARGET={}'.format(args.target)])
	make_process.wait()
	# time the execution of the perforated program in the lli interpreter

	result_array = [ None ] * args.N_trials
	for t in range(args.N_trials):
		stats = {}	# create the dictionary where we collect statistics
		try:
			start = time.time()
			interp_process = subprocess.Popen(['make', 'perforated-run', 'TARGET={}'.format(args.target)])
			interp_process.wait(timeout=args.timeout)
			end = time.time()
			# get the return code for criticality testing
			stats['return_code'] = interp_process.returncode
			stats['time'] = end - start
			if interp_process.returncode != 0:
				raise ValueError

			standard = '{}/standard.txt'.format(args.target)
			perforated ='{}/perforated.txt'.format(args.target)
			errors = {n: e for n, e in mod.error(standard, perforated).items() if n in filtered_error_names}

			print("time: ", stats['time'])
			stats['errors'] = errors

		except subprocess.TimeoutExpired:
			stats['time'] = float('inf')
			stats['return_code'] = float('nan')
			stats['errors'] = {error_name: 1.0
				for error_name in filtered_error_names}

		except ValueError:
			# set all errors to the max value if the program
			# has a non-zero return code
			stats['errors'] = {error_name: 1.0
				for error_name in filtered_error_names}

		result_array[t] = stats

	return result_array


def join_optimize(args):
	'''
	Test loop perforation for each combination of rates and find a optimal one. 
	'''

	# load loop info
	loop_info_path = os.path.join(args.target, 'loop-info.json')
	info_json = json.load(open(loop_info_path, 'r'))

	# import the error module
	sys.path.append(args.target)
	mod = importlib.import_module("error")
	exp = re.compile(args.error_filter)
	filtered_error_names = set(n for n in mod.error_names if exp.fullmatch(n))

	# initialize rate parameters to 1.
	rate_params = { m : { f: {l : 1 for l in ld } for f,ld in fd.items()} for m,fd in info_json.items() }
	results = {}	# results dictionary: {loop rate dict, jsonified} => statistic => value.

	# no perforation (rates are all 1).
	result_no_perf = test_perforation(args, rate_params, filtered_error_names, mod)
	results['!original_' + json.dumps(rate_params)] = result_no_perf
	
	# calculate average stats for no perforation
	no_perf_time_avg, no_perf_errors_avg = average_time_error(result_no_perf, args.N_trials)
	# there should be no errors when no loop perforation
	assert(no_perf_time_avg is not None and no_perf_errors_avg is not None)
	
	# exhaustive approach and greedy approach
	if (args.mode == 'exhaustive'):
		# try all combinations of perforation rates per function
		for module_name, func_dict in info_json.items():
			for func_name, loop_dict in func_dict.items():
				rates_perm = [p for p in itertools.product([1] + args.rates, repeat=len(loop_dict))]
				for rate in rates_perm:
					if (all(rt == 1 for rt in rate)):
						continue
					i = 0
					for loop_name in loop_dict:
						rate_params[module_name][func_name][loop_name] = rate[i]
						i = i + 1
					results[json.dumps(rate_params)] = test_perforation(args, rate_params, filtered_error_names, mod)
				# reset
				for loop_name in loop_dict:
					rate_params[module_name][func_name][loop_name] = 1
		
		# find a joined candidate based on time
		optimum_key, optimum_val = None, None

		for key, values in results.items():
			# should skip original loop (no perforation)
			if key[0] == '!':
				continue
			
			# calculate average performance and accuracy metrics
			value_avg = None
			skip = False
			for value in values:
				# skip ones with memory crashes/seg fault/infinite loop/etc
				if value['return_code'] != 0:
					skip = True
					break
				if value_avg is None:
					value_avg = value
				else:
					value_avg["time"] += value["time"]
					for error_key in value["errors"]:
						value_avg["errors"][error_key] += value["errors"][error_key]
			
			if skip:
				continue

			value_avg["time"] /= args.N_trials
			for error_key in value_avg["errors"]:
				value_avg["errors"][error_key] /= args.N_trials
			
			# skip ones with bad performance on all inputs
			if (min(value_avg["errors"].values()) >= args.max_error):
				continue
			
			if optimum_key is None or optimum_val["time"] > value_avg["time"]:
				optimum_key = key
				optimum_val = value_avg
	else:
		# for each loop, find the rate which passes criticality testing and has the highest score
		best_params_per_loop = []
		for module_name, func_dict in info_json.items():
			for func_name, loop_dict in func_dict.items():
				for loop_name in loop_dict:
					best_score = 0
					best_rate = 1

					for rate in args.rates:
						rate_params[module_name][func_name][loop_name] = rate
						result = test_perforation(args, rate_params, filtered_error_names, mod)
						results[json.dumps(rate_params)] = result
						time_avg, errors_avg = average_time_error(result, args.N_trials)

						# criticality testing
						if errors_avg is None or min(errors_avg.values()) >= args.max_error:
							continue
						
						# calculate score
						# there should be no absolute value but considering time imprecision for running toy programs
						sp_avg = no_perf_time_avg / time_avg
						# curr_score = score(sp_avg, min(errors_avg.values()), args.max_error) # take the minimum average accuracy
						curr_score = score(sp_avg, sum(errors_avg.values()) / len(errors_avg.values()), args.max_error) # take the average of average accuracy
						if curr_score > best_score:
							best_score = curr_score
							best_rate = rate

					rate_params[module_name][func_name][loop_name] = 1 # reset the current loop to 1.

					best_params = {}
					best_params['module_name'] = module_name
					best_params['func_name'] = func_name
					best_params['loop_name'] = loop_name
					best_params['score'] = best_score
					best_params['rate'] = best_rate
					best_params_per_loop.append(best_params)

		best_params_per_loop.sort(key=lambda p : p['score'], reverse=True) # sorted by score in decreasing order

		# try perforation rates with different combinations
		best_rate_params = { m : { f: {l : 1 for l in ld } for f,ld in fd.items()} for m,fd in info_json.items() }
		for p in best_params_per_loop:
			best_rate_params[p['module_name']][p['func_name']][p['loop_name']] = p['rate']
			result = test_perforation(args, best_rate_params, filtered_error_names, mod)
			results[json.dumps(best_rate_params)] = result
			time_avg, errors_avg = average_time_error(result, args.N_trials)
			# criticality testing
			if errors_avg is None or min(errors_avg.values()) >= args.max_error:
				best_rate_params[p['module_name']][p['func_name']][p['loop_name']] = 1

	if (args.mode == 'exhaustive'):
		if optimum_key is None:
			# any loop perforation fails
			joined = { m : { f: {l : 1 for l in ld } for f,ld in fd.items()} for m,fd in info_json.items() }
		else:
			joined = json.loads(optimum_key)
	else:
		joined = best_rate_params
	print("JOINED", joined)

	# dump final
	optimal_result = test_perforation(args, joined, filtered_error_names, mod)
	if(any(R['return_code'] for R in optimal_result) != 0):
		raise RuntimeError("The Joined result produces an error")

	results['!joined_' + json.dumps(joined)] = optimal_result
	print("THE JOINED RESULT perfs @ ["+",".join(map(str, flatten(joined).values()))+"]", json.dumps(optimal_result, indent=4))

	return results


if __name__ == "__main__":
	## USAGE AND SUCH
	parser = argparse.ArgumentParser(description="Driver program to compile perforated loops, collect results, and choose a point on the frontier")
	# `tests/matrix_multiply` is the default target.
	parser.add_argument('target', nargs='?', default='tests/matrix_multiply')
	parser.add_argument('-t', '--timeout', default=5, type=int)
	parser.add_argument('-e', '--max-error', default=0.5, type=float, help="the tolerance below which we will throw out loops")
	parser.add_argument('-r', '--rates', nargs='+', type=int, required=False, default=[2,3,5,8,13,21])
	parser.add_argument('--error_filter', type=str, required=False, default='.*')
	parser.add_argument('-n', '--N-trials', type=int, required=False, default=10)
	parser.add_argument('-m', '--mode', default="exhaustive", type=str, help="[exhaustive] or [greedy]")
	args = parser.parse_args()
	
	assert(args.mode in ["exhaustive", "greedy"]) # correct name for each perforation space exploration algorithm
	assert(1 not in args.rates) # 1 should not be considered as a perforated rate
	assert(len(args.rates) == len(set(args.rates))) # all rates are distinct
	print(args)

	loop_info_path = os.path.join(args.target, 'loop-info.json')
	results_path = os.path.join(args.target, 'results.json')

	####################### NOW WE BEGIN ########################
	subprocess.call(['make', 'clean'])

	# make and run the standard version, for output reasons
	subprocess.call(['make', 'standard', 'TARGET={}'.format(args.target)])
	intact_proc = subprocess.Popen(['make', 'standard-run', 'TARGET={}'.format(args.target)])
	intact_proc.wait()

	if intact_proc.returncode:
		raise RuntimeError("Standard run must succeed, failed with return code: {}".format(intact_proc.returncode))

	# collect loop info to JSON file
	make_process = subprocess.Popen(['make', 'loop-info', 'TARGET={}'.format(args.target)])
	make_process.wait()

	# run loop perforation
	results = join_optimize(args)

	# we now have a collection of {result => indent}.
	# In this case, it's a bunch of loops. Merge them together.
	print("All Results collected")
	print(json.dumps(dict(results), indent=4))
	with open(results_path, 'w') as file:
		json.dump(dict(results), file, indent=4)
