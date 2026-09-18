import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH para que pytest consiga importar o módulo 'src'
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
