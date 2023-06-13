import smtplib
from smtplib import SMTP_SSL
from email.message import EmailMessage
def sendmail(to,subject,body):
    server=smtplib.SMTP_SSL('smtp.gmail.com',465)
    server.login('swarnabhargavimarneni@gmail.com','ctwgrqtkqobvuhae')
    msg=EmailMessage()
    msg['From']='swarnabhargavimarneni@gmail.com'
    msg['subject']=subject
    msg['To']='swarnabhargavim@gmail.com'
    msg.set_content(body)
    server.send_message(msg)
    server.quit()