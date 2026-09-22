echo "sample,fastq_1,fastq_2,fastq_3,fastq_4,fastq_5,fastq_6,fastq_7,fastq_8" > samplesheet.csv

for r1 in fastqs/*_1.fastq.gz; do
    r2=${r1/_1.fastq.gz/_2.fastq.gz}
    sample=$(basename "$r1" _1.fastq.gz)

    echo "$sample,$PWD/$r1,$PWD/$r2,,,,,," >> samplesheet.csv
done