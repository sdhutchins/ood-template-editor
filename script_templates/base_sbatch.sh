#!/bin/bash
#SBATCH --job-name={{ job_name | default('my_job') }}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={{ num_cpus | default('1') }}
#SBATCH --mem={{ mem_per_cpu | default('4G') }}
#SBATCH --partition={{ partition | default('express') }}
#SBATCH --time={{ walltime | default('01:00:00') }}
#SBATCH --output={{ stdout_file | default('%x_%j.out') }}
#SBATCH --error={{ stderr_file | default('%x_%j.err') }}

echo "Running job: $SLURM_JOB_NAME"
echo "Job ID: $SLURM_JOB_ID"
echo "Running on node: $(hostname)"

# Your commands go here. For example:
# module load Python
# python my_script.py
