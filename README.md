# TB
## A directory for our extensions to CDC's varpipe platform 

### Run varpipe_summary.py to better summarize varpipe's output

Prerequisites:
- Completed VarPipe pipeline run
- Python environment with pandas installed (conda install -c conda-forge pandas)
- Access to the pipeline output directory

Copy the varpipe_summary.py script into your pipeline output directory:
```bash
cp /path/to/varpipe_summary.py /path/to/your/output/directory/
cd /path/to/your/output/directory/
```

```bash
python varpipe_summary.py
```
Output
- The script generates a summary.tsv file with the following columns:

Sample ID/
Sample Name/
Percent Reads Mapped/
Average Genome Coverage Depth/
Percent Reference Genome Covered/
Coverage Drop/
QC_Status/
Drug_Resistance_Summary/

### Using bracken_TB to check failed TB samples for contamination
The bracken_TB tool provides species-level taxonomic classification to help identify potential contaminants in failed samples.

Prerequisites:
- Download the bracken_TB folder
- Nextflow needed (if not using HiPerGator)
- Access to the failed TB samples fastq.gz files

Copy the failed TB samples fastq.gz files into the fastqs folder;

Then 
```bash
sbatch srun_bracken.sh
```
Or (if not using HiPerGator)

```bash
nextflow run main.nf --input "./fastqs/*_{R1_001,R2_001}.fastq.gz"
more results/bracken_out/*bracken >all_bracken.report
```
Output
- This section generates a report: all_bracken.report, which includes all the samples' bracken results.

### Run TBprofiler to check more loci

Prerequisites:
- Create conda environment:
 $ conda create -n TBprofiler python=3.8
 $ conda activate TBprofiler
 $ conda install -c bioconda tb-profiler

If not working:
 $ conda create --name TBprofiler --file ./conda/linux-latest.txt
Then
 $ conda activate TBprofiler

Setup:

- Copy TB sample fastq.gz files into the fastqs/ folder
- Copy samplesheet.sh and tbprofiler.sh into the TBProfiler/ folder
- Create sample sheet file
 
```bash
bash samplesheet.sh
```
Run analysis:
```bash
sbatch tbprofiler.sh
```

Generate summary:
```bash
tb-profiler collate

```
Output
- Individual sample reports in results/ directory
- The collate function generates tbprofiler.txt under TBProfiler/, which summarize all the drug resistance infomation.
