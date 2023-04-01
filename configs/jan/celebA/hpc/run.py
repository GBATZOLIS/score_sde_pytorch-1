import ml_collections
import torch
import math
import numpy as np
import configs.jan.celebA.potential_snr as base


def get_config():
  config = base.get_config()


  data = config.data
  data.base_dir = '/rds/user/js2164/hpc-work/data'
  data.dataset = 'celeba'
  return config