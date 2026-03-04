import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load API Key
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)

# Global variable to store the uploaded file object
RULE_BOOK_FILE = None

def initialize_context_cache(pdf_path: str):
    """
    Uploads the file using the Standard File API (Free).
    """
    global RULE_BOOK_FILE
    
    print(f"--- Uploading Rule Book from {pdf_path} ---")
    
    # 1. Check if file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Could not find the PDF at: '{pdf_path}'. Make sure firo_b_rules.pdf is in the same folder as main.py!")

    # 2. Upload the file to Google
    RULE_BOOK_FILE = client.files.upload(file=pdf_path)
    
    # 3. Wait for processing to complete
    print("Processing file...")
    while RULE_BOOK_FILE.state.name == "PROCESSING":
        time.sleep(2)
        RULE_BOOK_FILE = client.files.get(name=RULE_BOOK_FILE.name)

    if RULE_BOOK_FILE.state.name != "ACTIVE":
        raise Exception(f"File upload failed with state: {RULE_BOOK_FILE.state.name}")

    print(f"File Ready! Name: {RULE_BOOK_FILE.name}")


def generate_psychometric_report(scores: dict, labels: dict) -> str:
    """
    Sends the user scores + the uploaded file to the AI in a single request.
    """
    global RULE_BOOK_FILE

    # --- THE FIX: LAZY INITIALIZATION ---
    # If the file wasn't loaded on startup, force it to load right now.
    if not RULE_BOOK_FILE:
        print("Rule book was missing! Attempting to load now...")
        try:
            initialize_context_cache("firo_b_rules.pdf")
        except Exception as e:
            # This will print the exact error directly onto your web page so you can see what went wrong
            return f"**SYSTEM ERROR:** Could not load the Rule Book PDF. Details: {str(e)}"

    # Construct the user-specific prompt with the Management Student constraints
    user_data = f"""
    Design a student report that helps management students:
    • Understand their behaviour in group and work settings
    • Identify specialization fit (HR, Marketing, Finance, Operations, IT/Analytics, General Management)
    • Anticipate team compatibility, challenges, and stress points
    • Plan their PGDM journey (academics, internships, skills)
    
    **User Data:**
    - Inclusion: {labels['inclusion']} (Exp: {scores['matrix'][0][0]}, Want: {scores['matrix'][1][0]})
    - Control: {labels['control']} (Exp: {scores['matrix'][0][1]}, Want: {scores['matrix'][1][1]})
    - Affection: {labels['affection']} (Exp: {scores['matrix'][0][2]}, Want: {scores['matrix'][1][2]})

    *** Report Output Structure (MANDATORY SECTIONS)
    1. My Behavioural Snapshot
    • 4-5 bullet points summarising how the student typically behaves at work/in teams
    • Written in first person (“I tend to…”, “I usually…”)

    2. How I Function in Groups
    • Role in teams
    • Comfort with leadership and participation
    • Response to group dynamics  

    3. People I Work Best With
    • Description of team members the student feels comfortable with
    • Description of people or styles that may cause friction
    """
    
    # System instruction defines the persona
    sys_instruction = (
        "You are an expert Psychometrician. "
        "Your knowledge is strictly limited to the attached 'Rule Book' document. "
        "Analyze the user's scores based ONLY on the interpretation tables in the document."
    )

    try:
        # Pass the FILE and the PROMPT together in the 'contents' list
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=sys_instruction,
                temperature=0.3 # Keep it factual
            ),
            contents=[RULE_BOOK_FILE, user_data]
        )
        return response.text
    except Exception as e:
        return f"**AI Generation Failed:** {str(e)}"