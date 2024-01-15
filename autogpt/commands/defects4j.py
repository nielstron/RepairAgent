"""Commands to execute code"""

COMMAND_CATEGORY = "defects4j"
COMMAND_CATEGORY_TITLE = "Run Tests"

import os
import subprocess
from pathlib import Path
import re
import json
import random
import time

import docker
from docker.errors import DockerException, ImageNotFound
from docker.models.containers import Container as DockerContainer

from autogpt.agents.agent import Agent
from autogpt.command_decorator import command
from autogpt.logs import logger

import javalang

ALLOWLIST_CONTROL = "allowlist"
DENYLIST_CONTROL = "denylist"

def run_checkout(name: str, index:int, agent: Agent):
    cmd_temp = "defects4j checkout -p {} -v {}b -w {}"
    folder_name = "_".join([name.lower(), str(index), "buggy"])
    if os.path.exists(os.path.join("auto_gpt_workspace", folder_name)):
        os.system("rm -rf {}".format(os.path.join("auto_gpt_workspace", folder_name)))
    cmd = cmd_temp.format(name, index, folder_name)

    """Undo the changes that you made to the project and restore the original content of all files

    Args:
        name (str): The name of the project
        index (int): The number of the target bug
        agent (Agent): The agent piloting the execution 
    Returns:
        str: The output of the checkout command
    """
    logger.info(
        f"Restoring project '{name}', bug number {index}, in working directory '{agent.config.workspace_path}'"
    )

    if we_are_running_in_a_docker_container():
        logger.debug(
            f"Auto-GPT is running in a Docker container; executing tests directly..."
        )
        result = subprocess.run(
            [cmd],
            capture_output=True,
            encoding="utf8",
            cwd=agent.config.workspace_path,
            shell=True
        )
        if result.returncode == 0:
            return "The changed files were restored to their original content"
        else:
            return f"Error: {result.stderr}"
    else:
        logger.debug("Auto-GPT is not running in a Docker container")
        return "Tricky situation! Auto-GPT is not running in a Docker container"

"""@command(
    "undo_changes",
    "Undo the changes that you made to the project, and restore the original content of all files",
    {
        "name": {
            "type": "string",
            "description": "The name of the project under scope",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you are trying to fix.",
            "required": True

        }
    },
)"""
def undo_changes(name: str, index: int, agent: Agent) -> str:
    """Undo the changes that you made to the project and restore the original content of all files

    Args:
        name (str): Project name
        index (int): The idex of the bug

    Returns:
        str: A success message or a failure message depending on the exit code
    """
    ai_name = agent.ai_config.ai_name

    return run_checkout(name, index, agent)

@command(
    "run_tests",
    "Runs the test cases of the project being analyzed",
    {
        "name": {
            "type": "string",
            "description": "The name of the project for which the test cases should be run.",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you are trying to fix.",
            "required": True

        }
    },
)
def run_tests(name: str, index: int, agent: Agent) -> str:
    """Create and execute a Python file in a Docker container and return the STDOUT of the
    executed code. If there is any data that needs to be captured use a print statement

    Args:
        code (str): The Python code to run
        name (str): A name to be given to the Python file

    Returns:
        str: The STDOUT captured from the code when it ran
    """
    ai_name = agent.ai_config.ai_name

    return run_defects4j_tests(name, index, agent)

def run_defects4j_tests(name: str, index:int, agent: Agent):
    cmd_temp = "cd {} && defects4j compile && defects4j test"
    folder_name = "_".join([name.lower(), str(index), "buggy"])
    cmd = cmd_temp.format(folder_name)

    """Run tests on a given project and a bug number

    Args:
        name (str): The name of the project for which we want to execute the test suite
        index (int): The number of the target bug (the test cases would trigger that bug)
    Returns:
        str: The output of executing the test suite
    """
    logger.info(
        f"Executing test suite for project '{name}', bug number {index}"
    )

    if we_are_running_in_a_docker_container():
        logger.debug(
            f"Auto-GPT is running in a Docker container; executing tests directly..."
        )
        result = subprocess.run(
            [cmd],
            capture_output=True,
            encoding="utf8",
            cwd=agent.config.workspace_path,
            shell=True
        )
        if result.returncode == 0:
            logger.debug(
                "NO ERROR IF: " +result.stdout)
            if "BUILD FAILED" in result.stdout:
                with open(os.path.join(agent.config.workspace_path, folder_name+"_test.txt"), "w") as testrf:
                    testrf.write("")
                undo_c = undo_changes(name, index, agent)
                return result.stdout[result.stdout.find("BUILD FAILED"):]
            else:
                with open(os.path.join(agent.config.workspace_path, folder_name+"_test.txt"), "w") as testrf:
                    testrf.write(result.stdout)
                fail_report = extract_fail_report(name, index, agent)
                undo_c = undo_changes(name, index, agent)
                return fail_report
        else:
            if "BUILD FAILED" in result.stderr:
                with open(os.path.join(agent.config.workspace_path, folder_name+"_test.txt"), "w") as testrf:
                    testrf.write("")
                undo_c = undo_changes(name, index, agent)
                return result.stderr[result.stderr.find("BUILD FAILED"):]
            else:
                with open(os.path.join(agent.config.workspace_path, folder_name+"_test.txt"), "w") as testrf:
                    testrf.write("")
                undo_c = undo_changes(name, index, agent)
                return result.stderr
    else:
        logger.debug("Auto-GPT is not running in a Docker container")
        return "Tricky situation! Auto-GPT is not running in a Docker container"
    
    # TODO("Adapt this code later to run inside docker if it's not already running")
    try:
        client = docker.from_env()
        # You can replace this with the desired Python image/version
        # You can find available Python images on Docker Hub:
        # https://hub.docker.com/_/python
        image_name = "python:3-alpine"
        try:
            client.images.get(image_name)
            logger.debug(f"Image '{image_name}' found locally")
        except ImageNotFound:
            logger.info(
                f"Image '{image_name}' not found locally, pulling from Docker Hub..."
            )
            # Use the low-level API to stream the pull response
            low_level_client = docker.APIClient()
            for line in low_level_client.pull(image_name, stream=True, decode=True):
                # Print the status and progress, if available
                status = line.get("status")
                progress = line.get("progress")
                if status and progress:
                    logger.info(f"{status}: {progress}")
                elif status:
                    logger.info(status)

        logger.debug(f"Running {file_path} in a {image_name} container...")
        container: DockerContainer = client.containers.run(
            image_name,
            [
                "python",
                file_path.relative_to(agent.workspace.root).as_posix(),
            ],
            volumes={
                str(agent.config.workspace_path): {
                    "bind": "/workspace",
                    "mode": "rw",
                }
            },
            working_dir="/workspace",
            stderr=True,
            stdout=True,
            detach=True,
        )  # type: ignore

        container.wait()
        logs = container.logs().decode("utf-8")
        container.remove()

        # print(f"Execution complete. Output: {output}")
        # print(f"Logs: {logs}")

        return logs

    except DockerException as e:
        logger.warn(
            "Could not run the script in a container. If you haven't already, please install Docker https://docs.docker.com/get-docker/"
        )
        return f"Error: {str(e)}"

    except Exception as e:
        return f"Error: {str(e)}"



def we_are_running_in_a_docker_container() -> bool:
    """Check if we are running in a Docker container

    Returns:
        bool: True if we are running in a Docker container, False otherwise
    """
    return True
    return os.path.exists("/.dockerenv")



@command(
    "get_info",
    "Gets info about a specific bug in a specific project",
    {
        "name": {
            "type": "string",
            "description": "The name of the project.",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you want to get info about.",
            "required": True

        }
    },
)
def get_info(name: str, index: int, agent: Agent) -> str:
    """Create and execute a Python file in a Docker container and return the STDOUT of the
    executed code. If there is any data that needs to be captured use a print statement

    Args:
        name (str): Project name
        index (str): Bug number

    Returns:
        str: The info about the bug given by defects4j framework
    """
    ai_name = agent.ai_config.ai_name

    return execute_get_info(name, index, agent)

def execute_get_info(name: str, index:int, agent: Agent):
    cmd_temp = "defects4j info -p {} -b {}"
    cmd = cmd_temp.format(name, index)

    """Gets info about a specific bug of a project

    Args:
        name (str): The name of the project
        index (int): The index number of the target bug
        agent (Agent): The agent piloting the execution 
    Returns:
        str: The output of the info command
    """
    logger.info(
        f"Getting info for project '{name}', bug number {index}, in working directory '{agent.config.workspace_path}'"
    )

    if we_are_running_in_a_docker_container():
        logger.debug(
            f"Auto-GPT is running in a Docker container..."
        )
        result = subprocess.run(
            [cmd],
            capture_output=True,
            encoding="utf8",
            cwd=agent.config.workspace_path,
            shell=True
        )
        if result.returncode == 0:
            root_cause = extract_root_cause(result.stdout)
            edited_files = get_edited_files(name, index)
            lines_range = extract_lines_range(name, index)
            ## need to include hunks numbers
            localization_info = get_localization(name, index)
            return root_cause + "\n"+ localization_info
        
            #"Buggy files and range of possible buggy line numbers:\n" +\
            #"\n".join(["In file: {}  ,lines from {} to {}".format(ef, *lr) for ef, lr in zip(edited_files, lines_range)]) 
        else:
            return f"Error: {result.stderr}"
    else:
        logger.debug("Auto-GPT is not running in a Docker container")
        return "Tricky situation! Auto-GPT is not running in a Docker container"
    
    # TODO("Adapt this code later to run inside docker if it's not already running")

@command(
    "read_range",
    "Read a range of lines in a given file",
    {
        "name": {
            "type": "string",
            "description": "The name of the project.",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you want to get info about.",
            "required": True

        },
        "filepath": {
            "type": "string",
            "description": "The path to the file to read from.",
            "required": True,
        },
        "startline":{
            "type": "integer",
            "description": "The number of the line to start reading from in the given file.",
            "required": True

        },
        "endline":{
            "type": "integer",
            "description": "The number of the line to stop reading at.",
            "required": True

        }
    },
)
def read_range(name:str, index:str, filepath: str, startline: int, endline:int, agent: Agent) -> str:
    """Read a range of lines starting from line number startline and ending at line number endline

    Args:
        name (str): The name of the project
        index (int): The index number of the target bug
        filename (str): The path to the file to read from
        startline (int): The line number at which the reading starts
        endline (int): The line number at which the reading ends

    Returns:
        str: The read lines between startline and endline
    """
    ai_name = agent.ai_config.ai_name

    return execute_read_range(name, index, filepath, startline, endline, agent)

@command(
    "try_fixes",
    """This function allows you to try a list of fixes, the function will execute related tests to see if any of the fixes work.
    The list that you pass this function should be of the form:
    [{"name":"project name", "index":"bug index", "filepath":"path to file to edit", "startline":"line number", "endline":"line number", "lines_list":"the list of lines of code of the your fix"}, {...}, ...]""",
    {
        "fixes_list":  {
            "type": "string",
            "description": "The list of fixes to try.",
            "required": True,
        },
    },
)
def try_fixes(fixes_list, agent: Agent):
    fixes_feedback = ""
    for i, fix in enumerate(fixes_list):
        fix["agent"] = agent
        fixes_feedback += "Fix {}: ".format(i) + write_range(**fix) + "\n"

    return fixes_feedback

@command(
    "write_range",
    "Write a list of lines into a file to replace all lines between startline and endline. The test cases are run automatically after running the changes. The changes are reverted automatically if the the test cases fail.",
    {
        "name": {
            "type": "string",
            "description": "The name of the project.",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you want to get info about.",
            "required": True

        },
        "filepath": {
            "type": "string",
            "description": "The path to the file to write to",
            "required": True,
        },
        "startline":{
            "type": "integer",
            "description": "The number of the line at which the replacement starts",
            "required": True

        },
        "endline":{
            "type": "integer",
            "description": "The number of the line at which the replacement stops",
            "required": True

        },
        "lines_list":{
            "type": "list[string]",
            "description": "The list of the new lines to be written to the file",
            "required": True

        }
    },
)
def write_range(name:str, index:int, filepath: str, startline: int, endline:int, lines_list, agent: Agent) -> str:
    """Write a list of lines into a file to replace all lines between startline and endline

    Args:
        name (str): The name of the project
        index (int): The index number of the target bug
        filename (str): The path to the file to write to
        startline (int): The number of the line at which the replacement starts
        endline (int): The number of the line at which the replacement stops
        lines_list list[string]: The list of the new lines to be written to the file

    Returns:
        str: Success message or error message if it was not successful
    """
    ai_name = agent.ai_config.ai_name

    return execute_write_range(name, index, filepath, startline, endline, lines_list, agent)


def execute_read_range(name, index, filepath, startline, endline, agent):
    workspace = agent.config.workspace_path
    project_dir = os.path.join(workspace, name.lower()+"_"+str(index)+"_buggy")
    source_dir = ""
    all_dirs = os.listdir(os.path.join(workspace, project_dir))
    if "src" in all_dirs:
        source_dir = "src"
    else:
        source_dir = "source"

    if source_dir not in filepath:
        filepath = os.path.join(source_dir, filepath)
    if not os.path.exists(os.path.join(project_dir,filepath)):
        return "The filepath {} does not exist".format(os.path.join(project_dir,filepath))
    with open(os.path.join(project_dir,filepath)) as fp:
        lines = fp.readlines()

    lines_str = ""
    for i in range(startline-1, endline, 1):
        lines_str+="Line {}:".format(i+1) + lines[i]
    return lines_str


def execute_write_range(name, index, filepath, startline, endline, lines_list, agent):
    project_dir = "/workspace/Auto-GPT/auto_gpt_workspace/"+name.lower()+"_"+str(index)+"_buggy"
    if not os.path.exists(os.path.join(project_dir,filepath)):
        return "The filepath {} does not exist".format(os.path.join(project_dir,filepath))
    
    with open(os.path.join(project_dir,filepath)) as fp:
        lines = fp.readlines()

    lines_list = [l + "\n" if not l.endswith("\n") else l for l in lines_list ]
    new_lines = lines[:startline-1] + lines_list + lines[endline:]
    with open(os.path.join(project_dir,filepath), "w") as fp:
        fp.writelines(new_lines)

    run_ret = run_defects4j_tests(name, index, agent)
    return "Lines written successfully, the result of running test cases on the modified code is the following:\n" + run_ret

def get_edited_files(name, index):
    target_file = "/workspace/Auto-GPT/defects4j/framework/projects/{name}/patches/{index}.src.patch".format(name=name, index=index)
    with open(target_file) as ptf:
        diff_content = ptf.readlines()

    files_list = []
    for line in diff_content:
        if line.startswith("diff --git"):
            files_list.append(extract_file_name(line))
    return files_list

def extract_file_name(diff_line):
    diff_line = diff_line.split(" ")
    return "/".join(diff_line[2].split("/")[1:])


def extract_lines_range(name, index):
    import whatthepatch
    target_file = "/workspace/Auto-GPT/defects4j/framework/projects/{name}/patches/{index}.src.patch".format(name=name, index=index)
    with open(target_file) as ptf:
        text = ptf.readlines()
    diff = [x for x in whatthepatch.parse_patch(text)]
    min_max = []
    for diff0 in diff:
        max = 0
        min = 99999999999999
        for d in diff0.changes:
            if d.new is not None:
                if d.new < min:
                    min = d.new
                if d.new > max:
                    max = d.new
        min_max.append((min, max-5))
    return min_max


def extract_test_function(name, index, filepath, test_path, test_name, agent):
    pass


@command(
    "get_classes_and_methods",
    "This function allows you to get all classes and methods names within a file.\
    It returns a dictinary where keys are classes names and values are list of methods names\
    The file path should start from source or src directory depending on the project, you whould know which one is it after you execute get_info command",
    {
        "name": {
            "type": "string",
            "description": "The name of the project under scope",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you are trying to fix.",
            "required": True

        },
        "file_path":{
            "type": "string",
            "description": "the path to the file that is for which you want to extract the classes and functions",
            "required": True
        }
    },
)
def get_classes_and_methods(name: str, index: str, file_path: str, agent: Agent):
    """This function allows you to get all classes and methods names within a file. 
    It returns a dictinary where keys are classes names and values are list of methods names"""
    
    workspace = agent.config.workspace_path
    project_dir="{}_{}_buggy".format(name.lower(), index)
    source_dir = ""
    if os.path.exists(os.path.join(workspace, project_dir, "source")):
        source_dir = "source"
    elif os.path.exists(os.path.join(os.path.join(workspace, project_dir, "src"))):
        source_dir = "src"
    else:
        #return "Could not find source or src directory"
        pass
    with open(os.path.join(workspace, project_dir, file_path)) as tfp:
        content = tfp.read()

    tree = javalang.parse.parse(content)

    classes = {}
    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            classes[node.name] = []
            for method in node.methods:
                classes[node.name].append(method.name)
    return str(classes)

def list_files(start_path='.'):
    file_list = []
    for root, dirs, files in os.walk(start_path):
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                file_list.append(file_path)
    return file_list

@command(
    "search_code_base",
    "This function will seach in all java files for a provided list of keywords, it will return a dictionary where for each file\
    it will give the classes and within the classes the methods names and within the methods names a list of matched keywords against the method name\
    the returned results looks structurly like this { file_name: { class_name: { method_name: [...list of matched keywords...] } } } \
    this function is useful to search for already implemented methods that could be reused or to look for similar code to get an idea on how\
    to implement a certain functionality. This function does not return the code itself but just the matched methods names that contain at least one of the keywords.",
    {
        "name": {
            "type": "string",
            "description": "The name of the project under scope",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you are trying to fix.",
            "required": True

        },
        "key_words":{
            "type": "list",
            "description": "The list of keywords for which you want to find a match in the code base",
            "required": True
        }
    },
)

def search_code_base(name:str, index:str, key_words: list, agent: Agent):
    workspace = agent.config.workspace_path
    project_dir = "{}_{}_buggy".format(name.lower(), index)

    source_dir = ""
    all_dirs = os.listdir(os.path.join(workspace, project_dir))
    if "src" in all_dirs:
        source_dir = "src"
    else:
        source_dir = "source"

    java_files = list_files(os.path.join(workspace, project_dir))
    lower_kwords = [kw.lower() for kw in key_words]

    matched_files = {}
    for file in java_files:
        #logger.debug("searching file: " + file)
        with open(file) as jf:
            content = jf.read()
        tree = javalang.parse.parse(content)
        for path, node in tree:
            if isinstance(node, javalang.tree.ClassDeclaration):
                class_name = node.name
                #logger.debug("searching class: " + class_name)
                # Extract information about methods within the class
                for method_declaration in node.methods:
                    method_name = method_declaration.name
                    #logger.debug("searching method: " + method_name)
                    # Extract the code of the method
                    #method_code = content[method_declaration.position[0]: method_declaration.position[1]]
                    #method_code = method_declaration.body
                    #logger.debug(str(method_declaration.position))
                    #lower_code = method_code.lower()
                    matched_keyworkds = []
                    for kw in lower_kwords:
                        if kw in method_name.lower():
                            matched_keyworkds.append(kw)
                    if matched_keyworkds:
                        if file in matched_files:
                            if class_name in matched_files[file]:
                                matched_files[file][class_name][method_name] = matched_keyworkds
                            else:
                                matched_files[file][class_name]={method_name:matched_keyworkds}
                        else:
                            matched_files[file] = {class_name:{method_name:matched_keyworkds}}
    logger.debug(str(matched_files))
    matched_names = [f for f in java_files if f.endswith(".java") and any(k in f.lower() for k in lower_kwords)]
    return "The following matches were found:\n"+str(matched_files) + "\nThe search also matched the following files names: \n" + "\n".join(matched_names)



def extract_root_cause(info):
    separator = "--------------------------------------------------------------------------------"
    start_cause = info.find("Root cause")
    end_cause = info[start_cause:].find(separator)
    root_cause = info[start_cause:start_cause+end_cause]
    return root_cause


def extract_failing_test(output_message):
    # Define a regular expression pattern to match failing test information
    pattern = re.compile(r'Failing tests: (\d+)\n\s+- (.+::\w+)')
    
    # Search for the pattern in the output message
    match = pattern.search(output_message)
    
    if match:
        # Extract the number of failing tests and the test case information
        num_failures = int(match.group(1))
        test_case_info = match.group(2)
        
        # Split the test case information into class and function
        class_name, function_name = test_case_info.split('::')
        
        return {
            'num_failures': num_failures,
            'class_name': class_name,
            'function_name': function_name
        }
    else:
        return None


@command(
    "extract_test_code",
    "This function allows you to extract the code of the failing test cases which will help you understand the test case that led to failure\
    for example by looking at the assertions and the given input and expected output",
    {
        "name": {
            "type": "string",
            "description": "The name of the project under scope",
            "required": True,
        },
        "index":{
            "type": "integer",
            "description": "The index (number) of the bug that you are trying to fix.",
            "required": True

        },
        "test_file_path":{
            "type": "string",
            "description": "The path to the test file",
            "required": True

        }
    }
)
def extract_test_code(name:str, index:str, test_file_path: str, agent:Agent):

    workspace = agent.config.workspace_path
    project_dir = "{}_{}_buggy".format(name.lower(), index)
    
    with open(os.path.join(workspace, project_dir+"_test.txt")) as testf:
        test_message = testf.read()
    logger.debug(test_message)
    result = extract_failing_test(test_message)
    if not result:
        return "No test function found, probably the failing test message was not parsed correctly"
    
    if not test_file_path:
        return "You should provide the test file path"
        class_name = result["class_name"]
        path = "/".join(class_name.split("."))+".java"
        logger.debug(path)
        if os.path.exists(os.path.join(workspace, project_dir, "test", path)):
            test_file_path = os.path.join(workspace, project_dir, "test", path)
        elif os.path.exists(os.path.join(workspace, project_dir, "tests", path)):
            test_file_path = os.path.join(workspace, project_dir, "tests", path)
        else:
            results = search_code_base(name, index, [class_name], agent)
            results= json.loads(results.replace("The following matches were found:\n", ""))
            if results:
                test_file_path = list(results.keys())[0]
            else:
                return "Could not find the test file, something went wrong."
    
    else:
        test_file_path = os.path.join(agent.config.workspace_path, project_dir, test_file_path)

    with open(test_file_path, 'r') as file:
        file_content = file.read()
    
    function_name = result["function_name"]
    ind = file_content.find("public void {}".format(function_name))
    if ind == -1:
        return None
    file_content = file_content[ind:]
    ind2 = file_content[len("public void "):].find("public void ")
    if ind2 == -1:
        return file_content
    else:
        return file_content[:ind2+len("public void ")]


def extract_fail_report(name: str, index: str, agent: Agent):
    project_dir = "{}_{}_buggy".format(name.lower(), index)
    workspace = agent.config.workspace_path

    with open(os.path.join(workspace, project_dir, "failing_tests")) as wp_file:
        fail_content = wp_file.read().splitlines()

    failing_test_cases = []
    current_case = []
    case_base = ""
    for line in fail_content:
        if line.startswith("---"):
            if current_case:
                failing_test_cases.append(current_case)
                current_case = []
                case_base = ""
            current_case.append(line)
            case_base = line[4:line.find("::") if "::" in line else 1/0]
            ".".join(case_base.split(".")[:-1])
        elif line.startswith("\tat "):
            if case_base in line:
                current_case.append(line)
        else:
            current_case.append(line)

    if current_case:
        failing_test_cases.append(current_case)

    logger.debug(str(failing_test_cases))
    
    return "There are {} failing test cases, here is the full log of failing cases:\n".format(len(failing_test_cases))+\
        "\n\n".join(["\n".join(ftc) for ftc in failing_test_cases])

def prepare_init_file(root_path, root_uri, workspace_folder, workspace, project_dir):
    with open("lsp_init_template.json") as lit:
        lsp_template = json.load(lit)

    lsp_template["params"]["rootPath"] = root_path
    lsp_template["params"]["rootUri"] = root_uri
    lsp_template["params"]["initializationOptions"]["workspaceFolders"] = [workspace_folder]
    lsp_template["params"]["workspaceFolders"][0]["uri"] = workspace_folder
    lsp_template["params"]["workspaceFolders"][0]["name"] = project_dir

    with open(os.path.join(workspace, project_dir, "lspeclipse", "lsp_init_file.json"), "w") as json_handler:
        json.dump(lsp_template, json_handler)

def execute_command(command, init_req, req):
    # Open the subprocess with stdout redirected to a file
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stdin=subprocess.PIPE, text=True, shell=True)
    content_length = len(init_req)
    request = "Content-Length: {}\r\n\r\n{}".format(content_length, init_req)
    print(request)
    # Send the input to the subprocess
    process.stdin.write(request)
    #

    time.sleep(3)
    content_length = len(req)
    request = "Content-Length: {}\r\n\r\n{}".format(content_length, req)
    print(request)
    process.stdin.flush()
    process.stdin.write(request)
    #process.stdin.flush()
    time.sleep(2)
    process.kill()

def prepare_command(workspace, project_dir):
    cmd = ['cd {} &&'.format(os.path.join(workspace, project_dir, "lspeclipse")),
        '/usr/lib/jvm/java-17-openjdk-amd64/bin/java',
        '-Declipse.application=org.eclipse.jdt.ls.core.id1',
        '-Dosgi.bundles.defaultStartLevel=4',
        '-Declipse.product=org.eclipse.jdt.ls.core.product',
        '-Dlog.level=ALL',
        '-Xmx1G',
        '--add-modules=ALL-SYSTEM',
        '--add-opens java.base/java.util=ALL-UNNAMED',
        '--add-opens java.base/java.lang=ALL-UNNAMED',
        '-jar',
        './plugins/org.eclipse.equinox.launcher_1.6.600.v20231012-1237.jar',
        '-configuration',
        './config_linux',
        '-data',
        './workspace',
        '> lsp_output.txt'
    ]
    return " ".join(cmd)

def prepare_lsp_env(name, index, workspace):
    source_path = "lspeclipse"
    destination_path = os.path.join(workspace, "_".join([name.lower(), str(index), "buggy"]))

    # Using subprocess to execute the cp command
    command = ["cp", "-r", source_path, destination_path]

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")



def lsp_hover(name:str, index:str, file_path:str, line_number:int, column:int, agent: Agent):
    base_dir = "home/isleem/research_projects_repos/AutoGPT"
    workspace = agent.config.workspace
    project_dir = "_".join([name.lower(), str(index), "buggy"])
    id = random.randint(100, 9999999999)
    hover_request = {
        "jsonrpc": "2.0",
        "id": id,
        "method": "textDocument/hover","params": {
	        "textDocument": {
		        "uri": "file:///{base_dir}/{workspace}/{project_dir}/{file_path}".format(
                    base_dir=base_dir, workspace=workspace, project_dir=project_dir, file_path=file_path)
	        },
	        "position": {
		    "line": line_number,
		    "character": column
	        }
        }}

    string_request = json.dumps(hover_request)
    command = prepare_command(workspace, project_dir)
    logger.debug("COMMAND: " + command)
    if not os.path.exists(os.path.join(workspace, project_dir, "lspeclipse")):
        prepare_lsp_env(name, index, workspace)

    if not os.path.exists(os.path.join(workspace, project_dir, "lspeclipse", "lsp_init_file.json")):
        root_path = str(os.path.join(base_dir, workspace, project_dir))
        root_uri = "file://" + root_path
        workspace_folder = root_uri

        prepare_init_file(root_path, root_uri, workspace_folder, workspace, project_dir)

    with open(os.path.join(workspace, project_dir, "lspeclipse", "lsp_init_file.json")) as inif:
        init_content = inif.read()

    execute_command(command, init_content, string_request)

    if not os.path.exists(os.path.join(workspace, project_dir, "lsp_output.txt")):
        return "ERROR NO OUTPUT: LSP command was not executed correctly, shutting down LSP server, do not use again."
    else:
        with open(os.path.join(workspace, project_dir, "lsp_output.txt")) as lspf:
            tmpf_content = lspf.read()

        if len(tmpf_content) <2:
            return "ERROR EMPTY OUTPUT: LSP command was not executed correctly, shutting down LSP server, do not use again."
        else:
            return tmpf_content


## TO BE PUT TEMPORARILY HERE

from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import HumanMessage, SystemMessage, AIMessage

"""@command(
    "ask_chatgpt",
    "This function allows you to ask chatgpt any question. Chatgpt is LLM that has amazing question answering abilities.\
    strucutre your question as following ## Summary of the problem: PUT SUMMARY OF THE PROBLEM HERE ## Possible buggy code: HERE YOU PUT THE BUGGY CODE SNIPET, ## Failing test cases and test result: HERE PUT THE RESULT OF EXECUTING TEST CASES AND THE CODE OF THE FAILING CASE",
    {
        "question": {
            "type": "string",
            "description": "The name of the project under scope",
            "required": True,
        },
    }
)
"""
def ask_chatgpt(question: str, agent: Agent):
    chat = ChatOpenAI(openai_api_key="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")

    if not agent.ask_chatgpt:
        messages = [
        SystemMessage(content="You're a helpful assistant who answer questions mostly related to programming, software, debugging, code repair, code generation, code impelementation in all possible languages, you also a big base of knowledge regarding programming and software.\
If the details in the given quetion are not enough, you should ask the user to add more details and ask again."),
        HumanMessage(content=question),
    ]
        agent.ask_chatgpt = messages
    else:
        messages = agent.ask_chatgpt
        messages.append(HumanMessage(content=question))

    response = chat.invoke(messages)
    agent.ask_chatgpt.append(response)

    return response.content

def remove_comments(java_code):
    # Remove both single-line and multi-line comments
    pattern = re.compile(r'(/\*.*?\*/|//.*?$)', re.MULTILINE | re.DOTALL)
    return re.sub(pattern, '', java_code)

def extract_function_calls(java_code):

    java_code = remove_comments(java_code)
    # Define a pattern to match function or method calls, excluding if and while conditions
    pattern = re.compile(r'\b(?:(?!if|while)\w+\s*\(.*?\))')

    # Find all matches in the Java code
    matches = pattern.findall(java_code)

    logger.info(list(set(matches)))
    # Print the matches
    return [match for match in matches]

@command(
    "extract_similar_functions_calls",
    "For a provided buggy code snippet in 'code_snippet' within the file 'file_path', this function extracts similar function calls. This aids in understanding how functions are utilized in comparable code snippets, facilitating the determination of appropriate parameters to pass to a function.",
    {
        "name": {
            "type": "string",
            "description": "The name of the project",
            "required": True
        },
        "index": {
            "type": "string",
            "description": "The bug index",
            "required":True
        },
        "file_path": {
            "type": "string",
            "description": "The path of the file containing the buggy snippet",
            "required": True,
        },
        "code_snippet":{
            "type": "string",
            "description": "the buggy code snippet",
            "required": True
        }
    }
)

def extract_similar_functions_calls(name:str, index: str, file_path: str, code_snippet: str, agent:Agent):
    workspace = agent.config.workspace_path
    project_dir = "{}_{}_buggy".format(name.lower(), index)
    
    with open(os.path.join(workspace, project_dir, file_path)) as fpt:
        java_code = fpt.read()

    all_calls = extract_function_calls(java_code)
    calls = extract_function_calls(code_snippet)
    #logger.debug("ALL CALLS: " + str(all_calls))
    #logger.debug("CALLS: " + str(calls))
    if not calls:
        return "No function calls were found. There is no need to call this command again."
    similar_calls = {}
    for c in calls:
        ec = c[:c.find('(')]
        similar_calls[c] = []
        for ac in all_calls:
            if (ec in ac) and c!=ac:
                similar_calls[c].append(ac)

    logger.debug("SIMILAR: "+str(similar_calls))
    for c in similar_calls:
        if similar_calls[c]:
            break
    else:
        return "No similar functions calls were found. There is no need to use this command again."
    
    return "The following similar calls were found. The keys of the dictionary are calls from the code snippet, and the values are similar calls from the file.\n"+str(similar_calls)


def get_localization(name, index):
    localization_dir = "buggy-lines"
    methods_dir = "buggy-methods"
    file_name = "{}-{}.buggy.lines".format(name, index)
    if not os.path.exists(os.path.join(localization_dir, file_name)):
        lines_info = ""
    else:
        with open(os.path.join(localization_dir, file_name)) as buggy_lines_file:
            bug_lines = buggy_lines_file.read()
        lines_info = "The bug is located at exactly these lines numbers or around them: (the format is file-name#line-number# line-code):\n" + bug_lines

    file_name = "{}-{}.buggy.methods".format(name, index)
    print("I am here")
    if not os.path.exists(os.path.join(methods_dir, file_name)):
        methods_info = ""
    else:
        print("I am here 2")
        methods_info = "The following is the list of buggy methods:\n"
        with open(os.path.join(methods_dir, file_name)) as methods:
            methods_list = methods.read().splitlines()

        print(methods_info)
        for m in methods_list:
            if m.endswith("1"):
                methods_info += m +'\n'
    return lines_info + "\n" + methods_info