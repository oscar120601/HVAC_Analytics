from docx import Document
import sys

def read_docx(path):
    try:
        doc = Document(path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        return f"Error reading file: {e}"

if __name__ == "__main__":
    file_path = r"C:\Users\oscar.chang\Downloads\数据清洗代码评审.docx"
    content = read_docx(file_path)
    with open("temp_docx_feedback.txt", "w", encoding="utf-8") as f:
        f.write(content)
