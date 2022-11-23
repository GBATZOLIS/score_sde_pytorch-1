# coding=utf-8
# Copyright 2020 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
"""Config file for synthetic dataset."""

import ml_collections
import torch
import math
import numpy as np
from datetime import timedelta

from configs.ksphere.vesde import get_config as veconfig

def get_config():
  config = veconfig()

  # data
  data = config.data
  data.n_spheres = 5

  # model
  model = config.model
  model.sigma_min = 1e-3
  model.sigma_max = 4

  #logging
  logging = config.logging
  logging.log_path = f'logs/ksphere/n_{data.n_spheres}/'
  logging.log_name = f've_sig_{model.sigma_min}_{model.sigma_max}'

  return config