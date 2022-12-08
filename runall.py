#!/usr/bin/env python3

import sys
import os
import subprocess
import argparse
import yaml
import time
import re

if __name__ == '__main__':
    PYTHON3 = sys.executable
    parser = argparse.ArgumentParser(description='Command line options.')
    parser.add_argument('--rootdir', dest='rootdir', type=str, required=True,
                        help="Root directory of Apache Pony Mail")
    parser.add_argument('--load', dest='load', type=str, nargs='+',
                        help="Load only specific yaml spec files instead of all test specs")
    parser.add_argument('--ttype', dest='ttype', type=str, nargs='+',
                        help="Run only specified test types (generators, parsing, etc)")
    parser.add_argument('--gtype', dest='gtype', type=str, nargs='+',
                        help="Run only specified generators (medium, cluster, dkim, full, etc)")
    parser.add_argument('--yamldir', dest='yamldir', type=str, action='store',
                        help="Load yaml specs from alternate directory")
    parser.add_argument('--dropin', dest='dropin', type=str, action='store',
                        help="If set to a specific generator name, replaces its unit test results with the current "
                             "output in the yaml tests")
    parser.add_argument('--nomboxo', dest = 'nomboxo', action='store_true',
                        help = 'Skip Mboxo processing')
    parser.add_argument('--fof', dest='failonfail', action='store_true',
                        help="Stop running more tests if an error is encountered")
    parser.add_argument('--skipnodate', dest='skipnodate', action='store_true',
                        help="Skip generator tests with no Date: header")
    args = parser.parse_args()

    yamldir = args.yamldir or "yaml"

    if args.load:
        spec_files = args.load
    else:
        spec_files = [os.path.join(yamldir, x) for x in os.listdir(yamldir) if x.endswith('.yaml')]

    tests_success = 0
    tests_failure = 0
    tests_total = 0
    sub_success = 0
    sub_failure = 0
    sub_skipped = 0
    now = time.time()

    failbreak = False
    for spec_file in spec_files:
        with open(spec_file, 'r') as f:
            yml = yaml.safe_load(f)
            env = os.environ # always pass parent environ
            for test_type in yml:
                if args.ttype and test_type not in args.ttype:
                    print("Skipping test type %s due to --ttype flag" % test_type)
                    continue
                if test_type == 'args':
                     # Environment variable override, e.g. MOCK_GMTIME
                    env_ = yml[test_type].get("env", None)
                    if env_:
                        for key, val in env_.items():
                            env[key] = val
                    continue
                tests_total += 1
                # Use stderr so appears in correct sequence in logs; flush seems to be necessary for GitHub actions
                print("Running '%s' tests from %s..." % (test_type, spec_file), file=sys.stderr, flush=True)
                try:
                    cliargs = [PYTHON3, 'tests/test-%s.py' % test_type, '--rootdir', args.rootdir, '--load', spec_file,]
                    if args.nomboxo:
                        cliargs.append('--nomboxo')
                    if args.gtype and test_type == 'generators':
                        cliargs.append('--generators')
                        cliargs.extend(args.gtype)
                    if args.dropin:
                        cliargs.extend(['--dropin', args.dropin])
                    if args.skipnodate and test_type == 'generators':
                        cliargs.append('--skipnodate')
                    rv = subprocess.check_output(cliargs, env=env)
                    tests_success += 1
                except subprocess.CalledProcessError as e:
                    rv = e.output
                    print("FAIL: %s test from %s failed with code %d" % (test_type, spec_file, e.returncode), file=sys.stderr, flush=True)
                    tests_failure += 1
                    if args.failonfail:
                        failbreak = True
                        break
                finally:
                    # Fetch successes and failures from this spec run, add to total
                    m = re.search(r"^\[DONE\] (\d+) tests run, (\d+) failed\.( Skipped (\d+)\.)?", rv.decode('ascii'), re.MULTILINE)
                    if m:
                        sub_success += int(m.group(1)) - int(m.group(2))
                        sub_failure += int(m.group(2))
                        if m.group(4) is not None:
                            sub_skipped += int(m.group(4))
        if failbreak:
            break

    # No need for stderr at end of run
    print("-------------------------------------")
    print("Done with %u specification%s in %.2f seconds" % (tests_total, 's' if tests_total != 1 else '', time.time() - now))
    print("Specs processed: %4u" % tests_total)
    print("Total tests run: %4u" % (sub_success+sub_failure))
    print("Tests succeeded: %4u" % sub_success)
    print("Tests failed:    %4u" % sub_failure)
    print("Tests skipped:   %4u" % sub_skipped)
    print("-------------------------------------")
    if tests_failure:
        sys.exit(-1)
