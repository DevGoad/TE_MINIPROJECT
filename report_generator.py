import google.generativeai as genai
import os

# CONFIGURATION
# In a real job, you would use os.getenv("GEMINI_API_KEY") for security.
# For now, you can paste your key below.
API_KEY = "AIzaSyCWEb7-76MrYhuNDQJxEm2SvpNw8VK7Uww" 

genai.configure(api_key=API_KEY)

# Initialize the model
model = genai.GenerativeModel('gemini-2.5-flash')

def generate_psychometric_report(scores, labels):
    """
    Sends the calculated FIRO-B data to the LLM and gets a text report.
    """
    
    # 1. Construct the Prompt
    # We give the AI the specific data and the instructions on how to write.
    prompt = f"""
    You are an expert Psychologist specializing in the FIRO-B (Fundamental Interpersonal Relations Orientation-Behavior) assessment.
    
    I will provide you with the scores and interpreting labels for a client. Your task is to write a cohesive, professional, and empathetic 3-paragraph report summarizing their interpersonal needs.
    
    ### CLIENT DATA:
    
    1. INCLUSION (Social Interaction):
       - Scores: Expressed (e)={scores['matrix'][0][0]}, Wanted (w)={scores['matrix'][1][0]}
       - Interpretation: "{labels['inclusion']}"
       
    2. CONTROL (Leadership & Responsibility):
       - Scores: Expressed (e)={scores['matrix'][0][1]}, Wanted (w)={scores['matrix'][1][1]}
       - Interpretation: "{labels['control']}"
       
    3. AFFECTION (Intimacy & Closeness):
       - Scores: Expressed (e)={scores['matrix'][0][2]}, Wanted (w)={scores['matrix'][1][2]}
       - Interpretation: "{labels['affection']}"
    
    ### INSTRUCTIONS:
    - Write directly to the client (use "You").
    - Do not simply list the scores; explain what they mean in real life.
    - Paragraph 1: Discuss their social style (Inclusion).
    - Paragraph 2: Discuss their leadership and decision-making style (Control).
    - Paragraph 3: Discuss their approach to close personal relationships (Affection).
    - Tone: Constructive, insightful, and professional.
    - Keep the total length under 300 words.
    """

    try:
        # 2. Call the API
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating report: {str(e)}"