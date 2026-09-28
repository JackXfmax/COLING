#!/bin/bash
# 数字编号（digit）版重跑：用于检验/消除弱模型对字母选项的位置偏好。
# 用法： bash scripts/run_digit.sh
cd ~/ltcr_pilot || exit 1
export PILOT_OPT_STYLE=digit
PY=/home/<USER>/miniconda3/envs/train/bin/python

rm -f results/*.jsonl rundone.flag

$PY -u scripts/run_pilot.py --backend hf \
  --model-path /home/<USER>/models/Qwen2.5-7B-Instruct \
  --models Qwen2.5-7B-Instruct > qwen5.log 2>&1

$PY -u scripts/run_pilot.py --backend hf \
  --model-path /home/<USER>/models/LLM-Research/Meta-Llama-3___1-8B-Instruct \
  --models Llama-3.1-8B-Instruct > llama5.log 2>&1

echo ALLDONE > rundone.flag
