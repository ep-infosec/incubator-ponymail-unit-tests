#!/usr/bin/env python3
"""
Simple tool for collating multiple mbox files into a single one, sorted by message ID.
If the message-ID is missing, use the Date or Subject and prefix the sort key to appear last.

Can optionally sort by ezmlm number.
This should be less likely to have missing numbers or duplicate entries.
However duplicates can occur in archive files if:
- the sequence number was reset at any point
- multiple mailing lists were merged
- messages were somehow duplicated before archival

Used for multi-import tests where you wish to check that multiple sources give the same ID

Emails with duplicate sort keys are logged and dropped
"""

import argparse
import mailbox
import re
import sys

parser = argparse.ArgumentParser(description='Command line options.')
parser.add_argument('--ezmlm', dest='ezmlm', action='store_true',
                    help="Use ezmlm numbering for sorting")
parser.add_argument('args', nargs=argparse.REMAINDER)
args = parser.parse_args()

outmbox = args.args[0]
msgfiles = args.args[1:] # multiple input files allowed

allmessages = {}
noid = 0
skipped = 0
crlf = None # assume that all emails have the same EOL
for msgfile in msgfiles:
    messages = mailbox.mbox(
        msgfile, None, create=False
    )
    sortkey = None
    for key in messages.iterkeys():
        message = messages.get(key)
        if args.ezmlm:
            from_ = message.get_from()
            m = re.search(r"return-(\d+)-", from_)
            if m:
                sortkey = m.group(1)
            else:
                print("Failed to find ezmlm id in %s" % from_)
                skipped += 1
                continue
        else:
            msgid = message.get('message-id')
            if msgid:
                sortkey = msgid.strip()
            else:
                print("No message id, sorting by date or subject: ", message.get_from())
                noid += 1
                altid = message.get('date') or message.get('subject')
                sortkey = "~" + altid.strip() # try to ensure it sorts last
        # store the data
        file = messages.get_file(key, True)
        message_raw = b''
        if crlf is None:
            message_raw = file.readline()
            crlf = (message_raw.endswith(b'\r\n'))
        message_raw += file.read()
        file.close()
        if sortkey in allmessages:
            print("Duplicate sort key: %s" % sortkey)
            skipped += 1
        allmessages[sortkey] = message_raw


nw = 0
with open(outmbox, "wb") as f:
    for key in sorted(allmessages.keys()):
        f.write(allmessages[key])
        if crlf:
            f.write(b'\r\n')
        else:
            f.write(b'\n')
        nw += 1

print("Wrote %u emails to %s with CRLF %s (%u without message-id) WARN: %u skipped" % (nw, outmbox, crlf, noid, skipped))
