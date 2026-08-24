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


# ======== CONFIGURAÇÕES ========
load_dotenv()

USER = os.getenv("LOGIN", "")
PASSWORD = os.getenv("PASSWORD", "")

abas = ["https://juizdefora-mg-tst.vivver.com/adm/profissional"]
abas_id = []



URL = "https://juizdefora-mg-tst.vivver.com/login"

WAIT_TIME = 10

# ======== FUNÇÕES AUXILIARES ========

def normalizar(texto):
    texto = texto.upper().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto

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

"""Fim botões interaçã"""

def abrir_nova_aba(driver, url=None):
    aba_atual = driver.current_window_handle

    driver.switch_to.new_window("tab")

    aba_nova = driver.current_window_handle

    if url:
        driver.get(url)

    return aba_atual, aba_nova




def extrair_dados_tabela_profissional(espera):
    """Tenta extrair os nomes dos médicos da tabela.
       Se não existir tabela, extrai do card select2."""
    
    time.sleep(0.7)
    valores = set()
    try:
        table = espera.until(
            EC.visibility_of_element_located((By.ID, "adm_profissional_datatable"))
        )
        print("📄 Tabela encontrada! Extraindo dados...")

        tbody = table.find_element(By.TAG_NAME, "tbody")
        linhas = tbody.find_elements(By.TAG_NAME, "tr")

        for linha in linhas:
            colunas = linha.find_elements(By.TAG_NAME, "td")

            # Linha vazia
            if len(colunas) == 1 and "Não foram encontrados resultados" in colunas[0].text:
                print("⚠ Sem cadastros.")
                return False
                break

            # Linha invalida
            if len(colunas) <= 9:
                print("⚠ Linha ignorada (menos de 10 colunas)")
                continue

            return True
    except Exception:
        print("⚠ Nenhuma tabela encontrada. Extraindo do card...")
        nome_card = espera.until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#s2id_esf_area_profissional_id_profissional .select2-chosen"))
        ).text

        valores.add(normalizar(nome_card))

        print(f"✅ Apenas um registro encontrado: {nome_card}")

    return True


def verificar_profissional(driver,espera,action,id_aba):
   driver.switch_to.window(id_aba)
   profissional_existe = False
   campo_formulario = "adm_profissional"

   inserir(espera=espera,action=action,driver=driver,campo=f"{campo_formulario}_numpessoa",valor="ADALBERTO MARIA DA SILVA")
   click_btn_pesquisar(espera=espera,action=action,campo=campo_formulario)
   retorno_tabela = extrair_dados_tabela_profissional(espera=espera)
   print(retorno_tabela)
   if retorno_tabela == False:
    print("caminho triste")
    """Caminho que não existe profissional cadastrado"""
    element = driver.find_element(By.TAG_NAME, "body")
    element.send_keys(Keys.ESCAPE)
   else:
    """Caminho que existe profissional cadastrado"""
    print("caminho feliz")
    time.sleep(0.5)
    click_btn_editar(espera=espera,action=action,campo=campo_formulario)
    time.sleep(0.5)

    

def main():
    driver = webdriver.Edge()
    espera = WebDriverWait(driver, WAIT_TIME)
    action = ActionChains(driver)

    try:
        login(driver, espera,action)
        for aba in abas:
            abrir_nova_aba(driver,aba)
            abas_id.append(driver.window_handles[-1])
        verificar_profissional(driver=driver,espera=espera,action=action,id_aba=abas_id[0])
        time.sleep(1)

        
    except Exception as e:
        print(f"[ERRO] Ocorreu um erro: {e}")
    
    finally:
        print("Fechando navegador...")
        driver.quit()



if __name__ == "__main__":
    main()