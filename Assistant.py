import openai
import os
from docx import Document
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings


def ler_arquivo(caminho:str) -> str:
    try:
        with open(caminho, "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"O arquivo '{caminho}' não foi encontrado.")
        return ""
    
def preprocessar_docx(doc, tradutor=None) -> list[str]:
        documento = '\n'.join(parag.text for parag in doc.paragraphs)
        textos = documento.split("####")

        if tradutor:
            textos_traduzidos = []
            for doc in textos:
                textos_traduzidos.append(tradutor(doc)["response"]["choices"][0]["message"]["content"])
            
            return textos_traduzidos
        else:
            return textos
    

class ChromaDBManager:
    def __init__(self, path:str, collection_name:str, embedding_function="all-MiniLM-L6-v2"):
        if embedding_function == "all-MiniLM-L6-v2":
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            ef = self.__funcao_embbeding
        else: 
            return

        self.client = PersistentClient(path=path, settings=Settings(allow_reset=True))
        self.collection = self.client.get_or_create_collection(name=collection_name, embedding_function=ef)

    def __funcao_embbeding(self, textos:list[str]) -> list[str]:
        return self.model.encode(sentences=textos).tolist()
    
    def get_max_id(self) -> int:
        ids_str = self.collection.get()["ids"]
        
        return max([int(num) for num in ids_str]) + 1 if ids_str else 0

    def ler_todos_docxs(self, path:str, tradutor=None) -> list[str]:
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

    def query(self, query_texts:str, n_results:int = 5) -> dict:
        return self.collection.query(query_texts=query_texts, n_results=n_results)


class Assistant:
    def __init__(self, api_key_path:str = "credentials/apiKey", pasta_database:str = "dataBase", colecao:str = "colecao1"):
        self.pasta_database = pasta_database
        self.colecao = colecao
        self.db_manager = ChromaDBManager(pasta_database, colecao)
        self.openai_api_key = ler_arquivo(api_key_path)
        self.historico_atual = []

    def enviar_gpt(self, system_role:str, database:str, quest:str, collection_response) -> dict:
        openai.api_key = self.openai_api_key

        historico = self.historico_atual[-20:]
        historico_string = ""
        for dict in historico:
            if dict["role"] == "user":
                historico_string += f"User: {dict['content']}\n"
            if dict["role"] == "assistant":
                historico_string += f"Assistant: {dict['content']}\n"

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
    
    def gpt_tradutor_en(self, pergunta:str) -> dict:
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

    def query(self, pergunta:str) -> dict:
        pergunta_eng = self.gpt_tradutor_en(pergunta=pergunta)["response"]["choices"][0]["message"]["content"]
        collection_response = self.db_manager.query(query_texts=pergunta_eng, n_results=5)
        collection_database = collection_response["documents"][0]
        system_role = (
            "Você é um assistente inteligente, educado e dedicado da empresa Hakunamatata, que responde perguntas do usuário. "
            "Você possui 'dataBase' para buscar informações e 'historico' para lembrar a conversa com o usuário. "
            "Se você não souber como responder o usuário, responda com: 'Infelizmente essa informação não está na minha base de dados.' "
            "Você deve responder usando um máximo de 150 tokens. "
            "Agora, com base nos seguintes dados, responda a pergunta do usuário: "
        )

        return self.enviar_gpt(system_role=system_role, database=collection_database, quest=pergunta, collection_response=collection_response)
    
    def atualizar_documentos(self, traduzir:bool = False):
        self.db_manager.client.reset()
        self.db_manager = ChromaDBManager(self.pasta_database, self.colecao)
        self.db_manager.ler_todos_docxs("documentos", self.gpt_tradutor_en if traduzir else None)


    def salvar_historico_atual(self, historico):
        self.historico_atual.extend(historico)
        

if __name__=="__main__":
    assistente = Assistant()
    print(assistente.atualizar_documentos())
    #print(assistente.db_manager.client.list_collections())
    #print(assistente.query("O que é ChromaDB?"))
    pass