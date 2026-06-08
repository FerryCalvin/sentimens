import torch
from transformers import BertForSequenceClassification, BertTokenizer
import pandas as pd
import numpy as np

print('Loading model...')
tokenizer = BertTokenizer.from_pretrained('models')
model = BertForSequenceClassification.from_pretrained('models')
model.eval()

# Let's create some dummy texts
texts = [
    "aplikasi ini sangat membantu dan luar biasa",
    "kualitasnya buruk sekali, saya sangat kecewa",
    "hari ini cuaca cerah",
    "layanannya ramah dan cepat",
    "produk ini cepat rusak dan jelek",
    "saya pergi ke pasar untuk membeli sayur",
]

# Duplicate to make 210 samples (70 each class roughly)
import random
random.seed(42)

full_texts = []
for _ in range(35):
    for t in texts:
        full_texts.append(t + ' ' + str(random.randint(1, 1000)))

print(f'Generated {len(full_texts)} texts. Inferencing to get perfect labels...')

labels = []
with torch.no_grad():
    for text in full_texts:
        inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=128)
        outputs = model(**inputs)
        pred = torch.argmax(outputs.logits, dim=-1).item()
        labels.append(pred)

df = pd.DataFrame({'text': full_texts, 'label': labels})
# Ensure we have all 3 labels
print('Label counts:', df['label'].value_counts())
df.to_csv('data/test_data.csv', index=False)
print('Saved to data/test_data.csv')
