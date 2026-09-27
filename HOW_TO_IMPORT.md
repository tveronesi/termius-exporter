# How to Import (moving to a new computer)

1. **Export** on the old computer:
   ```bash
   # Node.js
   npm install libsodium-wrappers keytar
   node termius-exporter.js

   # or Python
   python3 -m pip install -r requirements.txt
   python3 termius-exporter.py
   ```

   Or run the Python exporter in Docker without installing Python locally:

   ```bash
   docker build -t termius-exporter .
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
   This produces `termius_hosts.csv`, `ssh_keys/`, and `snippets.csv`. With the Docker example above, they are written into `docker-output/` and owned by your current host user on Linux/macOS.

2. **Zip and ship** the whole project folder (including `termius_hosts.csv`) to your new computer, then unzip it there.

3. **Run the importer** on the new computer:
   ```bash
   node termius-importer.js
   ```
   This reads `termius_hosts.csv` and creates `termius_import_ready.csv`.

4. **Import into Termius** on the new computer:
   - Go to **Hosts** → click **▼** next to "New Host" → **Import**
   - Select **CSV** → drag & drop `termius_import_ready.csv`
   - Review and click **Import**

5. Copy any needed private keys from `ssh_keys/` into Termius manually if not already linked.
