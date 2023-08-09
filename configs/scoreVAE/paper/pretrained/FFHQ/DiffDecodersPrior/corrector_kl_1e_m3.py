import ml_collections
import torch
import math
import numpy as np
from datetime import timedelta

def get_config():
  config = ml_collections.ConfigDict()

  hpc = False

  #logging
  config.logging = logging = ml_collections.ConfigDict()
  logging.log_path = '/home/gb511/rds_work/projects/scoreVAE/experiments/gd_ffhq' if hpc else '/home/gb511/projects/scoreVAE/experiments/ffhq' 
  
  logging.encoder_log_name = 'only_encoder_ddpm_plus_smld_VAE_KLweight_1e_m3_DiffDecoders_continuous_prior_importance_sampling'
  logging.log_name = 'corrected' + '_' + logging.encoder_log_name
  
  logging.top_k = 3
  logging.every_n_epochs = 1000
  logging.envery_timedelta = timedelta(minutes=1)

  # training
  config.training = training = ml_collections.ConfigDict()
  config.training.lightning_module = 'corrected_encoder_only_pretrained_score_vae'
  training.use_pretrained = True
  training.prior_config_path = '/home/gb511/rds_work/projects/scoreVAE/experiments/gd_ffhq/DiffDecoders_continuous_prior/config.pkl' if hpc else '/home/gb511/projects/scoreVAE/experiments/ffhq/DiffDecoders_continuous_prior/config.pkl'
  training.prior_checkpoint_path = '/home/gb511/rds_work/projects/scoreVAE/experiments/gd_ffhq/DiffDecoders_continuous_prior/checkpoints/best/epoch=141--eval_loss_epoch=0.014.ckpt' if hpc else '/home/gb511/projects/scoreVAE/experiments/ffhq/DiffDecoders_continuous_prior/checkpoints/best/epoch=141--eval_loss_epoch=0.014.ckpt'
  training.encoder_only = True
  training.t_dependent = True

  #correction settings
  training.latent_correction = True
  training.encoder_checkpoint_path = '/home/gb511/rds_work/projects/scoreVAE/experiments/gd_ffhq/only_encoder_ddpm_plus_smld_VAE_KLweight_1e_m3_DiffDecoders_continuous_prior_importance_sampling/checkpoints/best/last.ckpt' if hpc else '/home/gb511/projects/scoreVAE/experiments/ffhq/only_encoder_ddpm_plus_smld_VAE_KLweight_1e_m3_DiffDecoders_continuous_prior_importance_sampling/checkpoints/best/last.ckpt'

  training.conditioning_approach = 'sr3'
  training.batch_size = 2
  training.t_batch_size = 1
  training.num_nodes = 1
  training.gpus = 1
  training.accelerator = 'cpu'
  training.accumulate_grad_batches = 2
  training.workers = 4*training.gpus
  #----- to be removed -----
  training.num_epochs = 10000
  training.n_iters = 2500000
  training.snapshot_freq = 5000
  training.log_freq = 250
  training.eval_freq = 2500
  #------              --------
  
  #training.importance_freq = 3 #we evaluate the contribution profile every importance_freq epochs
  training.visualisation_freq = 10
  training.visualization_callback = [] #['celeba_distribution_shift' ,'jan_georgios']
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
  data.base_dir = '/home/gb511/rds_work/datasets/' if hpc else '/home/gb511/datasets' 
  data.dataset = 'ffhq'
  data.datamodule = 'guided_diffusion_dataset'
  data.return_labels = False
  data.use_data_mean = False
  data.create_dataset = False
  data.split = [0.9, 0.05, 0.05]
  data.image_size = 128
  data.percentage_use = 1 #default:100
  data.effective_image_size = data.image_size
  data.shape = [3, data.image_size, data.image_size]
  data.latent_dim = 512
  data.class_cond = False
  data.centered = True
  data.random_crop = False
  data.random_flip = False
  data.num_channels = data.shape[0] #the number of channels the model sees as input.

  # model
  config.model = model = ml_collections.ConfigDict()
  model.checkpoint_path = None
  model.sigma_min = 0.01
  model.sigma_max = 50
  model.num_scales = 1000
  model.beta_min = 0.1
  model.beta_max = 20.
  model.dropout = 0.
  model.embedding_type = 'fourier'

  model.name = 'BeatGANsLatentScoreModel'
  model.ema_rate = 0.9999
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
  model.attention_resolutions = (16, )
  # number of time embed channels
  model.time_embed_channels: int = None
  # dropout applies to the resblocks (on feature maps)
  model.dropout: float = 0.
  model.channel_mult = (1, 1, 2, 3, 4)
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
  model.num_head_channels: int = -1
  # what's this?
  model.num_heads_upsample: int = -1
  # use resblock for upscale/downscale blocks (expensive)
  # default: True (BeatGANs)
  model.resblock_updown: bool = True
  # never tried
  model.use_new_attention_order: bool = False
  model.resnet_two_cond: bool = True
  model.resnet_cond_channels: int = None
  # init the decoding conv layers with zero weights, this speeds up training
  # default: True (BeattGANs)
  model.resnet_use_zero_module: bool = True
  # gradient checkpoint the attention operation
  model.attn_checkpoint: bool = False

  model.encoder_name = 'time_dependent_DDPM_encoder'
  model.encoder_input_channels = data.num_channels
  model.encoder_latent_dim = data.latent_dim
  model.encoder_base_channel_size = 64
  model.encoder_split_output=False


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