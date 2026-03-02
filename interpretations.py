def get_inclusion_label(e: int, w: int) -> str:
    """
    Maps (Expressed, Wanted) Inclusion scores to labels based on image_6a0ff8.jpg
    """
    # --- ROW 1: Low Wanted (0-3) ---
    if w <= 3:
        if e <= 3: return "The Loner"
        if 4 <= e <= 5: return "Now You See Him, Now You Don't Tendency"
        if e >= 6: return "Now You See Him, Now You Don't"
    
    # --- ROW 2: Medium Wanted (4-5) ---
    if 4 <= w <= 5:
        if e <= 3:
            return "Social Flexibility" if w == 4 else "Cautious Association"
        if 4 <= e <= 5: return "Balanced / Moderate Inclusion" # Unlabeled in source
        if e >= 6: return "The Conversationalist"

    # --- ROW 3: High Wanted (6-9) ---
    if w >= 6:
        if e <= 3: return "Inhibited Individual"
        if 4 <= e <= 5: return "Hidden Inhibitions"
        if e >= 6: return "People Gatherer"
    
    return "Unknown"

def get_control_label(e: int, w: int) -> str:
    """
    Maps (Expressed, Wanted) Control scores to labels based on image_6a1020.jpg
    """
    # --- ROW 1: Low Wanted (0-3) ---
    if w <= 3:
        if e <= 3: return "The Rebel"
        if 4 <= e <= 5: return "Self-Confident"
        if e >= 6: return "Mission Impossible"

    # --- ROW 2: Medium Wanted (4-5) + 6 for Low E ---
    # Special Handling for "The Loyal Lieutenant" at e0-3, w6
    if e <= 3 and w == 6: return "The Loyal Lieutenant"

    if 4 <= w <= 5:
        if e <= 3:
            return "The Matcher" if w == 4 else "The Checker"
        if 4 <= e <= 5: return "Balanced / Moderate Control" # Unlabeled in source
        if e >= 6: return "Mission Impossible with Narcissistic Tendencies"

    # --- ROW 3: High Wanted (6-9) ---
    if w >= 6:
        if e <= 3: return "Openly Dependent Person" # Covers 7-9 (6 handled above)
        if 4 <= e <= 5: return "Let's Take a Break"
        if e >= 6: return "Dependent-Independent Conflict"
        
    return "Unknown"

def get_affection_label(e: int, w: int) -> str:
    """
    Maps (Expressed, Wanted) Affection scores to labels based on image_6a1057.jpg
    """
    # --- ROW 1: Low Wanted (0-3) ---
    if w <= 3:
        if e <= 3: return "The Pessimist"
        if 4 <= e <= 5: return "Image of Intimacy Tendency"
        if e >= 6: return "Image of Intimacy"

    # --- ROW 2: Medium Wanted (4-5) ---
    if 4 <= w <= 5:
        if e <= 3:
            return "Warm Individual / Golden Mean" if w == 4 else "Careful Moderation"
        if 4 <= e <= 5: return "Balanced / Moderate Affection" # Unlabeled in source
        if e >= 6: return "Living Up to Expectations"

    # --- ROW 3: High Wanted (6-9) ---
    if w >= 6:
        if e <= 3: return "Cautious Lover"
        if 4 <= e <= 5: return "Cautious Lover in Disguise"
        if e >= 6: return "The Optimist"
        
    return "Unknown"