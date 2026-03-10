import os
import re
import time
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY2")
client = genai.Client(api_key=API_KEY)

RULE_BOOK_FILE = None


def initialize_context_cache(pdf_path: str):
    global RULE_BOOK_FILE
    print(f"--- Uploading Rule Book from {pdf_path} ---")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(
            f"Could not find the PDF at: '{pdf_path}'. "
            "Make sure firo_b_rules.pdf is in the same folder as main.py!"
        )
    RULE_BOOK_FILE = client.files.upload(file=pdf_path)
    print("Processing file...")
    while RULE_BOOK_FILE.state.name == "PROCESSING":
        time.sleep(2)
        RULE_BOOK_FILE = client.files.get(name=RULE_BOOK_FILE.name)
    if RULE_BOOK_FILE.state.name != "ACTIVE":
        raise Exception(f"File upload failed with state: {RULE_BOOK_FILE.state.name}")
    print(f"File Ready! Name: {RULE_BOOK_FILE.name}")


def generate_psychometric_report(scores: dict, labels: dict) -> str:
    """
    Sends user scores + uploaded PDF to Gemini and returns raw text.
    `scores` must contain: matrix, row_totals, col_totals, grand_total.
    """
    global RULE_BOOK_FILE

    if not RULE_BOOK_FILE:
        print("Rule book was missing! Attempting to load now...")
        try:
            initialize_context_cache("firo_b_rules.pdf")
        except Exception as e:
            return f"**SYSTEM ERROR:** Could not load the Rule Book PDF. Details: {str(e)}"

    matrix      = scores["matrix"]
    row_totals  = scores["row_totals"]
    col_totals  = scores["col_totals"]
    grand_total = scores["grand_total"]

    user_data = f"""
    You are an expert career coach and psychometrician for management students.
    Using the attached FIRO-B Rule Book, design a student-facing report based on the user's scores.

    **Goal:** Help the student understand their behavior in group and work settings, and anticipate team compatibility and challenges.
    **Tone:** Developmental (not predictive or clinical labeling), student-friendly, and focused on behavior-to-environment mapping.

    **User's FIRO-B Data:**
    - Inclusion: {labels['inclusion']} (Expressed: {matrix[0][0]}, Wanted: {matrix[1][0]}), Total Need: {col_totals[0]}
    - Control: {labels['control']} (Expressed: {matrix[0][1]}, Wanted: {matrix[1][1]}), Total Need: {col_totals[1]}
    - Affection: {labels['affection']} (Expressed: {matrix[0][2]}, Wanted: {matrix[1][2]}), Total Need: {col_totals[2]}
    - Total Expressed Behavior: {row_totals[0]}
    - Total Wanted Behavior: {row_totals[1]}
    - Overall Interpersonal Need: {grand_total}

    **CRITICAL INSTRUCTIONS:**
    You MUST output EXACTLY 7 sections, separated by the exact text "--- PAGE X ---". Do not add introductory or concluding remarks outside of this structure.

    --- PAGE 1 ---
    **1. Total Expressed and Wanted Behaviors**
    - Provide 4 to 5 bullet points explaining what their Total Expressed vs. Total Wanted behavior scores mean about how they initiate vs. wait for interactions.
    - **Your Total Needs:** Provide 2 to 3 bullet points explaining their Overall Interpersonal Need score and what it says about their general reliance on human interaction.

    --- PAGE 2 ---
    **2. Your Patterns of Need Fulfillment for Inclusion**
    - First line MUST be: "Your results on Expressed Inclusion ({matrix[0][0]}) and Wanted Inclusion ({matrix[1][0]}) suggest the following pattern of behaviors:"
    - Provide AT LEAST 5 bullet points describing their inclusion profile ({labels['inclusion']}) based on the rule book.

    --- PAGE 3 ---
    **3. Your Patterns of Need Fulfillment for Control**
    - First line MUST be: "Your results on Expressed Control ({matrix[0][1]}) and Wanted Control ({matrix[1][1]}) suggest the following pattern of behaviors:"
    - Provide AT LEAST 5 bullet points describing their control profile ({labels['control']}) based on the rule book.

    --- PAGE 4 ---
    **4. Your Patterns of Need Fulfillment for Affection**
    - First line MUST be: "Your results on Expressed Affection ({matrix[0][2]}) and Wanted Affection ({matrix[1][2]}) suggest the following pattern of behaviors:"
    - Provide AT LEAST 5 bullet points describing their affection profile ({labels['affection']}) based on the rule book.

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

    sys_instruction = (
        "You are an expert Psychometrician. "
        "Your knowledge is strictly limited to the attached 'Rule Book' document. "
        "Analyze the user's scores based ONLY on the interpretation tables in the document."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=sys_instruction,
                temperature=0.3
            ),
            contents=[RULE_BOOK_FILE, user_data]
        )
        return response.text
    except Exception as e:
        return f"**AI Generation Failed:** {str(e)}"


# ─────────────────────────────────────────────────────────────
#  HELPERS: parse Gemini output → HTML, then fill template
# ─────────────────────────────────────────────────────────────

def markdown_to_html(text: str) -> str:
    """
    Convert Gemini's markdown-style output into clean HTML.
    Handles:
      - "- item"          → <ul><li>
      - **fully bold**    → <h4> sub-heading
      - inline **bold**   → <strong>
      - everything else   → <p>
    """
    lines = text.split("\n")
    html_lines = []
    in_ul = False

    for raw_line in lines:
        line = raw_line.strip()

        # blank line
        if not line:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            continue

        # bullet point
        if line.startswith("- "):
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line[2:])
            if not in_ul:
                html_lines.append('<ul>')
                in_ul = True
            html_lines.append(f"  <li>{content}</li>")

        # stand-alone bold line → sub-heading (e.g. **Role in teams:**)
        elif re.match(r"^\*\*[^*]+\*\*\s*$", line):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            inner = re.sub(r"^\*\*(.*)\*\*\s*$", r"\1", line).rstrip(":")
            html_lines.append(f'<h4>{inner}</h4>')

        # regular paragraph
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            converted = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f'<p>{converted}</p>')

    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def parse_report_sections(raw_text: str) -> dict:
    """
    Split Gemini's output on "--- PAGE X ---" markers.
    Returns {"PAGE_1": "<html>...", ..., "PAGE_7": "<html>..."}
    """
    parts = re.split(r"-{2,3}\s*PAGE\s+(\d+)\s*-{2,3}", raw_text)

    page_contents: dict = {}
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            page_num = parts[i].strip()
            content  = parts[i + 1].strip()
            page_contents[page_num] = content

    sections = {}
    for i in range(1, 8):
        raw_section = page_contents.get(str(i), "")
        if not raw_section:
            sections[f"PAGE_{i}"] = "<p>Section content not available.</p>"
            continue

        # Strip Gemini's redundant bold section-title line at the top
        # (e.g. "**1. Total Expressed and Wanted Behaviors**")
        # — the template already has an <h2> for each page.
        lines = raw_section.split("\n")
        start_idx = 0
        for j, line in enumerate(lines):
            stripped = line.strip()
            if stripped:
                if re.match(r"^\*\*\d+\.\s+.*\*\*$", stripped):
                    start_idx = j + 1
                break

        section_text = "\n".join(lines[start_idx:]).strip()
        sections[f"PAGE_{i}"] = markdown_to_html(section_text)

    return sections


def fill_html_report(template_path: str, scores: dict, labels: dict, ai_report_text: str) -> str:
    """
    Read the HTML template, replace every {{PLACEHOLDER}} with the real value,
    and return the complete, ready-to-serve HTML string.

    Grid placeholders ({{E_INC}} etc.) are set first — these are also the ones
    the frontend may replace via JavaScript (first-occurrence only).

    STRIP_ placeholders are unique names used only in the mini-score strips on
    the interpretation pages, so they are never accidentally replaced by JS.
    """
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    matrix      = scores["matrix"]
    row_totals  = scores["row_totals"]
    col_totals  = scores["col_totals"]
    grand_total = scores["grand_total"]
    date_str    = datetime.now().strftime("%B %d, %Y")

    # ── Grid / metadata placeholders (first occurrence in template) ──────────
    grid_map = {
        "{{DATE}}":  date_str,
        "{{E_INC}}": str(matrix[0][0]),
        "{{E_CON}}": str(matrix[0][1]),
        "{{E_AFF}}": str(matrix[0][2]),
        "{{W_INC}}": str(matrix[1][0]),
        "{{W_CON}}": str(matrix[1][1]),
        "{{W_AFF}}": str(matrix[1][2]),
        "{{T_EXP}}": str(row_totals[0]),
        "{{T_WAN}}": str(row_totals[1]),
        "{{T_INC}}": str(col_totals[0]),
        "{{T_CON}}": str(col_totals[1]),
        "{{T_AFF}}": str(col_totals[2]),
        "{{G_TOT}}": str(grand_total),
    }
    for placeholder, value in grid_map.items():
        html = html.replace(placeholder, value)

    # ── STRIP_ placeholders (unique — only on interpretation pages) ──────────
    strip_map = {
        # Page 3 — Total Behaviors
        "{{STRIP_T_EXP}}":   str(row_totals[0]),
        "{{STRIP_T_WAN}}":   str(row_totals[1]),
        "{{STRIP_G_TOT}}":   str(grand_total),
        # Page 4 — Inclusion
        "{{STRIP_E_INC}}":   str(matrix[0][0]),
        "{{STRIP_W_INC}}":   str(matrix[1][0]),
        "{{STRIP_T_INC}}":   str(col_totals[0]),
        "{{INC_LABEL}}":     labels.get("inclusion", ""),
        # Page 5 — Control
        "{{STRIP_E_CON}}":   str(matrix[0][1]),
        "{{STRIP_W_CON}}":   str(matrix[1][1]),
        "{{STRIP_T_CON}}":   str(col_totals[1]),
        "{{CON_LABEL}}":     labels.get("control", ""),
        # Page 6 — Affection
        "{{STRIP_E_AFF}}":   str(matrix[0][2]),
        "{{STRIP_W_AFF}}":   str(matrix[1][2]),
        "{{STRIP_T_AFF}}":   str(col_totals[2]),
        "{{AFF_LABEL}}":     labels.get("affection", ""),
        # Page 7 — Snapshot (uses _2 suffix to stay unique)
        "{{STRIP_T_INC_2}}": str(col_totals[0]),
        "{{STRIP_T_CON_2}}": str(col_totals[1]),
        "{{STRIP_T_AFF_2}}": str(col_totals[2]),
        "{{STRIP_G_TOT_2}}": str(grand_total),
        # Page 8 — Group dynamics
        "{{STRIP_T_EXP_2}}": str(row_totals[0]),
        "{{STRIP_T_WAN_2}}": str(row_totals[1]),
        # Page 9 — People (uses _3 suffix)
        "{{STRIP_T_INC_3}}": str(col_totals[0]),
        "{{STRIP_T_CON_3}}": str(col_totals[1]),
        "{{STRIP_T_AFF_3}}": str(col_totals[2]),
    }
    for placeholder, value in strip_map.items():
        html = html.replace(placeholder, value)

    # ── AI section placeholders ──────────────────────────────────────────────
    sections = parse_report_sections(ai_report_text)
    for key, content in sections.items():
        html = html.replace("{{" + key + "}}", content)

    return html