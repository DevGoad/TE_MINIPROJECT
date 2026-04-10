"""
team_analyzer.py
────────────────
Team Report Analysis — independent of report_generator.py.

Flow:
  1. extract_report_data(bytes, name)   → scores from individual report PDF
  2. generate_team_analysis(members, …) → Gemini AI text (called once)
  3. render_team_report(members, …)     → complete HTML report string
"""

import os, re, io, time
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY2"))

_RULES_FILE = None
_TECH_FILE  = None


# ─────────────────────────────────────────────────────────────────────
#  PDF UPLOAD
# ─────────────────────────────────────────────────────────────────────

def _upload_pdf(path: str):
    if not os.path.exists(path):
        return None
    f = client.files.upload(file=path)
    while f.state.name == "PROCESSING":
        time.sleep(2)
        f = client.files.get(name=f.name)
    if f.state.name != "ACTIVE":
        raise RuntimeError(f"PDF upload failed: {path}")
    return f


def _ensure_pdfs():
    global _RULES_FILE, _TECH_FILE
    if _RULES_FILE is None:
        print("[team_analyzer] uploading firo_b_rules.pdf …")
        _RULES_FILE = _upload_pdf("firo_b_rules.pdf")
    if _TECH_FILE is None and os.path.exists("technical_guide.pdf"):
        print("[team_analyzer] uploading technical_guide.pdf …")
        _TECH_FILE = _upload_pdf("technical_guide.pdf")


# ─────────────────────────────────────────────────────────────────────
#  SCORE EXTRACTION
# ─────────────────────────────────────────────────────────────────────

def _find_firo_sequence(text: str):
    """
    Scan for 12 integers satisfying all FIRO-B arithmetic constraints.
    Works regardless of PDF text layout (DOM-order or visual-order).
    """
    nums = [int(n) for n in re.findall(r'\b(\d+)\b', text) if int(n) <= 54]
    for i in range(len(nums) - 11):
        w = nums[i:i + 12]
        if not all(0 <= v <= 9  for v in [w[0], w[1], w[2], w[4], w[5], w[6]]):
            continue
        if not all(0 <= v <= 18 for v in [w[8], w[9], w[10]]):
            continue
        if w[3]  != w[0] + w[1] + w[2]:   continue   # T_EXP
        if w[7]  != w[4] + w[5] + w[6]:   continue   # T_WAN
        if w[8]  != w[0] + w[4]:           continue   # T_INC
        if w[9]  != w[1] + w[5]:           continue   # T_CON
        if w[10] != w[2] + w[6]:           continue   # T_AFF
        if w[11] != w[8] + w[9] + w[10]:   continue   # G_TOT
        return w
    return None


def extract_report_data(file_bytes: bytes, name: str) -> dict:
    """Parse FIRO-B scores from a browser-printed individual report PDF."""
    try:
        import pypdf
        reader     = pypdf.PdfReader(io.BytesIO(file_bytes))
        page_texts = [p.extract_text() or "" for p in reader.pages]
    except ImportError:
        print("[ERROR] pypdf not installed. Run: pip install pypdf")
        page_texts = [""]
    except Exception as exc:
        print(f"[ERROR] PDF read: {exc}")
        page_texts = [""]

    full_text = "\n".join(page_texts)

    # ── Method 1 (most reliable): "Your result of N suggests" ────────
    # The Individual Needs table on page 4 of every individual report
    # contains exactly 6 sentences "Your result of N suggests …"
    # in the fixed order: EI, WI, EC, WC, EA, WA.
    yr_matches = re.findall(r'Your result of\s+(\d+)', full_text)
    if len(yr_matches) >= 6:
        e_inc = int(yr_matches[0])
        w_inc = int(yr_matches[1])
        e_con = int(yr_matches[2])
        w_con = int(yr_matches[3])
        e_aff = int(yr_matches[4])
        w_aff = int(yr_matches[5])
        t_exp = e_inc + e_con + e_aff
        t_wan = w_inc + w_con + w_aff
        t_inc = e_inc + w_inc
        t_con = e_con + w_con
        t_aff = e_aff + w_aff
        g_tot = t_inc + t_con + t_aff

        # Profile labels from "Profile: LABEL | eI = N" pattern pages
        labels    = re.findall(r'Profile:\s*(.+?)\s*\|', full_text)
        inc_label = labels[0].strip() if len(labels) > 0 else "—"
        con_label = labels[1].strip() if len(labels) > 1 else "—"
        aff_label = labels[2].strip() if len(labels) > 2 else "—"

        cover = page_texts[0] if page_texts else ""
        def ci(label: str, default="—") -> str:
            m = re.search(re.escape(label) + r'[\s\n]+([^\n]+)', cover, re.I)
            if m:
                v = m.group(1).strip()
                if v and not re.match(
                    r'^(Age|Gender|Occupation|Field|Team|Assessment|Report|Scored|FIRO)',
                    v, re.I
                ):
                    return v
            return default

        return {
            "name":        name.strip() or ci("Report prepared for") or "Unknown",
            "age":         ci("Age"),
            "gender":      ci("Gender"),
            "occupation":  ci("Occupation"),
            "designation": ci("Field / Designation"),
            "team_type":   ci("Team Context"),
            "e_inc": e_inc, "w_inc": w_inc,
            "e_con": e_con, "w_con": w_con,
            "e_aff": e_aff, "w_aff": w_aff,
            "t_exp": t_exp, "t_wan": t_wan,
            "t_inc": t_inc, "t_con": t_con, "t_aff": t_aff,
            "g_tot": g_tot,
            "inc_label": inc_label,
            "con_label": con_label,
            "aff_label": aff_label,
        }

    # ── Method 2: eI = N notation from pattern-score paragraphs ──────
    # The pattern pages contain "eI = N | wI = N | Total Need ... = N"
    def _rx(pat):
        m = re.search(pat, full_text, re.I)
        return int(m.group(1)) if m else 0

    ei2 = _rx(r'eI\s*=\s*(\d+)')
    wi2 = _rx(r'wI\s*=\s*(\d+)')
    ec2 = _rx(r'eC\s*=\s*(\d+)')
    wc2 = _rx(r'wC\s*=\s*(\d+)')
    ea2 = _rx(r'eA\s*=\s*(\d+)')
    wa2 = _rx(r'wA\s*=\s*(\d+)')
    if (ei2 + wi2 + ec2 + wc2 + ea2 + wa2) > 0:
        e_inc, w_inc = ei2, wi2
        e_con, w_con = ec2, wc2
        e_aff, w_aff = ea2, wa2
        t_exp = e_inc + e_con + e_aff
        t_wan = w_inc + w_con + w_aff
        t_inc = e_inc + w_inc
        t_con = e_con + w_con
        t_aff = e_aff + w_aff
        g_tot = t_inc + t_con + t_aff

        labels    = re.findall(r'Profile:\s*(.+?)\s*\|', full_text)
        inc_label = labels[0].strip() if len(labels) > 0 else "—"
        con_label = labels[1].strip() if len(labels) > 1 else "—"
        aff_label = labels[2].strip() if len(labels) > 2 else "—"

        cover = page_texts[0] if page_texts else ""
        def ci2(label: str, default="—") -> str:
            m = re.search(re.escape(label) + r'[\s\n]+([^\n]+)', cover, re.I)
            if m:
                v = m.group(1).strip()
                if v and not re.match(
                    r'^(Age|Gender|Occupation|Field|Team|Assessment|Report|Scored|FIRO)',
                    v, re.I
                ):
                    return v
            return default

        return {
            "name":        name.strip() or ci2("Report prepared for") or "Unknown",
            "age":         ci2("Age"),
            "gender":      ci2("Gender"),
            "occupation":  ci2("Occupation"),
            "designation": ci2("Field / Designation"),
            "team_type":   ci2("Team Context"),
            "e_inc": e_inc, "w_inc": w_inc,
            "e_con": e_con, "w_con": w_con,
            "e_aff": e_aff, "w_aff": w_aff,
            "t_exp": t_exp, "t_wan": t_wan,
            "t_inc": t_inc, "t_con": t_con, "t_aff": t_aff,
            "g_tot": g_tot,
            "inc_label": inc_label,
            "con_label": con_label,
            "aff_label": aff_label,
        }

    # Locate results-grid page (page 3 of individual report)
    results_page = full_text
    for pt in page_texts:
        if re.search(
            r'\[eI\]|Total\s+Need\s+for\s+Inclusion|Overall\s+Interpersonal',
            pt, re.I
        ):
            results_page = pt
            break

    # Primary: sequence-based extraction (layout-agnostic)
    seq = _find_firo_sequence(results_page) or _find_firo_sequence(full_text)

    if seq:
        e_inc, e_con, e_aff, t_exp = seq[0], seq[1], seq[2],  seq[3]
        w_inc, w_con, w_aff, t_wan = seq[4], seq[5], seq[6],  seq[7]
        t_inc, t_con, t_aff, g_tot = seq[8], seq[9], seq[10], seq[11]
    else:
        # Fallback: label-proximity
        def lp(text, *pats, mv=9):
            for p in pats:
                m = re.search(p + r'[^0-9]{0,80}?(\d+)', text, re.I | re.S)
                if m:
                    v = int(m.group(1))
                    if 0 <= v <= mv:
                        return v
            return 0

        e_inc = lp(results_page, r'\[eI\]', r'Expressed\s+Inclusion', mv=9)
        e_con = lp(results_page, r'\[eC\]', r'Expressed\s+Control',   mv=9)
        e_aff = lp(results_page, r'\[eA\]', r'Expressed\s+Affection', mv=9)
        w_inc = lp(results_page, r'\[wI\]', r'Wanted\s+Inclusion',    mv=9)
        w_con = lp(results_page, r'\[wC\]', r'Wanted\s+Control',      mv=9)
        w_aff = lp(results_page, r'\[wA\]', r'Wanted\s+Affection',    mv=9)
        t_exp = lp(results_page, r'Total\s+Expressed\s+Behavior', mv=27)
        t_wan = lp(results_page, r'Total\s+Wanted\s+Behavior',    mv=27)
        t_inc = lp(results_page, r'Total\s+Need\s+for\s+Inclusion', mv=18)
        t_con = lp(results_page, r'Total\s+Need\s+for\s+Control',   mv=18)
        t_aff = lp(results_page, r'Total\s+Need\s+for\s+Affection', mv=18)
        g_tot = lp(results_page, r'Overall\s+Interpersonal\s+Needs', mv=54)

        # Mathematical fallbacks
        if t_exp == 0: t_exp = e_inc + e_con + e_aff
        if t_wan == 0: t_wan = w_inc + w_con + w_aff
        if t_inc == 0: t_inc = e_inc + w_inc
        if t_con == 0: t_con = e_con + w_con
        if t_aff == 0: t_aff = e_aff + w_aff
        if g_tot == 0: g_tot = t_inc + t_con + t_aff

    # Profile labels (appear as "Profile: Label |" on pattern pages)
    labels    = re.findall(r'Profile:\s*(.+?)\s*\|', full_text)
    inc_label = labels[0].strip() if len(labels) > 0 else "—"
    con_label = labels[1].strip() if len(labels) > 1 else "—"
    aff_label = labels[2].strip() if len(labels) > 2 else "—"

    # User details from cover page
    cover = page_texts[0] if page_texts else ""

    def ci(label: str, default="—") -> str:
        m = re.search(re.escape(label) + r'[\s\n]+([^\n]+)', cover, re.I)
        if m:
            v = m.group(1).strip()
            if v and not re.match(
                r'^(Age|Gender|Occupation|Field|Team|Assessment|Report|Scored|FIRO)',
                v, re.I
            ):
                return v
        return default

    return {
        "name":        name.strip() or ci("Report prepared for") or "Unknown",
        "age":         ci("Age"),
        "gender":      ci("Gender"),
        "occupation":  ci("Occupation"),
        "designation": ci("Field / Designation"),
        "team_type":   ci("Team Context"),
        "e_inc": e_inc, "w_inc": w_inc,
        "e_con": e_con, "w_con": w_con,
        "e_aff": e_aff, "w_aff": w_aff,
        "t_exp": t_exp, "t_wan": t_wan,
        "t_inc": t_inc, "t_con": t_con, "t_aff": t_aff,
        "g_tot": g_tot,
        "inc_label": inc_label,
        "con_label": con_label,
        "aff_label": aff_label,
    }


# ─────────────────────────────────────────────────────────────────────
#  GEMINI TEAM ANALYSIS
# ─────────────────────────────────────────────────────────────────────

def _member_block(m: dict) -> str:
    return f"""Name          : {m['name']}
Occupation    : {m['occupation']} — {m['designation']}

INCLUSION  (social contact & belonging)
  Expressed   : {m['e_inc']} / 9  (how actively they include others)
  Wanted      : {m['w_inc']} / 9  (how much they want to be included)
  Total       : {m['t_inc']} / 18  Profile: {m['inc_label']}

CONTROL  (decision-making & authority)
  Expressed   : {m['e_con']} / 9  (how much they direct / lead)
  Wanted      : {m['w_con']} / 9  (how much structure they seek)
  Total       : {m['t_con']} / 18  Profile: {m['con_label']}

AFFECTION  (warmth & closeness)
  Expressed   : {m['e_aff']} / 9  (how warm / open they are)
  Wanted      : {m['w_aff']} / 9  (how much warmth they seek)
  Total       : {m['t_aff']} / 18  Profile: {m['aff_label']}

Total Expressed (initiative) : {m['t_exp']} / 27
Total Wanted   (receptivity) : {m['t_wan']} / 27
Overall Interpersonal Need   : {m['g_tot']} / 54"""


def generate_team_analysis(members: list, team_type: str, team_name: str) -> str:
    _ensure_pdfs()

    members_text = "\n\n---\n\n".join(
        f"[{m['name']}]\n{_member_block(m)}" for m in members
    )
    names   = ", ".join(m["name"] for m in members)
    label   = f'"{team_name}"' if team_name else "the team"
    context = team_type or "team project"

    prompt = f"""
You are analysing the FIRO-B® interpersonal profiles of {len(members)} team members
in {label}, working together on: {context}.

MEMBER DATA:
{members_text}

STRICT FORMAT RULES (read carefully before writing):
1. Output EXACTLY 8 sections separated by "--- SECTION N ---" markers.
2. No text before Section 1 or after Section 8.
3. Use bullet points (lines starting with "- ") for all content.
4. Use "- **bold heading**" on its own bullet to introduce a sub-topic.
5. NEVER use markdown tables (no pipe characters for tables).
6. NEVER write page numbers. Do NOT write "page 11", "(page 19)" or similar.
7. Always write full terms — never abbreviations like eI, wI, eC, wC, eA, wA.
   Write "Expressed Inclusion", "Wanted Control", etc.
8. When citing a score, write it as e.g. "{members[0]['name']}'s Expressed Inclusion score of {members[0]['e_inc']}" — never "eI={members[0]['e_inc']}".

--- SECTION 1 ---
**Overall Team Behavioral Profile**
One bullet per question, 2-3 sentences each:
- **People-oriented or task-oriented?** (reference actual scores)
- **Leadership style: centralised, distributed, or absent?**
- **Structure or flexibility preference?**
- **Emotional climate: supportive / neutral / strained — and why.**

--- SECTION 2 ---
**Natural Role Distribution in the Team**
Name specific members. For each role, say who fills it and why (based on scores).
If no member suits a role, explain why not.
- **Likely informal leaders**
- **Coordinators and facilitators**
- **Executors and doers**
- **Supporters and harmonizers**
- **Silent contributors**

--- SECTION 3 ---
**Team Strengths — What Will Work Well**
At least 2 bullets per area:
- **Collaboration strengths**
- **Communication strengths**
- **Decision-making advantages**
- **Emotional support dynamics**

--- SECTION 4 ---
**Likely Conflict Zones**
For each conflict type, provide exactly three bullets:
  - **Who is involved** (name them)
  - **Why it may arise** (cite actual scores in plain English)
  - **When most likely** (start / mid / deadline phase)

Cover all five:
- **Leadership struggles**
- **Dependency conflicts**
- **Emotional overload**
- **Decision delays**
- **Avoidance and disengagement**

--- SECTION 5 ---
**Communication and Working Style Mismatches**
Name specific members, explain the reason in 2-3 sentences each:
- **Who may feel unheard and why**
- **Who may feel overburdened and why**
- **Who may feel micromanaged and why**
- **Who may disengage silently and why**

--- SECTION 6 ---
**Stress and Performance Risks**
For each scenario, name the affected member(s) and explain the trigger:
- **Tight deadlines**
- **Ambiguous tasks or unclear expectations**
- **Authority-free environments**
- **Forced social interaction or team-building**
- **Emotional demands or interpersonal conflict**
- **Criticism or perceived failure**

--- SECTION 7 ---
**Conflict Mitigation and Team Management Strategies**
Provide 6-8 actionable strategies. Each must have:
- A bold heading on a bullet: "- **Strategy Name**"
- 2-3 sentences explaining what to do and why it works for this specific team.

--- SECTION 8 ---
**Role and Responsibility Recommendations**
Assign specific members from {names} by name. Give the behavioral reason.
If no one suits a role, recommend an alternative approach.
- **Team coordinator / project lead**
- **Deadline and task manager**
- **Communication owner**
- **Documentation and analysis owner**
- **Conflict resolver and harmonizer**
"""

    sys_inst = (
        "You are a certified FIRO-B® psychometrician and organisational team coach. "
        "Analyse using ONLY the attached reference documents as interpretive guidelines. "
        "Write in professional English suitable for a printed management report. "
        "Name individuals; cite their actual scores when making behavioural claims. "
        "⚠️ ABSOLUTE RULES — breaking any of these will make the report unusable: "
        "(1) NEVER write page number citations. Not '(page 11)', not 'page 25', not any similar form. Zero exceptions. "
        "(2) NEVER use shorthand notation: eI, wI, eC, wC, eA, wA. Always write the full term. "
        "(3) NEVER use markdown tables or pipe characters (|) for layout. "
        "(4) For 'when most likely to occur' — write it as a short inline phrase inside the same sentence, never as a separate label or column."
    )

    contents = []
    if _RULES_FILE: contents.append(_RULES_FILE)
    if _TECH_FILE:  contents.append(_TECH_FILE)
    contents.append(prompt)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=sys_inst,
                temperature=0.3,
            ),
            contents=contents,
        )
        return response.text
    except Exception as e:
        return f"**AI Generation Failed:** {str(e)}"


# ─────────────────────────────────────────────────────────────────────
#  MARKDOWN → HTML
# ─────────────────────────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    lines, out, in_ul = text.split("\n"), [], False

    for raw in lines:
        line = raw.strip()

        if not line:
            if in_ul: out.append("</ul>"); in_ul = False
            continue

        # Drop markdown table separator rows
        if re.match(r'^[\s|:\-]+$', line) and '|' in line:
            continue

        # Convert pipe-table rows to bullet items
        if line.startswith('|') or (line.count('|') >= 2 and '|' in line[:3]):
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                content = ' — '.join(
                    re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', c) for c in cells
                )
                if not in_ul: out.append('<ul>'); in_ul = True
                out.append(f'  <li>{content}</li>')
            continue

        # Bullet point
        if line.startswith('- ') or line.startswith('• '):
            raw_c  = line[2:]
            is_lh  = bool(re.match(r'^\*\*[^*]+\*\*:?\s*$', raw_c))
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', raw_c)
            content = re.sub(r'\*(.*?)\*',     r'<em>\1</em>',          content)
            if is_lh:
                # Bold-only bullet → h4 so the page-splitter can split here
                if in_ul: out.append('</ul>'); in_ul = False
                out.append(f'<h4>{content}</h4>')
            else:
                if not in_ul: out.append('<ul>'); in_ul = True
                out.append(f'  <li>{content}</li>')

        # Standalone bold line → section sub-heading
        elif re.match(r'^\*\*[^*]+\*\*\s*$', line):
            if in_ul: out.append('</ul>'); in_ul = False
            inner = re.sub(r'^\*\*(.*)\*\*\s*$', r'\1', line).rstrip(':')
            out.append(f'<h4>{inner}</h4>')

        # Markdown # heading
        elif line.startswith('#'):
            if in_ul: out.append('</ul>'); in_ul = False
            out.append(f'<h4>{re.sub(r"^#+\s*", "", line)}</h4>')

        # Paragraph
        else:
            if in_ul: out.append('</ul>'); in_ul = False
            conv = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            conv = re.sub(r'\*(.*?)\*',     r'<em>\1</em>',          conv)
            out.append(f'<p>{conv}</p>')

    if in_ul: out.append('</ul>')
    return '\n'.join(out)


def _parse_sections(raw: str) -> dict:
    parts    = re.split(r'-{2,3}\s*SECTION\s+(\d+)\s*-{2,3}', raw)
    page_map = {}
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            page_map[parts[i].strip()] = parts[i + 1].strip()

    sections = {}
    for i in range(1, 9):
        raw_sec = page_map.get(str(i), "")
        if not raw_sec:
            sections[i] = "<p>Content not available.</p>"
            continue
        lines, start = raw_sec.split("\n"), 0
        for j, ln in enumerate(lines):
            if ln.strip():
                if re.match(r'^\*\*.*\*\*\s*$', ln.strip()):
                    start = j + 1
                break
        sections[i] = _md_to_html("\n".join(lines[start:]).strip())
    return sections


# ─────────────────────────────────────────────────────────────────────
#  RENDER HELPERS
# ─────────────────────────────────────────────────────────────────────

_COLORS = ["#1e6fa8", "#d85c18", "#2d7d32", "#7d3c98"]

_SECTION_META = [
    (1, "Overall Team Behavioral Profile",      "🧩", False),
    (2, "Natural Role Distribution",             "🎯", False),
    (3, "Team Strengths",                        "💪", False),
    (4, "Likely Conflict Zones",                 "⚠️", True),
    (5, "Communication & Style Mismatches",      "💬", False),
    (6, "Stress & Performance Risks",            "📉", True),
    (7, "Conflict Mitigation Strategies",        "🛠️", False),
    (8, "Role & Responsibility Recommendations", "📋", False),
]

# Maximum <h4> items per A4 page for sections that produce long content.
# 99 = no split (all other sections fit on one page).
_ITEMS_PER_PAGE = {
    4: 2,   # Likely Conflict Zones  — 5 types  → 3 pages (2 + 2 + 1)
    6: 3,   # Stress & Performance   — 6 risks   → 2 pages (3 + 3)
    7: 3,   # Conflict Mitigation    — 8 strats  → 3 pages (3 + 3 + 2)
}


def _split_at_h4(html: str, per_page: int) -> list:
    """
    Split html at every <h4> boundary and group per_page chunks per page.
    Because _md_to_html now emits <h4> for ALL bold-only bullets, this
    works uniformly for every section — no separate li.lh handling needed.
    """
    if per_page >= 99:
        return [html]

    parts  = re.split(r'(?=<h4>)', html)
    chunks = [p for p in parts if p.strip()]   # drop empty preamble

    if len(chunks) <= per_page:
        return [html]   # already fits — no split needed

    pages = []
    for i in range(0, len(chunks), per_page):
        pages.append('\n'.join(chunks[i : i + per_page]))
    return pages


def _score_bar(score: int, maxv: int = 9, color: str = "#5c2d82") -> str:
    pct = min(100, round(score / maxv * 100)) if maxv else 0
    lvl = ("Low" if pct <= 33 else "Med" if pct <= 66 else "High")
    return (
        f'<span class="sb-val">{score}</span>'
        f'<span class="sb-wrap">'
        f'<span class="sb-fill" style="width:{pct}%;background:{color};"></span>'
        f'</span>'
        f'<span class="sb-lbl">{lvl}</span>'
    )


def _member_card(m: dict, idx: int) -> str:
    c, ltr = _COLORS[idx % 4], chr(65 + idx)
    return f"""
<div class="mc">
  <div class="mc-top" style="background:{c};">
    <span class="mc-let">{ltr}</span>
    <div class="mc-info">
      <div class="mc-name">{m['name']}</div>
      <div class="mc-sub">{m['occupation']} · {m['designation']}</div>
    </div>
    <div class="mc-ov">
      <div class="mc-ov-n">{m['g_tot']}</div>
      <div class="mc-ov-l">Overall</div>
    </div>
  </div>
  <div class="mc-body">
    <div class="mc-row">
      <span class="mc-rl" style="color:#1e6fa8;">Inclusion</span>
      <span class="mc-rs">
        {_score_bar(m['e_inc'],'9'if False else 9,'#1e6fa8')} Exp &nbsp;
        {_score_bar(m['w_inc'],9,'#6699cc')} Want &nbsp;
        <strong style="color:#1e6fa8;">{m['t_inc']}/18</strong>
      </span>
    </div>
    <div class="mc-row">
      <span class="mc-rl" style="color:#d85c18;">Control</span>
      <span class="mc-rs">
        {_score_bar(m['e_con'],9,'#d85c18')} Exp &nbsp;
        {_score_bar(m['w_con'],9,'#e09050')} Want &nbsp;
        <strong style="color:#d85c18;">{m['t_con']}/18</strong>
      </span>
    </div>
    <div class="mc-row">
      <span class="mc-rl" style="color:#2d7d32;">Affection</span>
      <span class="mc-rs">
        {_score_bar(m['e_aff'],9,'#2d7d32')} Exp &nbsp;
        {_score_bar(m['w_aff'],9,'#5aaa60')} Want &nbsp;
        <strong style="color:#2d7d32;">{m['t_aff']}/18</strong>
      </span>
    </div>
    <div class="mc-chips">
      <span class="mc-chip" style="border-color:#1e6fa8;color:#1e6fa8;">{m['inc_label']}</span>
      <span class="mc-chip" style="border-color:#d85c18;color:#d85c18;">{m['con_label']}</span>
      <span class="mc-chip" style="border-color:#2d7d32;color:#2d7d32;">{m['aff_label']}</span>
    </div>
  </div>
</div>"""


def _section_page(sn, title, icon, alert, members, content, label, start_pg):
    """
    Render one section as one or more standalone A4 .page divs.
    Long sections (4, 6, 7) are automatically split across multiple pages
    at <h4> boundaries so no content is ever hidden by overflow.
    """
    ac     = "#c02020" if alert else "#5c2d82"
    h4_bg  = "#fce8e8" if alert else "#f0eaf8"
    chips  = "".join(
        f'<span class="ms-chip" style="background:{_COLORS[i%4]}1a;'
        f'border:1px solid {_COLORS[i%4]}66;color:{_COLORS[i%4]};">'
        f'{chr(65+i)}&nbsp;{m["name"]}&nbsp;({m["g_tot"]})</span>'
        for i, m in enumerate(members)
    )

    per_page   = _ITEMS_PER_PAGE.get(sn, 99)
    page_parts = _split_at_h4(content, per_page)

    # Per-section CSS injected once (same class targets all pages of this section)
    section_css = (
        f'<style>'
        f'.p{sn} h4 {{'
        f'  color:{ac};'
        f'  border-left-color:{ac};'
        f'  background:{h4_bg};'
        f'}}'
        f'.p{sn} li::before {{ color:{ac}; }}'
        f'</style>'
    )

    pages_html = []
    for page_idx, part_html in enumerate(page_parts):
        pg_num     = start_pg + page_idx
        cont_label = f" (cont'd)" if page_idx > 0 else ""

        ph = (
            f'<div class="ph">'
            f'<span>Team Analysis Report — {label}</span>'
            f'<span>{title}{cont_label} | Page {pg_num}</span>'
            f'</div>'
        )

        if page_idx == 0:
            top = (
                f'<div class="sec-hdr">'
                f'<span class="s-icon">{icon}</span>'
                f'<span class="s-title" style="color:{ac};">{title}</span>'
                f'</div>'
                f'<div class="ms">{chips}</div>'
            )
        else:
            top = (
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
                f'<span style="font-size:13pt;">{icon}</span>'
                f'<span style="font-size:10pt;font-weight:700;text-transform:uppercase;'
                f'color:{ac};letter-spacing:.3px;">{title} — continued</span>'
                f'</div>'
                f'<div class="ms">{chips}</div>'
            )

        pages_html.append(
            f'<div class="page">'
            f'{ph}'
            f'{section_css}'
            f'{top}'
            f'<div class="ai p{sn}">{part_html}</div>'
            f'</div>'
        )

    return "\n".join(pages_html)


# ─────────────────────────────────────────────────────────────────────
#  RENDER TEAM REPORT
# ─────────────────────────────────────────────────────────────────────

def render_team_report(members, team_name, team_type, ai_text):
    sections     = _parse_sections(ai_text)
    date_str     = datetime.now().strftime("%B %d, %Y")
    label        = team_name.strip() or "Team Analysis"
    n            = len(members)
    names_str    = ", ".join(m["name"] for m in members)
    member_cards = "\n".join(_member_card(m, i) for i, m in enumerate(members))

    # ── Build section pages with accurate running page numbers ───────
    # Cover = page 1, Contents = page 2, sections start at page 3.
    running_pg      = 3
    sec_parts       = []
    toc_entries     = []

    for sn, title, icon, alert in _SECTION_META:
        content    = sections.get(sn, "<p>Not available.</p>")
        page_html  = _section_page(sn, title, icon, alert,
                                   members, content, label, running_pg)
        sec_parts.append(page_html)
        toc_entries.append((icon, title, running_pg))

        # Count how many .page divs were emitted for this section
        running_pg += page_html.count('<div class="page">')

    sec_pages = "\n".join(sec_parts)

    toc_rows = "".join(
        f'<div class="toc-row">'
        f'<span class="ti">{ic}</span>'
        f'<span class="tt">{tt}</span>'
        f'<span class="tp">Page {pg}</span>'
        f'</div>'
        for ic, tt, pg in toc_entries
    )

    score_rows = "".join(
        f'<tr>'
        f'<td style="font-weight:700;color:{_COLORS[i%4]};">{chr(65+i)}</td>'
        f'<td>{m["name"]}</td>'
        f'<td class="tc">{m["e_inc"]}/{m["w_inc"]}</td>'
        f'<td class="tc">{m["e_con"]}/{m["w_con"]}</td>'
        f'<td class="tc">{m["e_aff"]}/{m["w_aff"]}</td>'
        f'<td class="tc" style="font-weight:700;color:{_COLORS[i%4]};">{m["g_tot"]}</td>'
        f'</tr>'
        for i, m in enumerate(members)
    )

    CSS = """
*, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }
body {
    font-family: Arial, 'Helvetica Neue', sans-serif;
    font-size: 10.5pt; color:#222;
    background:#c0c0c0;
    -webkit-print-color-adjust:exact; print-color-adjust:exact;
}

/* Each section is its own A4 .page div — content cannot overflow */
.page {
    background:white; width:210mm; min-height:297mm; margin:8mm auto;
    padding:14mm 18mm 16mm 18mm;
    position:relative; overflow:hidden;
    box-shadow:0 2px 14px rgba(0,0,0,.28);
}
@media print {
    body { background:white; margin:0; }
    .page {
        width:210mm; min-height:0; margin:0;
        padding:14mm 18mm 16mm 18mm;
        box-shadow:none; overflow:hidden;
        page-break-before:always; break-before:page;
    }
    .page:first-child { page-break-before:avoid; break-before:avoid; }
    @page { size:A4; margin:0; }

    /* prevent mid-element breaks within a page */
    .ai h4          { page-break-after:avoid;  break-after:avoid;  }
    .ai ul li       { page-break-inside:avoid; break-inside:avoid; }
    .ai ul          { page-break-inside:avoid; break-inside:avoid; }
    .ai p           { page-break-inside:avoid; break-inside:avoid; }
    .mc             { page-break-inside:avoid; break-inside:avoid; }
    .mg             { page-break-inside:avoid; break-inside:avoid; }
    .toc-row        { page-break-inside:avoid; break-inside:avoid; }
    .sec-hdr        { page-break-after:avoid;  break-after:avoid;  }
    .ms             { page-break-inside:avoid; break-inside:avoid; }
    .st tr          { page-break-inside:avoid; break-inside:avoid; }
    .st thead       { display:table-header-group; }
}

/* ── Running header ── */
.ph {
    display:flex; justify-content:space-between;
    font-size:7pt; color:#bbb;
    padding-bottom:5px; border-bottom:.5pt solid #e0e0e0; margin-bottom:14px;
}

/* ── Section header ── */
.sec-hdr { display:flex; align-items:center; gap:12px; margin-bottom:12px; }
.s-icon  { font-size:18pt; line-height:1; flex-shrink:0; }
.s-title {
    font-size:15pt; font-weight:900; text-transform:uppercase;
    letter-spacing:.4px; line-height:1.1;
}

/* ── Member strip ── */
.ms { display:flex; flex-wrap:wrap; gap:5px; margin-bottom:14px; }
.ms-chip {
    font-size:7.5pt; font-weight:700; padding:3px 10px;
    border-radius:12px; white-space:nowrap;
}

/* ── AI content ── */
.ai { font-size:10.5pt; line-height:1.65; }
.ai p { margin-bottom:9px; color:#333; }
.ai strong { font-weight:700; }

/* h4 now replaces li.lh — styled as the same colored left-border callout box */
.ai h4 {
    font-size:10.5pt; font-weight:600;
    border-left:3px solid; border-radius:3px;
    padding:5px 10px 5px 9px; margin:12px 0 4px 0;
    display:block;
}
.ai ul { list-style:none; padding:0; margin:2px 0 8px 0; }
.ai ul li {
    display:block;
    padding:5px 0 5px 20px;
    position:relative;
    font-size:10.5pt; line-height:1.65; margin-bottom:4px; color:#333;
}
.ai ul li::before {
    content:"•"; font-size:12pt; line-height:1.3;
    position:absolute; left:0; top:5px;
}
.ai ul li > strong:first-child { font-weight:700; }

/* ── Score bars ── */
.sb-val  { font-weight:700; font-size:9pt; min-width:14px; display:inline-block; text-align:right; }
.sb-wrap {
    display:inline-block; width:36px; height:5px;
    background:#e0e0e0; border-radius:3px; vertical-align:middle;
    margin:0 3px; position:relative; overflow:hidden;
}
.sb-fill { position:absolute; left:0; top:0; bottom:0; border-radius:3px; }
.sb-lbl  { font-size:6.5pt; color:#999; font-weight:600; text-transform:uppercase; }

/* ── Member cards ── */
.mg { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin:14px 0; }
.mc { border:.5pt solid #ddd; border-radius:8px; overflow:hidden; font-size:8pt; }
.mc-top {
    display:flex; align-items:center; gap:9px;
    padding:8px 10px; color:white;
}
.mc-let  { font-size:22pt; font-weight:900; line-height:1; opacity:.9; width:28px; flex-shrink:0; }
.mc-info { flex:1; }
.mc-name { font-size:9.5pt; font-weight:700; line-height:1.2; }
.mc-sub  { font-size:6.5pt; opacity:.85; margin-top:2px; }
.mc-ov   { text-align:center; flex-shrink:0; }
.mc-ov-n { font-size:18pt; font-weight:900; line-height:1; }
.mc-ov-l { font-size:6pt; opacity:.85; text-transform:uppercase; letter-spacing:.5px; }
.mc-body { padding:9px 10px; }
.mc-row  { display:flex; align-items:center; gap:6px; margin-bottom:6px; font-size:7.5pt; }
.mc-rl   { font-weight:700; font-size:7pt; width:52px; flex-shrink:0; }
.mc-rs   { flex:1; color:#444; }
.mc-chips { display:flex; flex-wrap:wrap; gap:4px; margin-top:7px; }
.mc-chip { font-size:6pt; padding:2px 6px; border:.75pt solid; border-radius:10px; font-weight:600; }

/* ── Cover ── */
.cb  { background:#5c2d82; height:10px; width:calc(100% + 36mm); margin:0 -18mm; }
.ct  { margin-top:16px; }
.ct h1 { font-size:26pt; font-weight:900; color:#111; }
.ct h2 { font-size:20pt; font-weight:700; color:#5c2d82; line-height:1.2; margin-top:4px; }
.ct p  { font-size:10.5pt; font-weight:600; color:#7d9800; margin-top:5px; }
.cr    { margin:12px 0; }
.cr .r1 { height:8px; background:#5c2d82; }
.cr .r2 { height:3px; background:#7d9800; margin-top:3px; }
.cm { text-align:right; margin-top:18px; font-size:9pt; color:#888; }
.cm p { margin-bottom:8px; line-height:1.5; }
.cm strong { color:#222; font-size:10pt; display:block; }
.cd {
    position:absolute; bottom:14mm; left:18mm; right:18mm;
    font-size:6pt; color:#bbb; line-height:1.6;
}

/* ── TOC ── */
.toc-row {
    display:flex; align-items:center; gap:10px;
    padding:7px 0; border-bottom:.5pt solid #eee; font-size:10pt;
}
.toc-row:last-child { border-bottom:none; }
.ti { font-size:12pt; width:22px; text-align:center; flex-shrink:0; }
.tt { flex:1; color:#333; }
.tp { font-size:8pt; color:#bbb; }

/* ── Score table ── */
.st { width:100%; border-collapse:collapse; margin:12px 0; font-size:9pt; }
.st th {
    background:#5c2d82; color:white; padding:6px 8px;
    text-align:left; font-size:8pt;
}
.st td { padding:6px 8px; border-bottom:.5pt solid #eee; vertical-align:middle; }
.st tr:nth-child(even) td { background:#fafafa; }
.st tr:last-child td { border-bottom:none; }
.tc { text-align:center !important; }
.sh { font-size:7pt; color:rgba(255,255,255,.75); font-weight:400; display:block; }
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>{CSS}</style>
</head>
<body>

<!-- PAGE 1: COVER -->
<div class="page">
  <div class="cb"></div>
  <div class="ct">
    <h1><sup style="font-size:13pt;">®</sup></h1>
    <h2>Team Compatibility<br>Analysis Report</h2>
    <p>Fundamental Interpersonal Relations Orientation — Behavioral</p>
  </div>
  <div class="cr"><div class="r1"></div><div class="r2"></div></div>
  <div class="cm">
    <p><span style="font-size:7.5pt;color:#aaa;">Team / Project</span><strong>{label}</strong></p>
    <p><span style="font-size:7.5pt;color:#aaa;">Context</span><strong>{team_type or "—"}</strong></p>
    <p><span style="font-size:7.5pt;color:#aaa;">Report Generated</span><strong>{date_str}</strong></p>
    <p><span style="font-size:7.5pt;color:#aaa;">Members Analysed</span><strong>{n}</strong></p>
  </div>
  <div class="mg">{member_cards}</div>
  <div class="cd">
    This Team Analysis Report is generated for educational and developmental purposes only.
    Behavioural interpretations are based on self-reported psychometric data and should be treated as
    indicative, not prescriptive. Do not make final personnel decisions based solely on this report.
  </div>
</div>

<!-- PAGE 2: CONTENTS -->
<div class="page">
  <div class="ph">
    <span>Team Analysis Report — {label}</span>
    <span>Contents | Page 2</span>
  </div>
  <div class="sec-hdr">
    <span class="s-icon">📑</span>
    <span class="s-title" style="color:#5c2d82;">Contents</span>
  </div>
  <p style="font-size:10pt;color:#555;line-height:1.6;margin-bottom:12px;">
    This report analyses the interpersonal profiles of <strong>{n} team members</strong>
    ({names_str}) collaborating on a <strong>{team_type or "team project"}</strong>.
    The AI psychometrician has assessed behavioural compatibility, identified potential friction,
    and recommended role distribution based on validated interpretive criteria.
  </p>
  <table class="st">
    <thead>
      <tr>
        <th></th><th>Name</th>
        <th class="tc">Inclusion<span class="sh">Exp / Want</span></th>
        <th class="tc">Control<span class="sh">Exp / Want</span></th>
        <th class="tc">Affection<span class="sh">Exp / Want</span></th>
        <th class="tc">Overall</th>
      </tr>
    </thead>
    <tbody>{score_rows}</tbody>
  </table>
  <div style="margin-top:14px;">{toc_rows}</div>
</div>

<!-- PAGES 3+: ONE .page DIV PER SECTION (long sections span multiple .page divs) -->
{sec_pages}

</body>
</html>"""