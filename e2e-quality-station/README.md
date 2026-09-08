# 数字好友桌 e2e 质量站

上传源数据（Excel `auto_json` 列，或 jsonl / json），对照 fusion 的视觉 / 规则，看字段匹配率。

需要 **Python 3.9+**。同事电脑要能访问 fusion（默认 `http://192.168.110.81:8080`）。

```bash
python3 -m pip install -r requirements.txt
python3 scripts/e2e_quality_server.py --host 0.0.0.0 --port 8767
```

或：`./start.sh`

终端会打印本机和内网地址。同事用 **内网 IP** 打开，不要用 `127.0.0.1`。

| 地址 | 谁用 |
|---|---|
| `http://127.0.0.1:8767/` | 这台机器自己 |
| `http://这台机器的局域网IP:8767/` | 同事 |

站点文件写在本目录的 `output/e2e-quality/`。
