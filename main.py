from difflib import SequenceMatcher
from pathlib import Path
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait,Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
import json
import time
from rapidfuzz import fuzz, process
from selenium.common.exceptions import StaleElementReferenceException
from difflib import SequenceMatcher

import os
from fuzzywuzzy import fuzz
import pandas as pd


# ======== CONFIGURAÇÕES ========
load_dotenv()

USER = os.getenv("LOGIN", "")
PASSWORD = os.getenv("PASSWORD", "")

abas = ["https://juizdefora-mg-tst.vivver.com/adm/profissional"]
abas_id = []



URL = "https://juizdefora-mg-tst.vivver.com/login"

WAIT_TIME = 10
PLANILHA_PROFISSIONAIS = Path(__file__).parent / "Planilha" / "Teste.xlsx"
COLUNAS_OBRIGATORIAS = {"Nome", "CPF", "CNS", "CBO - Descrição", "N Conselho"}

# ======== FUNÇÕES AUXILIARES ========

def normalizar(texto):
    texto = texto.upper().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def carregar_profissionais(caminho=PLANILHA_PROFISSIONAIS):
    """Lê a planilha e retorna somente as linhas que possuem nome."""
    if not caminho.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {caminho}")

    dados = pd.read_excel(caminho, dtype=str, keep_default_na=False)
    dados.columns = dados.columns.str.strip()

    colunas_ausentes = COLUNAS_OBRIGATORIAS - set(dados.columns)
    if colunas_ausentes:
        raise ValueError(
            "Colunas obrigatórias ausentes na planilha: "
            + ", ".join(sorted(colunas_ausentes))
        )

    dados["Nome"] = dados["Nome"].str.strip()
    dados = dados[dados["Nome"] != ""]

    profissionais = dados.to_dict(orient="records")
    print(f"{len(profissionais)} profissional(is) carregado(s) de {caminho.name}.")
    return profissionais

'''
def carregar_dados_times(caminho):
    try:
        with open(caminho, "r", encoding="utf-8") as teamfile:
            leitor = json.load(teamfile)
            if "teams" in leitor:
                dados = leitor["teams"]
            else:
                dados = leitor  
    except FileNotFoundError:
        print(f"[ERRO] Arquivo JSON não encontrado: {caminho}")
        dados = []
    except json.JSONDecodeError as e:
        print(f"[ERRO] Erro ao ler o arquivo JSON: {e}")
        dados = []

    return dados
    '''



def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def inserir(espera, action,campo,valor,controle=False, driver=False):

    id_campo = f"s2id_{campo}"
    campo_id = f"lookup_key_{campo}"
    try:
        print(f"➡️ Esperando o campo '{campo_id}' ser clicável")
        campo_id_element = espera.until(EC.element_to_be_clickable((By.ID, campo_id)))

        # Tentativa de limpar (ignorar erro)
        try:
            campo_id_element.clear()
        except:
            pass

        print(f"✅ Campo {campo_id} clicado")
        print(f"➡️ Esperando o campo '{id_campo}' ser clicável")

        # Tenta clicar e digitar com anti-stale
        for _ in range(3):
            try:
                campo = espera.until(EC.visibility_of_element_located((By.ID, id_campo)))
                action.move_to_element(campo).click().perform()
                action.send_keys(valor).perform()
                break
            except StaleElementReferenceException:
                print("♻️ Campo ficou stale — recarregando elemento...")
                time.sleep(0.5)
        else:
            print("❌ Falha ao recuperar o campo após 3 tentativas")
            return False

        time.sleep(0.7)

        # Verifica se não houve resultados
        try:
            espera.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "ul.select2-results li.select2-no-results"
                ))
            )
            print(f"❌ Nenhum resultado encontrado para '{valor}'. Pulando...")
            return False
        except TimeoutException:
            pass

        # Controle extra para select2
        if controle:
            for _ in range(3):
                try:
                    campo = espera.until(EC.visibility_of_element_located((By.ID, id_campo)))
                    texto = campo.find_element(By.CSS_SELECTOR, ".select2-chosen").text.strip()
                    break
                except StaleElementReferenceException:
                    print("♻️ select2-chosen ficou stale — tentando novamente...")
                    time.sleep(0.5)
            else:
                print("❌ Não consegui ler o texto atual após 3 tentativas")
                return False

            # Se ainda não está selecionado o valor
            if texto.lower() != valor.lower():
                print("🔄 Valor diferente do atual — tentando selecionar nova opção...")

                try:
                    espera.until(EC.visibility_of_element_located((By.ID, "select2-drop")))
                    print("📋 Dropdown visível — buscando opções...")

                    lista = "#select2-drop ul.select2-results li.select2-result-selectable"

                    # Anti-stale na lista
                    for _ in range(3):
                        try:
                            opcoes = espera.until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, lista))
                            )
                            break
                        except StaleElementReferenceException:
                            print("♻️ Lista ficou stale — recarregando opções...")
                            time.sleep(0.5)
                    else:
                        print("❌ Falha ao carregar opções")
                        return False

                    clicou = False

                    # ========= MATCH EXATO =========
                    for op in opcoes:
                        try:
                            nome = op.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text.strip()

                            if nome.lower() == valor.lower():
                                op.click()
                                clicou = True
                                print(f"🎯 Match exato clicado: {nome}")
                                break
                        except StaleElementReferenceException:
                            print("♻️ Opção stale — recuperando...")
                            continue

                    # ========= MATCH PARCIAL SEGURO =========
                    if not clicou:
                        for op in opcoes:
                            try:
                                nome = op.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text.strip().lower()
                                alvo = valor.strip().lower()
                                # Ou trocar por
    #                             if similar(nome[:len(alvo)], alvo) > 0.7:  
                                    # op.click()
                                    # clicou = True
                                    # print(f"🔍 Match aproximado clicado: {nome}")
                                    # break

                                if nome.startswith(alvo): # Trocar para startswith
                                    op.click()
                                    clicou = True
                                    print(f"🔍 Match parcial seguro clicado: {nome}")
                                    break
                            except StaleElementReferenceException:
                                continue

                    if not clicou:
                        print(f"❌ Opção '{valor}' não encontrada na lista.")
                        return False

                except TimeoutException:
                    campo = espera.until(EC.visibility_of_element_located((By.ID, id_campo)))
                    texto_atual = campo.find_element(By.CSS_SELECTOR, ".select2-chosen").text.strip()

                    if texto_atual == valor:
                        print("✅ Valor preenchido automaticamente.")
                    else:
                        print(f"⚠️ Dropdown não apareceu e valor ainda não é '{valor}'.")
                        return False

            else:
                print(f"✅ '{valor}' já estava selecionado.")

        # Verificação final obrigatória
        time.sleep(0.3)
        campo = espera.until(EC.visibility_of_element_located((By.ID, id_campo)))
        final = campo.find_element(By.CSS_SELECTOR, ".select2-chosen").text.strip()

        if final.lower() != valor.lower():
            print(f"⚠️ ERRO FINAL: ficou '{final}', esperado '{valor}'")
            return False

        print("✅ Inserção concluída")
        time.sleep(0.7)
        return True

    except Exception as e:
        print(f"Não foi impossível inserir o campo {id_campo} devido {e}")
        return False


def login(driver, espera,action):
    driver.get(URL)

    campo_conta = espera.until(EC.presence_of_element_located((By.ID, "conta")))
    if(campo_conta.get_attribute("value") == "" or campo_conta is None):
        campo_conta.send_keys(USER)
    
    campo_senha = espera.until(EC.presence_of_element_located((By.NAME, "password")))
    campo_senha.send_keys(PASSWORD)
    
    btn_entrar =  espera.until(EC.visibility_of_element_located((By.CLASS_NAME, "btn_entrar")))
    action.move_to_element(btn_entrar).click().perform()

    try:
        popup = espera.until(EC.visibility_of_element_located((By.CLASS_NAME, "window_close")))
        popup.click()
    except TimeoutException:
        print("[INFO] Nenhuma noticia de boas-vindas encontrado.")




"""Botões de Interação"""

def click_btn_inserir(espera, action,campo):
    """Clica no botão de inserir dentro da tela."""
    try:
        btn_inserir = espera.until(
            EC.element_to_be_clickable((By.ID, f"{campo}_insert"))
        )
        action.move_to_element(btn_inserir).click().perform()
        print("✅ Botão inserir clicado.")
    except Exception as e:
        print(f"❌ Erro ao clicar em inserir: {e}")
        raise

def click_btn_limpar(espera, action,campo):
    """Clica no botão de limpar dentro da tela."""
    try:
        btn_limpar = espera.until(
            EC.element_to_be_clickable((By.ID, f"{campo}_clear"))
        )
        action.move_to_element(btn_limpar).click().perform()
        print("✅ Botão limpar clicado.")
    except Exception as e:
        print(f"❌ Erro ao clicar em limpar: {e}")
        raise

def click_btn_cancelar(espera, action,campo):
    """Clica no botão de cancelar dentro da tela."""
    try:
        btn_cancelar = espera.until(
            EC.element_to_be_clickable((By.ID, f"{campo}_cancel"))
        )
        action.move_to_element(btn_cancelar).click().perform()
        print("✅ Botão cancelar clicado.")
    except Exception as e:
        print(f"❌ Erro ao clicar em cancelar: {e}")
        raise

def click_btn_editar(espera, action,campo):
    """Clica no botão de editar dentro da tela."""
    try:
        btn_editar = espera.until(
            EC.element_to_be_clickable((By.ID, f"{campo}_edit"))
        )
        action.move_to_element(btn_editar).click().perform()
        print("✅ Botão editar clicado.")
    except Exception as e:
        print(f"❌ Erro ao clicar em editar: {e}")
        raise


def click_btn_pesquisar(espera, action,campo):
    """Clica no botão de pesquisar dentro da tela."""
    try:
        btn_pesquisar = espera.until(
            EC.element_to_be_clickable((By.ID, f"{campo}_search"))
        )
        action.move_to_element(btn_pesquisar).click().perform()
        print("✅ Botão pesquisar clicado.")
    except Exception as e:
        print(f"❌ Erro ao clicar em pesquisar: {e}")
        raise

def click_btn_confirmar(espera, action,campo):
    """Clica no botão de confirmar dentro da tela."""
    try:
        btn_confirmar = espera.until(
            EC.element_to_be_clickable((By.ID, f"{campo}_save"))
        )
        action.move_to_element(btn_confirmar).click().perform()
        print("✅ Botão confirmar clicado.")
    except Exception as e:
        print(f"❌ Erro ao clicar em confirmar: {e}")
        raise

"""Fim botões interaçã"""


def preencher_input_por_id(espera, action, id_campo, valor, somente_numeros=False):
    """Preenche um input pelo atributo name e confirma o valor informado."""
    valor = "" if valor is None else str(valor).strip()
    if somente_numeros:
        valor = "".join(caractere for caractere in valor if caractere.isdigit())

    if not valor:
        raise ValueError(f"O campo '{id_campo}' não possui um valor válido para preenchimento.")

    campo = espera.until(EC.element_to_be_clickable((By.ID, id_campo)))
    action.move_to_element(campo).click().perform()
    campo.clear()
    campo.send_keys(valor)

    valor_preenchido = campo.get_attribute("value")
    if valor_preenchido != valor:
        raise ValueError(
            f"Falha ao preencher '{id_campo}': recebido '{valor_preenchido}', esperado '{valor}'."
        )

    print(f"✅ Campo '{id_campo}' preenchido.")


def cadastrar_profissional(driver, espera, action, campo_formulario, profissional):
    """Abre o cadastro de profissional e preenche os dados disponíveis na planilha."""
    click_btn_cancelar(espera=espera, action=action, campo=campo_formulario)
    click_btn_inserir(espera=espera, action=action, campo=campo_formulario)

    if not inserir(
        espera=espera,
        action=action,
        driver=driver,
        campo=f"{campo_formulario}_numpessoa",
        valor=profissional["Nome"],
    ):
        raise ValueError(f"Não foi possível selecionar a pessoa '{profissional['Nome']}'.")
    preencher_input_por_id(
        espera=espera,
        action=action,
        id_campo="adm_profissional_numdocumentocons",
        valor=profissional["N Conselho"],
    )
    preencher_input_por_id(
        espera=espera,
        action=action,
        id_campo="adm_profissional_numcns",
        valor=profissional["CNS"],
        somente_numeros=True,
    )
    
    click_btn_confirmar(espera=espera, action=action, campo=campo_formulario)

def abrir_nova_aba(driver, url=None):
    aba_atual = driver.current_window_handle

    driver.switch_to.new_window("tab")

    aba_nova = driver.current_window_handle

    if url:
        driver.get(url)

    return aba_atual, aba_nova




def texto_resultado_tabela(driver):
    """Obtém o texto atual do corpo da tabela de resultados."""
    try:
        tabela = driver.find_element(By.ID, "adm_profissional_datatable")
        return tabela.find_element(By.TAG_NAME, "tbody").text.strip()
    except NoSuchElementException:
        return ""


def extrair_dados_tabela_profissional(espera, nome, resultado_anterior):
    """Aguarda a atualização da busca e confere se ela retornou o nome pesquisado."""
    try:
        espera.until(lambda driver: texto_resultado_tabela(driver) != resultado_anterior)
        table = espera.until(
            EC.visibility_of_element_located((By.ID, "adm_profissional_datatable"))
        )
        print("📄 Tabela encontrada! Extraindo dados...")

        tbody = table.find_element(By.TAG_NAME, "tbody")
        linhas = tbody.find_elements(By.TAG_NAME, "tr")

        nome_normalizado = normalizar(nome)
        for linha in linhas:
            texto_linha = linha.text.strip()
            if "Não foram encontrados resultados" in texto_linha:
                print("⚠ Sem cadastros.")
                return False
            if nome_normalizado in normalizar(texto_linha):
                print("✅ Profissional encontrado na tabela.")
                return True

        print("⚠ A busca não retornou o profissional pesquisado.")
        return False
    except TimeoutException as erro:
        raise RuntimeError("A tabela de resultado não foi atualizada após a busca.") from erro


def verificar_profissional(driver,espera,action,id_aba,profissional):
   driver.switch_to.window(id_aba)
   profissional_existe = False
   campo_formulario = "adm_profissional"
   nome = profissional["Nome"]

   print(f"\n🔎 Verificando: {nome}")
   click_btn_limpar(espera=espera, action=action, campo=campo_formulario)
   resultado_anterior = texto_resultado_tabela(driver)
   resultado_inserir = inserir(espera=espera,action=action,driver=driver,campo=f"{campo_formulario}_numpessoa",valor=nome)
   
   if resultado_inserir is False:
    # Nenhum resultado no select2 = pessoa não existe no sistema, então cadastra diretamente
    print(f"⚠️ '{nome}' não encontrado na busca. Iniciando cadastro diretamente...")
    click_btn_limpar(espera=espera, action=action, campo=campo_formulario)
    cadastrar_profissional(
        driver=driver,
        espera=espera,
        action=action,
        campo_formulario=campo_formulario,
        profissional=profissional,
    )
   else:
    # Resultado encontrado = pesquisa para confirmar se já está cadastrado
    click_btn_pesquisar(espera=espera,action=action,campo=campo_formulario)
    retorno_tabela = extrair_dados_tabela_profissional(
        espera=espera,
        nome=nome,
        resultado_anterior=resultado_anterior,
    )
    print(retorno_tabela)
    if retorno_tabela == False:
        print("Profissional não encontrado na tabela. Iniciando cadastro...")
        click_btn_cancelar(espera=espera, action=action, campo=campo_formulario)
        cadastrar_profissional(
            driver=driver,
            espera=espera,
            action=action,
            campo_formulario=campo_formulario,
            profissional=profissional,
        )
    else:
        print("Profissional já cadastrado.")

    

def main():
    driver = webdriver.Edge()
    espera = WebDriverWait(driver, WAIT_TIME)
    action = ActionChains(driver)

    try:
        profissionais = carregar_profissionais()
        login(driver, espera,action)
        for aba in abas:
            abrir_nova_aba(driver,aba)
            abas_id.append(driver.window_handles[-1])

        for indice, profissional in enumerate(profissionais, start=1):
            try:
                print(f"\n--- Registro {indice} de {len(profissionais)} ---")
                verificar_profissional(
                    driver=driver,
                    espera=espera,
                    action=action,
                    id_aba=abas_id[0],
                    profissional=profissional,
                )
            except Exception as e:
                print(f"[ERRO] Não foi possível processar {profissional['Nome']}: {e}")
                continue

            time.sleep(1)

        
    except Exception as e:
        print(f"[ERRO] Ocorreu um erro: {e}")
    
    finally:
        print("Fechando navegador...")
        driver.quit()


if __name__ == "__main__":
    main()
