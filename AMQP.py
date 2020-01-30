# -*- coding: utf-8 -*-
"""
Created on Wed Jan  8 15:08:43 2020

@author: Ori
"""
import pika
import json 
import numpy as np
import os.path
from scipy import stats as sps
from matplotlib import pyplot as plt
import smtplib
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.base import MIMEBase 
from email import encoders 
import datetime

def append2log(TitleWord):
    with open(pathLog, 'a') as file:
        file.write(TitleWord)
    return
def sendEmail(bodyTxt,imgPath):
    gmail_user = 'carmimeister@gmail.com'
    gmail_password = '918273645'
    to = ['Yair@eco-eng.co.il', 'Amit@eco-eng.co.il']
    msg = MIMEMultipart()    # instance of MIMEMultipart 
    msg['From'] = gmail_user # storing the senders email address       
    msg['To'] = ", ".join(to) # storing the receivers email address  
    msg['Subject'] = "Intel Anomaly Alert!" # storing the subject  
    body = 'Trend Detected - ' + bodyTxt # string to store the body of the mail 
    msg.attach(MIMEText(body, 'plain')) # attach the body with the msg instance 
    filename = 'test.png' 
    attachment = open(imgPath, "rb") # open the file to be sent  
    p = MIMEBase('application', 'octet-stream') # instance of MIMEBase and named as p 
    p.set_payload((attachment).read())  # To change the payload into encoded form 
    encoders.encode_base64(p)  # encode into base64 
    p.add_header('Content-Disposition', "attachment; filename= %s" % filename) 
    msg.attach(p) # attach the instance 'p' to instance 'msg' 
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
#        server.starttls()
        server.login(gmail_user, gmail_password)
        text = msg.as_string() 
        server.sendmail(gmail_user, to, text)
        server.close()
        print('email sent')
    except:
        print('Something went wrong...')
    return
def plotDataAndRegression(y,TitlePlt,TitleWord,toSave = 1):
    plt.figure() # plot the vector of numptsback and its regression line
    plt.plot(x, y, 'o', label='original data')
    plt.plot(x, intercept + slope*x, 'r', label='fitted line')
    plt.legend()
    plt.title(TitlePlt + ", " + TitleWord + " ,R-squared: %f" % r**2)
    if toSave:
        plt.savefig(os.path.join(pathImage))
    plt.close()
    sendEmail(TitleWord,pathImage) # call function to send email
    append2log(TitleWord) # append anomal event to log
    return
def linearModel(x):
    return slope*x+intercept
def predictCrossTime(threshold = 3):
    return (threshold - intercept)/slope
def msg_receive(ch, method, properties, body):
    ######## Parse incoming message #######
    # Sensor name and channel is in the routing key (split on .)
    # print("[%s]: %s " % (method.routing_key, data))
    global numPtsBack,x,dataTbls,counterTbls,freqs,slope,intercept,r,p,std_err,timestamp,timestmpsTbls
    
    if not method.routing_key in dataTbls:
        dataTbls[method.routing_key] = np.zeros((numPtsBack,26)) # will be a matrix, 26 cols (25 freqs + RMS) of the raw data from munisense (saved numptsback data points back)
        counterTbls[method.routing_key] = np.zeros((numPtsBack,26)) # will be a binary matrix, 26 cols (25 freqs + RMS) and numPtsBack. if trend detected - 1. otherwise (default) - 0.
        timestmpsTbls[method.routing_key] = [] # timestamps list
        thrshldsTbls[method.routing_key] = -1*np.ones(26) # an adaptive threshold for every frequency and rms (size 26). if -1, compare to updating threshold. if not -1, compare to the set threshold
    data = json.loads(body) # parse the body of message received as json object
    timestmpsTbls[method.routing_key].append(datetime.datetime.strptime(data["results"][0]['timestamp'][:-1], '%Y-%m-%dT%H:%M:%S.%f')) # get timestamp and append at end
    if len(timestmpsTbls[method.routing_key])>numPtsBack: # remove first if exceeds numptsback
        timestmpsTbls[method.routing_key].pop(0)    
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
    dataTbls[method.routing_key] = np.vstack((dataTbls[method.routing_key][1:,:],frqVals)) # append new frequencies to datatbls of this channel and remove first one
    ind = 0 # index running from 0-25 (frequencies and rms)
    for k in dataTbls[method.routing_key].T: # iterate the rows (25 freqs & RMS) of this channel  
        slope, intercept, r, p, std_err = sps.linregress(x, k) #  perform linear regression
        if thrshldsTbls[method.routing_key][ind]<0: # if hasn't crossed, continue to check against updated mean and std
            Cross = predictCrossTime(np.mean(k)+2*np.std(k)) # predict time it will cross threshold if continues in this trend (threshold set as mean of last half hour plus 3*std of last half hour)
        else: # if it crossed, threshold is not -1 and compare to last threshold (last mean+3std that it crossed)
            Cross = predictCrossTime(thrshldsTbls[method.routing_key][ind])
        if Cross>0 and Cross<360 and slope>0: # If it will cross in less than 1 hour (number of 10 seconds in an hour)
            counterTbls[method.routing_key][:,ind] = np.concatenate((counterTbls[method.routing_key][1:,ind],[1])) # append 1 to this channel, this frequency counter
            thrshldsTbls[method.routing_key][ind] =  np.mean(k)+2*np.std(k) # set threshold to this moment of anomaly
#            print("[%s]: %s, %s " % (method.routing_key, timestmpsTbls[method.routing_key][-1],freqs[ind]))
        else:
            counterTbls[method.routing_key][:,ind] = np.concatenate((counterTbls[method.routing_key][1:,ind],[0])) # append 0 to this channel, this frequency counter
            thrshldsTbls[method.routing_key][ind] =  -1 # reset so that threshold is updated next time it is anomal
        if np.sum(counterTbls[method.routing_key][-201:-1,ind]) >= 0.8*counterTbls[method.routing_key][-201:-1,ind].shape[0] and np.count_nonzero(k)>k.size/1.5: # if in the last N minutes it will cross in less than 1 hour in 80% of the times, alert
            if ind<len(freqs):
                txtstr = 'trend detected in freq %d [Hz]' %freqs[ind]
            else:
                txtstr = 'trend detected in RMS'
            plotDataAndRegression(k,txtstr,method.routing_key+timestmpsTbls[method.routing_key]) # call function to plot regression model and send email with details 
            counterTbls[method.routing_key][:,ind] = np.zeros(numPtsBack) # make zeros to not alert many times
            print(txtstr)
        ind+=1   


if __name__ == "__main__":
    if not 'dataTbls' in locals(): # if dont exist, make new dictionaries of data
        numPtsBack = 1080 # number of data points to track (6 10secs in min, 60 min in hr ---> 360 - 1 hour. max:8640)
        dataTbls = dict() # dictionary, keys are sensor names and values are spectrums
        counterTbls = dict()  # dictionary, keys are sensor names and values are binary counters if trend detected or not
        timestmpsTbls = dict() # dictionary, keys are sensor names and values are timestamps of corresponding line in dataTbls/counterTbls
        thrshldsTbls = dict() #dictionary, keys are sensor names and values are thresholds
        x = np.arange(numPtsBack) # last numPtsBack points
    pathLog = r'C:\Users\user\Desktop\Oric\ECO\intel - python\logfile.txt'#r'C:\Users\Ori\Desktop\Ori\ECO\intel - python\anomaly detection\logfile.txt'
    pathImage = r'C:\Users\user\Desktop\Oric\ECO\intel - python\test.png'#r"C:\Users\Ori\Desktop\Ori\ECO\intel - python\anomaly detection\test.png"
    if not os.path.exists(pathLog):
        open(pathLog, 'w').close()    
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