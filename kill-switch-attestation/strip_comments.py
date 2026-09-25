import os
import tokenize
import io

def remove_comments_py(source_code):
    io_obj = io.StringIO(source_code)
    out = ""
    last_lineno = -1
    last_col = 0
    try:
        for tok in tokenize.generate_tokens(io_obj.readline):
            token_type = tok[0]
            token_string = tok[1]
            start_line, start_col = tok[2]
            end_line, end_col = tok[3]
            if start_line > last_lineno:
                last_col = 0
            if start_col > last_col:
                out += (" " * (start_col - last_col))
            if token_type == tokenize.COMMENT:
                pass
            else:
                out += token_string
            last_lineno = end_line
            last_col = end_col
        return out
    except Exception as e:
        return source_code

def process_dir(d):
    for root, dirs, files in os.walk(d):
        if '.venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                new_content = remove_comments_py(content)
                
                
                lines = new_content.split('\n')
                cleaned_lines = [line for line in lines if line.strip() or not line]
                
                
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(new_content)

if __name__ == '__main__':
    process_dir('.')
