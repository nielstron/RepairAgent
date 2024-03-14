#!/bin/bash
export PATH=$PATH:/app/AutoGPT/defects4j/framework/bin
python3 experimental_setups/increment_experiment.py
python3 construct_commands_descriptions.py
input="$1"
dos2unix "$input"  # Convert file to Unix line endings (if needed)
while IFS= read -r line || [ -n "$line" ]
do
    tuple=($line)
    echo ${tuple[0]}, ${tuple[1]}
    python3 prepare_ai_settings.py "${tuple[0]}" "${tuple[1]}"
    python3 checkout_py.py "${tuple[0]}" "${tuple[1]}"
    ./run.sh --ai-settings ai_settings.yaml --gpt3only -c -l 40 -m json_file --experiment-file "$2"
done < "$input"