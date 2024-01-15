import subprocess
import os

def checkout_project(project_name, version):
    write_to = os.path.join("auto_gpt_workspace", "{}_{}_buggy".format(project_name.lower(), version))
    command = f'defects4j checkout -p {project_name} -v {version}b -w {write_to}'

    # Execute the command
    try:
        subprocess.run(command, shell=True, check=True)
        print("Checkout completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Checkout failed with error: {e}")


projects_list = [("Chart", 1), ("Cli", 8), ("Chart", 8),
                 ("Chart", 9), ("Cli", 25), ("Closure", 10),
                 ("Closure", 13), ("Closure", 14), ("Codec", 2),
                 ("Codec", 3), ("Codec", 4), ("Compress", 1),
                 ("Compress", 16), ("Compress", 19), ("Csv", 1),
                 ("Csv", 4), ("Gson", 13), ("Gson", 15),
                 ("JacksonCore", 5), ("JacksonCore", 8)]


for project, bug_number in projects_list:
    checkout_project(project, bug_number)

