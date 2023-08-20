from flask import Flask, request, jsonify, render_template
import Assistant

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('chat.html')


@app.route('/ask', methods=["POST"])
def ask():
    data = request.json
    user_message = data["message"]
    process_return = Assistant.processar_pergunta(user_message)


    return jsonify({"response": process_return["response"]["choices"][0]["message"]["content"], 
                    "prompt": process_return["prompt"][1]["content"], 
                    "collection_response": str(process_return['collection_response'])})

if __name__ == '__main__':
    app.run(debug=True)
