import os
import re
import glob
import argparse
import pandas as pd
import numpy as np
import shutil  # Import shutil for copying files

def parse_summary_file(file_path):
    """
    Parse a summary file that contains multiple sections separated by blank lines.
    
    Returns:
        dict: Dictionary containing parsed data from each section
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    sections = {}
    current_section = None
    section_lines = []
    
    for line in content.split('\n'):
        line = line.strip()
        
        # Detect section headers
        if line.endswith(':') and not line.startswith('\t'):
            if current_section and section_lines:
                sections[current_section] = section_lines
            current_section = line[:-1]  # Remove trailing colon
            section_lines = []
        elif line:
            section_lines.append(line)
    
    # Add last section
    if current_section and section_lines:
        sections[current_section] = section_lines
    
    return sections

def extract_sample_info(sections):
    """Extract basic sample information from the Sample Summary section"""
    sample_info = {}
    
    if 'Sample Summary' in sections:
        for line in sections['Sample Summary']:
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    sample_info[key] = value
    
    return sample_info

def parse_interpretations(sections):
    """Parse the Interpretations Summary section"""
    interpretations = []
    
    if 'Interpretations Summary' in sections:
        lines = sections['Interpretations Summary']
        if len(lines) > 1:  # Skip header
            for line in lines[1:]:
                parts = [p.strip() for p in line.split('\t')]
                if len(parts) >= 3:
                    drug = parts[0]
                    variant = parts[1]
                    interpretation = parts[2]
                    
                    # Format interpretation
                    if variant and variant != 'No reportable variant detected':
                        drug_info = f"{drug}:{interpretation} ({variant})"
                    else:
                        drug_info = f"{drug}:{interpretation}"
                    
                    interpretations.append(drug_info)
    
    return "; ".join(interpretations) if interpretations else "No interpretation data"

def parse_variants(sections):
    """Parse the Variant Summary section"""
    variants = []
    
    if 'Variant Summary' in sections:
        lines = sections['Variant Summary']
        if len(lines) > 1:  # Has more than just header
            for line in lines[1:]:
                # Skip empty lines
                if not line or line.isspace():
                    continue
                    
                parts = [p.strip() for p in line.split('\t')]
                # Only process if we have enough fields and they're not empty
                if len(parts) >= 6 and parts[1]:  # Check gene_name field is not empty
                    gene_name = parts[1]
                    nucleotide_change = parts[2]
                    percent_alt = parts[5]
                    
                    variant_info = f"{gene_name} {nucleotide_change} ({percent_alt}%)"
                    variants.append(variant_info)
    
    return "; ".join(variants) if variants else "No variants detected"

def concatenate_txt_files(output_file="summary.tsv"):
    """
    Concatenate summary and stats files, combining drug resistance data per sample.
    
    Args:
        output_file (str): Name of the output summary file
    """
    
    # Find files using glob patterns
    summary_files = glob.glob("./*/*summary.txt")
    stats_files = glob.glob("./*/*stats.txt") 
    qc_stats_files = glob.glob("./QC/*/*stats.txt")
    
    if not (summary_files or stats_files or qc_stats_files):
        print("No files found matching the patterns")
        return
    
    print(f"Found files:")
    print(f"  Summary files: {len(summary_files)}")
    print(f"  Stats files: {len(stats_files)}")
    print(f"  QC stats files: {len(qc_stats_files)}")
    
    # List all found files
    for file in summary_files:
        print(f"    - {file}")
    for file in stats_files:
        print(f"    - {file}")
    for file in qc_stats_files:
        print(f"    - {file}")
    
    # Process summary files to create drug resistance summaries
    interpretation_summaries = {}
    variant_summaries = {}
    
    for file in summary_files:
        try:
            sections = parse_summary_file(file)
            sample_info = extract_sample_info(sections)
            
            if 'Sample ID' in sample_info:
                sample_id = sample_info['Sample ID']
                
                # Extract interpretations
                interpretation_summaries[sample_id] = parse_interpretations(sections)
                
                # Extract variants
                variant_summaries[sample_id] = parse_variants(sections)
            
            print(f"Processed summary file: {file}")
            
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    # Now process stats files and merge with summaries
    all_dataframes = []
    
    # Process main directory stats files
    for file in stats_files:
        try:
            df = pd.read_csv(file, sep='\t')
            
            # Add QC status
            df['QC_Status'] = 'Pass'
            
            # Add drug resistance summary if available
            if 'Sample ID' in df.columns:
                df['Drug_Resistance_Summary'] = df['Sample ID'].map(
                    lambda x: interpretation_summaries.get(x, 'No interpretation data')
                )
                df['Variant_Summary'] = df['Sample ID'].map(
                    lambda x: variant_summaries.get(x, 'No variants detected')
                )
            else:
                df['Drug_Resistance_Summary'] = 'No Sample ID found'
                df['Variant_Summary'] = 'No Sample ID found'
            
            all_dataframes.append(df)
            print(f"Processed stats file: {file} ({len(df)} rows)")
            
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    # Process QC stats files (failed samples)
    for file in qc_stats_files:
        try:
            df = pd.read_csv(file, sep='\t')
            
            # Add QC status
            df['QC_Status'] = 'Failed'
            
            # Add drug resistance summary if available
            if 'Sample ID' in df.columns:
                df['Drug_Resistance_Summary'] = df['Sample ID'].map(
                    lambda x: interpretation_summaries.get(x, 'QC Failed - No interpretation')
                )
                df['Variant_Summary'] = df['Sample ID'].map(
                    lambda x: variant_summaries.get(x, 'QC Failed - No variants')
                )
            else:
                df['Drug_Resistance_Summary'] = 'QC Failed - No Sample ID found'
                df['Variant_Summary'] = 'QC Failed - No Sample ID found'
            
            all_dataframes.append(df)
            print(f"Processed QC file: {file} ({len(df)} rows)")
            
        except Exception as e:
            print(f"Error reading {file}: {e}")

    if all_dataframes:
        # Concatenate all dataframes
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        
        # Remove Pipeline Version, Date columns if they exist
        columns_to_remove = ['Pipeline Version', 'Date']
        for col in columns_to_remove:
            if col in combined_df.columns:
                combined_df = combined_df.drop(columns=[col])
                print(f"Removed column: {col}")
        
        # Sort by _S* pattern in Sample ID if Sample ID column exists
        if 'Sample ID' in combined_df.columns:
            def extract_s_number(sample_id):
                """Extract the number after _S from sample ID for sorting"""
                match = re.search(r'_S(\d+)', str(sample_id))
                return int(match.group(1)) if match else float('inf')
            
            # Add temporary column for sorting
            combined_df['_sort_key'] = combined_df['Sample ID'].apply(extract_s_number)
            
            # Sort by the _S* number
            combined_df = combined_df.sort_values('_sort_key')
            
            # Remove the temporary sorting column
            combined_df = combined_df.drop(columns=['_sort_key']).reset_index(drop=True)
            
            print("Sorted samples by _S* pattern in Sample ID")
        
        # Save to output file
        combined_df.to_csv(output_file, sep='\t', index=False)
        
        print(f"\nSummary created: {output_file}")
        print(f"Total samples: {len(combined_df)}")
        print(f"Columns: {', '.join(combined_df.columns)}")
        
        # Show QC status summary
        if 'QC_Status' in combined_df.columns:
            print(f"\nQC status summary:")
            print(combined_df['QC_Status'].value_counts())
        
    else:
        print("No data to concatenate.")

def collect_labware_files(output_folder="Labware files needed"):
    """
    Collect specific files (*.lineage_report.txt, *_stats.txt, *_summary.txt) 
    from each sample into a single folder.
    
    Args:
        output_folder (str): Name of the output folder
    """
    # Create the output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Find files using glob patterns
    lineage_files = glob.glob("./*/*lineage_report.txt")
    stats_files = glob.glob("./*/*_stats.txt")
    summary_files = glob.glob("./*/*_summary.txt")
    
    # Combine all file lists
    all_files = lineage_files + stats_files + summary_files
    
    if not all_files:
        print("No files found matching the patterns")
        return
    
    print(f"Found {len(all_files)} files to copy:")
    for file in all_files:
        print(f"  - {file}")
    
    # Copy files to the output folder
    for file in all_files:
        try:
            # Copy the file to the output folder
            destination = os.path.join(output_folder, os.path.basename(file))
            if not os.path.exists(destination):  # Avoid overwriting files
                shutil.copy(file, destination)
                print(f"Copied: {file} -> {destination}")
            else:
                print(f"Skipped (already exists): {file}")
        except Exception as e:
            print(f"Error copying {file}: {e}")

def main():
    """Main function to run all tasks"""
    # Define default output file and folder
    output_file = "summary.tsv"
    output_folder = "Labware files needed"
    
    print("Starting concatenation of summary and stats files...")
    concatenate_txt_files(output_file=output_file)
    
    print("\nCollecting labware files...")
    collect_labware_files(output_folder=output_folder)
    
    print("\nAll tasks completed.")

if __name__ == "__main__":
    main()