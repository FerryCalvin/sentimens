with open('training/evaluate.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('BertTokenizer', 'AutoTokenizer')

with open('training/evaluate.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated evaluate.py successfully.")
