# 数字好友桌 e2e 质量站

质量站代码都在**本目录**。拷到另一台电脑时，拷整个 `e2e-quality-station` 文件夹即可，不要再从仓库 `scripts/` 里零散取文件。

需要 **Python 3.9+**。同事电脑要能访问 fusion（默认 `http://192.168.110.81:8080`）。

```bash
python3 -m pip install -r requirements.txt
./start.sh
```

或：

```bash
python3 e2e_quality_server.py --host 0.0.0.0 --port 8767
```

终端会打印本机和内网地址。同事用 **内网 IP** 打开，不要用 `127.0.0.1`。

| 地址 | 谁用 |
|---|---|
| `http://127.0.0.1:8767/` | 这台机器自己 |
| `http://这台机器的局域网IP:8767/` | 同事 |

本仓库里跑时，页面数据仍写到仓库的 `output/e2e-quality/`（已有批次不用搬家）。单独拷走后，数据写在本目录的 `output/e2e-quality/`。
