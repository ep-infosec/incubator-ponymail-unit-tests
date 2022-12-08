#!/usr/bin/env python3
"""
This is the archiver parser test suite.
It tests live parsings against a set of predefined reference constants.
"""
import sys
import os
import mailbox
import yaml
import argparse
import collections
import hashlib
import interfacer

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
    cli_args = collections.namedtuple('testargs', ['parse_html'])(args.html)
    archie = interfacer.Archiver(archiver, cli_args)

    sys.stderr.write("Generating parsing specs for file '%s'...\n" % args.mboxfile)
    items = {}
    for mboxfile in args.mboxfile:
        tests = []
        mbox = mailbox.mbox(mboxfile, None if args.nomboxo else MboxoFactory, create=False)
        for key in mbox.keys():
            message_raw = _raw(args, mbox, key)
            message = mbox.get(key)
            lid = archiver.normalize_lid(message.get('list-id', '??'))
            json = archie.compute_updates(fake_args, lid, False, message, message_raw)
            body_sha3_256 = None
            if json and json.get('body') is not None:
                body_sha3_256 = hashlib.sha3_256(json['body'].encode('utf-8')).hexdigest()
            tests.append({
                'index': key,
                'message-id': message.get('message-id', '').strip(),
                'body_sha3_256': body_sha3_256,
                'attachments': json['attachments'] if json else [],
            })
        items[mboxfile] = tests
    with open(args.generate, 'w') as f:
        yaml.dump({'args': {'cmd': " ".join(sys.argv), 'parse_html': True if args.html else False}, 'parsing': items}, f, sort_keys=False)
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
    errors = 0
    tests_run = 0
    yml = yaml.safe_load(open(args.load, 'r'))
    parse_html = yml.get('args', {}).get('parse_html', False)

    test_args = collections.namedtuple('testargs', ['parse_html'])(parse_html)
    archie = interfacer.Archiver(archiver, test_args)
    _env = {}
    if 'args' in yml and 'env' in yml['args']:
        _env = yml['args']['env']

    mboxfiles = []

    for file, tests in yml['parsing'].items():
        mboxfiles.append(file)
        if not tests: # No tests under this filename, run same tests as next
            continue
        for mboxfile in mboxfiles:
            sys.stderr.write("Starting to process %s\n" % mboxfile)
            mbox = mailbox.mbox(mboxfile, None if args.nomboxo else MboxoFactory, create=False)
            no_messages = len(mbox.keys())
            no_tests = len(tests)
            if no_messages != no_tests:
                sys.stderr.write("Warning: %s run for parsing test of %s contains %u tests, but mbox file has %u emails!\n" %
                                ('TBA', mboxfile, no_tests, no_messages))
            for test in tests:
                tests_run += 1
                key = test['index']
                message_raw = _raw(args, mbox, key)
                message = mbox.get(key)
                msgid =(message.get('message-id') or '').strip()
                if msgid != test['message-id']:
                    sys.stderr.write("""[SEQ?] index %2u: Expected '%s', got '%s'!\n""" %
                                    (key, test['message-id'], msgid))
                    continue # no point continuing
                lid = archiver.normalize_lid(message.get('list-id', '??'))
                json = archie.compute_updates(fake_args, lid, False, message, message_raw)
                body_sha3_256 = None
                if json and json.get('body') is not None:
                    if not json.get('html_source_only'):
                        body_sha3_256 = hashlib.sha3_256(json['body'].encode('utf-8')).hexdigest()
                # get override for version (if any)
                expected = test.get(archie.version, test['body_sha3_256'])
                if body_sha3_256 != expected:
                    errors += 1
                    sys.stderr.write("""[FAIL] parsing index %2u: Expected: %s Got: %s\n""" %
                                    (key, expected, body_sha3_256))
                att = json['attachments'] if json else []
                att_expected = test['attachments'] or []
                if att != att_expected:
                    errors += 1
                    sys.stderr.write("""[FAIL] attachments index %2u: Expected: %s Got: %s\n""" %
                                    (key, att_expected, att))
                else:
                    print("[PASS] index %u" % (key))
        mboxfiles = []
    # N.B. The following line is parsed by runall.py
    print("[DONE] %u tests run, %u failed." % (tests_run, errors))
    if errors:
        sys.exit(-1)


def main():
    parser = argparse.ArgumentParser(description='Command line options.')
    parser.add_argument('--generate', dest='generate', type=str,
                        help='Generate a test yaml spec, output to file specified here')
    parser.add_argument('--load', dest='load', type=str,
                        help='Load and run tests from a yaml spec file')
    parser.add_argument('--mbox', dest='mboxfile', type=str, nargs='+',
                        help='If generating spec, which mbox corpus file to use for testing')
    parser.add_argument('--rootdir', dest='rootdir', type=str, required=True,
                        help="Root directory of Apache Pony Mail")
    parser.add_argument('--html', dest='html', action='store_true',
                        help="Enable HTML parsing if generating test specs")
    parser.add_argument('--nomboxo', dest = 'nomboxo', action='store_true',
                        help = 'Skip Mboxo processing')
    args = parser.parse_args()

    if args.rootdir:
        tools_dir = os.path.join(args.rootdir, 'tools')
    else:
        tools_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', "tools")
    sys.path.append(tools_dir)

    if args.generate:
        if not args.mboxfile:
            sys.stderr.write("Generating a test spec requires an mbox filepath passed with --mbox!\n")
            sys.exit(-1)
        generate_specs(args)
    elif args.load:
        run_tests(args)


if __name__ == '__main__':
    main()
