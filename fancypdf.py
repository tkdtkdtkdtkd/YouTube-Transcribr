import markdown
from weasyprint import HTML, CSS
import re  # Used for fixing the text
import os  # Used for file paths

def clean_and_fix_text(text_input):
    """
    Cleans and fixes the broken formatting of the input text
    to make it valid Markdown.
    """
    print("Cleaning and fixing text...")
    
    # Remove BOM character (seen at "word-of-mouth")
    cleaned_text = text_input.replace('\ufeff', '')
    
    # Remove "Transcribrr" artifacts
    cleaned_text = re.sub(r'\s*Transcribrr\s*', '\n', cleaned_text).strip()
    
    # --- Fix Major Sections ---
    
    # Convert "Part 1: ..." lines into Markdown headers
    cleaned_text = re.sub(r'^(Part \d+:.*?)$', r'### \1', cleaned_text, flags=re.MULTILINE)
    
    # Convert "Learnings..." line into a major header
    cleaned_text = re.sub(r'^(Learnings and Actionable Takeaways)$', r'\n---\n## \1', cleaned_text, flags=re.MULTILINE)
    
    # Convert "A. Core Philosophy..." lines into sub-headers
    cleaned_text = re.sub(r'^([A-Z]\..*?)$', r'### \1', cleaned_text, flags=re.MULTILINE)

    # --- Fix Broken Lists ---
    
    # Standardize Unicode bullets (•) to Markdown asterisks (*)
    cleaned_text = cleaned_text.replace('•', '*')
    
    # Fix run-on numbered lists (e.g., "1. Inbound... 2. Outbound...")
    cleaned_text = re.sub(r'( \d+\. )', r'\n\1', cleaned_text)
    
    # Fix run-on bulleted lists (e.g., "machine. * 1. Foundational...")
    cleaned_text = re.sub(r'( \* )', r'\n\1', cleaned_text)
    
    # Fix jumbled lists in the "Learnings" section (e.g., "Funnel: 2. Create...")
    cleaned_text = re.sub(r'(\S) (\d+\.)', r'\1\n\2', cleaned_text)
    
    # Clean up any potential double newlines created by the fixes
    cleaned_text = re.sub(r'\n\n+', '\n\n', cleaned_text)
    
    return cleaned_text.strip()


def create_fancy_pdf(text_input, output_filename="professional_summary.pdf"):
    """
    Cleans, converts, and styles text/markdown into a 'fancy' PDF.
    """
    
    # --- 1. Clean the Text ---
    cleaned_text = clean_and_fix_text(text_input)
    
    # Extract the title and main content
    lines = cleaned_text.split('\n', 1)
    title_line = lines[0].replace("Video: ", "").strip()
    main_content = lines[1] if len(lines) > 1 else ""
    
    # --- 2. Convert Markdown to HTML ---
    print("Converting Markdown to HTML...")
    html_body = markdown.markdown(main_content)
    
    html_doc = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{title_line}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="content">
            <h1>{title_line}</h1>
            {html_body}
        </div>
    </body>
    </html>
    """
    
    # --- 3. Define the "Fancy" CSS Styling ---
    
    css_style = """
    /* Use @font-face to import fonts for WeasyPrint */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Merriweather:wght@400;700&display=swap');

    @page {
        size: A4;
        margin: 1.5cm;
        background-color: #f8f9fa; /* Light gray page background */
    }
    
    body {
        font-family: 'Inter', 'Helvetica', 'Arial', sans-serif;
        line-height: 1.7;
        font-size: 11pt;
        color: #343a40; /* Dark gray text for readability */
        background-color: #ffffff; /* White content paper */
        max-width: 18cm; /* Content width */
        margin: 1cm auto; /* Center the content */
        padding: 1.5cm;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    
    h1 {
        font-family: 'Merriweather', 'Georgia', serif;
        font-size: 26pt;
        color: #0056b3; /* Deep Blue */
        text-align: center;
        margin-bottom: 20px;
        line-height: 1.3;
        border-bottom: 3px solid #007bff; /* Accent color border */
        padding-bottom: 15px;
    }

    /* Style for ## (Learnings...) */
    h2 {
        font-family: 'Merriweather', 'Georgia', serif;
        font-size: 20pt;
        color: #0056b3; /* Deep Blue */
        margin-top: 40px;
        margin-bottom: 15px;
        border-bottom: 1px solid #dee2e6; /* Light gray border */
        padding-bottom: 8px;
    }
    
    /* Style for ### (Part 1:, A., B., etc.) */
    h3 { 
        font-family: 'Inter', 'Helvetica', sans-serif;
        font-weight: 700; /* Bold */
        font-size: 15pt;
        color: #007bff; /* Bright Blue Accent */
        margin-top: 30px;
        margin-bottom: 10px;
    }
    
    p {
        margin-bottom: 12px;
    }
    
    ul, ol {
        margin-left: 5px;
        padding-left: 25px;
        margin-bottom: 15px;
    }
    
    li {
        margin-bottom: 8px;
        padding-left: 5px;
    }
    
    /* Style for **bold** text */
    strong { 
        font-weight: 700;
        color: #000;
    }
    
    /* Style for --- */
    hr { 
        border: 0;
        height: 2px;
        background-color: #e9ecef; /* Light, clean separator */
        margin-top: 40px;
        margin-bottom: 40px;
    }
    """
    
    # --- 4. Render the PDF ---
    print(f"Rendering PDF: {output_filename}...")
    
    try:
        # Use a dummy base_url to help resolve paths if any
        base_url = os.path.dirname(os.path.abspath(__file__))
        
        html = HTML(string=html_doc, base_url=base_url)
        css = CSS(string=css_style)
        
        # Write the PDF
        html.write_pdf(output_filename, stylesheets=[css])
        
        print(f"\n✅ Success! PDF saved as '{output_filename}'")
        
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("Please ensure WeasyPrint and its dependencies are installed correctly.")

# --- Main execution ---
if __name__ == "__main__":
    input_file = "input.txt"
    output_file = "professional_summary.pdf"
    
    try:
        # Read the text from the input file, using utf-8 encoding
        with open(input_file, 'r', encoding='utf-8') as f:
            raw_text = f.read()
        
        print(f"Successfully read from {input_file}.")
        
        # Call the main function with the text from the file
        create_fancy_pdf(raw_text, output_file)
    
    except FileNotFoundError:
        print(f"❌ ERROR: The file '{input_file}' was not found.")
        print("Please create 'input.txt' in the same directory and paste your text into it.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")d