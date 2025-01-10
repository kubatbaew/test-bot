import json

def load_data():
    try:
        with open('db.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []  # Если файла нет, вернуть пустой список

def save_data(data):
    with open('db.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

json.JSONDecodeError