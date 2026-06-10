import os
import sys
import time
import json
import argparse
import pandas as pd
import requests
from dotenv import load_dotenv

# Define mappings
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

def call_gemini_api(prompt, api_key, model_name="gemini-1.5-flash", max_retries=5):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    # We combine system instruction with user prompt since systemInstruction parameter is sometimes model-dependent in older API versions
    full_prompt = f"{SYSTEM_INSTRUCTION}\n\n{prompt}"
    
    payload = {
        "contents": [{
            "parts": [{"text": full_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 429:
                # Try to parse the exact retry delay from the error details
                sleep_time = (2 ** attempt) * 10 + 5
                try:
                    res_json = response.json()
                    details = res_json.get("error", {}).get("details", [])
                    for detail in details:
                        if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                            delay_str = detail.get("retryDelay", "")
                            if delay_str.endswith("s"):
                                sleep_time = float(delay_str[:-1]) + 2.0  # Add 2 seconds buffer
                                break
                except Exception as parse_err:
                    pass
                print(f"Rate limit hit (429). Sleeping for {sleep_time}s...")
                time.sleep(sleep_time)
                continue
                
            response.raise_for_status()
            res_json = response.json()
            
            # Extract text response safely
            candidates = res_json.get("candidates", [])
            if not candidates:
                raise ValueError(f"No candidates returned by API. Response: {res_json}")
                
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise ValueError(f"No parts in content. Response: {res_json}")
                
            text_response = parts[0].get("text", "").strip()
            
            # Strip markdown json block if present
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.startswith("```"):
                text_response = text_response[3:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]
            text_response = text_response.strip()
            
            try:
                labels = json.loads(text_response)
            except json.JSONDecodeError as je:
                print(f"JSON Decode Error: {je}")
                print(f"Raw response (length {len(text_response)}):")
                print(text_response)
                print(f"Full response JSON: {res_json}")
                raise je
                
            if not isinstance(labels, (list, dict)):
                raise ValueError(f"Response is not a JSON list or dict: {text_response}")
                
            return labels
            
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise e
            sleep_time = (2 ** attempt) * 2 + 1
            print(f"Retrying in {sleep_time}s...")
            time.sleep(sleep_time)

def verify_dataset(input_path, output_path, api_key, model_name, batch_size=50, limit=None, delay=2.0):
    print(f"Reading input file: {input_path}")
    df_input = pd.read_csv(input_path)
    
    # Handle optional limit
    if limit is not None:
        df_input = df_input.head(limit)
    
    total_rows = len(df_input)
    print(f"Total rows to process: {total_rows}")
    
    # Load existing progress if output file exists
    start_row = 0
    if os.path.exists(output_path):
        try:
            df_existing = pd.read_csv(output_path)
            start_row = len(df_existing)
            print(f"Output file found with {start_row} rows. Resuming from index {start_row}...")
        except Exception as e:
            print(f"Error reading existing output file: {e}. Overwriting instead.")
            start_row = 0
            
    # Open file in append or write mode
    is_resume = start_row > 0
    
    for i in range(start_row, total_rows, batch_size):
        end_idx = min(i + batch_size, total_rows)
        batch_df = df_input.iloc[i:end_idx].copy()
        current_batch_size = len(batch_df)
        
        print(f"Processing batch {i // batch_size + 1}: rows {i} to {end_idx - 1} ({current_batch_size} rows)...")
        
        # Format prompt
        data_lines = []
        for idx, row in batch_df.iterrows():
            text = str(row['text']).replace('\n', ' ')
            old_label_int = int(row['label'])
            old_label_str = LABEL_MAP_INT_TO_STR.get(old_label_int, "Netral")
            data_lines.append(f"ID {idx}: [Teks: {text}] | [Label Lama: {old_label_str}]")
            
        data_str = "\n".join(data_lines)
        prompt = f"Evaluasi dan koreksi {current_batch_size} baris data berikut:\n\n{data_str}\n\nBerikan hasil akhir HANYA dalam format JSON Object yang memetakan ID ke sentimennya (\"Positif\", \"Negatif\", atau \"Netral\"), seperti contoh berikut:\n{{\n  \"{batch_df.index[0]}\": \"Netral\",\n  \"{batch_df.index[-1]}\": \"Positif\"\n}}"
        
        # Call API
        try:
            corrected_dict = call_gemini_api(prompt, api_key, model_name)
            
            # Map strings back using index
            corrected_labels_str = []
            
            # If the API returned a list instead of a dict by mistake, fallback
            if isinstance(corrected_dict, list):
                print("Warning: API returned list instead of dict. Attempting positional alignment...")
                if len(corrected_dict) == current_batch_size:
                    corrected_labels_str = corrected_dict
                else:
                    corrected_dict = {}
            
            if not corrected_labels_str:
                for idx in batch_df.index:
                    # Check string key and int key
                    val = corrected_dict.get(str(idx)) or corrected_dict.get(int(idx))
                    if val is None:
                        # Fallback to single call for this specific missing row
                        print(f"Warning: Label for ID {idx} is missing from JSON. Querying individually...")
                        single_text = str(batch_df.loc[idx, 'text']).replace('\n', ' ')
                        single_label_str = LABEL_MAP_INT_TO_STR.get(int(batch_df.loc[idx, 'label']), "Netral")
                        single_data_str = f"ID {idx}: [Teks: {single_text}] | [Label Lama: {single_label_str}]"
                        single_prompt = f"Evaluasi dan koreksi 1 baris data berikut:\n\n{single_data_str}\n\nBerikan hasil akhir HANYA dalam format JSON Object yang memetakan ID ke sentimennya, seperti contoh berikut:\n{{\n  \"{idx}\": \"Netral\"\n}}"
                        try:
                            single_res = call_gemini_api(single_prompt, api_key, model_name)
                            val = single_res.get(str(idx)) or single_res.get(int(idx))
                            if val is None and isinstance(single_res, dict):
                                val = list(single_res.values())[0] if single_res else None
                            if val is None:
                                val = single_label_str # Fallback to original
                        except Exception as e:
                            print(f"Failed to query ID {idx} individually: {e}. Falling back to original label.")
                            val = single_label_str
                    corrected_labels_str.append(val)
            
            # Map strings to integers
            corrected_labels_int = []
            for lbl in corrected_labels_str:
                val = LABEL_MAP_STR_TO_INT.get(lbl, 1) # Default to Neutral (1) if unknown
                corrected_labels_int.append(val)
                
            batch_df['original_label'] = batch_df['label']
            batch_df['label'] = corrected_labels_int
            batch_df['corrected_label_str'] = corrected_labels_str
            
            # Save batch
            # We preserve text and corrected label columns
            output_df = batch_df[['text', 'label']]
            
            if not is_resume and i == 0:
                output_df.to_csv(output_path, index=False)
            else:
                output_df.to_csv(output_path, mode='a', header=False, index=False)
                
            print(f"Batch {i // batch_size + 1} processed and saved successfully.")
            
        except Exception as e:
            print(f"Critical error processing batch starting at index {i}: {e}")
            print("Aborting. You can run the script again to resume from this point.")
            sys.exit(1)
            
        # Respect rate limits
        if i + batch_size < total_rows:
            time.sleep(delay)
            
    print(f"Dataset verification complete! Saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Sentiment Dataset Verification Script")
    parser.add_argument("--file", type=str, choices=["train", "test", "valid", "all"], default="test", help="Which dataset file to process")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for API requests")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to process (useful for testing)")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between API requests in seconds")
    parser.add_argument("--model", type=str, default="gemini-flash-latest", help="Gemini model name")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment or .env file.")
        print("Please add GEMINI_API_KEY=your_key_here to d:\\SKRIPSI\\sentimens\\.env")
        sys.exit(1)
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    datasets_dir = os.path.join(base_dir, "datasets_verif")
    
    files_to_process = []
    if args.file in ["test", "all"]:
        files_to_process.append(("FINAL_TEST.csv", "FINAL_TEST_verified.csv"))
    if args.file in ["valid", "all"]:
        files_to_process.append(("FINAL_VALID.csv", "FINAL_VALID_verified.csv"))
    if args.file in ["train", "all"]:
        files_to_process.append(("FINAL_TRAIN.csv", "FINAL_TRAIN_verified.csv"))
        
    for in_name, out_name in files_to_process:
        in_path = os.path.join(datasets_dir, in_name)
        out_path = os.path.join(datasets_dir, out_name)
        
        if not os.path.exists(in_path):
            print(f"Error: Input file {in_path} does not exist.")
            continue
            
        print("="*60)
        print(f"Starting verification of {in_name}")
        print("="*60)
        
        verify_dataset(
            in_path,
            out_path,
            api_key,
            args.model,
            batch_size=args.batch_size,
            limit=args.limit,
            delay=args.delay
        )

if __name__ == "__main__":
    main()
