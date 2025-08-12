# Streamlit RAG App – Self‑Hosted on Oracle Linux 9

This repo contains **two ways** to deploy and run a Streamlit app (e.g., `rag_app_v2.py`) on **Oracle Linux 9** without using Streamlit Cloud:

* **Ansible playbook**: `ragapp.yml` — idempotent, taggable steps.
* **Bash menu script**: `deploy_ragapp.sh` — run steps interactively on a single host.

Both approaches set up:

* A dedicated system user (`ragapp`)
* Python virtual environment and dependencies
* A secured environment file (no secrets in Git)
* A `systemd` service to run Streamlit headlessly
* Optional Nginx reverse proxy (WebSockets ready)
* Optional TLS via Let’s Encrypt (certbot via snap)
* SELinux + firewalld adjustments

---

## 0) Requirements

* Oracle Linux 9 host (or RHEL 9–compatible)
* SSH/admin access
* Your Streamlit app in this repo (default entrypoint: `rag_app_v2.py`)
* **Do not commit secrets**. Use `/etc/default/ragapp` for environment variables.

Optional:

* A DNS record pointing to your server (for Nginx/TLS)

---

## 1) Directory Layout (suggested)

```
/opt/ragapp/            # app root (git-cloned or rsynced here)
  ├─ rag_app_v2.py      # your Streamlit entrypoint
  ├─ requirements.txt   # dependencies (if present)
  └─ .venv/             # created by scripts
/var/log/ragapp/        # runtime logs (stdout/err)
/etc/default/ragapp     # environment config (created by scripts)
```

---

## 2) Ansible Playbook (`ragapp.yml`)

### 2.1 Inventory

Create `hosts.ini` (example uses default Oracle Cloud user `opc`):

```
[ragapp]
yourserver ansible_host=YOUR_IP ansible_user=opc
```

### 2.2 Customize Variables

Open `ragapp.yml` and review the **vars** block:

* `app_dir`, `app_entrypoint`, `app_repo`, `app_branch`
* `app_host`, `app_port`, `base_url_path` (use `"rag"` to serve under `/rag`)
* `server_name` (domain), `use_nginx`, `use_tls`
* `env_vars` (e.g., `OPENAI_API_KEY`, `DB_PATH`, `TABLE_NAME`)

> **Note:** if you already copied your code to `app_dir`, set `app_repo: ""` and skip the `code` tag.

### 2.3 Run with Tags

You can run everything or just selected steps.

**Full deployment (no TLS):**

```
ansible-playbook -i hosts.ini ragapp.yml \
  --tags "packages,user,dirs,code,venv,deps,env,systemd,start,nginx,firewall,selinux"
```

**Only (env + service) changes:**

```
ansible-playbook -i hosts.ini ragapp.yml --tags "env,systemd,start"
```

**Enable TLS (after DNS is set):**

```
ansible-playbook -i hosts.ini ragapp.yml --tags "tls"
```

### 2.4 What It Does

* Installs OS packages (`dnf`)
* Creates `ragapp` user and directories
* Creates Python venv and installs dependencies
* Writes `/etc/default/ragapp` (600) with environment variables
* Creates and enables `ragapp.service`
* (Optional) Installs and configures Nginx as reverse proxy
* (Optional) Enables TLS via certbot
* Adjusts SELinux (`httpd_can_network_connect=1`) and opens firewall `http/https`

---

## 3) Bash Menu Script (`deploy_ragapp.sh`)

### 3.1 Usage

```
chmod +x deploy_ragapp.sh
./deploy_ragapp.sh
```

Choose from:

1. Create user/dirs
2. Python venv + deps
3. Write env file
4. Install systemd service
5. Install Nginx (proxy)
6. Enable TLS (certbot via snap)

> Edit the variables at the top of the script to match your paths, domain, and subpath (`BASE_URL_PATH`). Copy your code into `/opt/ragapp` (or adapt the script to `git clone`).

---

## 4) Environment & Secrets

Environment variables are stored in `/etc/default/ragapp` (root\:root, `0600`). Example content created by the scripts:

```
OPENAI_API_KEY=REPLACE_ME
DB_PATH=/opt/ragapp/data/lancedb
TABLE_NAME=wiki_aesir
HOST=127.0.0.1
PORT=8501
BASE_URL_PATH=
```

**Important:** Rotate credentials if they have ever been committed. Prefer CI/CD or host-level secret stores for production.

---

## 5) Nginx & Subpath

* Default root path: app served at `http://<domain>/`
* Subpath mode: set `base_url_path: "rag"` (Ansible) or `BASE_URL_PATH=rag` (Bash), which adds `--server.baseUrlPath rag` to Streamlit and proxies `/rag/` in Nginx.

**WebSockets:** The configs include `Upgrade`/`Connection` headers and long read/send timeouts for Streamlit’s live updates.

---

## 6) Systemd Service

Service file: `/etc/systemd/system/ragapp.service`

Common commands:

```
sudo systemctl status ragapp
sudo systemctl restart ragapp
sudo journalctl -u ragapp -e
```

Logs also append to:

```
/var/log/ragapp/app.log
/var/log/ragapp/app.err
```

---

## 7) Firewall & SELinux

* `firewalld` opens `http`/`https` when Nginx is enabled
* SELinux boolean `httpd_can_network_connect=1` allows Nginx to proxy to the app on `127.0.0.1:8501`

---

## 8) Updating the App

**Ansible:** re-run the tags you need (`code`, `deps`, `systemd`, etc.)

**Bash:** rerun the relevant menu items (e.g., `Python venv + deps` then `Install systemd service`).

**Manual (quick):**

```
cd /opt/ragapp
sudo -u ragapp bash -lc 'source .venv/bin/activate && pip install -r requirements.txt'
sudo systemctl restart ragapp
```

---

## 9) Troubleshooting

* **502/Bad Gateway (Nginx):**

  * `systemctl status ragapp` — confirm the app is running
  * `curl -I http://127.0.0.1:8501` — check local health
  * `nginx -t && systemctl reload nginx`
* **White page / UI stuck:** mismatched subpath — ensure `--server.baseUrlPath` equals Nginx location (`/rag/`).
* **TLS errors:** run the `tls` tag only after DNS points to your server; check `/var/log/nginx/error.log`.
* **Permission denied reading app files:** verify owner/group `ragapp:ragapp` and correct modes in `/opt/ragapp`.
* **Missing dependencies:** ensure `requirements.txt` exists; otherwise the scripts install bare `streamlit`.

---

## 10) Local Dev (no Nginx)

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=... DB_PATH=... TABLE_NAME=...
streamlit run rag_app_v2.py --server.address 127.0.0.1 --server.port 8501
```

Open: [http://127.0.0.1:8501](http://127.0.0.1:8501)

For subpath testing:

```
streamlit run rag_app_v2.py --server.baseUrlPath rag
```

---

## 11) Safety Notes

* Never commit `.env` or secrets. Provide `.env.example` if needed.
* Rotate leaked credentials immediately.
* Consider enabling GitHub secret scanning & pre-commit checks for `.env` files.

---

## 12) Variables Quick Reference

* **app\_user/app\_group**: `ragapp`
* **app\_dir**: `/opt/ragapp`
* **venv\_dir**: `/opt/ragapp/.venv`
* **env\_file**: `/etc/default/ragapp`
* **entrypoint**: `rag_app_v2.py`
* **listen**: `127.0.0.1:8501` (proxied by Nginx)
* **domain**: `example.com` (change to your domain)
* **subpath**: `base_url_path` / `BASE_URL_PATH` (empty for root)

---

## 13) License & Attribution

Feel free to adapt these scripts for your environment. Contributions welcome.

