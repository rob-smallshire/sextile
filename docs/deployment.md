# Deploying Sextile services

An operations note: how the Sextile services are hosted on one small VPS, how a
push becomes a running service, and where the secrets live. It records decisions
made before the first deployment so they are argued once, not per service.

## The host

```
netcup VPS pico             one IPv4 address, one IPv6, a handful of services
viewdata.no                 the domain; each service takes a subdomain
```

One cheap VPS runs every service. A Viewdata service is low-traffic and
low-load, so a single small box carries a handful or two of them at once.

Why one box: the cost of a second is not repaid by the load, and one host keeps
the DNS, the firewall and the deploy path in one place.

## Users on the host

| User | Kind | Login | `sudo` | Owns |
| --- | --- | --- | --- | --- |
| `<admin>` | a person | SSH key | full | administers the box |
| per service, e.g. `weather-viewdata` | system account | none (`nologin`) | none | its own process |
| `deploy` | CI account | SSH key, added when CI is wired | one `systemctl restart` | the code under `/srv` |

```sh
# one locked-down system account per service
sudo adduser --system --group --no-create-home --shell /usr/sbin/nologin weather-viewdata
```

Three classes, split by how much each can do. A service account cannot log in or
`sudo`, so a reached service is a dead end; `deploy` can update code and restart
one unit and no more; only `<admin>` holds real power, and only over a key. A
service's writable state is not a hand-chowned home directory but a `systemd`
`StateDirectory`, created and owned for the service on start.

Why split them: the internet-facing account and the CI account each hold the
least that lets them do their one job, so a compromise of either stops there.

## Hardening the host

The host is Debian 13. The admin account is created with a password for `sudo`
and a public key, and root's own SSH login is then closed:

```sh
sudo adduser <admin>
sudo usermod -aG sudo <admin>
sudo install -d -m 700 -o <admin> -g <admin> /home/<admin>/.ssh
# the admin's public key goes in /home/<admin>/.ssh/authorized_keys, mode 0600
```

```
# /etc/ssh/sshd_config.d/10-hardening.conf
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
```

The firewall denies inbound by default and opens each port only as the thing
behind it goes in; SSH is rate-limited rather than merely allowed:

```sh
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw limit 22/tcp
sudo ufw enable
```

`fail2ban` installs with its `sshd` jail enabled and bans persistent probers;
`unattended-upgrades` applies security updates daily:

```sh
sudo apt install -y fail2ban unattended-upgrades
# /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
```

Why in this order: a proven key login and a `ufw` rule admitting SSH come before
the sshd restart and before `ufw enable`, so no step locks the box against the
person running it. Password auth being off makes `fail2ban` belt-and-braces, kept
for the log quiet and the blocked scanners.

## Two planes

| Plane    | Protocol | Port            | Reaches                     | Routed by  |
| -------- | -------- | --------------- | --------------------------- | ---------- |
| Viewdata | raw TCP  | one high port each | the Sextile service      | the port   |
| Web      | HTTP(S)  | 80 / 443        | a one-page connection notice | the subdomain |

A Viewdata client opens a raw TCP socket. Nothing on that wire names a subdomain,
so the **port is the selector** and the subdomain is a human convention pointing
at the shared IP. `weather.viewdata.no:16651` and `wiki.viewdata.no:16651` would
reach the same service. The web plane is ordinary HTTP, so there the **subdomain
is the selector** and a reverse proxy routes each to its own landing page.

Why keep them apart: they are routed by different things, so a proxy that earns
its place on the web plane has nothing to do on the Viewdata plane.

## A service, as a systemd unit

```ini
# /etc/systemd/system/weather-viewdata.service
[Unit]
Description=weather-viewdata Viewdata service
After=network-online.target

[Service]
User=weather-viewdata
StateDirectory=weather-viewdata
WorkingDirectory=/var/lib/weather-viewdata
ExecStart=/srv/weather-viewdata/.venv/bin/sextile serve weather_viewdata:app --port 16651
EnvironmentFile=-/etc/sextile/weather-viewdata.env
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Each service is one unit: an unprivileged user, a fixed high port, `Restart` so a
crash recovers. `StateDirectory` gives it a `/var/lib/weather-viewdata` it owns
for its SQLite file, and `WorkingDirectory` runs it there while the code stays
under `/srv`. The `-` on `EnvironmentFile` makes the file optional, so a service
with no secrets needs no file and no edit to this unit.

Why systemd over containers: for a few tiny long-lived sockets on a 2 GB box,
one unit per service is lighter than Docker and asks nothing of the RAM the small
host is chosen to save.

## The web plane, with Caddy

```
# /etc/caddy/Caddyfile
weather.viewdata.no {
    root * /srv/www/weather
    file_server
}
wiki.viewdata.no {
    root * /srv/www/wiki
    file_server
}
```

`caddy` on 80/443 serves one static page per subdomain and obtains a Let's
Encrypt certificate for each automatically. Each page states the host and port to
dial; it is not the service, only the notice beside its door.

Why Caddy: automatic TLS for every subdomain with near-zero configuration, which
is the whole of what the web plane needs.

## Bringing up the web plane

DNS at the `viewdata.no` registrar points every subdomain at the host with one
wildcard record, and the apex alongside it:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| `A` | `*` | `<VPS_IP>` | 300 |
| `A` | `@` | `<VPS_IP>` | 300 |

The firewall opens the web ports (80 for the ACME challenge, 443 for traffic and
HTTP/3):

```sh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
```

Caddy installs from its official apt repository, runs as an unprivileged `caddy`
user under `systemd`, and reads `/etc/caddy/Caddyfile`; each service's landing
page lives under `/srv/www/<service>`. On reload Caddy fetches, and thereafter
renews, the certificate for each name in the Caddyfile.

Why this order: Caddy proves control of a name by answering Let's Encrypt on
port 80, so the record must resolve and 80 must be open before Caddy starts, or
the challenge retries in a loop. The wildcard record means a new service needs
only a Caddyfile block, never another DNS change.

## Repository and build

```
packages/sextile/            published to PyPI, versioned (see the changelog)
packages/weather-viewdata/   depends on the published sextile, deployed on its own
```

The workspace stays as it is; services are not extracted to their own
repositories. Deployment decouples by **publishing `sextile`** as an installable
dependency, so a service installs on the box without the workspace around it, and
a push builds and ships one service alone.

Why not one repo per service: `calendar-viewdata` and `weather-viewdata` keep the
framework's first invariant honest by living in-tree (see
[architecture](architecture.md)); moving a service out removes an application
that exercises the framework in the same test run, which is a real cost and buys
nothing deployment cannot get from a published dependency.

## Secrets

```python
# in the service's config factory
api_key = os.environ["OPENWEATHER_API_KEY"]   # raises at startup if unset
```

```
# /etc/sextile/weather-viewdata.env   root:weather-viewdata  0640
OPENWEATHER_API_KEY=...
```

A service reads each secret from the environment and fails at startup if it is
missing; `systemd` supplies the environment from a file owned by root and
readable only by the service user. No service currently needs a secret; the shape
is in place for the first that does.

Secrets are provisioned **on the box, out of CI**. GitHub then holds one secret
only, the deploy key, and never an upstream API key; a compromised pipeline can
restart a service but cannot read a credential that was never given to it. When
the set of placed keys outgrows memory, the next step is `age`/SOPS: encrypted
secrets committed to the repository, decrypted only on the box.

Why fail closed: a mis-provisioned box that refuses to start is found at once; one
that starts and serves a broken page is found by a reader.

## Deployment

```
tag push  ->  GitHub Actions  ->  ssh deploy@host  ->  pull, uv sync, restart one unit
```

A version tag on `master` triggers one job, gated behind a protected GitHub
Environment so a human approves the deploy. The job connects as a `deploy` user
whose authority is a forced command or a `sudo` restricted to
`systemctl restart <that unit>`, updates the service and restarts it. The
workflow is the same whether the service has secrets or not, because it never
handles them.

Why tag-gated and scoped: the repository is public, so anyone may open a pull
request; the deploy runs only on a maintainer's tag, never on `pull_request`, and
the key's reach is one service restart rather than the box.

## Security posture

The repository is public, so nothing in it is secret and the controls do not rest
on hiding the host, the ports or the deploy mechanism, all of which the workflow
file shows.

- Untrusted CI input (`pull_request` titles, branch names) is passed through
  `env:` variables, never interpolated into a shell `run:` step.
- Third-party actions are pinned to a commit SHA, not a moving tag.
- The deploy key is a dedicated non-root user, scoped to one restart, never able
  to read a runtime secret.
- The host takes key-only SSH with root login disabled, `fail2ban`,
  `unattended-upgrades`, and a firewall open to exactly SSH, 80, 443 and the
  service ports.
- The Viewdata plane is unauthenticated by the protocol's nature, which suits a
  public read-only service; the guarded surface is the deploy path, not the call.

## When to provision the VPS

Provision the netcup box **once this note is agreed and before wiring GitHub
Actions** — it is the target the automation needs, and it is where DNS, TLS,
`systemd` and a service are proven by hand first. The order:

1. Provision the VPS; point `viewdata.no` and one subdomain at its IP.
2. Harden the host (SSH keys, firewall, `fail2ban`, `unattended-upgrades`).
3. Install Caddy; serve one static landing page over automatic TLS.
4. Install one service by hand as a `systemd` unit on its port; dial it with
   `nc weather.viewdata.no 16651`.
5. Only then add the `deploy` user and the GitHub Actions workflow, so the
   automation targets a shape already known to work.
