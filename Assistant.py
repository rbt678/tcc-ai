import openai
from re import sub
from docx import Document
from spacy import load
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

class ChromaDBManager:
    def __init__(self, path:str, collection_name:str, embedding_function="all-MiniLM-L6-v2"):
        """
        Inicializa a classe ChromaDBManager para gerenciar uma coleção no ChromaDB.
        
        :param path: Caminho para o banco de dados.
        :param collection_name: Nome da coleção no banco de dados.
        :param embedding_function: Nome da função de embedding. Padrão é "all-MiniLM-L6-v2".
        """

        # Inicialização do modelo de embedding se for o padrão
        if embedding_function=="all-MiniLM-L6-v2":
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            ef = self.__funcao_embbeding
        else: return False

        # Conexão com o banco de dados e obtenção ou criação da coleção
        self.client = PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(name=collection_name, embedding_function=ef)

    def __funcao_embbeding(self, textos:list[str]) -> list[str]:
        """
        Calcula os embeddings para uma lista de textos.
        
        :param textos: Lista de textos para os quais os embeddings são calculados.
        :return: Lista de embeddings.
        """
        return self.model.encode(sentences=textos).tolist()

    def get_max_id(self) -> int:
        """
        Obtém o maior ID presente na coleção.
        
        :return: O próximo ID disponível na coleção.
        """
        ids_str = self.collection.get()["ids"]
        return max([int(num) for num in ids_str]) + 1 if ids_str else 0
    
    def add_na_collection(self, list_ids, list_texts):
        """
        Adiciona documentos na coleção.
        
        :param list_ids: Lista de IDs.
        :param list_texts: Lista de textos/documentos.
        """
        self.collection.add(ids=list_ids, documents=list_texts)

    def query(self, query_texts:str, n_results:int = 5) -> dict:
        """
        Realiza uma consulta na coleção.
        
        :param query_texts: Texto da consulta.
        :param n_results: Número de resultados a serem retornados. Padrão é 5.
        :return: Resultados da consulta.
        """
        return self.collection.query(query_texts=query_texts, n_results=n_results)


class Assistant:
    def __init__(self, db_manager: ChromaDBManager, api_key_path:str):
        """
        Inicializa a classe Assistant para interagir com o GPT-3 usando um banco de dados.

        :param caminho_docx: Caminho para o arquivo DOCX.
        :param db_manager: Instância da classe ChromaDBManager.
        :param api_key_path: Caminho para o arquivo que contém a chave da API OpenAI.
        """
        #self.caminho_docx = caminho_docx
        self.db_manager = db_manager
        self.openai_api_key = self._ler_arquivo(api_key_path)

    @staticmethod
    def _ler_arquivo(caminho:str) -> str:
        """
        Lê o conteúdo de um arquivo.
        
        :param caminho: Caminho do arquivo.
        :return: Conteúdo do arquivo.
        """
        try:
            with open(caminho, "r") as file:
                return file.read().strip()
        except FileNotFoundError:
            print(f"O arquivo '{caminho}' não foi encontrado.")
            return ""

    @staticmethod
    def _extrair_texto_docx(caminho:str) -> str:
        """
        Extrai o texto de um arquivo DOCX.
        
        :param caminho: Caminho do arquivo DOCX.
        :return: Texto extraído do arquivo.
        """
        doc = Document(caminho)
        return '\n'.join(parag.text for parag in doc.paragraphs)

    def preprocess(self, texto:str) -> list[str]:
        """
        Pré-processa o texto, removendo caracteres especiais e dividindo em sentenças.

        :param texto: Texto a ser pré-processado.
        :return: Lista de sentenças.
        """
        clean_text = sub(r'\W+', ' ', texto).lower()
        nlp = load('en_core_web_sm')
        doc = nlp(clean_text)
        return [p.text for p in doc.sents]

    def enviar_gpt(self, system_role:str, database:str, quest:str, collection_response) -> dict:
        """
        Interage com o modelo GPT-3 usando a chave da API fornecida.

        :param system_role: Mensagem inicial para o modelo.
        :param database: Base de dados para a consulta.
        :param quest: Pergunta do usuário.
        :return: Resposta do modelo GPT-3.
        """

        openai.api_key = self.openai_api_key
        prompt = [
            {"role": "system", "content": system_role},
            {"role": "user", "content": f"'database':\n###\n{database}\n###\n\nPergunta: {quest}\n"}
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
    
    def gpt_tradutor(self, pergunta:str):

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
        """
        Realiza uma consulta na base de dados e depois consulta o modelo GPT-3.

        :param pergunta: Pergunta do usuário.
        :return: Resposta do modelo GPT-3.
        """

        pergunta_eng = self.gpt_tradutor(pergunta=pergunta)["response"]["choices"][0]["message"]["content"]
        collection_response = self.db_manager.query(query_texts=pergunta_eng, n_results=5)
        collection_database = collection_response["documents"][0]
        system_role = (
            "You are an intelligent, polite, and dedicated assistant from Hakunamatata company. "
            "If you can't find the answer from the given 'database', "
            "please reply with: 'Infelizmente essa informação não está na minha base de dados.'. "
            "You have to respond using a maximum of 150 tokens. "
            "Now, based on the following database..."
        )

        return self.enviar_gpt(system_role=system_role, database=collection_database, quest=pergunta, collection_response=collection_response)

    def add_document_into_collection(self, caminho_docx):
        """
        Adiciona um documento no formato DOCX à coleção.

        :param caminho_docx: Caminho para o arquivo DOCX a ser adicionado.
        """
        clean_text = self.preprocess(self._extrair_texto_docx(caminho_docx))
        id_atual = self.db_manager.get_max_id() + 1
        list_ids = list(range(id_atual, id_atual+len(clean_text)))
        list_ids_str = [str(num) for num in list_ids]
        self.db_manager.add_na_collection(list_ids=list_ids_str, list_texts=clean_text)


def processar_pergunta(pergunta):
    db_manager = ChromaDBManager("baseDados", "colecao5")
    assistant = Assistant(db_manager=db_manager, api_key_path="credentials/apiKey")
    query_return = assistant.query(pergunta)

    return query_return


if __name__=="__main__":
    db_manager = ChromaDBManager("baseDados", "colecao5")
    assistant = Assistant("Documentacao_ChromaDB.docx", db_manager, "credentials/apiKey")
    #assistant.add_document_into_collection("Documentacao_ChromaDB.docx")