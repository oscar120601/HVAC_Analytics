from pypdf import PdfReader
import sys

def read_pdf(path):
    try:
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error reading PDF: {e}"

if __name__ == "__main__":
    file_path = r"C:\Users\oscar.chang\Downloads\数据清洗PRD评审.pdf"
    content = read_pdf(file_path)
    # Print to stdout but also save to file just in case
    # Encode to utf-8 to avoid console encoding issues
    try:
        print(content)
    except UnicodeEncodeError:
        print(content.encode('utf-8', errors='replace').decode('utf-8'))
        
    with open("temp_pdf_content.txt", "w", encoding="utf-8") as f:
        f.write(content)
