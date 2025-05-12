from utils.ai import AI
from bases.helper import BaseHelper
import schedule
from datetime import datetime
import os
from utils.getWeatherData import getTodayForecast
from utils.getRules import getValidRules
from utils.mailer import Mailer
from utils.pusher import Pusher

ai = AI()
mailer = Mailer()
pusher = Pusher()

class Weathery(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=False)

    def run(self):
        print("[Weathery] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        rules = getValidRules()
        
        for rule in rules:

            if rule.get("fields", {}).get("disableWeathery"):
                print(f"[Weathery] Rule {rule.get("fields", {}).get("ruleNumber")} triggered: {rule.get("fields", {}).get("comment")} - Weathery disabled")
                print("[Weathery] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                return
        
        weatherForecast = getTodayForecast()
        print(f"[Weathery] Obtained weather forecast")

        prompt = f"""Você é uma assistente que deve produzir um email com o resumo do tempo para hoje.
        Deve fazer uma descrição do tempo, temperatura, vento e humidade. Referece se vai ou não chover, entre outras informações que aches relevantes.
        Este email será enviado ao Afonso, por isso deve ser em português, e num tom amigável e descontraído. Deves escrever o email em teu nome, 'Weathery'.
        Deves tratar o Afonso por 'tu' e não por 'você'. O email deve ser escrito em português de Portugal, NÃO português do brasil.
        Este email será enviado no início do dia, pelas 8.40h da manhã, por isso deve ser um email curto e direto ao ponto.	
        O email deve ser médio-curto, mas informativo. 
        Também podes incluir recomendações de vestuário, como 'levar um casaco' ou 'não esquecer o guarda-chuva'.
        Deves escrever 'espero' com letra 'e' maiscula se for inicio de frase.
        Não deves usar markdown, nem HTML, nem emojis, nem nada disso. Apenas texto puro.
        Não termines o email com 'Espero que isso te ajude', ou algo do género. Não termines o email com uma pergunta.
        Faz um email amigável, mas não muito formal. Não uses palavras como 'caro' ou 'atenciosamente'. Usa parágrafos grandes, mas com espaçamentos.
        Termina o teu email com 'Cumprimentos, \nWeathery'.
        O vento está em km/h.Aqui estão as informações 'raw' obtidas pelo OpenWeatherMap: \n\n{weatherForecast}"""
        aiResponseText = ai.prompt(prompt)
        aiResponseSubject = ai.prompt(f"Qual seria o assunto do email? Diz apenas, e apenas um, e apenas 1, titulo sobre a previsão do tempo para HOJE. 'hoje' escreve-se com letra minuscula. Diz apenas o titulo diretamente. NÃO digas coisas como 'Aqui está o titulo' nem nada parecido.Aqui está o conteúdo do email: {aiResponseText}")
        
        print(f"[Weathery] Got AI responses. Emailing..")
        mail = mailer.send_email(
            name="Weathery",
            subject=aiResponseSubject,
            text=aiResponseText,
            to=os.environ.get("TO_EMAIL"),
        )
        print(f"[Weathery] Email sent. ID: {mail["id"]}")

        promptPusher = f"""Escreve uma notificação para o Afonso, com o resumo do tempo para hoje.
        Deve fazer uma descrição do tempo, temperatura, vento e humidade. Refere-se se vai ou não chover, entre outras informações que aches relevantes.
        Esta será uma notificação, por isso deve ser curta e direta ao ponto.
        Não deves usar markdown, nem HTML, nem emojis, nem nada disso. Apenas texto puro com acentos e simbolos.
        O vento está em km/h.
        Não cumprimentes o Afonso, e tenta com que a tua notificação fique com cerca de 30 palavras. Refere temperaturas, vento, humidade, e se vai chover ou não.
        Aqui estão os dados 'raw' obtidos pelo OpenWeatherMap: \n\n{weatherForecast}"""

        pusher.bulkPush(
            title="Previsão do tempo para hoje",
            body=ai.prompt(promptPusher),
            data={
                "helper": "weathery",
            },
        )
        print(f"[Weathery] Pushed notification")
        print("[Weathery] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
        timeSuffix = "AM" if os.environ.get("AM_PM_ENABLED") == "true" else ""
        print(f"08:40{timeSuffix} - {os.environ.get('TIMEZONE')}")
        schedule.every().day.at(f"08:40{timeSuffix}", os.environ.get("TIMEZONE")).do(self.run)