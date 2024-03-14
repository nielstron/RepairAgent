import os

base_dir = "defects4j/framework/projects/"

def get_list_of_projects(path="defects4j/framework/projects"):
    dirs = os.listdir(path)
    projects = []
    for d in dirs:
        if os.path.isdir(os.path.join(path, d)) and d!="lib":
            projects.append(d)
    return projects


def get_list_of_bugs(project_path):
    patches = [p.split(".")[0] for p in os.listdir(os.path.join(project_path, "patches")) if "src" in p]
    return patches


projects = get_list_of_projects()
bugs_list = []
for p in projects:
    project_path = os.path.join(base_dir, p)
    bugs = get_list_of_bugs(project_path)
    for b in bugs:
        bugs_list.append((p, b))

print(len(bugs_list))

with open("chatrepair_list.txt") as crlt:
    chatrepair_list = crlt.read()

chatrepair_list = chatrepair_list.split(",")
chatrepair_list = [tuple(c.split("_")) for c in chatrepair_list]

def construct_batches_files(dir_to_save, bugs_list, excludes, batch_size=10, batches_number = 72):
    filtered_list = [b for b in bugs_list if b not in excludes]
    chunks = [filtered_list[i:i+batch_size] for i in range(0, len(filtered_list), batch_size)][:batches_number]
    for i, chunk in enumerate(chunks):
        with open(os.path.join(dir_to_save, str(i)), "w") as svfile:
            svfile.write("\n\n".join([" ".join(c) for c in chunk]))

construct_batches_files("experimental_setups/batches", bugs_list, chatrepair_list)