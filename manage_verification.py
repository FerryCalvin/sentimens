import os
import sys
import json
import pandas as pd

INPUT_PATH = r"d:\SKRIPSI\sentimens\datasets_verif\FINAL_TEST.csv"
OUTPUT_PATH = r"d:\SKRIPSI\sentimens\datasets_verif\FINAL_TEST_verified.csv"

def read_chunk(start, count):
    if not os.path.exists(INPUT_PATH):
        print(json.dumps({"error": f"Input file not found at {INPUT_PATH}"}))
        return
    df = pd.read_csv(INPUT_PATH)
    chunk = df.iloc[start:start+count]
    result = []
    for idx, row in chunk.iterrows():
        result.append({
            "idx": int(idx),
            "text": str(row["text"]),
            "label": int(row["label"])
        })
    print(json.dumps(result))

def write_chunk(start, count, corrected_labels_str):
    try:
        corrected_labels = json.loads(corrected_labels_str)
    except Exception as e:
        print(json.dumps({"error": f"Failed to parse corrected labels JSON: {e}"}))
        return
        
    if not os.path.exists(INPUT_PATH):
        print(json.dumps({"error": f"Input file not found at {INPUT_PATH}"}))
        return
        
    df_input = pd.read_csv(INPUT_PATH)
    chunk = df_input.iloc[start:start+count].copy()
    
    if len(corrected_labels) != len(chunk):
        print(json.dumps({"error": f"Length mismatch! Expected {len(chunk)} labels, got {len(corrected_labels)}"}))
        return
        
    chunk["corrected_label"] = corrected_labels
    
    # We want output columns to be: text, label, corrected_label
    output_chunk = chunk[["text", "label", "corrected_label"]]
    
    if start == 0:
        # Overwrite/Create new file
        output_chunk.to_csv(OUTPUT_PATH, index=False)
        print(json.dumps({"success": f"Created new verified file with {len(output_chunk)} rows."}))
    else:
        # Append to existing file
        if not os.path.exists(OUTPUT_PATH):
            print(json.dumps({"error": "Output file does not exist, but start index > 0."}))
            return
        output_chunk.to_csv(OUTPUT_PATH, mode='a', header=False, index=False)
        print(json.dumps({"success": f"Appended {len(output_chunk)} rows to verified file."}))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage_verification.py [read|write] ...")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "read":
        start = int(sys.argv[2])
        count = int(sys.argv[3])
        read_chunk(start, count)
    elif cmd == "write":
        start = int(sys.argv[2])
        count = int(sys.argv[3])
        labels = sys.argv[4]
        write_chunk(start, count, labels)
