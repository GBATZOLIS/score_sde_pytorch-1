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

from configs.jan.default import get_default_configs

def get_config():
  config = get_default_configs()

  #logging
  config.logging = logging = ml_collections.ConfigDict()
  logging.log_path = 'logs/circles/fokker_planck/proto/'
  logging.log_name = 'fp_1e-3'
  logging.top_k = 5
  logging.every_n_epochs = 1000
  logging.envery_timedelta = timedelta(minutes=1)

 # training
  training = config.training
  training.lightning_module = 'fokker-planck' 
  training.batch_size = 500
  training.num_epochs = 5* int(1e4)
  training.n_iters = int(1e20)
  training.likelihood_weighting = True
  training.continuous = True
  training.sde = 'vesde'
  training.schedule = 'constant'
  training.alpha=1e-3
  training.alpha_min=1e-4
  training.alpha_max=1e-2
  training.hutchinson = False
  training.n_chunks=50
  # callbacks
  training.visualization_callback = ['2DSamplesVisualization', '2DVectorFieldVisualization']
  training.show_evolution = True 

  # validation
  validation = config.validation
  validation.batch_size = 500

  # sampling
  sampling = config.sampling
  sampling.method = 'pc'
  sampling.predictor = 'reverse_diffusion'
  sampling.corrector = 'none'
  sampling.n_steps_each = 1
  sampling.noise_removal = True
  sampling.probability_flow = False
  sampling.snr = 0.075 #0.15 in VE sde (you typically need to play with this term - more details in the main paper)

  # data
  config.data = data = ml_collections.ConfigDict()
  data.datamodule = 'Synthetic'
  data.dataset_type = 'Circles'
  data.use_data_mean = False # What is this?
  data.create_dataset = False
  data.split = [0.8, 0.1, 0.1]
  data.data_samples = 50000
  data.noise = 0.06
  data.factor = 0.5
  data.return_labels = False #whether to return the mixture class of each point in the mixture.
  data.shape = [2]
  data.dim = 2
  data.num_channels = 0 
  
  # model
  config.model = model = ml_collections.ConfigDict()
  model.checkpoint_path = 'logs/circles/fokker_planck/proto/fp_1e-3/checkpoints/best/last.ckpt' #'logs/circles/fokker_planck/fp_grad-alpha_0_deep/checkpoints/best/last.ckpt'
  model.sigma_max = 4
  model.sigma_min = 0.01
  model.beta_min = 0.1
  model.beta_max = 25

  model.name = 'fcn_potential'
  model.state_size = data.dim
  model.hidden_layers = 3
  model.hidden_nodes = 256
  model.dropout = 0.0
  model.scale_by_sigma = False
  model.num_scales = 1000
  model.ema_rate = 0.9999

  # optimization
  optim = config.optim
  optim.weight_decay = 0
  optim.optimizer = 'Adam'
  optim.lr = 2e-5
  optim.beta1 = 0.9
  optim.eps = 1e-8
  optim.warmup = 5000
  optim.grad_clip = 1.

  config.seed = 42
  config.device = torch.device('cuda:0') if torch.cuda.is_available() else torch.device('cpu')


  return config