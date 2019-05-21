#!/usr/bin/env python
# coding: utf-8
import argparse
import os
import random
import sys

import numpy as np
import torch
import yaml

from solver import (AdvTrainer, ASRTrainer, LMTrainer, SAETrainer,
                    TAETrainer, ASRTester, CHARLMTrainer)

torch.backends.cudnn.deterministic = True

# Arguments
parser = argparse.ArgumentParser(description='Training E2E asr.')
parser.add_argument('--type', type=str, 
    help='asr | rnn_lm | tae | sae | adv | test | char_lm',
    default='asr')
parser.add_argument('--name', type=str, help='Name for logging.', 
    default='newtest')
parser.add_argument('--config', type=str, 
    default='./conf/test.yaml', 
    help='Path to experiment config.')
parser.add_argument('--logdir', default='runs/', 
    type=str, help='Logging path.', required=False)
parser.add_argument('--ckpdir', default='result/', 
    type=str, help='Checkpoint/Result path.', required=False)
parser.add_argument('--seed', default=1, type=int, 
    help='Random seed for reproducable results.', required=False)
parser.add_argument('--verbose', default=True, 
    type=bool, required=False)

paras = parser.parse_args()

# note :  'rnn_lm': LMTrainer, was removed since validation error
# never got better. Use CHARLMTrainer instead.

type_map = {'asr': ASRTrainer, 'tae': TAETrainer, 
    'sae': SAETrainer, 'adv': AdvTrainer, 'test': ASRTester, 'char_lm': CHARLMTrainer}

config = yaml.load(open(paras.config,'r'), Loader=yaml.FullLoader)

random.seed(paras.seed)
np.random.seed(paras.seed)
torch.manual_seed(paras.seed)
if torch.cuda.is_available(): torch.cuda.manual_seed_all(paras.seed)

trainer = type_map[paras.type](config,paras)
trainer.load_data()
trainer.set_model()
trainer.exec()
