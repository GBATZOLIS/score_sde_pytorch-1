from . import BaseSdeGenerativeModel
from losses import get_scoreVAE_loss_fn
import pytorch_lightning as pl
import sde_lib
from models import utils as mutils
from . import utils
import torch.optim as optim
import os
import torch
from sde_lib import cVPSDE, csubVPSDE, cVESDE
from sampling.conditional import get_conditional_sampling_fn
import torchvision
import numpy as np

@utils.register_lightning_module(name='score_vae')
class ScoreVAEmodel(BaseSdeGenerativeModel.BaseSdeGenerativeModel):
    def __init__(self, config, *args, **kwargs):
        super().__init__(config)
        self.encoder = mutils.create_encoder(config)

    def configure_sde(self, config):
        if config.training.sde.lower() == 'vpsde':
            self.sde = sde_lib.cVPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
            self.sampling_eps = 1e-3
        elif config.training.sde.lower() == 'subvpsde':
            self.sde = sde_lib.csubVPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
            self.sampling_eps = 1e-3
        elif config.training.sde.lower() == 'vesde':            
            self.sde = sde_lib.cVESDE(sigma_min=config.model.sigma_min_x, sigma_max=config.model.sigma_max_x, N=config.model.num_scales, data_mean=data_mean)
            self.sampling_eps = 1e-5           
        else:
            raise NotImplementedError(f"SDE {config.training.sde} unknown.")
    
    def configure_loss_fn(self, config, train):
        loss_fn = get_scoreVAE_loss_fn(self.sde, train, 
                                        variational=config.training.variational, 
                                        likelihood_weighting=config.training.likelihood_weighting,
                                        eps=self.sampling_eps)
        return loss_fn
    
    def training_step(self, batch, batch_idx):
        loss = self.train_loss_fn(self.encoder, self.score_model, batch)
        self.log('train_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        return loss
    
    def validation_step(self, batch, batch_idx):
        loss = self.eval_loss_fn(self.encoder, self.score_model, batch)
        self.log('eval_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)

        if batch_idx == 1:
            reconstruction = self.sample(batch, p_steps=250)

            reconstruction =  reconstruction.cpu()
            grid_reconstruction = torchvision.utils.make_grid(reconstruction, nrow=int(np.sqrt(batch.size(0))), normalize=True, scale_each=True)
            self.logger.experiment.add_image('reconstruction', grid_reconstruction, self.current_epoch)
            
            batch = batch.cpu()
            grid_batch = torchvision.utils.make_grid(batch, nrow=int(np.sqrt(batch.size(0))), normalize=True, scale_each=True)
            self.logger.experiment.add_image('real', grid_batch)

            difference = torch.flatten(reconstruction, start_dim=1)-torch.flatten(batch, start_dim=1)
            L2norm = torch.linalg.vector_norm(difference, ord=2, dim=1)
            avg_L2norm = torch.mean(L2norm)

            self.log('reconstruction_loss', avg_L2norm, on_epoch=True, logger=True)

        return loss

    def sample(self, x, show_evolution=False, predictor='default', corrector='default', p_steps='default', c_steps='default', snr='default', denoise='default'):
        y = self.encoder(x)
        sampling_shape = [y.size(0)]+self.config.data.shape
        conditional_sampling_fn = get_conditional_sampling_fn(config=self.config, sde=self.sde, 
                                                              shape=sampling_shape, eps=self.sampling_eps, 
                                                              predictor=predictor, corrector=corrector, 
                                                              p_steps=p_steps, c_steps=c_steps, snr=snr, 
                                                              denoise=denoise, use_path=False)

        return conditional_sampling_fn(self.score_model, y, show_evolution)