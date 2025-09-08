#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

/*
========================================================================================
    PARAMETERS
========================================================================================
*/
params.input         = null
params.kraken_db     = "/blue/bphl-florida/share/kraken_bracken_database/PlusPF"
params.read_length   = 300              // Options: 50, 75, 100, 150, 250, 300
params.outdir        = "./results"

/*
========================================================================================
    PROCESSES
========================================================================================
*/
process kraken2 {
    tag "$id"
    publishDir "${params.outdir}/kraken_out", mode: 'copy'
    
    input:
    tuple val(id), path(reads)
    
    output:
    tuple val(id), path("*.kraken2.out"), emit: output
    tuple val(id), path("*.kraken2.report"), emit: report
    
    script:
    def prefix = "${id}"
    def paired = "--paired"  // Always paired since we're using paired input pattern
    
    """
    kraken2 \\
        --db ${params.kraken_db} \\
        --report ${prefix}.kraken2.report \\
        --output ${prefix}.kraken2.out \\
        ${paired} \\
        ${reads}
    """
}

process bracken {
    tag "$id"
    publishDir "${params.outdir}/bracken_out", mode: 'copy'
    
    input:
    tuple val(id), path(kraken_report)
    
    output:
    tuple val(id), path("*.bracken"), emit: output
    tuple val(id), path("*.bracken.report"), emit: report
    
    script:
    def prefix = "${id}"
    
    """
    bracken \\
        -d ${params.kraken_db} \\
        -i ${kraken_report} \\
        -o ${prefix}.bracken \\
        -w ${prefix}.bracken.report \\
        -r ${params.read_length} \\
        -l S \\
        -t 1000
    """
}

/*
========================================================================================
    WORKFLOW
========================================================================================
*/
workflow {
    
    // Create input channel from paired FASTQ files
    Channel
        .fromFilePairs(params.input)
        .map { sample, files ->
            [sample, files]
        }
        .set { ch_input }
    
    // Run Kraken2
    kraken2(ch_input)
    
    // Run Bracken
    bracken(kraken2.out.report)
}