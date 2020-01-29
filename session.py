# -*- coding: utf-8 -*-
"""
Created on Tue Jan 28 15:21:18 2020

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
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.base import MIMEBase 
from email import encoders 

class session:
    def __init__(self):
        self.dataTbls = dict() # dictionary, keys are sensor names and values are spectrums
        self.counterTbls = dict()  # dictionary, keys are sensor names and values are binary counters if trend detected or not
        self.timestmpsTbls = dict() # dictionary, keys are sensor names and values are timestamps of corresponding line in dataTbls/counterTbls
        self.thrshldsTbls = dict() #dictionary, keys are sensor names and values are thresholds
        self.x = np.arange(200) # last 200 points

        
    def startAMQP(self):# Setup AMQP Connection
        parameters = pika.URLParameters('amqps://eco-monitoring:p4_HVv%Mb6j&)P@amqp-ext.munisense.net:5671/eco-monitoring')
        print("Connecting AMQP..")
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        print("AMQP Connected!")
        print('Starting consume...')
        channel.basic_consume(queue="composite_results_pretty_v1", on_message_callback=self.msg_receive, auto_ack=True)
        print(' [*] Waiting for messages. To exit press CTRL+C')
        channel.start_consuming()
        
        
    def msg_receive(self,ch, method, properties, body):
        if not method.routing_key in self.dataTbls:
            self.dataTbls[method.routing_key] = np.zeros((200,26))
            self.counterTbls[method.routing_key] = np.zeros((200,26))
            self.timestmpsTbls[method.routing_key] = [] # timestamps list
            self.thrshldsTbls[method.routing_key] = -1*np.ones(26)
        freqs,frqVals = self.parseInput(ch, method, properties,body)
        self.detectTrend(freqs,frqVals)
        
    def parseInput(self, ch, method, properties, body):
        data = json.loads(body)
        self.timestmpsTbls[method.routing_key].append(data["results"][0]['timestamp']) # get timestamp
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
        self.dataTbls[method.routing_key] = np.vstack((self.dataTbls[method.routing_key][1:,:],frqVals)) # concatenate new frequencies to already existing
        return freqs,frqVals
        
    def detectTrend(self,freqs,frqVals):  
        ind = 0
        for k in self.dataTbls[method.routing_key].T: # iterate the rows of y and perform linear regression
            slope, intercept, r, p, std_err = sps.linregress(self.x, k)
            if thrshldsTbls[method.routing_key][ind]<0: # if hasn't crossed, continue to check against updated mean and std
                Cross = self.predictCrossTime(np.mean(k)+3*np.std(k)) # predict time it will cross threshold if continues in this trend (threshold set as mean of last half hour plus 3*std of last half hour)
            else: # if it crossed, threshold is not -1 and compare to last threshold (last mean+3std that it crossed)
                Cross = self.predictCrossTime(self.thrshldsTbls[method.routing_key][ind])
            if Cross>0 and Cross<360 and slope>0: # If it will cross in less than 1 hour (number of 10 seconds in an hour)
                self.counterTbls[method.routing_key][:,ind] = np.concatenate((self.counterTbls[method.routing_key][1:,ind],[1])) # append 1 to counter
                self.thrshldsTbls[method.routing_key][ind] =  np.mean(k)+3*np.std(k) # set threshold to this moment of anomaly
                print("[%s]: %s, %s " % (method.routing_key, self.timestmpsTbls[method.routing_key][-1],frqVals[ind]))
            else:
                self.counterTbls[method.routing_key][:,ind] = np.concatenate((self.counterTbls[method.routing_key][1:,ind],[0])) # append 0 to counter
                self.thrshldsTbls[method.routing_key][ind] =  -1 # reset so that threshold is updated next time it is anomal
            if np.sum(self.counterTbls[method.routing_key][:,ind]) >= 0.8*self.counterTbls[method.routing_key].shape[0] and np.count_nonzero(k)>k.size/1.5: # if in the last N minutes it will cross in less than 1 hour in 80% of the times, alert
                if ind<len(freqs):
                    txtstr = 'trend detected in freq %d [Hz]' %freqs[ind]
                else:
                    txtstr = 'trend detected in RMS'
                self.plotDataAndRegression(k,txtstr,method.routing_key+self.timestmpsTbls[method.routing_key])
                self.counterTbls[method.routing_key][:,ind] = np.zeros(200) # make zeros to not alert many times
                print(txtstr)
            ind+=1   
            
            
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
        filename = 'test' + '.png' 
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
        plt.figure()
        plt.plot(x, y, 'o', label='original data')
        plt.plot(x, intercept + slope*x, 'r', label='fitted line')
        plt.legend()
        plt.title(TitlePlt + ", " + TitleWord + " ,R-squared: %f" % r**2)
        if toSave:
            plt.savefig(os.path.join(r"C:\Users\Ori\Desktop\Ori\ECO\intel - python\anomaly detection\test.png")) #r'C:\Users\user\Desktop\Oric\ECO\intel - python'
        plt.close()
        self.sendEmail(TitleWord,r"C:\Users\Ori\Desktop\Ori\ECO\intel - python\anomaly detection\test.png")
        return
    
    
    def linearModel(self):
        return slope*x+intercept
    
    
    def predictCrossTime(threshold = 3):
        return (threshold - intercept)/slope