# RepairAgent
RepairAgent is an autonomous LLM-based agent for automated program repair.
For more details on how it works and how we built it, we invite you to check our paper:
https://arxiv.org/abs/2403.17134

## I. Requirements
* Docker >= 20.04: see documentation on how to install docker if you do not have it: https://docs.docker.com/get-docker
* OpenAI Token and credits:
   * Go to OpenAI website, create an account, buy credits that allows you to use the API
   * On the same website, create an API token
* At least 40GB of Disk space on your machine
* Internet access while running RepairAgent (To access OpenAI's API)

## II. How to use?
The easiest way to use repair is by retrieving the ready-to_use Docker image from DockerHub.

The advantages of using the docker image is that RepairAgent is already installed inside and the only action needed is to provide OPENAI'S api key.


Please follow the steps below:


### STEP 1: Pull the Docker Image from DockerHub

Execute the following commands in your terminal to retrieve and start our docker image
```shell
# Pull image
docker pull islemdockerdev/repair-agent:v1
# Run the image inside a container
docker run -itd --name apr-agent islemdockerdev/repair-agent:v1
# Start the container
docker start -i apr-agent
```
### STEP 2: Attach the Container to VScode
* After starting the container, open VSCode and navigate to the containers icon on the left panel (Ensure that you have the Remote Explorer extension installed on your VScode).

* Under the Dev Containers tab, locate the name of the container you just started (e.g., github-study).

* Finally, attach the container apr-agent to a new window by clicking the '+' sign located on the right of the container's name. Navigate to workdir folder in vscode window (**the workdir is /app/AutoGPT**).

* **Tutorial reference:** For detailed steps on how to attach a docker container in VScode, please refer to this short video tutorial (1min 38 sec): https://www.youtube.com/watch?v=8gUtN5j4QnY&t

### STEP 3: Set OPENAI Token
RepairAgent is based on OPENAI's LLMs such as GPT3.5. To use RepairAgent, you need to obtain an API-key from OpenAI. Once done, within the docker container, execute the following command:
```Python
python3.10 set_api_key.py
```
The script will prompt you to paste your token.

### STEP 4: Start RepairAgent
RepairAgent is set by default to run on Defects4J bugs (which this can be changed). 

* To specify which bugs you want RepairAgent to run on, you need to create a text file called, for example, bugs_list. Within this there already exist such file which we will use for the rest of the example commands. The file is located under "experimental_setups/bugs_list" folder.

Once done, you simply need to call the following command:
```shell
./run_on_defects4j.sh experimental_setups/bugs_list hyperparameters.json
```

You can open the file "hyperparameters.json" to check the parameters it contains (which we will explain later on).

#### 4.1. What would happen when you start RepairAgent?

* RepairAgent will checkout the project with given bug id.
* After that it will start the Autonomous process of repair.
* During that, on your terminal you will see the logs of the steps performed by RepairAgent

#### 4.2. Retrieve repair logs and history
RepairAgent saves the output to multiple files.

* You find the most important logs of repair agent under the folder "experimental_setups/experiment_X". where "experiment_X" is a subfolder created automatically and it increments with each call to the command "run_on_defects_4j"

* Under "experimental_setups/experiment_X", you typicaly find the following subfolders (created automatically):
   * "logs": a folder containing full chat history (full prompts) of RepairAgent and outputs of executed commands. One file per bug.
   * "plausible_patches": the list of plausible patches, if any generated. One file per bug.
   * "mutations_history": the fixes suggested by mutating previously suggested fixes. One file per bug.
   * "responses": the list of agent's responses at each cycle. One file per bug.

#### 4.3. Analyze logs
Under "experimental_setups" folder, you find some usefull scripts to postprocess the agent's logs.

* The script "collect_plausible_patches_files.py" is used to collect the set of generated plausible patches in a range of conducted experiments.
   * Example: the command will collect all plausible patches generated from experiments 1 to 9.
   ```shell
   python3.10 script.py 1 10
   ```

* The script "get_list_of_fully_executed.py" allows to get the runs that had at least reached 38/40 cycles. This script would allow you to point out executions that had unexpected termination (or called the exit function early)

## III. Customize RepairAgent

### 1. Changing the hyperparams.json file

* Budget control strategy determines how to tell the agent about the number of remaining cycles and the number of fixes suggested so far and the minimum number of fixes that should be reached.
   * FULL-TRACK: show full budget information
   * NO-TRACK: don't show budget information
   * FORCED: this strategy is experimental (Do not use as it is buggy)
   * Example:
   ```json
   ...
   "budget_control": {
         "name": "FULL-TRACK", 
         "params": {
               "#fixes": 4
         }
      }
   ...
   ```

* Repetition handling: restricted by default.
   ```json
   "repetition_handling": "RESTRICT",
   ```

* Commands limit: controls the number cycles allowed
   ```json
   "commands_limit": 40
   ```

* Request external fixes: experimental feature that allows to request fixes from another LLM. The number determines how many external fixes the RepairAgent can ask for.
   ```json
   "external_fix_strategy": 0,
   ```

### 2. Run RepairAgent on an arbitrary project
Documentation for this part will come soon. (We are working on encapsulating this part in one to make it easy to use.)


## IV. Help us improve RepairAgent
If you have the opportunity to use RepairAgent, we encourage you to report any issues, bugs, or gaps in the documentation/features. We are committed to addressing your concerns promptly.

You can raise an issue directly within this repository, or if you have any questions, feel free to [email me](mailto:fi_bouzenia@esi.dz).