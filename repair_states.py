

class State():

    def __init__(self, name):
        self.name = name
        self.description = ""




class RepairState(State):
    pass



class RepairLoop():

    def __init__():
        pass



more_info_to_fix = State(
    "more_info_to_fix",
"""In this state, you use the available commands to gather info that would help you suggest a fix for the bug.
The list of commands contains tools that would help you extract usefull info.
"""
)

more_info_to_understand = State(
    "more_info_to_understand",
"""In this state, you use the available commands to gather info that would help you suggest a fix for the bug.
From this state, you can choose to "Stay" in this state if you
"""
)