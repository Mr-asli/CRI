"""Best-effort, rate-limited operational notifications (Telegram and SMTP)."""
from __future__ import annotations
import os, smtplib, time, urllib.request, urllib.parse
from email.message import EmailMessage
_last_sent={}
def notify(subject: str, body: str, cooldown: int = 900) -> dict:
    now=time.time(); key=subject
    if now-_last_sent.get(key,0)<cooldown: return {'sent':False,'reason':'cooldown'}
    sent=[]; errors=[]
    token=os.getenv('TELEGRAM_BOT_TOKEN',''); chat=os.getenv('TELEGRAM_CHAT_ID','')
    if token and chat:
        data=urllib.parse.urlencode({'chat_id':chat,'text':f'{subject}\n{body}'}).encode()
        try:
            req=urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',data=data,method='POST')
            with urllib.request.urlopen(req,timeout=5) as response:
                if response.status == 200: sent.append('telegram')
        except Exception as exc: errors.append('telegram:'+type(exc).__name__)
    host=os.getenv('SMTP_HOST',''); recipient=os.getenv('ALERT_EMAIL_TO',''); sender=os.getenv('ALERT_EMAIL_FROM','')
    if host and recipient and sender:
        message=EmailMessage(); message['Subject']=subject; message['From']=sender; message['To']=recipient; message.set_content(body)
        try:
            with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=5) as smtp:
                if os.getenv('SMTP_STARTTLS','true').lower()=='true': smtp.starttls()
                if os.getenv('SMTP_USERNAME'): smtp.login(os.getenv('SMTP_USERNAME'),os.getenv('SMTP_PASSWORD',''))
                smtp.send_message(message); sent.append('email')
        except Exception as exc: errors.append('email:'+type(exc).__name__)
    if sent: _last_sent[key]=now
    return {'sent':bool(sent),'channels':sent,'errors':errors}
