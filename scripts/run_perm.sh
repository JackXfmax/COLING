#!/bin/bash
# 循环置换（cyclic permutation）版：每题把选项循环移位 6 次，消除模型对固定编号的位置偏好。
# 判据用"6 次置换中 >=3 次答对"，报告同时给出多数投票分与置换平均分。
# 调用量：80 题 x (1 mem + 6 comp) = 560 次/模型，约 6-9 分钟/模型。
cd ~/ltcr_pilot || exit 1
export PILOT_PERMS=6
PY=/home/<USER>/miniconda3/envs/train/bin/python

rm -f results/*.jsonl rundone.flag

$PY -u scripts/run_pilot.py --backend hf \
  --model-path /home/<USER>/models/Qwen2.5-7B-Instruct \
  --models Qwen2.5-7B-Instruct > qwen_perm.log 2>&1

$PY -u scripts/run_pilot.py --backend hf \
  --model-path /home/<USER>/models/LLM-Research/Meta-Llama-3___1-8B-Instruct \
  --models Llama-3.1-8B-Instruct > llama_perm.log 2>&1

echo ALLDONE > rundone.flag
