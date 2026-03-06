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
    # Runs in its own thread, printing a rotating spinner until stop_event is set.
    # \r moves the cursor back to the start of the line so each frame overwrites the last.
    # flush=True forces the output to appear immediately instead of being buffered.
    for frame in itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]):
        if stop_event.is_set():
            break
        print(f"\r  {frame}  Working...", end="", flush=True)
        time.sleep(0.1)
    print("\r" + " " * 20 + "\r", end="", flush=True)  # Clear the spinner line when done

def ssh_connect(ip, ssh_pass):
    client = paramiko.SSHClient()
    # AutoAddPolicy trusts new servers automatically instead of raising an error
    # when no saved host key exists yet.
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, 22, SSH_USER, ssh_pass)
    print(f"[+] Connected to server {ip}")
    return client

def check_distro(client):
    # Uses an interactive shell (not exec_command) so we can drain any login
    # banner text before sending our command — otherwise it could pollute the output.
    shell = client.invoke_shell()
    if shell.recv_ready():
        shell.recv(10000)

    shell.send("cat /etc/os-release\n")
    time.sleep(1)  # Wait for the remote command to finish and buffer the response

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

    # Pass the DB password 
    cmd = f"DB_ROOT_PASS='{db_pass}' bash /root/deb_lamp.sh"
    # get_pty=True allocates a pseudo-terminal — required by scripts that use
    # sudo or expect an interactive terminal to run correctly
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    # Must drain stdout even though we discard it — otherwise the remote process
    # stalls waiting for the buffer to clear
    stdout.read()

def install_lamp_rhel(client, db_pass):
    with SCPClient(client.get_transport()) as scp:
        scp.put('install-templates/rhel_lamp.sh', '/root/')

    cmd = f"DB_ROOT_PASS='{db_pass}' bash /root/rhel_lamp.sh"
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    stdout.read()

def setup_server(host, results):
    # Runs the full install flow for one server. Designed to be called in a
    # thread so all servers are provisioned in parallel. Any exception is caught
    # and recorded rather than crashing the whole program.
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

results = {}  # Shared dict — each thread writes to its own IP key
threads = []

# Spin up one thread per server so they all run at the same time.
# args=(host, results) passes those two values into setup_server.
for host in HOSTS:
    t = threading.Thread(target=setup_server, args=(host, results))
    threads.append(t)
    t.start()

# Start the spinner in a background thread while we wait for installs to finish.
# threading.Event is a simple flag — we set it to tell the spinner to stop.
stop_spinner = threading.Event()
spin_thread = threading.Thread(target=spinner, args=(stop_spinner,))
spin_thread.start()

# join() blocks until that thread finishes — we wait on all of them before
# printing so the summary only appears once everything is done.
for t in threads:
    t.join()

stop_spinner.set()  # Signal the spinner to stop
spin_thread.join()  # Wait for it to finish clearing the line

print("\n--- Results ---")
for ip, status in results.items():
    print(f"  {ip} ... {status}")

print("\n--- PHP Info Pages ---")
for ip, status in results.items():
    if status == "done":
        print(f"  http://{ip}/info.php")
