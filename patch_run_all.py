with open('run_all.bat', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('python main.py', 'uvicorn main:app --port 8001')
content = content.replace('Port 8000', 'Port 8001')
content = content.replace('http://localhost:8000', 'http://localhost:8001')

with open('run_all.bat', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated run_all.bat successfully.")
