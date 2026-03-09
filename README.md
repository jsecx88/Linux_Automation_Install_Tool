# Linux Automation Install Tool

Provisions a LAMP stack across multiple Linux servers in parallel over SSH.

## What it does

- Connects to each host via SSH
- Detects the distro (Debian/Ubuntu or RHEL/CentOS/Fedora)
- SCPs the appropriate install script and runs it
- Installs Apache, MariaDB, and PHP with common modules
- Configures the firewall and security headers
- Prints a summary with links to the PHP info test pages

## Setup

Edit the `HOSTS` list in `main.py` with your server IPs and passwords:

```python
HOSTS = [
    {"ip": "192.168.1.10", "ssh_pass": "yourpass", "db_pass": "dbpass"},
]
```

Install dependencies:

```bash
pip install paramiko scp
```

## Usage

```bash
python main.py
```

## Notes

- SSH user is hardcoded to `root`
- Delete `/var/www/html/info.php` on each server after setup
- Supports Debian/Ubuntu and RHEL/CentOS/Fedora
