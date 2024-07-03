import ml_collections
import torch
import math
import numpy as np
from datetime import timedelta

def get_config():
  config = ml_collections.ConfigDict()

  config.server = 'CIA'

  #logging
  config.logging = logging = ml_collections.ConfigDict()
  logging.log_path = '/home/gb511/rds_work/projects/scoreVAE/experiments/gd_ffhq' if config.server=='hpc' else '/store/CIA/gb511/projects/scoreVAE/experiments/ffhq' 
  logging.log_name = 'BeatGANsEncoder_flatten_linear_bigger_latent_deeper'
  logging.top_k = 3
  logging.every_n_epochs = 1000
  logging.envery_timedelta = timedelta(minutes=1)

  # training
  config.training = training = ml_collections.ConfigDict()
  config.training.lightning_module = 'encoder_only_pretrained_score_vae'
  training.use_pretrained = True
  training.prior_config_path = '/home/gb511/rds_work/projects/scoreVAE/experiments/gd_ffhq/DiffDecoders_continuous_prior/config.pkl' if config.server=='hpc' else '/store/CIA/gb511/projects/scoreVAE/experiments/ffhq/prior/config.pkl' 
  training.prior_checkpoint_path = '/home/gb511/rds_work/projects/scoreVAE/experiments/gd_ffhq/DiffDecoders_continuous_prior/checkpoints/best/epoch=141--eval_loss_epoch=0.014.ckpt' if config.server=='hpc' else '/store/CIA/gb511/projects/scoreVAE/experiments/ffhq/prior/epoch=141--eval_loss_epoch=0.014.ckpt' 
  training.encoder_only = True
  training.t_dependent = True
  training.conditioning_approach = 'sr3'
  training.batch_size = 16 #64
  training.t_batch_size = 1
  training.num_nodes = 1
  training.gpus = 4
  training.accelerator = 'gpu'
  training.accumulate_grad_batches = 1
  training.workers = 4*training.gpus
  #----- to be removed -----
  training.num_epochs = 10000
  training.n_iters = 2500000
  training.snapshot_freq = 5000
  training.log_freq = 250
  training.eval_freq = 2500
  #------              --------
  
  training.visualisation_freq = 10
  training.visualization_callback = []
  training.show_evolution = False

  training.likelihood_weighting = False
  training.continuous = True
  training.reduce_mean = True 
  training.sde = 'snrsde'
  training.beta_schedule = 'linear'

  ##new related to the training of Score VAE
  training.variational = True
  training.cde_loss = False
  training.kl_weight = 1e-3

  # validation
  config.validation = validation = ml_collections.ConfigDict()
  validation.batch_size = training.batch_size
  validation.workers = training.workers

  # sampling
  config.sampling = sampling = ml_collections.ConfigDict()
  sampling.method = 'pc'
  sampling.predictor = 'conditional_ddim'
  sampling.corrector = 'conditional_none'
  sampling.n_steps_each = 1
  sampling.noise_removal = True
  sampling.probability_flow = False
  sampling.snr = 0.15 #0.15 in VE sde (you typically need to play with this term - more details in the main paper)

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
  data.base_dir = '/home/gb511/rds_work/datasets/' if config.server=='hpc' else '/store/CIA/gb511/datasets' 
  data.dataset = 'celebA-HQ-160'
  data.datamodule = 'CelebA_Annotated_PKLDataset'
  data.normalization_mode = 'gd'
  data.attributes = ['all']

  data.return_labels = False
  data.use_data_mean = False
  data.create_dataset = False
  #data.split = [0.9, 0.05, 0.05]
  data.image_size = 128
  #data.percentage_use = 100 #default:100
  data.effective_image_size = data.image_size
  data.shape = [3, data.image_size, data.image_size]
  data.latent_dim = 1024
  data.class_cond = False
  data.centered = True
  data.random_crop = False
  data.random_flip = False
  data.num_channels = data.shape[0] #the number of channels the model sees as input.

  #encoder
  config.encoder = encoder = ml_collections.ConfigDict()
  encoder.name = 'BeatGANsEncoderModel'
  encoder.enc_use_time_condition = True
  encoder.model_channels = 128
  encoder.in_channels = data.num_channels  # Ensure 'data.num_channels' is defined elsewhere in your code
  encoder.image_size = data.image_size  # Ensure 'data.image_size' is defined elsewhere in your code
  encoder.enc_channel_mult = (1, 1, 2, 3, 4, 4)
  encoder.enc_num_res_blocks = 2
  encoder.dropout = 0
  encoder.dims = 2
  encoder.use_checkpoint = False
  encoder.num_heads = 1
  encoder.num_head_channels = -1  # Default setting, could be changed if needed
  encoder.use_new_attention_order = False
  encoder.resblock_updown = False
  encoder.conv_resample = True
  encoder.enc_attn_resolutions = ()  # Empty tuple indicates no specific resolutions for attention
  encoder.enc_pool = 'flatten-linear'
  encoder.resolution_before_flattening = data.image_size // 2**(len(encoder.enc_channel_mult)-1)  # Calculation based on 'enc_channel_mult'
  encoder.enc_out_channels = 2*data.latent_dim  # Ensure 'data.latent_dim' is defined elsewhere in your code
  encoder.encoder_split_output = False

  # model
  config.model = model = ml_collections.ConfigDict()
  model.checkpoint_path = None
  model.num_scales = 1000
  model.ema_rate = 0.999 #0.9999

  # optimization
  config.optim = optim = ml_collections.ConfigDict()
  optim.weight_decay = 0
  optim.optimizer = 'Adam'
  optim.lr = 5e-5
  optim.beta1 = 0.9
  optim.eps = 1e-8
  optim.warmup = 1000
  optim.slowing_factor = 1
  optim.grad_clip = 1.

  config.seed = 42
  return config