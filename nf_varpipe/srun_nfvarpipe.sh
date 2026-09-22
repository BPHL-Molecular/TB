#!/bin/bash
#SBATCH --job-name=tbvarpipe
#SBATCH --output=tbvarpipe_%j.out
#SBATCH --error=tbvarpipe_%j.err
#SBATCH --time=10:00:00
#SBATCH --cpus-per-task=6
#SBATCH --mem=100gb
#SBATCH --account=bphl-umbrella
#SBATCH --qos=bphl-umbrella
#SBATCH --job-name=nf-varpipe
#SBATCH --ntasks=1
#SBATCH --mail-user=emailg@flhealth.gov
#SBATCH --mail-type=FAIL,END


module load apptainer nextflow/25.10.4

APPTAINER_CACHEDIR=./
export APPTAINER_CACHEDIR

nextflow run . \
  -profile singularity \
  -c local.config \
  --input samplesheet.csv \
  -work-dir ./work \
  --outdir ./results 