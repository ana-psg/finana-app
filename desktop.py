import webview
from app import app
import threading
import subprocess

def kill_port_process(port):
    """Fecha um AnaFins antigo (processo Python órfão) que esteja a ocupar a porta do Flask."""
    try:
        result = subprocess.run('netstat -ano -p TCP', shell=True, capture_output=True, text=True)
        pids = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            # Só quem está ESCUTANDO exatamente na porta local (ex: 127.0.0.1:8000).
            # Antes, ":8000" também pegava :80001 e conexões de saída de outros programas.
            if len(parts) >= 5 and parts[1].endswith(f':{port}') and parts[3] == 'LISTENING':
                pids.add(parts[-1])

        for pid in pids:
            if pid.isdigit() and pid != '0' and _eh_python(pid):
                subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
            elif pid.isdigit() and pid != '0':
                print(f"Aviso: a porta {port} está em uso por outro programa (PID {pid}); ele não foi fechado.")
    except Exception as e:
        print(f"Aviso ao limpar portas: {e}")

def _eh_python(pid):
    """Só fecha um AnaFins antigo (python.exe/pythonw.exe), nunca outro programa que use a porta."""
    try:
        result = subprocess.run(f'tasklist /FI "PID eq {pid}" /FO CSV /NH', shell=True, capture_output=True, text=True)
        return result.stdout.strip().strip('"').lower().startswith('python')
    except Exception:
        return False

def start_server():
    # 0.0.0.0 = aceita o celular no Wi-Fi de casa (fora do computador, pede o PIN; ver routes/acesso.py)
    app.run(host='0.0.0.0', port=8000, use_reloader=False)

if __name__ == '__main__':
    # 1. Limpa qualquer processo preso na porta 8000
    kill_port_process(8000)
    
    # 2. Inicia o servidor Flask
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()
    
    # 3. Cria a janela do aplicativo com o título limpo "AnaFins"
    webview.create_window(
        'AnaFins', 
        'http://127.0.0.1:8000', 
        width=1300, 
        height=850,
        background_color='#0f0f13'
    )
    
    # 4. Permite baixar arquivos (ex: o PDF do relatório mensal)
    webview.settings['ALLOW_DOWNLOADS'] = True

    # 5. Inicia o pywebview
    webview.start()