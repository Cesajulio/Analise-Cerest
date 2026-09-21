import urllib.request
import os

files_to_download = ['ACGRBR23.dbc', 'ACGRBR24.dbc', 'ACGRBR25.dbc', 'ACGRBR26.dbc']
dirs = ['FINAIS', 'PRELIM']

for filename in files_to_download:
    print(f"\nProcurando por {filename}...")
    baixou = False
    
    for d in dirs:
        url = f'ftp://ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/{d}/{filename}'
        print(f"Tentando baixar de: {url}")
        
        try:
            # We try to download directly. If it fails (e.g. 550 file not found), it raises an exception
            urllib.request.urlretrieve(url, filename)
            print(f"Download concluído com sucesso a partir de {d}!")
            baixou = True
            break # Exit the dirs loop, proceed to next file
        except Exception as e:
            print(f"Não encontrado em {d} (ou erro): {e}")
            
    if not baixou:
        print(f"AVISO: Não foi possível baixar {filename} em nenhuma das pastas.")
        
print("\nProcesso de atualização finalizado!")
