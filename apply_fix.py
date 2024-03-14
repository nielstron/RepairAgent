def apply_changes(change_dict):
    file_name = change_dict.get("file_name", "")
    insertions = change_dict.get("insertions", [])
    deletions = change_dict.get("deletions", [])
    modifications = change_dict.get("modifications", [])

    # Read the original code from the file
    with open(file_name, 'r') as file:
        lines = file.readlines()

    # Apply deletions first to avoid conflicts with line number changes
    affected_lines = set()
    for line_number in deletions:
        if 1 <= line_number <= len(lines):
            lines[line_number - 1] = "\n"

    

    # Apply modifications
    for modification in modifications:
        line_number = modification.get("line_number", 0)
        modified_line = modification.get("modified_line", "")
        if 1 <= line_number <= len(lines):
            if modified_line.endswith("\n"):
                lines[line_number - 1] = modified_line
            else:
                lines[line_number - 1] = modified_line + "\n"

    # Apply insertions and record affected lines
    line_offset = 0
    from operator import itemgetter

    sorted_insertions = sorted(insertions, key=itemgetter('line_number')) 
    for insertion in sorted_insertions:
        line_number = insertion.get("line_number", 0) + line_offset
        for new_line in insertion.get("new_lines", []):
            lines.insert(line_number - 1, new_line)
            line_offset += 1


    # Write the modified code back to the file
    with open(file_name, 'w') as file:
        file.writelines(lines)

    return affected_lines

# Example usage:
changes_list = [
    {
        "file_name": "test_file_1.txt",
        "insertions": [
            {
                "line_number": 10,
                "new_lines": [
                    "    // ... new lines to insert ...\n",
                    "    // ... more new lines ...\n"
                ]
            },
            {
                "line_number": 16,
                "new_lines": [
                    "    // ... additional new lines ...\n"
                ]
            }
        ],
        "deletions": [3, 12],
        "modifications": [
            {
                "line_number": 5,
                "modified_line": "    if (dataset == null) {\n"
            },
            {
                "line_number": 14,
                "modified_line": "    int seriesCount = dataset.getColumnCount();\n"
            }
        ]
    },
    {
        "file_name": "test_file_2.txt",
        "insertions": [],
        "deletions": [],
        "modifications": [
            {
                "line_number": 3,
                "modified_line": "    days = 0\n"
            },
            {
                "line_number": 19,
                "modified_line": "    super()\n"
            }
        ]
    }
]


affected_lines = apply_changes(changes_list[1])

