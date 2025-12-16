#!/usr/bin/env bash
#SBATCH --job-name={{ job_name | default('echtvar-filt') }}
#SBATCH --output={{ stdout_file | default('echtvar-filt-%A-%a.log') }}
#SBATCH --error={{ stderr_file | default('echtvar-filt-%A-%a.err') }}
#SBATCH --cpus-per-task={{ cpus_per_task | default('4') }}
#SBATCH --mem={{ mem_per_task | default('12G') }}
#SBATCH --partition={{ partition | default('express') }}
#SBATCH --array={{ array_range | default('1-12') }}

pwd
hostname
date

# Reference genome FASTA used by bcftools norm
REF_GENOME="{{ ref_genome | default('/data/project/worthey_lab/datasets_central/human_reference_genome/processed/GRCh38/no_alt_rel20190408/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna') }}"

# Text file containing one VCF path per line
VCF_LIST="{{ vcf_list | default('/data/project/worthey_lab/projects/PAH_RHamid/support/echtvar-filtering/pah-vcfs.txt') }}"

# Base output directory where filtered VCFs will be written
OUTDIR="{{ output_dir | default('/data/project/worthey_lab/projects/PAH_RHamid/support/echtvar-filtering/') }}"

# Path to the echtvar archive (gnomAD 3.1.2) used for annotation
ECHTVAR_ARCHIVE="{{ echtvar_archive | default('gnomad.v3.1.2.echtvar.v2.zip') }}"

# Filter expression applied by echtvar (on gnomad_af)
ECHTVAR_EXPR="{{ echtvar_expr | default('gnomad_af < 0.1') }}"

# Directory of the echtvar tools checkout (cd here before running)
ECHTVAR_DIR="{{ echtvar_dir | default('/data/project/worthey_lab/projects/experimental_pipelines/brandon_test/tools/echtvar') }}"

# Number of runs (VCFs) to process per array task
PER_TASK={{ per_task | default('2') }}

# Total number of VCFs in the list (used to cap END_NUM)
TOTAL_RUNS={{ total_runs | default('23') }}

# Conda environment name that has bcftools + echtvar installed
CONDA_ENV="{{ conda_env | default('bcftools') }}"

# Enable conda, assumes Anaconda module is available and env exists
module load Anaconda3 2>/dev/null || module load Anaconda/3 2>/dev/null || true
eval "$(conda shell.bash hook)"
conda activate "${CONDA_ENV}"

# Change to the echtvar tools directory
cd "${ECHTVAR_DIR}"

set -eo pipefail

# Array task range calculation (each array task processes PER_TASK VCFs)
START_NUM=$(( (SLURM_ARRAY_TASK_ID - 1) * PER_TASK + 1 ))
END_NUM=$(( SLURM_ARRAY_TASK_ID * PER_TASK ))
if [ "${END_NUM}" -gt "${TOTAL_RUNS}" ]; then
    END_NUM="${TOTAL_RUNS}"
fi

echo "This is task ${SLURM_ARRAY_TASK_ID}, which will do runs ${START_NUM} to ${END_NUM}"

for (( run = START_NUM; run <= END_NUM; run++ )); do
    # Get VCF file path to process from the list
    vcf=$(sed -n "${run}p" "${VCF_LIST}")
    if [[ -z "${vcf}" ]]; then
        echo "No VCF found for line ${run} in ${VCF_LIST}, skipping..."
        continue
    fi

    # Sample name is the parent directory two levels up from the VCF
    smp=$(dirname "${vcf}" | xargs dirname | xargs basename)
    outdir="${OUTDIR%/}/"
    filtvcf="${outdir}${smp}.gnomad-af-filt.vcf.gz"

    mkdir -p "${outdir}"

    echo "============================================================================================================="
    echo "Processing ${vcf} for task ${SLURM_ARRAY_TASK_ID} run ${run}:"
    echo "  filtered vcf: ${filtvcf}"

    # Run bcftools + echtvar to annotate gnomAD AF and filter variants
    bcftools norm -m- -w 10000 -f "${REF_GENOME}" -O v "${vcf}" \
      | echtvar anno -i "${ECHTVAR_EXPR}" -e "${ECHTVAR_ARCHIVE}" - "${filtvcf}"

    echo "VCF AF filtering complete for ${vcf}"
    echo ""
done
