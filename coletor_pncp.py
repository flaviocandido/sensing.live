"""
Coletor de Licitações - PNCP (Portal Nacional de Contratações Públicas)
=========================================================================
Fase 1 do projeto: script que consulta a API oficial e pública do PNCP,
filtra as licitações por palavras-chave (no campo "objeto da compra") e
por status de recebimento de propostas, e salva o resultado em um CSV.

COMO RODAR (passo a passo para quem nunca programou):

OPÇÃO A - Mais fácil, sem instalar nada (recomendado para o primeiro teste):
  1. Acesse https://colab.research.google.com
  2. Clique em "Novo notebook"
  3. Copie e cole todo o conteúdo deste arquivo em uma célula
  4. Ajuste a seção "CONFIGURAÇÃO" logo abaixo com suas palavras-chave
  5. Aperte o botão de "play" (Shift+Enter) para rodar
  6. O resultado aparece na tela e um arquivo .csv é gerado (baixe pelo
     ícone de pasta no menu lateral esquerdo do Colab)

OPÇÃO B - Rodando no seu computador:
  1. Instale o Python (https://www.python.org/downloads/) se ainda não tiver
  2. Abra o terminal (Prompt de Comando/PowerShell no Windows, Terminal no Mac)
  3. Rode: pip install requests
  4. Rode: python coletor_pncp.py
"""

import requests
import csv
import time
from datetime import date, timedelta

# =============================================================================
# CONFIGURAÇÃO — é aqui que você mexe
# =============================================================================

# Suas palavras-chave. O script marca como "encontrada" qualquer licitação
# cujo objeto contenha QUALQUER UMA destas palavras/expressões.
PALAVRAS_CHAVE = [
    "monitoramento de temperatura",
    "cadeia fria",
    "temperatura",
]

# Filtro de status. Escolha uma opção:
#   "abertas"        -> só licitações ainda recebendo propostas (RECOMENDADO no dia a dia)
#   "encerradas"      -> propostas já encerradas, aguardando julgamento/resultado
#   "em_julgamento"   -> mesma lista de "encerradas" (o PNCP não distingue via API;
#                         a diferenciação fina exige abrir cada processo individualmente)
#   "todas"           -> não filtra por status (traz tudo do período)
STATUS_FILTRO = "abertas"

# Filtro de estado (opcional). Deixe como None para buscar em todo o Brasil
# (mais lento — só recomendado quando o sistema já estiver rodando sozinho).
# Para testar rápido agora, preencha com sua sigla, ex: "SP", "MG", "RJ".
UF_FILTRO = "SP"

# Período de busca (usado apenas quando STATUS_FILTRO != "abertas")
DIAS_PARA_TRAS = 7  # busca licitações publicadas nos últimos N dias

# Limite de segurança: quantas páginas no máximo buscar por modalidade.
# Cada página traz até 500 registros. 40 páginas = até 20.000 registros
# por modalidade, o que é mais que suficiente na prática. Isso evita que
# o script fique rodando por muito tempo em modalidades com alto volume
# (ex: Pregão Eletrônico nacional).
MAX_PAGINAS_POR_MODALIDADE = 40

# Nome do arquivo de saída
ARQUIVO_SAIDA = "licitacoes_encontradas.csv"

# =============================================================================
# Não é necessário mexer abaixo desta linha
# =============================================================================

BASE_URL = "https://pncp.gov.br/api/consulta/v1"

# Códigos de modalidade de contratação (tabela de domínio do PNCP)
MODALIDADES = {
    1: "Leilão - Eletrônico",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial",
    6: "Pregão - Eletrônico",
    7: "Pregão - Presencial",
    8: "Dispensa",
    9: "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão - Presencial",
}


def fazer_requisicao(url, params, tentativas=2):
    """Faz a chamada HTTP com timeout maior e uma nova tentativa em caso de timeout."""
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            return requests.get(url, params=params, timeout=60)
        except requests.exceptions.RequestException as erro:
            ultimo_erro = erro
            if tentativa < tentativas:
                continue
    raise ultimo_erro


def bate_com_palavra_chave(objeto_compra: str) -> bool:
    """Verifica se o texto do objeto contém alguma das palavras-chave configuradas."""
    if not objeto_compra:
        return False
    texto = objeto_compra.lower()
    return any(palavra.lower() in texto for palavra in PALAVRAS_CHAVE)


def buscar_abertas():
    """Busca licitações com propostas ainda em aberto (endpoint dedicado).

    IMPORTANTE: este endpoint também exige o código da modalidade de
    contratação como parâmetro (não é opcional na prática, mesmo a
    documentação sugerindo o contrário) — por isso percorremos todas as
    modalidades, uma de cada vez, e juntamos os resultados.
    """
    resultados = []
    hoje = date.today().strftime("%Y%m%d")

    for codigo_modalidade, nome_modalidade in MODALIDADES.items():
        pagina = 1
        while True:
            url = f"{BASE_URL}/contratacoes/proposta"
            params = {
                "dataFinal": hoje,
                "codigoModalidadeContratacao": codigo_modalidade,
                "pagina": pagina,
                "tamanhoPagina": 50,
            }
            if UF_FILTRO:
                params["uf"] = UF_FILTRO
            try:
                resp = fazer_requisicao(url, params)
                if resp.status_code == 204:
                    break  # sem resultados para esta modalidade
                if resp.status_code == 400:
                    print(f"  [{nome_modalidade}] modalidade não aceita neste endpoint (400) — pulando")
                    break
                resp.raise_for_status()
            except requests.exceptions.RequestException as erro:
                print(f"  [{nome_modalidade}] erro ao consultar, pulando: {erro}")
                break

            dados = resp.json()
            resultados.extend(dados.get("data", []))

            total_paginas = dados.get("totalPaginas", 1)
            total_registros = dados.get("totalRegistros", 0)
            if pagina == 1 and total_registros:
                print(f"  [{nome_modalidade}] total encontrado: {total_registros} — baixando...")
            if pagina >= total_paginas or total_paginas == 0 or pagina >= MAX_PAGINAS_POR_MODALIDADE:
                break
            pagina += 1

    return resultados


def buscar_por_periodo():
    """Busca licitações publicadas no período configurado, em todas as modalidades."""
    resultados = []
    data_final = date.today()
    data_inicial = data_final - timedelta(days=DIAS_PARA_TRAS)

    for codigo_modalidade, nome_modalidade in MODALIDADES.items():
        pagina = 1
        while True:
            url = f"{BASE_URL}/contratacoes/publicacao"
            params = {
                "dataInicial": data_inicial.strftime("%Y%m%d"),
                "dataFinal": data_final.strftime("%Y%m%d"),
                "codigoModalidadeContratacao": codigo_modalidade,
                "pagina": pagina,
                "tamanhoPagina": 50,
            }
            if UF_FILTRO:
                params["uf"] = UF_FILTRO
            try:
                resp = fazer_requisicao(url, params)
                if resp.status_code == 204:
                    break  # sem resultados para esta modalidade
                if resp.status_code == 400:
                    print(f"  [{nome_modalidade}] modalidade não aceita neste endpoint (400) — pulando")
                    break
                resp.raise_for_status()
            except requests.exceptions.RequestException as erro:
                print(f"  [{nome_modalidade}] erro ao consultar, pulando: {erro}")
                break

            dados = resp.json()
            resultados.extend(dados.get("data", []))

            total_paginas = dados.get("totalPaginas", 1)
            total_registros = dados.get("totalRegistros", 0)
            if pagina == 1 and total_registros:
                print(f"  [{nome_modalidade}] total encontrado: {total_registros} — baixando...")
            if pagina >= total_paginas or total_paginas == 0 or pagina >= MAX_PAGINAS_POR_MODALIDADE:
                break
            pagina += 1

    return resultados


def status_esta_encerrada(item) -> bool:
    """Compara a data-fim de propostas com hoje para inferir se está encerrada."""
    data_fim = item.get("dataEncerramentoProposta")
    if not data_fim:
        return False
    try:
        data_fim_date = date.fromisoformat(data_fim[:10])
        return data_fim_date < date.today()
    except ValueError:
        return False


def main():
    inicio = time.time()
    print(f"Buscando licitações — status: {STATUS_FILTRO}")
    print(f"Palavras-chave: {', '.join(PALAVRAS_CHAVE)}")
    if UF_FILTRO:
        print(f"Estado: {UF_FILTRO} (para buscar no Brasil todo, mude UF_FILTRO para None)")
    print()

    if STATUS_FILTRO == "abertas":
        brutos = buscar_abertas()
    else:
        brutos = buscar_por_periodo()
        if STATUS_FILTRO in ("encerradas", "em_julgamento"):
            brutos = [item for item in brutos if status_esta_encerrada(item)]

    print(f"\nTotal de licitações analisadas: {len(brutos)}")

    encontradas = [item for item in brutos if bate_com_palavra_chave(item.get("objetoCompra", ""))]
    print(f"Licitações que batem com as palavras-chave: {len(encontradas)}\n")

    if not encontradas:
        print("Nenhuma licitação encontrada com essas palavras-chave neste filtro.")
        print(f"\nTempo total de execução: {time.time() - inicio:.1f} segundos — CONCLUÍDO")
        return

    # Salva em CSV
    with open(ARQUIVO_SAIDA, "w", newline="", encoding="utf-8-sig") as f:
        campos = [
            "numeroControlePNCP", "orgao", "unidadeCompradora", "municipio", "uf",
            "modalidade", "situacao", "objeto", "valorTotalEstimado",
            "dataPublicacaoPncp", "dataAberturaProposta", "dataEncerramentoProposta",
        ]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for item in encontradas:
            orgao = item.get("orgaoEntidade", {}) or {}
            unidade = item.get("unidadeOrgao", {}) or {}
            writer.writerow({
                "numeroControlePNCP": item.get("numeroControlePNCP"),
                "orgao": orgao.get("razaoSocial"),
                "unidadeCompradora": unidade.get("nomeUnidade"),
                "municipio": unidade.get("municipioNome"),
                "uf": unidade.get("ufSigla"),
                "modalidade": item.get("modalidadeNome"),
                "situacao": item.get("situacaoCompraNome"),
                "objeto": item.get("objetoCompra"),
                "valorTotalEstimado": item.get("valorTotalEstimado"),
                "dataPublicacaoPncp": item.get("dataPublicacaoPncp"),
                "dataAberturaProposta": item.get("dataAberturaProposta"),
                "dataEncerramentoProposta": item.get("dataEncerramentoProposta"),
            })

    print(f"Resultado salvo em: {ARQUIVO_SAIDA}")
    print(f"\nTempo total de execução: {time.time() - inicio:.1f} segundos — CONCLUÍDO")

    # Mostra um resumo na tela também
    for item in encontradas[:10]:
        print("-" * 70)
        print(f"Órgão: {(item.get('orgaoEntidade') or {}).get('razaoSocial')}")
        print(f"Objeto: {item.get('objetoCompra')}")
        print(f"Valor estimado: R$ {item.get('valorTotalEstimado')}")
        print(f"Encerramento propostas: {item.get('dataEncerramentoProposta')}")


if __name__ == "__main__":
    main()
