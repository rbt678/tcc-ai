import openai
import os
from docx import Document
from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from chromadb.config import Settings
from spacy import load


def ler_arquivo(caminho:str):
    try:
        with open(caminho, "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"O arquivo '{caminho}' não foi encontrado.")
        return ""
    
def separar_sentencas(textos):
    nlp = load("pt_core_news_lg")
    docs = [nlp(t) for t in textos]
    sentencas = []
    for doc in docs:
        tokens = []
        for token in doc:
            if not token.is_stop and not token.is_punct:
                tokens.append(token.lemma_)
        sentencas.append(" ".join(tokens))
    return sentencas
    
def preprocessar_docx(doc, tradutor=None):
        documento = '\n'.join(parag.text for parag in doc.paragraphs)
        textos = documento.split("####")
        textos = separar_sentencas(textos)

        if tradutor:
            textos_traduzidos = []
            for doc in textos:
                textos_traduzidos.append(tradutor(doc)["response"]["choices"][0]["message"]["content"])
            
            return textos_traduzidos
        else:
            return textos
    

class ChromaDBManager:
    def __init__(self, path:str, collection_name:str, ef):
        self.client = PersistentClient(path=path, settings=Settings(allow_reset=True))
        self.collection = self.client.get_or_create_collection(name=collection_name, embedding_function=ef)
    
    def get_max_id(self):
        ids_str = self.collection.get()["ids"]
        
        return max([int(num) for num in ids_str]) + 1 if ids_str else 0

    def ler_todos_docxs(self, path:str, tradutor=None):
        sentences = []

        for filename in os.listdir(path):
            if filename.endswith(".docx"):
                doc = Document(os.path.join(path, filename))
                preprocess = preprocessar_docx(doc, tradutor)
                sentences.extend(preprocess)

        if sentences==[]:
            print("Não há arquivos .docx na pasta")
            return False
        
        sentences_ids = [str(i) for i in range(len(sentences))]
        self.collection.add(documents=sentences, ids=sentences_ids)

    def query(self, query_texts:str, n_results:int = 5):
        return self.collection.query(query_texts=query_texts, n_results=n_results)


class Assistant:
    def __init__(self, nome_da_empresa:str, api_key_path:str = "./credentials/apiKey", pasta_database:str = "dataBase", colecao:str = "colecao1"):
        self.nome_da_empresa = nome_da_empresa
        self.pasta_database = pasta_database
        self.colecao = colecao
        self.openai_api_key = ler_arquivo(api_key_path)
        self.historico_atual = []
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(api_key=self.openai_api_key, model_name="text-embedding-ada-002")
        self.db_manager = ChromaDBManager(path=pasta_database, collection_name=colecao, ef=self.openai_ef)

    def enviar_gpt(self, system_role:str, database:str, quest:str, collection_response):
        openai.api_key = self.openai_api_key

        historico = self.historico_atual[-20:]
        historico_string = ""
        for dict in historico:
            if dict["role"] == "user":
                historico_string += f"User: {dict['content']}\n"
            if dict["role"] == "assistant":
                historico_string += f"Assistant: {dict['content']}\n"

        historico_string = separar_sentencas([historico_string])

        prompt = [
            {"role": "system", "content": system_role},
            {"role": "user", "content": f"'database':\n###\n{database}\n###\n\n 'historico':\n###\n{historico_string}\n###\n\n Pergunta do usuário: {quest}\n"}
        ]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt,
            temperature=0.6,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0.1
        )
        
        return {'response': response, 'prompt': prompt, 'collection_response': collection_response}
    
    def gpt_tradutor_en(self, pergunta:str):
        openai.api_key = self.openai_api_key
        prompt=[{"role": "system","content": "Por favor traduza para o inglês tudo que o usuário enviar. E se o usuário enviar algo em inglês repita exatamente o que ele disse."},
                {"role": "user","content": "I like guarana, and you?"},
                {"role": "assistant","content": "I like guarana, and you?"},
                {"role": "user","content": "O que é ChromaDB?"},
                {"role": "assistant","content": "What is ChromaDB?"},
                {"role": "user","content": pergunta}]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt,
            temperature=0.5,
            max_tokens=100,
            top_p=1,
            frequency_penalty=1,
            presence_penalty=0
        )

        return {'response': response, 'prompt': prompt}

    def query(self, pergunta:str, traduzir:bool=False):
        if traduzir:
            pergunta_eng = self.gpt_tradutor_en(pergunta=pergunta)["response"]["choices"][0]["message"]["content"]
            
        collection_response = self.db_manager.query(query_texts= pergunta if not traduzir else pergunta_eng, n_results=5)
        collection_database = collection_response["documents"][0]
        system_role = (
            f"Você é um assistente inteligente, educado e dedicado da {self.nome_da_empresa}, que responde perguntas do usuário. "
            "Você possui 'dataBase' para buscar informações e 'historico' para lembrar da conversa com o usuário. "
            "Se você não souber como responder o usuário, responda com: 'Infelizmente essa informação não está na minha base de dados.' "
            "Você deve responder usando um máximo de 150 tokens. "
            "Agora, com base nos seguintes dados, responda a pergunta do usuário: "
        )

        return self.enviar_gpt(system_role=system_role, database=collection_database, quest=pergunta, collection_response=collection_response)
    
    def atualizar_documentos(self, traduzir:bool = False):
        print("\nResetando cliente...")
        self.db_manager.client.reset()
        print("\nCliente resetado.")
        
        print("\nAtualizando cliente...")
        self.db_manager = ChromaDBManager(path=self.pasta_database, collection_name=self.colecao, ef=self.openai_ef)
        print("\nCliente atualizado.")
        
        print("\nLendo todos os documentos...")
        self.db_manager.ler_todos_docxs("documentos", self.gpt_tradutor_en if traduzir else None)
        print("\nDocumentos atualizados.")


    def salvar_historico_atual(self, historico):
        self.historico_atual.extend(historico)
        

if __name__=="__main__":
    # assistente = Assistant(nome_da_empresa="Hakuna Empreendimentos")
    # print(assistente.atualizar_documentos())
    # print(assistente.db_manager.client.list_collections())
    # print(assistente.db_manager.collection.get())
    # print(assistente.query("O que é ChromaDB?"))
    pass