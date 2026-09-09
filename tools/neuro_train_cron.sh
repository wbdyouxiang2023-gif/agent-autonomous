#!/bin/bash
# 每天自动训练 NeuroCortex
python3 /root/.openclaw/workspace/tools/neuro_train.py >> /var/log/neuro_train.log 2>&1
