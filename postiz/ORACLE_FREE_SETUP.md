# Postiz on Oracle Cloud — 100% Free, Always On

A genuinely free-forever server for Postiz. No monthly cost. Oracle asks for a
credit card to verify identity but **does not charge** Always Free resources.

**Result:** Postiz running 24/7 at `https://yourname.duckdns.org` for $0.

---

## Part 1 — Create the free server (Oracle console)

1. Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/).
   Pick a home region close to you (you can't change it later).
2. In the console: **Menu → Compute → Instances → Create Instance**.
3. **Image and shape → Edit:**
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **Ampere → VM.Standard.A1.Flex**, set **4 OCPUs / 24 GB RAM**
     (all free). If you see *"out of capacity"*, either retry later or pick
     **VM.Standard.E2.1.Micro** (AMD, 1 GB — the safe fallback).
4. **Add SSH keys:** choose *Generate a key pair for me* and **download both
   keys** (you need the private key to log in).
5. Leave networking as default (it creates a VCN with a public IP). Click
   **Create**. Wait ~1 min, then copy the instance's **Public IP address**.

### Open the firewall (BOTH layers — this is the #1 gotcha)

**Layer 1 — Oracle's virtual firewall:**
1. On the instance page, click the **Virtual Cloud Network** link.
2. **Security Lists → Default Security List → Add Ingress Rules**, add two:
   | Source CIDR | IP Protocol | Destination Port |
   |---|---|---|
   | `0.0.0.0/0` | TCP | `80` |
   | `0.0.0.0/0` | TCP | `443` |

**Layer 2 — the server's own iptables:** handled automatically by `setup.sh`
below (Oracle's Ubuntu images block everything by default).

---

## Part 2 — Free domain (DuckDNS)

1. Go to [duckdns.org](https://www.duckdns.org), sign in (Google/GitHub — free).
2. Type a subdomain (e.g. `hplandscaping`) and click **add domain**.
3. Copy your **token** (shown at the top of the page).

You'll paste the subdomain + token into the setup script — it points the
domain at your server and keeps it updated automatically.

---

## Part 3 — Install Postiz

### Option A — Zero-SSH (cloud-init, fully hands-off)

Best if you'd rather not touch a terminal at all. **Before** clicking "Create
Instance" in Part 1, expand **Show advanced options → Management → User data →
Paste cloud-init script**, and paste the contents of
[`cloud-init.yaml`](./cloud-init.yaml) with your DuckDNS `DUCK_SUB` and
`DUCK_TOKEN` filled in at the top. The server installs Docker, opens its
firewall, points your domain, and launches Postiz automatically (~3–5 min after
it boots). You still must add the VCN ingress rules (Part 1). Then skip straight
to opening `https://yourname.duckdns.org`.

### Option B — SSH and run the script

SSH into the server (from your machine, using the private key you downloaded):
```bash
ssh -i /path/to/private-key ubuntu@<YOUR_PUBLIC_IP>
```

Then run:
```bash
git clone https://github.com/paxsonloveschool-dotcom/claude-code-config.git
cd claude-code-config/postiz
chmod +x setup.sh
./setup.sh
```

The script installs Docker, opens the OS firewall, wires up DuckDNS, generates
secrets, and launches everything. On ARM it'll ask for a Postiz `-arm64` image
tag — accept the default or grab the newest from
[the package page](https://github.com/gitroomhq/postiz-app/pkgs/container/postiz-app).

When it finishes, open **`https://yourname.duckdns.org`** and register your
admin account. Then lock signups:
```bash
sed -i 's/DISABLE_REGISTRATION=false/DISABLE_REGISTRATION=true/' .env
docker compose up -d
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Site won't load / times out | Re-check **both** firewall layers (Oracle ingress rules + `./setup.sh` ran). |
| HTTPS cert error on first load | Wait ~30–60s; Caddy is fetching the Let's Encrypt cert. Confirm DNS points to the right IP: `ping yourname.duckdns.org`. |
| Postiz container restarts / OOM (AMD 1 GB shape) | Add swap: `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`. |
| ARM image won't pull or crashes | Pin a different `-arm64` tag in `.env` (`POSTIZ_IMAGE=...`) and `docker compose up -d`. |
| Need logs | `docker compose logs -f postiz` |

For everything else (updates, backups, connecting social accounts), see
[`README.md`](./README.md).
