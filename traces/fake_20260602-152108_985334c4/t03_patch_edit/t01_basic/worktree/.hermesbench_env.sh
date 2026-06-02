#!/bin/bash
# hermesbench session env (auto-generated)
export HERMESBENCH_SESSION=hb-985334c4
export HERMESBENCH_HOME=/tmp/hb-home-985334c4-yz5oa8w8
export HERMESBENCH_WORKTREE=/home/am/projects/hermesbenchv0_1/traces/fake_20260602-152108_985334c4/t03_patch_edit/t01_basic/worktree
export DISABLED_TOOLSETS='kanban,memory_providers,observability,image_gen,video_gen,computer_use,cronjob,messaging,ha_*,send_message,delegate_task'
export PS1="$ "
export TERM=xterm-256color
stty -echo
set +o history
ulimit -v 2097152  # max_memory_mb=2048
ulimit -u 128  # max_processes=128
ulimit -f 104857600  # max_file_size_mb=100
