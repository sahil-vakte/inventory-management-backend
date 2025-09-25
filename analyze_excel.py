import pandas as pd
import sys

def analyze_excel(file_path):
    """Analyze the Excel file structure and content"""
    try:
        # Get all sheet names
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
        print(f"Excel file contains {len(sheet_names)} sheets:")
        for i, sheet in enumerate(sheet_names, 1):
            print(f"  {i}. {sheet}")
        
        print("\n" + "="*50)
        
        # Analyze each sheet
        for sheet_name in sheet_names:
            print(f"\n--- Sheet: {sheet_name} ---")
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                print(f"Shape: {df.shape}")
                print(f"Columns: {list(df.columns)}")
                
                # Show first few rows
                print("\nFirst 3 rows:")
                print(df.head(3).to_string())
                
                # Check for any non-null values to understand data structure
                print(f"\nNon-null counts:")
                print(df.count())
                
            except Exception as e:
                print(f"Error reading sheet {sheet_name}: {e}")
            
            print("\n" + "-"*30)
            
    except Exception as e:
        print(f"Error analyzing Excel file: {e}")

if __name__ == "__main__":
    analyze_excel("SOW_WIMS.xlsx")