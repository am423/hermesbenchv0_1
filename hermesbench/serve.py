"""hermesbench/serve.py — vLLM launch helper."""
from __future__ import annotations
import shutil, subprocess, sys, time, urllib.request
from pathlib import Path


def launch_vllm(
    model: str,
    port: int = 8999,
    quantization: str | None = None,
    config_path: str | None = None,
    served_name: str | None = None,
) -> None:
    """Launch a vLLM server with benchmark-correct flags."""
    from hermesbench.config import load_config
    cfg = load_config(config_path)
    vllm_cfg = cfg.get("vllm", {})
    model_cfg = cfg.get("model", {})
    flags = vllm_cfg.get("flags", {})

    if not served_name:
        served_name = model_cfg.get("served_name") or Path(model).name

    vllm_bin = shutil.which("vllm")
    if not vllm_bin:
        print("vllm not found. Install: pip install vllm")
        sys.exit(1)

    cmd = [vllm_bin, "serve", model,
           "--port", str(port),
           "--served-model-name", served_name,
           "--host", "0.0.0.0"]

    quant = quantization or flags.get("quantization")
    if quant:
        cmd += ["--quantization", quant]

    kv = flags.get("kv-cache-dtype") or flags.get("kv_cache_dtype")
    if kv:
        cmd += ["--kv-cache-dtype", kv]

    attn = flags.get("attention-backend") or flags.get("attention_backend")
    if attn:
        cmd += ["--attention-backend", attn]

    gpu_mem = flags.get("gpu-memory-utilization") or flags.get("gpu_memory_utilization")
    if gpu_mem:
        cmd += ["--gpu-memory-utilization", str(gpu_mem)]

    max_len = flags.get("max-model-len") or flags.get("max_model_len")
    if max_len:
        cmd += ["--max-model-len", str(max_len)]

    cmd += ["--enable-auto-tool-choice"]
    parser = flags.get("tool-call-parser") or model_cfg.get("tool_call_parser") or "hermes"
    cmd += ["--tool-call-parser", parser]
    cmd += ["--enforce-eager", "--trust-remote-code", "--enable-prefix-caching"]

    print("Launching vLLM:")
    print("  " + " ".join(cmd))
    print()

    proc = subprocess.Popen(cmd)

    print(f"Waiting for vLLM on port {port}...")
    for i in range(90):
        if proc.poll() is not None:
            print(f"vLLM exited with code {proc.returncode}")
            sys.exit(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            print(f"\nvLLM ready on port {port}")
            print(f"  Model: {served_name}")
            print(f"  Base URL: http://127.0.0.1:{port}/v1")
            print(f"\n  Run: hermesbench run --all --model {served_name} --base-url http://127.0.0.1:{port}/v1")
            break
        except Exception:
            time.sleep(2)
    else:
        print("vLLM failed to start within 180s")
        proc.terminate()
        sys.exit(1)

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down vLLM...")
        proc.terminate()
        proc.wait(timeout=10)
