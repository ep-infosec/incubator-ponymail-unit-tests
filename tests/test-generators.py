#!/usr/bin/env python3
"""
This is the archiver ID generator test suite.
It tests live generated IDs against a set of predefined reference constants.
"""
import sys
import os
import mailbox
import yaml
import argparse
import collections
import interfacer
import time
import email.utils

parse_html = False
nonce = None
fake_args = collections.namedtuple('fakeargs', ['verbose', 'ibody'])(False, None)

# get raw message, allowing for mboxo translation
def _raw(args, mbox, key):
    if args.nomboxo: # No need to filter the data
        file=mbox.get_file(key, True)
        message_raw=file.read()
        file.close()
    else:
        from mboxo_patch import MboxoReader
        file=mbox.get_file(key, True)
        file=MboxoReader(file)
        message_raw=file.read()
        file.close()
    return message_raw

def generate_specs(args):
    if not args.nomboxo:
        # Temporary patch to fix Python email package limitation
        # It must be removed when the Python package is fixed
        from mboxo_patch import MboxoFactory
    import archiver
    if args.generators:
        generator_names = args.generators
    else:
        try:
            import generators
        except:
            import plugins.generators as generators
        generator_names = generators.generator_names() if hasattr(generators, 'generator_names') else ['full', 'medium', 'cluster', 'legacy']
    yml = {}
    # sort so most recent generators come last to make comparisons easier
    for gen_type in sorted(generator_names, key=lambda s: s.replace('dkim','zkim')):
        test_args = collections.namedtuple('testargs', ['parse_html', 'generator'])(parse_html, gen_type)
        archie = interfacer.Archiver(archiver, test_args)
        sys.stderr.write("Generating specs for type '%s'...\n" % gen_type)

        gen_spec = []
        mbox = mailbox.mbox(args.mboxfile, None if args.nomboxo else MboxoFactory, create=False)
        for key in mbox.keys():
            message_raw = _raw(args, mbox, key)
            message = mbox.get(key)
            lid = args.lid or archiver.normalize_lid(message.get('list-id', '??'))
            json = archie.compute_updates(fake_args, lid, False, message, message_raw)
            mid = message.get('message-id','').strip()
            if json:
                gen_spec.append({
                    'index': key,
                    'message-id': mid,
                    'generated': json['mid'],
                })
            else:
                print("Cannot parse index %d: %s" % (key, mid))
        yml[gen_type] = gen_spec
    with open(args.generate, 'w') as f:
        # don't sort keys here
        yaml.dump({'args': {'cmd': " ".join(sys.argv)}, 'generators': {args.mboxfile: yml}}, f, sort_keys=False)
        f.close()


def run_tests(args):
    if not args.nomboxo:
        # Temporary patch to fix Python email package limitation
        # It must be removed when the Python package is fixed
        from mboxo_patch import MboxoFactory
    import archiver
    import logging
    verbose_logger = logging.getLogger()
    verbose_logger.setLevel(logging.WARN)
    verbose_logger.addHandler(logging.StreamHandler(sys.stderr))
    archiver.logger = verbose_logger

    try:
        import generators
    except:
        import plugins.generators as generators
    errors = 0
    skipped = 0
    tests_run = 0
    yml = yaml.safe_load(open(args.load, 'r'))
    _env = {}
    if 'args' in yml and 'env' in yml['args']:
        _env = yml['args']['env']
    generator_names = generators.generator_names() if hasattr(generators, 'generator_names') else ['full', 'medium', 'cluster', 'legacy']
    if args.generators:
        generator_names = args.generators
    mboxfiles = []
    for file, run in yml['generators'].items():
        mboxfiles.append(file)
        if not run: # No tests under this filename, run same tests as next
            continue
        for gen_type, tests in run.items():
            if gen_type not in generator_names:
                sys.stderr.write("Warning: generators.py does not have the '%s' generator, skipping tests\n" % gen_type)
                continue
            test_args = collections.namedtuple('testargs', ['parse_html', 'generator'])(parse_html, gen_type)
            archie = interfacer.Archiver(archiver, test_args)
            for mboxfile in mboxfiles:
                sys.stderr.write("Starting to process %s using %s\n" % (mboxfile,gen_type))
                mbox = mailbox.mbox(mboxfile, None if args.nomboxo else MboxoFactory, create=False)
                no_messages = len(mbox.keys())
                no_tests = len(tests)
                if no_messages != no_tests:
                    sys.stderr.write("Warning: %s run for %s contains %u tests, but mbox file has %u emails!\n" %
                                    (gen_type, mboxfile, no_tests, no_messages))
                for test in tests:
                    tests_run += 1
                    key = test['index']
                    message_raw = _raw(args, mbox, key)
                    message = mbox.get(key)
                    # Mock archived-at for slightly broken medium generators
                    if 'MOCK_AAT' in _env and gen_type == 'medium':
                        mock_aat = email.utils.formatdate(int(_env['MOCK_AAT']), False)
                        try:
                            message.replace_header('archived-at', mock_aat)
                        except:
                            message['archived-at'] = mock_aat
                    msgid =(message.get('message-id') or '').strip()
                    dateheader = message.get('date')
                    if args.skipnodate and not dateheader:
                        print("""[SKIP] %s, index %2u: No date header found and --skipnodate specified, skipping this test!""" %
                                         (gen_type, key, ))
                        skipped += 1
                        continue
                    if msgid != test['message-id']:
                        sys.stderr.write("""[SEQ?] %s, index %2u: Expected '%s', got '%s'!\n""" %
                                        (gen_type, key, test['message-id'], msgid))
                        continue # no point continuing
                    lid = args.lid or archiver.normalize_lid(message.get('list-id', '??'))
                    json = archie.compute_updates(fake_args, lid, False, message, message_raw)

                    # get override for version (if any)
                    expected = test.get(archie.version, test['generated'])
                    actual = json['mid']
                    if actual != expected:
                        errors += 1
                        sys.stderr.write("""[FAIL] %s, index %2u: Expected '%s', got '%s'!\n""" %
                                        (gen_type, key, expected, actual))
                        if args.dropin and gen_type == args.dropin:
                            if expected != actual:
                                test['generated'] = actual
                            else:
                                test['alternate'] = actual
                    else:
                        print("[PASS] %s index %u" % (gen_type, key))
        mboxfiles = [] # reset for the next set of tests
    if args.dropin and errors:
        sys.stderr.write("Writing replacement yaml as --dropin was specified\n")
        yaml.safe_dump(yml, open(args.load, "w"), sort_keys=False)
    # N.B. The following line is parsed by runall.py
    print("[DONE] %u tests run, %u failed. Skipped %u." % (tests_run, errors, skipped))
    if errors:
        sys.exit(-1)


def main():
    parser = argparse.ArgumentParser(description='Command line options.')
    parser.add_argument('--generate', dest='generate', type=str,
                        help='Generate a test yaml spec, output to file specified here')
    parser.add_argument('--generators', dest='generators', nargs='+', type=str,
                        help='Override the list of generator names')
    parser.add_argument('--load', dest='load', type=str,
                        help='Load and run tests from a yaml spec file')
    parser.add_argument('--mbox', dest='mboxfile', type=str,
                        help='If generating spec, which mbox corpus file to use for testing')
    parser.add_argument('--listid', dest='lid', type=str,
                        help='List-ID header override if needed')
    parser.add_argument('--rootdir', dest='rootdir', type=str, required=True,
                        help="Root directory of Apache Pony Mail")
    parser.add_argument('--nomboxo', dest = 'nomboxo', action='store_true',
                        help = 'Skip Mboxo processing')
    parser.add_argument('--dropin', dest = 'dropin', type=str,
                        help = 'Perform drop-in replacement of unit test results for the specified generator type [devs only!]')
    parser.add_argument('--skipnodate', dest = 'skipnodate', action='store_true',
                        help = 'Skip emails with no Date: header (useful for medium generator tests)')
    args = parser.parse_args()

    if args.rootdir:
        tools_dir = os.path.join(args.rootdir, 'tools')
    else:
        tools_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', "tools")
    sys.path.append(tools_dir)

    if os.environ.get('MOCK_GMTIME'):
        import time
        import traceback
        save_gmtime = time.gmtime
        def _time_gmtime(secs=None):
            if secs is None:
                callers = traceback.extract_stack(limit=2) # want last-1 and last (i.e. here)
                [filename, _, _, _] = callers[0] # This is last-1, i.e. my caller
                if filename.endswith("/tools/archiver.py") or filename.endswith("tools/generators.py"):
                    return save_gmtime(0)
            return save_gmtime(secs)

        time.gmtime = _time_gmtime
    
    if args.generate:
        if not args.mboxfile:
            sys.stderr.write("Generating a test spec requires an mbox filepath passed with --mbox!\n")
            sys.exit(-1)
        generate_specs(args)
    elif args.load:
        run_tests(args)


if __name__ == '__main__':
    main()
