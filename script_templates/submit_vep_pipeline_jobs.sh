#!/usr/bin/env bash

# Script to submit jobs to a VEP pipeline for a list of VCF files using Slurm.
# This script submits all jobs to Slurm and logs the submission.
#
# Usage (after filling variables via the template editor):
#   ./submit_vep_pipeline_jobs.sh

# Path to the VEP pipeline run script
VEP_SCRIPT="{{ vep_script | default('/data/user/home/shutchin/worthey/projects/experimental_pipelines/sdhutchins/vep-pipeline/src/run_pipeline.sh') }}"

# Path to a text file containing one VCF path per line
VCF_LIST="{{ vcf_list | default('/data/project/worthey_lab/projects/PAH_RHamid/support/pah_vcfs.txt') }}"

# Base output directory where per-sample subdirectories will be created
OUTPUT_DIR="{{ output_dir | default('/data/project/worthey_lab/projects/PAH_RHamid/analysis/pah-linkage-analysis/data/interim') }}"

# Datasets configuration file for the VEP pipeline
DATASETS_CONFIG="{{ datasets_config | default('/data/project/worthey_lab/projects/experimental_pipelines/sdhutchins/vep-pipeline/configs/datasets.yaml') }}"

# Directory of the VEP pipeline repo (used for cd before running jobs)
PIPELINE_DIR="{{ pipeline_dir | default('/data/project/worthey_lab/projects/experimental_pipelines/sdhutchins/vep-pipeline') }}"

# Validate required paths are provided
if [[ -z "$VCF_LIST" || -z "$OUTPUT_DIR" || -z "$DATASETS_CONFIG" || -z "$VEP_SCRIPT" || -z "$PIPELINE_DIR" ]]; then
    echo "All variables are required."
    echo "Please ensure VCF_LIST, OUTPUT_DIR, DATASETS_CONFIG, VEP_SCRIPT, and PIPELINE_DIR are set."
    exit 1
fi

# Iterate over the VCF file list and submit jobs
while IFS= read -r VCF_FILE; do
    [[ -z "$VCF_FILE" ]] && continue

    VCF_BASENAME=$(basename "$VCF_FILE" .vcf.gz)
    INDIVIDUAL_OUT_DIR="${OUTPUT_DIR}/${VCF_BASENAME}"
    mkdir -p "$INDIVIDUAL_OUT_DIR"

    # Change directory to VEP pipeline
    cd "$PIPELINE_DIR" || {
        echo "Failed to cd to $PIPELINE_DIR"
        exit 1
    }

    # Submit the job with the VEP pipeline script, passing required arguments
    JOB_SUBMISSION=$("$VEP_SCRIPT" -s -v "$VCF_FILE" -o "$INDIVIDUAL_OUT_DIR" -d "$DATASETS_CONFIG")
    echo "Submitted: $JOB_SUBMISSION"
done < "$VCF_LIST"
