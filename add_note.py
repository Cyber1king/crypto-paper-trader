#!/usr/bin/env python3
import json

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'r') as f:
    registry = json.load(f)

note = "Yahoo Finance does not publish Sunday 22:00-23:00 UTC bars at the start of each forex week. The replay therefore starts each week at Monday 00:00 UTC. This is a provider limitation, not data loss."

count = 0
for inst in registry['instruments']:
    if inst.get('market_type') == 'forex_spot':
        print('Processing:', inst['instrument_id'])
        # Find dataset_path key
        for i, key in enumerate(inst.keys()):
            if key == 'dataset_path':
                # Insert dataset_note after dataset_path
                new_inst = dict(inst)
                new_dict = {}
                keys_list = list(new_inst.keys())
                for k in keys_list:
                    new_dict[k] = new_inst[k]
                    if k == 'dataset_path':
                        new_dict['dataset_note'] = note
                inst_idx = registry['instruments'].index(inst)
                registry['instruments'][inst_idx] = new_inst
                count += 1
                print('  Added dataset_note to', inst['instrument_id'])
                break
    else:
        print('Skipping:', inst.get('instrument_id'))

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\data\research_registry.json', 'w') as f:
    json.dump(registry, f, indent=2)
    f.write('\n')

print('Total forex instruments updated:', count)