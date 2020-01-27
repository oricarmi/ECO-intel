# -*- coding: utf-8 -*-
"""
Created on Wed Jan  8 15:08:43 2020

@author: Ori
"""
import pika
import json 
import numpy as np
import win32api
import os.path
from scipy import stats as sps
from matplotlib import pyplot as plt
import smtplib

def plotDataAndRegression(y,TitlePlt,TitleWord,toSave = 1):
    plt.figure()
    plt.plot(x, y, 'o', label='original data')
    plt.plot(x, intercept + slope*x, 'r', label='fitted line')
    plt.legend()
    plt.title(TitlePlt + " ,R-squared: %f" % r**2)
    if toSave:
        plt.savefig(os.path.join(r'C:\Users\user\Desktop\Oric\ECO\intel - python',TitleWord + '.png'))
    plt.close()
    return
def linearModel(x):
    return slope*x+intercept
def predictCrossTime(threshold = 3):
    return (threshold - intercept)/slope
def sendEmail():
    gmail_user = 'carmimeister@gmail.com'
    gmail_password = '918273645'
    sent_from = gmail_user
    to = ['Yair@eco-eng.co.il', 'Amit@eco-eng.co.il']
    subject = 'Test from python'
    body = 'Hey, Test'
    
    email_text = """\
    From: %s
    To: %s
    Subject: %s
    
    %s
    """ % (sent_from, ", ".join(to), subject, body)
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(sent_from, to, email_text)
        server.close()
        print('email sent')
    except:
        print('Something went wrong...')

def msg_receive(ch, method, properties, body):
    ######## Parse incoming message #######
    # Sensor name and channel is in the routing key (split on .)
    # print("[%s]: %s " % (method.routing_key, data))
    global x,dataTbls,counterTbls,freqs,slope,intercept,r,p,std_err,timestamp,timestmpsTbls
    
    if not method.routing_key in dataTbls:
        dataTbls[method.routing_key] = np.zeros((200,26))
        counterTbls[method.routing_key] = np.zeros((200,26))
        timestmpsTbls[method.routing_key] = []
    data = json.loads(body)
    timestmpsTbls[method.routing_key] = data["results"][0]['timestamp'] # get timestamp
    spectrum = data["results"][0]['values'] # get freq values
    freqs = [] # frequencies list
    frqVals = [] # frequencies values list
    for f in spectrum.keys(): # iterate values and make one vector
        try:
            if float(f[0:-2])<=250:
                freqs.append(float(f[0:-2]))
                frqVals.append(float(spectrum[f])) 
        except:
            continue
    frqVals = np.asarray(frqVals) # make list to numpy array
    frqVals = np.concatenate((frqVals,[np.sqrt(np.mean(frqVals**2))])) # concatenate rms
    dataTbls[method.routing_key] = np.vstack((frqVals,dataTbls[method.routing_key][0:-1,:])) # concatenate new frequencies to already existing
    ind = 0
    for k in dataTbls[method.routing_key].T: # iterate the rows of y and perform linear regression
        slope, intercept, r, p, std_err = sps.linregress(x, k)
        Cross = predictCrossTime(np.mean(k)+3*np.std(k)) # predict time it will cross threshold if continues in this trend
        if Cross>0 and Cross<360: # If it will cross in less than 1 hour (number of 10 seconds in an hour)
            counterTbls[method.routing_key][:,ind] = np.concatenate(([1], counterTbls[method.routing_key][0:-1,ind])) # append 1 to counter
        else:
            counterTbls[method.routing_key][:,ind] = np.concatenate(([0], counterTbls[method.routing_key][0:-1,ind])) # append 0 to counter
        if np.sum(counterTbls[method.routing_key][:,ind]) >= 0.8*counterTbls[method.routing_key].shape[0]: # if in the last N minutes it will cross in less than 1 hour in 80% of the times, alert
            if ind<len(freqs):
                txtstr = 'trend detected in freq %d [Hz]' %freqs[ind]
            else:
                txtstr = 'trend detected in RMS'
            plotDataAndRegression(k,txtstr,method.routing_key+timestmpsTbls[method.routing_key])
#            win32api.MessageBox(0,txtstr,'alert')
        ind+=1   

if __name__ == "__main__":
    counter = np.zeros((30,20),dtype = int) # first 19 are freqs, 20 is energy (30 rows, last 5 minutes
    dataTbls = dict() # dictionary, keys are sensor names and values are spectrums
    counterTbls = dict()  # dictionary, keys are sensor names and values are binary counters if trend detected or not
    timestmpsTbls = dict() # dictionary, keys are sensor names and values are timestamps of corresponding line in dataTbls/counterTbls
    x = np.arange(200) # last 200 points
    # Setup AMQP Connection
    parameters = pika.URLParameters('amqps://eco-monitoring:p4_HVv%Mb6j&)P@amqp-ext.munisense.net:5671/eco-monitoring')

    print("Connecting AMQP..")
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    print("AMQP Connected!")

    print('Starting consume...')
    channel.basic_consume(queue="composite_results_pretty_v1", on_message_callback=msg_receive, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()