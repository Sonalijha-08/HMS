import socket
import threading

def handle_client(conn, addr):
    print(f"\n[*] SMTP connection established from {addr[0]}:{addr[1]}")
    try:
        conn.sendall(b"220 localhost HMS Mock SMTP Server Ready\r\n")
        email_content = ""
        in_data_mode = False
        
        while True:
            data = conn.recv(4096)
            if not data:
                break
            
            # Simple SMTP protocol parser
            chunk = data.decode('utf-8', errors='ignore')
            
            if in_data_mode:
                email_content += chunk
                if "\r\n.\r\n" in email_content or "\n.\n" in email_content or email_content.endswith("\r\n.\r\n"):
                    # Process email
                    print("\n" + "="*30 + " MOCK SMTP RECEIPT " + "="*30)
                    print(email_content.replace("\r\n.\r\n", "").replace("\n.\n", "").strip())
                    print("="*79 + "\n")
                    conn.sendall(b"250 2.0.0 OK: Message accepted\r\n")
                    in_data_mode = False
                    email_content = ""
            else:
                lines = chunk.split('\r\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    cmd_upper = line.upper()
                    if cmd_upper.startswith("EHLO") or cmd_upper.startswith("HELO"):
                        conn.sendall(b"250-localhost Hello\r\n250 HELP\r\n")
                    elif cmd_upper.startswith("MAIL FROM"):
                        conn.sendall(b"250 2.1.0 OK\r\n")
                    elif cmd_upper.startswith("RCPT TO"):
                        conn.sendall(b"250 2.1.5 OK\r\n")
                    elif cmd_upper.startswith("DATA"):
                        conn.sendall(b"354 Start mail input; end with <CR><LF>.<CR><LF>\r\n")
                        in_data_mode = True
                    elif cmd_upper.startswith("QUIT"):
                        conn.sendall(b"221 2.0.0 localhost closing connection\r\n")
                        return
                    else:
                        conn.sendall(b"250 OK\r\n")
    except Exception as e:
        print(f"Error handling SMTP client: {e}")
    finally:
        conn.close()
        print(f"[*] SMTP connection closed from {addr[0]}:{addr[1]}")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('127.0.0.1', 1025))
        server.listen(5)
        print("[*] HMS Mock SMTP Server running locally on 127.0.0.1:1025...")
        while True:
            conn, addr = server.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
    except Exception as e:
        print(f"Error starting mock SMTP server: {e}")
    finally:
        server.close()

if __name__ == '__main__':
    start_server()
