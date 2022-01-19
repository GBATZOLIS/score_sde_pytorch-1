"""Config file for synthetic dataset."""
import ml_collections
from configs.jan.circles.cp import default_cp

def get_config():
  config = default_cp.get_config()

  # training
  training = config.training
  training.LAMBDA=1
  training.adaptive = False

  return config
