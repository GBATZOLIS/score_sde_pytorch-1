#!/bin/bash 
#! Name of the job: 
#SBATCH -J non_uniform_0.75 
#! Which project should be charged (NB Wilkes2 projects end in '-GPU'): 
#SBATCH --account SCHOENLIEB-SL3-GPU 
#! How many whole nodes should be allocated? 
#SBATCH --nodes=1 
#! How many (MPI) tasks will there be in total? 
#! Note probably this should not exceed the total number of GPUs in use. 
#SBATCH --ntasks=1 
#! Specify the number of GPUs per node (between 1 and 4; must be 4 if nodes>1). 
#! Note that the job submission script will enforce no more than 32 cpus per GPU. 
#SBATCH --gres=gpu:1 
#! How much wallclock time will be required? 
#SBATCH --time=12:00:00 
#! What types of email messages do you wish to receive? 
#SBATCH --mail-type=begin        # send email when job begins 
#SBATCH --mail-type=end 
#SBATCH --mail-user=js2164@cam.ac.uk 
#! Do not change: 
#SBATCH -p ampere 
 
. /etc/profile.d/modules.sh                # Leave this line (enables the module command) 
module purge                               # Removes all modules still loaded 
module load rhel8/default-amp              # REQUIRED - loads the basic environment 
module unload miniconda/3 
module load cuda/11.4 
module list 
nvidia-smi 
source /home/js2164/.bashrc 
conda activate score_sde 
REPO=/rds/user/js2164/hpc-work/repos/score_sde_pytorch/ 
 
cd /home/js2164/rds/hpc-work/repos/score_sde_pytorch/ 
python main.py --config configs/ksphere/N_1/non_uniform_075.py \ 
 --mode train \ 
--log_path logs/ksphere/dim_10/n_1/random_isometry/ \ 
--log_name non_uniform_0.75 \ 