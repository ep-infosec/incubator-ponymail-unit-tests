#!/usr/bin/env python3

"""
This is a wrapper to standardise the API for different versions

Foal:
    def __init__(
        self, generator=None, parse_html=False, ignore_body=None, verbose=False
    ):

    def compute_updates(self, lid, private, msg, raw_msg):

Ponymail 12:
    def __init__(
        self, generator=None, parse_html=False, ignore_body=None, dump_dir=None, verbose=False, skipff=False
    ):

    def compute_updates(self, lid, private, msg):

0.11, 0.10:
    def __init__(self, parseHTML=False):

    def compute_updates(self, lid, private, msg):

"""

import sys
import inspect

class Archiver(object):
    def __init__(self, archiver_, args):
        self.expected_archie_parameters = inspect.signature(archiver_.Archiver).parameters
        self.expected_compute_parameters = inspect.signature(archiver_.Archiver.compute_updates).parameters

        # <= 0.11:
        if 'parseHTML' in self.expected_archie_parameters:
            if hasattr(args, 'generator'):
                archiver_.archiver_generator = args.generator
            self.archie = archiver_.Archiver(parseHTML=args.parse_html)
            params = inspect.signature(archiver_.Archiver.list_url).parameters
            if '_mlist' in params:
                self.version = 'v0.11'
            elif 'mlist' in params:
                self.version = 'v0.10'
            else:
                self.version = '?'
        # Ponymail 12+
        elif 'skipff' in self.expected_archie_parameters:
            self.archie = archiver_.Archiver(generator=getattr(args, 'generator', None),
                                             parse_html=args.parse_html,
                                             ignore_body=None,  # To be provided later
                                             skipff=True)
            self.version = 'v0.12'
        else: # Foal
            self.archie = archiver_.Archiver(generator=getattr(args, 'generator', None),
                                             parse_html=args.parse_html,
                                             ignore_body=None) # To be provided later
            self.version = 'foal'

        if 'raw_msg' in self.expected_compute_parameters:
            self.compute = self._compute_foal
        # PM 0.12 parameters
        elif 'args' in self.expected_compute_parameters:
            self.compute = self._compute_12
        # PM <= 0.11 parameters (missing args)
        else:
            self.compute = self._compute_11

    def _compute_foal(self, fake_args, lid, private, message, message_raw):
        return self.archie.compute_updates(lid, private, message, message_raw)[0]

    def _compute_12(self, fake_args, lid, private, message, message_raw):
        return self.archie.compute_updates(fake_args, lid, private, message)[0]

    def _compute_11(self, fake_args, lid, private, message, message_raw):
        return self.archie.compute_updates(lid, private, message)[0]

    def compute_updates(self, fake_args, lid, private, message, message_raw):
        return self.compute(fake_args, lid, private, message, message_raw)
