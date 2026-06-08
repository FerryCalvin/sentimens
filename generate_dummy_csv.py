import csv
import os
import random
from datetime import datetime, timedelta

DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "precomputed_large.csv")

def generate():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    fieldnames = [
        "teks_asli", "teks_bersih", "sentimen",
        "confidence_positif", "confidence_negatif", "confidence_netral",
        "source", "date"
    ]
    
    # Per the schema we will also need 'source' and 'date'. We will append them 
    # to the generate_csv_output structure later, but for the precomputed they must exist.
    
    sources = ["twitter"] * 70 + ["news"] * 30
    sentiments = ["Positif", "Negatif", "Netral"]
    
    start_date = datetime.now() - timedelta(days=30)
    
    print(f"Generating 2000 rows to {FILE_PATH}...")
    with open(FILE_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i in range(2000):
            sent = random.choice(sentiments)
            
            if sent == "Positif":
                cp = random.uniform(0.6, 0.99)
                cn = random.uniform(0.01, 1 - cp)
                cneu = 1 - cp - cn
            elif sent == "Negatif":
                cn = random.uniform(0.6, 0.99)
                cp = random.uniform(0.01, 1 - cn)
                cneu = 1 - cp - cn
            else:
                cneu = random.uniform(0.6, 0.99)
                cp = random.uniform(0.01, 1 - cneu)
                cn = 1 - cp - cneu
                
            src = random.choice(sources)
            dt = start_date + timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            
            writer.writerow({
                "teks_asli": f"Ini adalah contoh teks {src} dummy ke-{i} dengan sentimen {sent}.",
                "teks_bersih": f"contoh teks {src} dummy sentimen {sent}",
                "sentimen": sent,
                "confidence_positif": round(cp, 4),
                "confidence_negatif": round(cn, 4),
                "confidence_netral": round(cneu, 4),
                "source": src,
                "date": dt.isoformat()
            })
            
    print("Done!")

if __name__ == "__main__":
    generate()
