#!/usr/bin/env python3
"""
Sort yaml files so they can be compared easily.
"""

import sys
import yaml

yml = yaml.safe_load(open(sys.argv[1], 'r'))

# update the dict in place
for key1 in yml.keys():
    if key1 == 'parsing':
        yml[key1].pop('medium_original')
        for key2 in yml[key1]:
            for entry in yml[key1][key2]:
                # fix up the order by dropping and re-adding
                for n in ['index', 'message-id', 'body_sha3_256', 'attachments']:
                    entry[n] = entry.pop(n)
    elif key1 == 'generators':
        for key2 in yml[key1]:
            yml[key1][key2].pop('medium_original')
            for key3 in yml[key1][key2]:
                for entry in yml[key1][key2][key3]:
                    # fix up the order by dropping and re-adding
                    for n in ['index', 'message-id', 'generated']:
                        entry[n] = entry.pop(n)

yaml.dump(yml,sys.stdout, sort_keys=False)