from flask import Flask, request, jsonify, render_template
import Assistant


app = Flask(__name__)
assistant = Assistant.Assistant(nome_da_empresa="Clínica Dente Saudável")

@app.route('/')
def index():
    return render_template('chat.html')


@app.route('/ask', methods=["POST"])
def ask():
    data = request.json
    user_message = data["message"]
    if user_message == "reset_docs":
        assistant.atualizar_documentos()
        return jsonify({"response": "Documentos resetados"})
    process_return = assistant.query(pergunta=user_message)
    respostaGPT = process_return["response"]["choices"][0]["message"]["content"]
    promptEnviado = str(process_return["prompt"])
    respostaDaColecao = str(process_return['collection_response'])

    dict_historico = [
        {"role": "user","content": user_message},
        {"role": "assistant","content": respostaGPT}
    ]
    assistant.salvar_historico_atual(dict_historico)


    return jsonify({"response": respostaGPT, "prompt": promptEnviado, "collection_response": respostaDaColecao})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    #app.run(debug=True)
