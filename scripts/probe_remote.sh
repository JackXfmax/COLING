#!/bin/bash
echo '=== conda envs ==='
/home/xufei/miniconda3/bin/conda env list 2>/dev/null
echo '=== 各 env 的 torch/transformers ==='
for penv in /home/xufei/miniconda3/envs/*/bin/python; do
  [ -x "$penv" ] || continue
  echo "--- $penv ---"
  "$penv" -c "import torch,transformers; print('torch',torch.__version__,'cuda',torch.cuda.is_available()); print('tf',transformers.__version__)" 2>&1 | head -3
done
echo '=== base python torch? ==='
/home/xufei/miniconda3/bin/python -c "import torch; print('base torch',torch.__version__, torch.cuda.is_available())" 2>&1 | head -2
echo '=== PyPI 可达 ==='
timeout 8 curl -sI https://pypi.org 2>/dev/null | head -1 || echo 'NO PyPI'
echo '=== hf-mirror / modelscope ==='
timeout 8 curl -sI https://hf-mirror.com 2>/dev/null | head -1 || echo 'NO hf-mirror'
timeout 8 curl -sI https://modelscope.cn 2>/dev/null | head -1 || echo 'NO modelscope'
echo '=== Qwen 权重 ==='
du -sh /home/xufei/models/Qwen2.5-7B-Instruct 2>/dev/null
ls /home/xufei/models/Qwen2.5-7B-Instruct 2>/dev/null | head
echo '=== 其他模型目录 ==='
ls /home/xufei/models 2>/dev/null
echo '=== 项目代码 ==='
find /home/xufei -maxdepth 2 -iname '*LongTail*' -o -iname '*mem_layer*' 2>/dev/null | head
ls /home/xufei 2>/dev/null | grep -iE 'long|rhet|mem|proj|exp' | head
