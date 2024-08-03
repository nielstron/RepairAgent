#!/bin/bash
export PATH=$PATH:/app/AutoGPT/defects4j/framework/bin

for LANG in en_AU.UTF-8 en_GB.UTF-8 C.UTF-8 C; do
  if locale -a 2>/dev/null | grep -q "$LANG"; then
    export LANG
    break
  fi
done
export LC_COLLATE=C

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
    ./run.sh --ai-settings ai_settings.yaml -c -l 40 -m json_file --experiment-file "$2"
done < "$input"
