import re
import sys

def get_longest_quoted_string(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        matches = re.findall(r'"([^"]*)"', file.read())
    
    return max(matches, key=len) if matches else ""

if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else "data.txt"
    print(get_longest_quoted_string(target_file))