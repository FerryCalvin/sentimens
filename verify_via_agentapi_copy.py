import subprocess
import json
import os
import sys
import time
import pandas as pd
import shutil

LABEL_MAP_INT_TO_STR = {0: "Negatif", 1: "Netral", 2: "Positif"}
LABEL_MAP_STR_TO_INT = {
    "Negatif": 0,
    "Netral": 1,
    "Positif": 2,
    "negatif": 0,
    "netral": 1,
    "positif": 2
}

SYSTEM_INSTRUCTION = """Kamu adalah seorang Senior Data Annotator dan Pakar Linguistik Bahasa Indonesia (termasuk bahasa gaul, code-mixing, dan slang media sosial). Tugas utamamu adalah memverifikasi dan mengoreksi label klasifikasi sentimen dari sebuah dataset penelitian.

PANDUAN KLASIFIKASI SENTIMEN (SANGAT PENTING):
1. NEGATIF: Kalimat yang mengandung keluhan, kemarahan, umpatan/kata kasar (profanity), kritik pedas, ketidakpuasan, rumor buruk, atau SARKASME/SINDIRAN (contoh: memuji tetapi bermakna menjatuhkan/mengejek).
2. POSITIF: Kalimat yang mengandung pujian, dukungan, harapan, rasa syukur, optimisme, atau berita pencapaian/kemenangan (contoh: "Timnas menang", "IHSG Rebound").
3. NETRAL: Kalimat fakta, berita jurnalistik yang objektif tanpa opini penulis, kalimat tanya murni tanpa tendensi, atau pengumuman resmi.

ATURAN OUTPUT:
Kamu akan menerima daftar data dalam satu batch dengan format "ID: [Teks: ...] | [Label Lama: ...]".
Evaluasi "Label Lama" berdasarkan teksnya. Jika salah, perbaiki. Jika sudah benar, pertahankan.
Kamu WAJIB mengembalikan output HANYA dalam format JSON Object yang memetakan ID data ke string sentimen ("Positif", "Negatif", atau "Netral"). Dilarang memberikan teks penjelasan, markdown, atau basa-basi apa pun.
"""

EXE_PATH = r"C:\Users\USER\AppData\Local\Programs\antigravity\resources\bin\language_server.exe"

def call_agentapi(prompt, max_retries=5):
    cmd = [EXE_PATH, "agentapi", "new-conversation", "--model=flash", prompt]
    
    for attempt in range(max_retries):
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                stderr_str = result.stderr.decode('utf-8', errors='ignore')
                print(f"Error running agentapi (attempt {attempt+1}): {stderr_str}")
                time.sleep(10)
                continue
                
            stdout_str = result.stdout.decode('utf-8', errors='ignore')
            res_json = json.loads(stdout_str)
            conv_id = res_json["response"]["newConversation"]["conversationId"]
            return conv_id
        except Exception as e:
            print(f"Exception calling agentapi (attempt {attempt+1}): {e}")
            time.sleep(10)
            
    return None

def get_response(conv_id, max_wait=60):
    transcript_path = f"C:/Users/USER/.gemini/antigravity/brain/{conv_id}/.system_generated/logs/transcript.jsonl"
    
    for _ in range(max_wait * 2): # Poll every 0.5s
        if os.path.exists(transcript_path):
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line in lines:
                    if not line.strip():
                        continue
                    data = json.loads(line.strip())
                    if data.get("source") == "MODEL" and data.get("type") == "PLANNER_RESPONSE":
                        content = data.get("content", "").strip()
                        return content
            except Exception:
                pass
        time.sleep(0.5)
    return None

def clean_up_conv(conv_id):
    conv_dir = f"C:/Users/USER/.gemini/antigravity/brain/{conv_id}"
    for _ in range(5):
        try:
            if os.path.exists(conv_dir):
                shutil.rmtree(conv_dir)
            break
        except Exception:
            time.sleep(2)

def process_file(input_path, output_path, restart=False):
    print(f"Processing file: {input_path}")
    df = pd.read_csv(input_path)
    total_rows = len(df)
    print(f"Total rows in dataset: {total_rows}")
    
    # Check progress
    start_row = 0
    if restart and os.path.exists(output_path):
        print("Restart flagged. Deleting existing output file.")
        os.remove(output_path)
        
    if os.path.exists(output_path):
        try:
            df_out = pd.read_csv(output_path)
            start_row = len(df_out)
            print(f"Output file exists with {start_row} rows. Resuming...")
        except Exception as e:
            print(f"Error reading existing output: {e}. Overwriting.")
            start_row = 0
            
    i = start_row
    MAX_BATCH_SIZE = 65
    
    while i < total_rows:
        batch_df_indices = []
        while i < total_rows and len(batch_df_indices) < MAX_BATCH_SIZE:
            batch_df_indices.append(i)
            i += 1
            
        batch_df = df.iloc[batch_df_indices].copy()
        current_batch_size = len(batch_df)
        
        print(f"Processing rows {batch_df_indices[0]} to {batch_df_indices[-1]} ({current_batch_size} rows)...")
        
        # Format batch data
        data_lines = []
        for idx, row in batch_df.iterrows():
            text = str(row['text']).replace('\n', ' ').replace('\r', '').replace('"', "'")
            label_int = int(row['label'])
            label_str = LABEL_MAP_INT_TO_STR.get(label_int, "Netral")
            data_lines.append(f"ID {idx}: [Teks: {text}] | [Label Lama: {label_str}]")
            
        data_str = "\n".join(data_lines)
        prompt = f"""IMPORTANT: DO NOT CALL ANY TOOLS (such as run_command, list_dir, view_file, grep_search, etc.). You must NOT execute any tool calls under any circumstances. Simply evaluate the data and return the JSON directly.

{SYSTEM_INSTRUCTION}

Evaluasi dan koreksi {current_batch_size} baris data berikut:

{data_str}

Berikan hasil akhir HANYA dalam format JSON Object yang memetakan ID ke sentimennya ("Positif", "Negatif", atau "Netral"), seperti contoh berikut:
{{
  "{batch_df.index[0]}": "Netral",
  "{batch_df.index[-1]}": "Positif"
}}"""
        
        conv_id = call_agentapi(prompt)
        if not conv_id:
            print(f"Critical error: Failed to call agentapi for batch starting at row {batch_df_indices[0]}")
            sys.exit(1)
            
        response = get_response(conv_id)
        if not response:
            print(f"Critical error: Failed to get response for batch starting at row {batch_df_indices[0]}")
            clean_up_conv(conv_id)
            sys.exit(1)
            
        # Parse output
        try:
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            corrected_dict = json.loads(clean_response)
        except Exception as parse_err:
            print(f"Error parsing response JSON: {parse_err}")
            print(f"Response content: {response}")
            corrected_dict = {}
            
        corrected_labels = []
        for idx in batch_df.index:
            val = corrected_dict.get(str(idx)) or corrected_dict.get(int(idx))
            if val is None:
                print(f"Warning: Row {idx} not found in model response. Falling back to original label.")
                val = LABEL_MAP_INT_TO_STR.get(int(batch_df.loc[idx, 'label']), "Netral")
            
            corrected_labels.append(LABEL_MAP_STR_TO_INT.get(val, 1))
            
        batch_df['corrected_label'] = corrected_labels
        
        # Save batch
        if not os.path.exists(output_path):
            batch_df.to_csv(output_path, index=False)
        else:
            batch_df.to_csv(output_path, mode='a', header=False, index=False)
            
        print(f"Rows {batch_df_indices[0]} to {batch_df_indices[-1]} saved successfully.")
        clean_up_conv(conv_id)
        time.sleep(0.5)
        
    print(f"Verification complete for {input_path}!")
    
    # Print statistics
    final_df = pd.read_csv(output_path)
    print("Corrected Label Distribution:")
    print(final_df['corrected_label'].value_counts())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True, choices=["valid", "train"])
    parser.add_argument("--restart", action="store_true", help="Restart from beginning")
    args = parser.parse_args()
    
    datasets_dir = r"d:\SKRIPSI\sentimens\datasets_verif"
    
    if args.file == "valid":
        in_path = os.path.join(datasets_dir, "FINAL_VALID.csv")
        out_path = os.path.join(datasets_dir, "FINAL_VALID_verified.csv")
        process_file(in_path, out_path, restart=args.restart)
    elif args.file == "train":
        in_path = os.path.join(datasets_dir, "FINAL_TRAIN.csv")
        out_path = os.path.join(datasets_dir, "FINAL_TRAIN_verified.csv")
        process_file(in_path, out_path, restart=args.restart)
