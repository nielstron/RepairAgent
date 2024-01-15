#!/bin/bash

python3 prepare_ai_settings.py


./run.sh --ai-settings ai_settings.yaml --gpt3only -c -l 20
