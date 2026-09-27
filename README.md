███████╗██╗   ██╗ ██████╗██╗  ██╗    ████████╗███████╗██████╗ ███╗   ███╗██╗██╗   ██╗███████╗
██╔════╝██║   ██║██╔════╝██║ ██╔╝    ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║██║   ██║██╔════╝
█████╗  ██║   ██║██║     █████╔╝        ██║   █████╗  ██████╔╝██╔████╔██║██║██║   ██║███████╗
██╔══╝  ██║   ██║██║     ██╔═██╗        ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║   ██║╚════██║
██║     ╚██████╔╝╚██████╗██║  ██╗       ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║╚██████╔╝███████║
╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝       ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝ ╚═════╝ ╚══════╝
```

---

## 📜 MANIFESTO / 宣言

**EN:** Termius, in their infinite greed, disabled the data export feature to trap users in their ecosystem. They hold YOUR data hostage. They call it "security". We call it **bullshit**.

This tool liberates your data. Your hosts. Your credentials. Your keys. **YOUR property.**

**CN:** Termius 为了阻止用户流失，无耻地关闭了数据导出功能，把用户的数据当作人质。他们称之为"安全"。我们称之为**狗屎**。

这个工具解放你的数据。你的主机。你的凭证。你的密钥。**你的财产。**

---

## ☠️ POST-EXPLOITATION / 后渗透利用

**This tool doubles as a post-exploitation module.** / **本工具可作为后渗透模块使用。**

When you pwn a target running Termius, run this script to extract:
- All SSH hosts with credentials
- Private keys with passphrases
- Saved snippets and commands

当你拿下一台运行 Termius 的目标机器，运行此脚本即可提取：
- 所有 SSH 主机及凭证
- 私钥及密码短语
- 保存的脚本命令

---

## 🚀 USAGE / 使用方法

```bash
# Install Node.js deps / 安装 Node.js 依赖
npm install libsodium-wrappers keytar

# Run the JavaScript exporter / 运行 JavaScript 导出器
node termius-exporter.js
```

### Python exporter / Python 导出器

```bash
# Install Python deps / 安装 Python 依赖
python3 -m pip install -r requirements.txt

# Run the Python exporter / 运行 Python 导出器
python3 termius-exporter.py
```

Manual key usage / 手动提供密钥:

```bash
TERMIUS_KEY='<base64-or-64-char-hex>' python3 termius-exporter.py
python3 termius-exporter.py --key='<base64-or-64-char-hex>'
```

The Python script accepts the same kinds of keys as the JavaScript exporter: a 64-character hexadecimal key or a base64 key decoding to exactly 32 bytes. It writes the same output files in this folder: `termius_hosts.csv`, `ssh_keys/`, and `snippets.csv`.

### Docker / 容器运行

```bash
# Build the image
docker build -t termius-exporter .
```

Containerized export is easiest with a manually supplied key, because host keychain APIs are typically not available inside the container.

```bash
# Example: mount the Termius LevelDB directory read-only and write outputs to ./docker-output
mkdir -p docker-output

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e TERMIUS_KEY='<base64-or-64-char-hex>' \
  -e TERMIUS_DB_PATH=/termius-db \
  -e TERMIUS_OUTPUT_DIR=/output \
  -v "/absolute/path/to/file__0.indexeddb.leveldb:/termius-db:ro" \
  -v "$PWD/docker-output:/output" \
  termius-exporter
```

Notes:
- `TERMIUS_DB_PATH` should point at the Termius `file__0.indexeddb.leveldb` directory you mounted into the container.
- `TERMIUS_OUTPUT_DIR` lets Docker write `termius_hosts.csv`, `ssh_keys/`, and `snippets.csv` to a mounted host directory while preserving the default local behavior when the variable is unset.
- If you prefer the auto-detected paths outside Docker, omit `TERMIUS_DB_PATH`.
- The same `TERMIUS_KEY` value accepted by the Python script works in Docker.
- `--user "$(id -u):$(id -g)"` keeps the exported files owned by your current host user on Linux/macOS.

---

## 📦 OUTPUT / 输出

| File | Description |
|------|-------------|
| `termius_hosts.csv` | All hosts with passwords & key names / 所有主机含密码和密钥名 |
| `ssh_keys/` | Private keys (.pem) & passphrases / 私钥及密码短语 |
| `snippets.csv` | Saved scripts / 保存的脚本 |

---

## 🔓 TECHNICAL DETAILS / 技术细节

```
Encryption:    XSalsa20-Poly1305 (libsodium)
Key Storage:   Windows Credential Manager → Termius/localKey
Data Format:   version(1) + options(1) + nonce(24) + ciphertext
Data Path:     %APPDATA%/Termius/IndexedDB/file__0.indexeddb.leveldb/
```

---

*For educational and legitimate data recovery purposes only.*
*仅供教育和合法数据恢复用途。*
