COMMAND_CATEGORY = "states"
COMMAND_CATEGORY_TITLE = "STATES"
ALLOWLIST_CONTROL = "allowlist"
DENYLIST_CONTROL = "denylist"

"""@command(
    "change_state",
    "this command allows you to change the current state based on info that you collected and the next steps that you want to make. As intput to this function, give the name of the state that you want to switch to (next_state arg)",
    {
        "next_state_name": {
            "type": "string",
            "description": "The name the next_state",
            "required": True,
        }
    },
)"""
def change_state(next_state_name: str) -> str:
    return "==>" + next_state_name