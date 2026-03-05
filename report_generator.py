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
    You are an expert career coach and psychometrician for management students. 
    Using the attached FIRO-B Rule Book, design a student-facing report based on the user's scores.

    **Goal:** Help the student understand their behavior in group and work settings, and anticipate team compatibility and challenges.
    **Tone:** Developmental (not predictive or clinical labeling), student-friendly, and focused on behavior-to-environment mapping. Treat the scores as a tool for self-awareness, not a rigid box.

    **User's FIRO-B Data:**
    - Inclusion: {labels['inclusion']} (Expressed: {scores['matrix'][0][0]}, Wanted: {scores['matrix'][1][0]}), Total Need: {scores['col_totals'][0]}
    - Control: {labels['control']} (Expressed: {scores['matrix'][0][1]}, Wanted: {scores['matrix'][1][1]}), Total Need: {scores['col_totals'][1]}
    - Affection: {labels['affection']} (Expressed: {scores['matrix'][0][2]}, Wanted: {scores['matrix'][1][2]}), Total Need: {scores['col_totals'][2]}
    - Total Expressed Behavior: {scores['row_totals'][0]}
    - Total Wanted Behavior: {scores['row_totals'][1]}
    - Overall Interpersonal Need: {scores['grand_total']}

    **CRITICAL INSTRUCTIONS:**
    You MUST output EXACTLY 7 sections, separated by the exact text "--- PAGE X ---". Do not add introductory or concluding remarks outside of this structure. Strictly follow the bullet point counts.

    --- PAGE 1 ---
    **1. Total Expressed and Wanted Behaviors**
    - Provide 4 to 5 bullet points explaining what their Total Expressed vs. Total Wanted behavior scores mean about how they initiate vs. wait for interactions.
    - **Your Total Needs:** Provide 2 to 3 bullet points explaining their Overall Interpersonal Need score and what it says about their general reliance on human interaction.

    --- PAGE 2 ---
    **2. Your Patterns of Need Fulfillment for Inclusion**
    - First line MUST be: "Your results on Expressed Inclusion ({scores['matrix'][0][0]}) and Wanted Inclusion ({scores['matrix'][1][0]}) suggest the following pattern of behaviors:"
    - Provide AT LEAST 5 bullet points describing their inclusion profile ({labels['inclusion']}) based on the rule book. Focus on how they associate with others.

    --- PAGE 3 ---
    **3. Your Patterns of Need Fulfillment for Control**
    - First line MUST be: "Your results on Expressed Control ({scores['matrix'][0][1]}) and Wanted Control ({scores['matrix'][1][1]}) suggest the following pattern of behaviors:"
    - Provide AT LEAST 5 bullet points describing their control profile ({labels['control']}) based on the rule book. Focus on leadership, responsibility, and decision-making.

    --- PAGE 4 ---
    **4. Your Patterns of Need Fulfillment for Affection**
    - First line MUST be: "Your results on Expressed Affection ({scores['matrix'][0][2]}) and Wanted Affection ({scores['matrix'][1][2]}) suggest the following pattern of behaviors:"
    - Provide AT LEAST 5 bullet points describing their affection profile ({labels['affection']}) based on the rule book. Focus on emotional ties, warmth, and closeness.

    --- PAGE 5 ---
    **5. My Behavioural Snapshot**
    - Provide exactly 4 to 5 bullet points summarizing how the student typically behaves at work or in project teams.
    - **CRITICAL:** This section MUST be written entirely in the first-person perspective (e.g., "I tend to...", "I usually...", "I prefer...").

    --- PAGE 6 ---
    **6. How I Function in Groups**
    - **Role in teams:** Exactly 3 bullet points explaining their natural fit in a group.
    - **Comfort with leadership and participation:** Exactly 3 bullet points detailing how they handle authority and sharing ideas.
    - **Response to group dynamics:** Exactly 3 bullet points explaining how they react to conflict, consensus, or pressure.

    --- PAGE 7 ---
    **7. People I Work Best With**
    - **Who I work best with:** Exactly 3 bullet points describing the traits, styles, or behaviors of team members they will feel most comfortable and productive with.
    - **Potential friction points:** Exactly 3 bullet points describing the types of people or management styles that may cause them stress, annoyance, or conflict.
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