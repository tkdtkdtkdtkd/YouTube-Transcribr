import streamlit as st
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import google.generativeai as genai
import re
import time
import io
import os 
import markdown # <-- FOR FANCY PDF
from fpdf import FPDF # <-- FOR STANDARD PDF
from markdown_it import MarkdownIt # <-- FOR STANDARD PDF
from weasyprint import HTML, CSS # <-- FOR FANCY PDF

# Initialize the Markdown-it parser (for FPDF)
md_fpdf = MarkdownIt()

# --- Page Configuration ---
st.set_page_config(
    page_title="Transcribrr 🚀",
    page_icon="📜",
    layout="wide"
)

# --- 1. CORE HELPER FUNCTIONS (Your YouTube Code) ---

def clean_transcript_basic(text):
    """
    Simple text cleaning: normalizes whitespace and fixes contractions.
    """
    text = re.sub(r'\s+', ' ', text).strip()
    contractions = {
        r'\bi\s+': 'I ', r'\bim\b': "I'm", r'\bid\b': "I'd", r'\bive\b': "I've",
        r'\byoure\b': "you're", r'\byouve\b': "you've",
        r'\bhes\b': "he's", r'\bshes\b': "she's", r'\bits\b': "it's",
        r'\btheyre\b': "they're", r'\btheyve\b': "they've",
        r'\bweve\b': "we've", r'\bwere\b': "we're",
        r'\bdont\b': "don't", r'\bwont\b': "won't", r'\bcant\b': "can't",
        r'\bisnt\b': "isn't", r'\bwasnt\b': "wasn't", r'\barent\b': "aren't",
        r'\bdidnt\b': "didn't", r'\bdoesnt\b': "doesn't", r'\bhavent\b': "haven't",
        r'\bhasnt\b': "hasn't", r'\bhadnt\b': "hadn't",
        r'\bwouldnt\b': "wouldn't", r'\bshouldnt\b': "shouldn't", r'\bcouldnt\b': "couldn't",
        r'\bthats\b': "that's", r'\bwhats\b': "what's", r'\bwheres\b': "where's",
    }
    for pattern, replacement in contractions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r'\s+([,.!?])', r'\1', text)
    text = re.sub(r'([,.!?])(\w)', r'\1 \2', text)
    return text

@st.cache_data(show_spinner="Searching for channel videos...")
def get_channel_videos(api_key, channel_name, max_results=25):
    """
    Get latest video IDs from a YouTube channel by channel name.
    """
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        search_response = youtube.search().list(
            q=channel_name,
            type='channel',
            part='id,snippet',
            maxResults=1
        ).execute()
        
        if not search_response['items']:
            st.error(f"Channel '{channel_name}' not found")
            return []
        
        channel_id = search_response['items'][0]['id']['channelId']
        
        channel_response = youtube.channels().list(
            id=channel_id,
            part='contentDetails'
        ).execute()
        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        playlist_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part='snippet',
            maxResults=max_results
        ).execute()
        
        video_data = []
        for item in playlist_response['items']:
            video_id = item['snippet']['resourceId']['videoId']
            video_title = item['snippet']['title']
            video_data.append({'video_id': video_id, 'title': video_title})
        
        return video_data
    
    except Exception as e:
        st.error(f"Error accessing YouTube API: {e}")
        return []

@st.cache_data(show_spinner="Fetching transcripts...")
def get_transcripts_for_videos(video_ids_to_fetch):
    """
    Get transcripts for a list of selected video IDs.
    """
    transcripts = {}
    for video_id, video_title in video_ids_to_fetch:
        try:
            yt_api = YouTubeTranscriptApi()
            transcript_list = yt_api.fetch(video_id)
            transcripts[video_id] = {
                'title': video_title,
                'transcript_list': transcript_list
            }
            st.success(f"Got transcript for: {video_title}")
        except TranscriptsDisabled:
            st.warning(f"Transcripts are disabled for: {video_title}")
        except NoTranscriptFound:
            st.warning(f"No transcript found for: {video_title}")
        except Exception as e:
            st.error(f"Error fetching transcript for {video_title}: {e}")
        time.sleep(1) # Small delay
    
    return transcripts

# --- 2. CORE HELPER FUNCTIONS (Your Gemini Code) ---

def run_gemini_model(transcript_text, system_prompt, gemini_api_key):
    """
    A single function to run a Gemini model with a specific system prompt.
    """
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel("models/gemini-pro-latest")
        full_prompt = f"{system_prompt}\n\nHere is the text:\n---\n{transcript_text}\n---"
        
        gen_config = {
            "max_output_tokens": 9999999
        }
        
        response = model.generate_content(
            full_prompt,
            generation_config=gen_config
        )
        
        return response.text
    except Exception as e:
        return f"Error calling Gemini: {e}"

# Prompts from your scripts
BRAINROT_PROMPT = """**CRITICAL RULE: Do not summarize. You must rewrite the *entire* provided text from beginning to end, in this slang style. Do not skip any part of the original text, even if it seems boring. Your job is to make it un-boring.**

Write in chronically online Gen Z brainrot slang — think TikTok comments, meme-core humor, and chaotic but self-aware energy.
Keep it conversational, quick, and unserious, like you’re talking to your mutuals in a group chat at 2 a.m.
Use slang naturally — don’t spam it, but sprinkle it like seasoning. Keep sentences short and readable, and don’t overexplain jokes.
It should feel low-effort but effortlessly funny, like a post that somehow ate without trying.

Use any of these terms whenever they fit:

rizz, sigma, skibidi, gyatt, ohio, npc, fanum tax, kai cenat, mog, mogged, delulu, slay, ate, ate down, ate that, be so for real, bsfr, real, fr, frfr, ong, ongod, bet, cap, no cap, mid, peak, it’s giving, mother, mothered, girlboss, serve, serving, gagged, oop, pookie, pookie bear, goober, babygirl, mewing, side eye, valid, touch grass, ratio, ratioed, main character, ick, soft launch, hard launch, glow up, core, aesthetic, coquette, feral, girl dinner, girl math, doomscroll, chronically online, brainrot, simp, pick me, rizz god, rizzler, delulu era, flop era, serve era, real era, npc era, pipeline, canon event, lore, vibe check, go outside, down bad, lowkey, highkey, sus, no thoughts head empty, i fear, help, crying screaming throwing up, i’m him, she’s her, himbo, slaycore, periodt, stan twitter, delulu isn’t the solulu, yapping, barking, meow, purrr, werk, gagged, shook, no notes, low vibrational, filler episode, side quest, lore dump, goofycore, sillycore, skrunkly, villain arc, healing arc, redemption arc, flop era, it’s giving, respectfully, respectfully delulu, cooked, obliterated, real one, stay safe king, slay queen, go off, pop off, be so for real rn, nah cause, i fear, real behavior, touch sun, brainrot maxxing, let him cook, ate no crumbs, i’m folding, bffr, slayy, it’s my roman empire, rent free, doomscroll arc, cry about it, stay mad, touch grass challenge, not too much on me, respectfully ate.

Tone goals:

✨ It’s giving unserious but kinda profound
💀 Chronically online but self-aware
💅 Slaycore grammar chaos — correct spelling optional but flow is mandatory
🔥 Every line should sound like it could go viral in a TikTok comment section or meme screenshot

Keep it neat, readable, and funny. Use slang in a way that feels real, not forced. Be chaotic, but in a controlled chaos way."""

EXPLAINER_PROMPT = "make detailed points out of this, do not skip details and in the end give all learnings and resources in a clear set of actionables->"

# --- 3. FORMATTING AND PDF FUNCTIONS ---

# --- 3A: Standard PDF (FPDF) Functions ---

#
# THIS IS THE FIXED VERSION from our last conversation
#
def format_original_transcript(transcript_list):
    """
    Takes the raw transcript list and formats it into
    a single, cleaned block of text.
    """
    # 1. Get all text snippets
    all_text_snippets = [snippet['text'] for snippet in transcript_list]
    
    # 2. Join them all with a single space
    full_transcript = ' '.join(all_text_snippets)
    
    # 3. Clean the ENTIRE block at once
    cleaned_full_transcript = clean_transcript_basic(full_transcript)
    
    # 4. Return the single, continuous block of text.
    return cleaned_full_transcript


class PDF(FPDF):
    """
    Standard FPDF class for Original and Brainrot transcripts.
    """
    def header(self):
        self.set_font('DejaVu', 'B', 12)
        self.cell(0, 10, 'Transcribrr 🚀', 0, 1, 'C')

    def chapter_title(self, title):
        self.set_font('DejaVu', 'B', 14)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def chapter_body(self, text):
        html = md_fpdf.render(text)
        try:
            self.write_html(html)
        except Exception as e:
            st.warning(f"FPDF HTML rendering error, falling back to basic text: {e}")
            self.set_font('DejaVu', '', 12)
            self.multi_cell(0, 10, text)
        self.ln()

def create_pdf_from_transcripts(processed_transcripts):
    """
    Takes a list of (title, text) tuples and generates a PDF
    in memory using FPDF.
    """
    pdf = PDF()
    
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf', uni=True)
    except RuntimeError:
        st.error("DejaVu fonts not found! Please add DejaVuSans.ttf and DejaVuSans-Bold.ttf to your app's root directory.")
        st.stop()
    
    for title, text in processed_transcripts:
        pdf.add_page()
        pdf.chapter_title(title)
        pdf.chapter_body(text)
        
    return bytes(pdf.output(dest='S'))


# --- 3B: Fancy PDF (WeasyPrint) Functions ---

FANCY_PDF_CSS = """
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
    
    .video-section {
        /* This ensures each new video starts on a new page */
        page-break-before: always;
    }
    
    .video-section:first-child {
        page-break-before: auto; /* The first one doesn't need a break */
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

def clean_and_fix_text(text_input):
    """
    Cleans and fixes the broken formatting of the AI Explainer output
    to make it valid Markdown.
    """
    cleaned_text = text_input.replace('\ufeff', '')
    cleaned_text = re.sub(r'\s*Transcribrr\s*', '\n', cleaned_text).strip()
    cleaned_text = re.sub(r'^(Part \d+:.*?)$', r'### \1', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'^(Learnings and Actionable Takeaways)$', r'\n---\n## \1', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'^([A-Z]\..*?)$', r'### \1', cleaned_text, flags=re.MULTILINE)
    cleaned_text = cleaned_text.replace('•', '*')
    cleaned_text = re.sub(r'( \d+\. )', r'\n\1', cleaned_text)
    cleaned_text = re.sub(r'( \* )', r'\n\1', cleaned_text)
    cleaned_text = re.sub(r'(\S) (\d+\.)', r'\1\n\2', cleaned_text)
    cleaned_text = re.sub(r'\n\n+', '\n\n', cleaned_text)
    return cleaned_text.strip()

def create_fancy_pdf_from_transcripts(processed_transcripts):
    """
    Takes a list of (title, text) tuples, cleans them, and
    generates a "fancy" PDF in memory using WeasyPrint.
    """
    all_html_content = ""
    
    for title, text in processed_transcripts:
        full_text_for_cleaning = f"{title}\n{text}"
        cleaned_text = clean_and_fix_text(full_text_for_cleaning)
        
        lines = cleaned_text.split('\n', 1)
        title_line = lines[0].replace("Video: ", "").strip()
        main_content_md = lines[1] if len(lines) > 1 else ""
        
        main_content_html = markdown.markdown(main_content_md)
        
        all_html_content += f'<div class="video-section"><h1>{title_line}</h1>{main_content_html}</div>'

    html_doc = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Transcribrr Summary</title>
    </head>
    <body>
        {all_html_content}
    </body>
    </html>
    """
    
    try:
        base_url = os.path.dirname(os.path.abspath(__file__))
        html = HTML(string=html_doc, base_url=base_url)
        css = CSS(string=FANCY_PDF_CSS)
        pdf_bytes = html.write_pdf(stylesheets=[css])
        return pdf_bytes
        
    except Exception as e:
        st.error(f"Error generating 'Fancy' PDF with WeasyPrint: {e}")
        st.error("This can happen if WeasyPrint dependencies (like Pango, GDK-PixBuf) are not installed. Please check WeasyPrint documentation for your OS.")
        return None


# --- 4. THE STREAMLIT APP UI ---

st.title("Transcribrr 🚀")
st.info("Get transcripts from any YouTube channel and format them with AI.")

# Load API keys from secrets
try:
    YOUTUBE_KEY = st.secrets["YOUTUBE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    if not YOUTUBE_KEY or not GEMINI_KEY:
        st.error("API keys not found. Please add them to .streamlit/secrets.toml")
        st.stop()
except FileNotFoundError:
    st.error("`secrets.toml` file not found. Please create it in a `.streamlit` folder.")
    st.stop()
except KeyError:
    st.error("API keys not configured correctly in `secrets.toml`. Make sure YOUTUBE_API_KEY and GEMINI_API_KEY are set.")
    st.stop()


# Initialize session state
if 'video_list' not in st.session_state:
    st.session_state.video_list = []
if 'final_pdf_data' not in st.session_state:
    st.session_state.final_pdf_data = None

# --- STEP 1: Channel Search ---
st.header("Step 1: Find a Channel")
channel_name = st.text_input("Enter YouTube Channel Name", placeholder="e.g., MrBeast or TechWithTim")

if st.button("Search Channel"):
    st.session_state.video_list = [] # Clear old results
    st.session_state.final_pdf_data = None # Clear old PDF
    if channel_name:
        st.session_state.video_list = get_channel_videos(YOUTUBE_KEY, channel_name)
        if not st.session_state.video_list:
            st.warning("No videos found. Try a different channel name.")
    else:
        st.warning("Please enter a channel name.")

# --- STEP 2: Select Videos and Format ---
if st.session_state.video_list:
    st.header("Step 2: Select Videos and Format")
    
    with st.form(key="video_selection_form"):
        st.subheader(f"Found {len(st.session_state.video_list)} recent videos:")
        
        video_selections = {}
        for video in st.session_state.video_list:
            video_selections[video['video_id']] = st.checkbox(
                f"{video['title']} (ID: {video['video_id']})", key=video['video_id']
            )
        
        st.subheader("Step 3: Choose Format")
        format_option = st.radio(
            "Select transcript format:",
            ("Original Transcript", "Brainrot Transcript (Gen Z)", "AI Explainer (Detailed Notes)")
        )
        
        submit_button = st.form_submit_button(label="Generate Transcripts!")

    # --- STEP 3: Process and Download ---
    if submit_button:
        selected_videos = []
        for video_data in st.session_state.video_list:
            video_id = video_data['video_id']
            video_title = video_data['title']
            
            if video_id in video_selections and video_selections[video_id] is True:
                selected_videos.append((video_id, video_title))

        if not selected_videos:
            st.warning("Please select at least one video.")
        else:
            with st.spinner("Processing... This might take a few minutes..."):
                
                # 1. Fetch transcripts
                raw_transcripts = get_transcripts_for_videos(selected_videos)
                
                processed_transcripts = [] # List to hold (title, final_text)
                
                for video_id, data in raw_transcripts.items():
                    # 2. Format as "Original" first (USING THE FIXED FUNCTION)
                    original_formatted_text = format_original_transcript(data['transcript_list'])
                    
                    final_text = ""
                    title = f"Video: {data['title']}"
                    
                    # 3. Apply AI format if chosen
                    if format_option == "Original Transcript":
                        final_text = original_formatted_text
                    
                    elif format_option == "Brainrot Transcript (Gen Z)":
                        st.text(f"Running 'Brainrot' model on: {data['title']}...")
                        final_text = run_gemini_model(original_formatted_text, BRAINROT_PROMPT, GEMINI_KEY)
                    
                    elif format_option == "AI Explainer (Detailed Notes)":
                        st.text(f"Running 'AI Explainer' model on: {data['title']}...")
                        final_text = run_gemini_model(original_formatted_text, EXPLAINER_PROMPT, GEMINI_KEY)
                    
                    processed_transcripts.append((title, final_text))
                
                # 4. Generate PDF
                if processed_transcripts:
                    pdf_data = None
                    
                    # --- THIS IS THE CONDITIONAL LOGIC ---
                    if format_option == "AI Explainer (Detailed Notes)":
                        st.text("Generating 'Fancy' PDF with WeasyPrint...")
                        pdf_data = create_fancy_pdf_from_transcripts(processed_transcripts)
                    else:
                        st.text("Generating 'Standard' PDF with FPDF...")
                        pdf_data = create_pdf_from_transcripts(processed_transcripts)
                    # --- END OF LOGIC ---
                        
                    if pdf_data:
                        st.session_state.final_pdf_data = pdf_data
                        st.success("All transcripts processed and PDF is ready!")
                    else:
                        st.error("Could not generate PDF data.")
                else:
                    st.error("Could not process any transcripts.")

# --- Download Button ---
if st.session_state.final_pdf_data:
    st.balloons()
    st.header("Step 4: Download Your PDF!")
    st.download_button(
        label="Download PDF",
        data=st.session_state.final_pdf_data,
        file_name="transcribrr_output.pdf",
        mime="application/pdf"
    )