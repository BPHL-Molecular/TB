import os
import re
import glob
import argparse
import pandas as pd
import numpy as np

def concatenate_txt_files(output_file="summary.tsv"):
    """
    Concatenate interpretation and stats files, combining drug resistance data per sample.
    
    Args:
        output_file (str): Name of the output summary file
    """
    
    # Find files using glob patterns
    interpretation_files = glob.glob("./*/*interpretation.txt")
    stats_files = glob.glob("./*/*stats.txt") 
    qc_stats_files = glob.glob("./QC/*/*stats.txt")
    
    if not (interpretation_files or stats_files or qc_stats_files):
        print("No files found matching the patterns")
        return
    
    print(f"Found files:")
    print(f"  Interpretation files: {len(interpretation_files)}")
    print(f"  Stats files: {len(stats_files)}")
    print(f"  QC stats files: {len(qc_stats_files)}")
    
    # List all found files
    for file in interpretation_files:
        print(f"    - {file}")
    for file in stats_files:
        print(f"    - {file}")
    for file in qc_stats_files:
        print(f"    - {file}")
    
    # Process interpretation files to create drug resistance summaries
    interpretation_summaries = {}
    
    for file in interpretation_files:
        try:
            df = pd.read_csv(file, sep='\t')
            
            if 'Sample ID' in df.columns and 'Drug' in df.columns and 'Interpretation' in df.columns:
                # Group by Sample ID and create drug resistance summary
                for sample_id in df['Sample ID'].unique():
                    sample_data = df[df['Sample ID'] == sample_id]
                    
                    # Create summary of all drugs and their interpretations
                    drug_summary = []
                    for _, row in sample_data.iterrows():
                        drug = row['Drug']
                        variant = row.get('Variant', 'N/A')
                        interpretation = row['Interpretation']
                        
                        # Format: Drug: Interpretation (Variant info if available)
                        if variant and variant != 'No reportable variant detected':
                            drug_info = f"{interpretation} ({variant})"
                        else:
                            drug_info = f"{interpretation}"
                        
                        drug_summary.append(drug_info)
                    
                    # Join all drug information with semicolons
                    interpretation_summaries[sample_id] = "; ".join(drug_summary)
            
            print(f"Processed interpretation file: {file}")
            
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    # Now process stats files and merge with interpretation summaries
    all_dataframes = []
    
    # Process main directory stats files
    for file in stats_files:
        try:
            df = pd.read_csv(file, sep='\t')
            
            # Add QC status and source info
            df['QC_Status'] = 'Pass'
           
            
            # Add drug resistance summary if available
            if 'Sample ID' in df.columns:
                df['Drug_Resistance_Summary'] = df['Sample ID'].map(
                    lambda x: interpretation_summaries.get(x, 'No interpretation data')
                )
            else:
                df['Drug_Resistance_Summary'] = 'No Sample ID found'
            
            all_dataframes.append(df)
            print(f"Processed stats file: {file} ({len(df)} rows)")
            
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    # Process QC stats files (failed samples)
    for file in qc_stats_files:
        try:
            df = pd.read_csv(file, sep='\t')
            
            # Add QC status and source info
            df['QC_Status'] = 'Failed'
                        
            # Add drug resistance summary if available
            if 'Sample ID' in df.columns:
                df['Drug_Resistance_Summary'] = df['Sample ID'].map(
                    lambda x: interpretation_summaries.get(x, 'QC Failed - No interpretation')
                )
            else:
                df['Drug_Resistance_Summary'] = 'QC Failed - No Sample ID found'
            
            all_dataframes.append(df)
            print(f"Processed QC file: {file} ({len(df)} rows)")
            
        except Exception as e:
            print(f"Error reading {file}: {e}")

    if all_dataframes:
        # Concatenate all dataframes
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        
        # Remove Pipeline Version, Date, and Source_File columns if they exist
        columns_to_remove = ['Pipeline Version', 'Date']
        for col in columns_to_remove:
            if col in combined_df.columns:
                combined_df = combined_df.drop(columns=[col])
                print(f"Removed column: {col}")
        
        # Sort by _S* pattern in Sample ID if Sample ID column exists
        if 'Sample ID' in combined_df.columns:
            def extract_s_number(sample_id):
                """Extract the number after _S from sample ID for sorting"""
                import re
                match = re.search(r'_S(\d+)', str(sample_id))
                return int(match.group(1)) if match else float('inf')  # Put non-matching at end
            
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

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(description='Concatenate interpretation and stats txt files')
    parser.add_argument('-o', '--output', default='summary.tsv', 
                       help='Output file name (default: summary.tsv)')
    
    args = parser.parse_args()
    
    concatenate_txt_files(output_file=args.output)

if __name__ == "__main__":
    # Run the main function
    main()
