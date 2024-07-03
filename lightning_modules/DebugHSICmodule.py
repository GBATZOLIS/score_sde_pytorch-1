from . import BaseSdeGenerativeModel
from disentanglement_losses import get_disentangled_HSIC_scoreVAE_loss_fn, scoreVAE_loss_fn, get_DSM_loss_fn
import pytorch_lightning as pl
import sde_lib
from models import utils as mutils
from . import utils
from utils import get_named_beta_schedule
import torch.optim as optim
import os
import torch
from sde_lib import cVPSDE, csubVPSDE, cVESDE
from sampling.conditional import get_conditional_sampling_fn
from sampling.unconditional import get_sampling_fn
import torchvision
import numpy as np
import losses
import torch
import lpips
from pathlib import Path
from scipy.interpolate import PchipInterpolator
from torch.distributions import Uniform
from torch.nn.utils import clip_grad_norm_
from hsic import HSIC, rbf_kernel, dot_product_kernel, median_heuristic, convert_to_one_hot
import random
import gc

@utils.register_lightning_module(name='debug_disentangled_HSIC_score_vae')
class DisentangledHSICScoreVAEmodel(pl.LightningModule):
    def __init__(self, config, *args, **kwargs):
        super().__init__()
        self.save_hyperparameters()
        self.automatic_optimization = False  # Disable automatic optimization

        # Initialize the score model
        self.config = config
        
        # Unconditional score model
        self.score_model = mutils.load_prior_model(config)  # Can be either conditional or unconditional
        self.score_model.freeze()

        # Encoder
        self.encoder = mutils.create_model(config, aux_model='encoder')  # It encodes image latent characteristics independent from the encoded attributes

        # Initialize the exponential moving average sigma as a buffer
        self.register_buffer('sigma_ema', torch.tensor(-1.0, device=self.device))  # Initialize with some default value
        self.sigma_decay = 0.999

        self.register_buffer('step_counter', torch.tensor(0, device=self.device))


    # Function to toggle the `requires_grad` status of encoder parameters
    def set_requires_grad(self, model, value):
        for param in model.parameters():
            param.requires_grad = value

    def configure_sde(self, config):
        if config.training.sde.lower() == 'vpsde':
            self.sde = sde_lib.cVPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
            self.usde = sde_lib.VPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
            self.sampling_eps = 1e-3
        elif config.training.sde.lower() == 'subvpsde':
            self.sde = sde_lib.csubVPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
            self.usde = sde_lib.subVPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
            self.sampling_eps = 1e-3
        elif config.training.sde.lower() == 'vesde':            
            self.sde = sde_lib.cVESDE(sigma_min=config.model.sigma_min_x, sigma_max=config.model.sigma_max_x, N=config.model.num_scales)
            self.usde = sde_lib.VESDE(sigma_min=config.model.sigma_min_x, sigma_max=config.model.beta_max_x, N=config.model.num_scales)
            self.sampling_eps = 1e-5   
        elif config.training.sde.lower() == 'snrsde':
            self.sampling_eps = 1e-3

            if hasattr(config.training, 'beta_schedule'):
                # DISCRETE QUANTITIES
                N = config.model.num_scales
                betas = get_named_beta_schedule('linear', N)
                alphas = 1.0 - betas
                alphas_cumprod = np.cumprod(alphas, axis=0)
                discrete_snrs = alphas_cumprod/(1.0 - alphas_cumprod)

                # Monotonic Bicubic Interpolation
                snr = PchipInterpolator(np.linspace(self.sampling_eps, 1, len(discrete_snrs)), discrete_snrs)
                d_snr = snr.derivative(nu=1)

                def logsnr(t):
                    device = t.device
                    snr_val = torch.from_numpy(snr(t.cpu().numpy())).float().to(device)
                    return torch.log(snr_val)

                def d_logsnr(t):
                    device = t.device
                    dsnr_val = torch.from_numpy(d_snr(t.cpu().numpy())).float().to(device)
                    snr_val = torch.from_numpy(snr(t.cpu().numpy())).float().to(device)
                    return dsnr_val/snr_val

                self.sde = sde_lib.cSNRSDE(N=N, gamma=logsnr, dgamma=d_logsnr)
                self.usde = sde_lib.SNRSDE(N=N, gamma=logsnr, dgamma=d_logsnr)
            else:
                self.sde = sde_lib.cSNRSDE(N=config.model.num_scales)
                self.usde = sde_lib.SNRSDE(N=config.model.num_scales)

        else:
            raise NotImplementedError(f"SDE {config.training.sde} unknown.")

        self.sde.sampling_eps = self.sampling_eps
        self.usde.sampling_eps = self.sampling_eps

        self.t_dist = Uniform(self.sampling_eps, 1)
    
    def get_conditional_score_fn(self, train=False, gamma=1):
        def get_latent_correction_fn(encoder):
            def get_log_density_fn(encoder):
                def log_density_fn(x, z, t):
                    latent_distribution_parameters = encoder(x, t)
                    channels = latent_distribution_parameters.size(1) // 2
                    mean_z = latent_distribution_parameters[:, :channels]
                    log_var_z = latent_distribution_parameters[:, channels:]

                    # Flatten mean_z and log_var_z for consistent shape handling
                    mean_z_flat = mean_z.view(mean_z.size(0), -1)
                    log_var_z_flat = log_var_z.view(log_var_z.size(0), -1)
                    z_flat = z.view(z.size(0), -1)

                    logdensity = -0.5 * torch.sum(torch.square(z_flat - mean_z_flat) / log_var_z_flat.exp(), dim=1)
                    return logdensity

                return log_density_fn

            def latent_correction_fn(x, z, t):
                if not train:
                    torch.set_grad_enabled(True)

                log_density_fn = get_log_density_fn(encoder)
                device = x.device
                x.requires_grad = True
                ftx = log_density_fn(x, z, t)
                grad_log_density = torch.autograd.grad(outputs=ftx, inputs=x,
                                      grad_outputs=torch.ones(ftx.size()).to(device),
                                      create_graph=True, retain_graph=True, only_inputs=True)[0]
                assert grad_log_density.size() == x.size()

                if not train:
                    torch.set_grad_enabled(False)

                return grad_log_density

            return latent_correction_fn

        if gamma == 1:
            def conditional_score_fn(x, cond, t):
                y, z = cond
                
                latent_correction_fn = get_latent_correction_fn(self.encoder)
                pretrained_score_fn = mutils.get_score_fn(self.sde, self.score_model, conditional=True, 
                                                        train=train, continuous=True)
                conditional_score = pretrained_score_fn({'x': x, 'y': y}, t) + latent_correction_fn(x, z, t)
                return conditional_score
        else:
            def conditional_score_fn(x, cond, t):
                latent_correction_fn = get_latent_correction_fn(self.encoder)
                pretrained_score_fn = mutils.get_score_fn(self.sde, self.score_model, conditional=True, 
                                                        train=train, continuous=True)
                y, z = cond
                batchsize = x.size(0)
                y_uncond = torch.ones_like(y) * -1
                x_concat = torch.cat([x, x], dim=0)
                y_concat = torch.cat([y_uncond, y], dim=0)
                t_concat = torch.cat([t, t], dim=0)
                out = pretrained_score_fn({'x': x_concat, 'y': y_concat}, t_concat)  # (2*batchsize, *x.shape[1:])
                unconditional_score, conditional_score = out[:batchsize], out[batchsize:]
                reweighted_pretrained_score = (1 - gamma) * unconditional_score + gamma * conditional_score
                
                conditional_score = reweighted_pretrained_score + latent_correction_fn(x, z, t)
                
                return conditional_score

        return conditional_score_fn

    def configure_loss_fn(self, config, train):
        encoder_loss_fn = get_disentangled_HSIC_scoreVAE_loss_fn(self.sde,
                                        likelihood_weighting=config.training.likelihood_weighting,
                                        kl_weight=config.training.kl_weight,
                                        disentanglement_factor=config.training.disentanglement_factor)
        
        return encoder_loss_fn
    
    def training_step(self, batch, batch_idx):
        optimizers = self.optimizers()
        encoder_optimizer = optimizers

        # Scheduler for the encoder
        schedulers = self.lr_schedulers()
        encoder_scheduler = schedulers

        self.set_requires_grad(self.encoder, True)

        # Extract a small batch for scoreVAE_loss evaluation
        small_batch_size = self.config.training.small_batch_size
        indices = random.sample(range(batch[0].size(0)), small_batch_size)
        small_batch = (batch[0][indices], batch[1][indices])

        cond_score_fn = self.get_conditional_score_fn(train=True)

        # Use the small batch for scoreVAE_loss evaluation
        small_x, small_y = small_batch
        t0 = torch.zeros(small_x.shape[0]).type_as(small_x)
        latent_distribution_parameters = self.encoder(small_x, t0)
        channels = latent_distribution_parameters.size(1) // 2
        mean_z = latent_distribution_parameters[:, :channels]
        log_var_z = latent_distribution_parameters[:, channels:]
        latent = mean_z + (0.5 * log_var_z).exp() * torch.randn_like(mean_z)

        scoreVAE_loss = scoreVAE_loss_fn(cond_score_fn, small_x, small_y, mean_z, log_var_z, latent, self.t_dist, self.config.training.likelihood_weighting, self.config.training.kl_weight, self.sde)
        loss = scoreVAE_loss

        # Update sigma in EMA fashion
        new_sigma = median_heuristic(latent)
        if self.sigma_ema.item() < 0:
            sigma = new_sigma
        else:
            sigma = self.sigma_decay * self.sigma_ema.item() + (1 - self.sigma_decay) * new_sigma
        self.sigma_ema = torch.tensor(sigma, device=self.device)

        self.log('rbf_sigma_ema', sigma)
        self.log('encoder_loss', scoreVAE_loss)  # Logging the scoreVAE_loss directly

        self.manual_backward(loss)
        clip_grad_norm_(self.encoder.parameters(), self.config.optim.manual_grad_clip)
        encoder_optimizer.step()
        encoder_optimizer.zero_grad()

        # Step the scheduler
        encoder_scheduler.step()

        self.step_counter += 1  # Increment step counter



    def validation_step(self, batch, batch_idx):
        x, y = batch

        # Get the encoded latent and its associated parameters (mean_z, log_var_z) for the smaller batch
        small_batch_size = self.config.training.small_batch_size
        indices = random.sample(range(x.size(0)), small_batch_size)
        small_x, small_y = x[indices], y[indices]

        t0 = torch.zeros(small_x.shape[0]).type_as(small_x)
        latent_distribution_parameters = self.encoder(small_x, t0)
        channels = latent_distribution_parameters.size(1) // 2
        mean_z = latent_distribution_parameters[:, :channels]
        log_var_z = latent_distribution_parameters[:, channels:]
        latent = mean_z + (0.5 * log_var_z).exp() * torch.randn_like(mean_z)

        cond_score_fn = self.get_conditional_score_fn(train=False)
        weighting = self.config.training.likelihood_weighting
        kl_weight = self.config.training.kl_weight
        val_scoreVAE_loss = scoreVAE_loss_fn(cond_score_fn, small_x, small_y, mean_z, log_var_z,
                                            latent, self.t_dist, weighting,
                                            kl_weight, self.sde)
        self.log('val_scoreVAE_loss', val_scoreVAE_loss)

        # Compute HSIC between y and latent using EMA sigma with the entire batch, processed in smaller sub-batches without gradient tracking
        sub_batch_size = x.size(0) // 2  # Split into 2 sub-batches
        latents = []
        with torch.no_grad():
            for i in range(0, x.size(0), sub_batch_size):
                sub_x = x[i:i + sub_batch_size]
                sub_t0 = torch.zeros(sub_x.shape[0]).type_as(sub_x)
                latent_distribution_parameters = self.encoder(sub_x, sub_t0)
                channels = latent_distribution_parameters.size(1) // 2
                mean_z = latent_distribution_parameters[:, :channels]
                log_var_z = latent_distribution_parameters[:, channels:]
                latent = mean_z + (0.5 * log_var_z).exp() * torch.randn_like(mean_z)
                latents.append(latent)
                # Manual garbage collection
                del sub_x, latent_distribution_parameters, mean_z, log_var_z, latent
                torch.cuda.empty_cache()
                gc.collect()

        latent = torch.cat(latents, dim=0)

        hsic_instance = HSIC(
            kernel_x=lambda X: rbf_kernel(X, sigma=self.sigma_ema.item()),
            kernel_y=lambda Y: dot_product_kernel(convert_to_one_hot(Y)),
            algorithm='unbiased'
        )
        hsic_value = hsic_instance(latent, y)
        self.log('val_hsic_value', hsic_value)

        dis_factor = self.config.training.disentanglement_factor
        loss = val_scoreVAE_loss + dis_factor * hsic_value
        self.log('eval_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)



    def encode(self, x, y, use_latent_mean=False, encode_x_T=False):
        t0 = torch.zeros(x.shape[0]).type_as(x)
        latent_distribution_parameters = self.encoder(x, t0)
        latent_dim = latent_distribution_parameters.size(1) // 2
        mean_z = latent_distribution_parameters[:, :latent_dim]
        log_var_z = latent_distribution_parameters[:, latent_dim:]
        if use_latent_mean:
            z = mean_z
        else:
            z = mean_z + (0.5 * log_var_z).exp() * torch.randn_like(mean_z)
        
        # --new code--
        if encode_x_T:
            conditional_sampling_fn = get_conditional_sampling_fn(config=self.config, sde=self.sde, 
                                                              shape=x.size(), eps=self.sampling_eps, 
                                                              p_steps=256,
                                                              predictor='conditional_ddim',
                                                              direction='forward', 
                                                              x_boundary=x)

            score_fn = self.get_conditional_score_fn(train=False)
            cond = [y, z]
            x_T = conditional_sampling_fn(self.score_model, cond, score_fn=score_fn)
            return z, x_T
        else:
            return z, None

    def decode(self, y, z, x_T=None, gamma=1):
        sampling_shape = [z.size(0)] + self.config.data.shape
        conditional_sampling_fn = get_conditional_sampling_fn(config=self.config, sde=self.sde, 
                                                              shape=sampling_shape, eps=self.sampling_eps,
                                                              p_steps=128,
                                                              predictor='conditional_heun',
                                                              x_boundary=x_T)
        cond = [y, z]
        score_fn = self.get_conditional_score_fn(train=False, gamma=gamma)
        return conditional_sampling_fn(self.score_model, cond, score_fn=score_fn)

    def encode_n_decode(self, x, y, encode_x_T=False):
        z, x_T = self.encode(x, y, encode_x_T=encode_x_T)
        x_hat = self.decode(y, z, x_T)
        return x_hat
    
    def flip_attributes(self, y, attributes=None, attribute_to_index_map=None):
        # Create a copy of y to avoid modifying the original tensor
        y_flipped = y.clone()

        # Check if an attribute_to_index_map is provided, if not, fetch it from the data module
        if attribute_to_index_map is None:
            # Ensure self.trainer is available and has been set
            if self.trainer and hasattr(self.trainer, 'datamodule') and self.trainer.datamodule is not None:
                data_module = self.trainer.datamodule
                attribute_to_index_map = data_module.get_attribute_to_index_map()
            else:
                # Handle the case where the data module or trainer is not available
                raise RuntimeError("Data module is not accessible. Ensure this method is called within the LightningModule lifecycle.")

        if attributes == 'all':
            # If no attributes specified, assume flipping all attributes
            indices_to_flip = list(range(y.shape[1]))
        elif attributes == None:
            indices_to_flip = []
        else:
            if isinstance(attributes, str):
                attributes = [attributes]  # Wrap the single attribute in a list

            # Find the column indices for the specified attributes using the provided or fetched map
            indices_to_flip = [attribute_to_index_map[attr] for attr in attributes]

        # Flip the specified attributes in y_flipped
        for index in indices_to_flip:
            y_flipped[:, index] = 1 - y_flipped[:, index]

        return y_flipped

    def configure_optimizers(self):
        class scheduler_lambda_function:
            def __init__(self, warm_up):
                self.use_warm_up = True if warm_up > 0 else False
                self.warm_up = warm_up

            def __call__(self, s):
                if self.use_warm_up:
                    if s < self.warm_up:
                        return s / self.warm_up
                    else:
                        return 1
                else:
                    return 1
                
        # Optimizer for the encoder
        encoder_optimizer = optim.Adam(self.encoder.parameters(), lr=self.config.optim.encoder_lr, betas=(self.config.optim.beta1, 0.999), 
                                        eps=self.config.optim.eps, weight_decay=self.config.optim.weight_decay)
        
        # Set up the learning rate scheduler for the encoder's optimizer
        encoder_scheduler = optim.lr_scheduler.LambdaLR(encoder_optimizer, scheduler_lambda_function(self.config.optim.warmup))
        
        return {
            'optimizer': encoder_optimizer,
            'lr_scheduler': {
                'scheduler': encoder_scheduler,
                'interval': 'step'  # called after each training step
            }
        }