VALID_TRANSITIONS = {
    "OPEN": ["INVESTIGATING"],
    "INVESTIGATING": ["RESOLVED"],
    "RESOLVED": ["CLOSED"],
    "CLOSED": []
}


def validate_status_transition(current_status: str, new_status: str):
    current_status = current_status.upper()
    new_status = new_status.upper()

    allowed_next_states = VALID_TRANSITIONS.get(current_status, [])

    if new_status not in allowed_next_states:
        return False, f"Invalid transition from {current_status} to {new_status}"

    return True, "Valid transition"