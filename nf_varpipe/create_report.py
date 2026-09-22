#!/usr/bin/env python3

import platform

import yaml

"""The script accepts the stats, target coverage and final annotation file
It parses and merges those to the summary output file
"""


def sample_summary(stats_file):
    matrix = []
    with open(stats_file) as fh1:
        for lines in fh1:
            lined = lines.rstrip("\\r\\n").split("\\t")
            matrix.append(lined)

    output_lines = ["Sample Summary:"]

    output_lines.append(
        f"{matrix[0][0]}:\\t{matrix[1][0]}"
    )

    # Use only the portion before the first "-" as Sample Name
    sample_name = matrix[1][1].split("-")[0]
    output_lines.append(
        f"Sample Name:\\t{sample_name}"
    )

    output_lines.append(
        f"{matrix[0][5]}:\\t{matrix[1][5]}"
    )
    output_lines.append(
        f"{matrix[0][6]}:\\t{matrix[1][6]}"
    )
    output_lines.append(
        f"{matrix[0][7]}:\\t{matrix[1][7]}"
    )

    return output_lines


def target_coverage_summary(target_coverage_file):
    output_lines = ["\\n", "Target Coverage Summary:"]

    with open(target_coverage_file) as fh2:
        for lines in fh2:
            lined = lines.rstrip("\\r\\n").split("\\t")
            output_lines.append(f"{lined[4]}\\t{lined[2]}\\t{lined[3]}\\t{lined[6]}")

    return output_lines


def should_print_variant(lined):
    gene_name = lined[15]
    annotation = lined[7]
    position = int(lined[2])
    codon_pos = lined[14]
    nucleotide_change = lined[9]

    # Define gene filtering rules as a dictionary with functions
    gene_rules = {
        "rrl": lambda g, a, p, c, n: True,
        "ahpC": lambda g, a, p, c, n: True,
        "ahpC upstream": lambda g, a, p, c, n: True,

        "atpE": lambda g, a, p, c, n: a == "Non-synonymous",
        "pepQ": lambda g, a, p, c, n: a == "Non-synonymous",
        "mmpR": lambda g, a, p, c, n: a == "Non-synonymous",
        "inhA": lambda g, a, p, c, n: a == "Non-synonymous",
        "tlyA": lambda g, a, p, c, n: a == "Non-synonymous",

        "embB": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            and (
                p < 4246524
                or (4246586 < p < 4248314)
                or (4248329 < p < 4249653)
                or p > 4249692
            )
        ),

        "gyrA": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            and (
                ("-" in c and 87 < int(c.split("-")[1]) < 95)
                or ("-" not in c and 87 < int(c) < 95)
            )
        ),

        "gyrB": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            and (
                ("-" in c and 445 < int(c.split("-")[1]) < 508)
                or ("-" not in c and 445 < int(c) < 508)
            )
        ),

        "ethA": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            or (
                a == "Synonymous"
                and "1" in c
                and len(c) == 1
            )
        ),

        "katG": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            or (
                a == "Synonymous"
                and "1" in c
                and len(c) == 1
            )
        ),

        "eis": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            or a == "Non-Coding"
            or (
                a == "Synonymous"
                and "1" in c
                and len(c) == 1
            )
        ),

        "eis upstream": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            or a == "Non-Coding"
            or (
                a == "Synonymous"
                and "1" in c
                and len(c) == 1
            )
        ),

        "pncA": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            or a == "Non-Coding"
            or (
                a == "Synonymous"
                and "1" in c
                and len(c) == 1
            )
        ),

        "pncA upstream": lambda g, a, p, c, n: (
            a == "Non-synonymous"
            or a == "Non-Coding"
            or (
                a == "Synonymous"
                and "1" in c
                and len(c) == 1
            )
        ),

        "rrs": lambda g, a, p, c, n: (
            "1401" in n
            or "1402" in n
            or "1484" in n
        ),

        "fabG1": lambda g, a, p, c, n: (
            "c.-17" in n
            or "c.-15" in n
            or "c.-8" in n
            or c == "203"
        ),

        "fabG1 upstream": lambda g, a, p, c, n: (
            "c.-17" in n
            or "c.-15" in n
            or "c.-8" in n
            or c == "203"
        ),

        "rpoB": lambda g, a, p, c, n: (
            ("170" in c and a == "Non-synonymous")
            or ("-" not in c and 425 < int(c) < 453)
            or ("491" in c and a == "Non-synonymous")
            or (
                "-" in c
                and (
                    (
                        int(c.split("-")[0])
                        < 170
                        < int(c.split("-")[1])
                        and a == "Non-synonymous"
                    )
                    or (
                        453
                        > int(c.split("-")[1])
                        > 426
                    )
                    or (
                        int(c.split("-")[0]) < 426
                        and int(c.split("-")[1]) > 452
                    )
                    or (
                        int(c.split("-")[0])
                        < 491
                        < int(c.split("-")[1])
                        and a == "Non-synonymous"
                    )
                )
            )
        ),
    }

    # Check for gene names containing "rplC"
    if "rplC" in gene_name and annotation == "Non-synonymous":
        return True

    # For all other genes, check against the rules dictionary
    return gene_name in gene_rules and gene_rules[gene_name](
        gene_name,
        annotation,
        position,
        codon_pos,
        nucleotide_change,
    )


def variant_summary(annotation_file):
    output_lines = ["\\n", "Variant Summary:"]

    header = "\\t".join(
        [
            "POS",
            "Gene Name",
            "Nucleotide Change",
            "Amino acid Change",
            "Read Depth",
            "Percent Alt Allele",
            "Annotation",
        ]
    )
    output_lines.append(header)

    with open(annotation_file) as fh3:
        for lines in fh3:
            if lines.startswith("Sample ID"):
                continue

            lined = lines.rstrip("\\r\\n").split("\\t")

            if should_print_variant(lined):
                variant_line = "\\t".join(
                    [
                        lined[2],   # POS
                        lined[15],  # Gene Name
                        lined[9],   # Nucleotide Change
                        lined[11],  # Amino acid Change
                        lined[5],   # Read Depth
                        lined[6],   # Percent Alt Allele
                        lined[7],   # Annotation
                    ]
                )
                output_lines.append(variant_line)

    return output_lines


def write_summary(output_file, summary_lines):
    if output_file:
        for line in summary_lines:
            output_file.write(line + "\\n")
    else:
        for line in summary_lines:
            print(line)


def main():
    """Main function to execute the script."""

    stats = "${statsFile}"
    coverage = "${targetRegionCoverage}"
    annotation = "${drLociFinalAnnotation}"
    output_path = "summary.txt"

    # Collect all summary information
    sample_summary_lines = sample_summary(stats)
    coverage_summary_lines = target_coverage_summary(coverage)
    variant_summary_lines = variant_summary(annotation)

    # Combine all summary lines
    all_summary_lines = (
        sample_summary_lines
        + coverage_summary_lines
        + variant_summary_lines
    )

    # Write to file
    with open(output_path, "w") as output_file:
        write_summary(output_file, all_summary_lines)

    # Create versions file
    versions = {
        "${task.process}": {
            "python": platform.python_version(),
        }
    }

    with open("versions.yml", "w", encoding="utf-8") as f:
        f.write(yaml.dump(versions))


if __name__ == "__main__":
    main()