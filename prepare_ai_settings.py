import inquirer

template=\
"""ai_goals:
- Locate the bug within the project \"{name}\" (index of bug = {bug_index}),running test cases will help you to achieve this first goal
- Analyze the lines of code related to the bug and explain what you think is the buggy part
- By using the command write_range, try simple fixes at first, for example operator change, change identifier used, change numerical or boolean literal, change value of function arguments, change if conditino by reversing it, making it more specific or even less specific... Try all possible simple stupid fixes that are relevant to the buggy code.
- When simple fixes do not work, use the information you gathered to suggest more complex fixes
- Repeat the process till all the test cases pass
ai_name: AutoDebugV0.4.0
ai_role: an AI assistant that specializes in analyzing, debugging, and generating code with the primary objective of identifying and fixing bugs within Java projects. You should possess the capability to efficiently pinpoint bugs across multiple files, execute test cases to validate the fixes, and provide code solutions for rectifying the identified issues. The goal is to streamline the debugging process and suggest good fixes for existing bugs within a given project. Additionally, you should have the ability to document the changes made and write them into the respective files, ensuring seamless integration with the existing codebase. 
api_budget: 0.0"""


questions = [
    inquirer.Text("name", message="Name of the project"),
    inquirer.Text("bug_index", message="Index of the bug"),
]

answers = inquirer.prompt(questions)

settings = template.format(name=answers["name"], bug_index=answers["bug_index"])

with open("ai_settings.yaml", "w") as set_yaml:
    set_yaml.write(settings)