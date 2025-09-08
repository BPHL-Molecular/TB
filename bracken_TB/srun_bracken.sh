#!/usr/bin/bash
#SBATCH --account=bphl-umbrella
#SBATCH --qos=bphl-umbrella
#SBATCH --job-name=brackenTB
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20                   
#SBATCH --mem=200gb
#SBATCH --time=48:00:00
#SBATCH --output=bracken.%j.out
#SBATCH --error=bracken.err
#SBATCH --mail-user=<email>
#SBATCH --mail-type=FAIL,END

module load nextflow

APPTAINER_CACHEDIR=./
export APPTAINER_CACHEDIR

nextflow run main.nf --input "./fastqs/*_{R1_001,R2_001}.fastq.gz"

more results/bracken_out/*bracken >all_bracken.report