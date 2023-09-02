import discord
import Assistant

intents = discord.Intents.default()
intents.message_content = True
assistente = Assistant.Assistant()

client = discord.Client(intents=intents)
pessoas_ativas = []

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message:discord.Message):
    if message.author == client.user:
        return
    
    if message.author.id in pessoas_ativas:
        if message.content == "GPT!Parar":
            pessoas_ativas.remove(message.author.id)
            await message.channel.send("Conversa com o GPT Desativado!")

            return

        #envia a mensagem para o assistente
        process_return = assistente.query(pergunta=message.content)

        #envia a resposta do assistente para o discord
        await message.channel.send(process_return["response"]["choices"][0]["message"]["content"])

        #salva o historico
        dict_historico = [
            {"role": "user","content": message.content},
            {"role": "assistant","content": process_return["response"]["choices"][0]["message"]["content"]}
        ]
        assistente.salvar_historico_atual(dict_historico)

        #printar o prompt, a resposta da coleção e a mensagem que o usuário enviou
        print(f"Mensagem do usuário: {message.content}\n\n")
        print(f"Prompt: {process_return['prompt']}\n\n")
        print(f"Collection Response: {process_return['collection_response']}\n\n")

        return

    elif message.content == "GPT!":
        pessoas_ativas.append(message.author.id)
        await message.channel.send("Conversa com o GPT Ativado!")
        
        return


    
client.run(assistente.ler_arquivo("credentials/DISCORD_TOKEN"))