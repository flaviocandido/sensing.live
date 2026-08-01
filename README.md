# Sensing.Live — Coletor de Licitações (PNCP)

Fase 1 do projeto: script que consulta a API oficial e pública do
[PNCP](https://pncp.gov.br) (Portal Nacional de Contratações Públicas),
filtra as licitações por palavras-chave (no campo "objeto da compra") e
por status de recebimento de propostas, e salva o resultado em um CSV.

## Como rodar

### Opção A — sem instalar nada (recomendado para o primeiro teste)

1. Acesse https://colab.research.google.com
2. Clique em "Novo notebook"
3. Copie e cole todo o conteúdo de [`coletor_pncp.py`](coletor_pncp.py) em uma célula
4. Ajuste a seção `CONFIGURAÇÃO` no início do arquivo com suas palavras-chave
5. Aperte o botão de "play" (Shift+Enter) para rodar
6. O resultado aparece na tela e um arquivo `.csv` é gerado (baixe pelo
   ícone de pasta no menu lateral esquerdo do Colab)

### Opção B — rodando no seu computador

1. Instale o [Python](https://www.python.org/downloads/) se ainda não tiver
2. Abra o terminal (Prompt de Comando/PowerShell no Windows, Terminal no Mac)
3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Rode:

   ```bash
   python coletor_pncp.py
   ```

## Configuração

Todas as opções ficam no topo de `coletor_pncp.py`:

| Variável | Descrição |
| --- | --- |
| `PALAVRAS_CHAVE` | Lista de termos buscados no objeto da compra |
| `STATUS_FILTRO` | `abertas`, `encerradas`, `em_julgamento` ou `todas` |
| `UF_FILTRO` | Sigla do estado (ex: `SP`) ou `None` para todo o Brasil |
| `DIAS_PARA_TRAS` | Janela de dias para busca por período |
| `MAX_PAGINAS_POR_MODALIDADE` | Limite de páginas por modalidade de contratação |
| `ARQUIVO_SAIDA` | Nome do CSV gerado |
