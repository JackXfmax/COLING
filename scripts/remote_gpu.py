#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""远程 GPU 助手（paramiko 密码登录）。
环境变量：
  REMOTE_HOST  默认 <GPU_HOST_IP>
  REMOTE_USER  默认 xf
  REMOTE_PW    密码（必填）
用法：
  python remote_gpu.py probe          # 探测 GPU/环境
  python remote_gpu.py run "cmd"      # 远程执行单条命令
  python remote_gpu.py put loc rem    # 上传文件
  python remote_gpu.py get rem loc    # 下载文件
"""
import os, sys, paramiko

HOST = os.environ.get("REMOTE_HOST", "")
USER = os.environ.get("REMOTE_USER", "")
PW   = os.environ.get("REMOTE_PW", "")

def connect():
    assert HOST, "请设置环境变量 REMOTE_HOST（远程 GPU 主机地址，勿硬编码）"
    assert USER, "请设置环境变量 REMOTE_USER（远程用户名，勿硬编码）"
    assert PW, "请设置环境变量 REMOTE_PW"
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=30,
              look_for_keys=False, allow_agent=False)
    return c

def run(cmd, c=None):
    own = c is None
    c = c or connect()
    stdin, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    if own:
        c.close()
    return rc, out, err

def sftp_put(local, remote, c=None):
    own = c is None
    c = c or connect()
    sftp = c.open_sftp()
    sftp.put(local, remote)
    sftp.close()
    if own:
        c.close()

def sftp_get(remote, local, c=None):
    own = c is None
    c = c or connect()
    sftp = c.open_sftp()
    sftp.get(remote, local)
    sftp.close()
    if own:
        c.close()

PROBE = r"""
echo '=== host ==='; hostname; uname -a
echo '=== gpu ==='; nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'NO nvidia-smi'
echo '=== driver ==='; nvidia-smi -L 2>/dev/null | head -5
echo '=== python ==='; python3 --version 2>/dev/null; which python3
echo '=== torch/transformers ==='; python3 -c "import torch,transformers; print('torch',torch.__version__,'cuda',torch.cuda.is_available()); print('transformers',transformers.__version__)" 2>&1 | head -5
echo '=== disk ==='; df -h / /home /data 2>/dev/null | head -10
echo '=== models dirs ==='; ls -d /models /data/models ~/models 2>/dev/null; find / -maxdepth 3 -iname "*Llama*3.1*8B*" -type d 2>/dev/null | head; find / -maxdepth 4 -iname "*Qwen2.5*7B*" -type d 2>/dev/null | head
echo '=== net check ==='; timeout 8 curl -sI https://huggingface.co 2>/dev/null | head -1 || echo 'NO HF access'
echo '=== cwd contents ==='; pwd; ls -la | head -20
"""

if __name__ == "__main__":
    act = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if act == "probe":
        rc, out, err = run(PROBE)
        print(out)
        if err.strip():
            print("--- stderr ---\n", err)
    elif act == "run":
        cmd = sys.argv[2] if len(sys.argv) > 2 else ""
        rc, out, err = run(cmd)
        print("rc=", rc)
        print(out)
        if err.strip():
            print("--- stderr ---\n", err)
    elif act == "put":
        sftp_put(sys.argv[2], sys.argv[3])
        print("put ok", sys.argv[2], "->", sys.argv[3])
    elif act == "get":
        sftp_get(sys.argv[2], sys.argv[3])
        print("get ok", sys.argv[2], "->", sys.argv[3])
