#!/usr/bin/bash
#SBATCH --account=bphl-umbrella
#SBATCH --qos=bphl-umbrella
#SBATCH --job-name=TB
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20                   
#SBATCH --mem=200gb
#SBATCH --time=48:00:00
#SBATCH --output=tbprofiler.%j.out
#SBATCH --error=tbprofiler.err
#SBATCH --mail-user=yi.huang@flhealth.gov
#SBATCH --mail-type=FAIL,END

tb-profiler batch --csv samples.csv --args "--csv --af 0.1 --depth 10 --caller gatk" 
