import ml_collections
import torch
import math
import numpy as np
from datetime import timedelta

def get_config():
  config = ml_collections.ConfigDict()

  #logging
  config.logging = logging = ml_collections.ConfigDict()
  logging.log_path = '/home/gb511/projects/scoreVAE/experiments/cifar10' #'/home/gb511/rds/rds-t2-cs138-LlrDsbHU5UM/gb511/projects/scoreVAE/experiments/paper/pretrained/cifar10/'
  logging.log_name = 'continuous_conversion_linear'
  logging.top_k = 5
  logging.every_n_epochs = 1000
  logging.envery_timedelta = timedelta(minutes=1)

  # training
  config.training = training = ml_collections.ConfigDict()
  config.training.lightning_module = 'base'
  training.conditioning_approach = 'sr3'
  training.batch_size = 64
  training.t_batch_size = 1
  training.num_nodes = 1
  training.gpus = 1
  training.accelerator = None if training.gpus == 1 else 'ddp'
  training.accumulate_grad_batches = 1
  training.workers = 4*training.gpus
  #----- to be removed -----
  training.num_epochs = 10000
  training.n_iters = 2500000
  training.snapshot_freq = 5000
  training.log_freq = 250
  training.eval_freq = 2500
  #------              --------
  
  training.visualisation_freq = 1
  training.visualization_callback = 'base'
  training.show_evolution = False

  training.likelihood_weighting = False
  training.continuous = True
  training.reduce_mean = True 
  training.sde = 'snrsde'
  training.beta_schedule = 'linear'

  # validation
  config.validation = validation = ml_collections.ConfigDict()
  validation.batch_size = training.batch_size
  validation.workers = training.workers

  # sampling
  config.sampling = sampling = ml_collections.ConfigDict()
  sampling.method = 'pc'
  sampling.predictor = 'euler_maruyama'
  sampling.corrector = 'none'
  sampling.n_steps_each = 1
  sampling.noise_removal = True
  sampling.probability_flow = False
  sampling.snr = 0.15 

  # evaluation (this file is not modified at all - subject to change)
  config.eval = evaluate = ml_collections.ConfigDict()
  evaluate.callback = None
  evaluate.workers = training.workers
  evaluate.begin_ckpt = 50
  evaluate.end_ckpt = 96
  evaluate.batch_size = validation.batch_size
  evaluate.enable_sampling = True
  evaluate.num_samples = 50000
  evaluate.enable_loss = True
  evaluate.enable_bpd = False
  evaluate.bpd_dataset = 'test'

  # data
  config.data = data = ml_collections.ConfigDict()
  data.base_dir = '/home/gb511/datasets' #'/home/gb511/rds/rds-t2-cs138-LlrDsbHU5UM/gb511/datasets'
  data.dataset = 'cifar10'
  data.datamodule = data.dataset
  data.return_labels = False
  data.use_data_mean = False
  data.create_dataset = False
  data.split = [0.8, 0.1, 0.1]
  data.image_size = 32
  data.effective_image_size = data.image_size
  data.shape = [3, data.image_size, data.image_size]
  data.latent_dim = 384
  data.centered = False
  data.use_flip = False
  data.crop = False
  data.uniform_dequantization = False
  data.num_channels = data.shape[0] #the number of channels the model sees as input.

  # model
  config.model = model = ml_collections.ConfigDict()
  model.num_scales = 1000
  model.discrete_checkpoint_path = '/home/gb511/projects/scoreVAE/experiments/cifar10/prior_linear/checkpoints/epoch=799-step=281600.ckpt'
  model.checkpoint_path = None

  model.name = 'ImprovedDiffusionUNetModel'
  model.use_fp16 = False
  model.ema_rate = 0.999
  model.image_size = data.image_size
  model.in_channels = data.num_channels
  # base channels, will be multiplied
  model.model_channels: int = 128
  # output of the unet
  # suggest: 3
  # you only need 6 if you also model the variance of the noise prediction (usually we use an analytical variance hence 3)
  model.out_channels = data.num_channels
  # how many repeating resblocks per resolution
  # the decoding side would have "one more" resblock
  # default: 2
  model.num_res_blocks: int = 2
  # you can also set the number of resblocks specifically for the input blocks
  # default: None = above
  model.num_input_res_blocks: int = None
  # number of time embed channels and style channels
  model.embed_channels = data.latent_dim 
  # at what resolutions you want to do self-attention of the feature maps
  # attentions generally improve performance
  # default: [16]
  # beatgans: [32, 16, 8]
  model.attention_resolutions = (16, 8)
  # number of time embed channels
  model.time_embed_channels: int = None
  # dropout applies to the resblocks (on feature maps)
  model.dropout: float = 0.3
  model.channel_mult = (1, 2, 4)
  model.input_channel_mult = None
  model.conv_resample: bool = True
  # always 2 = 2d conv
  model.dims: int = 2
  # don't use this, legacy from BeatGANs
  model.num_classes: int = None
  model.use_checkpoint: bool = False
  # number of attention heads
  model.num_heads: int = 1
  # or specify the number of channels per attention head
  model.num_head_channels: int = 64
  # what's this?
  model.num_heads_upsample: int = -1
  # use resblock for upscale/downscale blocks (expensive)
  # default: True (BeatGANs)
  model.resblock_updown: bool = True
  # never tried
  model.use_new_attention_order: bool = False
  #model.resnet_two_cond: bool = False
  #model.resnet_cond_channels: int = None
  # init the decoding conv layers with zero weights, this speeds up training
  # default: True (BeattGANs)
  #model.resnet_use_zero_module: bool = True
  # gradient checkpoint the attention operation
  #model.attn_checkpoint: bool = False
  model.use_scale_shift_norm = True

  # optimization
  config.optim = optim = ml_collections.ConfigDict()
  optim.weight_decay = 0
  optim.optimizer = 'Adam'
  optim.lr = 1e-5
  optim.beta1 = 0.9
  optim.eps = 1e-8
  optim.warmup = 5000
  optim.grad_clip = 1.

  config.seed = 42
  return config