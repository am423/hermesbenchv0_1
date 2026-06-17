#!/bin/bash
# hermesbench session env (auto-generated)
export HERMESBENCH_SESSION=hb-728d3e12
export HERMESBENCH_HOME=/tmp/hb-home-728d3e12-06a1s72r
export HERMESBENCH_WORKTREE=/home/r0b0tdgx/hermesbenchv0_1/traces/vibethinker-3b-nvfp4_20260617-172123_728d3e12/t06_process_mgmt/t04_pipeline/worktree
export DISABLED_TOOLSETS='kanban,memory_providers,observability,image_gen,video_gen,computer_use,cronjob,messaging,ha_*,send_message,delegate_task'
export PS1="$ "
export TERM=xterm-256color
stty -echo
set +o history
ulimit -v 2097152  # max_memory_mb=2048
ulimit -u 128  # max_processes=128
ulimit -f 104857600  # max_file_size_mb=100
