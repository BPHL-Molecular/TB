echo "id,read1,read2" > samples.csv
for r1 in fastqs/*R1_001.fastq.gz; do
    r2=${r1/R1_001/R2_001}
    sample=$(basename $r1 _R1_001.fastq.gz)
    echo "$sample,./$r1,./$r2" >> samples.csv
done