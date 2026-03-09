import paramiko
from scp import SCPClient
import threading
import time
import sys
import itertools

# --- Config ---
# new dict for each server. SSH_USER is always root.
SSH_USER = "root"

HOSTS = [
    {"ip": "192.168.12.147", "ssh_pass": "pass", "db_pass": "pass"},
    {"ip": "192.168.12.153", "ssh_pass": "pass", "db_pass": "pass"},
    # {"ip": "192.168.12.149", "ssh_pass": "anotherpass", "db_pass": "dbpass3"},
]

def spinner(stop_event):
    for frame in itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]):
        if stop_event.is_set():
            break
        print(f"\r  {frame}  Working...", end="", flush=True)
        time.sleep(0.1)
    print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the spinner line when done

def ssh_connect(ip, ssh_pass):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, 22, SSH_USER, ssh_pass)
    print(f"[+] Connected to server {ip}")
    return client

def check_distro(client):
    shell = client.invoke_shell()
    if shell.recv_ready():
        shell.recv(10000)

    shell.send("cat /etc/os-release\n")
    time.sleep(1)

    output = shell.recv(10000).decode("utf-8").lower()
    shell.close()

    if "rhel" in output or "fedora" in output or "centos" in output:
        return "rhel"
    if "debian" in output or "ubuntu" in output:
        return "debian"

    return None

def install_lamp_debian(client, db_pass, ip):
    print(f"[+] Working on installing LAMP stack on: {ip}")

    with SCPClient(client.get_transport()) as scp:
        scp.put('install-templates/deb_lamp.sh', '/root/')

    cmd = f"DB_ROOT_PASS='{db_pass}' bash /root/deb_lamp.sh"
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    stdout.read()

def install_lamp_rhel(client, db_pass):
    with SCPClient(client.get_transport()) as scp:
        scp.put('install-templates/rhel_lamp.sh', '/root/')

    cmd = f"DB_ROOT_PASS='{db_pass}' bash /root/rhel_lamp.sh"
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    stdout.read()

def setup_server(host, results):
    ip = host["ip"]
    try:
        client = ssh_connect(ip, host["ssh_pass"])
        distro = check_distro(client)

        if distro == "debian":
            install_lamp_debian(client, host["db_pass"], ip)
        elif distro == "rhel":
            install_lamp_rhel(client, host["db_pass"])
        else:
            results[ip] = "skipped (unknown distro)"
            client.close()
            return

        client.close()
        results[ip] = "done"

    except Exception as e:
        results[ip] = f"failed: {e}"

# --- Main execution ---

results = {}
threads = []

for host in HOSTS:
    t = threading.Thread(target=setup_server, args=(host, results))
    threads.append(t)
    t.start()

stop_spinner = threading.Event()
spin_thread = threading.Thread(target=spinner, args=(stop_spinner,))
spin_thread.start()

for t in threads:
    t.join()

stop_spinner.set()
spin_thread.join()

print("\n--- Results ---")
for ip, status in results.items():
    print(f"  {ip} ... {status}")

print("\n--- PHP Info Pages ---")
for ip, status in results.items():
    if status == "done":
        print(f"  http://{ip}/info.php")
