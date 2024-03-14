# AutoDebug 0.4.x
This readme file gives some instructions on how to run AutoDebug 0.4.x.
AutoDebug 0.4.x customizes AutoGPT to perform the task of program repair on Defects4J dataset.


## How to use?
To apply AutoDebugv0.4.x on Defects4J you need to perform the following steps:
1. Checkout the bug that you want to fix using AutoDebug. For example, if you want to run AutoDebug on the bug with index 1 from the project chart, you need to checkout the project using the following command and give "Chart" and "1b" as answers to the prompt.
    ```Python
    # run the command and fill out the asked input
    ./checkout_bs.sh
    ```
 2. Run the following bash script
    ```shell
    ./run_on_defects4j.sh
    ```

## Customize how to run AutoDebug
Currently the run_on_defects4j.sh script executes AutoDebug in continous mode with a limit of 20 actions and uses GPT3.5 as the empowering model.

Here are other alternatives which you can adopt by replacing line 6 of the script ./run_on_defects4j with one of the following:
1. No continous mode
    ```
    ./run.sh --ai-settings ai_settings.yaml --gpt3only
    ```

2. Use GPT4 (with continous mode)
    ```
    ./run.sh --ai-settings ai_settings.yaml
    ```

