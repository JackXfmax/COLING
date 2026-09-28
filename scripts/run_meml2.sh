#!/bin/bash
# mem-L2 实验：同时跑 mem-L0(自由回忆) / mem-L2(N选一) / comp(N选一)
# 目的：检验 mem-comp 的 80 点落差里，有多少是"自由回忆 vs 再认"的任务形式差异造成的。
# 单次抽样（PERMS=1），先看量级；调用量 80x3 = 240 次/模型，约 2-3 分钟/模型。
cd ~/ltcr_pilot || exit 1
PY=/home/<USER>/miniconda3/envs/train/bin/python

rm -f results/*.jsonl rundone.flag

$PY -u scripts/run_pilot.py --backend hf \
  --model-path /home/<USER>/models/Qwen2.5-7B-Instruct \
  --models Qwen2.5-7B-Instruct > qwen_meml2.log 2>&1

$PY -u scripts/run_pilot.py --backend hf \
  --model-path /home/<USER>/models/LLM-Research/Meta-Llama-3___1-8B-Instruct \
  --models Llama-3.1-8B-Instruct > llama_meml2.log 2>&1

echo ALLDONE > rundone.flag
