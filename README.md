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
