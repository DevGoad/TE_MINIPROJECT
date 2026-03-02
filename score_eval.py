from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

# --- 1. CONFIGURATION: ENABLE FRONTEND CONNECTION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your local HTML file to talk to this backend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. DATA MODELS ---
class EvaluationRequest(BaseModel):
    # Front end sends: { "1": 0, "2": 5 ... }
    answers: Dict[int, int] 

# --- 3. QUESTION DATABASE (From your file) ---
# Type A: Never (1) to Usually (6)
# Type B: Nobody (1) to Most People (6)
QUESTIONS = [
    {"id": 1, "text": "I try to be with people.", "type": "A"},
    {"id": 2, "text": "I let other people decide what to do.", "type": "A"},
    {"id": 3, "text": "I join social groups.", "type": "A"},
    {"id": 4, "text": "I try to have close relationships with people.", "type": "A"},
    {"id": 5, "text": "I tend to join social organizations when I have an opportunity.", "type": "A"},
    {"id": 6, "text": "I let other people strongly influence my actions.", "type": "A"},
    {"id": 7, "text": "I try to be included in informal social activities.", "type": "A"},
    {"id": 8, "text": "I try to have close, personal relationships with people.", "type": "A"},
    {"id": 9, "text": "I try to include other people in my plans.", "type": "A"},
    {"id": 10, "text": "I let other people control my actions.", "type": "A"},
    {"id": 11, "text": "I try to have people around me.", "type": "A"},
    {"id": 12, "text": "I try to get close and personal with people.", "type": "A"},
    {"id": 13, "text": "When people are doing things together I tend to join them.", "type": "A"},
    {"id": 14, "text": "I am easily led by people.", "type": "A"},
    {"id": 15, "text": "I try to avoid being alone.", "type": "A"},
    {"id": 16, "text": "I try to participate in group activities.", "type": "A"}, 
    # Switching to Type B based on file structure around Q17
    {"id": 17, "text": "I try to be friendly to people.", "type": "B"},
    {"id": 18, "text": "I let other people decide what to do.", "type": "B"},
    {"id": 19, "text": "My personal relations with people are cool and distant.", "type": "B"},
    {"id": 20, "text": "I let other people take charge of things.", "type": "B"},
    {"id": 21, "text": "I try to have close relationships with people.", "type": "B"},
    {"id": 22, "text": "I let other people strongly influence my actions.", "type": "B"},
    {"id": 23, "text": "I try to get close and personal with people.", "type": "B"},
    {"id": 24, "text": "I let other people control my actions.", "type": "B"},
    {"id": 25, "text": "I act cool and distant with people.", "type": "B"},
    {"id": 26, "text": "I am easily led by people.", "type": "B"},
    {"id": 27, "text": "I try to have close personal relationships with people.", "type": "B"},
    {"id": 28, "text": "I like people to invite me to do things.", "type": "B"},
    {"id": 29, "text": "I like people to act close and personal with me.", "type": "B"},
    {"id": 30, "text": "I try to influence strongly other peoples actions.", "type": "B"},
    {"id": 31, "text": "I like people to invite me to join in their activities.", "type": "B"},
    {"id": 32, "text": "I like people to act close towards me.", "type": "B"},
    {"id": 33, "text": "I like to take charge of things when I am with people.", "type": "B"},
    {"id": 34, "text": "I like people to include me in their activities.", "type": "B"},
    {"id": 35, "text": "I like people to act cool and distant towards me.", "type": "B"},
    {"id": 36, "text": "I like to have other people do things the way I want them done.", "type": "B"},
    {"id": 37, "text": "I like people to ask me to participate in their discussions.", "type": "B"},
    {"id": 38, "text": "I like people to act friendly towards me.", "type": "B"},
    {"id": 39, "text": "I like people to invite me to participate in their activities.", "type": "B"},
    # Back to Type A for the final block
    {"id": 40, "text": "I like people to act distant towards me.", "type": "A"},
    {"id": 41, "text": "I try to be the dominant person when I am with people.", "type": "A"},
    {"id": 42, "text": "I like people to invite me to do things.", "type": "A"},
    {"id": 43, "text": "I like people to act close towards me.", "type": "A"},
    {"id": 44, "text": "I try to have other people to do things I want done.", "type": "A"},
    {"id": 45, "text": "I like people to invite me to join their activities.", "type": "A"},
    {"id": 46, "text": "I like people to act cool and distant towards me.", "type": "A"},
    {"id": 47, "text": "I try to influence strongly other peoples actions.", "type": "A"},
    {"id": 48, "text": "I like people to include me in their activities.", "type": "A"},
    {"id": 49, "text": "I like people to act close and personal with me.", "type": "A"},
    {"id": 50, "text": "I try to take charge of things when I am with people.", "type": "A"},
    {"id": 51, "text": "I like people to invite me to participate in their activities.", "type": "A"},
    {"id": 52, "text": "I like people to act distant towards me.", "type": "A"},
    {"id": 53, "text": "I try to have other people do things the way I want them done.", "type": "A"},
    {"id": 54, "text": "I take charge of things when I am with people.", "type": "A"},
]

# --- 4. YOUR EVALUATOR LOGIC (Integrated) ---
class QuestionnaireEvaluator:
    def __init__(self):
        self.question_section_map = self._initialize_section_map()
        self.scoring_key = self._initialize_scoring_key()

    def _initialize_section_map(self) -> Dict[int, tuple]:
        # TODO: PASTE YOUR REAL SECTION MAPPING HERE
        # Example: {1: (0,0), 2: (0,1)...} based on your answer key
        mapping = {1:(0,0),2:(1,1),3:(0,0),4:(0,2),5:(0,0),6:(1,1),7:(0,0),8:(0,2),9:(0,0),10:(1,1),11:(0,0),12:(0,2),13:(0,0),14:(1,1),15:(0,0),16:(0,0),17:(0,2),18:(1,1),19:(0,2),20:(1,1),21:(0,2),22:(1,1),23:(0,2),24:(1,1),25:(0,2),26:(1,1),27:(0,2),28:(1,0),29:(1,2),30:(0,1),31:(1,0),32:(1,2),33:(0,1),34:(1,0),35:(1,2),36:(0,1),37:(1,0),38:(1,2),39:(1,0),40:(1,2),41:(0,1),42:(1,0),43:(1,2),44:(0,1),45:(1,0),46:(1,2),47:(0,1),48:(1,0),49:(1,2),50:(0,1),51:(1,0),52:(1,2),53:(0,1),54:(0,1)}
        return mapping

    def _initialize_scoring_key(self) -> Dict[int, List[int]]:
        # TODO: PASTE YOUR REAL SCORING KEY HERE
        # Format: { Q_ID: [Score_Opt1, Score_Opt2, Score_Opt3, Score_Opt4, Score_Opt5, Score_Opt6] }
        key = {
            1: [0, 0, 0, 1, 1, 1], 
            2: [0, 0, 1, 1, 1, 1], 
            3: [0, 0, 1, 1, 1, 1],
            4: [0, 0, 0, 0, 1, 1],
            5: [0, 0, 1, 1, 1, 1],
            6: [0, 0, 1, 1, 1, 1],
            7: [0, 0, 0, 1, 1, 1],
            8: [1, 1, 1, 1, 0, 0],
            9: [0, 0, 0, 0, 1, 1],
            10: [0, 0, 0, 1, 1, 1],
            11: [0, 0, 0, 0, 1, 1],
            12: [0, 0, 0, 0, 0, 1],
            13: [0, 0, 0, 0, 1, 1],
            14: [0, 0, 0, 1, 1, 1],
            15: [0, 0, 0, 0, 0, 1],
            16: [0, 0, 0, 0, 0, 1],
            17: [0, 0, 0, 0, 1, 1],
            18: [0, 0, 0, 1, 1, 1],
            19: [1, 1, 1, 0, 0, 0],
            20: [0, 0, 0, 1, 1, 1],
            21: [0, 0, 0, 1, 1, 1],
            22: [0, 0, 1, 1, 1, 1],
            23: [1, 1, 1, 1, 0, 0],
            24: [0, 0, 0, 1, 1, 1],
            25: [1, 1, 1, 0, 0, 0],
            26: [0, 0, 0, 1, 1, 1],
            27: [1, 1, 1, 1, 0, 0],
            28: [0, 0, 0, 0, 1, 1],
            29: [0, 0, 0, 0, 1, 1],
            30: [0, 0, 0, 1, 1, 1],
            31: [0, 0, 0, 0, 1, 1],
            32: [0, 0, 0, 0, 1, 1],
            33: [0, 0, 0, 1, 1, 1],
            34: [0, 0, 0, 0, 1, 1],
            35: [1, 1, 0, 0, 0, 0],
            36: [0, 0, 0, 0, 1, 1],
            37: [0, 0, 0, 0, 0, 1],
            38: [0, 0, 0, 0, 1, 1],
            39: [0, 0, 0, 0, 0, 1],
            40: [1, 1, 0, 0, 0, 0],
            41: [0, 0, 1, 1, 1, 1],
            42: [0, 0, 0, 0, 1, 1],
            43: [0, 0, 0, 0, 0, 1],
            44: [0, 0, 0, 1, 1, 1],
            45: [0, 0, 0, 0, 1, 1],
            46: [1, 1, 0, 0, 0, 0],
            47: [0, 0, 1, 1, 1, 1],
            48: [0, 0, 0, 0, 1, 1],
            49: [0, 0, 0, 0, 1, 1],
            50: [0, 0, 0, 0, 1, 1],
            51: [0, 0, 0, 0, 1, 1],
            52: [1, 1, 0, 0, 0, 0],
            53: [0, 0, 0, 0, 1, 1],
            54: [0, 0, 0, 0, 1, 1]
        }
        return key

    def evaluate(self, user_responses: Dict[int, int]) -> Dict[str, Any]:
        matrix = [[0, 0, 0], [0, 0, 0]]
        for q_id_str, selected_idx in user_responses.items():
            q_id = int(q_id_str)
            if q_id not in self.scoring_key: continue
            
            row, col = self.question_section_map[q_id]
            score = self.scoring_key[q_id][selected_idx]
            matrix[row][col] += score

        row_totals = [sum(r) for r in matrix]
        col_totals = [
            matrix[0][0] + matrix[1][0],
            matrix[0][1] + matrix[1][1],
            matrix[0][2] + matrix[1][2]
        ]
        
        return {
            "matrix": matrix,
            "row_totals": row_totals,
            "col_totals": col_totals,
            "grand_total": sum(row_totals)
        }

evaluator = QuestionnaireEvaluator()

# --- 5. API ENDPOINTS ---

@app.get("/questions")
def get_questions():
    """Returns the list of 54 questions to the frontend."""
    return QUESTIONS

@app.post("/evaluate")
def evaluate_questionnaire(request: EvaluationRequest):
    """Receives answers, calculates scores, returns matrix."""
    return evaluator.evaluate(request.answers)