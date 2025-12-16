#!/usr/bin/env bash

# ------------------------------------------------------------------
# NF-Core RNASeq Slurm job script (template)
#
# This script is intended to be used as a template in the Template
# Bash Script Editor. Fill in the variables below via the editor UI
# (or edit by hand) and submit to Slurm with:
#   sbatch run_nfcore_rnaseq_job.sh
# ------------------------------------------------------------------

# Short, descriptive project name (used in run name & logging)
PROJECT="{{ project | default('My RNASeq Project') }}"

# Directory where NF-Core RNASeq output will be written
OUT_DIR="{{ outdir | default('/data/project/worthey_lab/projects/my_project/analysis/bulk_rnaseq') }}"

# Directory where config files (including samples.csv) live
CONFIG_DIR="{{ config_dir | default('/data/project/worthey_lab/projects/my_project/analysis/bulk_rnaseq/configs') }}"

# Directory where pipeline run logs should be stored
LOGS_DIR="{{ logs_dir | default('/data/project/worthey_lab/projects/production_pipelines/logs/nf-core-rnaseq') }}"

# Slurm partition to run on (express, short, medium, long)
PARTITION="{{ partition | default('medium') }}"

# Path to Nextflow binary
NF_BINARY="{{ nextflow | default('/data/project/worthey_lab/tools/nextflow/nextflow-21.10.6/nextflow') }}"

# Path to custom NF-Core RNASeq config (cgds-nf-core-rnaseq.config)
NF_CONFIG="{{ rnaseq_config | default('/data/project/worthey_lab/tools/nextflow/nextflow-21.10.6/cgds-nf-core-rnaseq.config') }}"

# Path to the NF-Core RNASeq workflow directory
RNASEQ_WORKFLOW="{{ nf_core_workflow | default('/data/project/worthey_lab/tools/nf-core-rnaseq/nf-core-rnaseq-3.6/workflow') }}"

# Path to the samples.csv file
SAMPLES_CSV="{{ samples_csv | default('/data/project/worthey_lab/projects/my_project/analysis/bulk_rnaseq/configs/samples.csv') }}"

# Reference genome and annotation paths
REF_GENOME="{{ ref_genome | default('/data/project/worthey_lab/datasets_central/human_reference_genome/processed/GRCh38/no_alt_rel20190408/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna') }}"
TRANSCRIPT_FASTA="{{ transcript_fasta | default('/data/project/worthey_lab/temp_datasets_central/brandon/gencode_v40_trx/GRCh38_no_alt_analysis_set.matched_transcripts.fa') }}"
GTF="{{ gtf | default('/data/project/worthey_lab/temp_datasets_central/brandon/gencode_v40_trx/gencode.v40.annotation.gtf') }}"
STAR_INDEX="{{ star_index | default('/data/project/worthey_lab/temp_datasets_central/brandon/RNAseqRefIndex/GRCh38_gencodev40_STAR') }}"

# Whether to clean up intermediate files after a successful run (true/false)
CLEANUP="{{ cleanup | default('true') }}"

# ------------------------------------------------------------------
# Derived paths
# ------------------------------------------------------------------

WORK_DIR="${OUT_DIR}/work"
RUN_REPORT="${OUT_DIR}/nf-core-rnaseq-run-report.html"

# Create a unique run name using project + timestamp
PRESENT_DATETIME=$(date +"%Y_%m_%d_%H_%M")
WORKFLOW_RUN_NAME="nfcore_rnaseq_${PROJECT// /_}_${PRESENT_DATETIME}"

# Ensure key directories exist
mkdir -p "${OUT_DIR}" "${CONFIG_DIR}" "${LOGS_DIR}" "${WORK_DIR}"

# ------------------------------------------------------------------
# Slurm settings
# ------------------------------------------------------------------
# See: https://slurm.schedmd.com/sbatch.html for details

#SBATCH --job-name={{ job_name | default('nfcore_rnaseq') }}
#SBATCH --cpus-per-task={{ cpus_per_task | default('2') }}
#SBATCH --mem-per-cpu={{ mem_per_cpu | default('8G') }}
#SBATCH --partition={{ partition | default('medium') }}
#SBATCH --output={{ logs_dir | default(LOGS_DIR) }}/nf-core-rnaseq.user%u.job%j.out
#SBATCH --error={{ logs_dir | default(LOGS_DIR) }}/nf-core-rnaseq.user%u.job%j.err

# ------------------------------------------------------------------
# Environment configuration for Nextflow on Slurm
# ------------------------------------------------------------------

# Prevent local execution of Nextflow tasks/jobs
export NXF_EXECUTOR="slurm"
export NXF_OPTS="-Xms1G -Xmx14G"
export NXF_ANSI_LOG=false

# Scratch / temp locations (customize if needed)
export NXF_TEMP="${USER_SCRATCH:-/tmp/$USER}"
export NXF_SINGULARITY_CACHEDIR="/data/project/worthey_lab/tools/nextflow/nextflow-singularity-image-cache"
export TMPDIR="${NXF_TEMP}"
export SINGULARITY_TMPDIR="${NXF_TEMP}"

# Nextflow, config, workflow, and input locations
INPUT="${SAMPLES_CSV}"

echo "Running NF-Core RNASeq pipeline with following setup:"
echo "    Project:           ${PROJECT}"
echo "    Nextflow:          ${NF_BINARY}"
echo "    NF-Core RNA-Seq:   ${RNASEQ_WORKFLOW}"
echo "    Workflow Config:   ${NF_CONFIG}"
echo "    Samples Config:    ${INPUT}"
echo "    Output Directory:  ${OUT_DIR}"
echo "    Work Directory:    ${WORK_DIR}"
echo "    Run Report:        ${RUN_REPORT}"
echo "    Slurm Partition:   ${PARTITION}"

# ------------------------------------------------------------------
# Run the NF-Core RNASeq workflow
# ------------------------------------------------------------------
# Note: Nextflow stores its .nextflow metadata in the launch directory.
# We use the logs directory as the launch directory so logs are centralized.

cd "${LOGS_DIR}" || {
  echo "ERROR: Failed to cd to logs directory: ${LOGS_DIR}"
  exit 1
}

module load Singularity/3.5.2-GCC-5.4.0-2.26 2>/dev/null || true

"${NF_BINARY}" run "${RNASEQ_WORKFLOW}" \
    -c "${NF_CONFIG}" \
    -profile cheaha \
    -ansi-log false \
    -name "${WORKFLOW_RUN_NAME}" \
    -with-report "${RUN_REPORT}" \
    -work-dir "${WORK_DIR}" \
    --input "${INPUT}" \
    --outdir "${OUT_DIR}" \
    --aligner star_salmon \
    --pseudo_aligner salmon \
    --fasta "${REF_GENOME}" \
    --gtf "${GTF}" \
    --transcript_fasta "${TRANSCRIPT_FASTA}" \
    --star_index "${STAR_INDEX}"

EXIT_CODE=$?

if [[ "${CLEANUP}" == "true" ]]; then
  if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo "Successful run detected, executing intermediate file clean up..."
    "${NF_BINARY}" clean "${WORKFLOW_RUN_NAME}" -k -f || echo "Nextflow clean failed; continuing."
  else
    echo "Error in workflow detected (exit code ${EXIT_CODE}), skipping cleaning to allow for workflow resume."
  fi
else
  echo "Cleanup disabled (CLEANUP=${CLEANUP})."
fi

exit ${EXIT_CODE}
